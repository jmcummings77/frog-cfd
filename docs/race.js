// Two frogs dropped from a tree: v(t) = vt tanh(g t / vt), with vt from the CFD drag.
const G = 9.81, RHO = 1.2;

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function drawFrog(ctx, x, y, s, headDown, color) {
  // Top-down tucked frog, body axis vertical. Head toward +y when headDown.
  ctx.save();
  ctx.translate(x, y);
  if (!headDown) ctx.rotate(Math.PI);
  ctx.fillStyle = color;
  ctx.strokeStyle = "rgba(0,0,0,.25)";
  ctx.lineWidth = 1;
  const leg = (sx) => {
    ctx.beginPath(); ctx.ellipse(sx * 0.42 * s, -0.12 * s, 0.17 * s, 0.36 * s, sx * 0.12, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  };
  leg(1); leg(-1);
  ctx.beginPath(); ctx.ellipse(0, -0.05 * s, 0.36 * s, 0.5 * s, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(0, 0.42 * s, 0.33 * s, 0.3 * s, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  for (const sx of [1, -1]) {
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(sx * 0.22 * s, 0.5 * s, 0.1 * s, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#1b1b1b"; ctx.beginPath(); ctx.arc(sx * 0.23 * s, 0.53 * s, 0.05 * s, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}

export function initRace(root, { results, props }) {
  const canvas = root.querySelector("canvas");
  const ctx = canvas.getContext("2d");
  const H_DROP = 40; // metres, a tall alder or Douglas fir branch
  const mass = 0.004;
  const A = props.frontal_area;
  const lanes = ["fwd", "bwd"].map((o) => {
    const cd = results.cases[o + "_a0"].Cd[0];
    const vt = Math.sqrt((2 * mass * G) / (RHO * cd * A));
    const tLand = (vt / G) * Math.acosh(Math.exp((G * H_DROP) / (vt * vt)));
    return { o, cd, vt, tLand, label: o === "fwd" ? "Snout first" : "Rear first", color: o === "fwd" ? "--series-1" : "--series-2" };
  });
  const pos = (l, t) => Math.min(H_DROP, ((l.vt * l.vt) / G) * Math.log(Math.cosh((G * t) / l.vt)));
  const vel = (l, t) => (t >= l.tLand ? 0 : l.vt * Math.tanh((G * t) / l.vt));

  let speed = 1, t = 0, playing = false, last = 0;
  const btn = root.querySelector("[data-play]");
  root.querySelectorAll("[data-speed]").forEach((b) => b.addEventListener("click", () => {
    root.querySelectorAll("[data-speed]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    speed = +b.dataset.speed;
  }));
  btn.addEventListener("click", () => {
    if (t >= Math.max(...lanes.map((l) => l.tLand))) t = 0;
    playing = !playing; btn.textContent = playing ? "Pause" : "Drop the frogs";
    last = performance.now();
    if (playing) requestAnimationFrame(tick);
  });

  function draw() {
    const dpr = Math.min(devicePixelRatio, 2);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== w * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const top = 80, bottom = h - 30, left = 44;
    const yOf = (m) => top + (m / H_DROP) * (bottom - top);
    ctx.font = "11px Inter, system-ui, sans-serif";
    ctx.fillStyle = css("--text-muted");
    ctx.strokeStyle = css("--grid");
    for (let m = 0; m <= H_DROP; m += 10) {
      ctx.beginPath(); ctx.moveTo(left, yOf(m)); ctx.lineTo(w - 8, yOf(m)); ctx.stroke();
      ctx.fillText(`${H_DROP - m} m`, 4, yOf(m) + 4);
    }
    ctx.fillStyle = css("--accent"); ctx.fillRect(left, bottom, w - left - 8, 4);
    const laneW = (w - left - 8) / lanes.length;
    lanes.forEach((l, i) => {
      const cx = left + laneW * (i + 0.5);
      const col = css(l.color);
      ctx.fillStyle = css("--text-primary");
      ctx.font = "600 13px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(l.label, cx, 16);
      // Seat the frog on its leading edge (snout tip or rear), so it lands on the ground line.
      const S = 34, lead = (l.o === "fwd" ? 0.72 : 0.55) * S;
      const y = yOf(pos(l, t)) - lead;
      // speed streaks
      const v = vel(l, t);
      ctx.strokeStyle = col; ctx.globalAlpha = 0.35; ctx.lineWidth = 2;
      for (const dx of [-8, 0, 8]) { ctx.beginPath(); ctx.moveTo(cx + dx, y - 22); ctx.lineTo(cx + dx, y - 22 - v * 2.2); ctx.stroke(); }
      ctx.globalAlpha = 1;
      drawFrog(ctx, cx, y, S, l.o === "fwd", css("--frog"));
      ctx.font = "12px Inter, system-ui, sans-serif";
      ctx.fillStyle = css("--text-secondary");
      const done = t >= l.tLand;
      const txt = done ? `landed at ${l.tLand.toFixed(2)} s` : `${v.toFixed(1)} m/s`;
      ctx.textAlign = "center";
      ctx.fillText(txt, cx, 34);
      ctx.textAlign = "left";
    });
    ctx.textAlign = "left";
    ctx.fillStyle = css("--text-muted");
    ctx.fillText(`t = ${t.toFixed(2)} s`, w - 80, h - 8);
  }
  function tick(now) {
    t += ((now - last) / 1000) * speed;
    last = now;
    const end = Math.max(...lanes.map((l) => l.tLand));
    if (t >= end) { t = end; playing = false; btn.textContent = "Drop again"; }
    draw();
    if (playing) requestAnimationFrame(tick);
  }
  new ResizeObserver(draw).observe(canvas);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  window.addEventListener("themechange", draw);
  const [first, second] = [...lanes].sort((a, b) => a.tLand - b.tLand);
  const gapCm = (H_DROP - pos(second, first.tLand)) * 100;
  root.querySelector(".race-summary").innerHTML = lanes.map((l) =>
    `<span><span class="swatch" style="background:var(${l.color})"></span> ${l.label}: terminal velocity <b>${l.vt.toFixed(1)} m/s</b>, lands in ${l.tLand.toFixed(2)} s</span>`).join(" &nbsp; ")
    + `<br>${first.label} wins. When it lands, the other frog is still <b>${gapCm.toFixed(0)} cm</b> up.`;
  draw();
  return { redraw: draw };
}
