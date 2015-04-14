#!/usr/bin/env python
# -*- coding: latin-1 -*-

# Screen scrape list of links to MLAs on Wikipedia, so we can link to the articles.

# Copyright (C) 2007 Matthew Somerville
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import datetime
import sys
import urlparse
import re

sys.path.extend((".", ".."))
from ni.resolvenames import memberList
date_today = datetime.date.today().isoformat()

# Get region pages
wiki_index_url = "http://en.wikipedia.org/wiki/Members_of_the_Northern_Ireland_Assembly_elected_in_2011"
wikimembers  = {}

# Grab pages
with open('../rawdata/Members_of_the_NIA_2007') as ur:
    content = ur.read()
with open('../rawdata/Members_of_the_NIA_2011') as ur:
    content += ur.read()

matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a></td>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>';
matches = re.findall(matcher, content)
matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a> \((?:resigned|deceased)\), replaced by <a href="/wiki/[^"]+"[^>]*>[^<]+</a></td>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>';
matches.extend( re.findall(matcher, content) )
matcher = '<tr>\s+<td><a href="/wiki/[^"]+"[^>]*>[^<]+</a> \((?:resigned|deceased)\), replaced by <a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a></td>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>';
matches.extend( re.findall(matcher, content) )
matcher = '<td><a href="([^"]*)" title="[^"]*">([^<]+)</a></td>\s*<th style="[^"]*">()</th>\s*<td.*?</td>\s*</tr>'
matches.extend( re.findall(matcher, content) )

for (url, name, cons) in matches:
    name = name.decode('utf-8')
    date = None
    if 'Mark Durkan' in name:
        date = '2008-01-01'
    elif 'Mark H. Durkan' in name:
        date = '2012-01-01'
    pid = memberList.match_person(name, date)
    wikimembers[pid] = url

print '''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>'''
k = wikimembers.keys()
k.sort()
for id in k:
    url = urlparse.urljoin(wiki_index_url, wikimembers[id])
    print '<personinfo id="%s" wikipedia_url="%s" />' % (id, url)
print '</publicwhip>'

wikimembers = set(wikimembers.keys())
allmembers = set( memberList.list() )
symdiff = allmembers.symmetric_difference(wikimembers)
if len(symdiff) > 0:
    print >>sys.stderr, "Failed to get all MLAs, these ones in symmetric difference"
    print >>sys.stderr, symdiff


