/* global maplibregl */
const BASE = new URL("./", window.location.href);
const STYLES = [
  "https://tiles.openfreemap.org/styles/dark",
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
];
const ATL = { lon: -84.388, lat: 33.749 };
const STORE_KEY = "forgecast.places.v1";
const STORE_USUAL = "forgecast.usual.v1";
const NEAR_PLACE_KM = 1.6;
const NEAR_COMMUTE_KM = 0.9;
const AIRPORT_KM = 10;
const WEEK_KM = 4;
const PERIMETER_MIN_KM = 14;
const DOWNTOWN = [-84.3908, 33.7550];
const I285_RING = [
  [-84.2590, 33.8915],
  [-84.2290, 33.8160],
  [-84.2060, 33.7460],
  [-84.4130, 33.6560],
  [-84.3950, 33.6550],
  [-84.4940, 33.7710],
  [-84.4590, 33.9090],
  [-84.3570, 33.9170],
];
const HIGHWAY_RULES = [
  [/\b(?:i|interstate)\s*-?\s*285\b|atlanta bypass|the perimeter/i, "I-285"],
  [/\b(?:ga|georgia)\s*-?\s*400\b|georgia 400/i, "GA-400"],
  [/\b(?:i|interstate)\s*-?\s*85\b|downtown connector|northeast expressway/i, "I-85"],
  [/\b(?:i|interstate)\s*-?\s*75\b/i, "I-75"],
  [/\b(?:i|interstate)\s*-?\s*20\b/i, "I-20"],
];
const GAZETTEER = {
  "ponce city market": [33.7724, -84.3652, "Ponce City Market, Atlanta"],
  "georgia tech": [33.7756, -84.3963, "Georgia Institute of Technology"],
  "midtown": [33.7838, -84.3861, "Midtown Atlanta"],
  "airport": [33.6407, -84.4277, "Hartsfield-Jackson Atlanta International Airport"],
  "hartsfield": [33.6407, -84.4277, "Hartsfield-Jackson Atlanta International Airport"],
  "five points": [33.7539, -84.3916, "Five Points, Atlanta"],
  "decatur": [33.7748, -84.2963, "Decatur, Georgia"],
  "briarlake": [33.8439, -84.2722, "Briarlake Road, Atlanta"],
  "briarlake road": [33.8439, -84.2722, "Briarlake Road, Atlanta"],
  "buffington": [33.6137, -84.4894, "5200 Buffington Road, College Park"],
  "buffington road": [33.6137, -84.4894, "5200 Buffington Road, College Park"],
};
const TIERS = [
  ["hits", "Hits your day"],
  ["could", "Could hit you"],
  ["later", "Later this week"],
];

const statusEl = document.getElementById("status");
const notesEl = document.getElementById("notes");
const listEl = document.getElementById("list");
const listKicker = document.getElementById("list-kicker");
const verdictEl = document.getElementById("verdict");
const corridorsEl = document.getElementById("corridors");
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
let selectedRouteId = null;

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

function highwaysFromText(blob) {
  const found = [];
  HIGHWAY_RULES.forEach(([rx, name]) => {
    if (rx.test(blob || "") && !found.includes(name)) found.push(name);
  });
  return found;
}

function nameCorridor(highways) {
  const order = ["I-285", "GA-400", "I-85", "I-75", "I-20"];
  const hit = order.find((n) => highways.includes(n));
  return hit || "local roads";
}

function slugId(name, used) {
  let base = String(name || "route").toLowerCase().replace(/\s+/g, "");
  if (!used.has(base)) {
    used.add(base);
    return base;
  }
  let n = 2;
  while (used.has(`${base}-${n}`)) n += 1;
  const id = `${base}-${n}`;
  used.add(id);
  return id;
}

function parseOsrmRoute(raw, a, b, kind, used) {
  const coords = (raw.geometry && raw.geometry.coordinates) || [];
  if (!coords || coords.length < 2) return null;
  let blob = "";
  (raw.legs || []).forEach((leg) => {
    (leg.steps || []).forEach((st) => { blob += ` ${st.ref || ""} ${st.name || ""}`; });
  });
  const highways = highwaysFromText(blob);
  const name = nameCorridor(highways);
  const mins = raw.duration != null ? Math.round(raw.duration / 60) : null;
  const miles = raw.distance != null ? Math.round((raw.distance / 1609) * 10) / 10 : null;
  const detail = [highways.join(" / ") || null, mins != null ? `${mins} min` : null, miles ? `${miles} mi` : null]
    .filter(Boolean).join(" · ");
  return {
    id: slugId(name, used),
    name,
    detail,
    highways,
    coords,
    duration_s: raw.duration,
    distance_m: raw.distance,
    kind,
    hits: 0,
    extra_min: 0,
  };
}

