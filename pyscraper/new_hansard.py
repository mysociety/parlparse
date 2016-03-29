#! /usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import sys
from lxml import etree
import xml.sax
import mx.DateTime
xmlvalidate = xml.sax.make_parser()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'lords'))

import codecs
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

from resolvemembernames import MemberList
from resolvenames import LordsList

parldata = '../../../parldata/'

xml_parser = etree.XMLParser(ns_clean=True)
etree.set_default_parser(xml_parser)


class PimsList(MemberList):

    def match_by_pims(self, pims_id):
        match = self.pims.get(pims_id, None)
        return match


class LordsPimsList(LordsList):

    def match_by_pims(self, pims_id):
        match = self.pims.get(pims_id, None)
        return match


class BaseParseDayXML(object):
    resolver = PimsList()

    type_to_xpath = {
        'debate': (
            '//ns:System[@type="Debate"]',
            'http://www.parliament.uk/commons/hansard/print'
        ),
        'westhall': (
            '//ns:System[@type="WestHall"]',
            'http://www.parliament.uk/commons/hansard/print'
        ),
        'lords': (
            '//ns:System[@type="Debate"]',
            'http://www.parliament.uk/lords/hansard/print'
        ),
        'pbc': (
            '//ns:System[@type="Debate"]',
            'http://www.parliament.uk/commons/hansard/print'
        ),
    }

    oral_headings = [
        'hs_3OralAnswers'
    ]
    major_headings = [
        'hs_6bDepartment',
        'hs_6bBigBoldHdg',
        'hs_2cBillTitle',
        'hs_2cGenericHdg',
        'hs_2GenericHdg',
        'hs_2cUrgentQuestion',
    ]
    minor_headings = [
        'hs_8Question',
        'hs_2cDebatedMotion'
    ]
    whall_headings = [
        'hs_2DebBill',
        'hs_2cWestHallDebate'
    ]
    paras = [
        'hs_Para',
    ]
    ignored_tags = [
        'hs_6bPetitions',
        'hs_76fChair',
        'hs_3MainHdg'
    ]
    root = etree.Element('publicwhip')
    ns = ''
    ns_map = {}

    debate_type = None
    current_speech = None
    date = ''
    rev = 'a'
    current_col = 0
    current_speech_num = 0
    current_speech_part = 1
    current_time = ''

    def get_tag_name_no_ns(self, tag):
        # remove annoying namespace for brevities sake
        tag_name = str(tag.tag)
        tag_name = tag_name.replace(
            '{{{0}}}'.format(self.ns),
            ''
        )
        return tag_name

    def get_pid(self):
        return '{0}{1}.{2}/{3}'.format(
            self.rev,
            self.current_col,
            self.current_speech_num,
            self.current_speech_part
        )

    def get_speech_id(self):
        return 'uk.org.publicwhip/{0}/{1}{2}.{3}.{4}'.format(
            self.debate_type,
            self.date,
            self.rev,
            self.current_col,
            self.current_speech_num
        )

    def check_for_pi(self, tag):
        pi = tag.xpath('.//processing-instruction("notus-xml")')
        if len(pi) == 1:
            self.parse_pi(pi[0])

    def clear_current_speech(self):
        if self.current_speech is not None:
            self.root.append(self.current_speech)
        self.current_speech_part = 1
        self.current_speech_num = self.current_speech_num + 1
        self.current_speech = None

    def new_speech(self, member, url):
        if self.current_speech is not None:
            self.clear_current_speech()
        self.current_speech = etree.Element('speech')
        self.current_speech.set('id', self.get_speech_id())
        if member is not None:
            self.current_speech.set('person_id', member['person_id'])
            self.current_speech.set('speakername', member['name'])
        else:
            self.current_speech.set('nospeaker', 'true')
        self.current_speech.set('colnum', self.current_col)
        self.current_speech.set('time', self.current_time)
        self.current_speech.set(
            'url',
            'http://www.publications.parliament.uk{0}'.format(
                url
            )
        )

    def parse_system_header(self, header):
        sitting = header.xpath('./ns:Sitting', namespaces=self.ns_map)[0]
        date = mx.DateTime.DateTimeFrom(sitting.get('short-date')).date
        if date:
            self.date = date

    def parse_member(self, tag):
        member_tag = None
        tag_name = self.get_tag_name_no_ns(tag)
        if tag_name == 'B':
            member_tag = tag.xpath('.//ns:Member', namespaces=self.ns_map)[0]
        elif tag_name == 'Member':
            member_tag = tag

        if member_tag is not None:
            if member_tag.get('PimsId') == '-1':
                return None
            member = self.resolver.match_by_pims(member_tag.get('PimsId'))
            if member is not None:
                member['person_id'] = member.get('id')
                member['name'] = self.resolver.name_on_date(member['person_id'], self.date)
                return member
            else:
                sys.stderr.write('No match for PimsId {0}'.format(member_tag.get('PimsId')))

        return None

    def parse_date(self, date):
        text = u''.join(date.xpath(".//text()"))
        time_parts = re.match('\s*the\s+house (?:being |having )?met at?\s+(.*?)$(?i)', text)
        if time_parts:
            time = time_parts.group(1)
            time = re.sub('</?i>',' ', time)
            time = re.sub('\s+',' ', time)
            if re.match("half-past Nine(?i)", time):
                    newtime = '09:30:00'
            elif re.match("a quarter to Ten o(?i)", time):
                    newtime = '09:45:00'
            elif re.match("Ten o'clock(?i)", time):
                    newtime = '10:00:00'
            elif re.match("half-past Ten(?i)", time):
                    newtime = '10:30:00'
            elif re.match("Eleven o&#039;clock(?i)", time):
                    newtime = '11:00:00'
            elif re.match("twenty-five minutes past\s*Eleven(?i)", time):
                    newtime = '11:25:00'
            elif re.match("twenty-six minutes past\s*Eleven(?i)", time):
                    newtime = '11:26:00'
            elif re.match("twenty-nine minutes past\s*Eleven(?i)", time):
                    newtime = '11:29:00'
            elif re.match("half-past Eleven(?i)", time):
                    newtime = '11:30:00'
            elif re.match("Twelve noon(?i)", time):
                    newtime = '12:00:00'
            elif re.match("half-past One(?i)", time):
                    newtime = '13:30:00'
            elif re.match("half-past Two(?i)", time):
                    newtime = '14:30:00'
            elif re.match("twenty minutes to Three(?i)", time):
                    newtime = '14:40:00'
            elif re.match("10 minutes past Three(?i)", time):
                    newtime = '15:10:00'
            elif re.match("Six o'clock(?i)", time):
                    newtime = '18:00:00'

            self.time = newtime

    def parse_oral_heading(self, heading):
        tag = etree.Element('oral-heading')
        tag.text = heading.text
        self.root.append(tag)

    def parse_major(self, heading, **kwargs):
        self.clear_current_speech()
        tag = etree.Element('major-heading')
        text = u"".join(heading.xpath(".//text()"))
        tag.text = text

        if 'extra_text' in kwargs:
            tag.text = u'{0} - '.format(tag.text)
            i = etree.Element('i')
            i.text = kwargs['extra_text']
            tag.append(i)

        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        tag.set(
            'url',
            'http://www.publications.parliament.uk{0}'.format(
                heading.get('url')
            )
        )
        self.root.append(tag)

    def parse_minor(self, heading):
        self.clear_current_speech()
        tag = etree.Element('minor-heading')
        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        tag.set(
            'url',
            'http://www.publications.parliament.uk{0}'.format(
                heading.get('url')
            )
        )
        text = u"".join(heading.xpath("./text()"))
        tag.text = text
        self.root.append(tag)

    def parse_WHDebate(self, debate):
        text = u''.join(debate.xpath('.//text()'))

        chair = debate.xpath(
            '(./preceding-sibling::ns:hs_76fChair | ./following-sibling::ns:hs_76fChair)',
            namespaces=self.ns_map
        )
        if len(chair) == 1:
            chair_text = u''.join(chair[0].xpath('.//text()'))
            text = u'{0} — {1}'.format(text, chair_text)

        self.clear_current_speech()
        tag = etree.Element('minor-heading')
        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        tag.set(
            'url',
            'http://www.publications.parliament.uk{0}'.format(
                debate.get('url')
            )
        )
        tag.text = text
        self.root.append(tag)

    def parse_question(self, question):
        tag = etree.Element('speech')
        tag.set('id', self.get_speech_id())
        tag.set('time', self.current_time)

        member = question.xpath('.//ns:Member', namespaces=self.ns_map)[0]
        member = self.parse_member(member)
        if member is not None:
            tag.set('person_id', member['person_id'])

        text = question.xpath(
            './/ns:QuestionText/text()', namespaces=self.ns_map
        )
        tag.text = u''.join(text)
        self.root.append(tag)

    def parse_petition(self, petition):
        petition.text = u'Petition - {0}'.format(petition.text)
        self.parse_major(petition)

    def parse_para_with_member(self, para, member, **kwargs):
        if member is not None:
            self.new_speech(member, para.get('url'))
        elif self.current_speech is None:
            self.new_speech(None, para.get('url'))

        tag = etree.Element('p')
        # this makes the text fetching a bit easier
        for m in para.xpath('.//ns:Member', namespaces=self.ns_map):
            m.getparent().text = m.tail
            m.getparent().remove(m)

        text = u"".join(para.xpath(".//text()"))
        if len(text) == 0:
            return

        tag.set('pid', self.get_pid())
        if 'css_class' in kwargs:
            tag.set('class', kwargs['css_class'])
        if 'pwmotiontext' in kwargs:
            tag.set('pwmotiontext', kwargs['pwmotiontext'])
        self.current_speech_part = self.current_speech_part + 1
        tag.text = text

        self.current_speech.append(tag)
        self.check_for_pi(para)

    # TODO: this needs to parse out the various things that filtersentence
    # catches at the moment. Some of those might be in the XML but mostly
    # it will need to be a port of that to create proper XML elements
    # using etree
    def parse_para(self, para):
        member = None
        for tag in para:
            tag_name = self.get_tag_name_no_ns(tag)
            if tag_name == 'B' or tag_name == 'Member':
                member = self.parse_member(tag)

        self.parse_para_with_member(para, member)

    def parse_brev(self, brev):
        tag = etree.Element('p')
        tag.set('pwmotiontext', 'yes')
        text = u"".join(brev.xpath(".//text()"))
        if len(text) == 0:
            return

        tag.set('pid', self.get_pid())
        self.current_speech_part = self.current_speech_part + 1
        tag.text = text
        self.current_speech.append(tag)

    def parse_votelist(self, votes, direction, vote_list, is_teller=False):
        for vote in votes:
            tag = etree.Element('mpname')
            member = self.parse_member(vote)
            tag.set('person_id', member['person_id'])
            tag.set('vote', direction)
            if is_teller:
                tag.set('teller', 'yes')
            tag.text = member['name']
            vote_list.append(tag)

        return vote_list

    def parse_division(self, division):
        tag = etree.Element('division')

        tag.set('id', self.get_speech_id())
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)

        ayes_count = \
            division.xpath('.//ns:AyesNumber/text()', namespaces=self.ns_map)
        noes_count = \
            division.xpath('.//ns:NoesNumber/text()', namespaces=self.ns_map)

        div_count = etree.Element('divisioncount')
        div_count.set('ayes', u''.join(ayes_count))
        div_count.set('noes', u''.join(noes_count))

        tag.append(div_count)

        ayes = division.xpath(
            './/ns:NamesAyes//ns:Member', namespaces=self.ns_map
        )
        noes = division.xpath(
            './/ns:NamesNoes//ns:Member', namespaces=self.ns_map
        )

        aye_tellers = division.xpath(
            './/ns:TellerNamesAyes//ns:Member', namespaces=self.ns_map
        )
        noe_tellers = division.xpath(
            './/ns:TellerNamesNoes//ns:Member', namespaces=self.ns_map
        )

        aye_list = etree.Element('mplist')
        aye_list.set('vote', 'aye')
        aye_list = self.parse_votelist(ayes, 'aye', aye_list)
        aye_list = self.parse_votelist(aye_tellers, 'aye', aye_list, True)
        tag.append(aye_list)

        noe_list = etree.Element('mplist')
        noe_list.set('vote', 'no')
        noe_list = self.parse_votelist(noes, 'no', noe_list)
        noe_list = self.parse_votelist(noe_tellers, 'no', noe_list, True)
        tag.append(noe_list)

        self.root.append(tag)

    def parse_timeline(self, tag):
        time = u''.join(tag.xpath('.//text()'))
        self.current_time = time

    def parse_pi(self, pi):
        # you would think there is a better way to do this but I can't seem
        # to extract attributes from processing instructions :(
        text = str(pi)
        matches = re.search(r'column=(\d+)\?', text)
        if matches is not None:
            col = matches.group(1)
            self.current_col = col
            self.current_speech_num = 0
            self.current_speech_part = 1

    def handle_tag(self, tag_name, tag):
        handled = True

        if tag_name == 'hs_6fDate':
            self.parse_date(tag)
        elif tag_name in self.oral_headings:
            self.parse_oral_heading(tag)
        elif tag_name in self.major_headings:
            self.parse_major(tag)
        elif tag_name in self.minor_headings:
            self.parse_minor(tag)
        elif tag_name in self.whall_headings:
            self.parse_WHDebate(tag)
        elif tag_name == 'Question':
            self.parse_question(tag)
        elif tag_name == 'hs_8Petition':
            self.parse_petition(tag)
        elif tag_name in self.paras:
            self.parse_para(tag)
        elif tag_name == 'hs_brev':
            self.parse_brev(tag)
        elif tag_name == 'Division':
            self.parse_division(tag)
        elif tag_name == 'hs_Timeline':
            self.parse_timeline(tag)
        elif type(tag) is etree._ProcessingInstruction:
            self.parse_pi(tag)
        elif tag_name in self.ignored_tags:
            pass
        else:
            handled = False

        return handled

    def parse_day(self, xml_file, out):
        self.ns = self.type_to_xpath[self.debate_type][1]
        self.ns_map = {'ns': self.ns}
        root_xpath = self.type_to_xpath[self.debate_type][0]

        xml = etree.parse(xml_file).getroot()
        commons = xml.xpath(
            root_xpath, namespaces=self.ns_map
        )
        if len(commons) == 0:
            sys.stderr.write(
                'Failed to find any debates of type {0}'
                .format(self.debate_type)
            )
            sys.exit()
        self.current_col = commons[0].get('ColStart')

        headers = commons[0].xpath(
            './/ns:Fragment/ns:Header', namespaces=self.ns_map
        )
        self.parse_system_header(headers[0])

        body_tags = commons[0].xpath(
            './/ns:Fragment/ns:Body', namespaces=self.ns_map
        )
        for b in body_tags:
            for tag in b:

                tag_name = self.get_tag_name_no_ns(tag)
                if not self.handle_tag(tag_name, tag):
                    sys.stderr.write(
                        "no idea what to do with {0}\n".format(tag_name)
                    )


