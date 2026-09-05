# -*- coding: utf-8 -*-
"""GĐ3 — LƯỚI CHẶN mìn "dịch vai bằng so khớp CHUỖI CON" (05/09/2026).

BỐI CẢNH (rà 05/09, sổ `docs/bao-mat-internet.md` mục G6): `iam.vai_cho_app`
dịch hành động → vai bằng SO KHỚP CHUỖI CON:
    if ("xoa" in ma or "toan_quyen" in ma) -> vai_xoa
    if any(t in ma for t in ("sua","tao","them")) -> leader

KIỂM TRA THẬT 05/09 — ba mã khớp chuỗi con mà không bằng chính xác:
  - `tao_pool`   (radary) chứa "tao"  → leader. **ĐÚNG Ý ĐỒ**: mô tả trong
    phan_quyen.json ghi rõ "(vai leader)".
  - `them_video` (radary) chứa "them" → leader. **ĐÚNG Ý ĐỒ**, mô tả ghi rõ.
  - `vai_xoa`    chứa "xoa" nhưng KHÔNG phải hành động — đã được
    `hanh_dong_cua_app` lọc ra (chỉ nhận mục có khóa "nhan").
→ HIỆN TẠI KHÔNG CÓ MÌN NÀO ĐANG NỔ. Nên KHÔNG đổi cách dịch vai (đổi là rủi ro
thật cho hành vi đang đúng), mà DỰNG LƯỚI này để mìn tương lai bị chặn ngay.

Đối chiếu làm ĐÚNG: `apps/plannery/server.py:_vai_tu_actions` dùng so khớp TẬP
HỢP CHÍNH XÁC → không dính bẫy. Nếu sau này gộp về một khuôn, dùng khuôn đó.
"""
import json
import io
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
LUAT = GOC / "nen" / "rules" / "phan_quyen.json"

TU_XOA = ("xoa", "toan_quyen")
TU_SUA = ("sua", "tao", "them")

# Mã ĐÃ RÀ 05/09 và xác nhận việc nâng vai là ĐÚNG Ý ĐỒ (mô tả trong luật ghi rõ).
DA_DUYET = {"tao_pool", "them_video"}


def _ma_hanh_dong_that() -> set[str]:
    """Chỉ mục có khóa 'nhan' mới là hành động thật (khuôn hanh_dong_cua_app)."""
    d = json.load(io.open(LUAT, encoding="utf-8-sig"))
    ra = set()
    for app in (d.get("apps") or {}).values():
        for ma, dk in (app or {}).items():
            if isinstance(dk, dict) and "nhan" in dk:
                ra.add(ma)
    return ra


def test_khong_co_ma_moi_vo_tinh_duoc_nang_vai():
    """Thêm hành động tên như 'xem_lich_su_xoa' hay 'thematic' là THĂNG QUYỀN
    LẶNG LẼ. Test này bắt ngay lúc thêm, trước khi lên hệ thật."""
    pham = []
    for ma in _ma_hanh_dong_that():
        if ma in DA_DUYET or ma in TU_XOA or ma in TU_SUA:
            continue
        hit = [t for t in TU_XOA + TU_SUA if t in ma]
        if hit:
            pham.append(f"{ma} (chứa {hit})")
    assert not pham, (
        "Mã hành động mới khớp CHUỖI CON nên bị nâng vai ngoài ý muốn:\n  "
        + "\n  ".join(pham)
        + "\n→ Đổi tên mã, hoặc thêm vào DA_DUYET nếu việc nâng vai là CÓ CHỦ ĐÍCH."
    )


def test_vai_xoa_khong_bi_coi_la_hanh_dong():
    """`vai_xoa` là KHÓA CẤU HÌNH, không phải hành động — nếu lọt vào danh sách
    hành động thì mọi app khai nó sẽ nâng vai sai."""
    assert "vai_xoa" not in _ma_hanh_dong_that()
