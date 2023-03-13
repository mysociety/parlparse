#!/usr/bin/env python3

# Screen scrape list of links to Lords on Wikipedia, so we can link to the articles.

# The Public Whip, Copyright (C) 2003 Francis Irving and Julian Todd
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import datetime
import sys
import urllib.parse
import re

sys.path.append("../pyscraper")
from lords.resolvenames import lordsList

# Get region pages
wiki_index_url = "http://en.wikipedia.org/wiki/Members_of_the_House_of_Lords"
date_today = datetime.date.today().isoformat()
wikimembers = {}

# Grab page 
ur = open('../rawdata/Members_of_the_House_of_Lords')
content = ur.read()
ur.close()

#<td><a href="/wiki/Geoffrey_Russell%2C_4th_Baron_Ampthill" title="Geoffrey Russell, 4th Baron Ampthill">The Lord Ampthill</a></td>
matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)" [^>]*?title="([^"]+)"[^>]*>([^<]+)</a>\s*</td>';
matches = re.findall(matcher, content)
for (url, title, name) in matches:
    id = None
    try:
        id = lordsList.GetLordIDfname(name, None, date_today)
    except Exception as e:
        continue

    if not id:
        continue
    wikimembers[id] = url

print('''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>''')
for id, url in sorted(wikimembers.items()):
    url = urllib.parse.urljoin(wiki_index_url, url)
    print('<personinfo id="%s" wikipedia_url="%s" />' % (id, url))
print('</publicwhip>')

#print "len: ", len(wikimembers)

# Check we have everybody -- ha! not likely yet
#allmembers = set(memberList.currentmpslist())
#symdiff = allmembers.symmetric_difference(wikimembers)
#if len(symdiff) > 0:
#    print >>sys.stderr, "Failed to get all MPs, these ones in symmetric difference"
#    print >>sys.stderr, symdiff


