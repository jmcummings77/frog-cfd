// Small dependency-free SVG charts with hover tooltips.
const NS = "http://www.w3.org/2000/svg";
const ORIENT = {
  fwd: { name: "Forwards (snout first)", short: "Forwards", color: "var(--series-1)" },
  bwd: { name: "Backwards (rear first)", short: "Backwards", color: "var(--series-2)" },
};

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
const widthFor = (host) => Math.max(300, Math.min(760, (host.clientWidth || 760) - 28));

// Draw now and again whenever the container's width changes noticeably.
export function mount(host, draw) {
  if (!host) return;
  let last = -1;
  const run = () => {
    const w = host.clientWidth;
    if (w === 0 || Math.abs(w - last) < 16) return;
    last = w;
    draw(host);
  };
  new ResizeObserver(run).observe(host);
  run();
}
const narrow = (W) => W < 520;
function svgRoot(host, w, h) {
  host.querySelectorAll(".gen").forEach((n) => n.remove());
  const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", class: "gen" });
  host.appendChild(svg);
  return svg;
}
function tooltip(host) {
  const t = document.createElement("div");
  t.className = "tooltip gen";
  host.appendChild(t);
  return {
    show(html, x, y) {
      t.innerHTML = html;
      t.style.opacity = 1;
      const hw = host.clientWidth, tw = t.offsetWidth;
      t.style.left = Math.min(Math.max(4, x + 12), hw - tw - 4) + "px";
      t.style.top = y - 10 - t.offsetHeight + "px";
    },
    hide() { t.style.opacity = 0; },
  };
}
function localXY(host, evt) {
  const r = host.getBoundingClientRect();
  return [evt.clientX - r.left, evt.clientY - r.top];
}
const fmt = (v, d = 3) => (v >= 0 ? "" : "−") + Math.abs(v).toFixed(d);
function ticks(min, max, n = 5) {
  const step0 = (max - min) / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0);
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

