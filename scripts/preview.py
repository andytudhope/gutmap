"""Run an isolated local Gut Atlas preview with the existing metadata archive."""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8092)
    parser.add_argument('--review-password',default='atlas-local')
    args=parser.parse_args()
    preview=ROOT/'data/preview.sqlite'
    if not preview.exists():
        source=ROOT/'data/atlas.sqlite'
        if not source.exists():
            raise SystemExit('The local metadata archive data/atlas.sqlite is required.')
        with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as source_db,sqlite3.connect(preview) as target:
            source_db.backup(target)
    os.environ['HUB_DB']=str(preview)
    from hub import app,db,edits,ingest
    os.environ['HUB_EDIT_PASSWORD_HASH']=edits.password_hash(args.review_password)
    db.initialize()
    with db.connect() as conn:
        for a in json.loads((ROOT/'content/source_audit.json').read_text()).values():
            r=a.get('bibliography')
            if r and not conn.execute('SELECT id FROM papers WHERE id=?',(r['id'],)).fetchone():
                source,ident=r['id'].split(':',1)
                ingest.upsert(conn,dict(id=ident,source=source,title=r['title'],authorString=r.get('authors',''),journalTitle=r.get('journal',''),pubYear=str(r['year']),doi=r.get('doi','')))
    print(f'Local preview: http://127.0.0.1:{args.port}')
    print(f'Local review password: {args.review_password}')
    print('Database: '+str(preview))
    sys.argv=['hub.app','--host','127.0.0.1','--port',str(args.port)]
    try:app.main()
    except KeyboardInterrupt:print('\nPreview stopped.')


if __name__=='__main__':main()
