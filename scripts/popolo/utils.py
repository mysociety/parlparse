import json
import os
import re
import tempfile
from popolo.menu import Menu


def new_id(max_id):
    base, id = re.match('(.*/)(\d+)$', max_id).groups()
    return '%s%d' % (base, int(id) + 1)


def edit_file(edit_data):
    fp = tempfile.NamedTemporaryFile(delete=False)
    json.dump(edit_data, fp, sort_keys=True, indent=2)
    fp.close()
    try:
        while True:
            os.system('vim "%s"' % fp.name)
            with open(fp.name) as f:
                try:
                    new_edit_data = json.load(f)
                    break
                except ValueError as e:
                    print("Bad JSON: %s" % e)
                    raw_input("Press Enter to continue...")
    finally:
        os.remove(fp.name)
    return new_edit_data


def get_person_from_name(name, data):
    person = data.get_person(name=name)
    if len(person) > 1:
        opts = []
        for p in person:
            mships = sorted(
                data.memberships.of_person(p['id']),
                key=lambda x: x.get('end_date', '9999-12-31'), reverse=True)
            if len(mships):
                m = mships[0]
                mship = '%s, %s-%s' % (
                    m['id'], m['start_date'], m.get('end_date', ''))
            else:
                mship = ''
            opts.append('%s (%s)' % (p['id'], mship))
        menu = Menu(opts)
        choice = menu.pick()
        if choice is None:
            raise Exception('Did not pick a person')
        return person[choice]
    elif len(person) != 1:
        raise Exception('Did not get any person')
    return person[0]
