from typing import Any, Dict, Optional

from maps.loader import load_botanic_streets
from services.geo import calculate_centroid, haversine_m, min_distance_to_geometry


def resolve_news_location_to_street(
    *,
    lat: Optional[float],
    lng: Optional[float],
    street_name: Optional[str],
    max_distance_m: float = 200.0,
) -> Dict[str, Any]:
    """
    Option C mapping: use coordinates if present, otherwise street name.
    Returns normalized street mapping details.
    """
    streets = load_botanic_streets() or {}
    features = streets.get("features", [])
    if not features:
        return {"matched": False, "reason": "street_data_unavailable"}

    normalized_name = (street_name or "").strip().lower()
    if normalized_name:
        same_name = [
            f for f in features if (f.get("properties", {}).get("name") or "").strip().lower() == normalized_name
        ]
        if same_name:
            chosen = same_name[0]
            props = chosen.get("properties", {})
            c_lat, c_lng = calculate_centroid(chosen.get("geometry", {}))
            return {
                "matched": True,
                "street_id": props.get("id"),
                "street_name": props.get("name") or street_name,
                "lat": c_lat if c_lat else None,
                "lng": c_lng if c_lng else None,
                "distance_m": None,
                "method": "street_name",
            }

    if lat is None or lng is None:
        return {"matched": False, "reason": "missing_location_signal"}

    best_feature = None
    best_dist = float("inf")
    for f in features:
        d = min_distance_to_geometry(float(lat), float(lng), f.get("geometry", {}))
        if d < best_dist:
            best_dist = d
            best_feature = f

    if best_feature is None:
        return {"matched": False, "reason": "no_feature_match"}

    props = best_feature.get("properties", {})
    c_lat, c_lng = calculate_centroid(best_feature.get("geometry", {}))
    return {
        "matched": best_dist <= max_distance_m,
        "street_id": props.get("id"),
        "street_name": props.get("name") or "Unknown",
        "lat": float(lat),
        "lng": float(lng),
        "distance_m": round(best_dist, 2),
        "method": "coordinates",
        "reason": None if best_dist <= max_distance_m else "too_far_from_street",
        "centroid_distance_m": round(haversine_m(float(lat), float(lng), c_lat, c_lng), 2)
        if c_lat and c_lng
        else None,
    }

