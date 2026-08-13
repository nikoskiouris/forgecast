/* global maplibregl */
const BASE = new URL("./", window.location.href);
const STYLES = [
  "https://tiles.openfreemap.org/styles/dark",
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
];
const ATL = { lon: -84.388, lat: 33.749 };
const STORE_KEY = "forgecast.places.v1";
const NEAR_PLACE_KM = 1.6;
const NEAR_COMMUTE_KM = 0.9;
const AIRPORT_KM = 10;
const WEEK_KM = 4;

const statusEl = document.getElementById("status");
const notesEl = document.getElementById("notes");
const listEl = document.getElementById("list");
const listKicker = document.getElementById("list-kicker");
const briefEmpty = document.getElementById("brief-empty");
const briefBody = document.getElementById("brief-body");
const briefPanel = document.getElementById("brief");
const boot = document.getElementById("boot");
const bootSub = document.getElementById("boot-sub");
const gate = document.getElementById("gate");
const form = document.getElementById("places-form");
const gateErr = document.getElementById("gate-err");
const goBtn = document.getElementById("go");

let map = null;
let markers = [];
let liveApi = false;
let bundle = null;
let report = null;
let selectedId = null;

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const r = 6371;
  const p1 = lat1 * Math.PI / 180;
  const p2 = lat2 * Math.PI / 180;
  const dphi = (lat2 - lat1) * Math.PI / 180;
  const dl = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(a)));
}

function distToRouteKm(lat, lon, coords) {
  if (!coords || coords.length < 2) return Infinity;
  const lat0 = lat;
  const xy = (la, lo) => {
    const x = (lo * Math.PI / 180) * Math.cos(lat0 * Math.PI / 180) * 6371;
    const y = (la * Math.PI / 180) * 6371;
    return [x, y];
  };
  const [px, py] = xy(lat, lon);
  let best = Infinity;
  for (let i = 0; i < coords.length - 1; i += 1) {
    const [ax, ay] = xy(coords[i][1], coords[i][0]);
    const [bx, by] = xy(coords[i + 1][1], coords[i + 1][0]);
    const dx = bx - ax;
    const dy = by - ay;
    let t = 0;
    if (dx || dy) t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
    const qx = ax + t * dx;
    const qy = ay + t * dy;
    best = Math.min(best, Math.hypot(px - qx, py - qy));
  }
  return best;
}

function extraMinutes(ev) {
  if (ev.severity === "high") return ev.kind === "event" ? 25 : 20;
  if (ev.severity === "mid") return 15;
  return 10;
}

function adviceFor(ev, near, onCommute, dest) {
  const who = near[0] || "your places";
  dest = dest || "work";
  if (ev.kind === "weather") {
    const blob = (ev.title + " " + (ev.summary || "")).toLowerCase();
    if (blob.includes("heat")) {
      return "Heat advisory today. Ease off midday outdoor time; storms can still pop this afternoon.";
    }
    return ev.title;
  }
  if (ev.kind === "transit") {
    const route = (ev.routes && ev.routes[0]) || "service";
    if (/red|gold|blue|green|rail/i.test(ev.title) || ev.area === "SUBWAY" || ev.area === "RAIL") {
      return `MARTA ${route} delays may affect trips near ${who}.`;
    }
    let title = ev.title.replace(/\.$/, "");
    if (!/^marta/i.test(title)) title = "MARTA " + title;
    return `${title}. Check before you ride.`;
  }
  if (ev.kind === "airport") return "ATL delays. Build extra time if you fly or use Airport Station.";
  if (ev.kind === "event") {
    return `Avoid ${ev.area || "the venue"} around event time: ${ev.title}.`;
  }
  if (ev.kind === "utility") {
    const bit = String(ev.title || "").replace("Utility work: ", "");
    return `Utility work near ${who}: ${bit}`;
  }
  if (onCommute) return `Leave ${extraMinutes(ev)} minutes earlier: ${ev.title} on your usual route to ${dest}.`;
  return `${ev.title} near ${who}.`;
}

