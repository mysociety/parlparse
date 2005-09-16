#! /usr/bin/env python2.3
# vim:sw=8:ts=8:et:nowrap

# to do:
# Fill in the 2003-2004 gap



import os
import datetime
import re
import sys
import urllib
import string
import tempfile

import miscfuncs
import difflib
import mx.DateTime
from resolvemembernames import memberList

from xmlfilewrite import WriteXMLHeader

toppath = miscfuncs.toppath
pwcmdirs = miscfuncs.pwcmdirs
chggdir = os.path.join(pwcmdirs, "chgpages")
chgtmp = tempfile.mktemp(".xml", "pw-chgtemp-", miscfuncs.tmppath)

uniqgovposns = ["Prime Minister",
				"Chancellor of the Exchequer",
				"Lord Steward",
				"Treasurer of Her Majesty's Household",
				"Chancellor of the Duchy of Lancaster",
				"President of the Council",
				"Parliamentary Secretary to the Treasury",
				"Second Church Estates Commissioner",
				"Chief Secretary",
				"Advocate General for Scotland",
				"Deputy Chief Whip (House of Lords)",
				"Vice Chamberlain",
				"Attorney General",
				"Chief Whip (House of Lords)",
				"Lord Privy Seal",
				"Solicitor General",
				"Economic Secretary",
				"Financial Secretary",
				"Lord Chamberlain",
				"Comptroller",
				"Deputy Prime Minister",
				"Paymaster General",
				"Master of the Horse",
				]

govposns = ["Secretary of State",
			"Minister without Portfolio",
			"Minister of State",
			"Parliamentary Secretary",
			"Parliamentary Under-Secretary",
			"Assistant Whip",
			"Lords Commissioner",
			"Lords in Waiting",
			"Baronesses in Waiting",
			 ]

govdepts = ["Department of Health",
			"HM Treasury",
			"HM Household",
			"Home Office",
			"Cabinet Office",
			"Privy Council Office",
                                "Ministry of Defence",
                                "Department for Environment, Food and Rural Affairs",
                                "Department for International Development",
                                "Department for Culture, Media & Sport",
                                "Department for Constitutional Affairs",
                                "Department for Education and Skills",
                                "Office of the Deputy Prime Minister",
                                "Department for Transport",
                                "Department for Work and Pensions",
                                "Northern Ireland Office",
                                "Law Officers' Department",
                                "Department of Trade and Industry",
                                "House of Commons",
                                "Foreign & Commonwealth Office",

                                "Office of the Secretary of State for Wales",
                                "Department for Productivity, Energy and Industry",
                                "Scotland Office",

                                "No Department",
                                ]

import newlabministers2003_10_15
from newlabministers2003_10_15 import opendate


renampos = re.compile("""<td><b>
        ([^,]*),	# last name
        \s*
        ([^<(]*?)	# first name
        \s*
        (?:\(([^)]*)\))? # constituency
        </b></td><td>
        ([^,<]*)	# position
        (?:,\s*([^<]*))? # department
        (?:</td>)?\s*$(?i)""",
        re.X)

bigarray = {}
# bigarray2 = {}

# do the xml thing
def WriteXML(moffice, fout):
        fout.write('<moffice id="%s" name="%s"' % (moffice.moffid, moffice.fullname))
        if moffice.matchid:
                fout.write(' matchid="%s"' % moffice.matchid)
        #fout.write("\n")

        fout.write(' dept="%s" position="%s"' % (re.sub("&", "&amp;", moffice.dept), moffice.pos))
        if moffice.responsibility:
                fout.write(' responsibility="%s"' % re.sub("&", "&amp;", moffice.responsibility))

        fout.write(' fromdate="%s"' % moffice.sdatestart)
        if moffice.stimestart:
                fout.write(' fromtime="%s"' % moffice.stimestart)
        #fout.write("\n")

        if moffice.bopen:
                fout.write(' todate="%s"' % "9999-12-31")
        else:
                fout.write(' todate="%s"' % moffice.sdateend)
                if moffice.stimeend:
                        fout.write(' totime="%s"' % moffice.stimeend)
        #fout.write("\n")

        fout.write(' source="%s">' % moffice.sourcedoc)
        fout.write('</moffice>\n')


