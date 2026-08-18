"""Danh mục THỊ TRƯỜNG từ đế OUTLIERY (danh bạ) qua gateway loopback.

Pool-theo-thị-trường (user chốt 18/08 — docs/RADARY_THI_TRUONG.md): mỗi
workspace gắn ĐÚNG MỘT thị trường, danh mục đối chiếu từ General › Niches —
radary KHÔNG tự đẻ sổ phân loại (DE.md luật 2). Khuôn khoa_v3: lỗi nói rõ
bằng RuntimeError, không nuốt, không fallback sổ nội bộ.
Cache 60s trong tiến trình: form/list gọi dày, danh mục đổi rất thưa.
"""
import json
import os
import time
import urllib.request

_cache = {'ts': 0.0, 'ds': []}
TTL_S = 60.0


def danh_sach(lam_moi=False) -> list[dict]:
    """[{ma, ten, ngon_ngu}] theo thứ tự đế trả. RuntimeError thông điệp tiếng
    Việt rõ ràng khi không lấy được — caller hiển thị nguyên văn, không nuốt."""
    if not lam_moi and _cache['ds'] and time.time() - _cache['ts'] < TTL_S:
        return _cache['ds']
    goc = os.environ.get('GATEWAY_URL', 'http://127.0.0.1:9000')
    try:
        with urllib.request.urlopen(f'{goc}/api/danh-ba/thi-truong', timeout=5) as r:
            ds = json.load(r)
    except Exception as e:
        raise RuntimeError(
            f'chưa lấy được danh mục thị trường từ OUTLIERY ({e.__class__.__name__}) '
            '— kiểm gateway 9000 đang chạy + thị trường đã khai ở General › Niches'
        ) from None
    _cache.update(ts=time.time(), ds=ds)
    return ds


def hop_le(ma: str) -> bool:
    """Mã có trong danh mục đế không — dùng cho validation, lỗi gateway NỔI LÊN."""
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
