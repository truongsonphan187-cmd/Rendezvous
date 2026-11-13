"""
=============================================================================
MODULE: ordered_median.py
MỤC ĐÍCH: Hiện thực Bộ Tổng Hợp Ordered Median Problem (OMP).
=============================================================================
Nhận vào N chi phí cá nhân và N trọng số thứ tự:
  1. Xác định hoán vị sắp xếp tăng dần của chi phí: c_(1) <= c_(2) <= ... <= c_(N).
  2. Tính tích vô hướng (dot product) giữa chi phí đã sắp xếp và vector trọng số w.
  3. Trả về tổng điểm phạt mục tiêu (Psi) kèm siêu dữ liệu xếp hạng chi tiết.
"""

from typing import List, Dict, Any, Tuple


class OrderedMedianResult:
    """Đóng gói kết quả tính toán của bộ lọc Ordered Median."""
    def __init__(
        self,
        total_penalty: float,
        sorted_costs: List[float],
        applied_weights: List[float],
        rank_to_original_index: List[int],
    ):
        self.total_penalty = total_penalty
        self.sorted_costs = sorted_costs
        self.applied_weights = applied_weights
        self.rank_to_original_index = rank_to_original_index

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_penalty": round(self.total_penalty, 4),
            "sorted_costs": [round(c, 4) for c in self.sorted_costs],
            "applied_weights": self.applied_weights,
            "rank_to_original_index": self.rank_to_original_index,
        }


def compute_ordered_median(
    individual_costs: List[float],
    rank_weights: List[float],
) -> OrderedMedianResult:
    """
    Thực thi hàm mục tiêu Ordered Median.

    Công thức:
        Psi = sum(w_j * c_(j) với j từ 1..N)
        trong đó c_(1) <= c_(2) <= ... <= c_(N)

    Tham số:
        individual_costs (List[float]): Danh sách chi phí phạt chưa sắp xếp của từng bạn.
        rank_weights (List[float]): Vector trọng số thứ hạng (thường tăng dần theo rank).

    Trả về:
        OrderedMedianResult: Đối tượng chứa điểm tổng kết và chi tiết xếp hạng.

    Báo lỗi:
        ValueError: Nếu độ dài danh sách chi phí và trọng số không khớp nhau hoặc rỗng.
    """
    n = len(individual_costs)
    if n == 0:
        return OrderedMedianResult(0.0, [], [], [])

    if len(rank_weights) != n:
        raise ValueError(
            f"Lỗi lệch kích thước: Nhận được {n} chi phí cá nhân nhưng có {len(rank_weights)} trọng số rank."
        )

    # Ghép cặp chi phí với vị trí gốc ban đầu: (chi phí, chỉ số gốc)
    indexed_costs = list(enumerate(individual_costs))
    # Sắp xếp tăng dần theo chi phí: c_(1) <= c_(2) <= ... <= c_(N)
    indexed_costs.sort(key=lambda item: item[1])

    sorted_costs: List[float] = []
    rank_to_original_index: List[int] = []
    total_penalty = 0.0

    for rank, (orig_idx, cost) in enumerate(indexed_costs):
        weight = rank_weights[rank]
        sorted_costs.append(cost)
        rank_to_original_index.append(orig_idx)
        total_penalty += cost * weight

    return OrderedMedianResult(
        total_penalty=total_penalty,
        sorted_costs=sorted_costs,
        applied_weights=rank_weights,
        rank_to_original_index=rank_to_original_index,
    )
