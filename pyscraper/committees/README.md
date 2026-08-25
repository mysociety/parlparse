# Committee and parliamentary post scrapers

Run from the repository root:

    poetry run python -m pyscraper.committees COMMAND

All Popolo files resolve people against `members/people.json`.

Each parliament package follows the same layout:

- `client.py` has HTTP transport, endpoint selection and request pacing.
- `models.py` defines records representing the upstream source data.
- `parsing.py` validates and normalizes XML, JSON, CSV or HTML responses.
- `scraper.py` handles cache reuse, person resolution, Popolo construction and the top-level workflow.

The existing Popolo file for each set of memberships is used to detect changes from the latest scrape or to avoid more expensive requests.

Request counts below are approximate logical HTTP GETs, excluding redirects and retries. They use the current source sizes (about 15 Senedd committees, 137 current Westminster committees, 386 current or former MLAs, and 3,000 MNIS IDs) and the default Westminster batch size of 50. A cached update means the existing output file is present and valid; a full run means the file is absent or `--full-refresh` is passed where supported.

## `westminster`

- Pulls from: the [MNIS XML API][mnis] for post histories, and the [UK Parliament Committees JSON API][committees] for committee memberships and metadata. No HTML pages are scraped.
- Produces: `members/posts/westminster-parliament-posts.json`.
- Contains: government, opposition and parliamentary posts, plus committee memberships, from the 2010 general election onwards.
- Dates: membership start and end dates where supplied.
- Committee metadata: descriptions for current committees, public links, category/type tags, and parent committee relationships.
- Cache: reuses committee metadata from the previous output. Use `--full-refresh` to refresh all current committee details.
- Requests: about 200 API calls on a full run: 2 MNIS XML requests, about 60 batched committee-membership requests for roughly 3,000 MNIS IDs, and about 137 current-committee detail requests. A cached update is about 62 calls, plus one detail request for each newly seen current committee. No HTML pages are scraped.

## `senedd`

- Pulls from: the English and Welsh [ModernGov XML APIs][senedd-api] for committee lists; scraped bilingual committee HTML pages for remits, roles and member IDs; linked CSV APIs for current memberships; and the scraped bilingual [Welsh Government minister pages][welsh-ministers].
- Produces: `members/posts/senedd-committees.json`.
- Contains: current committee memberships and current Welsh Government posts, including the Counsel General.
- Localisation: Welsh and English committee names, descriptions, committee roles and government titles in `extra.localised_values`; the main value is `Welsh / English`.
- Committee metadata: bilingual remit descriptions, Welsh and English public links, and category tags.
- Dates: the sources provide no usable dates; the start remains unknown; the daily artifact ends a membership the day before it disappears.
- Requests: about 64 on both an initial run and an update with an intact file, based on 15 current committees: 2 committee-list XML API calls, 30 scraped bilingual committee pages, 30 membership CSV downloads, and 2 scraped bilingual Welsh Government pages. The previous file supplies history, not a source-request cache.

## `scotland`

- Pulls from: Scottish Parliament JSON APIs for [committees][scot-committees], [committee roles][scot-roles], [person committee roles][scot-person-roles], [government role names][scot-government-roles], [dated government appointments][scot-member-government-roles] and member names; plus the scraped HTML committee index for public links.
- Produces: `members/posts/scottish-parliament-committees.json`.
- Contains: committees and memberships active on the day of the scrape, plus Scottish Government post history from 1999 onwards.
- Committee metadata: descriptions and public links.
- Dates: government posts use official start and end dates where supplied. Source committee dates select current records; the committee start remains unknown, and the daily artifact records the day before disappearance as the end.
- Cache: reuses public committee links from the previous output. Use `--full-refresh` to refresh the HTML index.
- Requests: 7 on a full run (6 JSON API calls and 1 scraped HTML committee-index page); 6 on a cached update, which skips the HTML page.

## `northern-ireland`

- Pulls from: four NI Assembly JSON APIs for current committee lists; the [current member roles JSON API][ni-roles]; the current-and-former-members JSON API; per-member role-history JSON APIs; and the scraped HTML committee index for public links.
- Produces: `members/posts/ni-assembly-committees.json`.
- Contains: current committee memberships plus ministerial post history, modelled as posts under the Northern Ireland Executive.
- Committee metadata: committee type tags and public links where an index match is available; no descriptions or localisation.
- Dates: ministerial posts use official start and end dates where supplied; committee starts remain unknown, and the daily artifact records the day before disappearance as the end.
- Cache: reuses public committee links and closed ministerial histories. The first run and `--full-refresh` fetch every MLA's role history; normal runs refresh only current or previously open ministers.
- Requests: about 393 on a full run: 6 base JSON API calls, 1 scraped HTML committee-index page, and about 386 per-person role-history API calls. A cached update is currently about 18 calls: the 6 base APIs plus roughly 12 current or previously open ministers, with no HTML scrape. The person-history count changes as the source and ministry change.

## `uk-committees`

- Pulls from: the [UK Parliament Committees JSON API][committees]. No HTML pages are scraped.
- Produces: current minigroup files under `parldata/scrapedjson/committees`.
- Contains: committee descriptions, public URLs, categories/types and current members.
- This is the legacy minigroup output, not a Popolo file under `members/posts`.
- Requests: always roughly 420 JSON API calls at the current size of about 137 committees, covering committee-list pagination plus one detail request and paginated current-membership requests per committee. It does not use an output-file cache and scrapes no HTML pages.



[mnis]: https://data.parliament.uk/membersdataplatform/memberquery.aspx
[committees]: https://committees-api.parliament.uk/index.html
[senedd-api]: https://business.senedd.wales/mgwebservice.asmx/GetCommittees
[scot-committees]: https://data.parliament.scot/api/committees/json
[scot-roles]: https://data.parliament.scot/api/committeeroles/json
[scot-person-roles]: https://data.parliament.scot/api/personcommitteeroles/json
[scot-government-roles]: https://data.parliament.scot/api/governmentroles/json
[scot-member-government-roles]: https://data.parliament.scot/api/membergovernmentroles/json
[ni-roles]: https://data.niassembly.gov.uk/members.asmx/GetAllMemberRoles_JSON
[welsh-ministers]: https://www.gov.wales/cabinet-ministers-and-deputy-ministers
