import { useState } from "react";

export function useCoordScore() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [latlng, setLatlng] = useState(null);

  const fetchScore = async (lat, lng) => {
    setLoading(true);
    setResult(null);
    setError(null);
    setLatlng({ lat, lng });
    try {
      const res = await fetch(`/api/score/coord?lat=${lat}&lng=${lng}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setResult(null);
    setError(null);
    setLatlng(null);
  };

  return { result, loading, error, latlng, fetchScore, clear };
}
