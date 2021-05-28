#! /usr/bin/python

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
        url = url.encode('utf-8')
        #print " reading " + url
        ur = urllib.urlopen(url)
        sr = ur.read()
        ur.close()

	if ur.code == 404:
		print "failed to fetch %s - skipping" % url
		continue

        # write the marker telling us which page this comes from
        lt = time.gmtime()
        fout.write('<page url="%s" scrapedate="%s" scrapetime="%s"/>\n' % \
            (url, time.strftime('%Y-%m-%d', lt), time.strftime('%X', lt)))

        sr = re.sub('<p([^>]*)/>', r'<p\1></p>', sr)
        soup_mp = BeautifulSoup.BeautifulSoup(sr)
        try:
            page = soup_mp.find('h1').findNextSiblings(lambda t: t.name != 'div')
        except:
            print 'Problem with ' + url.decode('utf-8')
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
#       for i in range(0,len(hrsections)):
#           print "------"
#           print hrsections[i]
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
def GlueAllType(pcmdir, cmindex, fproto, forcescrape):
    if not os.path.isdir(pcmdir):
        os.mkdir(pcmdir)

    for dnu in cmindex:
        # make the filename
        dgf = os.path.join(pcmdir, (fproto % dnu[0]))

        if forcescrape:
            if os.path.isfile(dgf):
                os.remove(dgf)

        # hansard index page
        url = dnu[1]

        # If already got file, skip
        if os.path.exists(dgf):
            continue

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
    corrections = {
        '/pa/cm/cmregmem/060214/memi02.htm': '2006-02-13',
        '/pa/cm/cmregmem/051101/memi02.htm': '2005-11-01',
        '/pa/cm/cmregmem/925/part1contents.htm': '2013-01-18',
    }
    urls = []
    idxurl = 'https://www.parliament.uk/mps-lords-and-offices/standards-and-financial-interests/parliamentary-commissioner-for-standards/registers-of-interests/register-of-members-financial-interests/'
    ur = urllib.urlopen(idxurl)
    content = ur.read()
    ur.close()

    soup = BeautifulSoup.BeautifulSoup(content)
    soup = soup.find(attrs='main-body').find('ul')
    ixurls = [urlparse.urljoin(idxurl, ix['href']) for ix in soup.findAll('a', href=True)]

    for ixurl in ixurls:
        ur = urllib.urlopen(ixurl)
        content = ur.read()
        ur.close()

        # <B>14&nbsp;May&nbsp;2001&nbsp;(Dissolution)</B>
        content = content.replace("&nbsp;", " ")

        # 2016-03-11 bad HTML, missing '<tr>'
        content = re.sub(
            "<td>\s*</td>\s*<td nowrap><b>Register of Members' Financial Interests - as at 7th March 2016</b></td>",
            '<tr>\g<0>',
            content)

        soup = BeautifulSoup.BeautifulSoup(content)

        if soup.find(text=re.compile('^Contents$(?i)')):
            # An immediate register page.
            # Remove comments
            content = re.sub('<!--.*?-->(?s)', '', content)

            alldates = re.findall('(?i)<(?:b|strong)>(\d+[a-z]* [A-Z][a-z]* \d\d\d\d)', content)
            if len(alldates) != 1:
                print alldates
                raise Exception, 'Date match failed, expected one got %d\n%s' % (len(alldates), url)

            date = mx.DateTime.DateTimeFrom(alldates[0]).date
            if (date, ixurl) not in urls:
                urls.append((date, ixurl))
        elif re.search('Session 201[79]|Session 20[2-9]', content):
            allurl_soups = soup.findAll('a', href=re.compile("(memi02|part1contents|/contents\.htm)"))
            for url_soup in allurl_soups:
                url = url_soup['href']
                url = urlparse.urljoin(ixurl, url)
                date = re.sub('^.*(\d\d)(\d\d)(\d\d).*', r'20\1-\2-\3', url)
                url_path = urlparse.urlparse(url)[2]
                if url_path in corrections:
                    date = corrections[url_path]
                if (date, url) not in urls:
                    urls.append((date, url))
        else:
            allurl_soups = soup.findAll('a', href=re.compile("(memi02|part1contents|/contents\.htm)"))
            for url_soup in allurl_soups:
                row_content = url_soup.findParent('tr').renderContents()
                url = url_soup['href']
                #print url
                if url == '060324/memi02.htm':
                    # fix broken URL
                    url = '/pa/cm/cmregmem/' + url

                url = urlparse.urljoin(ixurl, url)

                alldates = re.findall('\d+[a-z]*\s+[A-Z][a-z]*\s+\d\d\d\d', row_content, re.DOTALL)
                if len(alldates) != 1:
                    print alldates
                    raise Exception, 'Date match failed, expected one got %d\n%s' % (len(alldates), url)

                url_path = urlparse.urlparse(url)[2]
                if url_path in corrections:
                    date = corrections[url_path]
                else:
                    alldates[0] = re.sub('\s+', ' ', alldates[0])
                    date = mx.DateTime.DateTimeFrom(alldates[0]).date

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
def RegmemPullGluePages(datefrom, dateto, forcescrape):
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

    # discard URLs with dates outside of specified range
    urls = [x for x in urls if x[0] >= datefrom and x[0] <= dateto]

    # bring in and glue together parliamentary register of members interests and put into their own directories.
    # third parameter is a regexp, fourth is the filename (%s becomes the date).
    GlueAllType(pwcmregmem, urls, 'regmem%s.html', forcescrape)

    # urls = FindLordRegmemPages()
    # GlueAllType(pwldregmem, urls, 'regmem%s.html', forcescrape)

if __name__ == '__main__':
    RegmemPullGluePages(False)
