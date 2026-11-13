"""
=============================================================================
MODULE: run_playground.py
PURPOSE: Interactive Standalone Web Playground Server.
=============================================================================
Run with:
    python -m tiebreak_engine.playground.run_playground
    or
    python tiebreak_engine/playground/run_playground.py

Then visit: http://localhost:8080
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

# Ensure the root project directory is in sys.path
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    TieBreakResponse,
    ParticipantLocation,
    ItinerarySlot,
    CandidatePlace,
)
from tiebreak_engine.integration.tie_break_service import TieBreakService

app = FastAPI(
    title="TieBreak Engine Interactive Playground",
    description="Interactive sandbox to evaluate Ordered Median Problem & non-linear penalty parameters.",
    version="1.0.0",
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
    """Provides realistic presets for immediate interactive testing."""
    return {
        "presets": {
            "hcmc_5_friends": {
                "name": "TP. Hồ Chí Minh - 5 Bạn (Quận 1, 5, Bình Thạnh, Tân Bình, Quận 7)",
                "participants": [
                    {"id": "u1", "name": "An (Quận 1)", "lat": 10.7769, "lng": 106.7009},
                    {"id": "u2", "name": "Bình (Quận 5)", "lat": 10.7550, "lng": 106.6660},
                    {"id": "u3", "name": "Cường (Bình Thạnh)", "lat": 10.8030, "lng": 106.6950},
                    {"id": "u4", "name": "Dũng (Tân Bình)", "lat": 10.8010, "lng": 106.6540},
                    {"id": "u5", "name": "Em (Quận 7 - Xa nhất)", "lat": 10.7300, "lng": 106.7050},
                ],
                "slots": [
                    {
                        "slot_id": "slot_1_lunch",
                        "slot_name": "12:00 Trưa - Ăn uống",
                        "candidates": [
                            {"id": "c1_central", "name": "Quán Cơm Trung Tâm (Quận 3)", "lat": 10.7780, "lng": 106.6850},
                            {"id": "c1_south", "name": "Quán Bún Bò Phía Nam (Quận 4 giáp Q7)", "lat": 10.7580, "lng": 106.7030},
                        ],
                    },
                    {
                        "slot_id": "slot_2_cafe",
                        "slot_name": "14:30 Chiều - Cafe & Bida",
                        "candidates": [
                            {"id": "c2_north", "name": "Cafe Rooftop Hàng Xanh (Bình Thạnh)", "lat": 10.8020, "lng": 106.7110},
                            {"id": "c2_central", "name": "Billiard Club Nguyễn Thị Minh Khai (Q1)", "lat": 10.7850, "lng": 106.6960},
                        ],
                    },
                ],
                "default_penalty_exponent": 1.5,
                "default_fairness_factor": 0.8,
            },
            "hanoi_outlier": {
                "name": "Hà Nội - Nhóm có 1 bạn ở Long Biên (Qua sông)",
                "participants": [
                    {"id": "hn1", "name": "Hà (Hoàn Kiếm)", "lat": 21.0285, "lng": 105.8542},
                    {"id": "hn2", "name": "Linh (Cầu Giấy)", "lat": 21.0360, "lng": 105.7900},
                    {"id": "hn3", "name": "Minh (Đống Đa)", "lat": 21.0180, "lng": 105.8280},
                    {"id": "hn4", "name": "Nam (Long Biên - Qua cầu)", "lat": 21.0450, "lng": 105.8850},
                ],
                "slots": [
                    {
                        "slot_id": "slot_hn_lunch",
                        "slot_name": "11:30 Trưa - Lẩu",
                        "candidates": [
                            {"id": "hn_c1", "name": "Lẩu Phố Cổ (Hoàn Kiếm)", "lat": 21.0330, "lng": 105.8500},
                            {"id": "hn_c2", "name": "Lẩu Nướng Cầu Giấy", "lat": 21.0300, "lng": 105.7950},
                        ],
                    }
                ],
                "default_penalty_exponent": 1.0,
                "default_fairness_factor": 1.0,
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


# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Playground static UI not found. Please verify static/index.html."}


def main():
    port = int(os.environ.get("PORT", 8080))
    print("\n" + "=" * 65)
    print(f"🚀 TIEBREAK ENGINE INTERACTIVE PLAYGROUND RUNNING")
    print(f"👉 Local URL: http://localhost:{port}")
    print(f"👉 Health Check: http://localhost:{port}/api/health")
    print("=" * 65 + "\n")
    uvicorn.run("tiebreak_engine.playground.run_playground:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
