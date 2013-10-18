#!/usr/bin/env python
# coding=UTF-8

from cgi import escape
import errno
import sys
import os
import re
import random
import datetime
import itertools
import time
import traceback
import dateutil.parser as dateparser
from tempfile import NamedTemporaryFile
from optparse import OptionParser
from common import tidy_string
from common import non_tag_data_in
from common import just_time
from common import meeting_suspended
from common import meeting_closed

from lxml import etree

sys.path.append('../')

from BeautifulSoup import BeautifulSoup
from BeautifulSoup import NavigableString

from resolvemembernames import memberList

official_report_url_format = 'http://www.scottish.parliament.uk/parliamentarybusiness/28862.aspx?r={}&mode=html'

DIVISION_HEADINGS = ('FOR', 'AGAINST', 'ABSTENTIONS', 'SPOILED VOTES')

def is_division_way(element, report_date=None):
    """If it's a division heading, return a normalized version, otherwise None

    >>> is_division_way('  For ')
    ('FOR', None, None)
    >>> is_division_way('nonsense')
    (None, None, None)
    >>> is_division_way('abstentions ')
    ('ABSTENTIONS', None, None)
    >>> is_division_way(":\xA0FOR")
    ('FOR', None, None)
    >>> is_division_way('Abstention')
    ('ABSTENTIONS', None, None)
    >>> is_division_way('Absentions')
    ('ABSTENTIONS', None, None)
    >>> example_date = datetime.date(1999, 5, 13)
    >>> is_division_way('VOTES FOR DONALD DEWAR', example_date)
    ('FOR', 'Donald Dewar', u'uk.org.publicwhip/member/80147')
    >>> is_division_way('now cast your votes for someone', example_date)
    (None, None, None)
    >>> example_date = datetime.date(2000, 3, 14)
    >>> is_division_way('For Mr Kenneth Macintosh', example_date)
    ('FOR', 'Mr Kenneth Macintosh', u'uk.org.publicwhip/member/80191')
    >>> is_division_way('For option 1', example_date)
    ('FOR', 'Option 1', None)
    >>> is_division_way('The following member took the oath:')
    ('FOR', 'oath', None)
    >>> is_division_way('The following member made a solemn affirmation:')
    ('FOR', 'affirmation', None)
    >>> is_division_way('The following member made a solemn affirmation and repeated it in French:')
    ('FOR', 'affirmation', None)
    """

    tidied = tidy_string(non_tag_data_in(element)).upper()
    # Strip any non-word letters at the start and end:
    tidied = re.sub(r'^\W*(.*?)\W*$', '\\1', tidied)

    if tidied in DIVISION_HEADINGS:
        return (tidied, None, None)
    elif tidied in ('ABSTENTION', 'ABSENTIONS'):
        return ('ABSTENTIONS', None, None)
    elif re.search('^THE FOLLOWING MEMBERS? TOOK THE OATH( AND REPEATED IT IN .*)?:?$', tidied):
        return ('FOR', 'oath', None)
    elif re.search('^THE FOLLOWING MEMBERS? MADE A SOLEMN AFFIRMATION( AND REPEATED IT IN .*)?:?$', tidied):
        return ('FOR', 'affirmation', None)
    elif len(tidied.split()) < 128:
        # The second regular expression could be *very* slow on
        # strings that begin 'FOR', so only try it on short strings
        # that might be introducing a division, and assume that there
        # are 2 to 4 words in the name:
        m1 = re.search(r'^(?i)VOTES? FOR ([A-Z ]+)$', tidied)
        m2 = re.search(r'^FOR ((?:[A-Z]+\s*){2,4})$', tidied)
        m = m1 or m2
        if m:
            person_name = m.group(1).title()
            person_id = None
            if report_date:
                person_id = get_unique_speaker_id(person_name, report_date)
            return ('FOR', person_name, person_id)
        else:
            m = re.search(r'FOR OPTION (\d+)$', tidied)
            if m:
                return ('FOR', 'Option ' + m.group(1), None)
    return (None, None, None)

