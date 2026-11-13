"""
=============================================================================
MODULE: itinerary_solver.py
PURPOSE: Combinatorial Path Evaluator & Optimal Candidate Selection.
=============================================================================
Evaluates all candidate combinations across fixed chronological itinerary slots:
  Route for participant i: Home_i -> S_1 -> S_2 -> ... -> S_K -> Home_i
Computes individual distances, penalized costs, applies the Ordered Median
aggregator, and identifies the optimal tie-break winner.
"""

import itertools
import time
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from tiebreak_engine.core.router import RouterClient, Coordinate
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


@dataclass
class CombinationEvaluation:
    candidates: List[PlaceCandidate]
    total_penalty_score: float
    participant_evaluations: List[ParticipantEvaluation]
    average_distance_km: float
    max_distance_km: float
    min_distance_km: float


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
    Solves the multi-criteria tie-break problem over fixed chronological slots.
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
        Evaluates candidate combinations and selects the one with minimum OMP penalty.

        Args:
            participants: List of participants with home coordinates.
            slots: Ordered list of slots, each containing 1 or more tied candidates.
            penalty_exponent (k): Tier 1 exponent for individual distance.
            fairness_factor (lambda): Tier 2 Ordered Median fairness tuning.

        Returns:
            SolverSolution: Best combination, full breakdowns, and comparison alternatives.
        """
        start_time = time.perf_counter()
        num_participants = len(participants)

        if num_participants == 0:
            raise ValueError("At least one participant is required.")
        if len(slots) == 0:
            raise ValueError("At least one itinerary slot is required.")

        # Validate that each slot has at least one candidate
        for slot in slots:
            if not slot.candidates:
                raise ValueError(f"Slot '{slot.name}' (ID: {slot.id}) has no candidate places.")

        # 1. Generate rank weight vector W
        weights = generate_ordered_median_weights(num_participants, fairness_factor)

        # 2. Extract candidate lists for Cartesian product
        slot_candidate_lists = [slot.candidates for slot in slots]
        all_combinations = list(itertools.product(*slot_candidate_lists))

        evaluated_combinations: List[CombinationEvaluation] = []
        any_fallback_triggered = False

        # 3. Evaluate each combination
        for combo in all_combinations:
            combo_candidates: List[PlaceCandidate] = list(combo)

            # Precompute intra-itinerary distance: S_1 -> S_2 -> ... -> S_K
            shared_middle_distance = 0.0
            for idx in range(len(combo_candidates) - 1):
                from_c = combo_candidates[idx].coord
                to_c = combo_candidates[idx + 1].coord
                seg_dist, is_fallback = await self.router.get_distance_km(from_c, to_c)
                if is_fallback:
                    any_fallback_triggered = True
                shared_middle_distance += seg_dist

            first_spot_coord = combo_candidates[0].coord
            last_spot_coord = combo_candidates[-1].coord

            # Compute round-trip distance for each participant
            individual_distances: List[float] = []
            individual_costs: List[float] = []

            for p in participants:
                # Leg 1: Home -> First Spot
                leg1_dist, f1 = await self.router.get_distance_km(p.coord, first_spot_coord)
                # Leg 3: Last Spot -> Home
                leg3_dist, f3 = await self.router.get_distance_km(last_spot_coord, p.coord)
                if f1 or f3:
                    any_fallback_triggered = True

                # Total round trip: Home -> S_1 -> ... -> S_K -> Home
                total_dist = round(leg1_dist + shared_middle_distance + leg3_dist, 3)
                cost = compute_individual_penalty(total_dist, penalty_exponent)

                individual_distances.append(total_dist)
                individual_costs.append(cost)

            # 4. Apply Ordered Median Problem aggregation
            omp_result: OrderedMedianResult = compute_ordered_median(individual_costs, weights)

            # Build detailed participant evaluations
            participant_evals: List[ParticipantEvaluation] = []
            for rank, orig_idx in enumerate(omp_result.rank_to_original_index):
                p = participants[orig_idx]
                dist = individual_distances[orig_idx]
                cost = individual_costs[orig_idx]
                weight = weights[rank]
                weighted_val = round(cost * weight, 4)

                participant_evals.append(
                    ParticipantEvaluation(
                        participant_id=p.id,
                        participant_name=p.name,
                        total_distance_km=dist,
                        penalized_cost=round(cost, 4),
                        sorted_rank=rank + 1,  # 1-indexed for human readability
                        rank_weight=weight,
                        weighted_contribution=weighted_val,
                    )
                )

            # Sort participant evaluations by participant ID or original order for stable display
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
            )
            evaluated_combinations.append(evaluation)

        # 5. Select the combination with minimum total penalty score
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
