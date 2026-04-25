import sys
from pathlib import Path

# Add project root to path so we can import modules
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlmodel import Session
from maps.loader import load_botanic_streets
from db.models import Street
from db.database import engine, create_db_and_tables
from services.geo import calculate_centroid

def populate():
    print("Creating tables...")
    create_db_and_tables()

    print("Loading map data...")
    data = load_botanic_streets()
    if not data or "features" not in data:
        print("Failed to load map data.")
        return

    features = data["features"]
    print(f"Found {len(features)} features. Processing...")

    streets_to_add = []
    
    with Session(engine) as session:
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            
            # We only store streets that have names (optional, but requested for search)
            name = props.get("name")
            if not name:
                continue
                
            lat, lng = calculate_centroid(geom)
            if lat == 0.0 and lng == 0.0:
                continue

            street = Street(
                id=props.get("id"),
                name=name,
                highway=props.get("highway", "unknown"),
                centroid_lat=lat,
                centroid_lng=lng
            )
            streets_to_add.append(street)
            session.add(street)
            
        session.commit()
        print(f"Successfully added {len(streets_to_add)} named streets to the database.")

if __name__ == "__main__":
    populate()
