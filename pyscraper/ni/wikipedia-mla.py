#!/usr/bin/env python3

# Screen scrape list of links to MLAs on Wikipedia, so we can link to the articles.

# Copyright (C) 2007 Matthew Somerville
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import os
import sys
import urllib.parse
import re

file_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
sys.path.insert(0, file_dir)
from ni.resolvenames import memberList

wiki_index_url = "https://en.wikipedia.org/wiki/Members_of_the_4th_Northern_Ireland_Assembly"
wikimembers  = {}

# Grab pages
def read(y):
    with open(file_dir + '/../rawdata/Members_of_the_NIA_%d' % y) as ur:
        return ur.read()
content = read(2003) + read(2007) + read(2011) + read(2016) + read(2017) + read(2022)

matches = set()

# Links from all pages
matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a>[^<]*</td>\s+<td><a href="/wiki/[^"]+"[^>]*>([^<]+)</a>\s*</td>'
matches.update(re.findall(matcher, content))

# 4-6th Assembly
matcher = '<td><a href="([^"]*)" title="[^"]*">([^<]+)</a>[^<]*</td>\s*<t[hd] style="[^"]*">()\s*</t[hd]>\s*<td.*?\s*</td>\s*</tr>'
matches.update(re.findall(matcher, content))

# 4-6th Assembly changes
changes = re.findall('(?s)<h2><span[^>]*>MLAs by constituency.*?<h2><span[^>]*>Changes(.*?)</html>', content)
for change in changes:
    for m in re.findall('''(?x)
            <td[ ]style="width:[ ]2px;[^>]*>\s*</td>\s* # Thin column of party colour
            <td[^>]*>.*?\s*</td>\s* # Party name
            <td><a[ ]href="(/(?:wiki|w)/[^"]+)"[^>]*>([^<]+)</a>.*?\s*</td>\s* # Outgoing
            <td>(?:<a[ ]href="(/(?:wiki|w)/[^"]+)"[^>]*>([^<]+)</a>|<i>Vacant</i>).*?\s*</td> # Incoming''', change):
        matches.add((m[0], m[1], None))
        if m[2]: matches.add((m[2], m[3], None))

for (url, name, cons) in matches:
    date = None
    if 'Mark Durkan' in name:
        date = '2008-01-01'
    pid = memberList.match_person(name, date)
    wikimembers[pid] = url

print('''<?xml version="1.0" encoding="UTF-8"?>
<publicwhip>''')
k = sorted(wikimembers)
for id in k:
    url = urllib.parse.urljoin(wiki_index_url, wikimembers[id])
    print('<personinfo id="%s" wikipedia_url="%s" />' % (id, url))
print('</publicwhip>')

wikimembers = set(wikimembers.keys())
allmembers = set(memberList.list(fro='2004-01-01'))
symdiff = allmembers.symmetric_difference(wikimembers)
if len(symdiff) > 0:
    print("Failed to get all MLAs, these ones in symmetric difference", file=sys.stderr)
    print(symdiff, file=sys.stderr)
