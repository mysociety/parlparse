#! /usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import sys
import io
import tempfile
from lxml import etree
import xml.sax
import mx.DateTime
import miscfuncs

xmlvalidate = xml.sax.make_parser()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'lords'))

import codecs
streamWriter = codecs.lookup('utf-8')[-1]
sys.stdout = streamWriter(sys.stdout)

from pullgluepages import MakeDayMap, GetFileDayVersions
from miscfuncs import pwxmldirs
from resolvemembernames import MemberList
from resolvenames import LordsList
from filtersentence_xml import PhraseTokenize
from gidmatching import PrepareXMLForDiff, DoFactorDiff
from contextexception import ContextException
from xmlfilewrite import WriteXMLHeader

parldata = '../../../parldata/'

xml_parser = etree.XMLParser(ns_clean=True)
etree.set_default_parser(xml_parser)


class PimsList(MemberList):
    def pbc_match(self, name, date):
        name = re.sub(r'\n', ' ', name)
        # names are mostly lastname,\nfirstname so reform first
        if re.search(',', name):
            last, first = name.split(',')
            full = u'{0} {1}'.format(first.strip(), last.strip())
        # apart from committee chairman which we can use as is
        else:
            full = name.strip()
        ids = self.fullnametoids(full, date)
        if len(ids) == 1:
            mem_id = ids.pop()
            person_id = self.membertopersonmap[mem_id]
            member = self.persons[person_id]
            member['person_id'] = member.get('id')
            member['name'] = self.name_on_date(member['person_id'], date)
            return member

        return None


