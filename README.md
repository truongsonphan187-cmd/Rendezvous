# Rendezvous — Ordered Median Tie-Break Engine

Web mô phỏng và tối ưu hóa công bằng đa tiêu chí cho bài toán chọn điểm hẹn nhóm (**Optimal Meeting Problem**) sử dụng mô hình **Ordered Median Problem (OMP)** kết hợp **Quy hoạch động đa tầng trên đồ thị DAG (Layered DP)**.

- **Live Demo (Render):** https://rendezvous-6brs.onrender.com/
- **Đặc tả kỹ thuật & toán học:** [docs/SPEC.md](docs/SPEC.md)

---

## Cấu trúc dự án

```text
.
├── README.md
├── requirements.txt             # Thư viện Python cho FastAPI & Solver
├── Dockerfile                   # Cấu hình đóng gói & deploy (Render / Docker)
├── docs/
│   └── SPEC.md                  # Tài liệu đặc tả mô hình toán học & kiến trúc
├── scripts/
│   ├── generate_cases.py        # Script sinh bộ test benchmark (20 cases)
│   └── data/                    # Dữ liệu test sinh ra (JSON / TXT)
└── tiebreak_engine/             # Mã nguồn chính của hệ thống
    ├── core/                    # Thuật toán lõi (thuần Python, không phụ thuộc framework)
    │   ├── itinerary_solver.py  # Quy hoạch động đa tầng (Layered DP on Multi-Stage DAG)
    │   ├── ordered_median.py    # Bộ tổng hợp thứ hạng Ordered Median (OMP)
    │   ├── router.py            # Tính khoảng cách đường bộ OSRM & dự phòng Haversine 1.35x
    │   └── scoring_formula.py   # Hàm phạt cá nhân (k) & trọng số thứ hạng (λ)
    ├── integration/             # Tầng dịch vụ & Pydantic schemas
    │   ├── schemas.py
    │   └── tie_break_service.py
    ├── playground/              # Web App mô phỏng tương tác (FastAPI + LeafletJS)
    │   ├── run_playground.py
    │   └── static/              # Frontend (index.html, style.css, app.js)
    └── tests/                   # Bộ kiểm thử tự động (21 unit & API tests)
```

---

## Khởi chạy cục bộ (Local)

```bash
# 1. Cài đặt dependencies
pip install -r requirements.txt

# 2. Chạy web server mô phỏng
python -m tiebreak_engine.playground.run_playground
```

Mở trình duyệt tại **[http://localhost:8080](http://localhost:8080)**.

---

## Chạy kiểm thử (Unit & API Tests)

```bash
python -m unittest discover -s tiebreak_engine/tests -v
```
