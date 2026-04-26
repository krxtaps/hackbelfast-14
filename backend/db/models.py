from typing import Optional
from sqlmodel import Field, SQLModel


class NewsIncident(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True, description="Publisher/source name")
    url: str = Field(index=True, unique=True, description="Canonical URL for dedupe")
    title: str
    published_at: Optional[str] = Field(default=None, description="ISO timestamp if available")

    # Extracted fields (LLM-assisted), best-effort.
    location_text: Optional[str] = Field(default=None, index=True)
    street_name: Optional[str] = Field(default=None, index=True)
    street_id: Optional[str] = Field(default=None, index=True)
    lat: Optional[float] = Field(default=None)
    lng: Optional[float] = Field(default=None)
    category: Optional[str] = Field(default=None, index=True)
    severity: Optional[int] = Field(default=None, description="1-5")

    # Cached, short LLM summary for UI.
    summary: Optional[str] = Field(default=None)

class Street(SQLModel, table=True):
    __table_args__ = {'extend_existing': True}
    
    id: str = Field(primary_key=True, description="The internal stable ID (botanic_...)")
    name: Optional[str] = Field(default=None, index=True, description="The street name")
    highway: str = Field(description="The OSM highway type")
    centroid_lat: float = Field(description="Computed centroid latitude")
    centroid_lng: float = Field(description="Computed centroid longitude")

class Venue(SQLModel, table=True):
    __table_args__ = {'extend_existing': True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, unique=True, description="Foursquare external ID")
    name: str = Field(index=True)
    category: str = Field(index=True)
    lat: float
    lng: float
    opening_hours: Optional[str] = Field(default=None)
    hours_status: Optional[str] = Field(default="hours_unknown")
    opening_hours_source: Optional[str] = Field(default="unknown")

    trust_score: float = Field(default=1.0, description="Trustworthiness score (0.0 to 1.0)")
    verification_count: int = Field(default=0, description="Number of user verifications")
    is_active: bool = Field(default=True)