function tableView(host, head, rows) {
  const d = document.createElement("details");
  d.className = "table-view gen";
  d.innerHTML = `<summary>Show data table</summary><div class="table-scroll"><table><thead><tr>${head
    .map((h, i) => `<th class="${i ? "num" : ""}">${h}</th>`).join("")}</tr></thead><tbody>${rows
    .map((r) => `<tr>${r.map((c, i) => `<td class="${i ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  host.appendChild(d);
}

// Horizontal bars: total Cd per orientation, pressure (solid) + friction (pale) segments.
export function dragBars(host, R) {
  const W = widthFor(host), rowH = 46, top = 8, left = narrow(W) ? 84 : 170, right = 50, H = top + rowH * 2 + 34;
  const svg = svgRoot(host, W, H);
  const tip = tooltip(host);
  const max = Math.max(R.fwd_a0.Cd[0], R.bwd_a0.Cd[0]) * 1.15;
  const x = (v) => left + (v / max) * (W - left - right);
  const ax = el("g", { class: "axis" }, svg);
  for (const t of ticks(0, max, narrow(W) ? 3 : 5)) {
    el("line", { x1: x(t), x2: x(t), y1: top, y2: top + rowH * 2, class: "gridline" }, ax);
    el("text", { x: x(t), y: top + rowH * 2 + 16, "text-anchor": "middle" }, ax).textContent = t.toFixed(2);
  }
  el("text", { x: x(max / 2), y: H - 2, "text-anchor": "middle", class: "lbl" }, svg).textContent = "Drag coefficient Cd (frontal area)";
  ["fwd", "bwd"].forEach((o, i) => {
    const r = R[o + "_a0"], y = top + i * rowH + 9, h = rowH - 18;
    el("text", { x: left - 12, y: y + h / 2 + 4, "text-anchor": "end", class: "lbl", style: "font-size:13px;fill:var(--text-primary)" }, svg)
      .textContent = narrow(W) ? ORIENT[o].short : ORIENT[o].name;
    const p = r.Cd_pressure[0], v = r.Cd_viscous[0];
    const g = el("g", {}, svg);
    // Pressure segment from the baseline, square at the baseline, rounded data end is on the friction segment.
    el("rect", { x: x(0), y, width: Math.max(0, x(p) - x(0) - 1), height: h, fill: ORIENT[o].color }, g);
    el("path", {
      d: `M${x(p) + 1},${y} H${x(p + v) - 4} a4,4 0 0 1 4,4 V${y + h - 4} a4,4 0 0 1 -4,4 H${x(p) + 1} Z`,
      fill: ORIENT[o].color, "fill-opacity": 0.4,
    }, g);
    el("text", { x: x(p + v) + 8, y: y + h / 2 + 4, class: "val" }, svg).textContent = r.Cd[0].toFixed(3);
    const hit = el("rect", { x: left, y: y - 6, width: W - left - right, height: h + 12, fill: "transparent" }, svg);
    hit.addEventListener("pointermove", (e) => {
      const [mx, my] = localXY(host, e);
      tip.show(`<b>${ORIENT[o].name}</b><br>Total C<sub>d</sub> ${r.Cd[0].toFixed(3)} <span class="muted">± ${r.Cd[1].toFixed(3)}</span><br>
        Pressure ${p.toFixed(3)} <span class="muted">(${((p / r.Cd[0]) * 100).toFixed(0)}%)</span><br>
        Skin friction ${v.toFixed(3)} <span class="muted">(${((v / r.Cd[0]) * 100).toFixed(0)}%)</span>`, mx, my);
    });
    hit.addEventListener("pointerleave", () => tip.hide());
  });
  tableView(host, ["Orientation", "Total Cd", "Pressure", "Friction", "± (std, last iters)"],
    ["fwd", "bwd"].map((o) => {
      const r = R[o + "_a0"];
      return [ORIENT[o].short, r.Cd[0].toFixed(3), r.Cd_pressure[0].toFixed(3), r.Cd_viscous[0].toFixed(3), r.Cd[1].toFixed(3)];
    }));
}

// Convergence: Cd vs iteration, crosshair tooltip.
export function convergence(host, R) {
  const W = widthFor(host), H = narrow(W) ? 220 : 260, m = { l: 40, r: 12, t: 10, b: 34 };
  const svg = svgRoot(host, W, H);
  const tip = tooltip(host);
  const series = ["fwd", "bwd"].map((o) => ({ o, ...R[o + "_a0"].hist }));
  const xmax = Math.max(...series.map((s) => s.it[s.it.length - 1]));
  const ymax = Math.ceil(Math.max(...series.flatMap((s) => s.cd.slice(Math.floor(s.cd.length / 5)))) * 1.25 * 10) / 10;
  const x = (v) => m.l + (v / xmax) * (W - m.l - m.r);
  const y = (v) => H - m.b - (Math.min(v, ymax) / ymax) * (H - m.t - m.b);
  const ax = el("g", { class: "axis" }, svg);
  for (const t of ticks(0, ymax, 4)) {
    el("line", { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), class: "gridline" }, ax);
    el("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end" }, ax).textContent = t.toFixed(1);
  }
  for (const t of ticks(0, xmax, narrow(W) ? 3 : 6)) el("text", { x: x(t), y: H - m.b + 16, "text-anchor": "middle" }, ax).textContent = t;
  el("text", { x: (W + m.l) / 2, y: H - 2, "text-anchor": "middle", class: "lbl" }, svg).textContent = "Solver iteration";
  for (const s of series) {
    el("path", {
      d: s.it.map((v, i) => `${i ? "L" : "M"}${x(v).toFixed(1)},${y(s.cd[i]).toFixed(1)}`).join(""),
      fill: "none", stroke: ORIENT[s.o].color, "stroke-width": 2, "stroke-linejoin": "round",
    }, svg);
  }
  const avgStart = R.fwd_a0.iters - R.avg_iters;
  el("rect", { x: x(avgStart), y: m.t, width: x(xmax) - x(avgStart), height: H - m.t - m.b, fill: "var(--text-muted)", "fill-opacity": 0.07 }, svg);
  el("text", { x: x(avgStart) + 6, y: m.t + 14, class: "lbl" }, svg).textContent = "averaging window";
  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: "var(--text-muted)", "stroke-dasharray": "3 3", opacity: 0 }, svg);
  const dots = series.map((s) => el("circle", { r: 4, fill: ORIENT[s.o].color, stroke: "var(--surface-1)", "stroke-width": 2, opacity: 0 }, svg));
  const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" }, svg);
  hit.addEventListener("pointermove", (e) => {
    const [mx, my] = localXY(host, e);
    const sr = svg.getBoundingClientRect();
    const sx = ((e.clientX - sr.left) * W) / sr.width;
    const it = Math.min(xmax, Math.max(0, ((sx - m.l) / (W - m.l - m.r)) * xmax));
    let html = `<b>Iteration ${Math.round(it)}</b>`;
    series.forEach((s, k) => {
      let i = s.it.findIndex((v) => v >= it); if (i < 0) i = s.it.length - 1;
      dots[k].setAttribute("cx", x(s.it[i])); dots[k].setAttribute("cy", y(s.cd[i])); dots[k].setAttribute("opacity", 1);
      html += `<br><span class="swatch" style="background:${ORIENT[s.o].color}"></span> ${ORIENT[s.o].short}: ${s.cd[i].toFixed(3)}`;
    });
    cross.setAttribute("x1", x(it)); cross.setAttribute("x2", x(it)); cross.setAttribute("opacity", 1);
    tip.show(html, mx, my);
  });
  hit.addEventListener("pointerleave", () => { tip.hide(); cross.setAttribute("opacity", 0); dots.forEach((d) => d.setAttribute("opacity", 0)); });
}

// Pressure drag from the leading vs trailing half of the body, per orientation.
export function dragSplit(host, R) {
  const parts = [["leading", "Leading half"], ["trailing", "Trailing half"]];
  const W = widthFor(host), left = narrow(W) ? 64 : 130, right = 50, top = 8, barH = 18, gap = 4, groupGap = 22;
  const groupH = 2 * barH + gap;
  const H = top + parts.length * groupH + (parts.length - 1) * groupGap + 36;
  const svg = svgRoot(host, W, H);
  const tip = tooltip(host);
  const max = Math.max(...["fwd", "bwd"].flatMap((o) => parts.map(([k]) => R[o + "_a0"].split[k]))) * 1.18;
  const x = (v) => left + (v / max) * (W - left - right);
  const ax = el("g", { class: "axis" }, svg);
  const yEnd = top + parts.length * groupH + (parts.length - 1) * groupGap;
  for (const t of ticks(0, max, narrow(W) ? 3 : 5)) {
    el("line", { x1: x(t), x2: x(t), y1: top, y2: yEnd, class: "gridline" }, ax);
    el("text", { x: x(t), y: yEnd + 16, "text-anchor": "middle" }, ax).textContent = t.toFixed(2);
  }
  el("text", { x: x(max / 2), y: H - 2, "text-anchor": "middle", class: "lbl" }, svg).textContent = "Pressure-drag contribution (Cd units)";
  parts.forEach(([k, label], gi) => {
    if (narrow(W)) label = label.replace(" half", "");
    const gy = top + gi * (groupH + groupGap);
    el("text", { x: left - 12, y: gy + groupH / 2 + 4, "text-anchor": "end", class: "lbl", style: "font-size:13px;fill:var(--text-primary)" }, svg).textContent = label;
    ["fwd", "bwd"].forEach((o, i) => {
      const v = R[o + "_a0"].split[k], y = gy + i * (barH + gap), w = x(v) - x(0);
      el("path", { d: `M${x(0)},${y} H${x(v) - 4} a4,4 0 0 1 4,4 V${y + barH - 4} a4,4 0 0 1 -4,4 H${x(0)} Z`, fill: ORIENT[o].color }, svg);
      el("text", { x: x(v) + 6, y: y + barH / 2 + 4, class: "val" }, svg).textContent = v.toFixed(3);
      const hit = el("rect", { x: left, y: y - 2, width: W - left - right, height: barH + 4, fill: "transparent" }, svg);
      hit.addEventListener("pointermove", (e) => {
        const [mx, my] = localXY(host, e);
        tip.show(`<b>${ORIENT[o].name}</b><br>${label}: ${v.toFixed(3)}<br><span class="muted">of ${R[o + "_a0"].split.total.toFixed(3)} total pressure drag</span>`, mx, my);
      });
      hit.addEventListener("pointerleave", () => tip.hide());
    });
  });
  tableView(host, ["Orientation", "Leading half", "Trailing half", "Total (surface integral)", "OpenFOAM pressure Cd"],
    ["fwd", "bwd"].map((o) => {
      const r = R[o + "_a0"];
      return [ORIENT[o].short, r.split.leading.toFixed(3), r.split.trailing.toFixed(3), r.split.total.toFixed(3), r.Cd_pressure[0].toFixed(3)];
    }));
}

// Stability: restoring moment per degree of disturbance (diverging from zero).
export function stability(host, S) {
  const rows = [];
  for (const o of ["fwd", "bwd"]) for (const axis of ["pitch", "yaw"]) if (S?.[o]?.[axis]) rows.push({ o, axis, ...S[o][axis] });
  if (!rows.length) { host.hidden = true; return; }
  const W = widthFor(host), rowH = 34, left = narrow(W) ? 118 : 200, right = 16, top = 24;
  const H = top + rowH * rows.length + 40;
  const svg = svgRoot(host, W, H);
  const tip = tooltip(host);
  const lim = Math.max(...rows.map((r) => Math.abs(r.restoring_per_deg))) * 1.35;
  const x = (v) => left + ((v + lim) / (2 * lim)) * (W - left - right);
  const ax = el("g", { class: "axis" }, svg);
  const yEnd = top + rowH * rows.length;
  for (const t of ticks(-lim, lim, narrow(W) ? 2 : 4)) {
    el("line", { x1: x(t), x2: x(t), y1: top, y2: yEnd, class: "gridline" }, ax);
    el("text", { x: x(t), y: yEnd + 15, "text-anchor": "middle" }, ax).textContent = (t * 1000).toFixed(1);
  }
  el("line", { x1: x(0), x2: x(0), y1: top - 4, y2: yEnd, stroke: "var(--text-secondary)" }, svg);
  el("text", { x: x(0) - 6, y: 12, "text-anchor": "end", class: "lbl" }, svg).textContent = "← tips over";
  el("text", { x: x(0) + 6, y: 12, class: "lbl" }, svg).textContent = "swings back →";
  rows.forEach((r, i) => {
    const y = top + i * rowH + 7, h = rowH - 14, v = r.restoring_per_deg;
    el("text", { x: left - 10, y: y + h / 2 + 4, "text-anchor": "end", class: "lbl", style: "font-size:12.5px;fill:var(--text-primary)" }, svg)
      .textContent = `${ORIENT[r.o].short} · ${r.axis}`;
    const x0 = x(0), x1 = x(v), w = Math.abs(x1 - x0), rr = Math.min(4, w), xs = Math.min(x0, x1);
    const d = v >= 0
      ? `M${xs},${y} H${xs + w - rr} a${rr},${rr} 0 0 1 ${rr},${rr} V${y + h - rr} a${rr},${rr} 0 0 1 -${rr},${rr} H${xs} Z`
      : `M${xs + w},${y} H${xs + rr} a${rr},${rr} 0 0 0 -${rr},${rr} V${y + h - rr} a${rr},${rr} 0 0 0 ${rr},${rr} H${xs + w} Z`;
    el("path", { d, fill: ORIENT[r.o].color }, svg);
    const hit = el("rect", { x: left, y: y - 6, width: W - left - right, height: h + 12, fill: "transparent" }, svg);
    hit.addEventListener("pointermove", (e) => {
      const [mx, my] = localXY(host, e);
      tip.show(`<b>${ORIENT[r.o].name}, ${r.axis}</b><br>${fmt(v * 1000, 2)} ×10⁻³ per degree<br>
        <span class="muted">${v > 0 ? "Restoring: turns back into the wind" : "Destabilising: a nudge grows"}</span>`, mx, my);
    });
    hit.addEventListener("pointerleave", () => tip.hide());
  });
  el("text", { x: (left + W - right) / 2, y: yEnd + 30, "text-anchor": "middle", class: "lbl" }, svg)
    .textContent = narrow(W) ? "" : "Moment-coefficient change per degree (×10⁻³)";
  tableView(host, ["Case", "Restoring per degree", "ΔCm (5°)", "± (std)", "Neutral point (mm behind CG)"],
    rows.map((r) => [`${ORIENT[r.o].short} · ${r.axis}`, fmt(r.restoring_per_deg, 5), fmt(r.dCm, 5), r.dCm_std.toFixed(5), fmt(r.neutral_point_mm, 1)]));
}

// Neutral points on a body-length strip: where the disturbance force acts, relative to the CG.
export function neutralPoints(host, S, L_mm) {
  if (!S) { host.hidden = true; return; }
  const W = widthFor(host), left = narrow(W) ? 76 : 110, right = 20, rowH = 66, top = 12;
  const H = top + rowH * 2 + 34;
  const svg = svgRoot(host, W, H);
  const tip = tooltip(host);
  const all = ["fwd", "bwd"].flatMap((o) => ["pitch", "yaw"].map((a) => S[o]?.[a]?.neutral_point_mm ?? 0));
  const span = Math.max(L_mm * 0.75, ...all.map((v) => Math.abs(v) + 6));
  const x = (mm) => left + ((mm + span) / (2 * span)) * (W - left - right);
  ["fwd", "bwd"].forEach((o, i) => {
    const yc = top + i * rowH + rowH / 2;
    el("text", { x: left - 10, y: yc + 4, "text-anchor": "end", class: "lbl", style: "font-size:12.5px;fill:var(--text-primary)" }, svg).textContent = ORIENT[o].short;
    // body extent: leading end at -L/2 side (left), trailing end right; body spans ~±L/2 about the CG
    el("rect", { x: x(-L_mm / 2), y: yc - 9, width: x(L_mm / 2) - x(-L_mm / 2), height: 18, rx: 9, fill: "var(--frog)", "fill-opacity": 0.35 }, svg);
    el("text", { x: x(-L_mm / 2) + 4, y: yc + 24, class: "lbl" }, svg).textContent = o === "fwd" ? "snout (leading)" : "rear (leading)";
    el("text", { x: x(L_mm / 2) - 4, y: yc + 24, class: "lbl", "text-anchor": "end" }, svg).textContent = o === "fwd" ? "rear" : "snout";
    el("line", { x1: x(0), x2: x(0), y1: yc - 14, y2: yc + 14, stroke: "var(--text-primary)", "stroke-width": 2 }, svg);
    el("circle", { cx: x(0), cy: yc, r: 4, fill: "var(--surface-1)", stroke: "var(--text-primary)", "stroke-width": 2 }, svg);
    ["pitch", "yaw"].forEach((a, k) => {
      const r = S[o]?.[a]; if (!r) return;
      const mx = x(r.neutral_point_mm), my = yc + (k ? 6 : -6);
      if (a === "pitch")
        el("path", { d: `M${mx},${my - 7} l6,10 h-12 Z`, fill: ORIENT[o].color, stroke: "var(--surface-1)", "stroke-width": 2 }, svg);
      else
        el("rect", { x: mx - 5, y: my - 5, width: 10, height: 10, fill: ORIENT[o].color, stroke: "var(--surface-1)", "stroke-width": 2 }, svg);
      const hit = el("circle", { cx: mx, cy: my, r: 12, fill: "transparent" }, svg);
      hit.addEventListener("pointermove", (e) => {
        const [px, py] = localXY(host, e);
        const behind = r.neutral_point_mm > 0;
        tip.show(`<b>${ORIENT[o].name}, ${a} neutral point</b><br>${Math.abs(r.neutral_point_mm).toFixed(1)} mm ${behind ? "behind" : "ahead of"} the centre of mass<br>
          <span class="muted">${behind ? "Behind the CG, so the frog weathervanes" : "Ahead of the CG, so a nudge grows"}</span>`, px, py);
      });
      hit.addEventListener("pointerleave", () => tip.hide());
    });
  });
  const axY = top + rowH * 2 + 6;
  for (const t of ticks(-span, span, narrow(W) ? 4 : 6)) {
    el("line", { x1: x(t), x2: x(t), y1: axY, y2: axY + 4, stroke: "var(--border)" }, svg);
    el("text", { x: x(t), y: axY + 16, "text-anchor": "middle", class: "lbl" }, svg).textContent = t === 0 ? "CG" : `${t > 0 ? "+" : "−"}${Math.abs(t)}`;
  }
  el("line", { x1: x(-span), x2: x(span), y1: axY, y2: axY, stroke: "var(--border)" }, svg);
  el("text", { x: x(span), y: axY + 30, "text-anchor": "end", class: "lbl" }, svg).textContent = "mm from centre of mass";
  const lg = document.createElement("div");
  lg.className = "legend-row gen";
  lg.innerHTML = `<span>▲ pitch neutral point</span><span>■ yaw neutral point</span><span>○ centre of mass</span>`;
  host.insertBefore(lg, svg);
}
