/* Stage-specific schematics for intestinal and oral infections. */
'use strict';
function drawInfection(g,labels,story,stage){
 const d=story.infection_diagram,kind=d.kind;
 const line=(path,cls='process-ink')=>g.append('path').attr('d',path).attr('class',cls);
 const ellipse=(x,y,rx,ry=rx,cls='process-faint')=>g.append('ellipse').attr('cx',x).attr('cy',y).attr('rx',rx).attr('ry',ry).attr('class',cls);
 const label=(value,x,y,cls='process-small-label')=>text(labels,value,x,y,cls);
 const arrow=(x,y,toX,toY)=>{line(`M${x} ${y}L${toX} ${toY}`,'infection-arrow');const a=Math.atan2(toY-y,toX-x);line(`M${toX-11*Math.cos(a-.5)} ${toY-11*Math.sin(a-.5)}L${toX} ${toY}L${toX-11*Math.cos(a+.5)} ${toY-11*Math.sin(a+.5)}`,'infection-arrow');};
 const rod=(x,y)=>{g.append('rect').attr('x',x-17).attr('y',y-7).attr('width',34).attr('height',14).attr('rx',7).attr('class','process-microbe');line(`M${x+17} ${y}q15-12 23 0`);};
 const virus=(x,y)=>{ellipse(x,y,15,15,'process-ink');for(let j=0;j<8;j++){const a=j*Math.PI/4;line(`M${x+Math.cos(a)*15} ${y+Math.sin(a)*15}l${Math.cos(a)*7} ${Math.sin(a)*7}`);}};
 const egg=(x,y)=>{ellipse(x,y,17,22,'process-ink');ellipse(x,y,9,13);};
 const worm=(x,y,scale=1)=>line(`M${x} ${y}q${-45*scale} ${-55*scale} ${-15*scale} ${-85*scale}t${50*scale} ${10*scale}t${-20*scale} ${90*scale}`);
 const amoeba=(x,y)=>{line(`M${x-25} ${y}q-12-30 12-24q20-25 25 0q35 10 10 25q5 30-24 15q-30 10-23-16Z`);ellipse(x+2,y,6);};
 const microbe=(x,y)=>['worm','bloodloss','autoinfection','eggs'].includes(kind)?worm(x,y,.5):kind==='fungus'?ellipse(x,y,13,20,'process-ink'):['villus','liver'].includes(kind)&&story.id!=='cryptosporidiosis'?virus(x,y):story.id==='amoebiasis'?amoeba(x,y):story.id==='cryptosporidiosis'?egg(x,y):rod(x,y);
 const tissue=(y=350,damaged=false)=>{for(let j=0;j<10;j++){const x=125+j*55;if(damaged&&[4,5].includes(j)){line(`M${x} ${y+80}l12-20 14 17 17-25`);continue;}g.append('rect').attr('x',x).attr('y',y).attr('width',52).attr('height',100).attr('rx',10).attr('class','process-tissue');ellipse(x+26,y+70,8,13);}line(`M120 ${y-20}Q260 ${y-45} 400 ${y-20}T680 ${y-20}`,'process-flow');};
 const gut=(x,y)=>line(`M${x-40} ${y-50}q80-7 70 10t-70 22t70 22t-70 22t70 22M${x-60} ${y+65}V${y-72}q0-12 20-12h90q15 0 15 15v120q0 15-30 15`);
 const liver=(x,y)=>line(`M${x-65} ${y-30}q70-35 135 0l-25 35-60 10-55-15Z`);
 const mouth=(x,y)=>{line(`M${x-75} ${y}q75-75 150 0q-75 70-150 0Z`);line(`M${x-60} ${y}h120M${x-45} ${y-15}v30M${x-15} ${y-25}v45M${x+15} ${y-25}v45M${x+45} ${y-15}v30`);};
 const tooth=()=>{line('M285 190q-35-50-65-10t-5 100q15 40 15 130q10 65 40-20q10-35 20 0q30 85 40 20q0-90 15-130q30-60-5-100t-55 10Z');line('M170 300q65-35 115 5t95-5M170 440h200');};
 label(story.steps[stage].label,400,80,'process-stage-label');
 if(stage===0){
  if(story.region==='mouth'){mouth(400,330);for(let j=0;j<6;j++)microbe(320+j*30,300+(j%2)*45);label('Oral surface and its microbial habitat',400,470);}
  else{ellipse(190,305,85,85);label(['worm','eggs'].includes(kind)?'Soil / hands':'Exposure',190,420);microbe(190,310);arrow(290,310,460,310);gut(580,310);label(story.region==='colon'?'Large intestine':'Intestinal entry',580,440);}
  const words=d.exposure.split(' / ');words.forEach((s,i)=>label(s,400,160+i*25));
 }else if(stage===3){
  if(story.region==='mouth'){tooth();line('M370 225l160 70m-10-25-20 45m-5-55-20 45m-5-55-20 45');label(kind==='acid'?'Fluoride + plaque control':'Disrupt local growth / plaque',520,400);}
  else{gut(220,310);g.append('rect').attr('x',510).attr('y',240).attr('width',130).attr('height',160).attr('rx',8).attr('class','process-glass');line('M520 295h110M550 220h50M575 220v-25');arrow(475,320,340,320);label(['worm','bloodloss','eggs','autoinfection'].includes(kind)?'Targeted parasite treatment':kind==='liver'?'Prevention / supportive care':'Care matched to the organism',570,450);label(['worm','bloodloss','eggs','autoinfection'].includes(kind)?'Prevent repeated exposure':'Support the host',220,450);}
 }else if(['gum','acid','fungus'].includes(kind)){
  if(kind==='fungus'){tissue(370,false);for(let j=0;j<8;j++){const x=215+j*48;ellipse(x,340,10,16,'process-ink');if(j%2===0)line(`M${x} 330q15-45 30-20t15-35`);}label('Candida growth on mucosa',400,230);label(stage===1?'Attached yeast and filaments':'Plaques and local irritation',400,520);}
  else{tooth();for(let j=0;j<8;j++)rod(330+(j%2)*22,230+j*15);if(kind==='acid'){label('Sugar → microbial fermentation → acid',470,180);arrow(520,250,350,260);label(stage===1?'Local pH falls':'Acid dissolves tooth mineral',500,440);if(stage===2)g.append('circle').attr('cx',322).attr('cy',263).attr('r',18).attr('class','infection-affected');}
  else{for(let j=0;j<6;j++)ellipse(360+(j%2)*30,330+j*16,5,5,'infection-affected');label('Plaque at the gum margin',500,210);label(stage===1?'Host immune response at the gum':'Persistent tissue inflammation',500,460);if(stage===2&&story.id==='periodontitis'){line('M180 445h160M180 470h160','infection-arrow');label('Loss of supporting tissue',500,510);}}}
 }else if(['worm','bloodloss','autoinfection','eggs'].includes(kind)){
  if(stage===1&&['ascariasis','hookworm'].includes(story.id)){gut(200,340);line('M570 205v80m-12-20q-50-60-65 15l-8 65q65 15 70-45m28-35q50-60 65 15l8 65q-65 15-70-45');arrow(285,320,470,280);arrow(510,395,300,410);label('Larval migration through lungs',400,160);label('Larvae are swallowed back into the intestine',400,510);}
  else{tissue(370);for(let j=0;j<3;j++)worm(270+j*100,340,.8);if(kind==='bloodloss'){for(let j=0;j<6;j++)ellipse(290+j*40,475,4,7,'infection-affected');label('Attached adults → continuing blood loss',400,240);label('Iron depletion can produce anaemia',400,535);}
  else if(kind==='autoinfection'){line('M520 470C730 520 730 180 480 220','infection-arrow');arrow(480,220,430,260);label('Autoinfection: larvae re-enter tissue',400,180);label(stage===2?'Immune suppression can accelerate the cycle':'The cycle continues inside the same host',400,535);}
  else if(kind==='eggs'){for(let j=0;j<4;j++)egg(530+j*30,500);arrow(420,430,520,480);label('Adult females → perianal egg laying',400,200);label('Itching → eggs on fingers → reinfection',400,570);}
  else{label(story.id==='trichuriasis'?'Thin front end embedded in the colon':'Adult worms occupy the small-intestinal lumen',400,220);label(stage===2?'Heavy burdens impair tissue function':'Parasites mature at their intestinal site',400,535);}}
 }else if(['liver','systemic'].includes(kind)){
  gut(190,320);liver(585,280);arrow(290,290,490,270);label(kind==='liver'?'Virus reaches hepatocytes':'Bacteria cross into systemic circulation',400,170);if(stage===2){arrow(535,340,290,390);label('Bile returns organisms to the intestine',400,470);label(kind==='liver'?'Shedding in stool continues transmission':'Gallbladder carriage can sustain shedding',400,530);}else label('Intestinal entry and target organ are different locations',400,500);
 }else if(kind==='toxin'){
  tissue(360,stage===2);rod(270,310);for(let j=0;j<5;j++)g.append('path').attr('d',`M${350+j*35} 305l7 13-15 0Z`).attr('class','infection-affected');arrow(450,300,450,420);label('Shiga toxin acts on susceptible cells',400,190);label(stage===2?'Circulating toxin can injure kidney microvessels':'Protein synthesis is inhibited',400,525);if(stage===2){line('M590 465q-35-40-50 0t15 50q35 0 35-50Z');}
 }else if(kind==='villus'){
  for(let j=0;j<7;j++)line(`M${150+j*75} 440v-100q0-${stage===2?'35':'100'} 27-${stage===2?'35':'100'}t27 ${stage===2?'35':'100'}v100`,'process-tissue');for(let j=0;j<6;j++)microbe(180+j*75,stage===2?375:285);label(story.id==='cryptosporidiosis'?'Parasites occupy the epithelial brush border':'Virus infects mature villus cells',400,190);label(stage===2?'Reduced absorption → watery diarrhoea':'Absorptive intestinal surface',400,530);
 }else{
  tissue(360,stage===2);for(let j=0;j<5;j++)microbe(230+j*75,stage===1?300:410);if(stage===1){arrow(400,300,400,420);label('Attachment / entry at the intestinal surface',400,190);}
  else{for(let j=0;j<5;j++){ellipse(235+j*75,500,17,17,'infection-affected');ellipse(232+j*75,500,6,8);}label(story.id==='amoebiasis'?'Ulceration; possible spread through portal blood':'Tissue injury recruits inflammatory cells',400,200);label(story.id==='shigellosis'?'Colonic injury can cause bloody diarrhoea':'Inflammation changes gut function',400,565);}}
 const caption=story.steps[stage].schematic;const words=caption.split(' ');let row='',n=0;for(const word of words){if((row+' '+word).length>65){label(row,400,615+n*24,'infection-caption');n++;row=word;}else row=(row+' '+word).trim();}if(row)label(row,400,615+n*24,'infection-caption');label('Schematic · follow the source-linked explanation',400,705);
}
