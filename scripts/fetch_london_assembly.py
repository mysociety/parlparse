#!/usr/bin/env python

# Fetch London Assembly members from Wikidata

import argparse
import logging

import requests

from popolo import Popolo
from popolo.utils import edit_file, new_id


# Query to retrieve London Assembly memberships from Wikidata

WIKIDATA_SPARQL_QUERY = '''SELECT ?item ?itemLabel ?node ?parliamentarygroup ?starttime ?endtime ?twfy_id WHERE {
    ?node ps:P39 wd:Q56573014 .
    ?item p:P39 ?node .
    ?node pq:P580 ?starttime .
    OPTIONAL { ?item wdt:P2171 ?twfy_id }
    OPTIONAL { ?node pq:P4100 ?parliamentarygroup }
    OPTIONAL { ?node pq:P582 ?endtime }
    OPTIONAL { ?node pq:P2715 ?election }
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}'''


# Map of party Wikidata identifiers to the on_behalf_of_id slugs used in
# memberships.

# NB: This is *not necessarily* the same as the Wikidata IDs of a party in
# people.json, since we map Assembly groups to the party name people actually
# expect to see.

PARTY_TO_ON_BEHALF_OF_ID = {
    'Q9624':     'liberal-democrat',
    'Q10647':    'ukip',
    'Q56577681': 'labour',
    'Q56578473': 'green',
    'Q61584795': 'conservative',
    'Q61586635': 'brexit-alliance'
}

logger = logging.getLogger('import-members-from-wikidata')
logging.basicConfig()

parser = argparse.ArgumentParser()

parser.add_argument("-v", "--verbose", help="output all messages, instead of just warnings",
                    action="store_true")

parser.add_argument("--create", help="create new people where no match is found",
                    action="store_true")

args = parser.parse_args()

if args.verbose:
    logger.setLevel(logging.DEBUG)

logger.debug('Importing London Assembly Members from Wikidata')

url = 'https://query.wikidata.org/sparql'
data = requests.get(url, params={'query': WIKIDATA_SPARQL_QUERY, 'format': 'json'}).json()

pp_data = Popolo()

