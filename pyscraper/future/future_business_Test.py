#!/usr/bin/python

"""
Contains unit tests for the future_business parsing code.
"""

import unittest

import BeautifulSoup
import dateutil.parser
import datetime
import tempfile
import os
import codecs

from subprocess import call

from parse_future_business_and_calendar import \
    FutureBusinessListItem, \
    get_string_contents, \
    PrivateMembersBill, \
    BusinessItemTable, \
    FutureBusinessDay, \
    FutureEventsPage, \
    ten_minute_rule_re

from future_business import \
    adjust_year_with_timestamp, \
    PAGE_STORE

import xml.dom.minidom
dom_impl = xml.dom.minidom.getDOMImplementation()

def show_colordiff_files(a,b):
    call(["colordiff","-u",a,b])

def show_colordiff_strings(a,b):
    fd_a, fa_name = tempfile.mkstemp()
    fa = codecs.open(fa_name,"w")
    fa.write(a)
    fa.close()
    fd_b, fb_name = tempfile.mkstemp()
    fb = codecs.open(fb_name,"w")
    fb.write(b)
    fb.close()
    show_colordiff_files(fa_name,fb_name)

def compare_doms(dom1, dom2):
    """
    A utility function for comparing two DOMs.

    Ideally, one would want to ask if dom1 equals dom2.
    Sadly, that doesn't seem to work. Two doms that have the
    same structure appear to always produce the same xml under
    toxml, but I could be wrong!
    """

    debug_on_failure = False

    show_colordiff_strings(dom1.toprettyxml(indent="  ",encoding='utf-8'),
                           dom2.toprettyxml(indent="  ",encoding='utf-8'))

    try:
        assert dom1.toxml(encoding='utf-8') == dom2.toxml(encoding='utf-8')
    except AssertionError:
        if debug_on_failure:
            import pdb
            pdb.set_trace()
        else:
            raise

class TestFutureBusinessPages(unittest.TestCase):
    """Tests which instantiate a FutureBusinessPage object with HTML."""

    def compare_against_expected(self,basename):
        source_html = PAGE_STORE + "/%s.html" % (basename,)
        expected_xml = "expected-results/%s.xml" % (basename,)

        fep = FutureEventsPage(source_html)
        received_dom = fep.get_dom()

        parsed_temporary_fd, parsed_temporary_name = tempfile.mkstemp(prefix=basename+"-parsed-")
        parsed_temporary = os.fdopen(parsed_temporary_fd,"w")
        parsed_temporary.write(received_dom.toprettyxml(indent="  ",encoding='utf-8'))
        parsed_temporary.close()

        fpx = open(expected_xml)
        expected_dom = xml.dom.minidom.parse(fpx)
        fpx.close()

        expected_temporary_fd, expected_temporary_name = tempfile.mkstemp(prefix=basename+"-expected-")
        expected_temporary = os.fdopen(expected_temporary_fd,"w")
        expected_temporary.write(expected_dom.toprettyxml(indent="  ",encoding='utf-8'))
        expected_temporary.close()

        show_colordiff_files(parsed_temporary_name,expected_temporary_name)

        compare_doms(received_dom, expected_dom)

    def test_section_a(self):
        """Parse an example Future Business section A page, and
        compare to the expected XML"""

        self.compare_against_expected("future-business-a-20090825T111922")

    def test_section_b(self):
        """Parse an example Future Business section B page, and
        compare to the expected XML"""

        self.compare_against_expected("future-business-b-20100126T120139")

    def test_section_c(self):
        """Parse an example Future Business section C page, and
        compare to the expected XML"""

        self.compare_against_expected("future-business-c-20100204T151538")

    def test_section_c_trickier(self):
        """Parse a more tricky example Future Business section C page,
        and compare to the expected XML."""

        self.compare_against_expected("future-business-c-20100228T125224")

    def test_section_d(self):
        """Parse an example Future Business section D page, and
        compare to the expected XML"""

        self.compare_against_expected("future-business-d-20100126T120145")

    def test_section_e(self):
        """Parse an example Future Business section E page, and
        compare to the expected XML"""

        self.compare_against_expected("future-business-e-20100126T120146")

    def test_section_e_trickier(self):
        """Parse a more tricky Future Business section E page, and
        compare to the expected XML"""

        self.compare_against_expected("future-business-e-20100204T151539")

