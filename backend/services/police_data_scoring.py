import httpx
from typing import Dict, Any, List, Tuple
from collections import Counter
from services.geo import haversine_m

POLICE_RADIUS_M = 150.0  # Limit crime influence to 150m walking radius

# No longer needed here, moved to safety_engine.py

# Weights for different crime categories
CRIME_WEIGHTS = {
    "violent-crime": 5,
    "robbery": 5,
    "criminal-damage-arson": 4,
    "public-order": 3,
    "drugs": 3,
    "anti-social-behaviour": 2,
    "burglary": 2,
    "vehicle-crime": 2,
    "other-theft": 1,
    "shoplifting": 1,
}
DEFAULT_WEIGHT = 1
SCALE_FACTOR = 1.0 # 1 point of weight = 1 point off the score

async def fetch_nearby_crimes(lat: float, lng: float) -> List[Dict[str, Any]]:
    """
    Fetches recent crimes from the PSNI data.police.uk API for a given location.
    """
    url = f"https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                raw_crimes = response.json()
                # Filter by distance locally
                filtered_crimes = []
                for crime in raw_crimes:
                    c_lat = float(crime.get("location", {}).get("latitude", 0))
                    c_lng = float(crime.get("location", {}).get("longitude", 0))
                    if c_lat == 0 or c_lng == 0: continue
                    
                    if haversine_m(lat, lng, c_lat, c_lng) <= POLICE_RADIUS_M:
                        filtered_crimes.append(crime)
                return filtered_crimes
            return []
        except Exception as e:
            print(f"Error fetching crime data: {e}")
            return []


def calculate_score_from_crimes(crimes: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """
    Calculates a safety score and provides explanations based on the crimes array.
    Returns (score, explanations).
    """
    if not crimes:
        return 100, ["No recent crimes reported in this immediate area.", "Generally safe area."]

    total_crimes = len(crimes)
    total_penalty = 0
    category_counts = Counter()

    for crime in crimes:
        category = crime.get("category", "other-crime")
        category_counts[category] += 1
        weight = CRIME_WEIGHTS.get(category, DEFAULT_WEIGHT)
        total_penalty += weight * SCALE_FACTOR

    # Calculate final score clamped between 0 and 100
    score = max(0, min(100, int(100 - total_penalty)))

    # Generate explanations
    explanations = []
    explanations.append(f"{total_crimes} nearby crime(s) reported recently.")
    
    # Add specific callouts for severe crimes
    if category_counts["violent-crime"] > 0:
        explanations.append(f"Contains {category_counts['violent-crime']} report(s) of violent crime.")
    if category_counts["robbery"] > 0:
        explanations.append(f"Contains {category_counts['robbery']} report(s) of robbery.")
    if category_counts["anti-social-behaviour"] >= 5:
        explanations.append(f"High level of anti-social behaviour ({category_counts['anti-social-behaviour']} reports).")
        
    if score >= 80:
        explanations.append("Area appears generally safe with low severe crime activity.")
    elif score >= 50:
        explanations.append("Moderate crime activity detected.")
    else:
        explanations.append("Caution advised: High volume or severity of recent crimes in this area.")

    return score, explanations
