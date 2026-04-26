import json
from pathlib import Path
from sqlmodel import Session, select
from db.database import engine
from db.models import Venue

DATA_PATH = Path("datasets/osm_pois_belfast.json")

def migrate_osm():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    with Session(engine) as session:
        for row in data:
            ext_id = row.get("external_id")
            if not ext_id: continue

            existing = session.exec(select(Venue).where(Venue.external_id == ext_id)).first()
            if existing: continue

            venue = Venue(
                external_id=ext_id,
                name=row.get("name"),
                category=row.get("category"),
                lat=row.get("lat"),
                lng=row.get("lng"),
                opening_hours=row.get("opening_hours"),
                hours_status=row.get("hours_status"),
                opening_hours_source="osm"
            )
            session.add(venue)
            count += 1

        session.commit()
    print(f"Successfully migrated {count} OSM venues to database.")

if __name__ == "__main__":
    migrate_osm()
