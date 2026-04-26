from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from typing import Optional
from sqlmodel import Session, select


from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class LocationGeometry(BaseModel):
    type: str = Field(..., description="GeoJSON type, e.g., LineString or MultiLineString")
    coordinates: list = Field(..., description="GeoJSON coordinates array. Use this to draw the street on a map.")

class LocationInfo(BaseModel):
    lat: float = Field(..., description="Center latitude")
    lng: float = Field(..., description="Center longitude")
    geometry: Optional[LocationGeometry] = Field(None, description="The physical GeoJSON shape of the street")

class BreakdownComponent(BaseModel):
    score: float
    weight: float
    relative_to_avg: Optional[float] = None

class BreakdownBonus(BaseModel):
    type: str
    count: int
    bonus_applied: float

class ScoreBreakdown(BaseModel):
    crime: BreakdownComponent
    environment_direct: BreakdownComponent
    environment_neighborhood: BreakdownComponent
    sanctuaries: BreakdownBonus
    amenities: BreakdownBonus
    regional_average: float

class SanctuaryItem(BaseModel):
    name: str = Field(..., description="Name of the business")
    type: str = Field(..., description="Category (e.g., pharmacy, convenience, night_club)")
    distance_m: float = Field(..., description="Distance in meters from the street/user")
    bonus: float = Field(..., description="Safety bonus applied")
    hours: str = Field(..., description="The estimated hours category (e.g., late_night_likely)")
    raw_hours: Optional[str] = Field(None, description="Actual HH:MM-HH:MM if known")
    trust: float
    lat: float = Field(..., description="Latitude of the safe sanctuary. Use to plot green circles on map.")
    lng: float = Field(..., description="Longitude of the safe sanctuary.")

class SanctuaryDetails(BaseModel):
    count: int
    items: List[SanctuaryItem]
    bonus: float
    reasons: List[str]
    check_time: str

class SafetyScoreResponse(BaseModel):
    street_id: Optional[str] = Field(None, description="Internal Botanics ID")
    street_name: Optional[str] = Field(None, description="Human readable street name")
    location: LocationInfo
    score: int = Field(..., description="Final combined safety score (0-100)")
    breakdown: ScoreBreakdown = Field(..., description="Detailed mathematical breakdown of weights")
    explanations: List[str] = Field(..., description="User-friendly text explaining the score factors")
    environment: Dict[str, Any]
    sanctuaries: SanctuaryDetails = Field(..., description="List of currently OPEN safe sanctuaries nearby")
    amenities: Dict[str, Any]
    raw_data: Optional[Dict[str, Any]] = None

from db.database import create_db_and_tables, get_session
from db.models import Street
from maps.loader import load_botanic_streets
from services.environment_scoring import compute_all_environment_signals, compute_environment_signals
from services.safety_engine import get_combined_safety_score, get_street_combined_score
from services.amenities.amenity_scoring import get_nearest_sanctuaries

@asynccontextmanager
async def lifespan(app: FastAPI):
    description="""Handles startup and shutdown events."""
    create_db_and_tables()
    yield

