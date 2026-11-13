"""
=============================================================================
MODULE: schemas.py
PURPOSE: Pydantic Data Transfer Objects (DTOs) for FastAPI Integration.
=============================================================================
Defines strongly-typed request and response contracts for the TieBreakService,
aligning seamlessly with `backend/app/domain/patterns/TieBreak`.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ParticipantLocation(BaseModel):
    id: str = Field(..., description="Unique user or participant identifier")
    name: str = Field(..., description="Display name of the participant")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude of participant's home")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude of participant's home")


class CandidatePlace(BaseModel):
    id: str = Field(..., description="Unique candidate place identifier")
    name: str = Field(..., description="Name of the place / venue")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude of the place")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude of the place")
    slot_id: Optional[str] = Field(None, description="Identifier of the associated itinerary slot")
    votes: Optional[int] = Field(None, description="Number of upvotes received (tied)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional venue attributes")


class ItinerarySlot(BaseModel):
    slot_id: str = Field(..., description="Identifier for the time slot (e.g. slot_lunch)")
    slot_name: str = Field(..., description="Human-readable title (e.g. Lunch 12:00 PM)")
    candidates: List[CandidatePlace] = Field(..., min_length=1, description="List of tied candidate venues")


class TieBreakRequest(BaseModel):
    participants: List[ParticipantLocation] = Field(
        ..., min_length=1, description="List of participant home locations"
    )
    slots: List[ItinerarySlot] = Field(
        ..., min_length=1, description="Chronological sequence of tied itinerary slots"
    )
    penalty_exponent: float = Field(
        1.0, ge=1.0, le=5.0, description="Tier 1 distance penalty exponent (k >= 1.0)"
    )
    fairness_factor: float = Field(
        0.5, ge=0.0, le=5.0, description="Tier 2 Ordered Median fairness tuning (lambda >= 0.0)"
    )
    enable_osrm: bool = Field(
        True, description="Whether to query live OSRM routing before fallback"
    )


class ParticipantBreakdown(BaseModel):
    participant_id: str
    name: str
    total_distance_km: float
    penalized_cost: float
    rank: int
    rank_weight: float
    weighted_score: float


class CombinationSummary(BaseModel):
    places: List[CandidatePlace]
    total_penalty_score: float
    average_distance_km: float
    max_distance_km: float
    min_distance_km: float


class TieBreakResponse(BaseModel):
    success: bool = True
    selected_combination: List[CandidatePlace]
    total_penalty_score: float
    participant_breakdowns: List[ParticipantBreakdown]
    evaluated_combinations: List[CombinationSummary]
    execution_time_ms: float
    fallback_used: bool
    applied_parameters: Dict[str, float]
    message: str = "Tie-break resolution computed successfully."