for item in data['results']['bindings']:

    member = {
        'wikidata_id': item['item']['value'].rsplit('/', 1)[-1],
        'name': item['itemLabel']['value'],
        'membership_id': item['node']['value'].rsplit('/', 1)[-1],
        'party': item['parliamentarygroup']['value'].rsplit('/', 1)[-1],
        'start_date': item['starttime']['value'].split('T')[0],  # Datetime from Wikidata is always ISO 8601 with timestamp
    }

    if 'twfy_id' in item:
        member['parlparse_id'] = item['twfy_id']['value']

    if 'endtime' in item:
        member['end_date'] = item['endtime']['value'].split('T')[0]

    logger.debug(u'{} ({}) found in Wikidata'.format(member['name'], member['wikidata_id']))

    # Try retrieve this person by Wikidata ID, if that is known
    pp_person = pp_data.get_person(id=member['wikidata_id'], scheme='wikidata')

    if pp_person:

        pp_id = pp_person['id'].rsplit('/', 1)[-1]

        # This person has been matched on Wikidata ID. Hooray!

        logger.debug(u'{} ({}) matched to existing person {} by Wikidata ID'.format(
            member['name'],
            member['wikidata_id'],
            pp_id
        ))

        # Run a sanity check that Parlparse IDs match.
        if 'parlparse_id' not in member:
            logger.warning(u'{} ({}) does not have a TWFY ID set in Wikidata. Expected {}.'.format(
                member['name'],
                member['wikidata_id'],
                pp_id
            ))

        else:

            if member['parlparse_id'] != pp_id:
                logger.warning(u'{} ({}) has a ParlParse ID of {}, expected {}.'.format(
                    member['name'],
                    member['wikidata_id'],
                    member['parlparse_id'],
                    pp_id
                ))
            else:
                logger.debug(u'{} ({}) has expected ParlParse ID'.format(
                    member['name'],
                    member['wikidata_id'],
                ))

    else:

        # This person hasn't been matched on Wikidata ID. Can we do it by ParlParse ID?

        if 'parlparse_id' in member:
            pp_person = pp_data.get_person(id=member['parlparse_id'], scheme='wikidata')

            if pp_person:

                pp_id = pp_person['id'].rsplit('/', 1)[-1]

                logger.debug(u'{} ({}) matched to existing person {} by ParlParse ID'.format(
                    member['name'],
                    member['wikidata_id'],
                    pp_id))

                # We have a person matched on ParlParse. They don't have a Wikidata ID. Set it.
                if 'identifiers' not in pp_person:
                    pp_person['identifiers'] = []

                pp_person['identifiers'].append(
                    {
                        'scheme': 'wikidata',
                        'identifier': member['wikidata_id']
                    }
                )

                pp_data.persons[pp_person['id']].update(pp_person)

                logger.warning(u'{} has had Wikidata ID {} added to their ParlParse person entry.'.format(
                    member['name'],
                    member['wikidata_id']
                ))

    # Have we explicitly matched, or do we need to try names or mint new people?
    if pp_person:

        logger.debug('Matched with ParlParse member {} by explicit ID'.format(pp_person['id']))

    else:

        if args.create:

            # New people should be created.

            logger.debug('Minting new ID.')

            new_person_id = new_id(pp_data.max_person_id())
            logger.debug('New ID is {}'.format(new_person_id))

            new_person = {
              "id": new_person_id,
              "identifiers": [
                {
                  "identifier": member['wikidata_id'],
                  "scheme": "wikidata"
                }
              ],
              "other_names": [
                {
                  "family_name": member['name'].rpartition(' ')[2],
                  "given_name": member['name'].rpartition(' ')[0],
                  "note": "Main"
                }
              ]
            }
            pp_data.add_person(new_person)
            pp_person = pp_data.get_person(id=new_person_id)

        else:

            # This prompts a human to check the match and, if correct, hook it up on Wikidata.
            pp_person = pp_data.get_person(name=member['name'])

            if pp_person:
                pp_id = pp_person['id'].rsplit('/', 1)[-1]
                logger.warning(u'{} ({}) appears to match {} by name.'.format(
                    member['name'],
                    member['wikidata_id'],
                    pp_id
                ))
                logger.warning('If this is correct, add TheyWorkForYou ID {} to their Wikidata entry. If not, run with --create to mint new IDs.'.format(pp_id))

            else:

                # If we make it here, we have nothing. Tell the person to run with --create.

                logger.warning(u'{} ({}) cannot be matched on any ID or name. Run with --create to mint new IDs.'.format(
                    member['name'],
                    member['wikidata_id']
                ))

    # By this point, if pp_person exists all is good, if not then it should be skipped and an error raised.
    if pp_person:

        # Can we match up the party?
        if member['party'] in PARTY_TO_ON_BEHALF_OF_ID:

            # Try find an existing membership matching our identifier.

            logger.debug('Finding membership for ID {}'.format(member['membership_id']))

            pp_membership = pp_data.memberships.with_id(member['membership_id'], scheme='wikidata')

            if pp_membership:
                logger.debug('Matched to membership {}'.format(pp_membership['id']))

            else:
                new_membership_id = new_id(pp_data.max_londonassembly_id())
                logger.debug('No matching membership found. Creating new with id {}'.format(new_membership_id))

                new_membership = {
                  "id": new_membership_id,
                  "identifiers": [
                    {
                      "identifier": member['membership_id'],
                      "scheme": "wikidata"
                    }
                  ],
                  "person_id": pp_person['id']
                }

                pp_data.add_membership(new_membership)
                pp_membership = pp_data.memberships.with_id(id=new_membership_id)

            # Update membership details
            pp_membership['organization_id'] = 'london-assembly'
            pp_membership['on_behalf_of_id'] = PARTY_TO_ON_BEHALF_OF_ID[member['party']]
            # This is static for now, but if in future we want to differentiate members by constituency this will need to change.
            pp_membership['post_id'] = 'uk.org.publicwhip/cons/10839'
            pp_membership['start_date'] = member['start_date']

            if 'end_date' in member:
                pp_membership['end_date'] = member['end_date']
            else:
                # It's possible a date will be removed from a membership in Wikidata.
                # This makes sure if that's happened the date is also removed in ParlParse.
                pp_membership.pop('end_date', None)

            logger.debug('Membership updated.'.format(pp_membership['id']))

        else:

            # We can't match this party.

            logger.error('Could not match {} to party name. Edit the map in fetch_london_assembly.py to fix.'.format(member['party']))

    else:
        logger.error(u'Skipping doing anything with {} ({}). This shouldn\'t happen.'.format(
            member['name'],
            member['wikidata_id']
        ))

logger.debug('Writing data to people.json')

pp_data.dump()

logger.debug('Done!')
