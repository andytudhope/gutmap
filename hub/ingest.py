"""Bounded-memory metadata ingestion. Never downloads or stores paper full text."""
import argparse
import fcntl
import html
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .vocabulary import TOPICS
from .db import DB_PATH, connect, initialize, set_state, state

API = 'https://www.ebi.ac.uk/europepmc/webservices/rest/'
QUERY = '((TITLE_ABS:"gut microbiome" OR TITLE_ABS:"gut microbiota" OR TITLE_ABS:"intestinal microbiota" OR TITLE_ABS:"intestinal microbiome" OR TITLE_ABS:"gastrointestinal microbiome") AND (SRC:MED OR SRC:PPR))'
FASTING_QUERY = '((TITLE_ABS:"intermittent fasting" OR TITLE_ABS:"time-restricted eating" OR TITLE_ABS:"time restricted eating" OR TITLE_ABS:"time-restricted feeding" OR TITLE_ABS:"time restricted feeding" OR TITLE_ABS:"Ramadan" OR TITLE_ABS:"fasting-mimicking" OR TITLE_ABS:"fasting mimicking" OR TITLE_ABS:"alternate-day fasting" OR TITLE_ABS:"prolonged fasting" OR TITLE_ABS:"water-only fasting" OR TITLE:fasting) AND (TITLE_ABS:microbiome OR TITLE_ABS:microbiota) AND (SRC:MED OR SRC:PPR))'
QUERY = '(' + QUERY + ' OR ' + FASTING_QUERY + ')'

TAXA = {'Bifidobacterium':['bifidobacter'], 'Lactobacillus':['lactobacill','lacticaseibacill'], 'Akkermansia':['akkermansia'], 'Faecalibacterium':['faecalibacter'], 'Roseburia':['roseburia'], 'Bacteroides':['bacteroides'], 'Archaea':['methan','archaea'], 'Viruses & phages':['bacteriophag','virome','viral'], 'Fungi':['fung','mycobiom','candida']}
FUNCTIONS = {'Fermentation':['ferment','fiber','fibre'], 'Immune signalling':['immun','inflamm'], 'Gut–brain signalling':['gut-brain','gut brain','neuro','depress','anxiety'], 'Metabolites':['metabol','butyrate','bile acid','short-chain'], 'Transit':['transit','motility','constipat'], 'Barrier function':['barrier','permeability','mucin']}
REGION_WORDS = {'stomach':['gastric','stomach','helicobacter'], 'small':['small intestin','duoden','jejunu','ileal','ileum'], 'colon':['colon','colonic','colorectal'], 'rectum':['rectal','rectum']}
TAXA.update({'Streptococcus':['streptococc'], 'Veillonella':['veillonella'], 'Helicobacter':['helicobacter'],
 'Candida':['candida'], 'Saccharomyces':['saccharomyces'], 'Malassezia':['malassezia'],
 'Protists':['protist','blastocystis','dientamoeba','giardia','cryptosporid','entamoeba'],
 'Blastocystis':['blastocystis'], 'Dientamoeba':['dientamoeba'], 'Giardia':['giardia'],
 'Cryptosporidium':['cryptosporid'], 'Entamoeba':['entamoeba']})
REGION_WORDS.update({'mouth':['oral microbi','dental','tongue','saliva','plaque','mouth'],
 'oesophagus':['esophag','oesophag']})
FUNCTIONS.update({'Microbial partnerships':['cross-feeding','cross feeding','coculture','co-culture'],
 'Acid chemistry':['urease','nitrite','nitric oxide','plaque ph'],
 'Phage–host interactions':['bacteriophag','prophage','phage-host'],
 'Treatment & resistance':['eradication','antibiotic resistance','antimicrobial resistance']})
LOG = logging.getLogger('ingest')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def fetch(path, params=None):
    url = API + path + ('?' + urlencode(params) if params else '')
    for attempt in range(3):
        try:
            req = Request(url, headers={'User-Agent':'GutAtlas/1.0 (open-source metadata index)','Accept':'application/json'})
            with urlopen(req, timeout=40) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def clean(value):
    text=value or ''
    for _ in range(2):text=html.unescape(text)
    supermap=str.maketrans('0123456789+-=()inABDEGHIJKLMNOPRTUVW','⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁱⁿᴬᴮᴰᴱᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᴿᵀᵁⱽᵂ')
    submap=str.maketrans('0123456789+-=()','₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎')
    text=re.sub(r'<sup[^>]*>(.*?)</sup>',lambda m:re.sub('<[^>]+>','',m[1]).translate(supermap),text,flags=re.I)
    text=re.sub(r'<sub[^>]*>(.*?)</sub>',lambda m:re.sub('<[^>]+>','',m[1]).translate(submap),text,flags=re.I)
    return ' '.join(re.sub('<[^>]+>','',text).split())


