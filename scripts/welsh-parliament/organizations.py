#!/usr/bin/env python3

from os import path, sys

# To allow import popolo
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import logging
import requests
from popolo import Popolo
import re

# Logging:
logging.basicConfig(filename=path.join(path.abspath(__file__), "../../logs/log-organizations.txt"),
                    filemode='a',
                    format="[%(asctime)s] [%(levelname)-8s] --- %(message)s (%(filename)s:%(lineno)s)",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.DEBUG)

logger = logging.getLogger()

url = "https://query.wikidata.org/sparql"
query = """
SELECT DISTINCT
  ?parliamentarygroup ?parliamentarygroupLabel ?partof ?partofLabel #organization_id
WHERE {
  ?node   ps:P279 wd:Q3406079 .
  ?item   p:P279  ?node .
  ?term   ps:P39  ?item .
  ?member p:P39   ?term .
  ?term   pq:P580 ?starttime .
  OPTIONAL { ?term pq:P4100 ?parliamentarygroup }
  OPTIONAL { ?parliamentarygroup wdt:P361 ?partof }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""

r = requests.get(url, params = {"format": "json", "query": query})
data = r.json()

# Gather all potential Senedd organizations from Wikidata

candidates = []
for item in data["results"]["bindings"]:
    if "partofLabel" in item:
        candidate = {
            "wikidata_id": item["partof"]["value"].rsplit("/", 1)[-1],
            "name"       : item["partofLabel"]["value"]
        }
    else:
        candidate = {
            "wikidata_id": item["parliamentarygroup"]["value"].rsplit("/", 1)[-1],
            "name"       : item["parliamentarygroupLabel"]["value"]
        }

    if candidate["name"] == "independent politician":
        candidate["name"] = "independent"

    candidates.append(candidate)

popolo = Popolo()

# Check whether each candidate already exists, if not, create them

for candidate in candidates:

    logger.debug("Looking at {} ({}):".format(
        candidate["name"],
        candidate["wikidata_id"]
    ))

    org = popolo.get_organization(id=candidate["wikidata_id"], scheme="wikidata")

    if org:

        logger.debug("{} ({}) matched to existing org {} by Wikidata ID".format(
            candidate["name"],
            candidate["wikidata_id"],
            org["id"]
        ))

        if "parlparse_id" not in candidate:
            logger.warning("{} ({}) does not have a TWFY ID set in Wikidata. Expected {}.".format(
                candidate["name"],
                candidate["wikidata_id"],
                org["id"]
            ))

        else:

            if candidate["parlparse_id"] != org["id"]:
                logger.warning("{} ({}) has a parlparse ID of {}, expected {}.".format(
                    candidate["name"],
                    candidate["wikidata_id"],
                    candidate["parlparse_id"],
                    org["id"]
                ))

            else:
                logger.debug("{} ({}) has expected parlparse ID".format(
                    candidate["name"],
                    candidate["wikidata_id"],
                ))

    else:

        logger.debug("Creating parlparse ID for {} ({})".format(candidate["name"], candidate["wikidata_id"]))

        new_org_id = re.sub("'", "", re.sub(r'\s', '-', candidate["name"])).lower()
        logger.debug("Parlparse ID is {}".format(new_org_id))

        new_org = {
          "classification": "party",
          "id": new_org_id,
          "identifiers": [
            {
              "identifier": candidate["wikidata_id"],
              "scheme": "wikidata"
            }
          ],
          "name": candidate["name"]
        }

        popolo.add_organization(new_org)

logger.debug("Writing data to people.json")
popolo.dump()
logger.debug("Data has been written to people.json")
