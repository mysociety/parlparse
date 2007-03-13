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
import xml.sax
import shutil

import miscfuncs
import difflib
import mx.DateTime
from resolvemembernames import memberList
from resolvelordsnames import lordsList

from xmlfilewrite import WriteXMLHeader

toppath = miscfuncs.toppath
pwcmdirs = miscfuncs.pwcmdirs
chggdir = os.path.join(pwcmdirs, "chgpages")
chgtmp = tempfile.mktemp(".xml", "pw-chgtemp-", miscfuncs.tmppath)

membersdir = os.path.normpath(os.path.abspath(os.path.join("..", "members")))
ministersxml = os.path.join(membersdir, "ministers.xml")
peoplexml = os.path.join(membersdir, "people.xml") # generated from ministers.xml by personsets.py
   # used in


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
				"Master of the Horse"
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
                                "Deputy Prime Minister",
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
                                "Wales Office",
                                "Department for Communities and Local Government",
                                "No Department",
                                ]


ppsdepts = govdepts + [ "Minister Without Portfolio",
				"Minister without Portfolio",
				"Minister without Portfolio and Party Chair",
				"Prime Minister",
				"Prime Minister's Office",
				"Leader of the House of Commons",
                                "Leader of the House of Lords",
				]
ppsnondepts = [ "HM Official Opposition", "Leader of the Opposition" ]

import newlabministers2003_10_15
from newlabministers2003_10_15 import opendate

renampos = re.compile("""<td>\s*<b>
        ([^,]*),	# last name
        \s*
        ([^<\(]*?)	# first name
        \s*
        (?:\(([^)]*)\))? # constituency
        </b></td><td>
        ([^,<]*)	# position
        (?:,\s*([^<]*))? # department
        (?:</td>)?\s*$(?i)""",
        re.X)

bigarray = {}
# bigarray2 = {}

def ApplyPatches(filein, fileout, patchfile):
	shutil.copyfile(filein, fileout)
	status = os.system("patch --quiet %s <%s" % (fileout, patchfile))
	if status == 0:
		return True
	print "blanking out failed patch %s" % patchfile
	print "---- This should not happen, therefore assert!"
	assert False

# do the xml thing
def WriteXML(moffice, fout):
        fout.write('<moffice id="%s" name="%s"' % (moffice.moffid, moffice.fullname))  # should be cleaning up here, but aren't
        if moffice.matchid:
                fout.write(' matchid="%s"' % moffice.matchid)
        #fout.write("\n")

        # more runtime cleaning up of the xml rather than using a proper function
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




class protooffice:
	def __init__(self):
		pass

	def SelCteeproto(self, lsdatet, name, cons, committee):
		self.sdatet = lsdatet
		self.sourcedoc = "chgpages/selctee"
		self.dept = committee
		if not re.search("Committee", committee):
			self.dept += " Committee"
		self.pos = ""
		self.responsibility = ""
		if re.search("\(Chairman\)", name):
			self.pos = "Chairman"
		name = re.sub(" \(Chairman\)?$", "", name)

		self.fullname = re.sub("^Mrs? ", "", name).strip()
		# Why doesn't this work with an accent?

		if re.match("Si.n Simon$", self.fullname):
			self.fullname = "Sion Simon"
		if re.match("Si.n C\. James$", self.fullname):
			self.fullname = "Sian C James"
