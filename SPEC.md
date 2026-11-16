# 📘 Tài Liệu Đặc Tả Kỹ Thuật: Module Phân Giải Hòa Vote Bằng Ordered Median (`tiebreak_engine`)

> **Dự án:** Ứng dụng Web Lên Lịch Đi Chơi Nhóm (Đồ án Tư Duy Tính Toán / Computational Thinking)  
> **Thành phần:** Module Phân Giải Hòa Vote Đa Tiêu Chí sử dụng Ordered Median Problem (OMP)  
> **Đối tượng:** Đội ngũ phát triển (Developers), Kỹ sư Backend và Hội đồng Đánh giá Đồ án  
> **Dữ liệu tham khảo:** Ting, P.-H., Hwang, J.-R., Doong, J.-L., & Jeng, M.-C. (2008). Driver fatigue and highway driving: A simulator study. *Physiology & Behavior, 94*(3), 448–453. https://doi.org/10.1016/j.physbeh.2008.02.015  
> **Phiên bản:** 1.2.0  

---

## 1. Bối Cảnh & Mục Tiêu Nghiệp Vụ

### 1.1 Bối Cảnh Thực Tế
Trong ứng dụng lên lịch đi chơi nhóm, các thành viên thường bình chọn (vote) các địa điểm cho từng khung giờ/chặng nhất định (ví dụ: Ăn trưa, Giải trí, Cafe). Khi có từ hai địa điểm trở lên nhận được **số lượt vote bằng nhau**, tình trạng bế tắc (Tie Vote) sẽ xảy ra. Các giải pháp truyền thống như chọn ngẫu nhiên (random) hay ai vote trước thì chọn (first-come first-served) bỏ qua hoàn toàn sự vất vả trong việc di chuyển của các thành viên, dẫn đến mâu thuẫn và lười tham gia ("Xa quá lười đi").

### 1.2 Mục Tiêu của Module `tiebreak_engine`
`tiebreak_engine` là một module độc lập, cắm-và-chạy (plug-and-play) giúp tự động phân giải hòa vote bằng cách đánh giá toàn diện hành trình di chuyển của từng người đối với các ứng viên, nhằm đạt được **Mục Tiêu Kép**:
1. **Hiệu Quả Tập Thể (MinSum / Utilitarian):** Giảm thiểu tổng số km di chuyển của cả nhóm để tiết kiệm xăng xe, thời gian và khí thải.
2. **Công Bằng Cá Nhân (MinMax / Egalitarian):** Bảo vệ các thành viên ở xa (Outliers), ngăn chặn việc một người phải gánh quãng đường quá xa trong khi số đông còn lại đi rất gần.

---

## 2. Mô Hình Toán Học Tối Ưu Hóa (Mathematical Model)

Module sử dụng **Mô Hình 2 Tầng (Two-Tier Optimization Model)** kết hợp giữa Hàm Phạt Khoảng Cách Cá Nhân và Bộ Tổng Hợp Thứ Hạng Ordered Median Problem (OMP):

```
       [Tọa độ Nhà N Thành Viên] + [Các Chặng Thời Gian Có Quán Hòa Vote]
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       TẦNG 1: Chi Phí Cá Nhân Phạt Phi Tuyến     │
             │              c_i = f(d_i) = d_i ^ k              │
             │   (Tùy biến tại tiebreak_engine/core/scoring...) │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │     TẦNG 2: Bộ Tổng Hợp Ordered Median (OMP)     │
             │   1. Sắp xếp: c_(1) <= c_(2) <= ... <= c_(n)     │
             │   2. Tích vô hướng: Ψ = Σ (w_i * c_(i))          │
             │   (Cân bằng giữa Hiệu quả MinSum và MinMax)      │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
               [Lựa Chọn Tổ Hợp Địa Điểm Có Tổng Điểm Phạt Nhỏ Nhất]
```

### 2.1 Tầng 1: Hàm Phạt Khoảng Cách Cá Nhân (Individual Penalty Function)
Gọi $d_i$ là tổng quãng đường khứ hồi của thành viên $i \in \{1, \dots, N\}$ cho một chuỗi địa điểm được chọn ($\text{Nhà} \to S_1 \to S_2 \to \dots \to S_K \to \text{Nhà}$), tính theo đơn vị kilômét (km).

