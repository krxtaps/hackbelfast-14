from functools import lru_cache
from typing import Any, Dict

from maps.loader import find_nearest_street, load_botanic_streets
from services.amenities.amenity_scoring import (
    compute_amenity_signals,
    compute_sanctuary_signals,
)
from services.environment_scoring import compute_environment_signals
from services.geo import calculate_centroid, consolidate_street_segments, haversine_m
from services.news_risk.news_risk import news_penalty_points
from services.police_data_scoring import (
    calculate_score_from_crimes,
    fetch_nearby_crimes,
)

# Weight configuration
WEIGHT_CRIME = 0.5
WEIGHT_ENVIRONMENT_DIRECT = 0.25
WEIGHT_ENVIRONMENT_NEIGHBORHOOD = 0.25

# Amenities act as an additive 'Sanctuary Bonus' (0 to +10 pts)
# rather than a weighted component to avoid penalizing areas without them.


@lru_cache(maxsize=1)
def _get_global_env_stats():
    """Calculates global environment stats for the entire area."""
    from services.environment_scoring import compute_all_environment_signals

    all_sigs = compute_all_environment_signals()
    scores = [s["score"] for s in all_sigs]
    avg = sum(scores) / len(scores) if scores else 80.0
    return {"average": avg, "all_signals": all_sigs}


def _get_neighborhood_env_score(
    lat: float, lng: float, radius_m: float = 300.0
) -> tuple[float, int]:
    """
    Calculates the average environment score of all streets within radius_m.
    Returns (average_score, street_count).
    """
    stats = _get_global_env_stats()
    all_scores = stats["all_signals"]
    nearby_scores = []

    streets_data = load_botanic_streets()
    if not streets_data or "features" not in streets_data:
        return stats["average"], 0

    for i, feature in enumerate(streets_data["features"]):
        f_lat, f_lng = calculate_centroid(feature.get("geometry", {}))
        if f_lat == 0.0:
            continue

        if haversine_m(lat, lng, f_lat, f_lng) <= radius_m:
            # Match by ID to get the pre-calculated score
            s_id = feature.get("properties", {}).get("id")
            env_sig = next((s for s in all_scores if s["street_id"] == s_id), None)
            if env_sig:
                nearby_scores.append(env_sig["score"])

    if not nearby_scores:
        return stats["average"], 0

    return sum(nearby_scores) / len(nearby_scores), len(nearby_scores)


