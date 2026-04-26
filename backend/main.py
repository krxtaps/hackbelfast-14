from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from sqlmodel import Session, select

from api.schemas import SafetyScoreResponse
from db.database import create_db_and_tables, get_session
from db.models import Street
from maps.loader import load_botanic_streets
from services.amenities.amenity_scoring import get_nearest_sanctuaries
from services.environment_scoring import (
    compute_all_environment_signals,
    compute_environment_signals,
)
from services.geo import consolidate_street_segments
from services.pathfinding_service import PathfindingService
from services.safety_engine import get_combined_safety_score, get_street_combined_score
from services.solana_service import submit_memo_to_solana, get_public_key
from services.news_risk.news_ingest import ingest_sources
from services.news_risk.langchain_worker import NewsLangchainWorker
from services.news_risk.news_risk import compute_news_risk

load_dotenv(Path(__file__).parent / ".env")

pathfinding_service = PathfindingService()
news_worker = NewsLangchainWorker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events."""
    create_db_and_tables()
    # Warm pathfinding graph once so first route request is fast.
    await pathfinding_service.initialize_graph()
    # First population before serving requests.
    try:
        await news_worker.run_once()
    except Exception:
        pass
    # Keep ingesting in the background.
    news_worker.start()
    yield
    await news_worker.stop()


app = FastAPI(
    title="SafeWalk Botanic API",
    description="""
    ## Hybrid Safety Scoring for Belfast (Botanic Area)

    This API provides real-time safety metrics for urban walking. It combines three primary signal layers:

    1. **Crime Safety (40%)**: Real-time data from the Police API, weighted by severity and proximity.
    2. **Physical Infrastructure (40%)**: Street lighting, surface quality, and road classification.
    3. **Sanctuary Bonus (Additive up to +30)**: Proximity to active, open safe-havens like hospitals, pharmacies, and verified businesses.

    Scores are **Time-Aware**: venues that are closed at the requested time do not contribute to the safety bonus.
    """,
    version="1.1.0",
    lifespan=lifespan,
    contact={"name": "SafeWalk Team", "url": "https://arpanpandey.dev"},
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/", tags=["General"])
def read_root():
    return {
        "status": "online",
        "area": "Botanic, Belfast",
        "engine": "SafeWalk Hybrid v1.1",
    }


@app.post("/news/ingest", tags=["News"])
async def ingest_news():
    """
    Pulls latest RSS items and updates the local news cache.
    """
    return await ingest_sources()


@app.get("/news/worker/status", tags=["News"])
def news_worker_status():
    """
    Returns status for the scheduled LangChain news worker.
    """
    return news_worker.status()


@app.post("/news/worker/run-once", tags=["News"])
async def news_worker_run_once():
    """
    Triggers one immediate worker cycle.
    """
    return await news_worker.run_once()


@app.get("/news/risk", tags=["News"])
def get_news_risk(
    lookback_hours: int = Query(72, ge=1, le=720),
    lat: float | None = None,
    lng: float | None = None,
    street_id: str | None = None,
):
    """
    Returns a cached local-news risk signal (0-100) with citations.
    """
    return compute_news_risk(
        lookback_hours=lookback_hours,
        lat=lat,
        lng=lng,
        street_id=street_id,
    )


# ---------------------------------------------------------------------------
# Safety Scoring Endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/score",
    tags=["Safety Engine"],
    response_model=SafetyScoreResponse,
    response_model_exclude_none=True,
)
async def get_score(
    street_id: str,
    time: Optional[str] = Query(
        None, description="Current time (HH:MM). If empty, server time is used."
    ),
):
    """
    Returns the comprehensive safety score for a specific street by its internal ID.
    """
    result = await get_street_combined_score(street_id, check_time=time)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get(
    "/score/coord",
    tags=["Safety Engine"],
    response_model=SafetyScoreResponse,
    response_model_exclude_none=True,
)
async def get_score_by_coord(
    lat: float,
    lng: float,
    time: Optional[str] = Query(None, description="Current time (HH:MM)."),
):
    """
    Hybrid scoring for any coordinate.
    Snaps to the nearest street for environment data but uses exact location for crime/amenities.
    """
    return await get_combined_safety_score(lat, lng, check_time=time)


# ---------------------------------------------------------------------------
# Sanctuary & Amenity Endpoints
# ---------------------------------------------------------------------------


@app.get("/sanctuaries/nearest", tags=["Sanctuaries"])
def get_nearby_sanctuaries(
    lat: float,
    lng: float,
    limit: int = Query(5, description="Max results"),
    time: Optional[str] = Query(
        None, description="HH:MM. Filters for open venues only."
    ),
):
    """
    Finds the closest Safe Sanctuaries (Foursquare POIs) from a coordinate.
    """
    return get_nearest_sanctuaries(lat, lng, limit=limit, check_time=time or "")


@app.get("/sanctuaries", tags=["Sanctuaries"])
def list_sanctuaries(limit: int = Query(200, ge=1, le=1000)):
    """
    Returns active sanctuary points for selection and routing.
    """
    from services.amenities.amenity_scoring import _load_safe_sanctuaries

    sanctuaries = _load_safe_sanctuaries()
    return sanctuaries[:limit]


# ---------------------------------------------------------------------------
# Navigation & Search Endpoints
# ---------------------------------------------------------------------------


@app.get("/streets/search", tags=["Navigation"])
def search_streets(q: str, session: Session = Depends(get_session)):
    """Search for streets by name within the Botanic area."""
    streets = session.exec(select(Street)).all()
    results = [
        street
        for street in streets
        if street.name is not None and q.lower() in street.name.lower()
    ]
    if not results:
        raise HTTPException(status_code=404, detail="No matching streets found")
    return results


@app.get("/streets/botanic", tags=["Navigation"])
def get_botanic_streets():
    """Returns the full GeoJSON street network for the Botanic area."""
    data = load_botanic_streets()
    if not data:
        raise HTTPException(status_code=404, detail="Botanic streets data not found")
    return data


@app.get("/path/safest", tags=["Navigation"])
async def get_safest_path(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
    max_snap_distance_m: float = Query(50.0, ge=10.0, le=2000.0),
):
    """
    Returns a safety-optimized route between two coordinates.
    """
    result = await pathfinding_service.find_safest_path(
        start_lat=start_lat,
        start_lng=start_lng,
        end_lat=end_lat,
        end_lng=end_lng,
        max_snap_distance_m=max_snap_distance_m,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result)
    return result


@app.get("/path/safest/sanctuaries", tags=["Navigation"])
async def get_safest_path_between_sanctuaries(
    start_sanctuary_id: str,
    end_sanctuary_id: str,
    max_snap_distance_m: float = Query(50.0, ge=10.0, le=2000.0),
):
    """
    Returns a safety-optimized route between two sanctuary IDs.
    """
    from services.amenities.amenity_scoring import _load_safe_sanctuaries

    sanctuaries = _load_safe_sanctuaries()
    start = next((s for s in sanctuaries if s.get("sanctuary_id") == start_sanctuary_id), None)
    end = next((s for s in sanctuaries if s.get("sanctuary_id") == end_sanctuary_id), None)

    if not start:
        raise HTTPException(status_code=404, detail=f"Start sanctuary '{start_sanctuary_id}' not found")
    if not end:
        raise HTTPException(status_code=404, detail=f"End sanctuary '{end_sanctuary_id}' not found")

    result = await pathfinding_service.find_safest_path(
        start_lat=float(start["lat"]),
        start_lng=float(start["lng"]),
        end_lat=float(end["lat"]),
        end_lng=float(end["lng"]),
        max_snap_distance_m=max_snap_distance_m,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result)

    result["start_sanctuary"] = {
        "sanctuary_id": start.get("sanctuary_id"),
        "name": start.get("name"),
        "type": start.get("type"),
        "lat": start.get("lat"),
        "lng": start.get("lng"),
    }
    result["end_sanctuary"] = {
        "sanctuary_id": end.get("sanctuary_id"),
        "name": end.get("name"),
        "type": end.get("type"),
        "lat": end.get("lat"),
        "lng": end.get("lng"),
    }
    return result


# ---------------------------------------------------------------------------
# Solana-backed Anonymous Incident Reporting
# ---------------------------------------------------------------------------


@app.post("/incident/submit", tags=["Solana"])
async def submit_incident(payload: dict):
    """
    Receives an incident report from the frontend, hashes it, and submits
    a Solana memo transaction (devnet) signed by the backend wallet.

    The frontend user never needs SOL; the backend pays the tx fee.
    """
    hash_val = payload.get("hash", "")
    data = payload.get("payload", {})

    if not hash_val:
        raise HTTPException(status_code=400, detail="Missing 'hash' field")

    memo = f"belfast-safe:{hash_val}"

    try:
        result = submit_memo_to_solana(memo)
        return {
            "signature": result["signature"],
            "explorer_url": result["explorer_url"],
            "memo": memo,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solana submission failed: {e}")


@app.get("/wallet/address", tags=["Solana"])
def get_backend_wallet_address():
    """
    Returns the backend's Solana public key so the hackathon judges
    can verify on-chain activity.
    """
    return {
        "public_key": get_public_key(),
        "network": "devnet",
        "explorer_url": f"https://explorer.solana.com/address/{get_public_key()}?cluster=devnet",
    }



@app.get("/streets/botanic/environment", tags=["Infrastructure"])
def get_botanic_environment():
    """Returns pre-calculated environment signals for every street."""
    return compute_all_environment_signals()


@app.get("/streets/botanic/environment/{street_id}", tags=["Infrastructure"])
def get_street_environment(street_id: str):
    """Returns detailed infrastructure signals for a single street."""
    features = load_botanic_streets()
    if not features:
        raise HTTPException(status_code=404, detail="Botanic seed data not found")

    feature_list = features.get("features", []) if isinstance(features, dict) else []
    match = next(
        (f for f in feature_list if f.get("properties", {}).get("id") == street_id),
        None,
    )

    if match is None:
        raise HTTPException(status_code=404, detail=f"Street '{street_id}' not found")
    return compute_environment_signals(match)


@app.get("/streets/{street_id}/venues", tags=["Sanctuaries"])
async def get_street_venues(
    street_id: str,
    include_segments: bool = Query(
        False, description="Include per-segment scores and geometries (may be slower)"
    ),
):
    """
    Returns all venues physically located on or immediately adjacent to the ENTIRE street.
    - Consolidates all segments that share the same street name (like the Streamlit dashboard).
    - Returns merged geometry (MultiLineString) and, optionally, per-segment scores and geometries.
    """
    from maps.loader import load_botanic_streets
    from services.amenities.amenity_scoring import (
        AMENITY_RADIUS_M,
        _load_safe_sanctuaries,
    )
    from services.geo import min_distance_to_geometry
    from services.safety_engine import get_street_combined_score

    streets_data = load_botanic_streets()
    if not streets_data or "features" not in streets_data:
        raise HTTPException(status_code=404, detail="Street data not available")

    # Find the target street to get its name and segment
    target_feature = next(
        (
            f
            for f in streets_data["features"]
            if f.get("properties", {}).get("id") == street_id
        ),
        None,
    )
    if not target_feature:
        raise HTTPException(
            status_code=404, detail=f"Street with ID '{street_id}' not found"
        )

    # Consolidate all segments sharing the same street name
    segments, street_name, merged_geometry = consolidate_street_segments(
        target_feature, streets_data
    )

    sanctuaries = _load_safe_sanctuaries()

    # Consolidate venues that are close to any segment of the street (deduplicate by name+coords)
    seen_venues = set()
    venues = []
    for venue in sanctuaries:
        vlat, vlng = venue["lat"], venue["lng"]
        for seg in segments:
            geom = seg.get("geometry", {})
            dist = min_distance_to_geometry(vlat, vlng, geom)
            if dist <= AMENITY_RADIUS_M:
                vid = f"{venue.get('name')}_{vlat}_{vlng}"
                if vid not in seen_venues:
                    seen_venues.add(vid)
                    item = venue.copy()
                    item["distance_m"] = round(dist, 1)
                    venues.append(item)
                break

    # Sort venues by closest distance to the nearest segment
    venues.sort(key=lambda x: x.get("distance_m", 99999))

    # Optionally compute per-segment scores (async calls)
    per_segment = []
    if include_segments:
        # For speed, compute each segment score (async)
        for seg in segments:
            seg_id = seg.get("properties", {}).get("id")
            if not seg_id:
                continue
            try:
                seg_res = await get_street_combined_score(seg_id)
                per_segment.append(
                    {
                        "id": seg_id,
                        "name": seg.get("properties", {}).get("name"),
                        "score": seg_res.get("score"),
                        "geometry": seg.get("geometry"),
                    }
                )
            except Exception:
                # Don't fail the whole request just because one segment score failed
                per_segment.append(
                    {
                        "id": seg_id,
                        "name": seg.get("properties", {}).get("name"),
                        "score": None,
                        "geometry": seg.get("geometry"),
                    }
                )

    return {
        "street_id": street_id,
        "street_name": street_name or "Unknown",
        "segments_consolidated": len(segments),
        "venues_count": len(venues),
        "venues": venues,
        "merged_geometry": merged_geometry,
        "per_segment": per_segment if include_segments else None,
    }
