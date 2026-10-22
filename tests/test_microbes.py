import unittest
from hub import microbes,research,editorial

class Microbes(unittest.TestCase):
    def test_named_papers_connect_to_exact_filtered_research(self):
        d=microbes.dossier('MGYG000002454')
        self.assertGreater(d['total'],5)
        self.assertTrue(any(p['note'] for p in d['papers']))
        self.assertTrue(any('mucus' in x['url'] for x in d['links']))
        self.assertEqual(research.collection({'organism':['MGYG000002454']})['total'],d['total'])
        self.assertTrue(all(p['id'] not in {q['id'] for q in d['related']} for p in d['papers']))
    def test_genus_and_host_context_are_not_species_evidence(self):
        r=next(r for r in microbes.static('reference.json')['species'] if r[1][6]=='Blautia_A faecis')
        d=microbes.dossier(r[0]);self.assertEqual(d['total'],0);self.assertGreater(d['related_total'],0)
        self.assertEqual(d['aliases'],[])
        with microbes.connect() as db:r=db.execute("SELECT id FROM catalogue_records WHERE kind='viruses' AND host='Bacteroides' LIMIT 1").fetchone()
        d=microbes.dossier(r[0]);self.assertEqual(d['total'],0);self.assertGreater(d['related_total'],0)
        self.assertTrue(all(p['match']=='Predicted-host context' for p in d['related']))
        self.assertTrue(d['sources']);self.assertNotIn(d['sources'][0]['id'],microbes.paper_ids(r[0]))
    def test_sources_and_coverage(self):
        overview=microbes.overview();self.assertGreater(overview['linked_species'],50)
        self.assertEqual(len(overview['starts']),5)
        self.assertIsNone(microbes.dossier('unknown-id'))
        for o in editorial.read('microbes')['organisms']:
            for slug in o['studies']:self.assertIn(slug,editorial.notes())
        self.assertFalse(microbes.scientific('GCA-900066495 sp902362365'))
        self.assertFalse(microbes.scientific('Blautia_A faecis'))