def classify(record):
    text = (clean(record.get('title','')) + ' ' + clean(record.get('abstractText',''))).lower()
    topics = [t['id'] for t in TOPICS if any(k in text for k in t['keywords'])]
    if 'fasting' not in topics and re.search(r'\bfasting\b',clean(record.get('title','')).lower()) and not re.search(r'fasting (blood |plasma |serum )?(glucose|insulin|lipid)',clean(record.get('title','')).lower()):topics.append('fasting')
    taxa = [label for label, words in TAXA.items() if any(w in text for w in words)]
    functions = [label for label, words in FUNCTIONS.items() if any(w in text for w in words)]
    regions = [label for label, words in REGION_WORDS.items() if any(w in text for w in words)]
    if not regions:
        regions = ['unspecified']
    types = ' '.join(record.get('pubTypeList',{}).get('pubType',[])).lower()
    if 'meta-analysis' in types or 'systematic review' in types or 'systematic review' in text[:250]:
        kind = 'Evidence synthesis'
    elif 'randomized controlled trial' in types:
        kind = 'Randomised trial'
    elif 'clinical trial' in types:
        kind = 'Clinical trial'
    elif 'review' in types:
        kind = 'Review'
    elif record.get('source') == 'PPR' or 'preprint' in types:
        kind = 'Preprint'
    elif re.search(r'\b(mice|murine|mouse model|germ-free mouse|rat model)\b', text):
        kind = 'Animal / preclinical'
    else:
        kind = 'Research article'
    return topics, taxa, functions, regions, kind


def upsert(db, r, extra_topic=None):
    if not r.get('title'):
        return False
    source = r.get('source','MED')
    ident = str(r.get('id',''))
    if not ident:
        return False
    pid = source + ':' + ident
    doi = (r.get('doi') or '').lower().strip()
    duplicate = db.execute('SELECT id FROM papers WHERE doi=?', (doi,)).fetchone() if doi else None
    if duplicate:
        pid = duplicate['id']
        if source == 'PPR' and pid.startswith('MED:'):
            return True
    topics, taxa, functions, regions, kind = classify(r)
    if extra_topic and extra_topic not in topics:
        topics.append(extra_topic)
    pmcid = r.get('pmcid')
    pmid = ident if source == 'MED' else None
    access, url = 'DOI / publisher', 'https://doi.org/' + doi if doi else 'https://europepmc.org/article/' + source + '/' + ident
    links = r.get('fullTextUrlList',{}).get('fullTextUrl',[])
    free_links = sorted([l for l in links if l.get('availabilityCode') in ('OA','F') and l.get('url','').startswith('https://')], key=lambda l: l.get('documentStyle') != 'html')
    if pmcid:
        access, url = 'Free to read', 'https://europepmc.org/articles/' + pmcid
    elif free_links:
        access, url = 'Free to read', free_links[0]['url']
    timestamp = now()
    journal = r.get('journalInfo',{}).get('journal',{}).get('title') or r.get('journalTitle','')
    published = r.get('firstPublicationDate') or str(r.get('pubYear',''))
    values = (pid,pmid,pmcid,doi,clean(r['title']),clean(r.get('authorString',''))[:1200],journal,int(r.get('pubYear') or 0),published,url,access,kind,json.dumps(topics),json.dumps(taxa),json.dumps(regions),json.dumps(functions),int('retracted publication' in ' '.join(r.get('pubTypeList',{}).get('pubType',[])).lower()),timestamp,timestamp)
    db.execute('''INSERT INTO papers (id,pmid,pmcid,doi,title,authors,journal,year,published,url,access,study_type,topics,taxa,regions,functions,retracted,added,updated)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET title=excluded.title,authors=excluded.authors,journal=excluded.journal,
      pmid=coalesce(excluded.pmid,papers.pmid),pmcid=coalesce(excluded.pmcid,papers.pmcid),
      url=excluded.url,access=excluded.access,study_type=excluded.study_type,topics=excluded.topics,
      taxa=excluded.taxa,regions=excluded.regions,functions=excluded.functions,retracted=excluded.retracted,updated=excluded.updated''', values)
    return True