# NEW endeavour to get an id into all the names
#def NewSetNameMatch(cp, cpsdate):
#	cp.nmatchid = ""
#        cp.npersonid = ""
#
#	# don't match names that are in the lords
#        # (or Andrew Adonis, who at least briefly seems to be neither Lord or MP, but minister)
#	if not re.search("Duke |Lord |Baroness |Andrew Adonis|Lynda Clark", cp.fullname):
#		fullname = cp.fullname
#		cons = cp.cons
#
#		cp.nmatchid, cp.nremadename, cp.nremadecons = memberList.matchfullnamecons(fullname, cons, cpsdate)
#		if not cp.nmatchid:
#			raise Exception, 'No match: ' + fullname + " : " + (cons or "[nocons]") + " " + cpsdate + "\nOrig:" + cp.fullname
#               cp.npersonid = memberList.membertoperson(cp.nmatchid)
#
#	else:
#		cp.nremadename = cp.fullname
#		cp.nremadename = re.sub("^Rt Hon ", "", cp.nremadename)
#		cp.nremadename = re.sub(" [CO]BE$", "", cp.nremadename)
#		cp.nremadecons = ""
#
#
#	# make the structure we will sort by.  Note the ((,),) structure
#	cp.nsortobj = ((re.sub("(.*) (\S+)$", "\\2 \\1", cp.nremadename), cp.nremadecons), cpsdate)


class protooffice:
        def __init__(self, lsdatet, e, deptno):  # department number to extract multiple departments
                self.sdatet = lsdatet
                self.sourcedoc = "chgpages"

                nampos = renampos.match(e)
                if not nampos:
                        raise Exception, "renampos didn't match: '%s'" % e
                self.lasname = nampos.group(1)
		self.froname = nampos.group(2)
		self.cons = nampos.group(3)

		self.froname = re.sub(" (?:QC|MBE)?$", "", self.froname)
		self.fullname = "%s %s" % (self.froname, self.lasname)

		# special Gareth Thomas match
		if self.fullname == "Mr Gareth Thomas" and (
                (self.sdatet[0] >= '2004-04-16' and self.sdatet[0] <=
                '2004-09-20') or (self.sdatet[0] >= '2005-05-17')):
			self.cons = "Harrow West"

#                NewSetNameMatch(self, self.sdatet[0])

		pos = nampos.group(4)
		dept = nampos.group(5) or "No Department"
                responsibility = ""
                if self.sdatet[0] in bigarray and self.fullname in bigarray[self.sdatet[0]]:
                        responsibility = bigarray[self.sdatet[0]][self.fullname]

		# change of wording in 2004-11
		if dept == "Leader of the House of Commons":
			dept = "House of Commons"

                pos = re.sub(' \(Cabinet\)', '', pos)

                # separate out the departments if more than one
		if dept not in govdepts:
			self.depts = None

			# go through and try to match <dept> + " and "
			for gd in govdepts:
				dept0 = dept[:len(gd)]
				if (gd == dept0) and (dept[len(gd):len(gd) + 5] == " and "):
					dept1 = dept[len(gd) + 5:]

					# we're trying to split these strings up, but it's pretty rigid
					if dept1 in govdepts:
						self.depts = [ (pos, dept0), (pos, dept1) ]
						break
					pd1 = re.match("([^,]+),\s*(.+)$", dept1)
					if pd1 and pd1.group(2) in govdepts:
						self.depts = [ (pos, dept0), (pd1.group(1), pd1.group(2)) ]
						break
					print "Attempted match on", dept0

			if not self.depts:
                                print "No match for department: ", dept

		else:
			self.depts = [ (pos, dept) ]


		# map down to the department for this record
		self.pos = self.depts[deptno][0]
                self.responsibility = responsibility
		self.dept = self.depts[deptno][1]


	# turns the protooffice into a part of a chain
	def SetChainFront(self, fn, bfrontopen):
		if bfrontopen:
			(self.sdatestart, self.stimestart) = (opendate, None)
		else:
			(self.sdatestart, self.stimestart) = self.sdatet

		(self.sdateend, self.stimeend) = self.sdatet
		self.fn = fn
		self.bopen = True

	def SetChainBack(self, sdatet):
		self.sdatet = sdatet
		(self.sdateend, self.stimeend) = self.sdatet  # when we close it, it brings it up to the day the file changed
		self.bopen = False

	# this helps us chain the offices
	def StickChain(self, nextrec, fn):
                assert (self.sdateend, self.stimeend) < nextrec.sdatet
		assert self.bopen

		if (self.froname == nextrec.froname) and (self.lasname == nextrec.lasname) and (self.dept == nextrec.dept) and (self.pos == nextrec.pos):
                        if self.cons != nextrec.cons:
                                raise Exception, "Mismatched cons name %s %s" % (self.cons, nextrec.cons)
			(self.sdateend, self.stimeend) = nextrec.sdatet
			self.fn = fn
			return True
		return False

