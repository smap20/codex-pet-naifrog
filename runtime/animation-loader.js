async function nfReadAnimation(platform, client, directory, manifestPath) {
  if (!manifestPath) return undefined;
  try {
    const file = __NF_SAFE_JOIN__(platform, directory, manifestPath);
    if (!file) return undefined;
    const raw = await __NF_FS__.readFile(file, client);
    if (raw.length > 262144) return undefined;
    const spec = JSON.parse(raw);
    if (spec.version !== 1 || !Number.isInteger(spec.columns) || spec.columns < 1 || spec.columns > 64 ||
        !Number.isInteger(spec.rows) || spec.rows < 1 || spec.rows > 32 || spec.cellWidth !== 192 || spec.cellHeight !== 208 ||
        typeof spec.spritesheetPath !== "string" || !spec.states || !spec.states.idle) return undefined;
    const states = {};
    const allowed = ["idle", "running", "running-left", "running-right", "waiting", "review", "failed", "jumping", "waving"];
    for (const key of allowed) {
      const state = spec.states[key];
      if (!state) continue;
      if (!Number.isInteger(state.row) || state.row < 0 || state.row >= spec.rows ||
          !Array.isArray(state.frames) || state.frames.length < 1 || state.frames.length > 1024 ||
          typeof state.loop !== "boolean" ||
          (state.iterations !== undefined && (!Number.isInteger(state.iterations) || state.iterations < 1 || state.iterations > 20))) return undefined;
      if (state.frames.some(f => !Number.isInteger(f.column) || f.column < 0 || f.column >= spec.columns ||
          (f.row !== undefined && (!Number.isInteger(f.row) || f.row < 0 || f.row >= spec.rows)) ||
          !Number.isInteger(f.durationMs) || f.durationMs < 20 || f.durationMs > 10000 || (f.transitionMs !== undefined && (!Number.isInteger(f.transitionMs) || f.transitionMs < 0 || f.transitionMs > 500)))) return undefined;
      states[key] = {row: state.row, loop: state.loop, iterations: state.iterations || 1,
        frames: state.frames.map(f => ({row: f.row ?? state.row, column: f.column, durationMs: f.durationMs, transitionMs: f.transitionMs || 0}))};
    }
    if (!states.idle.loop) return undefined;
    let sustain;
    if (spec.sustain !== undefined) {
      const s=spec.sustain;
      if (!s || s.state !== 'running' || !states[s.state]?.loop ||
          !Number.isInteger(s.loopStart) || !Number.isInteger(s.loopEnd) ||
          s.loopStart < 1 || s.loopEnd <= s.loopStart ||
          s.loopEnd >= states[s.state].frames.length-1) return undefined;
      sustain={state:s.state,loopStart:s.loopStart,loopEnd:s.loopEnd};
    }
    let transitions={};
    if (spec.transitions !== undefined) {
      if (!Array.isArray(spec.transitions) || spec.transitions.length>8) return undefined;
      for (const t of spec.transitions) {
        if (!t || typeof t.from!=='string' || typeof t.to!=='string' || typeof t.animation!=='string' ||
            !states[t.from] || !states[t.to] || !states[t.animation] || states[t.animation].loop) return undefined;
        transitions[`${t.from}->${t.to}`]=t.animation;
      }
    }
    let drag;
    if (spec.drag !== undefined) {
      const d=spec.drag;
      if (!d || !['running-left','running-right'].includes(d.state) || !states[d.state] ||
          !Number.isInteger(d.apexFrame) || d.apexFrame < 1 || d.apexFrame >= states[d.state].frames.length-1) return undefined;
      drag={state:d.state,apexFrame:d.apexFrame};
    }
    const sheet = __NF_SAFE_JOIN__(platform, directory, spec.spritesheetPath);
    if (!sheet) return undefined;
    const rawImage = await __NF_FS__.readFileBase64(sheet, client);
    const encoded = typeof rawImage === "string" ? rawImage : rawImage.toString("base64");
    if (encoded.length > 48 * 1024 * 1024) return undefined;
    const bytes = Buffer.from(encoded, "base64"), info = __NF_IMAGE_INFO__(bytes);
    if (!info || info.width !== spec.columns * 192 || info.height !== spec.rows * 208) return undefined;
    return {version: 1, columns: spec.columns, rows: spec.rows, states, drag, sustain, transitions,
      disableLook: spec.disableLook !== false,
      transitionMs: Number.isFinite(spec.transitionMs) ? Math.max(0, Math.min(500, spec.transitionMs)) : 180,
      spritesheetDataUrl: `data:${info.mimeType};base64,${encoded}`};
  } catch { return undefined; }
}