def first(iterable):
    for element in iterable:
        if element:
            return element
    return None

member_vote_re = re.compile('''
        ^                               # Beginning of the string
        (?P<last_name>[^,\(\)0-9:]+)    # ... last name, >= 1 non-comma characters
        ,                               # ... then a comma
        \s*                             # ... and some greedy whitespace
        (?P<first_names>[^,\(\)0-9:]*?) # ... first names, a minimal match of any characters
        \s*\(\(?                        # ... an arbitrary amout of whitespace and an open banana
                                        #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9:]*?) # ... constituency, a minimal match of any characters
        \)\s*\(                         # ... close banana, whitespace, open banana
        (?P<party>\D*?)                 # ... party, a minimal match of any characters
        \)                              # ... close banana
        $                               # ... end of the string
''', re.VERBOSE)

member_vote_fullname_re = re.compile('''
        ^                               # Beginning of the string
        (?P<full_name>[^,\(\)0-9:]+)    # ... full name, >= 1 non-comma characters
        \s*\(\(?                        # ... an arbitrary amout of whitespace and an open banana
                                        #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9:]*?) # ... constituency, a minimal match of any characters
        \)\s*\(                         # ... close banana, whitespace, open banana
        (?P<party>\D*?)                 # ... party, a minimal match of any characters
        \)                              # ... close banana
        $                               # ... end of the string
''', re.VERBOSE)

member_vote_just_constituency_re = re.compile('''
        ^                               # Beginning of the string
        (?P<last_name>[^,\(\)0-9:]+)    # ... last name, >= 1 non-comma characters
        ,                               # ... then a comma
        \s*                             # ... and some greedy whitespace
        (?P<first_names>[^,\(\)0-9:]*?) # ... first names, a minimal match of any characters
        \s*\(\(?                        # ... an arbitrary amout of whitespace and an open banana
                                        #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9:]*?) # ... constituency, a minimal match of any characters
        \)\s*                           # ... close banana, whitespace
        $                               # ... end of the string
''', re.VERBOSE)

def get_unique_speaker_id(tidied_speaker, on_date):
    ids = memberList.match_whole_speaker(tidied_speaker,str(on_date))
    if ids is None:
        # This special return value (None) indicates that the speaker
        # is something we know about, but not an MSP (e.g Lord
        # Advocate)
        return None
    else:
        if len(ids) == 0:
            log_speaker(tidied_speaker,str(on_date),"missing")
            return None
        elif len(ids) == 1:
            Speech.speakers_so_far.append(ids[0])
            return ids[0]
        else:
            final_id = None
            # If there's an ambiguity there our best bet is to go
            # back through the previous IDs used today, and pick
            # the most recent one that's in the list we just got
            # back...
            for i in range(len(Speech.speakers_so_far) - 1, -1, -1):
                older_id = Speech.speakers_so_far[i]
                if older_id in ids:
                    final_id = older_id
                    break
            if final_id:
                Speech.speakers_so_far.append(final_id)
                return final_id
            else:
                log_speaker(tidied_speaker,str(on_date),"genuine ambiguity")
                # self.speaker_id = None

