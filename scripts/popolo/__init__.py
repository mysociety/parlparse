import json
import os

cur_dir = os.path.dirname(__file__)
JSON = os.path.join(cur_dir, '..', '..', 'members', 'people.json')


class Memberships(object):
    def __init__(self, mships, data):
        self.memberships = mships
        self.data = data

    def __iter__(self):
        return iter(self.memberships)

    def in_org(self, house):
        if house == 'house-of-lords':
            self.memberships = [m for m in self.memberships if 'organization_id' in m and m['organization_id'] == house]
        else:
            self.memberships = [m for m in self.memberships if 'post_id' in m and self.data.posts[m['post_id']]['organization_id'] == house]
        return Memberships(self.memberships, self.data)

    def on(self, date):
        self.memberships = [m for m in self.memberships if m.get('start_date', '0000-00-00') <= date <= m.get('end_date', '9999-12-31')]
        return Memberships(self.memberships, self.data)


class Popolo(object):
    def __init__(self):
        self.load(JSON)

    def load(self, json_file):
        self.json = j = json.load(open(json_file))
        self.persons = {p['id']: p for p in j['persons']}
        self.posts = {p['id']: p for p in j['posts']}
        self.orgs = {o['name']: o['id'] for o in j['organizations']}
        self.memberships = Memberships(j['memberships'], self)

    def dump(self):
        json.dump(self.json, open(JSON, 'w'), indent=2, sort_keys=True)