Chi phí cá nhân bị phạt $c_i$ được định nghĩa:

$$c_i = f(d_i) = d_i^k$$

Trong đó $k \ge 1.0$ là **Hệ số lũy thừa phạt quãng đường xa (Penalty Exponent)**:
* **Khi $k = 1.0$ (Chuẩn OMP sách giáo khoa):** Chi phí cá nhân tỷ lệ thuận tuyến tính với số km thực tế ($c_i = d_i$).
* **Khi $k > 1.0$ (Phạt cấp số nhân, ví dụ $k = 1.5$ hoặc $k = 2.0$):** Quãng đường xa bị đội điểm phạt lên theo hàm mũ, buộc thuật toán phải kéo điểm hẹn về phía người xa nhất.

### 2.2 Tầng 2: Bộ Lọc Thứ Hạng Ordered Median (Ordered Median Aggregator)
Với tập hợp chi phí cá nhân của $N$ người $\{c_1, c_2, \dots, c_N\}$:

1. **Bước Sắp Xếp Thứ Tự (Chữ ORDERED):** Sắp xếp dãy chi phí theo thứ tự không giảm:
   $$c_{(1)} \le c_{(2)} \le \dots \le c_{(N)}$$
   *Trong đó: $c_{(1)}$ là người đi gần nhất, $c_{(N)}$ là người phải đi xa nhất (Outlier).*

2. **Vector Trọng Số Thứ Hạng $\vec{w}$ (Chữ MEDIAN / OMP):**
   Định nghĩa vector trọng số $W = (w_1, w_2, \dots, w_N)$ với $w_i \ge 0$, trọng số gán theo **vị trí sau khi sắp xếp**, không gán theo tên người:
   * **MinSum (Ưu tiên tập thể):** $W = (1, 1, \dots, 1) \implies \Psi = \sum c_i$.
   * **MinMax / Center (Ưu tiên người xa nhất):** $W = (0, 0, \dots, 0, 1) \implies \Psi = c_{(N)}$.
   * **Ordered Median Dung Hòa:**
     $$w_i = 1.0 + \lambda \cdot \left(\frac{i - 1}{N - 1}\right)$$
     *với $\lambda \in [0.0, 2.0]$ là hệ số ưu tiên công bằng (Fairness Factor).*

3. **Hàm Mục Tiêu Toàn Cục ($\Psi$):**
   $$\Psi = \sum_{i=1}^N w_i \cdot c_{(i)}$$

Thuật toán duyệt toàn bộ các tổ hợp ứng viên qua tích Đề-các (Cartesian Product) và chọn ra tổ hợp làm **cực tiểu hóa điểm phạt $\Psi$**.

---

## 3. Các Quyết Định Kỹ Thuật Cốt Lõi (Key Architectural Decisions)

