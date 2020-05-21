#!/usr/bin/python

import re
import xml.dom.minidom
import time
import datetime
from dateutil.relativedelta import relativedelta
import dateutil.parser
import sys
import os
import glob
from optparse import OptionParser
from subprocess import call
import codecs

sys.path.append('../')
from resolvemembernames import memberList
from lords.resolvenames import lordsList
from contextexception import ContextException
from BeautifulSoup import BeautifulSoup, NavigableString, Comment, Tag

from future_business import *

dom_impl = xml.dom.minidom.getDOMImplementation()

"""This script parses the scraped HTML from the Future Business and
the Calendar and outputs XML that represents the same data.

The Future Business sections seems to divide into those sections that
have headings with class "paraFutureBusinessDate" for each day
(Sections A, B, D and F) and two which are a little different
(Sections C and E).

The Calendar pages have a table with two columns, the first of which
has start times or time ranges.  The second column has details of the
business - the committee pages have a slightly different format from
the other ones.

"""

current_file_scraped_date = None
verbose = False

def add_member_id_attribute(item,speakername,date,id_attribute='speakerid'):
    """'item' should be an XML DOM element.  'speakername' should be
    the full name of a representative, e.g. "Mr Andrew Dismore".
    'date' may be None, but for better results should be an ISO-6301
    date string, e.g. "2010-01-01".  If 'speakername' and 'date'
    resolve to a unique member ID, this will be set as an attribute in
    'item' with name 'speakerid'.  If there are no matches, the
    'speakerid' attribute will be set to be 'unknown'.  If there are
    multiple matches, a ContentException will be thrown."""

    speakername = re.sub('^Secretary *','',speakername)

    used_scraped_date = ""

    string_date = None
    if date:
        string_date = str(date)
    else:
        # If we don't have a date specified, use the date on which the
        # page was scraped, since not specifying a date is very likely
        # to produce an ambiguous answer:
        string_date = current_file_scraped_date
        used_scraped_date = " (used date of scraping)"

    id_set = memberList.fullnametoids(speakername,string_date)
    if not id_set:
        try:
            id_set = [ lordsList.GetLordIDfname(speakername, '', string_date) ]
        except ContextException:
            pass

    if len(id_set) == 1:
        item.setAttribute(id_attribute,list(id_set)[0])
    elif len(id_set) == 0:
        if verbose: print >> sys.stderr, (u"Warning: No match for '%s' on date '%s' %s" % (speakername,string_date,used_scraped_date)).encode("utf-8")
        item.setAttribute(id_attribute,'unknown')
    else:
        # This is rare - warn and output speakerid="ambiguous":
        if verbose: print >> sys.stderr, (u"Got multiple IDs for '%s' on date '%s'%s; they were: %s" % (speakername,string_date,used_scraped_date,str(id_set)))
        item.setAttribute(id_attribute,'ambiguous')

# FIXME: use the common version of this eventually:
def non_tag_data_in(o):
    """Take a BeautifulSoup element, typically a Tag, and return the
    text parts it contains, concatenated into a single string"""

    if o.__class__ == NavigableString:
        return re.sub('(?ms)[\r\n]',' ',o)
    elif o.__class__ == Tag:
        if o.name == 'script':
            return ''
        else:
            return ''.join( map( lambda x: non_tag_data_in(x) , o.contents ) )
    elif o.__class__ == Comment:
        return ''
    else:
        # Hope it's a string or something else concatenatable...
        return o

def tidied_non_tag_data_in(o):
    """Take a BeautifulSoup element, typically a Tag, and return the
    text parts it contains, concatenated into a single string, but
    remove and leading and trailing whitespace, and collapse any
    whitespace within the string into a single space"""

    return ' '.join(non_tag_data_in(o).strip().split())

def has_class_attribute(tag):
    """Return True if the tag has a class attribute, False otherwise."""

    for t in tag.attrs:
        if t[0] == 'class':
            return True
    return False

def assert_empty(tag):
    """This method will raise an exception if 'tag' has non-whitespace text beneath it."""

    if len(non_tag_data_in(tag).strip()) > 0:
        raise Exception, "Was going to ignore a tag, but it's non-empty:\n"+tag.prettify()

def get_string_contents(soup_element, recursive=False):
    """Takes a soup element and returns those strings which can be found beneath
    this node stripped, and then joined together.

    If the optional argument 'recursive' is True, then all strings beneath
    the current element are included, otherwise, just strings which are
    direct subnodes of 'soup_element' are included.
    """

    return u''.join([x for x in soup_element.findAll(text=True, recursive=recursive)]).strip()

def get_contents_and_lords(soup_item):
    """
    Takes a soup item (which is expected to be either a normal business_item,
    or a private members bill). Both these types of item can contain a span
    which indicates that the bill was introduced in the lords.

    Return a tuple of the text contained in the item, and True/False for whether
    it was introduced in the Lords.

    This function really should be somewhere in the object hierarchy below.
    """
    # We're going to assume there are no tags in there except the one span, and allow
    # things to go wrong otherwise.
    lords = False
    petitioner = None
    span_tag = soup_item.find('span')
    if span_tag:
        if span_tag.string.strip().upper() == u'LORDS':
            # This bill was introduced in the lords - let's note that
            lords = True
        elif ('class','charQueensConsent') in span_tag.attrs:
            # FIXME: just ignoring this for the moment, but maybe shouldn't...
            pass
        elif ('class','Italic') in span_tag.attrs:
            petitioner = tidied_non_tag_data_in(span_tag)
        else:
            raise ValueError('What are we doing here? span found with the following contents: %s' %soup_item.span)

    # There is some random whitespace in some of these items.
    # It doesn't look useful, so let's replace it with spaces.
    text = tidied_non_tag_data_in(soup_item)

    return (text, lords, petitioner)

# Regex for dealing with Ten minute Rule Motions. We'll make it ignore case,
# in case the parliament site aren't consistent on the first bit.
ten_minute_rule_re = re.compile("Ten minute Rule Motion: ([^:]*): (.*)", re.I)

# The text this regular expression is intended to deal with looks like:
# u"Ten minute Rule Motion: Mr Paul Burstow: Statutory Instruments Act 1946 (Amendment): That leave be given to bring in a Bill to amend the Statutory Instruments Act 1946."

class FutureBusinessListItem(object):
    """Class used to build up the contents of a future business list item.
    These items come in three basic forms: with just text content;
    containing a ten minute rule motion; and introducing private members' bills.
    """

    # If the business item represent a private members' bill collection,
    # this attribute will contain an item representing that.
    business_item_table = None

    # Notes whether or not the item was introduced in the lords.
    lords = False

    def __init__(self, soup, id, date):
        """Instantiate this object by passing in a soup item of a business
        item, and an id which will be used as the 'id' attribute in the
        xml version.
        Sets the title of the item, and whether the item was introduced in the lords.
        """
        self.id = id
        self.date = date
        self.diamond = False

        self.business_item_title = None
        self.lords = None
        self.petitioner = None
        self.tmr_match = None

        if soup:
            if soup.find('img',{'class':'diamond'}):
                self.diamond = True
            self.business_item_title, self.lords, self.petitioner = get_contents_and_lords(soup)

            # Is this a ten minute rule bill? If so, let's split out the member
            # and the motion. Otherwise, we just want to have a text element
            # containing the title of the business item.

            self.tmr_match = ten_minute_rule_re.match(self.business_item_title)

    def feed_pmbs(self, pmb_soup):
        """This is used if a collection of private members' bills is associated
        with this item. Pass in the soup item of the pmb table, and it will be
        parsed and added to this business item object."""
        self.business_item_table = BusinessItemTable(pmb_soup, self.id, self.date)

    def get_dom(self, document):
        item = document.createElement('business-item')
        item.setAttribute('id', self.id)

        if self.lords:
            item.setAttribute('lords', 'yes')

        if self.petitioner:
            item.setAttribute('petitionername',self.petitioner)
            add_member_id_attribute(item,self.petitioner,self.date,id_attribute='petitionerid')

        if self.tmr_match:
            item.setAttribute('ten_minute_rule', 'yes')

            groups = self.tmr_match.groups()
            item.setAttribute('speakername', groups[0])
            add_member_id_attribute(item,groups[0],self.date)

            motion = document.createElement('motion')
            motion.appendChild(document.createTextNode(groups[1]))
            item.appendChild(motion)

        else:
            if self.business_item_title:
                title = document.createElement('title')
                title.appendChild(document.createTextNode(self.business_item_title))
                item.appendChild(title)

            if self.business_item_table:
                for bit_item in self.business_item_table.all_items:
                    dom_item = bit_item.get_dom(document)
                    item.appendChild(dom_item)

        return item

