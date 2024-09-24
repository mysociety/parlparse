#!/usr/bin/env python3

import sys
from os import path

# To allow import popolo
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import logging

import requests
from popolo import Popolo
from popolo.utils import new_id

# Logging:
logging.basicConfig(
    filename=path.join(path.abspath(__file__), "../../logs/log-memberships.txt"),
    filemode="a",
    format="[%(asctime)s] [%(levelname)-8s] --- %(message)s (%(filename)s:%(lineno)s)",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

logger = logging.getLogger()

url = "https://query.wikidata.org/sparql"
query = """
SELECT
  ?item ?itemLabel
  ?term ?termLabel
  ?member ?memberLabel
  ?parliamentarygroup ?parliamentarygroupLabel ?partof
  ?post ?postLabel
  ?electionLabel
  ?starttime ?endtime
  ?endcauseLabel
  ?twfy_id
WHERE {
  ?node   ps:P279 wd:Q3406079 .
  ?item   p:P279  ?node .
  ?term   ps:P39  ?item .
  ?member p:P39   ?term .
  ?term   pq:P580 ?starttime .
  OPTIONAL { ?term wdt:P2171 ?twfy_id }
  OPTIONAL { ?term pq:P4100 ?parliamentarygroup }
  OPTIONAL { ?term pq:P768 ?post }
  OPTIONAL { ?term pq:P582 ?endtime }
  OPTIONAL { ?term pq:P1534 ?endcause }
  OPTIONAL { ?term pq:P2715 ?election }
  OPTIONAL { ?parliamentarygroup wdt:P361 ?partof }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""

r = requests.get(url, params={"format": "json", "query": query})
data = r.json()

# Gather all potential memberships of Members of the Senedd from Wikidata

candidates = []
for item in data["results"]["bindings"]:
    if "partof" in item:
        on_behalf_of_id = item["partof"]["value"]
    else:
        on_behalf_of_id = item["parliamentarygroup"]["value"]
    candidate = {
        "wikidata_id": item["term"]["value"].rsplit("/", 1)[-1],
        "name": item["memberLabel"]["value"],
        "person_id": item["member"]["value"].rsplit("/", 1)[-1],
        "post_id": item["post"]["value"].rsplit("/", 1)[-1],
        "on_behalf_of_id": on_behalf_of_id.rsplit("/", 1)[-1],
        "start_date": item["starttime"]["value"].split("T")[0],
    }

    if "twfy_id" in item:
        candidate["parlparse_id"] = item["twfy_id"]["value"]

    if "election" in item:
        candidate["start_reason"] = item["election"]["value"].rsplit("/", 1)[-1]

    if "endtime" in item:
        candidate["end_date"] = item["endtime"]["value"].split("T")[0]

    if "endcause" in item:
        candidate["end_reason"] = item["endcause"]["value"].rsplit("/", 1)[-1]

    candidates.append(candidate)

candidates.sort(key=lambda c: (c["start_date"], c["name"], c["post_id"]))
popolo = Popolo()

# Check whether each candidate already exists, if not, create them

for candidate in candidates:
    logger.debug(
        "Looking at {}'s membership ({}):".format(
            candidate["name"], candidate["wikidata_id"]
        )
    )

    membership = popolo.memberships.with_id(
        id=candidate["wikidata_id"], scheme="wikidata"
    )

    if membership:
        logger.debug(
            "{}'s membership ({}) matched to existing membership {} by Wikidata ID".format(
                candidate["name"], candidate["wikidata_id"], membership["id"]
            )
        )

        if "parlparse_id" not in candidate:
            logger.warning(
                "{}'s membership ({}) does not have a TWFY ID set in Wikidata. Expected {}.".format(
                    candidate["name"], candidate["wikidata_id"], membership["id"]
                )
            )

        else:
            if candidate["parlparse_id"] != membership["id"]:
                logger.warning(
                    "{}'s membership ({}) has a parlparse ID of {}, expected {}.".format(
                        candidate["name"],
                        candidate["wikidata_id"],
                        candidate["parlparse_id"],
                        membership["id"],
                    )
                )

            else:
                logger.debug(
                    "{}'s membership ({}) has expected parlparse ID".format(
                        candidate["name"],
                        candidate["wikidata_id"],
                    )
                )

    else:
        logger.debug(
            "Creating parlparse ID for {}'s membership ({})".format(
                candidate["name"], candidate["wikidata_id"]
            )
        )

        new_membership_id = new_id(popolo.max_ms_id())
        logger.debug("Parlparse ID is {}".format(new_membership_id))

        new_membership = {
            "id": new_membership_id,
            "identifiers": [
                {"identifier": candidate["wikidata_id"], "scheme": "wikidata"}
            ],
            "start_date": candidate["start_date"],
        }

        if "person_id" in candidate:
            new_membership["person_id"] = popolo.get_person(
                id=candidate["person_id"], scheme="wikidata"
            )["id"]

        if "post_id" in candidate:
            new_membership["post_id"] = popolo.get_post(
                id=candidate["post_id"], scheme="wikidata"
            )["id"]

        if "on_behalf_of_id" in candidate:
            new_membership["on_behalf_of_id"] = popolo.get_organization(
                id=candidate["on_behalf_of_id"], scheme="wikidata"
            )["id"]

        if "start_reason" in candidate:
            new_membership["start_reason"] = candidate["start_reason"]

        if "end_date" in candidate:
            new_membership["end_date"] = candidate["end_date"]

        if "end_reason" in candidate:
            new_membership["end_reason"] = candidate["end_reason"]

        popolo.add_membership(new_membership)

logger.debug("Writing data to people.json")
popolo.dump()
logger.debug("Data has been written to people.json")
