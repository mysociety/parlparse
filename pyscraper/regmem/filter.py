#! /usr/bin/env python3
# vim:sw=8:ts=8:et:nowrap

import re
import os

from bs4 import BeautifulSoup
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


class RunRegmemFilters2010(object):
    title = None
    category = None
    subcategory = None
    record = False

    def __init__(self, fout, text, sdate):
        self.fout = fout
        self.text = text
        self.sdate = sdate
        self.memberset = set()

    def _handle_h2(self, row):
        title = row.encode_contents().decode('utf-8')
        if title in ('HAGUE, Rt Hon William (Richmond (Yorks)', 'PEARCE, Teresa (Erith and Thamesmead'):
            title += ')'
        res = re.search("^([^,]*), ([^(]*) \((.*)\)\s*$", title)
        if not res:
            raise ContextException("Failed to break up into first/last/cons: %s" % title)
        (lastname, firstname, constituency) = res.groups()
        firstname = memberList.striptitles(firstname.decode('utf-8'))[0]
        lastname = lastname.decode('utf-8')
        if self.sdate < '2015-06-01':
            lastname = memberList.lowercaselastname(lastname)
        constituency = constituency.decode('utf-8')
        lastname = lastname.replace('O\u2019brien', "O'Brien") # Hmm
        (id, remadename, remadecons) = memberList.matchfullnamecons(firstname + " " + lastname, constituency, self.sdate)
        if not id:
            raise ContextException("Failed to match name %s %s (%s) date %s\n" % (firstname, lastname, constituency, self.sdate))
        self.fout.write('<regmem personid="%s" membername="%s" date="%s">\n' % (id, remadename, self.sdate))
        self.title = title
        self.category = None
        self.subcategory = None
        self.record = False
        self.memberset.add(id)

    def parse(self):
        print("2010-? new register of members interests!  Check it is working properly (via mpinfoin.pl) - %s" % self.sdate)

        WriteXMLHeader(self.fout)
        self.fout.write("<publicwhip>\n")

        text = re.sub('<span class="highlight">([^<]*?)</span>', r'\1', self.text)
        soup = BeautifulSoup(text, 'lxml')
        for row in soup.body.children:
            if not row.name:
                continue # Space between tags
            if row.name == 'page':
                self._end_entry()
            elif row.name == 'h2':
                self._handle_h2(row)
            else:
                cls = row.get('class', [''])[0]
                text = row.encode_contents().decode('utf-8')
                if cls == 'spacer':
                    if self.record:
                        self.fout.write('\t\t</record>\n')
                        self.record = False
                    continue
                if not text or re.match('\s*\.\s*$', text): continue
                if text == '<strong>%s</strong>' % self.title: continue
                if re.match('\s*Nil\.?\s*$', text):
                    self.fout.write('Nil.\n')
                    continue
                # Since 2015 election, register is all paragraphs, no headings :(
                if row.name == 'h3' or cls == 'shd0' or re.match('<strong>\d+\. ', text):
                    if re.match('\s*$', text): continue
                    m = re.match("(?:\s*<strong>)?\s*(\d\d?)\.\s*(.*)(?:</strong>\s*)?$", text)
                    if m:
                        if self.record:
                            self.fout.write('\t\t</record>\n')
                            self.record = False
                        if self.category:
                            self.fout.write('\t</category>\n')
                        self.category, categoryname = m.groups()
                        self.subcategory = None
                        categoryname = re.sub('<[^>]*>(?s)', '', categoryname).strip()
                        self.fout.write('\t<category type="%s" name="%s">\n' % (self.category, categoryname))
                        continue
                if not self.record:
                    self.fout.write('\t\t<record>\n')
                    self.record = True
                # This never matches nowadays - work out what to do with it
                subcategorymatch = re.match("\s*\(([ab])\)\s*(.*)$", text)
                if subcategorymatch:
                    self.subcategory = subcategorymatch.group(1)
                    self.fout.write('\t\t\t(%s)\n' % self.subcategory)
                    self.fout.write('\t\t\t<item subcategory="%s">%s</item>\n' % (self.subcategory, subcategorymatch.group(2)))
                    continue
                if self.subcategory:
                    self.fout.write('\t\t\t<item subcategory="%s">%s</item>\n' % (self.subcategory, text))
                else:
                    cls = cls.decode('utf-8')
                    if cls: cls = ' class="%s"' % cls
                    self.fout.write('\t\t\t<item%s>%s</item>\n' % (cls, text))
        self._end_entry()
        self.fout.write("</publicwhip>\n")

        self.check_missing()

    def check_missing(self):
        # check for missing/extra entries
        membersetexpect = set([m['person_id'] for m in memberList.mpslistondate(self.sdate)])
        missing = membersetexpect.difference(self.memberset)
        if len(missing) > 0:
            print("Missing %d MP entries:\n" % len(missing), missing)
        extra = self.memberset.difference(membersetexpect)
        if len(extra) > 0:
            print("Extra %d MP entries:\n" % len(extra), extra)

    def _end_entry(self):
        if self.record:
            self.fout.write('\t\t</record>\n')
        if self.category:
            self.fout.write('\t</category>\n')
        if self.title:
            self.fout.write('</regmem>\n')


def RunRegmemFilters(fout, text, sdate, sdatever):
    if sdate >= '2010-09-01':
        return RunRegmemFilters2010(fout, text, sdate).parse()
    sys.exit('Parsing regmem HTML before 2010-09-01 is no longer supported')


if __name__ == '__main__':
        from runfilters import RunFiltersDir
        RunFiltersDir(RunRegmemFilters, 'regmem', '2010-09-01', '9999-12-31', True)
