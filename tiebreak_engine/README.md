# 📍 Module Phân Giải Hòa Vote Bằng Ordered Median Problem (`tiebreak_engine`)

> **Module Tối Ưu Hóa Đa Tiêu Chí Dành Cho Ứng Dụng Lên Lịch Đi Chơi Nhóm**  
> Tự động phân giải các điểm hẹn có lượt bình chọn (vote) bằng nhau thông qua mô hình:  
> **Hàm Phạt Khoảng Cách Phi Tuyến + Bộ Lọc Thứ Hạng Ordered Median (OMP)**.

---

## 🚀 Khởi Động Nhanh: Mở Giao Diện Thử Nghiệm Trực Quan (Playground)

Bất kỳ thành viên nào trong nhóm hoặc giảng viên đều có thể khởi chạy môi trường thử nghiệm với bản đồ OpenStreetMap thực tế và các thanh gạt trọng số:

```bash
# 1. Cài đặt các gói phụ thuộc tối thiểu (nếu chưa có)
pip install -r tiebreak_engine/requirements.txt

# 2. Khởi chạy server Playground
python tiebreak_engine/playground/run_playground.py
```

Sau đó mở trình duyệt tại: **[http://localhost:8080](http://localhost:8080)**.

### 🛑 Cách Dừng Server Playground:
* **Cách thông thường:** Nhấn tổ hợp phím `Ctrl + C` trong cửa sổ Terminal đang chạy server.
* **Nếu đóng mất Terminal hoặc cổng 8080 bị kẹt (Windows PowerShell):**
  ```powershell
  Stop-Process -Id (Get-NetTCPConnection -LocalPort 8080).OwningProcess -Force
  ```
* **macOS / Linux:**
  ```bash
  lsof -ti:8080 | xargs kill -9
  ```

---

## 🌟 Các Tính Năng Nổi Bật Trong Giao Diện Playground

1. **Bản Đồ Đường Phố OSRM Thực Tế (Không Dùng Đường Thẳng / Chim Bay):**
   * Sử dụng API OpenStreetMap Routing Machine với dữ liệu GeoJSON chi tiết.
   * Lộ trình uốn lượn chính xác qua từng ngã tư, cây cầu và tuyến phố tại TP.HCM và Hà Nội.
   * Mỗi thành viên được mã hóa một màu sắc riêng để dễ dàng quan sát lộ trình xe chạy.
2. **2 Chế Độ Chạy Rõ Ràng:**
   * **📘 OMP Thuần Túy (Standard OMP):** Khóa cứng $k = 1.0$ theo đúng chuẩn sách giáo khoa toán tối ưu vị trí (Nickel & Puerto).
   * **🚀 OMP + Phạt Cấp Số Nhân:** Mở khóa thanh trượt $k > 1.0$ ($c_i = d_i^k$) để phạt nặng những ai đi xa.
3. **Quy Trình 3 Bước Trực Quan (Visual OMP Pipeline):**
   * **Bước 1:** Tính chi phí khoảng cách cá nhân $d_i$.
   * **Bước 2 (Chữ ORDERED):** Sắp xếp thứ tự chi phí từ gần nhất đến xa nhất $c_{(1)} \le \dots \le c_{(N)}$.
   * **Bước 3 (Chữ MEDIAN / OMP):** Nhân vector trọng số rank $w_i \times c_{(i)}$ ra tổng điểm phạt $\Psi$.
4. **Kéo Thả Icon Trực Tiếp Trên Bản Đồ (Drag & Drop):**
   * Có thể cầm chuột kéo nhà của bạn bè hoặc vị trí quán ăn đi bất cứ đâu, hệ thống sẽ tự động vẽ lại đường và tính lại điểm tức thì.

---

## 🛠️ Vùng Đất Dành Riêng Cho Developer: `core/scoring_formula.py`

Toàn bộ biểu thức toán học và công thức trọng số được cô lập hoàn toàn tại file:  
👉 **`tiebreak_engine/core/scoring_formula.py`**.

Developer có thể vào đây tự do chỉnh sửa công thức bằng Python thuần mà không sợ làm ảnh hưởng đến tầng API, bản đồ hay cơ sở dữ liệu:

```python
# tiebreak_engine/core/scoring_formula.py

def compute_individual_penalty(distance_km: float, penalty_exponent: float = 1.0) -> float:
    """
    TẦNG 1: Thay đổi cách phạt quãng đường cá nhân.
    Ví dụ: giữ nguyên bậc 1, hoặc lũy thừa 1.5, hoặc bình phương.
    """
    return float(distance_km ** penalty_exponent)


def generate_ordered_median_weights(num_participants: int, fairness_factor: float = 0.5) -> list[float]:
    """
    TẦNG 2: Thay đổi cách phân bổ vector trọng số thứ tự W = (w_1, ..., w_n).
    """
    weights = [1.0 + fairness_factor * (i / (num_participants - 1)) for i in range(num_participants)]
    return weights
```

---

## 🔌 Hướng Dẫn Tích Hợp Vào Backend Của Nhóm

Module được thiết kế dạng Facade Service, cắm thẳng vào `backend/app/domain/patterns/TieBreak/` hoặc gọi từ routers.

### Bước 1: Sao chép thư mục `tiebreak_engine/` vào repo
Thả thư mục `tiebreak_engine/` vào dự án (ví dụ đặt tại `backend/app/domain/patterns/TieBreak/`).

### Bước 2: Gọi Service xử lý Tie-Break

```python
from tiebreak_engine.integration.tie_break_service import TieBreakService
from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    ParticipantLocation,
    ItinerarySlot,
    CandidatePlace,
)

# 1. Khởi tạo service (tận dụng bộ nhớ đệm RAM)
service = TieBreakService()

# 2. Xây dựng payload dữ liệu đầu vào
request = TieBreakRequest(
    participants=[
        ParticipantLocation(id="u1", name="An", lat=10.7769, lng=106.7009),
        ParticipantLocation(id="u2", name="Bình", lat=10.7550, lng=106.6660),
        ParticipantLocation(id="u3", name="Cường", lat=10.8030, lng=106.6950),
    ],
    slots=[
        ItinerarySlot(
            slot_id="slot_lunch",
            slot_name="Ăn trưa (12:00)",
            candidates=[
                CandidatePlace(id="c1", name="Quán Cơm A", lat=10.7780, lng=106.6850),
                CandidatePlace(id="c2", name="Quán Bún B", lat=10.7580, lng=106.7030),
            ],
        )
    ],
    penalty_exponent=1.0,  # Hệ số phạt lũy thừa k
    fairness_factor=0.5,   # Trọng số công bằng lambda
    enable_osrm=True,      # Bật OSRM đường phố thực tế (tự fallback nếu mất mạng)
)

# 3. Thực thi giải bài toán tối ưu
response = await service.resolve(request)

# 4. Trích xuất kết quả
print("Quán chiến thắng:", [c.name for c in response.selected_combination])
print("Tổng điểm mục tiêu (Psi):", response.total_penalty_score)
print("Thời gian chạy:", response.execution_time_ms, "ms")
for item in response.participant_breakdowns:
    print(f"- {item.name}: đi {item.total_distance_km} km | Điểm phạt: {item.penalized_cost} | Hạng: {item.rank}")
```

---

## 🧪 Chạy Bộ Kiểm Thử Tự Động (Unit Tests)

Chạy toàn bộ 18 test cases kiểm thử toán học, định tuyến và API:

```bash
python -m unittest discover -s tiebreak_engine/tests -v
```

Tất cả các bài test chạy bằng thư viện chuẩn `unittest` của Python, **không cần cài đặt thêm pytest hay thư viện ngoài**.

---

## 🌿 Hướng Dẫn Git: Cách Đẩy Code Lên Nhánh Phụ Của Nhóm

### Trường hợp 1: Nếu đã clone repo nhóm ở thư mục khác
1. Copy thư mục `tiebreak_engine/` và file `SPEC.md` dán vào thư mục repo đó.
2. Mở Terminal tại repo nhóm và chạy:
   ```bash
   git checkout -b feat/tiebreak-engine
   git add tiebreak_engine SPEC.md
   git commit -m "feat(algorithm): implement ordered median tiebreak engine and playground"
   git push -u origin feat/tiebreak-engine
   ```

### Trường hợp 2: Nếu đẩy trực tiếp từ thư mục hiện tại
1. Khởi tạo git và liên kết với remote của nhóm:
   ```bash
   git init
   git remote add origin <URL_REPO_CUA_NHOM>
   git fetch origin
   ```
2. Tạo nhánh mới và push:
   ```bash
   git checkout -b feat/tiebreak-engine
   git add tiebreak_engine SPEC.md
   git commit -m "feat(algorithm): implement ordered median tiebreak engine and playground"
   git push -u origin feat/tiebreak-engine
   ```
3. Lên GitHub/GitLab bấm nút **"Compare & pull request"** để gửi PR cho cả nhóm mà không sợ ảnh hưởng đến nhánh `main`.

---

## 📂 Sơ Đồ Cấu Trúc Thư Mục

```text
tiebreak_engine/
├── README.md                      # Tài liệu hướng dẫn sử dụng tiếng Việt
├── requirements.txt               # Các gói phụ thuộc tối thiểu (fastapi, uvicorn, httpx, pydantic)
│
├── core/                          # Thuật toán toán học độc lập (Pure Python)
│   ├── scoring_formula.py         # [VÙNG CỦA DEV] Tự do chỉnh công thức phạt và trọng số OMP
│   ├── ordered_median.py          # Thuật toán OMP sắp xếp thứ tự và tính tích vô hướng
│   ├── itinerary_solver.py        # Đánh giá tổ hợp chuỗi hành trình cố định
│   └── router.py                  # Client OSRM đường phố + Cache RAM + Dự phòng Haversine 1.35x
│
├── integration/                   # Giao tiếp với Backend FastAPI của nhóm
│   ├── schemas.py                 # Pydantic DTOs chuẩn hóa dữ liệu
│   └── tie_break_service.py       # Facade Service cắm vào domain pattern TieBreak
│
├── playground/                    # Giao diện Web thử nghiệm trực quan
│   ├── run_playground.py          # Server FastAPI chạy môi trường sandbox
│   └── static/                    # Giao diện Leaflet OSM, sliders và pipeline trực quan
│       ├── index.html
│       ├── app.js
│       └── style.css
│
└── tests/                         # Bộ 18 automated unit & integration tests
    ├── test_math.py
    ├── test_router.py
    ├── test_solver.py
    ├── test_service.py
    └── test_playground_api.py
```
