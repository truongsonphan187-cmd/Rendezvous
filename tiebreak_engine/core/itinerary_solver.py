"""
=============================================================================
MODULE: itinerary_solver.py
MỤC ĐÍCH: Đánh Giá Lộ Trình & Tìm Quán Chiến Thắng Tối Ưu Bằng Layered DP + OMP.
=============================================================================
Thuật toán:
  1. Phân rã bài toán: Với chuỗi chặng đi chơi có thứ tự cố định (S_1 -> S_2 -> ... -> S_K),
     mọi thành viên di chuyển: Nhà_i -> S_1 -> (S_2 -> ... -> S_{K-1}) -> S_K -> Nhà_i.
  2. Quy hoạch động nhiều tầng (Layered DP): Quãng đường giữa D_middle(s_1, ..., s_K)
     cộng một hằng số như nhau cho mọi thành viên. Vì hàm chi phí cá nhân c_i = d_i^k
     đơn điệu tăng (k >= 1, w_i >= 0), việc cực tiểu hóa tổng điểm OMP Psi cho mỗi cặp
     biên (s_1, s_K) tương đương tuyệt đối với việc tìm đường đi ngắn nhất qua các chặng giữa.
  3. Duyệt M_1 x M_K cặp đầu-cuối: Đánh giá trọn vẹn mô hình Ordered Median trên các
     lộ trình Pareto-optimal tìm được, bảo toàn 100% độ chính xác so với Brute-Force
     trong khi giảm độ phức tạp từ O(M^K) xuống O(M_1 * M_K * K * M^2).
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
    Bộ giải tối ưu hóa lộ trình phân giải hòa vote đa tiêu chí trên chuỗi chặng thời gian cố định.
    Sử dụng giải thuật Phân rã + Layered DP + OMP Ranking.
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
        Đánh giá các tổ hợp ứng viên bằng Layered DP và chọn ra tổ hợp tối ưu toàn cục.
        Khớp nghiệm chính xác 100% với Brute-Force trên toàn bộ không gian tham số.
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

        # 2. Tối ưu hóa nạp trước (Prefetching) song song tất cả các cặp tọa độ cần thiết
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

        if len(slots) == 1:
            # =========================================================================
            # Trường hợp 1 chặng (K = 1): Không có chặng giữa
            # =========================================================================
            for c1 in slots[0].candidates:
                combo_candidates = [c1]
                shared_middle_distance = 0.0
                shared_geometry: List[List[float]] = []

                individual_distances: List[float] = []
                individual_costs: List[float] = []
                participant_routes: List[Tuple[RouteSegment, RouteSegment]] = []

                for p in participants:
                    leg1_route = await self.router.get_route(p.coord, c1.coord)
                    leg3_route = await self.router.get_route(c1.coord, p.coord)
                    if leg1_route.is_fallback or leg3_route.is_fallback:
                        any_fallback_triggered = True

                    total_dist = round(leg1_route.distance_km + leg3_route.distance_km, 3)
                    cost = compute_individual_penalty(total_dist, penalty_exponent)

                    individual_distances.append(total_dist)
                    individual_costs.append(cost)
                    participant_routes.append((leg1_route, leg3_route))

                omp_result: OrderedMedianResult = compute_ordered_median(individual_costs, weights)

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

                participant_evals.sort(key=lambda item: item.participant_id)
                avg_dist = round(sum(individual_distances) / num_participants, 3)

                evaluation = CombinationEvaluation(
                    candidates=combo_candidates,
                    total_penalty_score=round(omp_result.total_penalty, 4),
                    participant_evaluations=participant_evals,
                    average_distance_km=avg_dist,
                    max_distance_km=max(individual_distances),
                    min_distance_km=min(individual_distances),
                    shared_itinerary_geometry=shared_geometry,
                )
                evaluated_combinations.append(evaluation)

        else:
            # =========================================================================
            # Trường hợp K >= 2: Phân Rã + Quy Hoạch Động (Layered DP)
            # =========================================================================
            for s1 in slots[0].candidates:
                # Khởi tạo tầng 1 (slots[1])
                dp_states: Dict[str, Dict[str, Any]] = {}
                for c1_next in slots[1].candidates:
                    seg = await self.router.get_route(s1.coord, c1_next.coord)
                    if seg.is_fallback:
                        any_fallback_triggered = True
                    dp_states[c1_next.id] = {
                        "dist": seg.distance_km,
                        "path": [s1, c1_next],
                        "geom": list(seg.geometry),
                    }

                # Chuyển trạng thái DP qua các tầng tiếp theo (từ tầng 2 đến tầng K-1)
                for layer_idx in range(2, len(slots)):
                    next_dp_states: Dict[str, Dict[str, Any]] = {}
                    for curr_cand in slots[layer_idx].candidates:
                        best_prev_id = None
                        best_total_dist = float("inf")
                        best_seg = None

                        for prev_id, prev_info in dp_states.items():
                            prev_cand = prev_info["path"][-1]
                            seg = await self.router.get_route(prev_cand.coord, curr_cand.coord)
                            if seg.is_fallback:
                                any_fallback_triggered = True
                            dist = prev_info["dist"] + seg.distance_km
                            if dist < best_total_dist - 1e-9:
                                best_total_dist = dist
                                best_prev_id = prev_id
                                best_seg = seg

                        prev_info = dp_states[best_prev_id]
                        merged_geom = list(prev_info["geom"])
                        if best_seg and best_seg.geometry:
                            if merged_geom:
                                merged_geom.extend(best_seg.geometry[1:])
                            else:
                                merged_geom.extend(best_seg.geometry)

                        next_dp_states[curr_cand.id] = {
                            "dist": best_total_dist,
                            "path": prev_info["path"] + [curr_cand],
                            "geom": merged_geom,
                        }
                    dp_states = next_dp_states

                # Duyệt các ứng viên ở tầng cuối cùng s_K in slots[-1]
                for sK in slots[-1].candidates:
                    target_info = dp_states[sK.id]
                    combo_candidates = target_info["path"]
                    shared_middle_distance = target_info["dist"]
                    shared_geometry = target_info["geom"]

                    individual_distances: List[float] = []
                    individual_costs: List[float] = []
                    participant_routes: List[Tuple[RouteSegment, RouteSegment]] = []

                    for p in participants:
                        leg1_route = await self.router.get_route(p.coord, s1.coord)
                        leg3_route = await self.router.get_route(sK.coord, p.coord)
                        if leg1_route.is_fallback or leg3_route.is_fallback:
                            any_fallback_triggered = True

                        total_dist = round(leg1_route.distance_km + shared_middle_distance + leg3_route.distance_km, 3)
                        cost = compute_individual_penalty(total_dist, penalty_exponent)

                        individual_distances.append(total_dist)
                        individual_costs.append(cost)
                        participant_routes.append((leg1_route, leg3_route))

                    omp_result: OrderedMedianResult = compute_ordered_median(individual_costs, weights)

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

                    participant_evals.sort(key=lambda item: item.participant_id)
                    avg_dist = round(sum(individual_distances) / num_participants, 3)

                    evaluation = CombinationEvaluation(
                        candidates=combo_candidates,
                        total_penalty_score=round(omp_result.total_penalty, 4),
                        participant_evaluations=participant_evals,
                        average_distance_km=avg_dist,
                        max_distance_km=max(individual_distances),
                        min_distance_km=min(individual_distances),
                        shared_itinerary_geometry=shared_geometry,
                    )
                    evaluated_combinations.append(evaluation)

        # 4. Sắp xếp thứ tự các phương án theo điểm phạt mục tiêu tăng dần
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

    async def solve_bruteforce(
        self,
        participants: List[Participant],
        slots: List[Slot],
        penalty_exponent: float = 1.0,
        fairness_factor: float = 0.5,
    ) -> SolverSolution:
        """
        Duyệt vét cạn (Brute-Force Cartesian Product) toàn bộ M^K tổ hợp.
        Dùng cho mục đích đối sánh kiểm thử toán học (Benchmarking & Exact Equivalence Testing).
        """
        start_time = time.perf_counter()
        num_participants = len(participants)

        weights = generate_ordered_median_weights(num_participants, fairness_factor)
        slot_candidate_lists = [slot.candidates for slot in slots]
        all_combinations = list(itertools.product(*slot_candidate_lists))

        evaluated_combinations: List[CombinationEvaluation] = []
        any_fallback_triggered = False

        for combo in all_combinations:
            combo_candidates: List[PlaceCandidate] = list(combo)
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
                    if shared_geometry:
                        shared_geometry.extend(route_seg.geometry[1:])
                    else:
                        shared_geometry.extend(route_seg.geometry)

            first_spot_coord = combo_candidates[0].coord
            last_spot_coord = combo_candidates[-1].coord

            individual_distances: List[float] = []
            individual_costs: List[float] = []
            participant_routes: List[Tuple[RouteSegment, RouteSegment]] = []

            for p in participants:
                leg1_route = await self.router.get_route(p.coord, first_spot_coord)
                leg3_route = await self.router.get_route(last_spot_coord, p.coord)
                if leg1_route.is_fallback or leg3_route.is_fallback:
                    any_fallback_triggered = True

                total_dist = round(leg1_route.distance_km + shared_middle_distance + leg3_route.distance_km, 3)
                cost = compute_individual_penalty(total_dist, penalty_exponent)

                individual_distances.append(total_dist)
                individual_costs.append(cost)
                participant_routes.append((leg1_route, leg3_route))

            omp_result: OrderedMedianResult = compute_ordered_median(individual_costs, weights)

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

            participant_evals.sort(key=lambda item: item.participant_id)
            avg_dist = round(sum(individual_distances) / num_participants, 3)

            evaluation = CombinationEvaluation(
                candidates=combo_candidates,
                total_penalty_score=round(omp_result.total_penalty, 4),
                participant_evaluations=participant_evals,
                average_distance_km=avg_dist,
                max_distance_km=max(individual_distances),
                min_distance_km=min(individual_distances),
                shared_itinerary_geometry=shared_geometry,
            )
            evaluated_combinations.append(evaluation)

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
