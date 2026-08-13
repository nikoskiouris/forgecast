/* global maplibregl */
const BASE = new URL("./", window.location.href);
const STYLES = [
  "https://tiles.openfreemap.org/styles/dark",
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
];
const DEMAND = [-77.04, 38.91];

const asof = document.getElementById("asof");
const listEl = document.getElementById("list");
const statusEl = document.getElementById("status");
const notesEl = document.getElementById("notes");
const briefEmpty = document.getElementById("brief-empty");
const briefBody = document.getElementById("brief-body");
const briefPanel = document.getElementById("brief");
const boot = document.getElementById("boot");
const bootSub = document.getElementById("boot-sub");

let bundle = null;
let map = null;
let markers = [];
let selectedId = null;

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function pct(x) {
  return Math.round((x || 0) * 100) + "%";
}

function band(p) {
  if (p >= 0.28) return "high";
  if (p >= 0.16) return "mid";
  return "low";
}

function dataUrl(name) {
  return new URL("data/" + name, BASE).toString();
}

async function loadBundle() {
  const res = await fetch(dataUrl("demo.json"));
  if (res.ok) return res.json();
  const live = await fetch("/api/map");
  if (!live.ok) throw new Error("no demo data");
  const snap = await live.json();
  return {
    default_as_of: snap.as_of,
    horizon_days: snap.horizon_days,
    dates: [snap.as_of],
    snapshots: { [snap.as_of]: snap },
  };
}

function greatCircle(from, to, steps) {
  const toRad = (d) => (d * Math.PI) / 180;
  const toDeg = (r) => (r * 180) / Math.PI;
  const lat1 = toRad(from[1]);
  const lon1 = toRad(from[0]);
  const lat2 = toRad(to[1]);
  const lon2 = toRad(to[0]);
  const d = 2 * Math.asin(Math.sqrt(
    Math.sin((lat2 - lat1) / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2
  ));
  if (d < 1e-6) return [from, to];
  const coords = [];
  for (let i = 0; i <= steps; i += 1) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
    const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
    const z = A * Math.sin(lat1) + B * Math.sin(lat2);
    coords.push([toDeg(Math.atan2(y, x)), toDeg(Math.atan2(z, Math.sqrt(x * x + y * y)))]);
  }
  return coords;
}

function pulseGeo(pulse) {
  return {
    type: "FeatureCollection",
    features: (pulse || []).map((e) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [e.lon, e.lat] },
      properties: { tone: e.tone, action: e.action },
    })),
  };
}

function arcGeo(pins) {
  return {
    type: "FeatureCollection",
    features: pins
      .filter((p) => (p.probability || 0) >= 0.18)
      .map((p) => ({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: greatCircle([p.lon, p.lat], DEMAND, 48),
        },
      })),
  };
}

function ensureLayers() {
  if (!map.getSource("pulse")) {
    map.addSource("pulse", { type: "geojson", data: pulseGeo([]) });
    map.addLayer({
      id: "pulse-dots",
      type: "circle",
      source: "pulse",
      paint: {
        "circle-radius": 2.4,
        "circle-color": [
          "interpolate", ["linear"], ["get", "tone"],
          -8, "#e07a5f",
          0, "#e8c572",
          4, "#3dcca8",
        ],
        "circle-opacity": 0.4,
      },
    });
  }
  if (!map.getSource("arcs")) {
    map.addSource("arcs", { type: "geojson", data: arcGeo([]) });
    map.addLayer({
      id: "arcs",
      type: "line",
      source: "arcs",
      paint: {
        "line-color": "#e8c572",
        "line-opacity": 0.16,
        "line-width": 1.1,
      },
    });
  }
}

function clearMarkers() {
  markers.forEach((m) => m.remove());
  markers = [];
}

function pinEl(pin) {
  const el = document.createElement("button");
  const p = pin.probability || 0;
  const ship = pin.disruption_type === "shipping_threat";
  el.className = `pin pin-${band(p)}${ship ? " ship" : ""}${pin.kind === "supplier" ? " supplier" : ""}`;
  el.type = "button";
  el.dataset.id = pin.id;
  const n = pin.kind === "supplier" ? "" : `<span class="n">${Math.round(p * 100)}</span>`;
  el.innerHTML = `<span class="halo"></span><span class="core">${n}</span>`;
  el.title = `${pin.label} · ${pin.subtitle || ""}`;
  el.addEventListener("click", (ev) => {
    ev.stopPropagation();
    selectPin(pin.id, true);
  });
  return el;
}

function renderMarkers(snap) {
  clearMarkers();
  const all = [...(snap.pins || []), ...(snap.suppliers || [])];
  all.forEach((pin) => {
    const marker = new maplibregl.Marker({ element: pinEl(pin), anchor: "center" })
      .setLngLat([pin.lon, pin.lat])
      .addTo(map);
    markers.push(marker);
  });
  if (map.getSource("pulse")) map.getSource("pulse").setData(pulseGeo(snap.pulse));
  if (map.getSource("arcs")) map.getSource("arcs").setData(arcGeo(snap.pins || []));
}

function renderList(snap) {
  listEl.innerHTML = "";
  (snap.pins || []).forEach((pin) => {
    const d = pin.delta || 0;
    const btn = document.createElement("button");
    btn.className = `row ${band(pin.probability)}`;
    if (pin.id === selectedId) btn.classList.add("active");
    btn.type = "button";
    btn.innerHTML = `
      <div class="pct">${pct(pin.probability)}</div>
      <div>
        <div class="who">${esc(pin.label)}</div>
        <div class="sub">${esc(pin.subtitle)}${pin.site ? " · " + esc(pin.site) : ""}</div>
        <div class="delta ${d >= 0 ? "up" : "down"}">${d >= 0 ? "+" : ""}${Math.round(d * 100)} pts vs last month</div>
      </div>`;
    btn.addEventListener("click", () => selectPin(pin.id, true));
    listEl.appendChild(btn);
  });
}

