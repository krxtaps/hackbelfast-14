import { useEffect, useMemo, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
  useMap,
  useMapEvents
} from "react-leaflet";
import { ButtonComponent } from "@syncfusion/ej2-react-buttons";
import {
  AccordionComponent,
  AccordionItemDirective,
  AccordionItemsDirective,
} from "@syncfusion/ej2-react-navigations";
import { ProgressBarComponent } from "@syncfusion/ej2-react-progressbar";
import { ToastComponent } from "@syncfusion/ej2-react-notifications";
import {
  belfastAreaProfiles,
  dangerZones,
  safetyTips,
  streetSafetySegments,
  supportLocations,
  userStartPosition
} from "./data/belfastSafetyData";
import { scoreRouteForBelfast, useBelfastContext } from "./hooks/useBelfastContext";
import { useBotanicStreets } from "./hooks/useBotanicStreets";
import { useBotanicEnvironment } from "./hooks/useBotanicEnvironment";
import { useCoordScore } from "./hooks/useCoordScore";

// ── Constants ────────────────────────────────────────────────────────────────

const typeLabels = {
  pharmacy: "Pharmacy",
  clinic: "Urgent Care",
  sanctuary: "Sanctuary"
};

const typeColors = {
  pharmacy: "#22c55e",
  clinic: "#3b82f6",
  sanctuary: "#8b5cf6"
};

const typeIcons = {
  pharmacy: "💊",
  clinic: "🏥",
  sanctuary: "🕊️"
};

