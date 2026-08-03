const STATE = {
  player: null,
  map: null,
  socket: null,
  currentMode: "territory",
  selfMarker: null,
  selfLatLng: null,
  otherPlayers: {},
  territories: {},
  chests: {},
  graffiti: {},
  pendingChest: null,
  colors: ["#3df5c0", "#f5a623", "#ff3d8a", "#4d9fff", "#ff8a5c", "#c792ea"],

  streetViewOpen: false,
  heading: 0,
  manualWalking: false,
};

const SHOUT_RADIUS_M = 300;

function haversineMeters(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlambda = ((lng2 - lng1) * Math.PI) / 180;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dlambda / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function toRad(d) { return (d * Math.PI) / 180; }
function toDeg(r) { return (r * 180) / Math.PI; }

function bearingDegrees(lat1, lng1, lat2, lng2) {
  const p1 = toRad(lat1), p2 = toRad(lat2), dl = toRad(lng2 - lng1);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

function destinationPoint(lat, lng, bearingDeg, distM) {
  const R = 6371000;
  const delta = distM / R;
  const theta = toRad(bearingDeg);
  const p1 = toRad(lat), l1 = toRad(lng);
  const p2 = Math.asin(Math.sin(p1) * Math.cos(delta) + Math.cos(p1) * Math.sin(delta) * Math.cos(theta));
  const l2 = l1 + Math.atan2(
    Math.sin(theta) * Math.sin(delta) * Math.cos(p1),
    Math.cos(delta) - Math.sin(p1) * Math.sin(p2)
  );
  return { lat: toDeg(p2), lng: (((toDeg(l2) + 540) % 360) - 180) };
}

function normalizeAngleDiff(a) {
  return (((a + 180) % 360 + 360) % 360) - 180;
}

function toast(message) {
  const stack = document.getElementById("toast-stack");
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}