#!/usr/bin/env python

__author__ = "Neil Horner"
__date__ = "$27-Oct-2013 01:31:15$"

from urllib import quote_plus
import urllib2
import datetime
import sys

if len(sys.argv) != 3:
    sys.exit("enter two dates to search from in ISO 8601 format")
input_from = sys.argv[1]
input_to = sys.argv[2]

##Convert to format for website -- m/d/y

iso8601_from = datetime.datetime.strptime(input_from, '%Y-%m-%d')
date_from = iso8601_from.strftime('%D')

iso8601_to = datetime.datetime.strptime(input_to, '%Y-%m-%d')
date_to = iso8601_to.strftime('%D')


url = 'http://www.scottish.parliament.uk/parliamentarybusiness/28877.aspx'

data = {'SearchType': 'Advance',
'DateFrom': date_from + " 12:00:00 AM",
'DateTo': date_to + " 11:59:59 PM",
'SortBy': 'DateSubmitted',
'Answers': 'All',
'SearchFor': 'All',
'ResultsPerPage': '1000',
'SearchFor': 'WrittenQuestions'}

query_string = "&".join(quote_plus(k) + "=" + quote_plus(v)
for k, v in data.items())

full_url = url + "?" + query_string
res = urllib2.urlopen(full_url)
print res.read()