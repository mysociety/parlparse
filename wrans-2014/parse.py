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
import dateutil.parser
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
URL_ROOT = '%s/' % HOST
if ARGS.type == 'answers':
    URL_INDEX = URL_ROOT + 'written-questions'
else:
    URL_INDEX = URL_ROOT + 'written-statements'


def _lord_name_on_date(p, date):
    for n in PERSONS[p]:
        if n.get('start_date', '0000-00-00') <= date <= n.get('end_date', '9999-12-31'):
            return _lord_name(n)
    # Not available on this date (e.g. deceased)
    return ''

def _lord_name(n):
    name = n['honorific_prefix']
    if name in ('Bishop', 'Archbishop'):
        name = 'Lord %s' % name
    if n['lordname']:
        name += ' %s' % n['lordname']
    if n['lordofname']:
        name += ' of %s' % n['lordofname']
    # Earl of Clancarty is in the peerage of Ireland but the Lords
    # still uses it :/ Should really use peers-aliases.xml here.
    if name == 'Viscount Clancarty':
        name = 'The Earl of Clancarty'
    return name


with open(ARGS.members) as fp:
    MEMBERS = json.load(fp)
    DATADOTPARL_ID_TO_PERSON_ID = {}
    for person in MEMBERS['persons']:
        for i in person.get('identifiers', []):
            if i['scheme'] == 'datadotparl_id':
                DATADOTPARL_ID_TO_PERSON_ID[i['identifier']] = person['id']


def main():
    params = urllib.urlencode({
        'Page': 1,
        'Answered': 'Answered',
        'House': ARGS.house.title(),
    })
    url_page = '%s?%s' % (URL_INDEX, params)
    if ARGS.type == 'answers':
        writtens = Questions()
    else:
        writtens = Statements()
    errors = 0
    while url_page:
        r = requests.get(url_page)
        if 'There are no written' in r.content:
            break
        if 'Server Error' in r.content:
            requests.Session().cache.delete_url(url_page)
            errors += 1
            if errors >= 5:
                raise Exception, 'Too many server errors, giving up'
            continue
        writtens.add_from_html(r.content)
        url_page = writtens.next_page

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
    def find_speaker(self, h, date, big_card=False):
        if big_card:
            name = h.a.find(class_='primary-info').text.strip()
        else:
            name = h.a.text.strip()
        speaker_id = re.search('(\d+)/contact$', h.a['href']).group(1)
        person_id = DATADOTPARL_ID_TO_PERSON_ID[speaker_id]
        return AttrDict(id=person_id, name=name)

    def find_date(self, d, regex):
        date = re.match('\s*%s\s+(?P<date>.*)' % regex, d.text)
        date = date.group('date')
        date = dateutil.parser.parse(date).date().isoformat()
        return date


class WrittenThings(object):
    def __init__(self):
        self.by_id = {}
        self.by_dept = {}

    def add_from_html(self, data):
        """Provide a page of HTML, parse out all its things"""
        soup = bs4.BeautifulSoup(data)
        finished = False
        for item in soup.find_all(class_="card"):
            item = self.model(item, self)
            if item.list_date == ARGS.date:
                self.by_id[item.uid] = item
                self.by_dept.setdefault(item.dept, []).append(item)
            elif item.list_date < ARGS.date:
                finished = True
                break

        n = soup.find(title='Go to next page')
        if n.name == 'span' or finished:
            self.next_page = None
        elif n.name == 'a':
            self.next_page = '%s%s' % (HOST, n['href'])
        else:
            raise Exception

    def get_detail(self):
        url = '%s/detail/%s/%s' % (URL_INDEX, self.date, self.uid)
        r = requests.get(url)
        soup = bs4.BeautifulSoup(r.content)
        return soup

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
        href = st.find(class_="overlay-link")['href']
        m = re.match('/written-statements/detail/(\d\d\d\d-\d\d-\d\d)/(.+)', href)
        self.date, self.uid = m.groups()
        self.list_date = self.date

        # We might have things we don't yet want, or older things
        if ARGS.date != self.date:
            return

        self.dept = escape(st.find(class_="primary-info").text).strip()
        self.heading = escape(st.find(class_="text").text).strip()

        speaker = st.find(class_='content-text')
        self.speaker = self.find_speaker(speaker, self.date)

        # Ugh
        soup = self.get_detail()
        title = soup.find('h3', text='Statement made by')
        answerer = self.find_speaker(title.parent, self.date, big_card=True)
        title = soup.find('h3', text='Statement')
        statement = ''
        for t in title.next_siblings:
            statement += t.decode().strip()
        self.statement = statement

    def __str__(self):
        return u'''
<minor-heading id="uk.org.publicwhip/wms/{st.date}.{st.uid}.h" nospeaker="true">
    {st.heading}
</minor-heading>
<speech id="uk.org.publicwhip/wms/{st.date}.{st.uid}.0" person_id="{st.speaker.id}" speakername="{st.speaker.name}" url="{url_root}written-statements/detail/{st.date}/{st.uid}">
    {st.statement}
</speech>
'''.format(st=self, url_root=URL_ROOT)


class Question(WrittenThing):
    def __init__(self, qn, qns):
        self.qns = qns

        href = qn.find(class_="overlay-link")['href']
        m = re.match('/written-questions/detail/(\d\d\d\d-\d\d-\d\d)/(.+)', href)
        self.date_asked, self.uid = m.groups()
        self.date = self.date_asked

        self.dept = escape(qn.find(class_="primary-info").text).strip()
        self.heading = escape(qn.find(class_="secondary-info").text).strip()

        asker = qn.find(class_='content-text')
        self.asker = self.find_speaker(asker, self.date_asked)
        question = qn.find(class_="sub-card-question-text").text.strip()
        self.question = escape(question)

        answered = qn.find(class_='answer-info').find(class_='item')
        date_answer = self.find_date(answered, 'Answered')
        self.list_date = date_answer

        # We might have things we don't yet want, or older things
        if ARGS.date != date_answer:
            return

        # Ugh
        soup = self.get_detail()
        title = soup.find('h3', text='Answer')
        col = title.parent
        answerer = self.find_speaker(col, date_answer, big_card=True)
        row = col.parent
        row = row.find_next_sibling('div') # ignore answered date
        answer = ''
        for r in row.find_next_siblings('div'): # rows containing answer, correction
            for t in r.children:
                if t.name == 'div': # column, but not always present
                    for tt in t.children:
                        answer += tt.decode().strip()
                else:
                    answer += t.decode().strip()

        self.answer = AttrDict({
            'answerer': answerer,
            'date': date_answer,
            'answer': answer,
        })

    @property
    def questions_xml(self):
        return u'''
<ques id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.q0" person_id="{qn.asker.id}" speakername="{qn.asker.name}" url="{url_root}written-questions/detail/{qn.date_asked}/{qn.uid}">
    <p qnum="{qn.uid}">{qn.question}</p>
</ques>'''.format(qn=self, url_root=URL_ROOT)

    @property
    def answers_xml(self):
        return u'''
<reply id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.r{i}" person_id="{answer.answerer.id}" speakername="{answer.answerer.name}">
    {answer.answer}
</reply>'''.format(i=0, qn=self, answer=self.answer)

    def __str__(self):
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


if __name__ == '__main__':
    main()
