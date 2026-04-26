import json
import polars as pl
from pathlib import Path
from typing import Dict, Any, List
from sqlmodel import Session, select
from db.database import engine
from db.models import Venue
from functools import lru_cache
from datetime import datetime, time
from services.geo import haversine_m, min_distance_to_geometry

_BASE = Path(__file__).parent.parent.parent
_DATASETS = _BASE / "datasets"

PARKS_CSV = _DATASETS / "parksdata.csv"
BIKE_STATIONS_CSV = _DATASETS / "belfast-bike-stations-updated-25-june-2021.csv"
# FOURSQUARE_JSON = _DATASETS / "foursquare_pois_belfast_enriched.json" # Now using database

# ---------------------------------------------------------------------------
# Amenity Definitions & Safety Weights
# ---------------------------------------------------------------------------

# Static Amenities (Public infrastructure)
AMENITY_SAFETY_WEIGHTS = {
    "bike_station": 1.0,
    "park": 1.5,
}

# Safe Sanctuaries (Active businesses/services)
SANCTUARY_SAFETY_WEIGHTS = {
    "police": 8.0,      # High weight for safety
    "hospital": 5.0,
    "pharmacy": 4.0,    # Increased weight
    "fire_station": 4.0,
    "hotel": 3.0,
    "convenience": 2.0,
    "supermarket": 2.5,
    "night_club": 2.0,
    "gym": 1.5,
    "library": 1.5,
    "university": 1.0,
}

AMENITY_RADIUS_M = 25.0

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_static_amenities() -> List[Dict[str, Any]]:
    """Load parks and bike stations."""
    combined = []
    if PARKS_CSV.exists():
        try:
            df = pl.read_csv(PARKS_CSV, ignore_errors=True)
            for row in df.to_dicts():
                combined.append({"name": row.get("NAME"), "type": "park", "lat": float(row.get("LATITUDE")), "lng": float(row.get("LONGITUDE"))})
        except: pass
    if BIKE_STATIONS_CSV.exists():
        try:
            df = pl.read_csv(BIKE_STATIONS_CSV, ignore_errors=True)
            for row in df.to_dicts():
                combined.append({"name": row.get("Location"), "type": "bike_station", "lat": float(row.get("Latitude")), "lng": float(row.get("Longitude"))})
        except: pass
    return combined

def _load_safe_sanctuaries() -> List[Dict[str, Any]]:
    """Load Foursquare POIs from Database."""
    combined = []
    try:
        with Session(engine) as session:
            venues = session.exec(select(Venue).where(Venue.is_active == True)).all()
            for row in venues:
                fsq_cat = (row.category or "").lower()
                internal_type = "unknown"
                if any(x in fsq_cat for x in ["pharmacy", "drugstore"]): internal_type = "pharmacy"
                elif "convenience" in fsq_cat: internal_type = "convenience"
                elif "supermarket" in fsq_cat: internal_type = "supermarket"
                elif "night club" in fsq_cat or "bar" in fsq_cat: internal_type = "night_club"
                elif "gym" in fsq_cat: internal_type = "gym"
                elif "library" in fsq_cat: internal_type = "library"
                elif "university" in fsq_cat or "college" in fsq_cat: internal_type = "university"
                elif any(x in fsq_cat for x in ["police", "law enforcement"]): internal_type = "police"
                elif any(x in fsq_cat for x in ["hospital", "medical", "surgery", "doctor"]): internal_type = "hospital"
                elif "hotel" in fsq_cat or "hostel" in fsq_cat: internal_type = "hotel"
                elif "taxi" in fsq_cat or "ambulance" in fsq_cat: internal_type = "emergency"
                
                combined.append({
                    "sanctuary_id": row.external_id,
                    "name": row.name,
                    "type": internal_type,
                    "lat": float(row.lat),
                    "lng": float(row.lng),
                    "opening_hours": row.opening_hours,
                    "hours_status": row.hours_status,
                    "bonus_multiplier": _get_hours_multiplier(row.hours_status),
                    "trust_score": row.trust_score
                })
    except Exception as e:
        print(f"Error loading Sanctuaries: {e}")
    return combined

