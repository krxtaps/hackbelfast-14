import json
from sqlmodel import Session, select
from db.database import engine
from db.models import Venue

def _estimate_hours_for_category(category: str):
    if not category: return None, "hours_unknown"
    cat = category.lower()
    if any(x in cat for x in ["police", "hospital", "fire station", "hotel", "hostel", "emergency", "medical", "doctor"]):
        return "00:00-24:00", "verified_24_7"
    if any(x in cat for x in ["night club", "bar", "pub", "disco"]):
        return "21:00-03:00", "late_night_known"
    if any(x in cat for x in ["pharmacy", "drugstore", "convenience", "gas station"]):
        return "08:00-22:00", "late_night_likely"
    if any(x in cat for x in ["supermarket", "grocery", "gym", "fitness"]):
        return "06:00-22:00", "guestimated_extended_hours"
    if any(x in cat for x in ["library", "university", "college", "school", "park"]):
        return "09:00-18:00", "hours_unknown"
    return None, "hours_unknown"

with Session(engine) as session:
    venues = session.exec(select(Venue)).all()
    updated = 0
    for v in venues:
        if v.hours_status == "hours_unknown" or not v.opening_hours:
            est_h, est_s = _estimate_hours_for_category(v.category)
            if est_h:
                v.opening_hours = est_h
                v.hours_status = est_s
                updated += 1
    session.commit()
    print(f"Updated {updated} DB rows.")
