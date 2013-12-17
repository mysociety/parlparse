from resolvemembernames import memberList

for name, matches in memberList.fullnames.items():
    if len(matches)>1:
        for i in range(0, len(matches)-1):
            for j in range(i+1, len(matches)):
                if 'constituency' not in matches[i] or 'constituency' not in matches[j]:
                    continue
                if matches[i]['fromdate'] == matches[j]['fromdate'] and matches[i]['constituency'] == matches[j]['constituency']:
                    print name, i, j, matches[i]['fromdate'], matches[j]['fromdate'], matches[i]['id'], matches[j]['id']
