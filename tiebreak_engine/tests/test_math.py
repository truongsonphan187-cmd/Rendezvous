"""
Unit tests for mathematical scoring formulas and Ordered Median aggregation.
"""

import unittest
import math
from tiebreak_engine.core.scoring_formula import (
    compute_individual_penalty,
    generate_ordered_median_weights,
)
from tiebreak_engine.core.ordered_median import compute_ordered_median, OrderedMedianResult


class TestScoringFormula(unittest.TestCase):
    def test_individual_penalty_linear(self):
        """k = 1.0 preserves exact linear distance."""
        self.assertEqual(compute_individual_penalty(0.0, 1.0), 0.0)
        self.assertEqual(compute_individual_penalty(10.5, 1.0), 10.5)

    def test_individual_penalty_polynomial(self):
        """k = 2.0 squares the distance."""
        self.assertEqual(compute_individual_penalty(4.0, 2.0), 16.0)
        self.assertEqual(compute_individual_penalty(5.0, 2.0), 25.0)

    def test_individual_penalty_negative_clamp(self):
        """Non-positive distance returns 0.0."""
        self.assertEqual(compute_individual_penalty(-5.0, 1.5), 0.0)

    def test_weights_minsum(self):
        """lambda = 0.0 yields identical weights of 1.0 for all ranks (MinSum)."""
        weights = generate_ordered_median_weights(5, fairness_factor=0.0)
        self.assertEqual(len(weights), 5)
        self.assertEqual(weights, [1.0, 1.0, 1.0, 1.0, 1.0])

    def test_weights_fairness_progression(self):
        """lambda > 0.0 produces strictly increasing weights with respect to rank."""
        weights = generate_ordered_median_weights(4, fairness_factor=1.0)
        self.assertEqual(len(weights), 4)
        # rank 0: 1.0, rank 3: 1.0 + 1.0*(3/3) = 2.0
        self.assertEqual(weights[0], 1.0)
        self.assertEqual(weights[-1], 2.0)
        for i in range(len(weights) - 1):
            self.assertLessEqual(weights[i], weights[i + 1])


class TestOrderedMedianAggregator(unittest.TestCase):
    def test_ordered_median_computation(self):
        """Verifies rank sorting and scalar dot product."""
        costs = [30.0, 10.0, 20.0]
        weights = [1.0, 1.5, 2.0]

        result: OrderedMedianResult = compute_ordered_median(costs, weights)

        # Expected Psi = (10*1.0) + (20*1.5) + (30*2.0) = 10 + 30 + 60 = 100.0
        self.assertTrue(math.isclose(result.total_penalty, 100.0, rel_tol=1e-4))
        self.assertEqual(result.sorted_costs, [10.0, 20.0, 30.0])
        self.assertEqual(result.rank_to_original_index, [1, 2, 0])

    def test_dimension_mismatch_error(self):
        """Raises ValueError when lengths of costs and weights mismatch."""
        with self.assertRaises(ValueError):
            compute_ordered_median([10.0, 20.0], [1.0, 1.5, 2.0])


if __name__ == "__main__":
    unittest.main()
