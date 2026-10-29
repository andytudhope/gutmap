/* Organ-specific teaching scenes. Animation shows processes, never measured abundance or speed. */
(()=>{'use strict';
const TAU=Math.PI*2;
function render(svg,organ,data,options){
 const {onZone,onMicrobe,glyph,reduced}=options;
 const root=svg.append('g').attr('class','habitat-scene').attr('data-habitat-scene',organ);
 root.append('title').text(data.title);
 root.append('desc').text(data.visual.description);
 const defs=root.append('defs');
 defs.append('marker').attr('id','habitat-arrow').attr('viewBox','0 0 10 10').attr('refX',8).attr('refY',5).attr('markerWidth',5).attr('markerHeight',5).attr('orient','auto').append('path').attr('d','M0 0L10 5L0 10Z').attr('fill','currentColor');
 const zones=new Map(),motions=[];
 const path=(g,d,cls='hs-outline')=>g.append('path').attr('d',d).attr('class',cls);
 const text=(g,s,x,y,cls='hs-label',anchor='start')=>g.append('text').attr('x',x).attr('y',y).attr('class',cls).attr('text-anchor',anchor).text(s);
 const circle=(g,x,y,r,cls)=>g.append('circle').attr('cx',x).attr('cy',y).attr('r',r).attr('class',cls);
 const rect=(g,x,y,w,h,cls)=>g.append('rect').attr('x',x).attr('y',y).attr('width',w).attr('height',h).attr('class',cls);
 function action(g,fn,label){g.attr('role','button').attr('tabindex',0).attr('aria-label',label).on('click',e=>{e.stopPropagation();fn();}).on('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();fn();}});}
 function zone(id){const g=root.append('g').attr('class','hs-zone').attr('data-zone-id',id);zones.set(id,g);action(g,()=>onZone(id),data.zones.find(z=>z.id===id).name);return g;}
 function specimen(g,id,x,y,size=12){const m=g.append('g').attr('class','hs-microbe').attr('data-microbe-id',id).attr('transform',`translate(${x},${y})`);
  if(['streptococcus','veillonella'].includes(id)){for(let i=0;i<4;i++)circle(m,(i-1.5)*size*.56,Math.sin(i*1.6)*size*.25,size*.3,'hs-cell');}
  else if(id==='helicobacter')path(m,`M${-size} 4q${size*.5} ${-size} ${size} 0t${size} 0`,'hs-cell');
  else m.html(glyph(options.microbes[id].group,size));
  action(m,()=>onMicrobe(id),options.microbes[id].name+' — open field notes');m.append('title').text(options.microbes[id].name);return m;
 }
 function arrow(g,d,cls='hs-arrow'){return path(g,d,cls).attr('marker-end','url(#habitat-arrow)');}
 function leader(g,caption,x,y,d,anchor='start'){path(g,d,'hs-leader');text(g,caption,x,y,'hs-label',anchor);}
 text(root,data.visual.kicker,385,190,'hs-kicker');
 const phaseLabel=text(root,data.visual.process[0],650,850,'hs-process','middle');
 text(root,'Anatomical schematic · structures enlarged independently',650,888,'hs-footnote','middle');
 let phase=null;
 function mouth(){
  const saliva=zone('fluid');rect(saliva,385,235,530,190,'hs-fluid-field');
  for(let i=0;i<5;i++)path(saliva,`M390 ${270+i*29}Q590 ${250+i*29} 905 ${272+i*29}`,'hs-flow');
  arrow(saliva,'M740 250H885');text(saliva,'Saliva carries sugars and cells',395,227);
  const tooth=root.append('g');path(tooth,'M400 595Q395 518 465 494Q510 476 555 495Q600 476 650 494Q720 518 710 595L678 757Q660 790 632 705L603 644Q583 641 561 705Q528 790 510 757L477 635Z','hs-enamel');
  path(tooth,'M427 590Q430 535 475 522Q514 510 555 523Q602 506 642 522Q691 538 685 587','hs-dentine');
  leader(tooth,'Enamel: a non-shedding surface',410,800,'M470 781L475 625');
  const plaque=zone('mucus');path(plaque,'M401 522Q430 455 487 478Q518 449 555 473Q595 450 634 477Q689 453 714 521L686 535Q648 507 613 519Q573 504 551 519Q513 508 481 519Q438 504 416 541Z','hs-biofilm');
  for(let i=0;i<16;i++)specimen(plaque,i%3?'streptococcus':'veillonella',432+i*16,492+Math.sin(i)*10,10);
  leader(plaque,'Plaque stays attached',745,525,'M730 520L662 503');
  const food=zone('food');rect(food,400,335,470,102,'hs-hit');
  const sugar=d3.range(14).map(i=>circle(food,0,0,3.5,'hs-sugar'));
  const acid=d3.range(7).map(i=>circle(plaque,0,0,2.5,'hs-acid'));
  text(food,'Sugar enters the biofilm',430,322);text(plaque,'Acids reach the tooth surface',730,582,'hs-label','end');
  motions.push(t=>{sugar.forEach((n,i)=>{const u=(t*.11+i/14)%1;n.attr('cx',410+u*440).attr('cy',350+Math.sin(u*TAU+i)*24+u*115).attr('opacity',u<.85?.8:0);});acid.forEach((n,i)=>{const u=(t*.18+i/7)%1;n.attr('cx',470+i*25).attr('cy',499+u*37).attr('opacity',1-u);});});
 }
 function oesophagus(){
  const wall=zone('mucus');path(wall,'M490 235H550V741H490ZM745 235H805V741H745Z','hs-tissue');
  for(let side of[0,1])for(let i=0;i<13;i++){const x=side?754:502,y=247+i*35;path(wall,`M${x} ${y}l26 -4 16 12-6 17-30 1Z`,'hs-squamous');}
  const fluid=zone('fluid');rect(fluid,550,235,195,506,'hs-fluid-field');
  const left=path(wall,'','hs-muscle'),right=path(wall,'','hs-muscle');
  const food=zone('food');const bolus=food.append('g');path(bolus,'M-62-20Q-50-60 0-54Q52-60 65-20Q80 42 0 50Q-80 40-62-20Z','hs-bolus');
  for(let i=0;i<7;i++)specimen(bolus,i%2?'veillonella':'streptococcus',-35+i*11,Math.sin(i)*18,8);
  const wave=path(fluid,'M620 320V420','hs-flow-arrow').attr('marker-end','url(#habitat-arrow)');
  const contractionLead=path(root,'','hs-leader');text(root,'Contraction',390,310);text(root,'behind the bolus',390,336);
  leader(root,'Squamous',910,614,'M865 607L805 588','end');text(root,'lining',910,638,'hs-label','end');
  text(root,'Toward the stomach',650,790,'hs-label','middle');arrow(root,'M650 747V768');
  motions.push(t=>{const u=(t/7)%1,y=320+u*345,contract=y-80;contractionLead.attr('d',`M480 320L588 ${contract}`);bolus.attr('transform',`translate(650,${y})`);wave.attr('d',`M650 ${y+65}V${y+100}`);const points=d3.range(235,750,8);const curve=d3.line().curve(d3.curveBasis);left.attr('d',curve(points.map(v=>[550+47*Math.exp(-(((v-contract)/48)**2)),v])));right.attr('d',curve(points.map(v=>[745-47*Math.exp(-(((v-contract)/48)**2)),v])));});
 }
 function stomach(){
  const food=zone('food'),fluid=zone('fluid'),wall=zone('mucus');
  const outline='M515 237L535 320Q552 340 603 305Q683 240 775 310Q905 415 817 521Q767 580 689 553L850 581L861 611Q730 618 635 588Q487 598 450 479Q412 364 486 322L480 237';
  path(fluid,outline,'hs-gastric-lumen');path(wall,outline,'hs-gastric-mucus');path(root,outline,'hs-outline');
  for(let i=0;i<5;i++)path(fluid,`M${510+i*43} 370Q${470+i*53} 470 ${563+i*43} 526`,'hs-ruga');
  text(root,'Mixing chamber',690,247,'hs-label','middle');text(root,'To the duodenum',905,644,'hs-label','end');arrow(root,'M856 598H905');
  const bits=d3.range(12).map(i=>path(food,'M-6-4L5-7 9 4-4 7Z','hs-food-bit'));
  const acid=d3.range(15).map(()=>circle(fluid,0,0,2.5,'hs-acid'));
  arrow(fluid,'M575 400Q680 327 757 411Q775 470 712 499');
  text(root,'WALL DETAIL · ENLARGED',390,674,'hs-kicker');
  rect(fluid,395,687,510,32,'hs-acid-field');rect(wall,395,719,510,44,'hs-mucus-band');
  path(wall,'M395 765H475Q489 799 503 765H590Q604 799 618 765H705Q719 799 733 765H905V811H395Z','hs-tissue');
  specimen(wall,'helicobacter',440,739,14);specimen(wall,'helicobacter',485,736,13);
  text(root,'Acidic lumen',410,710);text(root,'Protective mucus + bicarbonate',675,747,'hs-label','middle');text(root,'Gastric pits',795,797);
  motions.push(t=>{bits.forEach((n,i)=>{const a=t*.7+i*TAU/12;n.attr('transform',`translate(${655+Math.cos(a)*122},${430+Math.sin(a)*76}) rotate(${a*70}) scale(${.8+(Math.sin(a)+1)*.2})`);});acid.forEach((n,i)=>{const a=t*.43+i*2.4;n.attr('cx',650+Math.cos(a)*(70+i*4)).attr('cy',430+Math.sin(a)*82);});});
 }
 function small(){
  const food=zone('food'),fluid=zone('fluid'),wall=zone('mucus');
  rect(fluid,390,260,520,145,'hs-fluid-field');arrow(fluid,'M405 285H885');text(root,'Flowing nutrients, bile and digestive enzymes',395,240);
  const villus=(x,tip)=>`M${x-62} 705V${tip+90}Q${x-57} ${tip} ${x} ${tip}Q${x+57} ${tip} ${x+62} ${tip+90}V705Z`;
  [455,650,845].forEach((x,i)=>{const tip=i===1?390:430;path(wall,villus(x,tip),'hs-villus-mucus');path(wall,villus(x,tip),'hs-villus');path(wall,`M${x-28} 705V${tip+76}Q${x} ${tip+25} ${x+28} ${tip+76}V705`,'hs-capillary');path(wall,`M${x} 705V${tip+90}`,'hs-lymph');for(let y=tip+100;y<685;y+=27){path(wall,`M${x-61} ${y}h12M${x+61} ${y}h-12`,'hs-cell-junction');}});
  text(root,'Villi increase the absorptive surface',650,772,'hs-label','middle');
  text(root,'Blood',565,722,'hs-blood-label');text(root,'Lymph',692,722,'hs-lymph-label');
  const nutrients=d3.range(15).map(()=>circle(food,0,0,3.5,'hs-sugar'));
  for(let i=0;i<5;i++)specimen(fluid,i%2?'veillonella':'streptococcus',460+i*90,337+Math.sin(i)*15,9);
  const absorbed=d3.range(6).map(i=>circle(wall,0,0,i<3?3:3.8,i<3?'hs-nutrient':'hs-fat')); 
  arrow(wall,'M650 346V375');text(root,'Absorption through the lining',650,327,'hs-label','middle');
  motions.push(t=>{nutrients.forEach((n,i)=>n.attr('cx',398+((t*.1+i/15)%1)*500).attr('cy',290+Math.sin(t+i)*24));absorbed.forEach((n,i)=>{const u=(t*.16+i/6)%1,x=[455,650,845][i%3],start=i%3===1?470:510;n.attr('cx',i<3?x-28+Math.sin(u*Math.PI)*5:x).attr('cy',start+u*(700-start)).attr('opacity',1-u*.6);});});
 }
 function colon(){
  const food=zone('food'),fluid=zone('fluid'),wall=zone('mucus');
  rect(fluid,390,260,520,248,'hs-fluid-field');
  const fibre=(x,y)=>{path(food,`M${x-72} ${y}q20-47 56-33q42-30 76 12q35 40-12 65q-53 26-99-4Z`,'hs-food-island');for(let i=0;i<6;i++)path(food,`M${x-48} ${y-18+i*9}q23-14 42 0t45 0`,'hs-fibre');};
  fibre(490,355);fibre(780,388);
  for(let i=0;i<16;i++)specimen(food,i%2?'bacteroides':'bifidobacterium',425+(i%8)*17+(i>7?275:0),335+(i%3)*21+(i>7?35:0),8);
  for(let i=0;i<7;i++)specimen(fluid,i%2?'methanobrevibacter':'faecalibacterium',420+i*73,466+Math.sin(i)*12,9);
  rect(wall,390,513,520,61,'hs-outer-mucus');rect(wall,390,575,520,64,'hs-inner-mucus');
  for(let i=0;i<8;i++)specimen(wall,'akkermansia',425+i*63,539,8);
  let cells='M390 642';for(let x=420;x<890;x+=104)cells+=`H${x}V699Q${x+20} 746 ${x+40} 699V642`;cells+='H910V769H390Z';path(wall,cells,'hs-tissue');
  for(let x=435;x<890;x+=104)circle(wall,x,696,6,'hs-goblet');
  text(root,'Complex food → microbial fermentation',400,239);
  text(root,'Outer mucus: microbial habitat',400,505);text(root,'Inner mucus: separation from the cells',650,610,'hs-label','middle');text(root,'Crypts descend into the lining; no villi',650,802,'hs-label','middle');
  const products=d3.range(9).map(()=>circle(fluid,0,0,3,'hs-nutrient'));
  arrow(fluid,'M855 460V495');text(root,'Products reach the host',905,485,'hs-small-label','end');
  motions.push(t=>products.forEach((n,i)=>{const u=(t*.12+i/9)%1;n.attr('cx',448+i*49).attr('cy',405+u*268).attr('opacity',u>.9?.35:.85);}));
 }
 function rectum(){
  const food=zone('food'),fluid=zone('fluid'),wall=zone('mucus');
  const chamber=(y,outlet=0)=>`M565 230V310C420 340 ${435-y} 465 485 552Q525 625 ${602-outlet} 662V780H${698+outlet}V662Q775 625 815 552C${865+y} 465 880 340 735 310V230`;
  const lining=path(wall,chamber(0),'hs-rectal-wall');wall.lower();
  path(fluid,'M570 260Q600 290 640 290','hs-flow-arrow').attr('marker-end','url(#habitat-arrow)');text(root,'Arriving from the sigmoid colon',650,213,'hs-label','middle');
  const stool=food.append('g');path(stool,'M-68-45Q-75-82-24-85Q27-100 54-59Q100-25 61 29Q50 77-10 73Q-78 84-72 29Q-98-2-68-45Z','hs-stool');
  for(let i=0;i<9;i++)specimen(stool,i%2?'bifidobacterium':'bacteroides',-40+(i%3)*32,-40+Math.floor(i/3)*38,8);
  const inner=wall.append('ellipse').attr('cx',650).attr('cy',700).attr('rx',72).attr('ry',17).attr('class','hs-sphincter');
  const outer=wall.append('ellipse').attr('cx',650).attr('cy',745).attr('rx',85).attr('ry',22).attr('class','hs-pelvic-floor');
  leader(root,'Internal sphincter',905,696,'M890 687L733 698','end');leader(root,'External sphincter',905,788,'M882 773L744 748','end');
  const signal=path(fluid,'M805 425Q906 390 875 308','hs-sensory').attr('marker-end','url(#habitat-arrow)');
  text(root,'Stretch → urge',920,294,'hs-label','end');
  motions.push(t=>{const u=(t/12)%1,release=Math.max(0,(u-.6)/.4);lining.attr('d',chamber(release<.05?Math.sin(u*4)*8:0,release*28));stool.attr('transform',`translate(650,${450+release*375}) scale(${1-release*.25},${1+release*.15})`).attr('opacity',release>.92?0:1);inner.attr('rx',72+release*18);outer.attr('rx',85+release*15);signal.attr('opacity',u<.6?.25+u:.25);phase=release>0?2:u>.26?1:0;});
 }
 ({mouth,oesophagus,stomach,small,colon,rectum}[organ])();
 let clock=null,playing=false,elapsed=0;
 function frame(seconds){motions.forEach(fn=>fn(seconds));const i=phase??Math.floor(seconds/4)%data.visual.process.length;phaseLabel.text(data.visual.process[i]);}
 function stop(){if(clock)clock.stop();clock=null;playing=false;}
 function play(){if(playing)return;playing=true;const offset=elapsed;clock=d3.timer(ms=>{if(document.hidden)return;elapsed=offset+ms/1000;frame(elapsed);});}
 function highlight(id){for(const[key,g]of zones)g.classed('hs-selected',key===id).attr('aria-pressed',String(key===id));}
 frame(organ==='rectum'?3:1.5);
 if(!reduced)play();
 return {stop,play,highlight,isPlaying:()=>playing,destroy:stop};
}
window.habitatScenes={render};
})();
