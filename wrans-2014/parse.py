#!/usr/bin/env python
#
# UK Parliament Written Answers are now in a new database-driven website. This
# site has a nice search, and RSS feeds, but for now we still need a bit of
# scraping to fetch the data. Ever so slightly simpler than the past, though!

import argparse
import datetime
import json
import os
import re
import urllib
from xml.sax.saxutils import escape

import bs4
import dateutil.parser
import requests
import requests_cache


# Command line arguments
yesterday = datetime.date.today() - datetime.timedelta(days=1)
parser = argparse.ArgumentParser(description='Scrape/parse new Written Answers database.')
parser.add_argument('--house', required=True, choices=['commons', 'lords'], help='Which house to fetch')
parser.add_argument('--type', required=True, choices=['answers', 'statements'], help='What sort of thing to fetch')
parser.add_argument('--date', default=yesterday.isoformat(), help='date to fetch')
parser.add_argument('--members', required=True, help='filename of membership JSON')
parser.add_argument('--out', required=True, help='directory in which to place output')
ARGS = parser.parse_args()

# Monkey patch, monkey patch, do the funky patch
cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
requests_cache.install_cache(cache_path, expire_after=60*60*12)

HOST = 'http://www.parliament.uk'
URL_ROOT = '%s/business/publications/written-questions-answers-statements/' % HOST
if ARGS.type == 'answers':
    URL_INDEX = URL_ROOT + 'written-questions-answers/'
else:
    URL_INDEX = URL_ROOT + 'written-statements/'


def _lord_name(m):
    n = m['name']
    name = n['honorific_prefix']
    if name in ('Bishop', 'Archbishop'):
        name = 'Lord %s' % name
    if n['lordname']:
        name += ' %s' % n['lordname']
    if n['lordofname']:
        name += ' of %s' % n['lordofname']
        if not n['lordname']:
            name = 'The ' + name
    # Earl of Clancarty is in the peerage of Ireland but the Lords
    # still uses it :/ Should really use peers-aliases.xml here.
    if name == 'Viscount Clancarty':
        name = 'The Earl of Clancarty'
    return name

with open(ARGS.members) as fp:
    MEMBERS = json.load(fp)
if ARGS.house == 'lords':
    MEMBERS_BY_NAME = {}
    for m in MEMBERS['memberships']:
        if m.get('organization_id') != 'house-of-lords': continue
        name = _lord_name(m).lower()
        MEMBERS_BY_NAME.setdefault(name, []).append(m)
else:
    DATADOTPARL_ID_TO_PERSON_ID = {}
    for person in MEMBERS['persons']:
        for i in person.get('identifiers', []):
            if i['scheme'] == 'datadotparl_id':
                DATADOTPARL_ID_TO_PERSON_ID[i['identifier']] = person['id']


def main():
    params = urllib.urlencode({
        'page': 1,
        'max': 100,
        'questiontype': 'QuestionsWithAnswersOnly',  # 'AllQuestions',
        'house': ARGS.house,
        'use-dates': 'True',
        'answered-from': ARGS.date,
        'answered-to': ARGS.date,
    })
    url_page = '%s?%s' % (URL_INDEX, params)
    if ARGS.type == 'answers':
        writtens = Questions()
    else:
        writtens = Statements()
    errors = 0
    while url_page:
        r = requests.get(url_page)
        if 'There are no results' in r.content:
            break
        if 'Server Error' in r.content:
            requests.Session().cache.delete_url(url_page)
            errors += 1
            if errors >= 3:
                raise Exception, 'Too many server errors, giving up'
            continue
        writtens.add_from_html(r.content)
        url_page = writtens.next_page

    # Make sure we have all grouped questions (some might actually not have
    # been returned due to bugs/being on another day)
    if ARGS.type == 'answers':
        for uid, qn in writtens.by_id.items():
            for a in qn.groupedquestions:
                writtens.get_by_id(a)

    output = ('%s' % writtens).encode('utf-8')
    if output:
        if ARGS.type == 'answers':
            filename = 'lordswrans' if ARGS.house == 'lords' else 'answers'
        else:
            filename = 'lordswms' if ARGS.house == 'lords' else 'ministerial'
        filename += ARGS.date + '.xml'
        with open(os.path.join(ARGS.out, filename), 'w') as fp:
            fp.write(output)
        print "* %s Written %s: found %d new items" % (ARGS.house.title(), ARGS.type.title(), writtens.number)


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class WrittenThing(object):
    def find_speaker(self, h, date):
        name = h.a.text
        if ARGS.house == 'lords':
            # Loop through all, match on name and date
            members = MEMBERS_BY_NAME[name.lower()]
            member = next((m for m in members if m['start_date'] <= date <= m.get('end_date', '9999-12-31')), None)
            if member is None:
                raise Exception('Could not find matching entry for %s' % name)
            person_id = member['person_id']
        else:
            speaker_id = re.search('(\d+)$', h.a['href']).group(1)
            person_id = DATADOTPARL_ID_TO_PERSON_ID[speaker_id]
        return AttrDict(id=person_id, name=name)

    def find_date(self, d, regex):
        date = re.match('\s*%s on:\s+(?P<date>.*)' % regex, d.text)
        date = date.group('date')
        date = dateutil.parser.parse(date).date().isoformat()
        return date