class CommonsParseDayXML(BaseParseDayXML):
    pass


class LordsParseDayXML(BaseParseDayXML):
    resolver = LordsPimsList()

    paras = [
        'hs_para',
        'hs_quote',
        'hs_quotefo',
        'hs_parafo'
    ]

    ignored_tags = ['hs_date']

    def parse_time(self, tag):
        time_txt = u''.join(tag.xpath('.//text()'))
        matches = re.match('(\d+).(\d+)\s*(am|pm)', time_txt)
        if matches:
            hours = int(matches.group(1))
            # mmmmmm
            if matches.group(3) == 'pm':
                hours = hours + 12
            time = mx.DateTime.DateTimeFrom(hour=hours, minute=int(matches.group(2)))
            self.current_time = time.strftime('%H:%M:%S')

    def parse_quote(self, quote):
        tag = etree.Element('p')
        tag.set('pid', self.get_pid())
        tag.set('class', 'indent')

        tag.text = quote.text

        i = quote.xpath('./ns:I', namespaces=self.ns_map)
        if len(i) == 1:
            i_text = u''.join(i[0].xpath('./text()'))
            new_i = etree.Element('i')
            new_i.text = i_text
            new_i.tail = i[0].tail
            if re.match(r'Official Report,?$', i_text):
                phrase = etree.Element('phrase')
                phrase.set('class', 'offrep')
                # FIXME: generate a proper id here
                phrase.set('id', new_i.tail)
                phrase.append(new_i)
                tag.append(phrase)
            else:
                tag.append(new_i)

        self.current_speech.append(tag)

    def parse_member(self, member):
        found_member = super(LordsParseDayXML, self).parse_member(member)
        if found_member is None:
            if member.get('PimsId') == 0:
                found_member = {
                    'person_id': 'unknown',
                    'name': u''.join(member.xpath('.//text()'))
                }

        return found_member

    def parse_newdebate(self, tag):
        heading = tag.xpath('.//ns:hs_DebateHeading', namespaces=self.ns_map)
        debate_type = tag.xpath('.//ns:hs_DebateType', namespaces=self.ns_map)
        if len(heading):
            if len(debate_type):
                text = u"".join(debate_type[0].xpath(".//text()"))
                self.parse_major(heading[0], extra_text=text)
            else:
                self.parse_major(heading[0])
        else:
            sys.stderr.write('newdebate with no heading', namespaces=self.ns_map)
            return

        procedure = tag.xpath('//ns:hs_Procedure', namespaces=self.ns_map)
        if len(procedure) == 1:
            self.handle_para(procedure[0])

        if tag.get('BusinessType') == 'Question':
            member = tag.xpath('.//ns:Member', namespaces=self.ns_map)
            member = self.parse_member(member[0])
            questions = tag.xpath('//ns:hs_Question', namespaces=self.ns_map)
            for question in questions:
                self.parse_para_with_member(question, member)

    def parse_procedure(self, procedure):
        tag = etree.Element('p')
        text = u"".join(procedure.xpath(".//text()"))
        if len(text) == 0:
            return

        tag.set('pid', self.get_pid())
        tag.set('class', 'italic')
        self.current_speech_part = self.current_speech_part + 1
        tag.text = text

        if self.current_speech is not None:
            self.current_speech.append(tag)

    def parse_amendment_heading(self, heading):
        self.new_speech(None, heading.get('url'))
        self.parse_para_with_member(heading, None)

    def parse_tabledby(self, tabledby):
        self.parse_para_with_member(
            tabledby,
            None,
            css_class='italic',
            pwmotiontext='unrecognized'
        )

    def parse_amendment(self, amendment):
        self.parse_para_with_member(
            amendment,
            None,
            css_class='italic',
            pwmotiontext='unrecognized'
        )

    def parse_clause_heading(self, heading):
        tag = etree.Element('p')
        text = u"".join(heading.xpath(".//text()"))
        i = etree.Element('i')
        i.text = text
        b = etree.Element('b')
        b.append(i)

        tag.set('pid', self.get_pid())
        tag.append(b)
        if self.current_speech is None:
            self.new_speech(None, heading.get('url'))
        self.current_speech.append(tag)

    def handle_tag(self, tag_name, tag):
        handled = True

        if tag_name == 'hs_time':
            self.parse_time(tag)
        elif tag_name == 'hs_quotefo':
            self.parse_quote(tag)
        elif tag_name == 'NewDebate':
            self.parse_newdebate(tag)
        elif tag_name == 'hs_Procedure':
            self.parse_procedure(tag)
        elif tag_name == 'hs_AmendmentHeading':
            self.parse_amendment_heading(tag)
        elif tag_name == 'hs_TabledBy':
            self.parse_tabledby(tag)
        elif tag_name == 'Amendment':
            self.parse_amendment(tag)
        elif tag_name == 'hs_ClauseHeading':
            self.parse_clause_heading(tag)
        else:
            handled = super(LordsParseDayXML, self).handle_tag(tag_name, tag)

        return handled


class ParseDay(object):
    valid_types = [
        'debate',
        'westhall',
        'lords',
        'pbc'
    ]

    def parse_day(self, fp, text, date, debate_type):
        if debate_type not in self.valid_types:
            sys.stderr.write('{0} not a valid type'.format(debate_type))
            sys.exit()
        out = streamWriter(fp)
        if debate_type == 'lords':
            parser = LordsParseDayXML()
        else:
            parser = CommonsParseDayXML()
        parser.debate_type = debate_type
        parser.parse_day(text, out)
        out.write(etree.tostring(parser.root))


if __name__ == '__main__':
    fp = sys.stdout
    xml_file = codecs.open(sys.argv[1], encoding='utf-8')
    house = sys.argv[2]
    date = os.path.basename(sys.argv[1])[2:12]
    ParseDay().parse_day(fp, xml_file, date, house)
