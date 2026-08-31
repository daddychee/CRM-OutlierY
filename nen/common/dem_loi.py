# -*- coding: utf-8 -*-
"""Trạm đo lỗi app qua gateway (B2 giám sát, 31/08/2026).

Mọi request app đi qua proxy chuyen_tiep — đó là chỗ đo tự nhiên: app trả 5xx,
cổng chết (502), timeout (504) đều ghi nhận Ở ĐÂY theo CỔNG (1-1 với app trong
hợp đồng apps.json), không đoán slug từ đường dẫn. Trang Applications đọc
tom_tat() để hiện "N lỗi / M request (5 phút)" + lỗi gần nhất.

Bộ đếm TRONG BỘ NHỚ (đủ cho LAN 1 worker — khuôn _TAC_VU; restart là về 0,
giới hạn đã biết); vết BỀN ghi JSON-lines qua nhat_ky (app="gateway") có trần
mỗi cửa sổ chống bão 5xx làm ngập đĩa.

ponytail: không khóa — gateway 1 event loop, mọi lời gọi từ coroutine cùng loop.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from nen.common import nhat_ky

CUA_SO = 300.0        # giây — cửa sổ trượt 5 phút
TRAN_GHI_DIA = 60     # dòng nhật ký đĩa tối đa mỗi cổng mỗi cửa sổ (chống bão)

_gio = time.time      # tách ra để test tua đồng hồ
_YEU_CAU: dict[int, deque] = defaultdict(deque)            # [ts, ...]
_LOI: dict[int, deque] = defaultdict(lambda: deque(maxlen=500))  # [(ts, status, duong)]
_GHI_DIA: dict[int, deque] = defaultdict(deque)            # ts các dòng đã xuống đĩa


def _don(dq: deque, bay_gio: float, lay_ts=lambda x: x) -> None:
    while dq and lay_ts(dq[0]) < bay_gio - CUA_SO:
        dq.popleft()


def ghi_yeu_cau(cong: int) -> None:
    dq = _YEU_CAU[cong]
    dq.append(_gio())
    _don(dq, dq[-1])


def ghi_loi(cong: int, status: int, duong: str, ghi_chu: str = "") -> None:
    bay_gio = _gio()
    _LOI[cong].append((bay_gio, status, duong))
    dia = _GHI_DIA[cong]
    _don(dia, bay_gio)
    if len(dia) < TRAN_GHI_DIA:
        dia.append(bay_gio)
        try:
            nhat_ky.ghi("gateway", "he-thong", "loi_app",
                        f"cong={cong} status={status} duong={duong}"
                        + (f" ({ghi_chu})" if ghi_chu else ""))
        except OSError:
            pass  # đĩa hỏng không được giết proxy — bộ đếm RAM vẫn đủ


def tom_tat() -> dict[int, dict]:
    """{cong: {yeu_cau, loi, gan_nhat{luc,status,duong}|None}} trong cửa sổ."""
    bay_gio = _gio()
    ket: dict[int, dict] = {}
    for cong in set(_YEU_CAU) | set(_LOI):
        yc = _YEU_CAU[cong]
        _don(yc, bay_gio)
        loi = [x for x in _LOI[cong] if x[0] >= bay_gio - CUA_SO]
        gan = None
        if loi:
            ts, status, duong = loi[-1]
            gan = {"luc": time.strftime("%H:%M:%S", time.localtime(ts)),
                   "status": status, "duong": duong}
        ket[cong] = {"yeu_cau": len(yc), "loi": len(loi), "gan_nhat": gan}
    return ket


def xoa_het() -> None:
    """Cho test — mỗi ca một trạng thái sạch."""
    _YEU_CAU.clear()
    _LOI.clear()
    _GHI_DIA.clear()
