# Initial data collection for Welsh Parliament
## May 2020

Building on the discussion found [on this pull request](https://github.com/mysociety/parlparse/pull/79) and historic mailing list conversation [here](https://groups.google.com/a/mysociety.org/forum/#!topic/theyworkforyou/h7wlagp2BmI), this collection of scripts attempts to get an initial collection of data relating to Welsh Parliament members together for addition to [`people.json`](../../members/people.json).

The current state of affairs seems to be:

- [`samknight`](https://github.com/samknight) previously committed [`yoursenedd_members.json`](../../rawdata/wamembers/yoursenedd_members.json) which serves as a good starting point for getting data into parlparse.
- [`jacksonj04`](https://github.com/jacksonj04) made changes last year to [introduce London Assembly members](https://github.com/mysociety/parlparse/commits?author=jacksonj04).
- The [WikiProject every politician project](https://www.wikidata.org/wiki/Wikidata:WikiProject_every_politician) have put in considerable effort to collate data relating to the Welsh Parliament and its members.
- EveryPolitican have released a [blog post](https://www.mysociety.org/2019/06/26/placing-everypolitician-on-hold/) suggesting their work is currently on hold. 
- The latest commits to the [`everypolitician-data`](https://github.com/everypolitician/everypolitician-data/tree/master/data/Wales) repo relating to Wales happened roughly one year ago. [`everypolitician-scrapers`](https://github.com/everypolitician-scrapers) has a number of scrapers  ([here](https://github.com/everypolitician-scrapers/wales-AMs-wikidata)/[here](https://github.com/everypolitician-scrapers/wales-positions)/[here](https://github.com/everypolitician-scrapers/wales-assembly-gender-balance)) which were running on [morph.io](https://morph.io/everypolitician-scrapers) but many of these are now returning errors.

The scripts contain here borrow from the `everypolitician-scrapers` scripts and `jacksonj04`'s contributions, using SPARQL to query Wikidata. The hope is, if the community can keep Wikidata as its primary source then it should be easier to integrate changes in Welsh Parliament into parlparse in future.

This feels like doing the following (with maybe some indication of order):
- [X] Update [`popolo.__init__.py`](../popolo/__init__.py) to include ranges for Members of the Senedd
- [X] Update `popolo.__init__.py` to include methods for adding organiasations and posts to `people.json`
- [X] Update `people.json` to introduce Members of the Senedd to persons
- [X] Update `people.json` to include organisations which are unqiue to the Senedd
- [X] Update `people.json` to include posts for Members of the Senedd
- [X] Update `people.json` to include memberships for Members of the Senedd

Four scripts within the [`scripts`](./scripts/) folder now allow for the introduction of Senedd items into `people.json`.