class BaseParseDayXML(object):
    input_root = None
    resolver = PimsList()

    type_to_xpath = {
        'debate': (
            '//ns:System[@type="Debate"]',
            'http://www.parliament.uk/commons/hansard/print'
        ),
        'westminhall': (
            '//ns:System[@type="WestHall"]',
            'http://www.parliament.uk/commons/hansard/print'
        ),
        'lords': (
            '//ns:System[@type="Debate"]',
            'http://www.parliament.uk/lords/hansard/print'
        ),
        'standing': (
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
        'hs_2cUrgentQuestion',
        'hs_3cMainHdg',
        'hs_2BusinessWODebate',
        'hs_2cStatement',
        'hs_2BillTitle',
        'hs_6bBillTitle',
        'hs_6bBusinessB4Questions',
        'hs_6bPrivateBusiness',
        'hs_6bRoyalAssent',
        'hs_6bBillsPresented', # FIXME should grab text of following tag
        'hs_6fCntrItalHdg',
        'hs_2cSO24Application',
        'hs_6bFormalmotion',
        'hs_2cDeferredDiv',
        'hs_3cPetitions',
    ]
    chair_headings = [
        'hs_76fChair',
    ]
    minor_headings = [
        'hs_8Question',
        'hs_8GenericHdg',
        'hs_8Clause',
        'hs_7SmCapsHdg',
        'hs_7PrivateBusinessHdg',
        'hs_7Bill',
        'hs_6bcBigBoldHdg',
        'hs_6bCorrection',
    ]
    generic_headings = [
        'hs_2cDebatedMotion',
        'hs_2cGenericHdg',
        'hs_2GenericHdg',
    ]
    whall_headings = [
        'hs_2cWestHallDebate',
        'hs_2WestHallDebate'
    ]
    paras = [
        'hs_Para',
        'hs_AmendmentLevel1',
        'hs_AmendmentLevel2',
        'hs_AmendmentLevel3',
        'hs_AmendmentLevel4',
        'hs_AmendmentHeading',
        'hs_newline10',
        'hs_newline12',
        'hs_Question',
        'hs_6CntrCapsHdg',
    ]
    indents = [
        'hs_quote',
        'hs_QuoteAllIndent',
        'hs_ParaIndent',
        'hs_AmendmentLevel0',
        'hs_IndentOne',
        'hs_IndentTwo',
    ]
    empty_tags = [
        'StartProcedure',
        'EndProcedure',
    ]
    ignored_tags = [
        'hs_TimeCode',
        'hs_6bPetitions',
        'hs_3MainHdg',
        'hs_3cWestHall',
        'hs_Venue'
    ]
    root = None
    ns = ''
    ns_map = {}

    debate_type = None
    current_speech = None
    date = ''
    rev = 'a'
    use_pids = True
    current_col = 0
    current_speech_col = 0
    current_speech_num = 0
    next_speech_num = 0
    current_speech_part = 1
    current_time = ''
    output_heading = False
    skip_tag = None
    uc_titles = False

    def __init__(self):
        self.reset()

    def reset(self):
        self.debate_type = None
        self.current_speech = None
        self.date = ''
        self.rev = 'a'
        self.current_col = 0
        self.current_speech_col = 0
        self.current_speech_num = 0
        self.next_speech_num = 0
        self.current_speech_part = 1
        self.current_time = ''
        self.root = None
        self.input_root = None
        self.output_heading = False

    def is_pre_new_parser(self):
        is_pre = False
        parser_start = mx.DateTime.Date(2016, 4, 1)
        file_date = mx.DateTime.DateTimeFrom(self.date)

        if file_date < parser_start:
            is_pre = True

        return is_pre

    def get_tag_name_no_ns(self, tag):
        # remove annoying namespace for brevities sake
        tag_name = str(tag.tag)
        tag_name = tag_name.replace(
            '{{{0}}}'.format(self.ns),
            ''
        )
        return tag_name

    def get_pid(self):
        pid = '{0}{1}.{2}/{3}'.format(
            self.rev,
            self.current_speech_col,
            self.current_speech_num,
            self.current_speech_part
        )
        self.current_speech_part = self.current_speech_part + 1
        return pid

    def get_speech_id_first_part(self):
        return self.date

    def get_speech_url(self, url):
        return ''

    def get_major_url(self, url):
        return ''

    def get_minor_url(self, url):
        return ''

    def get_speech_id(self):
        speech_id = 'uk.org.publicwhip/{0}/{1}{2}.{3}.{4}'.format(
            self.debate_type,
            self.get_speech_id_first_part(),
            self.rev,
            self.current_speech_col,
            self.next_speech_num
        )
        self.current_speech_num = self.next_speech_num
        if self.current_speech_col == self.current_col:
            self.next_speech_num += 1
        else:
            self.next_speech_num = 0
        self.current_speech_part = 1
        return speech_id

    def check_for_pi(self, tag):
        pi = tag.xpath('.//processing-instruction("notus-xml")')
        if len(pi) == 1 and self.pi_at_start:
            return
        if len(pi):
            self.parse_pi(pi[-1])

    def check_for_pi_at_start(self, tag):
        self.pi_at_start = False
        for c in tag.xpath('./node()'):
            if isinstance(c, str) and re.match('\s*$', c):
                continue
            elif type(c) is etree._ProcessingInstruction:
                self.parse_pi(c)
                self.pi_at_start = True
            return

    # this just makes any gid redirection easier
    def get_text_from_element(self, el):
        text = self.get_single_line_text_from_element(el)
        text = u'\n{0}\n'.format(text)
        return text

    def get_single_line_text_from_element(self, el):
        text = u''.join(el.xpath('.//text()'))
        text = re.sub('\n', ' ', text).strip()
        return text

    def clear_current_speech(self):
        if self.current_speech is not None and len(self.current_speech) > 0:
            self.root.append(self.current_speech)
        self.current_speech_col = self.current_col
        self.current_speech = None

    def new_speech(self, member, url):
        self.clear_current_speech()
        self.current_speech = etree.Element('speech')
        self.current_speech.set('id', self.get_speech_id())
        if member is not None:
            self.current_speech.set('speakername', member['name'])
            if 'type' in member:
                self.current_speech.set('type', member['type'])
            if 'person_id' in member:
                self.current_speech.set('person_id', member['person_id'])
            else:
                self.current_speech.set('nospeaker', 'true')
        else:
            self.current_speech.set('nospeaker', 'true')
        self.current_speech.set('colnum', self.current_col)
        self.current_speech.set('time', self.current_time)
        self.current_speech.set(
            'url',
            self.get_speech_url(url)
        )
        self.current_speech_part = 1

    def parse_system_header(self, header):
        sitting = header.xpath('./ns:Sitting', namespaces=self.ns_map)[0]
        date = mx.DateTime.DateTimeFrom(sitting.get('short-date')).date
        if date:
            self.date = date

    def handle_minus_member(self, member):
        return None

    def _parse_member_or_b(self, tag):
        member_tag = None
        tag_name = self.get_tag_name_no_ns(tag)
        if tag_name == 'B':
            member_tags = tag.xpath('.//ns:Member', namespaces=self.ns_map)
            if len(member_tags) == 1:
                member_tag = member_tags[0]
        elif tag_name == 'Member':
            member_tag = tag
        return member_tag

    def parse_member(self, tag):
        member_tag = self._parse_member_or_b(tag)
        if member_tag is not None:
            mnis_id = member_tag.get('MnisId')
            pims_id = None
            if mnis_id in (None, '-1'):
                pims_id = member_tag.get('PimsId')
                if pims_id in (None, "0", "-1"):
                    return self.handle_minus_member(member_tag)

            if pims_id: # Old way
                member = self.resolver.match_by_pims(pims_id, self.date)
            else:
                member = self.resolver.match_by_mnis(mnis_id, self.date)
            if member is not None:
                member['person_id'] = member.get('id')
                member['name'] = self.resolver.name_on_date(member['person_id'], self.date)
                if member_tag.get('ContributionType'):
                    member['type'] = member_tag.get('ContributionType')
                return member
            else:
                raise ContextException(
                    'No match for MnisId {0}\n'.format(mnis_id),
                    stamp=tag.get('url'),
                    fragment=member_tag.text
                )

        return None

    def parse_date(self, date):
        text = self.get_single_line_text_from_element(date)
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
        # this covers the "The Attorney General was Asked - " type
        # bits at the start of Oral questions which are in an
        # hs_6fDate tag.
        elif re.match('.*was asked.*', text):
            self.parse_para_with_member(date, None)

    def parse_oral_heading(self, heading):
        self.clear_current_speech()
        self.output_heading = True
        tag = etree.Element('oral-heading')
        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        tag.set(
            'url',
            self.get_major_url(heading.get('url'))
        )
        tag.text = heading.text
        self.root.append(tag)

    def parse_debateheading(self, tag):
        els = tag.xpath('*[not(processing-instruction("notus-xml"))]')
        assert len(els) == 1
        tag = els[0]  # Assume child is the actual heading
        tag_name = self.get_tag_name_no_ns(tag)
        return self.handle_tag(tag_name, tag)

    def parse_major(self, heading, **kwargs):
        text = self.get_text_from_element(heading)
        if text.strip() == 'Prayers':
            return
        self.clear_current_speech()
        tag = etree.Element('major-heading')
        if self.uc_titles:
            tag.text = text.upper()
        else:
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
            self.get_major_url(heading.get('url'))
        )
        self.root.append(tag)
        self.output_heading = True

    def parse_chair(self, heading):
	"""
	If we get an "in the Chair" heading in the main text, we include it as
	a speech. The one right at the start, we store in case we need to
        output a speech (otherwise it'll be ignored).
        """
        if self.output_heading:
            return self.parse_procedure(heading)
        self.initial_chair = self.get_text_from_element(heading)

    def parse_minor(self, heading):

        next_elt = heading.getnext()
        if next_elt is not None and self.get_tag_name_no_ns(next_elt) in self.minor_headings:
            text = u' - '.join([
                self.get_single_line_text_from_element(heading),
                self.get_single_line_text_from_element(next_elt)
            ])
            heading.text = text
            self.skip_tag = self.get_tag_name_no_ns(next_elt)

        self.clear_current_speech()
        tag = etree.Element('minor-heading')
        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        tag.set(
            'url',
            self.get_minor_url(heading.get('url'))
        )
        text = self.get_text_from_element(heading)
        tag.text = text
        self.root.append(tag)
        self.output_heading = True

    def parse_generic(self, heading):
        if self.next_speech_num == 0:
            self.parse_major(heading)
        else:
            self.parse_minor(heading)

    def parse_opposition(self, heading):
        """
        The opposition day tag is usually followed by another tag which will
        contain the text that says what the day is about so we use xpath to
        look ahead for that, grab the text and then add it to the text for the
        opposition day so we only have one heading.

        The XML will look something like this:

        <hs_3cOppositionDay>Backbench Business</hs_3cOppositionDay>
        <hs_2DebatedMotion>Contaminated Blood</hs_2DebatedMotion>

        from which we want to get a major heading like:

        <major-heading>Backbench Business - Contaminated Blood</major-heading>

        so join the two headings and then set the skip_tag to hs_2DebatedMotion
        which means the parser skips that tag and doesn't spit out a redundant
        minor heading
        """
        following = heading.xpath(
            '(./following-sibling::ns:hs_2cDebatedMotion|./following-sibling::ns:hs_7SmCapsHdg|./following-sibling::ns:hs_2GenericHdg)',
            namespaces=self.ns_map
        )
        text = ''
        if len(following) == 1:
            text = u' - '.join([
                self.get_single_line_text_from_element(heading),
                self.get_single_line_text_from_element(following[0])
            ])
            heading.text = text
            self.skip_tag = self.get_tag_name_no_ns(following[0])

        self.parse_major(heading)

    def parse_debated_motion(self, motion):
        """
        Similarly to above we want to include the text of the following
        hs_6bFormalmotion tag in the major heading that we are generating
        when we see the hs_2DebatedMotion tag
        """
        following = motion.xpath(
            './following-sibling::ns:hs_6bFormalmotion',
            namespaces=self.ns_map
        )
        text = ''
        if len(following) == 1:
            text = u' - '.join([
                self.get_single_line_text_from_element(motion),
                self.get_single_line_text_from_element(following[0])
            ])
            motion.text = text
            self.skip_tag = self.get_tag_name_no_ns(following[0])

        self.parse_major(motion)

    def parse_WHDebate(self, debate):
        text = self.get_single_line_text_from_element(debate)

        """
        The details of the chair of a Westminster Hall debate are contained
        in a hs_76fChair tag which we want to include in the minor heading
        that we generate to indicate the start of the debate. There doesn't
        seem to be any consistency in whether this tag is before or after
        the debate starting tag so we need to check before and after.

        We don't spit out the contents of the hs_76fChair tag as it's in the
        list of ignored tags as we only want to use it as part of this
        minor heading
        """
        chair = debate.xpath(
            '(./preceding-sibling::ns:hs_76fChair | ./following-sibling::ns:hs_76fChair)',
            namespaces=self.ns_map
        )
        if len(chair) == 1:
            chair_text = self.get_single_line_text_from_element(chair[0])
            text = u'\n{0} — {1}\n'.format(text, chair_text)

        self.clear_current_speech()
        tag = etree.Element('minor-heading')
        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        tag.set(
            'url',
            self.get_major_url(debate.get('url'))
        )
        tag.text = text
        self.root.append(tag)
        self.output_heading = True

    def parse_question(self, question):
        member = question.xpath('.//ns:Member', namespaces=self.ns_map)[0]
        member = self.parse_member(member)

        first_para = question.xpath('.//ns:hs_Para', namespaces=self.ns_map)[0]
        self.new_speech(member, first_para.get('url'))

        number = u''.join(
            question.xpath('.//ns:Number/text()', namespaces=self.ns_map)
        )
        if number != '':
            self.current_speech.set('oral-qnum', number)

        p = etree.Element('p')
        p.set('pid', self.get_pid())
        uin = question.xpath('.//ns:Uin', namespaces=self.ns_map)
        if len(uin) > 0:
            uin_text = u''.join(uin[0].xpath('.//text()'))
            m = re.match('\[\s*(\d+)\s*\]', uin_text)
            if m is not None:
                no = m.groups(1)[0]
                p.set('qnum', no)

        text = first_para.xpath(
            './/ns:QuestionText/text()', namespaces=self.ns_map
        )
        text = u''.join(text)
        """
        sometimes the question text is after the tag rather
        than inside it in which case we want to grab all the
        following-sibling text - can't use .tail as there may
        be things like time code tags in there which truncate
        .tail
        e.g:
        <Question><hs_Para><Number>21</Number>.
        <Uin>[904784]</Uin>
        <Member><B>Henry Bellingham</B> (North West Norfolk) (Con):</Member>
        <QuestionText></QuestionText>
        Is<hs_TimeCode time="2016-05-03T15:05:23"></hs_TimeCode>
        the Secretary of State aware that the Construction Industry (etc)
        </hs_Para></Question>
        """
        if text == '':
            q_text = first_para.xpath(
                './/ns:QuestionText/following-sibling::text()',
                namespaces=self.ns_map
            )
            if len(q_text):
                text = u''.join(q_text)

        p.text = re.sub('\n', ' ', text)
        self.current_speech.append(p)

        # and sometimes there is more question text in following siblings
        # so we need to handle those too
        following_tags = first_para.xpath(
            './following-sibling::*',
            namespaces=self.ns_map
        )
        for t in following_tags:
            tag_name = self.get_tag_name_no_ns(t)
            self.handle_tag(tag_name, t)

    def parse_indent(self, tag):
        self.parse_para_with_member(tag, None, css_class='indent')

    def parse_petition(self, petition):
        petition.text = u'Petition - {0}'.format(petition.text)
        self.parse_major(petition)

    def output_normally_ignored(self):
        self.clear_current_speech()

        tag = etree.Element('major-heading')
        tag.text = 'Prayers'

        if hasattr(self, 'initial_chair'):
            tag.text += ' - '
            i = etree.Element('i')
            i.text = self.initial_chair
            tag.append(i)

        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)
        self.root.append(tag)
        self.output_heading = True

    def parse_para_with_member(self, para, member, **kwargs):
        if not self.output_heading:
            self.output_normally_ignored()

        members = para.xpath('.//ns:Member', namespaces=self.ns_map)
        if member is not None:
            self.new_speech(member, para.get('url'))
        elif members:
            m_name = None
            bs = members[0].xpath('./ns:B', namespaces=self.ns_map)
            if len(bs) == 1:
                m_name = {'name': re.sub('\s+', ' ', bs[0].text).strip()}
            elif len(bs) == 0:
                m_name = {'name': re.sub('\s+', ' ', members[0].text).strip()}
            self.new_speech(m_name, para.get('url'))
        elif self.current_speech is None:
            self.new_speech(None, para.get('url'))

        # this makes the text fetching a bit easier
        if kwargs.get('strip_member', True):
            for m in members:
                italics = m.xpath('.//ns:I', namespaces=self.ns_map)
                text = ''.join(self.get_single_line_text_from_element(i) for i in italics)
                if text:
                    kwargs['css_class'] = 'italic'
                if m.tail:
                    text += ' ' + m.tail
                m.getparent().text = text
                m.getparent().remove(m)

        text = self.get_single_line_text_from_element(para)
        if len(text) == 0:
            return

        fs = u'<p>{0}</p>'.format(PhraseTokenize(self.date, text).GetPara())
        tag = etree.fromstring(fs)

        if self.use_pids:
            tag.set('pid', self.get_pid())
        if 'css_class' in kwargs:
            tag.set('class', kwargs['css_class'])
        if 'pwmotiontext' in kwargs:
            tag.set('pwmotiontext', kwargs['pwmotiontext'])

        self.current_speech.append(tag)

    # TODO: this needs to parse out the various things that filtersentence
    # catches at the moment. Some of those might be in the XML but mostly
    # it will need to be a port of that to create proper XML elements
    # using etree
    def parse_para(self, para):
        member = None
        for tag in para:
            tag_name = self.get_tag_name_no_ns(tag)
            if tag_name == 'B' or tag_name == 'Member':
                m = self.parse_member(tag)
                if m:
                    member = m

        self.parse_para_with_member(para, member)

    def parse_brev(self, brev):
        self.parse_para_with_member(brev, None, css_class="indent", pwmotiontext='yes')

    def parse_votelist(self, votes, direction, vote_list, is_teller=False):
        for vote in votes:
            tag = etree.Element('mpname')
            member = self.parse_member(vote)
            tag.set('person_id', member['person_id'])
            tag.set('vote', direction)
            if is_teller:
                tag.set('teller', 'yes')
            if self.debate_type == 'standing':
                tag.set('membername', member['name'])
            tag.text = member['name']

            proxy = None
            vote_text = self.get_single_line_text_from_element(vote)
            m = re.search('\(Proxy vote cast by (.*)\)', vote_text)
            if m:
                proxy = self.resolver.pbc_match(m.group(1), self.date)
            if proxy:
                tag.set('proxy', proxy['id'])

            vote_list.append(tag)

        return vote_list

    def parse_table(self, wrapper):
        rows = wrapper.xpath('.//ns:row', namespaces=self.ns_map)
        tag = etree.Element('table')
        body = etree.Element('tbody')
        url = None
        for row in rows:
            row_tag = etree.Element('tr')
            row_tag.set('pid', self.get_pid())

            for entry in row.xpath('(.//ns:hs_brev|.//ns:hs_Para)', namespaces=self.ns_map):
                if url is None:
                    url = entry.get('url')
                td_tag = etree.Element('td')
                td_tag.text = self.get_single_line_text_from_element(entry)
                row_tag.append(td_tag)

            if len(row_tag):
                body.append(row_tag)

        tag.append(body)

        if self.current_speech is None:
            self.new_speech(None, url)

        self.current_speech.append(tag)

    def get_division_tag(self, division, yes_text, no_text):
        tag = etree.Element('division')

        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('divdate', self.date)
        div_number = \
            division.xpath('.//ns:Number/text()', namespaces=self.ns_map)

        tag.set('divnumber', u''.join(div_number))
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)

        div_count = etree.Element('divisioncount')
        div_count.set('ayes', yes_text)
        div_count.set('noes', no_text)

        tag.append(div_count)

        return tag

    def parse_division(self, division):
        for tag in division:
            if type(tag) is etree._ProcessingInstruction:
                continue
            tag_name = self.get_tag_name_no_ns(tag)
            if tag_name not in ('hs_Para', 'England', 'EnglandWales', 'hs_DivListHeader', 'TwoColumn'):
                if not self.handle_tag(tag_name, tag):
                    raise ContextException('unhandled tag: {0}'.format(tag_name), fragment=tag, stamp=tag.get('url'))

        ayes_count = \
            division.xpath('./ns:hs_Para/ns:AyesNumber/text()', namespaces=self.ns_map)
        noes_count = \
            division.xpath('./ns:hs_Para/ns:NoesNumber/text()', namespaces=self.ns_map)

        ayes_count_text = u''.join(ayes_count)
        noes_count_text = u''.join(noes_count)

        self.clear_current_speech()

        tag = self.get_division_tag(division, ayes_count_text, noes_count_text)

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

        # England/EnglandWales not used since May 2018
        paras = division.xpath('(./ns:hs_Para|./ns:England/ns:hs_Para|./ns:EnglandWales/ns:hs_Para)', namespaces=self.ns_map)
        for para in paras:
            text = self.get_single_line_text_from_element(para)
            if re.search(r'Division\s*No', text):
                continue
            self.parse_para(para)

    def parse_time(self, tag):
        time_txt = u''.join(tag.xpath('.//text()'))
        if time_txt == '':
            return
        matches = re.match('(\d+)(?:[:.,]\s*(\d+))?[\xa0\s]*(am|pm)', time_txt)
        if matches:
            hours = int(matches.group(1))
            minutes = int(matches.group(2) or 0)
            if matches.group(3) == 'pm' and hours < 12:
                hours += 12
            time = mx.DateTime.DateTimeFrom(hour=hours, minute=minutes)
            self.current_time = time.strftime('%H:%M:%S')
        elif time_txt == 'Noon' or re.match('12\s*?noon', time_txt):
            self.current_time = "12:00:00"
        elif re.match('12\s*?midnight', time_txt):
            self.current_time = "00:00:00"
        elif re.match('Midnight', time_txt):
            self.current_time = "00:00:00"
        else:
            raise ContextException(
                "Unmatched time %s" % time_txt,
                fragment=tag,
                stamp=tag.get('url')
            )

    def parse_procedure(self, procedure):
        tag = etree.Element('p')
        text = self.get_single_line_text_from_element(procedure)
        if len(text) == 0:
            return

        # We ignore prayers
        if re.match('Prayers.*?read by', text):
            return

        if not self.output_heading:
            self.output_normally_ignored()

        tag.set('pid', self.get_pid())
        tag.set('class', 'italic')
        tag.text = text

        if self.current_speech is None:
            self.new_speech(None, procedure.get('url'))

        self.current_speech.append(tag)

    def parse_pi(self, pi):
        # you would think there is a better way to do this but I can't seem
        # to extract attributes from processing instructions :(
        text = str(pi)
        matches = re.search(r'column=(\d+)\?', text)
        if matches is not None:
            col = matches.group(1)
            self.current_col = col
            self.next_speech_num = 0

    def handle_tag(self, tag_name, tag):
        handled = True

        if self.skip_tag is not None and tag_name == self.skip_tag:
            self.skip_tag = None
        elif tag_name == 'hs_6fDate':
            self.parse_date(tag)
        elif tag_name in self.oral_headings:
            self.parse_oral_heading(tag)
        elif tag_name == 'hs_3cOppositionDay':
            self.parse_opposition(tag)
        elif tag_name == 'hs_2DebatedMotion':
            self.parse_debated_motion(tag)
        elif tag_name == 'DebateHeading':
            handled = self.parse_debateheading(tag)
        elif tag_name == 'hs_2DebBill':
            if self.debate_type == 'westminhall':
                self.parse_WHDebate(tag)
            elif self.debate_type == 'debate':
                self.parse_major(tag)
        elif tag_name in self.major_headings:
            self.parse_major(tag)
        elif tag_name in self.chair_headings:
            self.parse_chair(tag)
        elif tag_name in self.minor_headings:
            self.parse_minor(tag)
        elif tag_name in self.generic_headings:
            self.parse_generic(tag)
        elif tag_name in self.whall_headings:
            self.parse_WHDebate(tag)
        elif tag_name == 'Question':
            self.parse_question(tag)
        elif tag_name == 'hs_8Petition':
            self.parse_petition(tag)
        elif tag_name in self.indents:
            self.parse_indent(tag)
        elif tag_name in self.paras:
            self.parse_para(tag)
        elif tag_name == 'hs_brev' or tag_name == 'hs_brevIndent':
            self.parse_brev(tag)
        elif tag_name == 'TableWrapper':
            self.parse_table(tag)
        elif tag_name == 'Division':
            self.parse_division(tag)
        elif tag_name == 'hs_Timeline':
            self.parse_time(tag)
        elif tag_name in self.ignored_tags:
            pass
        elif tag_name in self.empty_tags:
            if len(tag) != 0 or tag.text:
                handled = False
        else:
            handled = False

        return handled

    def parse_day(self, xml_file):
        ok = self.setup_parser(xml_file)
        if not ok:
            return False
        self.root.set('scraperversion', self.rev)
        self.root.set('latest', 'yes')
        self.current_col = self.input_root[0].get('ColStart')

        headers = self.input_root[0].xpath(
            './/ns:Fragment/ns:Header', namespaces=self.ns_map
        )
        self.parse_system_header(headers[0])

        body_tags = self.input_root[0].xpath(
            './/ns:Fragment/ns:Body', namespaces=self.ns_map
        )
        for b in body_tags:
            for tag in b:

                # column numbers are contained in processing
                # instructions so first check if the tag is
                # one of those because then we don't need to
                # process any further
                if type(tag) is etree._ProcessingInstruction:
                    self.parse_pi(tag)
                    continue

                # PI handling - if it's right at the start, do
                # the column change now rather than after
                self.check_for_pi_at_start(tag)

                tag_name = self.get_tag_name_no_ns(tag)
                if self.verbose >= 2:
                    start_tag = re.sub('>.*', '>', etree.tounicode(tag))
                    print 'Parsing %s' % start_tag
                if not self.handle_tag(tag_name, tag):
                    raise ContextException(
                        'unhandled tag: {0}'.format(tag_name),
                        fragment=etree.tostring(tag),
                        stamp=tag.get('url')
                    )

                # PI handling - check inside all tags for processing
                # instructions to make sure we catch all column changes
                self.check_for_pi(tag)

        # make sure we add any outstanding speech.
        self.clear_current_speech()

        return True

    def get_date(self, xml_file):
        ok = self.setup_parser(xml_file)
        if not ok:
            return False

        headers = self.input_root[0].xpath(
            './/ns:Fragment/ns:Header', namespaces=self.ns_map
        )
        self.parse_system_header(headers[0])
        return self.date

    def setup_parser(self, xml_file):
        if self.input_root is not None:
            return True

        self.root = etree.Element('publicwhip')
        self.ns = self.type_to_xpath[self.debate_type][1]
        self.ns_map = {'ns': self.ns}
        root_xpath = self.type_to_xpath[self.debate_type][0]

        self.xml_root = etree.parse(xml_file).getroot()
        self.input_root = self.xml_root.xpath(
            root_xpath, namespaces=self.ns_map
        )
        if len(self.input_root) == 0:
            if self.verbose >= 1:
                sys.stderr.write(
                    'Failed to find any debates of type {0} in {1}\n'
                    .format(self.debate_type, xml_file.name)
                )
            return False
        return True


