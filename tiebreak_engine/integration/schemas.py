"""
=============================================================================
MODULE: schemas.py
MỤC ĐÍCH: Pydantic Data Transfer Objects (DTOs) Tương Thích Backend FastAPI.
=============================================================================
Định nghĩa các hợp đồng dữ liệu đầu vào và đầu ra cho TieBreakService,
khớp nối hoàn hảo với kiến trúc `backend/app/domain/patterns/TieBreak`.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ParticipantLocation(BaseModel):
    id: str = Field(..., description="Mã định danh duy nhất của thành viên")
    name: str = Field(..., description="Tên hiển thị của thành viên")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Vĩ độ nhà của thành viên")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Kinh độ nhà của thành viên")


class CandidatePlace(BaseModel):
    id: str = Field(..., description="Mã định danh quán/địa điểm ứng viên")
    name: str = Field(..., description="Tên quán hoặc địa điểm hẹn")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Vĩ độ của quán")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Kinh độ của quán")
    slot_id: Optional[str] = Field(None, description="Mã khung giờ chặng liên kết")
    votes: Optional[int] = Field(None, description="Số lượt vote bằng nhau")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Thuộc tính bổ sung của địa điểm")


class ItinerarySlot(BaseModel):
    slot_id: str = Field(..., description="Mã chặng thời gian (ví dụ: slot_lunch)")
    slot_name: str = Field(..., description="Tên chặng dễ đọc (ví dụ: Ăn trưa 12:00)")
    candidates: List[CandidatePlace] = Field(..., min_length=1, description="Danh sách các quán ứng viên bị hòa vote")


class TieBreakRequest(BaseModel):
    participants: List[ParticipantLocation] = Field(
        ..., min_length=1, description="Danh sách tọa độ nhà của các thành viên"
    )
    slots: List[ItinerarySlot] = Field(
        ..., min_length=1, description="Chuỗi chặng thời gian cần phân giải"
    )
    penalty_exponent: float = Field(
        1.0, ge=1.0, le=5.0, description="Hệ số lũy thừa phạt khoảng cách cá nhân (k >= 1.0)"
    )
    fairness_factor: float = Field(
        0.5, ge=0.0, le=5.0, description="Trọng số công bằng Ordered Median (lambda >= 0.0)"
    )
    enable_osrm: bool = Field(
        True, description="Có gọi định tuyến đường phố OSRM hay dùng dự phòng"
    )


class ParticipantBreakdown(BaseModel):
    participant_id: str
    name: str
    total_distance_km: float
    penalized_cost: float
    rank: int
    rank_weight: float
    weighted_score: float
    outbound_geometry: List[List[float]] = Field(default_factory=list, description="Tọa độ đường đi thực tế GeoJSON")
    inbound_geometry: List[List[float]] = Field(default_factory=list, description="Tọa độ đường về thực tế GeoJSON")


class CombinationSummary(BaseModel):
    places: List[CandidatePlace]
    total_penalty_score: float
    average_distance_km: float
    max_distance_km: float
    min_distance_km: float


class TieBreakResponse(BaseModel):
    success: bool = True
    selected_combination: List[CandidatePlace]
    total_penalty_score: float
    participant_breakdowns: List[ParticipantBreakdown]
    evaluated_combinations: List[CombinationSummary]
    shared_itinerary_geometry: List[List[float]] = Field(default_factory=list)
    execution_time_ms: float
    fallback_used: bool
    applied_parameters: Dict[str, float]
    message: str = "Phân giải hòa vote thành công."
