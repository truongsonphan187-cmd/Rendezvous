"""
=============================================================================
MODULE: scoring_formula.py
PURPOSE: Developer Customization Zone for Cost Penalties & Ranking Weights.
=============================================================================
This module isolates all mathematical penalty expressions from routing,
networking, and database layers.

To adjust the decision behavior:
  1. Modify `compute_individual_penalty` to change how individual travel distance
     is penalized (e.g., linear vs. polynomial vs. exponential).
  2. Modify `generate_ordered_median_weights` to tune how the group balances
     aggregate travel minimization (MinSum) against outlier fairness (MinMax).
"""

from typing import List


def compute_individual_penalty(distance_km: float, penalty_exponent: float = 1.0) -> float:
    """
    Tier 1: Computes penalized travel cost for an individual participant.

    Formula:
        cost = distance_km ^ penalty_exponent

    Parameters:
        distance_km (float): Total round-trip travel distance in kilometers.
        penalty_exponent (float): Exponent factor k >= 1.0.
            - k = 1.0 : Linear cost (standard Ordered Median Problem).
                        A 10 km trip costs twice as much as a 5 km trip.
            - k = 1.5 : Moderate progressive penalty for long trips.
            - k = 2.0 : Quadratic penalty (heavily penalizes distant participants).

    Returns:
        float: Penalized cost score (unit-less cost metric).
    """
    if distance_km <= 0.0:
        return 0.0

    # Ensure exponent does not invert the penalty logic
    exponent = max(1.0, float(penalty_exponent))
    return float(distance_km ** exponent)


def generate_ordered_median_weights(num_participants: int, fairness_factor: float = 0.5) -> List[float]:
    """
    Tier 2: Generates rank-dependent weight vector W = (w_1, ..., w_n) for ordered costs.

    The individual costs are first sorted ascending: c_(1) <= c_(2) <= ... <= c_(n).
    w_1 applies to the least-burdened participant; w_n applies to the most-burdened.

    Parameters:
        num_participants (int): Total number of participants (N).
        fairness_factor (float): Parameter lambda in [0.0, 2.0].
            - lambda = 0.0 : Utilitarian / MinSum (W = [1, 1, ..., 1]).
                             Minimizes total distance for the group as a whole.
            - lambda = 1.0 : Moderate progressive fairness.
                             Outliers carry higher voting weight in the objective.
            - lambda = 2.0 : High fairness priority.
                             Highest-cost participants dominate the selection.

    Returns:
        List[float]: A list of float weights of length `num_participants`.
    """
    if num_participants <= 0:
        return []
    if num_participants == 1:
        return [1.0]

    lambda_val = max(0.0, float(fairness_factor))
    weights: List[float] = []

    for rank in range(num_participants):
        # Normalized rank from 0 (lowest cost) to 1 (highest cost)
        relative_rank = rank / (num_participants - 1)
        # Linear weight progression
        w = 1.0 + (lambda_val * relative_rank)
        weights.append(round(w, 4))

    return weights
