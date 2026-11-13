"""
=============================================================================
MODULE: router.py
PURPOSE: Resilient Routing Client (OSRM Table/Route API + Cache + Haversine Fallback).
=============================================================================
Features:
  1. Primary Provider: Public OpenStreetMap Routing Machine (OSRM) driving API.
  2. Memory Cache: In-memory coordinate pair cache to avoid redundant API hits.
  3. Resilience Fallback: Automatic fallback to great-circle Haversine formula
     multiplied by an urban detour factor (1.35x) on network error/timeout/HTTP 429.
"""

import math
import logging
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass

try:
    import httpx
except ImportError:
    httpx = None  # Fallback gracefully if httpx is unavailable

logger = logging.getLogger("tiebreak_engine.router")

# Standard urban tortuosity / detour factor for road networks
URBAN_DETOUR_FACTOR = 1.35
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lng: float

    def cache_key(self) -> Tuple[float, float]:
        """Rounds coordinates to ~1.1m precision for robust cache hit rate."""
        return (round(self.lat, 5), round(self.lng, 5))


def haversine_distance_km(coord1: Coordinate, coord2: Coordinate) -> float:
    """Computes great-circle distance between two points on Earth in kilometers."""
    if coord1 == coord2:
        return 0.0

    phi1 = math.radians(coord1.lat)
    phi2 = math.radians(coord2.lat)
    delta_phi = math.radians(coord2.lat - coord1.lat)
    delta_lambda = math.radians(coord2.lng - coord1.lng)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


class RouterClient:
    """
    Manages pairwise routing and distance matrix computation.
    Thread-safe in-memory cache and automatic fallback mechanism.
    """

    def __init__(
        self,
        osrm_base_url: str = "https://router.project-osrm.org",
        timeout_seconds: float = 3.0,
        enable_osrm: bool = True,
    ):
        self.osrm_base_url = osrm_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.enable_osrm = enable_osrm
        self._distance_cache: Dict[Tuple[Tuple[float, float], Tuple[float, float]], float] = {}
        self.fallback_triggered_count: int = 0

    def get_cached_distance(self, c1: Coordinate, c2: Coordinate) -> Optional[float]:
        key = (c1.cache_key(), c2.cache_key())
        return self._distance_cache.get(key)

    def set_cached_distance(self, c1: Coordinate, c2: Coordinate, dist_km: float) -> None:
        key = (c1.cache_key(), c2.cache_key())
        self._distance_cache[key] = dist_km
        # Symmetric road network approximation for cache efficiency
        rev_key = (c2.cache_key(), c1.cache_key())
        if rev_key not in self._distance_cache:
            self._distance_cache[rev_key] = dist_km

    def compute_fallback_distance(self, c1: Coordinate, c2: Coordinate) -> float:
        """Calculates approximate driving distance via Haversine * Detour Factor."""
        direct_km = haversine_distance_km(c1, c2)
        return round(direct_km * URBAN_DETOUR_FACTOR, 3)

    async def get_distance_km(self, c1: Coordinate, c2: Coordinate) -> Tuple[float, bool]:
        """
        Gets the driving distance between two coordinates in kilometers.

        Returns:
            Tuple[float, bool]: (distance_in_km, is_fallback_used)
        """
        if c1.cache_key() == c2.cache_key():
            return 0.0, False

        # 1. Check in-memory cache
        cached = self.get_cached_distance(c1, c2)
        if cached is not None:
            return cached, False

        # 2. If OSRM is disabled, use fallback immediately
        if not self.enable_osrm or httpx is None:
            fallback_dist = self.compute_fallback_distance(c1, c2)
            self.set_cached_distance(c1, c2, fallback_dist)
            self.fallback_triggered_count += 1
            return fallback_dist, True

        # 3. Query OSRM Table or Route API
        # OSRM coordinate order: {lng},{lat};{lng},{lat}
        url = (
            f"{self.osrm_base_url}/route/v1/driving/"
            f"{c1.lng},{c1.lat};{c2.lng},{c2.lat}"
            f"?overview=false&alternatives=false&steps=false"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    routes = data.get("routes", [])
                    if routes:
                        distance_meters = float(routes[0].get("distance", 0.0))
                        distance_km = round(distance_meters / 1000.0, 3)
                        self.set_cached_distance(c1, c2, distance_km)
                        return distance_km, False

                logger.warning(
                    f"OSRM returned status {response.status_code}. Activating Haversine fallback."
                )
        except Exception as exc:
            logger.warning(
                f"OSRM request failed ({type(exc).__name__}: {exc}). Activating Haversine fallback."
            )

        # 4. Fallback execution
        self.fallback_triggered_count += 1
        fallback_dist = self.compute_fallback_distance(c1, c2)
        self.set_cached_distance(c1, c2, fallback_dist)
        return fallback_dist, True

    async def compute_distance_matrix(
        self, origins: List[Coordinate], destinations: List[Coordinate]
    ) -> Tuple[List[List[float]], bool]:
        """
        Computes pairwise distance matrix between origins and destinations.

        Returns:
            Tuple[List[List[float]], bool]: (matrix[len(origins)][len(destinations)], any_fallback_used)
        """
        matrix: List[List[float]] = []
        any_fallback = False

        for orig in origins:
            row: List[float] = []
            for dest in destinations:
                dist_km, is_fallback = await self.get_distance_km(orig, dest)
                if is_fallback:
                    any_fallback = True
                row.append(dist_km)
            matrix.append(row)

        return matrix, any_fallback
