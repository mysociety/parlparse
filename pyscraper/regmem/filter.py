#! /usr/bin/python
# vim:sw=8:ts=8:et:nowrap

import re
import os
import string

from BeautifulSoup import BeautifulStoneSoup
from contextexception import ContextException
from resolvemembernames import memberList
from miscfuncs import FixHTMLEntities
from miscfuncs import ApplyFixSubstitutions
from xmlfilewrite import WriteXMLHeader
import miscfuncs
toppath = miscfuncs.toppath

# directories
pwcmdirs = os.path.join(toppath, "cmpages")
pwxmldirs = os.path.join(toppath, "scrapedxml")
if not os.path.isdir(pwxmldirs):
	os.mkdir(pwxmldirs)

def RunRegmemFilters2010(fout, text, sdate, sdatever):
        print "2010-? new register of members interests!  Check it is working properly (via mpinfoin.pl) - %s" % sdate

        WriteXMLHeader(fout)
	fout.write("<publicwhip>\n")
        
        memberset = set()
        text = re.sub('<span class="highlight">([^<]*?)</span>', r'\1', text)
        t = BeautifulStoneSoup(text)
        for page in t('page'):
                title = page.h2.renderContents()
                if title in ('HAGUE, Rt Hon William (Richmond (Yorks)', 'PEARCE, Teresa (Erith and Thamesmead'):
                        title += ')'
                res = re.search("^([^,]*), ([^(]*) \((.*)\)\s*$", title)
                if not res:
                        raise ContextException, "Failed to break up into first/last/cons: %s" % title
                (lastname, firstname, constituency) = res.groups()
                firstname = memberList.striptitles(firstname)[0].decode('utf-8')
                lastname = memberList.lowercaselastname(lastname).decode('utf-8')
                constituency = constituency.decode('utf-8')
                lastname = lastname.replace(u'O\u2019brien', "O'Brien") # Hmm
                (id, remadename, remadecons) = memberList.matchfullnamecons(firstname + " " + lastname, constituency, sdate)
                if not id:
                        raise ContextException, "Failed to match name %s %s (%s) date %s\n" % (firstname, lastname, constituency, sdate)
                fout.write(('<regmem personid="%s" membername="%s" date="%s">\n' % (id, remadename, sdate)).encode("latin-1"))
                memberset.add(id)
                category = None
                categoryname = None
                subcategory = None
                record = False
                for row in page.h2.findNextSiblings():
                        text = row.renderContents().decode('utf-8').encode('iso-8859-1', 'xmlcharrefreplace')
                        if row.get('class') == 'spacer':
                            if record:
                                fout.write('\t\t</record>\n')
                                record = False
                            continue
                        if not text or re.match('\s*\.\s*$', text): continue
                        if text == '<strong>%s</strong>' % title: continue
                        if re.match('\s*Nil\.?\s*$', text):
                                fout.write('Nil.\n')
                                continue
                        # Since 2015 election, register is all paragraphs, no headings :(
                        if row.name == 'h3' or row.get('class') == 'shd0' or re.match('<strong>\d+\. ', text):
                                if re.match('\s*$', text): continue
                                m = re.match("(?:\s*<strong>)?\s*(\d\d?)\.\s*(.*)(?:</strong>\s*)?$", text)
                                if m:
                                        if record:
                                            fout.write('\t\t</record>\n')
                                            record = False
                                        if category:
                                                fout.write('\t</category>\n')
                                        category, categoryname = m.groups()
                                        subcategory = None
                                        categoryname = re.sub('<[^>]*>(?s)', '', categoryname).strip()
                                        fout.write('\t<category type="%s" name="%s">\n' % (category, categoryname))
                                        continue
                        if not record:
                            fout.write('\t\t<record>\n')
                            record = True
                        subcategorymatch = re.match("\s*\(([ab])\)\s*(.*)$", text)
                        if subcategorymatch:
                                subcategory = subcategorymatch.group(1)
                                fout.write('\t\t\t(%s)\n' % subcategory)
                                fout.write('\t\t\t<item subcategory="%s">%s</item>\n' % (subcategory, subcategorymatch.group(2)))
                                continue
                        if subcategory:
                                fout.write('\t\t\t<item subcategory="%s">%s</item>\n' % (subcategory, text))
                        else:
                                fout.write('\t\t\t<item>%s</item>\n' % text)
                if record:
                    fout.write('\t\t</record>\n')
                    record = False
                if category:
                        fout.write('\t</category>\n')
                fout.write('</regmem>\n')                                

        membersetexpect = set([m['person_id'] for m in memberList.mpslistondate(sdate)])
        
        # check for missing/extra entries
        missing = membersetexpect.difference(memberset)
        if len(missing) > 0:
                print "Missing %d MP entries:\n" % len(missing), missing
        extra = memberset.difference(membersetexpect)
        if len(extra) > 0:
                print "Extra %d MP entries:\n" % len(extra), extra

	fout.write("</publicwhip>\n")

