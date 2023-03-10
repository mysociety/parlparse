#! /usr/bin/python
# vim:sw=8:ts=8:et:nowrap

import re
import os

from BeautifulSoup import BeautifulStoneSoup
from contextexception import ContextException
from resolvemembernames import memberList
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
                firstname = memberList.striptitles(firstname.decode('utf-8'))[0]
                lastname = lastname.decode('utf-8')
                if sdate < '2015-06-01':
                    lastname = memberList.lowercaselastname(lastname)
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
                        # This never matches nowadays - work out what to do with it
                        subcategorymatch = re.match("\s*\(([ab])\)\s*(.*)$", text)
                        if subcategorymatch:
                                subcategory = subcategorymatch.group(1)
                                fout.write('\t\t\t(%s)\n' % subcategory)
                                fout.write('\t\t\t<item subcategory="%s">%s</item>\n' % (subcategory, subcategorymatch.group(2)))
                                continue
                        if subcategory:
                                fout.write('\t\t\t<item subcategory="%s">%s</item>\n' % (subcategory, text))
                        else:
                                cls = row.get('class', '').decode('utf-8').encode('iso-8859-1')
                                if cls: cls = ' class="%s"' % cls
                                fout.write('\t\t\t<item%s>%s</item>\n' % (cls, text))
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


def RunRegmemFilters(fout, text, sdate, sdatever):
    if sdate >= '2010-09-01':
        return RunRegmemFilters2010(fout, text, sdate, sdatever)
    sys.exit('Parsing regmem HTML before 2010-09-01 is no longer supported')


if __name__ == '__main__':
        from runfilters import RunFiltersDir
        RunFiltersDir(RunRegmemFilters, 'regmem', '2010-09-01', '9999-12-31', True)