function scoreLocal(events, places, commute, dest) {
  const now = Date.now();
  const items = [];
  events.forEach((ev) => {
    const end = ev.end ? Date.parse(ev.end) : null;
    const start = ev.start ? Date.parse(ev.start) : null;
    if (end && end < now - 2 * 3600 * 1000) return;
    if (start && start > now + 7 * 24 * 3600 * 1000 && !ev.metro) return;
    let near = [];
    let best = null;
    if (ev.metro) {
      near = places.map((p) => p.label);
      best = 0;
    } else {
      places.forEach((p) => {
        const d = haversineKm(p.lat, p.lon, ev.lat, ev.lon);
        best = best == null ? d : Math.min(best, d);
        const airportish = ev.kind === "airport" && (d <= AIRPORT_KM || /airport/i.test(p.address + p.label));
        if (d <= NEAR_PLACE_KM || airportish || (d <= WEEK_KM && (ev.kind === "event" || ev.kind === "weather"))) {
          near.push(p.label);
        }
      });
    }
    const onCommute = !ev.metro && distToRouteKm(ev.lat, ev.lon, commute) <= NEAR_COMMUTE_KM;
    if (ev.kind === "transit" && ev.metro && ev.severity !== "low") near = near.length ? near : places.map((p) => p.label);
    if (!near.length && !onCommute && !(ev.kind === "weather" && ev.metro)) return;
    let score = 0;
    if (best != null) {
      if (best <= 0.4) score += 80;
      else if (best <= 1.6) score += 55;
      else if (best <= 4) score += 22;
    }
    if (onCommute) score += 42;
    if (ev.metro && ev.kind === "weather") score += ev.severity === "high" ? 48 : 32;
    if (ev.kind === "transit" && ev.severity !== "low") score += 28;
    if (ev.kind === "event") score += 30;
    score += { high: 20, mid: 10, low: 0 }[ev.severity] || 0;
    items.push({
      event_id: ev.id,
      kind: ev.kind,
      severity: ev.severity,
      title: ev.title,
      summary: ev.summary,
      advice: adviceFor(ev, near, onCommute, dest),
      lat: ev.lat,
      lon: ev.lon,
      distance_km: best == null ? null : Math.round(best * 100) / 100,
      near,
      on_commute: onCommute,
      start: ev.start,
      end: ev.end,
      source: ev.source,
      source_url: ev.source_url,
      score,
    });
  });
  items.sort((a, b) => b.score - a.score);
  const quotas = { weather: 2, event: 3, transit: 3, airport: 1, road: 5, utility: 2 };
  const used = {};
  const picked = [];
  items.forEach((item) => {
    if (picked.length >= 16) return;
    const n = used[item.kind] || 0;
    if (n >= (quotas[item.kind] || 2)) return;
    const nearDup = picked.some((p) => p.kind === item.kind && haversineKm(item.lat, item.lon, p.lat, p.lon) < 0.35);
    if (nearDup) return;
    picked.push(item);
    used[item.kind] = n + 1;
  });
  picked.sort((a, b) => b.score - a.score);
  return picked;
}

async function photonGeocode(q, label) {
  const url = "https://photon.komoot.io/api/?lat=33.75&lon=-84.39&limit=5&q=" + encodeURIComponent(q);
  const res = await fetch(url);
  if (!res.ok) throw new Error("geocode failed");
  const data = await res.json();
  const hit = (data.features || []).find((f) => {
    const c = f.geometry && f.geometry.coordinates;
    if (!c) return false;
    const lon = c[0];
    const lat = c[1];
    return lat >= 33.47 && lat <= 34.26 && lon >= -84.90 && lon <= -83.90;
  });
  if (!hit) throw new Error("No Atlanta match for " + q);
  const c = hit.geometry.coordinates;
  const p = hit.properties || {};
  const street = [p.housenumber, p.street].filter(Boolean).join(" ");
  return {
    label,
    address: [street || p.name || q, p.city || "Atlanta"].filter(Boolean).join(", "),
    lat: c[1],
    lon: c[0],
  };
}

