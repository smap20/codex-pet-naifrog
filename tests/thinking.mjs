import fs from 'node:fs/promises';import vm from 'node:vm';import path from 'node:path';import assert from 'node:assert/strict';
const repo=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..'),root=repo+'/runtime',out=repo+'/.test-output';
await fs.mkdir(out,{recursive:true});
const raw=JSON.parse(await fs.readFile(repo+'/pet/animation-v4.5.json','utf8'));
const runtime=await fs.readFile(root+'/animation-runtime.js','utf8');const ctx={};vm.createContext(ctx);vm.runInContext(runtime,ctx);
const spec={...raw,states:Object.fromEntries(Object.entries(raw.states).map(([k,v])=>[k,{...v,frames:v.frames.map(f=>({...f,row:f.row??v.row,transitionMs:f.transitionMs||0}))}]))};
const frames=spec.states.running.frames,config=spec.sustain,ends=[];let total=0;for(const f of frames){total+=f.durationMs;ends.push(total);}
const intro=ends[config.loopEnd],loop=ends[config.loopEnd]-ends[config.loopStart-1];
let c=ctx.nfSustainBegin(spec,0),previous=0;
for(let t=0;t<intro;t++){const f=ctx.nfSustainFrame(spec,c,'running',t);assert(f.sustainIndex>=previous&&f.sustainIndex<=49);previous=f.sustainIndex;}
for(const t of [intro,intro+1,intro+loop*5,intro+loop*1000,3600000,86400000]){const f=ctx.nfSustainFrame(spec,c,'running',t);assert(f.sustainIndex>=22&&f.sustainIndex<=49);assert.equal(f.sustainPhase,'loop');}
// Inspect every original-frame exit: partial raises reverse; established
// scratching continues in source order all the way through lowering.
let longest=0;
for(let startIndex=0;startIndex<=49;startIndex++){
 c=ctx.nfSustainBegin(spec,0);const at=(startIndex?ends[startIndex-1]:0)+2;
 const before=ctx.nfSustainFrame(spec,c,'running',at);const first=ctx.nfSustainFrame(spec,c,'waiting',at);
 assert.equal(first.sustainIndex,before.sustainIndex);let last=first.sustainIndex;let elapsed=0;
 for(;elapsed<4000;elapsed+=10){let f=ctx.nfSustainFrame(spec,c,elapsed<100?'waiting':'review',at+elapsed);if(!f)break;
  assert(startIndex<22?f.sustainIndex<=last:f.sustainIndex>=last);last=f.sustainIndex;}
 assert(elapsed<4000);assert.equal(last,startIndex<22?0:79);longest=Math.max(longest,elapsed);
}
// Resume while lowering, starting at the currently displayed pose.
c=ctx.nfSustainBegin(spec,0);ctx.nfSustainFrame(spec,c,'running',3000);ctx.nfSustainFrame(spec,c,'waiting',3000);
let exiting=ctx.nfSustainFrame(spec,c,'waiting',4000);assert(exiting&&exiting.sustainIndex>49);
let resumed=ctx.nfSustainFrame(spec,c,'running',4000);assert.equal(resumed.sustainIndex,exiting.sustainIndex);
assert(ctx.nfSustainFrame(spec,c,'running',4100).sustainIndex<resumed.sustainIndex);
assert.equal(ctx.nfSustainFrame(spec,c,'running',7000).sustainPhase,'loop');