def check_html_to_xml(html_input, expected_xml, klass, *extra_arguments):
    """A utility function to help check that the objects which generate DOM
    elements after being passed HTML work.

    Takes the html_input, the expected xml output, a class ('klass')
    which will be instantiated with the former to produce the latter,
    and an id which the object will get.
    """

    soup = BeautifulSoup.BeautifulSoup(html_input).div
    full_constructor_arguments = [ soup ]
    full_constructor_arguments += extra_arguments
    item = klass(*full_constructor_arguments)
    expected_dom = xml.dom.minidom.parseString(expected_xml).documentElement

    # Doesn't really matter what's in this document
    document = dom_impl.createDocument(None, 'test', None)
    received_dom = item.get_dom(document)

    compare_doms(expected_dom, received_dom)

class Test_get_string_contents(unittest.TestCase):
    """Tests for the get_string_contents function.

    FUTURE TESTS:
    We could do with more tests in here to check with a dive containing more
    than just a string, and to check the use of the 'recursive' paramater.
    """

    def test_simple_contents(self):
        """This test just passes very simple soup to get_string_contents
        and checks it doesn't mess up.
        """

        input_html = """<div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Questions to the Secretary of State for Health, including Topical Questions.

</div>"""

        # We need to drop down to the div in order to have text on the next level.
        soup = BeautifulSoup.BeautifulSoup(input_html).div

        assert get_string_contents(soup) == 'Questions to the Secretary of State for Health, including Topical Questions.', get_string_contents(soup)


class TestFutureBusinessListItem(unittest.TestCase):
    """Tests for the FutureBusinessListItem class."""

    def test_simple_item(self):
        """Try instantiating FutureBusinessListItem using a simple, text only type
        item in html.
        """

        html_input = """<div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Questions to the Secretary of State for Health, including Topical Questions.

</div>"""
        expected_xml = u"<business-item id='test_1'><title>Questions to the Secretary of State for Health, including Topical Questions.</title></business-item>"

        check_html_to_xml(html_input, expected_xml, FutureBusinessListItem, 'test_1', datetime.date(2009,10,13))

    def test_with_lords(self):
        """Try instantianting a FutureBusinessListItem with something initiated
        in the lords.
        """

        html_input = '''<div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Remaining Stages of the Local Democracy, Economic Development and Construction Bill [<span class="Italic">Lords</span>].

</div>'''

        expected_xml = u"<business-item id='test_1' lords='yes'><title>Remaining Stages of the Local Democracy, Economic Development and Construction Bill [Lords].</title></business-item>"

        check_html_to_xml(html_input, expected_xml, FutureBusinessListItem, 'test_1', datetime.date(2009,10,13))

    def test_ten_minute_rule_re(self):
        """Check the operation of the Ten Minute Rule Motion regular expression
        on all the available Ten Minute Rule Motions.
        """

        tests = (
            (u"Ten minute Rule Motion: Mr Paul Burstow: Statutory Instruments Act 1946 (Amendment): That leave be given to bring in a Bill to amend the Statutory Instruments Act 1946.", (u"Mr Paul Burstow", u"Statutory Instruments Act 1946 (Amendment): That leave be given to bring in a Bill to amend the Statutory Instruments Act 1946.")),
            (u"Ten minute Rule Motion: Mr Douglas Carswell: Parliamentary Elections (Recall and Primaries): That leave be given to bring in a Bill to make provision for the recall of Members of the House of Commons in specified circumstances; to provide for the holding of primary elections in such circumstances; and for connected purposes.", (u"Mr Douglas Carswell", u"Parliamentary Elections (Recall and Primaries): That leave be given to bring in a Bill to make provision for the recall of Members of the House of Commons in specified circumstances; to provide for the holding of primary elections in such circumstances; and for connected purposes.")),
            (u"Ten minute Rule Motion: Mr Brooks Newmark: Cervical Cancer (Minimum Age for Screening): That leave be given to bring in a Bill to require NHS bodies in England to provide cervical screening for women aged 20 and over.", (u"Mr Brooks Newmark", u"Cervical Cancer (Minimum Age for Screening): That leave be given to bring in a Bill to require NHS bodies in England to provide cervical screening for women aged 20 and over.")),
            )

        for input_text, expected_output in tests:
            assert ten_minute_rule_re.match(input_text).groups() == expected_output

    def test_ten_minute_rule_motion(self):
        """Try instantiating FutureBusinessListItem with the HTML for a Ten Minute
        Rule Motion.
        """

        html_input = u"""<div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Ten minute Rule Motion: Mr Douglas Carswell: Parliamentary Elections (Recall and Primaries): That leave be given to bring
                  in a Bill to make provision for the recall of Members of the House of Commons in specified circumstances; to provide for the
                  holding of primary elections in such circumstances; and for connected purposes.

</div>"""

        expected_xml = u"<business-item id='test_1' ten_minute_rule='yes' speakerid='uk.org.publicwhip/member/1621' speakername='Mr Douglas Carswell'><motion>Parliamentary Elections (Recall and Primaries): That leave be given to bring in a Bill to make provision for the recall of Members of the House of Commons in specified circumstances; to provide for the holding of primary elections in such circumstances; and for connected purposes.</motion></business-item>"

        check_html_to_xml(html_input, expected_xml, FutureBusinessListItem, 'test_1', datetime.date(2009,10,13))

