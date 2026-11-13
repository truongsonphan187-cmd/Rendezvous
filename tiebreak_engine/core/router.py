"""
=============================================================================
MODULE: router.py
MỤC ĐÍCH: Client Định Tuyến Linh Hoạt (OSRM Route API + Cache RAM + Fallback Haversine).
=============================================================================
Tính năng:
  1. Nhà cung cấp chính: OpenStreetMap Routing Machine (OSRM) driving API.
     Lấy khoảng cách thực tế trên mạng lưới đường phố VÀ hình học đường đi GeoJSON
     (các khúc cua, ngã tư, cây cầu thực tế) thay vì đường thẳng.
  2. Bộ đệm bộ nhớ (RAM Cache): Lưu các cặp tọa độ đã tính để tránh gọi API trùng lặp.
  3. Phòng thủ mạng (Fallback): Tự động chuyển sang công thức chim bay Haversine nhân
     hệ số ngoằn ngoèo đô thị (1.35x) khi mất mạng, quá thời gian (timeout) hoặc bị hạn chế lượt gọi.
"""

import math
import logging
from typing import Dict, Tuple, List, Optional, Any
from dataclasses import dataclass, field

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger("tiebreak_engine.router")

# Hệ số ngoằn ngoèo đường phố thực tế so với đường chim bay (Urban Detour Factor)
URBAN_DETOUR_FACTOR = 1.35
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lng: float

    def cache_key(self) -> Tuple[float, float]:
        """Làm tròn tọa độ đến 5 chữ số thập phân (~1.1m) để tăng tỷ lệ trúng cache."""
        return (round(self.lat, 5), round(self.lng, 5))


@dataclass
class RouteSegment:
    distance_km: float
    # Danh sách tọa độ GeoJSON: [[lng, lat], [lng, lat], ...]
    geometry: List[List[float]]
    is_fallback: bool


def haversine_distance_km(coord1: Coordinate, coord2: Coordinate) -> float:
    """Tính khoảng cách cung tròn lớn (đường chim bay) giữa 2 tọa độ theo km."""
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
    Quản lý việc tính khoảng cách định tuyến và lấy hình học đường đi thực tế.
    """

    def __init__(
        self,
        osrm_base_url: str = "https://router.project-osrm.org",
        timeout_seconds: float = 4.0,
        enable_osrm: bool = True,
    ):
        self.osrm_base_url = osrm_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.enable_osrm = enable_osrm
        # Bộ đệm lưu: (c1_key, c2_key) -> RouteSegment
        self._route_cache: Dict[Tuple[Tuple[float, float], Tuple[float, float]], RouteSegment] = {}
        self.fallback_triggered_count: int = 0

    @property
    def _distance_cache(self) -> Dict[Tuple[Tuple[float, float], Tuple[float, float]], float]:
        """Thuộc tính tương thích ngược cho việc tra cứu khoảng cách km."""
        return {k: v.distance_km for k, v in self._route_cache.items()}

    def get_cached_distance(self, c1: Coordinate, c2: Coordinate) -> Optional[float]:
        route = self.get_cached_route(c1, c2)
        return route.distance_km if route else None

    def get_cached_route(self, c1: Coordinate, c2: Coordinate) -> Optional[RouteSegment]:
        key = (c1.cache_key(), c2.cache_key())
        return self._route_cache.get(key)

    def set_cached_route(self, c1: Coordinate, c2: Coordinate, segment: RouteSegment) -> None:
        key = (c1.cache_key(), c2.cache_key())
        self._route_cache[key] = segment

        # Với chiều ngược lại: đảo chiều mảng tọa độ đường đi để tối ưu cache
        rev_key = (c2.cache_key(), c1.cache_key())
        if rev_key not in self._route_cache:
            reversed_geometry = list(reversed(segment.geometry)) if segment.geometry else []
            self._route_cache[rev_key] = RouteSegment(
                distance_km=segment.distance_km,
                geometry=reversed_geometry,
                is_fallback=segment.is_fallback,
            )

    def compute_fallback_segment(self, c1: Coordinate, c2: Coordinate) -> RouteSegment:
        """Tính khoảng cách xấp xỉ qua Haversine * Hệ số đường phố 1.35x."""
        direct_km = haversine_distance_km(c1, c2)
        dist_km = round(direct_km * URBAN_DETOUR_FACTOR, 3)
        geometry = [[c1.lng, c1.lat], [c2.lng, c2.lat]]
        return RouteSegment(distance_km=dist_km, geometry=geometry, is_fallback=True)

    async def get_route(self, c1: Coordinate, c2: Coordinate) -> RouteSegment:
        """
        Lấy lộ trình đường đi thực tế, khoảng cách (km) và mảng tọa độ GeoJSON.
        """
        if c1.cache_key() == c2.cache_key():
            return RouteSegment(distance_km=0.0, geometry=[[c1.lng, c1.lat]], is_fallback=False)

        # 1. Kiểm tra trong bộ nhớ cache
        cached = self.get_cached_route(c1, c2)
        if cached is not None:
            return cached

        # 2. Nếu tắt OSRM hoặc thiếu thư viện httpx, dùng ngay fallback
        if not self.enable_osrm or httpx is None:
            fallback_seg = self.compute_fallback_segment(c1, c2)
            self.set_cached_route(c1, c2, fallback_seg)
            self.fallback_triggered_count += 1
            return fallback_seg

        # 3. Gọi API OSRM Route kèm hình học đường đi GeoJSON chi tiết
        url = (
            f"{self.osrm_base_url}/route/v1/driving/"
            f"{c1.lng},{c1.lat};{c2.lng},{c2.lat}"
            f"?overview=full&geometries=geojson&alternatives=false&steps=false"
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
                        geometry = routes[0].get("geometry", {}).get("coordinates", [])
                        segment = RouteSegment(
                            distance_km=distance_km,
                            geometry=geometry,
                            is_fallback=False,
                        )
                        self.set_cached_route(c1, c2, segment)
                        return segment

                logger.warning(
                    f"OSRM trả về mã lỗi {response.status_code}. Kích hoạt chế độ phòng thủ Haversine."
                )
        except Exception as exc:
            logger.warning(
                f"Gọi OSRM thất bại ({type(exc).__name__}: {exc}). Kích hoạt chế độ phòng thủ Haversine."
            )

        # 4. Kích hoạt dự phòng khẩn cấp
        self.fallback_triggered_count += 1
        fallback_seg = self.compute_fallback_segment(c1, c2)
        self.set_cached_route(c1, c2, fallback_seg)
        return fallback_seg

    async def get_distance_km(self, c1: Coordinate, c2: Coordinate) -> Tuple[float, bool]:
        """Hàm tiện ích trả về cặp giá trị: (khoảng_cách_km, có_dùng_dự_phòng_không)."""
        route = await self.get_route(c1, c2)
        return route.distance_km, route.is_fallback
