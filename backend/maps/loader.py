import json
from pathlib import Path
from typing import Dict, Any, Optional
from services.geo import calculate_centroid, haversine_m

def load_botanic_streets():
    """
    Loads the cleaned seed data for Botanic streets.
    Returns a dict (FeatureCollection) or None if the file doesn't exist.
    """
    seed_path = Path(__file__).parent / "seed" / "botanic-streets.seed.geojson"
    if not seed_path.exists():
        return None
    with open(seed_path, "r", encoding="utf-8") as f:
        return json.load(f)

def find_nearest_street(lat: float, lng: float) -> Optional[Dict[str, Any]]:
    """
    Finds the closest street feature in the Botanic seed data to the given lat/lng.
    Returns the GeoJSON feature or None if no data.
    """
    data = load_botanic_streets()
    if not data or "features" not in data:
        return None
    
    nearest = None
    min_dist = float('inf')
    
    for feature in data["features"]:
        feat_lat, feat_lng = calculate_centroid(feature.get("geometry", {}))
        if feat_lat == 0.0 and feat_lng == 0.0:
            continue
            
        dist = haversine_m(lat, lng, feat_lat, feat_lng)
        if dist < min_dist:
            min_dist = dist
            nearest = feature
            
    return nearest
