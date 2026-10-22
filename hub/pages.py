"""Simple, original-style views of shared knowledge and condition records."""
import html
import json
from urllib.parse import quote, urlencode, urlsplit
from . import db, editorial, knowledge

def shell(title, body, active='Learn', description='', extra='', learn_path='/'):
    from . import navigation
    active=active if active in ('Learn','Explore','Research','References') else 'Learn'
    version=lambda name:'/records.'+name+'?v='+str((db.ROOT/'static'/('records.'+name)).stat().st_mtime_ns)
    tabs=navigation.exploring(learn_path) if active=='Explore' else ''
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{e(description or title)}"><title>{e(title)} — Gut Atlas</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/learn.css"><link rel="stylesheet" href="/explore-navigation.css"><link rel="stylesheet" href="{version('css')}"><link rel="stylesheet" href="/contribute.css"><script src="{version('js')}" defer></script><script src="/contribute.js" defer></script></head><body class="knowledge-page"><header class="masthead"><a class="wordmark" href="/" aria-label="Gut Atlas home"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="13"/><path d="M12 7v7c-6 2-4 7 1 7h7c4 0 4 5 0 5h-6M20 8c5 3 5 8 0 9h-5"/></svg><span>gut atlas</span></a><span class="masthead-note">A LIVING ANATOMY</span>{navigation.primary(active)}</header>{tabs}<main id="main">{body}</main>{extra}</body></html>"""


def e(value):
    return html.escape(str(value if value is not None else ''), quote=True)

def url(value):
    return e(value) if urlsplit(value or '').scheme in ('https', 'http') else '#'

def link(path, label, cls=''):
    return f'<a class="{e(cls)}" href="{e(path)}">{e(label)}</a>'

def pill(text, kind=''):
    return f'<span class="pill {e(kind)}">{e(text)}</span>'

def status(value):
    return {'abstract_checked': 'Abstract checked', 'guidance_checked':'Official guidance checked', 'editorially_reviewed': 'Editorially reviewed', 'needs_review': 'Review open', 'candidate': 'Suggested reference', 'supports': 'Supports', 'challenges': 'Challenges', 'qualifies': 'Qualifies', 'inconclusive_for': 'Inconclusive'}.get(value, value.replace('_', ' '))

def bread(items):
    return '<nav class="breadcrumbs" aria-label="Breadcrumb">'+ ' <span aria-hidden="true">/</span> '.join(link(p, n) if p else f'<span>{e(n)}</span>' for p, n in items) + '</nav>'

def topic_card(t, number=1):
    glyphs = {'fibre': '◌', 'gut-brain': '↝', 'fermented-foods': '♧', 'ibs': '≈', 'movement': '↗', 'testing': '◎'}
    return f'''<a class="topic-card" href="/topics/{e(t['id'])}"><div class="card-top"><span>{number:02d} / {e(t['category'])}</span><span class="card-glyph" aria-hidden="true">{glyphs.get(t['id'],'◌')}</span></div><h3>{e(t['title'])}</h3><p>{e(t['question'])}</p><span class="card-bottom">Follow the connections <span>↗</span></span></a>'''

def source_links(ids, m=None):
    m = m or knowledge.model()
    return ''.join((pill('Retracted source','warning') if m['sources'].get(sid,{}).get('retracted') else '')+link('/research?' + urlencode({'paper': sid}), m['sources'].get(sid, {}).get('title', sid), 'source-link') for sid in ids)

def finding_card(f, relation=None):
    m = knowledge.model()
    return f'''<article class="finding-card" id="{e(f['id'])}"><div class="meta-row">{pill(f['system'])}{pill(status(f['review']))}{pill(status(relation),'relation') if relation else ''}</div><h3>{e(f['outcome']) if f['outcome'] != 'Not extracted' else 'Observed result'}</h3><p>{e(f['summary'])}</p><dl class="finding-context"><div><dt>Population</dt><dd>{e(m["studies"][f["study"]].get("population","Not extracted"))}</dd></div><div><dt>Timepoint</dt><dd>{e(f.get("timepoint","Not extracted"))}</dd></div><div><dt>Comparison</dt><dd>{e(f['comparison'])}</dd></div><div><dt>Sample</dt><dd>{e(f['sample'])}</dd></div><div><dt>Material checked</dt><dd>{e(f['material_reviewed'])}</dd></div><div><dt>Source location</dt><dd>{e(f['source_locator'])}</dd></div><div><dt>Source assessment</dt><dd>{e(f.get('reviewed_by') or f.get('provenance',{}).get('reviewer') or 'Review open')} {e(f.get('reviewed_date',''))}</dd></div></dl>{source_links(f['source_ids'],m)}<div class="record-actions">{link('/findings/'+quote(f['id']),'Inspect the study ↗')}{link('/contribute?'+urlencode({'target':f['id'],'kind':'explanation'}),'Improve this result note ↗')}</div></article>'''

def claim_card(c, compact=False):
    m = knowledge.model()
    kinds = ', '.join(dict.fromkeys(m['findings'][x['finding']]['system'] for x in c['evidence'] if x['relation'] != 'candidate')) or 'Scope not assessed'
    return f'''<article class="claim-card"><div class="meta-row">{pill(kinds)}{pill(status(c['status']))}</div><h3>{link('/claims/'+quote(c['id']),c['text'])}</h3><p class="limit"><span>What this does not establish</span>{e(c['limitations'])}</p><div class="record-actions">{link('/claims/'+quote(c['id']),'How do we know? ↗')}{link('/contribute?'+urlencode({'target':c['id'],'kind':'evidence'}),'Add evidence ↗')}</div></article>'''

def process(t, m):
    cards = []
    for i, step in enumerate(t['steps']):
        c = m['claims'][step['claim']]
        cards.append(f'''<a class="process-card" href="/claims/{e(quote(c['id']))}"><span class="step-number">{i+1:02d}</span><div class="process-symbol" aria-hidden="true">{'◌' if i%2==0 else '↝'}</div><span class="eyebrow">{e(step['title'])}</span><h3>{e(m['concepts'][c['subject']]['name'])}</h3><div class="process-arrow"><span>{e(c['predicate'].replace('_',' '))}</span><b aria-hidden="true">↓</b></div><p>{e(m['concepts'][c['object']]['name'])}</p><small>{e(c['context'].get('system',''))} · See the finding ↗</small></a>''')
    return '<div class="process-grid">'+''.join(cards)+'</div>'

def topic_page(ident):
    m = knowledge.model()
    t = m['topics'].get(ident)
    if not t:
        return None
    claim_cards = ''.join(claim_card(m['claims'][cid]) for cid in t['claims'])
    concept_chips = ''.join(link('/concepts/'+quote(cid),m['concepts'][cid]['name'],'concept-chip') for cid in t['concepts'])
    fids = list(dict.fromkeys(x['finding'] for cid in t['claims'] for x in m['claims'][cid]['evidence']))
    evidence = ''.join(finding_card(m['findings'][fid]) for fid in fids)
    gaps = ''.join(f'<li>{e(g)}</li>' for g in t['gaps'])
    related = ''.join(topic_card(other,i+1) for i,other in enumerate(m['topics'].values()) if other['id'] != ident)[:20000]
    clinical_sources = ''
    practical=(''.join(['<div class="everyday-guidance"><span class="eyebrow">AT THE TABLE</span><p class="reading-copy">',e(m['claims'][t['practical_claim']]['text']),'</p>',link('/claims/'+t['practical_claim'],'Read the guidance and its scope ↗'),'</div>'])) if t.get('practical_claim') else ''
    if ident == 'ibs':
        clinical_sources = ''.join(f'<a class="source-link" href="{url(s["url"])}" target="_blank" rel="noopener">{e(s["title"])} ↗</a>' for sid in editorial.read('conditions')['ibs']['clinical_sources'] for s in [editorial.read('pathways')['sources'][sid]])
    body = f'''<div class="page-width">{bread([('/','Learn'),('',t['title'])])}<header class="topic-hero"><span class="eyebrow">{e(t['category'])}</span><h1>{e(t['title'])}</h1><p class="deck">{e(t['answer'])}</p><div class="topic-meta"><span>Updated {e(t['updated'])}</span><span>{len(fids)} source-linked findings</span>{link('/contribute?'+urlencode({'target':ident,'kind':'explanation'}),'Improve this explanation ↗')}</div></header><nav class="topic-tabs" aria-label="Read at your depth"><a href="#understand">Understand</a><a href="#practice">In practice</a><a href="#evidence">The evidence</a><a href="#questions">Open questions</a></nav><section class="topic-section" id="understand"><div class="section-heading"><div><span class="eyebrow">FOLLOW THE PROCESS</span><h2>{e(t['question'])}</h2></div></div>{process(t,m)}<p class="diagram-caption">Each relationship opens its observation, experimental setting and source. These steps bring together separate experiments.</p><details class="learning-check"><summary>Check your understanding: {e(t['quiz']['question'])}</summary><p>{e(t['quiz']['answer'])}</p></details><div class="concept-chips">{concept_chips}</div></section><section class="topic-section practice-section" id="practice"><span class="eyebrow">FROM MECHANISM TO MEANING</span><h2>What does this mean in practice?</h2>{practical}<p class="reading-copy">{e(t['clinical'])}</p>{clinical_sources}<p>{link('/living-well#item=fibre','Explore food in everyday life ↗') if ident=='fibre' else link('/fermentation','Explore food fermentation ↗') if ident=='fermented-foods' else ''}</p></section><section class="topic-section" id="evidence"><div class="section-heading"><div><span class="eyebrow">HOW WE KNOW</span><h2>Inspect the claims.</h2></div>{link('/evidence?'+urlencode({'topic':ident}),'Compare these findings ↗')}</div><p class="section-intro">{e(t['review_scope'])} An abstract check confirms the scope of the summary; full-text and independent scientific review are separate steps.</p><div class="claim-grid">{claim_cards}</div><details class="source-details"><summary>Read the individual study findings · {len(fids)}</summary>{evidence}</details></section><section class="topic-section questions-section" id="questions"><span class="eyebrow">AT THE EDGE OF UNDERSTANDING</span><h2>What would make the picture clearer?</h2><p class="reading-copy">{e(t['open_question'])}</p><ul class="research-questions">{gaps}</ul>{link('/contribute?'+urlencode({'target':ident,'kind':'gap'}),'Add a research question ↗','button')}</section><section class="topic-section"><span class="eyebrow">CONTINUE EXPLORING</span><h2>Follow another connection.</h2><div class="topic-grid">{related}</div></section></div>'''
    return shell(t['title'], body, description=t['answer'])

def claim_page(ident):
    c = knowledge.claim(ident)
    if not c:
        return None
    subjects = link('/concepts/'+quote(c['subject']),c['subject_concept']['name'],'concept-chip')+' <span>→</span> '+link('/concepts/'+quote(c['object']),c['object_concept']['name'],'concept-chip')
    contexts = ''.join(f'<div><dt>{e(k.replace("_"," "))}</dt><dd>{e(v)}</dd></div>' for k,v in c['context'].items())
    findings = ''.join(finding_card(f,f['relation']) for f in c['findings']) or '<p>No result has yet been attached to this exact relationship.</p>'
    topics = ''.join(link('/topics/'+tid, knowledge.model()['topics'][tid]['title'],'text-link') for tid in c['topic_ids'])
    extra = '<p class="review-notice">This relationship needs reassessment because a source or finding changed.</p>' if c['needs_reassessment'] else ''
    return shell('Inspect a claim',f'''<div class="page-width narrow">{bread([('/research','Research'),('','Inspect a claim')])}<header class="record-hero"><span class="eyebrow">A CLAIM, IN CONTEXT</span><h1 class="claim-title">{e(c['text'])}</h1><div class="meta-row">{pill(status(c['status']))}{pill(c['clinical_certainty']+' · clinical certainty')}</div>{extra}<div class="concept-chips">{subjects}</div></header><dl class="finding-context">{contexts}</dl><aside class="boundary"><span class="eyebrow">THE BOUNDARY OF THE CLAIM</span><p>{e(c['limitations'])}</p></aside><section class="topic-section"><h2>What bears on this claim?</h2><p>Support, qualification and disagreement stay attached to their own experimental settings.</p>{findings}</section><section class="topic-section"><h2>Help refine this claim.</h2><div class="hero-actions">{link('/contribute?'+urlencode({'target':ident,'kind':'evidence'}),'Attach a finding ↗','button primary')}{link('/contribute?'+urlencode({'target':ident,'kind':'explanation'}),'Improve the wording ↗')}</div><p>{topics}</p><details class="record-details"><summary>Record & reuse</summary><code>{e(c['id'])}</code>{link('/api/knowledge/claim?'+urlencode({'id':ident}),'Read the structured record ↗')}</details></section></div>''','Research')

def finding_page(ident):
    m = knowledge.model()
    f = m['findings'].get(ident)
    if not f:
        return None
    s = m['studies'][f['study']]
    claims = ''.join(claim_card(c) for c in m['claims'].values() if any(x['finding']==ident for x in c['evidence']))
    return shell('Study finding',f'''<div class="page-width narrow">{bread([('/research','Research'),('','A study finding')])}<header class="record-hero"><span class="eyebrow">OBSERVATION → INTERPRETATION → QUESTION</span><h1 class="claim-title">{e(s['title'])}</h1><p>{e(s['design'])}</p></header>{finding_card(f)}<section class="topic-section"><h2>Interpretation</h2><p class="reading-copy">{e(f['interpretation'])}</p><h2>What remains open?</h2><p>{e(f['open_question'])}</p><details><summary>Study identity and independence</summary><p>{e(s['independence'])}</p><code>{e(s['id'])}</code></details></section><section class="topic-section"><h2>Where this finding is used</h2><div class="claim-grid">{claims}</div></section></div>''','Research')

def concept_page(ident):
    c = knowledge.concept(ident)
    if not c:
        return None
    topics = ''.join(topic_card(t,i+1) for i,t in enumerate(c['topics']))
    claims = ''.join(claim_card(x) for x in sorted(c['claims'], key=lambda x:x['status']=='needs_review')[:18])
    summaries = ''.join(f'<p>{e(t)}</p>' for t in c.get('summary',[]))
    family = (f'<p>Part of {link("/concepts/"+quote(c["parent"]),knowledge.model()["concepts"][c["parent"]]["name"])}</p>' if c.get('parent') else '')+''.join(link('/concepts/'+quote(v['id']),v['name'],'concept-chip') for v in c['children'])
    return shell(c['name'],f'''<div class="page-width">{bread([('/explore','Explore'),('',c['name'])])}<header class="topic-hero"><span class="eyebrow">{e(c['kind'].replace('_',' '))} · {e(c.get('subtype',''))}</span><h1>{e(c['name'])}</h1><p class="deck">{e(c.get('definition',''))}</p>{family}</header><div class="reading-copy">{summaries}</div><section class="topic-section"><h2>Understand it in context.</h2><div class="topic-grid">{topics}</div></section><section class="topic-section"><h2>Relationships & evidence</h2><div class="claim-grid">{claims or '<p>No assessed claim is attached to this concept yet.</p>'}</div></section><section class="topic-section"><h2>Refine this concept.</h2>{link('/contribute?'+urlencode({'target':ident,'kind':'identity'}),'Correct a definition or mapping ↗','button')}<details class="record-details"><summary>Names & mappings</summary><p>Exact aliases: {e(', '.join(c.get('aliases',[])) or 'None recorded')}</p><p>Related search terms: {e(', '.join(c.get('related_terms',[])) or 'None recorded')}</p><pre>{e(json.dumps(c.get('mappings',[]),ensure_ascii=False,indent=2))}</pre></details></section></div>''','Explore')

def options(values, selected, all_label='All', blank=''):
    return f'<option value="{e(blank)}">{e(all_label)}</option>'+''.join(f'<option value="{e(k)}"'+(' selected' if k==selected else '')+f'>{e(v)}</option>' for k,v in values)

def research_page(args):
    if args.get('paper'):
        return paper_page(args['paper'][0])
    m = knowledge.model()
    data = knowledge.evidence(args)
    arg = lambda k:args.get(k,[''])[0]
    filtered = []
    for r in data['rows'][:80]:
        c,f,s = r['claim'],r['finding'],r['study']
        filtered.append(f'''<tr><td>{pill(status(r['relation']))}{link('/claims/'+quote(c['id']),c['text'])}</td><td>{e(f['summary'])}{link('/findings/'+quote(f['id']),'Inspect finding ↗','table-link')}</td><td>{e(f['system'])}<small>{e(s['population'])}</small><details><summary>Comparison & measurement</summary><p>{e(f['comparison'])}</p><p>Sample: {e(f['sample'])}</p><p>Outcome: {e(f['outcome'])}</p><p>Time: {e(f['timepoint'])}</p></details></td><td>{pill(status(f['review']))}<small>{e(f['material_reviewed'])}</small>{source_links(f['source_ids'],m)}</td></tr>''')
    topic_opts=options([(t['id'],t['title']) for t in data['topics']],arg('topic'),'All questions')
    system_opts=options([(s,s) for s in data['systems']],arg('system'),'All systems')
    review_opts=options([('abstract_checked','Abstract checked'),('guidance_checked','Official guidance checked'),('editorially_reviewed','Editorially reviewed'),('needs_review','Review open'),('all','Include suggested references')],arg('review'),'Assessed relationships')
    relation_opts=options([(r,status(r)) for r in ['supports','challenges','qualifies','inconclusive_for','candidate']],arg('relation'),'All relationships')
    concepts=[(i,c['name']) for i,c in m['concepts'].items() if c['kind']=='organism']
    design_opts=options([(s,s) for s in data['designs']],arg('design'),'All designs')
    changes=''.join(f'<article class="change"><time>{e(c["date"])}</time><h3>{e(c["title"])}</h3><p>{e(c["text"])}</p></article>' for c in m['changes'][:10])
    with db.connect() as conn:
        total=conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0]
        checked=conn.execute('SELECT SUM(refs_checked) FROM papers').fetchone()[0]
        latest=[dict(r) for r in conn.execute('SELECT id,title,year,study_type,published,added FROM papers WHERE retracted=0 ORDER BY added DESC,published DESC LIMIT 6')]
    new=''.join(f'<article class="new-paper">{pill(s["study_type"])}<h3>{link("/research?"+urlencode({"paper":s["id"]}),s["title"])}</h3><small>Published {e(s["published"])} · Indexed {e(s["added"][:10])}<br>Claim relevance unassessed</small></article>' for s in latest)
    form=f'''<form class="evidence-filters" action="/evidence"><label>Question<select name="topic">{topic_opts}</select></label><label>Experimental system<select name="system">{system_opts}</select></label><label>Review status<select name="review">{review_opts}</select></label><label>Relationship<select name="relation">{relation_opts}</select></label><label class="wide-label">Find a result<input name="q" type="search" value="{e(arg('q'))}" placeholder="A result, organism or outcome…"></label><details class="advanced-filters"><summary>Organism, design & measurement</summary><div><label>Organism<select name="concept">{options(concepts,arg('concept'),'All organisms')}</select></label><label>Study design<select name="design">{design_opts}</select></label><label>Sample<input name="sample" value="{e(arg('sample'))}" placeholder="Stool, tissue, culture…"></label><label>Measured outcome<input name="outcome" value="{e(arg('outcome'))}"></label><label>Publication year<input name="year" value="{e(arg('year'))}" inputmode="numeric"></label></div></details><button class="button primary">Compare findings ↗</button>{link('/evidence','Clear filters')}</form>'''
    body=f'''<div class="page-width">{bread([('/','Gut Atlas'),('','Research')])}<header class="topic-hero"><span class="eyebrow">OBSERVATIONS, WITH THEIR BOUNDARIES</span><h1>Follow the evidence.</h1><p class="deck">Compare what was observed, where it was measured, and which claims it can support.</p><div class="research-subnav">{link('#findings','Compare findings')}{link('#new','Newly indexed')}{link('#changes','What changed?')}{link('/papers','Paper library & citation map ↗')}</div></header><section id="findings">{form}<div class="results-top"><p><strong>{data['total']}</strong> matching claim–finding relationships{(' · first 80 shown' if data['total']>80 else '')}</p>{link('/api/evidence?'+urlencode({k:v[0] for k,v in args.items()}),'Export this comparison ↓')}</div><div class="table-scroll" tabindex="0" role="region" aria-label="Evidence comparison"><table class="evidence-table"><thead><tr><th>Claim & relationship</th><th>Observed finding</th><th>Setting & comparison</th><th>Review & source</th></tr></thead><tbody>{''.join(filtered) or '<tr><td colspan="4">No findings match these filters. Try a broader question or search the paper library.</td></tr>'}</tbody></table></div><p class="scope-note">Curated evidence, checked at the material shown. Evidence selection is not systematic; clinical certainty has not been graded. Multiple reports may describe the same study.</p></section><section class="topic-section" id="new"><span class="eyebrow">DISCOVERY</span><h2>Newly indexed papers.</h2><p>Publication dates and tags help discover work. A new paper enters the evidence above only through a finding linked to a claim.</p><div class="new-papers">{new}</div><p>{link('/papers?display=list','Browse all '+format(total,',')+' indexed papers ↗')}</p><p class="scope-note">The citation map covers the local index. References checked for {checked:,} / {total:,} papers; missing links do not establish missing evidence.</p></section><section class="topic-section" id="changes"><span class="eyebrow">THE ACCOUNT CHANGES WITH THE EVIDENCE</span><h2>What changed?</h2><div class="changes">{changes}</div></section></div>'''
    return shell('Research',body,'Research')

def paper_page(ident):
    notes=editorial.read('evidence')
    ident=notes.get(ident,{}).get('paper',ident)
    with db.connect() as conn:
        if ident.startswith('doi:'):
            row=conn.execute('SELECT * FROM papers WHERE doi=?',(ident[4:].lower(),)).fetchone()
        else:
            row=conn.execute('SELECT * FROM papers WHERE id=?',(ident,)).fetchone()
    if not row:
        m=knowledge.model();source=m['sources'].get(ident)
        if not source:return None
        findings=''.join(finding_card(f) for f in m['findings'].values() if ident in f['source_ids'])
        return shell(source['title'],f'<div class="page-width narrow"><header class="record-hero"><span class="eyebrow">{e(source.get("kind","source"))}</span><h1 class="claim-title">{e(source["title"])}</h1><a href="{url(source["url"])}" target="_blank" rel="noopener">Open original source ↗</a></header>{findings}</div>','Research')
    p=dict(row);m=knowledge.model()
    findings=''.join(finding_card(f) for f in m['findings'].values() if p['id'] in f['source_ids'])
    return shell(p['title'],f'''<div class="page-width narrow">{bread([('/research','Research'),('','Publication')])}<header class="record-hero"><span class="eyebrow">{e(p['journal'])} · {e(p['year'])}</span><h1 class="claim-title">{e(p['title'])}</h1><p>{e(p['authors'])}</p>{pill('Retracted publication','warning') if p['retracted'] else pill('Preprint' if p['id'].startswith('PPR:') else 'Published report')}<div class="hero-actions"><a class="button" href="{url(p['url'])}" target="_blank" rel="noopener">Open original source ↗</a>{link('/papers?'+urlencode({'paper':p['id']}),'Citation neighbourhood ↗')}</div></header><section class="topic-section"><h2>Findings connected to this source</h2>{findings or '<p>This publication is indexed for discovery. No reviewed finding from it has been attached to a claim yet.</p><p>'+link('/contribute?kind=evidence','Connect a finding to a claim ↗')+'</p>'}</section></div>''','Research')

def conditions_page(ident=None):
    data=editorial.read('conditions')
    if ident:
        c=data.get(ident)
        if not c:return None
        sources=''.join(f'<a class="source-link" href="{url(s["url"])}" target="_blank" rel="noopener">{e(s["title"])} ↗</a>' for sid in c['clinical_sources'] for s in [editorial.read('pathways')['sources'][sid]])
        return shell(c['title'],f'''<div class="page-width narrow">{bread([('/explore','Explore'),('/conditions','Conditions'),('',c['title'])])}<header class="topic-hero"><span class="eyebrow">{e(c['category'])}</span><h1>{e(c['title'])}</h1><p class="deck">{e(c['lead'])}</p><p>Affected sites: {e(', '.join(c['affected_sites']) or 'Not yet mapped')}</p></header><div class="reading-copy">{''.join('<p>'+e(p)+'</p>' for p in c['paragraphs'])}</div><aside class="boundary"><span class="eyebrow">THE GUT CONNECTION</span><p>The condition introduction is source-linked. Its microbiome relationships have not yet received a claim-by-claim evidence assessment.</p></aside>{sources}<section class="topic-section"><h2>Investigate further</h2>{link('/topics/ibs','Read the IBS learning topic ↗') if ident=='ibs' else ''}<p>{link('/papers?'+urlencode({'q':c['research_terms'],'display':'list'}),'Find relevant indexed papers ↗')}</p>{link('/contribute?'+urlencode({'target':'condition:'+ident,'kind':'identity'}),'Improve this condition record ↗','button')}</section></div>''',active='Explore',learn_path='/conditions')
    rows=''.join(f'<a class="condition-link" href="/condition/{e(k)}"><span>{e(c["category"])}</span><h3>{e(c["title"])}</h3><p>{e(c["lead"])}</p></a>' for k,c in sorted(data.items(),key=lambda x:x[1]['title']))
    return shell('Symptoms & conditions',f'<div class="page-width">{bread([("/explore","Explore"),("","Conditions")])}<header class="topic-hero"><span class="eyebrow">A STARTING POINT FOR UNDERSTANDING</span><h1>Symptoms & conditions.</h1><p class="deck">Explore the condition, its relevant physiology and the questions research is asking about the gut.</p><p>These source-linked introductions have different depths of microbiome evidence. Each page makes its coverage explicit.</p></header><label class="directory-search">Find a condition<input type="search" data-filter-list="condition-grid" placeholder="IBS, Crohn’s, iron deficiency…"></label><div class="condition-grid" id="condition-grid">{rows}</div></div>',active='Explore',learn_path='/conditions')

def guide_page(ident):
    d=editorial.read('references');g=next((g for g in d['guides'] if g['id']==ident),None)
    if not g:return None
    refs={r['id']:r for r in d['references']}
    sections=''.join(f'<section class="guide-section"><h2>{e(s["title"])}</h2><p>{e(s["text"])}</p><div class="record-actions">'+''.join(link('/findings/finding:'+slug,'Study finding ↗') for slug in s['studies'])+'</div></section>' for s in g['sections'])
    sources=''.join(f'<a class="source-link" href="{url(refs[r]["url"])}" target="_blank" rel="noopener">{e(refs[r]["name"])} ↗</a>' for r in g['sources'] if r in refs)
    return shell(g['title'],f'<div class="page-width narrow">{bread([("/","Learn"),("","Reading route")])}<header class="topic-hero"><span class="eyebrow">TAKE THE LONGER WAY IN</span><h1>{e(g["title"])}</h1><p class="deck">{e(g["lead"])}</p></header><article class="reading-copy">{sections}</article><section class="topic-section"><h2>Continue reading</h2>{sources}</section></div>')

def search_page(query):
    data=knowledge.search(query,12)
    sections=''
    for key,title in [('explanations','Explanations'),('concepts','Things & processes'),('evidence','Claims & evidence'),('sources','Indexed sources')]:
        if data[key]:sections+='<section class="search-group"><h2>'+title+'</h2>'+''.join(f'<a class="search-result" href="{e(r["url"])}"><h3>{e(r["title"])}</h3><p>{e(r["text"])}</p></a>' for r in data[key])+'</section>'
    if not sections:sections='<p>No matching records. Try a food, process, organism or condition.</p>'
    if data['suggestion']:sections='<p>Did you mean '+link('/search?'+urlencode({'q':data['suggestion']}),data['suggestion'])+'?</p>'+sections
    return shell('Search',f'<div class="page-width narrow">{bread([("/","Gut Atlas"),("","Search")])}<header class="topic-hero"><span class="eyebrow">FOLLOW A CONNECTION</span><h1>Search the atlas.</h1><form action="/search" class="page-search"><label class="sr-only" for="page-query">Search</label><input id="page-query" name="q" value="{e(query)}" type="search"><button class="button primary">Search ↗</button></form></header>{sections}</div>')

def contribute_page(args):
    m=knowledge.model();target=args.get('target',[''])[0];kind=args.get('kind',['explanation'])[0]
    from .contributions import resolve_target
    if target:
        try:
            ident,family=resolve_target(m,target,kind)
            target={'topics':'topic:','claims':'claim:','concepts':'concept:','findings':''}[family]+ident
        except ValueError:target=''
    targets=[('topic:'+i,'Topic · '+t['title']) for i,t in m['topics'].items()]+[('claim:'+i,'Claim · '+c['text']) for i,c in m['claims'].items()]+[('concept:'+i,'Concept · '+c['name']) for i,c in m['concepts'].items()]+[(i,'Finding · '+f['summary']) for i,f in m['findings'].items()]
    opts=options(targets,target,'Choose the topic, claim or concept')
    kinds=options([(k,n) for k,n in [('explanation','Improve an explanation'),('evidence','Attach a study finding'),('identity','Correct a concept or mapping'),('gap','Add a research question')]],kind,'Choose how to contribute')
    fields=''.join(f'<label>{label}<input name="{name}" maxlength="2000" data-evidence-field placeholder="{placeholder}"></label>' for name,label,placeholder in [('system','Experimental system','Human, mouse, defined culture…'),('design','Study design','Randomised trial, cohort, coculture…'),('population','Population / strains','Who or what was studied?'),('comparison','Comparison','Intervention or exposure versus what?'),('sample','Sample / compartment','Stool, tissue, blood, defined culture…'),('outcome','Measured outcome','What was actually measured?'),('source_locator','Source location','Figure, table, section or abstract'),('timepoint','Timepoint / duration','When was it measured?')])
    form=f'''<form id="knowledge-contribution" class="contribution-form"><label>What would you like to do?<select name="kind" id="contribution-kind" required>{kinds}</select></label><label>Find the record<input id="target-filter" type="search" placeholder="Filter topics, claims and concepts…" autocomplete="off"></label><label>Where does it belong?<select name="target" required>{opts}</select></label><label>Your proposed explanation, finding or question<textarea name="text" rows="6" maxlength="12000" required></textarea></label><fieldset id="evidence-fields" hidden><legend>The experiment behind the finding</legend><label>DOI, PMID or ENA accession<input name="source" data-evidence-field placeholder="10.…, PMID:…, PRJEB…"></label><label>How does it bear on the claim?<select name="relation" data-evidence-field><option value="supports">Supports</option><option value="challenges">Challenges</option><option value="qualifies">Qualifies its scope</option><option value="inconclusive_for">Inconclusive</option></select></label><div class="form-grid">{fields}</div><label>Material you reviewed<select name="material_reviewed" data-evidence-field><option value="">Choose…</option><option>Published abstract</option><option>Full paper</option><option>Full paper and supplementary material</option><option>Dataset and documentation</option></select></label><label>Existing study, if this is another report or comparison<select name="study">{options([(i,s['title']) for i,s in m['studies'].items()],'','Let the reviewer group this report')}</select></label></fieldset><details id="mapping-fields"><summary>Include an identifier mapping</summary><div class="form-grid"><label>Authority<input name="mapping_authority" placeholder="NCBI Taxonomy, GTDB, ChEBI…"></label><label>Identifier<input name="mapping_identifier"></label><label>Mapping scope<select name="mapping_relation"><option value="exact">Exact</option><option value="broader">Broader</option><option value="narrower">Narrower</option><option value="related">Related</option></select></label><label>Version / release<input name="mapping_version"></label></div></details><div class="form-grid"><label>Name (optional)<input name="name" maxlength="200" autocomplete="name"></label><label>Email (private, optional)<input name="email" maxlength="320" type="email" autocomplete="email"></label></div><label class="check-label"><input name="public_credit" type="checkbox"> Credit me publicly by name if accepted</label><label class="honeypot" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label><p class="scope-note">A reviewer checks the source and scope before publication. Your email stays private. Accepted changes update the connected explanations and evidence.</p><button class="button primary" type="submit">Send for review ↗</button><p id="contribution-status" role="status" aria-live="polite"></p></form>'''
    body=f'''<div class="page-width narrow">{bread([('/','Gut Atlas'),('','Contribute')])}<header class="topic-hero"><span class="eyebrow">MAKE THE SHARED PICTURE CLEARER</span><h1>Bring what you know.</h1><p class="deck">A clearer explanation. An experiment that changes the story. An identity that needs correcting. Add it where it belongs.</p></header>{form}</div>'''
    return shell('Contribute',body,'Contribute')

def review_page():
    return shell('Review contributions','''<div class="page-width narrow"><header class="topic-hero"><span class="eyebrow">EDITORIAL REVIEW</span><h1>Refine the shared account.</h1></header><form id="review-login" class="contribution-form"><label>Review password<input name="password" type="password" required autocomplete="current-password"></label><button class="button primary">Sign in ↗</button><p role="status" id="review-login-status"></p></form><section id="review-workspace" hidden><div class="review-toolbar"><label>Queue<select id="review-queue"><option>pending</option><option>accepted</option><option>rejected</option></select></label><button class="button" id="review-logout">Sign out</button></div><div id="review-items"></div></section></div>''','Contribute')

def render(path,args):
    if path=='/evidence':return research_page(args)
    if path=='/search':return search_page(args.get('q',[''])[0][:200])
    if path=='/contribute':return contribute_page(args)
    if path=='/review':return review_page()
    if path=='/conditions':return conditions_page()
    for prefix,fn in [('/topics/',topic_page),('/claims/',claim_page),('/findings/',finding_page),('/concepts/',concept_page),('/condition/',conditions_page),('/guides/',guide_page)]:
        if path.startswith(prefix):return fn(path[len(prefix):])
    return None
