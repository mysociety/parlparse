#!/usr/bin/env python3

from os import path, sys

# To allow import popolo
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import logging
import requests
from popolo import Popolo
from popolo.utils import new_id

# Logging:
logging.basicConfig(filename=path.join(path.abspath(__file__), "../../logs/log-persons.txt"),
                    filemode='a',
                    format="[%(asctime)s] [%(levelname)-8s] --- %(message)s (%(filename)s:%(lineno)s)",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.DEBUG)

logger = logging.getLogger()

url = "https://query.wikidata.org/sparql"

query = """
SELECT DISTINCT
  ?member ?memberLabel    #person_id
  ?parlparse_id           #they work for you identifier
WHERE {
  ?node   ps:P279 wd:Q3406079 .
  ?item   p:P279  ?node .
  ?term   ps:P39  ?item .
  ?member p:P39   ?term .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""

r = requests.get(url, params = {"format": "json", "query": query})
data = r.json()

# Gather all potential Members of the Senedd from Wikidata

candidates = []
for item in data["results"]["bindings"]:
    candidate = {
        "wikidata_id": item["member"]["value"].rsplit("/", 1)[-1],
        "name"       : item["memberLabel"]["value"],
        "family_name": item["memberLabel"]["value"].rpartition(" ")[2],
        "given_name" : item["memberLabel"]["value"].rpartition(" ")[0],
    }

    if "parlparse_id" in item:
        candidate["parlparse_id"] = item["parlparse_id"]["value"]

    candidates.append(candidate)

popolo = Popolo()

# Check whether each candidate already exists, if not, create them

for candidate in candidates:

    logger.debug("Looking at {} ({}):".format(
        candidate["name"],
        candidate["wikidata_id"]
    ))

    person = popolo.get_person(id=candidate["wikidata_id"], scheme="wikidata")

    if person:

        logger.debug("{} ({}) matched to existing person {} by Wikidata ID".format(
            candidate["name"],
            candidate["wikidata_id"],
            person["id"]
        ))

        if "parlparse_id" not in candidate:
            logger.warning("{} ({}) does not have a TWFY ID set in Wikidata. Expected {}.".format(
                candidate["name"],
                candidate["wikidata_id"],
                person["id"]
            ))

        else:

            if candidate["parlparse_id"] != person["id"]:
                logger.warning("{} ({}) has a parlparse ID of {}, expected {}.".format(
                    candidate["name"],
                    candidate["wikidata_id"],
                    candidate["parlparse_id"],
                    person["id"]
                ))

            else:
                logger.debug("{} ({}) has expected parlparse ID".format(
                    candidate["name"],
                    candidate["wikidata_id"],
                ))

    else:

        logger.debug("Creating parlparse ID for {} ({})".format(candidate["name"], candidate["wikidata_id"]))

        new_person_id = new_id(popolo.max_person_id())
        logger.debug("Parlparse ID is {}".format(new_person_id))

        new_person = {
          "id": new_person_id,
          "identifiers": [
            {
              "identifier": candidate["wikidata_id"],
              "scheme": "wikidata"
            }
          ],
          "other_names": [
            {
              "family_name": candidate["family_name"],
              "given_name": candidate["given_name"],
              "note": "Main"
            }
          ]
        }

        popolo.add_person(new_person)

logger.debug("Writing data to people.json")
popolo.dump()
logger.debug("Data has been written to people.json")
