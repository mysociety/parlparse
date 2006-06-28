#!/usr/bin/env python2.4
# -*- coding: latin-1 -*-
# $Id: bbcconv.py,v 1.4 2005/03/25 23:33:35 theyworkforyou Exp $

# Screen scrape list of links to Lords on Wikipedia, so we can link to the articles.

# The Public Whip, Copyright (C) 2003 Francis Irving and Julian Todd
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import datetime
import sys
import urllib
import urlparse
import re
import sets

sys.path.append("../pyscraper")
sys.path.append("../pyscraper/lords")
import re
from resolvemembernames import memberList

# Get region pages
wiki_index_url = "http://en.wikipedia.org/wiki/MPs_elected_in_the_UK_general_election,_2005"
date_today = datetime.date.today().isoformat()
wikimembers  = sets.Set() # for storing who we have found links for

print '''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>'''

# Grab page 
ur = open('../rawdata/Members_of_the_House_of_Commons')
content = ur.read()
ur.close()

# <tr>
#<td><a href="/wiki/West_Ham_%28UK_Parliament_constituency%29" title="West Ham (UK Parliament constituency)">West Ham</a></td>
#<td><a href="/wiki/Lyn_Brown" title="Lyn Brown">Lyn Brown</a></td>
#<td>Labour</td>
matcher = '<tr>\s+<td><a href="/wiki/[^"]+" title="[^"]+">([^<]+)</a></td>\s+<td><a href="(/wiki/[^"]+)" title="[^"]+">([^<]+)</a></td>';
matches = re.findall(matcher, content)
for (cons, url, name) in matches:
    id = None
    try:
        (id, canonname, canoncons) = memberList.matchfullnamecons(name, cons, date_today)
    except Exception, e:
        print >>sys.stderr, e

    if not id:
        continue

    url = urlparse.urljoin(wiki_index_url, url)
    print '<memberinfo id="%s" wikipedia_url="%s" />' % (id, url)
    wikimembers.add(id)

print '</publicwhip>'

#print "len: ", len(wikimembers)

# Check we have everybody -- ha! not likely yet
#allmembers = sets.Set(memberList.currentmpslist())
#symdiff = allmembers.symmetric_difference(wikimembers)
#if len(symdiff) > 0:
#    print >>sys.stderr, "Failed to get all MPs, these ones in symmetric difference"
#    print >>sys.stderr, symdiff


