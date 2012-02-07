#! /usr/bin/env python

# XXX Pagination has been introduced for the 1998-2003 pages, so any
# rescraping of those will break with this current code.

import urllib
import urlparse
import re
import time, datetime
import os

root = []
#for i in range(1997,2003):
#    root.append('http://www.niassembly.gov.uk/record/hansard_session%d.htm' % i)
for i in range(2005,2007):
    root.append('http://archive.niassembly.gov.uk/record/hansard_session%d_A.htm' % i)
root.append('http://archive.niassembly.gov.uk/record/hansard_session%d_TA.htm' % i)
for i in range(2006,2012):
    root.append('http://archive.niassembly.gov.uk/record/hansard_session%d.htm' % i)
root.append('http://www.niassembly.gov.uk/Assembly-Business/Official-Report/Reports-11-12/')

ni_dir = os.path.dirname(__file__)

def scrape_ni_day(url, filename):
    filename = '%s/../../../parldata/cmpages/ni/%s' % (ni_dir, filename)
    if not os.path.isfile(filename):
        print "NI scraping %s" % url
        ur = urllib.urlopen(url)
        fp = open(filename, 'w')
        fp.write(ur.read())
        fp.close()
        ur.close()

def scrape_new_ni():
    for url in root:
        ur = urllib.urlopen(url)
        page = ur.read()
        ur.close()

        # Manual fixes
        page = page.replace('990315', '990715').replace('000617', '000619').replace('060706', '060606')
        page = page.replace('060919', '060919p').replace('071101', '071001').replace('071102', '071002')

        match = re.findall('<a href="([^"]*(p?)(\d{6})(i?)(?:today)?\.htm)">View (?:as|in) HTML *</a>', page)
        for day in match:
            date = time.strptime(day[2], "%y%m%d")
            filename = 'ni%d-%02d-%02d%s%s.html' % (date[0], date[1], date[2], day[1], day[3])
            scrape_ni_day(urlparse.urljoin(url, day[0]), filename)

        match = re.findall('<a class="html-link" href=\'(/Assembly-Business/Official-Report/Reports-\d\d-\d\d/([^/]*)/)\'>Read now</a>', page)
        for day in match:
            # Normally 12-December-2011 but recently 23-January-2012-1030am---1100am and 1030-1100am--17-January-2012
            date_string = re.search('(\d{1,2}-[a-zA-Z]*-\d\d\d\d)', day[1]).group(1)
            date = time.strptime(date_string, "%d-%B-%Y")

            if datetime.date(*date[:3]) == datetime.date.today(): continue
            if datetime.date(*date[:3]) < datetime.date(2011, 12, 12): continue
            filename = 'ni%d-%02d-%02d.html' % date[:3]
            scrape_ni_day(urlparse.urljoin(url, day[0]), filename)

if __name__ == '__main__':
    scrape_new_ni()
