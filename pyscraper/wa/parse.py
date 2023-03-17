#! /usr/bin/env python3

import copy
from dataclasses import dataclass, field
import datetime
from enum import Enum
from html import unescape
import os
from pathlib import Path
import re
import sys
from bs4 import BeautifulSoup, NavigableString

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from contextexception import ContextException
from wa.resolvenames import memberList

parldata = '../../../parldata/'

@dataclass
class Thing:
    major: int
    minor: int
    date: datetime.date
    time: datetime.datetime = None
    lang: str = ''
    en: str = ''
    cy: str = ''
    url: str = ''
    suffix: str = ''

    is_text = True
    info = False

    def id(self, lang):
        id = f'uk.org.publicwhip/senedd/{lang}/{self.date}.{self.major}.{self.minor}'
        if self.suffix:
            id += f'.{self.suffix}'
        return id

    def extra_attribs(self, tag, lang):
        pass

    def in_lang(self, lang):
        return self.__str__(lang)

    def __str__(self, lang='en'):
        soup = BeautifulSoup("<body>", 'lxml')
        tag = soup.new_tag(self.element_name)
        tag['id'] = self.id(lang)
        if self.time:
            tag['time'] = self.time.strftime("%H:%M")
        if self.url:
            tag['url'] = self.url
        self.extra_attribs(tag, lang)
        text = getattr(self, lang)
        if self.lang and lang != self.lang:
            tag['original_lang'] = self.lang
        if isinstance(text, (str, NavigableString)):
            if not text:
                other_lang = 'en' if lang == 'cy' else 'cy'
                tag['lang'] = other_lang
                text = getattr(self, other_lang)
        else:
            if not list(text):
                other_lang = 'en' if lang == 'cy' else 'cy'
                tag['lang'] = other_lang
                text = getattr(self, other_lang)

        if isinstance(text, (str, NavigableString)):
            tag.string = text
        else:
            text = list(copy.copy(text))
            for b in text:
                if self.info and b.name == 'p':
                    b['class'] = 'italic'
                tag.append(b)

        return str(tag)

class MajorHeading(Thing):
    element_name = 'major-heading'

class MinorHeading(Thing):
    element_name = 'minor-heading'

class Info(Thing):
    element_name = 'speech'
    is_text = False
    info = True

@dataclass
class Speech(Thing):
    speaker_id: int = 0
    speaker_name: str = ""

    element_name = 'speech'
    is_text = False

    def extra_attribs(self, tag, lang):
        if self.speaker_id:
            tag['person_id'] = self.speaker_id
        if self.speaker_name:
            tag['speakername'] = self.speaker_name
        'https://record.assembly.wales/Plenary/13263'

@dataclass
class Vote(Thing):
    vote: str = ''
    divnumber: int = 0
    title_en: str = ''
    title_cy: str = ''

    element_name = 'division'
    is_text = False

    def extra_attribs(self, tag, lang):
        tag['divdate'] = self.date
        tag['divnumber'] = self.divnumber
        if lang == 'cy':
            tag['title'] = self.title_cy
        else:
            tag['title'] = self.title_en

