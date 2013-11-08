#!/usr/bin/env python

__author__="Neil Horner"

from urllib import quote_plus
import re
from bs4 import BeautifulSoup
from lxml import etree
import datetime
from resolvemembernames import memberList
from optparse import OptionParser
import glob
import pprint


class Parse_sp_written:

    '''
    Parses SP written answers from html fetched from Scottish parliamernt website
    into daily XML files

    '''

    def __init__(self, warn):

        '''Parses SP written answers

        :param warn: switch on warnings for when some info is missing eg. speaker id
        :type warn: bool
        '''

        self.warn = warn
        wa_prefix = "../../../parldata/cmpages/sp/written-answers/"
        self.xml_output_directory = "../../../parldata/scrapedxml/sp-written/"
        self.ques_src_prefix = "http://www.scottish.parliament.uk/parliamentarybusiness/28877.aspx?SearchType=Advance&ReferenceNumbers="
        self.day_src_prefix = 'http://www.scottish.parliament.uk/parliamentarybusiness/28877.aspx'
        self.speaker_id_format = "uk.org.publicwhip/spwa/{0}.{1}.{2}{3}"

        #get the filenames to parse
        self.files_to_parse = glob.glob( wa_prefix + "*html" )

        self.create_xml(self.group_by_date(self.process_html()))


    def test(self, q):

        '''Take a look at the question attributes
        '''
        pprint.pprint(vars(q))


    def process_html(self):

        '''Gets all the html files, checks for correct file with BeautifulSoup
        passes them on to be processed

        :returns parsed_questions: List of question objects
        '''

        for html_file in self.files_to_parse:

            with open(html_file, 'r') as the_page:
                    soup = BeautifulSoup(the_page, "html5lib")

            parsed_questions = []

            soup_gvresults =  soup.findAll('tr', {'id' : re.compile('MAQA_Search_gvResults.*')})
            print type(soup_gvresults)

            if not soup_gvresults:
                if self.warn:
                    print(html_file + " does not seem to the right kind of file, or there are no questions in it")
            else:
                for q in self.get_q_and_a(soup_gvresults):
                    parsed_questions.append(q)

        return parsed_questions


    def get_q_and_a(self, soup_gvresults):

            '''Extracts all the relevant bits of the html file using BeautifulSoup
            :param soup_gvresults: bs4.element.ResultSet
            :returns yields question object
            '''
            for soup_question in soup_gvresults:

                q = self.Question()

                h = soup_question.find('div', {'id' : re.compile('.*pnlQuestionHeader')})

                if h:
                    header = h.find('span', {'id' : re.compile('MAQA_Search_gvResults.*')})
                    #header = self.get_soup_elem(h, 'span', 'MAQA_Search_gvResults.*')

                if header:
                    q.header = header.string
                    self.parse_question_header(q)

                ques_text = soup_question.find('span', {'id' : re.compile('.*lblQuestionTitle')})
                if ques_text:
                    #only select content within <p> tags to avoid junk before it
                    ps = []
                    for rp in [p.renderContents().decode("utf8") for p in ques_text.findAll('p')]:
                        ps.append(''.join(('<p>', rp, '</p>')))
                    q.ques_text = ''.join(ps)

                answer_date = soup_question.find('span', {'id' : re.compile('.*lblAnswerDate')})
                if answer_date:
                    q.answer_date = datetime.datetime.strptime(answer_date.string, '%d/%m/%Y')

                reply_text = soup_question.find('span', {'id' : re.compile('.*lblAnswerText')})
                if reply_text:
                    #All of the contents of .*lblAnswerText are part of the reply
                    q.reply_text = reply_text.renderContents().decode("utf8")

                answered_by = soup_question.find('span', {'id' : re.compile('.*lblAnswerByMSP')})
                if answered_by:
                    q.answered_by = unicode(answered_by.string)
                    q.answered_by_id = self.get_person_id(q.answered_by, q.answer_date )
                #self.test(q)
                yield q


    def parse_question_header(self, q):

        '''Parse the question header with the following form:
        "Question S4W-08976: Marco Biagi, Edinburgh Central, Scottish National Party, Date Lodged: 01/08/2012"
        and sets properties on question object

        :param q: question object
        '''

        parts = [p.strip() for p in re.split(':|, |Question', q.header)]

        if parts[1]:
            q.ques_id = parts[1]
        if parts[2]:
            q.speaker_name = parts[2]
        if parts[-1]:
            q.date_lodged = datetime.datetime.strptime(parts[-1], '%d/%m/%Y')
        if parts[-3]:
            q.speaker_party = self.party_name_acronym(parts[-3])

        #Sometimes there are commas within the constituency name, which increases number of elements in the list
        if parts[3: -3]:
            q.speaker_const = ','.join(parts[3: -3])
        q.speaker_id = self.get_person_id(q.speaker_name, q.date_lodged, q.speaker_const, q.speaker_party)


    def get_person_id(self, speaker_name, date, speaker_const="", speaker_party=""):

        '''Finds an id for a speaker.
        If warnings on, prints warnings if multiple or none found

        :param speaker name
        :param date: datetime object
        :param speaker_const: speaker constituency
        :param speaker party: str
        :returns speaker_id: str
        '''
        d = date.strftime('%Y-%m-%d')

        if speaker_const:
            search_string =  "{0} ({1}) ({2})".format(speaker_name, speaker_const, speaker_party)
        else:
            #Only speaker name given for replies
            search_string = speaker_name

        possible_ids = memberList.match_whole_speaker(search_string, d)

        if not possible_ids:
            if self.warn:
                print('no speaker id found for: {0}\n'.format(search_string))
            return "unknown"
        elif len(possible_ids) > 1:
            if self.warn:
                print ('multiple possible IDs found for name: {0} , date: {1}'.format(
                                                            search_string, d))
                print ("\n".join(possible_ids))
            return possible_ids[0]
        else:
            return possible_ids[0]


    def create_xml(self, day_grouped_qs):

        '''Takes a list of question objects and creates the XML
        :param day_grouped_qs: an iterator - date:question object list
        '''
        for date, qList in day_grouped_qs:

            root = etree.Element("publicwhip")
            src = etree.SubElement(root, "source")
            src.set("url", self.get_source_url(date))

            self.major_heading(root, "Written Answers " + date.strftime('%A %d %B %Y'), "1", date )
            self.major_heading(root, "Scottish Executive", "2", date )

            for q in qList:
                self.question_xml(root, q)
                self.reply_xml(root, q)
            file_date = date.strftime('%Y-%m-%d')
            self.xml_to_file("spwa" + file_date + '.xml', root)


    def question_xml(self, root, q):

        '''creates xml for question
        :param root: etree.Element
        :param q: question object
        '''

        self.minor_heading(root, q.ques_id, q.date_lodged)

        ques = etree.SubElement(root, 'ques')
        q_num = 0; #According to mhl SP q&as with multiple questions or replies are seperated, so this should always be 0

        ques.set("id", self.speaker_id_format.format(
                            q.date_lodged.strftime('%Y-%m-%d'),
                            q.ques_id,
                            'q',
                            str(q_num)))

        ques.set("speakerid", q.speaker_id)
        ques.set("speakername", "{0} ({1}) ({2})".format(
                            q.speaker_name,
                            q.speaker_const,
                            q.speaker_party))

        ques.set("spid", q.ques_id)
        ques.set("url", self.ques_src_prefix + q.ques_id)
        ques.text = q.ques_text