def is_member_vote(element, vote_date, expecting_a_vote=True):
    """Returns a speaker ID if this looks like a member's vote in a division

    Otherwise returns None.  If it looks like a vote, but the speaker
    can't be identified, this throws an exception.  As an example:

    >>> is_member_vote('Something random...', '2012-11-12')
    >>> is_member_vote('Baillie, Jackie (Dumbarton) (Lab)', '2012-11-12')
    u'uk.org.publicwhip/member/80476'
    >>> is_member_vote('Alexander, Ms Wendy (Paisley North) (Lab)', '2010-05-12')
    u'uk.org.publicwhip/member/80281'
    >>> is_member_vote('Purvis, Jeremy (Tweeddale, Ettrick and Lauderdale)', '2005-05-18')
    u'uk.org.publicwhip/member/80101'

    Now some examples that should be ignored:

    >>> is_member_vote(': SP 440 (EC Ref No 11766/99, COM(99) 473 final)', '1999-11-23')
    >>> is_member_vote('SP 666 (EC Ref No 566 99/0225, COM(99) (CNS))', '2000-02-08')
    >>> is_member_vote('to promote a private bill, the company relied on its general power under section 10(1)(xxxii)', '2006-05-22')

    And one that should throw an exception:

    >>> is_member_vote('Lebowski, Jeffrey (Los Angeles) (The Dude)', '2012-11-12')
    Traceback (most recent call last):
      ...
    Exception: A voting member 'Jeffrey Lebowski (Los Angeles)' couldn't be resolved

    If expecting_a_vote is False, then don't throw an exception if
    the name can't be resolved:

    >>> is_member_vote('Lebowski, Jeffrey (Los Angeles) (The Dude)', '2012-11-12', expecting_a_vote=False)

    Also try resolving names that aren't comma-reversed:

    >>> is_member_vote('Brian Adam (North-East Scotland) (SNP)', '1999-11-09')
    u'uk.org.publicwhip/member/80129'

    """
    tidied = tidy_string(non_tag_data_in(element))

    from_first_and_last = lambda m: m and "%s %s (%s)" % (m.group('first_names'),
                                                          m.group('last_name'),
                                                          m.group('constituency'))

    from_full = lambda m: m and m.group('full_name')
    vote_matches = (
        (member_vote_re, from_first_and_last),
        (member_vote_just_constituency_re, from_first_and_last),
        (member_vote_fullname_re, from_full))

    reformed_name = first(processor(regexp.search(tidied))
                        for regexp, processor in vote_matches)

    if not reformed_name:
        return None

    speaker_id = get_unique_speaker_id(reformed_name, str(vote_date))

    if speaker_id is None and expecting_a_vote:
        print "reformed_name is:", reformed_name
        print "vote_date is:", vote_date
        raise Exception, "A voting member '%s' couldn't be resolved" % (reformed_name,)
    else:
        return speaker_id

def log_speaker(speaker, date, message):
    if SPEAKERS_DEBUG:
        with open("speakers.txt", "a") as fp:
            fp.write(str(date)+": ["+message.encode('utf-8')+"] "+speaker.encode('utf-8')+"\n")

def filename_key(filename):
    m = re.search(r'^(\d+)\.html$', filename)
    if m:
        return int(m.group(1), 10)
    else:
        return 0

def is_page_empty(soup):
    """Return true if there's any text in <div id="ReportView">

    If the page isn't empty, this takes rather a long time, so
    only use this in cases where we've found the title is empty
    already."""
    report_view = soup.find('div', attrs={'id': 'ReportView'})
    return not ''.join(report_view.findAll(text=True)).strip()

def get_title_and_date(soup, page_id):
    """Extract the session and date from a page

    Returns a (session, date) tuple, or if the page should be skipped
    returns (None, None)."""

    title_elements = soup.findAll(attrs={"id" : "ReportView_ReportViewHtml_lblReportTitle"})
    if len(title_elements) > 1:
        raise Exception, "Too many title elements were found"
    elif len(title_elements) == 0:
        raise Exception, "No title elements were found"
    title = title_elements[0].string
    if not title:
        if is_page_empty(soup):
            return (None, None)
        else:
            raise Exception, "No title was found in a page that's non-empty; the page ID was: %d" % (page_id,)
    m = re.search(r'^(.*)\s+(\d{2} \w+ \d{4})$', title)
    if m:
        session = m.group(1).rstrip(',')
        report_date = dateparser.parse(m.group(2)).date()
        return (session, report_date)
    else:
        raise Exception, "Failed to parse the title and date from: {}".format(title)

