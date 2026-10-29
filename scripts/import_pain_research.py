"""Import the checked gut–pain citation route without storing abstracts or full text.

Run against the main archive by default, or set HUB_DB for an isolated preview.
The tracked manifest makes these additions reproducible and DOI-deduplicated.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub import db,ingest

def main():
    route=json.loads((db.ROOT/'content/pain_research.json').read_text())
    db.initialize()
    with db.connect() as conn:
        before=conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0]
        prior_edges=conn.execute('SELECT COUNT(*) FROM citations').fetchone()[0]
        for item in route['records']:
            ingest.upsert(conn,item['metadata'],extra_topic='pain')
            row=conn.execute('SELECT id FROM papers WHERE doi=?',(item['metadata']['doi'],)).fetchone()
            tags=item['index']
            conn.execute('UPDATE papers SET topics=?,taxa=?,functions=?,regions=?,study_type=? WHERE id=?',
                tuple(json.dumps(tags[k],ensure_ascii=False) for k in ('topics','taxa','functions','regions'))+(tags['study_type'],row['id']))
        identities={r['doi']:r['id'] for r in conn.execute("SELECT id,doi FROM papers WHERE doi IS NOT NULL AND doi!=''")}
        for edge in route['citation_edges']:
            source=identities.get(edge['source_doi']);target=identities.get(edge['target_doi'])
            if source and target and source!=target:
                conn.execute('INSERT OR IGNORE INTO citations VALUES (?,?)',(source,target))
        seed=identities['10.1002/jsp2.70174']
        conn.execute('UPDATE papers SET refs_checked=1 WHERE id=?',(seed,))
        db.set_state(conn,'pain_route_checked',route['checked'])
        total=conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0]
        edges=conn.execute('SELECT COUNT(*) FROM citations').fetchone()[0]
        print(f'{db.DB_PATH}: {total-before} new papers, {edges-prior_edges} new citation edges; {len(route["records"])} route records resolved.')
if __name__=='__main__':main()