#         if q.ques_paragraphs:
#             for paragraph in q.ques_paragraphs:
#                 p = etree.Element('p')
#                 p.text = paragraph
#                 ques.append(p)


    def reply_xml(self, root, q):

        '''creates xml for reply
        :param root: etree.Element
        :param q: question object
        '''

        reply = etree.SubElement(root, 'reply')
        r_num = 0;
        reply.set("id", self.speaker_id_format.format(
                            q.date_lodged.strftime('%Y-%m-%d'),
                            q.ques_id,
                            "r",
                            str(r_num)))

        reply.set("speakerid", q.answered_by_id)
        reply.set("speakername", q.answered_by)
        reply.set("url", self.ques_src_prefix + q.ques_id)
        reply.text = q.reply_text
#         if q.reply_paragraphs:
#             for paragraph in q.reply_paragraphs:
#                 p = etree.Element('p')
#                 p.text = paragraph
#                 reply.append(p)


    def xml_to_file(self, name, root):

        '''Writes xml to file
        :param name: file name
        :param root: etree.Element
        :raises IOError: if file can't be written
        '''

        try:
            f = open(self.xml_output_directory + name, 'w')
            f.write(self.doc_typedef())
            f.write(etree.tostring(root, pretty_print=True))
            f.close()
        except IOError:
            print "XML file cannot be written to file"


    def major_heading(self, root, text, mah_number, date):

        '''creates major heading elements and adds to XML tree
        :param root: etree.Element
        :param text: node text
        :param mah_number: major heading number
        :param date: datetime object
        '''

        mah = etree.SubElement(root, "major-heading")
        mah.set("id", "uk.org.publicwhip/spwa/" + date.strftime('%Y-%m-%d') + '.' + mah_number + '.mh')
        mah.set("nospeaker", "True")
        mah.set("url", self.get_source_url(date))
        mah.text = text


    def minor_heading(self, root, ques_id, date ):

        '''creates major heading elements and adds to XML tree.
        In SP written Q&As, it seems as if there's no longer a useful title
        for the minor-heading text, so just make it eg. "Question S4W-01234"
        '''
        mih = etree.SubElement(root, "minor-heading")
        mih.set("id", "uk.org.publicwhip/spwa/" + date.strftime('%Y-%m-%d') + '.' + ques_id + '.h')
        mih.set("nospeaker", "True")
        mih.set("url", self.ques_src_prefix + ques_id)
        mih.text = 'Question ' + ques_id


    def get_source_url(self, date):

        '''Gets source url for a given day of questions
        :param date: datetime object
        :returns full_url: str
        '''
        data = {'SearchType': 'Advance',
        'DateFrom': date.strftime('%D') + " 12:00:00 AM",
        'DateTo': date.strftime('%D') + " 11:59:59 PM",
        'SortBy': 'DateSubmitted',
        'Answers': 'All',
        'SearchFor': 'All',
        'ResultsPerPage': '1000',
        'SearchFor': 'WrittenQuestions'}

        query_string = "&".join(quote_plus(k) + "=" + quote_plus(v)
        for k, v in data.items())

        full_url =  self.day_src_prefix + "?" + query_string
        return full_url


    def group_by_date(self, questions):

        '''Orders question objects by day lodged

        :param questions: list of question objects
        :returns: an iterator: date:[question object list].
        '''

        grouped_qs = {}

        for q in questions:
            if q.date_lodged in grouped_qs:
                grouped_qs[q.date_lodged].append(q)
            else:
                grouped_qs[q.date_lodged] = [q]

        return grouped_qs.iteritems()


    class Question:

        '''Class to hold info on each question along with answers.
        defaults set in case they cannot be found from scraping
        '''

        def __init__(self):
            self.ques_id = ""
            self.date_lodged = ""
            self.header = ""
            self.speaker_party = ""
            self.speaker_const = ""
            self.speaker_name = ""
            self.speaker_id = ""
            self.ques_text = ""
            self.answered_by = ""
            self.answered_by_id = ""
            self.reply_text = ""
            self.answer_date = ""


    def party_name_acronym(self, party_name):

            '''Converts full party name from scraping to acronym as found in sp-members.xml

            :param party_name: full party name eg. Scottish National Party
            :returns party acronym or name: return party_name if acronym cannot be resolved
            '''

            names_acro = {
                'Scottish Conservative and Unionist Party':'Con',
                'Scottish Labour':'Lab',
                'Scottish Liberal Democrats':'LDem',
                'Scottish National Party':'SNP',
                'Scottish Socialist Party':'SSP',
                'Scottish Green Party':'Green',
                'Independent':'Independent',
                'Scottish Senior Citizens Unity Party':'SSCUP',
                '?':'SCCUP',#Not availble in search list on SP page
                'Solidarity Group':'Sol', # Not present in sp-members.xml but has results from scraping
            }

            if party_name in names_acro:
                return names_acro[party_name]
            else:
                return party_name


    def doc_typedef(self):
        dtd_string ="""<?xml version="1.0" encoding="utf-8"?>
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
        <!ENTITY aelig   "&#230;">
        <!ENTITY dagger  "&#8224;">
        <!ENTITY reg     "&#174;">
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
        <!ENTITY sup1    "&#185;">
        <!ENTITY sup2    "&#178;">
        <!ENTITY sup3    "&#179;">
        <!ENTITY ugrave  "&#249;">
        <!ENTITY ucirc   "&#251;">
        <!ENTITY Ugrave  "&#217;">
        <!ENTITY yacute  "&#253;">
        <!ENTITY frac12  "&#189;">
        <!ENTITY micro   "&#181;">
        <!ENTITY sbquo   "&#8218;">
        <!ENTITY trade   "&#8482;">
        <!ENTITY Dagger  "&#8225;">
        <!ENTITY radic   "&#8730;">
        ]>
        """
        return dtd_string

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-w', "--warnings",  action="store_true", dest="warn", default=False)

    (options, args) = parser.parse_args()
    Parse_sp_written(options.warn)


