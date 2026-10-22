import unittest
from urllib.parse import urlsplit
from hub import editorial,research,edits

class References(unittest.TestCase):
    def test_sources_and_guides_are_connected(self):
        d=editorial.document('references');sources={r['id'] for r in d['references']}
        self.assertGreaterEqual(len(sources),60)
        for r in d['references']:
            self.assertEqual(urlsplit(r['url']).scheme,'https')
            self.assertNotEqual(urlsplit(r['url']).hostname,'www.hmpdacc.org')
            self.assertTrue(r['review_basis'] and r['reviewed'] and r['route'])
        for g in d['guides']:
            self.assertTrue(set(g['sources'])<=sources)
            self.assertTrue(g['sections'])
            cited={n for s in g['sections'] for n in s['studies']}
            self.assertTrue(cited<=set(d['studies']))
            self.assertTrue(set(g['studies'])<=set(d['studies']))
            for s in g['sections']:self.assertTrue(set(s.get('sources',[]))<=sources)
            self.assertGreater(research.collection({'guide':[g['id']]})['total'],0)
        for c in d['coverage']:
            self.assertTrue(set(c['sources'])<=sources)
            self.assertTrue(c['text'] and c['next'] and c['links'])
        self.assertTrue({'stanford','oxford','cedars','cuhk','cleveland','mcc'}<={b['source'] for b in d['benchmarks']})
    def test_reference_text_has_canonical_edit_target(self):
        text=editorial.read('references')['guides'][0]['sections'][0]['text']
        self.assertTrue(edits.source_target(text).startswith('content:references:'))
    def test_neural_route_does_not_transport_serotonin_into_brain(self):
        maps={m['id']:m for m in editorial.read('mechanisms')['mechanisms']}
        brain=maps['gut-brain'];transport=[e for e in brain['edges'] if e['kind']=='transport']
        self.assertEqual([(e['source'],e['target']) for e in transport],[('3','2')])
        self.assertEqual(brain['nodes'][3]['name'],'Tryptophan availability')
        self.assertEqual(len(brain['steps']),5)
