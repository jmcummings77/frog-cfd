import { initViewer } from "./viewer.js";
import { dragBars, convergence, dragSplit } from "./charts.js";
import { initRace } from "./race.js";

const results = await fetch("data/results.json").then((r) => r.json());
const props = results.props;

// Fill inline numbers: <span data-r="fwd_a0.Cd.0" data-d="3">
document.querySelectorAll("[data-r]").forEach((n) => {
  const v = n.dataset.r.split(".").reduce((o, k) => (o == null ? o : o[k]), results.cases);
  if (typeof v === "number") n.textContent = v.toFixed(+(n.dataset.d ?? 3));
});

const fwd = results.cases.fwd_a0, bwd = results.cases.bwd_a0;
const vt = (cd, m = 0.004) => Math.sqrt((2 * m * 9.81) / (1.2 * cd * props.frontal_area));
const diff = (bwd.Cd[0] - fwd.Cd[0]) / fwd.Cd[0];
document.querySelectorAll("[data-calc]").forEach((n) => {
  const f = {
    vt_fwd: () => vt(fwd.Cd[0]).toFixed(1),
    vt_bwd: () => vt(bwd.Cd[0]).toFixed(1),
    cd_diff_pct: () => Math.abs(diff * 100).toFixed(0),
    speed_diff_pct: () => Math.abs((Math.max(vt(fwd.Cd[0]), vt(bwd.Cd[0])) / Math.min(vt(fwd.Cd[0]), vt(bwd.Cd[0])) - 1) * 100).toFixed(1),
    area_cm2: () => (props.frontal_area * 1e4).toFixed(2),
    re: () => Math.round(results.Re).toLocaleString("en-US"),
    vt_fwd_kmh: () => (vt(fwd.Cd[0]) * 3.6).toFixed(0),
    vt_bwd_kmh: () => (vt(bwd.Cd[0]) * 3.6).toFixed(0),
  }[n.dataset.calc];
  if (f) n.textContent = f();
});

dragBars(document.getElementById("chart-drag"), results.cases);
dragSplit(document.getElementById("chart-split"), results.cases);
convergence(document.getElementById("chart-conv"), { ...results.cases, avg_iters: results.avg_iters });
initRace(document.getElementById("race"), { results, props });
initViewer(document.getElementById("viewer"), { results }).catch((e) => {
  document.querySelector("#viewer .hint").textContent = "3D view unavailable: " + e.message;
});

// Theme toggle (wins over OS preference both ways)
const tbtn = document.querySelector(".theme-toggle");
tbtn?.addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = cur === "dark" ? "light" : "dark";
  try { localStorage.setItem("theme", document.documentElement.dataset.theme); } catch {}
  window.dispatchEvent(new Event("themechange"));
});
