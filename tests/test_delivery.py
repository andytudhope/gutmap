import json,re,threading,unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from hub.app import Handler
from hub.db import ROOT

class Delivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def test_versioned_assets_and_conditional_cache(self):
        with urlopen(self.url+'/') as response:html=response.read().decode()
        self.assertRegex(html,r'/learn.js\?v=\d+')
        with urlopen(self.url+'/') as response:anatomy=response.read().decode()
        self.assertRegex(anatomy,r'/learn.js\?v=\d+')
        asset=re.search(r'href="(/anatomy-art\.[a-f0-9]+\.json)"',anatomy)[1]
        with urlopen(self.url+asset) as response:
            self.assertIn('immutable',response.headers['Cache-Control']);etag=response.headers['ETag']
        with self.assertRaises(HTTPError) as caught:urlopen(Request(self.url+asset,headers={'If-None-Match':etag}))
        self.assertEqual(caught.exception.code,304)
        with urlopen(self.url+'/learn.js?v=1') as response:self.assertIn('max-age=31536000',response.headers['Cache-Control'])
        with urlopen(self.url+'/api/edits/session') as response:self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_prepared_art_has_all_paths_and_particles(self):
        art=json.loads(next((ROOT/'static').glob('anatomy-art.*.json')).read_text())
        self.assertEqual(set(art['geometry']),{'mouth','oesophagus','stomach','small','colon','rectum'})
        self.assertEqual(len(art['points']),3600)
        for g in art['geometry'].values():
            for path in g.values():
                self.assertGreater(path['length'],0)
                self.assertGreater(len(path['points']),1)

    def test_primary_navigation_and_explore_views(self):
        from hub import navigation
        for path in ('/', '/explore', '/mechanisms', '/conditions', '/condition/ibs', '/research', '/references'):
            with self.subTest(path=path),urlopen(self.url+path) as response:
                html=response.read().decode()
                primary=re.search(r'<nav class="site-nav"[^>]*>(.*?)</nav>',html)[1]
                self.assertEqual(re.findall(r'>([^<]+)</a>',primary),['Learn','Explore','Research','References'])
                section=navigation.active_section(path)
                self.assertIn(f'aria-current="page">{section}</a>',primary)
                if section=='Explore':
                    self.assertIn(navigation.exploring(path),html)
                else:
                    self.assertNotIn('class="explore-navigation"',html)
        with urlopen(self.url+'/explore') as response:
            html=response.read().decode()
            self.assertIn('id="anatomy"',html)
            self.assertIn('/explore.js?v=',html)
            self.assertNotIn('Explore the gut.',html)
            self.assertIn('href="/explore" aria-current="page">Microbes & genomes</a>',html)

    def test_reading_route_order(self):
        from hub import editorial
        self.assertEqual([g['id'] for g in editorial.read('references')['guides']],
                         ['gut-brain','food-cultures','early-life','medicines','testing'])
