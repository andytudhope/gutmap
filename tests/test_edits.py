import json,os,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from hub import db,edits,editorial,app

class EditTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=patch.object(db,'DB_PATH',Path(self.tmp.name)/'atlas.sqlite');self.path.start();db.initialize();editorial._read.cache_clear()
        self.env=patch.dict(os.environ,{'HUB_EDIT_PASSWORD_HASH':edits.password_hash('test reviewer password')});self.env.start()
    def tearDown(self):
        editorial._read.cache_clear();self.env.stop();self.path.stop();self.tmp.cleanup()
    def suggestion(self,selected='mixing chamber'):
        context=next(r for r in editorial.read('anatomy')['regions'] if r['id']=='stomach')['habitat'];before,after=context.split(selected,1)
        return dict(page='/#organ=stomach',selected=selected,suggestion='Explain this more clearly',email='private@example.org',anchor=dict(context=context,before=before,after=after,selector='#habitat-panel > p'))
    def test_accept_projects_exact_source_and_retains_history(self):
        original=(db.ROOT/'content/anatomy.json').read_bytes();id=edits.submit(self.suggestion())['id']
        edits.decide(id,dict(status='accepted',replacement='digestive chamber'))
        text=next(r for r in editorial.read('anatomy')['regions'] if r['id']=='stomach')['habitat']
        self.assertIn('digestive chamber',text);self.assertNotIn('mixing chamber',text)
        self.assertEqual((db.ROOT/'content/anatomy.json').read_bytes(),original)
        self.assertEqual(edits.queue('accepted')['total'],1)
        public=json.dumps(edits.published());self.assertNotIn('private@example.org',public);self.assertNotIn('Explain this more clearly',public)
    def test_reject_does_not_publish(self):
        context=self.suggestion()['anchor']['context'];id=edits.submit(self.suggestion())['id'];edits.decide(id,dict(status='rejected',decision_note='Keep the current wording'))
        self.assertEqual(edits.published(),[]);self.assertEqual(edits.queue('rejected')['total'],1)
        self.assertEqual(next(r for r in editorial.read('anatomy')['regions'] if r['id']=='stomach')['habitat'],context)
    def test_conflicting_and_duplicate_decisions(self):
        a=edits.submit(self.suggestion())['id'];b=edits.submit(self.suggestion())['id']
        edits.decide(a,dict(status='accepted',replacement='digestive chamber'))
        with self.assertRaises(edits.Conflict):edits.decide(b,dict(status='accepted',replacement='food chamber'))
        with self.assertRaises(edits.Conflict):edits.decide(a,dict(status='rejected'))
    def test_repeated_and_unicode_selection(self):
        context='A 🦠 and a 🦠';payload=dict(page='/explore#life=worms',selected='🦠',suggestion='Second symbol only',anchor=dict(context=context,before='A 🦠 and a ',after='',selector='#unique'))
        id=edits.submit(payload)['id'];edits.decide(id,dict(status='accepted',replacement='bacterium'))
        self.assertEqual(edits.published()[0]['published'],'A 🦠 and a bacterium')
        payload['anchor']['before']='wrong'
        with self.assertRaises(ValueError):edits.submit(payload)
    def test_catalogue_link_appears_only_after_note_approval(self):
        from hub.ingest import upsert
        from hub import microbes
        with db.connect() as conn:upsert(conn,dict(id='999002',source='MED',title='An experimental microbial process',pubYear='2025'))
        pid='MED:999002';record_id='MGYG000000001'
        note=dict(kind='Cell experiment',population='Defined isolate',finding='A measured reaction',meaning='A functional observation',question='Does it occur in vivo?',regions=['colon'],review_basis='Published abstract',catalogue_records=[record_id])
        payload=dict(paper_id=pid,base_revision=edits.note_record(pid)['base_revision'],reading_note=note)
        rejected=edits.submit_note(payload)['id'];edits.decide(rejected,dict(status='rejected'))
        self.assertNotIn(pid,microbes.paper_ids(record_id))
        accepted=edits.submit_note(payload)['id']
        self.assertNotIn(pid,microbes.paper_ids(record_id))
        edits.decide(accepted,dict(status='accepted',reading_note=note))
        self.assertIn(pid,microbes.paper_ids(record_id))
        published=editorial.notes()[next(k for k,n in editorial.notes().items() if n['paper']==pid)]
        self.assertEqual(published['catalogue_records'],[record_id])
        self.assertEqual(edits.queue('accepted')['items'][0]['paper_id'],pid)
        with self.assertRaises(ValueError):edits.note_fields({**note,'catalogue_records':['made-up-id']})

    def test_new_reading_note_keeps_canonical_identity(self):
        from hub.ingest import upsert
        with db.connect() as conn:upsert(conn,dict(id='999001',source='MED',title='Test gut microbiome paper',pubYear='2024'))
        record=edits.note_record('MED:999001')
        note=dict(kind='Human observational study',population='Adults',finding='A measured result',meaning='Its interpretation',question='A testable question',regions=['colon'],review_basis='Published abstract')
        payload=dict(paper_id='MED:999001',base_revision=record['base_revision'],reading_note=note,suggestion='A focused reading note')
        id=edits.submit_note(payload)['id'];edits.decide(id,dict(status='accepted',reading_note=note))
        published=next(n for n in editorial.read('evidence').values() if n['paper']=='MED:999001')
        self.assertEqual(published['finding'],note['finding']);self.assertEqual(published['paper'],'MED:999001')
        self.assertEqual(sum(n['paper']=='MED:999001' for n in editorial.notes().values()),1)
        with self.assertRaises(edits.Conflict):edits.submit_note(payload)
        with self.assertRaises(ValueError):edits.note_record('MED:does-not-exist')
    def test_existing_note_preserves_extra_fields_and_rejects_stale_changes(self):
        from hub.ingest import upsert
        with db.connect() as conn:upsert(conn,dict(id='33842951',source='MED',title='Ramadan study',pubYear='2021'))
        record=edits.note_record('MED:33842951');note=dict(record['note']);note['finding']='A revised finding'
        a=edits.submit_note(dict(paper_id='MED:33842951',base_revision=record['base_revision'],reading_note=note))['id']
        b=edits.submit_note(dict(paper_id='MED:33842951',base_revision=record['base_revision'],reading_note=note))['id']
        edits.decide(a,dict(status='accepted',reading_note=note))
        self.assertEqual(edits.note_record('MED:33842951')['note']['finding'],'A revised finding')
        with self.assertRaises(edits.Conflict):edits.decide(b,dict(status='accepted',reading_note=note))
    def test_password_session_and_http_privacy(self):
        app._attempts.clear();server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        def request(path,data=None,cookie='',origin=None):
            conn=HTTPConnection('127.0.0.1',server.server_port);headers={'Cookie':cookie}
            if data is not None:headers['Content-Type']='application/json'
            if origin:headers['Origin']=origin
            conn.request('POST' if data is not None else 'GET',path,json.dumps(data) if data is not None else None,headers);r=conn.getresponse();result=(r.status,json.loads(r.read()),dict(r.getheaders()));conn.close();return result
        try:
            self.assertEqual(request('/api/edits')[0],401)
            self.assertEqual(request('/api/edits/decide',{'id':1,'status':'accepted','replacement':'x'})[0],401)
            self.assertEqual(request('/api/edits/login',{'password':'incorrect'})[0],401)
            status,body,headers=request('/api/edits/login',{'password':'test reviewer password'});self.assertEqual(status,200)
            cookie=headers['Set-Cookie'].split(';')[0];self.assertIn('HttpOnly',headers['Set-Cookie'])
            self.assertEqual(request('/api/edits',cookie=cookie)[0],200)
            self.assertEqual(request('/api/edits/decide',{'id':1},cookie,'https://another.example')[0],403)
            self.assertEqual(request('/api/edits',cookie='gutmap_editor=9999999999.bad')[0],401)
            self.assertIsNone(edits.login('incorrect'))
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