pus = {'Culture':1, 'Media and Tourism':1}

def p(a):
        for i in a:
                if i[0] in pus:
                        print "PUS ", i
                else:
                        print "    ", i

def SpecMins(regex, fr, sdate):
        a = re.findall(regex, fr)
        for i in a:
                specpost = i[0]
                specname = re.sub("^\s+", "", i[1])
                specname = re.sub("\s+$", "", specname)
	        if not re.search("Duke |Lord |Baroness ", specname):
#		        nmatchid, nremadename, nremadecons = memberList.matchfullnamecons(specname, '', sdate)
#		        if not nmatchid:
#        			raise Exception, 'No match: ' + specname + " : " + specpost + " : " + sdate
#                        npersonid = memberList.membertoperson(nmatchid)
                        nremadename = specname
                        nremadename = re.sub("\s+MP$", "", nremadename)
                        bigarray.setdefault(sdate, {})
                        bigarray[sdate][nremadename] = specpost
	        else:
        		nremadename = specname
        		nremadename = re.sub("^Rt Hon ", "", nremadename)
        		nremadename = re.sub(" [CO]BE$", "", nremadename)
        		nremadecons = ""
                        bigarray.setdefault(sdate, {})
                        bigarray[sdate][nremadename] = specpost

def ParsePage(fr):

	# extract the updated date and time
	frupdated = re.search('<td class="lastupdated">\s*Updated (.*?)&nbsp;(.*?)\s*</td>', fr)
	lsudate = re.match("(\d\d)/(\d\d)/(\d\d)$", frupdated.group(1))
	y2k = int(lsudate.group(3)) < 50 and "20" or "19"
	sudate = "%s%s-%s-%s" % (y2k, lsudate.group(3), lsudate.group(2), lsudate.group(1))
	sutime = frupdated.group(2)

	# extract the date on the document
	frdate = re.search(">Her Majesty's Government at\s+(.*?)\s*<", fr)
	msdate = mx.DateTime.DateTimeFrom(frdate.group(1)).date

        # is it always posted up on the day it is announced?
	if msdate != sudate and sudate != "2004-09-20" and sudate != '2005-03-10' and sudate != '2005-05-13' and sudate != '2005-06-06':
		print "Updated date is %s, but date of change %s" % (sudate, msdate)

	sdate = sudate
	stime = sutime	# or midnight if not posted properly to match the msdate

        # extract special Ministers of State and PUSes
        namebit = "<td valign='TOP'>(.*?)(?:\s+\[.*?\])?</td>"
        alsobit = "(?:[-\s]+\(?also .*?\)?)?"
        SpecMins("<TR><td width='400'><b>Minister of State \((.*?)\)</b></td>%s" % namebit, fr, sdate)
        SpecMins("<TR><td width='400'>- Mini?ster of State \((.*?)\)%s</TD>%s" % (alsobit, namebit), fr, sdate)
        SpecMins("<tr><td>- Minister of State \((.*?)\)?%s</td>%s" % (alsobit, namebit), fr, sdate)
        SpecMins("<TR><td width='400'>- Minister (?:of State )?for (.*?)%s</TD>%s" % (alsobit, namebit), fr, sdate)
        SpecMins("<tr><td>- Minister for (.*?)</td>%s" % namebit, fr, sdate)
        SpecMins("<TR><td width='400'><B>Minister of (.*?)</B>%s" % namebit, fr, sdate)
        SpecMins("<TR><td width='400'>- Parliamentary Under-Secretary (?:of state )?(?:for )?\(?(.*?)\)?%s</TD>%s(?i)" % (alsobit, namebit), fr, sdate)

	# extract the alphabetical list
	alphl = re.search("ALPHABETICAL LIST OF HM GOVERNMENT([\s\S]*?)</table>", fr).group(1)
	lst = re.split("</?tr>(?i)", alphl)

	# match the name form on each entry
	#<TD><B>Abercorn, Duke of</B></TD><TD>Lord Steward, HM Household</TD>

	res = [ ]

	luniqgov = uniqgovposns[:]
	for e1 in lst:
		e = e1.strip()
		if re.match("(?:<[^<]*>|\s)*$", e):
			continue

		# multiple entry of departments (simple inefficient method)
		for deptno in range(3):  # at most 3 offices at a time, we'll handle
			ec = protooffice((sdate, stime), e, deptno)

			# prove we've got all the posts
			if ec.pos not in govposns:
				if ec.pos in luniqgov:
					luniqgov.remove(ec.pos)
				else:
					print "Unaccounted govt position", ec.pos

			res.append(ec)

			if len(ec.depts) == deptno + 1:
				break

	return (sdate, stime), res

