# vim:sw=8:ts=8:et:nowrap

import sys
import os
import urllib
import urlparse
import string
import re
import xml.sax

import mx.DateTime

import miscfuncs
from standingutils import construct_shortname, create_committee_letters

toppath = miscfuncs.toppath

# Creates an xml with the links into the index files for the Standing Committees.

url_pbc_current = "http://www.parliament.uk/business/publications/hansard/commons/bill-committee-debates/"
url_pbc_previous = "http://www.parliament.uk/business/publications/hansard/commons/bill-committee-debates/previous-sessions/"

pwsdantingindex = os.path.join(toppath, "standingindex.xml")

def get_oldstyle_bill_links(urlpage):
	res = [ ]
	uin = urllib.urlopen(urlpage)
	s = uin.read()
	uin.close()
	vdat = re.search("(?s)page title and static information follows(.*?)(end of variable data|$)", s).group(1)
	vdat = re.sub("(?s)<!--.*?-->", "", vdat)
	for lk in re.findall('<a href\s*=\s*"([^"]*)">(.*?)</a>(?is)', vdat):
		lklk = re.sub('\s', '', lk[0])
                if re.match('http://www.parliament.uk', lklk): continue
		lkname = re.sub("(?:\s|&nbsp;)+", " ", lk[1]).strip()
		res.append((urlparse.urljoin(urlpage, lklk), lkname))
		#print res[-1]
	return res

romanconvmap = { "I":1, "II":2, "III":3, "IV":4, "V":5, "VI":6, "VII":7, "1":1, "2":2, }


