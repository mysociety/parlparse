#!/usr/bin/env python3

# Screen scrape list of who's standing down in the 2010 general election

# Copyright (C) 2009 Matthew Somerville
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import sys
import re

sys.path.append("../pyscraper")
from resolvemembernames import memberList

today = '2010-04-12'

page = open('../rawdata/MPs_standing_down_in_2010').read()

print('''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>''')
m = re.findall('<li><a href="([^"]*)"[^>]*>([^<]*)</a>', page)
for row in m:
    url, name = row
    name = name.decode('utf-8')
    if name in ('Iris Robinson', 'Ashok Kumar', 'David Taylor'): continue
    id, canonname, canoncons = memberList.matchfullnamecons(name, None, today) 
    pid = memberList.membertoperson(id)
    print(('  <personinfo id="%s" name="%s" standing_down="1" />' % (pid, name)).encode('iso-8859-1'))
print('</publicwhip>')

