# -*- coding: utf-8 -*-
"""Khuôn sức khỏe SÂU của app (B1 giám sát, 31/08/2026).

Hợp đồng 2 tầng: `health` (liveness — sống/chết) giữ nguyên; app muốn khai
trạng thái TỪNG MODULE thì thêm trường `suc_khoe` vào apps.json trỏ tới một
endpoint trả đúng khuôn `bao_cao(...)` dưới đây. App không khai → tầng nền
đối xử như cũ, không có luật mới.

Nguyên tắc (van chống bịa cho GIÁM SÁT): check nổ exception là DỮ LIỆU
("loi" + lý do), không bao giờ được giết endpoint sức khỏe — trang giám sát
mà 500 thì chính nó thành điểm mù.
"""
from __future__ import annotations

from typing import Callable, Iterable

# thứ tự = độ nặng; gộp lấy mức xấu nhất
MUC = ("ok", "canh_bao", "loi")


def gop_trang_thai(mo_dun: Iterable[dict]) -> str:
    xau_nhat = 0
    for m in mo_dun:
        xau_nhat = max(xau_nhat, MUC.index(m.get("trang_thai", "loi")))
    return MUC[xau_nhat]


def bao_cao(app: str, phien_ban: str,
            cac_kiem: Iterable[tuple[str, Callable[[], tuple[str, str]]]]) -> dict:
    """Chạy lần lượt các kiểm (ten, ham); ham() -> (trang_thai, chi_tiet).

    Ham raise → module đó 'loi' kèm tên exception; trạng thái lạ ngoài MUC →
    'loi' (khai bừa không được vỡ lặng lẽ ở tầng render). Trả dict đúng khuôn
    mà gateway _do_dich_vu đọc.
    """
    mo_dun = []
    for ten, ham in cac_kiem:
        try:
            trang_thai, chi_tiet = ham()
            if trang_thai not in MUC:
                trang_thai, chi_tiet = "loi", (
                    f"check trả trạng thái lạ {trang_thai!r} — {chi_tiet}")
        except Exception as e:  # noqa: BLE001 — mọi lỗi check đều là dữ liệu
            trang_thai, chi_tiet = "loi", f"{type(e).__name__}: {e}"
        mo_dun.append({"ten": ten, "trang_thai": trang_thai, "chi_tiet": chi_tiet})
    return {"app": app, "phien_ban": phien_ban,
            "trang_thai": gop_trang_thai(mo_dun), "mo_dun": mo_dun}
