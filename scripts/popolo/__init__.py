import datetime
import json
import os

cur_dir = os.path.dirname(__file__)
JSON = os.path.join(cur_dir, "..", "..", "members", "people.json")


class Memberships(object):
    def __init__(self, mships, data):
        self._memberships = mships
        self.data = data

    def __iter__(self):
        return iter(self.memberships)

    def __len__(self):
        return len(self.memberships)

    def __str__(self):
        s = "[\n"
        for m in self:
            s += "%(id)s, %(person_id)s, " % m
            if "start_reason" in m:
                s += "(%(start_reason)s) " % m
            s += "%(start_date)s - " % m
            if "end_date" in m:
                s += "%(end_date)s" % m
            if "end_reason" in m:
                s += " (%(end_reason)s)" % m
            if "post_id" in m:
                s += " " + self.data.posts[m["post_id"]]["area"]["name"]
                s += " %(post_id)s" % m
            s += "\n"
        s += "]"
        return s

    @property
    def memberships(self):
        return [m for m in self._memberships if "redirect" not in m]

    def in_org(self, house):
        if house == "house-of-lords":
            mships = [
                m
                for m in self.memberships
                if "organization_id" in m and m["organization_id"] == house
            ]
        else:
            mships = [
                m
                for m in self.memberships
                if "post_id" in m
                and self.data.posts[m["post_id"]]["organization_id"] == house
            ]
        return Memberships(mships, self.data)

    def of_person(self, pid):
        mships = [m for m in self.memberships if m["person_id"] == pid]
        return Memberships(mships, self.data)

    def on(self, date):
        mships = [
            m
            for m in self.memberships
            if m.get("start_date", "0000-00-00")
            <= date
            <= m.get("end_date", "9999-12-31")
        ]
        return Memberships(mships, self.data)

    def with_id(self, id, scheme=None):
        if scheme:
            for m in self.memberships:
                if "identifiers" in m:
                    for identifier in m["identifiers"]:
                        if (
                            identifier["scheme"] == scheme
                            and identifier["identifier"] == id
                        ):
                            return m
        else:
            for m in self.memberships:
                if m["id"] == id:
                    return m

        return None

    def current(self):
        return self.on(datetime.date.today().isoformat())


class Popolo(object):
    def __init__(self):
        self.load(JSON)

    def update_persons_map(self):
        self.persons = {p["id"]: p for p in self.json["persons"] if "redirect" not in p}
        self.posts = {p["id"]: p for p in self.json["posts"]}
        self.orgs = {o["id"]: o for o in self.json["organizations"]}
        self.names = {}
        self.identifiers = {}

        for p in self.persons.values():
            names = [n for n in p["other_names"] if n["note"] == "Main"]
            n = sorted(
                names, key=lambda x: x.get("start_date", "0000-00-00"), reverse=True
            )[0]
            if "lordname" in n:
                name = n["honorific_prefix"]
                if n["lordname"]:
                    name += " " + n["lordname"]
                if n["lordofname"]:
                    name += " of " + n["lordofname"]
            else:
                name = n["family_name"]
                if "given_name" in n:
                    name = n["given_name"] + " " + name
            self.names[p["id"]] = name

            for i in p.get("identifiers", []):
                self.identifiers.setdefault(i["scheme"], {})[i["identifier"]] = p

    def update_memberships(self):
        self.memberships = None
        self.memberships = Memberships(self.json["memberships"], self)

    def update_orgs(self):
        self.orgs = {o["id"]: o for o in self.json["organizations"]}

    def update_posts(self):
        self.posts = {p["id"]: p for p in self.json["posts"]}

    @property
    def houses(self):
        post_houses = set(m["organization_id"] for m in self.posts.values())
        org_houses = set(
            m["organization_id"] for m in self.memberships if "organization_id" in m
        )
        return post_houses.union(org_houses)

    def load(self, json_file):
        self.json = json.load(open(json_file))
        self.update_persons_map()
        self.update_memberships()

    def _get_thing(self, things, id=None, name=None, scheme=None, typ=None):
        if name:
            if typ == "person":
                return [p for p in things.values() if self.names[p["id"]] == name]
            else:
                return [o for o in things.values() if o["name"] == name]
        if id:
            if scheme:
                try:
                    return next(
                        p
                        for p in things.values()
                        for i in p.get("identifiers", [])
                        if i["scheme"] == scheme and i["identifier"] == id
                    )
                except StopIteration:
                    return None
            else:
                return next(o for o in things.values() if o["id"] == id)

    # Get a person either by name, by parlparse ID, or if scheme is specified by another identifier
    def get_person(self, id=None, name=None, scheme=None):
        return self._get_thing(self.persons, id, name, scheme, "person")

    def get_organization(self, id=None, name=None, scheme=None):
        return self._get_thing(self.orgs, id, name, scheme)

    def get_post(self, id=None, name=None, scheme=None):
        return self._get_thing(self.posts, id, name, scheme)

    def add_person(self, person):
        self.json["persons"].append(person)
        self.update_persons_map()

    def add_membership(self, mship):
        self.json["memberships"].append(mship)
        self.update_memberships()

    def add_organization(self, org):
        self.json["organizations"].append(org)
        self.update_orgs()

    def add_post(self, post):
        self.json["posts"].append(post)
        self.update_posts()

    def _max_member_id(self, house, type="member", range_start=0):
        house_memberships = self.memberships.in_org(house)
        if house_memberships:
            id = max(
                int(m["id"].replace("uk.org.publicwhip/%s/" % type, ""))
                for m in house_memberships
            )
        else:
            id = range_start
        return "uk.org.publicwhip/%s/%d" % (type, id)

    def max_post_id(self, house, type="cons", range_start=0):
        house_posts = [p for p in self.posts.values() if p["organization_id"] == house]
        if house_posts:
            id = max(
                int(p["id"].replace("uk.org.publicwhip/%s/" % type, ""))
                for p in house_posts
            )
        else:
            id = range_start
        return "uk.org.publicwhip/%s/%d" % (type, id)

    max_mp_id = lambda self: self._max_member_id(
        "house-of-commons", range_start=0
    )  # Range ends at 69999
    max_ms_id = lambda self: self._max_member_id(
        "welsh-parliament", range_start=70000
    )  # Range ends at 79999
    max_msp_id = lambda self: self._max_member_id(
        "scottish-parliament", range_start=80000
    )  # Range ends at 89999
    max_mla_id = lambda self: self._max_member_id(
        "northern-ireland-assembly", range_start=90000
    )  # Range ends at 99999
    max_lord_id = lambda self: self._max_member_id(
        "house-of-lords", "lord", range_start=100000
    )  # Range ends at 199999
    max_londonassembly_id = lambda self: self._max_member_id(
        "london-assembly", range_start=200000
    )  # Range ends at 299999

    def max_person_id(self):
        id = max(p for p in self.persons.keys())
        return id

    def _verify(self, coll):
        seen = set()
        dupe = [
            x["id"] for x in self.json[coll] if x["id"] in seen or seen.add(x["id"])
        ]
        assert len(dupe) == 0, "Duplicate %s IDs: %s" % (coll, dupe)

    def verify(self):
        self._verify("persons")
        self._verify("memberships")

    def dump(self):
        self.verify()
        json.dump(self.json, open(JSON, "w"), indent=2, sort_keys=True)
