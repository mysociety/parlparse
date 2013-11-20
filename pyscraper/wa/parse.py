#! /usr/bin/env python

import re
import os
import glob
import sys
import time
import tempfile
import shutil

sys.path.append('../')
from contextexception import ContextException
from BeautifulSoup import BeautifulStoneSoup, Tag

import codecs
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

parldata = '../../../parldata/'

class ParseDay:
    def parse_day(self, fp, text, date):
        self.date = date
        self.text = text
        self.out = fp
        self.out = streamWriter(self.out)

        if date < '2013-01-01':
            raise Exception, 'Cannot parse pre 2013'

        self.parse_xml_day(date)
        #self.out.write('</publicwhip>\n')

    def display_preamble(self):
        self.out.write('<?xml version="1.0" encoding="utf-8"?>\n')
        self.out.write('''
<!DOCTYPE publicwhip
[
<!ENTITY pound   "&#163;">
<!ENTITY euro    "&#8364;">

<!ENTITY agrave  "&#224;">
<!ENTITY aacute  "&#225;">
<!ENTITY acirc   "&#226;">
<!ENTITY ccedil  "&#231;">
<!ENTITY egrave  "&#232;">
<!ENTITY eacute  "&#233;">
<!ENTITY ecirc   "&#234;">
<!ENTITY iacute  "&#237;">
<!ENTITY ograve  "&#242;">
<!ENTITY oacute  "&#243;">
<!ENTITY uacute  "&#250;">
<!ENTITY Aacute  "&#193;">
<!ENTITY Eacute  "&#201;">
<!ENTITY Iacute  "&#205;">
<!ENTITY Oacute  "&#211;">
<!ENTITY Uacute  "&#218;">
<!ENTITY Uuml    "&#220;">
<!ENTITY auml    "&#228;">
<!ENTITY euml    "&#235;">
<!ENTITY iuml    "&#239;">
<!ENTITY ntilde  "&#241;">
<!ENTITY ouml    "&#246;">
<!ENTITY uuml    "&#252;">
<!ENTITY fnof    "&#402;">

<!ENTITY nbsp    "&#160;">
<!ENTITY shy     "&#173;">
<!ENTITY deg     "&#176;">
<!ENTITY sup2    "&#178;">
<!ENTITY middot  "&#183;">
<!ENTITY ordm    "&#186;">
<!ENTITY frac14  "&#188;">
<!ENTITY frac12  "&#189;">
<!ENTITY frac34  "&#190;">
<!ENTITY ndash   "&#8211;">
<!ENTITY mdash   "&#8212;">
<!ENTITY lsquo   "&#8216;">
<!ENTITY rsquo   "&#8217;">
<!ENTITY ldquo   "&#8220;">
<!ENTITY rdquo   "&#8221;">
<!ENTITY hellip  "&#8230;">
<!ENTITY bull    "&#8226;">
]>

<publicwhip>
''')

    def getTagValue(self, item, tag_name):
        tag_n = item.getElementsByTagName(tag_name)
        if tag_n:
            tag_v = tag_n[0].firstChild.nodeValue
            return tag_v
        return ''

    def display_major_heading(self, item):
        agenda = self.getTagValue(item, 'Agenda_item_english')
        print '\n\n'
        print '###########################'
        print 'Major heading: %s' % agenda
        print '###########################'

    def get_english_text(self, item):
        lang = self.getTagValue(item, 'contribution_language')
        text = ''
        if lang == 'En':
            text = self.getTagValue(item, 'contribution_verbatim')
        else:
            text = self.getTagValue(item, 'contribution_translated')
        return text

    def new_speech(self, item):
        ctype = self.getTagValue(item, 'contribution_type')
        name = self.getTagValue(item, 'Member_name_English')
        speaker_id = self.getTagValue(item, 'Member_Id')
        text = self.getTagValue(item, 'contribution_verbatim')
        text_translated = self.getTagValue(item, 'contribution_translated')
        contribution_id = self.getTagValue( item, 'Contribution_ID')
        speech = { 
                'text': text,
                'text_translated': text,
                'speaker': speaker_id,
                'speaker_name': name,
                'ctype': ctype
            }
        return speech

    def add_to_speech(self, speech, item):
        text = self.getTagValue(item, 'contribution_verbatim')
        text_translated = self.getTagValue(item, 'contribution_translated')
        speech['text'] += '\n%s' % text
        speech['text_translated'] += '\n%s' % text_translated
        return speech

    def display_speech(self, speech):
        print ''
        print '-----------------'
        print 'type: %s, speaker: %s (%s)' % ( speech['ctype'], speech['speaker_name'], speech['speaker'])
        print '<div class="original">%s</div>' % speech['text']
        print '<div class="translated">%s</div>' % speech['text_translated']

    def display_vote(self, item, speech):
        print '\nVVVVVVVVVVVVVVVVVVVVVVVVVVVV'
        print 'Vote: %s' % speech['text']

    def parse_xml_day(self, date):
        soup = BeautifulStoneSoup(self.text)

        items = soup.find('XML_Plenary_Bilingual')
        #soup = soup('XML_Plenary_Bilingual')
        current_agenda_id = 0
        current_speaker = 0
        current_speech = 0 
        in_vote = 0
        for item in soup.dataroot.contents:
            agenda_id = ''
            try:
                agenda_id = item.contribution_type
                print agenda_id
            except:
                pass
            continue
            #['Agenda_Item_ID']
            agenda_id = self.getTagValue(item, 'Agenda_Item_ID')
            speaker_id = self.getTagValue(item, 'Member_Id')
            ctype = self.getTagValue(item, 'contribution_type')
            if current_speech == 0:
                current_speech = self.new_speech(item)

            if agenda_id != current_agenda_id:
                self.display_speech(current_speech)
                current_speech = self.new_speech(item)
                current_speaker = speaker_id
                current_agenda_id = agenda_id
                self.display_major_heading(item)
                continue

            elif speaker_id != current_speaker:
                current_speaker = speaker_id
                self.display_speech(current_speech)
                current_speech = self.new_speech(item)
                continue

            # TODO: DOES NOT WORK
            # see notes but can be M -> V
            # also amendments, not sure whats going on there 
            if ctype == 'V':
                self.display_vote(item, current_speech)
                current_speech = self.new_speech(item)

            current_speech = self.add_to_speech(current_speech, item)