| Lĩnh vực | Quyết định đã chọn | Phân tích & Lý do kỹ thuật |
| :--- | :--- | :--- |
| **Chuỗi Lộ Trình** | **Thứ tự chặng cố định (Case B)** | Buổi đi chơi diễn ra theo timeline thời gian cố định (Trưa 11:30 $\to$ Chiều 14:30 $\to$ Tối 18:00). Thuật toán giải bài toán tổ hợp chọn quán tối ưu qua từng chặng, không hoán vị thứ tự thời gian (không giải bài toán người bán hàng TSP tự do). |
| **Thước Đo Khoảng Cách** | **Khoảng cách thực tế (km) qua OSRM** | OpenStreetMap (OSRM) **không có dữ liệu kẹt xe (live traffic) thực tế tại Việt Nam**. Dùng thời gian (phút) của OSM sẽ rất ảo. Khoảng cách đường phố (km) là đại lượng vật lý chuẩn xác, phản ánh trực tiếp tiền xăng và công sức đi xe máy của sinh viên/nhóm bạn. |
| **Độ Uốn Lượn Bản Đồ** | **Đường phố thực tế (GeoJSON Polylines)** | Gọi OSRM với `overview=full&geometries=geojson` để lấy mảng hàng trăm tọa độ đường phố, ngã tư, cây cầu thực tế. Không vẽ đường chim bay thẳng tắp. |
| **Phòng Thủ Mạng** | **Bộ đệm RAM + Dự phòng Haversine 1.35x** | 1) Cache lưu các cặp tọa độ trong RAM để không gọi API trùng lặp.<br>2) Nếu mất mạng hoặc API OSRM bị nghẽn, tự động fallback sang đường chim bay Haversine nhân hệ số ngoằn ngoèo đô thị ($1.35\times$) kèm icon cảnh báo vàng. Đảm bảo app không bao giờ crash! |
| **Tính Năng Đi Nhờ (Carpooling)** | **Tạm hoãn ở V1** | Tránh bẫy phình to phạm vi (Feature Creep) làm phức tạp UI/UX và biến thành bài toán định tuyến xe đón rước (VRPPD). Sẽ phát triển ở giai đoạn sau. |
| **Vùng Cho Developer Tùy Biến** | **Tách riêng `core/scoring_formula.py`** | Tách rời toán học khỏi API và mạng. Developer có thể tự do sửa công thức phạt $c_i = d_i^k$ hoặc trọng số $w_i$ bằng Python thuần dễ hiểu. |
| **Môi Trường Sandbox (Playground)** | **FastAPI Standalone + Leaflet UI** | Một lệnh `python tiebreak_engine/playground/run_playground.py` mở ngay web app cục bộ có bản đồ uốn lượn thật, thanh trượt gạt trọng số và pipeline 3 bước trực quan. |

---

## 4. Cấu Trúc Thư Mục & Đóng Gói Module

```text
tiebreak_engine/
│
├── README.md                           # Tài liệu hướng dẫn sử dụng & tích hợp tiếng Việt
├── requirements.txt                    # Minimal dependencies (fastapi, uvicorn, httpx, pydantic)
│
├── core/                               # Thuật toán cốt lõi độc lập (Pure Python, zero framework)
│   ├── __init__.py
│   ├── scoring_formula.py              # [VÙNG CHO DEV] Chỉnh sửa công thức phạt & trọng số OMP
│   ├── ordered_median.py               # Thuật toán OMP sắp xếp thứ hạng & tính tích vô hướng
│   ├── itinerary_solver.py             # Sinh tổ hợp Đề-các & đánh giá chuỗi hành trình cố định
│   └── router.py                       # OSRM Client + Cache RAM + Dự phòng Haversine 1.35x
│
├── integration/                        # Cầu nối tích hợp vào backend FastAPI của nhóm
│   ├── __init__.py
│   ├── schemas.py                      # Pydantic DTOs (Request / Response validation models)
│   └── tie_break_service.py            # Facade Service cắm vào `backend/app/domain/patterns/TieBreak`
│
└── playground/                         # Môi trường Web thử nghiệm trực quan
    ├── __init__.py
    ├── run_playground.py               # Server FastAPI độc lập chạy trên cổng 8080
    └── static/
        ├── index.html                  # Giao diện Leaflet OSM, sliders, pipeline 3 bước
        ├── app.js                      # Quản lý trạng thái, kéo thả marker, gọi API real-time
        └── style.css                   # Định dạng Dashboard hiện đại, chuẩn Typography
```

---

## 5. Hướng Dẫn Tùy Biến Thuật Toán (`core/scoring_formula.py`)

Developer chỉ cần can thiệp vào duy nhất file này để thay đổi hành vi ra quyết định:

