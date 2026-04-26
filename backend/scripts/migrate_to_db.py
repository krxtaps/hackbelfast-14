import json
from pathlib import Path
from sqlmodel import Session, select
from db.database import engine, create_db_and_tables
from db.models import Venue

DATA_PATH = Path(__file__).parent.parent / "datasets" / "foursquare_pois_belfast_enriched.json"

def migrate_pois():
    print("Initializing database and tables...")
    create_db_and_tables()
    
    if not DATA_PATH.exists():
        print(f"Error: {DATA_PATH} not found.")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    count = 0
    with Session(engine) as session:
        for row in data:
            ext_id = row.get("external_id")
            if not ext_id:
                continue
            
            # Check if exists
            existing = session.exec(select(Venue).where(Venue.external_id == ext_id)).first()
            if existing:
                continue
                
            venue = Venue(
                external_id=ext_id,
                name=row.get("name"),
                category=row.get("category"),
                lat=row.get("lat"),
                lng=row.get("lng"),
                opening_hours=row.get("opening_hours"),
                hours_status=row.get("hours_status"),
                opening_hours_source=row.get("opening_hours_source", "unknown")
            )
            session.add(venue)
            count += 1
            
        session.commit()
    
    print(f"Successfully migrated {count} new venues to database.")

if __name__ == "__main__":
    migrate_pois()