class AdjourmentDebate(object):
    """A class that represents an adjournment debate in Westminster
    Hall, as found in Future Business part B"""

    def __init__(self, date, start_and_end_time, proposer, subject):
        times_text = non_tag_data_in(start_and_end_time)
        m = re.search('(?ims)((\d+).(\d+)\s+(am|pm))\s+\-\s+((\d+).(\d+)\s+(am|pm))',times_text)
        format = '%I.%M %p'
        start_time_text = m.group(2)+'.'+m.group(3)+' '+m.group(4)
        end_time_text = m.group(6)+'.'+m.group(7)+' '+m.group(8)
        start_time_tuple = time.strptime(start_time_text,format)
        end_time_tuple = time.strptime(end_time_text,format)
        self.start_datetime = datetime.datetime(date.year,date.month,date.day,
                                                start_time_tuple[3],
                                                start_time_tuple[4],
                                                start_time_tuple[5])
        self.end_datetime = datetime.datetime(date.year,date.month,date.day,
                                              end_time_tuple[3],
                                              end_time_tuple[4],
                                              end_time_tuple[5])
        self.proposer = non_tag_data_in(proposer).strip()
        self.subject = non_tag_data_in(subject).strip()

    def get_dom(self,document):
        item = document.createElement('whall-adjournment-debate')
        item.setAttribute('start-time', str(self.start_datetime.time()))
        item.setAttribute('end-time', str(self.end_datetime.time()))
        item.setAttribute('proposer', self.proposer)
        item.appendChild(document.createTextNode(self.subject))
        return item

class FutureBusinessNote(object):
    """A class that represents a note in a FutureBusinessSection -
    typically to say 'No outstanding debates.' or something similar."""
    def __init__(self,soup,id,date):
        self.text = tidied_non_tag_data_in(soup)
        self.id = id
        self.date = date

    def get_dom(self,document):
        item = document.createElement('future-business-note')
        item.setAttribute('id', self.id)
        item.appendChild(document.createTextNode(self.text))
        return item

class Intermission(object):
    """A class that represents intermissions in the programme for
    Westminster Hall described in Part B of Future Business"""

    def __init__(self,soup,id):
        self.text = tidied_non_tag_data_in(soup)
        self.id = id

    def get_dom(self,document):
        item = document.createElement('whall-adjournment-debates-intermission')
        item.appendChild(document.createTextNode(self.text))
        return item

class AdjourmentDebateList(object):
    """A class representing a list of debates in Westminster Hall"""

    def __init__(self, date, soup, id ):
        self.id = id
        self.date = date
        self.all_items = []
        tbody = soup.find('tbody')
        if not tbody:
            raise Exception, "Couldn't find tbody in AdjourmentDebateList"
        for row in tbody.findAll('tr',recursive=False):
            cells = row.findAll('td',recursive=False)
            if not cells:
                raise Exception, "Failed to find any cells in row: "+row.prettify()
            if len(cells) == 1:
                # Assume it's an intermission:
                item = Intermission(cells[0],self.id)
            elif len(cells) == 3:
                item = AdjourmentDebate(date,cells[0],cells[1],non_tag_data_in(cells[2]))
            else:
                raise Exception, "Always expect three cells in each table row of an AdjourmentDebateList; 'cells' was "+str(cells)
            self.all_items.append(item)

    def get_dom(self,document):
        adjournments = document.createElement('whall-adjournment-debate-list')
        for item in self.all_items:
            adjournments.appendChild(item.get_dom(document))
        return adjournments

class MotionHeading(object):
    def __init__(self,id,motion_heading):
        self.id = id
        self.motion_heading = motion_heading
    def get_dom(self, document):
        item = document.createElement('item-heading')
        item.setAttribute('id',self.id)
        item.appendChild(document.createTextNode(self.motion_heading))
        return item

class MotionText(object):
    def __init__(self,id,motion_text):
        self.id = id
        self.motion_text = motion_text
    def get_dom(self, document):
        item = document.createElement('motion-text')
        item.setAttribute('id',self.id)
        item.appendChild(document.createTextNode(self.motion_text))
        return item

class MotionMember(object):
    def __init__(self,id,motion_member):
        self.id = id
        self.motion_member = motion_member
    def get_dom(self, document):
        item = document.createElement('motion-member')
        item.setAttribute('id',self.id)
        item.appendChild(document.createTextNode(self.motion_member))
        return item

class MotionNote(object):
    def __init__(self,id,motion_note):
        self.id = id
        self.motion_note = motion_note
    def get_dom(self, document):
        item = document.createElement('motion-note')
        item.setAttribute('id',self.id)
        item.appendChild(document.createTextNode(self.motion_note))
        return item

class Motion(object):

    def __init__(self):
        self.all_items = []

    def get_unique_member(self):
        unique_member = None
        for i in self.all_items:
            if i.__class__ == MotionMember:
                if unique_member:
                    return None
                else:
                    unique_member = i.motion_member
        return unique_member

    def get_new_id(self):
        counter = len(self.all_items) + 1
        return "%s.%d" % (self.id,counter)

    def add_heading(self,heading_text):
        self.all_items.append(MotionHeading(self.get_new_id(),heading_text))

    def add_motion_note(self,note_text):
        self.all_items.append(MotionNote(self.get_new_id(),note_text))

    def add_motion_member(self,member_text):
        self.all_items.append(MotionMember(self.get_new_id(),member_text))

    def add_motion_text(self,motion_text):
        self.all_items.append(MotionText(self.get_new_id(),motion_text))

    def feed_motion(self, soup):
        """This method is expecting to be passed the middle tr from a private member's bill
        with a motion text paragraph. There should still be a member tr to come.
        """
        motion_div = soup.find('div', {'class': 'paraMotionText'})
        self.add_motion_text(tidied_non_tag_data_in(motion_div))

    def feed_member(self, soup):
        """This method is expecting to be passed the second tr from a
        private members bill (or the third, if there was a motion tr).
        From this we can get the member in charge.
        """

        member_div = soup.find('div', {'class': "paraMemberinCharge"})
        if member_div:
            new_member_text = member_div.string.split(':')[1].strip()
            self.add_motion_member(new_member_text)
            return
        member_div = soup.find('div', {'class': "paraMotionSponsor"})
        if member_div:
            new_member_text = non_tag_data_in(member_div).strip()
            self.add_motion_member(new_member_text)
        else:
            raise Exception, "In feed_member, couldn't parse:\n"+soup.prettify()

    def feed_note(self, soup):
        new_note_text = tidied_non_tag_data_in(soup)
        self.add_motion_note(new_note_text)

