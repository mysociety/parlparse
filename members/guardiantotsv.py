#!/usr/bin/env python2.4
# $Id:  $
# Creates TSV file mapping PublicWhip person IDs to Guardian person IDs
# from guardian-links.xml
import sys
sys.path.append("../pyscraper")
from BeautifulSoup import BeautifulStoneSoup
import re

xml = open("guardian-links.xml", 'r').read()
soup = BeautifulStoneSoup(xml)
people = soup.findAll('personinfo')

outfile = open("guardian-people.tsv", 'w')
headers = ['Canonical Guardian Name', 'Guardian ID', 'mySociety ID']
outfile.write("\t".join(headers) + "\n")
for person in people:
    public_whip_id = person['id']
    id_match = re.search('^uk.org.publicwhip/person/(\d+)$', public_whip_id)
    person_id = id_match.group(1)
    guardian_url = person['guardian_mp_summary']
    url_match = re.search('^http://www.guardian.co.uk/politics/person/(\d+)/(.*)$', guardian_url)
    guardian_person_id = url_match.group(1)
    guardian_person_name = url_match.group(2)
    line = [guardian_person_name, guardian_person_id, person_id]
    outfile.write("\t".join(line) + "\n")
outfile.close()