"""
Unit tests for combinatorial itinerary solver and fairness vs efficiency behavior.
"""

import unittest
from tiebreak_engine.core.router import RouterClient, Coordinate
from tiebreak_engine.core.itinerary_solver import (
    ItinerarySolver,
    Participant,
    PlaceCandidate,
    Slot,
)


class TestItinerarySolver(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = RouterClient(enable_osrm=False)  # Fast deterministic test
        self.solver = ItinerarySolver(self.router)

        # 3 Participants:
        # P1, P2 are clustered in North Saigon (Binh Thanh)
        # P3 is an outlier in South Saigon (District 7)
        self.participants = [
            Participant(id="p1", name="North 1", coord=Coordinate(lat=10.8000, lng=106.7000)),
            Participant(id="p2", name="North 2", coord=Coordinate(lat=10.8050, lng=106.7020)),
            Participant(id="p3", name="South Outlier", coord=Coordinate(lat=10.7300, lng=106.7100)),
        ]

        # 1 Itinerary Slot with 2 tied candidates:
        # Candidate North is very close to P1, P2 (~0.5 km), but far from P3 (~8 km)
        # Candidate Center is midway (~4 km from all)
        candidates = [
            PlaceCandidate(
                id="cand_north",
                name="North Spot",
                coord=Coordinate(lat=10.8020, lng=106.7010),
                slot_id="s1",
                slot_name="Lunch",
            ),
            PlaceCandidate(
                id="cand_center",
                name="Center Spot",
                coord=Coordinate(lat=10.7700, lng=106.7050),
                slot_id="s1",
                slot_name="Lunch",
            ),
        ]
        self.slots = [Slot(id="s1", name="Lunch", candidates=candidates)]

    async def test_minsum_prefers_cluster(self):
        """
        Under pure MinSum (k=1.0, lambda=0.0), the majority cluster (P1, P2)
        dictates the winner, selecting North Spot to minimize total aggregate distance.
        """
        solution = await self.solver.solve(
            participants=self.participants,
            slots=self.slots,
            penalty_exponent=1.0,
            fairness_factor=0.0,
        )

        self.assertEqual(solution.best_combination.candidates[0].id, "cand_north")
        self.assertEqual(len(solution.all_evaluated_combinations), 2)

    async def test_fairness_protects_outlier(self):
        """
        When penalty exponent k=2.0 (quadratic distance penalty), the massive penalty
        incurred by the South Outlier traveling to North Spot forces the system
        to select Center Spot to balance fairness.
        """
        solution = await self.solver.solve(
            participants=self.participants,
            slots=self.slots,
            penalty_exponent=2.0,
            fairness_factor=1.5,
        )

        # Center spot should win because outlier commute North^2 is heavily penalized
        self.assertEqual(solution.best_combination.candidates[0].id, "cand_center")


if __name__ == "__main__":
    unittest.main()