class PrivateMembersBill(Motion):
    """Class representing a private member's motion."""

    # If an instance of a PMB was introduced in the lords, this class
    # attribute will be overridden to True.
    lords = False

    # If an instance of a PMB has a separate motion text, this class
    # attribute will be overridden to contain that text
    motion_text = None

    def __init__(self, soup, container_id, date):
        """This method is expecting to be passed soup of the first tr from a
        private member's bill. From this we can find the id and the title.
        The container_id parameter should contain the id of the business item
        which this PMB lives under.

        Unlike most other items, we're going to set the id from the soup,
        rather than inventing one. This is because the PMBs are numbered.
        """

        Motion.__init__(self)

        # The number of this PMB, which we want to use for the id, is
        # contained in a span.
        item_span = soup.find('span', {"class": "charBusinessItemNumber"})
        if item_span:
            item_number = item_span.string
        else:
            item_number = 1 # Assume if no number, there's only the one?

        self.id = "%s.%s" %(container_id, item_number)
        self.date = date

        # The actual text of the bill (and whether it was introduced in the lords,
        # is in a div with class paraFBPrivateMembersBillItemHeading.
        if item_span:
            heading_div = item_span.findNext('div', {'class': "paraFBPrivateMembersBillItemHeading"})
        else:
            heading_div = soup.findNext('div', {'class': "paraFBPrivateMembersBillItemHeading"})

        # Get a text representation of the bill, and whether it is a lords one.
        self.heading_text, self.lords, self.petitioner = get_contents_and_lords(heading_div)

        self.add_heading(self.heading_text)

    def get_dom(self, document):
        item = document.createElement('private-members-bill')
        item.setAttribute('id', self.id)
        unique_member = self.get_unique_member()
        if unique_member:
            item.setAttribute('speakername', unique_member)
            add_member_id_attribute(item,unique_member,self.date)

        if self.lords:
            item.setAttribute('lords', 'yes')

        for sub_item in self.all_items:
            item.appendChild(sub_item.get_dom(document))

        return item

class EuropeanCommitteeEvent(Motion):
    xml_name = 'european-committee-motion'

    def __init__(self,soup,id):
        Motion.__init__(self)
        # introduction = tr.find('div', {'class': 'paraOrderofBusinessRubric-centred'})
        self.id = id
        self.start_datetime = None
        self.date_and_time_text = None
        if soup:
            self.date_and_time_text = tidied_non_tag_data_in(soup)
            if re.search('(?ims)Date and time of consideration to be arranged',self.date_and_time_text):
                pass
            else:
                m = re.search('(?ims)To be considered at (\d+)\.(\d+) (am|pm) on (\d+) ([a-zA-Z]+) (\d+)',self.date_and_time_text)
                if m:
                    new_date_time_str = m.group(6)+" "+m.group(5)+" "+m.group(4)+" "+m.group(1)+"."+m.group(2)+" "+m.group(3)
                    format = '%Y %B %d %I.%M %p'
                    self.start_datetime = datetime.datetime(*(time.strptime(new_date_time_str,format)[0:6]))
                else:
                    raise Exception, "Couldn't parse the date and time text introducing the European Committee business: '"+date_and_time_text+"'"

    def get_dom(self, document):
        item = document.createElement(self.xml_name)
        item.setAttribute('id', self.id)
        if self.start_datetime:
            item.setAttribute("start-time",str(self.start_datetime.strftime(FILENAME_DATE_FORMAT)))
        if self.date_and_time_text:
            scheduled = document.createElement('scheduled')
            scheduled.appendChild(document.createTextNode(self.date_and_time_text))
            item.appendChild(scheduled)

        unique_member = self.get_unique_member()
        if unique_member:
            item.setAttribute('speakername', unique_member)
            if self.start_datetime:
                add_member_id_attribute(item,unique_member,self.start_datetime.date())
            else:
                add_member_id_attribute(item,unique_member,None)

        for sub_item in self.all_items:
            item.appendChild(sub_item.get_dom(document))

        return item

# From November 2010, sometimes they have a BusinessItem table just after a
# motion proposed by the backbench committee. I just want the text, I can't
# be fussed with structure.
class GenericParaMotionText(EuropeanCommitteeEvent):
    xml_name = 'motion-text'

class BusinessItemTable(object):
    """This class represents a table of private members' bills.

    Logically, this table is part of the previous business item, since it represents
    a collection of private members' bills which come in that business item.
    """

    def __init__(self, soup, container_id, date):
        """Initialize this table with soup representing the table, and
        container_id, which will be used as the base for making ids of
        the PMBs in the table.
        """

        self.container_id = container_id
        self.soup = soup
        self.date = date

        self.all_items = []

        current_item = None

        for tr in self.soup.findAll('tr'):
            # Only consider the innermost <tr> here, otherwise we end
            # up duplicating them:
            if tr.find('tr'):
                continue
            if len(non_tag_data_in(tr).strip()) == 0: continue # Whitespace only

            # Have we found the first tr of a PMB?
            if tr.find('div', {'class': 'paraFBPrivateMembersBillItemHeading'}):
                if current_item:
                    self.all_items.append(current_item)
                current_item = PrivateMembersBill(tr, self.container_id, self.date)
            # European Committee events have a slightly different heading:
            elif tr.find('div', {'class': 'paraBusinessItemHeading'}):
                # At the start of the BusinessItem div, we sometimes
                # have a paraBusinessItemHeading without a preceding
                # paraOrderofBusinessRubric-centred, in that case
                # create one:
                if not current_item:
                    current_item = EuropeanCommitteeEvent(None,self.container_id)
                new_heading_text = tidied_non_tag_data_in(tr)
                current_item.add_heading(new_heading_text)
            elif tr.find('div', {'class': 'paraOrderofBusinessRubric-centred'}):
                if current_item:
                    self.all_items.append(current_item)
                current_item = EuropeanCommitteeEvent(tr,self.container_id)
            # Have we found the middle tr of a PMB with a motion text?
            elif tr.find('div', {'class': 'paraMotionText'}):
                if not current_item:
                    current_item = GenericParaMotionText(None,self.container_id)
                current_item.feed_motion(tr)
            # Have we found the final tr of a PMB? If so, good, let's yield it.
            elif tr.find('div', {'class': 'paraMemberinCharge'}) or tr.find('div', {'class': 'paraMotionSponsor'}):
                if not current_item:
                    current_item = GenericParaMotionText(None,self.container_id)
                current_item.feed_member(tr)
            elif tr.find('div', {'class': 'paraBusinessItemNote'}) or tr.find('div', {'class': 'paraMotionNote'}) or tr.find('div', {'class': 'paraMotionNote-centred'}):
                current_item.feed_note(tr)
            # We've found something I've not seen here before.
            else:
                print >> sys.stderr, (u"Unknown row is:\n"+tr.prettify()).encode('utf-8')
                raise ValueError("What are we doing here?")
        if current_item:
            self.all_items.append(current_item)

class WestminsterHallAdjournmentIntroduction(object):

    def __init__(self, soup, id, date):
        self.id = id
        self.text = tidied_non_tag_data_in(soup)
        self.date = date

    def get_dom(self, document):
        item = document.createElement('whall-adjournment-debates-introduction')
        item.setAttribute('id', self.id)
        item.appendChild(document.createTextNode(self.text))
        return item

