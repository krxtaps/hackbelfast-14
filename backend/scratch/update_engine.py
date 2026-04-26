with open("services/amenities/amenity_scoring.py", "r") as f:
    content = f.read()

old_loop = '''    sanctuaries = _load_safe_sanctuaries()
    nearby = []
    total_bonus = 0.0
    for s in sanctuaries:
        if geometry:
            dist = min_distance_to_geometry(s["lat"], s["lng"], geometry)
        else:
            dist = haversine_m(lat, lng, s["lat"], s["lng"])

        if dist <= AMENITY_RADIUS_M:
            # TIME FILTER: Only give bonus if open at check_time
            if not is_open_at(s.get("opening_hours"), check_time):
                continue'''

new_loop = '''    sanctuaries = _load_safe_sanctuaries()
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
                continue'''

content = content.replace(old_loop, new_loop)

old_return = '''return {"count": len(nearby), "items": nearby, "bonus": round(total_bonus, 1), "reasons": reasons, "check_time": check_time}'''
new_return = '''return {"count": len(nearby), "total_venues_nearby": total_venues_nearby, "items": nearby, "bonus": round(total_bonus, 1), "reasons": reasons, "check_time": check_time}'''

content = content.replace(old_return, new_return)

with open("services/amenities/amenity_scoring.py", "w") as f:
    f.write(content)