#		if re.match("Anne Picking$", self.fullname):
#			self.fullname = "Anne Moffat"
                self.cons = re.sub("&amp;", "&", cons)
                # Or this?
                if re.match("Ynys M.n", cons):
                        self.cons = "Ynys Mon"

	def PPSproto(self, lsdatet, name, master, dept):
		self.sdatet = lsdatet
		self.sourcedoc = "chgpages/privsec"

		nameMatch = re.match('(.*?)\s*\(([^)]*)\)\s*$', name)
		self.fullname = nameMatch.group(1).strip()
		self.fullname = re.sub("^Mrs? ", "", self.fullname)
		if re.match("Si.n Simon$", self.fullname):
			self.fullname = "Sion Simon"
		self.cons = re.sub("&amp;", "&", nameMatch.group(2))

		# map down to the department for this record
		self.pos = "PPS"
		master = re.sub('\s+,', ',', master)
		self.responsibility = master
		if dept == "Prime Minister":
			dept = "Prime Minister's Office"
		self.dept = dept


	def GovPostproto(self, lsdatet, e, deptno):  # department number to extract multiple departments
		self.sdatet = lsdatet
		self.sourcedoc = "chgpages/govposts"

		nampos = renampos.match(e)
		if not nampos:
			raise Exception, "renampos didn't match: '%s'" % e
		self.lasname = nampos.group(1)
		self.froname = nampos.group(2)
		self.cons = nampos.group(3)
		if self.cons == 'MP for Worcester':
			self.cons = None # Can only be one

		self.froname = re.sub("^Rt Hon\s+|^Mrs?\s+", "", self.froname)
		self.froname = re.sub("\s+(?:QC|[COM]BE)?$", "", self.froname)
		self.fullname = "%s %s" % (self.froname, self.lasname)

		# sometimes a bracket of constituency gets through, when the name hasn't been reversed
		mbrackinfullname = re.search("([^\(]*?)\s*\(([^\)]*)\)$", self.fullname)
		if mbrackinfullname:
			self.fullname = mbrackinfullname.group(1)
			assert not self.cons
			self.cons = mbrackinfullname.group(2)

		# special Gareth Thomas match
		if self.fullname == "Gareth Thomas" and (
                (self.sdatet[0] >= '2004-04-16' and self.sdatet[0] <=
                '2004-09-20') or (self.sdatet[0] >= '2005-05-17')):
			self.cons = "Harrow West"

		if self.cons == "Worcs.":
                        self.cons = None # helps make the stick-chain work

		if self.fullname == "Lord Bach of Lutterworth":
			self.fullname = "Lord Bach"

		# special Andrew Adonis match
		if self.fullname == "Andrew Adonis" and self.sdatet[0][:7] == "2005-05":
			self.fullname = "Lord Adonis"

		pos = nampos.group(4).strip()
		dept = (nampos.group(5) or "No Department").strip()
                dept = re.sub("\s+", " ", dept)
		responsibility = ""
		if self.sdatet[0] in bigarray and self.fullname in bigarray[self.sdatet[0]]:
			responsibility = bigarray[self.sdatet[0]][self.fullname]

		# change of wording in 2004-11
		if dept == "Leader of the House of Commons":
			dept = "House of Commons"
		# change of wording in 2006-04
		if pos == "Lord Commissioner":
			pos = "Lords Commissioner"

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
				print "\n***No match for department: '%s'\n" % dept

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
		if (self.sdateend, self.stimeend) >= nextrec.sdatet:
			print "\n\n *** datetime not incrementing\n\n"
			print self.sdateend, self.stimeend, nextrec.sdatet
			print fn
			assert False
		assert self.bopen

		if (self.fullname, self.dept, self.pos, self.responsibility) == (nextrec.fullname, nextrec.dept, nextrec.pos, nextrec.responsibility):
			consCheckA = self.cons
			if consCheckA:
				consCheckA = memberList.canonicalcons(consCheckA, self.sdateend)
			consCheckB = nextrec.cons
			if consCheckB:
				consCheckB = memberList.canonicalcons(consCheckB, nextrec.sdatet[0])
			if consCheckA != consCheckB:
				raise Exception, "Mismatched cons name %s %s" % (self.cons, nextrec.cons)
			(self.sdateend, self.stimeend) = nextrec.sdatet
			self.fn = fn
			return True
		return False


