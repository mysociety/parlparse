from base_resolver import ResolverBase


class MemberList(ResolverBase):
    deputy_speaker = None
    import_organization_id = "welsh-parliament"

    def reloadJSON(self):
        super(MemberList, self).reloadJSON()
        self.import_constituencies()
        self.import_people_json()
        self.senedd = {}
        for person in self.persons.values():
            for identifier in person.get("identifiers", []):
                if identifier.get("scheme") == "senedd":
                    id = identifier.get("identifier")
                    self.senedd[id] = person

    def match_by_id(self, id, date):
        if id == "1" or id == "5":  # Presiding Officer
            return self.senedd["162"]  # Elin Jones since 2016
        if id == "2":  # Deputy
            if date < "2021-05-12":
                return self.senedd["161"]  # Ann Jones
            return self.senedd["205"]  # David Rees
        if id == "6" and date == "2016-05-18":
            return self.senedd["102"]  # Carwyn Jones was the First Minister Elect
        return self.senedd[id]


memberList = MemberList()