class TestPrivateMembersBill(unittest.TestCase):
    """Tests for the PrivateMembersBill object."""

    def test_simple_case(self):
        """Instantiate a PrivateMembersBill with two tr input (the most common case)."""

        html_input = """
                     <tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td align="right" style="width: 1.06cm;" valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="text-align:right;"><span class="charBusinessItemNumber">3</span>
</div>

                                 </td>
                                 <td valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="padding-left:12pt;">	CROWN EMPLOYMENT (NATIONALITY) BILL: As amended in the Public Bill Committee, to be considered.
</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <div class="paraMemberinCharge">Member in charge: Mr Andrew Dismore
</div>

                        </td>
                     </tr>"""


        expected_xml = u'<private-members-bill id="test.3" speakerid="uk.org.publicwhip/member/1628" speakername="Mr Andrew Dismore"><item-heading id="test.3.1">CROWN EMPLOYMENT (NATIONALITY) BILL: As amended in the Public Bill Committee, to be considered.</item-heading><motion-member id="test.3.2">Mr Andrew Dismore</motion-member></private-members-bill>'

        soup = BeautifulSoup.BeautifulSoup(html_input)

        trs = soup.findAll('tr', recursive=False)

        bill_item = PrivateMembersBill(trs[0], 'test', datetime.date(2009,10,16))

        assert bill_item.id == 'test.3'

        assert bill_item.heading_text == u'CROWN EMPLOYMENT (NATIONALITY) BILL: As amended in the Public Bill Committee, to be considered.'

        bill_item.feed_member(trs[1])

        assert bill_item.get_unique_member() == u'Mr Andrew Dismore', bill_item.get_unique_member()


        expected_dom = xml.dom.minidom.parseString(expected_xml).documentElement

        # Doesn't really matter what's in this doc.
        document = dom_impl.createDocument(None, 'test', None)
        received_dom = bill_item.get_dom(document)

        compare_doms(expected_dom, received_dom)


    def test_with_lords(self):
        """Instantiate PrivateMembersBill with HTML of a PMB initiated in the lords."""

        html_input = """<tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td align="right" style="width: 1.06cm;" valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="text-align:right;"><span class="charBusinessItemNumber">2</span>
</div>

                                 </td>
                                 <td valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="padding-left:12pt;">	LAW COMMISSION BILL [<span class="Italic">LORDS</span>]: As amended in the Public Bill Committee, to be considered.

</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <div class="paraMemberinCharge">Member in charge: Emily Thornberry
</div>

                        </td>
                     </tr>"""

        expected_xml = '<private-members-bill id="test.2" lords="yes" speakerid="uk.org.publicwhip/member/1656" speakername="Emily Thornberry"><item-heading id="test.2.1">LAW COMMISSION BILL [LORDS]: As amended in the Public Bill Committee, to be considered.</item-heading><motion-member id="test.2.2">Emily Thornberry</motion-member></private-members-bill>'

        soup = BeautifulSoup.BeautifulSoup(html_input)

        trs = soup.findAll('tr', recursive=False)

        bill_item = PrivateMembersBill(trs[0], 'test', datetime.date(2009,10,16))

        assert bill_item.id == 'test.2'

        expected_text = u'LAW COMMISSION BILL [LORDS]: As amended in the Public Bill Committee, to be considered.'

        assert bill_item.heading_text == expected_text, (bill_item.heading_text, expected_text)

        bill_item.feed_member(trs[1])

        assert bill_item.get_unique_member() == u'Emily Thornberry', bill_item.get_unique_member()


        expected_dom = xml.dom.minidom.parseString(expected_xml).documentElement

        # Doesn't really matter what this document looks like
        document = dom_impl.createDocument(None, 'test', None)
        received_dom = bill_item.get_dom(document)

        compare_doms(expected_dom, received_dom)