class MinisterialStatement(object):

    def __init__(self, soup, id, date):
        self.id = id
        self.date = date
        self.statement_tuples = []
        for tr in soup.findAll('tr'):
            # Only consider the innermost <tr> here, otherwise we end
            # up duplicating them:
            if tr.find('tr'):
                continue
            # Each of these then should have a statement number in the
            # left hand cell:
            cells = tr.findAll('td')
            if len(cells) != 2:
                raise Exception, "Innermost row of a MinisterialStatement didn't have two cells: "+tr.prettify()
            statement_number_scraped_str = non_tag_data_in(cells[0]).strip()
            statement_number_scraped = None
            try:
                statement_number_scraped = int(statement_number_scraped_str,10)
            except:
                raise Exception, "We expected a parseable integer in the left cell each MinisterialStatement row - couldn't deal with: '"+statement_number_scraped_str+"'"
            c = cells[1]
            subject_tag = c.find('span',{'class':'charStatementSubject'})
            if not subject_tag:
                raise Exception, "Couldn't find charStatementSubject in right MinisterialStatement cell: "+c.prettify()
            subject = tidied_non_tag_data_in(subject_tag)
            # Remove it:
            subject_tag.extract()
            # What's left should just be the ministerial title, suffixed with a colon:
            minister = tidied_non_tag_data_in(c)
            minister = re.sub('\s*:\s*$','',minister)
            self.statement_tuples.append((statement_number_scraped,minister,subject))

    def get_dom(self, document):
        item = document.createElement('ministerial-statements')
        item.setAttribute('id', self.id)
        for t in self.statement_tuples:
            sub_item = document.createElement('ministerial-statement')
            sub_item.setAttribute('id','%s.%s'%(self.id,t[0]))
            sub_item.setAttribute('minister',t[1])
            sub_item.appendChild(document.createTextNode(t[2]))
            item.appendChild(sub_item)
        return item

class FutureBusinessDay(object):
    """Class representing a a day from the future business page."""

    def __init__(self, soup, parent_id, scraped_timestamp, date):
        """Start with the soup of the day, and an id, which
        we'll then use as the base for the ids of the items on that day.

        We'll also work out the date of this business day, and set that as
        an attribute called date.
        """

        self.soup = soup
        self.scraped_timestamp = scraped_timestamp
        date_div = self.soup.find('div', {'class': 'paraFutureBusinessDate'})
        if not date_div:
            raise Exception, "Failed to find date in FutureBusinessDay"

        # This will have year 1900, since there is no year in the
        # string - we'll have to fix it up.  Sometimes, however, this
        # div contains the name of the European Committee that this is
        # the schedule for, so detect that as a different case.
        date_string = date_div.string

        m_european_committee = re.search('(?ims)European\s+Committee\s+(\S+)',date_string)

        # We may have better information about the date, if this isn't
        # a European committee:
        self.date = date
        self.european_committee = None

        if m_european_committee:
            self.european_committee = m_european_committee.group(1)
            self.id = parent_id + "." + self.european_committee
        else:
            self.date = dateutil.parser.parse(date_string,fuzzy=True).date()
            if self.date == datetime.date.today():
                if verbose: print >> sys.stderr, (u"Warning: fuzzy date parsing of '%s' returned today's date" % (date_string.strip(),)).encode('utf-8')
            self.date = adjust_year_with_timestamp(self.date,self.scraped_timestamp)
            self.id = parent_id + "/" + str(self.date)

        self.all_items = []

        counter = 1

        item = None

        for content_item in self.soup.findAll(recursive=False):

            items_to_consider = []
            if has_class_attribute(content_item) and content_item['class'] == 'FutureBusinessItemGroup':
                items_to_consider = content_item.findAll(recursive=False,text=False)
            else:
                items_to_consider.append(content_item)

            for c in items_to_consider:

                # The following three types of tag are in the soup, but don't represent
                # business items:
                if not has_class_attribute(c):
                    continue
                empty_class = ( 'paraItemSeparatorRule-padding',
                                'paraOrderofBusinessItemSeparator',
                                'paraEndRule-padding' )
                if c['class'] in empty_class:
                    assert_empty(c)
                    continue

                elif c['class'] == 'paraFutureBusinessDate':
                    # (n.b. already extracted above)
                    continue

                elif c['class'] == 'paraFutureBusinessItemGroupHeading':
                    # I *think* it's OK to skip these headings...
                    # print >> sys.stderr, "Skipping the div '"+tidied_non_tag_data_in(c)+"'"
                    continue

                elif c['class'] == 'paraFutureBusinessDateNote' or c['class'] == 'paraBusinessItemNote' or c['class'] == 'paraMotionNote':
                    item = FutureBusinessNote(c,'%s.%s'%(self.id,counter),self.date)

                elif c['class'] == 'paraAdjournmentProposedSubject':
                    item = WestminsterHallAdjournmentIntroduction(c,'%s.%s'%(self.id,counter),self.date)

                # This is a new business item:
                elif c.name == 'div' and c['class'] == 'paraFutureBusinessListItem':
                    item = FutureBusinessListItem(c,'%s.%s'%(self.id, counter),self.date)

                elif c.name == 'table' and c['class'] == 'MinisterialStatement':
                    item = MinisterialStatement(c,'%s.%s'%(self.id, counter),self.date)

                # We've found a table of private members bills, which we add to the current
                # business item.
                elif c.name == 'table' and c['class'] == 'BusinessItem':
                    # In section D you don't necessarily get a
                    # paraFutureBusinessListItem beforehand:
                    if not item:
                        item = FutureBusinessListItem(None,'%s.%s'%(self.id, counter),self.date)
                    # But in either case, feed the private members bills:
                    item.feed_pmbs(c)
                    self.all_items.append(item)
                    counter += 1
                    item = None
                    continue

                elif c.name == 'table' and c['class'] == 'AdjournmentList':
                    item = AdjourmentDebateList(self.date,c,'%s.%s'%(self.id, counter))

                else:
                    raise Exception, "Unknown child found in FutureBusinessDay:\n"+c.prettify()

                # Now to work out if we have everything we need in order to yield this
                # busitess item. We can do this based on the next sibling of the current tag.
                # if there isn't a next sibling (we've come to the end of the table), or the
                # next sibling is something other than a table, then there isn't anything
                # left of this business item, and we can yield it and increment the counter.
                next_item = c.findNextSibling()

                if c['class'] in ('paraFutureBusinessDateNote', 'paraBusinessItemNote'):
                    self.all_items.append(item)
                    item = None
                    counter += 1                    

                if (not next_item or not (next_item.name == 'table' and next_item['class'] == 'BusinessItem')) and item:
                    self.all_items.append(item)
                    item = None
                    counter += 1

    def get_dom(self, document):
        """Make and return a DOM element to represent this business day.
        Needs to take a document since the DOM wants us to create all elements
        using a methond on the document.
        """

        if self.european_committee:
            item = document.createElement('european-committee')
            item.setAttribute('committee-letter',self.european_committee)
        else:
            item = document.createElement('business-day')
            item.setAttribute('date', self.date.isoformat())

        item.setAttribute('id', self.id)

        for sub_item in self.all_items:
            dom_item = sub_item.get_dom(document)
            item.appendChild(dom_item)

        return item

