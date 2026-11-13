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


if __name__ == "__main__":
    unittest.main()