```python
"""
File: tiebreak_engine/core/scoring_formula.py
Mục đích: Nơi định nghĩa các công thức toán học do Developer quyết định.
"""

def compute_individual_penalty(distance_km: float, penalty_exponent: float = 1.0) -> float:
    """
    TẦNG 1: Tính điểm phạt quãng đường cá nhân.
    - k = 1.0 : Chi phí tuyến tính (chuẩn OMP sách giáo khoa).
    - k = 1.5, 2.0 : Phạt lũy thừa/cấp số nhân cho người đi xa.
    """
    if distance_km <= 0.0:
        return 0.0
    return float(distance_km ** max(1.0, penalty_exponent))


def generate_ordered_median_weights(num_participants: int, fairness_factor: float = 0.5) -> list[float]:
    """
    TẦNG 2: Sinh vector trọng số thứ tự W = (w_1, ..., w_n) cho Ordered Median.
    - lambda = 0.0 : [1, 1, ..., 1] -> MinSum (tiết kiệm xăng cả nhóm).
    - lambda = 1.0 : Ordered Median dung hòa.
    - lambda = 2.0 : Tiệm cận MinMax (ưu tiên cứu người xa nhất).
    """
    if num_participants <= 0:
        return []
    if num_participants == 1:
        return [1.0]

    weights = []
    for rank in range(num_participants):
        w = 1.0 + fairness_factor * (rank / (num_participants - 1))
        weights.append(round(w, 4))
        
    return weights
```

---

## 6. Hợp Đồng Tích Hợp Vào Backend Của Nhóm

Backend chính của nhóm (`backend/app/`) tích hợp module qua class `TieBreakService` mà không cần chỉnh sửa database:

```python
from tiebreak_engine.integration.tie_break_service import TieBreakService
from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    ParticipantLocation,
    ItinerarySlot,
    CandidatePlace
)

# 1. Khởi tạo Service
service = TieBreakService()

# 2. Xây dựng DTO đầu vào
request_data = TieBreakRequest(
    participants=[
        ParticipantLocation(id="u1", name="An", lat=10.7769, lng=106.7009),
        ParticipantLocation(id="u2", name="Bình", lat=10.7550, lng=106.6660),
    ],
    slots=[
        ItinerarySlot(
            slot_id="slot_lunch",
            slot_name="Ăn trưa (12:00)",
            candidates=[
                CandidatePlace(id="c1", name="Quán Cơm Trung Tâm", lat=10.7780, lng=106.6850),
                CandidatePlace(id="c2", name="Quán Bún Bò Phía Nam", lat=10.7580, lng=106.7030),
            ]
        )
    ],
    penalty_exponent=1.0,  # k = 1.0 (OMP thuần) hoặc k > 1.0
    fairness_factor=0.5,   # lambda = 0.5
    enable_osrm=True
)

# 3. Gọi xử lý bất đồng bộ
result = await service.resolve(request_data)

# Kết quả nhận được:
# - result.selected_combination: Quán chiến thắng
# - result.total_penalty_score: Tổng điểm phạt tối ưu (Psi)
# - result.participant_breakdowns: Chi tiết từng người (km, chi phí phạt, hạng, trọng số w_i)
```

---

## 7. Kết Quả Nghiệm Thu & Kiểm Thử Tự Động

- [x] Thống nhất yêu cầu kỹ thuật & bài toán kinh doanh.
- [x] Tài liệu đặc tả kỹ thuật hoàn chỉnh (`SPEC.md`).
- [x] Xây dựng tầng `core/`:
  - [x] `scoring_formula.py` (Vùng tùy biến của Developer).
  - [x] `ordered_median.py` (OMP sort rank & dot product).
  - [x] `router.py` (OSRM đường phố thật + Cache RAM + Haversine 1.35x fallback).
  - [x] `itinerary_solver.py` (Bộ giải tổ hợp Đề-các qua chuỗi chặng cố định).
- [x] Xây dựng tầng `integration/`:
  - [x] `schemas.py` (Pydantic models DTOs).
  - [x] `tie_break_service.py` (Facade service cắm vào `backend/app/domain/patterns/TieBreak`).
- [x] Xây dựng tầng `playground/`:
  - [x] `run_playground.py` (FastAPI server cổng 8080).
  - [x] Giao diện Leaflet OSM đường phố thật + Sliders + Pipeline 3 bước trực quan.
- [x] Bộ kiểm thử tự động 18 test cases (100% Passed):
  - [x] Kiểm thử tính đơn điệu của OMP và hàm lũy thừa.
  - [x] Kiểm thử tính công bằng khi bảo vệ Outlier.
  - [x] Kiểm thử định tuyến, cache bộ nhớ và cơ chế dự phòng.
  - [x] Kiểm thử API và Facade Service.
- [x] Bàn giao:
  - [x] File `README.md` tiếng Việt hướng dẫn tích hợp và lệnh git.