class WrittenThings(object):
    def __init__(self):
        self.by_id = {}
        self.by_dept = {}

    def wanted_thing(self, st):
        return True

    def add_from_html(self, data):
        """Provide a page of HTML, parse out all its things"""
        soup = bs4.BeautifulSoup(data)
        for item in soup.find_all(class_="qna-result-container"):
            item = self.model(item, self)
            if self.wanted_thing(item):
                self.by_id[item.uid] = item
                self.by_dept.setdefault(item.dept, []).append(item)

        n = soup.find(text='Next').parent
        if n.name == 'span':
            self.next_page = None
        elif n.name == 'a':
            self.next_page = '%s%s' % (HOST, n['href'])
        else:
            raise Exception

    @property
    def number(self):
        return len(self.by_id)

    def __str__(self):
        """Outputs the things, grouped by department, as parlparse XML"""
        if not self.by_dept:
            return ''
        out = '<publicwhip>\n'
        for dept, deptitems in self.by_dept.items():
            out += '''
<major-heading id="uk.org.publicwhip/{gid}/{item.date}.{item.uid}.mh" nospeaker="true">
    {dept}
</major-heading>
'''.format(dept=dept, item=deptitems[0], gid=self.gid_type)
            out += ''.join([ '%s' % item for item in deptitems ])
        out += '\n</publicwhip>'
        return out


class Statement(WrittenThing):
    def __init__(self, st, sts):
        self.uid = escape(st.find(class_="qna-result-ws-uin").a.text)
        self.dept = escape(st.find(class_="qna-result-writtenstatement-answeringbody").text)
        self.heading = escape(st.find(class_="qna-result-ws-content-heading").text)

        date = st.find(class_="qna-result-ws-date")
        self.date = self.find_date(date, 'Made')
        speaker = st.find(class_='qna-result-writtenstatement-made-by')
        self.speaker = self.find_speaker(speaker, self.date)

        joint = st.find(class_='qna-result-writtenstatement-joint-statement-row')
        if joint:
            a = joint.find('a')
            a['href'] = HOST + a['href']

        statement = st.find(class_="qna-result-writtenstatement-text")
        self.statement = statement.renderContents().decode('utf-8').strip()

    def __str__(self):
        return u'''
<minor-heading id="uk.org.publicwhip/wms/{st.date}.{st.uid}.h" nospeaker="true">
    {st.heading}
</minor-heading>
<speech id="uk.org.publicwhip/wms/{st.date}.{st.uid}.0" person_id="{st.speaker.id}" speakername="{st.speaker.name}" url="{url_root}written-statement/{house}/{st.date}/{st.uid}/">
    {st.statement}
</speech>
'''.format(st=self, house=ARGS.house.title(), url_root=URL_ROOT)