acceptable_elements = ['a', 'abbr', 'acronym', 'address', 'area', 'b',
      'big', 'blockquote', 'body', 'br', 'button', 'caption', 'center',
      'cite', 'code', 'col', 'colgroup', 'dd', 'del', 'dfn', 'dir', 'div',
      'dl', 'dt', 'em', 'font', 'form', 'head', 'h1', 'h2', 'h3', 'h4',
      'h5', 'h6', 'hr', 'html', 'i', 'img', 'input', 'ins', 'kbd', 'label',
      'legend', 'li', 'link', 'map', 'menu', 'meta', 'noscript' 'ol',
      'p', 'pre', 'q', 's', 'samp', 'script', 'small', 'span', 'strike',
      'strong', 'style', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot',
      'th', 'thead', 'title', 'tr', 'tt', 'u', 'ul', 'var', 'form', 'body']

def replace_unknown_tags(html):
    """Replace any tags that aren't in a whitelist with their escaped versions

    The HTML from the Scottish Parliament is broken in that it
    sometimes uses unescaped angle brackets for quoting, for example
    in:

    <br/>The purpose of the raft of amendments is simple and can be
    expressed in the words of amendment 32, which simply
    says:<br/><br/>"leave out <Scottish Ministers> and insert
    <tribunal>".<br/>

    So, this replaces any unknown elements in the HTML with an escaped
    version.  Note that we can't do this easily in BeautifulSoup,
    since it will add (e.g.) an end tag for <tribunal>, and we can't
    tell after parsing if that were real, or part of a fixup.

    >>> example_html = '''<h3 foo="bar" >Hello!</h3 ><p>Here's some <stupid> <strong
    ... class="whatever">HTML</strong> just to annoy us.  And <some
    ... more> before closing the paragraph.</p>'''
    >>> print replace_unknown_tags(example_html)
    <h3 foo="bar" >Hello!</h3 ><p>Here's some &lt;stupid&gt; <strong
    class="whatever">HTML</strong> just to annoy us.  And &lt;some
    more&gt; before closing the paragraph.</p>

    """
    def replace_tag(match):
        tag_name = match.group(2).lower()
        if tag_name in acceptable_elements:
            return match.group(0)
        else:
            return escape(match.group(0))

    return re.sub(r'(?ims)(</?)(\w+)([^>]*/?>)', replace_tag, html)

def fix_inserted_br_in_vote_list(html):
    """Fix a common error in the vote lists of divisions

    >>> example_html = '''<br/>Robson, Euan (Roxburgh and Berwickshire)
    ... (LD)<br/>Rumbles, Mr Mike (West Aberdeenshire and
    ... Kincardine)<br/>(LD)<br/>Russell, Michael (South of Scotland) (SNP)'''
    >>> print fix_inserted_br_in_vote_list(example_html)
    <br/>Robson, Euan (Roxburgh and Berwickshire)
    (LD)<br/>Rumbles, Mr Mike (West Aberdeenshire and
    Kincardine) (LD)<br/>Russell, Michael (South of Scotland) (SNP)
    """
    return re.sub(r'(\))<br/>(\((LD|Lab)\)<br/>)', '\\1 \\2', html)

class ParsedPage(object):

    def __init__(self, session, report_date, page_id):
        self.session = session
        self.report_date = report_date
        self.page_id = page_id
        self.sections = []

    def __unicode__(self):
        return unicode(self.report_date) + u": " + self.session

    @property
    def normalized_session_name(self):
        s = re.sub(r'\s+', '-', self.session)
        return re.sub(r'[^-\w]', '', s).lower()

    @property
    def suggested_file_name(self):
        return "%s/%s_%d.xml" % (self.normalized_session_name, self.report_date, self.page_id)

    def as_xml(self):
        base_id = "uk.org.publicwhip/spor/"
        if self.normalized_session_name not in ('plenary', 'meeting-of-the-parliament'):
            base_id += self.normalized_session_name + "/"
        base_id += str(self.report_date)
        xml = etree.Element("publicwhip")
        for section_index, section in enumerate(self.sections):
            section_base_id = base_id + "." + str(section_index)
            for section_element in section.as_xml(section_base_id):
                xml.append(section_element)
        return xml

    def tidy_speeches(self):
        for section in self.sections:
            section.tidy_speeches()

