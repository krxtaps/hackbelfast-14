import json
from pathlib import Path

def load_botanic_streets():
    """
    Loads the cleaned seed data for Botanic streets.
    Returns a dict (FeatureCollection) or None if the file doesn't exist.
    """
    seed_path = Path(__file__).parent / "seed" / "botanic-streets.seed.geojson"
    if not seed_path.exists():
        return None
    with open(seed_path, "r", encoding="utf-8") as f:
        return json.load(f)
