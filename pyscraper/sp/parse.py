#!/usr/bin/python2.4

import sys
import os
import random
import datetime
import time

from BeautifulSoup import BeautifulSoup
from BeautifulSoup import NavigableString
from BeautifulSoup import Tag
from BeautifulSoup import Comment

from subprocess import call

from resolvemembernames import memberList

import re
import glob

# ------------------------------------------------------------------------
# 
# This script is quite horrendous, in my opinion - I'm sure it could
# be written much more simply by someone with better intuition for
# this type of webscraping.  (Or by me if I started again.)  
# 
# ------------------------------------------------------------------------

# If verbose is True then you'll get about a gigabyte of nonsense on
# standard output.

verbose = False

# Up to and including 2003-05-29 is the old format of the official
# reports, and 2003-06-03 and after is the new format.  There's one
# particular date that has a different format again, which is
# 2004-06-30.
#
# Old format:
# ~~~~~~~~~~~
#
# Table rows with left <td> containing column information
#                right <td> containing speeches ("substance")
#
# The right <td> can have multiple speeches, which may be split in
# awkward places because of indicating the start of the another column
# in the left td.  Even the speakers sometimes split by col number,
# e.g. 1999-05-19_1.html#Col76
#
# New format:
# ~~~~~~~~~~~
#
# One <p> per speech.
#
# Some contain "Col", some contain times, some quotes (begin with ")
#
# e.g. or2003-12-10_1.html:
#     Assorted headings (e.g. the contents link and right aligned <td> with date)
#
# One huge <td> with alternate:
#   <p> with column information </p>
#   <div> which is really just a content cell as in the early format </div>
#
# ------------------------------------------------------------------------
#
# Other miscellaneous notes:
# ~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# References to official reports look like:
#
#    [<em>Official Report</em>, 13 June 2001; c 1526.]
#
# Things in [<em>] may include:
#   atmosphere (laughter,intteruption)
#   references to official reports or committee reports
#   proposers of bills

# Things in normal <em> may include:
#
#   Amendment disagreed to.
#   Amendment agreed to.
#   Motion, as amended, agreed to.
#   Motion agreed to.
#   Motion debated,
#   Resolved,
#   Meeting closed at 17:46
#   Motion moved&#151;[Name of MSP]
#   Meeting suspended until 14:15.
#   On resuming&#151;
#   rose&#151;

# And some section headings...

def log_speaker(speaker,date,message):
    if False:
        out_file = open("speakers.txt", "a")
        out_file.write(str(date)+": ["+message+"] "+speaker+"\n")
        out_file.close()

class Heading:

    def __init__(self,id_within_column,colnum,time,url,date,heading_text,major):
        self.id_within_column = id_within_column
        self.colnum = colnum
        self.time = time
        self.url = url
        self.date = date
        self.major = major
        self.id = 'uk.org.publicwhip/spor/'+str(date)+'.'+str(colnum)+'.'+str(id_within_column)
        self.heading_text = heading_text

    def to_xml(self):
        if self.major:
            heading_type = 'major'
        else:
            heading_type = 'minor'
        # We probably want to remove all the markup and extraneous
        # spaces from the heading text.
        text_to_display = re.sub('(?ims)<[^>]+>','',self.heading_text)
        text_to_display = re.sub('(?ims)\s+',' ',text_to_display)
        text_to_display = re.sub('"','&quot;',text_to_display)
        text_to_display.strip()
        time_info = ''
        if self.time:
            time_info = ' time="' + str(self.time) + '"'
        result = '<%s-heading id="%s" nospeaker="True" colnum="%s" url="%s"%s>%s</%s-heading>' % ( heading_type, self.id, self.colnum, self.url, time_info, text_to_display, heading_type )
        return result

