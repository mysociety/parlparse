#!/usr/local/bin/python2.4

import urllib
import urlparse
import re
import time
import os

root = ['http://www.niassembly.gov.uk/theassembly/hansard.htm', 'http://www.niassembly.gov.uk/transitional/plenary/hansard.htm']
for i in range(1,19):
	root.append('http://www.niassembly.gov.uk/record/vol%dcontents.htm' % i)

for url in root:
	ur = urllib.urlopen(url)
	page = ur.read()
	ur.close()
	match = re.findall('"((?:Plenary/|minutes_of_proceedings_|reports/)?(p?)(\d{6})(i?)\.htm)"', page)
	for day in match:
		url_day = urlparse.urljoin(url, day[0])
		date = time.strptime(day[2], "%y%m%d")
		filename = '../../../parldata/cmpages/ni/ni%d-%02d-%02d%s%s.html' % (date[0], date[1], date[2], day[1], day[3])
		if not os.path.isfile(filename):
			print "Scraping %s" % url_day
			ur = urllib.urlopen(url_day)
			fp = open(filename, 'w')
			fp.write(ur.read())
			fp.close()
			ur.close()