# get the standing committee parsing to work, output XML
# res = [ (urllink, date, sitting number, sitting part, morning|afternoon) ]
def GetReportProceedings(urlpage, year):
	res = [ ]
	firstdate = ""
	uin = urllib.urlopen(urlpage)
	s = uin.read()
	uin.close()
	vdat = re.search("(?is)Reports? of proceedings(.*?)(Associated Memoranda|start of footer|$)", s)
	if urlpage == 'http://www.publications.parliament.uk/pa/cm/cmpbparliament.htm': # XXX
		vdat = re.sub('(?s)^.*(<A href=".*?">2nd)', '\1', s)
	elif urlpage == 'http://services.parliament.uk/bills/2012-13/crimeandcourts/committees/houseofcommonspublicbillcommitteeonthecrimeandcourtsbillhl201213.html': # XXX
		vdat = re.sub('(?is)^.*?Reports? of proceedings(.*?)<h3>Associated memoranda', r'\1', s)
	elif urlpage == 'http://services.parliament.uk/bills/2012-13/financeno2/committees/houseofcommonspublicbillcommitteeonthefinanceno2bill201213.html':
		vdat = re.sub('(?is)^.*?Reports? of proceedings(.*?)$', r'\1', s)
	elif not vdat:
		return res, None
	else: 
		vdat = vdat.group(1)
	vdat = re.sub("(?s)<!--.*?-->", "", vdat)
	# correct a few typos
	if year == "2005":
		vdat = re.sub('(/pa/cm200506/cmstand/e/st050705/am/50705s01.htm">1st  sitting</A></FONT></TD><TD><FONT size=\+1><A\s*href="/pa/cm200506/cmstand/)b/st050621(/am/50705s01.htm">5 July 2005)', '\g<1>e/st050705\g<2>', vdat)
		vdat = re.sub('(/pa/cm200506/cmstand/b/st060713/am/60713s01.htm">3rd sitting</A></FONT></TD><TD><FONT size=\+1><A href="/pa/cm200506/cmstand/b/st06071)1(/am/60713s01.htm">13 July 2006)', '\g<1>3\g<2>', vdat)
                if urlpage=='http://www.publications.parliament.uk/pa/cm200506/cmstand/cmscright.htm':
                        vdat = re.sub('<A href="/pa/cm200506/cmstand/a/st051213/am/51213s01\.htm">', '', vdat)
                        vdat = re.sub('2nd  sitting', '1st  sitting', vdat)
	if year == "2002":
		vdat = re.sub('(<A href="st030204/)a(m/30204s01.htm">20th sitting</A></FONT></TD><TD><FONT size=\+1><A href="st030204/pm/30204s01.htm">4 February 2003  \(afternoon\))', '\g<1>p\g<2>', vdat)
		vdat = re.sub('(<A href="st030225/)a(m/30225s01.htm">10th sitting</A></FONT></TD><TD><FONT size=\+1><A href="st030225/pm/30225s01.htm">25th February 2003 \(afternoon\))', '\g<1>p\g<2>', vdat)
		vdat = re.sub('(st03061)7/30618(s01.htm">2nd\s*sitting</A></FONT></TD>\s*<TD><FONT size=\+1><A href="st030618/30618s01.htm">18th June 2003)', '\g<1>8/30618\g<2>', vdat)
	if year == "2001":
		vdat = re.sub('(st011127/)a(m/11127s01.htm">6th sitting</A></FONT></TD>\s*<TD nowrap><FONT size=\+1><A href="st011127/pm/11127s01.htm">27th November 2001 \(afternoon\))', '\g<1>p\g<2>', vdat)
		vdat = re.sub('(st011122/)p(m/11122s01.htm">2nd sitting</A></FONT></TD>\s*<TD nowrap><FONT size=\+1><A href="st011122/am/11122s01.htm">22nd November 2001  \(morning\))', '\g<1>a\g<2>', vdat)
                vdat = re.sub('partII//', 'partII/', vdat)
	if year == "1997":
		vdat = re.sub('(st980512/pm/pt)1(/80512s01.htm">3rd sitting </A></FONT></TD>\s*<TD><FONT size=\+1><A href="st980512/pm/pt2/80512s01.htm">12 May 1998)', '\g<1>2\g<2>', vdat)
	if year == "2006":
		vdat = re.sub('(3rd sitting</A></TD><TD class="style1" valign="top"><A href="/pa/cm200607/cmpublic/serious/07062)6(/am/7062)6(s01.htm">28 June 2007 \(morning\))', '\g<1>8\g<2>8\g<3>', vdat)
	if year == "2008":
		vdat = re.sub('090609(/pm/90602s01.htm">6th sitting)', r'090602\1', vdat)
		vdat = re.sub('1 July 209', '1 July 2009', vdat)
		vdat = re.sub('(<A href="[^"]+")(20 October)', r'\1>\2', vdat)
        if year == "2010":
                vdat = re.sub('(110207s01.htm">Committee Debate)( *</a>)', r'\1 1st sitting\2', vdat)
        if year == "2013":
                vdat = re.sub('(131211s01.htm">Committee Debate)( *</a>)', r'\1 1st sitting\2', vdat)
        if year == "2014":
                vdat = re.sub('(150115s01.htm">Committee Debate)( *</a>)', r'\1 1st sitting\2', vdat)

	lks = re.findall('(?si)<a\s+href\s*=\s*"([^"]*)">(.*?)(?:</a>|<tr>|</table>)(?i)', vdat)
	for lk in lks:
		lklk = re.sub("\s", "", lk[0])
		lklk = urlparse.urljoin(urlpage, lklk)
		lkname = re.sub("(?:\s|&nbsp;|<br>|</?[iI]>)+", " ", lk[1]).strip()

                if re.match('https?://(www|services|subscriptions).parliament.uk', lklk): continue

                # Thing in the wrong place
                if re.match('Associated Memorand(um|a)', lkname): continue

                # They've done them under bills now...
                if int(year) >= 2009:
                        if 'PDF' in lkname: continue # We don't care about the pretty PDFs
                        msitting = re.match('(?:Public Bill )?Comm?ittee?(?: Stage| debates?)*(?: ?-|:)? *(\d+)(?:st|nd|rd|th) sitting(?i)', lkname)
			try:
                                sitting = int(msitting.group(1))
                        except:
                                raise Exception, "Could not find sitting in %s for %s" % (lkname, urlpage)
                        mdate = re.search('cmpublic/(.*?)/(\d\d)(\d\d)(\d\d)(?:/(am|pm))?/\d+s\d+(?:(?:part|p)(\d))?\.htm', lklk)
                        sdate = mx.DateTime.DateTimeFrom(
                                year=2000+int(mdate.group(2)),
                                month=int(mdate.group(3)),
                                day=int(mdate.group(4))
                        ).date
                        if mdate.group(5) == 'am': time = 'morning'
                        elif mdate.group(5) == 'pm': time = 'afternoon'
                        # Treat specially, don't yet know if will become common
                        elif mdate.group(5) is None and 'europeanunionref/130911' in lklk: time = 'morning'
                        if res and res[-1] == [ lklk, sdate, sitting, 0, time ]: continue

                        part = 0
                        if mdate.group(6):
                            part = int(mdate.group(6))

                        # In 2011, the Health and Social Care Bill 2010-11 started its sittings again at 1...
                        # We'll add 28 to all of these so they appear in the right order.
                        if (int(year) == 2010 and
                            re.search('/pa/cm201011/cmpublic/health', lklk) and
                            mx.DateTime.DateTime(*(int(x) for x in sdate.split('-'))) >= mx.DateTime.DateTime(2011, 06, 28)
                            ):
                                sitting += 28

                        res.append([ lklk, sdate, sitting, part, time ])
			if not firstdate or firstdate > sdate:
				firstdate = sdate
                        continue

		mprevdebates = re.match("Debates on.*?Bill in Session \d\d\d\d-\d\d", lkname)
		if (not res or res[-1][0] != lklk) and not mprevdebates:
			 res.append([lklk, "", 0, 0, ""])  # urllink, date, sitting number, sitting part, morning|afternoon
		msecreading = re.match("(Second|2nd) Reading Committee$|Standing Committee B$", lkname)
		monlysitting = re.match("Public Bill Committee$", lkname)
		mothmem = re.match("Other Memorand(?:ums|a) and Letters [Ss]ubmitted to the Committee$", lkname)
		msitting = re.match("(\d+)(?:st|nd|rd|th)\s+[Ss]itting(?: \((cont)'d\))?(?: \(Part ([I]*)\))?$", lkname)
		mdate = re.match("(?:<b>)?(\d+(?:st|nd|rd|th)? (?:January|February|March|April|May|June|July|August|September|October|November|December)(?: \d\d\d\d)?)(?:</b>)?(?: ?\(([Mm]orning|[Aa]fternoon|evening)\)?)?(?: [\[\(\-]?\s*[Pp]art ([IViv\d]*)\s*[\]\)]?)?(?: ?\((morning|[Aa]fternoon)\)?)?$", lkname)

		# from this we can assembly the components of the result
		if mothmem:
			assert not res[-1][1]
			assert res[-1][3] == 0
			res[-1][3] = 99999
		elif monlysitting or msecreading:
			pass # print lkname
		elif msitting:
			assert res[-1][2] == 0 or res[-1][2] == int(msitting.group(1))
			res[-1][2] = int(msitting.group(1)) # sitting
			if msitting.group(3): # part
				assert res[-1][3] == 0
				res[-1][3] = romanconvmap[msitting.group(3).upper()]
		elif mdate:
			sdate = mdate.group(1)
			if year == "2003" and not re.match(".*?\d$", sdate):
				if re.search("st04012[02]/[ap]m/4012[02]s01.htm$", res[-1][0]):
					sdate = sdate + " 2004"
				else:
					print year, mdate.group(0), res[-1][0]
					assert False
			if year == "1999":
				sdate = re.sub("February 1999", "February 2000", sdate)
			if year == "2004":
				sdate = re.sub("January 2004", "January 2005", sdate)
			if year == "2003" and re.match(".*?41111s01.htm$", res[-1][0]):
				sdate = re.sub("[34] November 2004", "11 November 2004", sdate)
			if year == "1999" and re.match(".*?00118s01.htm$", res[-1][0]):
				sdate = re.sub("7 February 2000", "18 January 2000", sdate)
			if year == "2005" and re.match(".*?6062\ds01.htm$", res[-1][0]):
				sdate = re.sub("2005", "2006", sdate)
                        if re.search("080304", res[-1][0]):
                                sdate = re.sub("February", "March", sdate)
			res[-1][1] = mx.DateTime.DateTimeFrom(sdate).date
			# firstdate is used to label the committee
			if not firstdate or firstdate > res[-1][1]:
				firstdate = res[-1][1]

			if mdate.group(2): # morning|afternoon
				assert not res[-1][4]
				res[-1][4] = mdate.group(2).lower()
			if mdate.group(4): # morning|afternoon
				assert not res[-1][4]
				res[-1][4] = mdate.group(4).lower()
			if mdate.group(3): # part
				assert res[-1][3] == 0
				res[-1][3] = romanconvmap[mdate.group(3).upper()]
		elif mprevdebates:
			pass
		elif lkname:
			print "  ****%s*" % lkname

	# check the numbering of the parts is good
	#for r in res:
	#	print r[1:]

	# single sitting, set it up
	if len(res) == 1:
		#print res
		assert (res[0][2] == 0 or res[0][2] == 1) and res[0][3] == 0
		res[0][2] = 1

	# two sittings, both without sitting numbers
	if len(res) == 2 and res[0][2] == 0 and res[1][2] == 0 and res[0][3] == 0 and res[1][3] == 0:
		res[0][2] = 2
		res[1][2] = 1

	# now check the numbering of the parts is consistent (requires sorting them)
	parts = [ [r[2], r[3], r[1], r]  for r in res  if r[3] != 99999 ]  # sitting, part, date, whole
	parts.sort()
	prev = None
	for p in parts:
		assert (int(p[2][:4]) - int(year) in [0, 1]) or (int(p[2][:4]) == 2012 and int(year) == 2010)
		if prev:
			if prev[0] == p[0]:
				if prev[1] == 0 and p[1] == 2:
					prev[1] = 1
					prev[3][3] = 1 # blank case, give it sitting number 1
				else:
					assert prev[1] + 1 == p[1] and prev[1] != 0 
			else:
				assert prev[0] + 1 == p[0]

			assert prev[2] <= p[2] # date
		else:
			if year == "2001" and re.search("/pa/cm200102/cmstand/special/cmadopt.htm$", urlpage):
				assert p[0] == 2  # 1st meeting held in private
			elif year == "1998" and re.search("/pa/cm199899/cmstand/special/special.htm$", urlpage):
				assert p[0] == 2  # 1st meeting held in private
			elif year == "1999" and re.search("/pa/cm199900/cmstand/a/cmserv.htm$", urlpage):
				assert p[0] == 25  # 1st 24 meeting ommitted
			elif year == "2006" and re.search("/pa/cm200607/cmpublic/cmpbwelf.htm", urlpage):
				assert p[0] == 13 # 1st 12 meetings in previous year
			elif year == "2012" and re.search("/bills/2012-13/financeno4/", urlpage):
				assert p[0] == 5 # 1st 4 meetings in previous session
				firstdate = '2012-04-24'
			elif year == "2013" and re.search("/bills/2013-14/finance/committees/houseofcommonspublicbillcommitteeonthefinanceno2bill201314", urlpage):
				assert p[0] == 5 # 1st 4 meetings in previous session
				firstdate = '2013-04-23'
			else:
				assert p[0] == 1, "%s first sitting not found" % urlpage
		prev = p
	return res, firstdate

