# Gut Atlas

An open, visual guide to the human gut: clear explanations, biological mechanisms and inspectable research evidence.

## Run

Run the local preview:

```sh
python3 scripts/preview.py
```

Open **http://127.0.0.1:8092**. This uses a separate `data/preview.sqlite` copied from the local metadata archive. Review contributions at `/review` with the local password `atlas-local`. Override it with `--review-password`. The preview binds to localhost and does not publish anything.

For a normal server, run `python3 -m hub.app --port 8091`. Set `HUB_DB` to choose a database. Set `HUB_EDIT_PASSWORD_HASH` to enable review; `python3 -m hub.edits` prints a hash for a password entered interactively.

Checks:

```sh
HUB_DB=data/preview.sqlite python3 -m unittest discover -s tests
```

## Ontology

Curated knowledge has six logical records: Concept, Claim, Study, Finding, Source and View. Edit `content/concepts.json`, `content/knowledge.json` and `content/topics.json`. `hub/knowledge.py` validates relationships and builds reverse links. Topic explanations, process steps, organism pages and research comparisons resolve the same claim and finding IDs.

`content/evidence.json` contains the source-scoped reading notes. `content/source_audit.json` records publication identity checks and a separate assessment of source support. An abstract check is distinct from full-text or independent scientific review. Unassessed diagram references remain candidates. A source correction or retraction flags affected claims for reassessment. Guidance is distinguished from experimental evidence.

Scientific contributions target a concept, claim, finding or topic. They can clarify an explanation, add supporting/conflicting evidence, correct a mapping or propose a question. DOI/PMID and supported ENA accessions resolve to source records. Accepted changes are projected into dependent views; public credit is opt-in and contact details stay private. Multiple reports can share a study record. Review requires a named reviewer and decision reason.

Bibliographic metadata and versioned source catalogues live in SQLite. No PDFs, full article texts, abstracts or sequences are stored by the site. Update discovery with `python3 -m hub.ingest --force`. Audit source identities with `python3 scripts/audit_sources.py`; its optional abstract inspection output should be a temporary path outside the project. Keep the database when publishing code changes because it also holds contributions and decisions.