async function osrmFetch(points, alternatives) {
  const path = points.map(([lon, lat]) => `${lon.toFixed(5)},${lat.toFixed(5)}`).join(";");
  const qs = `overview=simplified&geometries=geojson&steps=true${alternatives ? "&alternatives=true" : ""}`;
  const url = `https://router.project-osrm.org/route/v1/driving/${path}?${qs}`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();
  return data.routes || [];
}

function nearestRing(lon, lat) {
  let best = Infinity;
  let idx = 0;
  I285_RING.forEach((pt, i) => {
    const d = haversineKm(lat, lon, pt[1], pt[0]);
    if (d < best) {
      best = d;
      idx = i;
    }
  });
  return idx;
}

function shorterArcVia(a, b) {
  const i0 = nearestRing(a.lon, a.lat);
  const i1 = nearestRing(b.lon, b.lat);
  if (i0 === i1) return null;
  const n = I285_RING.length;
  const cw = (i1 - i0 + n) % n;
  const ccw = (i0 - i1 + n) % n;
  const clockwise = cw <= ccw;
  const idxs = [];
  let i = i0;
  for (let s = 0; s < n; s += 1) {
    i = clockwise ? (i + 1) % n : (i - 1 + n) % n;
    if (i === i1) break;
    idxs.push(i);
  }
  if (!idxs.length) return null;
  const pt = I285_RING[idxs[Math.floor(idxs.length / 2)]];
  return { lon: pt[0], lat: pt[1] };
}

function downtownVia(a, b) {
  const direct = haversineKm(a.lat, a.lon, b.lat, b.lon);
  if (direct < PERIMETER_MIN_KM) return null;
  const via = haversineKm(a.lat, a.lon, DOWNTOWN[1], DOWNTOWN[0])
    + haversineKm(DOWNTOWN[1], DOWNTOWN[0], b.lat, b.lon);
  if (via > direct * 1.65) return null;
  return { lon: DOWNTOWN[0], lat: DOWNTOWN[1] };
}

function pickCorridors(routes) {
  if (!routes.length) return [];
  const timed = routes.filter((r) => r.duration_s);
  const cap = timed.length ? Math.min(...timed.map((r) => r.duration_s)) * 1.85 : null;
  const viable = routes.filter((r) => cap == null || !r.duration_s || r.duration_s <= cap);
  const chosen = [];
  const seen = new Set();
  viable.forEach((r) => {
    if (seen.has(r.name) || chosen.length >= 3) return;
    seen.add(r.name);
    chosen.push(r);
  });
  return chosen.length ? chosen : routes.slice(0, 1);
}

async function commuteOptions(a, b) {
  const used = new Set();
  let routes = [];
  try {
    const raws = await osrmFetch([[a.lon, a.lat], [b.lon, b.lat]], true);
    raws.forEach((raw, i) => {
      const parsed = parseOsrmRoute(raw, a, b, i === 0 ? "shortest" : "alternate", used);
      if (parsed) routes.push(parsed);
    });
  } catch (e) {
    routes = [];
  }
  const names = new Set(routes.map((r) => r.name));
  const direct = haversineKm(a.lat, a.lon, b.lat, b.lon);
  const addVia = async (pt, want, kind) => {
    if (!pt || names.has(want)) return;
    try {
      const extra = await osrmFetch([[a.lon, a.lat], [pt.lon, pt.lat], [b.lon, b.lat]], false);
      extra.forEach((raw) => {
        const parsed = parseOsrmRoute(raw, a, b, kind, used);
        if (parsed && (parsed.highways.includes(want) || parsed.name === want) && !names.has(parsed.name)) {
          routes.push(parsed);
          names.add(parsed.name);
        }
      });
    } catch (e) { /* keep what we have */ }
  };
  if (direct >= PERIMETER_MIN_KM) {
    if (!names.has("I-285")) await addVia(shorterArcVia(a, b), "I-285", "perimeter");
    if (!names.has("I-85")) await addVia(downtownVia(a, b), "I-85", "alternate");
  }
  const picked = pickCorridors(routes);
  if (picked.length) return picked;
  return [{
    id: "yourroute",
    name: "your route",
    detail: "straight line",
    highways: [],
    coords: [[a.lon, a.lat], [b.lon, b.lat]],
    kind: "shortest",
    hits: 0,
    extra_min: 0,
  }];
}

