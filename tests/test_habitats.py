import unittest
from urllib.parse import urlsplit
from hub import editorial
from hub import research
from hub.ingest import classify

class Habitats(unittest.TestCase):
    def test_seven_distinct_sourced_explanations_with_resolved_interactions(self):
        habitats=editorial.read('exploration')['habitats']
        anatomy=editorial.document('anatomy')
        self.assertEqual(set(habitats),{'mouth','oesophagus','stomach','small','cecum','colon','rectum'})
        self.assertEqual(len({h['visual']['kicker'] for h in habitats.values()}),7)
        for h in habitats.values():
            self.assertEqual({z['id'] for z in h['zones']},{'food','fluid','mucus'})
            self.assertEqual(len(h['visual']['process']),3)
            self.assertTrue(h['visual']['takeaway'])
            for source in h['visual']['sources']:
                self.assertEqual(urlsplit(source['url']).scheme,'https')
            for zone in h['zones']:
                self.assertTrue(set(zone['residents'])<=anatomy['microbes'].keys())
                self.assertTrue(set(zone['papers'])<=anatomy['studies'].keys())

    def test_cecum_connects_anatomy_habitat_and_human_research(self):
        anatomy=editorial.document('anatomy')
        ids=[r['id'] for r in anatomy['regions']]
        self.assertEqual(ids[3:6],['small','cecum','colon'])
        self.assertEqual(len({r['number'] for r in anatomy['regions']}),len(ids))
        cecum=anatomy['regions'][4]
        papers=set(cecum['papers'])
        for theme in cecum['research']:
            papers.update(theme['papers'])
        self.assertTrue(papers<=anatomy['studies'].keys())
        self.assertIn('MED:22829946',{anatomy['studies'][p]['paper'] for p in papers})
        result=research.collection({'region':['cecum']})
        self.assertIn('MED:22829946',{p['id'] for p in result['papers']})
        for spelling in ['cecum','caecum','cecal','caecal','ileocecal','ileocaecal']:
            self.assertIn('cecum',classify({'title':spelling+' microbiome'})[3])
