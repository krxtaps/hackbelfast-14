from services.amenities.amenity_scoring import is_open_at
print(is_open_at("08:00-22:00", "21:00"))
print(is_open_at("21:00-03:00", "01:00"))
print(is_open_at("21:00-03:00", "12:00"))
