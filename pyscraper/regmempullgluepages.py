#! /usr/bin/python
# vim:sw=8:ts=8:et:nowrap

import sys
import urllib
import urlparse
import re
import os.path
import time
import mx.DateTime
import tempfile
import BeautifulSoup

import miscfuncs
toppath = miscfuncs.toppath

# Pulls in register of members interests, glues them together, removes comments,
# and stores them on the disk

# output directories
pwcmdirs = os.path.join(toppath, "cmpages")
pwcmregmem = os.path.join(pwcmdirs, "regmem")
pwldregmem = os.path.join(pwcmdirs, "ldregmem")

tempfilename = tempfile.mktemp("", "pw-gluetemp-", miscfuncs.tmppath)

# Scrape everything from the contents page
def GlueByContents(fout, url_contents, regmemdate):
	ur = urllib.urlopen(url_contents)
	sr = ur.read()
	ur.close()

        soup = BeautifulSoup.BeautifulSoup(sr)
        mps = soup.find('a', attrs={'name':'A'}).parent.findNextSiblings('p')
        for p in mps:
		url = urlparse.urljoin(url_contents, p.a['href'])
                #print " reading " + url
	        ur = urllib.urlopen(url)
	        sr = ur.read()
	        ur.close()

		# write the marker telling us which page this comes from
                lt = time.gmtime()
                fout.write('<page url="%s" scrapedate="%s" scrapetime="%s"/>\n' % \
			(url, time.strftime('%Y-%m-%d', lt), time.strftime('%X', lt)))

                sr = re.sub('<p([^>]*)/>', r'<p\1></p>', sr)
                soup_mp = BeautifulSoup.BeautifulSoup(sr)
                page = soup_mp.find('h1').findNextSiblings(lambda t: t.name != 'div')
                page = '\n'.join([ str(p) for p in page ]) + '\n'
                miscfuncs.WriteCleanText(fout, page)

def GlueByNext(fout, url, regmemdate):
	# loop which scrapes through all the pages following the nextlinks
        starttablewritten = False
        matcheddate = False
        if re.search("ldreg", url):
            matcheddate = True
        sections = 0
	while 1:
		#print " reading " + url
		ur = urllib.urlopen(url)
		sr = ur.read()
		ur.close();

                sections += 1

                # check date
                if not matcheddate:
                        dateinpage = re.search("current as at\s*<[bB]>(.*)</[bB]>", sr)
                        if not dateinpage:
                                raise Exception, 'Not found date marker'
                        dateinpage = dateinpage.group(1).replace("&nbsp;", " ")
                        dateinpage = mx.DateTime.DateTimeFrom(dateinpage).date
                        if dateinpage != regmemdate:
                                raise Exception, 'Date in page is %s, expected %s - update the URL list in regmempullgluepages.py' % (dateinpage, regmemdate)
                        matcheddate = True

		# write the marker telling us which page this comes from
                lt = time.gmtime()
                fout.write('<page url="%s" scrapedate="%s" scrapetime="%s"/>\n' % \
			(url, time.strftime('%Y-%m-%d', lt), time.strftime('%X', lt)))

		# split by sections
		hrsections = re.split(
                        '<TABLE border=0 width="90%">|' +
                        '</TABLE>\s*?<!-- end of variable data -->|' +
                        '<!-- end of variable data -->\s*</TABLE>' +
                        '(?i)', sr)

		# write the body of the text
#		for i in range(0,len(hrsections)):
#                        print "------"
#                        print hrsections[i]
                text = hrsections[2] 
                m = re.search('<TABLE .*?>([\s\S]*)</TABLE>', text)
                if m:
                        text = m.group(1)
                m = re.search('<TABLE .*?>([\s\S]*)', text)
                if m:
                        text = m.group(1)
                if not starttablewritten and re.search('COLSPAN=4', text):
                        text = "<TABLE>\n" + text
                        starttablewritten = True
                miscfuncs.WriteCleanText(fout, text)

		# find the lead on with the footer
		footer = hrsections[3]

                nextsectionlink = re.findall('<A href="([^>]*?)"><IMG border=0\s+align=top src="/pa/img/next(?:grn|drd).gif" ALT="next page"></A>', footer)
		if not nextsectionlink:
			break
		if len(nextsectionlink) > 1:
			raise Exception, "More than one Next Section!!!"
		url = urlparse.urljoin(url, nextsectionlink[0])

        # you evidently didn't find any links
        assert sections > 10
        
        fout.write('</TABLE>')


