#!/usr/bin/env python

# Fetch London Assembly members from Wikidata

import argparse
import logging

import requests

from popolo import Popolo
from popolo.utils import edit_file, new_id


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

logger.info('Importing London Assembly Members from Wikidata')

query = '''SELECT ?item ?itemLabel ?electoraldistrict ?electoraldistrictLabel ?parliamentarygroup ?parliamentarygroupLabel ?starttime ?endtime ?twfy_id WHERE {
    ?node ps:P39 wd:Q56573014 .
    ?item p:P39 ?node .
    ?node pq:P580 ?starttime .
    OPTIONAL { ?item wdt:P2171 ?twfy_id }
    OPTIONAL { ?node pq:P4100 ?parliamentarygroup }
    OPTIONAL { ?node pq:P768 ?electoraldistrict }
    OPTIONAL { ?node pq:P582 ?endtime }
    OPTIONAL { ?node pq:P2715 ?election }
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}'''

url = 'https://query.wikidata.org/sparql'
data = requests.get(url, params={'query': query, 'format': 'json'}).json()

pp_data = Popolo()

for item in data['results']['bindings']:

    member = {
        'wikidata_id': item['item']['value'].rsplit('/', 1)[-1],
        'name': item['itemLabel']['value']
    }

    if 'twfy_id' in item:
        member['parlparse_id'] = item['twfy_id']['value']

    logger.info(u'{} ({}) found in Wikidata'.format(member['name'], member['wikidata_id']))

    # Try retrieve this person by Wikidata ID, if that is known
    pp_person = pp_data.get_person(id=member['wikidata_id'], scheme='wikidata')

    if pp_person:

        pp_id = pp_person['id'].rsplit('/', 1)[-1]

        # This person has been matched on Wikidata ID. Hooray!

        logger.info(u'{} ({}) matched to existing person {} by Wikidata ID'.format(
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
                logger.info(u'{} ({}) has expected ParlParse ID'.format(
                    member['name'],
                    member['wikidata_id'],
                ))

    else:

        # This person hasn't been matched on Wikidata ID. Can we do it by ParlParse ID?

        if 'parlparse_id' in member:
            pp_person = pp_data.get_person(id=member['parlparse_id'], scheme='wikidata')

            if pp_person:

                pp_id = pp_person['id'].rsplit('/', 1)[-1]

                logger.info(u'{} ({}) matched to existing person {} by ParlParse ID'.format(
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

            logger.info('Minting new ID.')

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

        # This is where processing actual memberships will go
        pass

    else:
        logger.error(u'Skipping doing anything with {} ({}). This shouldn\'t happen.'.format(
            member['name'],
            member['wikidata_id']
        ))

logger.debug('Writing data to people.json')

pp_data.dump()

logger.debug('Done!')
