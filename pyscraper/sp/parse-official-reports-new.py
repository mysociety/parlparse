#!/usr/bin/env python

# Notes on things still to fix:
#    4161 (the old one was: parldata/scrapedxml/spsp1999-05-13.xml
#    4163
#      Need to look for VOTES FOR <candidate> and create a new division
#      with the candidate attribute set.


from cgi import escape
import sys
import os
import re
import random
import datetime
import time
import dateutil.parser as dateparser
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

def is_division_way(element):
    """If it's a division heading, return a normalized version, otherwise None

    >>> is_division_way('  For ')
    'FOR'
    >>> is_division_way('nonsense')
    >>> is_division_way('abstentions ')
    'ABSTENTIONS'
    >>> is_division_way(":\xA0FOR")
    'FOR'
    >>> is_division_way('Abstention')
    'ABSTENTIONS'
    """
    tidied = tidy_string(non_tag_data_in(element)).upper()
    # Strip any non-word letters at the start and end:
    tidied = re.sub(r'^\W*(.*?)\W*$', '\\1', tidied)
    if tidied in DIVISION_HEADINGS:
        return tidied
    elif tidied == 'ABSTENTION':
        return 'ABSTENTIONS'
    else:
        return None

member_vote_re = re.compile('''
        ^                              # Beginning of the string
        (?P<last_name>[^,\(\)0-9]+)    # ... last name, >= 1 non-comma characters
        ,                              # ... then a comma
        \s*                            # ... and some greedy whitespace
        (?P<first_names>[^,\(\)0-9]*?) # ... first names, a minimal match of any characters
        \s*\(\(?                       # ... an arbitrary amout of whitespace and an open banana
                                       #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9]*?) # ... constituency, a minimal match of any characters
        \)\s*\(                        # ... close banana, whitespace, open banana
        (?P<party>\D*?)                # ... party, a minimal match of any characters
        \)                             # ... close banana
        $                              # ... end of the string
''', re.VERBOSE)

