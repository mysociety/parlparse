import datetime
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

    def __len__(self):
        return len(self.memberships)

    def __str__(self):
        s = '[\n'
        for m in self:
            s += '%(id)s, %(person_id)s, ' % m
            if 'start_reason' in m: s += '(%(start_reason)s) ' % m
            s += '%(start_date)s - ' % m
            if 'end_date' in m: s += '%(end_date)s' % m
            if 'end_reason' in m: s += ' (%(end_reason)s)' % m
            if 'post_id' in m: s += ' %(post_id)s' % m
            s += '\n'
        s += ']'
        return s

    def in_org(self, house):
        if house == 'house-of-lords':
            mships = [m for m in self.memberships if 'organization_id' in m and m['organization_id'] == house]
        else:
            mships = [m for m in self.memberships if 'post_id' in m and self.data.posts[m['post_id']]['organization_id'] == house]
        return Memberships(mships, self.data)

    def of_person(self, pid):
        mships = [m for m in self.memberships if m['person_id'] == pid]
        return Memberships(mships, self.data)

    def on(self, date):
        mships = [m for m in self.memberships if m.get('start_date', '0000-00-00') <= date <= m.get('end_date', '9999-12-31')]
        return Memberships(mships, self.data)

    def current(self):
        return self.on(datetime.date.today().isoformat())


class Popolo(object):
    def __init__(self):
        self.load(JSON)

    def load(self, json_file):
        self.json = j = json.load(open(json_file))
        self.persons = {p['id']: p for p in j['persons'] if 'redirect' not in p}
        self.posts = {p['id']: p for p in j['posts']}
        self.orgs = {o['name']: o['id'] for o in j['organizations']}
        self.memberships = Memberships([m for m in j['memberships'] if 'redirect' not in m], self)
        self.names = {}

        for p in self.persons.values():
            names = [n for n in p['other_names'] if n['note'] == 'Main']
            n = sorted(names, key=lambda x: x.get('start_date', '0000-00-00'), reverse=True)[0]
            if 'lordname' in n:
                name = n['honorific_prefix']
                if n['lordname']:
                    name += ' ' + n['lordname']
                if n['lordofname']:
                    name += ' of ' + n['lordofname']
            else:
                name = n['family_name']
                if 'given_name' in n:
                    name = n['given_name'] + ' ' + name
            self.names[p['id']] = name

    def get_person(self, id=None, name=None):
        if name:
            return [p for p in self.persons.values() if self.names[p['id']] == name]
        if id:
            return (p for p in self.persons.values() if p['id'] == id).next()

    def dump(self):
        json.dump(self.json, open(JSON, 'w'), indent=2, sort_keys=True)
