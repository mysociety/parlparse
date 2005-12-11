#! /usr/bin/python2.3
# vim:sw=8:ts=8:et:nowrap
# -*- coding: latin-1 -*-

import sys
import re
import os
import string
from resolvemembernames import memberList

from miscfuncs import ApplyFixSubstitutions
from miscfuncs import IsNotQuiet
from contextexception import ContextException

from splitheadingsspeakers import StampUrl



################## the start of lords resolve names
import xml.sax

# more tedious stuff to do: "earl of" and "sitting as" cases

titleconv = {  'L.':'Lord',
			   'B.':'Baroness',
			   'Abp.':'Arch-bishop',
			   'Bp.':'Bishop',
			   'V.':'Viscount',
			   'E.':'Earl',
			   'D.':'Duke',
			   'M.':'Marquess',
			   'C.':'Countess',
			   'Ly.':'Lady',
			}

hontitles = [ 'Lord  ?Bishop', 'Lord', 'Baroness', 'Viscount', 'Earl', 'Countess', 'Archbishop', 'Duke', 'Lady' ]
hontitleso = string.join(hontitles, '|')

honcompl = re.compile('(?:The\s+(%s)|(%s) \s*(.*?))(?:\s+of\s+(.*))?$' % (hontitleso, hontitleso))

