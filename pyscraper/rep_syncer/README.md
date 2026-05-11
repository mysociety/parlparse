# rep_syncer

Syncs representative data from external parliament APIs into `members/people.json`.

Currently only covers Scottish Parliament, however other scripts exist for other Parliaments.

e.g.
```bash

# get Senedd from wikidata and add official IDs
scripts/welsh-parliament/persons.py
scripts/welsh-parliament/official-ids.py

# get MLAs (part of daily update)
scripts/add-new-mlas

# get Lords (part of daily update)
scripts/add-new-lords
```

## Usage

```bash
poetry run python -m pyscraper.rep_syncer sp run [--people PATH] [--dry-run] [--quiet]
```

| Option | Description |
|---|---|
| `--people PATH` | Path to `people.json` (auto-detected from repo root if omitted) |
| `--dry-run` | Print changes but do not write `people.json` |
| `--quiet` | Suppress progress messages |
