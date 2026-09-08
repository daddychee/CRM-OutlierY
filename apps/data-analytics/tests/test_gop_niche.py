# -*- coding: utf-8 -*-
"""GỘP NICHE RESEARCH VÀO DATA-ANALYTICS — phương án B (Owner chốt 08/09).

Owner: "chuẩn logic" — không để app đã gộp giao diện vẫn đứng riêng ở tab API.
Làm TỪNG BƯỚC, mỗi bước test xanh + kiểm sống mới đi tiếp:
  B1 hợp đồng: 3 việc niche chuyển sang data-analytics (slug niche-research
     KHÔNG còn viec_api) + di trú cấp phát trong két.
  B2 mã nguồn: 2 chỗ xin khóa đổi slug (niche-research/khoa_v3.py,
     data-analytics/niche_run.py).
  B3 kiểm sống: pipeline ngách vẫn chạy được bằng khóa mới.

Test này chỉ đọc hợp đồng + mã nguồn, KHÔNG gọi API, KHÔNG cần gateway sống.
"""
import json
import pathlib

GOC = pathlib.Path(__file__).resolve().parents[1]
ROOT = pathlib.Path(r"D:\AI AGENT OUTLIERY")
APPS_JSON = ROOT / "nen" / "rules" / "apps.json"

VIEC_NICHE = {"quet_kenh", "phan_tich", "lay_transcript"}


def _apps() -> list:
    d = json.loads(APPS_JSON.read_text(encoding="utf-8"))
    return d if isinstance(d, list) else (d.get("apps") or [])


def _app(slug: str) -> dict:
    return next(x for x in _apps() if x.get("slug") == slug)


# ══ B1 — HỢP ĐỒNG ═══════════════════════════════════════════════════════════════
def test_b1_ba_viec_niche_nam_duoi_data_analytics():
    """Sau khi gộp: 3 việc của ngách phải khai dưới app CHỦ (data-analytics)."""
    ma = {v["ma"] for v in (_app("data-analytics").get("viec_api") or [])}
    thieu = VIEC_NICHE - ma
    assert not thieu, f"data-analytics chua khai: {sorted(thieu)}"
    # 2 viec san co khong duoc mat
    assert {"dien_giai", "phan_bien"} <= ma, ma


def test_b1_slug_niche_khong_con_khai_viec_api():
    """App con đã gộp thì KHÔNG còn đứng riêng ở tab API Per-app nữa."""
    a = _app("niche-research")
    assert not (a.get("viec_api") or []), \
        "niche-research van con viec_api -> tab API van hien app rieng"
    assert a.get("gop_vao") == "data-analytics", "phai giu co gop_vao"


def test_b1_viec_niche_giu_dung_loai():
    """Loại việc phải giữ nguyên để két cấp đúng kiểu khóa (youtube/llm/transcript)."""
    v = {x["ma"]: x for x in (_app("data-analytics").get("viec_api") or [])}
    assert v["quet_kenh"]["loai"] == "youtube", v.get("quet_kenh")
    assert v["phan_tich"]["loai"] == "llm", v.get("phan_tich")
    assert v["lay_transcript"]["loai"] == "transcript", v.get("lay_transcript")


def test_b1_ten_viec_niche_ghi_ro_xuat_xu():
    """Owner nhìn tab API phải biết việc nào vốn của khối Ngách."""
    v = {x["ma"]: x["ten"] for x in (_app("data-analytics").get("viec_api") or [])}
    for ma in VIEC_NICHE:
        assert "ngách" in v[ma].lower() or "niche" in v[ma].lower(), (ma, v.get(ma))


# ══ B2 — MÃ NGUỒN XIN KHÓA ══════════════════════════════════════════════════════
def test_b2_service_niche_xin_khoa_theo_slug_app_chu():
    """Service :9113 vẫn chạy thật nhưng khóa phải xin dưới slug app CHỦ."""
    src = (ROOT / "apps" / "niche-research" / "khoa_v3.py").read_text(encoding="utf-8")
    assert "api-khoa/data-analytics" in src, "khoa_v3 cua niche chua doi slug"
    assert "api-khoa/niche-research" not in src, "van con xin theo slug cu"


def test_b2_data_analytics_kiem_khoa_theo_slug_moi():
    """Bước 'check API' trước Researching phải soi đúng chỗ cấp khóa mới."""
    src = (GOC / "src" / "niche_run.py").read_text(encoding="utf-8")
    assert "api-khoa/data-analytics" in src, "niche_run.kiem_khoa chua doi slug"
    assert "api-khoa/niche-research" not in src, "van con doc slug cu"


# ══ B3 — CẤP PHÁT TRONG KÉT (di trú dữ liệu) ════════════════════════════════════
def test_b3_ket_da_di_tru_cap_phat_sang_app_chu():
    """3 việc phải có khóa dưới data-analytics; slug cũ không còn cấp phát —
    nếu không, chạy ngách sẽ báo 'chưa cấp khóa' dù Owner đã cấp từ lâu."""
    import sqlite3
    c = sqlite3.connect(str(ROOT / "data" / "nen" / "ket.db"))
    try:
        row = c.execute("SELECT gia_tri FROM cau_hinh WHERE khoa='api.cap_phat'").fetchone()
    finally:
        c.close()
    cap = json.loads(row[0]) if row else {}
    da = cap.get("data-analytics") or {}
    for ma in VIEC_NICHE:
        assert (da.get(ma) or {}).get("khoa"), f"data-analytics thieu khoa viec {ma}"
    assert not (cap.get("niche-research") or {}), \
        "cap phat cu cua niche-research chua duoc don"
