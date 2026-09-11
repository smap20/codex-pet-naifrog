// Optional per-pet extension. No changes to the built-in animation tables.
function nfFrameAt(spec, state, elapsed) {
  const stateKey = spec.states[state] ? state : "idle";
  const action = spec.states[stateKey];
  const length = action.frames.reduce((n, f) => n + f.durationMs, 0);
  if (!action.loop && elapsed >= length * (action.iterations || 1)) {
    return nfFrameAt(spec, "idle", elapsed - length * (action.iterations || 1));
  }
  let remaining = Math.max(0, elapsed) % length;
  for (const frame of action.frames) {
    if (remaining < frame.durationMs) return {row: frame.row ?? action.row, column: frame.column, stateKey, transitionMs: frame.transitionMs || 0};
    remaining -= frame.durationMs;
  }
  return {row: action.frames[0].row ?? action.row, column: action.frames[0].column, stateKey};
}
function nfPosition(frame, spec) {
  return `${spec.columns === 1 ? 0 : frame.column / (spec.columns - 1) * 100}% ${spec.rows === 1 ? 0 : frame.row / (spec.rows - 1) * 100}%`;
}
function nfPetRenderer(props) {
  const {source, className, state = "idle", respondToHover = false, lookFrame} = props;
  const spec = source.animationSpec;
  const [hovered, setHovered] = Ger.useState(false);
  const reducedMotion = VLe();
  const current = Ger.useRef(null);
  const previous = Ger.useRef(null);
  const snapshot = Ger.useRef(null);
  const drag = Ger.useRef(null);
  const pointer = Ger.useRef(null);
  const [dragActive,setDragActive] = Ger.useState(false);
  const action = dragActive ? '$drag' : respondToHover && hovered ? "jumping" : state;
  Ger.useEffect(() => {
    if (!spec.drag) return;
    const release = event => {
      if (pointer.current === null || (event.type !== 'blur' && event.pointerId !== pointer.current)) return;
      pointer.current = null;
      if (drag.current) drag.current.pressed = false;
      if (reducedMotion) {drag.current=null;setDragActive(false);}
    };
    const types=['pointerup','pointercancel','lostpointercapture','blur'];
    for(const type of types)window.addEventListener(type,release,true);
    return () => {for(const type of types)window.removeEventListener(type,release,true);};
  },[spec,reducedMotion]);
  Ger.useEffect(() => {
    const node = current.current, old = previous.current;
    if (!node || !old) return;
    const before = snapshot.current;
    const start = performance.now();
    const fade = reducedMotion ? 0 : spec.transitionMs;
    old.style.backgroundPosition = before ? before.position : "0% 0%";
    old.style.backgroundImage = before ? before.image : "none";
    let raf, transitionStart = start, hasPrevious = Boolean(before), lastState = before?.stateKey, lastFrame = null, activeFade = fade;
    const draw = now => {
      const elapsed = now - start;
      let dragged = action === '$drag' && drag.current ? nfDragFrame(spec,drag.current,now) : null;
      if (action === '$drag' && !dragged) {
        drag.current=null;setDragActive(false);
        return;
      }
      const frame = dragged || (!spec.disableLook && lookFrame
        ? {row: lookFrame.rowIndex, column: lookFrame.columnIndex, stateKey: "look"}
        : nfFrameAt(spec, action, reducedMotion ? 0 : elapsed));
      const position = nfPosition(frame, spec);
      const frameId = `${frame.stateKey}:${frame.row}:${frame.column}`;
      const sourceCut = !reducedMotion && frame.transitionMs && frameId !== lastFrame;
      if (((lastState !== undefined && frame.stateKey !== lastState) || sourceCut) && snapshot.current) {
        activeFade = sourceCut ? frame.transitionMs : fade;
        old.style.backgroundPosition = snapshot.current.position;
        old.style.backgroundImage = snapshot.current.image;
        transitionStart = now;
        hasPrevious = true;
      }
      lastState = frame.stateKey;
      lastFrame = frameId;
      node.style.backgroundPosition = position;
      const progress = hasPrevious && activeFade ? Math.min(1, (now - transitionStart) / activeFade) : 1;
      node.style.opacity = String(progress);
      old.style.opacity = String(1 - progress);
      snapshot.current = {row: frame.row, stateKey: frame.stateKey, position, image: node.style.backgroundImage};
      if (!reducedMotion) raf = requestAnimationFrame(draw);
    };
    draw(start);
    return () => cancelAnimationFrame(raf);
  }, [spec, action, reducedMotion, spec.disableLook ? null : lookFrame]);
  const layer = {
    position: "absolute", inset: 0, backgroundImage: `url(${spec.spritesheetDataUrl})`,
    backgroundSize: `${spec.columns * 100}% ${spec.rows * 100}%`,
    backgroundRepeat: "no-repeat", imageRendering: "auto", pointerEvents: "none"
  };
  return Ger.createElement("div", {
    className: K(Uer.Root, className),
    "data-codex-pet-id": source.petId,
    "data-codex-pet-state": action,
    "data-local-animation-version": "1",
    "aria-hidden": "true",
    onPointerEnter: () => respondToHover && setHovered(true),
    onPointerLeave: () => respondToHover && setHovered(false),
    onPointerDownCapture: event => {
      if (!spec.drag || event.button !== 0 || event.isPrimary === false || pointer.current !== null) return;
      pointer.current=event.pointerId;
      if (drag.current) drag.current.pressed=true;
      else drag.current=nfDragBegin(spec,performance.now());
      setDragActive(true);
    },
    style: {position: "relative", backgroundImage: "none", imageRendering: "auto"}
  }, Ger.createElement("div", {ref: current, style: {...layer}}),
     Ger.createElement("div", {ref: previous, style: {...layer, opacity: 0}}));
}

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
