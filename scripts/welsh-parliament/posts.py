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
    filename=path.join(path.abspath(__file__), "../../logs/log-posts.txt"),
    filemode="a",
    format="[%(asctime)s] [%(levelname)-8s] --- %(message)s (%(filename)s:%(lineno)s)",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

logger = logging.getLogger()

url = "https://query.wikidata.org/sparql"
query = """
SELECT
  ?post ?postLabel (year(?inception) as ?inceptionYear) (year(?dissolved) as ?dissolvedYear)
WHERE {
  ?node   ps:P279 wd:Q6970524 .
  ?item   p:P279  ?node .
  ?region ps:P31  ?item .
  ?post   p:P31   ?region .
  OPTIONAL {?post wdt:P571 ?inception}
  OPTIONAL {?post wdt:P576 ?dissolved}
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""

r = requests.get(url, params={"format": "json", "query": query})
data = r.json()

# Gather all potential Senedd posts from Wikidata

candidates = []
for item in data["results"]["bindings"]:
    candidate = {
        "wikidata_id": item["post"]["value"].rsplit("/", 1)[-1],
        "name": item["postLabel"]["value"],
    }

    if "inceptionYear" in item:
        candidate["start_date"] = item["inceptionYear"]["value"]

    if "dissolvedYear" in item:
        candidate["end_date"] = item["dissolvedYear"]["value"]

    candidates.append(candidate)

popolo = Popolo()
candidates.sort(key=lambda c: (c["start_date"], c["name"]))

# Check whether each candidate already exists, if not, create them

for candidate in candidates:
    logger.debug(
        "Looking at {} ({}):".format(candidate["name"], candidate["wikidata_id"])
    )

    post = popolo.get_post(id=candidate["wikidata_id"], scheme="wikidata")

    if post:
        logger.debug(
            "{} ({}) matched to existing post {} by Wikidata ID".format(
                candidate["name"], candidate["wikidata_id"], post["id"]
            )
        )

        if "parlparse_id" not in candidate:
            logger.warning(
                "{} ({}) does not have a TWFY ID set in Wikidata. Expected {}.".format(
                    candidate["name"], candidate["wikidata_id"], post["id"]
                )
            )

        else:
            if candidate["parlparse_id"] != post["id"]:
                logger.warning(
                    "{} ({}) has a parlparse ID of {}, expected {}.".format(
                        candidate["name"],
                        candidate["wikidata_id"],
                        candidate["parlparse_id"],
                        post["id"],
                    )
                )

            else:
                logger.debug(
                    "{} ({}) has expected parlparse ID".format(
                        candidate["name"],
                        candidate["wikidata_id"],
                    )
                )

    else:
        logger.debug(
            "Creating parlparse ID for {} ({})".format(
                candidate["name"], candidate["wikidata_id"]
            )
        )

        new_post_id = new_id(popolo.max_post_id("welsh-parliament", range_start=70000))
        logger.debug("Parlparse ID is {}".format(new_post_id))

        new_post = {
            "area": {"name": candidate["name"]},
            "id": new_post_id,
            "identifiers": [
                {"identifier": candidate["wikidata_id"], "scheme": "wikidata"}
            ],
            "label": "MS for {}".format(candidate["name"]),
            "organization_id": "welsh-parliament",
            "role": "MS",
        }

        if "start_date" in candidate:
            new_post["start_date"] = candidate["start_date"]

        if "end_date" in candidate:
            new_post["end_date"] = candidate["end_date"]

        popolo.add_post(new_post)

logger.debug("Writing data to people.json")
popolo.dump()
logger.debug("Data has been written to people.json")
