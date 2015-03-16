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
wiki_index_url = "http://en.wikipedia.org/wiki/Members_of_the_Northern_Ireland_Assembly_elected_in_2007"
wikimembers  = {}
current_members = []

# Grab page 
ur = open('../rawdata/Members_of_the_NIA_2007')
content = ur.read()
ur.close()

matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a></td>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>';
matches = re.findall(matcher, content)
matcher = '<tr>\s+<td><a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a> \((?:resigned|deceased)\), replaced by <a href="/wiki/[^"]+"[^>]*>[^<]+</a></td>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>';
matches.extend( re.findall(matcher, content) )
matcher = '<tr>\s+<td><a href="/wiki/[^"]+"[^>]*>[^<]+</a> \((?:resigned|deceased)\), replaced by <a href="(/wiki/[^"]+)"[^>]*>([^<]+)</a></td>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>';
matches.extend( re.findall(matcher, content) )
for (url, name, cons) in matches:
    name = name.decode('utf-8')
    try:
        id, str = memberList.match(name, date_today)
        current_members.append(id)
    except Exception, e:
        try:
            id, str = memberList.match(name, '2011-01-01')
        except Exception, e:
            # For the resigned/died MLAs, use an earlier date
            id, str = memberList.match(name, '2007-01-01')
            #print >>sys.stderr, e
    pid = memberList.membertoperson(id)
    wikimembers[pid] = url

print '''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>'''
k = wikimembers.keys()
k.sort()
for id in k:
    url = urlparse.urljoin(wiki_index_url, wikimembers[id])
    print '<personinfo id="%s" wikipedia_url="%s" />' % (id, url)
print '</publicwhip>'

wikimembers = set(current_members)
allmembers = set( memberList.list() )
symdiff = allmembers.symmetric_difference(wikimembers)
if len(symdiff) > 0:
    print >>sys.stderr, "Failed to get all MLAs, these ones in symmetric difference"
    print >>sys.stderr, symdiff


