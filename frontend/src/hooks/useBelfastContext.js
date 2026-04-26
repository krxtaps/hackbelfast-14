import { useEffect, useState } from "react";
import { belfastAreaProfiles } from "../data/belfastSafetyData";

function distanceInKm([lat1, lon1], [lat2, lon2]) {
  const toRad = (value) => (value * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 6371 * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

function getTimeRiskMultiplier(hour) {
  if (hour >= 22 || hour <= 4) return 0.8;
  if (hour >= 18) return 0.9;
  return 1;
}

export function useBelfastContext(position) {
  const [state, setState] = useState({
    status: "loading",
    areaProfile: null,
    advisory: "Loading Belfast context...",
    error: ""
  });

  useEffect(() => {
    let cancelled = false;

    setState((current) => ({
      ...current,
      status: "loading",
      advisory: "Loading Belfast context..."
    }));

    const timer = setTimeout(() => {
      if (cancelled) return;

      try {
        const withDistance = belfastAreaProfiles
          .map((profile) => ({
            ...profile,
            distanceKm: distanceInKm(position, profile.center)
          }))
          .sort((a, b) => a.distanceKm - b.distanceKm);

        const nearest = withDistance[0];
        const hour = new Date().getHours();
        const timeRiskMultiplier = getTimeRiskMultiplier(hour);
        const adjustedProfile = {
          ...nearest,
          adjustedLighting: Number((nearest.lighting * timeRiskMultiplier).toFixed(2)),
          adjustedFootfall: Number((nearest.footfall * timeRiskMultiplier).toFixed(2)),
          timeRiskMultiplier
        };

        setState({
          status: "ready",
          areaProfile: adjustedProfile,
          advisory: `Area profile active: ${adjustedProfile.name}. Time-adjusted lighting ${Math.round(adjustedProfile.adjustedLighting * 100)}%.`,
          error: ""
        });
      } catch (error) {
        setState({
          status: "error",
          areaProfile: null,
          advisory: "Belfast context unavailable. Using route-only fallback.",
          error: error instanceof Error ? error.message : "Unknown Belfast data error"
        });
      }
    }, 350);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [position]);

  return state;
}

export function scoreRouteForBelfast({
  routePoints,
  destinationType,
  nearbyStreetRisk,
  areaProfile
}) {
  if (!routePoints || routePoints.length < 2) return null;

  const riskToScore = { low: 95, medium: 70, high: 42 };
  const destinationBonus = { sanctuary: 8, clinic: 7, pharmacy: 5 };
  const complexityPenalty = Math.max(0, routePoints.length - 2) * 3.5;
  const lightingScore = Math.round((areaProfile?.adjustedLighting ?? 0.65) * 100);
  const footfallScore = Math.round((areaProfile?.adjustedFootfall ?? 0.6) * 100);
  const cctvScore = Math.round((areaProfile?.cctvCoverage ?? 0.6) * 100);
  const emergencyAccessScore = Math.round((areaProfile?.emergencyAccess ?? 0.65) * 100);
  const streetRiskScore = riskToScore[nearbyStreetRisk] ?? 65;
  const bonus = destinationBonus[destinationType] ?? 4;

  const weighted =
    lightingScore * 0.22 +
    footfallScore * 0.2 +
    cctvScore * 0.18 +
    emergencyAccessScore * 0.15 +
    streetRiskScore * 0.25 -
    complexityPenalty +
    bonus;

  const overallScore = Math.max(0, Math.min(100, Math.round(weighted)));
  const safetyGrade =
    overallScore >= 80 ? "A" : overallScore >= 68 ? "B" : overallScore >= 55 ? "C" : "D";

  return {
    overallScore,
    safetyGrade,
    breakdown: {
      lightingScore,
      footfallScore,
      cctvScore,
      emergencyAccessScore,
      streetRiskScore,
      complexityPenalty: Number(complexityPenalty.toFixed(1))
    }
  };
}
