import re

with open("main.py", "r") as f:
    content = f.read()

# Fix the Description in FastAPI init
new_desc = """\"\"\"
    ## Hybrid Safety Scoring for Belfast (Botanic Area)

    This API provides real-time safety metrics for urban walking. It combines three primary signal layers:

    1. **Crime Safety (40%)**: Real-time data from the Police API, weighted by severity and proximity.
    2. **Physical Infrastructure (40%)**: Street lighting, surface quality, and road classification.
    3. **Sanctuary Bonus (Additive up to +30)**: Proximity to active, open safe-havens like hospitals, pharmacies, and verified businesses.

    Scores are **Time-Aware**: venues that are closed at the requested time do not contribute to the safety bonus.
    \"\"\""""
content = re.sub(r'description="""\n    ## Hybrid Safety.*?    """', new_desc, content, flags=re.DOTALL)


# Add Pydantic Models for the docs
models = """
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

"""

# Insert models right after imports
import_end = content.find("from db.database")
content = content[:import_end] + models + content[import_end:]

# Update the endpoints
content = content.replace(
    '@app.get("/score", tags=["Safety Engine"])',
    '@app.get("/score", tags=["Safety Engine"], response_model=SafetyScoreResponse, response_model_exclude_none=True)'
)
content = content.replace(
    '@app.get("/score/coord", tags=["Safety Engine"])',
    '@app.get("/score/coord", tags=["Safety Engine"], response_model=SafetyScoreResponse, response_model_exclude_none=True)'
)

with open("main.py", "w") as f:
    f.write(content)

print("Updated main.py")
