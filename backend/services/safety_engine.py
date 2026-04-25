from typing import Dict, Any, List
from services.police_data_scoring import fetch_nearby_crimes, calculate_score_from_crimes
from services.environment_scoring import compute_environment_signals
from maps.loader import find_nearest_street, load_botanic_streets
from services.geo import calculate_centroid

# Weight configuration
WEIGHT_CRIME = 0.7
WEIGHT_ENVIRONMENT = 0.3

async def get_combined_safety_score(lat: float, lng: float) -> Dict[str, Any]:
    """
    Core safety engine: Combines Crime Safety and Environmental Safety.
    Returns a unified score and detailed explanation breakdown.
    """
    # 1. Crime Analytics (via Police Data Service)
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes)
    
    # 2. Environmental Signals (via Environment Service)
    env_score = 100
    env_explanations = []
    env_details = None
    
    nearest_street = find_nearest_street(lat, lng)
    if nearest_street:
        env_details = compute_environment_signals(nearest_street)
        env_score = env_details.get("score", 100)
        env_explanations = env_details.get("reasons", [])
    else:
        env_explanations = ["No specific street-level environment data found for this exact location."]

    # 3. Hybrid Scoring Logic
    final_score = int((crime_score * WEIGHT_CRIME) + (env_score * WEIGHT_ENVIRONMENT))
    
    # Unified Explanations
    explanations = []
    explanations.append("--- Crime & Security ---")
    explanations.extend(crime_explanations)
    explanations.append("--- Physical Environment ---")
    explanations.extend(env_explanations)

    return {
        "location": {"lat": lat, "lng": lng},
        "score": final_score,
        "breakdown": {
            "crime": {
                "score": crime_score,
                "weight": WEIGHT_CRIME,
                "count": len(crimes)
            },
            "environment": {
                "score": env_score,
                "weight": WEIGHT_ENVIRONMENT,
                "street": env_details.get("street_name") if env_details else None
            }
        },
        "explanations": explanations,
        "raw_data": {
            "crimes": crimes,
            "environment": env_details
        }
    }

async def get_street_combined_score(street_id: str) -> Dict[str, Any]:
    """
    Calculates the combined safety score for a specific street by its ID.
    """
    streets_data = load_botanic_streets()
    if not streets_data or "features" not in streets_data:
        return {"error": "Street data not available"}
        
    feature = next(
        (f for f in streets_data["features"] if f.get("properties", {}).get("id") == street_id),
        None
    )
    
    if not feature:
        return {"error": f"Street with ID '{street_id}' not found"}
        
    geometry = feature.get("geometry", {})
    lat, lng = calculate_centroid(geometry)
    
    # 1. Crime Analytics at street centroid
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes)
    
    # 2. Environmental Signals for this specific feature
    env_details = compute_environment_signals(feature)
    env_score = env_details.get("score", 100)
    env_explanations = env_details.get("reasons", [])

    # 3. Hybrid Scoring
    final_score = int((crime_score * WEIGHT_CRIME) + (env_score * WEIGHT_ENVIRONMENT))
    
    return {
        "street_id": street_id,
        "street_name": feature.get("properties", {}).get("name"),
        "location": {"lat": lat, "lng": lng},
        "score": final_score,
        "breakdown": {
            "crime": {"score": crime_score, "weight": WEIGHT_CRIME},
            "environment": {"score": env_score, "weight": WEIGHT_ENVIRONMENT}
        },
        "explanations": crime_explanations + env_explanations,
        "environment": env_details
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
