import re

with open("main.py", "r") as f:
    content = f.read()

new_endpoint = '''
@app.get("/streets/{street_id}/venues", tags=["Sanctuaries"])
def get_street_venues(street_id: str):
    """
    Returns all venues (Safe Sanctuaries and businesses) physically located on or immediately adjacent to a specific street.
    """
    from maps.loader import load_botanic_streets
    from services.geo import min_distance_to_geometry
    from services.amenities.amenity_scoring import _load_safe_sanctuaries, AMENITY_RADIUS_M

    streets_data = load_botanic_streets()
    if not streets_data or "features" not in streets_data:
        raise HTTPException(status_code=404, detail="Street data not available")

    feature = next(
        (f for f in streets_data["features"] if f.get("properties", {}).get("id") == street_id),
        None
    )

    if not feature:
        raise HTTPException(status_code=404, detail=f"Street with ID '{street_id}' not found")

    geometry = feature.get("geometry", {})
    sanctuaries = _load_safe_sanctuaries()
    
    results = []
    for s in sanctuaries:
        dist = min_distance_to_geometry(s["lat"], s["lng"], geometry)
        if dist <= AMENITY_RADIUS_M:
            s_data = s.copy()
            s_data["distance_m"] = round(dist, 1)
            results.append(s_data)

    results.sort(key=lambda x: x["distance_m"])
    return {
        "street_id": street_id, 
        "street_name": feature.get("properties", {}).get("name"), 
        "venues_count": len(results), 
        "venues": results
    }
'''

content += new_endpoint

with open("main.py", "w") as f:
    f.write(content)
