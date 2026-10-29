import unittest
from urllib.parse import urlsplit
from hub import editorial

class Habitats(unittest.TestCase):
    def test_six_distinct_sourced_explanations_with_resolved_interactions(self):
        habitats=editorial.read('exploration')['habitats']
        anatomy=editorial.document('anatomy')
        self.assertEqual(set(habitats),{'mouth','oesophagus','stomach','small','colon','rectum'})
        self.assertEqual(len({h['visual']['kicker'] for h in habitats.values()}),6)
        for h in habitats.values():
            self.assertEqual({z['id'] for z in h['zones']},{'food','fluid','mucus'})
            self.assertEqual(len(h['visual']['process']),3)
            self.assertTrue(h['visual']['takeaway'])
            for source in h['visual']['sources']:
                self.assertEqual(urlsplit(source['url']).scheme,'https')
            for zone in h['zones']:
                self.assertTrue(set(zone['residents'])<=anatomy['microbes'].keys())
                self.assertTrue(set(zone['papers'])<=anatomy['studies'].keys())
