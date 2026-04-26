import math
from typing import Any, Dict, Iterable, Tuple


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


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def bbox_from_points(
    points: Iterable[Tuple[float, float]],
    buffer_m: float = 0.0,
) -> Tuple[float, float, float, float]:
    """
    Compute a bounding box (min_lat, min_lng, max_lat, max_lng) with an optional
    meter buffer applied.
    """
    pts = list(points)
    if not pts:
        return 0.0, 0.0, 0.0, 0.0

    lats = [p[0] for p in pts]
    lngs = [p[1] for p in pts]

    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)

    if buffer_m <= 0:
        return min_lat, min_lng, max_lat, max_lng

    mean_lat = (min_lat + max_lat) / 2
    lat_buf = buffer_m / 111_320.0
    denom = 111_320.0 * math.cos(math.radians(mean_lat))
    lng_buf = buffer_m / denom if denom != 0 else 0.0

    return (
        min_lat - lat_buf,
        min_lng - lng_buf,
        max_lat + lat_buf,
        max_lng + lng_buf,
    )


def point_to_segment_distance_m(
    p_lat: float, p_lng: float, s1: Tuple[float, float], s2: Tuple[float, float]
) -> float:
    """
    Computes the minimum distance in meters from point P to line segment (S1, S2).
    S1 and S2 are (lng, lat) tuples from GeoJSON.
    """
    # Convert to (lat, lng) for haversine
    s1_lat, s1_lng = s1[1], s1[0]
    s2_lat, s2_lng = s2[1], s2[0]

    # We use a simple projection for small distances (hackathon-friendly)
    # For more precision, one would use a proper spatial library, but this works well for Belfast scale.

    # Distance from P to S1 and S2
    d1 = haversine_m(p_lat, p_lng, s1_lat, s1_lng)

    # Check if P projects onto segment
    # Using dot product in local planar approx
    dx = s2_lng - s1_lng
    dy = s2_lat - s1_lat
    if dx == 0 and dy == 0:
        return d1

    t = ((p_lng - s1_lng) * dx + (p_lat - s1_lat) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))

    proj_lat = s1_lat + t * dy
    proj_lng = s1_lng + t * dx

    return haversine_m(p_lat, p_lng, proj_lat, proj_lng)


def min_distance_to_geometry(
    p_lat: float, p_lng: float, geometry: Dict[str, Any]
) -> float:
    """
    Finds the minimum distance in meters from a point to any part of the GeoJSON geometry.
    """
    g_type = geometry.get("type")
    coords = geometry.get("coordinates", [])

    if g_type == "Point":
        return haversine_m(p_lat, p_lng, coords[1], coords[0])

    lines = []
    if g_type == "LineString":
        lines = [coords]
    elif g_type == "MultiLineString":
        lines = coords
    else:
        return 999999.0

    min_dist = 999999.0
    for line in lines:
        for i in range(len(line) - 1):
            dist = point_to_segment_distance_m(p_lat, p_lng, line[i], line[i + 1])
            if dist < min_dist:
                min_dist = dist

    return min_dist


def consolidate_street_segments(
    feature: Dict[str, Any],
    streets_data: Dict[str, Any],
) -> Tuple[list[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Consolidates all street segments that share the same street name.
    This matches the dashboard behavior of grouping segments by street name.

    Args:
        feature: The target street feature
        streets_data: The full GeoJSON FeatureCollection (with "features" key)

    Returns:
        (segments, street_name, merged_geometry)
        - segments: List of all features sharing the same street name
        - street_name: The consolidated street name (or empty string if None)
        - merged_geometry: A MultiLineString combining all segment geometries
    """
    if not streets_data or "features" not in streets_data:
        return [feature], "", feature.get("geometry", {})

    street_name = feature.get("properties", {}).get("name") or ""

    # Collect ALL segments that share this street name
    if street_name:
        segments = [
            f
            for f in streets_data["features"]
            if f.get("properties", {}).get("name") == street_name
        ]
    else:
        segments = [feature]

    # Build merged geometry from all segments
    merged_coords = []
    for seg in segments:
        geom = seg.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])
        if gtype == "LineString":
            merged_coords.append(coords)
        elif gtype == "MultiLineString":
            for line in coords:
                merged_coords.append(line)

    merged_geometry = (
        {"type": "MultiLineString", "coordinates": merged_coords}
        if merged_coords
        else feature.get("geometry", {})
    )

    return segments, street_name, merged_geometry
