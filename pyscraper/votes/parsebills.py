# vim:sw=8:ts=8:et:nowrap

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

# Some files have commented out older entries, for the moment I think
# it is best to ignore them -- FD

xmlcommentreplace=re.compile('''<!--[\s\S]*?-->''')
source=xmlcommentreplace.sub('',source)

def linktype(desc):
	if re.match('Explanatory Note(s)?', desc):
		return 'explanatory note'
	
	if re.match('Amendment(s)?',desc):
		return 'amendment'
	
	if re.match('Standing Committee Proceedings',desc):
		return 'standing committee'

	if re.match('Petitions against the(?P<billname>[-a-z.,A-Z0-9()\s]*?)Bill',desc):
		return 'petitions'

	return 'unknown'

def makelement(gdict):
	rest=gdict.pop('rest')
	elem=Element('bill',gdict)

	pat=re.compile('\s*<br>(\s|&nbsp;)*<a\s*href="(?P<href>[^"]*?)"\s*title="(?P<title>[^"]*?)"\s*>\s*<b>\s*<i>(?P<desc>[^<]*?)</i>\s*</b>\s*</a>(?i)')

	pos=0
	#print rest
	mobj=pat.match(rest)
	while mobj and len(rest)>0:
		pos=pos+1
		linkdict=mobj.groupdict()
		desc=linkdict.pop('desc')
		desc=re.sub('\s+',' ',desc)
		desc.strip()
		type=linktype(desc)
		linkdict.update({'desc':desc, 'type':type})
		link=Element('link',linkdict)

		elem.insert(pos,link)

		rest=rest[mobj.end():]
		mobj=pat.match(rest)

		#print elementtree.ElementTree.tostring(elem)

	print "remainder=%s\n" % rest

	return elem
		
billpattern=re.compile('''<tr[^>]*>\s*<td[^>]*>\s*<img src="/pa/img/(?P<billtype>sqrgrn.gif|diamdrd.gif)"[^>]*></TD>\s*<TD><FONT size=\+1><A HREF="(?P<link>[^"]*)"\s*TITLE="Link to (?P<billname1>[-a-z.,A-Z0-9()\s]*?) Bill(\s*\[HL\]\s*)?"><B>(?P<billname2>[-a-z.,A-Z0-9()\s]*?) Bill(\s*\[HL\])?\s*\((?P<billno>\d+)\)\s*</B></A></FONT>(?P<rest>[\s\S]*?)</td></tr>(?i)''')


billtreeroot=Element('billstatus')

i=0
m=billpattern.search(source)
while m:
	i=i+1
	print i
	#print m.groups()
	gdict=m.groupdict()
	if gdict['billtype']=='sqrgrn.gif':
		billtype='commons'
	elif gdict['billtype']=='diamdrd.gif':
		billtype='lords'
	gdict.update([('billtype',billtype)])

	elem=makelement(gdict)
	billtreeroot.insert(i,elem)

	source=source[m.end():]
	m=billpattern.search(source)

billtree=ElementTree(billtreeroot)
sourcename=sourcename.replace('.html','.xml')

billtree.write('bills/%s' % sourcename)

print i
