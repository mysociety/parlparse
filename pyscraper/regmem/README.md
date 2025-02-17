# pyscraper.regmem

This is a module that downloads the registers of members interests for different Parliaments and parses to a common format. 

Scrapers currently covered:

- House of Commons (API)
- Scottish Parliament (API)
- Senedd (scraper)
- Northern Ireland Assembly (API)
- London (scraper - partial)

# CLI

See options with `python -m pyscraper.regmem --help`

## Common format

The common format is descripted in `models.py` and is meant to be flexible enough to handle the quite detailed fields from the Commons API, with sensible more basic options for Parliaments that just release a free text.

The basic structure is tiered: person > category > entry > subitem/details.

A register is meant to be snapshot of a particular time or release. There shouldn't be duplicate persons, or categories under persons. 

For every register in every chamber we create a json in this format (which will be stored in the TWFY database and used to generate the main register view), and a version in the 'legacy' XML format, which is used to generate the over time comparisons.

## Scraper notes

For the three API based approaches, the structure of the API can be seen in the `api_models.py` files.

All scrapers depend on the relevant official ID for a person being stored in `people.json`.

### Commons

The most detailed API, and the only one that uses child interests to handle multiple payments related to the same org. 

This does 'releases' and new registers are accessible as 'registers' in the API. 

### Scottish Parliament

This is reprocessing a big json file. For the moment, this is just handling current MPs (where we have ids in people.json), although there is more historical data we could pull on. 

Here we just use the description field to store free text interests.

There isn't a strong concept of releases here, instead we infer releases from unique `date_updated`.

Some entries are dropped if they have a 'rejected' status. If we find out that's important to capture we could include and store the status as a detail. We are similarly not including information about the approval process that is stored in the json.

### Northern Ireland Assembly

This is also reprocessing json from the API. Nothing especially tricky in this one, it's mostly converting a flat-ish data structure to our tiered approach. 

Like Scotland, this retrospectively creates the idea of registers from the register start date of an entry. 

### Senedd

This is a web scraper, getting a list of IDs from the central page, and then scraping the MS profile pages twice (in English and Welsh). There's only 60 MSs, so this doesn't take that long.

New registers are inferred by a new date updates scraped from one of the pages. 

This scraper stores information in the `details` structure rather than using the description field. As a result, Senedd entries will *not* have a description field to use as a heading. 

### London

This is a scraper that fetches the interests for the London Assembly and Mayor's Team.

This is included at this point mostly as a test the format is flexible enough.

To be used properly, we need to ensure assembly members are in people.json and ideally have the relevant identifers added. 

Again, no strong concept of register releases. Currently will just fetch current version, and the published date is the *last* published date of any data for a person. 

May want to drop gift and hospitality entries more than a year before the published date.