async function osrmRoute(a, b) {
  const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=simplified&geometries=geojson`;
  const res = await fetch(url);
  if (!res.ok) return [[a.lon, a.lat], [b.lon, b.lat]];
  const data = await res.json();
  const coords = data.routes && data.routes[0] && data.routes[0].geometry && data.routes[0].geometry.coordinates;
  return (coords && coords.length >= 2) ? coords : [[a.lon, a.lat], [b.lon, b.lat]];
}

function weekdayName(iso) {
  try {
    return new Date(iso || Date.now()).toLocaleDateString("en-US", { weekday: "long", timeZone: "America/New_York" });
  } catch (e) {
    return "today";
  }
}

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || "null");
  } catch (e) {
    return null;
  }
}

function savePlaces(places) {
  localStorage.setItem(STORE_KEY, JSON.stringify(places));
}

function formPlaces() {
  const home = document.getElementById("home").value.trim();
  const work = document.getElementById("work").value.trim();
  const gym = document.getElementById("gym").value.trim();
  const places = [];
  if (home) places.push({ label: "home", address: home });
  if (work) places.push({ label: "work", address: work });
  if (gym) places.push({ label: "gym", address: gym });
  return places;
}

function fillForm(places) {
  const by = Object.fromEntries((places || []).map((p) => [p.label, p.address]));
  document.getElementById("home").value = by.home || "";
  document.getElementById("work").value = by.work || "";
  document.getElementById("gym").value = by.gym || "";
}

async function detectLive() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) return false;
    const body = await res.json();
    return Boolean(body.ok);
  } catch (e) {
    return false;
  }
}

async function loadEvents() {
  if (liveApi) {
    const res = await fetch("/api/events");
    if (res.ok) return res.json();
  }
  const baked = await fetch(new URL("data/demo.json", BASE));
  if (!baked.ok) throw new Error("no city data");
  return baked.json();
}

async function runDay(places) {
  if (liveApi) {
    const res = await fetch("/api/day", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ places }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "briefing failed");
    return body;
  }
  const resolved = [];
  for (const p of places) {
    if (p.lat != null && p.lon != null) resolved.push(p);
    else resolved.push(await photonGeocode(p.address, p.label));
  }
  let commute = [];
  const home = resolved.find((p) => p.label === "home");
  const work = resolved.find((p) => p.label === "work");
  const dest = work ? work.label : (resolved[1] ? resolved[1].label : "work");
  if (home && work) commute = await osrmRoute(home, work);
  else if (resolved.length >= 2) commute = await osrmRoute(resolved[0], resolved[1]);
  const items = scoreLocal(bundle.events || [], resolved, commute, dest);
  return {
    as_of: bundle.as_of,
    weekday: weekdayName(bundle.as_of),
    center_lat: resolved.reduce((s, p) => s + p.lat, 0) / resolved.length,
    center_lon: resolved.reduce((s, p) => s + p.lon, 0) / resolved.length,
    zoom: resolved.length === 1 ? 12.2 : 11.2,
    places: resolved,
    commute,
    items,
    events: bundle.events || [],
    notes: bundle.notes || [],
    sources_ok: bundle.sources_ok || [],
    sources_failed: bundle.sources_failed || [],
  };
}

function pinClass(ev) {
  const bits = ["pin", ev.severity || "mid"];
  if (ev.kind) bits.push(ev.kind);
  return bits.join(" ");
}

function clearMarkers() {
  markers.forEach((m) => m.remove());
  markers = [];
}

function pinEl(ev, kind) {
  const el = document.createElement("button");
  el.className = pinClass({ ...ev, kind: kind || ev.kind });
  el.type = "button";
  el.dataset.id = ev.id || ev.event_id;
  el.innerHTML = `<span class="halo"></span><span class="core"></span>`;
  el.title = ev.title || ev.label || "";
  el.addEventListener("click", (evt) => {
    evt.stopPropagation();
    selectPin(el.dataset.id, true);
  });
  return el;
}

function ensureLayers() {
  if (!map.getSource("commute")) {
    map.addSource("commute", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({
      id: "commute",
      type: "line",
      source: "commute",
      paint: { "line-color": "#3dcca8", "line-width": 2.4, "line-opacity": 0.75 },
    });
  }
}

function setCommute(coords) {
  if (!map.getSource("commute")) return;
  map.getSource("commute").setData({
    type: "FeatureCollection",
    features: coords && coords.length >= 2 ? [{
      type: "Feature",
      geometry: { type: "LineString", coordinates: coords },
    }] : [],
  });
}

function renderMarkers() {
  clearMarkers();
  const events = (report && report.events) || (bundle && bundle.events) || [];
  const hit = new Set(((report && report.items) || []).map((i) => i.event_id));
  events.forEach((ev) => {
    if (ev.lat == null || ev.lon == null) return;
    const marker = new maplibregl.Marker({ element: pinEl(ev), anchor: "center" })
      .setLngLat([ev.lon, ev.lat])
      .addTo(map);
    if (hit.has(ev.id)) marker.getElement().classList.add("active");
    markers.push(marker);
  });
  ((report && report.places) || []).forEach((p) => {
    const marker = new maplibregl.Marker({
      element: pinEl({ id: "place:" + p.label, title: p.label, kind: "place", severity: "mid" }, "place"),
      anchor: "center",
    }).setLngLat([p.lon, p.lat]).addTo(map);
    markers.push(marker);
  });
  setCommute(report && report.commute);
}

function findEvent(id) {
  if (id && String(id).startsWith("place:")) {
    const label = String(id).slice(6);
    const p = ((report && report.places) || []).find((x) => x.label === label);
    if (!p) return null;
    return { id, kind: "place", title: p.label, summary: p.address, lat: p.lat, lon: p.lon, source: "You" };
  }
  const item = ((report && report.items) || []).find((i) => i.event_id === id);
  const ev = (((report && report.events) || (bundle && bundle.events) || [])).find((e) => e.id === id);
  if (item && ev) return { ...ev, ...item, title: item.advice || ev.title };
  return item || ev || null;
}

function whenText(ev) {
  if (!ev) return "";
  const opts = { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" };
  const a = ev.start ? new Date(ev.start).toLocaleString("en-US", opts) : "";
  const b = ev.end ? new Date(ev.end).toLocaleString("en-US", opts) : "";
  if (a && b) return a + " → " + b;
  return a || b;
}

function renderBrief(ev) {
  if (!ev) {
    briefEmpty.hidden = false;
    briefBody.hidden = true;
    return;
  }
  briefEmpty.hidden = true;
  briefBody.hidden = false;
  briefBody.className = "brief";
  const tags = [];
  (ev.near || []).forEach((t) => tags.push(t));
  if (ev.on_commute) tags.push("commute");
  if (ev.kind) tags.push(ev.kind);
  const src = ev.source_url
    ? `<p><a href="${esc(ev.source_url)}" target="_blank" rel="noreferrer">${esc(ev.source || "Source")}</a></p>`
    : (ev.source ? `<p class="muted">${esc(ev.source)}</p>` : "");
  briefBody.innerHTML = `
    <div class="site">${esc((ev.kind || "event").replace("_", " "))}</div>
    <p class="brief-head">${esc(ev.advice || ev.title)}</p>
    <div class="tags">${tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
    <p>${esc(ev.summary || ev.title || "")}</p>
    ${whenText(ev) ? `<p class="muted">${esc(whenText(ev))}</p>` : ""}
    ${ev.distance_km != null ? `<p class="muted">${ev.distance_km} km from a saved place</p>` : ""}
    ${src}
  `;
  briefPanel.classList.add("open-mobile");
}

function renderList() {
  listEl.innerHTML = "";
  const items = (report && report.items) || [];
  const day = (report && report.weekday) || weekdayName();
  listKicker.textContent = items.length ? `Your ${day}` : "Atlanta now";
  if (!items.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.style.padding = "8px";
    p.textContent = report && report.places && report.places.length
      ? "Nothing loud on your places. Pins on the map are still live city events."
      : "Enter a place to see what hits you. Map shows live Atlanta events.";
    listEl.appendChild(p);
    (((report && report.events) || (bundle && bundle.events) || []).filter((e) => e.kind === "event" || e.severity === "high").slice(0, 8)).forEach((ev) => {
      const btn = document.createElement("button");
      btn.className = `row ${ev.severity} ${ev.kind}`;
      btn.type = "button";
      btn.innerHTML = `<div class="kind">${esc(ev.kind)}</div><div><div class="who">${esc(ev.title)}</div><div class="sub">${esc(ev.source || "")}</div></div>`;
      btn.addEventListener("click", () => selectPin(ev.id, true));
      listEl.appendChild(btn);
    });
    return;
  }
  items.forEach((item) => {
    const btn = document.createElement("button");
    btn.className = `row ${item.severity} ${item.kind}${item.event_id === selectedId ? " active" : ""}`;
    btn.type = "button";
    const meta = item.on_commute ? "on your commute" : (item.near || []).join(", ");
    btn.innerHTML = `<div class="kind">${esc(item.kind)}</div><div><div class="who">${esc(item.advice)}</div><div class="sub">${esc(meta)} · ${esc(item.source)}</div></div>`;
    btn.addEventListener("click", () => selectPin(item.event_id, true));
    listEl.appendChild(btn);
  });
}

function selectPin(id, fly) {
  selectedId = id;
  const ev = findEvent(id);
  document.querySelectorAll(".row").forEach((el) => {
    el.classList.toggle("active", false);
  });
  document.querySelectorAll(".pin").forEach((el) => {
    el.classList.toggle("active", el.dataset.id === id);
  });
  renderBrief(ev);
  if (fly && ev && map && ev.lon != null) {
    map.flyTo({ center: [ev.lon, ev.lat], zoom: Math.max(map.getZoom(), 12.4), speed: 0.8 });
  }
}

function paint() {
  const n = ((report && report.events) || (bundle && bundle.events) || []).length;
  const hits = (report && report.items && report.items.length) || 0;
  const when = (report && report.as_of) || (bundle && bundle.as_of);
  statusEl.textContent = `${hits ? hits + " hits · " : ""}${n} live events`;
  const notes = (report && report.notes) || (bundle && bundle.notes) || [];
  notesEl.textContent = notes.join(" ") + (when ? " Updated " + new Date(when).toLocaleString("en-US", { timeZone: "America/New_York" }) + "." : "");
  renderList();
  if (map) renderMarkers();
  if (report && report.center_lon != null && map) {
    map.flyTo({ center: [report.center_lon, report.center_lat], zoom: report.zoom || 11.2, speed: 0.7 });
  }
}

function initMap(styleUrl) {
  map = new maplibregl.Map({
    container: "map",
    style: styleUrl,
    center: [ATL.lon, ATL.lat],
    zoom: 10.6,
    attributionControl: true,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-left");
  let loaded = false;
  map.on("load", () => {
    loaded = true;
    ensureLayers();
    paint();
    boot.classList.add("hide");
  });
  map.once("error", () => {
    if (!loaded && styleUrl === STYLES[0]) initMap(STYLES[1]);
  });
}

async function submitPlaces(places) {
  gateErr.hidden = true;
  goBtn.disabled = true;
  goBtn.textContent = "Reading the city…";
  try {
    report = await runDay(places);
    savePlaces(report.places);
    gate.classList.add("hide");
    paint();
    if (report.items[0]) selectPin(report.items[0].event_id, false);
  } catch (err) {
    gateErr.hidden = false;
    gateErr.textContent = err.message || String(err);
    gate.classList.remove("hide");
  } finally {
    goBtn.disabled = false;
    goBtn.textContent = "See my forecast";
  }
}

form.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const places = formPlaces();
  if (!places.length) return;
  submitPlaces(places);
});

document.getElementById("chips").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  document.getElementById("home").value = btn.dataset.home || "";
  document.getElementById("work").value = btn.dataset.work || "";
});

document.getElementById("edit-places").addEventListener("click", () => {
  gate.classList.remove("hide");
});

async function main() {
  bootSub.textContent = "Reading Atlanta…";
  liveApi = await detectLive();
  bundle = await loadEvents();
  report = {
    as_of: bundle.as_of,
    weekday: weekdayName(bundle.as_of),
    events: bundle.events || [],
    items: [],
    places: [],
    commute: [],
    notes: bundle.notes || [],
    sources_ok: bundle.sources_ok || [],
    sources_failed: bundle.sources_failed || [],
    center_lat: ATL.lat,
    center_lon: ATL.lon,
    zoom: 10.6,
  };
  const saved = loadSaved();
  if (saved && saved.length) fillForm(saved);
  initMap(STYLES[0]);
}

main().catch((err) => {
  bootSub.textContent = "Could not load Atlanta feeds.";
  console.error(err);
});
