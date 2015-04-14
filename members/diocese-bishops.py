#!/usr/bin/env python2.4

import datetime
import sys
import urllib
import re

sys.path.append("../pyscraper")
from lords.resolvenames import lordsList

# Get region pages
date_today = datetime.date.today().isoformat()

print '''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>'''

ur = urllib.urlopen('https://www.churchofengland.org/links/caths.aspx')
content = ur.read()
ur.close()
matcher = '<p><a href="(.*?)".*?>(.*?)(?:\(.*?\))?</a></p>(?s)'
matches = re.findall(matcher, content)
for (url, name) in matches:
    name = name.replace('&amp;', 'and').replace('&nbsp;', ' ')
    name = re.sub('^Saint', 'St', name)
    name = re.sub('\s+', ' ', name)
    id = None
    title = 'Bishop'
    if name=='York' or name=='Canterbury':
        title = 'Archbishop'
    try:
        id = lordsList.GetLordIDfname('%s of %s' % (title,name), None, date_today)
    except Exception, e:
        print >>sys.stderr, e
    if not id:
        continue
    print '<personinfo id="%s" diocese_url="%s" />' % (id, url)
print '</publicwhip>'
