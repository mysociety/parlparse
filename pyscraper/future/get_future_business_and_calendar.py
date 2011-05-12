#!/usr/bin/python

"""
This script will scrape the most recent versions of each Future
Business section and pages from the calendar in the future.  Pages are
only written if they are different from the most recent version.  The
output is to the PAGE_STORE directory defined in future_business.py.
"""

from future_business import *

import os
import errno
import re
import sys
import glob
from optparse import OptionParser
import datetime
import dateutil.parser

import time

parser = OptionParser()
parser.add_option('-q', "--quiet", dest="quiet", action="store_true",
                  default=False, help="suppress the usual output of what's been done with each page")
(options, args) = parser.parse_args()

# Trying out httplib2. This hasn't reached 1.0 yet, but I think it's worth
# giving it a go to avoid having to think about caching, downloading headers,
# etags, etc. manually.

import httplib2

# Location of the cache directory for httplib2
cache_directory = '.cache'

# This will cause a directory for httplib2 to use for its
# cache to be created if it doesn't already exist.
http_fetcher = httplib2.Http(cache_directory)

timestamp_re = re.compile('^(.*)-\d{8}T\d{6}.html$')

def write_if_changed(directory_name,
                     filename,
                     content):
    # Store the current working directory so we can go back at the end.
    original_directory = os.getcwd()

    enter_or_create_directory(directory_name)

    try:
        filename_match = timestamp_re.search(filename)
        if not filename_match:
            raise "Failed to match the filename '"+filename+"', expected to match: "+timestamp_re.pattern

        prefix = filename_match.group(1)
        earlier_files = matching_ordered(prefix+"-",".html")

        if len(earlier_files) > 0:
            fp = open(earlier_files[-1])
            latest_file_content = fp.read()
            fp.close()
            if latest_file_content == content:
                # It's just the same as the last version, don't bother saving it...
                if not options.quiet:
                    print "   Not writing "+filename+", the content is the same as "+earlier_files[-1]
                return False

        if not options.quiet:
            print "Writing a file with updated contents: "+filename

        # Otherwise we should just write the file:
        fp = open(filename, 'w')
        fp.write(content)
        fp.close()
        return True

    finally:
        # Return to the original directory
        os.chdir(original_directory)

tidy_class_re = '(class="[^"]+) today([^"]*")'
tidy_class_replacement = '\\1\\2'

if __name__ == '__main__':

    d = start_date = datetime.date.today()
    end_date = start_date + datetime.timedelta(days=CALENDAR_DAYS)

    while True:
        if d > end_date:
            break

        if d.isoweekday() in (6,7):
            d += datetime.timedelta(days=1)
            continue

        for section, calendar_url_format in CALENDAR_SECTIONS.items():
            formatted_date = d.strftime(CALENDAR_URL_DATE_FORMAT)
            url = calendar_url_format % (formatted_date,)
            response, content = http_fetcher.request(url)
            content = re.sub(tidy_class_re,tidy_class_replacement,content)
            content = re.sub('(class=")today ', r'\1', content)
            content = re.sub('class="today"', 'class=""', content)
            content = re.sub('<a class="selected"', '<a', content)
            time.sleep(4)
            response_timestamp = dateutil.parser.parse(response['date'])
            page_filename = CALENDAR_PAGE_FILENAME_FORMAT % (section,d,response_timestamp.strftime(FILENAME_DATE_FORMAT))
            updated = write_if_changed(PAGE_STORE,
                                       page_filename,
                                       content)
        d += datetime.timedelta(days=1)

    for part in FUTURE_BUSINESS_PARTS:
        url = FUTURE_BUSINESS_TEMPLATE_LOCATION % (part,)

        # Fetch the current version of Future Business for a particular part:
        response, content = http_fetcher.request(url)
        content = re.sub(tidy_class_re,tidy_class_replacement,content)

        # Example response:
        #   {'status': '200',
        #    'content-length': '94447',
        #    'content-location': 'http://www.publications.parliament.uk/pa/cm/cmfbusi/a01.htm',
        #    'vary': 'Accept-Encoding',
        #    'server': 'Netscape-Enterprise/6.0',
        #    'connection': 'keep-alive',
        #    'date': 'Tue, 18 Aug 2009 23:38:28 GMT',
        #    'content-type': 'text/html'}

        if re.search('^[45]',response['status']):
            print >> sys.stderr, "Error %s fetching %s" % (response['status'],url)
            continue

        response_timestamp = dateutil.parser.parse(response['date'])

        page_filename = PAGE_FILENAME_FORMAT % (part,response_timestamp.strftime(FILENAME_DATE_FORMAT))

        # Check if we need to store a copy of the page and do so if we do.
        updated = write_if_changed(PAGE_STORE,
                                   page_filename,
                                   content)
