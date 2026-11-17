"""
=============================================================================
MODULE: itinerary_solver.py
MỤC ĐÍCH: Đánh Giá Lộ Trình Tổ Hợp & Tìm Quán Chiến Thắng Tối Ưu Nhất.
=============================================================================
Đánh giá tất cả các tổ hợp ứng viên cho chuỗi chặng đi chơi có thứ tự cố định:
  Lộ trình của bạn i: Nhà_i -> Chặng 1 -> Chặng 2 -> ... -> Chặng Cuối -> Nhà_i
Tính khoảng cách di chuyển thực tế, chi phí phạt cá nhân, tổng hợp qua
Ordered Median và xác định tổ hợp chiến thắng tối ưu nhất.
"""

import itertools
import time
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from tiebreak_engine.core.router import RouterClient, Coordinate, RouteSegment
from tiebreak_engine.core.scoring_formula import (
    compute_individual_penalty,
    generate_ordered_median_weights,
)
from tiebreak_engine.core.ordered_median import compute_ordered_median, OrderedMedianResult


@dataclass
class Participant:
    id: str
    name: str
    coord: Coordinate


@dataclass
class PlaceCandidate:
    id: str
    name: str
    coord: Coordinate
    slot_id: str
    slot_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Slot:
    id: str
    name: str
    candidates: List[PlaceCandidate]


@dataclass
class ParticipantEvaluation:
    participant_id: str
    participant_name: str
    total_distance_km: float
    penalized_cost: float
    sorted_rank: int
    rank_weight: float
    weighted_contribution: float
    outbound_geometry: List[List[float]] = field(default_factory=list)
    inbound_geometry: List[List[float]] = field(default_factory=list)


@dataclass
class CombinationEvaluation:
    candidates: List[PlaceCandidate]
    total_penalty_score: float
    participant_evaluations: List[ParticipantEvaluation]
    average_distance_km: float
    max_distance_km: float
    min_distance_km: float
    shared_itinerary_geometry: List[List[float]] = field(default_factory=list)


@dataclass
class SolverSolution:
    best_combination: CombinationEvaluation
    all_evaluated_combinations: List[CombinationEvaluation]
    execution_time_ms: float
    fallback_used: bool
    penalty_exponent: float
    fairness_factor: float


