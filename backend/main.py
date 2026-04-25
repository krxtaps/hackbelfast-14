from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from maps.loader import load_botanic_streets
from services.environment_scoring import compute_all_environment_signals, compute_environment_signals

app = FastAPI()

app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/streets/botanic")
def get_botanic_streets():
    data = load_botanic_streets()
    if not data:
        raise HTTPException(status_code=404, detail="Botanic streets data not found")
    return data

from services.safety_engine import get_combined_safety_score, get_street_combined_score
from sqlmodel import Session, select
from db.database import get_session
from db.models import Street
from fastapi import Depends

@app.get("/score")
async def get_score(street_id: str):
    """Returns combined safety score for a given street ID."""
    result = await get_street_combined_score(street_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/score/coord")
async def get_score_by_coord(lat: float, lng: float):
    """Returns combined safety score for a given coordinate (hybrid)."""
    return await get_combined_safety_score(lat, lng)

@app.get("/streets/search")
def search_streets(q: str, session: Session = Depends(get_session)):
    # Simple partial match case-insensitive search
    statement = select(Street).where(Street.name.contains(q))
    results = session.exec(statement).all()
    if not results:
        raise HTTPException(status_code=404, detail="No matching streets found")
    return results


# ---------------------------------------------------------------------------
# Environment / static dataset endpoints
# ---------------------------------------------------------------------------

@app.get("/streets/botanic/environment")
def get_botanic_environment():
    """
    Returns environment signals (lighting assets, faults, road class,
    baseline adjustment) for every Botanic street.
    """
    return compute_all_environment_signals()


@app.get("/streets/botanic/environment/{street_id}")
def get_street_environment(street_id: str):
    """
    Returns environment signals for a single street identified by its
    botanic_<hash> ID (e.g. botanic_22d4825d).
    """
    features = load_botanic_streets()
    if not features:
        raise HTTPException(status_code=404, detail="Botanic seed data not found")
    # load_botanic_streets returns a FeatureCollection dict
    feature_list = features.get("features", []) if isinstance(features, dict) else []
    match = next(
        (f for f in feature_list if f.get("properties", {}).get("id") == street_id),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail=f"Street '{street_id}' not found")
    return compute_environment_signals(match)
