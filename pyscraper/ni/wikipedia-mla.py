#!/usr/bin/env python
# -*- coding: latin-1 -*-

# Screen scrape list of links to MLAs on Wikipedia, so we can link to the articles.

# Copyright (C) 2007 Matthew Somerville
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import sys
import urlparse
import re

sys.path.extend((".", ".."))
from ni.resolvenames import memberList

wiki_index_url = "https://en.wikipedia.org/wiki/Members_of_the_4th_Northern_Ireland_Assembly"
wikimembers  = {}

# Grab pages
def read(y):
    with open('../rawdata/Members_of_the_NIA_%d' % y) as ur:
        return ur.read()
content = read(2003) + read(2007) + read(2011) + read(2016)

matches = set()

# Links from all pages
matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a></td>\s+<td><a href="/wiki/[^"]+"[^>]*>([^<]+)</a>(?: \(<b>Leader</b>\))?</td>'
matches.update(re.findall(matcher, content))

# 3rd Assembly replacements
matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a> \((?:resigned|deceased)\), replaced by <a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a></td>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>'
for m in re.findall(matcher, content):
    matches.add( (m[0], m[1], m[4]) )
    matches.add( (m[2], m[3], m[4]) )

# 4th Assembly
matcher = '<td><a href="([^"]*)" title="[^"]*">([^<]+)</a></td>\s*<th style="[^"]*">()</th>\s*<td.*?</td>\s*</tr>'
matches.update(re.findall(matcher, content))

# 4th Assembly changes
changes = re.search('Members of the 4th.*<h2><span[^>]*>Changes</span>(.*?)</html>(?s)', content).group(1)
for m in re.findall('<td>.*?<a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a>.*?</td>\s*</tr>', changes):
    matches.add((m[0], m[1], None))

for (url, name, cons) in matches:
    name = name.decode('utf-8')
    date = None
    if 'Mark Durkan' in name:
        date = '2008-01-01'
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
allmembers = set(memberList.list())
for d in ('2004-01-01', '2007-01-10', '2011-01-01', '2015-01-01', '2016-01-01', '2016-02-01'):
    allmembers |= set(memberList.list(d))

symdiff = allmembers.symmetric_difference(wikimembers)
if len(symdiff) > 0:
    print >>sys.stderr, "Failed to get all MLAs, these ones in symmetric difference"
    print >>sys.stderr, symdiff