class ItinerarySolver:
    """
    Giải bài toán phân giải hòa vote đa tiêu chí trên chuỗi chặng thời gian cố định.
    """

    def __init__(self, router: Optional[RouterClient] = None):
        self.router = router or RouterClient()

    async def solve(
        self,
        participants: List[Participant],
        slots: List[Slot],
        penalty_exponent: float = 1.0,
        fairness_factor: float = 0.5,
    ) -> SolverSolution:
        """
        Đánh giá các tổ hợp ứng viên và chọn ra tổ hợp có tổng điểm phạt OMP nhỏ nhất.
        """
        start_time = time.perf_counter()
        num_participants = len(participants)

        if num_participants == 0:
            raise ValueError("Yêu cầu tối thiểu phải có một thành viên tham gia.")
        if len(slots) == 0:
            raise ValueError("Yêu cầu tối thiểu phải có một chặng thời gian.")

        for slot in slots:
            if not slot.candidates:
                raise ValueError(f"Chặng '{slot.name}' (ID: {slot.id}) không có quán ứng viên nào.")

        # 1. Sinh vector trọng số thứ tự W = (w_1, ..., w_n)
        weights = generate_ordered_median_weights(num_participants, fairness_factor)

        # 2. Tạo tích Đề-các (Cartesian Product) cho tất cả các tổ hợp quán qua từng chặng
        slot_candidate_lists = [slot.candidates for slot in slots]
        all_combinations = list(itertools.product(*slot_candidate_lists))

        # Tối ưu hóa: Thu thập tất cả các cặp tọa độ độc nhất và nạp song song (prefetch)
        unique_coord_pairs = set()
        for s_i in range(len(slots) - 1):
            for c_from in slots[s_i].candidates:
                for c_to in slots[s_i + 1].candidates:
                    unique_coord_pairs.add((c_from.coord, c_to.coord))
        for first_cand in slots[0].candidates:
            for p in participants:
                unique_coord_pairs.add((p.coord, first_cand.coord))
        for last_cand in slots[-1].candidates:
            for p in participants:
                unique_coord_pairs.add((last_cand.coord, p.coord))

        if self.router.enable_osrm and unique_coord_pairs:
            uncached = [(c1, c2) for (c1, c2) in unique_coord_pairs if not self.router.get_cached_route(c1, c2)]
            if uncached:
                import asyncio
                await asyncio.gather(*[self.router.get_route(c1, c2) for c1, c2 in uncached])

        evaluated_combinations: List[CombinationEvaluation] = []
        any_fallback_triggered = False

        # 3. Đánh giá từng tổ hợp lộ trình
        for combo in all_combinations:
            combo_candidates: List[PlaceCandidate] = list(combo)

            # Tính quãng đường và gom hình học chung giữa các quán: Quán 1 -> Quán 2 -> ... -> Quán K
            shared_middle_distance = 0.0
            shared_geometry: List[List[float]] = []

            for idx in range(len(combo_candidates) - 1):
                from_c = combo_candidates[idx].coord
                to_c = combo_candidates[idx + 1].coord
                route_seg = await self.router.get_route(from_c, to_c)
                if route_seg.is_fallback:
                    any_fallback_triggered = True
                shared_middle_distance += route_seg.distance_km
                if route_seg.geometry:
                    # Nối tiếp tọa độ đường đi mà không bị lặp điểm giao
                    if shared_geometry and route_seg.geometry:
                        shared_geometry.extend(route_seg.geometry[1:])
                    else:
                        shared_geometry.extend(route_seg.geometry)

            first_spot_coord = combo_candidates[0].coord
            last_spot_coord = combo_candidates[-1].coord

            # Tính quãng đường khứ hồi và lưu tọa độ lộ trình cho từng thành viên
            individual_distances: List[float] = []
            individual_costs: List[float] = []
            participant_routes: List[Tuple[RouteSegment, RouteSegment]] = []

            for p in participants:
                # Chặng đi: Nhà -> Quán đầu tiên
                leg1_route = await self.router.get_route(p.coord, first_spot_coord)
                # Chặng về: Quán cuối cùng -> Nhà
                leg3_route = await self.router.get_route(last_spot_coord, p.coord)

                if leg1_route.is_fallback or leg3_route.is_fallback:
                    any_fallback_triggered = True

                total_dist = round(leg1_route.distance_km + shared_middle_distance + leg3_route.distance_km, 3)
                cost = compute_individual_penalty(total_dist, penalty_exponent)

                individual_distances.append(total_dist)
                individual_costs.append(cost)
                participant_routes.append((leg1_route, leg3_route))

            # 4. Áp dụng bộ tổng hợp Ordered Median Problem (OMP)
            omp_result: OrderedMedianResult = compute_ordered_median(individual_costs, weights)

            # Đóng gói chi tiết đánh giá cho từng thành viên
            participant_evals: List[ParticipantEvaluation] = []
            for rank, orig_idx in enumerate(omp_result.rank_to_original_index):
                p = participants[orig_idx]
                dist = individual_distances[orig_idx]
                cost = individual_costs[orig_idx]
                weight = weights[rank]
                weighted_val = round(cost * weight, 4)
                leg1_r, leg3_r = participant_routes[orig_idx]

                participant_evals.append(
                    ParticipantEvaluation(
                        participant_id=p.id,
                        participant_name=p.name,
                        total_distance_km=dist,
                        penalized_cost=round(cost, 4),
                        sorted_rank=rank + 1,
                        rank_weight=weight,
                        weighted_contribution=weighted_val,
                        outbound_geometry=leg1_r.geometry,
                        inbound_geometry=leg3_r.geometry,
                    )
                )

            # Sắp xếp hiển thị theo ID thành viên ban đầu
            participant_evals.sort(key=lambda item: item.participant_id)

            avg_dist = round(sum(individual_distances) / num_participants, 3)
            max_dist = max(individual_distances)
            min_dist = min(individual_distances)

            evaluation = CombinationEvaluation(
                candidates=combo_candidates,
                total_penalty_score=round(omp_result.total_penalty, 4),
                participant_evaluations=participant_evals,
                average_distance_km=avg_dist,
                max_distance_km=max_dist,
                min_distance_km=min_dist,
                shared_itinerary_geometry=shared_geometry,
            )
            evaluated_combinations.append(evaluation)

        # 5. Chọn tổ hợp có tổng điểm phạt mục tiêu nhỏ nhất
        evaluated_combinations.sort(key=lambda eval_item: eval_item.total_penalty_score)
        best_combo = evaluated_combinations[0]

        exec_time = round((time.perf_counter() - start_time) * 1000.0, 2)

        return SolverSolution(
            best_combination=best_combo,
            all_evaluated_combinations=evaluated_combinations,
            execution_time_ms=exec_time,
            fallback_used=any_fallback_triggered or (self.router.fallback_triggered_count > 0),
            penalty_exponent=penalty_exponent,
            fairness_factor=fairness_factor,
        )