def SpecMins(regex, fr, sdate):
        a = re.findall(regex, fr)
        for i in a:
                specpost = i[0]
                specname = re.sub("^\s+", "", i[1])
                specname = re.sub("\s+$", "", specname)
                nremadename = specname
                nremadename = re.sub("^Rt Hon ", "", nremadename)
                if not re.search("Duke |Lord |Baroness ", specname):
                        nremadename = re.sub("\s+MP$", "", nremadename)
                        nremadename = re.sub(" [COM]BE$", "", nremadename)
                bigarray.setdefault(sdate, {})
                if specpost == "Universitites":
                        specpost = "Universities"
                bigarray[sdate][nremadename] = specpost


def ParseSelCteePage(fr, gp):
        if gp == "selctee0100_2006-09-29.html":
                return "SKIPTHIS", None
        else:
                frupdated = re.search('<td class="lastupdated">\s*Updated (.*?)(?:&nbsp;| )(.*?)\s*</td>', fr)
                lsudate = re.match("(\d\d)/(\d\d)/(\d\d\d\d)$", frupdated.group(1))
                if lsudate:
                    sudate = "%s-%s-%s" % (lsudate.group(3), lsudate.group(2), lsudate.group(1))
                else:
                    lsudate = re.match("(\d\d)/(\d\d)/(\d\d)$", frupdated.group(1))
                    y2k = int(lsudate.group(3)) < 50 and "20" or "19"
                    sudate = "%s%s-%s-%s" % (y2k, lsudate.group(3), lsudate.group(2), lsudate.group(1))
                sutime = frupdated.group(2)
	# extract the date on the document
	frdate = re.search("Select Committee\s+Membership at\s+(.*?)\s*<(?i)", fr)
        if frdate:
                msdate = mx.DateTime.DateTimeFrom(frdate.group(1)).date
                if sudate != msdate:
                        if sudate in ['2006-05-19', '2006-07-05', '2006-11-17']:
                                sudate = msdate
                        elif msdate in ['2007-02-08']:
                                sudate = msdate
                        elif sudate > '2007-01-26':
                                print "mismatch of dates;", msdate, "updated:", sudate

        sdate = sudate
        stime = sutime
        res = [ ]

        committees = re.findall("<a\s+href=(?:'|\")(?:http://hcl2\.hclibrary/sections/hcio/mmc/selcom\.asp)?#\d+(?:'|\")>(.*?)</a></I>", fr, re.I | re.S)
        committees = map(lambda x: re.sub("\s+", " ", x).replace("&amp;", "&"), committees)
        found = { }

        # XXX: This is slow, speed it up!
        list = re.findall("<tr>\s*<td (?:colspan='3' bgcolor='#F1ECE4'|bgcolor=#f1ece4 colSpan=3)(?: height=\"\d+\")?>(?:<b>)?<font size=\+1>(?:<b>)?(?:<I>)?<A\s+NAME='?\d+'?></a>\s*([^<]*?)\s*(?:</b>)?</font>.*?</tr>\s*((?:<tr>\s*<td(?: height=\"19\")?>.*?</td>\s*<td(?: height=\"19\")?>.*?</td>\s*<td(?: height=\"19\")?>.*?</td>\s*</tr>\s*)+)<tr>\s*<td colspan='?3'?(?: height=\"19\")?>&nbsp;?</td>\s*</tr>", fr, re.I | re.S)
        for committee in list:
                cteename = re.sub("\s+", " ", committee[0]).replace("&amp;", "&")
                members = committee[1]
                if cteename not in committees:
                        print "Committee title not in list: ", cteename
                else:
                        found[cteename] = 1
                for member in re.findall("<tr>\s*<td(?: height=\"19\")?>\s*(.*?)\s*</td>\s*<td(?: height=\"19\")?>\s*(.*?)\s*</td>\s*<td(?: height=\"19\")?>\s*(.*?)\s*</td>\s*</tr>(?i)", members):
                        name = member[0]
                        const = member[1]
                        party = member[2]
                        ec = protooffice()
                        ec.SelCteeproto((sdate, stime), name, const, cteename)
                        res.append(ec)
        for i in committees:
                if i not in found:
                        print "Argh:", i

        return (sdate, stime), res

