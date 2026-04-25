import { useEffect, useMemo, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  useMap
} from "react-leaflet";
import { ButtonComponent } from "@syncfusion/ej2-react-buttons";
import { DialogComponent } from "@syncfusion/ej2-react-popups";
import {
  safetyTips,
  streetSafetySegments,
  supportLocations,
  userStartPosition
} from "./data/belfastSafetyData";
import { scoreRouteForBelfast, useBelfastContext } from "./hooks/useBelfastContext";

const typeLabels = {
  pharmacy: "Pharmacy",
  clinic: "Clinic",
  sanctuary: "Sanctuary"
};

const typeColors = {
  pharmacy: "#22c55e",
  clinic: "#3b82f6",
  sanctuary: "#8b5cf6"
};

const streetRiskColors = {
  low: "#16a34a",
  medium: "#f59e0b",
  high: "#ef4444"
};

function distanceInKm([lat1, lon1], [lat2, lon2]) {
  const toRad = (value) => (value * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 6371 * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

function routeDistanceKm(points) {
  if (!points || points.length < 2) {
    return 0;
  }
  let total = 0;
  for (let index = 1; index < points.length; index += 1) {
    total += distanceInKm(points[index - 1], points[index]);
  }
  return total;
}

function RecenterMap({ center }) {
  const map = useMap();

  useEffect(() => {
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    map.setView(center, map.getZoom(), { animate: !prefersReducedMotion });
  }, [center, map]);

  return null;
}

function App() {
  const [currentPosition, setCurrentPosition] = useState(userStartPosition);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [routePoints, setRoutePoints] = useState([]);
  const [routeTitle, setRouteTitle] = useState("");
  const [locationState, setLocationState] = useState("loading");
  const [locationStatus, setLocationStatus] = useState("Requesting your location...");
  const [routeNotice, setRouteNotice] = useState("");
  const [isOnline, setIsOnline] = useState(window.navigator.onLine);

  const belfastContext = useBelfastContext(currentPosition);
  const selectedLocationDistanceKm = selectedLocation
    ? distanceInKm(currentPosition, selectedLocation.coords)
    : null;

  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  const requestCurrentLocation = () => {
    if (!navigator.geolocation) {
      setLocationState("unsupported");
      setLocationStatus("Geolocation not supported. Using demo Belfast location.");
      return;
    }

    setLocationState("loading");
    setLocationStatus("Requesting your location...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextPosition = [position.coords.latitude, position.coords.longitude];
        setCurrentPosition(nextPosition);
        setLocationState("ready");
        setLocationStatus("Using your current location.");
        setRouteNotice("");
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setLocationState("denied");
          setLocationStatus("Location permission denied. Using demo Belfast location.");
          return;
        }
        setLocationState("error");
        setLocationStatus("Could not get your location. Using demo Belfast location.");
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000
      }
    );
  };

  useEffect(() => {
    requestCurrentLocation();
  }, []);

  const nearest = useMemo(() => {
    const nearestFor = (type) => {
      const options = supportLocations.filter((place) => place.type === type);
      return options.reduce((best, place) => {
        const distanceKm = distanceInKm(currentPosition, place.coords);
        if (!best || distanceKm < best.distanceKm) {
          return { ...place, distanceKm };
        }
        return best;
      }, null);
    };

    const nearestPharmacy = nearestFor("pharmacy");
    const nearestClinic = nearestFor("clinic");
    const nearestSanctuary = nearestFor("sanctuary");
    const nearestMedical = [nearestPharmacy, nearestClinic]
      .filter(Boolean)
      .reduce((best, place) => {
        if (!best || place.distanceKm < best.distanceKm) {
          return place;
        }
        return best;
      }, null);

    return {
      nearestMedical,
      nearestSanctuary
    };
  }, [currentPosition]);

  const streetsByDistance = useMemo(() => {
    return streetSafetySegments
      .map((street) => {
        const nearestPointDistance = Math.min(
          ...street.path.map((point) => distanceInKm(currentPosition, point))
        );
        return { ...street, nearestPointDistance };
      })
      .sort((a, b) => a.nearestPointDistance - b.nearestPointDistance);
  }, [currentPosition]);

  const currentRisk = useMemo(() => {
    if (streetsByDistance.length === 0) {
      return "low";
    }
    return streetsByDistance[0].level;
  }, [streetsByDistance]);

  const activeRouteScore = useMemo(() => {
    return scoreRouteForBelfast({
      routePoints,
      destinationType: selectedLocation?.type,
      nearbyStreetRisk: currentRisk,
      areaProfile: belfastContext.areaProfile
    });
  }, [routePoints, selectedLocation, currentRisk, belfastContext.areaProfile]);

  const buildRoute = ({ location, title, includeLowRiskDetour = false }) => {
    if (!location) {
      setRouteNotice("No suitable destination found in current Belfast demo data.");
      return;
    }

    if (includeLowRiskDetour) {
      const lowRiskStreet = streetsByDistance.find((street) => street.level === "low");
      if (!lowRiskStreet) {
        setRouteNotice("No low-risk street segment available for safer journey planning.");
        return;
      }
      setSelectedLocation(location);
      setRouteTitle(`${title} via ${lowRiskStreet.name}`);
      setRoutePoints([
        currentPosition,
        lowRiskStreet.path[0],
        lowRiskStreet.path[lowRiskStreet.path.length - 1],
        location.coords
      ]);
      setRouteNotice("");
      return;
    }

    setSelectedLocation(location);
    setRouteTitle(title);
    setRoutePoints([currentPosition, location.coords]);
    setRouteNotice("");
  };

  const showMinorInjuries = () =>
    buildRoute({
      location: nearest.nearestMedical,
      title: "Minor injuries route"
    });

  const showSanctuary = () =>
    buildRoute({
      location: nearest.nearestSanctuary,
      title: "Nearest sanctuary route"
    });

  const showSaferJourney = () =>
    buildRoute({
      location: nearest.nearestSanctuary || nearest.nearestMedical,
      title: "Safer journey route",
      includeLowRiskDetour: true
    });

  const clearRoute = () => {
    setSelectedLocation(null);
    setRoutePoints([]);
    setRouteTitle("");
    setRouteNotice("");
  };

  const disableActions = locationState === "loading" || belfastContext.status === "loading";

  return (
    <div className="app">
      <a className="skip-link" href="#app-controls">
        Skip map and jump to controls
      </a>

      <section
        className="map-top"
        aria-label="Belfast map with street safety overlays and route guidance"
      >
        <p className="sr-only" id="map-accessibility-note">
          Interactive map. Use the controls section to generate routes and safety scores.
        </p>
        <MapContainer
          center={currentPosition}
          zoom={13}
          className="map"
          aria-describedby="map-accessibility-note"
        >
          <RecenterMap center={currentPosition} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <CircleMarker
            center={currentPosition}
            radius={9}
            pathOptions={{ color: "#0f172a", fillColor: "#0f172a", fillOpacity: 0.95 }}
          >
            <Popup>{locationStatus}</Popup>
          </CircleMarker>

          {streetSafetySegments.map((street) => (
            <Polyline
              key={street.id}
              positions={street.path}
              pathOptions={{
                color: streetRiskColors[street.level],
                weight: 6,
                opacity: 0.75
              }}
            >
              <Popup>
                <strong>{street.name}</strong>
                <br />
                Safety grade: {street.level.toUpperCase()}
                <br />
                {street.notes}
              </Popup>
            </Polyline>
          ))}

          {supportLocations.map((location) => (
            <CircleMarker
              key={location.id}
              center={location.coords}
              radius={7}
              pathOptions={{
                color: typeColors[location.type],
                fillColor: typeColors[location.type],
                fillOpacity: 0.9
              }}
            >
              <Popup>
                <strong>{location.name}</strong>
                <br />
                {typeLabels[location.type]}
                <br />
                {location.details}
              </Popup>
            </CircleMarker>
          ))}

          {routePoints.length > 1 && (
            <Polyline
              positions={routePoints}
              pathOptions={{ color: "#0ea5e9", weight: 6, dashArray: "8, 8" }}
            />
          )}
        </MapContainer>
      </section>

      <section className="controls-bottom" id="app-controls" aria-busy={disableActions}>
        <div className="header-row">
          <div>
            <h1>Belfast Safety App</h1>
            <p>Street-level safety grading with quick action routing.</p>
            <p className="location-status" role="status" aria-live="polite">
              {locationStatus}
            </p>
          </div>
          <span className={`risk-pill ${currentRisk}`}>
            Nearby street risk: {currentRisk.toUpperCase()}
          </span>
        </div>

        {!isOnline && (
          <div className="state-banner warning" role="status" aria-live="polite">
            You are offline. Route actions use cached Belfast placeholder data only.
          </div>
        )}

        {(locationState === "denied" || locationState === "error") && (
          <div className="state-banner warning" role="status" aria-live="polite">
            Live location unavailable. Actions continue using Belfast fallback coordinates.
          </div>
        )}

        {belfastContext.status === "error" && (
          <div className="state-banner error" role="alert">
            Belfast context hook failed: {belfastContext.error}
          </div>
        )}

        {routeNotice && (
          <div className="state-banner error" role="alert">
            {routeNotice}
          </div>
        )}

        <div className="location-controls">
          <ButtonComponent cssClass="e-outline" onClick={requestCurrentLocation}>
            Use My Current Location
          </ButtonComponent>
          <span className="context-status" role="status" aria-live="polite">
            {belfastContext.advisory}
          </span>
        </div>

        <div className="button-row">
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
            Journey Planner
          </ButtonComponent>
        </div>

        <div className="bottom-grid">
          <div className="info-card modern-card" aria-labelledby="route-card-title">
            <h2 id="route-card-title">Current route</h2>
            <p>{routeTitle || "Choose one of the 3 actions to generate a route."}</p>
            {selectedLocation && (
              <>
                <p>
                  Destination: <strong>{selectedLocation.name}</strong> (
                  {typeLabels[selectedLocation.type]}) -{" "}
                  {selectedLocationDistanceKm?.toFixed(2)} km
                </p>
                <p>Route length (polyline): {routeDistanceKm(routePoints).toFixed(2)} km</p>
              </>
            )}
            <ButtonComponent cssClass="e-outline" onClick={clearRoute}>
              Clear route
            </ButtonComponent>
          </div>

          <div className="info-card modern-card" aria-labelledby="insights-card-title">
            <h2 id="insights-card-title">Street safety insights</h2>
            <ul className="street-list">
              {streetsByDistance.slice(0, 3).map((street) => (
                <li key={street.id}>
                  <span
                    className={`street-level ${street.level}`}
                    title={`Risk ${street.level}`}
                  />
                  {street.name} - {street.level.toUpperCase()}
                </li>
              ))}
            </ul>
            <ul>
              {safetyTips[currentRisk].map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          </div>

          <div
            className="info-card modern-card full-width"
            aria-labelledby="score-card-title"
          >
            <h2 id="score-card-title">Belfast route safety score</h2>
            {!activeRouteScore && <p>Select a route to generate score details.</p>}
            {activeRouteScore && (
              <>
                <p className="score-headline" role="status" aria-live="polite">
                  Score: <strong>{activeRouteScore.overallScore}/100</strong> · Grade{" "}
                  <strong>{activeRouteScore.safetyGrade}</strong>
                </p>
                <div className="score-grid">
                  <p>Lighting: {activeRouteScore.breakdown.lightingScore}</p>
                  <p>Footfall: {activeRouteScore.breakdown.footfallScore}</p>
                  <p>CCTV: {activeRouteScore.breakdown.cctvScore}</p>
                  <p>Emergency Access: {activeRouteScore.breakdown.emergencyAccessScore}</p>
                  <p>Street Risk: {activeRouteScore.breakdown.streetRiskScore}</p>
                  <p>
                    Complexity Penalty: -{activeRouteScore.breakdown.complexityPenalty}
                  </p>
                </div>
              </>
            )}
            <p className="small-note">
              Belfast hook factors include area profile, adjusted lighting/footfall and
              street-level risk.
            </p>
          </div>
        </div>
      </section>

      <DialogComponent
        header={selectedLocation?.name || "Route destination"}
        visible={Boolean(selectedLocation)}
        width="390px"
        showCloseIcon
        isModal={false}
        close={clearRoute}
      >
        {selectedLocation && (
          <div className="detail-content">
            <p>
              <strong>Type:</strong> {typeLabels[selectedLocation.type]}
            </p>
            <p>
              <strong>Details:</strong> {selectedLocation.details}
            </p>
            <p>
              <strong>Approx distance:</strong>{" "}
              {selectedLocationDistanceKm?.toFixed(2)} km
            </p>
          </div>
        )}
      </DialogComponent>
    </div>
  );
}

export default App;
