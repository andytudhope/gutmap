"""Targeted evidence contributions and reviewer-approved knowledge overlays."""
import json
import re
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import urlopen
from . import db, edits


def initialize(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS knowledge_sources (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL,
      version TEXT NOT NULL DEFAULT '', checked TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS knowledge_contributions (
      id INTEGER PRIMARY KEY, created TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
      CHECK(status IN ('pending','accepted','rejected')), kind TEXT NOT NULL, target TEXT NOT NULL,
      payload TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
      public_credit INTEGER NOT NULL DEFAULT 0, reviewer TEXT NOT NULL DEFAULT '',
      decided TEXT NOT NULL DEFAULT '', decision_note TEXT NOT NULL DEFAULT ''
    );''')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def resolve_source(value):
    from . import ingest
    value = edits.text(value, 300, True).strip()
    doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', value, flags=re.I)
    doi = re.sub(r'^doi:', '', doi, flags=re.I)
    pmid = re.sub(r'^(?:PMID:|MED:)', '', value, flags=re.I).strip()
    match = re.fullmatch(r'https://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?', value)
    if match:
        pmid = match[1]
    with db.connect() as conn:
        r = conn.execute('SELECT id,title,url FROM papers WHERE id=? OR doi=? OR pmid=?', (value, doi.lower(), pmid)).fetchone()
        if r:
            return dict(r)
    if re.fullmatch(r'\d{1,10}', pmid):
        data = ingest.fetch('search', dict(query='SRC:MED AND EXT_ID:' + pmid, format='json', resultType='core', pageSize=1))
        records = data.get('resultList', {}).get('result', [])
        if not records:
            raise ValueError('No publication found for this PMID')
        r = records[0]
    elif re.fullmatch(r'10\.\d{4,9}/\S+', doi):
        with urlopen('https://api.crossref.org/works/' + quote(doi, safe=''), timeout=15) as response:
            m = json.load(response)['message']
        r = dict(id=m['DOI'], source='DOI', doi=m['DOI'], title=m['title'][0], pubYear=str(m['published']['date-parts'][0][0]), authorString=', '.join(a.get('family', '') for a in m.get('author', [])), journalTitle=m.get('container-title', [''])[0])
    elif re.fullmatch(r'(?:PRJ[END][AB]\d+|[SED]R[PRSX]\d+|GCA_\d+(?:\.\d+)?)', value):
        from xml.etree import ElementTree
        try:
            with urlopen('https://www.ebi.ac.uk/ena/browser/api/xml/' + quote(value), timeout=15) as response:
                root = ElementTree.fromstring(response.read())
            title = next((e.text for e in root.iter() if e.tag.endswith(('TITLE', 'STUDY_TITLE')) and e.text), value)
        except Exception as exc:
            raise ValueError('The dataset accession could not be resolved at ENA') from exc
        source = dict(id=value, title=title, kind='dataset', url='https://www.ebi.ac.uk/ena/browser/view/' + value, version='Accession checked ' + now()[:10], checked=now())
        with db.connect() as conn:
            conn.execute('INSERT OR REPLACE INTO knowledge_sources VALUES (:id,:title,:kind,:url,:version,:checked)', source)
        return source
    else:
        raise ValueError('Use a DOI, PMID, or supported ENA study, sample, run or assembly accession')
    with db.connect() as conn:
        ingest.upsert(conn, r)
        if r.get('doi'):
            found = conn.execute('SELECT id,title,url FROM papers WHERE doi=?', (r['doi'].lower(),)).fetchone()
        else:
            found = conn.execute('SELECT id,title,url FROM papers WHERE id=?', (r['source']+':'+str(r['id']),)).fetchone()
        return dict(found)


def target_fingerprint(record):
    fields={k:record.get(k) for k in ('text','answer','definition','name','subject','predicate','object','context','summary','mappings')}
    return hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def resolve_target(m, value, kind):
    for prefix, family in [('topic:','topics'),('concept:','concepts'),('claim:','claims')]:
        if value.startswith(prefix):
            ident=value[len(prefix):]
            if ident not in m[family]:raise ValueError('The selected record does not exist')
            return ident,family
    preferred=('claims',) if kind=='evidence' else ('concepts',) if kind=='identity' else ('topics','claims') if kind=='gap' else ('claims','findings','topics','concepts')
    for family in preferred:
        if value in m[family]:return value,family
    raise ValueError('Choose a record appropriate to this contribution')


def clean_payload(kind, data):
    p = {'text': edits.text(data.get('text'), 12000, True).strip()}
    if kind == 'evidence':
        for key in ('system', 'design', 'population', 'sample', 'outcome', 'comparison', 'material_reviewed', 'source_locator'):
            p[key] = edits.text(data.get(key), 2000, True).strip()
        p['relation'] = edits.text(data.get('relation'), 40, True)
        if p['relation'] not in ('supports', 'challenges', 'qualifies', 'inconclusive_for'):
            raise ValueError('Choose how the finding bears on the claim')
        if p['material_reviewed'] not in ('Published abstract', 'Full paper', 'Full paper and supplementary material', 'Dataset and documentation'):
            raise ValueError('Identify the material you reviewed')
        for key in ('timepoint', 'interpretation', 'question', 'study'):
            p[key] = edits.text(data.get(key, ''), 2000)
    if kind == 'identity' and data.get('mapping'):
        mapping = data['mapping']
        if not isinstance(mapping, dict) or mapping.get('relation') not in ('exact', 'broader', 'narrower', 'related'):
            raise ValueError('A mapping needs an explicit scope')
        p['mapping'] = {k: edits.text(mapping.get(k), 400, True) for k in ('authority', 'identifier', 'relation', 'version')}
    return p


def submit(data):
    from . import knowledge
    if data.get('website'):
        raise ValueError('Invalid submission')
    kind = data.get('kind')
    if kind not in ('explanation', 'evidence', 'identity', 'gap'):
        raise ValueError('Choose a contribution type')
    target = edits.text(data.get('target'), 300, True)
    m = knowledge.model()
    target,family=resolve_target(m,target,kind)
    if target not in {**m['concepts'], **m['claims'], **m['findings'], **m['topics']}:
        raise ValueError('Choose a topic, concept, claim or finding from the atlas')
    if kind == 'evidence' and family!='claims':
        raise ValueError('Attach evidence to a specific claim')
    if kind == 'identity' and family!='concepts':
        raise ValueError('Attach an identity correction to a concept')
    if kind == 'gap' and family not in ('claims','topics'):
        raise ValueError('Attach a question to a topic or claim')
    payload = clean_payload(kind, data)
    payload['record_type']=family
    record=m[family][target]
    payload['_target_fingerprint']=target_fingerprint(record)
    if kind == 'evidence':
        if payload.get('study') and payload['study'] not in m['studies']:
            raise ValueError('The selected study does not exist')
        source = resolve_source(data.get('source'))
        payload.update(source_id=source['id'], source_title=source['title'])
    name = edits.text(data.get('name', ''), 200)
    email = edits.text(data.get('email', ''), 320)
    credit = data.get('public_credit') is True
    if credit and not name.strip():
        raise ValueError('Supply a name to receive public credit')
    with db.connect() as conn:
        ident = conn.execute('INSERT INTO knowledge_contributions(created,kind,target,payload,name,email,public_credit) VALUES (?,?,?,?,?,?,?)', (now(), kind, target, json.dumps(payload, ensure_ascii=False), name, email, int(credit))).lastrowid
    return dict(id=ident, status='pending')


def queue(status='pending'):
    if status not in ('pending', 'accepted', 'rejected'):
        raise ValueError('Unknown queue')
    with db.connect() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM knowledge_contributions WHERE status=? ORDER BY id DESC LIMIT 100', (status,))]


def decide(data):
    from . import knowledge
    status = data.get('status')
    if status not in ('accepted', 'rejected'):
        raise ValueError('Choose accept or reject')
    reviewer = edits.text(data.get('reviewer'), 200, True).strip()
    note = edits.text(data.get('decision_note'), 4000, True).strip()
    with db.connect() as conn:
        row = conn.execute('SELECT * FROM knowledge_contributions WHERE id=?', (int(data['id']),)).fetchone()
        if not row:
            raise ValueError('Contribution not found')
        if row['status'] != 'pending':
            raise edits.Conflict('This contribution already has a decision')
    payload = json.loads(row['payload'])
    if status == 'accepted':
        if data.get('replacement'):
            payload['text'] = edits.text(data['replacement'], 12000, True)
        m = knowledge.model()
        family=payload.get('record_type')
        record=m[family].get(row['target']) if family else {**m['concepts'],**m['claims'],**m['findings'],**m['topics']}.get(row['target'])
        if not record or (payload.get('_target_fingerprint') and payload['_target_fingerprint']!=target_fingerprint(record)):
            raise edits.Conflict('The target changed after this contribution. Review the current record and submit an updated proposal.')
        if row['kind'] == 'evidence':
            if row['target'] not in m['claims']:
                raise edits.Conflict('The target claim no longer exists')
            p = clean_payload('evidence', payload)
            payload.update(p)
        trial = {**dict(row), 'payload': json.dumps(payload), 'reviewer': reviewer, 'decided': now()}
        import copy
        c, d, t = copy.deepcopy(m['concepts']), copy.deepcopy({k: m[k] for k in ('claims', 'studies', 'findings', 'changes')}), copy.deepcopy(m['topics'])
        knowledge.apply_contribution(c, d, t, trial)
        knowledge.validate(c, d, t)
    with db.connect() as conn:
        count = conn.execute("UPDATE knowledge_contributions SET status=?,payload=?,reviewer=?,decided=?,decision_note=? WHERE id=? AND status='pending'", (status, json.dumps(payload, ensure_ascii=False), reviewer, now(), note, row['id'])).rowcount
        if count != 1:
            raise edits.Conflict('This contribution already has a decision')
    return dict(id=row['id'], status=status)
