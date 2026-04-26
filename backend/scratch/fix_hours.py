from sqlmodel import Session, select
from db.database import engine
from db.models import Venue

def _estimate_hours(cat: str):
    c = (cat or "").lower()
    if any(x in c for x in ["police", "hospital", "fire station", "hotel", "hostel", "emergency", "medical", "doctor", "clinic", "doctors"]):
        return "00:00-24:00", "verified_24_7"
    if any(x in c for x in ["night club", "bar", "pub", "disco", "nightclub"]):
        return "21:00-03:00", "late_night_known"
    if any(x in c for x in ["pharmacy", "drugstore", "convenience", "gas station", "fast_food", "restaurant"]):
        return "08:00-22:00", "late_night_likely"
    if any(x in c for x in ["supermarket", "grocery", "gym", "fitness"]):
        return "06:00-22:00", "guestimated_extended_hours"
    if any(x in c for x in ["library", "university", "college", "school", "park", "cafe", "clothes", "bakery", "unknown"]):
        return "09:00-18:00", "hours_unknown"
    return "09:00-18:00", "hours_unknown"  # Give ALL of them default hours to avoid parsing fails

with Session(engine) as session:
    venues = session.exec(select(Venue)).all()
    for v in venues:
        if not v.opening_hours or "-" not in v.opening_hours or ";" in v.opening_hours:
            h, s = _estimate_hours(v.category)
            v.opening_hours = h
            v.hours_status = s
    session.commit()
    print("Fixed venue hours.")