class BusinessDivisionHeading(object):
    """Class to represent a business division heading. There seems to be just the one
    of these at the start of the page.
    """
    def __init__(self, soup, id, scraped_timestamp, date):
        """Initialize with the soup and an id."""
        self.id = id
        self.date = date

        # Contents is just the join of the strings immediately under the heading.
        self.contents = get_string_contents(soup, recursive=False)

        # This heading contains the date on which the future business in this page
        # stops. This could be very useful, so we'll pick it out.
        self.end_date = None
        if re.search("for the period ending on",self.contents):
            self.end_date = dateutil.parser.parse(self.contents, fuzzy=True).date().isoformat()

    def get_dom(self, document):
        """Create a DOM element to represent this heading.
        Needs to be passed a document since elements are created
        using a method on the document.
        """
        item = document.createElement('division-heading')
        item.setAttribute('id', self.id)
        if self.end_date:
            item.setAttribute('end_date', self.end_date)
        contents = document.createTextNode(self.contents)
        item.appendChild(contents)

        return item

class MotionSponsor(object):
    def __init__(self,id,name,group,amendment,date):
        self.group = group
        self.amendment = amendment
        self.id = id
        self.name = name
        self.date = date
    def get_dom(self,document):
        item = document.createElement('motion-sponsor')
        item.setAttribute('id',self.id)
        item.setAttribute('speakername',self.name)
        add_member_id_attribute(item,self.name,self.date)
        item.setAttribute('group',str(self.group))
        item.setAttribute('amendment',str(self.amendment))
        return item

class MotionParagraph(object):
    def __init__(self,id,soup):
        self.id = id
        self.paragraph_text = tidied_non_tag_data_in(soup)
        self.original_class = soup['class']
    def get_dom(self,document):
        item = document.createElement('motion-paragraph')
        item.setAttribute('id',self.id)
        item.setAttribute('original_class',self.original_class)
        item.appendChild(document.createTextNode(self.paragraph_text))
        return item
    def empty(self):
        return len(self.paragraph_text) == 0
    def is_item_number_or_header(self):
        m = re.search('^\S*(\s*\([a-zA-Z0-9]+\)\s*)*$',self.paragraph_text)
        return m

class RemainingBusinessItem(object):
    def __init__(self,id,date):
        self.id = id
        self.date = date
        self.sponsors = []
        self.paragraphs = []
        self.paragraph_number = 1
        self.is_amendment = False
        self.amendment_number = None
        self.heading_text = None
    def set_heading_text(self,heading_text):
        self.heading_text = heading_text
    def set_is_amendment(self,is_amendment):
        self.is_amendment = is_amendment
    def set_amendement_number(self,amendment_number_text):
        if self.amendment_number:
            raise Exception, "The amendment number had already been set (to "+self.amendment_number+"), trying to set with: "+amendment_number_text
        m = re.search('^\s*\((\w+)\)\s*$',amendment_number_text)
        if not m:
            raise Exception, "Unexpected form of paraAmendmentNumber - currently think it should be like '(a)', '(b)', etc."
        self.amendment_number = m.group(1)
        self.id += "." + self.amendment_number
    def add_motion_sponsor(self,sponsor_name,group=False,amendment=False):
        sponsor = MotionSponsor(None, # Set the ID to none initially - in the case of amendments, we may not have the amendment number until later
                                sponsor_name,
                                group,
                                amendment,
                                self.date)
        self.sponsors.append(sponsor)
    def add_paragraph(self,soup):
        new_paragraph = MotionParagraph('%s.p%d'%(self.id,self.paragraph_number),soup)
        # Ignore empty paragraphs:
        if len(new_paragraph.paragraph_text) == 0:
            return
        if len(self.paragraphs) > 0:
            last_paragraph = self.paragraphs[-1]
            if last_paragraph.is_item_number_or_header() and new_paragraph.original_class == last_paragraph.original_class:
                last_paragraph.paragraph_text += " "+new_paragraph.paragraph_text
                return
        self.paragraphs.append(new_paragraph)
        self.paragraph_number += 1

    def get_dom(self,document):
        item = document.createElement('remaining-business-item')
        item.setAttribute('id',self.id)
        if self.is_amendment:
            item.setAttribute('amendment','True')
        if self.heading_text:
            item.setAttribute('heading',self.heading_text)
        for paragraph in self.paragraphs:
            item.appendChild(paragraph.get_dom(document))
        sponsor_number = 1
        for sponsor in self.sponsors:
            sponsor.id = '%s.s%d'%(self.id,sponsor_number)
            item.appendChild(sponsor.get_dom(document))
            sponsor_number += 1
        return item

class Remaining(object):
    def __init__(self, soup, id, scraped_timestamp, date):
        self.id = id
        self.date = date
        self.scraped_timestamp = scraped_timestamp
        tbody = soup.find('tbody')
        if not tbody:
            raise Exception, "Failed to find tbody"
        self.all_items = []
        current_item = None
        current_item_number = 1
        for div in tbody.findAll('div'):
            # All of these classes *may* force the creation of a new item:
            if div['class'] in ( 'paraFutureBusinessItemHeading',
                                 'paraBusinessItemHeading',
                                 'paraAmendmenttoMotionPreamble',
                                 'paraAmendmentNumber' ):
                span_in_div = div.find('span')
                if span_in_div and ('class','charBusinessItemNumber') in span_in_div.attrs:
                    # Then this is a new Item:
                    if current_item:
                        self.all_items.append(current_item)
                        current_item_number += 1
                    current_item = RemainingBusinessItem('%s.%s'%(self.id,current_item_number),self.date)
                    parsed_item_number = int(non_tag_data_in(span_in_div).strip())
                    if parsed_item_number != current_item_number:
                        raise Exception("parsed_item_number ("+str(parsed_item_number)+") didn't match counted item number ("+current_item_number+")")
                elif div['class'] == 'paraAmendmenttoMotionPreamble':
                    if not current_item:
                        raise Exception, "We should never find paraAmendmenttoMotionPreamble with no current item - what would it be amending?"
                    self.all_items.append(current_item)
                    # Don't increment the number, though - this is an
                    # amendment that will contain an amendment number
                    # - we will change the ID on setting that:
                    current_item = RemainingBusinessItem('%s.%s'%(self.id,current_item_number),self.date)
                    current_item.set_is_amendment(True)
                elif div['class'] == 'paraAmendmentNumber':
                    if not current_item:
                        raise Exception, "We should never find paraAmendmentNumber with no current item - what would it be amending?"
                    if current_item.amendment_number:
                        self.all_items.append(current_item)
                        current_item = RemainingBusinessItem('%s.%s'%(self.id,current_item_number),self.date)
                        current_item.set_is_amendment(True)
                        current_item.set_amendement_number(tidied_non_tag_data_in(div))
                    else:
                        current_item.set_amendement_number(tidied_non_tag_data_in(div))
                else:
                    # It's the heading text:
                    current_item.set_heading_text(non_tag_data_in(div).strip())
            elif div['class'] == 'paraMotionSponsor':
                current_item.add_motion_sponsor(non_tag_data_in(div).strip())
            elif div['class'] == 'paraMotionSponsorGroup':
                current_item.add_motion_sponsor(non_tag_data_in(div).strip(),group=True)
            elif div['class'] == 'paraAmendmentSponsor':
                current_item.add_motion_sponsor(non_tag_data_in(div).strip(),amendment=True)
            elif div['class'] in ( "paraMotionNote",
                                   "paraMotionNote-centred",
                                   "paraMotionSub-Paragraph",
                                   "paraMotionSub-Paragraph-continued",
                                   "paraMotionSub-Sub-Paragraph",
                                   "paraMotionNumberedParagraph-continued",
                                   "paraMotionCross-Heading-leftregular",
                                   "paraMotionText",
                                   "paraMotionText-continued",
                                   "paraMotionNote-centred",
                                   "paraMotionNumberedParagraph-hanging",
                                   "paraMotionNumberedParagraph-indented",
                                   "paraMotionCross-Heading-centredregular",
                                   "paraDefinitionList" ):
                current_item.add_paragraph(div)
            else:
                raise Exception, "Unhandled div class: "+div['class']+", which prettified is: "+div.prettify()
        if current_item:
            self.all_items.append(current_item)
            current_item_number += 1

    def get_dom(self,document):
        item = document.createElement('remaining-business')
        for sub_item in self.all_items:
            item.appendChild(sub_item.get_dom(document))
        return item

