"""Shared concepts, contextual claims, study findings, sources and teaching views."""
import copy
import difflib
import json
import re
from collections import defaultdict
from urllib.parse import quote

from . import db, editorial, edits

KINDS = {'place', 'organism', 'molecule', 'food', 'process', 'exposure',
         'intervention', 'community', 'host_component', 'condition', 'symptom',
         'measurement', 'mechanism_component'}
RELATIONS = {'supports', 'challenges', 'qualifies', 'inconclusive_for', 'candidate'}
_cache = None


def validate(concepts, data, topics):
    errors = []
    for ident, c in concepts.items():
        if c['id'] != ident or c['kind'] not in KINDS:
            errors.append('Invalid concept: ' + ident)
        if c.get('parent') and c['parent'] not in concepts:
            errors.append('Unknown parent: ' + ident)
        if c.get('parent') in concepts and (c['kind']!='organism' or concepts[c['parent']]['kind']!='organism'):
            errors.append('Taxonomic parent must be an organism concept: '+ident)
    for ident, f in data['findings'].items():
        if f['study'] not in data['studies']:
            errors.append('Unknown study: ' + ident)
        elif not set(f['source_ids'])<=set(data['studies'][f['study']]['source_ids']):
            errors.append('Finding source is absent from its study: '+ident)
    for ident, c in data['claims'].items():
        for key in ('subject', 'object'):
            if c[key] not in concepts:
                errors.append('Unknown concept in ' + ident + ': ' + c[key])
        for e in c['evidence']:
            if e['finding'] not in data['findings'] or e['relation'] not in RELATIONS:
                errors.append('Invalid evidence link: ' + ident)
        if c['predicate']=='degrades' and c['subject'] in concepts and c['object'] in concepts:
            if concepts[c['subject']]['kind'] not in ('organism','host_component') or concepts[c['object']]['kind'] not in ('molecule','food'):
                errors.append('Degradation needs a biological actor and material: '+ident)
    for ident, topic in topics.items():
        if any(c not in concepts for c in topic['concepts']):
            errors.append('Unknown topic concept: ' + ident)
        if any(c not in data['claims'] for c in topic['claims']):
            errors.append('Unknown topic claim: ' + ident)
        if any(s['claim'] not in topic['claims'] for s in topic['steps']):
            errors.append('A teaching step must use an explicit topic claim: '+ident)
    if errors:
        raise ValueError('; '.join(errors))


