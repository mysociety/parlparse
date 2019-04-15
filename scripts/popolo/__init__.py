import datetime
import json
import os

cur_dir = os.path.dirname(__file__)
JSON = os.path.join(cur_dir, '..', '..', 'members', 'people.json')


class Memberships(object):
    def __init__(self, mships, data):
        self._memberships = mships
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

    @property
    def memberships(self):
        return [m for m in self._memberships if 'redirect' not in m]

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

    def update_persons_map(self):
        self.persons = {p['id']: p for p in self.json['persons'] if 'redirect' not in p}
        self.posts = {p['id']: p for p in self.json['posts']}
        self.orgs = {o['name']: o['id'] for o in self.json['organizations']}
        self.memberships = Memberships(self.json['memberships'], self)
        self.names = {}
        self.identifiers = {}

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

            for i in p.get('identifiers', []):
                self.identifiers.setdefault(i['scheme'], {})[i['identifier']] = p

    def load(self, json_file):
        self.json = j = json.load(open(json_file))
        self.update_persons_map()

    # Get a person either by name, by parlparse ID, or if scheme is specified by another identifier
    def get_person(self, id=None, name=None, scheme=None):
        if name:
            return [p for p in self.persons.values() if self.names[p['id']] == name]
        if id:
            if scheme:
                if id in self.identifiers[scheme]:
                    return self.identifiers[scheme][id]
                else:
                    return None
            else:
                return (p for p in self.persons.values() if p['id'] == id).next()

    def add_person(self, person):
        self.json['persons'].append(person)
        self.update_persons_map()

    def add_membership(self, mship):
        self.json['memberships'].append(mship)

    def _max_member_id(self, house, type='member'):
        id = max(int(m['id'].replace('uk.org.publicwhip/%s/' % type, '')) for m in self.memberships.in_org(house))
        return 'uk.org.publicwhip/%s/%d' % (type, id)

    max_lord_id = lambda self: self._max_member_id('house-of-lords', 'lord')
    max_mp_id = lambda self: self._max_member_id('house-of-commons')
    max_mla_id = lambda self: self._max_member_id('northern-ireland-assembly')
    max_msp_id = lambda self: self._max_member_id('scottish-parliament')
    max_londonassembly_id = lambda self: self._max_member_id('london-assembly')

    def max_person_id(self):
        id = max(p for p in self.persons.keys())
        return id

    def _verify(self, coll):
        seen = set()
        dupe = [x['id'] for x in self.json[coll] if x['id'] in seen or seen.add(x['id'])]
        assert len(dupe) == 0, 'Duplicate %s IDs: %s' % (coll, dupe)

    def verify(self):
        self._verify('persons')
        self._verify('memberships')

    def dump(self):
        self.verify()
        json.dump(self.json, open(JSON, 'w'), indent=2, sort_keys=True)
