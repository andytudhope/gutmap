"""Targeted suggestions, moderator decisions and durable published text overlays."""
import hashlib,hmac,json,os,secrets,time
from urllib.parse import urlsplit
from .db import connect

COOKIE='gutmap_editor'
TEXT_KEYS={'title','name','lead','tagline','role','habitat','question','caption','description','definition','text','finding','meaning','practical','label','summary_intro','niche','imbalance','support','selection_note','intro','next','response','answer','limitations'}
TEXT_LISTS={'summary','paragraphs','tags','connections'}

def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS edit_suggestions(
      id INTEGER PRIMARY KEY, created TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
      CHECK(status IN ('pending','accepted','rejected')),
      page TEXT NOT NULL, anchor TEXT NOT NULL, selected TEXT NOT NULL, suggestion TEXT NOT NULL,
      name TEXT NOT NULL DEFAULT '', occupation TEXT NOT NULL DEFAULT '', affiliation TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
      kind TEXT NOT NULL DEFAULT 'text', paper_id TEXT REFERENCES papers(id), proposal TEXT NOT NULL DEFAULT '{}',
      target TEXT NOT NULL, replacement TEXT NOT NULL DEFAULT '', published TEXT NOT NULL DEFAULT '',
      decided TEXT, decision_note TEXT NOT NULL DEFAULT ''
    );''')

def revision():
    with connect() as db:return db.execute("SELECT COUNT(*) FROM edit_suggestions WHERE status='accepted'").fetchone()[0]

def published():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id,page,anchor,target,published,replacement,kind,paper_id FROM edit_suggestions WHERE status='accepted' ORDER BY decided,id")]

def project(name,data):
    rows=published()
    if not rows:return data
    data=json.loads(json.dumps(data))
    prefix='content:'+name+':'
    for row in rows:
        if name=='evidence' and row['kind']=='reading-note':
            value=json.loads(row['published']);slug=next((k for k,v in data.items() if v['paper']==row['paper_id']),'contributed-'+hashlib.sha256(row['paper_id'].encode()).hexdigest()[:16]);data[slug]=value
            continue
        if not row['target'].startswith(prefix):continue
        keys=json.loads(row['target'][len(prefix):]);node=data
        try:
            for key in keys[:-1]:node=node[key]
            if node[keys[-1]]==json.loads(row['anchor'])['context']:node[keys[-1]]=row['published']
        except (KeyError,IndexError,TypeError):pass
    return data

def paper(data,rows=None):
    prefix='paper:'+data['id']+':'
    for row in published() if rows is None else rows:
        if row['target'].startswith(prefix):
            field=row['target'][len(prefix):]
            if data.get(field)==json.loads(row['anchor'])['context']:data[field]=row['published']
    return data

def leaves(node,path=()):
    if isinstance(node,dict):
        for k,v in node.items():yield from leaves(v,path+(k,))
    elif isinstance(node,list):
        for i,v in enumerate(node):yield from leaves(v,path+(i,))
    elif isinstance(node,str) and path and (path[-1] in TEXT_KEYS or len(path)>1 and path[-2] in TEXT_LISTS):yield path,node

def source_target(context):
    from . import editorial
    matches=[]
    for name in ['anatomy','pathways','exploration','conditions','evidence','mechanisms','references','microbes']:
        for path,text in leaves(editorial.read(name)):
            if text==context:matches.append('content:'+name+':'+json.dumps(path,separators=(',',':')))
    if not matches:
        for name in ['concepts','knowledge','topics']:
            for path,text in leaves(editorial.read(name)):
                if text==context:matches.append('content:'+name+':'+json.dumps(path,separators=(',',':')))
    with connect() as db:
        for field in ['title','authors','journal']:
            matches += ['paper:'+r['id']+':'+field for r in db.execute('SELECT id FROM papers WHERE '+field+'=? LIMIT 2',(context,))]
    for row in published():
        if row['target'].startswith('paper:') and row['published']==context and current(row['target'])==context:matches.append(row['target'])
    matches=list(dict.fromkeys(matches))
    return matches[0] if len(matches)==1 else None

def current(target):
    if target.startswith('note:'):return note_snapshot(target[5:])
    if target.startswith('content:'):
        from .editorial import read
        _,name,keys=target.split(':',2);node=read(name)
        for k in json.loads(keys):node=node[k]
        return node
    if target.startswith('paper:'):
        pid,field=target[6:].rsplit(':',1)
        with connect() as db:
            row=db.execute('SELECT id,title,authors,journal FROM papers WHERE id=?',(pid,)).fetchone()
        return paper(dict(row))[field] if row else None
    with connect() as db:
        row=db.execute("SELECT published FROM edit_suggestions WHERE target=? AND status='accepted' ORDER BY decided DESC,id DESC LIMIT 1",(target,)).fetchone()
    return row['published'] if row else None

def text(value,limit,required=False):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):raise ValueError('Invalid or missing text')
    return value

def submit(data):
    if data.get('website'):raise ValueError('Invalid submission')
    page=text(data.get('page'),2000,True)
    path=urlsplit(page).path
    if '\\' in page or any(ord(c)<32 for c in page) or (path not in ('/','/explore','/explore','/research','/papers','/mechanisms','/references','/living-well','/fermentation','/illness-recovery') and not path.startswith(('/topics/','/concepts/','/claims/','/findings/','/guides/','/condition/'))):raise ValueError('Invalid page')
    anchor=data.get('anchor')
    if not isinstance(anchor,dict):raise ValueError('Missing text target')
    anchor={k:text(anchor.get(k),12000 if k in ('context','before','after') else 2000,k in ('context','selector')) for k in ('context','before','after','selector')}
    selected=text(data.get('selected'),6000,True)
    if anchor['before']+selected+anchor['after']!=anchor['context']:raise ValueError('Selection does not match its context')
    target=source_target(anchor['context']) or 'dom:'+hashlib.sha256((page+'\n'+anchor['selector']).encode()).hexdigest()
    fields=[text(data.get(k,''),n) for k,n in [('name',200),('occupation',300),('affiliation',400),('email',320)]]
    suggestion=text(data.get('suggestion'),12000,True)
    paper_id=None
    if target.startswith('content:evidence:'):
        from .editorial import read
        paper_id=read('evidence')[json.loads(target.split(':',2)[2])[0]]['paper']
    elif target.startswith('paper:'):paper_id=target[6:].rsplit(':',1)[0]
    with connect() as db:
        ident=db.execute('INSERT INTO edit_suggestions(created,page,anchor,selected,suggestion,name,occupation,affiliation,email,target,paper_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)',(str(time.time_ns()),page,json.dumps(anchor,ensure_ascii=False),selected,suggestion,*fields,target,paper_id)).lastrowid
    return {'id':ident}

def queue(status,offset=0):
    if status not in ('pending','accepted','rejected'):raise ValueError('Unknown status')
    with connect() as db:
        offset=max(0,offset)
        rows=[dict(r) for r in db.execute('SELECT * FROM edit_suggestions WHERE status=? ORDER BY created DESC LIMIT 50 OFFSET ?',(status,offset))]
        return {'items':rows,'total':db.execute('SELECT COUNT(*) FROM edit_suggestions WHERE status=?',(status,)).fetchone()[0],'offset':offset}

def decide(ident,data):
    status=data.get('status')
    if status not in ('accepted','rejected'):raise ValueError('Choose accept or reject')
    with connect() as db:row=db.execute('SELECT * FROM edit_suggestions WHERE id=?',(ident,)).fetchone()
    if not row:raise ValueError('Suggestion not found')
    if row['status']!='pending':raise Conflict('This suggestion already has a decision')
    if row['kind']=='reading-note':return decide_note(row,data)
    replacement=text(data.get('replacement',''),12000,status=='accepted')
    note=text(data.get('decision_note',''),2000)
    anchor=json.loads(row['anchor']);live=current(row['target'])
    if status=='accepted' and live is not None and live!=anchor['context']:raise Conflict('The text has changed since this suggestion was submitted. Select the current text to propose a new change.')
    result=anchor['before']+replacement+anchor['after'] if status=='accepted' else ''
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        # Guard both duplicate decisions and simultaneous changes to the same target.
        latest=db.execute("SELECT published FROM edit_suggestions WHERE target=? AND status='accepted' ORDER BY decided DESC,id DESC LIMIT 1",(row['target'],)).fetchone()
        if status=='accepted' and latest and latest['published']!=anchor['context']:raise Conflict('Another edit changed this text')
        count=db.execute("UPDATE edit_suggestions SET status=?,replacement=?,published=?,decided=?,decision_note=? WHERE id=? AND status='pending'",(status,replacement,result,str(time.time_ns()),note,ident)).rowcount
        if count!=1:raise Conflict('This suggestion already has a decision')
    return {'id':ident,'status':status}

class Conflict(Exception):pass

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),310000).hex()

def configured():return bool(os.environ.get('HUB_EDIT_PASSWORD_HASH'))

def login(password):
    stored=os.environ.get('HUB_EDIT_PASSWORD_HASH','')
    if not stored or not hmac.compare_digest(password_hash(password,stored.split(':')[0]),stored):return None
    expiry=str(int(time.time())+8*3600)
    signature=hmac.new(stored.encode(),expiry.encode(),hashlib.sha256).hexdigest()
    return expiry+'.'+signature

def authenticated(cookie):
    from http.cookies import SimpleCookie,CookieError
    try:
        token=SimpleCookie(cookie or '')[COOKIE].value;expiry,signature=token.split('.')
        stored=os.environ.get('HUB_EDIT_PASSWORD_HASH','')
        return bool(stored) and int(expiry)>time.time() and hmac.compare_digest(signature,hmac.new(stored.encode(),expiry.encode(),hashlib.sha256).hexdigest())
    except (KeyError,ValueError,CookieError):return False


NOTE_FIELDS=('kind','population','finding','meaning','question','regions','review_basis','catalogue_records')

def note_snapshot(pid):
    from .editorial import read
    note=next((n for n in read('evidence').values() if n['paper']==pid),None)
    return {k:note.get(k,[] if k in ('regions','catalogue_records') else '') for k in NOTE_FIELDS} if note else None

def note_record(pid):
    with connect() as db:row=db.execute('SELECT id,title,year,doi,url FROM papers WHERE id=?',(pid,)).fetchone()
    if not row:raise ValueError('Choose a paper from the research library')
    base=note_snapshot(pid)
    return {'paper':paper(dict(row)),'note':base,'base_revision':hashlib.sha256(json.dumps(base,sort_keys=True).encode()).hexdigest()}

def note_fields(data):
    if not isinstance(data,dict):raise ValueError('Missing reading note')
    fields={k:text(data.get(k,''),6000 if k in ('finding','meaning','question') else 400,True) for k in NOTE_FIELDS if k not in ('regions','catalogue_records')}
    regions=data.get('regions')
    if not isinstance(regions,list) or not regions or len(regions)>7 or any(r not in ('mouth','oesophagus','stomach','small','colon','rectum','unspecified') for r in regions):raise ValueError('Choose the relevant gut regions')
    records=data.get('catalogue_records',[])
    if not isinstance(records,list) or len(records)>12 or any(not isinstance(r,str) or len(r)>200 for r in records):raise ValueError('Use up to 12 catalogue record IDs')
    from .microbes import descriptor
    if any(not descriptor(r) for r in records):raise ValueError('A catalogue record ID was not found')
    fields['catalogue_records']=list(dict.fromkeys(records))
    fields['regions']=list(dict.fromkeys(regions))
    return fields

def submit_note(data):
    if data.get('website'):raise ValueError('Invalid submission')
    pid=text(data.get('paper_id'),200,True);record=note_record(pid)
    if data.get('base_revision')!=record['base_revision']:raise Conflict('This reading note has changed. Reopen it to suggest changes to the current version.')
    proposal=note_fields(data.get('reading_note'))
    contacts=[text(data.get(k,''),n) for k,n in [('name',200),('occupation',300),('affiliation',400),('email',320)]]
    guidance=text(data.get('suggestion',''),12000)
    with connect() as db:
        ident=db.execute("INSERT INTO edit_suggestions(created,page,anchor,selected,suggestion,name,occupation,affiliation,email,target,kind,paper_id,proposal) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(str(time.time_ns()),'/research?paper='+pid,json.dumps({'base':record['note']},ensure_ascii=False),record['paper']['title'],guidance,*contacts,'note:'+pid,'reading-note',pid,json.dumps(proposal,ensure_ascii=False))).lastrowid
    return {'id':ident}

def decide_note(row,data):
    status=data['status'];review=text(data.get('decision_note',''),2000)
    expected=revision()
    if status=='accepted':
        base=json.loads(row['anchor'])['base']
        if note_snapshot(row['paper_id'])!=base:raise Conflict('This reading note has changed since the suggestion was submitted')
        from .editorial import read
        prior=next((n for n in read('evidence').values() if n['paper']==row['paper_id']),{})
        value={**prior,**note_fields(data.get('reading_note'))}
        from datetime import datetime,timezone
        value.update(paper=row['paper_id'],author='Community contribution',reviewed=datetime.now(timezone.utc).date().isoformat())
        result=json.dumps(value,ensure_ascii=False)
    else:result=''
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT COUNT(*) FROM edit_suggestions WHERE status='accepted'").fetchone()[0]!=expected:raise Conflict('Another edit was just published. Reload the review queue.')
        count=db.execute("UPDATE edit_suggestions SET status=?,replacement=?,published=?,decided=?,decision_note=? WHERE id=? AND status='pending'",(status,'',result,str(time.time_ns()),review,row['id'])).rowcount
        if count!=1:raise Conflict('This suggestion already has a decision')
    return {'id':row['id'],'status':status}

if __name__=='__main__':
    from getpass import getpass
    print('HUB_EDIT_PASSWORD_HASH='+password_hash(getpass('Review password: ')))