class TestBusinessItemTable(unittest.TestCase):
    """Tests which instantiate the BusinessItemTable class."""

    def test_short_input(self):
        """Instantiaet a BusinessItemTable object with a fairly short,
        valid looking table of PMBs.

        There are no actual asserts in here, we're just checking that
        there is no error.
        """

        text = """
               <table class="BusinessItem" width="100%" cellpadding="0" cellspacing="0" border="0">
                  <tbody>
                     <tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td align="right" style="width: 1.06cm;" valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="text-align:right;"><span class="charBusinessItemNumber">1</span>
</div>

                                 </td>
                                 <td valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="padding-left:12pt;">	DAMAGES (ASBESTOS-RELATED CONDITIONS) BILL: Not amended in the Public Bill Committee, to be considered.
</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <div class="paraMemberinCharge">Member in charge: Mr Andrew Dismore
</div>

                        </td>
                     </tr>
                     <tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td align="right" style="width: 1.06cm;" valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="text-align:right;"><span class="charBusinessItemNumber">3</span>
</div>

                                 </td>
                                 <td valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="padding-left:12pt;">	CROWN EMPLOYMENT (NATIONALITY) BILL: As amended in the Public Bill Committee, to be considered.
</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <div class="paraMemberinCharge">Member in charge: Mr Andrew Dismore
</div>

                        </td>
                     </tr>
                  </tbody>
               </table>
"""

        soup = BeautifulSoup.BeautifulSoup(text).table

        business_item_table = BusinessItemTable(soup, 'test', datetime.date(2009,10,16))

        # This test used to check some XML generation, but this class doesn't do that any more.
        # I guess it's worth leaving it here just instantiating the class with some HTML
        # to prevent that getting an error.

    def test_with_motion_text(self):
        """Try instantiating the BusinessItemTable class with a table
        containing a PMB initiated in the lords.
        """

        input_html = """
               <table class="BusinessItem" width="100%" cellpadding="0" cellspacing="0" border="0">
                  <tbody>
                     <tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td align="right" style="width: 1.06cm;" valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="text-align:right;"><span class="charBusinessItemNumber">9</span>
</div>

                                 </td>
                                 <td valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="padding-left:12pt;">	ROYAL MARRIAGES AND SUCCESSION TO THE CROWN (PREVENTION OF DISCRIMINATION) BILL: Adjourned debate on Second Reading [27 March].
</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td style="width: 1.69cm;" align="right"> </td>
                                 <td>
                                    <div class="paraMotionText">   And a Motion being made, and the Question being proposed, That the Bill be now read a second time:
</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <div class="paraMemberinCharge">Member in charge: Dr Evan Harris
</div>

                        </td>
                     </tr>
                  </tbody>
               </table>"""

        soup = BeautifulSoup.BeautifulSoup(input_html).table

        business_item_table = BusinessItemTable(soup, 'test', datetime.date(2009,10,16))

        # This test used to check some XML generation, but this class doesn't do that any more.
        # I guess it's worth leaving it here just instantiating the class with some HTML
        # to prevent that getting an error.