function adviceFor(ev, near, onCommute, dest, routeNames, usualName) {
  const who = near[0] || "your places";
  dest = dest || "work";
  const names = (routeNames || []).filter(Boolean);
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
  if (onCommute && names.length > 1) {
    return `Leave ${extraMinutes(ev)} minutes earlier: ${ev.title} sits on both ${names.join(" and ")}.`;
  }
  if (onCommute && names.length) {
    const label = names[0];
    if (usualName && label === usualName) {
      return `Leave ${extraMinutes(ev)} minutes earlier: ${ev.title} on your usual ${label}.`;
    }
    return `Leave ${extraMinutes(ev)} minutes earlier: ${ev.title} on ${label}.`;
  }
  if (names.length) return `On ${names.join(" / ")} (not your usual): ${ev.title}.`;
  if (onCommute) return `Leave ${extraMinutes(ev)} minutes earlier: ${ev.title} on your usual route to ${dest}.`;
  return `${ev.title} near ${who}.`;
}

function tierFor(when, onUsual, dist, ev, usualId) {
  if (when === "week") return "later";
  const close = dist != null && dist <= 0.4;
  const severeWx = ev.kind === "weather" && ev.severity === "high";
  if (usualId == null) {
    if (onUsual || close || severeWx) return "hits";
    return "could";
  }
  if (onUsual || close || severeWx) return "hits";
  return "could";
}

function scoreLocal(events, places, routes, dest, usualId) {
  const now = Date.now();
  const items = [];
  events.forEach((ev) => {
    const end = ev.end ? Date.parse(ev.end) : null;
    const start = ev.start ? Date.parse(ev.start) : null;
    if (end && end < now - 2 * 3600 * 1000) return;
    const weekLater = start && start > now + 7 * 24 * 3600 * 1000;
    if (weekLater && !ev.metro) return;
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
    const hit = ev.metro ? [] : (routes || []).filter((r) => distToRouteKm(ev.lat, ev.lon, r.coords) <= NEAR_COMMUTE_KM);
    const usual = usualId || ((routes || []).length === 1 ? routes[0].id : null);
    const onUsual = usual ? hit.some((r) => r.id === usual) : hit.length > 0;
    const commuteHit = hit.length > 0;
    if (ev.kind === "transit" && ev.metro && ev.severity !== "low") near = near.length ? near : places.map((p) => p.label);
    if (!near.length && !commuteHit && !(ev.kind === "weather" && ev.metro)) return;
    let score = 0;
    if (best != null) {
      if (best <= 0.4) score += 80;
      else if (best <= 1.6) score += 55;
      else if (best <= 4) score += 22;
    }
    if (onUsual) score += 50;
    else if (commuteHit) score += 28;
    if (ev.metro && ev.kind === "weather") score += ev.severity === "high" ? 48 : 32;
    if (ev.kind === "transit" && ev.severity !== "low") score += 28;
    if (ev.kind === "event") score += 30;
    score += { high: 20, mid: 10, low: 0 }[ev.severity] || 0;
    const when = (start && start > now + 18 * 3600 * 1000 && start < now + 7 * 24 * 3600 * 1000) ? "week" : "now";
    if (when === "week") score *= 0.65;
    const names = [];
    hit.forEach((r) => { if (!names.includes(r.name)) names.push(r.name); });
    const usualName = (routes || []).find((r) => r.id === usual)?.name;
    items.push({
      event_id: ev.id,
      kind: ev.kind,
      severity: ev.severity,
      title: ev.title,
      summary: ev.summary,
      advice: adviceFor(ev, near, onUsual || (usual == null && commuteHit), dest, names, usualName),
      lat: ev.lat,
      lon: ev.lon,
      distance_km: best == null ? null : Math.round(best * 100) / 100,
      near,
      on_commute: onUsual || (usual == null && commuteHit),
      on_routes: hit.map((r) => r.id),
      route_names: names,
      tier: tierFor(when, onUsual || (usual == null && commuteHit), best, ev, usual),
      start: ev.start,
      end: ev.end,
      source: ev.source,
      source_url: ev.source_url,
      score,
    });
  });
  items.sort((a, b) => b.score - a.score);
  const quotas = { weather: 2, event: 3, transit: 3, airport: 1, road: 6, utility: 2 };
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
  picked.sort((a, b) => ({ hits: 0, could: 1, later: 2 }[a.tier] - { hits: 0, could: 1, later: 2 }[b.tier]) || (b.score - a.score));
  return picked;
}

