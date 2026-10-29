"""Authored notes have one home; bibliographic facts come from the paper index."""
import json
from functools import lru_cache
from .db import ROOT,connect
from . import edits

@lru_cache(maxsize=8)
def _read(name,modified,revision):
    return edits.project(name,json.loads((ROOT/'content'/f'{name}.json').read_text()))

def read(name):
    path=ROOT/'content'/f'{name}.json'
    return _read(name,path.stat().st_mtime_ns,edits.revision())

def notes():
    overrides=edits.published()
    with connect() as db:
        papers={r['id']:edits.paper(dict(r),overrides) for r in db.execute('SELECT id,title,authors,journal,year,doi,pmid,url FROM papers')}
    audit=read('source_audit')
    result={}
    for slug,n in read('evidence').items():
        if n['paper'] not in papers:
            bibliography=audit.get(slug,{}).get('bibliography')
            if not bibliography:continue
            papers[n['paper']]=bibliography
        assessment=dict(audit.get(slug,{}))
        if assessment.get('paper')!=n['paper'] or assessment.get('reviewed_finding')!=n['finding']:
            assessment['support_status']='needs_review'
        result[slug]={**papers[n['paper']],**n,'review_basis':assessment.get('material_reviewed') if assessment.get('support_status')=='abstract_checked' else 'Editorial note · source review open','source_audit':assessment}
    return result

def document(view):
    if view not in ('anatomy','pathways','exploration','mechanisms','references'):return None
    data=read(view)
    if view=='anatomy':
        from .knowledge import model
        concepts=model()['concepts']
        data={**data,'microbes':{key:{**m,'name':concepts[key]['name'],'summary':concepts[key].get('summary',m.get('summary',[]))} for key,m in data['microbes'].items()},'community':[{**m,'name':concepts[m['id']]['name'],'summary':concepts[m['id']].get('summary',m['summary'])} for m in data['community']]}
    if view=='pathways':
        data={**data,'pages':{k:dict(v) for k,v in data['pages'].items()}}
        data['mechanisms']=read('mechanisms')['mechanisms']
        data['guides']=[{k:g[k] for k in ('id','title','lead')} for g in read('references')['guides']]
        fields=('id','title','lead','category','type','layout','organisms','aliases','connection','affected_sites','gut_evidence_status')
        data['pages']['infections']={**data['pages']['illness-recovery'], 'title':'Infections', 'intro':data['pages']['illness-recovery']['intro']}
        data['pages']['illness-recovery']=data['pages']['infections']
        from .knowledge import model
        data['entities']=model()['concepts']
    if view in ('anatomy','pathways','mechanisms'):
        from .knowledge import model
        m=model();data={**data,'knowledge':{k:m[k] for k in ('claims','findings','sources','concepts')}}
    return {**data,'studies':notes()} if view in ('anatomy','pathways','mechanisms','references') else data

def entity(ident):
    pathways=read('pathways')
    from .knowledge import model
    e=model()['concepts'].get(ident)
    if not e:return None
    links=[];papers=set()
    for page,p in pathways['pages'].items():
        for story in p['stories']:
            stages=[s for s in story['steps'] if ident in s['chain'] or ident in story['organisms']]
            if stages:
                links.append({'title':story['title'],'page':page,'url':'/'+page+'#item='+story['id']})
                papers.update(ref for s in stages for ref in s['studies'])
    return {**e,'pathways':links,'studies':sorted(papers)}
