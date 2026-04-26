from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LocationGeometry(BaseModel):
    type: str = Field(
        ...,
        description="GeoJSON type, e.g. LineString or MultiLineString",
    )
    coordinates: list = Field(
        ...,
        description="GeoJSON coordinates array. Use this to draw the street on a map.",
    )


class LocationInfo(BaseModel):
    lat: float = Field(..., description="Center latitude")
    lng: float = Field(..., description="Center longitude")
    geometry: Optional[LocationGeometry] = Field(
        None, description="The physical GeoJSON shape of the street"
    )


class BreakdownComponent(BaseModel):
    score: float
    weight: float
    relative_to_avg: Optional[float] = None
    street: Optional[str] = None
    nearby_streets_count: Optional[int] = None


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
    type: str = Field(
        ...,
        description="Category (e.g., pharmacy, convenience, night_club)",
    )
    distance_m: float = Field(
        ..., description="Distance in meters from the street/user"
    )
    bonus: float = Field(..., description="Safety bonus applied")
    hours: str = Field(
        ...,
        description="The estimated hours category (e.g., late_night_likely)",
    )
    raw_hours: Optional[str] = Field(None, description="Actual HH:MM-HH:MM if known")
    trust: float
    lat: float = Field(
        ...,
        description="Latitude of the safe sanctuary. Use to plot green circles on map.",
    )
    lng: float = Field(..., description="Longitude of the safe sanctuary.")


class SanctuaryDetails(BaseModel):
    count: int
    bonus: float
    items: List[SanctuaryItem]
    reasons: List[str]
    check_time: str


class SafetyScoreResponse(BaseModel):
    street_id: Optional[str] = Field(None, description="Internal Botanics ID")
    street_name: Optional[str] = Field(None, description="Human readable street name")
    location: LocationInfo
    score: int = Field(..., description="Final combined safety score (0-100)")
    breakdown: ScoreBreakdown = Field(
        ..., description="Detailed mathematical breakdown of weights"
    )
    explanations: List[str] = Field(
        ..., description="User-friendly text explaining the score factors"
    )
    environment: Dict[str, Any]
    sanctuaries: SanctuaryDetails = Field(
        ..., description="List of currently OPEN safe sanctuaries nearby"
    )
    amenities: Dict[str, Any]
    raw_data: Optional[Dict[str, Any]] = None
