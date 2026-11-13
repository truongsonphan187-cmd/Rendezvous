"""
=============================================================================
MODULE: scoring_formula.py
MỤC ĐÍCH: Vùng Tùy Biến Công Thức Phạt & Trọng Số Ordered Median Dành Cho Dev.
=============================================================================
File này cô lập hoàn toàn các biểu thức toán học, tách biệt khỏi tầng mạng,
routing và cơ sở dữ liệu.

Khi muốn thay đổi hành vi ra quyết định của thuật toán:
  1. Chỉnh sửa hàm `compute_individual_penalty` để đổi cách phạt quãng đường cá nhân
     (ví dụ: tuyến tính bậc 1, lũy thừa bậc 1.5, hoặc bình phương bậc 2).
  2. Chỉnh sửa hàm `generate_ordered_median_weights` để cân đối giữa:
     - MinSum (tổng quãng đường cả nhóm ngắn nhất).
     - MinMax (ưu tiên bảo vệ người đi xa nhất - tính công bằng).
"""

from typing import List


def compute_individual_penalty(distance_km: float, penalty_exponent: float = 1.0) -> float:
    """
    TẦNG 1: Tính điểm phạt chi phí di chuyển cho từng cá nhân.

    Công thức:
        chi_phi = distance_km ^ penalty_exponent

    Tham số:
        distance_km (float): Tổng quãng đường khứ hồi (km).
        penalty_exponent (float): Hệ số lũy thừa k >= 1.0.
            - k = 1.0 : Chi phí tuyến tính (chuẩn Ordered Median Problem sách giáo khoa).
                        Đi 10 km tốn gấp đôi đi 5 km.
            - k = 1.5 : Phạt lũy thừa vừa phải cho các chặng đường xa.
            - k = 2.0 : Phạt bình phương (phạt cực nặng những ai phải đi quá xa).

    Trả về:
        float: Điểm phạt chi phí cá nhân (không thứ nguyên).
    """
    if distance_km <= 0.0:
        return 0.0

    # Đảm bảo hệ số k tối thiểu là 1.0 để không làm đảo ngược logic phạt
    exponent = max(1.0, float(penalty_exponent))
    return float(distance_km ** exponent)


def generate_ordered_median_weights(num_participants: int, fairness_factor: float = 0.5) -> List[float]:
    """
    TẦNG 2: Sinh vector trọng số thứ tự W = (w_1, ..., w_n) cho thuật toán Ordered Median.

    Các chi phí cá nhân được sắp xếp tăng dần: c_(1) <= c_(2) <= ... <= c_(n).
    w_1 áp dụng cho người đi gần nhất; w_n áp dụng cho người đi xa nhất.

    Tham số:
        num_participants (int): Số lượng thành viên tham gia (N).
        fairness_factor (float): Hệ số công bằng lambda trong đoạn [0.0, 2.0].
            - lambda = 0.0 : MinSum thuần túy (W = [1, 1, ..., 1]).
                             Tối ưu tổng quãng đường cho cả nhóm.
            - lambda = 1.0 : Ordered Median dung hòa.
                             Người đi xa nhất có tiếng nói lớn hơn trong hàm mục tiêu.
            - lambda = 2.0 : Ưu tiên công bằng cao (tiệm cận MinMax).
                             Người chịu thiệt nhiều nhất sẽ quyết định địa điểm thắng.

    Trả về:
        List[float]: Danh sách gồm N trọng số kiểu float.
    """
    if num_participants <= 0:
        return []
    if num_participants == 1:
        return [1.0]

    lambda_val = max(0.0, float(fairness_factor))
    weights: List[float] = []

    for rank in range(num_participants):
        # Thứ hạng chuẩn hóa từ 0 (gần nhất) đến 1 (xa nhất)
        relative_rank = rank / (num_participants - 1)
        # Tăng trọng số tuyến tính theo thứ hạng
        w = 1.0 + (lambda_val * relative_rank)
        weights.append(round(w, 4))

    return weights