def model():
    global _cache
    names = ('concepts', 'knowledge', 'topics', 'evidence', 'source_audit', 'anatomy')
    with db.connect() as conn:
        contribution_revision = conn.execute("SELECT COALESCE(MAX(id),0),COUNT(*) FROM knowledge_contributions WHERE status='accepted'").fetchone()
        paper_stamp = tuple(conn.execute('SELECT COUNT(*),MAX(updated),SUM(retracted) FROM papers').fetchone())
    stamp = (str(db.DB_PATH), tuple((db.ROOT / 'content' / (n + '.json')).stat().st_mtime_ns for n in names),
             edits.revision(), tuple(contribution_revision), paper_stamp)
    if _cache and _cache[0] == stamp:
        return _cache[1]
    concepts = copy.deepcopy(editorial.read('concepts'))
    data = copy.deepcopy(editorial.read('knowledge'))
    topics = copy.deepcopy(editorial.read('topics'))
    anatomy=editorial.read('anatomy')
    for r in anatomy['regions']:
        concepts[r['id']].update(definition=r['role'],summary=[r['role'],r['habitat']])
    for c in [*anatomy['microbes'].values(),*anatomy['community']]:
        concepts[c['id']]['summary']=c.get('summary',[c.get('role','')])
    notes = editorial.read('evidence')
    audit = editorial.read('source_audit')
    source_ids = {s for f in data['findings'].values() for s in f['source_ids']}
    sources = copy.deepcopy(data.get('sources',{}))
    with db.connect() as conn:
        for r in conn.execute('SELECT id,title,authors,journal,year,doi,pmid,url,study_type,retracted FROM papers WHERE id IN (' + ','.join('?' for _ in source_ids) + ')', tuple(source_ids)):
            sources[r['id']] = {**dict(r), 'kind': 'publication', 'publication_status': 'retracted' if r['retracted'] else 'preprint' if r['id'].startswith('PPR:') else 'published report'}
        for r in conn.execute('SELECT * FROM knowledge_sources'):
            sources[r['id']] = dict(r)
        accepted = [dict(r) for r in conn.execute("SELECT * FROM knowledge_contributions WHERE status='accepted' ORDER BY id")]
        for contribution in accepted:
            sid=json.loads(contribution['payload']).get('source_id')
            if sid and sid not in sources:
                r=conn.execute('SELECT id,title,authors,journal,year,doi,pmid,url,study_type,retracted FROM papers WHERE id=?',(sid,)).fetchone()
                if r:sources[sid]={**dict(r),'kind':'publication','publication_status':'retracted' if r['retracted'] else 'published report'}
    for slug, a in audit.items():
        if a['paper'] not in sources and a.get('bibliography'):
            r = a['bibliography']
            sources[a['paper']] = {**r, 'kind': 'publication', 'publication_status': 'retracted' if r.get('retracted') else 'preprint' if a['paper'].startswith('PPR:') else 'published report'}
    for ident, f in data['findings'].items():
        note = notes.get(f.get('note'))
        if note:
            changed = f['summary'] != note['finding'] or f['source_ids'] != [note['paper']]
            f.update(summary=note['finding'], interpretation=note['meaning'], open_question=note['question'], source_ids=[note['paper']])
            assessment=audit.get(f['note'],{})
            if changed or assessment.get('support_status')!='abstract_checked' or assessment.get('reviewed_finding')!=note['finding'] or assessment.get('paper')!=note['paper']:
                f['review'] = 'needs_review'
                f['review_note'] = 'The note changed after its source assessment.' if changed else 'Scientific source support review is open.'
            else:
                f['review']='abstract_checked'
                f['material_reviewed']=assessment['material_reviewed']
                f['reviewed_by']=assessment.get('reviewer','Source check')
                f['reviewed_date']=assessment.get('checked','')
    for row in accepted:
        apply_contribution(concepts, data, topics, row)
    for f in data['findings'].values():
        if any(sources.get(s,{}).get('retracted') for s in f['source_ids']):
            f.update(review='needs_review',review_note='A source has been retracted; reassessment is required.')
    validate(concepts, data, topics)
    used_by = defaultdict(list)
    for tid, t in topics.items():
        for cid in t['claims']:
            used_by[cid].append(tid)
    for cid, c in data['claims'].items():
        c['topic_ids'] = used_by[cid]
        c['needs_reassessment'] = any(
            data['findings'][e['finding']]['review'] == 'needs_review'
            or any(sources.get(s, {}).get('retracted') for s in data['findings'][e['finding']]['source_ids'])
            for e in c['evidence'] if e['relation'] != 'candidate')
        if c['needs_reassessment']:
            c['status'] = 'needs_review'
    result = dict(concepts=concepts, claims=data['claims'], studies=data['studies'],
                  findings=data['findings'], sources=sources, topics=topics,
                  changes=data['changes'], schema_version=1)
    _cache = stamp, result
    return result


