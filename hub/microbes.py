"""Connect catalogue identifiers to indexed titles and reviewed evidence, without inferred disease claims."""
import json,re
from collections import defaultdict
from functools import lru_cache
from urllib.parse import urlencode
from .db import ROOT,connect,decode_metadata
from . import editorial,research

@lru_cache(maxsize=4)
def static_records(name,stamp):
    return json.loads((ROOT/'static'/name).read_text())

def static(name):return static_records(name,(ROOT/'static'/name).stat().st_mtime_ns)

def words(value):return re.findall(r'[a-z][a-z0-9_-]*',value.lower())
def scientific(value):
    parts=value.replace('_',' ').split()
    return ' '.join(parts[:2]) if len(parts)>1 and re.fullmatch(r'[A-Z][a-z]+',parts[0]) and re.fullmatch(r'[a-z][a-z-]+',parts[1]) and parts[1] not in ('sp','spp','bacterium') else ''

def descriptor(ident):
    if ident.startswith('MGYG'):
        row=next((r for r in static('reference.json')['species'] if r[0]==ident),None)
        if not row:return None
        return dict(id=ident,name=row[1][6] or ident,genus=re.sub(r'_[A-Z]+$','',row[1][5]),kind=row[1][0],lineage=row[1],source='UHGG',source_doi='10.1038/s41587-020-0603-3',accessions=[ident],metadata=dict(accession=ident,recovery=row[2],completeness=row[3],proteins=row[4],genomes=row[6]))
    if ident.startswith('cgf:'):
        row=next((r for r in static('fungi.json')['species'] if r['id']==ident[4:]),None)
        if not row:return None
        return dict(id=ident,name=row['name'],genus=row['name'].split()[0],kind='Fungi',lineage=[row['group'],row['family']],source='CGF',source_doi='10.1016/j.cell.2024.04.043',metadata=row)
    with connect() as db:
        row=db.execute('SELECT * FROM catalogue_records WHERE id=?',(ident,)).fetchone()
        if not row:return None
        r=dict(row);a=decode_metadata(r.pop('attributes'))
        crosswalk=[x[0] for x in db.execute('SELECT source_id FROM catalogue_crosswalk WHERE record_key=? LIMIT 60',(r['key'],))]
    aliases=[]
    for value in re.split(r'[;,|]',a.get('previous_names','')):
        if scientific(value):aliases.append(scientific(value))
    return dict(id=ident,name=r['name'],genus=r['branch'] if r['kind']!='viruses' else '',host=r['host'] if r['kind']=='viruses' else '',kind=r['kind'],lineage=[r['branch']],source=r['source'].upper(),source_doi=a.get('catalogue_paper') or a.get('paper'),aliases=aliases,accessions=[ident.split(':',1)[-1],a.get('representative',''),*crosswalk],metadata={**a,'crosswalk':crosswalk})

_cache=None

def edits_revision():
    from .edits import revision
    return revision()

def index():
    global _cache
    model=research.model();stamp=(id(model),edits_revision(),(ROOT/'content/microbes.json').stat().st_mtime_ns)
    if _cache and _cache[0]==stamp:return _cache[1]
    named=defaultdict(dict);genera=defaultdict(dict);records=defaultdict(dict);accessions=defaultdict(dict)
    # Only index words that occur as catalogue genera. No full-text or abstract corpus is retained.
    genera_set={re.sub(r'_[A-Z]+$','',r[1][5]).lower() for r in static('reference.json')['species']}
    genera_set.update(r['name'].split()[0].lower() for r in static('fungi.json')['species'])
    with connect() as db:
        for row in db.execute("SELECT DISTINCT branch FROM catalogue_records WHERE kind!='viruses'"):genera_set.add(row[0].lower())
    for p in model['papers'].values():
        if p.get('retracted'):continue
        texts=[('Named in paper title',p['title'])]
        if p.get('note'):texts += [('Named in reviewed note',p['note'].get('finding','')+' '+p['note'].get('meaning',''))]
        for basis,text in texts:
            for accession in re.findall(r'\b(?:MGYG\d+(?:\.\d+)?|UHGV-\d+|vOTU-\d+|GCA_\d+(?:\.\d+)?)\b',text,re.I):accessions[accession.lower()][p['id']]='Catalogue identifier in title or reviewed note'
            tokens=words(text)
            for i,token in enumerate(tokens):
                if token not in genera_set:continue
                genera[token][p['id']]=basis
                if i+1<len(tokens):named[token+' '+tokens[i+1]][p['id']]=basis
        for ident in (p.get('note') or {}).get('catalogue_records',[]):records[ident][p['id']]='Reviewed catalogue-record link'
    for organism in editorial.read('microbes')['organisms']:
        for slug in organism['studies']:
            pid=model['aliases'].get(slug)
            if pid in model['papers']:
                named[organism['name'].lower()][pid]='Curated organism reading note'
                genera[organism['name'].split()[0].lower()][pid]='Curated organism reading note'
    _cache=(stamp,dict(model=model,named=named,genera=genera,records=records,accessions=accessions));return _cache[1]