async def get_combined_safety_score(
    lat: float, lng: float, check_time: str | None = None
) -> Dict[str, Any]:
    """
    Core safety engine: Combines Crime Safety, Environmental Safety, and Amenities.
    Returns a unified score and detailed explanation breakdown.
    """
    # Normalize check_time to string (empty string if None)
    check_time_str = check_time or ""

    # 1. Crime Analytics (via Police Data Service)
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes)

    # 2. Environmental Signals (Direct & Relative)
    stats = _get_global_env_stats()
    global_avg = stats["average"]

    env_score = 100
    env_explanations = []
    env_details = None
    geometry = None

    nearest_street = find_nearest_street(lat, lng)
    if nearest_street:
        geometry = nearest_street.get("geometry")
        env_details = compute_environment_signals(nearest_street)
        env_score = env_details.get("score", 100)
        env_explanations = env_details.get("reasons", [])

        # Add relative standing
        diff = env_score - global_avg
        standing = "above" if diff >= 0 else "below"
        env_explanations.append(
            f"Infrastructure: {abs(diff):.1f} points {standing} the Botanic average."
        )
    else:
        env_explanations = [
            "No specific street-level environment data found for this exact location."
        ]

    # 3. Neighborhood Context (Relative)
    nb_score, nb_count = _get_neighborhood_env_score(lat, lng)
    nb_diff = nb_score - global_avg
    nb_standing = "above" if nb_diff >= 0 else "below"

    # Update explanations for neighborhood
    if nb_count > 1:
        env_explanations.append(
            f"Area Context: {abs(nb_diff):.1f} points {nb_standing} average regional safety."
        )

    # 4. Amenities & Sanctuaries (Landmarks)
    amenity_details = compute_amenity_signals(lat, lng)
    sanctuary_details = compute_sanctuary_signals(lat, lng, check_time=check_time_str)

    amenity_bonus = amenity_details.get("bonus", 0.0)
    sanctuary_bonus = sanctuary_details.get("bonus", 0.0)
    news_risk = news_penalty_points(lat=lat, lng=lng, lookback_hours=72)
    news_penalty = float(news_risk.get("penalty_points", 0.0))

    # 5. Hybrid Scoring Logic
    # Base: 60% Crime, 40% Environment
    # Plus: Additive bonuses (Sanctuaries are weighted more heavily)
    base_score = (
        (crime_score * WEIGHT_CRIME)
        + (env_score * WEIGHT_ENVIRONMENT_DIRECT)
        + (nb_score * WEIGHT_ENVIRONMENT_NEIGHBORHOOD)
    )
    final_score = int(max(0, min(100, base_score + amenity_bonus + sanctuary_bonus - news_penalty)))

    # Unified Explanations
    explanations = []
    explanations.append("--- Crime & Security ---")
    explanations.extend(crime_explanations)
    explanations.append("--- Physical Environment ---")
    explanations.extend(env_explanations)

    explanations.append("--- Safe Sanctuaries (Foursquare) ---")
    if sanctuary_details["reasons"]:
        explanations.extend(sanctuary_details["reasons"])
    else:
        explanations.append("No safe sanctuaries (active POIs) within 200m.")

    explanations.append("--- Community Amenities ---")
    if amenity_details["reasons"]:
        explanations.extend(amenity_details["reasons"])
    else:
        explanations.append("No major public amenities within 200m.")
    explanations.append("--- Local News Signal ---")
    explanations.append(
        f"Recent local-news risk applied as -{news_penalty:.1f} points "
        f"(risk {news_risk.get('risk', 0):.1f}, {news_risk.get('incidents_used', 0)} incident(s))."
    )

    return {
        "location": {"lat": lat, "lng": lng, "geometry": geometry},
        "score": final_score,
        "breakdown": {
            "crime": {
                "score": crime_score,
                "weight": WEIGHT_CRIME,
                "count": len(crimes),
            },
            "environment_direct": {
                "score": env_score,
                "weight": WEIGHT_ENVIRONMENT_DIRECT,
                "street": env_details.get("street_name") if env_details else "",
                "relative_to_avg": round(env_score - global_avg, 1),
            },
            "environment_neighborhood": {
                "score": round(nb_score, 1),
                "weight": WEIGHT_ENVIRONMENT_NEIGHBORHOOD,
                "nearby_streets_count": nb_count,
                "relative_to_avg": round(nb_score - global_avg, 1),
            },
            "sanctuaries": {
                "type": "bonus",
                "count": sanctuary_details["count"],
                "bonus_applied": sanctuary_bonus,
            },
            "amenities": {
                "type": "bonus",
                "count": amenity_details["count"],
                "bonus_applied": amenity_bonus,
            },
            "regional_average": round(global_avg, 1),
            "news_signal": {
                "type": "penalty",
                "risk": news_risk.get("risk", 0.0),
                "incidents_used": news_risk.get("incidents_used", 0),
                "penalty_applied": news_penalty,
            },
        },
        "explanations": explanations,
        "raw_data": {
            "crimes": crimes,
            "environment": env_details,
            "sanctuaries": sanctuary_details,
            "amenities": amenity_details,
            "news_risk": news_risk,
        },
    }


