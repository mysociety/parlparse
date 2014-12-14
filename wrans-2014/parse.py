#!/usr/bin/env python
#
# UK Parliament Written Answers are now in a new database-driven website. This
# site has a nice search, and RSS feeds, but for now we still need a bit of
# scraping to fetch the data. Ever so slightly simpler than the past, though!

import argparse
import datetime
import os
import re
import urllib
from xml.sax.saxutils import escape

import bs4
import lxml.etree
import dateutil.parser
import requests
import requests_cache


# Command line arguments
yesterday = datetime.date.today() - datetime.timedelta(days=1)
parser = argparse.ArgumentParser(
    description='Scrape/parse new Written Answers database.')
parser.add_argument(
    '--date', dest='date', action='store', default=yesterday.isoformat(),
    help='date to fetch')
parser.add_argument(
    '--members', dest='members', action='store', required=True,
    help='filename of current member XML')
parser.add_argument(
    '--out', dest='out', action='store', required=True,
    help='directory in which to place output')
ARGS = parser.parse_args()

# Monkey patch, monkey patch, do the funky patch
cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
requests_cache.install_cache(cache_path, expire_after=60*60*12)

HOST = 'http://www.parliament.uk'
URL_ROOT = '%s/business/publications/written-questions-answers-statements/written-questions-answers/' % HOST
MEMBERS = lxml.etree.parse(ARGS.members)


def main():
    params = urllib.urlencode({
        'page': 1,
        'max': 100,
        'questiontype': 'QuestionsWithAnswersOnly',  # 'AllQuestions',
        'house': 'commons',  # 'commons,lords',
        'use-dates': 'True',
        'answered-from': ARGS.date,
        'answered-to': ARGS.date,
    })
    url_page = '%s?%s' % (URL_ROOT, params)
    questions = Questions()
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
        questions.add_from_html(r.content)
        url_page = questions.next_page

    # Make sure we have all grouped questions (some might actually not have
    # been returned due to bugs/being on another day)
    for uid, qn in questions.by_id.items():
        for a in qn.groupedquestions:
            questions.get_by_id(a)

    output = ('%s' % questions).encode('utf-8')
    if output:
        with open(os.path.join(ARGS.out, 'answers%s.xml' % ARGS.date), 'w') as fp:
            fp.write(output)
        print "* Commons Written Answers: found %d written answers" % questions.number


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class Questions(object):
    def __init__(self):
        self.by_id = {}
        self.by_dept = {}

    def add_from_html(self, data):
        """Provide a page of HTML, parse out all its questions"""
        soup = bs4.BeautifulSoup(data)
        for qn in soup.find_all(class_="qna-result-container"):
            qn = Question(qn, self)
            # If the question was answered/corrected on our date
            if ARGS.date in [ a.date for a in qn.answers ]:
                self.by_id[qn.uid] = qn
                self.by_dept.setdefault(qn.dept, []).append(qn)

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
        """Outputs the questions, grouped by department, as parlparse XML"""
        if not self.by_dept:
            return ''
        out = '<publicwhip>\n'
        for dept, deptqns in self.by_dept.items():
            out += '''
<major-heading id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.mh" nospeaker="true">
    {dept}
</major-heading>
'''.format(dept=dept, qn=deptqns[0])
            out += ''.join([ '%s' % qn for qn in deptqns ])
        out += '\n</publicwhip>'
        return out

    def get_by_id(self, uid):
        # It is possible that when we need to look up a grouped ID, it's not
        # present. Either it was on a different day (possible), or there's a
        # mistake in what has been returned from the search. Perform a separate
        # scrape/parse of the question if so, to get its data.
        if uid in self.by_id:
            return self.by_id[uid]
        r = requests.get(URL_ROOT, params={'uin': uid})
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


class Question(object):
    def __init__(self, qn, qns):
        self.qns = qns

        self.uid = qn.find(class_="qna-result-question-uin").a.text
        self.dept = qn.find(class_="qna-result-question-answeringbody").text
        try:
            hdg = qn.find(class_="qna-result-question-hansardheading")
            self.heading = hdg.text
        except:
            self.heading = '*No heading*'

        date_asked = qn.find(class_="qna-result-question-date")
        self.date_asked = self.find_date(date_asked, 'Asked')
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

    def find_speaker(self, h, date):
        speaker_id = re.search('(\d+)$', h.a['href']).group(1)
        members = MEMBERS.xpath('//member[@datadotparl_id="%s"]' % speaker_id)
        member = None
        for m in members:
            if m.attrib['fromdate'] <= date <= m.attrib['todate']:
                member = m
                break
        if member is None:
            raise Exception('Could not find matching entry for %s' % speaker_id)
        return AttrDict(id=member.attrib['id'], name=h.a.text)

    def find_date(self, d, regex):
        date = re.match('\s*%s on:\s+(?P<date>.*)' % regex, d.text)
        date = date.group('date')
        date = dateutil.parser.parse(date).date().isoformat()
        return date

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
<ques id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.q{i}" speakerid="{qn.asker.id}" speakername="{qn.asker.name}" url="http://www.parliament.uk/business/publications/written-questions-answers-statements/written-question/Commons/{qn.date_asked}/{qn.uid}/">
    <p qnum="{qn.uid}">{qn.question}</p>
</ques>'''.format(i=i, qn=qn) for i, qn in enumerate(qns)])

    @property
    def answers_xml(self):
        return ''.join([u'''
<reply id="uk.org.publicwhip/wrans/{qn.date_asked}.{qn.uid}.r{i}" speakerid="{answer.answerer.id}" speakername="{answer.answerer.name}">
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


if __name__ == '__main__':
    main()