class Speech:

    def __init__(self,id_within_column,colnum,time,url,date,parser):
        if verbose: print "- Creating Speech..."
        self.id_within_column = id_within_column
        self.colnum = colnum
        self.time = time
        self.url = url
        self.date = date
        self.id = 'uk.org.publicwhip/spor/'+str(date)+'.'+str(colnum)+'.'+str(id_within_column)
        self.paragraphs = [ ]
        if verbose: print "- self.paragraphs was: "+str(self.paragraphs)
        self.speakerid = None
        self.name = None
        self.question_number = None
        self.parser = parser

    def no_text_yet(self):
        return len(self.paragraphs) == 0

    def add_paragraph(self,paragraph):
        # if verbose: print "- in add_paragraph, self.paragraphs was: "+str(self.paragraphs)
        if not paragraph:
            raise Exception, "Trying to add null paragraph..."
        self.paragraphs.append(paragraph)

    def add_text_to_last_paragraph(self,text):
        if self.paragraphs:
            last = self.paragraphs.pop()
            # if verbose: print "- last ["+str(last.__class__)+"] was: "+str(last)
            # if verbose: print "- text ["+str(text.__class__)+"] was: "+str(text)
            # if verbose: print "- self.paragraphs ["+str(self.paragraphs.__class__)+"] was: "+str(self.paragraphs)
            self.paragraphs.append(last+text)
        else:
            self.paragraphs = [ text ]

    def set_speaker(self,speaker):
        if verbose: print "- setting self.name to: "+speaker
        self.name = speaker

    def complete(self):
        # Once we're sure the speech is completed we can decode the
        # name:
        if self.name:
            tidied_speaker = self.name.strip()
            tidied_speaker = re.sub( '(?ims)^\s*', '', tidied_speaker )
            tidied_speaker = re.sub( '(?ims):?\s*$', '', tidied_speaker )
            tidied_speaker = re.sub( '(?ms) +', ' ', tidied_speaker )
            if verbose: print '- New speech from ' + tidied_speaker

            ids = memberList.match_whole_speaker(tidied_speaker,str(self.date))

            final_id = None

            if ids != None:
                if len(ids) == 0:
                    log_speaker(tidied_speaker,str(self.date),"missing")
                elif len(ids) == 1:
                    final_id = ids[0]
                else:
                    # If there's an ambiguity there our best bet is to go
                    # back through the previous IDs used today, and pick
                    # the most recent one that's in the list we just got
                    # back...
                    for i in range(len(parser.speakers_so_far)-1,-1,-1):
                        older_id = parser.speakers_so_far[i]
                        if older_id in ids:
                            final_id = older_id
                            break
                    if not final_id:
                        log_speaker(tidied_speaker,str(self.date),"genuine ambiguity")
                        self.speakerid = None

                if final_id:
                    parser.speakers_so_far.append(final_id)
                    self.speakerid = final_id
                    self.name = tidied_speaker
                else:
                    self.speakerid = None
                    self.name = tidied_speaker

            else:
                # It's something we know about, but not an MSP (e.g
                # Lord Advocate)
                self.name = tidied_speaker
                self.speakerid = None

    def set_question_number(self,number):
        self.question_number = number

    def display(self):
        if verbose: print '- Speech from: '+self.name
        if self.question_number:
            if verbose: print '- Numbered: '+self.question_number
        for p in self.paragraphs:
            if verbose: print '   [paragraph] ' + p

    def to_xml(self):

        # Those awkward alphabetical lists.

        if self.name and (len(self.name) == 1 or self.name == 'Abbreviations'):
            self.paragraphs.insert(0,'<b>'+self.name+'</b>')
            self.name = None

        # We only resolve from the list of MSPs in general, so make
        # George Younger a special case:
        if self.name and re.search('George Younger',self.name):
            self.speakerid = "uk.org.publicwhip/lord/100705"

        # Also we should try to recognize Her Majesty The Queen:
        if self.name and re.search('(?ims)Her Majesty The Queen',self.name):
            self.speakerid = "uk.org.publicwhip/royal/-1"

        # The speech id should look like:
        #    uk.org.publicwhip/spor/2003-06-26.1219.2
        # The speaker id should look like:
        #    uk.org.publicwhip/member/931

        if self.name:
            if self.speakerid:
                speaker_info = 'speakerid="%s" speakername="%s"' % ( self.speakerid, self.name )
            else:
                speaker_info = 'speakername="%s"' % ( self.name )
        else:
            speaker_info = 'nospeaker="true"'

        question_info = ' '
        if self.question_number:
            question_info = 'questionnumber="%s" ' % ( self.question_number )

        time_info = ''
        if self.time:
            time_info = ' time="' + str(self.time) + '"'

        # FIXME: We should probaly output things that look like
        # questions or replies as <ques> and <reply>...

        result = '<speech id="%s" %s %scolnum="%s" url="%s"%s>' % ( self.id, speaker_info, question_info, self.colnum, self.url, time_info )
        html = ''

        for p in self.paragraphs:
            html += "\n<p>" + p + "</p>\n"

        # Try to turn these paragraphs into more XHTML-like closed <p>
        # tags...

        real_paragraphs = re.split("(?ims)\s*</?p[^>]*>\s*",html)
        real_paragraphs = filter( lambda x: not re.match( "(?ims)^\s*$", x ), real_paragraphs )
        real_paragraphs = map( lambda x: x.strip(), real_paragraphs )

        for p in real_paragraphs:
            result += "\n<p>" + p + "</p>\n"

        result += '</speech>'
        return result

class Division:

    def __init__(self,id_within_column,colnum,time,url,date,divnumber):
        self.id_within_column = id_within_column
        self.colnum = colnum
        self.time = time
        self.url = url
        self.date = date
        self.divnumber = divnumber
        self.for_votes = list()
        self.against_votes = list()
        self.abstentions_votes = list()
        self.spoiled_votes_votes = list()
        self.id = 'uk.org.publicwhip/spdivision/'+str(date)+'.'+str(colnum)+'.'+str(divnumber)
        self.candidate = None

    def set_candidate(self,candidate):
        self.candidate = candidate

    def add_votes(self, which_way, name):
        if which_way == 'FOR':
            self.for_votes.append(name)
        elif which_way == 'AGAINST':
            self.against_votes.append(name)
        elif which_way == 'ABSTENTIONS':
            self.abstentions_votes.append(name)
        # There's one instance of a spoiled vote.  I'm not sure quite
        # how this happens with the electronic voting system - maybe
        # there's a "SPOIL VOTE" button, or you pour a glass of water
        # onto the machine...
        elif which_way == 'SPOILED VOTES':
            self.spoiled_votes_votes.append(name)
        else:
            raise Exception, "add_votes for unknown way: " + which_way

    def to_xml(self):
        candidate_info = ''
        if self.candidate:
            candidate_info = ' candidate="'+self.candidate+'"'
        result = '<division id="%s"%s nospeaker="True" divdate="%s" divnumber="%s" colnum="%d" time="%s" url="%s">' % ( self.id, candidate_info, self.date, self.divnumber, self.colnum, self.time, self.url )
        result += "\n"
        result += '  <divisioncount for="%d" against="%d" abstentions="%d" spoiledvotes="%d"/>' % ( len(self.for_votes), len(self.against_votes), len(self.abstentions_votes), len(self.spoiled_votes_votes) )
        result += "\n"
        if self.candidate:
            ways_to_list = [ "for" ]
        else:
            ways_to_list = [ "for", "against", "abstentions", "spoiled votes" ]
        for way in ways_to_list:
            votes = None
            if way == "for":
                votes = self.for_votes
            elif way == "against":
                votes = self.against_votes
            elif way == "abstentions":
                votes = self.abstentions_votes
            else:
                votes = self.spoiled_votes_votes
            result += '  <msplist vote="%s">' % ( way )
            result += "\n"
            for msp in votes:
                ids = memberList.match_whole_speaker(msp,str(self.date))
                if ids != None:
                    if len(ids) > 1:
                        raise Exception, "Ambiguous name in division results: "+msp
                    if len(ids) == 1:
                        result += '    <mspname id="%s" vote="%s">%s</mspname>' % ( ids[0], way, msp )
                        result += "\n"
                else:
                    raise Exception, "Odd voter in divison: "+msp
            result += "  </msplist>\n"
        result += '</division>'
        return result

speakers = []

or_prefix = "../../../parldata/cmpages/sp/official-reports/"

dates = []
currentdate = datetime.date( 1999, 5, 12 )

enddate = datetime.date.today()
while currentdate <= enddate:
    dates.append( currentdate )
    currentdate += datetime.timedelta(days=1)

# When we change to the new format...
cutoff_date = datetime.date( 2003, 06, 03 )

# It's helpful to have some way to spot the element that contains the
# right table - hopefully this will do that...

def two_cell_rows( table_tag ):
    rows = table_tag.findAll('tr',recursive=False)
    plausible_rows = 0
    for r in rows:
        cells = r.findAll('td',recursive=False)
        if len(cells) == 2:
            plausible_rows += 1
    return plausible_rows

