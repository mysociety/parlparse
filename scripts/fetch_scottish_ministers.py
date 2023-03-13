#!/usr/bin/env python3

import os
import json
import sys
import urllib.request

import dateutil.parser as dateparser

rawdata_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'rawdata'))
members_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'members'))
path_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'pyscraper' ))

sys.path.append(path_dir)

from sp.resolvenames import memberList

api_points = {
    'sp_minister_data.json': 'https://data.parliament.scot/api/membergovernmentroles/json',
    'sp_minister_type.json': 'https://data.parliament.scot/api/governmentroles/json',
    'sp_msps.json': 'https://data.parliament.scot/api/members/json'
}

for outfile, url in api_points.items():
    data = urllib.request.urlopen(url).read()
    output = os.path.join(rawdata_dir, outfile)
    with open(output, 'wb+') as fp:
        fp.write(data)

with open(os.path.join(rawdata_dir, 'sp_minister_data.json')) as fp:
    ministers = json.load(fp)

with open(os.path.join(rawdata_dir, 'sp_minister_type.json')) as fp:
    minister_type = json.load(fp)

with open(os.path.join(rawdata_dir, 'sp_msps.json')) as fp:
    msps = json.load(fp)

type_to_name = {}
id_to_name = {}

for msp in msps:
    id_to_name[msp['PersonID']] = msp['ParliamentaryName']

for min_type in minister_type:
    type_to_name[min_type['ID']] = min_type['Name']

new_ministers = []
for minister in ministers:
    name = id_to_name[minister['PersonID']]
    role = type_to_name[minister['GovernmentRoleID']]
    start = dateparser.parse(minister['ValidFromDate']).date().isoformat()
    end = '9999-12-31'
    if minister['ValidUntilDate']:
        end = dateparser.parse(minister['ValidUntilDate']).date().isoformat()
    person_id = memberList.match_whole_speaker(name, start)
    new_minister = {
        'id': 'scot.parliament.data/membergovernmentroles/%s' % minister['ID'],
        'source': 'https://data.parliament.scot/api/membergovernmentroles/json',
        'role': role,
        'person_id': person_id,
        'organization_id': 'scottish-parliament',
        'start_date': start
    }
    if end != '9999-12-31':
        new_minister['end_date'] = end
    new_ministers.append(new_minister)

with open(os.path.join(members_dir, 'sp-ministers.json'), 'w') as sp_fp:
    json.dump(new_ministers, sp_fp, indent=2)
