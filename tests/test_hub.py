from pathlib import Path
import hashlib,json,re,sqlite3,unittest
from hub import editorial,atlas,research
from hub.db import ROOT,connect,encode_metadata,decode_metadata

class AtlasTest(unittest.TestCase):
    def test_archive_preserved(self):
        with connect() as db:
            for table,n in [('papers',7892),('citations',1663),('references_pending',18531),('catalogue_records',176486),('catalogue_crosswalk',596695)]:
                self.assertGreaterEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],n)
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0],'ok')
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
    def test_metadata_codec(self):
        data={'taxonomy':'α;Bacteria','length':42000,'known':False}
        self.assertEqual(decode_metadata(encode_metadata(data)),data)
    def test_editorial_references_resolve(self):
        notes=editorial.notes();self.assertEqual(set(notes),set(editorial.read('evidence')))
        paths=editorial.read('pathways')
        for page in paths['pages'].values():
            self.assertLessEqual(sum(bool(s.get('featured')) for s in page['stories']),8)
            for story in page['stories']:
                for step in story['steps']:
                    self.assertTrue(set(step['studies'])<=set(notes))
                    self.assertTrue(set(step['chain'])<=set(editorial.document('pathways')['entities']))
                    self.assertTrue(set(step['sources'])<=set(paths['sources']))
    def test_condition_collection(self):
        conditions=editorial.read('conditions');self.assertGreaterEqual(len(conditions),100)
        sources=editorial.read('pathways')['sources']
        for s in conditions.values():
            self.assertEqual(len(s['paragraphs']),3)
            self.assertTrue(all(p.strip() for p in s['paragraphs']))
            self.assertTrue(s['clinical_sources']);self.assertTrue(set(s['clinical_sources'])<=set(sources))
        items=editorial.document('pathways')['pages']['illness-recovery']['stories']
        self.assertGreaterEqual(sum(s['type']=='condition' for s in items),104)
        self.assertNotIn('paragraphs',next(s for s in items if s['id']=='ibs'))
    def test_catalogue_queries(self):
        for kind in ['viruses','protists','fungi']:
            data=atlas.catalogues({'kind':[kind],'limit':['1']})
            self.assertGreater(data['total'],0);self.assertEqual(len(data['records']),1)
            record=atlas.record(data['records'][0]['id']);self.assertIsInstance(record['attributes'],dict)
        data=atlas.catalogues({'source':['gpd'],'limit':['1']})
        self.assertTrue(atlas.record(data['records'][0]['id'])['crosswalk'])
    def test_research_links(self):
        result=research.collection({});self.assertGreaterEqual(result['library_total'],7892)
        self.assertEqual(result['annotated'],len(editorial.read('evidence')))
        healthy=research.collection({'population':['Healthy adults']})
        self.assertTrue(healthy['total'])
    def test_seeders_note_words_and_formatting(self):
        import html
        source=(ROOT/'static/index.html').read_text()
        note=re.search(r'<section id="seeders-note".*?</section>',source,re.S).group()
        self.assertGreater(len(re.sub('<[^>]+>',' ',note).split()),200)
        self.assertEqual(note.count('<blockquote>'),1)
        self.assertIn('t=650s">Adyashanti</a>',note)
    def test_title_markup(self):
        from hub.ingest import clean
        self.assertEqual(clean('&lt;i&gt;Bifidobacterium longum&lt;/i&gt; Subsp. <i>longum</i> 5<sup>1A</sup>'),'Bifidobacterium longum Subsp. longum 5¹ᴬ')
        self.assertEqual(clean('H<sub>2</sub>O &amp; CO<sub>2</sub>'),'H₂O & CO₂')
    def test_fasting_and_worm_coverage(self):
        paths=editorial.read('pathways')
        fasting=[s for s in paths['pages']['living-well']['stories'] if s['category']=='Fasting']
        self.assertEqual(len(fasting),3)
        self.assertTrue(all(s['research_topic']=='fasting' for s in fasting))
        worms=[m for m in editorial.read('anatomy')['community'] if m['group']=='Worms']
        self.assertEqual(len(worms),12)
        self.assertEqual({m['family'] for m in worms},{'Roundworms','Tapeworms','Flukes'})
        self.assertTrue(all(len(m['summary'])>=3 for m in worms))
    def test_citation_discovery_edges(self):
        import tempfile
        from unittest.mock import patch
        from hub import db,ingest
        with tempfile.TemporaryDirectory() as tmp,patch.object(db,'DB_PATH',Path(tmp)/'test.sqlite'):
            db.initialize()
            def paper(id):return dict(id=id,source='MED',title='Gut microbiome study '+id,pubYear='2024',doi='10.test/citing' if id=='3' else '')
            def response(path,params):
                if path.endswith('/citations'):return {'citationList':{'citation':[{'source':'MED','id':'3'}]}}
                self.assertIn('EXT_ID:',params['query'])
                self.assertIn(ingest.QUERY,params['query'])
                return {'resultList':{'result':[paper('2'),paper('3')]}}
            with db.connect() as conn:
                ingest.upsert(conn,paper('1'))
                ingest.upsert(conn,dict(paper('3'),id='preprint',source='PPR'))
                conn.execute('INSERT INTO references_pending VALUES (?,?)',('MED:1','2'));conn.commit()
                with patch.object(ingest,'fetch',side_effect=response):ingest.expand_corpus(conn,5,1)
                self.assertEqual(set(map(tuple,conn.execute('SELECT source,target FROM citations'))),{('MED:1','MED:2'),('PPR:preprint','MED:1')})
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM references_pending').fetchone()[0],0)
    def test_removed_legacy(self):
        from hub.app import ASSETS,PAGES
        self.assertNotIn('/previous',PAGES);self.assertNotIn('previous.html',ASSETS)
        self.assertFalse((ROOT/'hub/content.py').exists())

if __name__=='__main__':unittest.main()
