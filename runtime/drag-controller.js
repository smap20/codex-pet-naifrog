// Sample only original float frames. Pointer ownership, not move frequency,
// controls suspension. The same timeline survives left/right direction changes.
function nfDragSample(spec, control, now) {
  const frames = spec.states[spec.drag.state].frames;
  let elapsed = Math.max(0, now-control.start), index=control.indices[0];
  for (const i of control.indices) {
    index=i;
    if (elapsed < frames[i].durationMs) return {index,done:false};
    elapsed-=frames[i].durationMs;
  }
  return {index,done:true};
}
function nfDragRange(from,to) {
  return Array.from({length:Math.abs(to-from)+1},(_,i)=>from+(to>=from?i:-i));
}
function nfDragBegin(spec,now) {
  return {pressed:true,wasPressed:true,phase:'rise',start:now,
    indices:nfDragRange(0,spec.drag.apexFrame)};
}
function nfDragFrame(spec,control,now) {
  const frames=spec.states[spec.drag.state].frames,apex=spec.drag.apexFrame;
  let sample=nfDragSample(spec,control,now);
  if(control.pressed!==control.wasPressed) {
    control.wasPressed=control.pressed;
    control.start=now;
    if(control.pressed) {
      control.phase='rise';control.indices=nfDragRange(sample.index,apex);
    } else {
      control.phase='fall';
      // Early release reverses the partial lift; release from the summit uses
      // the original landing sequence. Both start at the displayed pose.
      control.indices=sample.index<apex?nfDragRange(sample.index,0):nfDragRange(sample.index,frames.length-1);
    }
    sample={index:control.indices[0],done:false};
  }
  if(sample.done&&control.pressed)control.phase='hold';
  if(sample.done&&!control.pressed)return null;
  return {...frames[sample.index],stateKey:'drag',dragIndex:sample.index,phase:control.phase};
}