# this goes through all the files and chains govt positions together
def ParseGovPostsChggdir():
	govpostdir = os.path.join(chggdir, "govposts")

	gps = os.listdir(govpostdir)
	gps = [ x for x in gps if re.match(".*\.html$", x) ]
	gps.sort() # important to do in order of date

	chainprotos = [ ]
	sdatetlist = [ ]
	for gp in gps:
		#print os.path.join(govpostdir, gp)
		f = open(os.path.join(govpostdir, gp))
		fr = f.read()
		f.close()

		# get the protooffices from this file
		sdatet, proff = ParsePage(fr)


		# stick any chains we can
		proffnew = [ ]
		lsxfromincomplete = ((not chainprotos) and ' fromdateincomplete="yes"') or ''
		for prof in proff:
			bstuck = False
			for chainproto in chainprotos:
				if chainproto.bopen and (chainproto.fn != gp) and chainproto.StickChain(prof, gp):
					assert not bstuck
					bstuck = True
			if not bstuck:
				proffnew.append(prof)

		# close the chains that have not been stuck
		for chainproto in chainprotos:
			if chainproto.bopen and (chainproto.fn != gp):
				chainproto.SetChainBack(sdatet)
				#print "closing", chainproto.lasname, chainproto.sdatet

		# append on the new chains
		bfrontopen = not chainprotos
		for prof in proffnew:
			prof.SetChainFront(gp, bfrontopen)
			chainprotos.append(prof)

		sdatetlist.append(sdatet)

	# no need to close off the running cases with year 9999, because it's done in the writexml
	return chainprotos, sdatetlist

# endeavour to get an id into all the names
def SetNameMatch(cp, cpsdates):
	cp.matchid = ""
#        cp.personid = ""

	# don't match names that are in the lords
        # (or Andrew Adonis, who at least briefly seems to be neither Lord or MP, but minister)
	if not re.search("Duke |Lord |Baroness |Andrew Adonis", cp.fullname):
		fullname = cp.fullname
		cons = cp.cons

		cp.matchid, cp.remadename, cp.remadecons = memberList.matchfullnamecons(fullname, cons, cpsdates[0])
		if not cp.matchid:
			cp.matchid, cp.remadename, cp.remadecons = memberList.matchfullnamecons(fullname, cons, cpsdates[1])
		if not cp.matchid:
			raise Exception, 'No match: ' + fullname + " : " + (cons or "[nocons]") + "\nOrig:" + cp.fullname
#                cp.personid = memberList.membertoperson(cp.matchid)

	else:
		cp.remadename = cp.fullname
		cp.remadename = re.sub("^Rt Hon ", "", cp.remadename)
		cp.remadename = re.sub(" [CO]BE$", "", cp.remadename)
		cp.remadecons = ""


	# make the structure we will sort by.  Note the ((,),) structure
	cp.sortobj = ((re.sub("(.*) (\S+)$", "\\2 \\1", cp.remadename), cp.remadecons), cp.sdatestart)


# indentify open for gluing
def GlueGapBetweenDataSets(mofficegroup):
	# find the open dates at the two ends
	opendatefront = [ ]
	opendateback = [ ]

	for i in range(len(mofficegroup)):
		if mofficegroup[i][1].sdateend == opendate:
			opendateback.append(i)
		if mofficegroup[i][1].sdatestart == opendate:
			opendatefront.append(i)

	# nothing there
	if not opendateback and not opendatefront:
		return

	# glue the facets together
	for iopendateback in range(len(mofficegroup) - 1, -1, -1):
		if mofficegroup[iopendateback][1].sdateend == opendate:
			iopendatefrontm = None
			for iopendatefront in range(len(mofficegroup)):
				if (mofficegroup[iopendatefront][1].sdatestart == opendate and
					mofficegroup[iopendateback][1].pos == mofficegroup[iopendatefront][1].pos and
					mofficegroup[iopendateback][1].dept == mofficegroup[iopendatefront][1].dept):
					iopendatefrontm = iopendatefront

			#if iopendatefrontm == None:
			#	rp = mofficegroup[iopendateback]
			#	print "%s\tpos='%s'\tdept='%s'" % (rp[1].remadename, rp[1].pos, rp[1].dept)
			assert iopendatefrontm != None

			# glue the two things together
			mofficegroup[iopendatefrontm][1].sdatestart = mofficegroup[iopendateback][1].sdatestart
			mofficegroup[iopendatefrontm][1].stimestart = None
			mofficegroup[iopendatefrontm][1].sourcedoc = mofficegroup[iopendateback][1].sourcedoc + " " + mofficegroup[iopendatefrontm][1].sourcedoc
			del mofficegroup[iopendateback]

	for iopendatefront in range(len(mofficegroup)):
		assert not (mofficegroup[iopendatefront][1].sdatestart == opendate)
	#	rp = mofficegroup[iopendatefront]
	#	print "\t%s\tpos='%s'\tdept='%s'" % (rp[1].remadename, rp[1].pos, rp[1].dept)



