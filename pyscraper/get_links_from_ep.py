#!/usr/bin/env python3

import operator

from everypolitician import EveryPolitician
from lxml import etree


def output_file(country, legislature, filename):
    data = EveryPolitician().country(country).legislature(legislature)
    output_filename = "../members/{0}.xml".format(filename)
    root = etree.Element("publicwhip")

    sorted_people = sorted(data.popolo().persons, key=operator.attrgetter("name"))
    for person in sorted_people:
        parlparse_id = person.identifier_value("parlparse")
        if parlparse_id is not None:
            props = {}
            if person.twitter:
                props["twitter_username"] = person.twitter
            if person.facebook:
                props["facebook_page"] = person.facebook

            if props:
                props["id"] = parlparse_id
                info = etree.Element("personinfo", props)
                root.append(info)

    et = etree.ElementTree(root)
    et.write(output_filename, pretty_print=True)


output_file("UK", "Commons", "social-media-commons")
output_file("Scotland", "Parliament", "social-media-sp")
output_file("Northern-Ireland", "Assembly", "social-media-ni")
