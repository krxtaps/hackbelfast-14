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
import { AutoCompleteComponent } from "@syncfusion/ej2-react-dropdowns";
import { userStartPosition, safetyTips } from "./data/belfastSafetyData";
import { useBotanicStreets } from "./hooks/useBotanicStreets";
import { useBotanicEnvironment } from "./hooks/useBotanicEnvironment";
import { useCoordScore } from "./hooks/useCoordScore";
import { useIncidentReport } from "./hooks/useIncidentReport";
import { useSanctuaries, fetchNearestSanctuaries } from "./hooks/useSanctuaries";
import { useSafestPath } from "./hooks/useSafestPath";

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

// Percentile thresholds computed from all street scores
function computePercentiles(envMap) {
  const scores = Object.values(envMap)
    .map((e) => e.score)
    .filter((s) => s != null)
    .sort((a, b) => a - b);
  if (scores.length < 3) return { p33: 70, p66: 80 };
  return {
    p33: scores[Math.floor(scores.length * 0.33)],
    p66: scores[Math.floor(scores.length * 0.66)],
  };
}

function percentileColor(score, p33, p66) {
  if (score == null) return "#94a3b8";
  if (score >= p66) return "#16a34a";  // top third  → green
  if (score >= p33) return "#f59e0b";  // mid third  → amber
  return "#ef4444";                     // bottom third → red
}

