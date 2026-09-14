// Only question identifiers and interaction counters cross windows, never answers.
var nfInputChannel, nfInputState={pending:[],sequence:0}, nfInputListeners=new Set();
function nfInputInit(){
 if(nfInputChannel||typeof BroadcastChannel==='undefined')return;
 try{nfInputChannel=new BroadcastChannel('naifrog-input-v1');}catch(error){console.warn('[naifrog] input channel unavailable',error);return;}
 nfInputChannel.onmessage=({data})=>{
  if(data?.kind==='query'){if(!nfInputState.pending.length)return;nfInputChannel.postMessage({kind:'state',value:nfInputState});return;}
  if(data?.kind!=='state'||!Array.isArray(data.value?.pending)||!Number.isInteger(data.value.sequence))return;
  nfInputState=data.value;for(const f of nfInputListeners)f(nfInputState);
 };
 nfInputChannel.postMessage({kind:'query'});
}
function nfQuestionKey(t,id=t.itemId){return JSON.stringify([t.hostId,t.threadId,t.entityKey,id]);}
function nfInputChange(kind,t,ids){
 nfInputInit();let pending=nfInputState.pending,sequence=nfInputState.sequence;
 const keys=(ids||[t.itemId]).map(id=>nfQuestionKey(t,id));
 if(kind==='sync'){
  const matches=k=>{try{const a=JSON.parse(k.startsWith('typed:')?k.slice(6):k);return a[0]===t.hostId&&a[1]===t.threadId&&a[2]===t.entityKey;}catch{return false;}};
  pending=pending.filter(k=>!matches(k)||keys.includes(k)||keys.some(id=>k==='typed:'+id));
  pending=[...pending,...keys.filter(k=>!pending.includes(k))];
 }
 if(kind==='open')pending=[...pending,...keys.filter(k=>!pending.includes(k))];
 if(kind==='close')pending=pending.filter(k=>!keys.includes(k));
 if(kind==='type'&&keys.some(k=>pending.includes(k))){
  // Mark the question once; subsequent keystrokes never restart the laugh.
  const markers=keys.map(k=>'typed:'+k);
  if(!markers.some(k=>pending.includes(k))){sequence++;pending=[...pending,...markers];}
 }
 if(kind==='close')pending=pending.filter(k=>!keys.map(k=>'typed:'+k).includes(k));
 console.debug('[naifrog] question event',kind,'pending',pending.length,'sequence',sequence);
 nfInputState={pending,sequence};for(const f of nfInputListeners)f(nfInputState);
 nfInputChannel?.postMessage({kind:'state',value:nfInputState});
}
function nfUseInput(){
 const [value,setValue]=__NF_REACT__.useState(nfInputState);
 __NF_REACT__.useEffect(()=>{nfInputInit();nfInputListeners.add(setValue);setValue(nfInputState);return()=>nfInputListeners.delete(setValue);},[]);
 return value;
}
