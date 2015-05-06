#!/usr/bin/env python

import codecs
import csv
import json
import os
import re
import sys
import unicodedata
import urllib

sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

CSV_URL = 'https://edit.yournextmp.com/media/candidates.csv'
JSON = os.path.join(os.path.dirname(__file__), '..', '..', 'members', 'people.json')


def main():
    data = load_data()
    changed = update_from(CSV_URL, data)
    if changed:
        json.dump(data['json'], open(JSON, 'w'), indent=2, sort_keys=True)


def update_from(csv_url, data):
    changed = False
    for ynmp_id, name, party, cons, person_id in ynmp_csv_reader(csv_url):
        if party not in data['orgs']:
            data['orgs'][party] = slugify(party)
            data['json']['organizations'].append({'id': slugify(party), 'name': party})
        if person_id not in data['persons']:
            person_id = ''
        identifier = {'scheme': 'yournextmp', 'identifier': ynmp_id}
        if person_id:
            if identifier not in data['persons'][person_id].setdefault('identifiers', []):
                data['persons'][person_id]['identifiers'].append(identifier)
        else:
            data['max_person_id'] += 1
            person_id = 'uk.org.publicwhip/person/%d' % data['max_person_id']
            data['json']['persons'].append({
                'id': person_id,
                'identifiers': [identifier],
                'shortcuts': {
                    'current_party': party,
                    'current_constituency': cons,
                }
            })

        new_mship = {
            'name': name,
            'on_behalf_of_id': data['orgs'][party],
            'person_id': person_id,
            'start_date': '2015-05-08',
            'start_reason': 'general_election',
        }
        if cons in data['existing']:
            mship = data['existing'][cons]
            if mship_has_changed(mship, new_mship):
                changed = True
                print "Updating %s with %s %s, %s, %s, %s" % (mship['id'], name['given_name'], name['family_name'], party, cons, person_id)
        else:
            changed = True
            data['max_mship_id'] += 1
            print "NEW result %s, %s %s, %s, %s, %s" % (data['max_mship_id'], name['given_name'], name['family_name'], party, cons, person_id)
            mship = {
                'id': 'uk.org.publicwhip/member/%d' % data['max_mship_id'],
                'post_id': data['posts_by_name'][cons]['id'],
            }
            data['json']['memberships'].append(mship)
            data['existing'][cons] = mship
        if changed:
            mship.update(new_mship)

    return changed


def slugify(value):
    """
    Converts to ASCII. Converts spaces to hyphens. Removes characters that
    aren't alphanumerics, underscores, or hyphens. Converts to lowercase.
    Also strips leading and trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def load_data():
    """Load in existing JSON (including any new MPs already set)"""
    j = json.load(open(JSON))
    persons = {p['id']: p for p in j['persons']}
    posts = {p['id']: p for p in j['posts']}
    posts_by_name = {p['area']['name']: p for p in j['posts'] if p['organization_id'] == 'house-of-commons' and 'end_date' not in p}
    assert len(posts_by_name) == 650
    orgs = {o['name']: o['id'] for o in j['organizations']}
    max_person_id = max(int(p['id'].replace('uk.org.publicwhip/person/','')) for p in j['persons'])

    existing = {}
    max_mship_id = 0
    mships = (m for m in j['memberships'] if 'post_id' in m and posts[m['post_id']]['organization_id'] == 'house-of-commons')
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
    'Labour Party': 'Labour',
    'Conservative Party': 'Conservative',
    'Conservative and Unionist Party': 'Conservative',
    'Liberal Democrats': 'Liberal Democrat',
    'Ulster Unionist Party': 'UUP',
    'Speaker seeking re-election': 'Speaker',
    'Scottish National Party (SNP)': 'Scottish National Party',
    'Plaid Cymru - The Party of Wales': 'Plaid Cymru',
    "Labour and Co-operative Party": 'Labour/Co-operative',
    'Democratic Unionist Party - D.U.P.': 'DUP',
    'The Respect Party': 'Respect',
    "SDLP (Social Democratic & Labour Party)": "Social Democratic and Labour Party",
    "UK Independence Party (UKIP)": "UKIP",
    "UK Independence Party (UK I P)": "UKIP",
    "Alliance - Alliance Party of Northern Ireland": 'Alliance',
    'Green Party': 'Green',
    'Scottish Green Party': 'Green',
    'Traditional Unionist Voice - TUV': 'Traditional Unionist Voice',
}


def ynmp_csv_reader(fn):
    if isinstance(fn, basestring):
        fn = urllib.urlopen(fn)
    for row in csv.DictReader(fn):
        name = row['name'].decode('utf-8').strip()
        # TWFY has separate first/last name fields. This should catch most.
        m = re.match(u'(.*?) ((?:ap |van |de |di |von |st |duncan |lloyd |\u00d3 )*[^ ]*(?: Jnr)?)$(?i)', name)
        given, family = m.groups()
        party = row['party'].decode('utf-8')
        party = PARTY_YNMP_TO_TWFY.get(party, party)
        cons = row['constituency'].decode('utf-8')
        person_id = row['parlparse_id']
        ynmp_id = int(row['id'])
        elected = row.get('elected', '')
        if elected.lower() in ('true', 'yes', 'y', 'elected'):
            yield ynmp_id, {'given_name': given, 'family_name': family}, party, cons, person_id


def mship_has_changed(old, new):
    if old['name'] != new['name'] or old['on_behalf_of_id'] != new['on_behalf_of_id'] or old['person_id'] != new['person_id']:
        return True
    return False


if __name__ == '__main__':
    main()