class ParseDay:
    def parse_day(self, date, text, votes, qnr):
        self.date = date
        if votes: self.parse_votes(votes)
        self.parse_plenary(text)
        if qnr: self.parse_qnr(qnr)
        en = self.output('en')
        cy = self.output('cy')
        return en, cy

    def output(self, lang):
        out = '<?xml version="1.0" encoding="utf-8"?>\n<publicwhip>\n'
        for speech in self.speeches:
            out += speech.in_lang(lang) + "\n"
        out += '</publicwhip>\n'
        return out

    def add_speech(self, item, Typ, **kwargs):
        agenda_id = item.Agenda_Item_ID.string.split('-')[1]
        order_id = kwargs.pop('order_id', None)
        if order_id is None:
            order_id = int(item.Contribution_ID.string)
        kwargs['date'] = datetime.datetime.strptime(item.MeetingDate.string, '%Y-%m-%dT%H:%M:%S').date()
        if 'url' not in kwargs and item.Contribution_ID:
            meeting_id = item.Meeting_ID.string
            contribution_id = item.Contribution_ID.string
            kwargs['url'] = f'https://record.assembly.wales/Plenary/{meeting_id}#C{contribution_id}'
        if item.ContributionTime and item.ContributionTime.string:
            kwargs['time'] = datetime.datetime.strptime(item.ContributionTime.string, '%Y-%m-%dT%H:%M:%S')
        self.speeches.append(Typ(major=agenda_id, minor=order_id, **kwargs))

    def display_heading_agenda(self, item, typ, **kwargs):
        agenda_cy = str(item.Agenda_item_welsh.string)
        agenda_en = str(item.Agenda_item_english.string)
        self.add_speech(item, typ, en=agenda_en, cy=agenda_cy, suffix='h', **kwargs)

    def display_heading_text(self, item):
        lang, text_cy, text_en = self._verbatim_text(item, html=False)
        self.add_speech(item, MinorHeading, lang=lang, en=text_en, cy=text_cy)

    def display_speech(self, item, html=True, double_escaped=False, order_id=None):
        lang, text_cy, text_en = self._verbatim_text(item, html=html, double_escaped=double_escaped)
        if not text_cy and not text_en:
            return
        member_id = item.Member_Id.string
        if member_id:
            name = str(item.Member_name_English.string or '')
            if member_id == '7':
                speaker_id = None
                name = 'Member of the Senedd'
            else:
                try:
                    person = memberList.match_by_id(member_id, self.date)
                except KeyError:
                    raise Exception(f"Could not find person for {name} {member_id}")
                speaker_id = person['id']
            self.add_speech(item, Speech, lang=lang, en=text_en, cy=text_cy, speaker_id=speaker_id, speaker_name=name, order_id=order_id)
        else:
            self.add_speech(item, Info, lang=lang, en=text_en, cy=text_cy, order_id=order_id)

    def display_info(self, item):
        lang, text_cy, text_en = self._verbatim_text(item)
        if not text_cy and not text_en:
            return
        if b'In the bilingual version, the left-hand column' in text_en.encode_contents():
            return
        self.add_speech(item, Info, lang=lang, en=text_en, cy=text_cy)

    def display_vote(self, item):
        lang, text_cy, text_en = self._verbatim_text(item)
        self.add_speech(item, Info, lang=lang, en=text_en, cy=text_cy)

        vote_id = int(item.Contribution_ID.string)
        division = self.divisions[vote_id]

        m = re.search('record.senedd.wales/VoteOutcome/\d+/\?#V(\d+)', str(text_en))
        url = 'https://' + m.group(0)
        number = m.group(1)

        soup_en = BeautifulSoup("<body>", 'lxml')
        soup_cy = BeautifulSoup("<body>", 'lxml')

        count_el = soup_en.new_tag('divisioncount')
        count_el['for'] = division['for']
        count_el['against'] = division['against']
        count_el['abstain'] = division['abstain']
        soup_en.body.append(count_el)
        soup_cy.body.append(copy.copy(count_el))

        votes = {'for': [], 'against': [], 'abstain': [], 'didnotvote': []}
        for id, (name, vote) in division['votes'].items():
            vote_el = soup_en.new_tag('msname')
            vote_el['person_id'] = id
            vote_el['vote'] = vote
            vote_el.string = name
            votes[vote].append(vote_el)

        for way in ('for', 'against', 'abstain', 'didnotvote'):
            list_el = soup_en.new_tag('mslist')
            list_el['vote'] = way
            list_el.extend(votes[way])
            soup_en.body.append(list_el)
            soup_cy.body.append(copy.copy(list_el))

        self.add_speech(item, Vote, en=soup_en.body, cy=soup_cy.body,
            divnumber=number, title_en=division['name_en'], title_cy=division['name_cy'],
            url=url, suffix='v')

    def _verbatim_text(self, item, html=True, double_escaped=False):
        text_verbatim = item.contribution_verbatim.string or ''
        text_translated = item.contribution_translated.string or ''
        if html:
            if text_translated:
                if double_escaped: # ANR is double escaped
                    text_translated = unescape(text_translated)
                text_translated = BeautifulSoup(text_translated, 'lxml').body
            if text_verbatim:
                if double_escaped:
                    text_verbatim = unescape(text_verbatim)
                text_verbatim = BeautifulSoup(text_verbatim, 'lxml').body
        if item.contribution_language:
            lang = str(item.contribution_language.string).lower()
            if lang == 'cy':
                text_cy = text_verbatim
                text_en = text_translated
            elif lang == 'en':
                text_en = text_verbatim
                text_cy = text_translated
        else:  # QNR does not have this, and only translates Welsh to English
            text_en = text_translated
            if text_verbatim == text_translated:
                text_cy = ''
                lang = 'en'
            else:
                text_cy = text_verbatim
                lang = 'cy'
        return lang, text_cy, text_en

    def parse_votes(self, votes):
        soup = BeautifulSoup(votes, 'xml')
        self.divisions = {}
        for item in soup.find_all(['XML_Plenary_Vote', 'XML_Plenary-FifthSenedd_Vote']):
            vote_id = int(item.Contribution_ID.string)
            if vote_id not in self.divisions:
                self.divisions[vote_id] = {
                    "name_en": item.Vote_Name_English.string,
                    "name_cy": item.Vote_Name_Welsh.string,
                    "for": item.VotesTotalFor.string,
                    "against": item.VotesTotalAgainst.string,
                    "abstain": item.VotesTotalAbstain.string,
                    #"result_en": item.Vote_Result_Welsh.string,
                    #"result_cy": item.Vote_Result_English.string,
                    #"meeting_type": item.Meeting_type.string,
                    "votes": {},
                }
            vote = str(item.Results_Result.string).lower()
            if not int(item.Member_Id.string): continue
            name = str(item.Member_name_English.string)
            try:
                person = memberList.match_by_id(item.Member_Id.string, self.date)
            except KeyError:
                raise Exception(f"Could not find person for {name} {item.Member_Id.string}")
            self.divisions[vote_id]['votes'][person['id']] = (name, vote)

    def parse_qnr(self, qnr):
        soup = BeautifulSoup(qnr, 'xml')
        current_agenda_en = ""
        major = False
        c = 0  # There are duplicate order IDs in the QNR
        for item in soup.find_all(['XML_Plenary_QNR_Bilingual', 'XML_Plenary-FifthSenedd_QNR_Bilingual']):
            if not major:
                major = True
                self.add_speech(item, MajorHeading, en='QNR', cy='QNR', suffix='mh', order_id=c)

            agenda_en = str(item.Agenda_item_english.string)
            if agenda_en != current_agenda_en and agenda_en:
                current_agenda_en = agenda_en
                self.display_heading_agenda(item, MinorHeading, order_id=c)

            ctype = str(item.contribution_type.string)
            if ctype == 'QNR':
                self.display_speech(item, html=False, order_id=c)
            elif ctype == 'ANR':
                self.display_speech(item, double_escaped=True, order_id=c)
            else:
                raise Exception(f"Unknown contribution type {ctype}")
            c += 1

    def parse_plenary(self, text):
        soup = BeautifulSoup(text, 'xml')

        self.speeches = []
        current_agenda_id = '0'
        for item in soup.find_all(['XML_Plenary_Bilingual', 'XML_Plenary-FifthSenedd_Bilingual']):
            #entry_id = item.Contribution_ID
            #tv_spoken = item.contribution_spoken_seneddTv
            #tv_translated = item.contribution_translated_seneddTv

            agenda_id = item.Agenda_Item_ID.string.split('-')[1]
            agenda_en = str(item.Agenda_item_english.string)
            if agenda_id != current_agenda_id and agenda_en:
                current_agenda_id = agenda_id
                self.display_heading_agenda(item, MajorHeading)

            ctype = str(item.contribution_type.string)
            if ctype == 'C':
                self.display_speech(item)
            elif ctype == 'I':
                self.display_info(item)
            elif ctype == 'B':
                self.display_heading_text(item)
            elif ctype == 'O':
                self.display_speech(item)
            elif ctype == 'V':
                self.display_vote(item)
            else:
                raise Exception(f"Unknown contribution type {ctype}")


