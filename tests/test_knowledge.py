import copy
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from hub import app, contributions, db, editorial, edits, knowledge, pages
from hub.ingest import upsert


class KnowledgeModel(unittest.TestCase):
    def test_identity_and_parentage_are_explicit(self):
        c=knowledge.model()['concepts']
        for genus,species in [('streptococcus','streptococcus-thermophilus'),('ruminococcus','ruminococcus-bromii'),('faecalibacterium','faecalibacterium-prausnitzii'),('saccharomyces','saccharomyces-cerevisiae')]:
            self.assertNotEqual(c[genus]['name'],c[species]['name'])
            self.assertEqual(c[species]['parent'],genus)
        self.assertEqual(c['tea']['kind'],'food')
        self.assertEqual(c['colonocytes']['kind'],'host_component')
        self.assertEqual(c['gut']['kind'],'community')
        self.assertEqual(c['meal-timing']['kind'],'exposure')

    def test_disease_related_terms_are_not_exact_aliases(self):
        c=knowledge.model()['concepts']['condition:fatty-liver']
        self.assertNotIn('ALD',c['aliases'])
        self.assertIn('ALD',c['related_terms'])
        pneumonia=editorial.read('conditions')['pneumonia']
        self.assertEqual(pneumonia['affected_sites'],['lungs'])
        self.assertNotIn('region',pneumonia)

    def test_coculture_source_is_the_primary_experiment(self):
        m=knowledge.model()
        f=m['findings']['finding:cross-feeding']
        self.assertEqual(f['source_ids'],['MED:26420851'])
        self.assertEqual(m['sources']['MED:26420851']['doi'],'10.1093/femsle/fnv176')
        self.assertIn('cross-feeding',m['sources']['MED:26420851']['title'].lower())
        self.assertEqual(f['system'],'Laboratory')

    def test_validation_rejects_broken_scientific_references(self):
        m=knowledge.model();data=copy.deepcopy(m)
        data['claims']['rb-starch']['subject']='unknown'
        with self.assertRaises(ValueError):knowledge.validate(m['concepts'],data,m['topics'])
        data=copy.deepcopy(m);data['claims']['rb-starch']['evidence'][0]['relation']='named in title'
        with self.assertRaises(ValueError):knowledge.validate(m['concepts'],data,m['topics'])

    def test_search_resolves_everyday_terms_and_condition_intent(self):
        self.assertEqual(knowledge.search('fiber')['explanations'][0]['id'],'fibre')
        results=knowledge.search('IBS')
        self.assertTrue(any(x['url']=='/condition/ibs' for x in results['concepts']))
        self.assertEqual(knowledge.search('bifidobactrium')['suggestion'],'Bifidobacterium')

    def test_evidence_keeps_support_qualification_and_context(self):
        c=knowledge.claim('exercise-microbiome')
        self.assertEqual({f['relation'] for f in c['findings']},{'supports','qualifies'})
        self.assertEqual({f['timepoint'] for f in c['findings']},{'6 weeks plus 6-week washout','3 weeks'})
        rows=knowledge.evidence({'topic':['fibre'],'system':['Laboratory']})['rows']
        self.assertTrue(rows)
        self.assertTrue(all(r['finding']['system']=='Laboratory' for r in rows))
        self.assertTrue(all(r['relation']!='candidate' for r in knowledge.evidence({})['rows']))

    def test_topic_and_mechanism_share_the_same_claim(self):
        m=knowledge.model()
        fibre=m['topics']['fibre'];story=editorial.document('pathways')['pages']['living-well']['stories'][0]
        self.assertIn('cross-feeding-butyrate',fibre['claims'])
        self.assertIn('cross-feeding-butyrate',story['steps'][2]['claims'])
        maps=editorial.read('mechanisms')['mechanisms']
        self.assertTrue(any('cross-feeding-butyrate' in e.get('related_claims',[]) for mm in maps for e in mm['edges']))
        self.assertIn('/claims/cross-feeding-butyrate',pages.topic_page('fibre'))

    def test_pages_are_readable_without_javascript(self):
        text=pages.topic_page('fibre')
        self.assertIn('<h1>What happens to fibre?</h1>',text)
        self.assertIn('R. bromii can open resistant starch',text)
        self.assertIn('What does this mean in practice?',text)
        self.assertIn('What would make the picture clearer?',text)
        self.assertIn('Source location',text)


