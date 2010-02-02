#!/usr/bin/python
import sys
sys.path.append("../pyscraper")
import urllib, re
base = 'http://politics.guardian.co.uk'
from BeautifulSoup import BeautifulSoup
out = open('../rawdata/mpinfo/guardian-mpsurls2005.txt', 'w')
for i in range(-272, -266):
	url = '%s/person/browse/mps/az/0,,%d,00.html' % (base, i)
	fp = urllib.urlopen(url)
	index = fp.read()
	fp.close()
	m = re.findall('<a href="(/person/0[^"]*)">(.*?), (.*?)</a>', index)
	for match in m:
		url = '%s%s' % (base, match[0])
		name = '%s %s' % (match[2], match[1])
		fp = urllib.urlopen(url)
		person = fp.read()
		mpurl = fp.geturl()
                print "Parsing %s" % (mpurl)
                fp.close()
                soup = BeautifulSoup(person)
                cons_div = soup.find('div', attrs={'id':'constituency'})
                cons_link = cons_div.a
                # first link in the constituency div
		cons = re.search('<a href="([^"]*)">(.*?)</a>', str(cons_link))
		consurl, consname = cons.groups()
		out.write('%s\t%s\t%s\t%s\n' % (name, consname, mpurl, consurl))

