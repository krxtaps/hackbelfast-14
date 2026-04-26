with open("services/safety_engine.py", "r") as f:
    content = f.read()

old_logic = '''    # 1. Crime Analytics at street centroid
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes)

    # 2. Environmental Signals for this specific feature
    env_details = compute_environment_signals(feature)
    env_score = env_details.get("score", 100)
    env_explanations = env_details.get("reasons", [])

    # 3. Neighborhood Context
    nb_score, nb_count = _get_neighborhood_env_score(lat, lng)

    # 4. Amenities & Sanctuaries
    amenity_details = compute_amenity_signals(lat, lng, geometry=geometry)
    sanctuary_details = compute_sanctuary_signals(lat, lng, check_time=check_time, geometry=geometry)'''

new_logic = '''    # 1. Amenities & Sanctuaries
    amenity_details = compute_amenity_signals(lat, lng, geometry=geometry)
    sanctuary_details = compute_sanctuary_signals(lat, lng, check_time=check_time, geometry=geometry)
    total_venues = sanctuary_details.get("total_venues_nearby", 0)

    # 2. Crime Analytics at street centroid
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes, business_count=total_venues)

    # 3. Environmental Signals for this specific feature
    env_details = compute_environment_signals(feature)
    env_score = env_details.get("score", 100)
    env_explanations = env_details.get("reasons", [])

    # 4. Neighborhood Context
    nb_score, nb_count = _get_neighborhood_env_score(lat, lng)'''

content = content.replace(old_logic, new_logic)

old_coord = '''    # 1. Crime Analytics
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes)

    # 2. Environmental Signals (Direct & Relative)'''

new_coord = '''    # 1. Amenities & Sanctuaries
    amenity_details = compute_amenity_signals(lat, lng)
    sanctuary_details = compute_sanctuary_signals(lat, lng, check_time=check_time)
    total_venues = sanctuary_details.get("total_venues_nearby", 0)

    # 2. Crime Analytics
    crimes = await fetch_nearby_crimes(lat, lng)
    crime_score, crime_explanations = calculate_score_from_crimes(crimes, business_count=total_venues)

    # 3. Environmental Signals (Direct & Relative)'''

content = content.replace(old_coord, new_coord)

# remove the later computation of amenities in coord
content = content.replace('''    # 4. Amenities & Sanctuaries (Landmarks)
    amenity_details = compute_amenity_signals(lat, lng)
    sanctuary_details = compute_sanctuary_signals(lat, lng, check_time=check_time)

''', "")

with open("services/safety_engine.py", "w") as f:
    f.write(content)