function stampRoutes(routes, items) {
  return (routes || []).map((route) => {
    const on = (items || []).filter((i) => (i.on_routes || []).includes(route.id));
    const extra = on.filter((i) => i.kind === "road" || i.kind === "event" || i.kind === "utility")
      .reduce((s, i) => s + extraMinutes(i), 0);
    return { ...route, hits: on.length, extra_min: extra };
  });
}

function retier(items, routes, usualId) {
  const usualName = (routes || []).find((r) => r.id === usualId)?.name;
  return (items || []).map((item) => {
    const onUsual = usualId ? (item.on_routes || []).includes(usualId) : (item.on_routes || []).length > 0;
    const when = item.tier === "later" ? "week" : "now";
    const tier = item.tier === "later" ? "later" : tierFor(when, onUsual, item.distance_km, item, usualId);
    let advice = item.advice;
    if (item.kind === "road") {
      advice = adviceFor(item, item.near || [], onUsual, "work", item.route_names || [], usualName);
    }
    return { ...item, on_commute: onUsual, tier, advice };
  }).sort((a, b) => ({ hits: 0, could: 1, later: 2 }[a.tier] - { hits: 0, could: 1, later: 2 }[b.tier]) || (b.score - a.score));
}

function verdictFor(routes, items, usualId) {
  const stamped = stampRoutes(routes, items);
  if (!stamped.length) return "";
  const messy = stamped.filter((r) => r.hits);
  const clean = stamped.filter((r) => !r.hits);
  const names = stamped.map((r) => r.name).join(" vs ");
  if (stamped.length === 1) {
    const r = stamped[0];
    if (!r.hits) return `${r.name} looks clear. Nothing loud is sitting on your corridor.`;
    return `${r.name} is in trouble today — ${r.hits} hit${r.hits === 1 ? "" : "s"} on your corridor.`;
  }
  if (usualId == null) {
    if (!messy.length) return `${names}. Both look clear. Tap the corridor you actually drive.`;
    if (clean.length) {
      return `${messy[0].name} is the messy habit today. ${clean[0].name} is the clean corridor. Tap the one you actually drive.`;
    }
    const worst = stamped.slice().sort((a, b) => b.hits - a.hits || b.extra_min - a.extra_min)[0];
    return `Every corridor has weather. ${worst.name} is the loudest. Tap the one you actually drive.`;
  }
  const usual = stamped.find((r) => r.id === usualId) || stamped[0];
  const others = stamped.filter((r) => r.id !== usualId);
  if (!usual.hits && others[0] && others[0].hits) {
    return `Your ${usual.name} is clean. ${others[0].name} is the messy one — stay on your habit.`;
  }
  if (usual.hits && others[0] && !others[0].hits) {
    return `Your usual ${usual.name} is in trouble. ${others[0].name} is the clean corridor today.`;
  }
  if (usual.hits) return `Your ${usual.name} has ${usual.hits} hit${usual.hits === 1 ? "" : "s"} today.`;
  return `Your ${usual.name} looks clear.`;
}

function normAddr(q) {
  return String(q || "").toLowerCase().replace(/,/g, " ").replace(/brairlake/g, "briarlake")
    .replace(/buffinton/g, "buffington").replace(/\s+/g, " ").trim();
}

