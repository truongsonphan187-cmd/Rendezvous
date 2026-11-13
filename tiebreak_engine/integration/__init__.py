"""
Integration module exposing schemas and service adapters.
"""
from tiebreak_engine.integration.schemas import (
    ParticipantLocation,
    CandidatePlace,
    ItinerarySlot,
    TieBreakRequest,
    TieBreakResponse,
    ParticipantBreakdown,
    CombinationSummary,
)
from tiebreak_engine.integration.tie_break_service import TieBreakService

__all__ = [
    "ParticipantLocation",
    "CandidatePlace",
    "ItinerarySlot",
    "TieBreakRequest",
    "TieBreakResponse",
    "ParticipantBreakdown",
    "CombinationSummary",
    "TieBreakService",
]
