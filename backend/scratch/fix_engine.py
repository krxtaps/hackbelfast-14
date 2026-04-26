import re

with open("services/amenities/amenity_scoring.py", "r") as f:
    content = f.read()

loop_regex = r'''    sanctuaries = _load_safe_sanctuaries\(\)\n    nearby = \[\]\n    total_bonus = 0\.0\n    for s in sanctuaries:\n        if geometry:\n            dist = min_distance_to_geometry\(s\["lat"\], s\["lng"\], geometry\)\n        else:\n            dist = haversine_m\(lat, lng, s\["lat"\], s\["lng"\]\)\n\n        if dist <= AMENITY_RADIUS_M:\n            # TIME FILTER: Only give bonus if open at check_time\n            if not is_open_at\(s.get\("opening_hours"\), check_time\):\n                continue'''

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

content = re.sub(loop_regex, new_loop, content)

with open("services/amenities/amenity_scoring.py", "w") as f:
    f.write(content)
