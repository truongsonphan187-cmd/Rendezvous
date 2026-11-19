"""
End-to-end integration tests for TieBreakService and Pydantic schemas.
"""

import unittest
from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    ParticipantLocation,
    ItinerarySlot,
    CandidatePlace,
)
from tiebreak_engine.integration.tie_break_service import TieBreakService


class TestTieBreakService(unittest.IsolatedAsyncioTestCase):
    async def test_end_to_end_resolution(self):
        service = TieBreakService()

        request = TieBreakRequest(
            participants=[
                ParticipantLocation(id="u1", name="Alice", lat=10.7769, lng=106.7009),
                ParticipantLocation(id="u2", name="Bob", lat=10.7550, lng=106.6660),
            ],
            slots=[
                ItinerarySlot(
                    slot_id="slot_lunch",
                    slot_name="Lunch",
                    candidates=[
                        CandidatePlace(id="c1", name="Bistro Central", lat=10.7720, lng=106.6980),
                        CandidatePlace(id="c2", name="Chinatown Diner", lat=10.7520, lng=106.6600),
                    ],
                )
            ],
            penalty_exponent=1.0,
            fairness_factor=0.5,
            enable_osrm=False,  # Resilient fallback mode for fast deterministic testing
        )

        response = await service.resolve(request)

        self.assertTrue(response.success)
        self.assertEqual(len(response.selected_combination), 1)
        self.assertGreater(response.total_penalty_score, 0.0)
        self.assertEqual(len(response.participant_breakdowns), 2)
        self.assertEqual(len(response.evaluated_combinations), 2)
        self.assertGreaterEqual(response.execution_time_ms, 0.0)
        # Check single-slot breakdown
        for p in response.participant_breakdowns:
            self.assertAlmostEqual(p.outbound_distance_km + p.inbound_distance_km, p.total_distance_km, places=2)
            self.assertEqual(p.middle_distance_km, 0.0)

    async def test_multi_slot_dag_visualization_payload(self):
        service = TieBreakService()

        request = TieBreakRequest(
            participants=[
                ParticipantLocation(id="u1", name="Alice", lat=10.7769, lng=106.7009),
                ParticipantLocation(id="u2", name="Bob", lat=10.7550, lng=106.6660),
            ],
            slots=[
                ItinerarySlot(
                    slot_id="slot_lunch",
                    slot_name="Lunch",
                    candidates=[
                        CandidatePlace(id="c1", name="Bistro Central", lat=10.7720, lng=106.6980),
                        CandidatePlace(id="c2", name="Chinatown Diner", lat=10.7520, lng=106.6600),
                    ],
                ),
                ItinerarySlot(
                    slot_id="slot_cafe",
                    slot_name="Cafe",
                    candidates=[
                        CandidatePlace(id="c3", name="Highlands", lat=10.7800, lng=106.7000),
                        CandidatePlace(id="c4", name="Phuc Long", lat=10.7600, lng=106.6700),
                    ],
                ),
            ],
            penalty_exponent=1.0,
            fairness_factor=0.5,
            enable_osrm=False,
        )

        response = await service.resolve(request)

        self.assertTrue(response.success)
        self.assertEqual(len(response.selected_combination), 2)
        self.assertIsNotNone(response.dag_visualization)
        self.assertTrue(response.dag_visualization.enabled)
        self.assertEqual(response.dag_visualization.layers_count, 2)
        # 2 cands in slot 1 x 2 cands in slot 2 = 4 edges
        self.assertEqual(len(response.dag_visualization.edges), 4)
        # 1 step transition (slot 1 -> slot 2)
        self.assertEqual(len(response.dag_visualization.steps), 1)
        self.assertGreater(response.dag_visualization.optimal_middle_distance_km, 0.0)

        # Check breakdown math: outbound + middle + inbound == total
        for p in response.participant_breakdowns:
            self.assertGreater(p.middle_distance_km, 0.0)
            calc_sum = round(p.outbound_distance_km + p.middle_distance_km + p.inbound_distance_km, 2)
            self.assertAlmostEqual(calc_sum, p.total_distance_km, places=1)


if __name__ == "__main__":
    unittest.main()