# read through our index list of daydebates
def GlueAllType(pcmdir, cmindex, fproto, deleteoutput):
	if not os.path.isdir(pcmdir):
		os.mkdir(pcmdir)

	for dnu in cmindex:
		# make the filename
		dgf = os.path.join(pcmdir, (fproto % dnu[0]))

                if deleteoutput:
                    if os.path.isfile(dgf):
                            os.remove(dgf)
                else:
                    # hansard index page
                    url = dnu[1]

                    # If already got file and it's recent, skip
                    if os.path.exists(dgf) and dnu[0] > '2010-09-01':
                        continue
                    # if we already have got the file, check the pagex link agrees in the first line
                    # no need to scrape it in again
                    if os.path.exists(dgf):
                            fpgx = open(dgf, "r")
                            pgx = fpgx.readline()
                            fpgx.close()
                            if pgx:
                                    pgx = re.findall('<page url="([^"]*)"[^/]*/>', pgx)
                                    if pgx:
                                            if pgx[0] == url:
                                                    #print 'skipping ' + url
                                                    continue
                            #print 'RE-scraping ' + url
                    else:
                            pass
                            #print 'scraping ' + url

                    # now we take out the local pointer and start the gluing
                    dtemp = open(tempfilename, "w")
                    if dnu[0] > '2010-09-01':
                        GlueByContents(dtemp, url, dnu[0])
                    else:
                        GlueByNext(dtemp, url, dnu[0])

                    # close and move
                    dtemp.close()
                    os.rename(tempfilename, dgf)

# Get index of all regmem pages from the index
def FindRegmemPages():
        urls = []
        idxurl = 'http://www.publications.parliament.uk/pa/cm/cmregmem.htm'
        ur = urllib.urlopen(idxurl)
        content = ur.read()
        ur.close()

        soup = BeautifulSoup.BeautifulSoup(content)
        soup = [ table.find('table') for table in soup.findAll('table') if table.find('table') ]
        ixurls = [urlparse.urljoin(idxurl, ix['href']) for ix in soup[0].findAll('a', href=True)]

        for ixurl in ixurls:
            ur = urllib.urlopen(ixurl)
            content = ur.read()
            ur.close();

            # Remove comments
            content = re.sub('<!--.*?-->(?s)', '', content)

            # <A HREF="/pa/cm199900/cmregmem/memi02.htm">Register
            #              of Members' Interests November 2000</A>
            allurls = re.findall('<a href="([^>]*)">(?i)', content)
            for url in allurls:
                    #print url
                    if url.find("memi02") >= 0 or url.find("part1contents") >= 0:
                            if url == '060324/memi02.htm':
                                # fix broken URL
                                url = '/pa/cm/cmregmem/' + url

                            url = urlparse.urljoin(ixurl, url)

                            # find date
                            ur = urllib.urlopen(url)
                            content = ur.read()
                            ur.close();
                            # <B>14&nbsp;May&nbsp;2001&nbsp;(Dissolution)</B>
                            content = content.replace("&nbsp;", " ")
                            alldates = re.findall('(?i)<(?:b|strong)>(\d+[a-z]* [A-Z][a-z]* \d\d\d\d)', content)
                            if len(alldates) != 1:
                                    print alldates
                                    raise Exception, 'Date match failed, expected one got %d\n%s' % (len(alldates), url)

                            date = mx.DateTime.DateTimeFrom(alldates[0]).date

                            #print date, url
                            if (date, url) not in urls:
                                urls.append((date, url))

        return urls

def FindLordRegmemPages():
        urls = [('2004-10-01', 'http://www.publications.parliament.uk/pa/ld200304/ldreg/reg01.htm')]
        ixurl = 'http://www.publications.parliament.uk/pa/ld/ldreg.htm'
        ur = urllib.urlopen(ixurl)
        content = ur.read()
        ur.close();

        allurls = re.findall('<a href="([^>]*reg01[^>]*)">.*?position on (.*?)\)</a>(?i)', content)
        for match in allurls:
                url = urlparse.urljoin(ixurl, match[0])
                date = mx.DateTime.DateTimeFrom(match[1]).date
                urls.append((date, url))

        return urls

###############
# main function
###############
def RegmemPullGluePages(deleteoutput):
	# make the output directory
	if not os.path.isdir(pwcmdirs):
		os.mkdir(pwcmdirs)
                
        # When these were hardcoded originally:
        # http://www.publications.parliament.uk/pa/cm/cmhocpap.htm#register
        # urls = [ 
        #        ('2004-01-31', 'http://www.publications.parliament.uk/pa/cm/cmregmem/memi02.htm'),
        #        ('2003-12-04', 'http://www.publications.parliament.uk/pa/cm200203/cmregmem/memi02.htm')
        #        ]
        
        urls = FindRegmemPages();

	# bring in and glue together parliamentary register of members interests and put into their own directories.
	# third parameter is a regexp, fourth is the filename (%s becomes the date).
	GlueAllType(pwcmregmem, urls, 'regmem%s.html', deleteoutput)

        # urls = FindLordRegmemPages()
	# GlueAllType(pwldregmem, urls, 'regmem%s.html', deleteoutput)

if __name__ == '__main__':
        RegmemPullGluePages(False)