class ForthcomingDebatesItem(object):
    def __init__( self, id, soup = None, name = None, text = None ):
        self.id = id
        if soup:
            self.text = tidied_non_tag_data_in(soup)
            class_map = {  "paraWHDebatesRubric": "debates-rubric",
                           "paraWHDebatesDateRange": "debates-date-range",
                           "paraNoticeText": "notice",
                           "paraForthcomingDebatesHeading": "forthcoming-debates-heading" }
            if not soup['class'] in class_map:
                raise Exception, "Unknown div class '"+soup['class']+"' in ForthcomingDebates"
            self.name = class_map[soup['class']]
        else:
            self.name = name
            self.text = text

    def get_dom( self, document ):
        item = document.createElement(self.name)
        item.setAttribute('id',self.id)
        text = document.createTextNode(self.text)
        item.appendChild(text)
        return item

class ForthcomingDebates(object):
    """Class to represent the notice about ForthcomingDebates"""
    def __init__(self, soup, id, scraped_timestamp, date):
        """Initialize with the soup and an id."""
        self.id = id
        self.date = date
        self.contents = ''
        self.heading = None
        self.all_items = []
        counter = 1
        for div in soup.findAll('div',recursive=False):
            if div['class'] == "paraItemSeparatorRule-padding":
                assert_empty(div)
                continue
            if div['class'] == "paraForthcomingDebatesHeading":
                for c in div.contents:
                    if type(c) == NavigableString:
                        item = ForthcomingDebatesItem("%s.%d"%(self.id,counter),None,'forthcoming-debates-heading',tidied_non_tag_data_in(c))
                        counter += 1
                        self.all_items.append(item)
            elif div['class'] == 'paraEndRule-padding':
                # That's empty...
                continue
            else:
                item = ForthcomingDebatesItem("%s.%d"%(self.id,counter),div)
                counter += 1
                self.all_items.append(item)

    def get_dom(self, document):
        """Create a DOM element to represent this heading.
        Needs to be passed a document since elements are created
        using a method on the document.
        """
        item = document.createElement('forthcoming-debates')
        item.setAttribute('id', self.id)
        for sub_item in self.all_items:
            item.appendChild(sub_item.get_dom(document))
        return item

class BusinessDivisionNote(object):
    """Class to represent a business division note. There seems to be just one of
    these in the page, at the start."""

    def __init__(self, soup, id, scraped_timestamp, date):
        """Initialize with the soup of the note, and an id."""
        self.id = id
        self.date = date
        # The note should just contain a string. There might be some funny whitespace,
        # so we strip that out and replace with spaces.
        self.contents = tidied_non_tag_data_in(soup)

    def get_dom(self, document):
        """Get a DOM item representing this business division note.
        Needs to be passed a document since elements are created using
        a method of the document.
        """
        item = document.createElement('division-note')
        item.setAttribute('id', self.id)
        contents = document.createTextNode(self.contents)
        item.appendChild(contents)

        return item

def is_future_business_div(x):
    if x.name != 'div':
        return False
    for t in x.attrs:
        if t[0] == 'div':
            continue
        if re.search('^FutureBusiness[A-F]',t[1]):
            return True
    return False

def table_or_div(x):
    return x.name == 'div' or x.name == 'table'

def selected_css(x):
    for t in x.attrs:
        if t[0] == 'class' and re.search('selected',t[1]):
            return True
    return False

def parse_calendar_time(time_text):
    t = time.strptime(time_text,"%I.%M%p")
    return datetime.time(t[3],t[4])

class CalendarTimespan(object):
    """ Class representing a series of programmed events starting at a
    particular time """

    def __init__(self, id, start_time, end_time = None):
        self.id = id
        self.start_time = start_time
        self.end_time = end_time
        self.event_sections = []

    def add_event_section(self, event):
        self.event_sections.append(event)

    def get_dom(self,document):
        item = document.createElement('calendar-event-timespan')
        item.setAttribute('id', self.id)
        if self.start_time:
            item.setAttribute('start-time', str(self.start_time))
        if self.end_time:
            item.setAttribute('end-time', str(self.end_time))
        for section in self.event_sections:
            item.appendChild(section.get_dom(document))
        return item

class SelectCommitteeEvent(object):

    def __init__(self,id,committee_name,subject,location,witness):
        self.id = id
        self.committee_name = committee_name
        self.subject = subject
        self.location = location
        self.witness = witness

    def get_dom(self,document):
        item = document.createElement('calendar-event-select-committee')
        item.setAttribute('id',self.id)
        if self.committee_name:
            item.setAttribute('committee-name',self.committee_name)
        for t in [ ('subject',self.subject),
                   ('location',self.location),
                   ('witness',self.witness) ]:
            if t[1]:
                sub_item = document.createElement(t[0])
                text = document.createTextNode(t[1])
                sub_item.appendChild(text)
                item.appendChild(sub_item)
        return item

class BasicEventSection(object):
    """ Class representing a programmed event in the main chamber of
    the Commons or the Lords """

    def __init__(self,id,heading):
        self.id = id
        self.heading = heading
        self.all_items = []

    def add_item(self,item):
        self.all_items.append(item)

    def get_dom(self,document):
        item = document.createElement('calendar-event-section')
        item.setAttribute('id', self.id)
        if self.heading:
            heading = document.createElement('heading')
            heading.setAttribute('id',self.id+".h")
            heading_text = document.createTextNode(self.heading)
            heading.appendChild(heading_text)
            item.appendChild(heading)
        for sub_item in self.all_items:
            item.appendChild(sub_item.get_dom(document))
        return item

class SimpleItem(object):
    """ Class to represent a single event, e.g. a question from someone """

    def __init__(self,id,date,text):
        self.id = id
        self.date = date
        m = re.search('^(.*)\s+-\s+([^-]+)\s*$',text)
        self.member = None
        self.text = None
        if m:
            # FIXME: check whether this is recognised member - for the
            # moment, just exclude a few common cases:
            if re.search('(?ims)(report\s+stage|(first|1st|second|2nd|third|3rd)\s+reading|committee\sof\sthe\swhole\shouse)',m.group(2)):
                self.text = text.strip()
            else:
                self.text = m.group(1).strip()
                self.member = m.group(2).strip()
        else:
            self.text = text.strip()

    def get_dom(self,document):
        item = document.createElement('calendar-item')
        item.setAttribute('id', self.id)
        if self.member:
            item.setAttribute('speakername', self.member)
            add_member_id_attribute(item,self.member,self.date)
        contents = document.createTextNode(self.text)
        item.appendChild(contents)
        return item

def is_subject_div(x):
    if x.name == 'div':
        first_emphasized = x.find('em')
        if first_emphasized:
            text = tidied_non_tag_data_in(first_emphasized)
            if re.search('Subject',text):
                return True
    return False