class Section(object):

    def __init__(self, title, url):
        self.title = title
        self.speeches_and_votes = []
        self.url = url

    def as_xml(self, section_base_id):
        heading_element = etree.Element("major-heading",
                                        url=self.url,
                                        nospeaker="True",
                                        id=section_base_id + ".0")
        heading_element.text = self.title
        result = [heading_element]
        for i, speech_or_vote in enumerate(self.speeches_and_votes, 1):
            result.append(speech_or_vote.as_xml(section_base_id + "." + str(i)))
        return result

    @staticmethod
    def group_by_key(speech_or_division):
        if isinstance(speech_or_division, Division):
            return "division/%d" % id(speech_or_division)
        elif isinstance(speech_or_division, Speech):
            s = speech_or_division
            return s.speaker_id or s.speaker_name or "nospeaker"
        else:
            raise Exception, "Unknown type %s passed to group_by_key" % (type(speech_or_division),)

    def tidy_speeches(self):
        # First remove any empty speeches:
        self.speeches_and_votes = [sv for sv in
                                   self.speeches_and_votes
                                   if not sv.empty()]
        collapsed = []
        grouped = itertools.groupby(self.speeches_and_votes, Section.group_by_key)
        for key, sv_grouper in grouped:
            sv_group = list(sv_grouper)
            if len(sv_group) == 1:
                collapsed.append(sv_group[0])
            else:
                new_speech = sv_group[0]
                for speech_to_add in sv_group[1:]:
                    new_speech.paragraphs += speech_to_add.paragraphs
                collapsed.append(new_speech)
        self.speeches_and_votes = collapsed

class Division(object):

    def __init__(self, report_date, url, divnumber, candidate=None, candidate_id=None):
        self.report_date = report_date
        self.url = url
        self.divnumber = divnumber
        self.votes = {}
        self.candidate = candidate
        self.candidate_id = candidate_id
        for way in DIVISION_HEADINGS:
            self.votes[way] = []

    def empty(self):
        total_votes = 0
        for way in DIVISION_HEADINGS:
            total_votes += len(self.votes[way])
        return total_votes == 0

    def add_vote(self, which_way, voter_name, voter_id):
        if which_way not in DIVISION_HEADINGS:
            raise Exception, "add_votes for unknown way: " + str(which_way)
        self.votes[which_way].append((voter_name, voter_id))

    def as_xml(self, division_id):
        attributes = {'url': self.url,
                      'divdate': str(self.report_date),
                      'nospeaker': "True",
                      'divnumber': str(self.divnumber),
                      'id': division_id}
        if self.candidate:
            attributes['candidate'] = self.candidate
        if self.candidate_id:
            attributes['candidate_id'] = self.candidate_id
        result = etree.Element("division", **attributes)
        def to_attr(s):
            return s.lower().replace(' ', '')
        division_count = etree.Element("divisioncount")
        for way in DIVISION_HEADINGS:
            attribute = to_attr(way)
            count = len(self.votes[way])
            division_count.set(attribute, str(count))
        result.append(division_count)
        for way in DIVISION_HEADINGS:
            attribute_value = to_attr(way)
            msp_list = etree.Element('msplist',
                                     vote=attribute_value)
            for voter_name, voter_id in self.votes[way]:
                msp_name = etree.Element('mspname',
                                         id=voter_id,
                                         vote=attribute_value)
                msp_name.text = voter_name
                msp_list.append(msp_name)
            result.append(msp_list)
        return result

