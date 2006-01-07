# vim:sw=8:ts=8:et:nowrap

import elementtree
from elementtree.ElementTree import ElementTree, Element

import os
import sys
import xml
import re

os.chdir('bills')
billsfiles=os.listdir(os.getcwd())
billsfiles=filter(lambda s:re.match('bills',s), billsfiles)

topelement=Element('top')
i=1

for bf in billsfiles:
	print bf
	try:
		billpage=ElementTree(file=bf)
		print billpage
		billpage=billpage.getroot()

		# data common to all bills on a page
		date=billroot.get('date')
		session='2005-6'

		bills=billpage.findall("//bill")
		for bill in bills:

			billname=bill.get('billname')
			billnumber=bill.get('billno')
			billlink=bill.get('link')


			links=bill.findall("//link")

			print links
		
			billinfo=Element('billprint',
				{
					'name' : billname,
					'number' : billnumber,
					'link' : billlink,
					'date' : date,
					'session': session
					}	
				)
	
			print billinfo,billname,billnumber,billlink,date,session
		
		if len(links)>0:
			for j in range(len(links)):
				link=links[j]
				type=link.get('type')
				href=link.get('link')
				topelement.set(type,href)
		print billinfo
		elementtree.ElementTree.tostring(billinfo)

		topelement.insert(i,billinfo)
		i=i+1

	except xml.parsers.expat.ExpatError, errorinst:
		print errorinst
		print "XML parsing error in %s" % vf, sys.exc_info()[0]
	

top=ElementTree(topelement)

top.write('allbillinfo.xml')

	
