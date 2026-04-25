from typing import Dict, Any, Tuple

def calculate_centroid(geometry: Dict[str, Any]) -> Tuple[float, float]:
    """
    Computes a representative point (centroid) for a GeoJSON geometry.
    Supports LineString and MultiLineString.
    Returns (lat, lng).
    """
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])

    if not coordinates:
        return 0.0, 0.0

    all_points = []
    if geom_type == "LineString":
        all_points = coordinates
    elif geom_type == "MultiLineString":
        for line in coordinates:
            all_points.extend(line)
    elif geom_type == "Point":
        all_points = [coordinates]
    else:
        # Fallback for unexpected types
        return 0.0, 0.0

    if not all_points:
        return 0.0, 0.0

    sum_lng = sum(pt[0] for pt in all_points)
    sum_lat = sum(pt[1] for pt in all_points)
    count = len(all_points)

    return sum_lat / count, sum_lng / count


import math

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))