const riskColors = {
  low: "#16a34a",
  medium: "#f59e0b",
  high: "#ef4444"
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function distanceInKm([lat1, lon1], [lat2, lon2]) {
  const toRad = (v) => (v * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function routeDistanceKm(points) {
  if (!points || points.length < 2) return 0;
  let total = 0;
  for (let i = 1; i < points.length; i++) total += distanceInKm(points[i - 1], points[i]);
  return total;
}

function scoreColor(score) {
  return score >= 75 ? "#16a34a" : score >= 55 ? "#f59e0b" : "#ef4444";
}

function envScoreColor(score) {
  // Environment scores range 79–88, so use tight thresholds
  if (score == null) return "#94a3b8";
  if (score >= 86) return "#16a34a";   // top ~35% — safest
  if (score >= 84) return "#eab308";   // middle band
  if (score >= 81) return "#f97316";   // lower band
  return "#ef4444";                     // bottom ~10% — caution
}

function botanicLineStyle(highway, envScore) {
  const base = { weight: 3, opacity: 0.85 };
  if (highway === "primary" || highway === "secondary") base.weight = 5;
  else if (highway === "tertiary") base.weight = 4;
  base.color = envScoreColor(envScore);
  return base;
}

function scoreGrade(score) {
  if (score == null) return "—";
  if (score >= 75) return "SAFE";
  if (score >= 55) return "MODERATE";
  return "CAUTION";
}

// ── Sub-components ───────────────────────────────────────────────────────────

function MapClickHandler({ onMapClick }) {
  useMapEvents({ click: (e) => onMapClick(e.latlng.lat, e.latlng.lng) });
  return null;
}

function RecenterMap({ center }) {
  const map = useMap();
  useEffect(() => {
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    map.setView(center, map.getZoom(), { animate: !reduced });
  }, [center, map]);
  return null;
}

function LocationDetail({ loc, onRoute }) {
  return (
    <div className="location-detail">
      <div className="loc-meta-row">
        <span
          className="loc-type-chip"
          style={{
            background: typeColors[loc.type] + "18",
            color: typeColors[loc.type],
            border: `1px solid ${typeColors[loc.type]}50`
          }}
        >
          {typeIcons[loc.type]} {typeLabels[loc.type]}
        </span>
        <span className="loc-dist-badge">{loc.distanceKm.toFixed(2)} km</span>
      </div>
      <p className="loc-line">📍 {loc.address}</p>
      <p className="loc-line">📞 {loc.phone}</p>
      <p className="loc-line">🕐 {loc.hours}</p>
      <p className="services-label">Services offered:</p>
      <ul className="services-list">
        {loc.services.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
      <div className="expect-box">
        <strong>What to expect:</strong> {loc.whatToExpect}
      </div>
      <ButtonComponent cssClass="e-primary e-small route-here-btn" onClick={onRoute}>
        Navigate Here →
      </ButtonComponent>
    </div>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────

function App() {
  const [currentPosition, setCurrentPosition] = useState(userStartPosition);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [routePoints, setRoutePoints] = useState([]);
  const [routeTitle, setRouteTitle] = useState("");
  const [locationState, setLocationState] = useState("loading");
  const [locationStatus, setLocationStatus] = useState("Requesting your location…");
  const [routeNotice, setRouteNotice] = useState("");
  const [isOnline, setIsOnline] = useState(window.navigator.onLine);
  const [activeFilters, setActiveFilters] = useState(["pharmacy", "clinic", "sanctuary"]);
  const [activeTab, setActiveTab] = useState(0);
  const [streetSearch, setStreetSearch] = useState("");
  const [streetSearchResults, setStreetSearchResults] = useState([]);
  const [streetSearchLoading, setStreetSearchLoading] = useState(false);
  const toastRef = useRef(null);

  const belfastContext = useBelfastContext(currentPosition);
  const botanicStreets = useBotanicStreets();
  const botanicEnv = useBotanicEnvironment();
  const coordScore = useCoordScore();
  const selectedDistKm = selectedLocation
    ? distanceInKm(currentPosition, selectedLocation.coords)
    : null;

  // Online/offline detection
  useEffect(() => {
    const on = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // Geolocation
  const requestCurrentLocation = () => {
    if (!navigator.geolocation) {
      setLocationState("unsupported");
      setLocationStatus("Geolocation not supported. Using demo Belfast location.");
      return;
    }
    setLocationState("loading");
    setLocationStatus("Requesting your location…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCurrentPosition([pos.coords.latitude, pos.coords.longitude]);
        setLocationState("ready");
        setLocationStatus("Using your current location.");
        setRouteNotice("");
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          setLocationState("denied");
          setLocationStatus("Location denied. Using demo Belfast location.");
        } else {
          setLocationState("error");
          setLocationStatus("Could not get location. Using demo Belfast location.");
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  };

  useEffect(() => {
    requestCurrentLocation();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Nearest locations
  const nearest = useMemo(() => {
    const nearestFor = (type) =>
      supportLocations
        .filter((p) => p.type === type)
        .reduce((best, p) => {
          const d = distanceInKm(currentPosition, p.coords);
          return !best || d < best.distanceKm ? { ...p, distanceKm: d } : best;
        }, null);

    const nearestPharmacy = nearestFor("pharmacy");
    const nearestClinic = nearestFor("clinic");
    const nearestSanctuary = nearestFor("sanctuary");
    const nearestMedical = [nearestPharmacy, nearestClinic]
      .filter(Boolean)
      .reduce((best, p) => (!best || p.distanceKm < best.distanceKm ? p : best), null);

    return { nearestMedical, nearestSanctuary };
  }, [currentPosition]);

  // Streets sorted by proximity
  const streetsByDistance = useMemo(
    () =>
      streetSafetySegments
        .map((s) => ({
          ...s,
          nearestPointDistance: Math.min(...s.path.map((pt) => distanceInKm(currentPosition, pt)))
        }))
        .sort((a, b) => a.nearestPointDistance - b.nearestPointDistance),
    [currentPosition]
  );

  const currentRisk = useMemo(
    () => (streetsByDistance.length === 0 ? "low" : streetsByDistance[0].level),
    [streetsByDistance]
  );

  const activeRouteScore = useMemo(
    () =>
      scoreRouteForBelfast({
        routePoints,
        destinationType: selectedLocation?.type,
        nearbyStreetRisk: currentRisk,
        areaProfile: belfastContext.areaProfile
      }),
    [routePoints, selectedLocation, currentRisk, belfastContext.areaProfile]
  );

  // All locations sorted by distance from user
  const locationsByDistance = useMemo(
    () =>
      supportLocations
        .map((loc) => ({ ...loc, distanceKm: distanceInKm(currentPosition, loc.coords) }))
        .sort((a, b) => a.distanceKm - b.distanceKm),
    [currentPosition]
  );

  // Route builder
  const buildRoute = ({ location, title, includeLowRiskDetour = false }) => {
    if (!location) {
      setRouteNotice("No suitable destination found in Belfast data.");
      return;
    }

    let points;
    let fullTitle;

    if (includeLowRiskDetour) {
      const lowRiskStreet = streetsByDistance.find((s) => s.level === "low");
      if (!lowRiskStreet) {
        setRouteNotice("No low-risk street available for safer journey.");
        return;
      }
      points = [
        currentPosition,
        lowRiskStreet.path[0],
        lowRiskStreet.path[lowRiskStreet.path.length - 1],
        location.coords
      ];
      fullTitle = `${title} via ${lowRiskStreet.name}`;
    } else {
      points = [currentPosition, location.coords];
      fullTitle = title;
    }

    setSelectedLocation(location);
    setRouteTitle(fullTitle);
    setRoutePoints(points);
    setRouteNotice("");

    toastRef.current?.show({
      title: "Route set",
      content: `Navigating to ${location.name}`,
      position: { X: "Right", Y: "Bottom" },
      timeOut: 3500,
      showCloseButton: true
    });
  };

  const showMinorInjuries = () =>
    buildRoute({ location: nearest.nearestMedical, title: "Minor injuries route" });
  const showSanctuary = () =>
    buildRoute({ location: nearest.nearestSanctuary, title: "Nearest sanctuary" });
  const showSaferJourney = () =>
    buildRoute({
      location: nearest.nearestSanctuary || nearest.nearestMedical,
      title: "Safer journey",
      includeLowRiskDetour: true
    });
  const clearRoute = () => {
    setSelectedLocation(null);
    setRoutePoints([]);
    setRouteTitle("");
    setRouteNotice("");
  };

  const toggleFilter = (type) =>
    setActiveFilters((prev) =>
      prev.includes(type) ? prev.filter((f) => f !== type) : [...prev, type]
    );

  // Voice guide — placeholder using browser TTS.
  // TODO: swap speechSynthesis for ElevenLabs streaming TTS for natural voice.
  const speakRouteGuide = () => {
    if (!selectedLocation) {
      toastRef.current?.show({
        title: "No active route",
        content: "Set a route first, then tap Voice Guide.",
        position: { X: "Right", Y: "Bottom" },
        timeOut: 2500
      });
      return;
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const msg = new SpeechSynthesisUtterance(
        `Route set. Navigating to ${selectedLocation.name}, a ${typeLabels[selectedLocation.type]} ` +
          `located ${selectedDistKm?.toFixed(1)} kilometres from your current position. ` +
          `The current area risk level is ${currentRisk}. Stay on well-lit routes.`
      );
      window.speechSynthesis.speak(msg);
    }
  };

  const disableActions = locationState === "loading" || belfastContext.status === "loading";

  const handleMapClick = (lat, lng) => coordScore.fetchScore(lat, lng);

  const handleStreetSearch = async (q) => {
    setStreetSearch(q);
    if (!q.trim()) { setStreetSearchResults([]); return; }
    setStreetSearchLoading(true);
    try {
      const res = await fetch(`/api/streets/search?q=${encodeURIComponent(q)}`);
      setStreetSearchResults(res.ok ? await res.json() : []);
    } catch { setStreetSearchResults([]); }
    finally { setStreetSearchLoading(false); }
  };

  // ── Tab content functions ────────────────────────────────────────────────

  const getHelpContent = () => (
    <div className="tab-panel">
      <div className="quick-action-grid">
        <ButtonComponent
          cssClass="e-primary action-btn"
          onClick={showMinorInjuries}
          disabled={disableActions}
        >
          💊 Minor Injuries
        </ButtonComponent>
        <ButtonComponent
          cssClass="e-success action-btn"
          onClick={showSanctuary}
          disabled={disableActions}
        >
          🕊️ Sanctuary
        </ButtonComponent>
        <ButtonComponent
          cssClass="e-info action-btn"
          onClick={showSaferJourney}
          disabled={disableActions}
        >
          🗺️ Safe Journey
        </ButtonComponent>
      </div>

      <div className="filter-strip">
        <span className="filter-label">Show on map:</span>
        <div className="filter-chips">
          {["pharmacy", "clinic", "sanctuary"].map((type) => (
            <button
              key={type}
              className={`filter-chip ${activeFilters.includes(type) ? "chip-on" : "chip-off"}`}
              style={
                activeFilters.includes(type)
                  ? {
                      borderColor: typeColors[type],
                      color: typeColors[type],
                      background: typeColors[type] + "15"
                    }
                  : {}
              }
              onClick={() => toggleFilter(type)}
            >
              {typeIcons[type]} {typeLabels[type]}
            </button>
          ))}
        </div>
      </div>

      <div className="loc-status-row">
        <span className="loc-status-text">{locationStatus}</span>
        <ButtonComponent
          cssClass="e-outline e-small"
          onClick={requestCurrentLocation}
          disabled={locationState === "loading"}
        >
          📍 My Location
        </ButtonComponent>
      </div>

      <h3 className="section-heading">Nearest Support Locations</h3>

      <AccordionComponent
        key={currentPosition.join(",")}
        expandMode="Single"
      >
        <AccordionItemsDirective>
          {locationsByDistance.slice(0, 8).map((loc, i) => (
            <AccordionItemDirective
              key={loc.id}
              header={`${typeIcons[loc.type]}  ${loc.name}  —  ${loc.distanceKm.toFixed(2)} km`}
              content={() => (
                <LocationDetail
                  loc={loc}
                  onRoute={() =>
                    buildRoute({ location: loc, title: `Route to ${loc.name}` })
                  }
                />
              )}
              expanded={i === 0}
            />
          ))}
        </AccordionItemsDirective>
      </AccordionComponent>
    </div>
  );

  const routeContent = () => (
    <div className="tab-panel">
      {!selectedLocation ? (
        <div className="empty-state">
          <div className="empty-icon">🗺️</div>
          <p className="empty-title">No active route</p>
          <p className="empty-sub">
            Use the <strong>Get Help</strong> tab to navigate to the nearest pharmacy, clinic, or
            sanctuary.
          </p>
        </div>
      ) : (
        <>
          <div className="route-summary-card">
            <div className="route-dest-row">
              <span
                className="loc-type-chip"
                style={{
                  background: typeColors[selectedLocation.type] + "18",
                  color: typeColors[selectedLocation.type],
                  border: `1px solid ${typeColors[selectedLocation.type]}50`
                }}
              >
                {typeIcons[selectedLocation.type]} {typeLabels[selectedLocation.type]}
              </span>
              <span className="route-dist">{selectedDistKm?.toFixed(2)} km</span>
            </div>
            <h3 className="route-dest-name">{selectedLocation.name}</h3>
            <p className="route-meta">
              Route length: {routeDistanceKm(routePoints).toFixed(2)} km ·{" "}
              {routeTitle}
            </p>
            <p className="route-address">📍 {selectedLocation.address}</p>
            <div className="route-actions">
              <ButtonComponent cssClass="e-outline e-small" onClick={clearRoute}>
                ✕ Clear Route
              </ButtonComponent>
              <ButtonComponent cssClass="e-outline e-small voice-btn" onClick={speakRouteGuide}>
                🔊 Voice Guide
              </ButtonComponent>
            </div>
            <p className="voice-note">
              Voice Guide uses browser TTS now — ElevenLabs natural voice ready to wire in.
            </p>
          </div>

          {activeRouteScore && (
            <div className="score-card">
              <h3 className="section-heading">Route Safety Score</h3>
              <div className="score-hero-row">
                <span className="score-big">{activeRouteScore.overallScore}</span>
                <span className="score-label">/100</span>
                <span
                  className="score-grade"
                  style={{
                    background: scoreColor(activeRouteScore.overallScore) + "18",
                    color: scoreColor(activeRouteScore.overallScore),
                    border: `2px solid ${scoreColor(activeRouteScore.overallScore)}50`
                  }}
                >
                  {activeRouteScore.safetyGrade}
                </span>
              </div>
              <ProgressBarComponent
                id="overall-score-bar"
                type="Linear"
                value={activeRouteScore.overallScore}
                height="18"
                minimum={0}
                maximum={100}
                progressColor={scoreColor(activeRouteScore.overallScore)}
                trackColor="#e2e8f0"
                animation={{ enable: true, duration: 1200 }}
              />

              <div className="breakdown-list">
                {[
                  ["💡 Lighting", activeRouteScore.breakdown.lightingScore],
                  ["🚶 Footfall", activeRouteScore.breakdown.footfallScore],
                  ["📹 CCTV Coverage", activeRouteScore.breakdown.cctvScore],
                  ["🚑 Emergency Access", activeRouteScore.breakdown.emergencyAccessScore],
                  ["⚠️ Street Risk Score", activeRouteScore.breakdown.streetRiskScore]
                ].map(([label, val]) => (
                  <div key={label} className="breakdown-row">
                    <div className="breakdown-header">
                      <span className="breakdown-label">{label}</span>
                      <span className="breakdown-val">{val}</span>
                    </div>
                    <ProgressBarComponent
                      id={`bd-${label.replace(/[^a-z0-9]/gi, "")}`}
                      type="Linear"
                      value={val}
                      height="8"
                      minimum={0}
                      maximum={100}
                      progressColor={scoreColor(val)}
                      trackColor="#e2e8f0"
                      animation={{ enable: true, duration: 900 }}
                    />
                  </div>
                ))}
              </div>
              <p className="small-note">
                Complexity penalty: −{activeRouteScore.breakdown.complexityPenalty}
              </p>
            </div>
          )}
        </>
      )}

      <div className="tips-card">
        <h3 className="section-heading">
          Safety Tips —{" "}
          <span style={{ color: riskColors[currentRisk] }}>{currentRisk.toUpperCase()} RISK</span>
        </h3>
        <ul className="tips-list">
          {safetyTips[currentRisk].map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </div>
    </div>
  );

  const safetyContent = () => (
    <div className="tab-panel">
      <div className="advisory-card">
        <p className="advisory-text">{belfastContext.advisory}</p>
      </div>

      <h3 className="section-heading">Belfast Area Safety Profiles</h3>
      <p className="small-note" style={{ marginBottom: "0.75rem" }}>
        Scores reflect lighting, footfall, CCTV coverage and emergency access — adjusted for
        time of day.
      </p>

      {belfastAreaProfiles.map((area) => {
        const score = Math.round(
          ((area.lighting + area.footfall + area.cctvCoverage + area.emergencyAccess) / 4) * 100
        );
        const isNearest = belfastContext.areaProfile?.id === area.id;
        return (
          <div key={area.id} className={`area-block ${isNearest ? "area-nearest" : ""}`}>
            <div className="area-header-row">
              <span className="area-name">
                {isNearest && <span className="you-are-here">📍 </span>}
                {area.name}
                {isNearest && <span className="you-badge"> You are here</span>}
              </span>
              <span
                className="area-score-chip"
                style={{
                  background: scoreColor(score) + "18",
                  color: scoreColor(score),
                  border: `1px solid ${scoreColor(score)}50`
                }}
              >
                {score}%
              </span>
            </div>
            <ProgressBarComponent
              id={`area-${area.id}`}
              type="Linear"
              value={score}
              height="14"
              minimum={0}
              maximum={100}
              progressColor={scoreColor(score)}
              trackColor="#e2e8f0"
              animation={{ enable: true, duration: 1000 }}
            />
            <div className="area-metrics-row">
              <span title="Lighting">💡 {Math.round(area.lighting * 100)}%</span>
              <span title="Footfall">🚶 {Math.round(area.footfall * 100)}%</span>
              <span title="CCTV">📹 {Math.round(area.cctvCoverage * 100)}%</span>
              <span title="Emergency Access">🚑 {Math.round(area.emergencyAccess * 100)}%</span>
            </div>
          </div>
        );
      })}

      <h3 className="section-heading" style={{ marginTop: "1.25rem" }}>
        Nearby Street Risk
      </h3>
      <ul className="street-risk-list">
        {streetsByDistance.slice(0, 6).map((s) => (
          <li key={s.id} className="street-risk-item">
            <span className="street-dot" style={{ background: riskColors[s.level] }} />
            <span className="street-name">{s.name}</span>
            <span
              className="risk-chip"
              style={{
                background: riskColors[s.level] + "18",
                color: riskColors[s.level],
                border: `1px solid ${riskColors[s.level]}50`
              }}
            >
              {s.level.toUpperCase()}
            </span>
          </li>
        ))}
      </ul>

      {/* 🆕 Street search */}
      <div className="street-search-section" style={{ marginTop: "1.25rem" }}>
        <h3 className="section-heading">Search Streets</h3>
        <input
          type="text"
          className="street-search-input"
          placeholder="Search for a street…"
          value={streetSearch}
          onChange={(e) => handleStreetSearch(e.target.value)}
          style={{
            width: "100%",
            padding: "8px 10px",
            borderRadius: 6,
            border: "1px solid #cbd5e1",
            fontSize: 14,
            boxSizing: "border-box"
          }}
        />
        {streetSearchLoading && (
          <p className="small-note" style={{ marginTop: 4 }}>Searching…</p>
        )}
        {streetSearchResults.length > 0 && (
          <ul className="street-risk-list" style={{ marginTop: 8 }}>
            {streetSearchResults.map((r) => {
              const env = botanicEnv.envMap[r.id];
              const score = env?.score ?? null;
              return (
                <li key={r.id} className="street-risk-item">
                  <span
                    className="street-dot"
                    style={{
                      background: score != null && score >= 85
                        ? "#16a34a"
                        : score != null && score >= 80
                        ? "#f59e0b"
                        : "#94a3b8"
                    }}
                  />
                  <span className="street-name">{r.name || r.id}</span>
                  <span
                    className="risk-chip"
                    style={{
                      background: score != null ? (score >= 85 ? "#16a34a18" : "#f59e0b18") : "#94a3b818",
                      color: score != null ? (score >= 85 ? "#16a34a" : "#f59e0b") : "#94a3b8",
                      border: `1px solid ${score != null ? (score >= 85 ? "#16a34a50" : "#f59e0b50") : "#94a3b850"}`
                    }}
                  >
                    {score != null ? `${score}/100` : "N/A"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        {streetSearch && !streetSearchLoading && streetSearchResults.length === 0 && (
          <p className="small-note" style={{ marginTop: 4 }}>No streets found for "{streetSearch}"</p>
        )}
      </div>
    </div>
  );

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-panel">
        Skip to controls
      </a>

      {/* ── Map ──────────────────────────────────────────────────────────── */}
      <section className="map-section" aria-label="Belfast safety map">
        <MapContainer center={currentPosition} zoom={13} className="fullmap">
          <RecenterMap center={currentPosition} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* Colour-coded danger zone polygons */}
          {dangerZones.map((zone) => (
            <Polygon
              key={zone.id}
              positions={zone.polygon}
              pathOptions={{
                color: riskColors[zone.level],
                fillColor: riskColors[zone.level],
                weight: 1.5,
                fillOpacity: 0.15,
                opacity: 0.45
              }}
            >
              <Popup>
                <strong>{zone.name}</strong>
                <br />
                Risk level: {zone.level.toUpperCase()}
              </Popup>
            </Polygon>
          ))}

          {/* Street-level safety overlays */}
          {streetSafetySegments.map((s) => (
            <Polyline
              key={s.id}
              positions={s.path}
              pathOptions={{ color: riskColors[s.level], weight: 6, opacity: 0.75 }}
            >
              <Popup>
                <strong>{s.name}</strong>
                <br />
                Safety: {s.level.toUpperCase()}
                <br />
                {s.notes}
              </Popup>
            </Polyline>
          ))}

          {/* Support location markers (filtered) */}
          {supportLocations
            .filter((loc) => activeFilters.includes(loc.type))
            .map((loc) => (
              <CircleMarker
                key={loc.id}
                center={loc.coords}
                radius={9}
                pathOptions={{
                  color: typeColors[loc.type],
                  fillColor: typeColors[loc.type],
                  fillOpacity: 0.9
                }}
              >
                <Popup>
                  <strong>{loc.name}</strong>
                  <br />
                  {typeLabels[loc.type]}
                  <br />
                  🕐 {loc.hours}
                  <br />
                  📞 {loc.phone}
                </Popup>
              </CircleMarker>
            ))}

          {/* User position */}
          <CircleMarker
            center={currentPosition}
            radius={10}
            pathOptions={{ color: "#0f172a", fillColor: "#0f172a", fillOpacity: 0.95 }}
          >
            <Popup>{locationStatus}</Popup>
          </CircleMarker>

          {/* Active route line */}
          {routePoints.length > 1 && (
            <Polyline
              positions={routePoints}
              pathOptions={{ color: "#0ea5e9", weight: 7, dashArray: "10 8", opacity: 0.9 }}
            />
          )}

          {/* 🆕 API-loaded botanic street overlays (from Overpass) */}
          {botanicStreets.status === "ready" &&
            botanicStreets.streets.map((street) => {
              const env = botanicEnv.envMap[street.id];
              const score = env?.score ?? null;
              return (
                <Polyline
                  key={street.id}
                  positions={street.path}
                  pathOptions={botanicLineStyle(street.highway, score)}
                >
                  <Popup>
                    <strong>{street.name || "Unnamed"}</strong>
                    <br />
                    Highway: {street.highway}
                    <br />
                    Environment score: {score != null ? `${score}/100` : "N/A"}
                    <br />
                    {env?.reasons?.slice(0, 2).join(" · ")}
                  </Popup>
                </Polyline>
              );
            })}

          {/* 🆕 Coord score popup when user clicks the map */}
          {coordScore.result && coordScore.latlng && (
            <CircleMarker
              center={[coordScore.latlng.lat, coordScore.latlng.lng]}
              radius={12}
              pathOptions={{
                color: scoreColor(coordScore.result.overallScore ?? 50),
                fillColor: scoreColor(coordScore.result.overallScore ?? 50),
                fillOpacity: 0.6,
                weight: 3
              }}
            >
              <Popup>
                <strong>Location Safety Score</strong>
                <br />
                Overall: {coordScore.result.overallScore ?? "—"}/100
                <br />
                <button
                  onClick={() => coordScore.clear()}
                  style={{
                    marginTop: 4,
                    padding: "2px 8px",
                    fontSize: 12,
                    cursor: "pointer"
                  }}
                >
                  Dismiss
                </button>
              </Popup>
            </CircleMarker>
          )}

          {/* 🆕 Map click handler + coord score marker */}
          <MapClickHandler onMapClick={handleMapClick} />
        </MapContainer>

        {/* Map legend overlay */}
        <div className="map-legend" aria-label="Map legend">
          <p className="legend-title">Risk Zones</p>
          {[
            ["low", "#16a34a", "Low"],
            ["medium", "#f59e0b", "Medium"],
            ["high", "#ef4444", "High"]
          ].map(([, color, label]) => (
            <div key={label} className="legend-row">
              <span className="legend-swatch" style={{ background: color }} />
              <span>{label}</span>
            </div>
          ))}
          <div className="legend-divider" />
          <p className="legend-title">Locations</p>
          {Object.entries(typeColors).map(([type, color]) => (
            <div key={type} className="legend-row">
              <span className="legend-swatch" style={{ background: color }} />
              <span>
                {typeIcons[type]} {typeLabels[type]}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Info Panel ───────────────────────────────────────────────────── */}
      <section id="main-panel" className="panel-section">
        <div className="panel-header">
          <div className="panel-title-col">
            <h1 className="app-title">Belfast Safe</h1>
            <p className="app-subtitle">Street-level safety companion</p>
          </div>
          <div className="panel-header-right">
            <span className={`risk-pill risk-${currentRisk}`}>
              {currentRisk.toUpperCase()} RISK
            </span>
            <button
              className="sos-btn"
              onClick={showMinorInjuries}
              aria-label="Emergency SOS — find nearest help"
              disabled={disableActions}
            >
              SOS
            </button>
          </div>
        </div>

        {/* Status banners */}
        {!isOnline && (
          <div className="state-banner warning" role="status">
            Offline — using cached placeholder data
          </div>
        )}
        {(locationState === "denied" || locationState === "error") && (
          <div className="state-banner warning" role="status">
            Live location unavailable — using demo Belfast position
          </div>
        )}
        {belfastContext.status === "error" && (
          <div className="state-banner error" role="alert">
            Context error: {belfastContext.error}
          </div>
        )}
        {routeNotice && (
          <div className="state-banner error" role="alert">
            {routeNotice}
          </div>
        )}

        {/* Custom tab navigation */}
        <div className="tab-wrapper">
          <div className="custom-tab-header" role="tablist">
            {[
              { label: "🆘 Get Help" },
              { label: "🗺️ Route" },
              { label: "📊 Safety Data" },
            ].map((t, i) => (
              <button
                key={i}
                role="tab"
                aria-selected={activeTab === i}
                className={`custom-tab-btn${activeTab === i ? " active" : ""}`}
                onClick={() => setActiveTab(i)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="custom-tab-content">
            {activeTab === 0 && getHelpContent()}
            {activeTab === 1 && routeContent()}
            {activeTab === 2 && safetyContent()}
          </div>
        </div>
      </section>

      <ToastComponent ref={toastRef} />
    </div>
  );
}

export default App;