def apply_contribution(concepts, data, topics, row):
    p = json.loads(row['payload'])
    credit = row['name'] if row['public_credit'] else 'Community contributor'
    provenance = dict(contribution=row['id'], credit=credit, reviewer=row['reviewer'], reviewed=row['decided'])
    target = row['target']
    if row['kind'] == 'evidence':
        sid = p.get('study') or 'study:contribution:' + str(row['id'])
        # Reuse an existing report grouping unless a reviewer specifies a comparison.
        if not p.get('study'):
            sid = next((k for k, s in data['studies'].items() if p['source_id'] in s['source_ids']), sid)
        data['studies'].setdefault(sid, dict(id=sid, title=p['source_title'], design=p['design'], system=p['system'], population=p['population'], source_ids=[p['source_id']], independence='Report grouping; independent replication not assumed'))
        if p['source_id'] not in data['studies'][sid]['source_ids']:
            data['studies'][sid]['source_ids'].append(p['source_id'])
        fid = 'finding:contribution:' + str(row['id'])
        data['findings'][fid] = dict(id=fid, study=sid, summary=p['text'], interpretation=p.get('interpretation', ''), open_question=p.get('question', ''), source_ids=[p['source_id']], source_locator=p['source_locator'], system=p['system'], sample=p['sample'], outcome=p['outcome'], comparison=p['comparison'], timepoint=p.get('timepoint', 'Not extracted'), effect_size=None, uncertainty=None, review='editorially_reviewed', material_reviewed=p['material_reviewed'], regions=[], provenance=provenance)
        data['claims'][target]['evidence'].append(dict(finding=fid, relation=p['relation']))
    elif row['kind'] == 'explanation':
        family=p.get('record_type')
        if family=='concepts':
            concepts[target].update(definition=p['text'],provenance=provenance)
        elif target in data['claims']:
            data['claims'][target].update(text=p['text'], provenance=provenance)
        elif target in topics:
            topics[target].update(answer=p['text'], provenance=provenance)
        elif target in concepts:
            concepts[target].update(definition=p['text'], provenance=provenance)
        elif target in data['findings']:
            data['findings'][target].update(summary=p['text'], review='needs_review', provenance=provenance)
    elif row['kind'] == 'identity':
        concepts[target]['definition'] = p['text']
        if p.get('mapping'):
            concepts[target]['mappings'].append(p['mapping'])
        concepts[target]['provenance'] = provenance
    elif row['kind'] == 'gap':
        if target in topics and p.get('record_type')!='claims':
            topics[target]['gaps'].append(p['text'])
        elif target in data['claims']:
            data['claims'][target].setdefault('gaps', []).append(p['text'])
    data['changes'].insert(0, dict(date=row['decided'][:10], title={'evidence': 'Evidence added', 'explanation': 'Explanation improved', 'identity': 'Concept clarified', 'gap': 'Research question added'}[row['kind']], text=p['text'], claims=[target] if target in data['claims'] else [], provenance=provenance))


def claim(ident):
    m = model()
    c = m['claims'].get(ident)
    if not c:
        return None
    return {**c, 'subject_concept': m['concepts'][c['subject']], 'object_concept': m['concepts'][c['object']],
            'findings': [{**m['findings'][e['finding']], 'relation': e['relation'],
                          'study_record': m['studies'][m['findings'][e['finding']]['study']],
                          'sources': [m['sources'].get(s, dict(id=s, title=s, url='')) for s in m['findings'][e['finding']]['source_ids']]}
                         for e in c['evidence']]}


def concept(ident):
    m = model()
    c = m['concepts'].get(ident)
    if not c:
        return None
    claims = [v for v in m['claims'].values() if ident in [v['subject'], v['object'], *v.get('concepts', [])]]
    return {**c, 'claims': claims, 'topics': [t for t in m['topics'].values() if ident in t['concepts']],
            'children': [v for v in m['concepts'].values() if v.get('parent') == ident]}


def evidence(args):
    m = model()
    def arg(key):
        return args.get(key, [''])[0][:300]
    rows = []
    for cid, c in m['claims'].items():
        if arg('topic') and arg('topic') not in c['topic_ids']:
            continue
        if arg('concept') and arg('concept') not in (c['subject'], c['object'], *c.get('concepts', [])):
            continue
        for link in c['evidence']:
            if link['relation'] == 'candidate' and arg('relation') != 'candidate' and arg('review') != 'all':
                continue
            f = m['findings'][link['finding']]
            s = m['studies'][f['study']]
            if arg('review') and arg('review') != 'all' and arg('review') != f['review']:
                continue
            if arg('relation') and arg('relation') != link['relation']:
                continue
            if arg('system') and arg('system') != f['system']:
                continue
            if arg('sample') and arg('sample').lower() not in f['sample'].lower():
                continue
            if arg('outcome') and arg('outcome').lower() not in f['outcome'].lower():
                continue
            if arg('design') and arg('design') != s['design']:
                continue
            if arg('q') and arg('q').lower() not in ' '.join([c['text'], f['summary'], f['outcome'], s['population'], m['concepts'][c['subject']]['name'], m['concepts'][c['object']]['name']]).lower():
                continue
            sources = [m['sources'].get(sid, {}) for sid in f['source_ids']]
            if arg('year') and not any(str(s.get('year')) == arg('year') for s in sources):
                continue
            rows.append(dict(claim=c, finding=f, study=s, relation=link['relation'], sources=sources))
    rows.sort(key=lambda r: (r['relation'] == 'candidate', r['finding']['review'] == 'needs_review', -max([s.get('year') or 0 for s in r['sources']] or [0]), r['claim']['id']))
    return dict(rows=rows, total=len(rows), topics=list(m['topics'].values()),
                systems=sorted({f['system'] for f in m['findings'].values()}),
                designs=sorted({s['design'] for s in m['studies'].values()}),
                review_counts={k: sum(f['review'] == k for f in m['findings'].values()) for k in ('abstract_checked', 'guidance_checked', 'needs_review', 'editorially_reviewed')})


