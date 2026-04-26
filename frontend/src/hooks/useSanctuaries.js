import { useEffect, useState } from "react";

// Botanic area bounding box — filter out anything outside
const BOUNDS = {
  minLat: 54.575,
  maxLat: 54.600,
  minLng: -5.960,
  maxLng: -5.915,
};

function inBotanic(lat, lng) {
  return (
    lat >= BOUNDS.minLat &&
    lat <= BOUNDS.maxLat &&
    lng >= BOUNDS.minLng &&
    lng <= BOUNDS.maxLng
  );
}

// Map API types → our three UI categories
export function categorise(type = "") {
  const t = type.toLowerCase();
  if (t.includes("pharmacy") || t.includes("chemist")) return "pharmacy";
  if (
    t.includes("hospital") ||
    t.includes("clinic") ||
    t.includes("doctor") ||
    t.includes("gp") ||
    t.includes("medical") ||
    t.includes("dentist")
  )
    return "clinic";
  return "sanctuary";
}

export function useSanctuaries() {
  const [sanctuaries, setSanctuaries] = useState([]);
  const [status, setStatus] = useState("idle");

  useEffect(() => {
    setStatus("loading");
    fetch("/api/sanctuaries?limit=500")
      .then((r) => {
        if (!r.ok) throw new Error(`API ${r.status}`);
        return r.json();
      })
      .then((data) => {
        const filtered = (Array.isArray(data) ? data : [])
          .filter((s) => inBotanic(s.lat, s.lng))
          .map((s) => ({
            id: s.sanctuary_id || `${s.lat}_${s.lng}`,
            name: s.name || "Unknown",
            type: categorise(s.type),
            rawType: s.type,
            coords: [s.lat, s.lng],
            address: s.address || "",
            phone: s.phone || "",
            hours: s.opening_hours || "Hours unavailable",
            services: [s.type || "Safe location"],
            whatToExpect: "A safe, staffed location you can enter.",
          }));
        setSanctuaries(filtered);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return { sanctuaries, status };
}

export async function fetchNearestSanctuaries(lat, lng, limit = 10) {
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const res = await fetch(
    `/api/sanctuaries/nearest?lat=${lat}&lng=${lng}&limit=${limit}&time=${time}`
  );
  if (!res.ok) return [];
  const data = await res.json();
  return (Array.isArray(data) ? data : []).map((s) => ({
    id: s.sanctuary_id || `${s.lat}_${s.lng}`,
    name: s.name || "Unknown",
    type: categorise(s.type),
    rawType: s.type,
    coords: [s.lat, s.lng],
    distanceKm: (s.distance_m || 0) / 1000,
    address: s.address || "",
    phone: s.phone || "",
    hours: s.opening_hours || "Hours unavailable",
    services: [s.type || "Safe location"],
    whatToExpect: "A safe, staffed location you can enter.",
  }));
}
