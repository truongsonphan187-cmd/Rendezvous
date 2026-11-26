# Rendezvous — Ordered Median Tie-Break Engine

**Web mô phỏng và bộ giải tối ưu hóa công bằng đa tiêu chí cho bài toán chọn điểm hẹn nhóm (*Optimal Meeting Problem*)**, sử dụng mô hình **Ordered Median Problem (OMP)** kết hợp **Quy hoạch động đa tầng trên đồ thị DAG (*Layered DP*)**.

- **Live Web Demo:** [https://rendezvous-6brs.onrender.com/](https://rendezvous-6brs.onrender.com/)
- **Đặc tả toán học & kiến trúc chi tiết:** [docs/SPEC.md](docs/SPEC.md)

---

## 1. Bài toán & Mục tiêu

Khi một nhóm bạn bình chọn (vote) địa điểm đi chơi theo lịch trình gồm 1 hoặc nhiều chặng (ví dụ: *Ăn trưa $\to$ Cafe $\to$ Giải trí*) và xảy ra **hòa phiếu (tie-vote)** giữa nhiều quán ứng viên, các cách chọn ngẫu nhiên thường gây bất công cho người ở xa.

`tiebreak_engine` giải quyết bế tắc này bằng cách tối ưu đồng thời hai tiêu chí:
1. **Hiệu quả tập thể (*MinSum / Utilitarian*):** Giảm thiểu tổng quãng đường di chuyển của cả nhóm.
2. **Công bằng cá nhân (*MinMax / Egalitarian*):** Bảo vệ thành viên ở xa nhất (*outlier*), tránh tình trạng số đông đi rất gần trong khi một người phải di chuyển quá xa.

---

## 2. Tính năng của Web Mô Phỏng

- **Bản đồ đường phố thực tế (OSRM + LeafletJS):** Tính toán và vẽ lộ trình giao thông thực tế dạng GeoJSON thông qua OpenStreetMap Routing Machine. Tự động chuyển sang dự phòng **Haversine $\times 1.35$** nếu mất mạng hoặc OSRM quá tải, bảo đảm ứng dụng không bao giờ sập.
- **Tương tác trực tiếp trên bản đồ:** Kéo-thả vị trí nhà thành viên (`P1..Pn`) và các địa điểm ứng viên (`D1..Dk`) để quan sát kết quả tính lại ngay lập tức; hỗ trợ thêm/xóa thành viên và mở rộng từ **1 đến 5 chặng** lịch trình.
- **Hai chế độ tinh chỉnh thuật toán:**
  - **OMP tiêu chuẩn ($k = 1.0$):** Chi phí cá nhân tỷ lệ tuyến tính với quãng đường thực tế (km).
  - **OMP mở rộng ($k > 1.0$):** Áp dụng hàm phạt lũy thừa lên quãng đường xa ($c_i = d_i^k$).
  - **Thanh trượt trọng số công bằng ($\lambda$):** Điều chỉnh liên tục từ $\lambda = 0.0$ (*MinSum*) sang $\lambda \ge 1.0$ (ưu tiên giảm tải cho người đi xa nhất).
- **Trực quan hóa thuật toán Layered DP trên DAG:** Khi có từ 2 chặng trở lên, hệ thống dựng sơ đồ các tầng ứng viên và các cạnh chuyển chặng; rê chuột vào từng cạnh để làm nổi bật tuyến đường tương ứng trên bản đồ và xem số lượng phương án kém hơn đã bị cắt tỉa theo nguyên lý tối ưu Bellman.
- **Bảng phân tích chi tiết:** Hiển thị phân rã 3 phần quãng đường của từng thành viên (`Đi riêng + Đi chung + Về riêng`), điểm đóng góp theo thứ hạng, và bảng so sánh tất cả các tổ hợp ứng viên.

---

## 3. Mô hình Toán học & Giải thuật

Hệ thống sử dụng mô hình tối ưu hai tầng kết hợp phân rã đồ thị:

### Tầng 1 — Hàm phạt khoảng cách cá nhân
Gọi $d_i$ là tổng quãng đường (km) của thành viên $i \in \{1, \dots, N\}$ cho lộ trình $\text{Nhà}_i \to s_1 \to \dots \to s_K \to \text{Nhà}_i$. Chi phí cá nhân bị phạt được tính:

$$c_i = d_i^k \quad (k \ge 1.0)$$

### Tầng 2 — Bộ tổng hợp thứ hạng Ordered Median (OMP)
1. Sắp xếp chi phí cá nhân theo thứ tự không giảm: $c_{(1)} \le c_{(2)} \le \dots \le c_{(N)}$.
2. Sinh vector trọng số thứ hạng (tăng dần theo hạng đứng, không phụ thuộc danh tính người):

   $$w_i = 1.0 + \lambda \cdot \left(\frac{i - 1}{N - 1}\right) \quad (\lambda \ge 0.0)$$

3. Cực tiểu hóa hàm mục tiêu toàn cục:

   $$\Psi = \sum_{i=1}^{N} w_i \cdot c_{(i)}$$

### Giải thuật Quy hoạch động đa tầng (Layered DP on DAG)
Với mọi cặp điểm biên đầu–cuối $(s_1 \in S_1, s_K \in S_K)$ cố định, các chặng trung gian $(S_2 \to \dots \to S_{K-1})$ đóng góp cùng một quãng đường di chuyển chung $D_{\text{middle}}(s_1, s_K)$ cho cả nhóm. Do $c_i = (d_{i,\text{ends}} + D_{\text{middle}})^k$ đơn điệu tăng nghiêm ngặt với $k \ge 1$ và $w_i \ge 0$, bài toán giảm độ phức tạp từ vét cạn $O(M^K)$ xuống $O(M_1 \cdot M_K \cdot K M^2)$ mà vẫn **khớp nghiệm chính xác 100%** với Brute-force.

*Tài liệu tham khảo nền tảng phạt phi tuyến:* Ting, P.-H., Hwang, J.-R., Doong, J.-L., & Jeng, M.-C. (2008). Driver fatigue and highway driving: A simulator study. *Physiology & Behavior*, 94(3), 448–453.

---

## 4. Cấu trúc Dự án

```text
.
├── README.md                          # Tài liệu tổng quan và hướng dẫn sử dụng
├── requirements.txt                   # Thư viện Python cho FastAPI, httpx, Pydantic
├── Dockerfile                         # Đóng gói container triển khai trên Render / Docker
├── docs/
│   └── SPEC.md                        # Tài liệu đặc tả kỹ thuật & chứng minh toán học
├── scripts/
│   ├── generate_cases.py              # Script sinh 20 bộ dữ liệu benchmark (TP.HCM)
│   └── data/                          # Đầu ra JSON / TXT từ script sinh test
└── tiebreak_engine/                   # Gói mã nguồn chính
    ├── core/                          # Thuật toán thuần Python (không phụ thuộc web framework)
    │   ├── scoring_formula.py         # Công thức phạt cá nhân (k) & vector trọng số (λ)
    │   ├── ordered_median.py          # Bộ tổng hợp thứ hạng OMP
    │   ├── itinerary_solver.py        # Giải thuật Layered DP trên Multi-Stage DAG
    │   └── router.py                  # OSRM client, RAM cache & dự phòng Haversine 1.35x
    ├── integration/                   # Tầng dịch vụ và hợp đồng dữ liệu
    │   ├── schemas.py                 # Pydantic request/response DTOs
    │   └── tie_break_service.py       # Facade Service điều phối định tuyến & bộ giải
    ├── playground/                    # Web Server & Giao diện mô phỏng trực quan
    │   ├── run_playground.py          # FastAPI server (cổng mặc định 8080, hoặc biến PORT)
    │   └── static/                    # Frontend HTML / CSS / JavaScript (LeafletJS)
    └── tests/                         # Bộ kiểm thử tự động (21 unit & API tests)
        ├── test_math.py
        ├── test_solver.py
        ├── test_router.py
        ├── test_service.py
        └── test_playground_api.py
```

---

## 5. Cài đặt & Khởi chạy

### Yêu cầu hệ thống
- Python 3.11 trở lên (khuyến nghị 3.11 – 3.13)
- Kết nối Internet để tải bản đồ OpenStreetMap và gọi OSRM Routing API (nếu ngoại tuyến, ứng dụng tự động dùng Haversine 1.35x).

### Chạy cục bộ (Local)

```bash
# 1. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

# 2. Khởi chạy FastAPI Playground Server
python -m tiebreak_engine.playground.run_playground
```

Mở trình duyệt tại **[http://localhost:8080](http://localhost:8080)**.

> Có thể đổi cổng bằng biến môi trường `PORT` (ví dụ `PORT=7860`) và tắt auto-reload bằng `ENV=production`.

### Chạy bằng Docker

```bash
docker build -t rendezvous-tiebreak .
docker run -p 7860:7860 rendezvous-tiebreak
```

Sau đó truy cập **[http://localhost:7860](http://localhost:7860)**.

---

## 6. Tài liệu API (FastAPI Endpoints)

| Method | Endpoint | Mô tả |
| :--- | :--- | :--- |
| `GET` | `/` | Giao diện Web Playground tương tác |
| `GET` | `/api/health` | Kiểm tra trạng thái hoạt động (`{"status": "healthy", ...}`) |
| `GET` | `/api/sample-data` | Trả về 3 kịch bản mẫu (`saigon_outlier_conflict`, `hanoi_river_crossing`, `saigon_2_slots_chain`) |
| `POST` | `/api/tiebreak` | Tính toán tổ hợp địa điểm tối ưu, phân rã chi phí và dữ liệu đồ thị DAG |

### Ví dụ Payload `POST /api/tiebreak`

```json
{
  "participants": [
    { "id": "u1", "name": "Người 1", "lat": 10.8120, "lng": 106.6980 },
    { "id": "u2", "name": "Người 2", "lat": 10.7200, "lng": 106.7150 }
  ],
  "slots": [
    {
      "slot_id": "slot_1",
      "slot_name": "Chặng 1",
      "candidates": [
        { "id": "c1", "name": "Địa điểm 1.1", "lat": 10.8250, "lng": 106.6850 },
        { "id": "c2", "name": "Địa điểm 1.2", "lat": 10.7780, "lng": 106.6890 }
      ]
    }
  ],
  "penalty_exponent": 1.0,
  "fairness_factor": 0.5,
  "enable_osrm": true
}
```

---

## 7. Kiểm thử & Sinh dữ liệu Benchmark

Chạy toàn bộ **21 unit & integration tests** (kiểm tra công thức toán, đối sánh ngẫu nhiên giữa Layered DP và Brute-force, router/cache, service và FastAPI endpoints):

```bash
python -m unittest discover -s tiebreak_engine/tests -v
```

Sinh lại 20 kịch bản kiểm thử quy mô từ nhỏ đến lớn vào thư mục `scripts/data/`:

```bash
python scripts/generate_cases.py
```

---

## 8. Công nghệ sử dụng

- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, HTTPX
- **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3, LeafletJS
- **Bản đồ & Định tuyến:** OpenStreetMap Tiles, OSRM Public Routing API
- **Triển khai:** Docker, Render
