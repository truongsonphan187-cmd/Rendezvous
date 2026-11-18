"""
Unit tests for combinatorial itinerary solver, Layered DP vs Brute-Force equivalence,
and fairness vs efficiency trade-offs.
"""

import unittest
import random
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

    async def test_multi_slot_dp_matches_brute_force_3_slots(self):
        """
        Verify that for K = 3 slots, Layered DP yields the identical optimal
        combination and identical Psi score as Brute Force.
        """
        slot2_cands = [
            PlaceCandidate(id="s2_c1", name="Cafe A", coord=Coordinate(lat=10.7800, lng=106.6900), slot_id="s2", slot_name="Cafe"),
            PlaceCandidate(id="s2_c2", name="Cafe B", coord=Coordinate(lat=10.7850, lng=106.6950), slot_id="s2", slot_name="Cafe"),
        ]
        slot3_cands = [
            PlaceCandidate(id="s3_c1", name="Dinner A", coord=Coordinate(lat=10.7600, lng=106.6800), slot_id="s3", slot_name="Dinner"),
            PlaceCandidate(id="s3_c2", name="Dinner B", coord=Coordinate(lat=10.7650, lng=106.6850), slot_id="s3", slot_name="Dinner"),
        ]
        three_slots = [
            self.slots[0],
            Slot(id="s2", name="Cafe", candidates=slot2_cands),
            Slot(id="s3", name="Dinner", candidates=slot3_cands),
        ]

        dp_sol = await self.solver.solve(self.participants, three_slots, penalty_exponent=1.5, fairness_factor=0.8)
        bf_sol = await self.solver.solve_bruteforce(self.participants, three_slots, penalty_exponent=1.5, fairness_factor=0.8)

        self.assertAlmostEqual(dp_sol.best_combination.total_penalty_score, bf_sol.best_combination.total_penalty_score, places=4)
        dp_cand_ids = [c.id for c in dp_sol.best_combination.candidates]
        bf_cand_ids = [c.id for c in bf_sol.best_combination.candidates]
        self.assertEqual(dp_cand_ids, bf_cand_ids)

    async def test_layered_dp_randomized_equivalence(self):
        """
        Rigorous stress test: 25 randomized configurations across varying N, K (3 to 5 slots),
        candidate counts, k exponents, and lambda fairness factors.
        Verifies 100% mathematical match between Layered DP and Brute-Force.
        """
        rng = random.Random(42)  # Deterministic seed for repeatable tests

        for case_idx in range(25):
            n_participants = rng.randint(3, 5)
            k_slots = rng.randint(3, 4)
            k_exp = rng.choice([1.0, 1.2, 1.5, 2.0])
            lam = rng.choice([0.0, 0.4, 0.8, 1.2])

            pts = [
                Participant(
                    id=f"p_{i}",
                    name=f"User {i}",
                    coord=Coordinate(lat=10.70 + rng.random() * 0.15, lng=106.60 + rng.random() * 0.15)
                )
                for i in range(n_participants)
            ]

            test_slots = []
            for s_idx in range(k_slots):
                n_cands = rng.randint(2, 3)
                cands = [
                    PlaceCandidate(
                        id=f"s{s_idx}_c{c_idx}",
                        name=f"Place {s_idx}.{c_idx}",
                        coord=Coordinate(lat=10.70 + rng.random() * 0.15, lng=106.60 + rng.random() * 0.15),
                        slot_id=f"s{s_idx}",
                        slot_name=f"Slot {s_idx}",
                    )
                    for c_idx in range(n_cands)
                ]
                test_slots.append(Slot(id=f"s{s_idx}", name=f"Slot {s_idx}", candidates=cands))

            dp_res = await self.solver.solve(pts, test_slots, penalty_exponent=k_exp, fairness_factor=lam)
            bf_res = await self.solver.solve_bruteforce(pts, test_slots, penalty_exponent=k_exp, fairness_factor=lam)

            self.assertAlmostEqual(
                dp_res.best_combination.total_penalty_score,
                bf_res.best_combination.total_penalty_score,
                places=4,
                msg=f"Mismatch at randomized case {case_idx}: DP={dp_res.best_combination.total_penalty_score}, BF={bf_res.best_combination.total_penalty_score}"
            )


if __name__ == "__main__":
    unittest.main()