class CommonsParseDayXML(BaseParseDayXML):
    uc_titles = False


class PBCParseDayXML(BaseParseDayXML):
    current_chair = None

    use_pids = False

    ignored_tags = [
        'hs_CLHeading',
        'hs_CLAttended',
        'hs_6fCntrItalHdg',
        'hs_TimeCode',
    ]

    def reset(self):
        self.chairs = []
        self.members = []
        self.clerks = []
        self.witnesses = []
        super(PBCParseDayXML, self).reset()

    def get_speech_id_first_part(self):
        return self.sitting_id

    def get_member_with_no_id(self, member_tag):
        name = member_tag.text
        if not name:
            bs = member_tag.xpath('./ns:B', namespaces=self.ns_map)
            if bs:
                name = bs[0].text

        name = name.rstrip(':')
        member = self.resolver.pbc_match(name, self.date)
        return member

    # check for a cross symbol before the name of a member which tells
    # us that they are attending the committee
    #
    # the text[-1] is because we fetch all the preceding text nodes and
    # we want the immediately preceding one which will be the last one
    # in the array
    def get_attending_status(self, member_tag):
        text = member_tag.xpath('./preceding-sibling::text()')
        if len(text) > 0 and re.search(u'\u2020', text[-1]):
            return 'true'

        return 'false'

    def parse_chairmen(self, chair):
        member_tags = chair.xpath('.//ns:Member', namespaces=self.ns_map)
        for member_tag in member_tags:
            member = self.parse_member(member_tag)
            if member is None:
                member = self.get_member_with_no_id(member_tag)

            if member is not None:
                member['attending'] = self.get_attending_status(member_tag)
                self.chairs.append(member)
            else:
                raise ContextException(
                    u'No match for PBC chairman {0}'.format(member_tag.text),
                    stamp=member_tag.get('url'),
                    fragment=member_tag.text
                )

    def parse_clmember(self, clmember):
        member_tag = clmember.xpath('.//ns:Member', namespaces=self.ns_map)[0]
        member = self.parse_member(member_tag)
        if member is None:
            member = self.get_member_with_no_id(member_tag)

        cons_tags = member_tag.xpath('.//ns:I', namespaces=self.ns_map)
        cons = ''
        if len(cons_tags) == 1:
            cons_tag = cons_tags[0]
            cons = cons_tag.text
            cons = re.sub(r'[()]', '', cons)

        if member is not None:
            member['attending'] = self.get_attending_status(member_tag)
            member['pbc_cons'] = cons
            self.members.append(member)
        else:
            raise ContextException(
                u'No match for PBC member {0}'.format(member_tag.text),
                stamp=member_tag.get('url'),
                fragment=member_tag.text
            )

    def parse_clerks(self, clerks):
        text = clerks.text
        self.clerks = text.split(',')

    def parse_witness(self, witness):
        self.witnesses.append(witness.text)

    def committee_finished(self):
        committee = etree.Element('committee')

        chairmen = etree.Element('chairmen')
        for c in self.chairs:
            mp = etree.Element('mpname')
            mp.set('person_id', c['person_id'])
            mp.set('membername', c['name'])
            mp.set('attending', c['attending'])
            mp.text = c['name']
            chairmen.append(mp)

        committee.append(chairmen)

        def current_membership(pid):
            members = self.resolver.persontomembermap[pid]
            members = [self.resolver.members[mid] for mid in members]
            members = [m for m in members if m['start_date'] <= self.date <= m['end_date']]
            assert len(members) == 1
            return members[0]

        for m in self.members:
            mp = etree.Element('mpname')
            mp.set('person_id', m['person_id'])
            mp.set('membername', m['name'])
            mp.set('attending', m['attending'])
            mp.text = m['name']
            cons = etree.Element('i')

            # if it's a different cons then it's probably a position
            # so use that instead and skip the party
            curr_member = current_membership(m['person_id'])
            if curr_member['constituency'] != m['pbc_cons']:
                cons.text = u'({0})'.format(m['pbc_cons'])
            else:
                cons.text = u'({0})'.format(curr_member['constituency'])
                cons.tail = u'({0})'.format(curr_member['party'])
            mp.append(cons)
            committee.append(mp)

        for c in self.clerks:
            clerk = etree.Element('clerk')
            clerk.text = c
            committee.append(clerk)

        self.root.append(committee)

        witnesses = etree.Element('witnesses')
        for w in self.witnesses:
            witness = etree.Element('witness')
            witness.text = w
            witnesses.append(witness)

        self.root.append(witnesses)

    def parse_bill_title(self, title_tag):
        title = self.get_single_line_text_from_element(title_tag)

        bill = etree.Element('bill')
        bill.set('title', title)
        bill.set('session', self.session)
        bill.text = title

        self.root.insert(0, bill)

    def handle_minus_member(self, member):
        if member.get('InTheChair') == 'True':
            return self.current_chair

        return self.get_member_with_no_id(member)

    def parse_chair(self, chair):
        self.new_speech(None, chair.get('url'))
        text = self.get_text_from_element(chair)
        tag = etree.Element('p')
        tag.text = text
        self.current_speech.append(tag)

        chair_match = re.match(
            r'\s*\[\s*(.*)\s+in\s+the\s+chair\s*\](?i)',
            text
        )
        if chair_match is not None:
            name = chair_match.groups(1)[0]
            chair = self.resolver.pbc_match(name, self.date)
            if chair is not None:
                self.current_chair = chair
        else:
            raise ContextException(u'No match for chair {0}'.format(text))

    def get_division_tag(self, division, yes_text, no_text):
        tag = etree.Element('divisioncount')

        div_number = \
            division.xpath('.//ns:Number/text()', namespaces=self.ns_map)

        tag.set('id', self.get_speech_id())
        tag.set('divnumber', u''.join(div_number))
        tag.set('ayes', yes_text)
        tag.set('noes', no_text)
        tag.set('url', '')

        return tag


    def parse_amendment(self, amendment, level):
        tag = etree.Element('p')
        tag.set('amendmenttext', 'true')
        tag.set('amendmentlevel', str(level))
        tag.text = amendment.text

        if self.current_speech is None:
            self.new_speech(None, amendment.get('url'))
        self.current_speech.append(tag)

    def parse_table(self, table):
        paras = table.xpath('(.//ns:hs_Para|.//ns:hs_brev)', namespaces=self.ns_map)
        for para in paras:
            tag_name = self.get_tag_name_no_ns(para)
            if tag_name == 'hs_Para':
                self.parse_para_with_member(para, None)
            else:
                self.parse_para_with_member(para, None, css_class="indent")

    def parse_brev(self, brev):
        self.parse_para_with_member(brev, None, css_class="indent")

    def parse_para(self, para):
        has_i = False
        has_witness = False
        for tag in para.iter():
            tag_name = self.get_tag_name_no_ns(tag)
            if tag_name == 'Witness':
                has_witness = True
                name = self.get_single_line_text_from_element(tag).rstrip(':')
                self.new_speech({'name': name}, para.get('url'))
            # Infer from italic text that it's a motiony thing and we should
            # start a new para which is a bit fragile
            elif tag_name == 'I':
                has_i = True

        if has_i and not has_witness:
            self.new_speech(None, para.get('url'))

        if has_witness:
            for w in para.xpath('.//ns:Witness', namespaces=self.ns_map):
                w.getparent().text = w.tail
                w.getparent().remove(w)
            self.parse_para_with_member(para, None)
        else:
            super(PBCParseDayXML, self).parse_para(para)

    def handle_tag(self, tag_name, tag):
        handled = True

        if tag_name == 'hs_CLMember':
            self.parse_clmember(tag)
        elif tag_name == 'hs_CLClerks':
            self.parse_clerks(tag)
        elif tag_name == 'hs_CLChairman':
            self.parse_chairmen(tag)
        elif tag_name == 'hs_8GenericHdg':
            self.parse_minor(tag)
        elif tag_name == 'hs_AmendmentLevel1':
            self.parse_amendment(tag, 1)
        elif tag_name == 'hs_AmendmentLevel2':
            self.parse_amendment(tag, 2)
        elif tag_name == 'TableWrapper':
            self.parse_table(tag)
        elif tag_name == 'hs_CLPara':
            self.parse_witness(tag)
        elif tag_name == 'hs_brevIndent':
            self.parse_brev(tag)
        elif tag_name in ('hs_2BillTitle', 'hs_2DebBill'):
            self.parse_bill_title(tag)
        elif tag_name == 'hs_3MainHdg':
            self.committee_finished()
            self.parse_major(tag)
        elif tag_name == 'hs_ParaIndent':
            self.parse_para_with_member(tag, None, css_class="indent")
        else:
            handled = super(PBCParseDayXML, self).handle_tag(tag_name, tag)

        return handled

    def get_sitting(self, xml_file):
        ok = self.setup_parser(xml_file)
        if not ok:
            return False

        # This isn't nice.
        fragment = self.input_root[0].xpath('.//ns:Fragment', namespaces=self.ns_map)[0]
        self.session, debate_num = re.search('Commons/(\d{4}_\d{4})/Committee_\d+/Debate_(\d+)/Sitting_\d+', fragment.get('__uri__')).groups()
        header = fragment.xpath('./ns:Header', namespaces=self.ns_map)[0]
        try:
            # The sitting number is only given in a random attribute
            data_id = header.xpath('./ns:SystemDataId', namespaces=self.ns_map)[0]
            data_id = self.get_single_line_text_from_element(data_id)
            sitting_num = int(re.match('P(?:BC|MB)\s*\d+-(\d+)', data_id).group(1))
        except:
            # Try and find one in the filename then.
            sitting_num = int(re.search('(\d+)(?:st|nd|rd|th) sit', xml_file.name).group(1))

        try:
            title = header.xpath('./ns:Title', namespaces=self.ns_map)[0]
            title = self.get_single_line_text_from_element(title).partition(' ')[0].upper()
        except:
            fragment = self.xml_root.xpath('.//ns:Fragment', namespaces=self.ns_map)[0]
            title = fragment.xpath('.//ns:Cover', namespaces=self.ns_map)[0].get('debate')
            title = title.partition(' ')[0].upper()

        self.session = re.sub('(\d{4})_\d\d(\d\d)', r'\1-\2', self.session)

        # The 0 here is a part number. I do not know what the XML outputs for multiple parts
        from standing.utils import construct_shortname
        self.sitting_id = construct_shortname(debate_num, title, sitting_num, 0, self.date)