async def get_street_combined_score(
    street_id: str, check_time: str | None = None
) -> Dict[str, Any]:
    """
    Calculates the combined safety score for a specific street by its ID.
    Consolidates all segments that share the same street name, matching the dashboard.
    """
    streets_data = load_botanic_streets()
    if not streets_data or "features" not in streets_data:
        return {"error": "Street data not available"}

    feature = next(
        (
            f
            for f in streets_data["features"]
            if f.get("properties", {}).get("id") == street_id
        ),
        None,
    )

    if not feature:
        return {"error": f"Street with ID '{street_id}' not found"}

    # Consolidate all segments sharing the same street name
    segments, street_name, merged_geometry = consolidate_street_segments(
        feature, streets_data
    )
    centroid_source = feature.get("geometry", {})
    lat, lng = calculate_centroid(centroid_source)

    # 1. Crime Analytics at street centroid
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes)

    # 2. Environmental Signals for the whole street name
    env_details = compute_environment_signals(feature)
    env_score = env_details.get("score", 100)
    env_explanations = env_details.get("reasons", [])

    # 3. Neighborhood Context
    nb_score, nb_count = _get_neighborhood_env_score(lat, lng)

    # 4. Amenities & Sanctuaries across all matching segments
    check_time_str = check_time or ""
    amenity_details = compute_amenity_signals(lat, lng, geometry=centroid_source)
    sanctuary_details = compute_sanctuary_signals(
        lat, lng, check_time=check_time_str, geometry=centroid_source
    )

    amenity_bonus = amenity_details.get("bonus", 0.0)
    sanctuary_bonus = sanctuary_details.get("bonus", 0.0)
    news_risk = news_penalty_points(street_id=street_id, lat=lat, lng=lng, lookback_hours=72)
    news_penalty = float(news_risk.get("penalty_points", 0.0))

    # 5. Global Relativity
    stats = _get_global_env_stats()
    global_avg = stats["average"]

    env_diff = env_score - global_avg
    nb_diff = nb_score - global_avg

    env_standing = "above" if env_diff >= 0 else "below"
    nb_standing = "above" if nb_diff >= 0 else "below"

    # 6. Hybrid Scoring
    base_score = (
        (crime_score * WEIGHT_CRIME)
        + (env_score * WEIGHT_ENVIRONMENT_DIRECT)
        + (nb_score * WEIGHT_ENVIRONMENT_NEIGHBORHOOD)
    )
    final_score = int(max(0, min(100, base_score + amenity_bonus + sanctuary_bonus - news_penalty)))

    # Combined explanations
    all_explanations = crime_explanations + env_explanations
    all_explanations.append(
        f"Infrastructure: {abs(env_diff):.1f} points {env_standing} the Botanic average."
    )
    if nb_count > 1:
        all_explanations.append(
            f"Area Context: {abs(nb_diff):.1f} points {nb_standing} average regional safety."
        )

    if len(segments) > 1:
        all_explanations.append(
            f"Consolidated {len(segments)} segments sharing street name '{street_name}'."
        )

    if sanctuary_details["reasons"]:
        all_explanations.extend(sanctuary_details["reasons"])
    if amenity_details["reasons"]:
        all_explanations.extend(amenity_details["reasons"])
    all_explanations.append(
        f"Local News Signal: -{news_penalty:.1f} points "
        f"(risk {news_risk.get('risk', 0):.1f}, {news_risk.get('incidents_used', 0)} incident(s))."
    )

    return {
        "street_id": street_id,
        "street_name": street_name,
        "consolidated_segments": len(segments),
        "segment_ids": [seg.get("properties", {}).get("id") for seg in segments],
        "location": {"lat": lat, "lng": lng, "geometry": centroid_source},
        "merged_geometry": merged_geometry,
        "score": final_score,
        "breakdown": {
            "crime": {"score": crime_score, "weight": WEIGHT_CRIME},
            "environment_direct": {
                "score": env_score,
                "weight": WEIGHT_ENVIRONMENT_DIRECT,
                "relative_to_avg": round(env_diff, 1),
            },
            "environment_neighborhood": {
                "score": round(nb_score, 1),
                "weight": WEIGHT_ENVIRONMENT_NEIGHBORHOOD,
                "relative_to_avg": round(nb_diff, 1),
            },
            "sanctuaries": {
                "type": "bonus",
                "count": sanctuary_details["count"],
                "bonus_applied": sanctuary_bonus,
            },
            "amenities": {
                "type": "bonus",
                "count": amenity_details["count"],
                "bonus_applied": amenity_bonus,
            },
            "regional_average": round(global_avg, 1),
            "news_signal": {
                "type": "penalty",
                "risk": news_risk.get("risk", 0.0),
                "incidents_used": news_risk.get("incidents_used", 0),
                "penalty_applied": news_penalty,
            },
        },
        "explanations": all_explanations,
        "environment": env_details,
        "sanctuaries": sanctuary_details,
        "amenities": amenity_details,
        "news_risk": news_risk,
    }


async def get_feature_combined_score(feature: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates the combined safety score for a GeoJSON feature object.
    """
    street_id = feature.get("properties", {}).get("id")
    if street_id:
        return await get_street_combined_score(street_id)

    # Fallback to coordinate-based if no ID
    geometry = feature.get("geometry", {})
    lat, lng = calculate_centroid(geometry)
    return await get_combined_safety_score(lat, lng)