function findPin(id) {
  const snap = currentSnap();
  return (snap.pins || []).find((p) => p.id === id)
    || (snap.suppliers || []).find((p) => p.id === id);
}

function renderBrief(pin) {
  if (!pin || pin.kind === "supplier") {
    if (pin && pin.kind === "supplier") {
      briefEmpty.hidden = true;
      briefBody.hidden = false;
      briefBody.className = "brief";
      briefBody.innerHTML = `
        <div class="site">Allied supply</div>
        <div class="brief-head">${esc(pin.label)}</div>
        <p class="muted">${esc(pin.site || "")} · ${esc(pin.subtitle)}</p>
        <div class="tags">${(pin.exposed_programs || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
        <p class="muted">Not a risk pin. This is a node on the demo bill of materials.</p>`;
      return;
    }
    briefEmpty.hidden = false;
    briefBody.hidden = true;
    return;
  }
  briefEmpty.hidden = true;
  briefBody.hidden = false;
  briefBody.className = "brief";
  const d = pin.delta || 0;
  const drivers = (pin.drivers || []).map((x) => `<li>${x.direction === "up" ? "↑" : "↓"} ${esc(x.indicator)} — ${esc(x.detail)}</li>`).join("");
  const analogs = (pin.analogs || []).map((a) => `<li>${esc(a.name)} (${a.year}) — ${Math.round(a.similarity * 100)}% similar. ${esc(a.outcome)}. ${esc(a.difference)}</li>`).join("")
    || "<li>No close analog above the similarity floor.</li>";
  const up = (pin.would_increase || []).map((s) => `<li>${esc(s)}</li>`).join("");
  const down = (pin.would_decrease || []).map((s) => `<li>${esc(s)}</li>`).join("");
  const src = (pin.sources || []).slice(0, 5).map((u) => `<li><a href="${esc(u)}" target="_blank" rel="noreferrer">${esc(u)}</a></li>`).join("");
  briefBody.innerHTML = `
    <div class="site">${esc(pin.site || pin.label)}</div>
    <div class="brief-pct">${pct(pin.probability)}</div>
    <div class="delta ${d >= 0 ? "up" : "down"}" style="margin-top:6px">${d >= 0 ? "+" : ""}${Math.round(d * 100)} pts vs last month</div>
    <p class="brief-head">${esc(pin.headline)}</p>
    <div class="tags">
      ${(pin.exposed_programs || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
      ${(pin.exposed_suppliers || []).slice(0, 3).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
    </div>
    <h3 class="sec">What moved the forecast</h3>
    <ul>${drivers}</ul>
    <h3 class="sec">Historical analogs</h3>
    <ul>${analogs}</ul>
    <h3 class="sec">What would raise it</h3>
    <ul>${up}</ul>
    <h3 class="sec">What would lower it</h3>
    <ul>${down}</ul>
    ${src ? `<h3 class="sec">Sources</h3><ul>${src}</ul>` : ""}
  `;
  briefPanel.classList.add("open-mobile");
}

function selectPin(id, fly) {
  selectedId = id;
  const pin = findPin(id);
  document.querySelectorAll(".row").forEach((el, i) => {
    const snap = currentSnap();
    el.classList.toggle("active", snap.pins[i] && snap.pins[i].id === id);
  });
  document.querySelectorAll(".pin").forEach((el) => {
    el.classList.toggle("active", el.dataset.id === id);
  });
  renderBrief(pin);
  if (fly && pin && map) {
    map.flyTo({ center: [pin.lon, pin.lat], zoom: Math.max(map.getZoom(), 3.4), speed: 0.7 });
  }
}

function currentSnap() {
  const key = asof.value || bundle.default_as_of;
  return bundle.snapshots[key];
}

function showSnap() {
  const snap = currentSnap();
  if (!snap) return;
  statusEl.textContent = `${snap.portfolio} · ${snap.horizon_days}d · ${snap.pins.length} nodes`;
  notesEl.textContent = (snap.notes || []).join(" ");
  renderList(snap);
  if (map) renderMarkers(snap);
  if (selectedId) selectPin(selectedId, false);
}

function initMap(styleUrl) {
  map = new maplibregl.Map({
    container: "map",
    style: styleUrl,
    center: [55, 26],
    zoom: 2.05,
    attributionControl: true,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-left");
  let loaded = false;
  map.on("load", () => {
    loaded = true;
    try { map.setProjection({ type: "globe" }); } catch (e) { /* older maplibre */ }
    ensureLayers();
    showSnap();
    boot.classList.add("hide");
  });
  map.once("error", () => {
    if (!loaded && styleUrl === STYLES[0]) initMap(STYLES[1]);
  });
}

async function main() {
  bootSub.textContent = "Scoring sample world…";
  bundle = await loadBundle();
  (bundle.dates || []).forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    asof.appendChild(opt);
  });
  asof.value = bundle.default_as_of;
  asof.addEventListener("change", () => {
    selectedId = null;
    renderBrief(null);
    showSnap();
  });
  initMap(STYLES[0]);
}

main().catch((err) => {
  bootSub.textContent = "Demo failed to load. Run forgecast snapshot, then serve.";
  console.error(err);
});