def ParseGovPostsPage(fr, gp):
	# extract the updated date and time
        if gp == "govposts0036_2006-05-05.html":  # was an on-going update
                return "SKIPTHIS", None
        if gp == "govposts0037_2006-05-09.html":  # probably contained mistakes, corrected in next one
                return "SKIPTHIS", None
        if gp == "govposts0038_2006-05-09.html":
                return "SKIPTHIS", None
        if gp == "govposts0039_2006-05-10.html":
                sdate, stime = "2006-05-08", "00:01" #  print sdate, stime, "we could move this date back to the shuffle"
        elif gp == "govposts0069_2006-09-07.html":
                sdate, stime = "2006-09-06", "12:00" #  Grr, they didn't update the date!
        elif gp == "govposts0071_2006-09-29.html":
                return "SKIPTHIS", None
                #sudate = "2006-09-25"
                #sutime = "12:00"
        else:
                frupdated = re.search('<td class="lastupdated">\s*Updated (.*?)(?:&nbsp;| )(.*?)\s*</td>', fr)
                if not frupdated:
                    print "Failed to find lastupdated on:", gp
                lsudate = re.match("(\d\d)/(\d\d)/(\d\d\d\d)$", frupdated.group(1))
                if lsudate:
                    sudate = "%s-%s-%s" % (lsudate.group(3), lsudate.group(2), lsudate.group(1))
                else:
                    lsudate = re.match("(\d\d)/(\d\d)/(\d\d)$", frupdated.group(1))
                    y2k = int(lsudate.group(3)) < 50 and "20" or "19"  # I don't think our records go back far enough to merit this!
                    sudate = "%s%s-%s-%s" % (y2k, lsudate.group(3), lsudate.group(2), lsudate.group(1))
                sutime = frupdated.group(2)
                # extract the date on the document
                frdate = re.search(">Her Majesty's Government at\s+(.*?)\s*<", fr)
                msdate = mx.DateTime.DateTimeFrom(frdate.group(1)).date

                # is it always posted up on the day it is announced?
                if msdate != sudate and sudate not in ["2004-09-20", '2005-03-10', '2005-05-13', '2005-06-06', '2006-05-16', '2006-06-12', '2006-06-13', '2006-06-14', '2006-06-15', '2006-07-27', '2006-08-17']:
                        print "%s : Updated date is %s, but date of change %s" % (gp, sudate, msdate)


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
        Malphl = re.search("ALPHABETICAL LIST OF HM GOVERNMENT([\s\S]*?)</table>", fr)
        if not Malphl:
                print gp
        alphl = Malphl.group(1)
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
			ec = protooffice()
			ec.GovPostproto((sdate, stime), e, deptno)

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

#	<td class="lastupdated">
#		Updated 16/12/04&nbsp;16:31
#	</td>

