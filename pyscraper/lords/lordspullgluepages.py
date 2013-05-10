# vim:sw=8:ts=8:et:nowrap

import sys
import urllib
import urlparse
import re
import os.path
import xml.sax
import time
import string
import tempfile
import mx.DateTime
import traceback
import miscfuncs
toppath = miscfuncs.toppath
pwcmdirs = miscfuncs.pwcmdirs
tempfilename = miscfuncs.tempfilename

from miscfuncs import NextAlphaString, AlphaStringToOrder
from pullgluepages import ReplicatePatchToNewScrapedVersion, CmIndexFromNewPage

# Pulls in all the debates, written answers, etc, glues them together, removes comments,
# and stores them on the disk

# we should put lordspages into cmpages as another directory, and move
# all patch files into a set of directories parallel to the html and xml containing directories


# index file which is created
pwlordsindex = os.path.join(toppath, "lordindex.xml")

# output directories (everything of one day in one file).
pwlordspages = os.path.join(pwcmdirs, "lordspages")


# this does the main loading and gluing of the initial day debate
# files from which everything else feeds forward

# gets the index file which we use to go through the pages
class LoadLordsIndex(xml.sax.handler.ContentHandler):
	def __init__(self, lpwcmindex):
		self.res = []
		if not os.path.isfile(lpwcmindex):
			return
		parser = xml.sax.make_parser()
		parser.setContentHandler(self)
		parser.parse(lpwcmindex)

	def startElement(self, name, attr):
		if name == "lordsdaydeb":
			ddr = (attr["date"], attr["url"], int(attr["type"]))
			if self.res and self.res[-1][0] == ddr[0]:
				if self.res[-1][2] > ddr[2]:
					return
				self.res.pop()
			self.res.append(ddr)

# extract the table of contents from an index page
def ExtractIndexContents(urlx, sdate):
	urx = urllib.urlopen(urlx)
        lktex = urx.read()
        urx.close()
        lktex = re.sub('^.*?<a name="contents">\s*</a>\s*(?s)', '', lktex)
        lktex = re.sub('^(.*?)<hr(?: ?/)?>.*$(?s)', r'\1', lktex)
        lktex = re.sub('<!--.*?-->(?s)', '', lktex)

	# get the links
        res = re.findall('<h[23] align="?center"?><a href="([^"]*?\.htm)#[^"]*"(?: shape="rect")?>([^<]*)</a>\s*</h[23]>(?is)', lktex)
        if not res:
                res = re.findall('<p><a href\s*=\s*"([^"]*?\.htm)#[^"]*"><h3><center>((?:<!|[^<])*)(?:</center>|</h3>)+\s*</a></p>(?i)', lktex)
	if not res:
		print "no links found from day index page", urlx
		raise Exception, "no links"
	return res


