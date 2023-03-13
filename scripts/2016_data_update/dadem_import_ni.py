#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import codecs
import csv
import json
import os
import re
import sys
import unicodedata

sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

CSV_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'rawdata', '2016_election', 'mla.csv')
JSON = os.path.join(os.path.dirname(__file__), '..', '..', 'members', 'people.json')


def main():
    data = load_data()
    changed = update_from(CSV_FILE, data)
    if changed:
        json.dump(data['json'], open(JSON, 'w'), indent=2, sort_keys=True)


def update_from(csv_url, data):
    changed = False
    for name, party, cons, person_id in dadem_csv_reader(csv_url):
        # Here we have an elected person.
        if party not in data['orgs']:
            data['orgs'][party] = slugify(party)
            data['json']['organizations'].append({'id': slugify(party), 'name': party})

        if person_id not in data['persons']:
            person_id = ''

        if person_id == '':
            data['max_person_id'] += 1
            person_id = 'uk.org.publicwhip/person/%d' % data['max_person_id']
            name['note'] = 'Main'
            new_person = {
                'id': person_id,
                'other_names': [name],
                'shortcuts': {
                    'current_party': party,
                    'current_constituency': cons,
                }
            }
            data['json']['persons'].append(new_person)
            data['persons'][person_id] = new_person

        changed = True
        data['max_mship_id'] += 1
        # out = u'NEW result {0}, {1} {2}, {3}, {4}, {5}\n'.format(
            # data['max_mship_id'], name['given_name'], name['family_name'], party, cons, person_id
        # )
        # sys.stdout.write(out)
        mship = {
            'id': 'uk.org.publicwhip/member/%d' % data['max_mship_id'],
            'post_id': data['posts_by_name'][cons]['id'],
            'on_behalf_of_id': data['orgs'][party],
            'person_id': person_id,
            'start_date': '2016-05-07',
            'start_reason': 'regional_election',
        }
        data['json']['memberships'].append(mship)
        data['existing'][cons] = mship

    return changed


def slugify(value):
    """
    Converts to ASCII. Converts spaces to hyphens. Removes characters that
    aren't alphanumerics, underscores, or hyphens. Converts to lowercase.
    Also strips leading and trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def load_data():
    """Load in existing JSON (including any new MPs already set)"""
    j = json.load(open(JSON))
    persons = {p['id']: p for p in j['persons']}
    posts = {p['id']: p for p in j['posts']}
    posts_by_name = {p['area']['name']: p for p in j['posts'] if p['organization_id'] == 'northern-ireland-assembly' and 'end_date' not in p}
    assert len(posts_by_name) == 18
    orgs = {o['name']: o['id'] for o in j['organizations']}
    max_person_id = max(int(p['id'].replace('uk.org.publicwhip/person/','')) for p in j['persons'])

    existing = {}
    max_mship_id = 0
    mships = (m for m in j['memberships'] if 'post_id' in m and posts[m['post_id']]['organization_id'] == 'northern-ireland-assembly')
    for mship in mships:
        max_mship_id = max(max_mship_id, int(mship['id'].replace('uk.org.publicwhip/member/','')))
        if 'end_date' in mship:
            continue  # Not a new MP
        cons = posts[mship['post_id']]['area']['name']
        assert cons not in existing
        existing[cons] = mship

    return {
        'json': j,
        'persons': persons,
        'posts_by_name': posts_by_name,
        'orgs': orgs,
        'max_person_id': max_person_id,
        'max_mship_id': max_mship_id,
        'existing': existing,
    }


PARTY_YNMP_TO_TWFY = {
    'Scottish Labour': 'Labour',
    'Labour Party': 'Labour',
    'Conservative Party': 'Conservative',
    'Conservative and Unionist Party': 'Conservative',
    'Scottish Conservative and Unionist Party': 'Conservative',
    'Liberal Democrats': 'Liberal Democrat',
    'Scottish Liberal Democrats': 'Liberal Democrat',
    'Ulster Unionist Party': 'UUP',
    'Speaker seeking re-election': 'Speaker',
    'Scottish National Party (SNP)': 'Scottish National Party',
    'Plaid Cymru - The Party of Wales': 'Plaid Cymru',
    "Labour and Co-operative Party": 'Labour/Co-operative',
    'Democratic Unionist Party - D.U.P.': 'DUP',
    'Democratic Unionist Party': 'DUP',
    'The Respect Party': 'Respect',
    "SDLP (Social Democratic & Labour Party)": "Social Democratic and Labour Party",
    "UK Independence Party (UKIP)": "UKIP",
    "UK Independence Party (UK I P)": "UKIP",
    "Alliance - Alliance Party of Northern Ireland": 'Alliance',
    "Alliance Party": 'Alliance',
    'Green Party': 'Green',
    'Scottish Green Party': 'Green',
    'Traditional Unionist Voice - TUV': 'Traditional Unionist Voice',
}


def dadem_csv_reader(fn):
    if isinstance(fn, str):
        fn = open(fn)
    for row in csv.DictReader(fn):
        given = row['First']
        family = row['Last']
        party = row['Party'].decode('utf-8')
        party = PARTY_YNMP_TO_TWFY.get(party, party)
        cons = row['Constituency'].decode('utf-8')
        person_id = None
        if row['parlparse_id']:
            person_id = 'uk.org.publicwhip/person/{0}'.format(row['parlparse_id'])
        yield {'given_name': given, 'family_name': family}, party, cons, person_id


def mship_has_changed(old, new):
    if old['name'] != new['name'] or old['on_behalf_of_id'] != new['on_behalf_of_id'] or old['person_id'] != new['person_id']:
        return True
    return False


if __name__ == '__main__':
    main()