def _get_hours_multiplier(status: str) -> float:
    if status == "verified_24_7": return 1.5
    if status == "late_night_known": return 1.2
    if status == "late_night_likely": return 1.1
    if status == "guestimated_extended_hours": return 1.05
    return 1.0

def compute_amenity_signals(lat: float, lng: float, geometry: Dict[str, Any] = None) -> Dict[str, Any]:
    """Computes safety signals based on nearby static public amenities."""
    amenities = _load_static_amenities()
    nearby = []
    total_bonus = 0.0
    for am in amenities:
        if geometry:
            dist = min_distance_to_geometry(am["lat"], am["lng"], geometry)
        else:
            dist = haversine_m(lat, lng, am["lat"], am["lng"])
            
        if dist <= AMENITY_RADIUS_M:
            am_type = am["type"]
            bonus = AMENITY_SAFETY_WEIGHTS.get(am_type, 0.0)
            nearby.append({"name": am["name"], "type": am_type, "distance_m": round(dist, 1), "bonus": round(bonus, 1)})
            total_bonus += bonus
    
    total_bonus = min(total_bonus, 5.0) # Lower cap for static amenities
    reasons = [f"Amenity: {am['name']} ({am['type']}) nearby (+{am['bonus']:.1f})" for am in nearby]
    return {"count": len(nearby), "items": nearby, "bonus": round(total_bonus, 1), "reasons": reasons}

def is_open_at(hours_str: str, check_time: str) -> bool:
    """Checks if a venue is open at a specific time (HH:MM)."""
    if not hours_str or hours_str == "00:00-24:00":
        return True
    
    try:
        check_dt = datetime.strptime(check_time, "%H:%M").time()
        
        # Handle simple ranges like 09:00-21:00 or overnight 17:00-02:00
        start_str, end_str = hours_str.split("-")
        start_t = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_t = datetime.strptime(end_str.strip(), "%H:%M").time()
        
        if start_t <= end_t:
            # Normal range
            return start_t <= check_dt <= end_t
        else:
            # Overnight range
            return check_dt >= start_t or check_dt <= end_t
    except:
        return True # Default to open if parsing fails for hackathon demo

def compute_sanctuary_signals(lat: float, lng: float, check_time: str = None, geometry: Dict[str, Any] = None) -> Dict[str, Any]:
    """Computes safety signals based on nearby Safe Sanctuaries (active POIs)."""
    if not check_time:
        check_time = datetime.now().strftime("%H:%M")

    sanctuaries = _load_safe_sanctuaries()
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
                continue

            s_type = s["type"]
            base = SANCTUARY_SAFETY_WEIGHTS.get(s_type, 1.0)
            bonus = base * s["bonus_multiplier"] * (s["trust_score"] or 1.0)
            nearby.append({
                "name": s["name"], "type": s_type, "distance_m": round(dist, 1),
                "bonus": round(bonus, 1), "hours": s["hours_status"],
                "raw_hours": s.get("opening_hours"), "trust": s["trust_score"], "lat": s["lat"], "lng": s["lng"]
            })
            total_bonus += bonus

    total_bonus = min(total_bonus, 30.0) # Higher cap for safe sanctuaries
    reasons = [f"Sanctuary: {s['name']} ({s['type']}) is open (+{s['bonus']:.1f})" for s in nearby]
    return {"count": len(nearby), "total_venues_nearby": total_venues_nearby, "items": nearby, "bonus": round(total_bonus, 1), "reasons": reasons, "check_time": check_time}

def get_nearest_sanctuaries(lat: float, lng: float, limit: int = 5, check_time: str = None) -> List[Dict[str, Any]]:
    """Returns the top N nearest safe sanctuaries to a coordinate."""
    sanctuaries = _load_safe_sanctuaries()
    results = []
    for s in sanctuaries:
        if check_time and not is_open_at(s.get("opening_hours"), check_time):
            continue
            
        dist = haversine_m(lat, lng, s["lat"], s["lng"])
        results.append({**s, "distance_m": round(dist, 1)})
        
    # Sort by distance
    results.sort(key=lambda x: x["distance_m"])
    return results[:limit]