class FutureEventsPage(object):
    """Class representing a page downloaded from Future Business or the Calendar"""

    # A mapping of CSS classes to Python classes. This will tell us what kind
    # of object to instantiate when we meet divs below.
    class_map = {
        "paraFutureBusinessDivisionHeading": BusinessDivisionHeading,
        "paraFutureBusinessDivisionNote": BusinessDivisionNote,
        "ForthcomingDebates": ForthcomingDebates,
        "BusinessItem" : Remaining,
        "WHFutureBusinessDay" : FutureBusinessDay,
        "FutureBusinessDay": FutureBusinessDay }

    def __init__(self, filename):
        """Pass in the filename of the page"""

        self.future_business_section = None

        basename_match = re.search('(?ims)^(.*)\.html$',os.path.basename(filename))
        if not basename_match:
            raise Exception, "The filename didn't have a .html extension: "+filename
        self.id = basename_match.group(1)

        timestamp_match = re.search('(?ims)^.*(\d{8}T\d{6}).*$',filename)
        if not timestamp_match:
            raise Exception, "Failed to find the timestamp in filename: "+filename
        scraped_timestamp_str = timestamp_match.group(1)
        self.scraped_timestamp = dateutil.parser.parse(scraped_timestamp_str)
        global current_file_scraped_date
        current_file_scraped_date = str(self.scraped_timestamp.date())

        fp = open(filename)
        html = fp.read()
        fp.close()

        # Make a soup of the page, remembering to convert HTML entities
        # to unicode characters.
        html = re.sub('<(div [^>]*[^ ])/>', r'<\1></div>', html)
        soup = BeautifulSoup(html,convertEntities=BeautifulSoup.HTML_ENTITIES)

        self.all_items = []

        calendar_daily_summary = soup.find('div', {'class':'calendar-daily-summary'})

        self.id = "uk.org.publicwhip"
        self.date = None

        if calendar_daily_summary:
            # Then this is a page from the calendar, not future business.
            #
            # Although we could guess from the filename which house
            # and section this is, let's determine it from the the
            # page content - hopefully that's more robust.

            selected_date = soup.find('div',{'id':'selected-date'})
            date_text = tidied_non_tag_data_in(selected_date)
            datetime_parsed = dateutil.parser.parse(date_text, fuzzy=True)
            if not datetime_parsed:
                raise Exception, "Failed to parse date text '"+date_text+"'"
            self.date = datetime_parsed.date()

            houses_list = soup.find('ul',{'id':'houses'})
            if not houses_list:
                raise Exception, "Failed to find house list"
            selected_list_item = houses_list.find(selected_css)
            if not selected_list_item:
                raise Exception, "Failed to find a selected tab in the house list"
            self.house = None
            if re.search('commons',selected_list_item['class']):
                self.house = 'commons'
            elif re.search('lords',selected_list_item['class']):
                self.house = 'lords'
            else:
                raise Exception, "Unknown house selected in:\n"+selected_list_item.prettify()

            location_list = soup.find('ul',{'id':'location-selector'})
            if not location_list:
                raise Exception, "Failed to find the location list"
            selected_list_item = location_list.find(selected_css)
            if not selected_list_item:
                raise Exception, "Failed to find selected location tab in the location list"
            location_link = selected_list_item.find('a')
            if not location_link:
                raise Exception, "Failed to find a link in the selected location tab"
            location_long = tidied_non_tag_data_in(location_link)
            long_name_to_short = { 'Main Chamber': 'main-chamber',
                                   'Grand Committee': 'grand-committee',
                                   'Select Committee': 'select-committee',
                                   'Westminster Hall': 'westminster-hall',
                                   'General Committee': 'general-committee' }
            self.location = None
            for k in long_name_to_short:
                if re.search(re.escape(k),location_long):
                    self.location = long_name_to_short[k]
                    break
            if not self.location:
                raise Exception, "Unknown location '"+location_long+"'"
            self.combined = self.house+"-"+self.location
            if not re.search(re.escape(self.combined),filename):
                raise Exception, "The scraped house+location ("+self.combined+") didn't match the filename ("+filename+")"

            self.original_url = CALENDAR_SECTIONS[self.combined] % (self.date.strftime(CALENDAR_URL_DATE_FORMAT),)

            self.id += "/calendar/"+self.house+"/"+self.location+"/"+str(self.date)+"/"+scraped_timestamp_str+"/"

            self.timespans = []
            timespan_counter = 1
            section_counter = 1
            item_counter = 1

            self.no_events = False
            no_events_div = soup.find('div',{'class':'no-events'})
            if no_events_div:
                self.no_events = True
                self.no_events_text = tidied_non_tag_data_in(no_events_div)
            else:
                events_div = soup.find('div',{'id':'events-output'})
                if not events_div:
                    raise Exception, "Failed to find a div with id 'events-output'"

                current_timespan = None
                current_section = None

                for row in events_div.findAll('tr'):
                    # Check this is the bottom level; if there are
                    # nested rows then we don't understand the
                    # structure yet:
                    if row.find('tr'):
                        raise Exception, "Don't expected nested tables in 'events-output'"
                    heading_cells = row.findAll('th')
                    if heading_cells:
                        if len(heading_cells) != 2:
                            raise Exception, "We expect two heading columns in the table in 'events-output', not "+str(len(heading_cells))
                        if not tidied_non_tag_data_in(heading_cells[0]) == 'Time' and tidied_non_tag_data_in(heading_cells[1]) == 'Business':
                            raise Exception, "Unexpected column headings in:\n"+row.prettify()
                    else:
                        cells = row.findAll('td')
                        if len(cells) != 2:
                            raise Exception, "We expect two columns in the table in 'events-output', not "+str(len(cells))
                        time_text = tidied_non_tag_data_in(cells[0])
                        if len(time_text) == 0:
                            # Then this is a continuation of the current timespan:
                            pass
                        else:
                            if current_timespan:
                                if current_section:
                                    current_timespan.add_event_section(current_section)
                                self.timespans.append(current_timespan)
                                timespan_counter += 1
                                section_counter = 1
                                current_timespan = None
                                current_section = None
                            start_time = None
                            end_time = None
                            single_time_re = '(\d+)(\.\d+)?(am|pm)'
                            m_range = re.search(single_time_re+"\s+-\s+"+single_time_re,time_text)
                            m_start = re.search(single_time_re,time_text)
                            if m_range:
                                start_minutes = m_range.group(2) or ".00"
                                start_time_text = m_range.group(1) + start_minutes + m_range.group(3)
                                start_time = parse_calendar_time(start_time_text)
                                end_minutes = m_range.group(5) or ".00"
                                end_time_text = m_range.group(4) + end_minutes + m_range.group(6)
                                end_time = parse_calendar_time(end_time_text)
                            elif m_start:
                                start_minutes = m_start.group(2) or ".00"
                                start_time_text = m_start.group(1) + start_minutes + m_start.group(3)
                                start_time = parse_calendar_time(start_time_text)
                            else:
                                raise Exception, "Couldn't parse the time text '"+time_text
                            current_timespan = CalendarTimespan(self.id+str(timespan_counter),start_time,end_time)

                        c = cells[1]

                        # Sometimes there's nothing in the time column,
                        # so just create a timespan with no times:
                        if not current_timespan:
                            current_timespan = CalendarTimespan(self.id+str(timespan_counter),None,None)

                        if self.combined in ("commons-main-chamber",
                                             "commons-westminster-hall",
                                             "lords-main-chamber",
                                             "lords-grand-committee"):
                            heading_tag = c.find('strong')

                            if heading_tag:
                                if current_section:
                                    current_timespan.add_event_section(current_section)
                                    section_counter += 1
                                    item_counter = 1
                                    current_section = None
                                current_section = BasicEventSection(self.id+str(timespan_counter)+"."+str(section_counter),
                                                                    tidied_non_tag_data_in(heading_tag))
                                heading_tag.extract()
                            remaining_text = tidied_non_tag_data_in(c)
                            if remaining_text:
                                simple_item = SimpleItem(self.id+str(timespan_counter)+"."+str(section_counter)+"."+str(item_counter),
                                                         self.date,
                                                         remaining_text)
                                if not current_section:
                                    current_section = BasicEventSection(self.id+str(timespan_counter)+"."+str(section_counter),
                                                                        None)
                                current_section.add_item(simple_item)
                                item_counter += 1
                        elif self.combined in ("commons-select-committee","commons-general-committee","lords-select-committee"):

                            committee_name_tag = c.find('strong')
                            committee_name = None
                            if committee_name_tag:
                                committee_name = tidied_non_tag_data_in(committee_name_tag)

                            witness_div = c.find('div',{'class':'witness'})
                            witness = None
                            if witness_div:
                                prefix = witness_div.find('em')
                                if prefix:
                                    prefix.extract()
                                witness = tidied_non_tag_data_in(witness_div)
                                witness_div.extract()

                            location_div = c.find('div',{'class':'location'})
                            location = None
                            if location_div:
                                prefix = location_div.find('em')
                                if prefix:
                                    prefix.extract()
                                location = tidied_non_tag_data_in(location_div)
                                location_div.extract()

                            subject_div = c.find(is_subject_div)
                            subject = None
                            if subject_div:
                                prefix = subject_div.find('em')
                                if prefix:
                                    prefix.extract()
                                subject = tidied_non_tag_data_in(subject_div)
                                subject_div.extract()

                            if current_section:
                                current_timespan.add_event_section(current_section)
                                section_counter += 1

                            current_section = SelectCommitteeEvent(self.id+str(timespan_counter)+"."+str(section_counter),
                                                                   committee_name,
                                                                   subject,
                                                                   location,
                                                                   witness)

                        else:
                            raise Exception, "Unhandles section "+self.combined
                current_timespan.add_event_section(current_section)
                self.timespans.append(current_timespan)

        else:
            self.future_business_content = soup.find(is_future_business_div)

            letter_span_tag = self.future_business_content.find('span', { "class" : "charFutureBusinessDivisionLetter" } )
            if not letter_span_tag:
                raise Exception, "Couldn't find the <span> which contains the section letter"
            self.future_business_section = get_string_contents(letter_span_tag).strip()

            self.original_url = FUTURE_BUSINESS_TEMPLATE_LOCATION % (self.future_business_section.lower(),)

            heading = self.future_business_content.find('div', { "class" : "paraFutureBusinessDivisionHeading" } )
            if not heading:
                raise Exception, "Failed to find the BusinessDivisionHeading"

            self.heading_text = non_tag_data_in(heading).strip()
            self.heading_text = re.sub('(?ms)^'+self.future_business_section+'\s*(.*)$','\\1',self.heading_text)

            if self.future_business_section == 'C':
                div_items = self.future_business_content.findAll(table_or_div, recursive=False)
            else:
                div_items = self.future_business_content.findAll('div', recursive=False)

            self.id += "/future/"+self.future_business_section.lower()+"/"+scraped_timestamp_str+"/"

            counter = 1

            empty_classes = ( 'paraEndRule-padding',
                              'paraItemSeparatorRule-padding',
                              'paraOrderofBusinessItemSeparator' )

            for div_item in div_items:
                if not has_class_attribute(div_item):
                    if verbose: print >> sys.stderr, (u"Warning: Skipping this div because it has no 'class' attribute: "+unicode(div_item)).encode('utf-8')
                    continue
                if div_item['class'] in empty_classes:
                    assert_empty(div_item)
                    continue
                o = self.class_map[div_item['class']](div_item, '%s%s' %(self.id, counter), self.scraped_timestamp, self.date)
                counter += 1
                self.all_items.append( o )

    def get_dom(self):
        """Get a DOM representing this page. This can then be used to generate actual XML."""
        if self.future_business_section:
            document = dom_impl.createDocument(None, 'business-schedule', None)
            document.documentElement.setAttribute('id', self.id)
            document.documentElement.setAttribute('url',self.original_url)
            if self.future_business_section:
                document.documentElement.setAttribute('future-business-section', self.future_business_section)
            if self.heading_text:
                document.documentElement.setAttribute('title', self.heading_text)

            for item in self.all_items:
                dom_item = item.get_dom(document)
                document.documentElement.appendChild(dom_item)

            return document
        else:
            document = dom_impl.createDocument(None, 'calendar-schedule', None)
            d = document.documentElement
            d.setAttribute('url',self.original_url)
            d.setAttribute('house',self.house)
            d.setAttribute('location',self.location)
            d.setAttribute('date',str(self.date))
            if self.no_events:
                d.setAttribute('no-events','True')
                recess_text_node = document.createTextNode(self.no_events_text)
                d.appendChild(recess_text_node)
            else:
                for timespan in self.timespans:
                    t = timespan.get_dom(document)
                    d.appendChild(t)
            return document

