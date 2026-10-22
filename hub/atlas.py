"""Bounded catalogue queries and shared entities for every Learn destination."""
import json
from .db import connect,decode_metadata
from . import editorial

def _arg(args,key,default=''):
    return args.get(key,[default])[0][:200]

def catalogues(args):
    kind=_arg(args,'kind','viruses');source=_arg(args,'source');branch=_arg(args,'branch');host=_arg(args,'host');gut=_arg(args,'gut');q=_arg(args,'q').strip()
    clauses=["kind IN ('protists','fungi','eukaryotes')"] if kind=='all_eukaryotes' else ['kind=?'];params=[] if kind=='all_eukaryotes' else [kind]
    provenance=source if source in ('gpd','mgv') else ''
    if provenance:clauses.append('key IN (SELECT record_key FROM catalogue_crosswalk WHERE source=?)');params.append(provenance)
    for key,value in [('source','' if provenance else source),('branch',branch),('host',host),('gut',gut)]:
        if value:clauses.append(key+'=?');params.append(value)
    if q:
        clauses.append('(name LIKE ? OR id LIKE ? OR host LIKE ? OR key IN (SELECT record_key FROM catalogue_crosswalk WHERE source_id LIKE ?))');params += ['%'+q+'%']*4
    where=' WHERE '+' AND '.join(clauses)
    limit=min(100,max(1,int(_arg(args,'limit','40'))));offset=max(0,int(_arg(args,'offset','0')))
    with connect() as db:
        total=db.execute('SELECT COUNT(*) FROM catalogue_records'+where,params).fetchone()[0]
        rows=[dict(r) for r in db.execute('SELECT * FROM catalogue_records'+where+' ORDER BY name,id LIMIT ? OFFSET ?',(*params,limit,offset))]
        base=(" WHERE kind IN ('protists','fungi','eukaryotes')" if kind=='all_eukaryotes' else ' WHERE kind=?')+(' AND source=?' if source and not provenance else '');bp=([] if kind=='all_eukaryotes' else [kind])+([source] if source and not provenance else [])
        if provenance:base+=' AND key IN (SELECT record_key FROM catalogue_crosswalk WHERE source=?)';bp.append(provenance)
        branches=[dict(r) for r in db.execute('SELECT branch AS name,COUNT(*) AS count FROM catalogue_records'+base+' GROUP BY branch ORDER BY count DESC',bp)]
        hosts=[dict(r) for r in db.execute("SELECT host AS name,COUNT(*) AS count FROM catalogue_records"+base+" AND host!='' GROUP BY host ORDER BY count DESC LIMIT 80",bp)]
        kind_clause="r.kind IN ('protists','fungi','eukaryotes')" if kind=='all_eukaryotes' else 'r.kind=?'
        sources=[dict(r) for r in db.execute('SELECT s.*,COUNT(r.id) AS records FROM catalogue_sources s JOIN catalogue_records r ON r.source=s.id WHERE '+kind_clause+' GROUP BY s.id ORDER BY records DESC',() if kind=='all_eukaryotes' else (kind,))]
        all_sources=[dict(r) for r in db.execute('SELECT id,name FROM catalogue_sources')]
    starts=[]
    if kind in ('protists','fungi','all_eukaryotes'):
        with connect() as db:
            for name in (['Giardia duodenalis','Blastocystis','Dientamoeba','Cryptosporidium'] if kind!='fungi' else ['Candida albicans','Saccharomyces cerevisiae','Malassezia restricta']):
                row=db.execute("SELECT id,name FROM catalogue_records WHERE name LIKE ? ORDER BY length(name) LIMIT 1",(name+'%',)).fetchone()
                if row:starts.append(dict(row))
    for r in rows:r.pop('key');r['attributes']=decode_metadata(r['attributes'])
    return dict(research_starts=starts,provenance=[dict(id=r['id'],name=r['name']) for r in all_sources if r['id'] in ('gpd','mgv')],records=rows,total=total,offset=offset,has_more=offset+len(rows)<total,branches=branches,hosts=hosts,sources=sources)

def record(ident):
    with connect() as db:
        row=db.execute('SELECT r.*,s.name AS catalogue,s.url AS source_url,s.version,s.metadata_url,s.sha256,s.description FROM catalogue_records r JOIN catalogue_sources s ON s.id=r.source WHERE r.id=?',(ident,)).fetchone()
        if not row:return None
        item=dict(row);record_key=item.pop('key');item['attributes']=decode_metadata(item['attributes'])
        item['crosswalk']=[dict(r) for r in db.execute('SELECT source,source_id FROM catalogue_crosswalk WHERE record_key=? ORDER BY source,source_id LIMIT 60',(record_key,))]
        item['related']=[dict(r) for r in db.execute('SELECT id,name,source FROM catalogue_records WHERE entity_id=? AND id!=? LIMIT 20',(item['entity_id'],ident))]

    item['entity']=editorial.entity(item['entity_id'])
    return item

def entity(ident):
    e=editorial.entity(ident)
    with connect() as db:
        rows=[dict(r) for r in db.execute('SELECT id,name,source,attributes FROM catalogue_records WHERE entity_id=? LIMIT 20',(ident,))]
    if not e and rows:e={'id':ident,'kind':'organism','name':rows[0]['name'],'attributes':decode_metadata(rows[0]['attributes'])}
    if not e:return None
    return {**e,'catalogues':[{k:r[k] for k in ('id','name','source')} for r in rows]}
