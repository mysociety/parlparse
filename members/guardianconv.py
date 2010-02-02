#!/usr/bin/env python2.4
# $Id: guardianconv.py,v 1.10 2004/12/24 14:46:56 theyworkforyou Exp $

# Converts tab file of Guardian URLs into XML.  Also extracts swing/majority
# from the constituency page on the Guardian.

# The Public Whip, Copyright (C) 2003 Francis Irving and Julian Todd
# This is free software, and you are welcome to redistribute it under
# certain conditions.  However, it comes with ABSOLUTELY NO WARRANTY.
# For details see the file LICENSE.html in the top level of the source.

input = '../rawdata/mpinfo/guardian-mpsurls2005.txt'
date = '2010-02-01'

import sys
import string
import urllib
import re
sys.path.append("../pyscraper")
from resolvemembernames import memberList
from BeautifulSoup import BeautifulSoup

print '''<?xml version="1.0" encoding="ISO-8859-1"?>
<publicwhip>
'''

ih = open(input, 'r')

c = 0
for l in ih:
    c = c + 1
    origname, origcons, personurl, consurl = map(string.strip, l.split("\t"))
    origname = re.sub("^(.*), (.*)$", '\\2 \\1', origname)

    # Match the name, and output basic URLs
    print >>sys.stderr, "Working on %s %s" % (origname, origcons)
    id, name, cons =  memberList.matchfullnamecons(origname, origcons, date)
    print  >>sys.stderr, "ID %s name %s cons %s" % (id, name, cons)
    personid = memberList.membertoperson(id)
    cons = cons.replace("&", "&amp;")

    print '<personinfo id="%s" guardian_mp_summary="%s" />' % (personid, personurl)
    print '<consinfo canonical="%s" guardian_election_results="%s" />' % (cons.encode("latin-1"), consurl)

    # Majority
    setsameelection =  memberList.getmembersoneelection(id)
    #print setsameelection

    # Grab swing from the constituency page
    again = 1
    # we retry URLs as sometimes (1 in 40) they fail (some
    # incompatibility between Guardian web server and Python url
    # library?)
    while again:
        print >>sys.stderr, "Trying %s" % consurl
        try:
            ur = urllib.urlopen(consurl)
            again = 0
        except:
            print >>sys.stderr, "---------------------- RETRYING URL"
            again = 1
    content = ur.read()
    ur.close()
    soup = BeautifulSoup(content)
    vote_cells = soup.findAll('td', attrs={"class": "last"})
    # Assumes most recent vote will be at top
    if vote_cells:
        vote_percent_pattern = re.compile('(\d{1,2}\.\d)%')
        top_vote_match = re.search(vote_percent_pattern, vote_cells[0].string)
        second_vote_match = re.search(vote_percent_pattern, vote_cells[1].string)
        swing = round( ( float(top_vote_match.group(1)) - float(second_vote_match.group(1)) ) / 2 , 2)
        for id in setsameelection:
            print '<memberinfo id="%s" swing_to_lose_seat="%s" />' % (id, swing)
    else:
        print >>sys.stderr, "no match for swing at url %s" % consurl

    majority_div = soup.find('div', attrs={"class": "figures", "id": "majority"})
    if majority_div:
        majority = majority_div.p.span.string.strip()
        for id in setsameelection:
            print '<memberinfo id="%s" majority_in_seat="%s" />' % (id, majority.replace(",", ""))
    else:
        print >>sys.stderr, "no match for majority at url %s" % consurl

    print ''

assert c == 646, "Expected 646 MPs, got %d MPs" % c

ih.close()

print '</publicwhip>'

