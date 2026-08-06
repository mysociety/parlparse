# Scottish Parliament Written Questions Scraper

Converts Scottish Parliament written questions and answers from the [Scottish Parliament API](https://data.parliament.scot/) into TheyWorkForYou XML format.

## Overview

This module scrapes answered written questions from the Scottish Parliament's open data API and converts them into TheyWorkForYou transcript file. 

## Usage

The module provides a CLI via `poetry run python -m pyscraper.sp_wrans`:

### Convert a single year
```bash
poetry run python -m pyscraper.sp_wrans convert --year 2024
```

### Convert all years (2011-present)
```bash
poetry run python -m pyscraper.sp_wrans convert-all
```

### Convert a specific date range
```bash
poetry run python -m pyscraper.sp_wrans convert-date-range --start-date 2024-01-15 --end-date 2024-02-28
```

### Update with latest questions
```bash
poetry run python -m pyscraper.sp_wrans update
```

### Options

## Output

XML files are written to `parldata/scrapedxml/sp-written/` with filenames like `spwa2024-03-15.xml` (one file per answer date).