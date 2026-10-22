"""Resolve bibliographic records referenced by the single editorial reading list."""
import concurrent.futures,json,sys
from pathlib import Path
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub import ingest,editorial
from hub.db import initialize,connect

def resolve(ident):
    source,id=ident.split(':',1)
    if source=='DOI':
        with urlopen('https://api.crossref.org/works/'+id,timeout=30) as r:m=json.load(r)['message']
        return dict(id=id,source='DOI',doi=m['DOI'],title=m['title'][0],authorString=', '.join(a.get('family','') for a in m.get('author',[])),pubYear=str(m['published']['date-parts'][0][0]),journalTitle=m.get('container-title',[''])[0])
    result=ingest.fetch('search',dict(query='EXT_ID:'+id+' AND SRC:'+source,format='json',resultType='core',pageSize=1))
    return result.get('resultList',{}).get('result',[None])[0]

def main():
    initialize()
    with connect() as db:existing={r['id'] for r in db.execute('SELECT id FROM papers')}
    missing={n['paper'] for n in editorial.read('evidence').values()}-existing
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(resolve,missing))
    with connect() as db:
        for r in records:
            if not r:raise RuntimeError('An editorial source did not resolve')
            ingest.upsert(db,r)
    print('Resolved',len(records),'missing paper records')
if __name__=='__main__':main()