# main function that sticks it together
def ParseGovPosts():

	# get from our two sources (which unfortunately don't overlap, so they can't be merged)
	# We have a gap from 2003-10-15 to 2004-06-06 which needs filling !!!
	porres = newlabministers2003_10_15.ParseOldRecords()
	cpres, sdatetlist = ParseGovPostsChggdir()

	# allocate ids and merge lists
	rpcp = []

	# run through the office in the documented file
	moffidn = 1;
	for po in porres:

		cpsdates = [po.sdatestart, po.sdateend]
		if cpsdates[1] == opendate:
			cpsdates[1] = newlabministers2003_10_15.dateofinfo

		SetNameMatch(po, cpsdates)
		po.moffid = "uk.org.publicwhip/moffice/%d" % moffidn
		rpcp.append((po.sortobj, po))
		moffidn += 1

	# run through the offices in the new code
	assert moffidn < 1000
	moffidn = 1000
	for cp in cpres:
		cpsdates = [cp.sdatestart, cp.sdateend]
		if cpsdates[0] == opendate:
			cpsdates[0] = sdatetlist[0][0]

		SetNameMatch(cp, cpsdates)
		cp.moffid = "uk.org.publicwhip/moffice/%d" % moffidn
		rpcp.append((cp.sortobj, cp))
		moffidn += 1


	# (this would be a good place for matching and gluing overlapping duplicates together)
	rpcp.sort()
        old = ''
        for i in range(0, len(rpcp)-1):
                for j in range(i+1, len(rpcp)):
                        if not len(rpcp[i]) or not len(rpcp[j]): continue
                        old = rpcp[i][1]
                        new = rpcp[j][1]
                        if new.remadename==old.remadename and old.dept==new.dept and old.pos==new.pos and old.sdateend==new.sdatestart and old.stimeend==new.stimestart:
        			new.sdatestart = old.sdatestart
                                new.stimestart = old.stimestart
                		new.sourcedoc = old.sourcedoc + " " + new.sourcedoc
        			rpcp[i] = ()

	# now we batch them up into the person groups
	mofficegroups = [ ]
	prevrpm = None
	for rp in rpcp:
                if rp == ():
                        continue
		if not prevrpm or prevrpm[0][0] != rp[0][0]:
			mofficegroups.append([ ])
		mofficegroups[-1].append(rp)
		prevrpm = rp


	# now look for open ends
	for mofficegroup in mofficegroups:
		GlueGapBetweenDataSets(mofficegroup)


	fout = open(chgtmp, "w")
	WriteXMLHeader(fout)
	fout.write("<publicwhip>\n")

	fout.write("\n")
	for lsdatet in sdatetlist:
		fout.write('<chgpageupdates date="%s" time="%s"/>\n' % lsdatet)


	# output the file, a tag round the groups of offices which form a single person
	for mofficegroup in mofficegroups:
		fout.write("\n<ministerofficegroup>\n")
		for rp in mofficegroup:
			WriteXML(rp[1], fout)
		fout.write("</ministerofficegroup>\n")

	fout.write("</publicwhip>\n\n")
	fout.close();

	# copy file over to its place
	# ...

	# we get the members directory and overwrite the file that's there
	# (in future we'll have to load and check match it)
	membersdir = os.path.normpath(os.path.abspath(os.path.join("..", "members")))
	ministersxml = os.path.join(membersdir, "ministers.xml")

	#print "Over-writing %s;\nDon't forget to check it in" % ministersxml
	if os.path.isfile(ministersxml):
		os.remove(ministersxml)
	os.rename(chgtmp, ministersxml)


