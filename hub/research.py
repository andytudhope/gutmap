"""A shared literature layer for the anatomy, reference catalogues and paper map."""
import json
import re
from collections import Counter, defaultdict
from .db import ROOT, DB_PATH, connect, state
from .vocabulary import TOPICS
from .ingest import classify
from . import editorial,edits

_cache = None

def _design(kind):
    k=kind.lower()
    if 'random' in k:return 'Randomised trial'
    if 'mouse' in k or 'mice' in k or 'animal' in k:return 'Animal / preclinical'
    if 'coculture' in k or 'co-culture' in k or 'cell' in k or 'laboratory' in k or 'mutant' in k or 'enzyme' in k:return 'Mechanism experiment'
    if 'human' in k or 'people' in k or 'volunteer' in k:return 'Human study'
    return 'Research article'

def model():
    global _cache
    path=ROOT/'content/anatomy.json'
    pathway_path=ROOT/'content/pathways.json'
    with connect() as db:
        stamp=(edits.revision(),str(DB_PATH),tuple(db.execute('SELECT COUNT(*),MAX(updated),SUM(refs_checked) FROM papers').fetchone()),db.execute('SELECT COUNT(*) FROM citations').fetchone()[0],db.execute('SELECT COUNT(*) FROM references_pending').fetchone()[0],path.stat().st_mtime_ns,pathway_path.stat().st_mtime_ns,(ROOT/'content/mechanisms.json').stat().st_mtime_ns,(ROOT/'content/references.json').stat().st_mtime_ns,(ROOT/'content/evidence.json').stat().st_mtime_ns,(ROOT/'content/concepts.json').stat().st_mtime_ns,(ROOT/'content/source_audit.json').stat().st_mtime_ns,(ROOT/'content/pain_research.json').stat().st_mtime_ns,tuple(db.execute("SELECT COUNT(*),MAX(id) FROM knowledge_contributions WHERE status='accepted'").fetchone()))
        if _cache and _cache[0]==stamp:return _cache[1]
        rows=[dict(r) for r in db.execute('SELECT * FROM papers ORDER BY year DESC')]
        overrides=edits.published()
        for row in rows:edits.paper(row,overrides)
        edges=[tuple(r) for r in db.execute('SELECT source,target FROM citations')]
        pending=Counter(r[0] for r in db.execute('SELECT source FROM references_pending'))
        refreshed=state(db,'research_refresh') or state(db,'last_success')
    data=editorial.document('anatomy')
    pathway=editorial.document('pathways')
    papers={}
    aliases={}
    for p in rows:
        for key in ('topics','taxa','regions','functions'):p[key]=json.loads(p[key])
        p['annotated']=False;p['note']=None;p['note_id']=None;p['setting']=p['study_type'];p['population']='Not reviewed';p['entity_ids']=[];p['pathways']=[];p['datasets']=[]
        papers[p['id']]=p
        if p.get('doi'):aliases['doi:'+p['doi'].lower()]=p['id']
        if p.get('pmid'):aliases['pmid:'+p['pmid']]=p['id']
    for slug,note in data['studies'].items():
        doi=note.get('doi','').lower()
        match=re.search(r'pubmed.ncbi.nlm.nih.gov/(\d+)',note['url'])
        pmid=str(note.get('pmid') or (match.group(1) if match else ''))
        pid=aliases.get('doi:'+doi) if doi else None
        pid=note['paper']
        p=papers.get(pid,{})
        text=' '.join([note['title'],note['finding'],note['meaning']])
        topics,taxa,functions,regions,kind=classify({'title':note['title'],'abstractText':text})
        p.update(id=pid,title=note['title'],authors=p.get('authors') or note['authors'],journal=note['journal'],year=note['year'],doi=doi or p.get('doi',''),pmid=pmid or p.get('pmid'),study_type=p.get('study_type') if p.get('study_type') not in (None,'Research article') else _design(note['kind']),topics=sorted(set(p.get('topics',[])+topics)),taxa=sorted(set(p.get('taxa',[])+taxa)),functions=sorted(set(p.get('functions',[])+functions)),regions=note['regions'],setting=note['kind'],annotated=True,note=note,note_id=slug,retracted=p.get('retracted',0),source='Atlas reading notes + bibliographic metadata')
        if p.get('access')!='Free to read':
            p['url']=note['url'];p['access']='Free to read' if re.search(r'(pmc.ncbi.nlm.nih.gov/articles|europepmc.org/articles)',note['url']) else 'DOI / publisher'
        p['population']=note.get('population','Not reviewed');p['entity_ids']=p.get('entity_ids',[]);p['pathways']=p.get('pathways',[]);p['datasets']=p.get('datasets',[])
        for record_id in note.get('catalogue_records',[]):
            p['datasets'].append(dict(title='Microbes · '+record_id,url='/explore#record='+record_id))
        papers[pid]=p;aliases[slug]=pid
        if doi:aliases['doi:'+doi]=pid
        if pmid:aliases['pmid:'+pmid]=pid
    for ident,organism in [(k,v) for k,v in data['microbes'].items()]+[(m['id'],m) for m in data['community']]:
        habitats=organism.get('regions') or [r['id'] for r in data['regions'] if ident in r['residents']]
        if not habitats:continue
        url='/#organ='+habitats[0]+('&microbe=' if ident in data['microbes'] else '&community=')+ident
        for slug in organism.get('papers',[]):
            pid=aliases.get(slug)
            if pid in papers:papers[pid]['pathways'].append(dict(title='Organism · '+organism['name'],url=url))
    for page,content in pathway['pages'].items():
        for story in content['stories']:
            for stage in story.get('steps',[]):
                for slug in stage['studies']:
                    pid=aliases.get(slug)
                    if pid not in papers:continue
                    p=papers[pid]
                    p['entity_ids']=sorted(set(p['entity_ids']+stage['chain']+story['organisms']))
                    entry=dict(title=content['title']+' · '+story['title'],url='/'+page+'#item='+story['id'])
                    if entry not in p['pathways']:p['pathways'].append(entry)
    for mechanism in editorial.read('mechanisms')['mechanisms']:
        for step in mechanism['steps']:
            for slug in step['studies']:
                pid=aliases.get(slug)
                if pid in papers:
                    entry=dict(title='Mechanisms · '+mechanism['title']+' · '+step['title'],url='/mechanisms#map='+mechanism['id']+'&step='+step['id'])
                    if entry not in papers[pid]['pathways']:papers[pid]['pathways'].append(entry)
    for guide in editorial.read('references')['guides']:
        for slug in guide['studies']:
            pid=aliases.get(slug)
            if pid in papers:
                entry=dict(title='Reading routes · '+guide['title'],url='/references#guide='+guide['id'])
                if entry not in papers[pid]['pathways']:papers[pid]['pathways'].append(entry)
    for entry in editorial.read('pain_research')['records']:
        pid=aliases.get('doi:'+entry['metadata']['doi'])
        if pid in papers:
            papers[pid]['pathways'].append(dict(title='Inflammation · Persistent Pain',url='/inflammation#view=stories&item=pain'))
    dataset_links={
      '10.1101/2025.11.01.686033':('UHGV clusters','/explore#life=viruses'),
      '10.1016/j.cell.2021.01.029':('GPD source crosswalk','/explore#life=viruses&source=gpd'),
      '10.1038/s41564-021-00928-6':('MGV source crosswalk','/explore#life=viruses&source=mgv'),
      '10.64898/2026.06.24.734308':('EukDetect2 reference','/explore#life=protists&source=eukdetect2'),
      '10.24072/pcjournal.173':('EukProt datasets','/explore#life=protists&source=eukprot&scope=all'),
      '10.1016/j.cell.2024.04.043':('Cultivated gut fungi','/explore#life=fungi')}
    # Discovery labels link only to explicitly matching canonical names/aliases.
    # A genus label is never resolved to a species by taking its first word.
    entities={}
    from .knowledge import model as knowledge_model
    for ident,c in knowledge_model()['concepts'].items():
        if c['kind']!='organism':continue
        group=c.get('attributes',{}).get('group','')
        entry=dict(name=c['name'],learn='/concepts/'+ident,microbes='/explore#life='+{'Fungi':'fungi','Viruses':'viruses','Protists':'protists','Worms':'worms'}.get(group,'prokaryotes'))
        for name in [c['name'],*c.get('aliases',[])]:entities[name]=entry
    for p in papers.values():
        if p.get('doi') in dataset_links:
            title,link=dataset_links[p['doi']];p['datasets'].append(dict(title=title,url=link))
    # Canonical IDs allow a DOI-linked note and a PubMed record to share one node.
    refs=defaultdict(list);cited=defaultdict(list)
    edges=[(a,b) for a,b in edges if a in papers and b in papers and a!=b]
    for a,b in edges:refs[a].append(b);cited[b].append(a)
    region_names={r['id']:r['name'] for r in data['regions']}
    for p in papers.values():
        p['references']=len(refs[p['id']]);p['cited_by']=len(cited[p['id']]);p['pending_references']=pending[p['id']]
        p['regions']=[r for r in p['regions'] if r in region_names] or ['unspecified']
    selectors={field:sorted({value for p in papers.values() for value in (p[field] if isinstance(p[field],list) else [p[field]]) if value}) for field in ('taxa','functions','study_type','year')}
    result=dict(selectors=selectors,papers=papers,aliases=aliases,edges=edges,refs=refs,cited=cited,regions=region_names,topics={t['id']:t['title'] for t in TOPICS},entities=entities,clusters=pathway.get('clusters',{}),refreshed=refreshed)
    _cache=(stamp,result)
    return result