# Actually parse the stuff here:

if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option('-v', "--verbose", dest="verbose", action="store_true",
                      default=False, help="verbose output, otherwise quiet apart from errors")
    parser.add_option('-f', '--force', dest='force', action="store_true",
                      help='force reparse of everything')
    (options, args) = parser.parse_args()
    verbose = options.verbose

    parse_to_stdout = True
    filenames = args
    # If there are no filenames explicitly passed in on the command
    # line, parse everything from PAGE_STORE with the default rules.
    if not args:
        filenames = sorted(glob.glob(os.path.join(PAGE_STORE,'*.html')))
        parse_to_stdout = False
        if 0 != call(["mkdir","-p",OUTPUT_DIRECTORY]):
            raise Exception, "Failed to create the directory: "+OUTPUT_DIRECTORY

    for filename in filenames:
        if 'future-business-' in filename: continue
        try:
            old_basename = os.path.basename(filename)
            new_basename = re.sub('\.html','.xml',old_basename)
            output_filename = os.path.join(OUTPUT_DIRECTORY,new_basename)
            tmp_output_filename = output_filename + ".tmp"

            if (not parse_to_stdout) and (not options.force) and os.path.exists(output_filename):
                if verbose:
                    print >> sys.stderr, new_basename + " already exists, and --force not specified, so skipping..."
                continue

            if verbose:
                print >> sys.stderr, "Parsing "+filename

            if (not parse_to_stdout) and old_basename in ( 'future-business-c-20100411T162434.html', ):
                    if verbose:
                        print >> sys.stderr, "FIXME: Skipping the file "+old_basename+": currently misparses"
                    continue

            fep = FutureEventsPage(filename)
            xml_output = fep.get_dom().toprettyxml(indent="  ",encoding='utf-8')
            if parse_to_stdout:
                print xml_output
            else:
                fp = open(tmp_output_filename,"w")
                fp.write(xml_output)
                fp.close()

                changed_output = True
                if os.path.exists(output_filename):
                    result = os.system("diff %s %s > /dev/null" % (tmp_output_filename,output_filename))
                    if 0 == result:
                        changed_output = False

                retcode = call( [ "mv", tmp_output_filename, output_filename ] )
                if retcode != 0:
                    raise Exception, "Moving "+tmp_output_filename+" to "+output_filename+" failed."

                if changed_output:
                    fil = open(os.path.join(OUTPUT_DIRECTORY,'changedates.txt'), 'a+')
                    fil.write('%d,%s\n' % (time.time(), new_basename))
                    fil.close()

        except BaseException, e:
            print >> sys.stderr, "Failed for filename: "+filename
            raise
