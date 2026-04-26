from typing import Optional
from sqlmodel import Field, SQLModel

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