class Contributions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(db,'DB_PATH',Path(self.tmp.name)/'test.sqlite');self.patch.start()
        db.initialize();editorial._read.cache_clear();knowledge._cache=None
        with db.connect() as conn:
            upsert(conn,dict(id='999003',source='MED',title='A microbial culture experiment',pubYear='2026',doi='10.test/evidence'))

    def tearDown(self):
        knowledge._cache=None;editorial._read.cache_clear();self.patch.stop();self.tmp.cleanup()

    def evidence(self):
        return dict(kind='evidence',target='rb-starch',text='A defined experiment gives a different substrate response.',source='PMID:999003',relation='challenges',system='Laboratory',design='Coculture',population='Defined strains',sample='Culture medium',outcome='Starch degradation',comparison='Matched cultures on a different starch',material_reviewed='Full paper',source_locator='Figure 2',name='Private Contributor',email='private@example.org',public_credit=False)

    def accept(self,ident,**extra):
        return contributions.decide(dict(id=ident,status='accepted',reviewer='Test reviewer',decision_note='Checked the comparison and source scope',**extra))

    def test_approval_adds_disagreement_without_replacing_support(self):
        ident=contributions.submit(self.evidence())['id']
        self.assertEqual(len(knowledge.claim('rb-starch')['findings']),1)
        self.accept(ident)
        c=knowledge.claim('rb-starch')
        self.assertEqual({f['relation'] for f in c['findings']},{'supports','challenges'})
        self.assertIn('MED:999003',knowledge.model()['sources'])
        self.assertIn('A defined experiment',pages.topic_page('fibre'))
        self.assertIn('A defined experiment',pages.research_page({'topic':['fibre']}))
        public=json.dumps(knowledge.model())
        self.assertNotIn('private@example.org',public)
        self.assertNotIn('Private Contributor',public)
        self.assertIn('Test reviewer',public)

    def test_correction_propagates_to_topic_claim_and_research(self):
        ident=contributions.submit(dict(kind='explanation',target='rb-starch',text='A clearer, carefully scoped description.'))['id']
        self.accept(ident)
        self.assertIn('carefully scoped',knowledge.claim('rb-starch')['text'])
        self.assertIn('carefully scoped',pages.topic_page('fibre'))
        self.assertIn('carefully scoped',pages.research_page({'topic':['fibre']}))

    def test_retraction_flags_every_dependent_claim(self):
        ident=contributions.submit(self.evidence())['id'];self.accept(ident)
        with db.connect() as conn:conn.execute("UPDATE papers SET retracted=1 WHERE id='MED:999003'")
        c=knowledge.claim('rb-starch')
        self.assertTrue(c['needs_reassessment'])
        self.assertEqual(c['status'],'needs_review')
        self.assertIn('Retracted source',pages.topic_page('fibre'))

    def test_duplicate_decisions_and_incomplete_evidence_rejected(self):
        ident=contributions.submit(self.evidence())['id'];self.accept(ident)
        with self.assertRaises(edits.Conflict):self.accept(ident)
        data=self.evidence();del data['comparison']
        with self.assertRaises(ValueError):contributions.submit(data)
        data=self.evidence();data['target']='fibre'
        with self.assertRaises(ValueError):contributions.submit(data)

    def test_multiple_reports_can_share_a_study(self):
        data=self.evidence();data['study']='study:starch-keystone'
        ident=contributions.submit(data)['id'];self.accept(ident)
        m=knowledge.model()
        self.assertEqual(m['findings']['finding:contribution:'+str(ident)]['study'],'study:starch-keystone')

    def test_rejection_and_public_credit(self):
        data=self.evidence();data['name']='Public author';data['public_credit']=True
        ident=contributions.submit(data)['id']
        contributions.decide(dict(id=ident,status='rejected',reviewer='Test reviewer',decision_note='Different experimental question'))
        self.assertEqual(len(knowledge.claim('rb-starch')['findings']),1)
        ident=contributions.submit(data)['id'];self.accept(ident)
        self.assertIn('Public author',json.dumps(knowledge.model()))

    def test_concept_and_topic_with_same_slug_are_distinct_targets(self):
        topic_before=knowledge.model()['topics']['fibre']['answer']
        ident=contributions.submit(dict(kind='explanation',target='concept:fibre',text='A more precise material definition.'))['id']
        self.accept(ident)
        self.assertEqual(knowledge.model()['concepts']['fibre']['definition'],'A more precise material definition.')
        self.assertEqual(knowledge.model()['topics']['fibre']['answer'],topic_before)

    def test_stale_explanation_cannot_overwrite_a_newer_review(self):
        payload=dict(kind='explanation',target='rb-starch',text='A carefully scoped correction.')
        first=contributions.submit(payload)['id'];second=contributions.submit(payload)['id']
        self.accept(first)
        with self.assertRaises(edits.Conflict):self.accept(second)

    def test_review_queue_is_private_and_new_pages_submit(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            conn=HTTPConnection('127.0.0.1',server.server_port)
            conn.request('GET','/api/contributions/review');response=conn.getresponse()
            self.assertEqual(response.status,401);response.read()
            conn.request('POST','/api/contributions/decide',json.dumps({'id':1,'status':'accepted'}),{'Content-Type':'application/json'})
            response=conn.getresponse();self.assertEqual(response.status,401);response.read();conn.close()
            for page in ('/mechanisms','/references'):
                payload=dict(page=page,selected='clarify',suggestion='Improve clarity',anchor=dict(context='clarify',before='',after='',selector='#test'))
                self.assertTrue(edits.submit(payload)['id'])
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    unittest.main()