class Speech(object):

    def __init__(self, speaker_name, speech_date, last_time, url):
        self.speaker_name = speaker_name
        self.speech_date = speech_date
        self.last_time = last_time
        self.url = url
        self.paragraphs = []
        self.speaker_id = None
        if self.speaker_name:
            self.update_speaker_id(speaker_name)

    def empty(self):
        return 0 == len(self.paragraphs)

    def update_speaker_id(self, tidied_speaker):
        final_id = get_unique_speaker_id(tidied_speaker, self.speech_date)
        self.speaker_id = final_id
        self.speaker_name = tidied_speaker

    speakers_so_far = []

    @classmethod
    def reset_speakers_so_far(cls):
        cls.speakers_so_far = []

    def as_xml(self, speech_id):
        attributes = {'url': self.url,
                      'id': speech_id}
        if self.speaker_name:
            attributes['speakername'] = self.speaker_name
            if self.speaker_id:
                attributes['speakerid'] = self.speaker_id
            else:
                attributes['speakerid'] = 'unknown'
        else:
            attributes['nospeaker'] = 'true'
        result = etree.Element("speech", **attributes)
        for i, paragraph in enumerate(self.paragraphs):
            p = etree.Element('p')
            p.text = paragraph
            result.append(p)
        return result

def quick_parse_html(filename, page_id, original_url):
    with open(filename) as fp:
        html = fp.read()
    html = replace_unknown_tags(html)
    html = fix_inserted_br_in_vote_list(html)
    soup = BeautifulSoup(html, convertEntities=BeautifulSoup.HTML_ENTITIES)
    # If this is an error page, there'll be a message like:
    #   <span id="ReportView_lblError">Please check the link you clicked, as it does not reference a valid Official Report</span>
    # ... so ignore those.
    error = soup.find('span', attrs={'id': 'ReportView_lblError'})
    if error and error.string and 'Please check the link' in error.string:
        return (None, None, None)
    session, report_date = get_title_and_date(soup, page_id)
    if session is None:
        # Then this was an empty page, which should be skipped
        return (None, None, None)
    return (session, report_date, soup)

