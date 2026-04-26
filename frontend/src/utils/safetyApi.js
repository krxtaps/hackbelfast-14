function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function asArray(value) {
  if (Array.isArray(value)) return value;
  if (isObject(value) && Array.isArray(value.items)) return value.items;
  return [];
}

export function toLatLngPathFromGeometry(geometry) {
  if (!isObject(geometry)) return [];
  const { type, coordinates } = geometry;
  if (!Array.isArray(coordinates)) return [];

  if (type === "LineString") {
    return coordinates
      .filter((pair) => Array.isArray(pair) && pair.length >= 2)
      .map(([lng, lat]) => [lat, lng]);
  }

  if (type === "MultiLineString") {
    const longest = coordinates.reduce(
      (best, segment) => (Array.isArray(segment) && segment.length > best.length ? segment : best),
      []
    );
    return longest
      .filter((pair) => Array.isArray(pair) && pair.length >= 2)
      .map(([lng, lat]) => [lat, lng]);
  }

  return [];
}

export function normalizeSafetyScoreResponse(raw) {
  if (!isObject(raw)) return null;

  const location = isObject(raw.location) ? raw.location : {};
  const environment =
    (isObject(raw.environment) && raw.environment) ||
    (isObject(raw.raw_data) && isObject(raw.raw_data.environment) && raw.raw_data.environment) ||
    {};
  const sanctuaries =
    (isObject(raw.sanctuaries) && raw.sanctuaries) ||
    (isObject(raw.raw_data) && isObject(raw.raw_data.sanctuaries) && raw.raw_data.sanctuaries) ||
    {};
  const amenities =
    (isObject(raw.amenities) && raw.amenities) ||
    (isObject(raw.raw_data) && isObject(raw.raw_data.amenities) && raw.raw_data.amenities) ||
    {};

  const score = toNumber(raw.score ?? raw.overallScore);
  const lat = toNumber(location.lat);
  const lng = toNumber(location.lng);
  const breakdown = isObject(raw.breakdown) ? raw.breakdown : {};
  const explanations = Array.isArray(raw.explanations) ? raw.explanations : [];

  return {
    ...raw,
    street_id: raw.street_id ?? raw.id ?? environment.street_id ?? null,
    street_name: raw.street_name ?? raw.name ?? environment.street_name ?? null,
    score,
    overallScore: score,
    location: {
      lat,
      lng,
      geometry: isObject(location.geometry) ? location.geometry : null
    },
    breakdown,
    explanations,
    environment,
    sanctuaries: {
      count: Number.isFinite(Number(sanctuaries.count)) ? Number(sanctuaries.count) : 0,
      items: Array.isArray(sanctuaries.items) ? sanctuaries.items : [],
      bonus: Number.isFinite(Number(sanctuaries.bonus)) ? Number(sanctuaries.bonus) : 0,
      reasons: Array.isArray(sanctuaries.reasons) ? sanctuaries.reasons : [],
      check_time: sanctuaries.check_time ?? null
    },
    amenities: {
      count: Number.isFinite(Number(amenities.count)) ? Number(amenities.count) : 0,
      items: Array.isArray(amenities.items) ? amenities.items : [],
      bonus: Number.isFinite(Number(amenities.bonus)) ? Number(amenities.bonus) : 0,
      reasons: Array.isArray(amenities.reasons) ? amenities.reasons : []
    }
  };
}