def get_committee_attributes(committees):
	res = [ ]
        for year, index_url, index_text in committees:
                if index_url == 'http://services.parliament.uk/bills/2009-10/thirdpartiesrightsagainstinsurers.html':
                        index_url = 'http://services.parliament.uk/bills/2009-10/thirdpartiesrightsagainstinsurers/committees/houseofcommonspublicbillcommitteeonthethirdpartiesrightsagainstinsurersbillhl200910.html'
                if re.match('House of Lords Special Public Bill Committees', index_text):
                        continue
                # The following two had their meetings in 2008-09 and are linked from there also
                if year == '2009' and index_text in ('Child Poverty Bill', 'Equality Bill'):
                        continue
                if index_url == 'http://services.parliament.uk/bills/2010-11/armedforces/committees/houseofcommonspublicbillcommitteeonthearmedforcesbill201011.html':
                        continue
                if 'Police Reform and Social Responsibility' in index_text and 'policereform' not in index_url:
                        index_url = 'http://services.parliament.uk/bills/2010-11/policereformandsocialresponsibility/committees/houseofcommonspublicbillcommitteeonthepolicereformandsocialresponsibilitybill201011.html'

                mcttee = re.match("""
        # The name of the Bill (occasionally they forget to put 'Bill')
        (.*?[ ](?:Bill|Dogs|Schools[ ]and[ ]Families|Names))
        # Some way of saying it's a Bill that started in the Lords
        (?:\s?\[(?:<i>)?(?:Lords|HL)(?:</i>)?\])?
        (?:\s?(?:<i>)?\[Lords\](?:</i>)?)?
        (?:\s*\[(?:<i>)?<FONT[ ]size=\-1>LORDS</FONT>(?:</i>)?\])?
        # Occasionally PBC doesn't look at all clauses
        (?:\s*Bill)?(?:</i>)*(?:\s)*(?:\(except[ ]clauses.*?\)[ ])?
        # And they used to say which Standing Committee was looking at it
        (\((Standing[ ]Committee[ ][a-zA-Z]|Special[ ]Standing[ ]Committee|(Second|2nd)[ ]Reading[ ]Committee)\)\s?)?
        # They occasionally repeat the session for no reason
        (?:\s?\d\d\d\d-\d\d)?
        # New ones since 2010-11 sometimes put "Committee" at the end
        (?:[ ]Committee)?
        \s*$(?ix)""", index_text)
                assert mcttee, "Unrecognized committee or bill name: %s" % index_text
                billtitle = mcttee.group(1)
                if billtitle == "Company & Business Names":
                        billtitle = "Company and Business Names (Chamber of Commerce, Etc.) Bill"
                if billtitle == "Breeding and Sale of Dogs":
                        billtitle = "Breeding and Sale of Dogs Bill"
                if billtitle == "Children, Schools and Families":
                        billtitle = "Children, Schools and Families Bill"
                assert re.match(".*? Bill$", billtitle), 'Does not end in Bill : %s' % billtitle
                committee = mcttee.group(2)
                #res.append((year, billtitle, committee, index_url))
                ps, committeedate = GetReportProceedings(index_url, year)
                for p in ps:
                        res.append(((year, billtitle, committee, index_url, committeedate), p))
	return res

