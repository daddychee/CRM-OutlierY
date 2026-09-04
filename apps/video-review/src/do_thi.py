# -*- coding: utf-8 -*-
"""Đọc đường cong giữ chân từ ẢNH CHỤP YouTube Studio.

Vì sao đọc từ ảnh: Studio KHÔNG cho export đường cong (chỉ export được số liệu
cấp video/kênh), còn YouTube Analytics API thì phải OAuth — user chốt không đấu
OAuth vào hạ tầng. Nên anh chụp màn hình, máy dò toạ độ.

Cách dò: đường "Video này" của Studio là màu xanh lam, dải "thông thường" là xám.
Tách bằng độ lệch kênh xanh - đỏ nên không nhầm hai đường với nhau.

ĐÂY LÀ SỐ SUY RA, KHÔNG PHẢI SỐ GỐC. Dùng để tìm CHỖ TỤT, không phải để tuyên bố
con số tuyệt đối. Luôn neo lại bằng 3 số người dùng đọc trên Studio; lệch quá
NGUONG_NEO thì từ chối, đòi chụp lại — thà không có còn hơn có số sai.
"""
from __future__ import annotations

import json
from pathlib import Path

NGUONG_NEO = 3.0          # điểm phần trăm; lệch hơn thế là ảnh không đọc được
SO_DIEM = 100             # quy về 100 điểm, mỗi điểm 1% độ dài video


def _numpy():
    import numpy as np
    return np


def doc_duong_cong(duong_anh: Path) -> list[float] | None:
    """Ảnh → danh sách SO_DIEM giá trị 0..100. None nếu không thấy đường xanh."""
    try:
        from PIL import Image
    except ImportError:
        return None
    np = _numpy()
    try:
        im = Image.open(duong_anh).convert("RGB")
    except OSError:
        return None
    a = np.asarray(im).astype(int)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mask = (B - R > 40) & (B > 90) & (G > R)
    ys, xs = np.nonzero(mask)
    if len(xs) < 50:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    if x1 - x0 < 40:
        return None
    cot: dict[int, float] = {}
    for x in range(x0, x1 + 1):
        c = ys[xs == x]
        if len(c):
            cot[x] = float(c.mean())
    if len(cot) < (x1 - x0) * 0.5:
        return None
    y_tren, y_duoi = _khung_doc(cot, a.shape[0])
    if y_duoi <= y_tren:
        return None
    ra = []
    for i in range(SO_DIEM):
        x = x0 + (x1 - x0) * i / (SO_DIEM - 1)
        y = _noi_suy(cot, x)
        pt = (y_duoi - y) / (y_duoi - y_tren) * 100.0
        ra.append(max(0.0, min(100.0, pt)))
    return ra


def _khung_doc(cot: dict[int, float], cao_anh: int) -> tuple[float, float]:
    """Mép trên = điểm cao nhất của đường (retention đầu video ~100%);
    mép dưới = đáy vùng vẽ, suy từ điểm thấp nhất cộng lề."""
    ys = list(cot.values())
    y_tren = min(ys)
    y_duoi = max(ys)
    # đường cuối video hiếm khi chạm 0 — chừa lề theo tỉ lệ chiều cao vùng vẽ
    return y_tren, y_duoi + (y_duoi - y_tren) * 0.06


def _noi_suy(cot: dict[int, float], x: float) -> float:
    lo = int(x)
    if lo in cot:
        return cot[lo]
    gan = sorted(cot.keys(), key=lambda k: abs(k - x))[:2]
    return sum(cot[k] for k in gan) / len(gan)


def neo_bang_so_that(cong: list[float], hook_30: float, thoi_luong: float) -> dict:
    """Chỉnh trục bằng số NGƯỜI ĐỌC trên Studio, và bắt lỗi khi ảnh mờ.

    hook_30 là % còn lại ở giây 30 — điểm đó trên đường cong phải khớp. Lệch quá
    NGUONG_NEO nghĩa là ảnh đọc sai (mờ, bị che, cắt cúp), trả đạt=False để giao
    diện đòi chụp lại thay vì im lặng dùng số sai.
    """
    if not cong or thoi_luong <= 0 or hook_30 is None:
        return {"dat": False, "ly_do": "thiếu dữ liệu để neo"}
    pt = 30.0 / thoi_luong * 100.0
    if pt >= SO_DIEM:
        return {"dat": False, "ly_do": "video ngắn hơn 30 giây"}
    doc = _diem_tai(cong, pt)
    lech = doc - hook_30
    if abs(lech) > NGUONG_NEO:
        return {"dat": False, "lech": lech, "doc_duoc": doc,
                "ly_do": f"ảnh đọc ra {doc:.1f}% ở giây 30 nhưng số anh nhập là "
                         f"{hook_30:.1f}% — lệch {abs(lech):.1f} điểm"}
    he_so = hook_30 / doc if doc > 0 else 1.0
    return {"dat": True, "lech": lech, "doc_duoc": doc,
            "cong": [round(min(100.0, v * he_so), 2) for v in cong]}


def _diem_tai(cong: list[float], pt: float) -> float:
    pt = max(0.0, min(float(len(cong) - 1), pt))
    lo = int(pt)
    hi = min(lo + 1, len(cong) - 1)
    t = pt - lo
    return cong[lo] * (1 - t) + cong[hi] * t


def tim_cho_tut(cong: list[float], thoi_luong: float, top: int = 3) -> list[dict]:
    """Các quãng tụt mạnh bất thường so với chính video đó.

    Đường giữ chân luôn dốc, nên không dùng ngưỡng cứng: so độ dốc từng quãng với
    độ dốc TRUNG VỊ của chính video này. Bỏ qua quãng còn quá ít khán giả — mẫu
    mỏng thì không kết luận.
    """
    if len(cong) < 10 or thoi_luong <= 0:
        return []
    doc = [max(0.0, cong[i] - cong[i + 1]) for i in range(len(cong) - 1)]
    thu = sorted(doc)
    trung_vi = thu[len(thu) // 2] or 0.01
    ra = []
    i = 0
    while i < len(doc):
        if doc[i] > max(trung_vi * 2.5, 0.8):
            j = i
            while j + 1 < len(doc) and doc[j + 1] > trung_vi * 1.5:
                j += 1
            mat = cong[i] - cong[min(j + 1, len(cong) - 1)]
            ra.append({
                "tu_giay": i / (len(cong) - 1) * thoi_luong,
                "den_giay": min(j + 1, len(cong) - 1) / (len(cong) - 1) * thoi_luong,
                "mat_diem": round(mat, 1),
                "con_lai": round(cong[min(j + 1, len(cong) - 1)], 1)})
            i = j + 1
        else:
            i += 1
    ra.sort(key=lambda d: -d["mat_diem"])
    return ra[:top]


def dong_goi(cong: list[float]) -> str:
    return json.dumps([round(v, 2) for v in cong], ensure_ascii=False)


def mo_goi(chu: str) -> list[float]:
    try:
        return [float(v) for v in json.loads(chu or "[]")]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
