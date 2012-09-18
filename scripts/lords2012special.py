#!/usr/bin/env python
#
# Lords Written Answers over the 2012 summer recess are output in a different
# format. This just quickly makes an XML file from it, not totally robust.

import os
import codecs
import sys
import re
import urllib
import time
from BeautifulSoup import BeautifulSoup, NavigableString

import xml.sax
xmlvalidate = xml.sax.make_parser()

sys.path.append('../pyscraper/')
sys.path.append('../pyscraper/lords/')
from resolvelordsnames import lordsList

# The days that have had written answers so far
days = (
    ('31','07','2012'), ('06','08','2012'), ('13','08','2012'),
    ('20','08','2012'), ('28','08','2012'), ('03','09','2012'),
    ('10','09','2012'), ('17','09','2012')
)

for day in days:
    date = '%s-%s-%s' % (day[2], day[1], day[0])
    type = 'lordswrans'
    fn = '../../parldata/scrapedxml/%s/%s%sa.xml' % (type, type, date)
    if os.path.exists(fn):
        continue

    url = 'http://www.publications.parliament.uk/pa/ld/ldtoday/writtens/%s%s%s.htm' % day
    u = urllib.urlopen(url)
    d = u.read()
    code = u.getcode()
    if code == 404: # Not there yet
        continue
    soup = BeautifulSoup(d)
    content = soup.find('div', 'hansardContent')

    ques_id = None
    after_question = False
    in_reply = False
    id = 0
    out = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip scrapeversion="a" latest="yes">
'''
    for child in content.contents:
        if isinstance(child, NavigableString) and re.match('\s+$', child): continue # Ignore gaps
        name = child.name
        cl = child.get('class', None)
        namecl = (name, cl)
        text = ''.join(child(text=True))

        # Ignore stuff
        if name == 'hr': continue
        elif namecl == ('ul', 'prevNext'): continue
        elif namecl == ('p', None): continue
        elif namecl == ('h1', 'mainTitle') and text == 'House of Lords': continue
        elif namecl == ('h2', 'mainSubTitle') and text in ('Summer Recess 2012', 'Written Answers and Statements'): continue
        elif namecl == ('p', 'DebateType') and text in ('Question', 'Questions'): continue
        if not text: continue

        if namecl == ('h2', 'DebateHeading'):
            minor_heading_text = text.replace('&#160;', ' ').strip()
            minor_heading_first = ''
        elif namecl == ('p', 'TabledBy'):
            # Get speaker
            ques_name = child.strong.string
            last_ques_id = ques_id
            ques_id = lordsList.GetLordIDfname(ques_name, loffice=None, sdate=date)
            if after_question and ques_id == last_ques_id:
                continue # Another question, same speaker, shouldn't be here.
            after_question = False
            if in_reply:
                out += '</reply>\n'
                in_reply = False
            out += '<minor-heading%s id="uk.org.publicwhip/wrans/%sa.0.%d" nospeaker="true" colnum="0" url="">%s</minor-heading>\n' % (minor_heading_first, date, id, minor_heading_text)
            id += 1
            if not minor_heading_first:
                minor_heading_first = ' inserted-heading="true"'
        elif namecl == ('p', 'Question'):
            text = re.sub('\[\s*HL', '[HL', text)
            if in_reply:
                out += '</reply>\n'
                in_reply = False
            # Each question needs a heading to be displayed separately
            out += '<ques id="uk.org.publicwhip/wrans/%sa.0.%d" speakerid="%s" speakername="%s" colnum="0" url=""><p>%s</p></ques>\n' % (date, id, ques_id, ques_name, text.replace('[HL', ' [HL'))
            id += 1
            after_question = True
        elif namecl == ('p', 'para'):
            if after_question:
                after_question = False
                colon = text.find(':')
                reply_name = text[:colon]
                m = re.search('\((.*?)\)', reply_name)
                if m:
                    reply_name = m.group(1)
                reply_id = lordsList.GetLordIDfname(reply_name, loffice=None, sdate=date)
                text = text[colon+2:]
                out += '<reply id="uk.org.publicwhip/wrans/%sa.0.%d" speakerid="%s" speakername="%s" colnum="0" url="">\n' % (date, id, reply_id, reply_name)
                id += 1
                in_reply = True
            out += '<p>%s</p>\n' % text.strip()
        elif namecl == ('p', 'WAIndent'):
            out += '<p class="indent">%s</p>\n' % text
        elif namecl in ( ('p', 'WrittensFootnote'), ('p', 'parafo') ):
            out += '<p>%s</p>\n' % text
        elif name == 'table' and cl in ('TableGrid', 'prettyTable'):
            out += unicode(child)
        else:
            raise Exception, child

    if in_reply: out += '</reply>\n'
    out += '</publicwhip>'
    fp = codecs.open( fn, 'w', encoding='iso-8859-1', errors='xmlcharrefreplace' )
    fp.write(out)
    fp.close()
    xmlvalidate.parse(fn)
    fp = open('../../parldata/scrapedxml/lordspages/changedates.txt', 'a')
    fp.write('%s,%s%s\n' % (int(time.time()), type, date))
    fp.close()