# Legacy patch system, use patchfilter.py and patchtool now
fixsubs = 	[
	( 'Nestle&#171;', 'Nestle', 1, '2004-01-31' ),
]

def RunRegmemFilters(fout, text, sdate, sdatever):
        if sdate >= '2010-09-01':
                return RunRegmemFilters2010(fout, text, sdate, sdatever)

        # message for cron so I check I'm using this
        print "New register of members interests!  Check it is working properly (via mpinfoin.pl) - %s" % sdate

	text = ApplyFixSubstitutions(text, sdate, fixsubs)

        WriteXMLHeader(fout)
	fout.write("<publicwhip>\n")

        text = re.sub('Rt Shaun', 'Shaun', text) # Always get his name wrong
        text = re.sub('&#128;', '&#163;', text) # Always get some pound signs wrong
        rows = re.findall("<TR>(.*)</TR>", text)
        rows = [ re.sub("&nbsp;", " ", row) for row in rows ]
        rows = [ re.sub("<B>|</B>|<BR>|`", "", row) for row in rows ]
        rows = [ re.sub('<span style="background-color: #FFFF00">|</span>', '', row) for row in rows ]
        rows = [ re.sub('<IMG SRC="3lev.gif">', "", row) for row in rows ]
        rows = [ re.sub("&#173;", "-", row) for row in rows ]
        rows = [ re.sub('\[<A NAME="n\d+"><A HREF="\#note\d+">\d+</A>\]', '', row) for row in rows ]
        rows = [ re.sub('\[<A NAME="n\d+">\d+\]', '', row) for row in rows ]

        # Fix incorrect tabling of categories when highlighting is in play
        rows = [ re.sub('<TD COLSPAN=4>(\d\.) ([^<]*?)</TD>', r'<TD>\1</TD><TD COLSPAN=3>\2</TD>', row) for row in rows ]
        # split into cells within a row
        rows = [ re.findall("<TD.*?>\s*(.*?)\s*</TD>", row) for row in rows ]

        memberset = set()
        needmemberend = False
        category = None
        categoryname = None
        subcategory = None
        for row in rows:
                striprow = re.sub('</?[^>]+>', '', "".join(row))
                #print row
                if striprow.strip() == "":
                        # There is no text on the row, just tags
                        pass
                elif len(row) == 1 and re.match("(?i)(<i>)? +(</i>)?", row[0]):
                        # <TR><TD COLSPAN=4>&nbsp;</TD></TR>
                        pass
                elif len(row) == 1:
                        # <TR><TD COLSPAN=4><B>JACKSON, Robert (Wantage)</B></TD></TR>
                        res = re.search("^([^,]*), ([^(]*) \((.*)\)$", row[0])
                        if not res:
                                print row
                                raise ContextException, "Failed to break up into first/last/cons: %s" % row[0]
                        (lastname, firstname, constituency) = res.groups()
                        constituency = constituency.replace(')', '')
                        constituency = constituency.replace('(', '')
                        firstname = memberList.striptitles(firstname)[0]

                        # Register came out after they stood down
                        if (firstname == 'Ian' and lastname == 'GIBSON' and sdate > '2009-06-08') \
                            or (firstname == 'Michael' and lastname == 'MARTIN' and sdate > '2009-06-22'):
                                check_date = '2009-06-08'
                        else:
                                check_date = sdate
                        (id, remadename, remadecons) = memberList.matchfullnamecons(firstname + " " + memberList.lowercaselastname(lastname), constituency, check_date)
                        if not id:
                                raise ContextException, "Failed to match name %s %s (%s) date %s" % (firstname, lastname, constituency, sdate)
                        if category:
                                fout.write('\t</category>\n')
                        if needmemberend:
                                fout.write('</regmem>\n')                                
                                needmemberend = False
                        fout.write(('<regmem personid="%s" membername="%s" date="%s">\n' % (id, remadename, sdate)).encode("latin-1"))
                        memberset.add(id)
                        needmemberend = True
                        category = None
                        categoryname = None
                        subcategory = None
                elif len(row) == 2 and row[0] == '' and re.match('Nil\.\.?', row[1]):
                        # <TR><TD></TD><TD COLSPAN=3><B>Nil.</B></TD></TR> 
                        fout.write('Nil.\n')
                elif len(row) == 2 and row[0] != '':
                        # <TR><TD><B>1.</B></TD><TD COLSPAN=3><B>Remunerated directorships</B></TD></TR>
                        if category:
                                fout.write('\t</category>\n')
                        digits = row[0]
                        category = re.match("\s*(\d\d?)\.$", digits).group(1)
                        categoryname = row[1]
                        subcategory = None
                        fout.write('\t<category type="%s" name="%s">\n' % (category, categoryname))
                elif len(row) == 2 and row[0] == '':
                        # <TR><TD></TD><TD COLSPAN=3><B>Donations to the Office of the Leader of the Liberal Democrats received from:</B></TD></TR>
                        if subcategory:
                                fout.write('\t\t<item subcategory="%s">%s</item>\n' % (subcategory, FixHTMLEntities(row[1])))
                        else:
                                fout.write('\t\t<item>%s</item>\n' % FixHTMLEntities(row[1]))
                elif len(row) == 3 and row[0] == '' and row[1] == '':
                        # <TR><TD></TD><TD></TD><TD COLSPAN=2>19 and 20 September 2002, two days fishing on the River Tay in Scotland as a guest of Scottish Coal. (Registered 3 October 2002)</TD></TR>
                        if subcategory:
                                fout.write('\t\t<item subcategory="%s">%s</item>\n' % (subcategory, FixHTMLEntities(row[2])))
                        else:
                                fout.write('\t\t<item>%s</item>\n' % FixHTMLEntities(row[2]))
                elif len(row) == 3 and row[0] == '':
                        # <TR><TD></TD><TD><B>(a)</B></TD><TD COLSPAN=2>Smithville Associates; training consultancy.</TD></TR>
                        if subcategory:
                                fout.write('\t\t<item subcategory="%s">%s</item>\n' % (subcategory, FixHTMLEntities(row[1] + ' ' + row[2])))
                        else:
                                fout.write('\t\t<item>%s</item>\n' % FixHTMLEntities(row[1] + ' ' + row[2]))
                elif len(row) == 4 and row[0] == '' and (row[1] == '' or row[1] == '<IMG SRC="3lev.gif">'):
                        # <TR><TD></TD><TD></TD><TD>(b)</TD><TD>Great Portland Estates PLC</TD></TR>
                        subcategorymatch = re.match("\(([ab])\)$", row[2])
                        if not subcategorymatch:
                                content = FixHTMLEntities(row[2] + " " + row[3])
                                if subcategory:
                                        fout.write('\t\t<item subcategory="%s">%s</item>\n' % (subcategory, content))
                                else:
                                        fout.write('\t\t<item>%s</item>\n' % content)
                        else:
                                subcategory = subcategorymatch.group(1)
                                fout.write('\t\t(%s)\n' % subcategory)
                                fout.write('\t\t<item subcategory="%s">%s</item>\n' % (subcategory, FixHTMLEntities(row[3])))
                else:
                        print row
                        raise ContextException, "Unknown row type match, length %d" % (len(row))
        if category:
                fout.write('\t</category>\n')
        if needmemberend:
                fout.write('</regmem>\n')                                
                needmemberend = False

        membersetexpect = set([m['person_id'] for m in memberList.mpslistondate(sdate)])
        
        # check for missing/extra entries
        missing = membersetexpect.difference(memberset)
        if len(missing) > 0:
                print "Missing %d MP entries:\n" % len(missing), missing
        extra = memberset.difference(membersetexpect)
        if len(extra) > 0:
                print "Extra %d MP entries:\n" % len(extra), extra

	fout.write("</publicwhip>\n")

if __name__ == '__main__':
        from runfilters import RunFiltersDir
        RunFiltersDir(RunRegmemFilters, 'regmem', '1000-01-01', '9999-12-31', True)