class LordsList(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.lords={} # ID --> MPs
		self.lordnames={} # "lordnames" --> lords
		self.parties = {} # constituency --> MPs

		parser = xml.sax.make_parser()
		parser.setContentHandler(self)
		#parser.parse("../members/all-lords.xml")
		#parser.parse("../members/all-lords-extras.xml")
		parser.parse("../members/peers-ucl.xml")


		# set this to the file if we are to divert unmatched names into a file
		# for collection
		self.newlordsdumpfname = "../members/newlordsdump.xml"
		# self.newlordsdumpfname = None  # suppresses the feature
		self.newlordsdumpfile = None  # file opens only on first use
		self.newlordsdumped = [ ]

	# check that the lordofnames that are blank happen after the ones that have values
	# where the lordname matches
	def startElement(self, name, attr):
		""" This handler is invoked for each XML element (during loading)"""
		if name == "lord":
			if self.lords.get(attr["id"]):
				raise Exception, "Repeated identifier %s in members XML file" % attr["id"]
			self.lords[attr["id"]] = attr

			lname = attr["lordname"] or attr["lordofname"]
			lname = re.sub("\.", "", lname)
			assert lname
			self.lordnames.setdefault(lname, []).append(attr.copy())

	def DumpUnknownLord(self, ltitle, llordname, llordofname, stampurl):
		assert self.newlordsdumpfname
		if not self.newlordsdumpfile:
			if IsNotQuiet():
				print "Opening", self.newlordsdumpfname
			self.newlordsdumpfile = open(self.newlordsdumpfname, "w")

		# dump new names to a file
		if (ltitle, llordname, llordofname) not in self.newlordsdumped:
			if IsNotQuiet():
				print "Dumping:", (ltitle, llordname, llordofname)
			assert not re.search("^\s|\s$", llordname) and not re.search("^\s|\s$", llordofname)
			self.newlordsdumpfile.write('<lord id="uk.org.publicwhip/lord/"\n\thouse="lords"\n\ttitle="%s" lordname="%s" lordofname="%s"\n\tsource="%s"\n/>\n' % \
									    (ltitle, llordname, llordofname, stampurl.reps()))
			self.newlordsdumpfile.flush()
			self.newlordsdumped.append((ltitle, llordname, llordofname))
		assert False
		return "notyetlisted"

	# main matchinf function
	def GetLordID(self, ltitle, llordname, llordofname, loffice, stampurl, sdate, bDivision):
		if ltitle == "Lord Bishop":
			ltitle = "Bishop"
		llordofname = string.replace(llordofname, ".", "")
		llordname = string.replace(llordname, ".", "")
		llordname = string.replace(llordname, "&#039;", "'")

		lname = llordname or llordofname
		assert lname
		lmatches = self.lordnames.get(lname, [])

		# match to successive levels of precision for identification
		res = [ ]
		for lm in lmatches:
			if lm["title"] != ltitle:  # mismatch title
				continue
			if llordname and llordofname: # two name case
				if (lm["lordname"] == llordname) and (lm["lordofname"] == llordofname):
					assert lm["fromdate"] <= sdate <= lm["todate"]
					res.append(lm)
				continue
			if lm["lordname"] and lm["lordofname"]: # compare to double name
				continue

			# single name cases
			lmlname = lm["lordname"] or lm["lordofname"]
			if (llordname and lm["lordname"]) or (llordofname and lm["lordofname"]):
				if lname == lmlname:
					if lm["fromdate"] <= sdate <= lm["todate"]:
						res.append(lm)
					else:
						assert ltitle == "Bishop"
				continue

			# cross-match
			if lname == lmlname:
				if lm["fromdate"] <= sdate <= lm["todate"]:
					print "cm---", ltitle, lm["lordname"], lm["lordofname"], llordname, llordofname
					res.append(lm)
				else:
					assert bDivision

		if not res:
			print "Unknown Lord", (ltitle, llordname, llordofname, stampurl)
			raise ContextException("unknown lord", stamp=stampurl, fragment=lname)

		assert len(res) == 1

		return res[0]["id"]


	def GetLordIDfname(self, name, loffice, sdate, stampurl=None):
		hom = honcompl.match(name)
		if not hom:
			print "format failure on '" + name + "'"
			raise ContextException("lord name format failure", stamp=stampurl, fragment=name)

		# now we have a speaker, try and break it up
		ltit = hom.group(1)
		if not ltit:
			ltit = hom.group(2)
			lname = hom.group(3)
		else:
			lname = ""
		ltit = re.sub("  ", " ", ltit)
		lplace = ""
		if hom.group(4):
			lplace = re.sub("  ", " ", hom.group(4))

		lname = re.sub("^De ", "de ", lname)
		return lordlist.GetLordID(ltit, lname, lplace, loffice, stampurl, sdate, False)


	def MatchRevName(self, fss, sdate, stampurl):
		assert fss
		lfn = re.match('(.*?)(?: of (.*?))?, ?((?:L|B|Abp|Bp|V|E|D|M|C|Ly)\.?)$', fss)
		if not lfn:
			print "$$$%s$$$" % fss
			raise ContextException("No match of format in MatchRevName", stamp=stampurl, fragment=fss)
		ltitle = titleconv[lfn.group(3)]
		llordname = string.replace(lfn.group(1), ".", "")
		llordname = string.replace(llordname, "&#039;", "'")
		llordname = re.sub("^De ", "de ", llordname)
		llordofname = ""
		if lfn.group(2):
			llordofname = string.replace(lfn.group(2), ".", "")

		return lordlist.GetLordID(ltitle, llordname, llordofname, "", stampurl, sdate, True)

# class instantiation
lordlist = LordsList()


################## the end of lords resolve names










# marks out center types bold headings which are never speakers
respeaker = re.compile('(<center><b>[^<]*</b></center>|<b>[^<]*</b>(?:\s*:)?)(?i)')
respeakerb = re.compile('<b>\s*([^<]*?),?\s*</b>(\s*:)?(?i)')
respeakervals = re.compile('([^:(]*?)\s*(?:\(([^:)]*)\))?(:)?$')

renonspek = re.compile('division|contents|amendment(?i)')
reboldempty = re.compile('<b>\s*</b>(?i)')

regenericspeak = re.compile('the (?:deputy )?chairman of committees|the deputy speaker|the clerk of the parliaments|the lord chancellor|the noble lord said(?i)')
#retitlesep = re.compile('(Lord|Baroness|Viscount|Earl|The Earl of|The Lord Bishop of|The Duke of|The Countess of|Lady)\s*(.*)$')



def LordsFilterSpeakers(fout, text, sdate):
	stampurl = StampUrl(sdate)

	# setup for scanning through the file.
	for fss in respeaker.split(text):

		# strip off the bolds tags
		# get rid of non-bold stuff
		bffs = respeakerb.match(fss)
		if not bffs:
			fout.write(fss)
			stampurl.UpdateStampUrl(fss)
			continue

		# grab a trailing colon if there is one
		fssb = bffs.group(1)
		if bffs.group(2):
			fssb = fssb + ":"

		# empty bold phrase
		if not re.search('\S', fssb):
			continue

		# division/contents/amendment which means this is not a speaker
		if renonspek.search(fssb):
			fout.write(fss)
			continue

		# part of quotes as an inserted title in an amendment
		if re.match('["[]', fssb):
			fout.write(fss)
			continue

		# another title type (all caps)
		if not re.search('[a-z]', fssb):
			fout.write(fss)
			continue

		# start piecing apart the name by office and leadout type
		namec = respeakervals.match(fssb)
		if not namec:
			print fssb
			raise ContextException("bad format", stamp=stampurl, fragment=fssb)

		if namec.group(2):
			name = namec.group(2)
			loffice = namec.group(1)
		else:
			name = namec.group(1)
			loffice = None
		colon = namec.group(3)
		if not colon:
			colon = ""

		# get rid of some standard ones
		if re.match('noble lords|a noble lord|a noble baroness|the speaker(?i)', name):
			fout.write('<speaker speakerid="%s">%s</speaker>' % ('no-match', name))
			continue
		if regenericspeak.match(name):
			fout.write('<speaker speakerid="%s">%s</speaker>' % ('no-match', name))
			continue

		lsid = lordlist.GetLordIDfname(name, loffice=loffice, sdate=sdate, stampurl=stampurl)

		fout.write('<speaker speakerid="%s" speakername="%s" colon="%s">%s</speaker>' % (lsid, name, colon, name))





