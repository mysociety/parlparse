#!/usr/bin/env python

# Fetch a legislature from EveryPolitician, and for all people with a ParlParse
# ID and Wikidata ID import the Wikidata ID.

from everypolitician import EveryPolitician
from popolo import Popolo
from popolo.utils import edit_file


def getPersonIdentifierBySchema(person, scheme):
    if 'identifiers' in person:
        for identifier in person['identifiers']:
            if identifier['scheme'] == scheme:
                return identifier['identifier']
    return None


legislatures_to_fetch = [
    {
        'ep_country_slug': 'UK',
        'ep_legislature_slug': 'Commons'
    },
    {
        'ep_country_slug': 'Scotland',
        'ep_legislature_slug': 'Parliament'
    },
    {
        'ep_country_slug': 'Northern-Ireland',
        'ep_legislature_slug': 'Assembly'
    },
]

pp_data = Popolo()

for legislature in legislatures_to_fetch:

    ep_country = EveryPolitician().country(legislature['ep_country_slug'])
    ep_legislature = ep_country.legislature(legislature['ep_legislature_slug'])

    ep_people = ep_legislature.popolo().persons

    print ('{}/{}: Found {} people.'.format(legislature['ep_country_slug'],
                                            legislature['ep_legislature_slug'],
                                            len(ep_people)
                                            ))

    for ep_person in ep_people:
        if ep_person.identifier_value('parlparse') and ep_person.wikidata:
            pp_person = pp_data.get_person(id=ep_person.identifier_value('parlparse'))

            pp_wikidata_identifier = getPersonIdentifierBySchema(pp_person, 'wikidata')

            if not pp_wikidata_identifier:
                print ('{} ({}) is missing a Wikidata identifier of {}, fixing...'.format(ep_person.name.encode('utf-8'), pp_person['id'], ep_person.wikidata))

                if 'identifiers' not in pp_person:
                    pp_person['identifiers'] = []

                pp_person['identifiers'].append(
                    {
                        'scheme': 'wikidata',
                        'identifier': ep_person.wikidata
                    }
                )

            elif pp_wikidata_identifier != ep_person.wikidata:
                print ('{} ({}) has a Wikidata identifier mismatch ({} in Parlparse vs {} in EveryPolitician). Please resolve manually!'.format(ep_person.name.encode('utf-8'), pp_person['id'], pp_wikidata_identifier, ep_person.wikidata))

            pp_data.persons[pp_person['id']].update(pp_person)

        else:
            print('Skipping person {}, does not have both ParlParse and Wikidata IDs.'.format(ep_person.name.encode('utf-8')))

print ('Writing data...')

pp_data.dump()

print ('Done!')
