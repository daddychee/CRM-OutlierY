"""Nguồn khóa V3 — KÉT OUTLIERY qua gateway loopback (làm gọn RadarY, Owner 16/08).

Bảng api_keys nội bộ NGHỈ sau migration (không đọc, không xóa — sử liệu). Mỗi RUN
lấy danh sách khóa MỚI từ trang API Keys (cấp phát theo việc: harvest /
quet_dinh_ky) — không cache qua đêm, Owner đổi khóa/cấp phát là run sau ăn ngay.
Gateway chết / việc chưa được cấp khóa → run DỪNG với thông điệp rõ, TUYỆT ĐỐI
không âm thầm rơi về bảng nội bộ (chống hai nguồn khóa lệch nhau).
Cơ chế XOAY khóa của app giữ nguyên (scan.API) — chỉ đổi NGUỒN danh sách.
"""
import json
import os
import urllib.request


def lay_khoa(viec: str) -> list[str]:
    """Danh sách khóa YouTube cho một VIỆC của radary, thứ tự như cấp phát.

    Ném RuntimeError với thông điệp tiếng Việt rõ ràng khi không lấy được —
    caller hiển thị nguyên văn, không nuốt."""
    goc = os.environ.get('GATEWAY_URL', 'http://127.0.0.1:9000')
    url = f"{goc}/api/cau-hinh/api-khoa/radary"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.load(r)
    except Exception as e:
        raise RuntimeError(
            f"chưa lấy được khóa từ OUTLIERY ({e.__class__.__name__}) — kiểm "
            "gateway 9000 đang chạy + khóa đã cấp phát ở General › API Keys") from None
    muc = (data or {}).get(viec) or {}
    keys = [k.get('key') for k in muc.get('khoa', []) if k.get('key')]
    if not keys:
        raise RuntimeError(
            f"OUTLIERY chưa cấp khóa YouTube cho việc '{viec}' của radary — "
            "cấp ở General › API Keys (tab Per-app config)")
    return keys
