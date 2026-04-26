import { useEffect, useState } from "react";

// GeoJSON coords are [lng, lat]; Leaflet needs [lat, lng]
function toLatLng(coordinates) {
  return coordinates.map(([lng, lat]) => [lat, lng]);
}

export function useBotanicStreets() {
  const [streets, setStreets] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | loading | ready | error
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");

    fetch("/api/streets/botanic")
      .then((res) => {
        if (!res.ok) throw new Error(`API ${res.status}`);
        return res.json();
      })
      .then((geojson) => {
        if (cancelled) return;
        const parsed = (geojson.features ?? [])
          .filter((f) => f.geometry?.type === "LineString")
          .map((f) => ({
            id: f.properties.id,
            name: f.properties.name ?? "Unnamed street",
            highway: f.properties.highway ?? "unclassified",
            path: toLatLng(f.geometry.coordinates)
          }));
        setStreets(parsed);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { streets, status, error };
}
