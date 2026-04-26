import json
from pathlib import Path

for filename in ["datasets/foursquare_pois_belfast.json", "datasets/foursquare_pois_belfast_enriched.json"]:
    fsq_file = Path(filename)
    if not fsq_file.exists(): continue
    records = json.loads(fsq_file.read_text())

    def _estimate_hours_for_category(category: str):
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

    updated = 0
    for r in records:
        if r.get("hours_status") == "hours_unknown" or not r.get("opening_hours"):
            est_h, est_s = _estimate_hours_for_category(r.get("category", ""))
            if est_h:
                r["opening_hours"] = est_h
                r["hours_status"] = est_s
                updated += 1

    fsq_file.write_text(json.dumps(records, indent=2))
    print(f"Updated {updated} records in {filename}.")
