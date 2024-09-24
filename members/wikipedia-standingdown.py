#!/usr/bin/env python3

# Screen scrape list of who's standing down in the 2010 general election

# Copyright (C) 2009 Matthew Somerville
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

import re
import sys

sys.path.append("../pyscraper")
from resolvemembernames import memberList

today = "2024-05-24"

page = open("../rawdata/Members_of_the_2024_standing_down").read()
page = re.sub(
    "(?s)^.*?<caption>Members of Parliament not standing for re-election", "", page
)
page = re.sub("(?s)</table>.*", "", page)

print("""<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>""")
m = re.findall(r'<tr>\s*<td>.*?<a href="([^"]*)"[^>]*>([^<]*)</a>', page)
for row in m:
    url, name = row
    pid, canonname, canoncons = memberList.matchfullnamecons(name, None, today)
    print(('  <personinfo id="%s" name="%s" standing_down_2024="1" />' % (pid, name)))
print("</publicwhip>")