def parse_html(session, report_date, soup, page_id, original_url):
    divnumber = 0
    report_view = soup.find('div', attrs={'id': 'ReportView'})
    div_children_of_report_view = report_view.findChildren('div', recursive=False)
    if len(div_children_of_report_view) != 1:
        raise Exception, 'We only expect one <div> child of <div id="ReportView">; there were %d in page with ID %d' % (len(div_children_of_report_view), page_id)

    Speech.reset_speakers_so_far()

    main_div = div_children_of_report_view[0]

    top_level_divs = main_div.findChildren('div', recursive=False)

    # The first div should just contain links to sections further down
    # the page:

    contents_div, text_div = top_level_divs

    # Just check that my assumption that the first div only contains
    # links is correct:

    contents_tuples = []

    contents_links = contents_div.findAll(True)
    for link in contents_links:
        if link.name == 'br':
            continue
        if link.name != 'a':
            raise Exception, "There was something other than a <br> or an <a> in the supposed contents <div>, for page ID: %d" % (page_id,)
        href = link['href']
        m = re.search(r'#(.*)', href)
        if not m:
            raise Exception, "Failed to find the ID from '%s' in page with ID: %d" % (href, page_id)
        contents_tuples.append((m.group(1), tidy_string(non_tag_data_in(link))))

    parsed_page = ParsedPage(session, report_date, page_id)

    # Now consider the div that actually has text in it.  Each speech
    # is in its own div, while the rest that we care about are
    # headings:

    current_votes = None
    current_division_way = None
    current_time = None
    current_url = original_url

    for top_level in text_div:
        # There are sometimes some empty NavigableString elements at
        # the top level, so just ignore those:
        if not len(unicode(top_level).strip()):
            continue
        if top_level.name == 'h2':
            section_title = tidy_string(non_tag_data_in(top_level, tag_replacement=u' '))
            if not section_title:
                raise Exception, "There was an empty section title in page ID: %d" % (page_id)
            parsed_page.sections.append(
                Section(section_title, current_url))
        elif top_level.name in ('br',):
            # Ignore line breaks - we use paragraphs instead
            continue
        elif top_level.name == 'a':
            try:
                current_url = original_url + "#" + top_level['id']
            except KeyError:
                pass
        elif top_level.name == 'div':
            # This div contains a speech, essentially:

            for speech_part in top_level:
                if hasattr(speech_part, 'name'):
                    if speech_part.name == 'b':
                        speaker_name = non_tag_data_in(speech_part)
                        # If there's a training colon, remove that (and any whitespace)
                        speaker_name = re.sub(r'[\s:]*$', '', speaker_name)
                        current_speech = Speech(tidy_string(speaker_name),
                                                report_date,
                                                current_time,
                                                current_url)
                        parsed_page.sections[-1].speeches_and_votes.append(current_speech)
                    elif speech_part.name == 'br':
                        # Ignore the line breaks...
                        pass
                    else:
                        raise Exception, "Unexpected tag '%s' in page ID: %d" % (speech_part.name, page_id)
                elif isinstance(speech_part, NavigableString):
                    tidied_paragraph = tidy_string(speech_part)
                    # print "tidied_paragraph is", tidied_paragraph.encode('utf-8'), "of type", type(tidied_paragraph)
                    division_way, division_candidate, division_candidate_id = is_division_way(tidied_paragraph, report_date)
                    member_vote = is_member_vote(tidied_paragraph, report_date, expecting_a_vote=current_votes)
                    maybe_time = just_time(tidied_paragraph)
                    closed_time = meeting_closed(tidied_paragraph)
                    if closed_time:
                        current_time = closed_time
                    suspended_time_tuple = meeting_suspended(tidied_paragraph)
                    if suspended_time_tuple:
                        suspended, suspension_time_type, suspension_time = suspended_time_tuple
                    else:
                        suspended = False
                        suspension_time_type = suspension_time = None
                    if division_way:
                        # If this is a vote for a particular
                        # candidate, or the introduction to an
                        # oath-taking, add the text as a speech too:
                        if division_candidate:
                            current_speech = Speech(None,
                                                    report_date,
                                                    current_time,
                                                    current_url)
                            parsed_page.sections[-1].speeches_and_votes.append(current_speech)
                            current_speech.paragraphs.append(tidied_paragraph)
                        if (not current_votes) or (current_votes.candidate != division_candidate):
                            current_votes = Division(report_date, current_url, divnumber, division_candidate, division_candidate_id)
                            divnumber += 1
                            parsed_page.sections[-1].speeches_and_votes.append(current_votes)
                        current_division_way = division_way
                    elif member_vote:
                        if current_votes is None:
                            raise Exception, "Got a member's vote before an indication of which way the vote is"
                        current_votes.add_vote(current_division_way, tidied_paragraph, member_vote)
                    elif maybe_time:
                        current_time = maybe_time
                    else:
                        if current_votes:
                            current_votes = None
                        # If this speech doesn't have any paragraphs
                        # yet, make sure that it has the current time,
                        # so that (for example) if we get a "Meeting
                        # closed at 17:44." at the end, that speech
                        # ends up with that time.
                        if len(current_speech.paragraphs) == 0:
                            current_speech.last_time = current_time
                        current_speech.paragraphs.append(tidied_paragraph)
                    if suspended and suspension_time:
                        current_time = suspension_time
                else:
                    raise Exception, "Totally unparsed element:\n%s\n... unhandled in page ID: %d" % (speech_part, page_id)

        else:
            raise Exception, "There was an unhandled element '%s' in page with ID: %d" % (top_level.name, page_id)

    return parsed_page

SPEAKERS_DEBUG = False

