#!/usr/bin/env python3

from os import path, sys

# To allow import popolo
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import logging
import requests
from popolo import Popolo
from xml.etree import ElementTree

# Logging:
logging.basicConfig(filename=path.join(path.abspath(__file__), "../../logs/log-official-ids.txt"),
                    filemode='a',
                    format="[%(asctime)s] [%(levelname)-8s] --- %(message)s (%(filename)s:%(lineno)s)",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.DEBUG)

logger = logging.getLogger()

url = 'https://business.senedd.wales/mgwebservice.asmx/GetCouncillorsByWard'
r = requests.get(url)
data = ElementTree.fromstring(r.content)

# Gather all potential Members of the Senedd from official API

NAME_FIXES = {
    'Eluned Morgan': 'Baroness Morgan of Ely',
}

candidates = []
for item in data.findall('.//councillor'):
    name = item.find('fullusername').text
    name = name.replace(' MS', '')
    name = name.replace('Rt. Hon. ', '')
    name = NAME_FIXES.get(name, name)
    candidate = {
        "official_id": item.find('councillorid').text,
        "name"       : name,
    }
    candidates.append(candidate)

popolo = Popolo()

# Check whether each candidate already exists, if not, create them

for candidate in candidates:

    logger.debug("Looking at {} ({}):".format(
        candidate["name"],
        candidate["official_id"]
    ))

    person = popolo.get_person(id=candidate["official_id"], scheme="senedd")

    if person:
        logger.debug("{} ({}) matched to existing person {} by ID".format(
            candidate["name"], candidate["official_id"], person["id"]))
    else:
        matches = popolo.get_person(name=candidate["name"])
        matches = [m for m in matches if len(popolo.memberships.of_person(m["id"]).in_org('welsh-parliament'))]
        if not matches:
            logger.warning('Could not find matching person for {}'.format(candidate["name"]))
            sys.exit('Could not find matching person for {}'.format(candidate["name"]))
        if len(matches) > 1:
            sys.exit('Too many matches for {}'.format(candidate["name"]))
        person = matches[0]
        logger.debug("Adding identifier {} to person {}".format(candidate["official_id"], person["id"]))
        person["identifiers"].append({ "identifier": candidate["official_id"], "scheme": "senedd" })

logger.debug("Writing data to people.json")
popolo.dump()
logger.debug("Data has been written to people.json")
