"""Danh mục THỊ TRƯỜNG + NGÁCH từ đế OUTLIERY (danh bạ) qua gateway loopback.

Pool-theo-thị-trường (user chốt 18/08 — docs/RADARY_THI_TRUONG.md): mỗi
workspace gắn MỘT ngách + MỘT thị trường thuộc ngách đó; danh mục đối chiếu từ
General › Niches — radary KHÔNG tự đẻ sổ phân loại (DE.md luật 2). Khuôn
khoa_v3: lỗi nói rõ bằng RuntimeError, không nuốt, không fallback sổ nội bộ.
Cache 60s trong tiến trình: form/list gọi dày, danh mục đổi rất thưa.
"""
import json
import os
import time
import urllib.request

_cache: dict = {}          # duong -> (ts, du_lieu)
TTL_S = 60.0


def _doc(duong: str, lam_moi=False):
    ts, ds = _cache.get(duong, (0.0, None))
    if not lam_moi and ds is not None and time.time() - ts < TTL_S:
        return ds
    goc = os.environ.get('GATEWAY_URL', 'http://127.0.0.1:9000')
    try:
        with urllib.request.urlopen(f'{goc}{duong}', timeout=5) as r:
            ds = json.load(r)
    except Exception as e:
        raise RuntimeError(
            f'chưa lấy được danh mục từ OUTLIERY ({e.__class__.__name__}) '
            '— kiểm gateway 9000 đang chạy + ngách/thị trường đã khai ở General › Niches'
        ) from None
    _cache[duong] = (time.time(), ds)
    return ds


def danh_sach(lam_moi=False) -> list[dict]:
    """Thị trường: [{ma, ten, ngon_ngu}]. RuntimeError thông điệp rõ khi không lấy được."""
    return _doc('/api/danh-ba/thi-truong', lam_moi)


def ds_ngach(lam_moi=False) -> list[dict]:
    """Ngách: [{ma, ten, thi_truong: [TT-xx...]}] — tập thị trường do user chọn
    ở General (ngách mới = 0 thị trường, không có mặc định)."""
    return _doc('/api/danh-ba/ngach', lam_moi)


def hop_le(ma: str) -> bool:
    """Mã thị trường có trong danh mục đế không — validation, lỗi gateway NỔI LÊN."""
    return any(t.get('ma') == ma for t in danh_sach())


def ten_cua(ma: str) -> str:
    """Tên hiển thị của mã thị trường — best-effort: gateway chết trả mã trần
    (chỉ phục vụ hiển thị, danh sách workspace không được chết theo gateway)."""
    if not ma:
        return ''
    try:
        for t in danh_sach():
            if t.get('ma') == ma:
                return t.get('ten') or ma
    except RuntimeError:
        pass
    return ma
