"""Download compact public MGnify species metadata; never sequence files."""
import concurrent.futures
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

BASE='https://www.ebi.ac.uk/metagenomics/api/v1/genome-catalogues/human-gut-v2-0-2/genomes'
ROOT=Path(__file__).resolve().parent.parent

def fetch(page):
    url=BASE+'?'+urlencode({'page':page,'page_size':1000})
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'GutAtlas-local-reference/0.2','Accept':'application/json'}),timeout=45) as response:
                return json.load(response)
        except Exception:
            if attempt==2:raise
            time.sleep(1+attempt)

def main():
    first=fetch(1)
    pagination=first['meta']['pagination']
    records=list(first['data'])
    print('Public catalogue:',pagination,flush=True)
    pages=pagination['pages']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for page,result in zip(range(2,pages+1),pool.map(fetch,range(2,pages+1))):
            records.extend(result['data'])
            print('Read page',page,'records',len(records),flush=True)
    species=[]
    for row in records:
        a=row['attributes']
        lineage=[part[3:] for part in a['taxon-lineage'].split(';')]
        species.append([row['id'],lineage,a['type'],a['completeness'],a['num-proteins'],a.get('eggnog-coverage'),a.get('num-genomes-total')])
    species.sort(key=lambda r:r[0])
    assert len({s[0] for s in species})==pagination['count']
    payload=dict(source='MGnify / UHGG',version='human-gut-v2-0-2',url='https://www.ebi.ac.uk/metagenomics/genome-catalogues/human-gut-v2-0-2',
                 source_api=BASE,downloaded=datetime.now(timezone.utc).date().isoformat(),scope='Species representatives across human gut samples; not a personal microbiome or a map of organ-level abundance.',
                 fields=['accession','lineage','representative_type','completeness','proteins','predicted_annotation_percent','genomes_in_cluster'],species=species)
    path=ROOT/'static/reference.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
    print('Saved',len(species),'species;',path.stat().st_size,'bytes',flush=True)

if __name__=='__main__':main()