def read_or_blank(f):
    if f.exists():
        return open(f, encoding='utf-8-sig').read()

def age_cmp(f, mtime):
    if f.exists():
        return f.stat().st_mtime < mtime
    return True

def write_if_text(t, f):
    if t:
        fp = open(f, 'w')
        fp.write(t)
        fp.close()

if __name__ == '__main__':
    ind = Path(sys.argv[1])
    outd = Path(sys.argv[2])
    for fn in sorted(os.scandir(ind / 'plenary'), reverse=True, key=lambda e: e.name):
        out_en = outd / 'en' / fn.name
        out_cy = outd / 'cy' / fn.name
        in_plenary = ind / 'plenary' / fn.name
        in_vote = ind / 'votes' / fn.name
        in_qnr = ind / 'qnr' / fn.name

        msg = 'Parsing'
        if out_en.exists():
            out_mtime = out_en.stat().st_mtime
            msg = 'Reparsing'
            if age_cmp(in_plenary, out_mtime) and age_cmp(in_vote, out_mtime) and age_cmp(in_qnr, out_mtime):
                continue

        text = read_or_blank(in_plenary)
        votes = read_or_blank(in_vote)
        qnr = read_or_blank(in_qnr)
        date = fn.name[6:16]
        print(msg, 'Senedd', date)
        en, cy = ParseDay().parse_day(date, text, votes, qnr)
        write_if_text(en, out_en)
        write_if_text(cy, out_cy)