def matches(d):
    ix=index();direct=dict(ix['records'].get(d['id'],{}));name=scientific(d['name']);aliases=list(dict.fromkeys([x for x in [name,*d.get('aliases',[])] if x]))
    for accession in [d['id'],*d.get('accessions',[])]:
        if accession:direct.update(ix['accessions'].get(accession.lower(),{}))
    for alias in aliases:direct.update(ix['named'].get(alias.lower(),{}))
    # Accession-only records can still be explicitly linked through a contributed reading note.
    direct.update(ix['records'].get(d['id'],{}))
    genus=d.get('genus','').lower();host=d.get('host','').lower()
    related=dict(ix['genera'].get(genus or host,{}));related={pid:basis for pid,basis in related.items() if pid not in direct}
    return direct,related,aliases

def brief(pid,basis):
    p=index()['model']['papers'][pid]
    return {k:p.get(k) for k in ('id','title','year','journal','url','access','study_type','note','note_id','pathways','regions','functions')}|dict(match=basis)

def ordered(rows):
    papers=index()['model']['papers'];return sorted(rows,key=lambda pid:(not papers[pid]['annotated'],-(papers[pid]['year'] or 0),pid))

def dossier(ident):
    d=descriptor(ident)
    if not d:return None
    direct,related,aliases=matches(d);ix=index();model=ix['model'];sources=[]
    if d.get('source_doi'):
        pid=model['aliases'].get('doi:'+d['source_doi'].lower())
        if pid:sources=[brief(pid,'Catalogue source publication')]
    links={};questions=[];functions=defaultdict(int)
    for pid in direct:
        p=model['papers'][pid]
        for link in p['pathways']:links[link['url']]=link
        for function in p['functions']:functions[function]+=1
        note=p.get('note')
        if note and note.get('question'):questions.append(dict(text=note['question'],paper=pid))
    curated=next((o for o in editorial.read('microbes')['organisms'] if o['name'] in aliases),None)
    if curated:
        for link in curated['links']:links[link['url']]=link
    term=aliases[0] if aliases else d.get('genus') or d.get('host')
    observations=[];meta=d['metadata']
    if d['source']=='UHGG':
        observations.append(('The representative was sequenced from a cultured isolate.' if meta['recovery']=='Isolate' else 'The representative was reconstructed from DNA in a mixed microbial sample.'))
        observations.append(str(meta['genomes'])+' genomes belong to this species cluster in UHGG; the representative encodes '+str(meta['proteins'])+' predicted proteins.')
    elif d['source']=='CGF':observations.append('This fungus was cultured from human stool. Its CGF species cluster contains '+str(meta['genomes'])+' genomes; the representative isolate is '+meta['representative']+'.')
    elif d['source']=='UHGV':
        observations.append('The cluster is represented by '+str(meta.get('representative',''))+', a '+str(meta.get('length',''))+'-base viral genome.')
        if d.get('host'):observations.append('Sequence-based host prediction links this cluster to '+d['host']+'. Its assigned lifestyle is '+str(meta.get('lifestyle') or 'undetermined')+'.')
    else:
        if meta.get('observation'):observations.append(meta['observation']+' '+meta.get('observation_scope',''))
        if meta.get('data_type'):observations.append('The reference is a '+meta['data_type']+' dataset'+(' from strain '+meta['strain'] if meta.get('strain') else '')+'.')
    return dict(record=d,observations=observations,papers=[brief(pid,direct[pid]) for pid in ordered(direct)[:40]],total=len(direct),related=[brief(pid,'Predicted-host context' if d.get('host') else 'Genus context') for pid in ordered(related)[:12]],related_total=len(related),related_name=d.get('host') or d.get('genus'),aliases=aliases,sources=sources,links=list(links.values()),questions=questions[:6],functions=[dict(name=k,count=v) for k,v in sorted(functions.items(),key=lambda x:-x[1])],external='https://europepmc.org/search?'+urlencode(dict(query='"'+term+'"')) if term and re.fullmatch(r'[A-Za-z][A-Za-z -]+',term) else None)

def paper_ids(ident):
    d=descriptor(ident)
    return set(matches(d)[0]) if d else set()

def overview():
    ix=index();named={};linked=0
    for r in static('reference.json')['species']:
        name=scientific(r[1][6]);ids=set(ix['named'].get(name.lower(),{})) if name else set();ids.update(ix['records'].get(r[0],{}))
        if ids:linked+=1;named[r[0]]=len(ids)
    # Authored starting points keep the landing view grounded in specific questions and papers.
    starts=[]
    topics=[('Microbial partnerships','Bacteroides thetaiotaomicron'),('Mucus and metabolism','Akkermansia muciniphila'),('Methane and transit','Methanobrevibacter smithii'),('Immune signalling','Bacteroides fragilis'),('Butyrate production','Faecalibacterium prausnitzii')]
    for title,name in topics:
        row=next((r for r in static('reference.json')['species'] if r[1][6]==name),None) or next((r for r in static('reference.json')['species'] if re.sub(r'_[A-Z]+(?= |$)','',r[1][6])==name),None)
        if row:starts.append(dict(title=title,name=name,id=row[0],papers=named.get(row[0],0),context_papers=len(ix['genera'].get(re.sub(r'_[A-Z]+$','',row[1][5]).lower(),{}))))
    return dict(linked=named,linked_species=linked,catalogue_species=len(static('reference.json')['species']),starts=starts,library_papers=len(ix['model']['papers']))
