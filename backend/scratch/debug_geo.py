from services.geo import min_distance_to_geometry
from maps.loader import load_botanic_streets
import json

def debug_geometry_distance():
    # 1. Get Botanic Avenue geometry
    data = load_botanic_streets()
    botanic_segments = [f for f in data["features"] if f["properties"].get("name") == "Botanic Avenue"]
    
    # 2. Known Sanctuary (Michael Dwyers)
    s_lat, s_lng = 54.59496, -5.95091
    
    print(f"Testing distance from {s_lat}, {s_lng} to all Botanic Avenue segments...")
    for seg in botanic_segments:
        dist = min_distance_to_geometry(s_lat, s_lng, seg["geometry"])
        print(f"Segment {seg['properties']['id']}: {dist:.2f} meters")
    
    if dist < 200:
        print("SUCCESS: Distance is within 200m radius.")
    else:
        print("FAILURE: Distance is too large!")

if __name__ == "__main__":
    debug_geometry_distance()