def search_into(db, query, max_pages=100, topic=None):
    cursor, count = '*', 0
    for _ in range(max_pages):
        data = fetch('search',dict(query=query,format='json',resultType='core',pageSize=100,cursorMark=cursor))
        results = data.get('resultList',{}).get('result',[])
        for r in results:
            count += bool(upsert(db,r,topic))
        db.commit()
        LOG.info('Indexed %s metadata records', count)
        next_cursor = data.get('nextCursorMark')
        if not results or not next_cursor or next_cursor == cursor:
            return count, True
        cursor = next_cursor
    return count, False


def link_references(db, budget=150):
    papers = db.execute('SELECT id,pmid FROM papers WHERE refs_checked=0 AND pmid IS NOT NULL ORDER BY EXISTS(SELECT 1 FROM citations c WHERE c.source=papers.id OR c.target=papers.id),added LIMIT ?', (budget,)).fetchall()
    for p in papers:
        try:
            page = 1
            while True:
                data = fetch('MED/' + p['pmid'] + '/references',dict(format='json',pageSize=1000,page=page))
                refs = data.get('referenceList',{}).get('reference',[])
                for ref in refs:
                    refid = str(ref.get('id',''))
                    if refid and ref.get('source') == 'MED':
                        db.execute('INSERT OR IGNORE INTO references_pending VALUES (?,?)',(p['id'],refid))
                if len(refs) < 1000:
                    break
                page += 1
            db.execute('UPDATE papers SET refs_checked=1 WHERE id=?',(p['id'],))
            db.commit()
            time.sleep(.08)
        except Exception as e:
            LOG.warning('Reference lookup deferred for %s: %s', p['id'], type(e).__name__)
    db.execute('''INSERT OR IGNORE INTO citations SELECT r.source,p.id FROM references_pending r JOIN papers p ON p.pmid=r.target_pmid WHERE r.source != p.id''')
    db.execute('''DELETE FROM references_pending WHERE EXISTS (SELECT 1 FROM papers p WHERE p.pmid=target_pmid)''')
    db.commit()


def expand_corpus(db,budget=300,forward=15):
    """Resolve relevant references and citing work; discovery never creates reading notes."""
    if budget<=0:return 0
    ref_cursor=state(db,'reference_discovery_cursor','')
    ids=[r[0] for r in db.execute('SELECT DISTINCT target_pmid FROM references_pending WHERE target_pmid>? ORDER BY target_pmid LIMIT ?',(ref_cursor,budget))]
    if not ids and budget:
        ids=[r[0] for r in db.execute('SELECT DISTINCT target_pmid FROM references_pending ORDER BY target_pmid LIMIT ?',(budget,))]
    if ids:set_state(db,'reference_discovery_cursor',ids[-1])
    candidates=set(ids);forward_edges=[]
    cursor=state(db,'citation_cursor','')
    isolates=db.execute("SELECT id,pmid FROM papers p WHERE pmid IS NOT NULL AND id>? AND NOT EXISTS(SELECT 1 FROM citations c WHERE c.source=p.id OR c.target=p.id) ORDER BY id LIMIT ?",(cursor,forward)).fetchall()
    if not isolates and forward:
        set_state(db,'citation_cursor','');db.commit()
    for p in isolates:
        LOG.info('Checking citing papers for %s',p['id'])
        try:
            data=fetch('MED/'+p['pmid']+'/citations',dict(format='json',pageSize=100,page=1))
            for c in data.get('citationList',{}).get('citation',[]):
                if c.get('source')=='MED' and c.get('id'):
                    candidates.add(str(c['id']));forward_edges.append((str(c['id']),p['id']))
            set_state(db,'citation_cursor',p['id']);db.commit()
        except Exception as e:LOG.warning('Citing-paper lookup deferred for %s: %s',p['id'],type(e).__name__)
    imported=0
    ordered=sorted(candidates)
    for start in range(0,len(ordered),75):
        group=ordered[start:start+75]
        data=fetch('search',dict(query=QUERY+' AND SRC:MED AND EXT_ID:('+ ' OR '.join(group)+')',format='json',resultType='core',pageSize=100))
        for record in data.get('resultList',{}).get('result',[]):imported+=bool(upsert(db,record))
        db.commit()
    db.execute("INSERT OR IGNORE INTO citations SELECT r.source,p.id FROM references_pending r JOIN papers p ON p.pmid=r.target_pmid WHERE r.source!=p.id")
    db.execute("DELETE FROM references_pending WHERE EXISTS(SELECT 1 FROM papers p WHERE p.pmid=target_pmid)")
    for source,target in forward_edges:
        db.execute('INSERT OR IGNORE INTO citations SELECT id,? FROM papers WHERE pmid=? AND id!=?',(target,source,target))
    db.commit();LOG.info('Citation discovery: %s relevant records processed',imported)
    return imported