def collection(args):
    m=model()
    def arg(k):return args.get(k,[''])[0][:200]
    words=arg('q').lower().split()[:12]
    if arg('organism'):
        from .microbes import paper_ids
        organism_papers=paper_ids(arg('organism'))
    else:organism_papers=None
    def match(p):
        if organism_papers is not None and p['id'] not in organism_papers:return False
        if arg('guide') and not any(x['url']=='/references#guide='+arg('guide') for x in p['pathways']):return False
        if arg('mechanism') and not any(x['url'].startswith('/mechanisms#map='+arg('mechanism')+'&') for x in p['pathways']):return False
        if arg('population') and arg('population')!=p['population']:return False
        if arg('entity') and arg('entity') not in p['entity_ids']:return False
        if arg('region') and arg('region') not in p['regions']:return False
        if arg('topic') and arg('topic') not in p['topics']:return False
        if arg('taxon') and not any(arg('taxon').lower() in t.lower() for t in p['taxa']):return False
        if arg('function') and arg('function') not in p['functions']:return False
        if arg('evidence') and arg('evidence')!=p['study_type']:return False
        if arg('year') and str(p['year'])!=arg('year'):return False
        if arg('access')=='free' and p['access']!='Free to read':return False
        if arg('notes')=='1' and not p['annotated']:return False
        text=' '.join([p['title'],p['authors'],p['journal'],str(p['year']),p.get('doi') or '',p.get('pmid') or '',p['id'],*p['taxa'],*p['functions'],*(m['topics'].get(t,t) for t in p['topics']),*((p['note'] or {}).get(k,'') for k in ('finding','meaning'))]).lower()
        return all(w in text for w in words)
    papers=sorted((p for p in m['papers'].values() if match(p)),key=lambda p:(not p['annotated'],-(p['year'] or 0),-p['cited_by'],p['id']))
    total=len(papers);limit=min(1500,max(1,int(arg('limit') or 1000)));offset=max(0,int(arg('offset') or 0));papers=papers[offset:offset+limit];ids={p['id'] for p in papers}
    summary=next((m['clusters'][key+':'+arg(key)] for key in ('entity','function','taxon','topic') if key+':'+arg(key) in m['clusters']),None)
    if summary:summary={**summary,'papers':[m['papers'][m['aliases'][slug]] for slug in summary['studies'] if slug in m['aliases']]}
    return dict(selectors=m['selectors'],cluster_summary=summary,offset=offset,has_more=offset+len(papers)<total,papers=papers,edges=[e for e in m['edges'] if e[0] in ids and e[1] in ids],total=total,library_total=len(m['papers']),library_edges=len(m['edges']),references_checked=sum(bool(p.get('refs_checked')) for p in m['papers'].values()),annotated=sum(p['annotated'] for p in m['papers'].values()),regions=m['regions'],topics=m['topics'],entities=m['entities'],populations=sorted({p['population'] for p in m['papers'].values() if p['population']!='Not reviewed'}),evidence=sorted({p['study_type'] for p in m['papers'].values()}),refreshed=m['refreshed'])

def paper_detail(ident):
    m=model();ident=m['aliases'].get(ident,ident);p=m['papers'].get(ident)
    if not p:return None
    def brief(pid):
        p=m['papers'][pid]
        return {k:p.get(k) for k in ('id','title','year','authors','study_type','annotated','url','access','taxa','topics','regions','functions')}
    def shared(q):return 3*len(set(p['taxa'])&set(q['taxa']))+2*len(set(p['topics'])&set(q['topics']))+len(set(p['functions'])&set(q['functions']))
    others=sorted((q for q in m['papers'].values() if q['id']!=ident and shared(q)>0),key=lambda q:(-shared(q),not q['annotated'],-(q['year'] or 0)))[:16]
    refs=sorted(m['refs'][ident],key=lambda k:-(m['papers'][k]['year'] or 0));cited=sorted(m['cited'][ident],key=lambda k:-(m['papers'][k]['year'] or 0))
    return dict(paper=p,references=[brief(k) for k in refs],cited_by=[brief(k) for k in cited],shared=[brief(q['id']) for q in others],edges=[e for e in m['edges'] if ident in e])
