#!/usr/bin/env python
#
# UK Parliament Written Answers are now in a new database-driven website. This
# site has a nice-ish search, but for now we still need a bit of scraping to
# fetch the data. Ever so slightly simpler than the past, though!

import argparse
import datetime
import json
import os
import re
import urllib
from xml.sax.saxutils import escape

import bs4
import requests
import requests_cache


# Command line arguments
yesterday = datetime.date.today() - datetime.timedelta(days=1)
parser = argparse.ArgumentParser(description='Scrape/parse new Written Answers/Statements database.')
parser.add_argument('--house', required=True, choices=['commons', 'lords'], help='Which house to fetch')
parser.add_argument('--type', required=True, choices=['answers', 'statements'], help='What sort of thing to fetch')
parser.add_argument('--date', default=yesterday.isoformat(), help='date to fetch')
parser.add_argument('--members', required=True, help='filename of membership JSON')
parser.add_argument('--out', required=True, help='directory in which to place output')
ARGS = parser.parse_args()

# Monkey patch, monkey patch, do the funky patch
cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
requests_cache.install_cache(cache_path, expire_after=60*60*12)

HOST = 'https://questions-statements.parliament.uk'
API_HOST = 'https://writtenquestions-api.parliament.uk'
if ARGS.type == 'answers':
    URL_INDEX = HOST + '/written-questions'
    API_INDEX = API_HOST + '/api/writtenquestions/questions'
else:
    URL_INDEX = HOST + '/written-statements'
    API_INDEX = API_HOST + '/api/writtenstatements/statements'

with open(ARGS.members) as fp:
    MEMBERS = json.load(fp)
    DATADOTPARL_ID_TO_PERSON_ID = {}
    for person in MEMBERS['persons']:
        for i in person.get('identifiers', []):
            if i['scheme'] == 'datadotparl_id':
                DATADOTPARL_ID_TO_PERSON_ID[int(i['identifier'])] = person['id']


def main():
    params = {
        'take': 20,
        'house': ARGS.house.title(),
        'expandMember': 'true',
    }
    if ARGS.type == 'answers':
        writtens = Questions()
        get_from_list(writtens, dict(params, answeredWhenFrom=ARGS.date, answeredWhenTo=ARGS.date))
        get_from_list(writtens, dict(params, correctedWhenFrom=ARGS.date, correctedWhenTo=ARGS.date))
        # Make sure we have all grouped questions (some might actually not have
        # been returned due to being on another day)
        for uin, qn in writtens.by_id.items():
            qn.groupedQuestions = map(writtens.get_by_uin, qn.groupedQuestions)
    else:
        writtens = Statements()
        params['madeWhenFrom'] = ARGS.date
        params['madeWhenTo'] = ARGS.date
        get_from_list(writtens, params)

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


def get_from_list(writtens, params):
    params = urllib.urlencode(params)
    url_page = '%s?%s' % (API_INDEX, params)
    errors = 0
    skip = 0
    while url_page:
        url = '%s&skip=%d' % (url_page, skip)
        print url
        j = requests.get(url).json()
        if not j['results']:
            break
        if j.get('status') == 500:
            requests.Session().cache.delete_url(url_page)
            errors += 1
            if errors >= 5:
                raise Exception, 'Too many server errors, giving up: %s' % j['title']
            continue
        writtens.add_from_json(j)
        if writtens.number < j['totalResults']:
            skip += 20
        else:
            url_page = None


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class WrittenThing(AttrDict):
    def find_speaker(self, speaker):
        person_id = DATADOTPARL_ID_TO_PERSON_ID[speaker['id']]
        return AttrDict(id=person_id, name=speaker['name'])

    def find_date(self, date):
        return date.replace('T00:00:00', '')

    def fix_text(self, text):
        soup = bs4.BeautifulSoup(text)
        return ''.join(map(unicode, soup.body.contents))

    def get_detail(self):
        url = '%s/%s' % (API_INDEX, self['id'])
        return requests.get(url).json()['value']


