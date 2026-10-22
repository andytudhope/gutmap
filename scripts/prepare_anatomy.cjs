/* Optional authoring tool: npm install --no-save playwright, run the local server,
   then node scripts/prepare_anatomy.cjs http://127.0.0.1:8091.
   Rebuild after changing anatomical paths; no browser tooling is needed to serve the site. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
(async()=>{
 const browser=await chromium.launch(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto(process.argv[2]||'http://127.0.0.1:8091');
  await page.waitForFunction(()=>typeof S!=='undefined'&&S.loaded);
  const art=await page.evaluate(()=>{
   S.timer.stop();order.forEach(id=>{delete geometry[id].node.lookup;delete geometry[id].routeNode.lookup;});
   const ink=svg.append('g');order.forEach(id=>organInk(ink,id));
   const rng=d3.randomLcg(.718),weights=['stomach','stomach','small','small','small','colon','colon','colon','oesophagus','rectum','mouth'];
   const points=d3.range(3600).map(i=>{const id=weights[i%weights.length],p=sample(id,rng);return[order.indexOf(id),p.x,p.y,.35+rng()*.75,.15+rng()*.35];});
   const hatches=d3.range(700).map(i=>{const p=sample(i%3===0?'stomach':i%3===1?'colon':'small',rng),length=2+rng()*7;return[p.x,p.y,length*.6,-length];});
   ink.selectAll('.tissue-shade').each(function(){const pts=[...this.getAttribute('d').matchAll(/[ML](-?[\d.]+),(-?[\d.]+)/g)].map(m=>[+m[1],+m[2]]);if(pts.length<100)return;const chosen=pts.filter((_,i)=>i%2===0||i===pts.length-1);this.setAttribute('d',chosen.map(([x,y],i)=>(i?'L':'M')+Number(x.toFixed(2))+','+Number(y.toFixed(2))).join(''));});
   const table=node=>{const length=node.getTotalLength();return{length,points:Array.from({length:Math.ceil(length/2)+1},(_,i)=>{const p=node.getPointAtLength(Math.min(i*2,length));return[p.x,p.y];})};};
   return{ink:ink.html(),points,hatches,geometry:Object.fromEntries(order.map(id=>[id,{shape:table(geometry[id].node),route:table(geometry[id].routeNode)}]))};
  });
  const content=JSON.stringify(art,(k,v)=>typeof v==='number'?Number(v.toFixed(3)):v),name='anatomy-art.'+crypto.createHash('sha256').update(content).digest('hex').slice(0,12)+'.json';
  const root=path.resolve(__dirname,'..'),staticDir=path.join(root,'static');fs.writeFileSync(path.join(staticDir,name),content);
  for(const file of ['learn.js','index.html']){const target=path.join(staticDir,file);fs.writeFileSync(target,fs.readFileSync(target,'utf8').replace(/anatomy-art\.[a-f0-9]{12}\.json/g,name));}
  for(const file of fs.readdirSync(staticDir))if(/^anatomy-art\.[a-f0-9]{12}\.json$/.test(file)&&file!==name)fs.unlinkSync(path.join(staticDir,file));
  console.log('Prepared '+name);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