class Question(WrittenThing):
    def __init__(self, qn, qns):
        self.qns = qns

        self.uid = escape(qn.find(class_="qna-result-question-uin").a.text)
        self.dept = escape(qn.find(class_="qna-result-question-answeringbody").text)
        try:
            hdg = qn.find(class_="qna-result-question-hansardheading")
            self.heading = escape(hdg.text)
        except:
            self.heading = '*No heading*'

        date_asked = qn.find(class_="qna-result-question-date")
        self.date_asked = self.find_date(date_asked, 'Asked')
        self.date = self.date_asked
        asker = qn.find(class_='qna-result-question-title')
        self.asker = self.find_speaker(asker, self.date_asked)
        question = qn.find(class_="qna-result-question-text").text.strip()
        self.question = escape(question)

        self.answers = []
        for answer_ctr in qn.findAll(class_='qna-result-answer-container'):
            date_answer = answer_ctr.find(class_="qna-result-answer-date")
            date_answer = self.find_date(date_answer, '(Answered|Corrected)')
            answerer = answer_ctr.find(class_="qna-result-answer-title")
            answerer = self.find_speaker(answerer, date_answer)

            groupedquestions_container = answer_ctr.find(class_="qna-result-groupedquestions-container")
            groupedquestions = []
            if groupedquestions_container:
                groupedquestions = answer_ctr.find_all(class_='qna-result-groupedquestion-container')
                groupedquestions = [x.a.text for x in groupedquestions]
                groupedquestions_container.extract()

            answer = answer_ctr.find(class_="qna-result-answer-content")
            # Remove show/hide changes JS-only code at top
            for l in answer.findAll('label'): l.extract()
            for l in answer.findAll('input'): l.extract()
            # Replace spans with semantic elements
            for l in answer.findAll('span', class_='ins'):
                l.name = 'ins'
            for l in answer.findAll('span', class_='del'):
                l.name = 'del'

            answer = answer.renderContents().decode('utf-8').strip()

            # Attachments are okay just left in the answer
            # attachments = answer_ctr.find(class_="qna-result-attachments-container")
            # if attachments:
            #     self.attachments = answer_ctr.find_all(class_='qna-result-attachment-container')

            self.answers.append(AttrDict({
                'answerer': answerer,
                'date': date_answer,
                'answer': answer,
                'groupedquestions': groupedquestions,
            }))

    @property
    def groupedquestions(self):
        if len(self.answers):
            return self.answers[-1].groupedquestions
        return []

    @property
    def secondary_group_question(self):
        return self.groupedquestions and self.uid > min(self.groupedquestions)

    @property
    def questions_xml(self):
        qns = [self] + [self.qns.by_id[q] for q in self.groupedquestions]
        return ''.join([u'''
<ques id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.q{i}" person_id="{qn.asker.id}" speakername="{qn.asker.name}" url="{url_root}written-question/{house}/{qn.date_asked}/{qn.uid}/">
    <p qnum="{qn.uid}">{qn.question}</p>
</ques>'''.format(i=i, qn=qn, house=ARGS.house.title(), url_root=URL_ROOT) for i, qn in enumerate(qns)])

    @property
    def answers_xml(self):
        return ''.join([u'''
<reply id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.r{i}" person_id="{answer.answerer.id}" speakername="{answer.answerer.name}">
    {answer.answer}
</reply>'''.format(i=i, qn=self, answer=answer) for i, answer in enumerate(self.answers)])

    def __str__(self):
        # TODO If we were to import unanswered questions, we would want to
        # redirect them if they then got grouped together when answered. This
        # might work, but isn't needed for now.
        if self.secondary_group_question:
            return ''
        #    oldgid = "uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.h".format(qn=self)
        #    newgid = "uk.org.publicwhip/wrans/{qn.date_asked}.{id}.h".format(qn=self, id=min(self.groupedquestions))
        #    matchtype = 'altques'
        #    return '<gidredirect oldgid="%s" newgid="%s" matchtype="%s"/>\n' % (oldgid, newgid, matchtype)

        return u'''
<minor-heading id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.h" nospeaker="true">
    {qn.heading}
</minor-heading>
{qn.questions_xml}
{qn.answers_xml}
'''.format(qn=self)


class Statements(WrittenThings):
    gid_type = 'wms'
    model = Statement


class Questions(WrittenThings):
    gid_type = 'wrans'
    model = Question

    def wanted_thing(self, qn):
        # If the question was answered/corrected on our date
        if ARGS.date in [ a.date for a in qn.answers ]:
            return True
        return False

    def get_by_id(self, uid):
        # It is possible that when we need to look up a grouped ID, it's not
        # present. Either it was on a different day (possible), or there's a
        # mistake in what has been returned from the search. Perform a separate
        # scrape/parse of the question if so, to get its data.
        if uid in self.by_id:
            return self.by_id[uid]
        r = requests.get(URL_INDEX, params={'uin': uid})
        if 'There are no results' in r.content:
            return
        if 'Server Error' in r.content:
            return
        soup = bs4.BeautifulSoup(r.content)
        qn = soup.find(class_='qna-result-container')
        qn = Question(qn, self)
        self.by_id[qn.uid] = qn
        self.by_dept.setdefault(qn.dept, []).append(qn)
        return qn


if __name__ == '__main__':
    main()
