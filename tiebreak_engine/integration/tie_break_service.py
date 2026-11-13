"""
=============================================================================
MODULE: tie_break_service.py
MỤC ĐÍCH: Service Giao Tiếp (Facade) Cho backend/app/domain/patterns/TieBreak.
=============================================================================
Cung cấp cổng giao tiếp bất đồng bộ (async), nhận Pydantic DTOs, thực thi
thuật toán Ordered Median cốt lõi và trả về phản hồi chuẩn hóa kèm hình học đường đi.
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
    Service facade được thiết kế để cắm trực tiếp vào backend FastAPI của nhóm
    tại `backend/app/domain/patterns/TieBreak/` hoặc gọi từ routers.
    """

    def __init__(self, router: Optional[RouterClient] = None):
        self.router = router or RouterClient()
        self.solver = ItinerarySolver(self.router)

    async def resolve(self, request: TieBreakRequest) -> TieBreakResponse:
        """
        Bất đồng bộ xử lý phân giải hòa vote các quán ăn/địa điểm hẹn.
        """
        self.router.enable_osrm = request.enable_osrm

        # 1. Chuyển đổi DTO Thành viên -> Thực thể Domain cốt lõi
        domain_participants: List[Participant] = [
            Participant(
                id=p.id,
                name=p.name,
                coord=Coordinate(lat=p.lat, lng=p.lng),
            )
            for p in request.participants
        ]

        # 2. Chuyển đổi DTO Chặng & Quán ứng viên -> Thực thể Domain
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

        # 3. Chạy thuật toán giải bài toán tối ưu
        solution: SolverSolution = await self.solver.solve(
            participants=domain_participants,
            slots=domain_slots,
            penalty_exponent=request.penalty_exponent,
            fairness_factor=request.fairness_factor,
        )

        # 4. Đóng gói DTOs phản hồi trả về
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
                outbound_geometry=pe.outbound_geometry,
                inbound_geometry=pe.inbound_geometry,
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
            shared_itinerary_geometry=solution.best_combination.shared_itinerary_geometry,
            execution_time_ms=solution.execution_time_ms,
            fallback_used=solution.fallback_used,
            applied_parameters={
                "penalty_exponent": solution.penalty_exponent,
                "fairness_factor": solution.fairness_factor,
            },
            message=(
                "Phân giải hòa vote thành công qua mạng lưới đường phố OSRM thực tế."
                if not solution.fallback_used
                else "Phân giải hòa vote thành công qua cơ chế dự phòng Haversine (1.35x)."
            ),
        )