def centred( t ):
    if t.__class__ == NavigableString:
        return False
    elif t.__class__ == Comment:
        return False
    elif t.__class__ == Tag:
        if t.name == 'center':
            return True
        if t.has_key('align') and t['align'].lower() == 'center':
            return True
        else:
            for c in t.contents:
                if centred(c):
                    return True
        return False
    else:
        raise Exception, "Unknown class: "+str(t.__class__)

def non_tag_data_in( o ):
    if o.__class__ == NavigableString:
        return re.sub('(?ms)[\r\n]',' ',o)
    elif o.__class__ == Tag:
        return ''.join( map( lambda x: non_tag_data_in(x) , o.contents ) )
    elif o.__class__ == Comment:
        return ''

def just_time( non_tag_text ):
    m = re.match( '^\s*(\d?\d):(\d\d)\s*$', non_tag_text )
    if m:
        return datetime.time(int(m.group(1),10),int(m.group(2),10))
    else:
        return None

def full_date( s ):
    stripped = s.strip()
    try:
        return time.strptime(stripped,'%A %d %B %Y')
    except:
        return None

def full_date_without_weekday( s ):
    stripped = s.strip()
    try:
        return time.strptime(stripped,'%d %B %Y')
    except:
        return None

def find_opening_paragraphs( body ):
    
    t = body.find( lambda x: x.name == 'p' and re.search('(?ims)(opened|recommenced).*at\s+([0-9]?[0-9]):([0-9][0-9])',non_tag_data_in(x)) )
    if t:

        if verbose: print "parent is: "+t.parent.name
        if t.parent and t.parent.parent and t.parent.parent.parent:
            if verbose: print "great-grandparent is: " + t.parent.parent.parent.name
            pass
        if verbose: print " siblings: "+str(len(t.parent.contents))
        
        previous_paragraphs = []
        next_paragraphs = []
        previous = t.previousSibling
        while previous:
            if previous.__class__ == Tag and previous.name == 'p':
                previous_paragraphs.insert(0,previous)
            previous = previous.previousSibling
        next = t.nextSibling
        while next:
            if next.__class__ == Tag and next.name == 'p':
                if len(str(next)) > 500:
                    break
                else:
                    next_paragraphs.append(next)
            next = next.nextSibling

        all_opening_paragraphs = previous_paragraphs + [ t ] + next_paragraphs

        useful_opening_paragraphs = previous_paragraphs + [ t ] + next_paragraphs[0:1]

        return useful_opening_paragraphs
        
    else:
        return None
        # raise Exception, "Couldn't find the opening announcement in "+detail_filename

