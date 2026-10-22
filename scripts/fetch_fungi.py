"""Import the CGF paper's compact Figure 1 metadata, without genome sequences."""
import concurrent.futures
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent.parent
REPO='yexianingyue/Cultivated-Gut-Fungi'
FILES=['01.label-name.txt','04.family-band-color.txt','09.genomeSize.txt','10.numberOfGenes.txt','11.numberOfGenomes.txt']

def get(url):
    with urlopen(Request(url,headers={'User-Agent':'GutAtlas-CGF-metadata/1.0'}),timeout=45) as response:
        return response.read()

def records(raw):
    body=raw.decode('utf-8-sig').replace('\r\n','\n').split('\nDATA\n',1)[1]
    return [line.split('\t') for line in body.strip().splitlines() if line.strip() and not line.startswith('#')]

def build(raw,revision):
    labels=records(raw['01.label-name.txt'])
    families={row[0]:row[2] for row in records(raw['04.family-band-color.txt'])}
    size={row[0]:int(row[1]) for row in records(raw['09.genomeSize.txt'])}
    genes={row[0]:int(row[1]) for row in records(raw['10.numberOfGenes.txt'])}
    # The publication encodes cluster size as sqrt(number of genomes) in iTOL.
    genomes={row[0]:round(float(row[1])**2) for row in records(raw['11.numberOfGenomes.txt'])}
    species=[]
    for strain,label,*_ in labels:
        match=re.fullmatch(r'(.+) (c\d+)',label)
        assert match,label
        name,cluster=match.groups()
        prefix=name.split()[0]
        rank='family' if prefix.endswith('aceae') else 'order' if prefix.endswith('ales') else 'phylum' if prefix.endswith('ota') else 'genus'
        species.append(dict(id=cluster,name=name,label=label,representative=strain,group=prefix,group_rank=rank,family=families.get(strain),genome_bp=size[strain],genes=genes[strain],genomes=genomes[strain],unnamed=' ' not in name))
    species.sort(key=lambda s:int(s['id'][1:]))
    assert len(species)==206
    assert len({s['id'] for s in species})==206
    assert sum(s['genomes'] for s in species)==760
    assert sum(s['unnamed'] for s in species)==69
    return dict(source='Cultivated Gut Fungi (CGF)',paper='https://doi.org/10.1016/j.cell.2024.04.043',repository='https://github.com/'+REPO,revision=revision,downloaded=datetime.now(timezone.utc).date().isoformat(),provenance={name:dict(url=f'https://raw.githubusercontent.com/{REPO}/{revision}/Figure1/{name}',sha256=hashlib.sha256(b).hexdigest()) for name,b in raw.items()},species=species)

def main():
    revision=json.loads(get(f'https://api.github.com/repos/{REPO}/commits/main'))['sha']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        data=list(pool.map(lambda name:get(f'https://raw.githubusercontent.com/{REPO}/{revision}/Figure1/{name}'),FILES))
    payload=build(dict(zip(FILES,data)),revision)
    path=ROOT/'static/fungi.json'
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n')
    print(f"Saved {len(payload['species'])} species / 760 genomes; {path.stat().st_size:,} bytes")

if __name__=='__main__':main()
