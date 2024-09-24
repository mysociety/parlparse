#! /usr/bin/env python3
# vim:sw=8:ts=8:et:nowrap

# Run the script with --help to see command line options

import os
import sys

# change current directory to pyscraper folder script is in
os.chdir(os.path.dirname(sys.argv[0]) or ".")

from optparse import OptionParser

import ni.scrape
from miscfuncs import SetQuiet
from regmem.filter import RunRegmemFilters
from regmem.pullgluepages import RegmemPullGluePages
from runfilters import RunFiltersDir, RunNIFilters

# Parse the command line parameters

parser = OptionParser()

parser.set_usage("""
Fetches/parses NI Assembly plenary data, and the UK Parliament register of
members' interests. Converts them into handy XML files, tidying up HTML errors,
generating unique identifiers for speeches, reordering sections, name matching
MPs and so on as it goes.

Specify at least one of the following actions to take:
scrape          download new raw pages
parse           process scraped data into XML files

And choose at least one of these sections to apply them to:
regmem          Register of Members' Interests
ni              Northern Ireland Assembly

Example command line
        ./lazyrunall.py --date=2004-03-03 --force-scrape scrape parse debates
It forces redownload of the debates for 3rd March, and reprocesses them.""")


# See what options there are

parser.add_option(
    "--force-parse",
    action="store_true",
    dest="forceparse",
    default=False,
    help="forces reprocessing of debates by first deleting output files",
)
parser.add_option(
    "--force-scrape",
    action="store_true",
    dest="forcescrape",
    default=False,
    help="forces redownloading of HTML first deleting output files",
)

parser.add_option(
    "--from",
    dest="datefrom",
    metavar="date",
    default="1000-01-01",
    help="date to process back to, default is start of time",
)
parser.add_option(
    "--to",
    dest="dateto",
    metavar="date",
    default="9999-12-31",
    help="date to process up to, default is present day",
)
parser.add_option(
    "--date",
    dest="date",
    metavar="date",
    default=None,
    help="date to process (overrides --from and --to)",
)

parser.add_option(
    "--patchtool",
    action="store_true",
    dest="patchtool",
    default=None,
    help="launch ./patchtool to fix errors in source HTML",
)
parser.add_option(
    "--quietc",
    action="store_true",
    dest="quietc",
    default=None,
    help="low volume error messages; continue processing further files",
)

(options, args) = parser.parse_args()
if options.date:
    options.datefrom = options.date
    options.dateto = options.date
if options.quietc:
    SetQuiet()

# See what commands there are

# can't you do this with a dict mapping strings to bools?
options.scrape = False
options.parse = False
options.regmem = False
options.ni = False
for arg in args:
    if arg == "scrape":
        options.scrape = True
    elif arg == "parse":
        options.parse = True
    elif arg == "regmem":
        options.regmem = True
        options.remote = True
    elif arg == "regmem-local":
        options.regmem = True
        options.remote = False
    elif arg == "ni":
        options.ni = True
    else:
        print("error: no such option %s" % arg, file=sys.stderr)
        parser.print_help()
        sys.exit(1)
if len(args) == 0:
    parser.print_help()
    sys.exit(1)
if not options.scrape and not options.parse:
    print("error: choose what to do; scrape, parse, or both", file=sys.stderr)
    parser.print_help()
    sys.exit(1)
if not options.regmem and not options.ni:
    print("error: choose what work on; regmem, several of them", file=sys.stderr)
    parser.print_help()
    sys.exit(1)


# Download/generate the new data
if options.scrape:
    if options.ni:
        ni.scrape.scrape_ni(options.datefrom, options.dateto, options.forcescrape)
    if options.regmem:
        RegmemPullGluePages(options)

# Parse it into XML
if options.parse:
    if options.ni:
        RunFiltersDir(RunNIFilters, "ni", options, options.forceparse)
    if options.regmem:
        RunFiltersDir(RunRegmemFilters, "regmem", options, options.forceparse)