if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option('-f', '--force', dest='force', action="store_true",
                      help='force reparse of everything')
    parser.add_option("--test", dest="doctest",
                      default=False, action='store_true',
                      help="Run all doctests in this file")
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      default=False, help="produce very verbose output")
    parser.add_option('--speakers-debug', dest='speakers_debug', action='store_true',
                      default=False, help="log speakers that couldn't be found")
    parser.add_option('--from', dest='from_date',
                      default="1999-05-12",
                      help="only parse files from this date onwards (inclusive)")
    parser.add_option('--to', dest='to_date',
                      default=str(datetime.date.today()),
                      help="only parse files up to this date (inclusive)")
    (options, args) = parser.parse_args()

    if options.doctest:
        import doctest
        failure_count, test_count = doctest.testmod()
        sys.exit(0 if failure_count == 0 else 1)

    SPEAKERS_DEBUG = options.speakers_debug

    from_date = dateparser.parse(options.from_date).date()
    to_date = dateparser.parse(options.to_date).date()

    html_directory = "../../../parldata/cmpages/sp/official-reports-new/"
    xml_output_directory = "../../../parldata/scrapedxml/sp-new/"

    for filename in sorted(os.listdir(html_directory), key=filename_key):
        html_filename = os.path.join(html_directory, filename)

        # By default, don't consider files that have an mtime earlier
        # than 10 days before from_date.  There are cases where this
        # won't work properly, but will save lots of time in the
        # typical case.
        if not options.force:
            earliest_to_consider = datetime.datetime.combine(from_date,
                                                             datetime.time())
            earliest_to_consider -= datetime.timedelta(days=10)

            last_modified = datetime.datetime.fromtimestamp(os.path.getmtime(html_filename))
            if last_modified < earliest_to_consider:
                if options.verbose:
                    print "Skipping", html_filename, "(it's well before %s)" % (from_date,)
                continue

        m = re.search(r'^(\d+)\.html$', filename)
        if not m:
            if options.verbose:
                print "Skipping", html_filename, "(wrong filename format)"
            continue
        page_id = int(m.group(1), 10)
        # if page_id < 8098:
        #     continue
        print "got filename", filename
        parsed_page = None
        try:
            if os.path.getsize(html_filename) == 0:
                if options.verbose:
                    print "Skipping", html_filename, "(empty)"
                continue
            official_url = official_report_url_format.format(page_id)
            # Do a quick parse of the page first, to extract the date
            # so we know whether to bother with it:
            session, report_date, soup = quick_parse_html(html_filename,
                                                          page_id,
                                                          official_url)
            if session is None:
                if options.verbose:
                    print "Skipping", html_filename, "(not useful after parsing)"
                continue
            if report_date < from_date or report_date > to_date:
                if options.verbose:
                    print "Skipping", html_filename, "(outside requested date range)"
                continue
            parsed_page = parse_html(session,
                                     report_date,
                                     soup,
                                     page_id,
                                     official_url)
        except Exception as e:
            # print "parsing the file '%s' failed, with the exception:" % (filename,)
            # print unicode(e).encode('utf-8')
            # traceback.print_exc()
            print "parsing the file '%s' failed" % (filename,)
            raise

        if parsed_page is None:
            if options.verbose:
                print "Skipping", html_filename, "(outside requested date range)"
        else:
            if options.verbose:
                print "Parsed", html_filename

            parsed_page.tidy_speeches()

            if options.verbose:
                print "  suggested output filename is:", parsed_page.suggested_file_name
            output_filename = os.path.join(xml_output_directory,
                                           parsed_page.suggested_file_name)
            output_directory, output_leafname = os.path.split(output_filename)
            # Ensure that the directory exists:
            try:
                output_directory = os.path.dirname(output_filename)
                os.mkdir(output_directory)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

            xml = etree.tostring(parsed_page.as_xml(), pretty_print=True)
            with NamedTemporaryFile(delete=False,
                                    dir=xml_output_directory) as ntf:
                ntf.write(xml)

            changed_output = True
            if os.path.exists(output_filename):
                if 0 == os.system("diff %s %s > /dev/null" % (ntf.name,output_filename)):
                    changed_output = False

            if changed_output:
                os.rename(ntf.name, output_filename)
                changedates_filename = os.path.join(xml_output_directory,
                                                     output_directory,
                                                     'changedates.txt')
                with open(changedates_filename, 'a+') as fp:
                    fp.write('%d,%s\n' % (time.time(),
                                          output_leafname))
            else:
                if options.verbose:
                    print "  not writing, since output is unchanged"
                os.remove(ntf.name)