function gazetteerLookup(q) {
  const n = normAddr(q);
  if (GAZETTEER[n]) {
    const [lat, lon, address] = GAZETTEER[n];
    return { address, lat, lon };
  }
  let best = null;
  let bestLen = 0;
  Object.keys(GAZETTEER).forEach((k) => {
    if (n.includes(k) && k.length > bestLen) {
      best = GAZETTEER[k];
      bestLen = k.length;
    }
  });
  if (!best) return null;
  const [lat, lon, address] = best;
  return { address, lat, lon };
}

function photonScore(query, hay) {
  const stop = new Set(["atlanta", "ga", "georgia", "road", "rd", "street", "st", "ave", "dr"]);
  const tokens = normAddr(query).split(" ").filter((t) => t && !stop.has(t) && !/^\d+$/.test(t));
  return tokens.reduce((s, t) => s + (hay.includes(t) ? 3 : 0), 0);
}

async function photonGeocode(q, label) {
  const gaz = gazetteerLookup(q);
  if (gaz && !/\d/.test(q)) return { label, ...gaz };
  const url = "https://photon.komoot.io/api/?lat=33.75&lon=-84.39&limit=5&q=" + encodeURIComponent(q);
  const res = await fetch(url);
  if (!res.ok) {
    if (gaz) return { label, ...gaz };
    throw new Error("geocode failed");
  }
  const data = await res.json();
  const ranked = [];
  (data.features || []).forEach((f) => {
    const c = f.geometry && f.geometry.coordinates;
    if (!c) return;
    const lon = c[0];
    const lat = c[1];
    if (!(lat >= 33.47 && lat <= 34.26 && lon >= -84.90 && lon <= -83.90)) return;
    const p = f.properties || {};
    const street = [p.housenumber, p.street].filter(Boolean).join(" ");
    const address = [street || p.name || q, p.city || "Atlanta"].filter(Boolean).join(", ");
    const hay = normAddr(`${p.name || ""} ${street} ${p.city || ""}`);
    ranked.push({ score: photonScore(q, hay), place: { label, address, lat, lon } });
  });
  ranked.sort((a, b) => b.score - a.score);
  const photon = ranked[0] ? ranked[0].place : null;
  if (gaz && photon) {
    if (photonScore(q, normAddr(gaz.address)) > photonScore(q, normAddr(photon.address))) {
      return { label, ...gaz };
    }
  }
  if (photon) return photon;
  if (gaz) return { label, ...gaz };
  throw new Error("No Atlanta match for " + q);
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

function odKey(places) {
  const home = (places || []).find((p) => p.label === "home");
  const work = (places || []).find((p) => p.label === "work") || (places || [])[1];
  if (!home || !work) return null;
  return `${home.lat.toFixed(3)},${home.lon.toFixed(3)}>${work.lat.toFixed(3)},${work.lon.toFixed(3)}`;
}

function loadUsual(places) {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE_USUAL) || "null");
    if (!raw || raw.key !== odKey(places)) return null;
    return raw.name || null;
  } catch (e) {
    return null;
  }
}

function saveUsual(places, name) {
  const key = odKey(places);
  if (!key || !name) return;
  localStorage.setItem(STORE_USUAL, JSON.stringify({ key, name }));
}

