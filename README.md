# parlparse

## Prerequisites

You should probably install the following tools before attempting anything in
this README, otherwise things may not work as expected (or at all):

* [lxml](http://lxml.de/)

## Scrape data from data.parliament.uk

The source of data for the 2010 election onwards is
[data.parliament.uk](http://data.parliament.uk/membersdataplatform/memberquery.aspx).
This data is scraped and stored locally for parsing, but needs updating manually
using the following process.

1. Change to the `scripts/datadotparl` directory.
2. Run `./crawl-members`

## Update from data.parliament.uk

The data.parliament data is used to generate a list of members positions (in
`ministers-2010.json`) which includes government posts, opposition posts,
parliamentary posts and committee memberships from the 2010 general election
onwards.

Before updating, you should run the data.parliament.uk scraper.

1. Change to the `scripts/datadotparl` directory.
2. Run `./update-members` to parse the XML and update things.
