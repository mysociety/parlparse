# Use these to form each future business URL:
FUTURE_BUSINESS_PARTS = [ 'a', 'b', 'c', 'd', 'e', 'f' ]
FUTURE_BUSINESS_TEMPLATE_LOCATION = 'http://www.publications.parliament.uk/pa/cm/cmfbusi/%s01.htm'

CALENDAR_SECTIONS = { "commons-main-chamber" : "http://services.parliament.uk/calendar/Commons/MainChamber/%s/events.html",
                      "commons-westminster-hall" : "http://services.parliament.uk/calendar/Commons/WestminsterHall/%s/events.html",
                      "commons-general-committee" : "http://services.parliament.uk/calendar/Commons/GeneralCommittee/%s/events.html",
                      "commons-select-committee" : "http://services.parliament.uk/calendar/Commons/SelectCommittee/%s/events.html",
                      "lords-main-chamber" : "http://services.parliament.uk/calendar/Lords/MainChamber/%s/events.html",
                      "lords-grand-committee" : "http://services.parliament.uk/calendar/Lords/GrandCommittee/%s/events.html",
                      "lords-select-committee" : "http://services.parliament.uk/calendar/Lords/SelectCommittee/%s/events.html" }

# The directory in which to store our own copies of the page.
PAGE_STORE = '../../../parldata/cmpages/future'

# The format of the filenames in the PAGE_STORE directory.  The first
# %s will be replaced by the section, the second by the timestamp from
# the server in FILENAME_DATE_FORMAT.
PAGE_FILENAME_FORMAT = "future-business-%s-%s.html"

# The format of calendar pages in the PAGE_STORE directory.  The first
# %s is replaced by the section name, the second by the date the
# calendar is about and the third the date it was fetched on.
CALENDAR_PAGE_FILENAME_FORMAT = "%s-%s-%s.html"

# The directory in which to store the files output by the scraper.
PARSED_XML_STORE = 'parsed_xml'

# The format of the filenames in the PARSED_XML_STORE directory.
# The %s will be replaced by the date in the FILENAME_DATE_FORMAT.
XML_FILENAME_FORMAT = "%s-future-business-%s.xml"

# The format of the date based component the filenames of both the stored
# pages, and the scraped xml pages.
FILENAME_DATE_FORMAT = "%Y%m%dT%H%M%S"

# The format of the dates in the calendar's URLs
CALENDAR_URL_DATE_FORMAT = "%Y/%m/%d"

# Number of days in the future to scrape the calendar for:
CALENDAR_DAYS = 7

import os
import errno
import glob
import datetime

def enter_or_create_directory(directory_name):
    """Change the current working directory to that with name
    'directory_name', creating it if it doesn't already exist."""

    try:
        os.mkdir(directory_name)
    except OSError, e:
        # Ignore the error if it already exists
        if e.errno != errno.EEXIST:
            raise
    os.chdir(directory_name)

def matching_ordered(prefix,suffix):
    """Find all the files in the current directory that start with
    prefix and end with suffix, and return them ordered by name"""

    composed_glob = prefix+'*'+suffix
    return sorted(glob.glob(composed_glob))

def adjust_year_with_timestamp(date_with_broken_year,timestamp):
    # Try either the year in the timestamp or the next year:
    date_earlier = datetime.date(timestamp.year,
                                 date_with_broken_year.month,
                                 date_with_broken_year.day)
    date_later = datetime.date(timestamp.year+1,
                               date_with_broken_year.month,
                               date_with_broken_year.day)
    # Work out the differences from the timestamp:
    difference_earlier = timestamp.date() - date_earlier
    difference_later = timestamp.date() - date_later
    # Return the date that's nearest to the timestamp:
    if difference_earlier < difference_later:
        return date_earlier
    else:
        return date_earlier