function applyUsual(rep) {
  const usualName = loadUsual(rep.places);
  const match = (rep.routes || []).find((r) => r.name === usualName);
  selectedRouteId = match ? match.id : null;
  rep.items = retier(rep.items || [], rep.routes || [], selectedRouteId);
  rep.routes = stampRoutes(rep.routes || [], rep.items);
  rep.corridor = verdictFor(rep.routes, rep.items, selectedRouteId);
  if (selectedRouteId) {
    const on = (rep.routes.find((r) => r.id === selectedRouteId) || {}).coords;
    if (on && on.length >= 2) rep.commute = on;
  }
  return rep;
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
    return applyUsual(body);
  }
  const resolved = [];
  for (const p of places) {
    if (p.lat != null && p.lon != null) resolved.push(p);
    else resolved.push(await photonGeocode(p.address, p.label));
  }
  let routes = [];
  const home = resolved.find((p) => p.label === "home");
  const work = resolved.find((p) => p.label === "work");
  const dest = work ? work.label : (resolved[1] ? resolved[1].label : "work");
  if (home && work) routes = await commuteOptions(home, work);
  else if (resolved.length >= 2) routes = await commuteOptions(resolved[0], resolved[1]);
  const usualName = loadUsual(resolved);
  const usualId = (routes.find((r) => r.name === usualName) || {}).id || null;
  selectedRouteId = usualId;
  const items = scoreLocal(bundle.events || [], resolved, routes, dest, usualId);
  const stamped = stampRoutes(routes, items);
  return {
    as_of: bundle.as_of,
    weekday: weekdayName(bundle.as_of),
    center_lat: resolved.reduce((s, p) => s + p.lat, 0) / resolved.length,
    center_lon: resolved.reduce((s, p) => s + p.lon, 0) / resolved.length,
    zoom: routes.length ? 11.0 : (resolved.length === 1 ? 12.2 : 11.2),
    places: resolved,
    commute: (stamped[0] && stamped[0].coords) || [],
    routes: stamped,
    corridor: verdictFor(stamped, items, usualId),
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
  if (!map.getSource("corridors")) {
    map.addSource("corridors", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({
      id: "corridors-alt",
      type: "line",
      source: "corridors",
      filter: ["!=", ["get", "active"], true],
      paint: {
        "line-color": "#e8c572",
        "line-width": 2.2,
        "line-opacity": 0.5,
        "line-dasharray": [2.2, 1.6],
      },
    });
    map.addLayer({
      id: "corridors-on",
      type: "line",
      source: "corridors",
      filter: ["==", ["get", "active"], true],
      paint: { "line-color": "#3dcca8", "line-width": 3.2, "line-opacity": 0.9 },
    });
  }
}

function currentRoute() {
  const routes = (report && report.routes) || [];
  if (selectedRouteId) return routes.find((r) => r.id === selectedRouteId) || null;
  return routes[0] || null;
}

function setCorridors(routes, activeId) {
  if (!map.getSource("corridors")) return;
  const features = (routes || []).filter((r) => r.coords && r.coords.length >= 2).map((r) => ({
    type: "Feature",
    properties: { id: r.id, name: r.name, active: Boolean(activeId) && r.id === activeId },
    geometry: { type: "LineString", coordinates: r.coords },
  }));
  map.getSource("corridors").setData({ type: "FeatureCollection", features });
}

function hudPad() {
  if (window.innerWidth <= 960) return { top: 100, bottom: 250, left: 18, right: 18 };
  return { top: 108, bottom: 88, left: 392, right: 412 };
}

function inWell(lon, lat, pad) {
  try {
    const p = map.project([lon, lat]);
    const w = map.getContainer().clientWidth;
    const h = map.getContainer().clientHeight;
    return p.x >= pad.left && p.x <= w - pad.right && p.y >= pad.top && p.y <= h - pad.bottom;
  } catch (e) {
    return false;
  }
}

function boundsOf(pts) {
  const b = new maplibregl.LngLatBounds(pts[0], pts[0]);
  pts.forEach((p) => b.extend(p));
  return b;
}

function frameDay() {
  if (!map || !report) return;
  const pad = hudPad();
  const pts = [];
  ((report.places) || []).forEach((p) => pts.push([p.lon, p.lat]));
  const route = currentRoute();
  const coords = (route && route.coords) || report.commute || [];
  coords.forEach((c, i) => { if (i % 6 === 0) pts.push(c); });
  if (coords.length) pts.push(coords[coords.length - 1]);
  if (pts.length < 1) return;
  map.fitBounds(boundsOf(pts), { padding: pad, maxZoom: 12.2, duration: 800, essential: true });
}

function focusPin(ev) {
  if (!map || !ev || ev.lon == null) return;
  const pad = hudPad();
  if (ev.metro) {
    frameDay();
    return;
  }
  const pts = [[ev.lon, ev.lat]];
  const places = (report && report.places) || [];
  let nearest = null;
  let nd = Infinity;
  places.forEach((p) => {
    const d = haversineKm(ev.lat, ev.lon, p.lat, p.lon);
    if (d < nd) {
      nd = d;
      nearest = p;
    }
  });
  if (nearest && nd < 10) pts.push([nearest.lon, nearest.lat]);
  const route = currentRoute();
  if (route && route.coords) {
    route.coords.forEach((c) => {
      if (haversineKm(ev.lat, ev.lon, c[1], c[0]) < 6) pts.push(c);
    });
  }
  if (pts.length === 1) {
    pts.push([ev.lon - 0.018, ev.lat - 0.014]);
    pts.push([ev.lon + 0.018, ev.lat + 0.014]);
  }
  const zoom = map.getZoom();
  if (zoom >= 11.4 && inWell(ev.lon, ev.lat, pad)) return;
  map.fitBounds(boundsOf(pts), {
    padding: pad,
    maxZoom: Math.min(12.7, Math.max(zoom, 11.6)),
    duration: 650,
    essential: true,
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
  setCorridors(report && report.routes, selectedRouteId);
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
  (ev.route_names || []).forEach((t) => tags.push(t));
  if (ev.on_commute) tags.push("your usual");
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

function renderCorridors() {
  if (!corridorsEl) return;
  corridorsEl.innerHTML = "";
  const routes = (report && report.routes) || [];
  if (!routes.length) return;
  routes.forEach((route) => {
    const btn = document.createElement("button");
    const active = route.id === selectedRouteId;
    btn.type = "button";
    btn.className = `corridor${active ? " active" : ""}${route.hits ? " messy" : " clear"}`;
    const flag = active ? "your usual" : (route.hits ? `${route.hits} hit${route.hits === 1 ? "" : "s"}` : "clear");
    btn.innerHTML = `<div><div class="cname">${esc(route.name)}</div><div class="cdetail">${esc(route.detail || "")}</div></div><div class="chits">${esc(flag)}</div>`;
    btn.addEventListener("click", () => selectCorridor(route.id));
    corridorsEl.appendChild(btn);
  });
}

function selectCorridor(id) {
  selectedRouteId = id;
  const route = ((report && report.routes) || []).find((r) => r.id === id);
  if (route && report && report.places) saveUsual(report.places, route.name);
  if (report) {
    report.items = retier(report.items || [], report.routes || [], selectedRouteId);
    report.routes = stampRoutes(report.routes || [], report.items);
    report.corridor = verdictFor(report.routes, report.items, selectedRouteId);
    if (route && route.coords) report.commute = route.coords;
  }
  paint({ frame: true });
}

function rowFor(item) {
  const btn = document.createElement("button");
  btn.className = `row ${item.severity} ${item.kind}${item.event_id === selectedId ? " active" : ""}`;
  btn.type = "button";
  const meta = [
    (item.route_names || []).length ? "on " + item.route_names.join(" / ") : "",
    item.on_commute ? "your usual" : (item.near || []).join(", "),
    item.source,
  ].filter(Boolean).join(" · ");
  btn.innerHTML = `<div class="kind">${esc(item.kind)}</div><div><div class="who">${esc(item.advice)}</div><div class="sub">${esc(meta)}</div></div>`;
  btn.addEventListener("click", () => selectPin(item.event_id, true));
  return btn;
}

function renderList() {
  listEl.innerHTML = "";
  const items = (report && report.items) || [];
  const day = (report && report.weekday) || weekdayName();
  listKicker.textContent = items.length || ((report && report.routes) || []).length ? `Your ${day}` : "Atlanta now";
  if (verdictEl) {
    const text = (report && report.corridor) || "";
    verdictEl.hidden = !text;
    verdictEl.textContent = text;
  }
  renderCorridors();
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
  TIERS.forEach(([id, label]) => {
    const chunk = items.filter((item) => item.tier === id);
    if (!chunk.length) return;
    const h = document.createElement("div");
    h.className = "tier-h";
    h.textContent = label;
    listEl.appendChild(h);
    chunk.forEach((item) => listEl.appendChild(rowFor(item)));
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
  if (fly && ev && map && ev.lon != null) focusPin(ev);
}

function paint(opts) {
  const n = ((report && report.events) || (bundle && bundle.events) || []).length;
  const hits = (report && report.items && report.items.length) || 0;
  const when = (report && report.as_of) || (bundle && bundle.as_of);
  statusEl.textContent = `${hits ? hits + " hits · " : ""}${n} live events`;
  const notes = (report && report.notes) || (bundle && bundle.notes) || [];
  notesEl.textContent = notes.join(" ") + (when ? " Updated " + new Date(when).toLocaleString("en-US", { timeZone: "America/New_York" }) + "." : "");
  renderList();
  if (map) renderMarkers();
  if (opts && opts.frame && report && map) frameDay();
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
    paint({ frame: true });
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
    routes: [],
    corridor: "",
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