class Parser:

    def __init__(self):
        # This should persist between parses (we're doing them in order...)

        self.major_regexp = None
        self.minor_regexp = None

        self.current_column = None
        self.current_id_within_column = 0

        self.current_anchor = None
        self.current_time = None

        self.current_speech = None
        self.current_division = None
        self.current_heading = None

        self.results_expected = None

        self.started = False

        self.division_number = 0

        self.all_stuff = []
        self.speakers_so_far = []

    def parse_column(self,tag):
        a_name_tag = tag.find('a')
        if a_name_tag:
            if verbose: print "a_name_tag class is: "+str(a_name_tag.__class__)
            a_name = a_name_tag['name']
            if a_name:
                self.current_anchor = a_name

        text_in_tag = non_tag_data_in(tag)

        m = re.search('Col\s*([0-9]+)',text_in_tag)
        if not m:
            # It's probably the last row, with a "Scottish Parliament
            # 2000" notice, or empty for padding at the end...
            if not (re.search('Scottish Parliament',text_in_tag) or re.match('(?ims)^\s*$',text_in_tag)):
                raise Exception, "Couldn't find column from: "+text_in_tag+" prettified, was: "+tag.prettify()

        if m:
            self.current_column = int(m.group(1))
            self.current_id_within_column = 0

    def parse_weird_day( self, body, report_date, url ):

        self.started = False

        # For some reason, this day has a different format from all the rest.

        max_paragraphs = -1
        main_cell = None

        for cell in body.findAll('td'):

            paragraphs = filter( lambda x: x and x.__class__ == Tag and x.name == 'p', cell.contents )

            if len(paragraphs) > max_paragraphs:
                max_paragraphs = len(paragraphs)
                main_cell = cell

        if verbose: print "Picking cell with " + str(max_paragraphs) + " plausible paragraphs."

        # Now go through each of the contents of that <td>, which
        # should be either column indicators or paragraphs with "substance"

        self.parse_substance(main_cell,report_date,url)

    def parse_early_format( self, body, report_date, url ):

        opening_paragraphs = find_opening_paragraphs(body)
        
        opening_table = None
        if opening_paragraphs:
            self.started = False
            t = opening_paragraphs[0]
            if t.parent and t.parent.parent and t.parent.parent.parent:
                great_grand_parent = t.parent.parent.parent
                if great_grand_parent.name == 'table':
                    opening_table = great_grand_parent
        else:
            self.started = True # Since this may just be a continuation...

        # Look for all the tables in the page and pick the one that
        # has the most two cell rows...  (This is mostly right, but
        # for a few cases I've added some empty two cell rows :))
        
        main_table = None
        max_two_cell_rows = -1

        for table in body.findAll('table'):
            plausible_rows = two_cell_rows(table)
            if verbose: print "considering table with: "+str(plausible_rows)+" plausible rows"
            if plausible_rows > max_two_cell_rows:
                main_table = table
                max_two_cell_rows = plausible_rows

        if verbose: print "Picking table with " + str(max_two_cell_rows) + " plausible rows."

        all_rows = []

        if opening_table and opening_table != main_table:
            for row in opening_table.findAll('tr',recursive=False):
                all_rows.append(row)
        for row in main_table.findAll('tr',recursive=False):
            all_rows.append(row)

        volume = None
        number = None

        date = None

        for row in all_rows:

            # if verbose: print "========= row is: "+row.prettify()

            cells = row.findAll('td',recursive=False)

            col_cell = None
            substance_cell = None

            if verbose: print 'cells in row: ' + str(len(cells))
            if len(cells) == 1:
                # This is probably the 'presiding officer opened' bit, or
                # one of the <hr>s at the top.
                # if verbose: print cells[0].prettify()
                substance_cell = cells[0]
            elif len(cells) == 2:
                col_cell = cells[0]
                substance_cell = cells[1]
            else:
                raise Exception, "Unexpected number of cells "+str(len(cells))+" in "+row.prettify()

            # If the substance cell is right aligned, then it's either
            # going to have the date or the volume + number information
            # (more or less)...

            # if verbose: print 'substance cell has name ' + substance_cell.prettify()

            if substance_cell.has_key('align'):
                if substance_cell['align'].lower() == 'right':
                    t = non_tag_data_in(substance_cell)
                    t = " ".join(t.split())
                    m = re.search('Vol (\d+)',t)
                    if m:
                        volume = int(m.group(1))
                    m = re.search('Num (\d+)',t)
                    if m:
                        number = int(m.group(1))
                    if number or volume:
                        continue
                    m = re.search('([0-9]+ \w+ [0-9]+)',t)
                    if m:
                        w = time.strptime(m.group(1),'%d %B %Y')
                        date = datetime.date( w[0], w[1], w[2] )
                    continue

            if col_cell:
                self.parse_column(col_cell)

            # Now deal with the cell with substance.  This is quite a bit trickier...

            self.parse_substance(substance_cell.contents,report_date,url)

    def parse_late_format( self, body, report_date, url ):

        self.started = False

        max_divs = -1
        main_cell = None

        for cell in body.findAll('td'):

            divs = filter( lambda x: x and x.__class__ == Tag and x.name == 'div', cell.contents )

            if len(divs) > max_divs:
                max_divs = len(divs)
                main_cell = cell

        if verbose: print "Picking cell with " + str(max_divs) + " plausible divs."

        # Now go through each of the contents of that <td>, which
        # should be either column indicators or divs with "substance"

        for m in main_cell.contents:

            if m.__class__ == Tag and m.name == 'p':
                non_tag_data = non_tag_data_in(m)
                if re.match('(?ims)^\s*$',non_tag_data):
                    continue
                if full_date_without_weekday(non_tag_data):
                    continue
                self.parse_column(m)
            elif m.__class__ == Tag and m.name == 'div':
                self.parse_substance(m,report_date,url)
            elif m.__class__ == Tag:
                if m.name == 'span' and m['class'] and m['class'].lower() == 'largeheading':
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,non_tag_data_in(m),True)
                    self.current_id_within_column += 1
                    continue
                if m.name == 'span' and m['class'] and m['class'].lower() == 'orcolno':
                    self.parse_column(m)
                    continue
                if m.name == 'br':
                    continue
                non_tag_data = non_tag_data_in(m)
                if re.match('(?ims)^\s*$',non_tag_data):
                    continue
                raise Exception, "Unknown element in contents of main cell: "+m.prettify()
            elif m.__class__ == Comment:
                continue
            else:
                if not re.match('(?ims)^\s*$',str(m)):
                    raise Exception, "Unknown non-empty navigable string in contents of main cell: "+str(m)

    def complete_current(self):
        if self.current_speech:
            self.current_speech.complete()
            self.all_stuff.append(self.current_speech)
            self.current_speech = None
        if self.current_division:
            self.all_stuff.append(self.current_division)
            self.current_division = None
        if self.current_heading:
            self.all_stuff.append(self.current_heading)
            self.current_heading = None

    def make_url(self,url_without_anchor):
        if self.current_anchor:
            return url_without_anchor + "#" + self.current_anchor
        else:
            return url_without_anchor

    def parse_substance(self,contents,report_date,url):

        non_empty_contents = filter(lambda x: x.__class__ != NavigableString or not re.match('^\s*$',x), contents)

        for s in non_empty_contents:

            if verbose:
                print "/#####################"
                if s.__class__ == NavigableString:
                    print "[NavigableString] "+s
                elif s.__class__ == Tag:
                    print "[Tag] "+s.prettify()
                else:
                    print "[Comment]"+str(s)
                print "#####################/"

            if s.__class__ == Comment:
                continue

            non_tag_text = non_tag_data_in(s)

            # In the one weird day, this might be a column number
            # paragraph, so check for that:

            if re.match( '\s*Col\s*[0-9]+\s', non_tag_text ):
                self.parse_column(s)
                continue

            # This might just be the time:
            maybe_time = just_time(non_tag_text)
            if maybe_time:
                self.current_time = maybe_time
                continue

            # I don't think we ever care if there's no displayable text:

            if re.match('(?ims)^\s*$',non_tag_text):
                continue

            # Might this be one of the headings we parsed from the
            # contents page?

            for_matching = re.sub('(?ims)\s+',' ',non_tag_text).strip()

            minor_heading_match = False
            major_heading_match = False

            if major_regexp and re.match(major_regexp,for_matching):
                major_heading_match = True
            elif minor_regexp and re.match(minor_regexp,for_matching):
                minor_heading_match = True

            if major_heading_match or minor_heading_match:
                if verbose: print "WOOHOO! Found an actual heading ("+for_matching+")"
                self.complete_current()
                self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,for_matching,major_heading_match)
                self.current_id_within_column += 1
                continue

            # It's sometimes hard to detect the headings at the
            # beginning of the page, so look out for them in particular...

            if not self.started:

                non_tag_text = re.sub('(?ms)\s+',' ',non_tag_text)
                if verbose: print "Not started, and looking at '" + non_tag_text + "'"

                if re.match('(?ims)\s*Scottish Parliament\s*',non_tag_text):
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,s.prettify(),True)
                    self.current_id_within_column += 1
                    continue

                if full_date(non_tag_text):
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,s.prettify(),False)
                    self.current_id_within_column += 1
                    continue

                if full_date_without_weekday(non_tag_text):
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,s.prettify(),False)
                    self.current_id_within_column += 1
                    continue

                if re.match('^[\s\(]*(Afternoon|Morning)[\s\)]*$',non_tag_text):
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,s.prettify(),False)
                    self.current_id_within_column += 1
                    continue

                m = re.search('(?ims)(opened|recommenced).*at\s+([0-9]?[0-9]):([0-9][0-9])',non_tag_text)
                if m:
                    self.current_time = datetime.time(int(m.group(2),10),int(m.group(3),10))                    
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,s.prettify(),False)
                    self.current_id_within_column += 1
                    continue

            if NavigableString == s.__class__ or s.name == 'sup' or s.name == 'sub' or s.name == 'br':
                if self.results_expected:
                    if NavigableString == s.__class__:
                        # Then just add that name to the votes...
                        stripped = str(s).strip()
                        stripped = re.sub('(?ms)\s+',' ',stripped)
                        if len(stripped) > 0: # At the end of a list, we might get an empty one...
                            self.current_division.add_votes(self.results_expected,stripped)
                        continue
                    elif s.name == 'br':
                        # We can ignore that, it's just dividing up
                        # the names in the list of votes.
                        continue
                self.results_expected = None
                if NavigableString == s.__class__:
                    text_to_add = s
                else:
                    text_to_add = str(s)
                if self.current_speech:
                    self.current_speech.add_text_to_last_paragraph(text_to_add)
                else:
                    # If it's just a break, it's safe to ignore it in this situation:
                    if not (s.__class__ == Tag and s.name == 'br'):
                        raise Exception, "Wanted to add '"+text_to_add+"' to the current speech, but there wasn't a current speech."
                continue

            if verbose: print '- '+s.name+" <-- got a tag with this name"

            # So, there might be all manner of things here.  Mostly
            # they will be <p>, which is likely to be a speech or a
            # continuing speech.  If it is <center> or something
            # containing a <center> it is likely to be a heading,
            # however....

            if centred(s):
                self.results_expected = None
                if verbose: print "- Centred, so a heading or something:\n" + s.prettify()
                non_tag_data = non_tag_data_in(s)
                if not re.match('(?ims)^\s*$',non_tag_data):
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,s.prettify(),False)
                    self.current_id_within_column += 1
                continue

            if len(s.contents) == 0:
                continue

            # As above, there may be empty NavigableStrings in the
            # contents of s, so filter them out:

            s_contents = filter(lambda x: x.__class__ != Comment and (x.__class__ != NavigableString or not re.match('^\s*$',x)), s.contents)

            if s.name == 'p' and len(s_contents) == 1 and s_contents[0].__class__ == Tag and (s_contents[0].name == 'em' or s_contents[0].name == 'i'):
                if verbose: print "Got what looks like some narrative..."
                # Then this is probably some narrative, so create
                # a speech but don't set a speaker.
                self.results_expected = None
                self.complete_current()
                self.current_speech = Speech(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,self)
                self.started = True
                self.current_id_within_column += 1
                self.current_speech.add_paragraph(s.contents[0].prettify())
                continue

            # Sometimes we get lists or audience reaction in the
            # speech, so just add them.

            if s.name == 'ol' or s.name == 'i' or s.name == 'ul' or s.name == 'table':
                self.results_expected = None
                if self.current_speech:
                    self.current_speech.add_text_to_last_paragraph( s.prettify() )
                else:
                    self.complete_current()
                    self.current_speech = Speech(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,self)
                    self.current_id_within_column += 1
                    self.current_speech.add_text_to_last_paragraph( s.prettify() )
                continue

            if s.name != 'p':
                self.results_expected = None
                # If it's empty, we probably don't care either...
                just_text = non_tag_data_in(s)
                if re.match('^\s*$',just_text):
                    continue
                if re.match('^\s*(Access Keys|Accessibility|Sitemap)\s*$',just_text):
                    continue
                if re.match('^\s*\s*$',just_text):
                    continue
                if full_date_without_weekday:
                    continue
                else:
                    raise Exception, "There was an unexpected s, which was: "+s.name+" with content: "+s.prettify()

            # So now this must be a paragraph...

            # Sometimes there's a pointless <br/> at the start of the <p>.
            if len(s_contents) > 0 and s_contents[0].__class__ == Tag and s_contents[0].name == 'br':
                if verbose: print "- removing leading <br> from contents..."
                s_contents = s_contents[1:]

            if len(s_contents) == 0:
                if verbose: print "- tag is now empty, so continuing"
                continue

            # If there is a <strong> element in the first place, that is
            # probably the name of a speaker, and this is the beginning of
            # a new speech, so separate the first element from the rest:

            first = s_contents[0]
            rest = s_contents[1:]

            if first.__class__ == Tag:
                if verbose: print "- first's name is "+first.name

            # This may be the results of a division, so test for that.

            if first.__class__ == Tag and (first.name == 'strong' or first.name == 'b') and (first.string):

                so_far = ''

                # Fetch the next sibling until we run out or they stop being "<strong>":
                next = first
                while True:
                    if not next:
                        break
                    if next.__class__ == Tag and (next.name == 'strong' or next.name == 'b') and (next.string):
                        so_far += next.string
                    elif next.__class__ == NavigableString:
                        if re.match('(?ms)^\s*$',str(next)):
                            so_far += str(next)
                        else:
                            break
                    next = next.nextSibling

                if verbose: print "Considering as division indicator: '"+so_far

                division_report = False

                if re.match('(?ms)^\s*F\s*OR[:\s]*$',so_far):
                    if verbose: print "Got FOR"
                    division_report = True
                    self.results_expected = 'FOR'
                elif re.match('(?ms)^\s*A\s*GAINST[:\s]*$',so_far):
                    if verbose: print "Got AGAINST"
                    division_report = True
                    self.results_expected = 'AGAINST'
                elif re.match('(?ms)^\s*A\s*BST?ENTIONS?[:\s]*$',so_far):
                    if verbose: print "Got ABSTENTIONS"
                    division_report = True
                    self.results_expected = 'ABSTENTIONS'
                elif re.match('(?ms)^\s*S\s*POILED\s+VOTES?[:\s]*$',so_far):
                    if verbose: print "Got SPOILED VOTES"
                    division_report = True
                    self.results_expected = 'SPOILED VOTES'
                else:
                    if verbose: print "Didn't match any in: '"+so_far+"'"
                if division_report and self.results_expected:
                    if not self.current_division:
                        if verbose: print '- Creating new division: ' + so_far
                        self.complete_current()
                        self.current_division = Division(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,self.division_number)
                        self.division_number += 1
                    continue

            if first.__class__ == Tag and (first.name == 'strong' or first.name == 'b'):

                # Now we know it's probably a new speaker...

                self.results_expected = None

                # Remove all the empty NavigableString objects from rest:
                rest = filter( lambda x: not (x.__class__ == NavigableString and re.match('^\s*$',x)), rest )

                # This is a bit complicated - if the current speaker
                # only has a name, then this is probably a
                # continuation of the name, broken by a column
                # boundary...

                speaker = non_tag_data_in(first)
                if verbose: print "first use of speaker: '" + speaker + "'"

                while len(rest) > 0 and rest[0].__class__ == Tag and (rest[0].name == 'strong' or rest[0].name == 'b'):
                    # In any case, sometimes there are two <strong>s
                    # next to each other that make up the name...
                    if verbose: print "rest is: " + str(rest)
                    if verbose: print "speaker is: "+ str(speaker)
                    speaker = speaker + non_tag_data_in(rest[0])
                    rest = rest[1:]

                if verbose: print "ended up with speaker: '" + speaker + "'"
                question_number = None

                m = re.match('^\s*([\d ]+)\.?\s*(.*)$',speaker)
                if m:
                    # Then this is probably a numbered question...
                    number = re.sub('(?ms)\s','',m.group(1))
                    if len(number) > 0:
                        if verbose: print '- MATCHED! (question number was "' + number + "'"
                        question_number = int(number)
                        speaker = m.group(2)

                added_to_name = False

                if self.current_speech and self.current_speech.no_text_yet():
                    if verbose: print "- No text in current speech yet, so add to the name."
                    self.current_speech.set_speaker(self.current_speech.name+speaker)
                    added_to_name = True
                else:
                    if verbose: print "- Either there wasn't a current speech ("+str(self.current_speech)+") or there was text in it."
                    self.complete_current()
                    self.current_speech = Speech(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,self)
                    self.current_id_within_column += 1

                self.started = True

                if question_number:
                    self.current_speech.set_question_number(question_number)

                # When voting for particular candidates the results
                # come up like this; maybe we should treat them as a
                # division...  These come up in:
                #    sp1999-05-13.xml
                #    sp1999-05-19.xml
                #    sp2000-10-26.xml
                #    sp2001-11-22.xml
                #    sp2003-05-21.xml
                #    sp2006-01-12.xml
                #    sp2007-05-16.xml

                mcandidate = re.search('VOTES? FOR (.*)',speaker)
                if mcandidate:
                    self.current_speech.add_paragraph("<b>"+speaker.strip()+"</b>")
                    if verbose: "Found votes for a candiate: "+speaker
                    division_report = True
                    self.results_expected = 'FOR'
                    if verbose: print '- Creating new division for candidate: ' + so_far
                    self.complete_current()
                    self.current_division = Division(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,self.division_number)
                    self.current_division.set_candidate(mcandidate.group(1))
                    self.division_number += 1
                    continue
                elif not added_to_name:
                    self.current_speech.set_speaker(speaker)

                add_to_last = False

                for r in rest:
                    maybe_time = just_time(non_tag_data_in(r))
                    if maybe_time:
                        self.current_time = maybe_time
                        continue
                    if r.__class__ == NavigableString:
                        if add_to_last:
                            self.current_speech.add_text_to_last_paragraph(r)
                        else:
                            self.current_speech.add_paragraph(r)
                        add_to_last = True
                    elif r.name == 'strong':
                        if len(r.contents) == 1:
                            s = r.string or non_tag_data_in(r)
                            if verbose: print "- r.string is: "+str(s)
                            # if verbose: print "- r prettified is: "+r.prettify()
                            if not re.match('^\s*$',s):
                                # My best guess is that this is just emphasis within the paragraph...
                                self.current_speech.add_text_to_last_paragraph('<strong>'+s+'</strong>')
                                add_to_last = True
                                if verbose: print "- WARNING: Non-empty <strong> in rest " + str(r.__class__) + " in " + r.prettify()
                        else:
                            raise Exception, "len(tag.contents) > 1 in " + r.prettify()
                    elif r.name == 'sup':
                        self.current_speech.add_text_to_last_paragraph('<sup>'+str(r)+'</sup>')
                        add_to_last = True
                    elif r.name == 'sub':
                        self.current_speech.add_text_to_last_paragraph('<sub>'+str(r)+'</sub>')
                        add_to_last = True
                    elif r.name == 'ol' or r.name == 'ul' or r.name == 'table':
                        self.current_speech.add_paragraph('<div>'+str(r)+'</div>')
                    elif r.name == 'br':
                        self.current_speech.add_text_to_last_paragraph('<br/>')
                        add_to_last = True
                    elif r.name == 'b':
                        self.current_speech.add_text_to_last_paragraph('<b>'+r.string+'</b>')
                        add_to_last = True
                    elif r.name == 'em':
                        self.current_speech.add_text_to_last_paragraph('<em>'+r.string+'</em>')
                        add_to_last = True
                    elif r.name == 'i':
                        self.current_speech.add_text_to_last_paragraph('<i>'+r.string+'</i>')
                        add_to_last = True
                    elif r.name == 'a':
                        # These are just <A NAME="MakeMarkAuto_11"></A>
                        pass
                    elif r.name == 'p':
                        if verbose: print "- Adding paragraph."
                        self.current_speech.add_paragraph( r.prettify() )
                    else:
                        raise Exception, "Strange, item in rest is of class " + str(r.__class__) + " is " + r.prettify() +" from "+s.prettify()

                continue

            if s.name == 'p' and self.results_expected:
                if verbose: print "- We were expecting results and found: " + s.prettify()
                for v in s.contents:
                    if v.__class__ == NavigableString:
                        stripped = str(v).strip()
                        stripped = re.sub('(?ms)\s+',' ',stripped)
                        if verbose: print "  - in contents: "+str(stripped)
                        if len(stripped) > 0: # At the end of a list, we might get an empty one...
                            self.current_division.add_votes(self.results_expected,stripped)
                # There might be some more in the next substance cell
                # so don't reset results_expected yet.
                continue

            if s.__class__ == Tag and s.name == 'p':
                if self.started:
                    if self.current_speech:
                        self.current_speech.add_paragraph( s.string or s.prettify() )
                    else:
                        if verbose:
                            print "- No current speech (and we'd started) but got a bare paragraph!"
                            print s.prettify()
                else:
                    self.complete_current()
                    self.current_heading = Heading(self.current_id_within_column,self.current_column,self.current_time,self.make_url(url),report_date,s.prettify(),False)
                    self.current_id_within_column += 1


