#!/usr/bin/python

import lxml.html
from lxml import etree
import urlparse
import dateutil.parser
import datetime
import re
import sys
import urllib
import urllib2
import os
from optparse import OptionParser
import time

output_directory = "../../../parldata/cmpages/sp/official-reports/"

current_date = datetime.date.today()
search_back_to = datetime.date(2011, 1, 1)

official_reports_browse_url = 'http://www.scottish.parliament.uk/parliamentarybusiness/39977.aspx'

user_agent = 'Mozilla/5.0 (Ubuntu; X11; Linux i686; rv:9.0.1) Gecko/20100101 Firefox/9.0.1'

parser = OptionParser()
parser.add_option('-v', '--verbose', dest='verbose', action='store_true',
                  default=False, help='Print progress messages')
parser.add_option('-t', '--test', dest='test', action='store_true',
                  default=False, help='Run doctests')
(options, args) = parser.parse_args()

def slash_date(d):
    '''
    >>> d = datetime.date(2011,3,2)
    >>> slash_date(d)
    '2/3/2011'
    '''
    return '{d}/{m}/{y}'.format(d=d.day,
                                m=d.month,
                                y=d.year)

def text_date(d):
    '''
    >>> d = datetime.date(2011,3,2)
    >>> text_date(d)
    '02 March 2011'
    '''
    return d.strftime('%d %B %Y')

def comma_date(d):
    '''
    >>> d = datetime.date(2011,3,2)
    >>> comma_date(d)
    '[2011,3,2]'
    '''
    return '[{y},{m},{d}]'.format(y=d.year,
                                  m=d.month,
                                  d=d.day)

# Unfortunately urllib.urlencode uses quote_plus, not quote, and we
# also need to escape '/' characters:

def quote_pair(t):
    '''
    >>> quote_pair(('ORBrowser1_dateFrom_ClientState', '{"minDateStr":"5/12/1999 0:0:0","maxDateStr":"12/31/2099 0:0:0"}'))
    'ORBrowser1_dateFrom_ClientState=%7B%22minDateStr%22%3A%225%2F12%2F1999%200%3A0%3A0%22%2C%22maxDateStr%22%3A%2212%2F31%2F2099%200%3A0%3A0%22%7D'
    '''
    return urllib.quote(t[0], '') + '=' + urllib.quote(t[1], '')

if options.test:
    if options.verbose:
        print "Running doctests..."
    import doctest
    doctest.testmod()
    sys.exit(0)

post_parameters = [
    ('AjaxScriptManager_HiddenField', ''),
    ('ORBrowser1$btnSearch', 'Browse'),
    ('ORBrowser1$dateFrom', str(search_back_to)),
    ('ORBrowser1$dateFrom$dateInput', str(search_back_to) + '-00-00-00'),
    ('ORBrowser1$dateTo', str(current_date)),
    ('ORBrowser1$dateTo$dateInput', str(current_date) + '-00-00-00'),
    ('ORBrowser1_dateFrom_ClientState', '{"minDateStr":"5/12/1999 0:0:0","maxDateStr":"12/31/2099 0:0:0"}'),
    ('ORBrowser1_dateFrom_calendar_AD', '[[1999,5,12],[2099,12,30],[2011,7,1]]'),
    ('ORBrowser1_dateFrom_calendar_SD', '[[2011,1,1]]'),
    ('ORBrowser1_dateFrom_dateInput_ClientState', '{"enabled":true,"emptyMessage":"","minDateStr":"5/12/1999 0:0:0","maxDateStr":"12/31/2099 0:0:0"}'),
    ('ORBrowser1_dateFrom_dateInput_text', text_date(search_back_to)),
    ('ORBrowser1_dateTo_ClientState', '{{"minDateStr":"{} 0:0:0","maxDateStr":"12/31/2099 0:0:0"}}'.format(slash_date(search_back_to))),
    ('ORBrowser1_dateTo_calendar_AD', '[{},[2099,12,30],{}]'.format(comma_date(search_back_to), comma_date(current_date))),
    ('ORBrowser1_dateTo_calendar_SD', '[]'),
    ('ORBrowser1_dateTo_dateInput_ClientState', '{{"enabled":true,"emptyMessage":"","minDateStr":"{} 0:0:0","maxDateStr":"12/31/2099 0:0:0"}}'.format(slash_date(search_back_to))),
    ('ORBrowser1_dateTo_dateInput_text', text_date(current_date)),
    ('Search$SearchTerms', ''),
    ('__EVENTARGUMENT', ''),
    ('__EVENTTARGET', ''),
    ('__EVENTVALIDATION', '/wEWCAL+raDpAgLkyYOkAgLuqPeQDAKRgf61CgLA8+H0DAKm3+v1DgK31+3eCAK1kfniCsRZiGV61DLzTRq4Owywfzmq1dKt'),
    ('__SCROLLPOSITIONX', '0'),
    ('__SCROLLPOSITIONY', '57'),
    ('__VIEWSTATE', ''),
    ('__VIEWSTATEGUID', '8b55e34e-b11c-4f57-817b-261f66bfb16d')
]

encoded_parameters = '&'.join(quote_pair(t) for t in post_parameters)

# The server seems to return a 500 error unless I add the Accept
# header.  It can't hurt to add the User-Agent and Referer headers as
# well.

headers = {
    'User-Agent': user_agent,
    'Referer': official_reports_browse_url,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

if options.verbose:
    print "Fetching:", official_reports_browse_url

request = urllib2.Request(official_reports_browse_url, encoded_parameters, headers)
response = urllib2.urlopen(request)

parser = etree.HTMLParser()

tree = etree.parse(response, parser)

for e in tree.xpath('.//div[@id="ORBrowser1_pnlResults"]//tr'):
    cells = e.getchildren()
    date_text = cells[0].text
    if date_text == 'Date':
        continue
    parsed_date = dateutil.parser.parse(date_text).date()
    link_element = cells[1].find('a')
    if not link_element.text.startswith('Meeting of the Parliament'):
        continue
    full_url = urlparse.urljoin(
        official_reports_browse_url,
        link_element.get('href'))
    # The non-Javascript version seems to be obtained by adding
    # &mode=html to the end of the query string:
    full_url += '&mode=html'
    print "For date", parsed_date, "got URL:", full_url
    destination_leafname = 'ornew' + str(parsed_date) + '.html'
    destination = os.path.join(output_directory,
                               destination_leafname)
    destination = os.path.realpath(destination)
    if os.path.exists(destination):
        if options.verbose:
            print "Skipping, since this file exists:", destination
    else:
        if options.verbose:
            print "Downloading to:", destination
        headers['Referer'] = official_reports_browse_url
        request = urllib2.Request(full_url,
                                  None,
                                  headers)
        response = urllib2.urlopen(request)
        with open(destination, 'w') as fp:
            fp.write(response.read())
        time.sleep(5)
