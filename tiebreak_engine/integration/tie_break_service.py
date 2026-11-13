"""
=============================================================================
MODULE: tie_break_service.py
PURPOSE: Integration Facade Service for backend/app/domain/patterns/TieBreak.
=============================================================================
Provides a unified, async entry point that accepts Pydantic DTOs, executes
the core Ordered Median algorithm, and returns structured API responses.
"""

from typing import List, Optional
from tiebreak_engine.core.router import RouterClient, Coordinate
from tiebreak_engine.core.itinerary_solver import (
    ItinerarySolver,
    Participant,
    PlaceCandidate,
    Slot,
    SolverSolution,
)
from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    TieBreakResponse,
    CandidatePlace,
    ParticipantBreakdown,
    CombinationSummary,
)


class TieBreakService:
    """
    Facade service designed to be plugged directly into the FastAPI backend
    at `backend/app/domain/patterns/TieBreak/` or called from application routers.
    """

    def __init__(self, router: Optional[RouterClient] = None):
        self.router = router or RouterClient()
        self.solver = ItinerarySolver(self.router)

    async def resolve(self, request: TieBreakRequest) -> TieBreakResponse:
        """
        Asynchronously resolves candidate place ties across an itinerary.

        Args:
            request (TieBreakRequest): Input data containing participant homes,
                                       itinerary slots, and tuning parameters.

        Returns:
            TieBreakResponse: Selected optimal places and mathematical breakdown.
        """
        # Configure routing mode (OSRM vs offline Haversine detour)
        self.router.enable_osrm = request.enable_osrm

        # 1. Transform Pydantic Participants -> Core Domain Entities
        domain_participants: List[Participant] = [
            Participant(
                id=p.id,
                name=p.name,
                coord=Coordinate(lat=p.lat, lng=p.lng),
            )
            for p in request.participants
        ]

        # 2. Transform Pydantic Slots & Candidates -> Core Domain Entities
        domain_slots: List[Slot] = []
        for slot_dto in request.slots:
            candidates: List[PlaceCandidate] = [
                PlaceCandidate(
                    id=c.id,
                    name=c.name,
                    coord=Coordinate(lat=c.lat, lng=c.lng),
                    slot_id=slot_dto.slot_id,
                    slot_name=slot_dto.slot_name,
                    metadata=c.metadata or {},
                )
                for c in slot_dto.candidates
            ]
            domain_slots.append(
                Slot(id=slot_dto.slot_id, name=slot_dto.slot_name, candidates=candidates)
            )

        # 3. Solve the optimization problem
        solution: SolverSolution = await self.solver.solve(
            participants=domain_participants,
            slots=domain_slots,
            penalty_exponent=request.penalty_exponent,
            fairness_factor=request.fairness_factor,
        )

        # 4. Construct Response DTOs
        selected_places: List[CandidatePlace] = [
            CandidatePlace(
                id=c.id,
                name=c.name,
                lat=c.coord.lat,
                lng=c.coord.lng,
                slot_id=c.slot_id,
                metadata=c.metadata,
            )
            for c in solution.best_combination.candidates
        ]

        participant_breakdowns: List[ParticipantBreakdown] = [
            ParticipantBreakdown(
                participant_id=pe.participant_id,
                name=pe.participant_name,
                total_distance_km=pe.total_distance_km,
                penalized_cost=pe.penalized_cost,
                rank=pe.sorted_rank,
                rank_weight=pe.rank_weight,
                weighted_score=pe.weighted_contribution,
            )
            for pe in solution.best_combination.participant_evaluations
        ]

        evaluated_summaries: List[CombinationSummary] = [
            CombinationSummary(
                places=[
                    CandidatePlace(
                        id=cand.id,
                        name=cand.name,
                        lat=cand.coord.lat,
                        lng=cand.coord.lng,
                        slot_id=cand.slot_id,
                        metadata=cand.metadata,
                    )
                    for cand in combo.candidates
                ],
                total_penalty_score=combo.total_penalty_score,
                average_distance_km=combo.average_distance_km,
                max_distance_km=combo.max_distance_km,
                min_distance_km=combo.min_distance_km,
            )
            for combo in solution.all_evaluated_combinations
        ]

        return TieBreakResponse(
            success=True,
            selected_combination=selected_places,
            total_penalty_score=solution.best_combination.total_penalty_score,
            participant_breakdowns=participant_breakdowns,
            evaluated_combinations=evaluated_summaries,
            execution_time_ms=solution.execution_time_ms,
            fallback_used=solution.fallback_used,
            applied_parameters={
                "penalty_exponent": solution.penalty_exponent,
                "fairness_factor": solution.fairness_factor,
            },
            message=(
                "Tie-break resolved successfully via OSRM network routing."
                if not solution.fallback_used
                else "Tie-break resolved using resilient Haversine (1.35x detour) fallback."
            ),
        )