def GlueByNext(fout, urla, urlx, sdate):
	# put out the indexlink for comparison with the hansardindex file
	lt = time.gmtime()
	fout.write('<pagex url="%s" scrapedate="%s" scrapetime="%s"/>\n' % \
			(urlx, time.strftime('%Y-%m-%d', lt), time.strftime('%X', lt)))

        if urla[0] == 'http://www.publications.parliament.uk/pa/ld200607/ldhansrd/text/61130-0001.htm':
                urla = [urla[0]]
        if urla[0] == 'http://www.publications.parliament.uk/pa/ld200607/ldhansrd/text/70125-0001.htm':
                urla = urla[2:]
        if urla[0] == 'http://www.publications.parliament.uk/pa/ld200506/ldhansrd/vo050517/text/50517-02.htm':
                urla.insert(0, 'http://www.publications.parliament.uk/pa/ld200506/ldhansrd/vo050517/text/50517-01.htm')
        if urla[0] == 'http://www.publications.parliament.uk/pa/ld200405/ldhansrd/vo041123/text/41123-02.htm':
                urla.insert(0, 'http://www.publications.parliament.uk/pa/ld200405/ldhansrd/vo041123/text/41123-01.htm')
        if urla[0] == 'http://www.publications.parliament.uk/pa/ld200708/ldhansrd/text/80722-0001.htm':
                urla = [urla[0]]
        if urla[0] == 'http://www.publications.parliament.uk/pa/ld200708/ldhansrd/text/81104-0001.htm':
                urla = [urla[0]]
        if urla[0] == 'http://www.publications.parliament.uk/pa/ld201011/ldhansrd/text/110119-0001.htm':
                urla = [urla[0]]
        # Missing header/footer, need to be able to find 2nd HTML page
        if urla[0] == 'http://www.publications.parliament.uk/pa/ld201213/ldhansrd/text/130327-0001.htm':
                urla.insert(1, 'http://www.publications.parliament.uk/pa/ld201213/ldhansrd/text/130327-0002.htm')

	# loop which scrapes through all the pages following the nextlinks
	# knocking off the known links as we go in case a "next page" is missing.
	while urla:
		url = urla[0]
		ur = urllib.urlopen(url)
		sr = ur.read()
		ur.close();

		# write the marker telling us which page this comes from
		fout.write('<page url="' + url + '"/>\n')

		# To cope with post 2006-07-03, turn <body> into <hr>
                sr = re.sub('<body><notus', '<body><hr><notus', sr)
                #sr = re.sub('<body><br>', '<body><hr><br>', sr)
                sr = re.sub('<body><h3 align="center"', '<body><hr><h3 align="center"', sr)
                sr = re.sub('<body><p>', '<body><hr><p>', sr)

                # post 2006-09
                sr = re.sub("</?mekonParaReplace[^>]*>", "", sr)
                sr = re.sub("</?mekonHrefReplace[^>]*>", "", sr)
                sr = re.sub("<meta[^>]*>", "", sr)
                sr = re.sub('<a name="([^"]*)" />', r'<a name="\1"></a>', sr) # Should be WriteCleanText like for Commons?
                sr = re.sub('(<a href="[^"]*&amp)(">.*?)(</a>)(;.*?)([ .,<])', r'\1\4\2\4\3\5', sr)
                sr = re.sub('<div id="maincontent1">\s+<notus', '<hr> <notus', sr)
                sr = re.sub('<div id="maincontent1">\s*<link[^>]*>\s*<notus', '<hr> <notus', sr) # New 2008-10...
                sr = re.sub('<div id="maincontent1">\s*<link[^>]*>\s*<h1', '<hr> <h1', sr) # New 2011-01...
                sr = re.sub('<div id="maincontent">(?:\s*<table.*?</table>)?(?s)', '', sr)
                if url in ('http://www.publications.parliament.uk/pa/ld200607/ldhansrd/text/71001w0001.htm',
                    'http://www.publications.parliament.uk/pa/ld201011/ldhansrd/text/110118-0001.htm',
                    ):
                        sr = re.sub('Daily Hansard</span></div>', 'Daily Hansard</span></div> <hr>', sr)
                # To deal with missing header/footer on this day. Might need removing if they come back?
                if url == 'http://www.publications.parliament.uk/pa/ld201213/ldhansrd/text/121105-wms0001.htm' or re.match('http://www.publications.parliament.uk/pa/ld201213/ldhansrd/text/130327', url):
                        sr = re.sub('<body>', '<body> <hr>', sr)
			
                # For 2013-02-26, 2013-05-08, so far
                sr = re.sub('<div id="content-small"><!--end', '<div id="content-small"> <hr><!--end', sr)

                # post 2008-03, stupid duplication of <b>s
                sr = re.sub('<b>((?:<a name="[^"]*"></a>)*)<b>', '\\1<b>', sr)
                sr = re.sub('</b><!--[^>]*--></b>', '</b>', sr)

		# split by sections
		hrsections = re.split('<hr[^>]*>(?i)', sr)

		# this is the case for debates on 2003-03-13 page 30
		# http://www.publications.parliament.uk/pa/cm200203/cmhansrd/vo030313/debtext/30313-32.htm
		if len(hrsections) == 1:
                        # special case for the Grand committee proceedings on 2011-03-23
			if url == 'http://www.publications.parliament.uk/pa/ld201011/ldhansrd/text/110323-gc0001.htm':
				miscfuncs.WriteCleanText(fout, sr, False)
			else:
				# print len(hrsections), 'page missing', url
				# fout.write('<UL><UL><UL></UL></UL></UL>\n')
				print "Bridging the empty page at %s" % url
			urla = urla[1:]
			continue

                # Lords Written Statements on 2006-07-05, for example, sadly
                if len(hrsections) == 2:
                        miscfuncs.WriteCleanText(fout, hrsections[1], False)
                
		# write the body of the text
		for i in range(1, len(hrsections) - 1):
			miscfuncs.WriteCleanText(fout, hrsections[i], False)

		# find the lead on with the footer
		footer = hrsections[-1]

		# the files are sectioned by the <hr> tag into header, body and footer.
		nextsectionlink = re.findall('<\s*a\s+href\s*=\s*"?(.*?)"?\s*>next section</a>(?i)', footer)
		if len(nextsectionlink) > 1:
			raise Exception, "More than one Next Section!!!"
		if not nextsectionlink:
			urla = urla[1:]
			if urla:
				print "Bridging the missing next section link at %s" % url
		else:
			url = urlparse.urljoin(url, nextsectionlink[0])
			# Specific case on 2011-02-23
			if url == 'http://www.publications.parliament.uk/pa/ld201011/ldhansrd/text/110323-wms0001.htm':
				url = 'http://www.publications.parliament.uk/pa/ld201011/ldhansrd/text/110323-gc0001.htm'	
			# this link is known
			if (len(urla) > 1) and (urla[1] == url):
				urla = urla[1:]
			# unknown link, either there's a gap in the urla's or a mistake.
			else:
				for uo in urla:
					if uo == url:
						print string.join(urla, "\n")
						print "\n\n"
						print url
						print "\n\n"
						raise Exception, "Next Section misses out the urla list"
				urla[0] = url

	pass  #endwhile urla



