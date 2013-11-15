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
import gzip
from StringIO import StringIO
import random

output_directory = "../../../parldata/cmpages/sp/official-reports-new/"

official_report_url_format = 'http://www.scottish.parliament.uk/parliamentarybusiness/28862.aspx?r={0}&mode=html'

user_agent = 'Mozilla/5.0 (Ubuntu; X11; Linux i686; rv:9.0.1) Gecko/20100101 Firefox/9.0.1'

parser = OptionParser()
parser.add_option('-q', '--quiet', dest='quiet', action='store_true',
                  default=False, help='Suppress progress messages')
parser.add_option('-t', '--test', dest='test', action='store_true',
                  default=False, help='Run doctests')
parser.add_option('--historic', dest='historic',
                  help='Fetch all documents with ID up to MAXID',
                  metavar='MAXID')
parser.add_option('--daily', help='Fetch the documents listed today',
                  default=False, action='store_true')
parser.add_option('--track-missing', dest='missing',
                  help='Record and skip those that are missing',
                  default=False, action='store_true')

(options, args) = parser.parse_args()

minimum_sleep = 2
maximum_sleep = 10

def pp(element):
    print etree.tostring(element, pretty_print = True)

missing_report_ids_filename = os.path.join(output_directory, 'missing')
missing_report_ids = set()

if options.missing:
    with open(missing_report_ids_filename) as fp:
        for line in fp:
            line = line.strip()
            if line:
                i = int(line, 10)
                missing_report_ids.add(i)

def get_document_from_id(official_report_id):
    html_filename = os.path.join(output_directory, str(official_report_id) + '.html')
    if not os.path.exists(html_filename):
        url = official_report_url_format.format(official_report_id)
        if not options.quiet:
            print "Fetching:", url
        request = urllib2.Request(url)
        request.add_header('User-Agent', user_agent)
        opener = urllib2.build_opener()
        response = None
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            # Specifying a non-existent r parameter sometimes gets us
            # a 500 error, and sometimes a 403, so ignore those:
            if e.code in (500, 403):
                if options.missing:
                    if official_report_id not in missing_report_ids:
                        missing_report_ids.add(official_report_id)
                        with open(missing_report_ids_filename, "a") as fp:
                            fp.write(str(official_report_id) + "\n")
                return
            else:
                raise
        with open(html_filename, 'w') as fp:
            fp.write(response.read())
        time.sleep(random.uniform(minimum_sleep, maximum_sleep))
    parser = etree.HTMLParser()
    with open(html_filename) as fp:
        tree = etree.parse(fp, parser)

def main():

    if options.historic:
        for i in range(1, int(options.historic, 10)):
            get_document_from_id(i)

    elif options.daily:
        url = 'http://www.scottish.parliament.uk/parliamentarybusiness/OfficialReport.aspx'
        request = urllib2.Request(url)
        request.add_header('User-Agent', user_agent)
        opener = urllib2.build_opener()
        response = urllib2.urlopen(request)
        parser = etree.HTMLParser()
        html = response.read()
        html = re.sub('(?ims)^\s*', '', html)
        tree = etree.parse(StringIO(html), parser)
        report_ids = set()
        for link in tree.xpath('.//a'):
            href = link.get('href')
            if href:
                m = re.search(r'28862.aspx\?r=(\d+)', href)
                if m:
                    report_ids.add(int(m.group(1), 10))
        min_report_id = min(report_ids) - 20
        max_report_id = max(report_ids) + 20
        for report_id in range(min_report_id, max_report_id + 1):
            get_document_from_id(report_id)

    else:
        print "Either --daily or --historic=MAXID must be specified"

if options.test:
    if not options.quiet:
        print "Running doctests..."
    import doctest
    doctest.testmod()
    sys.exit(0)
else:
    main()
