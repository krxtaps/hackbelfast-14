with open("services/amenities/amenity_scoring.py", "r") as f:
    content = f.read()

# Manual replacement strategy
new_func = '''def compute_sanctuary_signals(lat: float, lng: float, check_time: str = None, geometry: Dict[str, Any] = None) -> Dict[str, Any]:
    """Computes safety signals based on nearby Safe Sanctuaries (active POIs)."""
    if not check_time:
        check_time = datetime.now().strftime("%H:%M")

    sanctuaries = _load_safe_sanctuaries()
    nearby = []
    total_bonus = 0.0
    total_venues_nearby = 0
    for s in sanctuaries:
        if geometry:
            dist = min_distance_to_geometry(s["lat"], s["lng"], geometry)
        else:
            dist = haversine_m(lat, lng, s["lat"], s["lng"])

        if dist <= AMENITY_RADIUS_M:
            total_venues_nearby += 1
            # TIME FILTER: Only give bonus if open at check_time
            if not is_open_at(s.get("opening_hours"), check_time):
                continue

            s_type = s["type"]
            base = SANCTUARY_SAFETY_WEIGHTS.get(s_type, 1.0)
            bonus = base * s["bonus_multiplier"] * (s["trust_score"] or 1.0)
            nearby.append({
                "name": s["name"], "type": s_type, "distance_m": round(dist, 1),
                "bonus": round(bonus, 1), "hours": s["hours_status"],
                "raw_hours": s.get("opening_hours"), "trust": s["trust_score"], "lat": s["lat"], "lng": s["lng"]
            })
            total_bonus += bonus

    total_bonus = min(total_bonus, 30.0) # Higher cap for safe sanctuaries
    reasons = [f"Sanctuary: {s['name']} ({s['type']}) is open (+{s['bonus']:.1f})" for s in nearby]
    return {"count": len(nearby), "total_venues_nearby": total_venues_nearby, "items": nearby, "bonus": round(total_bonus, 1), "reasons": reasons, "check_time": check_time}
'''

import re
content = re.sub(r'def compute_sanctuary_signals.*?return \{"count".*?\}\n', new_func, content, flags=re.DOTALL)

with open("services/amenities/amenity_scoring.py", "w") as f:
    f.write(content)
