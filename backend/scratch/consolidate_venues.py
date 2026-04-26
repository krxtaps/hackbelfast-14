import re

with open("main.py", "r") as f:
    content = f.read()

old_regex = r'@app\.get\("/streets/\{street_id\}/venues".*?return \{(?:[^{}]*|\{[^{}]*\})*\}'

new_endpoint = '''@app.get("/streets/{street_id}/venues", tags=["Sanctuaries"])
def get_street_venues(street_id: str):
    """
    Returns all venues physically located on or immediately adjacent to the ENTIRE street 
    (automatically finding and consolidating all street segments that share the same name).
    """
    from maps.loader import load_botanic_streets
    from services.geo import min_distance_to_geometry
    from services.amenities.amenity_scoring import _load_safe_sanctuaries, AMENITY_RADIUS_M

    streets_data = load_botanic_streets()
    if not streets_data or "features" not in streets_data:
        raise HTTPException(status_code=404, detail="Street data not available")

    # Find the target street to get its name
    target_feature = next(
        (f for f in streets_data["features"] if f.get("properties", {}).get("id") == street_id),
        None
    )

    if not target_feature:
        raise HTTPException(status_code=404, detail=f"Street with ID '{street_id}' not found")

    street_name = target_feature.get("properties", {}).get("name")

    # Find ALL segments that share this street name
    if street_name:
        segments = [f for f in streets_data["features"] if f.get("properties", {}).get("name") == street_name]
    else:
        segments = [target_feature]

    sanctuaries = _load_safe_sanctuaries()
    
    seen_venues = set()
    results = []
    
    for s in sanctuaries:
        lat, lng = s["lat"], s["lng"]
        # Check if this venue is close to ANY of the street segments
        for seg in segments:
            geom = seg.get("geometry", {})
            dist = min_distance_to_geometry(lat, lng, geom)
            if dist <= AMENITY_RADIUS_M:
                # Use coordinates and name as a unique identifier to prevent duplicates
                venue_id = f"{s.get('name')}_{lat}_{lng}"
                if venue_id not in seen_venues:
                    seen_venues.add(venue_id)
                    s_data = s.copy()
                    s_data["distance_m"] = round(dist, 1)
                    results.append(s_data)
                break # Already added, skip checking remaining segments for this venue

    results.sort(key=lambda x: x["distance_m"])
    return {
        "street_id": street_id, 
        "street_name": street_name or "Unknown", 
        "segments_consolidated": len(segments),
        "venues_count": len(results), 
        "venues": results
    }'''

content = re.sub(old_regex, new_endpoint, content, flags=re.DOTALL)

with open("main.py", "w") as f:
    f.write(content)