def get_heading_regexps(contents_filename):

    # Open the contents page and grab the debate headings.  This
    # probably isn't strictly necessary, but might help:

    fp = open(contents_filename)
    html = fp.read()
    fp.close()

    html = re.sub('(?i)&nbsp;',' ', html)

    soup = ScottishParliamentSoup( html, fromEncoding='iso-8859-15' )
    # Find the table with the most two-cell rows:

    main_contents_table = None
    max_two_cell_rows = -1

    for table in soup.findAll('table'):
        plausible_rows = two_cell_rows(table)
        if plausible_rows > max_two_cell_rows:
            main_contents_table = table
            max_two_cell_rows = plausible_rows

    major_headings = []
    minor_headings = []

    for row in main_contents_table.findAll('tr'):
        cells = row.findAll('td',recursive=False)
        if len(cells) == 2:
            c = cells[0]
            # links = c.findAll('a')
            # for link in links:
            text = non_tag_data_in(c)
            text = re.sub('(?ims)\s+',' ',text)
            if re.match('^\s*$',text):
                continue
            # Just ignore the listed MSP names, we only care about
            # the headings...
            msp_names = memberList.match_whole_speaker(text,str(d))
            if msp_names != None and len(msp_names) > 0:
                continue
            if text.upper() == text:
                major_headings.append(text.strip())
            else:
                minor_headings.append(text.strip())

    if verbose:
        print "On "+str(d)
        print "MAJOR HEADINGS:"
        for h in major_headings:
            print "   "+h
        print "Minor Headings:"
        for h in minor_headings:
            print "   "+h

    major_escaped = map( lambda x: re.escape(x), major_headings )
    minor_escaped = map( lambda x: re.escape(x), minor_headings )

    major_regexp = None
    minor_regexp = None

    if len(major_escaped) > 0:
        major_regexp = re.compile("(?ims)^("+"|".join(major_escaped)+")$")
        if verbose: print "major_regexp is: "+major_regexp.pattern
    if len(minor_escaped) > 0:
        minor_regexp = re.compile("(?ims)^("+"|".join(minor_escaped)+")$")
        if verbose: print "minor_regexp is: "+minor_regexp.pattern
    
    return ( major_regexp, minor_regexp )