// Execute the exact React effects with a deterministic clock and style refs.
let hooks=[],index=0,pending=[],now=0,raf=null,dirty=false,reduced=false,state='idle',hoverEnabled=false,tree;
const listeners=new Map();ctx.window={addEventListener:(n,f)=>{if(!listeners.has(n))listeners.set(n,new Set());listeners.get(n).add(f)},removeEventListener:(n,f)=>listeners.get(n)?.delete(f)};
ctx.Ger={useRef:init=>{let i=index++;return hooks[i]??=({current:init})},useState:init=>{let i=index++;hooks[i]??=({value:init});return[hooks[i].value,v=>{hooks[i].value=typeof v==='function'?v(hooks[i].value):v;dirty=true}]},useEffect:(fn,deps)=>{let i=index++,old=hooks[i];if(!old||deps.some((d,j)=>d!==old.deps[j]))pending.push(()=>{old?.cleanup?.();hooks[i]={deps,cleanup:fn()}})},createElement:(tag,props,...children)=>({tag,props,children})};
ctx.K=(...x)=>x.filter(Boolean).join(' ');ctx.Uer={Root:'pet'};ctx.VLe=()=>reduced;ctx.performance={now:()=>now};ctx.requestAnimationFrame=f=>{raf=f;return 1};ctx.cancelAnimationFrame=()=>{raf=null};
function render(){index=0;pending=[];dirty=false;tree=ctx.nfPetRenderer({source:{petId:'custom:naifrog',animationSpec:spec},state,respondToHover:hoverEnabled});for(const child of tree.children)if(!child.props.ref.current)child.props.ref.current={style:{...child.props.style}};for(const effect of pending)effect();return tree;}
function advance(t){now=t;const f=raf;raf=null;f?.(t);if(dirty)render();}
function target(s,t){advance(t);state=s;render();}
function position(){return tree.children[0].props.ref.current.style.backgroundPosition;}
function reset(){for(const h of hooks)h?.cleanup?.();hooks=[];now=0;raf=null;dirty=false;state='idle';reduced=false;hoverEnabled=false;render();}
const pos=f=>ctx.nfPosition(f,spec);
reset();target('running',1000);advance(14000);const held=position();target('waiting',14000);assert.equal(position(),held);
target('review',14100);let foundNew=false;
for(let t=14100;t<17500;t+=10){advance(t);if(position()===pos(spec.states.review.frames[0])){foundNew=true;break;}}
assert(foundNew,'latest requested state starts at frame zero after release');
// Rerendering for unrelated props while thinking must not repeat introduction.
reset();target('running',0);advance(8000);const p=position();render();assert.equal(position(),p);
// Explicit drag/hover remain immediate. They do not wait for hand lowering.
tree.props.onPointerDownCapture({button:0,pointerId:7,isPrimary:true});render();assert.equal(position(),pos(spec.states['running-right'].frames[0]));advance(12000);assert.equal(position(),pos(spec.states['running-right'].frames[52]));
reset();hoverEnabled=true;target('running',0);advance(3000);tree.props.onPointerEnter();render();assert.equal(position(),pos(spec.states.jumping.frames[0]));
tree.props.onPointerLeave();render();assert.equal(position(),pos(spec.states.running.frames[0]));
reduced=true;render();assert.equal(raf,null);target('waiting',4000);assert.equal(position(),pos(spec.states.waiting.frames[0]));
for(const h of hooks)h?.cleanup?.();for(const set of listeners.values())assert.equal(set.size,0);

// Preview uses the exact rendered frames and opacity, not a separate timeline.
reset();const demo=[];let oldState='idle',oldStart=0;
const changes=[[0,'idle'],[1000,'running'],[18000,'waiting'],[24000,'running'],[24500,'review'],[28000,'running'],[32000,'idle'],[32400,'running'],[37000,'review']];
const positions=new Map();for(const [key,a]of Object.entries(spec.states))a.frames.forEach((f,i)=>positions.set(pos(f),{...f,stateKey:key,index:i}));
for(let tick=0;tick<42*24;tick++){
 const t=tick*1000/24;const next=changes.filter(([at])=>at<=t).at(-1)[1];
 advance(t);if(next!==state){state=next;render();oldState=next;oldStart=t;}
 const layers=tree.children.map(child=>({frame:positions.get(child.props.ref.current.style.backgroundPosition),opacity:Number(child.props.ref.current.style.opacity)}));
 assert(layers[0].frame);demo.push({timeMs:t,requested:state,layers,old:ctx.nfFrameAt(spec,oldState,t-oldStart)});
}
await fs.writeFile(out+'/thinking-demo-frames.json',JSON.stringify(demo));
await fs.writeFile(out+'/thinking-test.json',JSON.stringify({passed:true,introMs:intro,loopMs:loop,maxExitMs:longest,checks:['original intro exactly once','only frames22-49 during sustained work up to24h','every-frame exit preserves current pose','early raise reverses to rest','exit finishes in original frame order','latest target begins at frame zero','resume lowering retraces same poses into loop','rerenders retain phase','drag and hover preempt immediately','reduced motion and cleanup','preview exported from exact renderer effects']},null,2));
console.log('Thinking controller and actual renderer tests passed; maximum release duration',longest,'ms');
