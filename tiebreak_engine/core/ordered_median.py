"""
=============================================================================
MODULE: ordered_median.py
PURPOSE: Implementation of the Ordered Median Problem (OMP) Aggregator.
=============================================================================
Given N individual costs and N rank weights, this module:
  1. Identifies the sorted permutation of individual costs.
  2. Computes the scalar dot product between sorted costs and weights.
  3. Returns both the total penalty metric (Psi) and full rank association metadata.
"""

from typing import List, Dict, Any, Tuple


class OrderedMedianResult:
    """Encapsulates the output of the Ordered Median Aggregation."""
    def __init__(
        self,
        total_penalty: float,
        sorted_costs: List[float],
        applied_weights: List[float],
        rank_to_original_index: List[int],
    ):
        self.total_penalty = total_penalty
        self.sorted_costs = sorted_costs
        self.applied_weights = applied_weights
        self.rank_to_original_index = rank_to_original_index

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_penalty": round(self.total_penalty, 4),
            "sorted_costs": [round(c, 4) for c in self.sorted_costs],
            "applied_weights": self.applied_weights,
            "rank_to_original_index": self.rank_to_original_index,
        }


def compute_ordered_median(
    individual_costs: List[float],
    rank_weights: List[float],
) -> OrderedMedianResult:
    """
    Executes the Ordered Median objective function.

    Formula:
        Psi = sum(w_j * c_(j) for j in 1..N)
        where c_(1) <= c_(2) <= ... <= c_(N)

    Parameters:
        individual_costs (List[float]): Unordered list of individual penalized costs.
        rank_weights (List[float]): Rank weights, typically non-decreasing.

    Returns:
        OrderedMedianResult: Object containing aggregate penalty and breakdown metadata.

    Raises:
        ValueError: If lengths of costs and weights mismatch or list is empty.
    """
    n = len(individual_costs)
    if n == 0:
        return OrderedMedianResult(0.0, [], [], [])

    if len(rank_weights) != n:
        raise ValueError(
            f"Dimension mismatch: Received {n} individual costs but {len(rank_weights)} rank weights."
        )

    # Pair each cost with its original index: (cost, original_idx)
    indexed_costs = list(enumerate(individual_costs))
    # Sort ascending by cost: c_(1) <= c_(2) <= ... <= c_(N)
    indexed_costs.sort(key=lambda item: item[1])

    sorted_costs: List[float] = []
    rank_to_original_index: List[int] = []
    total_penalty = 0.0

    for rank, (orig_idx, cost) in enumerate(indexed_costs):
        weight = rank_weights[rank]
        sorted_costs.append(cost)
        rank_to_original_index.append(orig_idx)
        total_penalty += cost * weight

    return OrderedMedianResult(
        total_penalty=total_penalty,
        sorted_costs=sorted_costs,
        applied_weights=rank_weights,
        rank_to_original_index=rank_to_original_index,
    )
