// Interactive 3D frog: surface pressure + animated streamline particles.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const CP_STOPS = [
  [-1.0, [0x18, 0x4f, 0x95]],
  [-0.5, [0x5f, 0x9f, 0xea]],
  [0.0, [0xe8, 0xe7, 0xe2]],
  [0.5, [0xec, 0x83, 0x83]],
  [1.0, [0xb3, 0x2b, 0x2b]],
];
const SPEED_STOPS = [
  [0.0, [0xcd, 0xe2, 0xfb]],
  [0.6, [0x6d, 0xa7, 0xec]],
  [1.0, [0x2a, 0x78, 0xd6]],
  [1.3, [0x10, 0x42, 0x81]],
];

function ramp(stops, v) {
  if (v <= stops[0][0]) return stops[0][1];
  for (let i = 1; i < stops.length; i++) {
    if (v <= stops[i][0]) {
      const [a, ca] = stops[i - 1], [b, cb] = stops[i];
      const f = (v - a) / (b - a);
      return ca.map((c, k) => c + (cb[k] - c) * f);
    }
  }
  return stops[stops.length - 1][1];
}
export const cpColor = (v) => ramp(CP_STOPS, v);

export async function initViewer(root, { results }) {
  const [frog, lines] = await Promise.all([
    fetch("data/frog.json").then((r) => r.json()),
    fetch("data/streamlines.json").then((r) => r.json()),
  ]);
  const canvas = root.querySelector("canvas");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 1, 2000);
  camera.up.set(0, 0, 1);
  camera.position.set(-62, -88, 34);
  const controls = new OrbitControls(camera, canvas);
  controls.target.set(-6, 0, -1);
  controls.enableDamping = true;
  controls.minDistance = 40;
  controls.maxDistance = 400;
  // Wheel zoom only after the viewer is clicked, so the page still scrolls past it.
  controls.enableZoom = false;
  canvas.addEventListener("pointerdown", () => { controls.enableZoom = true; });
  root.addEventListener("pointerleave", () => { controls.enableZoom = false; });

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8a80, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(-40, -60, 120);
  scene.add(sun);

  // Frog mesh
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(frog.positions, 3));
  geo.setIndex(frog.indices);
  geo.computeVertexNormals();
  const nV = frog.positions.length / 3;
  const colors = new Float32Array(nV * 3);
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  const frogMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.0 });
  scene.add(new THREE.Mesh(geo, frogMat));

  // Streamlines: faint lines + moving particles
  const PER_LINE = 22;
  const lineGroup = new THREE.Group();
  scene.add(lineGroup);
  const ptsGeo = new THREE.BufferGeometry();
  let tracks = [];
  // Round particle sprite
  const dot = document.createElement("canvas");
  dot.width = dot.height = 64;
  const dctx = dot.getContext("2d");
  const grad = dctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.55, "rgba(255,255,255,1)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  dctx.fillStyle = grad;
  dctx.fillRect(0, 0, 64, 64);
  const ptsMat = new THREE.PointsMaterial({
    size: 1.4, vertexColors: true, sizeAttenuation: true, transparent: true, opacity: 0.95,
    map: new THREE.CanvasTexture(dot), alphaTest: 0.05, depthWrite: false,
  });
  const points = new THREE.Points(ptsGeo, ptsMat);
  scene.add(points);

  const state = { orient: "fwd", color: "cp", flow: true };
  const LOOP_MS = 22; // physical milliseconds per animation loop

  function applyColors() {
    const cp = frog["cp_" + state.orient];
    const green = [0x6f, 0xbf, 0x4a];
    for (let i = 0; i < nV; i++) {
      const c = state.color === "cp" ? cpColor(cp[i]) : green;
      colors[3 * i] = (c[0] / 255) ** 2.2;
      colors[3 * i + 1] = (c[1] / 255) ** 2.2;
      colors[3 * i + 2] = (c[2] / 255) ** 2.2;
    }
    geo.attributes.color.needsUpdate = true;
    root.querySelector(".legend").hidden = state.color !== "cp";
  }

  function buildLines() {
    lineGroup.clear();
    tracks = lines[state.orient].map((l) => {
      const p = l.p;
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
      const lineMat = new THREE.LineBasicMaterial({ color: 0x7f8c99, transparent: true, opacity: 0.22 });
      lineGroup.add(new THREE.Line(g, lineMat));
      return { ...l, phase: Math.random() * LOOP_MS };
    });
    const n = tracks.length * PER_LINE;
    ptsGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    ptsGeo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  }

  function updateParticles(tNow) {
    const pos = ptsGeo.attributes.position.array;
    const col = ptsGeo.attributes.color.array;
    let k = 0;
    for (const l of tracks) {
      const T = l.t, P = l.p, S = l.s, tEnd = T[T.length - 1];
      for (let j = 0; j < PER_LINE; j++) {
        const t = (tNow + l.phase + (j * LOOP_MS) / PER_LINE) % LOOP_MS;
        if (t > tEnd) { pos[3 * k] = pos[3 * k + 1] = pos[3 * k + 2] = 1e5; k++; continue; }
        let lo = 0, hi = T.length - 1;
        while (hi - lo > 1) { const m = (lo + hi) >> 1; if (T[m] <= t) lo = m; else hi = m; }
        const f = (t - T[lo]) / Math.max(1e-9, T[hi] - T[lo]);
        for (let a = 0; a < 3; a++) pos[3 * k + a] = P[3 * lo + a] + (P[3 * hi + a] - P[3 * lo + a]) * f;
        const c = ramp(SPEED_STOPS, S[lo]);
        col[3 * k] = (c[0] / 255) ** 2.2; col[3 * k + 1] = (c[1] / 255) ** 2.2; col[3 * k + 2] = (c[2] / 255) ** 2.2;
        k++;
      }
    }
    ptsGeo.attributes.position.needsUpdate = true;
    ptsGeo.attributes.color.needsUpdate = true;
  }

  function readout() {
    const r = results.cases[state.orient + "_a0"];
    const el = root.querySelector(".readout");
    if (!r) { el.hidden = true; return; }
    el.innerHTML = `${state.orient === "fwd" ? "Snout first" : "Rear first"}<br>C<sub>d</sub> <b>${r.Cd[0].toFixed(3)}</b>`;
  }

  function setOrient(o) {
    state.orient = o;
    applyColors();
    buildLines();
    readout();
  }

  root.querySelectorAll("[data-orient]").forEach((b) =>
    b.addEventListener("click", () => {
      root.querySelectorAll("[data-orient]").forEach((x) => x.setAttribute("aria-pressed", x === b));
      setOrient(b.dataset.orient);
    }));
  root.querySelectorAll("[data-color]").forEach((b) =>
    b.addEventListener("click", () => {
      root.querySelectorAll("[data-color]").forEach((x) => x.setAttribute("aria-pressed", x === b));
      state.color = b.dataset.color;
      applyColors();
    }));
  root.querySelectorAll("[data-flow]").forEach((b) =>
    b.addEventListener("click", () => {
      root.querySelectorAll("[data-flow]").forEach((x) => x.setAttribute("aria-pressed", x === b));
      state.flow = b.dataset.flow === "on";
      points.visible = lineGroup.visible = state.flow;
    }));

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas);

  setOrient("fwd");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const t0 = performance.now();
  renderer.setAnimationLoop((now) => {
    controls.update();
    // 1 real second = 4 ms of physical time (250x slow motion).
    if (state.flow) updateParticles(reduce ? 8 : ((now - t0) / 1000) * 4);
    renderer.render(scene, camera);
  });
}
