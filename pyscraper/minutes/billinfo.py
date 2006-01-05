import elementtree
from elementtree.ElementTree import ElementTree, Element

import os
import sys
import xml
import re

cwdfiles=os.listdir(os.getcwd())
votesfiles=filter(lambda s:re.match('votes',s), cwdfiles)


topelement=Element('top')
i=1

for vf in votesfiles:
	print vf
	try:
		votetree=ElementTree(file=vf)
		voteroot=votetree.getroot()
		date=voteroot.get('date')
		acts=votetree.findall('//royal_assent/act')
		if len(acts)>0:
			assent=Element('assent',{'date': date})
			for j in range(len(acts)):
				assent.insert(j,acts[j])
			topelement.insert(i,assent)
			i=i+1
	except xml.parsers.expat.ExpatError, errorinst:
		print errorinst
		print "XML parsing error in %s" % vf, sys.exc_info()[0]
	


top=ElementTree(topelement)

top.write('allvotes.xml')

	