def seed(db):
    # Source records resolve the editorial reading list; never invent paper metadata.
    from .editorial import read
    from scripts.sync_editorial import resolve
    for note in read('evidence').values():
        record=resolve(note['paper'])
        if record:upsert(db,record)
    pmids = ['21286935','36145079','34304786','26460205']
    search_into(db,'EXT_ID:(' + ' OR '.join(pmids) + ') AND SRC:MED',max_pages=1)
    for t in TOPICS:
        # A small historical seed, followed by the rolling literature search.
        phrase = t['keywords'][0].replace('constipat','constipation').replace('bloat','bloating').replace('immun','immune').replace('bifidobacter','bifidobacterium').replace('methan','methane').replace('metaboli','metabolic').replace('diarrh','diarrhea')
        q = QUERY + ' AND TITLE_ABS:"' + phrase + '" sort_cited:y'
        data = fetch('search',dict(query=q,format='json',resultType='core',pageSize=20))
        for r in data.get('resultList',{}).get('result',[]):
            upsert(db,r,t['id'])
        db.commit()
    set_state(db,'seeded',now())
    db.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed',action='store_true')
    parser.add_argument('--force',action='store_true')
    parser.add_argument('--references',type=int,default=1000)
    parser.add_argument('--expand',type=int,default=300)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    initialize()
    with open(str(DB_PATH)+'.ingest.lock','w') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            LOG.info('Another ingestion is running')
            return
        with connect() as db:
            last = state(db,'last_success')
            if last and not args.force and not args.seed and (datetime.now(timezone.utc)-datetime.fromisoformat(last)).total_seconds() < 96*3600:
                LOG.info('Next update is due 96 hours after %s',last)
                return
            if DB_PATH.stat().st_size > 250*1024*1024:
                raise RuntimeError('Metadata database reached 250 MiB soft ceiling; review capacity before importing more')
            run_id = db.execute('INSERT INTO runs(started,status) VALUES (?,?)',(now(),'running')).lastrowid
            db.commit()
            try:
                if args.seed and not state(db,'seeded'):
                    seed(db)
                # FIRST_IDATE catches newly indexed older papers. UPDATE_DATE catches corrections.
                start = (datetime.fromisoformat(last)-timedelta(days=7)).date().isoformat() if last else (datetime.now(timezone.utc)-timedelta(days=30)).date().isoformat()
                end = datetime.now(timezone.utc).date().isoformat()
                q = QUERY + f' AND (FIRST_IDATE:[{start} TO {end}] OR UPDATE_DATE:[{start} TO {end}])'
                count, complete = search_into(db,q)
                link_references(db,args.references)
                expand_corpus(db,args.expand)
                if not complete:
                    raise RuntimeError('Page budget reached; checkpoint retained for a complete retry')
                stamp = now()
                set_state(db,'last_success',stamp)
                set_state(db,'query',q)
                db.execute('UPDATE runs SET finished=?,status=?,discovered=? WHERE id=?',(stamp,'success',count,run_id))
                db.execute('DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY id DESC LIMIT 100)')
                db.commit()
                db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                LOG.info('Complete: %s records processed',count)
            except Exception as e:
                db.execute('UPDATE runs SET finished=?,status=?,message=? WHERE id=?',(now(),'failed',str(e)[:500],run_id))
                db.commit()
                raise

if __name__ == '__main__':
    main()
