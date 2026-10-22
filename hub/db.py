import os
import sqlite3
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get('HUB_DB', ROOT / 'data' / 'atlas.sqlite'))


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS catalogue_sources (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, url TEXT NOT NULL,
          metadata_url TEXT NOT NULL, sha256 TEXT NOT NULL, imported TEXT NOT NULL, description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS catalogue_records (
          key INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, source TEXT NOT NULL REFERENCES catalogue_sources(id),
          entity_id TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL,
          branch TEXT NOT NULL, host TEXT NOT NULL DEFAULT '', gut TEXT NOT NULL DEFAULT 'reference',
          attributes BLOB NOT NULL
        );
        CREATE INDEX IF NOT EXISTS catalogue_branch ON catalogue_records(kind,source,branch);
        CREATE INDEX IF NOT EXISTS catalogue_entity ON catalogue_records(entity_id);
        CREATE TABLE IF NOT EXISTS catalogue_crosswalk (
          source TEXT NOT NULL, source_id TEXT NOT NULL, record_key INTEGER NOT NULL REFERENCES catalogue_records(key),
          PRIMARY KEY(source,source_id,record_key)
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS crosswalk_record ON catalogue_crosswalk(record_key);
        CREATE TABLE IF NOT EXISTS papers (
          id TEXT PRIMARY KEY, pmid TEXT, pmcid TEXT, doi TEXT,
          title TEXT NOT NULL, authors TEXT NOT NULL DEFAULT '',
          journal TEXT NOT NULL DEFAULT '', year INTEGER, published TEXT,
          url TEXT NOT NULL, access TEXT NOT NULL, study_type TEXT NOT NULL,
          topics TEXT NOT NULL, taxa TEXT NOT NULL, regions TEXT NOT NULL,
          functions TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'Europe PMC',
          retracted INTEGER NOT NULL DEFAULT 0, refs_checked INTEGER NOT NULL DEFAULT 0,
          added TEXT NOT NULL, updated TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS papers_doi ON papers(doi);
        CREATE TABLE IF NOT EXISTS citations (
          source TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          target TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          PRIMARY KEY(source,target)
        );
        CREATE TABLE IF NOT EXISTS references_pending (
          source TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
          target_pmid TEXT NOT NULL, PRIMARY KEY(source,target_pmid)
        );
        CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs (
          id INTEGER PRIMARY KEY, started TEXT NOT NULL, finished TEXT,
          status TEXT NOT NULL, discovered INTEGER NOT NULL DEFAULT 0,
          message TEXT NOT NULL DEFAULT ''
        );
        ''')
        from .edits import initialize as initialize_edits
        initialize_edits(db)
        from .contributions import initialize as initialize_contributions
        initialize_contributions(db)


def state(db, key, default=None):
    row = db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
    return row['value'] if row else default


def set_state(db, key, value):
    db.execute('INSERT INTO state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))


def encode_metadata(value):
    return zlib.compress(json.dumps(value,ensure_ascii=False,separators=(",",":")).encode())

def decode_metadata(value):
    return json.loads(zlib.decompress(value))