class LordsParseDayXML(BaseParseDayXML):
    resolver = LordsList()

    paras = [
        'hs_para',
        'hs_parafo',
        'hs_Question',
        'hs_newline10',
        'hs_newline12',
    ]

    ignored_tags = [
        'hs_date',
        'hs_Venue',
    ]

    def parse_quote(self, quote):
        tag = etree.Element('p')
        tag.set('pid', self.get_pid())
        tag.set('class', 'indent')

        tag.text = re.sub('\n', ' ', quote.text)

        i = quote.xpath('./ns:I', namespaces=self.ns_map)
        if len(i) == 1:
            i_text = self.get_single_line_text_from_element(i[0])
            new_i = etree.Element('i')
            new_i.text = i_text
            new_i.tail = re.sub('\n', ' ', i[0].tail or '')
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
        # special hand edited XML case :/
        name = member.get('ContinuationText')
        if name == 'The Queen':
            return {
                'person_id': 'uk.org.publicwhip/person/13935',
                'name': u'The Queen'
            }

        tag_name = self.get_tag_name_no_ns(member)
        if tag_name == 'B' and self.get_single_line_text_from_element(member) == '':
            return None

        found_member = super(LordsParseDayXML, self).parse_member(member)
        if found_member is None:
            # In cases where there are unattributes exclamations then MnisId
            # is missing. Often the name will be "Noble Lords" or the like
            member_tag = self._parse_member_or_b(member)
            if member_tag is None:
                raise ContextException(
                    'Could not find member',
                     stamp=member.get('url'),
                     fragment=etree.tostring(member),
                )
            if member_tag.get('MnisId') == '-1':
                found_member = {
                    'person_id': 'unknown',
                    'name': self.get_single_line_text_from_element(member).rstrip(':')
                }

        return found_member

    def parse_newdebate(self, tag):
        time = tag.xpath('.//ns:hs_time', namespaces=self.ns_map)
        if len(time):
            self.parse_time(time[0])

        heading = tag.xpath('.//ns:hs_DebateHeading|.//hs_AmendmentHeading', namespaces=self.ns_map)
        debate_type = tag.xpath('.//ns:hs_DebateType', namespaces=self.ns_map)
        if len(heading):
            if len(debate_type):
                text = self.get_single_line_text_from_element(debate_type[0])
                self.parse_major(heading[0], extra_text=text)
            else:
                self.parse_major(heading[0])
        else:
            raise ContextException(
                'New Lords debate with no heading',
                 stamp=tag.get('url'),
                 fragment=tag
             )
            return

        #procedure = tag.xpath('.//ns:hs_Procedure', namespaces=self.ns_map)
        #if len(procedure) == 1:
        #    self.handle_para(procedure[0])

        want_member = tag.get('BusinessType') in ('Question', 'GeneralDebate')

        member = None
        member_tags = tag.xpath('.//ns:Member', namespaces=self.ns_map)
        if len(member_tags):
            if want_member:
                member = self.parse_member(member_tags[0])
            else:
                tabledby_tags = tag.xpath('.//ns:hs_TabledBy', namespaces=self.ns_map)
                self.parse_para_with_member(tabledby_tags[0], None, css_class='italic', strip_member=False)

        questions = tag.xpath('.//ns:hs_Question', namespaces=self.ns_map)
        for question in questions:
            self.parse_para_with_member(question, member if want_member else None)

    def parse_amendment_heading(self, heading):
        self.parse_minor(heading)

    def parse_tabledby(self, tabledby):
        self.parse_para_with_member(
            tabledby,
            None,
            strip_member=False,
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
        text = self.get_single_line_text_from_element(heading)
        i = etree.Element('i')
        i.text = text
        b = etree.Element('b')
        b.append(i)

        tag.set('pid', self.get_pid())
        tag.append(b)
        if self.current_speech is None:
            self.new_speech(None, heading.get('url'))
        self.current_speech.append(tag)

    def parse_division(self, division):
        ayes_count = \
            division.xpath('.//ns:ContentsNumber/text()', namespaces=self.ns_map)
        noes_count = \
            division.xpath('.//ns:NotContentsNumber/text()', namespaces=self.ns_map)

        ayes_count_text = u''.join(ayes_count)
        noes_count_text = u''.join(noes_count)

        # output a summary of the division results
        div_summary = \
            u"Ayes {0}, Noes {1}.".format(ayes_count_text, noes_count_text)
        div_summary_tag = etree.Element('p')
        div_summary_tag.set('pid', self.get_pid())
        div_summary_tag.set('pwmotiontext', 'yes')
        div_summary_tag.text = div_summary
        self.current_speech.append(div_summary_tag)

        self.clear_current_speech()

        tag = etree.Element('division')

        tag.set('id', self.get_speech_id())
        tag.set('nospeaker', 'true')
        tag.set('divdate', self.date)

        div_number = \
            division.xpath('.//ns:DivisionNumber/text()', namespaces=self.ns_map)

        tag.set('divnumber', u''.join(div_number))
        tag.set('colnum', self.current_col)
        tag.set('time', self.current_time)

        div_count = etree.Element('divisioncount')
        div_count.set('content', ayes_count_text)
        div_count.set('not-content', noes_count_text)

        tag.append(div_count)

        ayes = division.xpath(
            './/ns:NamesContents//ns:hs_DivListNames', namespaces=self.ns_map
        )
        noes = division.xpath(
            './/ns:NamesNotContents//ns:hs_DivListNames', namespaces=self.ns_map
        )

        aye_list = etree.Element('lordlist')
        aye_list.set('vote', 'content')
        aye_list = self.parse_votelist(ayes, 'content', aye_list)
        tag.append(aye_list)

        no_list = etree.Element('lordlist')
        no_list.set('vote', 'not-content')
        no_list = self.parse_votelist(noes, 'not-content', no_list)
        tag.append(no_list)

        self.root.append(tag)

        paras = division.xpath('./ns:hs_Procedure', namespaces=self.ns_map)
        for para in paras:
            text = u''.join(para.xpath('.//text()'))
            if re.search(r'Contents', text) or \
                    re.search(r'Division\s*on', text):
                continue
            self.parse_para(para)

    def parse_votelist(self, votes, direction, vote_list):
        for vote in votes:
            tag = etree.Element('lord')
            member_name = self.get_single_line_text_from_element(vote)
            is_teller = False
            if re.match('.*\[Teller\].*', member_name):
                member_name = re.sub('\[Teller\]', '', member_name)
                member_name = member_name.strip()
                is_teller = True

            # convert smart quote to apostrophe
            member_name = re.sub(u'\u2019', "'", member_name)

            member = self.resolver.MatchRevName(member_name, self.date, vote.get('url'))
            tag.set('person_id', member)
            tag.set('vote', direction)
            if is_teller:
                tag.set('teller', 'yes')
            tag.text = self.resolver.name_on_date(member, self.date)
            vote_list.append(tag)

        return vote_list

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
        elif tag_name == 'Division':
            self.parse_division(tag)
        else:
            handled = super(LordsParseDayXML, self).handle_tag(tag_name, tag)

        return handled


class ParseDay(object):
    valid_types = [
        'debate',
        'westminhall',
        'lords',
        'standing'
    ]

    output_dirs = {
        'debate': 'debates',
        'westminhall': 'westminhall',
        'lords': 'lordspages',
        'standing': 'standing'
    }

    output_files = {
        'debate': 'debates',
        'westminhall': 'westminster',
        'lords': 'daylord',
        'standing': 'standing'
    }

    parser = None

    def reset(self):
        self.prev_file = None
        self.output_file = None
        self.parser = None

    def get_output_pbc_filename(self, date, xml_file):
        shortnamemap = { }
        pwstandingpages = os.path.join(pwxmldirs, "standing")
        for f in os.listdir(pwstandingpages):
            m = re.match("(standing.*?)([a-z]*)\.xml$", f)
            if m:
                shortnamemap.setdefault(m.group(1), []).append(
                    (miscfuncs.AlphaStringToOrder(m.group(2)), m.group(2), f))
            elif f.endswith('~') or f == 'changedates.txt':
                pass
            elif os.path.isfile(os.path.join(pwstandingpages, f)):
                print "not recognized file:", f, " in ", pwstandingpages

        self.parser.get_sitting(xml_file)
        sitting_id = self.parser.sitting_id

        dgflatestalpha, dgflatest = "", None
        if sitting_id in shortnamemap:
            ldgf = max(shortnamemap[sitting_id])
            dgflatestalpha = ldgf[1]
            dgflatest = os.path.join(pwstandingpages, ldgf[2])
        self.rev = miscfuncs.NextAlphaString(dgflatestalpha)
        dgfnext = os.path.join(pwstandingpages, '%s%s.xml' % (sitting_id, self.rev))
        assert not dgflatest or os.path.isfile(dgflatest)
        assert not os.path.isfile(dgfnext), dgfnext

        return dgflatest, dgfnext

    def get_output_filename(self, date, debate_type):
        daymap, scrapedDataOutputPath = MakeDayMap(
            self.output_dirs.get(debate_type),
            self.output_files.get(debate_type),
            pwxmldirs,
            'xml'
        )

        latestFilePath, latestFileStem, nextFilePath, nextFileStem = \
            GetFileDayVersions(
                date,
                daymap,
                scrapedDataOutputPath,
                self.output_files.get(debate_type),
                'xml'
            )

        version_match = re.match('\d+-\d+-\d+([a-z])', nextFileStem)
        self.rev = version_match.groups(1)[0]

        return latestFilePath, nextFilePath

    """
    This fakes exactly enough of the old flatb structure from the filter
    version of the code for use in the diff/redirect creation code.
    """
    def gen_flatb(self, chks):
        flatb = []
        for chk in chks:
            details = chk[1]
            gidmatch = re.match('id="([^"]*)"', details)
            if gidmatch:
                gid = gidmatch.group(1)
                # http://stackoverflow.com/questions/652276/is-it-possible-to-create-anonymous-objects-in-python#652417
                entry = type('', (object,), {"GID": gid})()
                flatb.append(entry)

        return flatb

    def normalise_gids(self, string):
        string = re.sub(u'(publicwhip\/[a-z]*\/\d{4}-\d{2}-\d{2})[a-z]', r'\1', string)
        string = re.sub(u'(publicwhip\/standing\/.*?\d{4}-\d{2}-\d{2})[a-z]', r'\1', string)
        string = re.sub(u'(pid=")[a-z]([\d.\/]*")', r'\1\2', string)

        return string

    def compare_xml_files(self, prevfile, nextfile):
        hprevfile = io.open(prevfile, encoding='utf-8')
        dprevfile = hprevfile.readlines()
        hprevfile.close()

        hnextfile = io.open(nextfile, encoding='utf-8')
        dnextfile = hnextfile.readlines()
        hnextfile.close()

        if len(dprevfile) == len(dnextfile):
            sprevfile = self.normalise_gids(u''.join(dprevfile[1:]))
            snextfile = self.normalise_gids(u''.join(dnextfile[1:]))
            if sprevfile == snextfile:
                return "SAME"
        if len(dprevfile) < len(dnextfile):
            sprevfile = self.normalise_gids(u''.join(dprevfile[1:]))
            snextfile = self.normalise_gids(u''.join(dnextfile[1:len(dprevfile)]))
            if sprevfile == snextfile:
                return "EXTENSION"
        return "DIFFERENT"

    def remove_para_newlines(self, string):
        return re.sub(
            '(?s)(<p[^>]*>)(.*?)(<\/p>)',
            lambda m: (u''.join((m.group(1), re.sub('\n', ' ', m.group(2)), m.group(3)))),
            string
        )

    def rewrite_previous_version(self, newfile):
        # open the old and new XML files
        xin = io.open(self.prev_file, encoding='utf-8')
        xprevs = xin.read()
        xin.close()

        xin = io.open(newfile, encoding='utf-8')
        xcur = xin.read()
        xin.close()

        xprevs = self.remove_para_newlines(xprevs)
        xcur = self.remove_para_newlines(xcur)

        # pull out the scrape versions and the XML as a string
        mpw = re.search('<publicwhip([^>]*)>([\s\S]*?)</publicwhip>', xprevs)
        mpc = re.search('<publicwhip([^>]*)>([\s\S]*?)</publicwhip>', xcur)

        if mpc is None or mpw is None:
            sys.stderr.write('Failed to do diff for {0}\n'.format(self.prev_file))
            return

        # take the XML string and turn it into the data structures used
        # by the diffing code, then do the diffing
        essflatbindx, essflatblist, oldchks = PrepareXMLForDiff(mpc.group(2))
        essxindx, essxlist, chks = PrepareXMLForDiff(mpw.group(2))
        flatb = self.gen_flatb(oldchks)
        xprevcompress = DoFactorDiff(essflatbindx, essflatblist, essxindx, essxlist, chks, flatb)

        # spit out the rewritten previous version with redirects
        tempfilenameoldxml = tempfile.mktemp(".xml", "pw-filtertempold-", miscfuncs.tmppath)
        foout = io.open(tempfilenameoldxml, mode="w", encoding='utf-8')
        if self.parser.is_pre_new_parser:
            WriteXMLHeader(foout, encoding="UTF-8", output_unicode=True)
        foout.write(u'<publicwhip scrapeversion="%s" latest="no">\n' % self.prev_file)
        foout.writelines([unicode(x) for x in xprevcompress])
        foout.write(u"</publicwhip>\n\n")
        foout.close()
        assert os.path.isfile(self.prev_file)
        os.remove(self.prev_file)
        os.rename(newfile, self.output_file)
        os.rename(tempfilenameoldxml, self.prev_file)

    def output(self, stream):
        stream.write(etree.tounicode(self.parser.root, pretty_print=True))

    def handle_file(self, filename, debate_type, verbose):
        if debate_type not in self.valid_types:
            sys.stderr.write('{0} not a valid type'.format(debate_type))
            sys.exit()

        xml_file = io.open(filename, encoding='utf-8')
        self.set_parser_for_type(debate_type)
        self.parser.verbose = verbose
        date = self.parser.get_date(xml_file)
        if date is False:
            return 'not-present'

        if debate_type == 'standing':
            prev_file, output_file = self.get_output_pbc_filename(date, xml_file)
        else:
            prev_file, output_file = self.get_output_filename(date, debate_type)
        self.parser.rev = self.rev

        self.prev_file = prev_file
        self.output_file = output_file

        tempfilename = tempfile.mktemp(".xml", "pw-filtertemp-", miscfuncs.tmppath)

        parse_ok = self.parse_day(xml_file, debate_type)

        if parse_ok:
            out = io.open(tempfilename, mode='w', encoding='utf-8')
            self.output(out)
            out.close()
        else:
            sys.stderr.write('Failed to parse {0}\n'.format(filename))
            os.remove(tempfilename)
            return 'failed'

        # FIME: should be using more temp files here
        # if we have a previous version check if it's different from
        # the new one
        if self.prev_file is not None:
            diffs = self.compare_xml_files(self.prev_file, tempfilename)
            # if they are the same then delete the old one
            if diffs == 'SAME':
                os.remove(tempfilename)
                return 'same'
            # otherwise do the diff and redirect dance
            else:
                self.rewrite_previous_version(tempfilename)
                return 'change'
        else:
            os.rename(tempfilename, self.output_file)
            return 'new'

    def set_parser_for_type(self, debate_type):
        if self.parser is not None:
            return

        parser_types = {
            'lords': LordsParseDayXML,
            'standing': PBCParseDayXML,
        }
        self.parser = parser_types.get(debate_type, CommonsParseDayXML)()
        self.parser.debate_type = debate_type

    def parse_day(self, text, debate_type):
        self.set_parser_for_type(debate_type)
        if debate_type == 'standing':
            if not hasattr(self.parser, 'sitting_id'):
                self.parser.get_sitting(text)
        parse_ok = self.parser.parse_day(text)
        if parse_ok:
            return True

        return False

if __name__ == '__main__':
    xml_file = codecs.open(sys.argv[1], encoding='utf-8')
    house = sys.argv[2]
    parse = ParseDay()
    parse_ok = parse.parse_day(xml_file, house)
    if parse_ok:
        parse.output(sys.stdout)
