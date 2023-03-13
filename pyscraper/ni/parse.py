#! /usr/bin/env python3

import re
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ni.resolvenames import memberList
from contextexception import ContextException

parldata = '../../../parldata/'

class ParseDayParserBase(object):
    def __init__(self, fp, date, **kwargs):
        self.out = fp
        self.date = date
        self.idA = 0
        self.idB = 0

    def id(self):
        return '%s.%s.%s' % (self.date, self.idA, self.idB)

    def time_period(self, ptext, optional=False):
        match = re.search('(\d\d?)(?:[.:]\s*(\d\d?))? ?(am|pm|noon|midnight)', ptext)
        if not match:
            if not optional:
                raise ContextException('Time not found in TimePeriod %s' % p)
            return None
        hour = int(match.group(1))
        if hour<12 and match.group(3) == 'pm':
            hour += 12
        if hour==12 and match.group(3) in ('midnight', 'am'):
            hour = 0
        minutes = match.group(2) or '00'
        if len(minutes) == 1: minutes = '0' + minutes
        timestamp = "%s:%s" % (hour, minutes)
        return timestamp


class ParseDayJSON(ParseDayParserBase):
    def display_speech(self):
        if self.heading:
            timestamp = self.heading['ts']
            if timestamp:
                timestamp = ' time="%s"' % timestamp
            typ = self.heading['type']
            text = self.heading['text']
            if typ == 'major':
                self.idA += 1
                self.idB = 0
            else:
                self.idB += 1
            self.out.write('<%s-heading id="uk.org.publicwhip/ni/%s"%s>%s</%s-heading>\n' % (typ, self.id(), timestamp, text, typ))
            self.heading = {}
        if self.text:
            if 'id' in self.speaker:
                speaker_str = self.speaker['id']
            elif 'name' in self.speaker:
                speaker_str = 'person_id="unknown" speakername="%s"' % self.speaker['name']
            else:
                speaker_str = 'nospeaker="true"'
            timestamp = self.speaker.get('ts', '')
            if timestamp:
                timestamp = ' time="%s"' % timestamp
            self.idB += 1
            self.out.write('<speech id="uk.org.publicwhip/ni/%s" %s%s>\n%s</speech>\n' % (self.id(), speaker_str, timestamp, self.text))
            self.text = ''

    def parse_day(self, input):
        self.heading = {}
        self.pre_heading = {}
        self.speaker = {}
        self.text = ''
        timestamp = ''
        j = json.loads(input)
        if 'AllHansardComponentsList' in j:
            j = j['AllHansardComponentsList']['HansardComponent']
        for line in j:
            text = (line['ComponentText'] or '').replace('&', '&amp;')
            if not text:
                print("WARNING: Empty line: %s" % line)
            elif line['ComponentType'] == 'Document Title':
                assert re.match('(Plenary|PLE), %s/%s/%s$(?i)' % (self.date[8:10], self.date[5:7], self.date[0:4]), text), text
            elif line['ComponentType'] == 'Time':
                timestamp = self.time_period(text)
            elif line['ComponentType'] == 'Header':
                if line['ComponentHeaderId'] in (0, 1, '0', '1'):
                    typ = 'major'
                elif line['ComponentHeaderId'] in (2, '2'):
                    typ = 'minor'
                else:
                    raise Exception("Unknown ComponentHeaderId %s" % line['ComponentHeaderId'])
                if self.heading and self.heading['type'] == typ:
                    self.pre_heading = {'level': line['ComponentHeaderId'], 'text': self.heading['text']}
                    self.heading['text'] += ' &#8212; %s' % text
                else:
                    self.display_speech()
                    self.speaker = {'ts': timestamp}
                    if self.pre_heading and self.pre_heading['level'] == line['ComponentHeaderId']:
                        text = '%s &#8212; %s' % (self.pre_heading['text'], text)
                    elif self.pre_heading and self.pre_heading['level'] > line['ComponentHeaderId']:
                        self.pre_heading = {}
                    self.heading = {'text': text, 'ts': timestamp, 'type': typ}
            elif re.match('Speaker \((MlaName|DeputyChairAndName|ChairAndName|DeputySpeaker|PrincipalDeputySpeaker|MinisterAndName|ActingSpeaker|TemporarySpeaker|Speaker)\)$', line['ComponentType']):
                # RelatedItemId here is the NI speaker ID. We could use that!
                # But for now, carry on going by name as all that code exists.
                self.display_speech()
                speaker = text.replace(':', '')
                id, stri = memberList.match(speaker, self.date)
                self.speaker = {'id': stri, 'ts': timestamp}
            elif line['ComponentType'] == 'Speaker (Special)' or line['ComponentType'] == 'Speaker (GuestSpeaker)':
                self.display_speech()
                speaker = text.replace(':', '')
                self.speaker = {'name': speaker, 'ts': timestamp}
            elif line['ComponentType'] == 'Question':
                self.display_speech()
                m = re.match('(T?[0-9]+\. )?(.*?) asked', text)
                id, stri = memberList.match(m.group(2), self.date)
                self.speaker = {'id': stri, 'ts': timestamp}
                self.text += "<p>%s</p>\n" % text
            elif line['ComponentType'] == 'Quote':
                self.text += '<p class="indent">%s</p>\n' % text
            elif line['ComponentType'] in ('Plenary Item Text', 'Procedure Line'):
                match = re.match('The Assembly met at ((\d\d?):(\d\d?) (am|pm)|12 noon)', text)
                if match:
                    timestamp = self.time_period(text)
                    self.speaker['ts'] = timestamp
                self.text += '<p class="italic">%s</p>\n' % text
            elif line['ComponentType'] == 'Bill Text':
                self.text += text.replace('<p>', '<p class="indent">')  # Already is HTML
            elif line['ComponentType'] in ('Division', 'Spoken Text'):
                text = re.sub('\s*<BR />\s*<BR />\s*(?i)', '</p>\n<p>', text)
                text = re.sub('WIDTH=50%', 'WIDTH="50%"', text)
                self.text += '<p>%s</p>\n' % text
            else:
                raise ContextException("Uncaught Component Type! %s" % line['ComponentType'])
        self.display_speech()

class ParseDay(object):
    def parse_day(self, out, text, date):
        out.write('<?xml version="1.0" encoding="utf-8"?>\n')
        out.write('''
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
        if date > '2014-11-01':
            parser = ParseDayJSON(out, date)
        else:
            sys.exit("Parsing <=2014-11-01 HTML is no longer supported")
        parser.parse_day(text)
        out.write('</publicwhip>\n')


if __name__ == '__main__':
    fp = sys.stdout
    text = open(sys.argv[1]).read()
    date = os.path.basename(sys.argv[1])[2:12]
    ParseDay().parse_day(fp, text, date)
