# Scottish Parliament Written Questions Scraper

Converts Scottish Parliament written questions and answers from the [Scottish Parliament API](https://data.parliament.scot/) into TheyWorkForYou XML format.

## Overview

This module scrapes answered written questions from the Scottish Parliament's open data API and converts them into XML files compatible with the MySociety transcript format used by TheyWorkForYou. It handles complex text processing challenges including:

- HTML table extraction and cleanup
- "Table X:" header detection with automatic column detection
- Multi-paragraph text splitting
- Person ID resolution via the people.json
- HTML entity resolution and XML escaping

## Installation

This module is part of the parlparse project. Install dependencies with Poetry:

```bash
cd /path/to/parlparse
poetry install
```

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
- `--verbose`: Print detailed progress information
- `--year YYYY`: Specify year to convert (convert command only)
- `--start-date YYYY-MM-DD`: Start date for date range conversion (convert-date-range command only)
- `--end-date YYYY-MM-DD`: End date for date range conversion (convert-date-range command only)
- `--force-refresh`: Re-download cached data instead of using existing downloads

## Output

XML files are written to `parldata/scrapedxml/sp-written/` with filenames like `spwa2024-03-15.xml` (one file per answer date).

The XML follows the MySociety transcript schema with:
- `MajorHeading`: Date header
- `Question`: Each written question with speaker and text
- `Reply`: Government minister's answer
- `SpeechItem`: Individual paragraphs/tables within questions/answers

## Architecture

The module is split into focused components:

### Core Modules

| Module | Purpose | Key Functions |
|---|---|---|
| [`api_models.py`](api_models.py) | Pydantic models for SP API data | `SPQuestion` with PascalCase aliases |
| [`download.py`](download.py) | API fetching and caching | `download_questions()`, `get_written_answered_questions()` |
| [`convert.py`](convert.py) | Transcript assembly and XML output | `build_transcript_for_date()`, `convert_questions_to_xml()` |

### Text Processing Pipeline

| Module | Purpose | Key Functions |
|---|---|---|
| [`cleanup.py`](cleanup.py) | HTML entities, XML escaping | `clean_text()`, `resolve_entities()`, `escape_xml()` |
| [`tables.py`](tables.py) | Table detection and formatting | `extract_html_tables()`, `clean_html_table()`, `detect_table_columns()` |
| [`text_processing.py`](text_processing.py) | SpeechItem conversion orchestrator | `text_to_speech_items()` |

### CLI
- [`__main__.py`](__main__.py): Typer-based command-line interface

## Data Flow

```
Scottish Parliament API
         ↓
    download.py (caching to parldata/cmpages/sp_wrans/)
         ↓
    api_models.py (SPQuestion validation)
         ↓
    text_processing.py pipeline:
      • cleanup.py: HTML entities → Unicode → XML-safe
      • tables.py: Extract HTML tables, detect "Table X:" patterns
      • convert.py: Person ID resolution, transcript assembly
         ↓
    MySociety XML (parldata/scrapedxml/sp-written/)
```

## Text Processing Details

### HTML Table Handling
- **Inline HTML tables**: Parsed with lxml.html for robustness with malformed/truncated markup
- **"Table X:" patterns**: Auto-detects column structure from newline-delimited data
- **IE conditional comments**: Stripped before parsing to avoid XML issues

### Person ID Resolution
Maps Scottish Parliament member IDs to MySociety person IDs via:
1. `IdentifierScheme.SCOTPARL` lookups in member database
2. Fallback to name-based matching when ID lookup fails
3. Preserves original SP member URLs for reference

### Content Types
- **Paragraphs**: Split on blank lines, XML-escaped
- **Tables**: Preserved as `<table>` SpeechItems with both plain-text and HTML content
- **Multi-line answers**: Proper paragraph detection while preserving table structures

## Example Output

```xml
<transcript>
  <major-heading id="2024-03-15">15 Mar 2024</major-heading>
  
  <question id="S6W-29123" qnum="S6W-29123" person_id="uk.org.publicwhip/person/26123" 
            url="https://www.parliament.scot/chamber-and-committees/questions-and-answers/question?ref=S6W-29123">
    <p>To ask the Scottish Government what steps it is taking to improve rural broadband.</p>
  </question>
  
  <reply person_id="uk.org.publicwhip/person/26456" speakername="Cabinet Secretary">
    <p>The Scottish Government is committed to ensuring all of Scotland has access to superfast broadband.</p>
    <table>
      <tr><th>Area</th><th>Coverage %</th></tr>
      <tr><td>Rural</td><td>87.2</td></tr>
      <tr><td>Urban</td><td>98.6</td></tr>
    </table>
  </reply>
</transcript>
```

## Development

### Running Tests
```bash
# Lint check
bash script/lint

# Convert test (single year)
python -m pyscraper.sp_wrans convert --year 2026 --verbose

# Full regression test
python -m pyscraper.sp_wrans convert-all
```

### Data Sources
- **API Base**: `https://data.parliament.scot/api/motionsquestionsanswersquestions`
- **Member Database**: `parldata/members/people.json` 
- **Cache Directory**: `parldata/cmpages/sp_wrans/`
- **Output Directory**: `parldata/scrapedxml/sp-written/`

### Error Handling
- Graceful handling of malformed HTML tables (truncated API responses)
- Automatic table structure detection with fallback to paragraph formatting  
- Comprehensive HTML entity resolution with safe XML escaping
- Person ID resolution with name-based fallbacks
