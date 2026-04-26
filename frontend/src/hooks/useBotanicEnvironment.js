import { useEffect, useState } from "react";

export function useBotanicEnvironment() {
  const [envMap, setEnvMap] = useState({});   // street_id → env data
  const [status, setStatus] = useState("idle");

  useEffect(() => {
    setStatus("loading");
    fetch("/api/streets/botanic/environment")
      .then((res) => {
        if (!res.ok) throw new Error(`API ${res.status}`);
        return res.json();
      })
      .then((data) => {
        const map = {};
        data.forEach((item) => {
          map[item.street_id] = item;
        });
        setEnvMap(map);
        setStatus("ready");
      })
      .catch(() => setStatus("error"));
  }, []);

  return { envMap, status };
}