# --------------------------------------------------------------------------
# End of function and class definitions...

class ScottishParliamentSoup(BeautifulSoup):

    # None of these seem to work in the way that I expect from the
    # documentation, so just use the default parser..

    # BeautifulSoup.NESTABLE_TAGS['p'] = [ 'center', 'td'  ]
    # BeautifulSoup.NESTABLE_TAGS['td'].append( 'center' )
    # BeautifulSoup.NESTABLE_TAGS['center'].append( 'td' )
    # BeautifulSoup.NESTABLE_TAGS['center'].append( 'p' )
    pass

def compare_filename(a,b):
    ma = re.search('_(\d+)\.html',a)
    mb = re.search('_(\d+)\.html',b)
    if ma and mb:
        mai = int(ma.group(1))
        mbi = int(mb.group(1))
        if mai < mbi:
            return -1
        if mai > mbi:
            return 1
        else:
            return 0
    else:
        raise Exception, "Couldn't match filenames: "+a+" and "+B

force = False

last_column_number = 0
    
for d in dates:

    xml_output_directory = "../../../parldata/scrapedxml/sp/"
    output_filename = xml_output_directory + "sp" + str(d) + ".xml"

    if (not force) and os.path.exists(output_filename):
        continue

    contents_filename = or_prefix + "or" +str(d) + "_0.html"

    filenames = glob.glob( or_prefix + "or" + str(d) + "_*.html" )
    filenames.sort(compare_filename)

    if len(filenames) == 0:
        continue

    contents_filename = filenames[0]

    major_regexp, minor_regexp = get_heading_regexps(contents_filename)

    all = []

    parser = Parser()

    parser.current_column = last_column_number

    parser.major_regexp = major_regexp
    parser.minor_regexp = minor_regexp

    # Get the original URLs:

    original_urls = []

    urls_filename = or_prefix + "or" + str(d) + ".urls"
    fp = open(urls_filename)
    for line in fp.readlines():
        url = line.rstrip()
        if len(url) > 0:
            original_urls.append(url)
    fp.close()

    if verbose:
        for o in original_urls:
            print "original url was: "+o

        for f in filenames:
            print "filename was: "+f

    detail_filenames = filenames[1:]

    #        # There are a few odd files:
    # 
    #        # 2001-09-26 <-- excellent example with lots of different languages :)
    # 
    #        if str(d) == '1999-05-12' or str(d) == '1999-06-02' or str(d) == '1999-09-01':
    #            # Those just have lists of names...
    #            continue
    # 
    #        if str(d) == '2003-05-15':
    #            # That page is 404, apparently
    #            continue

    for i in range(0,len(detail_filenames)):

        detail_filename = detail_filenames[i]
        original_url = original_urls[i+1]

        if re.search('1999-05-12_[12]',detail_filename):
            continue # It's just a table of names...
        elif re.search('1999-06-02_[12]',detail_filename):
            continue # More lists of names...
        elif re.search('1999-09-01_[12]',detail_filename):
            continue # More lists of names...
        elif re.search('2000-07-06_[23]',detail_filename):
            continue # Those are two annexes which are contained in main report anyway
        elif re.search('2003-05-15',detail_filename):
            continue # That's 404

        fp = open(detail_filename)
        html = fp.read()
        fp.close()

        # Swap the windows-1252 euro and iso-8859-1 pound signs for the
        # equivalent entities...

        html = re.sub('\x80','&#8364;', html) # windows-1252 euro
        html = re.sub('\xA3','&#163;', html) # iso-8859 pound (currency) sign
        html = re.sub('\xB0','&#176;', html) # iso-8859 degree sign
        html = re.sub('\x97','&#8212;', html) # windows-1252 euro

        # Remove all the font tags...
        html = re.sub('(?i)</?font[^>]*>','', html)

        # Remove all the <u> tags...
        html = re.sub('(?i)</?u>','', html)

        # Change non-breaking spaces to normal spaces:
        html = re.sub('(?i)&nbsp;',' ', html)

        # In the earlier format, the <td> with the text sometimes doesn't
        # start with a <p>...
        html = re.sub('(?ims)(<td[^>]*>)\s*(<strong)',r'\1<p>\2',html)

        # The square brackets around things like 'Laughter' and 'Applause'
        # tend to come outside the <i></i>, which is rather inconvenient.
        html = re.sub('(?ims)\[\s*<i>([^<]*)</i>[\s\.]*\]',r'<i>[\1]</i>',html)

        # Similarly, swap <em><p></p></em> for <p><em></em></p>
        html = re.sub('(?ims)<em>\s*<p>([^<]*)</p>\s*</em>',r'<p><em>[\1]</em></i>',html)

        # Similarly, swap <strong><p></p></strong> for <p><strong></strong></p>
        html = re.sub('(?ims)<strong>\s*<p>([^<]*)</p>\s*</strong>',r'<p><strong>[\1]</strong></i>',html)

        # Or just remove any that doesn't catch:
        html = re.sub('(?ims)<em>\s*<p>',r'<p><em>',html)
        html = re.sub('(?ims)</p>\s*</em>',r'</em></p>',html)

        # The <center> tags are often misplaced, which completely
        # breaks the parse tree.
        # FIXME: this might break the detection of headings...
        html = re.sub('(?ims)<center>\s*<p','<p align="center"',html)
        html = re.sub('(?ims)<p>\s*<center','<p align="center"',html)
        html = re.sub('(?ims)</?center>','',html)

        # There are some useless <a name=""> tags...

        html = re.sub('(?ims)<a name="MakeMark[^>]+>[^<]*</a>','',html)

        # And sometimes they forget the "<strong>" before before
        # introducing a speaker:

        html = re.sub('(?ims)<p>([^<]*)</strong>',r'<p><strong>\1</strong>',html)

        log_speaker("------------------------------------",str(d),"")

        # Some of these seem to be windows-1252, some seem to be
        # iso-8859-1.  The decoding you set here doesn't actually seem to
        # solve these problems anyway (FIXME)...

        soup = ScottishParliamentSoup( html, fromEncoding='iso-8859-15' )

        #    nestable_keys = soup.NESTABLE_TAGS.keys()
        #    nestable_keys.sort()
        #
        #    for i in nestable_keys:
        #        l = soup.NESTABLE_TAGS[i]
        #        if verbose: print str(i) + " can nest in [ " + ', '.join(l) + " ]"
        #
        #    for i in soup.RESET_NESTING_TAGS:
        #        if verbose: print "soup.RESET_NESTING_TAGS has: "+str(i)

        body = soup.find('body')

        if body == None:
            print "body was None for: "+str(d)
            continue

        if verbose:
            print "----- " + detail_filename
            print soup.prettify()
            print "---------------------------------"

        elements_before = len(parser.all_stuff)

        if str(d) == '2004-06-30':
            parser.parse_weird_day( body, d, original_url )
        elif d >= cutoff_date:
            parser.parse_late_format( body, d, original_url )
        else:
            parser.parse_early_format( body, d, original_url )

        elements_added = len(parser.all_stuff) - elements_before

        last_column_number = parser.current_column

        if elements_added < 3 and not re.search('1999-07-02_1',detail_filename):
            raise Exception, "Very suspicious: only "+str(elements_added)+" added by parsing: "+detail_filename

        if verbose:
            print "=== Displaying results from " + detail_filename
            print "=== " + original_url

    parser.complete_current()

    o = open(output_filename,"w")

    o.write('''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE publicwhip [

<!ENTITY pound   "&#163;">
<!ENTITY euro    "&#8364;">

<!ENTITY agrave  "&#224;">
<!ENTITY aacute  "&#225;">
<!ENTITY egrave  "&#232;">
<!ENTITY eacute  "&#233;">
<!ENTITY ecirc   "&#234;">
<!ENTITY iacute  "&#237;">
<!ENTITY ograve  "&#242;">
<!ENTITY oacute  "&#243;">
<!ENTITY uacute  "&#250;">
<!ENTITY Aacute  "&#193;">
<!ENTITY Eacute  "&#201;">
<!ENTITY Iacute  "&#205;">
<!ENTITY Oacute  "&#211;">
<!ENTITY Uacute  "&#218;">
<!ENTITY Uuml    "&#220;">
<!ENTITY auml    "&#228;">
<!ENTITY euml    "&#235;">
<!ENTITY iuml    "&#239;">
<!ENTITY ouml    "&#246;">
<!ENTITY uuml    "&#252;">
<!ENTITY fnof    "&#402;">

<!ENTITY nbsp    "&#160;">
<!ENTITY shy     "&#173;">
<!ENTITY deg     "&#176;">
<!ENTITY middot  "&#183;">
<!ENTITY ordm    "&#186;">
<!ENTITY ndash   "&#8211;">
<!ENTITY mdash   "&#8212;">
<!ENTITY lsquo   "&#8216;">
<!ENTITY rsquo   "&#8217;">
<!ENTITY ldquo   "&#8220;">
<!ENTITY rdquo   "&#8221;">
<!ENTITY hellip  "&#8230;">
<!ENTITY bull    "&#8226;">

<!ENTITY acirc   "&#226;">
<!ENTITY Agrave  "&#192;">
<!ENTITY Aring   "&#197;">
<!ENTITY aring   "&#229;">
<!ENTITY atilde  "&#227;">
<!ENTITY Ccedil  "&#199;">
<!ENTITY ccedil  "&#231;">
<!ENTITY Egrave  "&#200;">
<!ENTITY Icirc   "&#206;">
<!ENTITY icirc   "&#238;">
<!ENTITY Igrave  "&#204;">
<!ENTITY igrave  "&#236;">
<!ENTITY ntilde  "&#241;">
<!ENTITY ocirc   "&#244;">
<!ENTITY oelig   "&#339;">
<!ENTITY Ograve  "&#210;">
<!ENTITY Oslash  "&#216;">
<!ENTITY oslash  "&#248;">
<!ENTITY Scaron  "&#352;">
<!ENTITY scaron  "&#353;">
<!ENTITY sup3    "&#179;">
<!ENTITY ugrave  "&#249;">
<!ENTITY yacute  "&#253;">
]>

<publicwhip>

''')
    
    for i in parser.all_stuff:
        if i.__class__ == Speech or i.__class__ == Heading or i.__class__ == Division:
            o.write( "\n" + i.to_xml() + "\n" )
    o.write("\n\n</publicwhip>\n")
    o.close()

    retcode = call( [ "xmlstarlet", "val", output_filename ] )
    if retcode != 0:
        raise Exception, "Validating "+output_filename+" for well-formedness failed."