def ParsePrivSecPage(fr, gp):
	# problem here is there's no date on the page to compare with the lastupdated
	# extract the updated date and time
        if (gp == 'privsec0017_2006-01-13.html'):
                sdate = '2006-01-13'
                stime = '12:00'
        elif (gp == 'privsec0025_2006-06-14.html'):
                sdate = '2006-05-08'
                stime = '00:01'
        elif (gp == 'privsec0030_2006-06-22.html'):
                sdate = '2006-06-22'
                stime = '12:00'
        elif (gp == 'privsec0041_2006-09-07.html'):
                sdate = '2006-09-06'
                stime = '12:00'
        elif (gp == 'privsec0052_2007-02-08.html'):
                sdate = '2007-02-08'
                stime = '12:00'
        elif gp == "privsec0043_2006-09-29.html" or gp == "privsec0044_2006-10-26.html":
                return "SKIPTHIS", None

        else:
                frupdated = re.search('<td class="lastupdated">\s*Updated (.*?)(?:&nbsp;| )(.*?)\s*</td>', fr)
                if not frupdated:
                        print "failed to find lastupdated in", gp
                lsudate = re.match("(\d\d)/(\d\d)/(\d\d\d\d)$", frupdated.group(1))
                if lsudate:
                    sudate = "%s-%s-%s" % (lsudate.group(3), lsudate.group(2), lsudate.group(1))
                else:
                    lsudate = re.match("(\d\d)/(\d\d)/(\d\d)$", frupdated.group(1))
	            y2k = int(lsudate.group(3)) < 50 and "20" or "19"
	            sudate = "%s%s-%s-%s" % (y2k, lsudate.group(3), lsudate.group(2), lsudate.group(1))
	        sutime = frupdated.group(2)

	        sdate = sudate
	        stime = sutime	# or midnight if not posted properly to match the msdate


	res = [ ]
        Mppstext = re.search('''(?xi)<tr>\s*<td[^>]*>
							<font[^>]*><b>Attorney-General.see.</b>\s*Law\s+Officers.Department</font>
							</td>\s*</tr>
							([\s\S]*?)</table>''', fr)

        # skip over a holding page that says the PPSs are not sorted out right after the reshuffle
        if re.search('Following the reshuffle', fr):
                assert not Mppstext
                return "SKIPTHIS", None

        if not Mppstext:
                print gp
                #print fr
        ppstext = Mppstext.group(1)
	ppslst = re.split("</?tr>(?i)", ppstext)

	# match the name form on each entry
	#<TD><B>Abercorn, Duke of</B></TD><TD>Lord Steward, HM Household</TD>

	luniqgov = uniqgovposns[:]
	deptname = None
	ministername = None
	for e1 in ppslst:
		e = e1.strip()
		if re.match("(?:<[^<]*>|\s|&nbsp;)*$", e):
			continue
		deptMatch = re.match('\s*<td[^>]*>(?:<font[^>]*>|<b>){2,}([^<]*)(?:(?:</b>|</font>){2,}</td>)?\s*$(?i)', e1)
		if deptMatch:
			deptname = re.sub("&amp;", "&", deptMatch.group(1))  # carry forward department name
			deptname = re.sub("\s+", " ", deptname)
			continue
		nameMatch = re.match("\s*<td>\s*([^<]*)</td>\s*<td>\s*([^<]*)(?:</td>)?\s*$(?i)", e1)
		if nameMatch.group(1):
			ministername = nameMatch.group(1)  # carry forward minister name (when more than one PPS)
			if ministername == 'Rt Hon Lord Rooker , Minister of State':
				ministername = 'Rt Hon Lord Rooker of Perry Bar , Minister of State'

		if re.search('vacant(?i)', nameMatch.group(2)):
			continue

		if deptname in ppsdepts:
			ec = protooffice()
			ec.PPSproto((sdate, stime), nameMatch.group(2), ministername, deptname)
			res.append(ec)
		else:
			if deptname not in ppsnondepts:
				print "unknown department/post", deptname
				assert False

	return (sdate, stime), res



# this goes through all the files and chains positions together
def ParseChggdir(chgdirname, ParsePage, bfrontopenchains):
	fchgdir = os.path.join(chggdir, chgdirname)

	gps = os.listdir(fchgdir)
	gps = [ x for x in gps if re.match(".*\.html$", x) ]
	gps.sort() # important to do in order of date

	chainprotos = [ ]
	sdatetlist = [ ]
	sdatetprev = ("1997-05-01", "")
	for gp in gps:
                filename = gp
		patchfile = '%s/patches/chgpages/%s/%s.patch' % (toppath, chgdirname, gp)
		if os.path.isfile(patchfile):
			patchtempfilename = tempfile.mktemp("", "min-applypatchtemp-", '%s/tmp/' % toppath)
			ApplyPatches(os.path.join(fchgdir, filename), patchtempfilename, patchfile)
			filename = patchtempfilename
		f = open(os.path.join(fchgdir, filename))
		fr = f.read()
		f.close()

		# get the protooffices from this file
		sdatet, proff = ParsePage(fr, gp)
		if sdatet == "SKIPTHIS":
			continue

		# all PPSs and committee memberships get cancelled when cross the general election.
		if chgdirname != "govposts" and sdatet[0] > "2005-05-01" and sdatetprev[0] < "2005-05-01":
			genelectioncuttoff = ("2005-04-11", "00:01")
			#print "genelectioncuttoffgenelectioncuttoff", chgdirname

			# close the chains that have not been stuck
			for chainproto in chainprotos:
				if chainproto.bopen:
					chainproto.SetChainBack(genelectioncuttoff)


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
		bfrontopen = bfrontopenchains and not chainprotos
		for prof in proffnew:
			prof.SetChainFront(gp, bfrontopen)
			chainprotos.append(prof)

		# list of all the times scraping has been made
		sdatetlist.append((sdatet[0], sdatet[1], chgdirname))

		sdatetprev = sdatet

	# no need to close off the running cases with year 9999, because it's done in the writexml
	return chainprotos, sdatetlist

