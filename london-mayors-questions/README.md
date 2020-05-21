# London Mayor's Questions

## How it works

You can add `--help` to any command for a full list of options.

### Scraping/Parsing Meetings

The `./questions.py meetings` command scrapes (by default) any unscraped dates between the `default_start_date` in `config.json` and yesterday.

If a page returns a 404, it's assumed there is no meeting and this date is flagged in `state.json` to not be scraped again.

If the page returns content, it's parsed to extract sessions. Each session is then scraped, and parsed for questions. New question IDs are added to the `state.json` file

### Scraping/Parsing Questions
