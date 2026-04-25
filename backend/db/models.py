from typing import Optional
from sqlmodel import Field, SQLModel

class Street(SQLModel, table=True):
    id: str = Field(primary_key=True, description="The internal stable ID (botanic_...)")
    name: Optional[str] = Field(default=None, index=True, description="The street name")
    highway: str = Field(description="The OSM highway type")
    centroid_lat: float = Field(description="Computed centroid latitude")
    centroid_lng: float = Field(description="Computed centroid longitude")