# endeavour to get an id into all the names
def SetNameMatch(cp, cpsdates, mpidmap):
	cp.matchid = ""

	# don't match names that are in the lords
        if cp.fullname == 'Dame Marion Roe DBE':
                cp.fullname = 'Marion Roe'
	if not re.search("Duke |Lord |Baroness |Dame |^Earl ", cp.fullname):
		fullname = cp.fullname
		cons = cp.cons
                if fullname == "Michael Foster" and not cons:
                        if cpsdates[0] in ["2006-05-08", "2006-05-09", "2006-05-10", "2006-05-11"]:
                                cons = "Worcester"   # this Michael Foster had been a PPS
                        else:
                                print cpsdates[0]; assert False  # double check we still have the right Michael Foster

                if fullname == "Rt Hon Michael Ancram, Earl of QC" or fullname == "Rt Hon Michael Ancram, Earl of, QC":
                        fullname = "Michael Ancram"
                if fullname == "Hon Nicholas Nicholas Soames":
                        fullname = "Nicholas Soames"
		cp.matchid, cp.remadename, cp.remadecons = memberList.matchfullnamecons(fullname, cons, cpsdates[0])
		if not cp.matchid:
                        print cpsdates[0]
			print (cp.matchid, cp.remadename, cp.remadecons)
			print cpsdates
			raise Exception, 'No match: ' + fullname + " : " + (cons or "[nocons]") + "\nOrig:" + cp.fullname
	else:
		cp.remadename = cp.fullname
		cp.remadename = re.sub("^Rt Hon ", "", cp.remadename)
		cp.remadename = re.sub(" [COMD]BE$", "", cp.remadename)
		cp.remadecons = ""
		date = cpsdates[0]

		# Manual fixes for old date stuff. Hmm.
		if cp.remadename == 'Lord Adonis' and date<'2005-05-23':
			date = '2005-05-23'
		if cp.remadename == 'Baroness Clark of Calton' and date=='2005-06-28':
			date = '2005-07-13'
		if (cp.remadename == 'Baroness Morgan of Huyton' or cp.remadename == 'Lord Rooker') and date=='2001-06-11':
			date = '2001-06-21'
		if cp.remadename == 'Lord Grocott' and date=='2001-06-12':
			date = '2001-07-03'
		if cp.remadename == 'Lord Davidson of Glen Cova':
			cp.remadename = 'Lord Davidson of Glen Clova'
		if cp.remadename == 'Lord Rooker of Perry Bar':
			cp.remadename = 'Lord Rooker'

		bnonlords = cp.remadename in ['Duke of Abercorn', 'Lord Vestey']
		if not bnonlords:
			fullname = cp.remadename
			cp.matchid = lordsList.GetLordIDfname(cp.remadename, None, date) # loffice isn't used?

	# make the structure we will sort by.  Now uses the personids from people.xml (slightly backward.  It means for running from scratch you should execute personsets.py, this operation, and personsets.py again)
	if cp.matchid in mpidmap:
		cp.sortobj = mpidmap[cp.matchid]
	else:
		if not bnonlords:
			print "mpid of", cp.remadename, "not found in people.xml; please run personsets.py and this command again"
		cp.sortobj = (re.sub("(.*) (\S+)$", "\\2 \\1", cp.remadename), cp.remadecons)