app = FastAPI(
    title="SafeWalk Botanic API",
    description="""
    ## Hybrid Safety Scoring for Belfast (Botanic Area)

    This API provides real-time safety metrics for urban walking. It combines three primary signal layers:

    1. **Crime Safety (40%)**: Real-time data from the Police API, weighted by severity and proximity.
    2. **Physical Infrastructure (40%)**: Street lighting, surface quality, and road classification.
    3. **Sanctuary Bonus (Additive up to +30)**: Proximity to active, open safe-havens like hospitals, pharmacies, and verified businesses.

    Scores are **Time-Aware**: venues that are closed at the requested time do not contribute to the safety bonus.
    description=""",
    version="1.1.0",
    lifespan=lifespan,
    contact={
        "name": "SafeWalk Team",
        "url": "https://github.com/arpanpandey/HackBelfast"
    }
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.get("/", tags=["General"])
def read_root():
    return {"status": "online", "area": "Botanic, Belfast", "engine": "SafeWalk Hybrid v1.1"}

# ---------------------------------------------------------------------------
# Safety Scoring Endpoints
# ---------------------------------------------------------------------------

@app.get("/score", tags=["Safety Engine"], response_model=SafetyScoreResponse, response_model_exclude_none=True)
async def get_score(
    street_id: str, 
    time: Optional[str] = Query(None, description="Current time (HH:MM). If empty, server time is used.")
):
    description="""
    Returns the comprehensive safety score for a specific street by its internal ID.
    description="""
    result = await get_street_combined_score(street_id, check_time=time)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/score/coord", tags=["Safety Engine"], response_model=SafetyScoreResponse, response_model_exclude_none=True)
async def get_score_by_coord(
    lat: float, 
    lng: float, 
    time: Optional[str] = Query(None, description="Current time (HH:MM).")
):
    description="""
    Hybrid scoring for any coordinate. 
    Snaps to the nearest street for environment data but uses exact location for crime/amenities.
    description="""
    return await get_combined_safety_score(lat, lng, check_time=time)

# ---------------------------------------------------------------------------
# Sanctuary & Amenity Endpoints
# ---------------------------------------------------------------------------

@app.get("/sanctuaries/nearest", tags=["Sanctuaries"])
def get_nearby_sanctuaries(
    lat: float, 
    lng: float, 
    limit: int = Query(5, description="Max results"), 
    time: Optional[str] = Query(None, description="HH:MM. Filters for open venues only.")
):
    description="""
    Finds the closest Safe Sanctuaries (Foursquare POIs) from a coordinate.
    description="""
    return get_nearest_sanctuaries(lat, lng, limit=limit, check_time=time)

# ---------------------------------------------------------------------------
# Navigation & Search Endpoints
# ---------------------------------------------------------------------------

@app.get("/streets/search", tags=["Navigation"])
def search_streets(q: str, session: Session = Depends(get_session)):
    description="""Search for streets by name within the Botanic area."""
    statement = select(Street).where(Street.name.contains(q))
    results = session.exec(statement).all()
    if not results:
        raise HTTPException(status_code=404, detail="No matching streets found")
    return results

@app.get("/streets/botanic", tags=["Navigation"])
def get_botanic_streets():
    description="""Returns the full GeoJSON street network for the Botanic area."""
    data = load_botanic_streets()
    if not data:
        raise HTTPException(status_code=404, detail="Botanic streets data not found")
    return data

# ---------------------------------------------------------------------------
# Environment Endpoints
# ---------------------------------------------------------------------------

@app.get("/streets/botanic/environment", tags=["Infrastructure"])
def get_botanic_environment():
    description="""Returns pre-calculated environment signals for every street."""
    return compute_all_environment_signals()

@app.get("/streets/botanic/environment/{street_id}", tags=["Infrastructure"])
def get_street_environment(street_id: str):
    description="""Returns detailed infrastructure signals for a single street."""
    features = load_botanic_streets()
    if not features:
        raise HTTPException(status_code=404, detail="Botanic seed data not found")
    
    feature_list = features.get("features", []) if isinstance(features, dict) else []
    match = next((f for f in feature_list if f.get("properties", {}).get("id") == street_id), None)
    
    if match is None:
        raise HTTPException(status_code=404, detail=f"Street '{street_id}' not found")
    return compute_environment_signals(match)

@app.get("/streets/{street_id}/venues", tags=["Sanctuaries"])
def get_street_venues(street_id: str):
    """
    Returns all venues physically located on or immediately adjacent to the ENTIRE street 
    (automatically finding and consolidating all street segments that share the same name).
    """
    from maps.loader import load_botanic_streets
    from services.geo import min_distance_to_geometry
    from services.amenities.amenity_scoring import _load_safe_sanctuaries, AMENITY_RADIUS_M

    streets_data = load_botanic_streets()
    if not streets_data or "features" not in streets_data:
        raise HTTPException(status_code=404, detail="Street data not available")

    # Find the target street to get its name
    target_feature = next(
        (f for f in streets_data["features"] if f.get("properties", {}).get("id") == street_id),
        None
    )

    if not target_feature:
        raise HTTPException(status_code=404, detail=f"Street with ID '{street_id}' not found")

    street_name = target_feature.get("properties", {}).get("name")

    # Find ALL segments that share this street name
    if street_name:
        segments = [f for f in streets_data["features"] if f.get("properties", {}).get("name") == street_name]
    else:
        segments = [target_feature]

    sanctuaries = _load_safe_sanctuaries()
    
    seen_venues = set()
    results = []
    
    for s in sanctuaries:
        lat, lng = s["lat"], s["lng"]
        # Check if this venue is close to ANY of the street segments
        for seg in segments:
            geom = seg.get("geometry", {})
            dist = min_distance_to_geometry(lat, lng, geom)
            if dist <= AMENITY_RADIUS_M:
                # Use coordinates and name as a unique identifier to prevent duplicates
                venue_id = f"{s.get('name')}_{lat}_{lng}"
                if venue_id not in seen_venues:
                    seen_venues.add(venue_id)
                    s_data = s.copy()
                    s_data["distance_m"] = round(dist, 1)
                    results.append(s_data)
                break # Already added, skip checking remaining segments for this venue

    results.sort(key=lambda x: x["distance_m"])
    return {
        "street_id": street_id, 
        "street_name": street_name or "Unknown", 
        "segments_consolidated": len(segments),
        "venues_count": len(results), 
        "venues": results
    }
