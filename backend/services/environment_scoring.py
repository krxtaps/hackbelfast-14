"""
environment_scoring.py
======================
Computes static environment signals for each Botanic street feature using
Open Data NI datasets:

  - Street Lighting Faults  (datasets/LightingFaultsCurrentYear.csv)
  - Street Lighting Assets  (datasets/Street Lighting Assets.csv)
  - Highway Network         (datasets/HighwayNetwork.geojson  — wired, not yet present)

Lighting Assets have OSGB36 Easting/Northing coordinates which we convert to
WGS84 (lat/lng) for proximity comparisons.  We use a pure-Python Helmert
approximation that is accurate to ~5 m — good enough for 100 m radius checks.

Lighting Faults have no coordinates; we match them to the street by a simple
case-insensitive substring check on the SECTION_NAME field versus the street
name in the seed GeoJSON.

All heavy CSV work uses polars.  Geometry is done with plain Python math.
No ML, no PyTorch, no databases.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl

from services.geo import calculate_centroid, haversine_m

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BASE = Path(__file__).parent.parent
_DATASETS = _BASE / "datasets"
_MAPS = _BASE / "maps"

LIGHTING_FAULTS_CSV = _DATASETS / "LightingFaultsCurrentYear.csv"
LIGHTING_ASSETS_CSV = _DATASETS / "Street Lighting Assets.csv"
HIGHWAY_NETWORK_CSV = _DATASETS / "HIGHWAY_NETWORK.CSV"
BOTANIC_SEED = _MAPS / "seed" / "botanic-streets.seed.geojson"

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Radius in metres around a street centroid to count nearby assets/faults
ASSET_RADIUS_M = 100.0
FAULT_RADIUS_M = 100.0

# Baseline adjustment contributions
ASSET_BONUS_PER_LAMP = 0.5       # each nearby lamp adds up to this
ASSET_BONUS_CAP = 5.0            # cap on asset bonus
FAULT_PENALTY_PER_FAULT = 2.0   # each open fault subtracts this
FAULT_PENALTY_CAP = 10.0         # cap on fault penalty
ENVIRONMENT_BASE_SCORE = 80.0    # starting point for environment score out of 100

# Highway class bonuses (OSM highway tag → score adjustment)
HIGHWAY_BONUSES: dict[str, float] = {
    "primary": 3.0,
    "secondary": 2.0,
    "tertiary": 1.5,
    "residential": 1.0,
    "service": 0.5,
    "footway": 0.0,
    "cycleway": 0.0,
    "path": -0.5,
    "unclassified": 0.0,
}

# ---------------------------------------------------------------------------
# Irish Grid (TM65 / Airy Modified) → WGS84 conversion
# ---------------------------------------------------------------------------
# The Open Data NI Street Lighting datasets use Irish Grid coordinates
# (Easting / Northing on the TM65 datum, Airy Modified ellipsoid).
# We convert via:
#   1. Reverse the TM65 transverse-Mercator projection → geodetic on Airy Modified
#   2. Airy Modified → ECEF Cartesian
#   3. 3-parameter Helmert shift (OSNI recommended values for Ireland)
#   4. ECEF → WGS84 geodetic
# Accuracy: ~1–5 m over Northern Ireland — adequate for 100 m radius proximity.

def _ig_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """
    Convert Irish Grid (TM65) Easting/Northing to WGS84 lat/lng.
    Returns (lat_deg, lng_deg).
    """
    # --- Step 1: Reverse TM65 projection → lat/lng on Airy Modified ellipsoid ---
    a   = 6_377_340.189   # Airy Modified semi-major axis (m)
    b   = 6_356_034.448   # Airy Modified semi-minor axis (m)
    e2  = 1.0 - (b / a) ** 2
    F0  = 1.000035         # TM65 scale factor
    lat0 = math.radians(53.5)   # true origin latitude
    lng0 = math.radians(-8.0)   # true origin longitude (8°W)
    N0  = 250_000.0        # northing of true origin (m)
    E0  = 200_000.0        # easting  of true origin (m)

    nn  = (a - b) / (a + b)
    nn2, nn3 = nn ** 2, nn ** 3

    lat = lat0
    for _ in range(25):   # Newton iteration
        M = b * F0 * (
            (1 + nn + 5/4*nn2 + 5/4*nn3) * (lat - lat0)
            - (3*nn + 3*nn2 + 21/8*nn3)  * math.sin(lat - lat0) * math.cos(lat + lat0)
            + (15/8*nn2 + 15/8*nn3)      * math.sin(2*(lat - lat0)) * math.cos(2*(lat + lat0))
            - (35/24*nn3)                * math.sin(3*(lat - lat0)) * math.cos(3*(lat + lat0))
        )
        lat = lat + (northing - N0 - M) / (a * F0)

    sin_l, cos_l, tan_l = math.sin(lat), math.cos(lat), math.tan(lat)
    nu   = a * F0 / math.sqrt(1 - e2 * sin_l ** 2)
    rho  = a * F0 * (1 - e2) / (1 - e2 * sin_l ** 2) ** 1.5
    eta2 = nu / rho - 1
    dE   = easting - E0

    lat_airy = (
        lat
        - (tan_l / (2 * rho * nu)) * dE**2
        + (tan_l / (24 * rho * nu**3) * (5 + 3*tan_l**2 + eta2 - 9*tan_l**2*eta2)) * dE**4
        - (tan_l / (720 * rho * nu**5) * (61 + 90*tan_l**2 + 45*tan_l**4)) * dE**6
    )
    lng_airy = (
        lng0
        + (1 / (cos_l * nu)) * dE
        - (1 / (6  * cos_l * nu**3) * (nu/rho + 2*tan_l**2)) * dE**3
        + (1 / (120 * cos_l * nu**5) * (5 + 28*tan_l**2 + 24*tan_l**4)) * dE**5
        - (1 / (5040 * cos_l * nu**7) * (61 + 662*tan_l**2 + 1320*tan_l**4 + 720*tan_l**6)) * dE**7
    )

    # --- Step 2: Airy Modified geodetic → ECEF Cartesian ---
    nu2  = a / math.sqrt(1 - e2 * math.sin(lat_airy)**2)
    X    = nu2 * math.cos(lat_airy) * math.cos(lng_airy)
    Y    = nu2 * math.cos(lat_airy) * math.sin(lng_airy)
    Z    = nu2 * (1 - e2) * math.sin(lat_airy)

    # --- Step 3: Helmert 3-parameter shift (TM65 → WGS84, OSNI values) ---
    X2 = X + 482.530
    Y2 = Y - 130.596
    Z2 = Z + 564.557

    # --- Step 4: ECEF → WGS84 geodetic (Bowring / iterative) ---
    a2   = 6_378_137.0
    b2   = 6_356_752.3142
    e2_2 = 1 - (b2 / a2) ** 2
    p    = math.sqrt(X2**2 + Y2**2)
    # Bowring's formula (fast convergence)
    theta = math.atan2(Z2 * a2, p * b2)
    lat_w = math.atan2(
        Z2 + (e2_2 * b2**2 / a2) * math.sin(theta) ** 3,
        p  -  e2_2 * a2           * math.cos(theta) ** 3,
    )
    lng_w = math.atan2(Y2, X2)

    return math.degrees(lat_w), math.degrees(lng_w)


# Keep old name as alias so call sites don't need updating
_osgb36_to_wgs84 = _ig_to_wgs84


# ---------------------------------------------------------------------------
# Dataset loaders (cached so each file is read only once per process)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_lighting_faults() -> pl.DataFrame | None:
    """
    Load street lighting faults CSV.
    Returns a polars DataFrame with columns: section_name, fault_type, status.
    Returns None if file is missing.
    """
    if not LIGHTING_FAULTS_CSV.exists():
        return None

    df = pl.read_csv(
        LIGHTING_FAULTS_CSV,
        infer_schema_length=500,
        has_header=True,
    )
    # Normalise column names to snake_case
    df = df.rename({c: c.strip().lower().replace(" ", "_") for c in df.columns})
    # Keep only open / pending faults for a meaningful signal
    open_statuses = {"open", "in progress", "pending", "new"}
    if "status" in df.columns:
        df = df.filter(pl.col("status").str.to_lowercase().is_in(open_statuses))
    return df


@lru_cache(maxsize=1)
def _load_lighting_assets() -> pl.DataFrame | None:
    """
    Load street lighting assets CSV (Belfast-only, pre-filtered) and convert
    Irish Grid → WGS84.  Returns a polars DataFrame with lat_wgs84 / lng_wgs84.
    Returns None if file is missing.
    """
    if not LIGHTING_ASSETS_CSV.exists():
        return None

    df = pl.read_csv(
        LIGHTING_ASSETS_CSV,
        infer_schema_length=10_000,
        has_header=True,
        schema_overrides={"MOUNT_HEIGHT": pl.Float64},
        ignore_errors=True,
    )
    df = df.rename({c: c.strip().lower().replace(" ", "_") for c in df.columns})

    # Cast coordinates; drop rows with null/invalid values
    df = df.with_columns([
        pl.col("easting").cast(pl.Float64, strict=False),
        pl.col("northing").cast(pl.Float64, strict=False),
    ]).drop_nulls(subset=["easting", "northing"])

    # Convert Irish Grid → WGS84 for all rows in the (already Belfast-only) file
    eastings  = df["easting"].to_list()
    northings = df["northing"].to_list()
    lats, lngs = [], []
    for e, n in zip(eastings, northings):
        la, lo = _ig_to_wgs84(e, n)
        lats.append(la)
        lngs.append(lo)

    df = df.with_columns([
        pl.Series("lat_wgs84", lats),
        pl.Series("lng_wgs84", lngs),
    ])
    return df


@lru_cache(maxsize=1)
def _load_botanic_streets() -> list[dict[str, Any]]:
    """Load all features from the Botanic seed GeoJSON."""
    with open(BOTANIC_SEED, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


@lru_cache(maxsize=1)
def _load_highway_network() -> pl.DataFrame | None:
    """
    Load official Highway Network CSV and filter to Eastern division (Belfast).
    Returns a polars DataFrame.
    """
    if not HIGHWAY_NETWORK_CSV.exists():
        return None

    df = pl.read_csv(
        HIGHWAY_NETWORK_CSV,
        infer_schema_length=1000,
        ignore_errors=True,
    )
    # Filter to Eastern division for performance
    df = df.filter(pl.col("DIVISION_NAME") == "EASTERN")
    return df


def _match_official_class(street_name: str | None, highway_df: pl.DataFrame | None) -> str | None:
    """
    Find official class (A, B, C, U, F) for a street.
    Uses substring matching on SECTION_NAME.
    """
    if highway_df is None or not street_name:
        return None

    s_name = street_name.upper()
    # Handle common abbreviations (e.g., Avenue -> AV)
    s_name = s_name.replace(" AVENUE", " AV")
    s_name = s_name.replace(" ROAD", " RD")
    s_name = s_name.replace(" STREET", " ST")
    s_name = s_name.replace(" GARDENS", " GDS")
    s_name = s_name.replace(" TERRACE", " TER")
    s_name = s_name.replace(" PLACE", " PL")
    s_name = s_name.replace(" SQUARE", " SQ")
    s_name = s_name.replace(" CRESCENT", " CRES")

    # Filter to rows where SECTION_NAME contains the street name
    # We look for the part after the first space (id prefix)
    matches = highway_df.filter(pl.col("SECTION_NAME").str.contains(s_name))
    if matches.is_empty():
        return None

    # Return the most frequent class among matches
    counts = matches["CLASS"].value_counts().sort("count", descending=True)
    return counts["CLASS"][0]


# ---------------------------------------------------------------------------
# Per-street signal computation
# ---------------------------------------------------------------------------

# 1 degree of latitude  ≈ 111 km; 1 degree of longitude ≈ 69 km at 54°N
_LAT_DEG_PER_M  = 1.0 / 111_000
_LNG_DEG_PER_M  = 1.0 / 69_000   # approx at Belfast latitude


def _count_nearby_assets(lat: float, lng: float, assets_df: pl.DataFrame, radius_m: float) -> int:
    """
    Count lighting assets within radius_m metres of (lat, lng).
    Uses a cheap degree-bbox pre-filter in polars to reduce candidates
    from ~109k to dozens before running haversine.
    """
    lat_margin = radius_m * _LAT_DEG_PER_M
    lng_margin = radius_m * _LNG_DEG_PER_M

    candidates = assets_df.filter(
        (pl.col("lat_wgs84").is_between(lat - lat_margin, lat + lat_margin)) &
        (pl.col("lng_wgs84").is_between(lng - lng_margin, lng + lng_margin))
    )
    if candidates.is_empty():
        return 0

    clats = candidates["lat_wgs84"].to_list()
    clngs = candidates["lng_wgs84"].to_list()
    return sum(
        1
        for la, lo in zip(clats, clngs)
        if haversine_m(lat, lng, la, lo) <= radius_m
    )


def _count_nearby_faults(street_name: str | None, faults_df: pl.DataFrame) -> int:
    """
    Count open lighting faults whose SECTION_NAME contains the street name.
    Falls back to 0 if street_name is None or no faults CSV was loaded.
    """
    if not street_name:
        return 0
    name_upper = street_name.upper()
    if "section_name" not in faults_df.columns:
        return 0
    matches = faults_df.filter(
        pl.col("section_name").str.to_uppercase().str.contains(name_upper)
    )
    return len(matches)


def _highway_road_class(highway_tag: str) -> str:
    """
    Map an OSM highway tag to a human-readable road class label.
    """
    mapping = {
        "primary": "A-road (primary)",
        "primary_link": "A-road (primary link)",
        "secondary": "B-road (secondary)",
        "secondary_link": "B-road (secondary link)",
        "tertiary": "C-road (tertiary)",
        "tertiary_link": "C-road (tertiary link)",
        "residential": "Residential",
        "service": "Service road",
        "footway": "Footway",
        "cycleway": "Cycleway",
        "path": "Path / track",
        "living_street": "Living street",
        "pedestrian": "Pedestrian zone",
        "unclassified": "Unclassified",
    }
    return mapping.get(highway_tag, highway_tag or "unknown")


# Road class bonus mapping (Official Class → score adjustment)
OFFICIAL_CLASS_BONUSES: dict[str, float] = {
    "A": 3.0,  # Main arterial roads
    "B": 2.0,  # Secondary routes
    "C": 1.5,  # Tertiary / collector roads
    "U": 1.0,  # Unclassified / Residential
    "F": 0.0,  # Footway
}


def _compute_baseline_adjustment(
    asset_count: int,
    fault_count: int,
    highway_tag: str,
    official_class: str | None = None,
) -> tuple[float, int, list[str]]:
    """
    Deterministic formula:
      adjustment = asset_bonus - fault_penalty + road_class_bonus
      score = base_score + adjustment
    Returns (adjustment, score, reasons).
    """
    reasons: list[str] = []

    asset_bonus = min(asset_count * ASSET_BONUS_PER_LAMP, ASSET_BONUS_CAP)
    if asset_count > 0:
        reasons.append(f"+{asset_bonus:.1f} from {asset_count} nearby street lamp(s)")

    fault_penalty = min(fault_count * FAULT_PENALTY_PER_FAULT, FAULT_PENALTY_CAP)
    if fault_count > 0:
        reasons.append(f"−{fault_penalty:.1f} from {fault_count} open lighting fault(s)")

    # Prefer official road class if available, otherwise fallback to OSM tag
    if official_class and official_class in OFFICIAL_CLASS_BONUSES:
        highway_bonus = OFFICIAL_CLASS_BONUSES[official_class]
        class_label = f"official class {official_class}"
    else:
        highway_bonus = HIGHWAY_BONUSES.get(highway_tag, 0.0)
        class_label = f"road class ({highway_tag})"

    if highway_bonus != 0.0:
        sign = "+" if highway_bonus > 0 else "−"
        reasons.append(f"{sign}{abs(highway_bonus):.1f} from {class_label}")

    adjustment = round(asset_bonus - fault_penalty + highway_bonus, 2)
    score = max(0, min(100, int(ENVIRONMENT_BASE_SCORE + adjustment)))

    if not reasons:
        reasons.append("No environment signals available for this street.")
    return adjustment, score, reasons


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_environment_signals(feature: dict[str, Any]) -> dict[str, Any]:
    """
    Given a single GeoJSON feature from the Botanic seed, compute environment
    signals and return a structured dict:

        {
            "street_id": str,
            "street_name": str | None,
            "highway": str,
            "road_class": str,
            "lighting_asset_count": int,
            "lighting_fault_count": int,
            "baseline_adjustment": float,
            "reasons": [str, ...]
        }
    """
    props = feature.get("properties", {})
    geometry = feature.get("geometry", {})

    street_id: str = props.get("id", "")
    street_name: str | None = props.get("name")
    highway_tag: str = props.get("highway", "unclassified")

    lat, lng = calculate_centroid(geometry)

    # Load datasets (cached after first call)
    assets_df = _load_lighting_assets()
    faults_df = _load_lighting_faults()
    highway_df = _load_highway_network()

    asset_count = _count_nearby_assets(lat, lng, assets_df, ASSET_RADIUS_M) if assets_df is not None else 0
    fault_count = _count_nearby_faults(street_name, faults_df) if faults_df is not None else 0
    official_class = _match_official_class(street_name, highway_df)

    road_class = _highway_road_class(highway_tag)
    if official_class:
        road_class = f"Official {official_class} (from {road_class})"

    adjustment, score, reasons = _compute_baseline_adjustment(
        asset_count, fault_count, highway_tag, official_class
    )

    return {
        "street_id": street_id,
        "street_name": street_name,
        "highway": highway_tag,
        "official_class": official_class,
        "road_class": road_class,
        "lighting_asset_count": asset_count,
        "lighting_fault_count": fault_count,
        "baseline_adjustment": adjustment,
        "score": score,
        "reasons": reasons,
    }


def compute_all_environment_signals() -> list[dict[str, Any]]:
    """
    Compute environment signals for every feature in the Botanic seed GeoJSON.
    Results are deterministic and can be cached at the call site.
    """
    features = _load_botanic_streets()
    return [compute_environment_signals(f) for f in features]
