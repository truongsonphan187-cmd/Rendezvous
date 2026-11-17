"""
=============================================================================
MODULE: run_playground.py
MỤC ĐÍCH: Server Môi Trường Test Web Trực Quan Độc Lập.
=============================================================================
Cách chạy:
    python tiebreak_engine/playground/run_playground.py

Sau đó mở trình duyệt tại: http://localhost:8080
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    TieBreakResponse,
)
from tiebreak_engine.integration.tie_break_service import TieBreakService

app = FastAPI(
    title="TieBreak Engine Interactive Playground",
    description="Môi trường thử nghiệm trực quan đánh giá thuật toán Ordered Median & hàm phạt khoảng cách phi tuyến.",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = TieBreakService()
STATIC_DIR = CURRENT_FILE.parent / "static"


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "TieBreak Engine Playground"}


@app.get("/api/sample-data")
async def get_sample_data():
    """
    Cung cấp các kịch bản mẫu thực tế có điểm lật kèo rõ ràng
    để người test thấy rõ tác động của việc kéo thanh trượt k và lambda!
    """
    return {
        "presets": {
            "saigon_outlier_conflict": {
                "name": "🔥 Sài Gòn: 4 bạn cụm Bắc (Gò Vấp/Bình Thạnh) vs. 1 bạn xa (Quận 7)",
                "description": "Kéo k từ 1.0 -> 2.0 để thấy quán thắng LẬT KÈO từ Gò Vấp (tiện đa số) sang Quận 4 (cứu bạn Q7)!",
                "flip_threshold_k": 1.6,
                "participants": [
                    {"id": "u1", "name": "An (Q1 / Đa Kao)", "lat": 10.7890, "lng": 106.6970},
                    {"id": "u2", "name": "Bình (Bình Thạnh)", "lat": 10.8060, "lng": 106.7020},
                    {"id": "u3", "name": "Cường (Phú Nhuận)", "lat": 10.7960, "lng": 106.6760},
                    {"id": "u4", "name": "Dũng (Gò Vấp)", "lat": 10.8280, "lng": 106.6690},
                    {"id": "u5", "name": "Em (Quận 7 - Outlier)", "lat": 10.7180, "lng": 106.7020},
                ],
                "slots": [
                    {
                        "slot_id": "slot_dinner",
                        "slot_name": "18:00 Tối - Ăn Uống Tụ Tập",
                        "candidates": [
                            {
                                "id": "cand_govap",
                                "name": "Quán Lẩu Dê Gò Vấp (Gần 4 bạn Bắc, bạn Q7 đi 16km)",
                                "lat": 10.8220,
                                "lng": 106.6780,
                            },
                            {
                                "id": "cand_q4",
                                "name": "Quán Nướng Cầu Kênh Tẻ Q4 (Cân bằng, bạn Q7 đi 4km)",
                                "lat": 10.7580,
                                "lng": 106.7010,
                            },
                        ],
                    }
                ],
                "default_penalty_exponent": 1.0,
                "default_fairness_factor": 0.0,
            },
            "hanoi_river_crossing": {
                "name": "🔥 Hà Nội: 3 bạn nội thành (Cầu Giấy/Đống Đa) vs. 1 bạn qua sông (Long Biên)",
                "description": "Ở k=1.0 Cầu Giấy thắng. Khi k >= 1.5, quán Phố Cổ thắng để bạn Long Biên không phải lội qua cầu quá xa!",
                "flip_threshold_k": 1.5,
                "participants": [
                    {"id": "hn1", "name": "Hà (Cầu Giấy)", "lat": 21.0360, "lng": 105.7900},
                    {"id": "hn2", "name": "Linh (Đống Đa)", "lat": 21.0200, "lng": 105.8250},
                    {"id": "hn3", "name": "Minh (Ba Đình)", "lat": 21.0380, "lng": 105.8200},
                    {"id": "hn4", "name": "Nam (Long Biên - Bên kia sông)", "lat": 21.0480, "lng": 105.8890},
                ],
                "slots": [
                    {
                        "slot_id": "slot_hn_lunch",
                        "slot_name": "12:00 Trưa - Ăn Lẩu",
                        "candidates": [
                            {
                                "id": "hn_caugiay",
                                "name": "Lẩu Nướng Cầu Giấy (Tiện 3 bạn, bạn Long Biên đi 13km)",
                                "lat": 21.0320,
                                "lng": 105.7940,
                            },
                            {
                                "id": "hn_phoco",
                                "name": "Nhà Hàng Phố Cổ Hoàn Kiếm (Cận cầu, bạn Long Biên đi 4km)",
                                "lat": 21.0350,
                                "lng": 105.8520,
                            },
                        ],
                    }
                ],
                "default_penalty_exponent": 1.0,
                "default_fairness_factor": 0.0,
            },
            "saigon_2_slots_chain": {
                "name": "🔥 Sài Gòn 2 Chặng: Trưa Ăn Uống + Chiều Cafe Bida",
                "description": "Chuỗi hành trình đa chặng. Kéo slider sẽ thấy tổ hợp 4 đường thay đổi thứ hạng winner!",
                "flip_threshold_k": 1.5,
                "participants": [
                    {"id": "p1", "name": "Quân (Tân Bình)", "lat": 10.8010, "lng": 106.6540},
                    {"id": "p2", "name": "Khánh (Bình Thạnh)", "lat": 10.8050, "lng": 106.7000},
                    {"id": "p3", "name": "Tuấn (Quận 1)", "lat": 10.7769, "lng": 106.7009},
                    {"id": "p4", "name": "Hải (Quận 7 - Outlier)", "lat": 10.7250, "lng": 106.7080},
                ],
                "slots": [
                    {
                        "slot_id": "slot_lunch",
                        "slot_name": "Chặng 1 (11:30): Ăn Trưa",
                        "candidates": [
                            {"id": "s1_q3", "name": "Cơm Niêu Trung Tâm Q3", "lat": 10.7800, "lng": 106.6870},
                            {"id": "s1_q7", "name": "Lẩu Bò Nam Sài Gòn Q7", "lat": 10.7420, "lng": 106.7090},
                        ],
                    },
                    {
                        "slot_id": "slot_cafe",
                        "slot_name": "Chặng 2 (14:30): Cafe Bida",
                        "candidates": [
                            {"id": "s2_binhthanh", "name": "Rooftop Cafe Hàng Xanh", "lat": 10.8030, "lng": 106.7110},
                            {"id": "s2_q4", "name": "Billiards Club Khánh Hội Q4", "lat": 10.7620, "lng": 106.7020},
                        ],
                    },
                ],
                "default_penalty_exponent": 1.0,
                "default_fairness_factor": 0.0,
            },
        }
    }


@app.post("/api/tiebreak", response_model=TieBreakResponse)
async def resolve_tiebreak(request: TieBreakRequest):
    try:
        response = await service.resolve(request)
        return response
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(
            index_file,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )
    return {"message": "Không tìm thấy file giao diện playground static."}


def main():
    port = int(os.environ.get("PORT", 8080))
    print("\n" + "=" * 65)
    print(f"🚀 MÔI TRƯỜNG PLAYGROUND TIEBREAK ENGINE ĐANG CHẠY")
    print(f"👉 Đường dẫn cục bộ: http://localhost:{port}")
    print(f"👉 Kiểm tra sức khỏe API: http://localhost:{port}/api/health")
    print("=" * 65 + "\n")
    uvicorn.run("tiebreak_engine.playground.run_playground:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
