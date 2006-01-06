# vim:sw=8:ts=8:et:nowrap

import elementtree
from elementtree.ElementTree import ElementTree, Element

import os
import sys
import xml
import re

os.chdir('bills')
billsfiles=os.listdir(os.getcwd())

topelement=Element('top')
i=1

for bf in billsfiles:
	print bf
	try:
		billtree=ElementTree(file=bf)
		billroot=billtree.getroot()
		date=billroot.get('date')

		links=billtree.findall("//link")
		links=filter(lambda e:e.get('type',default='unknown')=='unknown',links)
		if len(links)>0:
			for j in range(len(links)):
				topelement.insert(j,links[j])
			i=i+1

	except xml.parsers.expat.ExpatError, errorinst:
		print errorinst
		print "XML parsing error in %s" % vf, sys.exc_info()[0]
	

top=ElementTree(topelement)

top.write('allbillinfo.xml')

	
