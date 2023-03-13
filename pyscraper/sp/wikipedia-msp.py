#!/usr/bin/env python3

# Screen scrape list of links to MLAs on Wikipedia, so we can link to the articles.
# (Very slightly adapted to get MSPs instead by Mark Longair.)

# Copyright (C) 2007 Matthew Somerville
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import datetime
import os
import sys
import urllib.parse
import re

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), '..'))

from sp.resolvenames import memberList
date_today = datetime.date.today().isoformat()

# These were the original locations of these pages:
wiki_index_urls = [
    "http://en.wikipedia.org/wiki/Members_of_the_1st_Scottish_Parliament",
    "http://en.wikipedia.org/wiki/Members_of_the_2nd_Scottish_Parliament",
    "http://en.wikipedia.org/wiki/Members_of_the_3rd_Scottish_Parliament",
    "http://en.wikipedia.org/wiki/Members_of_the_4th_Scottish_Parliament",
    "http://en.wikipedia.org/wiki/Members_of_the_5th_Scottish_Parliament",
]
wikimembers  = {}

content = ''

for u in wiki_index_urls:
    leaf = re.sub('.*/','',u)
    ur = open('../../rawdata/' + leaf)
    content += ur.read()
    ur.close()

matcher = '(?ims)<a href="(/wiki/[^"]+)" [^>]*?title="[^"]+"[^>]*>([^<]+)</a>'
matches = re.findall(matcher, content)

matches.append(('/wiki/Dorothy_Grace_Elder','Dorothy-Grace Elder'))
matches.append(('/wiki/Chris_Harvie', 'Christopher Harvie'))
matches.append(('/wiki/Nicholas_Johnston', 'Nick Johnston'))

for (url, name) in matches:
    id_list = None
    try:
        id_list = memberList.match_string_somehow(name, '', '', True)
    except Exception as e:
        print(e, file=sys.stderr)
    if not id_list:
        continue

    for id_to_add in id_list:
        wikimembers[id_to_add] = url

print('''<?xml version="1.0" encoding="UTF-8"?>
<publicwhip>''')
k = sorted(wikimembers)
for id in k:
    url = urllib.parse.urljoin(wiki_index_urls[0], wikimembers[id])
    print('<personinfo id="%s" wikipedia_url="%s" />' % (id, url))
print('</publicwhip>')

wikimembers = set(wikimembers.keys())
allmembers = set([ memberList.membertoperson(id) for id in memberList.list_all_dates() ])

symdiff = allmembers.symmetric_difference(wikimembers)
if len(symdiff) > 0:
    print("Failed to get all MSPs, these ones in symmetric difference", file=sys.stderr)
    print("\n".join(symdiff), file=sys.stderr)
