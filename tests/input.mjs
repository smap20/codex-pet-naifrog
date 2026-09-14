import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const code=fs.readFileSync(new URL('../runtime/input-bridge.js',import.meta.url),'utf8');
const channels=[];
class BroadcastChannel{constructor(){channels.push(this)}postMessage(data){for(const c of channels)if(c!==this)c.onmessage?.({data:structuredClone(data)})}}
const a={BroadcastChannel},b={BroadcastChannel};vm.createContext(a);vm.createContext(b);vm.runInContext(code,a);vm.runInContext(code,b);a.nfInputInit();b.nfInputInit();
const t={hostId:'local',threadId:'test',entityKey:'turn',itemId:'question'};
a.nfInputChange('open',t);assert.equal(b.nfInputState.pending.length,1);
a.nfInputChange('type',t);assert.equal(b.nfInputState.sequence,1);
a.nfInputChange('type',t);assert.equal(b.nfInputState.sequence,1);
a.nfInputChange('close',t);assert.equal(b.nfInputState.pending.length,0);
a.nfInputChange('type',t);assert.equal(b.nfInputState.sequence,1);
a.nfInputChange('open',t,['next']);a.nfInputChange('close',t,['next']);assert.equal(b.nfInputState.pending.length,0);
console.log('Cross-window waiting, first edit, no repeat on typing, submit/skip cleanup passed');
a.nfInputChange('sync',t,['unanswered']);assert.equal(b.nfInputState.pending.length,1);
a.nfInputChange('type',{...t,itemId:'unanswered'});assert.equal(b.nfInputState.pending.length,2);
a.nfInputChange('sync',t,[]);assert.equal(b.nfInputState.pending.length,0);
a.nfInputChange('sync',t,[]);assert.equal(b.nfInputState.pending.length,0);
const other={...t,entityKey:'other-turn'};a.nfInputChange('sync',other,['live']);a.nfInputChange('sync',t,[]);assert.equal(b.nfInputState.pending.length,1);a.nfInputChange('sync',other,[]);assert.equal(b.nfInputState.pending.length,0);
console.log('Finished/unanswered turns, removed questions and typing markers clear; other live turns preserved');