def normalise(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.lower().replace('fiber', 'fibre')).strip()


def search(query, limit=6):
    m = model()
    q = normalise(query)[:200]
    result = dict(query=query, explanations=[], concepts=[], evidence=[], sources=[], suggestion=None)
    if not q:
        return result
    words = q.split()
    def score(strings):
        values = [normalise(str(s)) for s in strings]
        text = ' '.join(values)
        return (100 if q in values else 20 if any(v.startswith(q) for v in values) else 5) if all(w in text for w in words) else 0
    for t in m['topics'].values():
        n = score([t['title'], t['question'], t['answer'], *(m['concepts'][i]['name'] for i in t['concepts'])])
        if n:
            result['explanations'].append(dict(id=t['id'], title=t['title'], text=t['answer'], url='/topics/' + t['id'], score=n))
    for page, view in editorial.read('pathways')['pages'].items():
        for story in view['stories']:
            n = score([story['title'], story['lead'], *story.get('aliases', []), *story.get('tags', [])])
            if n:
                result['explanations'].append(dict(id=story['id'], title=story['title'], text=story['lead'], url='/'+page+'#item='+story['id'], score=n))
    for c in m['concepts'].values():
        n = score([c['name'], *c.get('aliases', []), *c.get('related_terms', [])])
        if n:
            related=any(q==normalise(t) for t in c.get('related_terms',[])) and q not in [normalise(c['name']),*[normalise(a) for a in c.get('aliases',[])]]
            result['concepts'].append(dict(id=c['id'], title=c['name'], text=('Related search term · ' if related else '')+c['kind'] + ' · ' + c.get('definition', ''), match_kind='related' if related else 'name', url=('/condition/'+c['id'][10:]) if c['kind']=='condition' else '/concepts/' + quote(c['id']), score=n))
    for c in m['claims'].values():
        n = score([c['text']])
        if n:
            result['evidence'].append(dict(id=c['id'], title=c['text'], text=c['status'].replace('_', ' '), url='/claims/' + quote(c['id']), score=n))
    with db.connect() as conn:
        clauses = ['(title LIKE ? OR doi LIKE ? OR pmid LIKE ?)'] * len(words)
        params = [v for w in words for v in ['%' + w + '%'] * 3]
        for r in conn.execute('SELECT id,title,year,url FROM papers WHERE ' + ' AND '.join(clauses) + ' ORDER BY year DESC LIMIT ?', (*params, limit)):
            result['sources'].append(dict(id=r['id'], title=r['title'], text=str(r['year']) + ' · Indexed publication', url='/research?paper=' + quote(r['id'])))
    for key in ('explanations', 'concepts', 'evidence'):
        result[key] = sorted(result[key], key=lambda x: -x['score'])[:limit]
    if not any(result[k] for k in ('explanations', 'concepts', 'evidence', 'sources')):
        names = {normalise(c['name']): c['name'] for c in m['concepts'].values()}
        near = difflib.get_close_matches(q, names, n=1, cutoff=.7)
        result['suggestion'] = names[near[0]] if near else None
    return result
