"""Local Gut Atlas server: static views and small metadata APIs."""
import argparse,gzip,json,mimetypes,time,re
from collections import defaultdict
from threading import Lock
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit,unquote
from .db import ROOT,initialize,connect
from . import atlas,editorial,research,edits,microbes,knowledge,contributions,pages,navigation

PAGES={'/':'index.html','/learn':'index.html','/references':'references.html','/mechanisms':'mechanisms.html','/edits':'edits.html','/explore':'index.html','/research':'research.html','/papers':'research.html',**{path:'pathways.html' for path in ['/living-well','/fermentation','/illness-recovery']}}
ASSETS={p.relative_to(ROOT/'static').as_posix():p for p in (ROOT/'static').rglob('*') if p.is_file()}

_attempts=defaultdict(list)
_attempt_lock=Lock()

def limited(key,maximum,window):
    now=time.monotonic()
    with _attempt_lock:
        for k in list(_attempts):
            if not _attempts[k] or _attempts[k][-1]<now-3600:del _attempts[k]
        if len(_attempts)>4096:return True
        _attempts[key]=[t for t in _attempts[key] if t>now-window]
        if len(_attempts[key])>=maximum:return True
        _attempts[key].append(now)
    return False

class Handler(BaseHTTPRequestHandler):
    def send(self,value,status=200,ctype='application/json; charset=utf-8',headers=None):
        payload=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
        compressed=len(payload)>1000 and 'gzip' in self.headers.get('Accept-Encoding','')
        if compressed:payload=gzip.compress(payload)
        self.send_response(status);self.send_header('Content-Type',ctype)
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('Cache-Control',(headers or {}).get('Cache-Control','no-store' if self.path.startswith(('/edits','/api/edits')) else 'no-cache'))
        if compressed:self.send_header('Content-Encoding','gzip');self.send_header('Vary','Accept-Encoding')
        self.send_header('Content-Length',str(len(payload)))
        for key,value in (headers or {}).items():
            if key!='Cache-Control':self.send_header(key,value)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(payload)

    def authorized(self):return edits.authenticated(self.headers.get('Cookie'))
    def secure(self):return self.headers.get('X-Forwarded-Proto')=='https'
    def client_key(self):
        return self.headers.get('X-Forwarded-For',self.client_address[0]).split(',')[0].strip() if self.client_address[0] in ('127.0.0.1','::1') else self.client_address[0]
    def do_POST(self):
        try:self.post()
        except edits.Conflict as e:self.send({'error':str(e)},409)
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e:self.send({'error':str(e) or 'Invalid request'},400)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            self.log_error('%s: %s',type(e).__name__,e);self.send({'error':'Could not save this request'},500)
    def post(self):
        origin=self.headers.get('Origin','')
        if origin and origin not in ('http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')):return self.send({'error':'Origin not allowed'},403)
        size=int(self.headers.get('Content-Length','0'))
        if size<=0 or size>100000:return self.send({'error':'Request is too large or empty'},413)
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send({'error':'Use JSON'},415)
        path=urlsplit(self.path).path
        if path.startswith('/api/edits/') and path not in ('/api/edits/login','/api/edits/submit','/api/edits/submit-note') and not self.authorized():return self.send({'error':'Sign in to review edits'},401)
        data=json.loads(self.rfile.read(size))
        if not isinstance(data,dict):raise ValueError('Use an object')
        if path=='/api/contributions':
            if limited('submit:'+self.client_key(),20,3600):return self.send({'error':'Please try again later'},429)
            return self.send(contributions.submit(data),201)
        if path=='/api/contributions/decide':
            if not self.authorized():return self.send({'error':'Sign in to review contributions'},401)
            return self.send(contributions.decide(data))
        if path in ('/api/edits/submit','/api/edits/submit-note'):
            if limited('submit:'+self.client_key(),20,3600):return self.send({'error':'Please try again later'},429)
            return self.send(edits.submit_note(data) if path.endswith('submit-note') else edits.submit(data),201)
        if path=='/api/edits/login':
            if not edits.configured():return self.send({'error':'The review password is not configured'},503)
            if not self.secure() and self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost','[::1]'):return self.send({'error':'Use HTTPS to sign in'},403)
            if limited('login:'+self.client_key(),10,900):return self.send({'error':'Please try again later'},429)
            token=edits.login(edits.text(data.get('password'),1000,True))
            if not token:return self.send({'error':'Incorrect password'},401)
            return self.send({'ok':True},headers={'Set-Cookie':edits.COOKIE+'='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+('; Secure' if self.secure() else '')})
        if path=='/api/edits/logout':return self.send({'ok':True},headers={'Set-Cookie':edits.COOKIE+'=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+('; Secure' if self.secure() else '')})
        if path=='/api/edits/decide':return self.send(edits.decide(int(data['id']),data))
        return self.send({'error':'Not found'},404)
    def do_HEAD(self):self.do_GET()
    def do_GET(self):
        try:self.get()
        except (BrokenPipeError,ConnectionResetError):pass
        except (ValueError,TypeError):self.send({'error':'Invalid query'},400)
        except Exception as e:
            self.log_error('%s: %s',type(e).__name__,e);self.send({'error':'Could not load this view'},500)

    def get(self):
        url=urlsplit(self.path);path=unquote(url.path).rstrip('/') or '/';args=parse_qs(url.query)
        if path=='/api/contributions/review':
            if not self.authorized():return self.send({'error':'Sign in to review contributions'},401)
            return self.send({'items':contributions.queue(args.get('status',['pending'])[0])},headers={'Cache-Control':'no-store'})
        if path=='/api/search':return self.send(knowledge.search(args.get('q',[''])[0][:200]))
        if path=='/api/evidence':return self.send(knowledge.evidence(args))
        if path in ('/api/knowledge','/api/knowledge/export'):return self.send(knowledge.model())
        if path=='/api/knowledge/claim':
            data=knowledge.claim(args.get('id',[''])[0]);return self.send(data or {'error':'Claim not found'},200 if data else 404)
        if path=='/api/knowledge/concept':
            data=knowledge.concept(args.get('id',[''])[0]);return self.send(data or {'error':'Concept not found'},200 if data else 404)
        if path in ('/evidence','/search','/contribute','/review','/conditions') or path.startswith(('/topics/','/claims/','/findings/','/concepts/','/condition/','/guides/')):
            page=pages.render(path,args)
            return self.send(page.encode() if page else b'Page not found',200 if page else 404,ctype='text/html; charset=utf-8',headers={'Cache-Control':'no-store'} if path=='/review' else None)
        if path=='/api/edits/note':return self.send(edits.note_record(args.get('paper',[''])[0]))
        if path=='/api/edits/session':return self.send({'authenticated':self.authorized(),'configured':edits.configured()})
        if path=='/api/edits':
            if not self.authorized():return self.send({'error':'Sign in to review edits'},401)
            return self.send(edits.queue(args.get('status',['pending'])[0],int(args.get('offset',['0'])[0])))
        if path=='/api/text-edits':
            rev=edits.revision();return self.send({'revision':rev,'patches':[] if args.get('revision',[''])[0]==str(rev) else [p for p in edits.published() if p['kind']=='text']})
        if path=='/api/microbes':
            data=microbes.dossier(args['id'][0][:200]) if args.get('id') else microbes.overview()
            return self.send(data or {'error':'Record not found'},200 if data else 404)
        if path=='/api/health':return self.send({'ok':True})
        if path=='/api/learn':
            data=editorial.document(args.get('view',['anatomy'])[0]);return self.send(data or {'error':'Not found'},200 if data else 404)
        if path=='/api/learn/item':
            data=editorial.read('conditions').get(args.get('id',[''])[0]);return self.send(data or {'error':'Not found'},200 if data else 404)
        if path=='/api/research':return self.send(research.collection(args))
        if path=='/api/research/paper':data=research.paper_detail(args.get('id',[''])[0])
        elif path=='/api/atlas/catalogues':return self.send(atlas.catalogues(args))
        elif path=='/api/atlas/record':data=atlas.record(args.get('id',[''])[0])
        elif path=='/api/atlas/entity':data=atlas.entity(args.get('id',[''])[0])
        else:
            asset=ASSETS.get(PAGES.get(path,path.lstrip('/')))
            if asset:
                if asset.suffix=='.html':
                    # Version asset URLs so cached scripts/styles refresh with each code change.
                    html=asset.read_text()
                    section=navigation.active_section(path)
                    html=re.sub(r'<nav class="site-nav".*?</nav>',navigation.primary(section),html,flags=re.S)
                    if path in ('/explore','/mechanisms'):
                        html=html.replace('</header>','</header>'+navigation.exploring(path),1)
                    html=html.replace('</head>','<link rel="stylesheet" href="/explore-navigation.css"></head>')
                    def version(match):
                        name=match.group(2);file=ASSETS.get(name)
                        return match.group(1)+'/'+name+('?v='+str(file.stat().st_mtime_ns) if file else '')+match.group(3)
                    html=re.sub(r'((?:src|href)=")/([^"?]+\.(?:js|css))(")',version,html)
                    return self.send(html.encode(),ctype='text/html; charset=utf-8')
                stat=asset.stat();etag='"'+str(stat.st_mtime_ns)+'-'+str(stat.st_size)+'"'
                immutable=bool(re.search(r'\.[a-f0-9]{12}\.',asset.name))
                headers={'ETag':etag,'Cache-Control':'public, max-age='+('31536000, immutable' if immutable or 'v' in args else '3600')}
                if self.headers.get('If-None-Match')==etag:return self.send(b'',status=304,headers=headers)
                return self.send(asset.read_bytes(),ctype=(mimetypes.guess_type(asset)[0] or 'application/octet-stream')+'; charset=utf-8',headers=headers)
            return self.send({'error':'Not found'},404)
        return self.send(data or {'error':'Not found'},200 if data else 404)

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8091);a=p.parse_args();initialize()
    server=ThreadingHTTPServer((a.host,a.port),Handler);server.daemon_threads=True
    print(f'Gut Atlas listening on {a.host}:{a.port}',flush=True);server.serve_forever()
if __name__=='__main__':main()
