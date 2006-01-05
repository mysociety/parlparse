import os
import os.path
import sys
import re
from elementtree.ElementTree import ElementTree,Element

parldata='../../../parldata'
billsdir='cmpages/chgpages/bills'

sourcedir=os.path.join(parldata,billsdir)

sourcename=sys.argv[1]
sourcefilename=os.path.join(sourcedir, sourcename)

sourcefile=open(sourcefilename,'r')

source=sourcefile.read()

billpattern=re.compile('''<tr[^>]*>\s*<td[^>]*>\s*<img src="/pa/img/(?P<billtype>sqrgrn.gif|diamdrd.gif)"[^>]*></TD>\s*<TD><FONT size=\+1><A HREF="(?P<link>[^"]*)"\s*TITLE="Link to (?P<billname1>[-a-z.,A-Z0-9()\s]*?) Bill(\s*\[HL\]\s*)?"><B>(?P<billname2>[-a-z.,A-Z0-9()\s]*?) Bill(\s*\[HL\])?\s*\((?P<billno>\d+)\)\s*</B></A></FONT>([\s\S]*?)</td></tr>(?i)''')


billtreeroot=Element('billstatus')

i=0
m=billpattern.search(source)
while m:
	i=i+1
	print i
	print m.groups()
	gdict=m.groupdict()
	if gdict['billtype']=='sqrgrn.gif':
		billtype='commons'
	elif gdict['billtype']=='diamdrd.gif':
		billtype='lords'
	gdict.update([('billtype',billtype)])
	elem=Element('bill',gdict)
	billtreeroot.insert(i,elem)
	source=source[m.end():]
	m=billpattern.search(source)

billtree=ElementTree(billtreeroot)
sourcename=sourcename.replace('.html','.xml')

billtree.write('bills/%s' % sourcename)

print i