class WrittenThings(object):
    def __init__(self):
        self.by_id = {}
        self.by_dept = {}

    def add_from_json(self, data):
        """Provide the API JSON, parse out all its things"""
        for result in data['results']:
            item = result['value']
            item = self.model(item, self)
            self.by_id[item.uin] = item
            self.by_dept.setdefault(item.answeringBodyName, []).append(item)

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
<major-heading id="uk.org.publicwhip/{gid}/{item.date}.{item.uin}.mh" nospeaker="true">
    {dept}
</major-heading>
'''.format(dept=dept, item=deptitems[0], gid=self.gid_type)
            out += ''.join([ '%s' % item for item in deptitems ])
        out += '\n</publicwhip>'
        return out


class Statement(WrittenThing):
    def __init__(self, st, sts):
        super(Statement, self).__init__(st)
        self.date = self.find_date(self.dateMade)
        self.uin = self.uin.lower()
        self.heading = escape(self.title)
        self.speaker = self.find_speaker(self.member)

        data = self.get_detail()
        self.statement = self.fix_text(data['text'])
        for a in data['attachments']:
            self.statement += '<p><a href="%s">%s</a> (%s, %.1fKB)</p>' % (a['url'], a['title'], a['fileType'], a['fileSizeBytes']/1024.0)

    def __str__(self):
        return u'''
<minor-heading id="uk.org.publicwhip/wms/{st.date}.{st.uin}.h" nospeaker="true">
    {st.heading}
</minor-heading>
<speech id="uk.org.publicwhip/wms/{st.date}.{st.uin}.0" person_id="{st.speaker.id}" speakername="{st.speaker.name}" url="{url_root}/written-statements/detail/{st.date}/{st.uin}">
    {st.statement}
</speech>
'''.format(st=self, url_root=HOST)


class Question(WrittenThing):
    def __init__(self, qn, qns):
        super(Question, self).__init__(qn)
        self.date = self.find_date(self.dateTabled)
        self.heading = escape(self.heading or 'Question')
        self.asker = self.find_speaker(self.askingMember)

        data = self.get_detail()
        self.question = escape(data['questionText'])
        self.answerer = self.find_speaker(self.answeringMember)
        self.date_answer = self.find_date(self.dateAnswered)
        self.answer = self.fix_text(data['answerText'])
        for a in data['attachments']:
            self.answer += '<p><a href="%s">%s</a> (%s, %.1fKB)</p>' % (a['url'], a['title'], a['fileType'], a['fileSizeBytes']/1024.0)

    @property
    def secondary_group_question(self):
        return self.groupedQuestions and self.uin > min(map(lambda x: x['uin'], self.groupedQuestions))

    @property
    def questions_xml(self):
        qns = [self] + self.groupedQuestions
        return ''.join([u'''
<ques id="uk.org.publicwhip/wrans/{qn.date}.{qn.uin}.q{i}" person_id="{qn.asker.id}" speakername="{qn.asker.name}" url="{url_root}/written-questions/detail/{qn.date}/{qn.uin}">
    <p qnum="{qn.uin}">{qn.question}</p>
</ques>'''.format(i=i, qn=qn, url_root=HOST) for i, qn in enumerate(qns)])

    @property
    def answers_xml(self):
        return u'''
<reply id="uk.org.publicwhip/wrans/{qn.date}.{qn.uin}.r{i}" person_id="{qn.answerer.id}" speakername="{qn.answerer.name}">
    {qn.answer}
</reply>'''.format(i=0, qn=self)

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
<minor-heading id="uk.org.publicwhip/wrans/{qn.date}.{qn.uin}.h" nospeaker="true">
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

    def get_by_uin(self, uin):
        if uin in self.by_id:
            return self.by_id[uin]

        qn = requests.get(API_INDEX, params={'expandMember': 'true', 'uin': uin}).json()
        qn = qn['results'][0]['value']
        qn = Question(qn, self)
        self.by_id[qn.uin] = qn
        self.by_dept.setdefault(qn.answeringBodyName, []).append(qn)
        return qn


if __name__ == '__main__':
    main()
