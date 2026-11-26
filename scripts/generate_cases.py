import json
import math
import random
from pathlib import Path
from typing import Any

# Tọa độ tương đối (km) của các cụm quận/khu vực thực tế tại TP.HCM
HCMC_CLUSTERS = [
    ("Quan 1 - Ben Thanh", 0.0, 0.0),
    ("Quan 3 - Ho Con Rua", -1.3, 1.0),
    ("Quan 5 - Nguyen Van Cu", -3.5, -2.2),
    ("Quan 10 - Su Van Hanh", -3.1, -0.4),
    ("Binh Thanh - Hang Xanh", 2.0, 2.4),
    ("Phu Nhuan - Phan Xich Long", -0.7, 2.7),
    ("Thao Dien - Thu Duc", 5.2, 1.8),
    ("Linh Trung - Thu Duc", 11.5, 8.2),
    ("Quan 7 - Phu My Hung", 1.8, -6.5),
    ("Tan Binh - Cong Hoa", -4.8, 3.6),
    ("Go Vap - Phan Van Tri", -1.8, 6.8),
    ("Quan 4 - Vinh Khanh", 1.1, -1.8),
]

# Cấu hình 20 test cases phân tầng từ nhỏ -> trung bình -> lớn -> biên
CASE_CONFIGS = [
    (3, 2, [2, 2]),
    (4, 3, [3, 2, 3]),
    (2, 4, [2, 3, 2, 2]),
    (5, 2, [4, 3]),
    (6, 3, [3, 4, 3]),
    (4, 5, [2, 3, 4, 2, 3]),
    (7, 4, [4, 3, 5, 3]),
    (5, 6, [3, 2, 4, 3, 2, 3]),
    (8, 3, [5, 6, 4]),
    (6, 7, [2, 4, 3, 5, 2, 4, 3]),
    (9, 5, [4, 5, 6, 4, 5]),
    (7, 8, [3, 4, 5, 3, 4, 6, 3, 4]),
    (10, 6, [6, 7, 5, 8, 6, 5]),
    (8, 9, [4, 5, 6, 7, 4, 5, 6, 5, 4]),
    (11, 7, [7, 8, 6, 9, 7, 8, 6]),
    (9, 10, [5, 6, 7, 8, 5, 6, 7, 8, 6, 5]),
    (12, 8, [8, 9, 7, 10, 8, 9, 7, 8]),
    (10, 11, [6, 7, 8, 9, 10, 6, 7, 8, 9, 7, 6]),
    (12, 1, [12]),
    (12, 12, [10, 11, 12, 10, 12, 11, 10, 12, 11, 10, 12, 12]),
]


def sample_point(
    rng: random.Random, active_clusters: list[tuple[str, float, float]]
) -> tuple[str, float, float]:
    name, cx, cy = rng.choice(active_clusters)
    # Độ lệch bán kính trong nội khu (0.2km - 1.5km)
    dx = rng.gauss(0.0, 0.75)
    dy = rng.gauss(0.0, 0.75)
    return name, round(cx + dx, 3), round(cy + dy, 3)


def generate_dataset(seed: int = 2026) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    dataset = []

    for case_idx, (num_people, num_stages, options_per_stage) in enumerate(
        CASE_CONFIGS, start=1
    ):
        # Chọn ngẫu nhiên 3 đến 8 cụm quận hoạt động cho mỗi case để tạo tính cục bộ thực tế
        k_clusters = min(len(HCMC_CLUSTERS), rng.randint(3, 8))
        active_clusters = rng.sample(HCMC_CLUSTERS, k_clusters)

        vertices = []
        # 1. Tạo đỉnh người xuất phát (0 .. P-1)
        for p in range(num_people):
            district, x, y = sample_point(rng, active_clusters)
            vertices.append(
                {
                    "index": len(vertices),
                    "id": f"U{p + 1}",
                    "role": "person",
                    "stage": 0,
                    "option": p + 1,
                    "district": district,
                    "coords": [x, y],
                }
            )

        # 2. Tạo đỉnh các options theo từng chặng nối tiếp
        for s_idx, num_opts in enumerate(options_per_stage, start=1):
            for o_idx in range(1, num_opts + 1):
                district, x, y = sample_point(rng, active_clusters)
                vertices.append(
                    {
                        "index": len(vertices),
                        "id": f"S{s_idx}_O{o_idx}",
                        "role": "venue_option",
                        "stage": s_idx,
                        "option": o_idx,
                        "district": district,
                        "coords": [x, y],
                    }
                )

        total_v = len(vertices)
        dist_matrix = [[0.0] * total_v for _ in range(total_v)]

        # 3. Sinh ma trận khoảng cách đầy đủ giữa mọi cặp đỉnh (u, v)
        for i in range(total_v):
            x1, y1 = vertices[i]["coords"]
            for j in range(i + 1, total_v):
                x2, y2 = vertices[j]["coords"]
                euclidean = math.hypot(x2 - x1, y2 - y1)

                # Hệ số uốn lượn đường phố thực tế (1.22 -> 1.42)
                tortuosity = rng.uniform(1.22, 1.42)
                base_road_dist = max(0.3, euclidean * tortuosity)

                # Bất đối xứng đường một chiều nhẹ giữa chiều đi và chiều về
                asym_forward = rng.uniform(0.97, 1.05)
                asym_backward = rng.uniform(0.97, 1.05)

                dist_matrix[i][j] = round(base_road_dist * asym_forward, 2)
                dist_matrix[j][i] = round(base_road_dist * asym_backward, 2)

        dataset.append(
            {
                "case_id": case_idx,
                "num_people": num_people,
                "num_stages": num_stages,
                "options_per_stage": options_per_stage,
                "total_vertices": total_v,
                "vertices": vertices,
                "dist_matrix": dist_matrix,
            }
        )

    return dataset


def export_files(dataset: list[dict[str, Any]]) -> None:
    out_dir = Path(__file__).resolve().parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hangout_20_cases.json"
    txt_path = out_dir / "hangout_20_cases.txt"

    # Xuất JSON đầy đủ
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(dataset, f_json, ensure_ascii=False, indent=2)

    # Xuất TXT ma trận kề thuần số cho C++/Python thuật toán
    with open(txt_path, "w", encoding="utf-8") as f_txt:
        f_txt.write(f"{len(dataset)}\n")
        for case in dataset:
            f_txt.write(f"\n# CASE {case['case_id']} (V={case['total_vertices']})\n")
            f_txt.write(f"{case['num_people']} {case['num_stages']}\n")
            f_txt.write(" ".join(map(str, case["options_per_stage"])) + "\n")
            for row in case["dist_matrix"]:
                f_txt.write(" ".join(f"{val:.2f}" for val in row) + "\n")


if __name__ == "__main__":
    data = generate_dataset(seed=2026)
    export_files(data)
    print(
        f"Generated {len(data)} cases -> scripts/data/hangout_20_cases.json & hangout_20_cases.txt"
    )
