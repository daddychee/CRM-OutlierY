"""S2 — Phát hiện đỉnh Most Replayed. Thuần tính toán, không mạng (test bằng heatmap giả).

Thuật toán (METHODOLOGY §S2):
1. Bỏ ~5% bucket đầu (artifact "ai cũng xem từ đầu").
2. Đỉnh = local maximum có prominence z ≥ ngưỡng, z tính TƯƠNG ĐỐI theo phân bố của
   CHÍNH video đó (không so intensity tuyệt đối giữa hai video).
3. Cửa sổ transcript quanh đỉnh co giãn theo độ dài video: max(±45s, ±1.5 bucket).
4. Lọc `navigation` (đỉnh trùng mốc chapter) làm ở lớp Python nếu có chapters; video này
   không có chapters nên bước đó tự bỏ qua — quyết định value/confusion để S3 (LLM) lo.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean, pstdev

from .heatmap import Bucket

DROP_HEAD_FRAC = 0.05      # bỏ 5% bucket đầu
Z_THRESHOLD = 1.0          # prominence tối thiểu (z so với chính video)
WINDOW_SEC_MIN = 45.0      # nửa cửa sổ tối thiểu (giây)
WINDOW_BUCKET_MULT = 1.5   # hoặc 1.5 bucket, lấy cái lớn hơn
CHAPTER_TOL_BUCKETS = 1.0  # đỉnh cách mốc chapter ≤ 1 bucket => navigation


@dataclass(frozen=True)
class Peak:
    idx: int              # chỉ số bucket
    t_start: float        # cửa sổ transcript quanh đỉnh
    t_end: float
    t_center: float       # tâm bucket đỉnh
    intensity: float      # value gốc của bucket
    intensity_z: float    # z so với phân bố (sau khi bỏ head)
    is_navigation: bool   # trùng mốc chapter (nếu biết chapters)

    def as_dict(self) -> dict:
        return asdict(self)


def _bucket_len(buckets: list[Bucket]) -> float:
    return mean(b.end - b.start for b in buckets)


def detect_peaks(
    buckets: list[Bucket],
    *,
    chapter_starts: list[float] | None = None,
    z_threshold: float = Z_THRESHOLD,
) -> list[Peak]:
    """Trả danh sách đỉnh, sắp theo intensity_z giảm dần.

    chapter_starts: giây bắt đầu các chapter (nếu video có) để đánh dấu navigation.
    """
    n = len(buckets)
    if n < 5:
        return []

    blen = _bucket_len(buckets)
    head_cut = int(round(n * DROP_HEAD_FRAC))
    body = buckets[head_cut:]                       # vùng xét đỉnh
    vals = [b.value for b in body]

    mu = mean(vals)
    sigma = pstdev(vals)
    if sigma == 0:
        return []

    half_win = max(WINDOW_SEC_MIN, WINDOW_BUCKET_MULT * blen)
    total_end = buckets[-1].end
    chapters = chapter_starts or []

    peaks: list[Peak] = []
    for j, b in enumerate(body):
        left = body[j - 1].value if j > 0 else float("-inf")
        right = body[j + 1].value if j < len(body) - 1 else float("-inf")
        if not (b.value >= left and b.value >= right):
            continue                                # không phải local max
        z = (b.value - mu) / sigma
        if z < z_threshold:
            continue

        center = (b.start + b.end) / 2
        is_nav = any(abs(center - cs) <= CHAPTER_TOL_BUCKETS * blen for cs in chapters)
        peaks.append(Peak(
            idx=head_cut + j,
            t_start=max(0.0, center - half_win),
            t_end=min(total_end, center + half_win),
            t_center=round(center, 2),
            intensity=round(b.value, 4),
            intensity_z=round(z, 3),
            is_navigation=is_nav,
        ))

    peaks.sort(key=lambda p: p.intensity_z, reverse=True)
    return peaks