member_vote_just_constituency_re = re.compile('''
        ^                              # Beginning of the string
        (?P<last_name>[^,\(\)0-9]+)    # ... last name, >= 1 non-comma characters
        ,                              # ... then a comma
        \s*                            # ... and some greedy whitespace
        (?P<first_names>[^,\(\)0-9]*?) # ... first names, a minimal match of any characters
        \s*\(\(?                       # ... an arbitrary amout of whitespace and an open banana
                                       #     (with possibly an extra open banana)
        (?P<constituency>[^\(\)0-9]*?) # ... constituency, a minimal match of any characters
        \)\s*                          # ... close banana, whitespace
        $                              # ... end of the string
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

def is_member_vote(element, vote_date):
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
    """
    tidied = tidy_string(non_tag_data_in(element))
    m = member_vote_re.search(tidied) or member_vote_just_constituency_re.search(tidied)
    if m:
        reformed_name = "%s %s (%s)" % (m.group('first_names'),
                                        m.group('last_name'),
                                        m.group('constituency'))
        speaker_id = get_unique_speaker_id(reformed_name, str(vote_date))
        if speaker_id is None:
            print "reformed_name is:", reformed_name
            print "vote_date is:", vote_date
            raise Exception, "A voting member '%s' couldn't be resolved" % (reformed_name,)
        else:
            return speaker_id
    else:
        return None

def log_speaker(speaker, date, message):
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

class ParsedPage(object):

    def __init__(self, session, report_date):
        self.session = session
        self.report_date = report_date
        self.sections = []

    def __unicode__(self):
        return unicode(self.report_date) + u": " + self.session

    @property
    def normalized_session_name(self):
        s = re.sub(r'\s+', '-', self.session)
        return re.sub(r'[^-\w]', '', s).lower()

    @property
    def suggested_file_name(self):
        return "%s-%s.xml" % (self.report_date, self.normalized_session_name)

    def as_xml(self):
        base_id = "uk.org.publicwhip/spor2/" + str(self.report_date)
        xml = etree.Element("publicwhip")
        for section_index, section in enumerate(self.sections):
            section_base_id = base_id + "." + str(section_index)
            for section_element in section.as_xml(section_base_id):
                xml.append(section_element)
        return xml

class Section(object):

    def __init__(self, title, url):
        self.title = title
        self.speeches_and_votes = []
        self.url = url

    def as_xml(self, section_base_id):
        result = [etree.Element("major-heading",
                                url=self.url,
                                nospeaker="True",
                                id=section_base_id + ".0")]
        for i, speech_or_vote in enumerate(self.speeches_and_votes, 1):
            result.append(speech_or_vote.as_xml(section_base_id + "." + str(i)))
        return result

class Division(object):

    def __init__(self, report_date, url):
        self.report_date = report_date
        self.url = url
        self.votes = {}
        for way in DIVISION_HEADINGS:
            self.votes[way] = []

    def add_vote(self, which_way, voter_name, voter_id):
        if which_way not in DIVISION_HEADINGS:
            raise Exception, "add_votes for unknown way: " + which_way
        self.votes[which_way].append((voter_name, voter_id))

    def as_xml(self, division_id):
        result = etree.Element("division",
                               url=self.url,
                               divdate=str(self.report_date),
                               nospeaker="True",
                               id=division_id)
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
        self.update_speaker_id(speaker_name)
        self.speaker_id = None

    def update_speaker_id(self, tidied_speaker):
        final_id = get_unique_speaker_id(tidied_speaker, self.speech_date)
        self.speaker_id = final_id
        self.speaker_name = tidied_speaker

    speakers_so_far = []

    @classmethod
    def reset_speakers_so_far(cls):
        cls.speakers_so_far = []

    def as_xml(self, speech_id):
        result = etree.Element("speech",
                               url=self.url,
                               speakername=self.speaker_name,
                               id=speech_id)
        if self.speaker_id:
            result.set('speakerid', self.speaker_id)
        else:
            result.set('speakerid', 'unknown')
        for i, paragraph in enumerate(self.paragraphs):
            p = etree.Element('p')
            p.text = paragraph
            result.append(p)
        return result
    
def parse_html(filename, page_id, original_url):
    with open(filename) as fp:
        html = fp.read()
    html_with_fixed_tags = replace_unknown_tags(html)
    soup = BeautifulSoup(html_with_fixed_tags, convertEntities=BeautifulSoup.HTML_ENTITIES)
    # If this is an error page, there'll be a message like:
    #   <span id="ReportView_lblError">Please check the link you clicked, as it does not reference a valid Official Report</span>
    # ... so ignore those.
    error = soup.find('span', attrs={'id': 'ReportView_lblError'})
    if error and error.string and 'Please check the link' in error.string:
        return
    session, report_date = get_title_and_date(soup, page_id)
    if session is None:
        # Then this was an empty page, which should be skipped
        return None

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

    parsed_page = ParsedPage(session, report_date)

    # Now consider the div that actually has text in it.  Each speech
    # is in its own div, while the rest that we care about are
    # headings:

    current_time = None
    current_url = original_url

    for top_level in text_div:
        # There are sometimes some empty NavigableString elements at
        # the top level, so just ignore those:
        if not len(unicode(top_level).strip()):
            continue
        if top_level.name == 'h2':
            section_title = tidy_string(non_tag_data_in(top_level))
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
            current_speech = None
            current_votes = None
            current_division_way = None

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
                # FIXME: could just be else, surely...
                elif isinstance(speech_part, NavigableString):
                    tidied_paragraph = tidy_string(speech_part)
                    # print "tidied_paragraph is", tidied_paragraph, "of type", type(tidied_paragraph)
                    division_way = is_division_way(tidied_paragraph)
                    member_vote = is_member_vote(tidied_paragraph, report_date)
                    maybe_time = just_time(tidied_paragraph)
                    closed_time = meeting_closed(tidied_paragraph)
                    if closed_time:
                        current_time = closed_time
                    suspended_time = meeting_suspended(tidied_paragraph)
                    if division_way:
                        if not current_votes:
                            current_votes = Division(report_date, current_url)
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
                    if suspended_time:
                        current_time = suspended_time
                else:
                    raise Exception, "Totally unparsed element:\n%s\n... unhandled in page ID: %d" % (speech_part, page_id)

        else:
            raise Exception, "There was an unhandled element '%s' in page with ID: %d" % (top_level.name, page_id)

    return parsed_page

if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option('-f', '--force', dest='force', action="store_true",
                      help='force reparse of everything')
    parser.add_option("--test", dest="doctest",
                      default=False, action='store_true',
                      help="Run all doctests in this file")
    parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                      default=False, help="produce very verbose output")
    (options, args) = parser.parse_args()

    if options.doctest:
        import doctest
        failure_count, test_count = doctest.testmod()
        sys.exit(0 if failure_count == 0 else 1)

    html_directory = "../../../parldata/cmpages/sp/official-reports-new/"
    xml_output_directory = "../../../parldata/scrapedxml/sp-new/"

    for filename in sorted(os.listdir(html_directory), key=filename_key):
        m = re.search(r'^(\d+)\.html$', filename)
        if not m:
            continue
        page_id = int(m.group(1), 10)
        # if page_id < 5548:
        if page_id < 5591:
            continue
        print "got filename", filename
        parsed_page = parse_html(os.path.join(html_directory, filename),
                                 page_id,
                                 official_report_url_format.format(page_id))

        if parsed_page is not None:
            print "suggested name would be:", parsed_page.suggested_file_name

        continue

        # print "parsed to:", etree.tostring(parsed_page.as_xml(), pretty_print=True)

        # if changed_output:
        if True:
            with  open('%schangedates.txt' % xml_output_directory, 'a+') as fp:
                fp.write('%d,sp%s.xml\n' % (time.time(), str(parsed_page.report_date)))

        break
