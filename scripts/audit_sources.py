"""Check editorial publication identities against Europe PMC/Crossref.

Only bibliographic metadata is saved. Abstracts can be inspected in a temporary
file with --abstracts; they are never written into the site or its database.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hub import ingest
from hub.db import ROOT, connect, initialize


def audit(abstract_path=None):
    notes = json.loads((ROOT / 'content/evidence.json').read_text())
    records, abstracts = {}, {}
    for source in ('MED', 'PPR'):
        ids = [n['paper'].split(':', 1)[1] for n in notes.values() if n['paper'].startswith(source + ':')]
        for start in range(0, len(ids), 50):
            data = ingest.fetch('search', dict(query='SRC:' + source + ' AND EXT_ID:(' + ' OR '.join(ids[start:start + 50]) + ')', format='json', resultType='core', pageSize=1000))
            for r in data.get('resultList', {}).get('result', []):
                pid = r['source'] + ':' + r['id']
                records[pid] = r
                abstracts[pid] = ingest.clean(r.get('abstractText', ''))
    for n in notes.values():
        if n['paper'].startswith('DOI:'):
            doi = n['paper'][4:]
            with urlopen('https://api.crossref.org/works/' + quote(doi, safe=''), timeout=30) as response:
                r = json.load(response)['message']
            records[n['paper']] = dict(id=doi, source='DOI', doi=doi, title=r['title'][0], pubYear=str(r['published']['date-parts'][0][0]), journalTitle=r.get('container-title', [''])[0], authorString=', '.join(a.get('family', '') for a in r.get('author', [])))
    initialize()
    with connect() as db:
        for r in records.values():
            ingest.upsert(db, r)
    prior_path = ROOT / 'content/source_audit.json'
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    output = {}
    for slug, n in notes.items():
        r = records.get(n['paper'])
        old = prior.get(slug, {})
        if old.get('paper') != n['paper'] or old.get('reviewed_finding') != n['finding']:
            old = {}
        output[slug] = dict(paper=n['paper'], checked=datetime.now(timezone.utc).date().isoformat(), identity_status='resolved' if r else 'unresolved', title=ingest.clean(r['title']) if r else '', doi=r.get('doi', '') if r else '', provider='Crossref' if n['paper'].startswith('DOI:') else 'Europe PMC', support_status=old.get('support_status', 'needs_review'), material_reviewed=old.get('material_reviewed', 'Not checked in this source audit'), review_note=old.get('review_note', 'Publication identity checked. Scientific support and applicability still need review.'))
        if old.get('reviewed_finding'):
            output[slug]['reviewed_finding'] = old['reviewed_finding']
        with connect() as conn:
            row = conn.execute('SELECT id,title,authors,journal,year,doi,pmid,url,study_type,retracted FROM papers WHERE id=?', (n['paper'],)).fetchone()
        if row:
            output[slug]['bibliography'] = dict(row)
    prior_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n')
    if abstract_path:
        Path(abstract_path).write_text(json.dumps(abstracts, ensure_ascii=False))
    print(f'Resolved {sum(v["identity_status"] == "resolved" for v in output.values())}/{len(output)} editorial sources; scientific review is tracked separately.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--abstracts', help='Optional temporary file outside the project for reading abstracts')
    audit(parser.parse_args().abstracts)
