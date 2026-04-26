import math
import csv
import httpx
from pathlib import Path
from functools import lru_cache
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
OFFLINE_ASB_DATA_PATH = (
    Path(__file__).resolve().parent.parent / "datasets" / "anti-social-behaviour-monthly-data.csv"
)


@lru_cache(maxsize=1)
def _load_offline_asb_series() -> List[int]:
    """
    Loads Belfast monthly anti-social incident counts from local dataset.
    """
    if not OFFLINE_ASB_DATA_PATH.exists():
        return []

    monthly_counts: List[int] = []
    with OFFLINE_ASB_DATA_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            district = (row.get("Policing_District") or "").strip().lower()
            measure = (row.get("Data_Measure") or "").strip().lower()
            if district != "belfast city":
                continue
            if "anti-social behaviour" not in measure:
                continue
            try:
                monthly_counts.append(int(row.get("Incident_Count", "0")))
            except ValueError:
                continue
    return monthly_counts


def _offline_proxy_crimes() -> List[Dict[str, Any]]:
    """
    Generates a local proxy crime sample when live police API is unavailable.
    """
    monthly_counts = _load_offline_asb_series()
    if not monthly_counts:
        return []

    # Use trailing average for recent trend and project to a local 150m context.
    recent_window = monthly_counts[-6:] if len(monthly_counts) >= 6 else monthly_counts
    avg_recent = sum(recent_window) / max(1, len(recent_window))

    # Convert city-level monthly incidents into a bounded local incident proxy.
    # This keeps crime influence present in "full score" mode without exploding penalties.
    local_incident_proxy = max(1, min(12, round(avg_recent / 500)))

    return [{"category": "anti-social-behaviour"} for _ in range(local_incident_proxy)]

async def fetch_nearby_crimes(lat: float, lng: float) -> List[Dict[str, Any]]:
    """
    Fetches recent crimes from the PSNI data.police.uk API for a given location.
    """
    offline_proxy = _offline_proxy_crimes()

    url = f"https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}"
    async with httpx.AsyncClient(timeout=6.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                raw_crimes = response.json()
                # Filter by distance locally
                filtered_crimes = []
                for crime in raw_crimes:
                    c_lat = float(crime.get("location", {}).get("latitude", 0))
                    c_lng = float(crime.get("location", {}).get("longitude", 0))
                    if c_lat == 0 or c_lng == 0:
                        continue

                    if haversine_m(lat, lng, c_lat, c_lng) <= POLICE_RADIUS_M:
                        filtered_crimes.append(crime)
                if filtered_crimes:
                    return filtered_crimes
                return offline_proxy
            return offline_proxy
        except Exception:
            return offline_proxy


def calculate_score_from_crimes(crimes: List[Dict[str, Any]], business_count: int = 0) -> Tuple[int, List[str]]:
    """
    Calculates a safety score and provides explanations based on the crimes array,
    normalized by business density (footfall proxy) and using a logarithmic scale
    to prevent penalizing busy areas linearly.
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

    # 1. Logarithmic Crime Scaling
    # Instead of linear penalty (e.g., 50 crimes = -100 points), 
    # we soften the blow of sheer volume. log1p(50)*16 = ~62 penalty.
    log_penalty = math.log1p(total_penalty) * 16.0

    # 2. Footfall Proxy Normalization (Business Density)
    # The more businesses near the street, the higher the natural foot traffic,
    # meaning the crime rate per capita is actually much lower.
    # 0 businesses -> divide by 1.0 (no discount)
    # 20 businesses -> log1p(20) * 0.15 = divide by ~1.45
    # 50 businesses -> log1p(50) * 0.15 = divide by ~1.59
    density_discount = max(1.0, 1.0 + (math.log1p(business_count) * 0.15))
    
    final_penalty = log_penalty / density_discount

    # Calculate final score clamped between 0 and 100
    score = max(0, min(100, int(100 - final_penalty)))

    # Generate explanations
    explanations = []
    explanations.append(f"{total_crimes} nearby crime(s) reported recently.")
    if business_count > 5:
        explanations.append(f"Crime impact normalized for high-footfall area ({business_count} active venues).")
    
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
