import unittest
from hub import editorial,research

class Mechanisms(unittest.TestCase):
    def test_routes_have_resolved_evidence_and_compartments(self):
        data=editorial.document('mechanisms');maps=data['mechanisms']
        self.assertEqual(len({m['id'] for m in maps}),11)
        for m in maps:
            nodes={n['id'] for n in m['nodes']};edges={e['id'] for e in m['edges']}
            for n in m['nodes']:self.assertTrue(n['role'] and n['compartment'])
            for e in m['edges']:
                self.assertIn(e['source'],nodes);self.assertIn(e['target'],nodes)
                self.assertIn(e['kind'],('transport','conversion','signal','inhibition'))
            for s in m['steps']:
                self.assertTrue(s['studies'])
                self.assertTrue(set(s['edges'])<=edges)
                for slug in s['studies']:self.assertIn(slug,data['studies'])
            self.assertEqual(edges,{e for s in m['steps'] for e in s['edges']})
            for item in m['measurements']:self.assertTrue(set(item['nodes'])<=nodes)
    def test_regulation_and_paper_links(self):
        maps={m['id']:m for m in editorial.read('mechanisms')['mechanisms']}
        iron=maps['iron'];self.assertTrue(any(e['source']=='5' and e['target']=='2' and e['kind']=='inhibition' for e in iron['edges']))
        self.assertFalse(any('brain' in n['name'].lower() for n in maps['serotonin']['nodes']))
        self.assertGreater(research.collection({'mechanism':['iron']})['total'],0)
        model=research.model()
        # The notes remain canonical paper records; map arrows never become citation edges.
        self.assertTrue(any('/mechanisms#map=iron' in x['url'] for p in model['papers'].values() for x in p['pathways']))