def GetBillLinks(bforce):
        uin = urllib.urlopen(url_pbc_current)
        s = uin.read()
        uin.close()
        current_committees = re.findall('<a href="(http://services.parliament.uk/bills/[^"]*)">(.*?)</a>(?is)', s)
        current_session = re.search('<(?:h2|strong)>Session (\d{4})-\d+</(?:h2|strong)>', s).group(1)
        committees = [ (current_session, link, text) for link, text in current_committees ]

        # Remove duplicates, maintain order
        seen = set()
        committees = [ c for c in committees if c not in seen and not seen.add(c) ]

        # if you don't do --force-index, you just get the current year
        if bforce:
                billyears = [ ]
                uin = urllib.urlopen(url_pbc_previous)
                s = uin.read()
                uin.close()
                billyears = re.findall('<a href="([^"]*)"[^>]*>(Session .*?)</a>(?is)', s)

                for billyear in billyears:
                        match = re.match("Session (\d\d\d\d)-\d\d(?:\d\d)?", billyear[1])
                        if not match:
                                raise Exception, "Did not find session dates in %s" % billyear[1]
                        year = match.group(1)
                        if miscfuncs.IsNotQuiet():
                                print "year=", year
                        for link, text in get_oldstyle_bill_links(billyear[0]):
                                committees.append( (year, link, text) )

        return get_committee_attributes(committees)

