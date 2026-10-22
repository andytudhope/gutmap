import unittest
from hub import editorial,knowledge,research

class LivingWell(unittest.TestCase):
    def test_new_topics_resolve_the_same_findings_in_learning_and_research(self):
        data=editorial.document('pathways');model=knowledge.model()
        stories={s['id']:s for s in data['pages']['living-well']['stories']}
        for ident in ('fasting','toilet-posture-care','slow-cooking-eating'):
            story=stories[ident]
            self.assertTrue(story['featured'])
            for step in story['steps']:
                self.assertTrue(set(step['chain'])<=model['concepts'].keys())
                self.assertTrue(set(step['sources'])<=data['sources'].keys())
                claim=model['claims'][step['claims'][0]]
                self.assertEqual(step['text'],claim['text'])
                self.assertEqual({e['finding'] for e in claim['evidence']},{'finding:'+n for n in step['studies']})
                for slug in step['studies']:
                    note=data['studies'][slug]
                    paper=research.paper_detail(note['paper'])['paper']
                    self.assertEqual(paper['note']['finding'],model['findings']['finding:'+slug]['summary'])
                    self.assertIn('/living-well#item='+ident,[v['url'] for v in paper['pathways']])
        self.assertNotIn('ramadan-fasting',stories)
        self.assertFalse(any('ramadan-fasting' in key for key in model['claims']))
        self.assertIn('fasting-ramadan',{n for step in stories['fasting']['steps'] for n in step['studies']})

    def test_toilet_and_fasting_evidence_keeps_counterexamples_and_scope(self):
        notes=editorial.read('evidence')
        self.assertIn('did not improve',notes['toilet-footstool']['finding'])
        self.assertIn('not a national',notes['toilet-bidet-japan']['meaning'])
        self.assertIn('not establish',notes['slow-eating']['meaning'])
        self.assertIn('not a slow-cooker trial',notes['cooking-bean-structure']['meaning'])
        self.assertIn('No male comparison',notes['fasting-women-hormones']['meaning'])
        self.assertIn('did not significantly improve',notes['fasting-year-trial']['finding'])
        self.assertIn('Mouse immune findings do not establish',notes['ketosis-microbiome']['meaning'])

    def test_new_practices_and_merged_alias_are_discoverable(self):
        for term,ident in [('bidet','toilet-posture-care'),('slow cooking','slow-cooking-eating'),('Ramadan fasting','fasting')]:
            self.assertTrue(any(r['url']=='/living-well#item='+ident for r in knowledge.search(term)['explanations']))