// Fallback (no percentiles yet)
function envScoreColor(score) {
  if (score == null) return "#94a3b8";
  return score >= 80 ? "#16a34a" : score >= 75 ? "#f59e0b" : "#ef4444";
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
  const [incidentModalOpen, setIncidentModalOpen] = useState(false);
  const [incidentType, setIncidentType] = useState("suspicious_activity");
  const [incidentDesc, setIncidentDesc] = useState("");
  const [streetRouteFromSelected, setStreetRouteFromSelected] = useState(null);
  const [streetRouteToSelected, setStreetRouteToSelected] = useState(null);
  const [streetRouteLoading, setStreetRouteLoading] = useState(false);
  const toastRef = useRef(null);
  const fromACRef = useRef(null);
  const toACRef = useRef(null);

  const botanicStreets = useBotanicStreets();
  const botanicEnv = useBotanicEnvironment();
  const coordScore = useCoordScore();
  const incidentReport = useIncidentReport();
  const { sanctuaries, status: sanctuariesStatus } = useSanctuaries();
  const safestPath = useSafestPath();

  // Percentile thresholds — recomputed when env data loads
  const percentiles = useMemo(
    () => computePercentiles(botanicEnv.envMap),
    [botanicEnv.envMap]
  );

  // Deduplicated street list for AutoComplete data source
  const streetDataSource = useMemo(() => {
    const seen = new Set();
    return botanicStreets.streets
      .filter((s) => s.name && !seen.has(s.name) && seen.add(s.name))
      .map((s) => ({ id: s.id, text: s.name }))
      .sort((a, b) => a.text.localeCompare(b.text));
  }, [botanicStreets.streets]);

  const selectedDistKm = selectedLocation
    ? distanceInKm(currentPosition, selectedLocation.coords)
    : null;

  // Nearest sanctuaries by type (from loaded list, sorted by distance)
  const nearest = useMemo(() => {
    if (!sanctuaries.length) return { nearestMedical: null, nearestSanctuary: null };
    const withDist = sanctuaries.map((s) => ({
      ...s,
      distanceKm: distanceInKm(currentPosition, s.coords),
    }));
    const nearestFor = (type) =>
      withDist
        .filter((s) => s.type === type)
        .sort((a, b) => a.distanceKm - b.distanceKm)[0] || null;
    const nearestPharmacy = nearestFor("pharmacy");
    const nearestClinic = nearestFor("clinic");
    const nearestSanctuary = nearestFor("sanctuary");
    const nearestMedical = [nearestPharmacy, nearestClinic]
      .filter(Boolean)
      .sort((a, b) => a.distanceKm - b.distanceKm)[0] || null;
    return { nearestMedical, nearestSanctuary };
  }, [sanctuaries, currentPosition]);

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

  // Route score from pathfinding result
  const activeRouteScore = safestPath.meta
    ? safestPath.meta.avgSafetyScore
    : null;

  // All sanctuaries sorted by distance from user
  const locationsByDistance = useMemo(
    () =>
      sanctuaries
        .map((loc) => ({ ...loc, distanceKm: distanceInKm(currentPosition, loc.coords) }))
        .sort((a, b) => a.distanceKm - b.distanceKm),
    [sanctuaries, currentPosition]
  );

  // Route builder — uses the safest-path API
  const buildRoute = async ({ location, title }) => {
    if (!location) {
      setRouteNotice("No suitable destination found in the Botanic area.");
      return;
    }
    setSelectedLocation(location);
    setRouteTitle(title);
    setRouteNotice("");
    safestPath.clear();

    const result = await safestPath.findPath(
      currentPosition[0], currentPosition[1],
      location.coords[0], location.coords[1]
    );

    if (result && result.path_coordinates) {
      setRoutePoints(result.path_coordinates);
    } else {
      // Fallback straight line if pathfinding fails
      setRoutePoints([currentPosition, location.coords]);
      if (result === null) setRouteNotice("Could not find a street-level path — showing straight line.");
    }

    toastRef.current?.show({
      title: "Route set",
      content: `Navigating to ${location.name}`,
      position: { X: "Right", Y: "Bottom" },
      timeOut: 3500,
      showCloseButton: true
    });
  };

  const showMinorInjuries = () =>
    buildRoute({ location: nearest.nearestMedical, title: "Nearest medical" });
  const showSanctuary = () =>
    buildRoute({ location: nearest.nearestSanctuary, title: "Nearest sanctuary" });
  const showSaferJourney = () =>
    buildRoute({
      location: nearest.nearestSanctuary || nearest.nearestMedical,
      title: "Safest route",
    });
  const clearRoute = () => {
    setSelectedLocation(null);
    setRoutePoints([]);
    setRouteTitle("");
    setRouteNotice("");
    safestPath.clear();
    setStreetRouteFromSelected(null);
    setStreetRouteToSelected(null);
    if (fromACRef.current) fromACRef.current.value = null;
    if (toACRef.current) toACRef.current.value = null;
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
          `Stay on well-lit routes in the Botanic area.`
      );
      window.speechSynthesis.speak(msg);
    }
  };

  const disableActions = locationState === "loading" || sanctuariesStatus === "loading";

  const handleMapClick = (lat, lng) => coordScore.fetchScore(lat, lng);

  const buildStreetToStreetRoute = async () => {
    if (!streetRouteFromSelected || !streetRouteToSelected) return;
    setStreetRouteLoading(true);
    // Use the midpoint of each street's geometry from the botanic streets GeoJSON
    const fromStreet = botanicStreets.streets.find(s => s.id === streetRouteFromSelected.id);
    const toStreet   = botanicStreets.streets.find(s => s.id === streetRouteToSelected.id);
    if (!fromStreet || !toStreet) {
      setRouteNotice("Streets not found in map data.");
      setStreetRouteLoading(false);
      return;
    }
    const midOf = (pts) => pts[Math.floor(pts.length / 2)];
    const fromCoord = midOf(fromStreet.path);
    const toCoord   = midOf(toStreet.path);

    setRoutePoints([fromCoord, toCoord]);
    setRouteTitle(`${streetRouteFromSelected.name} → ${streetRouteToSelected.name}`);
    setRouteNotice("");
    setSelectedLocation({ name: streetRouteToSelected.name, type: "sanctuary", coords: toCoord, address: "" });
    safestPath.clear();

    const result = await safestPath.findPath(fromCoord[0], fromCoord[1], toCoord[0], toCoord[1]);
    if (result?.path_coordinates) {
      setRoutePoints(result.path_coordinates);
    }
    setStreetRouteLoading(false);
    setActiveTab(1); // switch to Route tab
  };

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
          Minor Injuries
        </ButtonComponent>
        <ButtonComponent
          cssClass="e-success action-btn"
          onClick={showSanctuary}
          disabled={disableActions}
        >
          Sanctuary
        </ButtonComponent>
        <ButtonComponent
          cssClass="e-info action-btn"
          onClick={showSaferJourney}
          disabled={disableActions}
        >
          Safe Journey
        </ButtonComponent>
      </div>

      {/* Report incident button */}
      <button
        className="report-incident-btn"
        onClick={() => { incidentReport.reset(); setIncidentModalOpen(true); }}
      >
        Report Incident Anonymously
      </button>

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
          My Location
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

      {/* Street-to-street route planner */}
      <div className="street-route-planner">
        <h3 className="section-heading">Plan a Route</h3>
        <p className="small-note" style={{ marginBottom: "0.85rem" }}>
          Pick any two streets in the Botanic area — the safest A* path is calculated automatically.
        </p>

        {/* FROM */}
        <label className="route-planner-label">From</label>
        <AutoCompleteComponent
          id="from-street-ac"
          ref={fromACRef}
          dataSource={streetDataSource}
          fields={{ value: "text" }}
          placeholder="e.g. Botanic Avenue"
          highlight={true}
          minLength={1}
          select={(args) => {
            if (args.itemData) {
              setStreetRouteFromSelected({ id: args.itemData.id, name: args.itemData.text });
            }
          }}
          change={(args) => {
            if (!args.value) setStreetRouteFromSelected(null);
          }}
          cssClass="route-ac"
        />

        {/* TO */}
        <label className="route-planner-label" style={{ marginTop: "0.75rem" }}>To</label>
        <AutoCompleteComponent
          id="to-street-ac"
          ref={toACRef}
          dataSource={streetDataSource}
          fields={{ value: "text" }}
          placeholder="e.g. University Road"
          highlight={true}
          minLength={1}
          select={(args) => {
            if (args.itemData) {
              setStreetRouteToSelected({ id: args.itemData.id, name: args.itemData.text });
            }
          }}
          change={(args) => {
            if (!args.value) setStreetRouteToSelected(null);
          }}
          cssClass="route-ac"
        />

        <ButtonComponent
          cssClass="e-primary find-route-syncfusion-btn"
          disabled={!streetRouteFromSelected || !streetRouteToSelected || streetRouteLoading}
          onClick={buildStreetToStreetRoute}
        >
          {streetRouteLoading ? "Finding safest path…" : "Find Safest Route"}
        </ButtonComponent>
      </div>

      {!selectedLocation ? (
        <div className="empty-state" style={{ marginTop: "1rem" }}>
          <p className="empty-title">No active route</p>
          <p className="empty-sub">
            Search streets above or use <strong>Get Help</strong> to navigate to the nearest support location.
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
              {safestPath.status === "loading" && "⏳ Finding safest path…"}
              {safestPath.meta && (
                <>
                  {(safestPath.meta.distanceM / 1000).toFixed(2)} km via safest streets ·{" "}
                  Safety score: <strong>{safestPath.meta.avgSafetyScore}/100</strong>
                </>
              )}
              {safestPath.status === "error" && `Straight-line fallback · ${safestPath.error}`}
              {safestPath.status === "idle" && `${routeDistanceKm(routePoints).toFixed(2)} km`}
            </p>
            <p className="route-address">{selectedLocation.address || "Botanic area, Belfast"}</p>
            <div className="route-actions">
              <ButtonComponent cssClass="e-outline e-small" onClick={clearRoute}>
                Clear Route
              </ButtonComponent>
              <ButtonComponent cssClass="e-outline e-small voice-btn" onClick={speakRouteGuide}>
                Voice Guide
              </ButtonComponent>
            </div>
          </div>

          {safestPath.meta && (
            <div className="score-card">
              <h3 className="section-heading">Route Safety Score</h3>
              <div className="score-hero-row">
                <span className="score-big">{safestPath.meta.avgSafetyScore}</span>
                <span className="score-label">/100</span>
                <span
                  className="score-grade"
                  style={{
                    background: scoreColor(safestPath.meta.avgSafetyScore) + "18",
                    color: scoreColor(safestPath.meta.avgSafetyScore),
                    border: `2px solid ${scoreColor(safestPath.meta.avgSafetyScore)}50`
                  }}
                >
                  {scoreGrade(safestPath.meta.avgSafetyScore)}
                </span>
              </div>
              <ProgressBarComponent
                id="overall-score-bar"
                type="Linear"
                value={safestPath.meta.avgSafetyScore}
                height="18"
                minimum={0}
                maximum={100}
                progressColor={scoreColor(safestPath.meta.avgSafetyScore)}
                trackColor="#e2e8f0"
                animation={{ enable: true, duration: 1200 }}
              />
              <p className="small-note">
                {(safestPath.meta.distanceM / 1000).toFixed(2)} km via{" "}
                {safestPath.segments.length} street segment
                {safestPath.segments.length !== 1 ? "s" : ""} · Safety-optimised by Dijkstra
              </p>
            </div>
          )}
        </>
      )}

      <div className="tips-card">
        <h3 className="section-heading">Safety Tips</h3>
        <ul className="tips-list">
          {safetyTips["medium"].map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </div>
    </div>
  );

  const safetyContent = () => {
    // Top/bottom streets by environment score
    const rankedStreets = Object.entries(botanicEnv.envMap)
      .map(([id, env]) => ({ id, name: env.street_name || id, score: env.score }))
      .filter((s) => s.score != null)
      .sort((a, b) => b.score - a.score);

    return (
    <div className="tab-panel">
      <div className="advisory-card">
        <p className="advisory-text">
          🗺️ Botanic area, South Belfast — safety scores are live, based on PSNI crime data,
          street lighting infrastructure, and proximity to sanctuaries.
        </p>
      </div>

      <h3 className="section-heading">Street Safety Rankings</h3>
      <p className="small-note" style={{ marginBottom: "0.75rem" }}>
        Colour-coded by percentile: green = top third, amber = middle, red = bottom third.
        Tap any street on the map for details.
      </p>

      {botanicEnv.status === "loading" && <p className="small-note">Loading street data…</p>}
      {botanicEnv.status === "ready" && (
        <>
          <div className="percentile-legend">
            {[
              ["🟢 Safest streets", `Score ≥ ${Math.round(percentiles.p66)}`, "#16a34a"],
              ["🟡 Mid tier", `${Math.round(percentiles.p33)}–${Math.round(percentiles.p66)}`, "#f59e0b"],
              ["🔴 Lower tier", `Score < ${Math.round(percentiles.p33)}`, "#ef4444"],
            ].map(([label, range, color]) => (
              <div key={label} className="percentile-row">
                <span className="street-dot" style={{ background: color }} />
                <span className="street-name">{label}</span>
                <span className="risk-chip" style={{ background: color + "18", color, border: `1px solid ${color}50` }}>
                  {range}
                </span>
              </div>
            ))}
          </div>

          <h3 className="section-heading" style={{ marginTop: "1rem" }}>Top 5 Safest</h3>
          <ul className="street-risk-list">
            {rankedStreets.slice(0, 5).map((s) => (
              <li key={s.id} className="street-risk-item">
                <span className="street-dot" style={{ background: percentileColor(s.score, percentiles.p33, percentiles.p66) }} />
                <span className="street-name">{s.name}</span>
                <span className="risk-chip" style={{ background: "#16a34a18", color: "#16a34a", border: "1px solid #16a34a50" }}>
                  {s.score}/100
                </span>
              </li>
            ))}
          </ul>

          <h3 className="section-heading" style={{ marginTop: "1rem" }}>⚠️ Needs Attention</h3>
          <ul className="street-risk-list">
            {rankedStreets.slice(-5).reverse().map((s) => (
              <li key={s.id} className="street-risk-item">
                <span className="street-dot" style={{ background: percentileColor(s.score, percentiles.p33, percentiles.p66) }} />
                <span className="street-name">{s.name}</span>
                <span className="risk-chip" style={{ background: "#ef444418", color: "#ef4444", border: "1px solid #ef444450" }}>
                  {s.score}/100
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* 🆕 Street search */}
      <div className="street-search-section" style={{ marginTop: "1.25rem" }}>
        <h3 className="section-heading">Search Streets</h3>
        <input
          type="text"
          placeholder="Search for a street…"
          value={streetSearch}
          onChange={(e) => handleStreetSearch(e.target.value)}
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
  };

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

          {/* Botanic streets — hidden when a route is active to reduce visual noise */}
          {botanicStreets.status === "ready" && routePoints.length < 2 &&
            botanicStreets.streets.map((street) => {
              const env = botanicEnv.envMap[street.id];
              const score = env?.score ?? null;
              const color = percentileColor(score, percentiles.p33, percentiles.p66);
              const weight = ["primary", "secondary"].includes(street.highway) ? 5
                : street.highway === "tertiary" ? 4 : 3;
              return (
                <Polyline
                  key={street.id}
                  positions={street.path}
                  pathOptions={{ color, weight, opacity: 0.85 }}
                >
                  <Popup>
                    <strong>{street.name || "Unnamed street"}</strong><br />
                    Safety score: {score != null ? `${score}/100` : "N/A"}<br />
                    {score != null && (
                      score >= percentiles.p66 ? "🟢 Top tier — safest streets"
                      : score >= percentiles.p33 ? "🟡 Mid tier"
                      : "🔴 Lower tier — exercise caution"
                    )}<br />
                    {env?.reasons?.slice(0, 2).join(" · ")}
                  </Popup>
                </Polyline>
              );
            })}

          {/* Real sanctuary/location markers from API */}
          {sanctuaries
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
                  <strong>{loc.name}</strong><br />
                  {typeIcons[loc.type]} {typeLabels[loc.type]}<br />
                  🕐 {loc.hours || "Hours unavailable"}
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

          {/* Active route — per-segment safety colours + outline for contrast */}
          {routePoints.length > 1 && safestPath.segments.length > 0 && (
            <>
              {/* White outline underneath for readability on dark tiles */}
              <Polyline
                positions={routePoints}
                pathOptions={{ color: "#fff", weight: 11, opacity: 0.6 }}
              />
              {/* Per-segment safety colouring */}
              {safestPath.segments.map((seg, i) => {
                const segColor = scoreColor(Math.round(seg.safety_score_100));
                return (
                  <Polyline
                    key={i}
                    positions={[[seg.from.lat, seg.from.lng], [seg.to.lat, seg.to.lng]]}
                    pathOptions={{ color: segColor, weight: 7, opacity: 0.95 }}
                  >
                    <Popup>
                      <strong>{seg.street_name || "Street"}</strong><br />
                      Safety: {seg.safety_score_100}/100<br />
                      Length: {seg.distance_m}m
                    </Popup>
                  </Polyline>
                );
              })}
            </>
          )}

          {/* Fallback: straight-line route when pathfinding unavailable */}
          {routePoints.length > 1 && safestPath.segments.length === 0 && (
            <>
              <Polyline
                positions={routePoints}
                pathOptions={{ color: "#fff", weight: 11, opacity: 0.5 }}
              />
              <Polyline
                positions={routePoints}
                pathOptions={{ color: "#0ea5e9", weight: 7, dashArray: "10 8", opacity: 0.9 }}
              />
            </>
          )}

          {/* Route destination marker */}
          {selectedLocation && (
            <CircleMarker
              center={selectedLocation.coords}
              radius={14}
              pathOptions={{
                color: "#fff",
                fillColor: typeColors[selectedLocation.type] || "#0ea5e9",
                fillOpacity: 1,
                weight: 3
              }}
            >
              <Popup>
                <strong>{selectedLocation.name}</strong><br />
                {typeIcons[selectedLocation.type]} Destination
              </Popup>
            </CircleMarker>
          )}


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
            <span className={`risk-pill risk-medium`}>
              BOTANIC
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
        {sanctuariesStatus === "error" && (
          <div className="state-banner error" role="alert">
            Could not load sanctuaries — check the backend is running
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
              { label: "Get Help" },
              { label: "Route" },
              { label: "Safety Data" },
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

      {/* ── Incident Report Modal ─────────────────────────────────────────── */}
      {incidentModalOpen && (
        <div className="modal-backdrop" onClick={() => setIncidentModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>

            {incidentReport.status === "done" ? (
              /* ── Success state ── */
              <div className="modal-success">
                <div className="modal-success-icon">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                </div>
                <h2 className="modal-success-title">Report Submitted</h2>
                <p className="modal-success-sub">
                  Your report has been recorded. No personal data was stored.
                </p>
                <div className="tx-box">
                  <span className="tx-label">Reference</span>
                  <code className="tx-sig">{incidentReport.txSignature?.slice(0, 20)}…</code>
                  {incidentReport.explorerUrl && (
                    <a
                      href={incidentReport.explorerUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="tx-link"
                    >
                      View details
                    </a>
                  )}
                </div>
                <button className="modal-close-btn" onClick={() => {
                  setIncidentModalOpen(false);
                  setIncidentDesc("");
                  setIncidentType("suspicious_activity");
                  incidentReport.reset();
                }}>
                  Close
                </button>
              </div>
            ) : (
              /* ── Form state ── */
              <>
                <div className="modal-header">
                  <h2 className="modal-title">Report an Incident</h2>
                  <button className="modal-x" onClick={() => setIncidentModalOpen(false)}>×</button>
                </div>

                <p className="modal-sub">
                  Reports are <strong>anonymous</strong> — no identity is stored.
                  A cryptographic reference is generated for integrity.
                </p>

                <label className="modal-label">Incident type</label>
                <select
                  className="modal-select"
                  value={incidentType}
                  onChange={(e) => setIncidentType(e.target.value)}
                  disabled={incidentReport.status === "submitting"}
                >
                  <option value="suspicious_activity">Suspicious Activity</option>
                  <option value="broken_lighting">Broken / Missing Lighting</option>
                  <option value="street_harassment">Street Harassment</option>
                  <option value="unsafe_road">Unsafe Road Condition</option>
                  <option value="antisocial_behaviour">Antisocial Behaviour</option>
                  <option value="other">Other</option>
                </select>

                <label className="modal-label">Description <span className="modal-optional">(optional)</span></label>
                <textarea
                  className="modal-textarea"
                  rows={3}
                  placeholder="Briefly describe what happened…"
                  value={incidentDesc}
                  onChange={(e) => setIncidentDesc(e.target.value)}
                  disabled={incidentReport.status === "submitting"}
                />

                <div className="modal-location-row">
                  <span className="modal-location-label">Location</span>
                  <span className="modal-location-val">
                    {currentPosition[0].toFixed(4)}, {currentPosition[1].toFixed(4)}
                  </span>
                </div>

                {incidentReport.error && (
                  <div className="modal-error">{incidentReport.error}</div>
                )}

                <button
                  className="modal-submit-btn"
                  disabled={incidentReport.status === "submitting"}
                  onClick={() =>
                    incidentReport.submitIncident({
                      type: incidentType,
                      description: incidentDesc,
                      lat: currentPosition[0],
                      lng: currentPosition[1],
                    })
                  }
                >
                  {incidentReport.status === "submitting" && "Submitting…"}
                  {(incidentReport.status === "idle" || incidentReport.status === "error") && "Submit Report"}
                </button>

                <p className="modal-chain-note">
                  Zero personal data collected
                </p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
