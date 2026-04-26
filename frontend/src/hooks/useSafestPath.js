import { useState } from "react";

export function useSafestPath() {
  const [path, setPath] = useState(null);     // [[lat,lng], ...]
  const [segments, setSegments] = useState([]); // route_segments array
  const [meta, setMeta] = useState(null);     // distance, avg safety score
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState(null);

  const findPath = async (startLat, startLng, endLat, endLng) => {
    setStatus("loading");
    setPath(null);
    setSegments([]);
    setMeta(null);
    setError(null);
    try {
      const res = await fetch(
        `/api/path/safest?start_lat=${startLat}&start_lng=${startLng}&end_lat=${endLat}&end_lng=${endLng}&max_snap_distance_m=200`
      );
      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || data.detail || `API ${res.status}`);
      }
      // path_coordinates is [[lat, lng], ...]
      setPath(data.path_coordinates || []);
      setSegments(data.route_segments || []);
      setMeta({
        distanceM: data.total_distance_m,
        avgSafetyScore: Math.round((data.average_safety_score || 0) * 100),
        weightedCost: data.total_weighted_cost,
      });
      setStatus("done");
      return data;
    } catch (e) {
      setError(e.message);
      setStatus("error");
      return null;
    }
  };

  const clear = () => {
    setPath(null);
    setSegments([]);
    setMeta(null);
    setStatus("idle");
    setError(null);
  };

  return { path, segments, meta, status, error, findPath, clear };
}
