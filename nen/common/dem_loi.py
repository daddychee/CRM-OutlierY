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
_MS: dict[int, deque] = defaultdict(lambda: deque(maxlen=2000))  # [(ts, ms)] — latency
_LOI: dict[int, deque] = defaultdict(lambda: deque(maxlen=500))  # [(ts, status, duong)]
_NUT: dict[int, deque] = defaultdict(lambda: deque(maxlen=200))  # nút chết: POST 404/405
_GHI_DIA: dict[int, deque] = defaultdict(deque)            # ts các dòng đã xuống đĩa


def _don(dq: deque, bay_gio: float, lay_ts=lambda x: x) -> None:
    while dq and lay_ts(dq[0]) < bay_gio - CUA_SO:
        dq.popleft()


def ghi_yeu_cau(cong: int, ms: float | None = None) -> None:
    """Đếm request; kèm ms (TTFB đo tại proxy, P1 01/09) thì nuôi luôn p50/p95.
    Chỗ chưa đo gọi không ms vẫn đếm được (tương thích ngược)."""
    bay_gio = _gio()
    dq = _YEU_CAU[cong]
    dq.append(bay_gio)
    _don(dq, bay_gio)
    if ms is not None:
        _MS[cong].append((bay_gio, ms))


def ghi_nut_chet(cong: int, status: int, duong: str) -> None:
    """NÚT CHẾT runtime (P1): người dùng bấm nút mà server trả 404/405 cho
    POST/PUT/DELETE — UI↔server lệch. Đếm RIÊNG, không trộn 'loi' 5xx (bệnh
    khác nhau); vết bền đi chung kênh nhật ký."""
    bay_gio = _gio()
    _NUT[cong].append((bay_gio, status, duong))
    try:
        nhat_ky.ghi("gateway", "he-thong", "nut_chet",
                    f"cong={cong} status={status} duong={duong}")
    except OSError:
        pass


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


def _bach_phan(vals: list[float], q: float) -> float:
    vals = sorted(vals)
    return vals[int(q * (len(vals) - 1))]


def _moi_nhat(ds: list) -> dict | None:
    if not ds:
        return None
    ts, status, duong = ds[-1]
    return {"luc": time.strftime("%H:%M:%S", time.localtime(ts)),
            "status": status, "duong": duong}


def tom_tat() -> dict[int, dict]:
    """{cong: {yeu_cau, loi, nut_chet, p50, p95, gan_nhat, nut_chet_gan_nhat}}
    trong cửa sổ; không có số đo → None (không bịa 0)."""
    bay_gio = _gio()
    ket: dict[int, dict] = {}
    for cong in set(_YEU_CAU) | set(_LOI) | set(_NUT):
        yc = _YEU_CAU[cong]
        _don(yc, bay_gio)
        loi = [x for x in _LOI[cong] if x[0] >= bay_gio - CUA_SO]
        nut = [x for x in _NUT[cong] if x[0] >= bay_gio - CUA_SO]
        ms = [m for ts, m in _MS[cong] if ts >= bay_gio - CUA_SO]
        theo_loai: dict[str, int] = {}
        for _ts, status, _d in loi:
            nhan = str(status) if status in (502, 504) else "5xx"
            theo_loai[nhan] = theo_loai.get(nhan, 0) + 1
        ket[cong] = {"yeu_cau": len(yc), "loi": len(loi), "nut_chet": len(nut),
                     "p50": round(_bach_phan(ms, 0.5)) if ms else None,
                     "p95": round(_bach_phan(ms, 0.95)) if ms else None,
                     "theo_loai": theo_loai,
                     "gan_nhat": _moi_nhat(loi),
                     "nut_chet_gan_nhat": _moi_nhat(nut)}
    return ket


def xoa_het() -> None:
    """Cho test — mỗi ca một trạng thái sạch."""
    _YEU_CAU.clear()
    _MS.clear()
    _LOI.clear()
    _NUT.clear()
    _GHI_DIA.clear()
