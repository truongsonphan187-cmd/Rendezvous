"""
Unit tests for routing client, cache, and Haversine fallback mechanism.
"""

import unittest
from tiebreak_engine.core.router import (
    RouterClient,
    Coordinate,
    haversine_distance_km,
    URBAN_DETOUR_FACTOR,
)


class TestRouter(unittest.IsolatedAsyncioTestCase):
    def test_haversine_distance(self):
        """Validates great-circle distance between two known Saigon coordinates."""
        c1 = Coordinate(lat=10.7797, lng=106.6990)
        c2 = Coordinate(lat=10.7725, lng=106.6980)

        dist = haversine_distance_km(c1, c2)
        self.assertTrue(0.6 < dist < 1.2)

    def test_haversine_same_point(self):
        """Distance from a point to itself is 0."""
        c = Coordinate(lat=10.7769, lng=106.7009)
        self.assertEqual(haversine_distance_km(c, c), 0.0)

    async def test_fallback_when_osrm_disabled(self):
        """When enable_osrm=False, router uses Haversine * 1.35x detour factor."""
        router = RouterClient(enable_osrm=False)
        c1 = Coordinate(lat=10.7700, lng=106.6900)
        c2 = Coordinate(lat=10.7800, lng=106.7000)

        dist, is_fallback = await router.get_distance_km(c1, c2)
        self.assertTrue(is_fallback)
        expected_fallback = round(haversine_distance_km(c1, c2) * URBAN_DETOUR_FACTOR, 3)
        self.assertEqual(dist, expected_fallback)

    async def test_memory_cache(self):
        """Cached coordinates return immediately without recalculating."""
        router = RouterClient(enable_osrm=False)
        c1 = Coordinate(lat=10.7700, lng=106.6900)
        c2 = Coordinate(lat=10.7800, lng=106.7000)

        dist1, _ = await router.get_distance_km(c1, c2)
        initial_cache_size = len(router._distance_cache)
        self.assertGreaterEqual(initial_cache_size, 1)

        # Second query should hit cache directly
        cached_val = router.get_cached_distance(c1, c2)
        self.assertEqual(cached_val, dist1)


if __name__ == "__main__":
    unittest.main()