def WriteXML(fout, billinks):
	fout.write('<?xml version="1.0" encoding="ISO-8859-1"?>\n')
	fout.write("<publicwhip>\n\n")

	for billink in billinks:
		(h, p) = billink
		(year, billtitle, committee, indexurl, committeedate) = h
		(urllink, date, sittingnumber, sittingpart, daypart) = p

		# construct short name to use for the pullglued file	
		if committee:
			mstandc = re.match("\(?Standing Committee ([a-zA-Z])\)?", committee)
			if mstandc:
				shortcommitteeletter = mstandc.group(1).upper()
			elif re.match("\(?Special Standing Committee\)?", committee):
				shortcommitteeletter = "S"
			elif re.match("\(?(Second|2nd) Reading Committee\)?", committee):
				shortcommitteeletter = "2"
			else:
				print "Unrecognized committee for short name:", committee
				assert False
		else: 
			shortcommitteeletter =  create_committee_letters(indexurl, urllink)
	
		shortname = construct_shortname(committeedate, shortcommitteeletter, sittingnumber, sittingpart, date)
		fout.write('<standingcttee shortname="%s" session="%s" date="%s" sittingnumber="%d" sittingpart="%d" daypart="%s" committeename="%s" billtitle="%s" urlindex="%s" url="%s"/>\n' % (shortname, year, date, sittingnumber, sittingpart, daypart, committee, billtitle, indexurl, urllink))

	fout.write("\n</publicwhip>\n")


###############
# main function
###############
def UpdateStandingHansardIndex(bforce):
	#print "not--UpdateStandingHansardIndex"
	#return
	billinks = GetBillLinks(bforce)

	# we need to extend it to the volumes, but this will do for now.
	fpwsdantingindex = open(pwsdantingindex, "w");
	WriteXML(fpwsdantingindex, billinks)
	fpwsdantingindex.close()