# indentify open for gluing
def GlueGapDataSetGaptonewlabministers2003(mofficegroup):
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

			if iopendatefrontm == None:
				rp = mofficegroup[iopendateback]
				print "%s\tpos='%s'\tdept='%s'" % (rp[1].remadename, rp[1].pos, rp[1].dept)
			assert iopendatefrontm != None

			# glue the two things together
			mofficegroup[iopendatefrontm][1].sdatestart = mofficegroup[iopendateback][1].sdatestart
			mofficegroup[iopendatefrontm][1].stimestart = None
			mofficegroup[iopendatefrontm][1].sourcedoc = mofficegroup[iopendateback][1].sourcedoc + " " + mofficegroup[iopendatefrontm][1].sourcedoc
			del mofficegroup[iopendateback]

	# check all linked up
	for iopendatefront in range(len(mofficegroup)):
		assert not (mofficegroup[iopendatefront][1].sdatestart == opendate)
	#	rp = mofficegroup[iopendatefront]
	#	print "\t%s\tpos='%s'\tdept='%s'" % (rp[1].remadename, rp[1].pos, rp[1].dept)



def CheckPPStoMinisterpromotions(mofficegroup):
	# now sneak in a test that MPs always get promoted from PPS to ministerialships
	ppsdatesend = [ ]
	ministerialdatesstart = [ ]
	committeegovlist = [ ]
	for rp in mofficegroup:
		if rp[1].pos == "PPS":
			committeegovlist.append((rp[1].sdatestart, "govpost", rp[1]))
			if rp[1].dept != "Prime Minister's Office":
				ppsdatesend.append(rp[1].sdateend)
		elif rp[1].pos == "Chairman":
			if rp[1].dept != "Modernisation of the House of Commons Committee":
				committeegovlist.append((rp[1].sdatestart, "committee", rp[1]))
		elif rp[1].pos == "":
			pass # okay to be an ordinary member and a gov position
			#committeegovlist.append((rp[1].sdatestart, "committee", rp[1]))
		else:  # ministerial position
			if rp[1].pos != "Second Church Estates Commissioner":
				committeegovlist.append((rp[1].sdatestart, "govpost", rp[1]))
			if rp[1].pos != "Assistant Whip":
				ministerialdatesstart.append(rp[1].sdatestart)

	# check we always go from PPS to ministerial position
	if ppsdatesend and ministerialdatesstart:
		if max(ppsdatesend) > min(ministerialdatesstart):
			if mofficegroup[0][1].fullname not in ["Paddy Tipping"]:
				print "New demotion to PPS for: ", mofficegroup[0][1].fullname

	# check that goverment positions don't overlap committee positions
	committeegovlist.sort()
	ioverlaps = 0
	for i in range(len(committeegovlist)):
		j = i + 1
		while j < len(committeegovlist) and committeegovlist[i][2].sdateend > committeegovlist[j][2].sdatestart:
			if (committeegovlist[i][1] == "govpost") != (committeegovlist[j][1] == "govpost"):
				ioverlaps += 1
			j += 1
	if ioverlaps:
		print "Overlapping government and committee posts for: ", mofficegroup[0][1].fullname

