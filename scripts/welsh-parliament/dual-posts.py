#!/usr/bin/env python3
#
# This script will search for people who were both MS and MP, or both MS and
# Lord, and add their Wikidata ID to people.json so they match later on

import logging
import sys
from os import path

import requests

# To allow import popolo
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from popolo import Popolo

popolo = Popolo()

logging.basicConfig(
    filename=path.join(path.abspath(__file__), "../../logs/log-dual.txt"),
    filemode="a",
    format="[%(asctime)s] [%(levelname)-8s] --- %(message)s (%(filename)s:%(lineno)s)",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

logger = logging.getLogger()

url = "https://query.wikidata.org/sparql"

query = """
SELECT DISTINCT
  ?member ?memberLabel
WHERE {
  ?node   ps:P279 wd:Q3406079 .
  ?item   p:P279  ?node .
  ?term   ps:P39  ?item .
  ?member p:P39   ?term .
  ?node2  ps:P279 wd:Q16707842 .
  ?item2  p:P279  ?node2 .
  ?term2  ps:P39  ?item2 .
  ?member p:P39   ?term2 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""

r = requests.get(url, params={"format": "json", "query": query})
data = r.json()

# Gather all potential Members of the Senedd who were also MPs from Wikidata

for item in data["results"]["bindings"]:
    wikidata_id = item["member"]["value"].rsplit("/", 1)[-1]
    name = item["memberLabel"]["value"]
    person = popolo.get_person(id=wikidata_id, scheme="wikidata")
    if person:
        logger.debug(
            "{} ({}) matched to existing person {} by Wikidata ID".format(
                name, wikidata_id, person["id"]
            )
        )
    else:
        logger.debug("Finding parlparse ID for {} ({})".format(name, wikidata_id))
        matches = popolo.get_person(name=name)
        if not len(matches):
            logger.debug("No match - will be a Lord")
            continue
        if len(matches) > 1:
            logger.debug("Multiple matches, filtering to modern ones")
            matches = [
                m
                for m in matches
                if popolo.memberships.of_person(m["id"]).on("2010-01-01")
            ]
            assert len(matches) == 1
        match = matches[0]
        logger.debug(
            "Adding ID {} to person {} ({})".format(wikidata_id, name, match["id"])
        )
        popolo.persons[match["id"]]["identifiers"].append(
            {"scheme": "wikidata", "identifier": wikidata_id}
        )

query = """
SELECT DISTINCT
  ?member ?memberLabel
WHERE {
  ?node   ps:P279 wd:Q3406079 .
  ?item   p:P279  ?node .
  ?term   ps:P39  ?item .
  ?member p:P39   ?term .
  ?node2  ps:P39  wd:Q18952564 .
  ?member p:P39   ?node2 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
}
"""

r = requests.get(url, params={"format": "json", "query": query})
data = r.json()

# Gather all potential Members of the Senedd who were also Lords from Wikidata

for item in data["results"]["bindings"]:
    wikidata_id = item["member"]["value"].rsplit("/", 1)[-1]
    name = item["memberLabel"]["value"]
    person = popolo.get_person(id=wikidata_id, scheme="wikidata")
    if person:
        logger.debug(
            "{} ({}) matched to existing person {} by Wikidata ID".format(
                name, wikidata_id, person["id"]
            )
        )
    else:
        logger.debug("Finding parlparse ID for {} ({})".format(name, wikidata_id))
        if "," in name:
            name = name.split(", ")[1].replace("Baron ", "Lord ")
        else:
            # Special cases
            if name == "Jenny Randerson":
                name = "Jennifer Randerson"
            if name == "Nick Bourne":
                name = "Nicholas Bourne"
            first, last = name.split(" ")
            for person in popolo.persons.values():
                for n in person["other_names"]:
                    if n.get("lordname") == last and n.get("given_name").startswith(
                        first
                    ):
                        name = popolo.names[person["id"]]

        matches = popolo.get_person(name=name)
        assert len(matches) == 1
        match = matches[0]
        logger.debug(
            "Adding ID {} to person {} ({})".format(wikidata_id, name, match["id"])
        )
        popolo.persons[match["id"]]["identifiers"].append(
            {"scheme": "wikidata", "identifier": wikidata_id}
        )

popolo.dump()