###############
# main function
###############
def LordsPullGluePages(datefrom, dateto, bforcescrape):
	# make the output firectory
	if not os.path.isdir(pwlordspages):
		os.mkdir(pwlordspages)

	# load the index file previously made by createhansardindex
	clordsindex = LoadLordsIndex(pwlordsindex)

	# scan through the directory and make a mapping of all the copies for each
	lddaymap = { }
	for ldfile in os.listdir(pwlordspages):
		mnums = re.match("daylord(\d{4}-\d\d-\d\d)([a-z]*)\.html$", ldfile)
		if mnums:
			lddaymap.setdefault(mnums.group(1), []).append((AlphaStringToOrder(mnums.group(2)), mnums.group(2), ldfile))
		elif os.path.isfile(os.path.join(pwlordspages, ldfile)):
			print "not recognized file:", ldfile, " in ", pwlordspages

        scrape = []

        # Post 2010 election scraping done directly, not via index
        if dateto >= '2010-05-18':
                if datefrom > '2010-05-18':
                        date = mx.DateTime.DateTimeFrom(datefrom)
                else:
                        date = mx.DateTime.DateTimeFrom('2010-05-18')
                while date.date <= dateto and date < mx.DateTime.today():
                        for recordType, link in CmIndexFromNewPage(date, 'lords'):
                                scrape.append((date.date, link, recordType))
                        date += mx.DateTime.DateTimeDelta(1)

	# loop through the index of each lord line.
	for dnu in clordsindex.res:
		# implement date range
		if dnu[0] < datefrom or dnu[0] > dateto:
			continue
                scrape.append(dnu)

        for dnu in scrape:
		# make the filename
		dgflatestalpha, dgflatest = "", None
		if dnu[0] in lddaymap:
			ldgf = max(lddaymap[dnu[0]])
			dgflatestalpha = ldgf[1]
			dgflatest = os.path.join(pwlordspages, ldgf[2])
                dgfnextalpha = NextAlphaString(dgflatestalpha)
		ldgfnext = 'daylord%s%s.html' % (dnu[0], dgfnextalpha)
		dgfnext = os.path.join(pwlordspages, ldgfnext)
		assert not dgflatest or os.path.isfile(dgflatest)
		assert not os.path.isfile(dgfnext)
                dgfnextstem = "%s%s" % (dnu[0], dgfnextalpha)
                dgflateststem = "%s%s" % (dnu[0], dgflatestalpha)

		# hansard index page
		urlx = dnu[1]

		# if not force scrape then we may choose to scrape it anyway
		# where the header doesn't match
		if not bforcescrape and dgflatest:
			fpgx = open(dgflatest, "r")
			pgx = fpgx.readline()
			fpgx.close()
			if pgx:
				pgx = re.findall('<pagex url="([^"]*)"[^/]*/>', pgx)
				if pgx:
					if pgx[0] == urlx:
						continue

		# make the message
		print dnu[0], (dgflatest and 'RE-scraping' or 'scraping'), re.sub(".*?ldhansrd/", "", urlx)

		# The different sections are often all run together
		# with the title of written answers in the middle of a page.
                icont = ExtractIndexContents(urlx, dnu[0])
		# this gets the first link (the second [0][1] would be it's title.)
		urla = [ ]
		for iconti in icont:
			uo = urlparse.urljoin(urlx, iconti[0])
			if (not urla) or (urla[-1] != uo):
				urla.append(uo)

		# now we take out the local pointer and start the gluing
		# we could check that all our links above get cleared.
                try:
                        dtemp = open(tempfilename, "w")
		        GlueByNext(dtemp, urla, urlx, dnu[0])
		        dtemp.close()
	        except Exception, e:
                        print e   
			traceback.print_exc()
		        print "Problem with %s, moving on" % dnu[0]
		        continue

		# now we have to decide whether it's actually new and should be copied onto dgfnext.
		if dgflatest: # the removal of \r makes testing sizes unreliable -- : and os.path.getsize(tempfilename) == os.path.getsize(dgflatest):
			# load in as strings and check matching
			fdgflatest = open(dgflatest)
			sdgflatest = fdgflatest.readlines()
			fdgflatest.close()

			fdgfnext = open(tempfilename)
			sdgfnext = fdgfnext.readlines()
			fdgfnext.close()

			# first line contains the scrape date
			if sdgflatest[1:] == sdgfnext[1:]:
				print "  matched with:", dgflatest
				continue

		ReplicatePatchToNewScrapedVersion('lordspages', dgflateststem, dgflatest, dgfnext, dgfnextstem)

		print dnu[0], (dgflatest and 'RE-scraped' or 'scraped'), re.sub(".*?cmpages/", "", dgfnext)
		os.rename(tempfilename, dgfnext)