class LoadMPIDmapping(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.mpidmap = {}
		self.in_person = None
		parser = xml.sax.make_parser()
		parser.setContentHandler(self)
		parser.parse(peoplexml)
	def startElement(self, name, attr):
		if name == "person":
			assert not self.in_person
			self.in_person = attr["id"]
		elif name == "office":
			assert attr["id"] not in self.mpidmap
			self.mpidmap[attr["id"]] = self.in_person
	def endElement(self, name):
		if name == "person":
			self.in_person = None


# main function that sticks it together
def ParseGovPosts():

	# get from our two sources (which unfortunately don't overlap, so they can't be merged)
	# I believe our gap from 2003-10-15 to 2004-06-06 is complete, though there is a terrible gap in the PPSs
	porres = newlabministers2003_10_15.ParseOldRecords()
	cpres, sdatetlist = ParseChggdir("govposts", ParseGovPostsPage, True)

	# parliamentary private secs
	cpressec, sdatelistsec = ParseChggdir("privsec", ParsePrivSecPage, False)

	# parliamentary Select Committees
	cpresselctee, sdatelistselctee = ParseChggdir("selctee", ParseSelCteePage, False)


	mpidmap = LoadMPIDmapping().mpidmap

	# allocate ids and merge lists
	rpcp = []

	# run through the office in the documented file
	moffidn = 1;
	for po in porres:
		cpsdates = [po.sdatestart, po.sdateend]
		if cpsdates[1] == opendate:
			cpsdates[1] = newlabministers2003_10_15.dateofinfo

		SetNameMatch(po, cpsdates, mpidmap)
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

		SetNameMatch(cp, cpsdates, mpidmap)
		cp.moffid = "uk.org.publicwhip/moffice/%d" % moffidn
		rpcp.append((cp.sortobj, cp))
		moffidn += 1

	# private secretaries
	for cp in cpressec:
		cpsdates = [cp.sdatestart, cp.sdateend]
		SetNameMatch(cp, cpsdates, mpidmap)
		cp.moffid = "uk.org.publicwhip/moffice/%d" % moffidn
		rpcp.append((cp.sortobj, cp))
		moffidn += 1

	for cp in cpresselctee:
		cpsdates = [cp.sdatestart, cp.sdateend]
		SetNameMatch(cp, cpsdates, mpidmap)
		cp.moffid = "uk.org.publicwhip/moffice/%d" % moffidn
		rpcp.append((cp.sortobj, cp))
		moffidn += 1

	# bring same to same places
	# the sort object is by name, constituency, dateobject
	rpcp.sort()
	# (there was a gluing loop here, but it was wrong thing to do, since it disrupted gluing of datasets-- failures shouldn't be happening to here)

	# now we batch them up into the person groups to make it visible
	# and facilitate the once-only gluing of the two documents (newlabministers records and webpage scrapings) together
	# this is a conservative grouping.  It may fail to group people which should be grouped,
	# but this gets sorted out in the personsets.py
	mofficegroups = [ ]
	prevrpm = None
	for rp in rpcp:
		if rp:
			if not prevrpm or prevrpm[0] != rp[0]:
				mofficegroups.append([ ])
			mofficegroups[-1].append(rp)
			prevrpm = rp


	# now look for open ends
	for mofficegroup in mofficegroups:
		GlueGapDataSetGaptonewlabministers2003(mofficegroup)
		CheckPPStoMinisterpromotions(mofficegroup)

	fout = open(chgtmp, "w")
	WriteXMLHeader(fout)
	fout.write("\n<!-- ministerofficegroup is just for readability.  Actual grouping is done in personsets.py -->\n\n")
	fout.write("<publicwhip>\n")

	fout.write("\n")
	for lsdatet in sdatetlist:
		fout.write('<chgpageupdates date="%s" time="%s" chgtype="%s"/>\n' % lsdatet)
	for lsdatet in sdatelistsec:
		fout.write('<chgpageupdates date="%s" time="%s" chgtype="%s"/>\n' % lsdatet)
	for lsdatet in sdatelistselctee:
		fout.write('<chgpageupdates date="%s" time="%s" chgtype="%s"/>\n' % lsdatet)


	# output the file, a tag round the groups of offices which form a single person
	# (could sort them by last name as well)
	for mofficegroup in mofficegroups:
		fout.write('\n<ministerofficegroup>\n')
		for rp in mofficegroup:
			WriteXML(rp[1], fout)
		fout.write("</ministerofficegroup>\n")

	fout.write("</publicwhip>\n\n")
	fout.close();

	# we get the members directory and overwrite the file that's there
	# (in future we'll have to load and check match it)

	#print "Over-writing %s;\nDon't forget to check it in" % ministersxml
	if os.path.isfile(ministersxml):
		os.remove(ministersxml)
	os.rename(chgtmp, ministersxml)


