"""Import catalogue metadata only; sequences and alignments stay at their sources.

Downloaded inputs are cached under /tmp, outside the site and database.
"""
import argparse,csv,hashlib,io,json,re,sys,time,urllib.request
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from hub.db import connect,initialize,encode_metadata
CACHE=Path('/tmp/gut-catalogue-inputs')
URLS={
 'uhgv.tsv':'https://portal.nersc.gov/UHGV/metadata/votus_metadata.tsv',
 'uhgv-genomes.tsv':'https://portal.nersc.gov/UHGV/metadata/uhgv_metadata.tsv',
 'eukprot.tsv':'https://ndownloader.figshare.com/files/34436246',
 'preprint.csv':'https://www.biorxiv.org/content/early/2026/06/25/2026.06.24.734308/DC2/embed/media-2.csv?download=true',
 'euk-clusters.csv':'https://www.biorxiv.org/content/early/2026/06/25/2026.06.24.734308/DC3/embed/media-3.csv?download=true',
 'blastodb.html':'https://blastodb.com/datasets/'
}
def compact(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'))
def obtain(name):
 CACHE.mkdir(exist_ok=True);path=CACHE/name
 if path.exists() and path.stat().st_size>0:return path
 temp=path.with_suffix(path.suffix+'.part')
 with urllib.request.urlopen(urllib.request.Request(URLS[name],headers={'User-Agent':'GutAtlas-metadata/1.0'}),timeout=90) as r,temp.open('wb') as out:
  while chunk:=r.read(1048576):out.write(chunk)
 temp.replace(path);return path

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def source(db,id,name,url,path,version,description):
 db.execute('INSERT INTO catalogue_sources VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,metadata_url=excluded.metadata_url,sha256=excluded.sha256,imported=excluded.imported,description=excluded.description',(id,name,version,url,URLS[path.name],digest(path),datetime.now(timezone.utc).isoformat(timespec='seconds'),description))
def put(db,id,src,entity,name,kind,branch,host='',gut='reference',**attrs):
 for key,prefix in [('giardia','giardia intestinalis'),('giardia','giardia duodenalis'),('giardia','giardia lamblia'),('saccharomyces','saccharomyces cerevisiae'),('rhizopus','rhizopus microsporus'),('aspergillus','aspergillus oryzae')]:
  if name.lower().startswith(prefix):entity=key
 db.execute('INSERT INTO catalogue_records(id,source,entity_id,name,kind,branch,host,gut,attributes) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET entity_id=excluded.entity_id,name=excluded.name,branch=excluded.branch,host=excluded.host,gut=excluded.gut,attributes=excluded.attributes',(id,src,entity,name,kind,branch,host,gut,encode_metadata(attrs)))
def clean(v):return '' if v in ('NULL','NA','N/A',None) else v

def uhgv(db):
 p=obtain('uhgv.tsv');rows=csv.DictReader(p.open(),delimiter='\t');count=0
 source(db,'uhgv','Unified Human Gut Virome','https://github.com/snayfach/UHGV',p,'species clusters / retrieved 2026-10-20','Human gut viral clusters; bacterial hosts and lifestyles are computational predictions.')
 for r in rows:
  tax=clean(r['ictv_taxonomy']).split(';');hostline=clean(r['host_lineage']);host=next((s[3:] for s in reversed(hostline.split(';')) if s.startswith(('g__','f__','o__','c__','p__','d__'))),'')
  branch=tax[5] if len(tax)>5 else tax[-1] if tax[0] else r['uhgv_taxonomy'].split(';')[0]
  id='uhgv:'+r['uhgv_votu'];put(db,id,'uhgv',id,r['uhgv_votu'],'viruses',branch,host,'gut-derived',representative=r['uhgv_genome'],length=int(r['genome_length']),genes=int(r['cds_count']),quality=r['checkv_quality'],completeness=clean(r['checkv_completeness']),taxonomy=clean(r['ictv_taxonomy']),cluster_taxonomy=r['uhgv_taxonomy'],host_lineage=hostline,lifestyle=clean(r['lifestyle']),hyperprevalent=r['hyperprevalent']=='Yes',url=r['http_url'],paper='10.1101/2025.11.01.686033')
  count+=1
 assert count==168536,count
 print('UHGV:',count,'species clusters',flush=True)
 p=obtain('uhgv-genomes.tsv');source(db,'gpd','Gut Phage Database','https://www.sanger.ac.uk/data/gut-phage-database/',p,'UHGV source crosswalk','GPD original genome identifiers mapped to UHGV clusters.');source(db,'mgv','Metagenomic Gut Virus catalogue','https://portal.nersc.gov/MGV/',p,'UHGV source crosswalk','MGV original genome identifiers mapped to UHGV clusters.')
 counts=Counter()
 for r in csv.DictReader(p.open(),delimiter='\t'):
  src=r['original_study_alias'].lower()
  if src not in ('gpd','mgv'):continue
  db.execute('INSERT OR IGNORE INTO catalogue_crosswalk SELECT ?,?,key FROM catalogue_records WHERE id=?',(src,r['original_id'],'uhgv:'+r['uhgv_votu']));counts[src]+=1
 print('Original identifier crosswalks:',dict(counts),flush=True)
 assert counts['gpd']>100000 and counts['mgv']>100000,counts


def normalized(name):return re.sub(r'[^a-z0-9]+',' ',name.lower()).strip()
def eukaryotes(db):
 p=obtain('preprint.csv');rows=list(csv.DictReader(p.open(encoding='utf-8-sig')));assert len([r for r in rows if r['Group']=='Protist'])==989
 source(db,'eukdetect2','EukDetect2','https://github.com/allind/EukDetect',p,'2026 preprint / Table S1','Broad microbial eukaryote reference. Catalogue membership is separate from detection in human gut samples.')
 clusters={r['Representative genome'].rstrip('_'):r for r in csv.DictReader(obtain('euk-clusters.csv').open(encoding='utf-8-sig')) if r.get('Cluster','').startswith('Cluster_')}
 lookup={}
 observed={'Blastocystis':'Blastocystis detected in public human-gut cohorts analysed in the EukDetect2 preprint.','Dientamoeba':'Dientamoeba detected in human-gut cohorts analysed in the EukDetect2 preprint.','Entamoeba':'Entamoeba detected in human-gut cohorts analysed in the EukDetect2 preprint.'}
 for r in rows:
  name=r['Genome'].replace('_',' ');genus=name.split()[0];taxid=r['Species taxonomy ID'];entity='ncbi:'+taxid;lookup.setdefault(normalized(' '.join(name.split()[:2])),entity)
  kind='fungi' if r['Group']=='Fungi' else 'protists';gut='cohort-lineage' if genus in observed else 'reference'
  put(db,'eukdetect2:'+r['Genome'],'eukdetect2',entity,name,kind,genus,gut=gut,cluster=clusters.get(r['Genome'].rstrip('_'),{}).get('Cluster',''),cluster_size=clusters.get(r['Genome'].rstrip('_'),{}).get('Cluster size',''),taxid=taxid,genome=r['Genome'],sequence_source=r['Source'],previous_database=r['Present in EukDetect version 1']=='TRUE',url='https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id='+taxid,paper='10.64898/2026.06.24.734308',observation=observed.get(genus,''),observation_scope='Genus-level cohort observation; not a strain-level prevalence estimate' if genus in observed else '')
 print('EukDetect2:',Counter(r['Group'] for r in rows),'(published table counts)',flush=True)
 p=obtain('eukprot.tsv');source(db,'eukprot','EukProt','https://evocellbio.com/eukprot/',p,'v3 / 2021-11-22 / published 2022','Genome and transcriptome metadata across eukaryotic diversity. Includes lineages outside human gut habitats.')
 n=0
 for r in csv.DictReader(p.open(),delimiter='\t'):
  name=r['Name_to_Use'].replace('_',' ');eid=lookup.get(normalized(' '.join(name.split()[:2])),'eukprot:'+r['EukProt_ID']);tax=r['Taxonomy_UniEuk'];kind='fungi' if 'Fungi' in tax else 'eukaryotes' if any(t in tax for t in ['Metazoa;','Embryophyta;']) else 'protists'
  put(db,'eukprot:'+r['EukProt_ID'],'eukprot',eid,name,kind,r['Supergroup_UniEuk'],gut='reference',strain=r['Strain'],taxonomy=tax,data_type=r['Data_Source_Type'],previous_names=r['Previous_Names'],genus=r['Genus_UniEuk'],url=clean(r['Data_Source_URL']),dataset=r['Data_Source_Name'],paper=r['Paper_DOI'].split(';')[0],catalogue_paper='10.24072/pcjournal.173',rrna_accession=r['18S_Sequence_GenBank_ID'])
  n+=1
 assert n==993,n
 print('EukProt:',n,'datasets',flush=True)

def blasto(db):
 p=obtain('blastodb.html');s=p.read_text();start=s.index('window.collectorData = ')+len('window.collectorData = ');d,_=json.JSONDecoder().raw_decode(s[start:])
 source(db,'blastodb','BlastoDB','https://blastodb.com/',p,'retrieved 2026-10-20','Subtype and sequence-reference metadata from the Blastocystis community resource.')
 for item in d['subtypes']:
  r=item['data'];name=r.get('name') or item['slug'];put(db,'blastodb:'+item['slug'],'blastodb','ncbi:12968','Blastocystis '+name,'protists','Blastocystis',host=', '.join(r.get('sources',[])),gut='reference',url='https://blastodb.com'+item['pageUrl'],record_type='Subtype',hosts=r.get('sources',[]))
 for item in d['datasets']:
  r=item['data'];links=re.findall(r'https://www.ncbi.nlm.nih.gov/nuccore/[A-Za-z0-9_.]+',compact(r));put(db,'blastodb:'+item['slug'],'blastodb','ncbi:12968',item['title'],'protists','Blastocystis',host=', '.join(r.get('sources',[])),gut='reference',url='https://blastodb.com'+item['pageUrl'],record_type='Sequence dataset',subtypes=r.get('subtypes',[]),accession_url=links[0] if links else '',data_type=', '.join(r.get('datatypes',[])))
 print('BlastoDB:',len(d['subtypes']),'subtypes,',len(d['datasets']),'sequence datasets',flush=True)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['uhgv','eukaryotes','blasto']);a=parser.parse_args();initialize()
 for name,fn in [('uhgv',uhgv),('eukaryotes',eukaryotes),('blasto',blasto)]:
  if a.only and name!=a.only:continue
  with connect() as db:fn(db)
 with connect() as db:print('Catalogue records:',db.execute('SELECT count(*) FROM catalogue_records').fetchone()[0]);db.commit();db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
if __name__=='__main__':main()