class TestFutureBusinessDay(unittest.TestCase):
    """Tests which instantiate FutureBusinessDay objects."""

    def test_fbd(self):
        """Instantiate with a fairly simple business day."""

        html_input = """<div class="FutureBusinessDay">
               <div class="paraFutureBusinessDate">Tuesday 13 October
</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Questions to the Secretary of State for Health, including Topical Questions.

</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Ten minute Rule Motion: Mr Douglas Carswell: Parliamentary Elections (Recall and Primaries): That leave be given to bring
                  in a Bill to make provision for the recall of Members of the House of Commons in specified circumstances; to provide for the
                  holding of primary elections in such circumstances; and for connected purposes.

</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Remaining Stages of the Local Democracy, Economic Development and Construction Bill [<span class="Italic">Lords</span>].

</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	At the end of the sitting: Adjournment: Subject to be announced.

</div>


</div>"""

        expected_xml = u"<business-day id='test/2009-10-13' date='2009-10-13'><business-item id='test/2009-10-13.1'><title>Questions to the Secretary of State for Health, including Topical Questions.</title></business-item><business-item id='test/2009-10-13.2' ten_minute_rule='yes' speakerid='uk.org.publicwhip/member/1621' speakername='Mr Douglas Carswell'><motion>Parliamentary Elections (Recall and Primaries): That leave be given to bring in a Bill to make provision for the recall of Members of the House of Commons in specified circumstances; to provide for the holding of primary elections in such circumstances; and for connected purposes.</motion></business-item><business-item id='test/2009-10-13.3' lords='yes'><title>Remaining Stages of the Local Democracy, Economic Development and Construction Bill [Lords].</title></business-item><business-item id='test/2009-10-13.4'><title>At the end of the sitting: Adjournment: Subject to be announced.</title></business-item></business-day>"

        check_html_to_xml(html_input, expected_xml, FutureBusinessDay, 'test', dateutil.parser.parse('20090825T111922'), datetime.date(2009,10,13))

    def test_with_pmbs(self):
        """Instantiate FutureBusinessDay with html for a day including PMBs."""

        html_input = """
            <div class="FutureBusinessDay">
               <div class="paraFutureBusinessDate">Friday 16 October
</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Private Members' Bills

</div>

               <table class="BusinessItem" width="100%" cellpadding="0" cellspacing="0" border="0">
                  <tbody>
                     <tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td align="right" style="width: 1.06cm;" valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="text-align:right;"><span class="charBusinessItemNumber">1</span>
</div>

                                 </td>
                                 <td valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="padding-left:12pt;">	DAMAGES (ASBESTOS-RELATED CONDITIONS) BILL: Not amended in the Public Bill Committee, to be considered.
</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <div class="paraMemberinCharge">Member in charge: Mr Andrew Dismore
</div>

                        </td>
                     </tr>
                     <tr>
                        <td>
                           <table width="100%" cellpadding="0" cellspacing="0" border="0">
                              <tr>
                                 <td align="right" style="width: 1.06cm;" valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="text-align:right;"><span class="charBusinessItemNumber">3</span>
</div>

                                 </td>
                                 <td valign="top">
                                    <div class="paraFBPrivateMembersBillItemHeading" style="padding-left:12pt;">	CROWN EMPLOYMENT (NATIONALITY) BILL: As amended in the Public Bill Committee, to be considered.
</div>

                                 </td>
                              </tr>
                           </table>
                        </td>
                     </tr>
                     <tr>
                        <td>
                           <div class="paraMemberinCharge">Member in charge: Mr Andrew Dismore
</div>

                        </td>
                     </tr>
                  </tbody>
               </table>
               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	At the end of the sitting: Adjournment: Subject to be announced.

</div>
</div>
"""
        expected_xml = u'<business-day date="2009-10-16" id="test/2009-10-16"><business-item id="test/2009-10-16.1"><title>Private Members\' Bills</title><private-members-bill id="test/2009-10-16.1.1" speakerid="uk.org.publicwhip/member/1628" speakername="Mr Andrew Dismore"><item-heading id="test/2009-10-16.1.1.1">DAMAGES (ASBESTOS-RELATED CONDITIONS) BILL: Not amended in the Public Bill Committee, to be considered.</item-heading><motion-member id="test/2009-10-16.1.1.2">Mr Andrew Dismore</motion-member></private-members-bill><private-members-bill id="test/2009-10-16.1.3" speakerid="uk.org.publicwhip/member/1628" speakername="Mr Andrew Dismore"><item-heading id="test/2009-10-16.1.3.1">CROWN EMPLOYMENT (NATIONALITY) BILL: As amended in the Public Bill Committee, to be considered.</item-heading><motion-member id="test/2009-10-16.1.3.2">Mr Andrew Dismore</motion-member></private-members-bill></business-item><business-item id="test/2009-10-16.2"><title>At the end of the sitting: Adjournment: Subject to be announced.</title></business-item></business-day>'

        check_html_to_xml(html_input, expected_xml, FutureBusinessDay, 'test', dateutil.parser.parse('20090825T111922'),  datetime.date(2009,10,16))

    def test_with_end_rubbish(self):
        """The final day in the page has some extra tags at the end.
        These contain nothing of interest, but we should make sure it works with
        them in.
        """

        html_input = """
            <div class="FutureBusinessDay">
               <div class="paraFutureBusinessDate">Thursday 22 October
</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Questions to the Secretary of State for Transport, including Topical Questions, and to the Minister for Women and Equality.

</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Topical debate: Subject to be announced.

</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	Motion to take note of the outstanding reports of the Public Accounts Committee to which the Government has replied. Details
                  to be given in the Official Report.

</div>

               <div class="paraFutureBusinessListItem"><img src="parldiam.gif" class="diamond">	At the end of the sitting: Adjournment: Subject to be announced.

</div>

               <div class="paraItemSeparatorRule-padding">
</div>

               <hr style="width:432.05pt;height:2pt; background-color:black">

</div>"""

        expected_xml = u'<business-day date="2009-10-22" id="test/2009-10-22"><business-item id="test/2009-10-22.1"><title>Questions to the Secretary of State for Transport, including Topical Questions, and to the Minister for Women and Equality.</title></business-item><business-item id="test/2009-10-22.2"><title>Topical debate: Subject to be announced.</title></business-item><business-item id="test/2009-10-22.3"><title>Motion to take note of the outstanding reports of the Public Accounts Committee to which the Government has replied. Details to be given in the Official Report.</title></business-item><business-item id="test/2009-10-22.4"><title>At the end of the sitting: Adjournment: Subject to be announced.</title></business-item></business-day>'

        check_html_to_xml(html_input, expected_xml, FutureBusinessDay, 'test', dateutil.parser.parse('20090825T111922'),  datetime.date(2009,10,22))

if __name__ == '__main__':
    unittest.main()
