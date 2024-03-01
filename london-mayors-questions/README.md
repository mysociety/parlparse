# London Mayor's Questions

You can add `--help` to any command for a full list of options.

The scraper stores working files in a git-ignored `json_cache` directory. 

- `fetch-unknown-questions` - which accepts custom start and end dates. The `--last-week` flag goes back 7 days. This updates `json_cache/ids.json` with the current known set of question ids.
- `fetch-unstored`, any questions we haven't previously downloaded will be fetched.
- `refresh-unanswered`, any without answers (or with holding answers only) will be downloaded again.
- `build-xml` accepts an `--outdir` argument and will convert the stored questions into xml files for import. The date of the file each question is put in based on the date of the answer - so the question is only moved to the XML when it is answered. 

So the final command to call looks something like this:

```bash
./questions.py fetch-unknown-questions --last-week fetch-unstored refresh-unanswered build-xml --outdir temp/
```

