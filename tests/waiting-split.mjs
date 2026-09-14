import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url),ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(new URL('runtime/animation-runtime.js',root),'utf8'),ctx);
const spec=JSON.parse(fs.readFileSync(new URL('pet/animation-v4.6.json',root)));
const q=ctx.nfFrameAt(spec,'$question',0);assert.equal(q.row,15);assert.equal(q.column,9);
for(const t of [0,500,5000,60000])assert.deepEqual(ctx.nfFrameAt(spec,'$question',t),q);
assert.equal(spec.states.waiting.frames.length,46);assert.notDeepEqual(ctx.nfFrameAt(spec,'waiting',0),q);assert.equal(ctx.nfFrameAt(spec,'waiting',0).stateKey,'waiting');
console.log('Question holds side-eye independently of the restored 46-frame ordinary waiting animation');
