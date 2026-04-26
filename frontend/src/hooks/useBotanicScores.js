import { useEffect, useState } from "react";

/**
 * Fetches combined safety scores (crime + environment) for ALL botanic
 * streets from the /api/streets/botanic/scores bulk endpoint.
 */
export function useBotanicScores() {
  const [scoreMap, setScoreMap] = useState({});   // street_id → { score, crime_score, env_score }
  const [status, setStatus] = useState("idle");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");

    fetch("/api/streets/botanic/scores")
      .then((res) => {
        if (!res.ok) throw new Error(`API ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        const map = {};
        data.forEach((item) => {
          map[item.street_id] = item;
        });
        setScoreMap(map);
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { scoreMap, status };
}
