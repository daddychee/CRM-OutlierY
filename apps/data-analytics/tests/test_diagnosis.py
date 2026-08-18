"""Test cỗ máy chẩn đoán số liệu (luật ngoài code) + tầng phiên dịch + route /chan-doan.

Chia 2 phần:
- PHẦN CŨ: dữ liệu mock time-series (dòng cuối = mới nhất) — giữ tương thích ngược.
- PHẦN MỚI: report YouTube Studio THẬT (dòng Total + N video, tên cột tiếng Anh, đơn vị %).
"""

import io
import os
from pathlib import Path

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

import pandas as pd
import pytest

from src.diagnosis_engine import (ap_anh_xa_cot, chan_doan, chan_doan_kenh,
                                  chan_doan_video, doc_anh_xa, doc_bang_luat,
                                  doc_bao_cao, liet_ke_video, tach_total_va_video)

COT = ["impressions", "ctr", "views", "retention", "hook_retention",
       "watchtime", "engagement", "revenue", "rpm", "subs"]
DONG_NEN = dict(zip(COT, [10000, 0.05, 500, 0.5, 0.7, 100, 0.05, 10, 2, 20]))

# Report YouTube Studio thật để test đọc-thật (bỏ qua nếu máy không có thư mục mẫu)
_SAMPLING = Path(__file__).resolve().parent / "du-lieu-mau"
REPORT_THAT = _SAMPLING / "Table data.csv"
REPORT_XLSX = _SAMPLING / "Test.xlsx"


def _bao_cao(dong_cuoi: dict | None = None, so_dong_nen: int = 5) -> pd.DataFrame:
    """5 dòng nền giống nhau + 1 dòng cuối (mới nhất) tùy chỉnh."""
    dong = [dict(DONG_NEN)] * so_dong_nen
    dong.append({**DONG_NEN, **(dong_cuoi or {})})
    return pd.DataFrame(dong)


# ─────────────────────────── PHẦN CŨ (tương thích ngược) ───────────────────────────

def test_ctr_thap_retention_tot_khop_luat_bao_bi():
    kq = chan_doan(_bao_cao({"ctr": 0.02, "retention": 0.55}))
    ma = [r["ma_luat"] for r in kq["matched"]]
    assert "YT-01" in ma
    assert kq["tang_vo"] == "ctr"
    assert all(r["tang_pheu"] == "ctr" for r in kq["matched"])
    assert kq["canh_bao_baseline"] is None


def test_moi_thu_tot_khong_khop_luat_nao():
    kq = chan_doan(_bao_cao())
    assert kq["matched"] == [] and kq["tang_vo"] is None


def test_them_luat_moi_vao_csv_ap_duoc_ngay(tmp_path):
    luat_csv = tmp_path / "luat_moi.csv"
    luat_csv.write_text(
        "linh_vuc,ma_luat,dieu_kien,tang_pheu,nguyen_nhan,cach_sua,do_tin_cay,nguon_tham_khao\n"
        "tiktok,TT-01,so_share < so_share_baseline * 0.5,engagement,"
        "It chia se,Them CTA chia se,vua,test\n",
        encoding="utf-8",
    )
    df = pd.DataFrame([{"so_share": 100}] * 5 + [{"so_share": 10}])
    kq = chan_doan(df, doc_bang_luat(luat_csv))
    assert [r["ma_luat"] for r in kq["matched"]] == ["TT-01"]
    assert kq["tang_vo"] == "engagement"


def test_guardrail_baseline_it_du_lieu():
    it_dong = pd.DataFrame([DONG_NEN] * 2)
    kq = chan_doan(it_dong)
    assert kq["canh_bao_baseline"] is not None

    mot_dong = pd.DataFrame([{"ctr": 0.02, "retention": 0.5}])
    kq1 = chan_doan(mot_dong)
    assert kq1["baselines"] == {} and kq1["canh_bao_baseline"] is not None
    assert all("_baseline" not in r["dieu_kien"] for r in kq1["matched"])


def test_baseline_la_trung_vi_ben_voi_outlier():
    dong = [dict(DONG_NEN)] * 4 + [{**DONG_NEN, "views": 1_000_000}, dict(DONG_NEN)]
    kq = chan_doan(pd.DataFrame(dong))
    assert kq["baselines"]["views"] == 500


# ─────────────────────── PHẦN MỚI: tầng phiên dịch (ánh xạ cột) ───────────────────────

def test_anh_xa_cot_quy_doi_don_vi_phan_tram():
    """Report ghi CTR = 4.61 (%) → sau ánh xạ phải về 0.0461 (thang 0-1)."""
    df = pd.DataFrame({
        "Impressions click-through rate (%)": [4.61],
        "Average percentage viewed (%)": [24.19],
        "Views": [10562],
    })
    m = ap_anh_xa_cot(df)
    assert abs(m["ctr"].iloc[0] - 0.0461) < 1e-9
    assert abs(m["retention"].iloc[0] - 0.2419) < 1e-9
    assert m["views"].iloc[0] == 10562


def test_anh_xa_giu_cot_khong_map():
    """Cột không có trong bảng ánh xạ → giữ nguyên (tên chuẩn hóa), không mất dữ liệu."""
    df = pd.DataFrame({"Views": [100], "Cột lạ Không Map": ["x"]})
    m = ap_anh_xa_cot(df)
    assert "views" in m.columns
    assert "cột_lạ_không_map" in m.columns


def test_anh_xa_rong_van_chay():
    """Không truyền bảng ánh xạ (hoặc rỗng) → df dùng tên biến luật sẵn vẫn chẩn đoán được."""
    m = ap_anh_xa_cot(_bao_cao(), anh_xa=[])
    assert "ctr" in m.columns and "retention" in m.columns


# ─────────────────────── PHẦN MỚI: report YouTube Studio thật ───────────────────────

def test_tach_total_va_video():
    """Report YouTube: dòng 'Total' tách khỏi các dòng video."""
    df = pd.DataFrame({
        "Content": ["Total", "abc123", "def456"],
        "Views": [1000, 600, 400],
        "Impressions click-through rate (%)": [5.0, 4.0, 6.0],
    })
    total, videos = tach_total_va_video(df)
    assert total is not None
    assert len(videos) == 2
    assert "Total" not in videos["Content"].values


def test_khong_phai_report_youtube_giu_nguyen():
    """Dữ liệu không có dòng Total → trả (None, df nguyên) — không nhầm là report YouTube."""
    total, videos = tach_total_va_video(_bao_cao())
    assert total is None
    assert len(videos) == len(_bao_cao())


def test_chan_doan_video_so_baseline_kenh():
    """Video CTR cao + retention thấp → khớp luật giật-tít (YT-02), tầng vỡ = retention."""
    df = pd.DataFrame({
        "Content": ["Total"] + [f"v{i}" for i in range(6)],
        "Impressions click-through rate (%)": [4.0, 9.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        "Average percentage viewed (%)": [30.0, 12.0, 35.0, 33.0, 34.0, 32.0, 31.0],
        "Views": [10000, 500, 900, 950, 800, 850, 870],
    })
    kq = chan_doan_video(df, 0)  # video "v0" ctr cao retention thấp
    assert kq["che_do"] == "video"
    assert kq["tang_vo"] == "retention"
    assert "YT-02" in [r["ma_luat"] for r in kq["matched"]]
    assert kq["so_video"] == 6


def test_chan_doan_kenh_dung_dong_total():
    """Chẩn đoán kênh: dòng Total so mặt bằng video của chính kênh."""
    df = pd.DataFrame({
        "Content": ["Total"] + [f"v{i}" for i in range(6)],
        "Average percentage viewed (%)": [22.0, 45.0, 48.0, 46.0, 47.0, 44.0, 43.0],
        "Impressions click-through rate (%)": [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0],
        "Views": [10000, 900, 950, 800, 850, 870, 880],
    })
    kq = chan_doan_kenh(df)
    assert kq["che_do"] == "kenh"
    # Total retention 22% thấp hẳn so mặt bằng video (~45%) → khớp luật retention
    assert kq["tang_vo"] == "retention"


def test_chan_doan_kenh_khong_co_total_bao_loi():
    with pytest.raises(ValueError):
        chan_doan_kenh(_bao_cao())


def test_liet_ke_video():
    df = pd.DataFrame({
        "Content": ["Total", "aaa", "bbb"],
        "Video title": [None, "Video A", "Video B"],
        "Views": [1000, 600, 400],
    })
    ds = liet_ke_video(df)
    assert len(ds) == 2
    assert ds[0]["tieu_de"] == "Video A" and ds[0]["views"] == 600


def test_chan_doan_tu_dong_nhan_report_youtube():
    """chan_doan() gặp report YouTube → tự chuyển sang chế độ video (không dùng 'dòng cuối')."""
    df = pd.DataFrame({
        "Content": ["Total", "v0", "v1"],
        "Impressions click-through rate (%)": [4.0, 9.0, 4.0],
        "Average percentage viewed (%)": [30.0, 12.0, 35.0],
        "Views": [10000, 500, 900],
    })
    kq = chan_doan(df)
    assert kq["che_do"] == "video"


@pytest.mark.skipif(not REPORT_THAT.exists(), reason="Không có report mẫu trên máy này")
def test_doc_report_that_80_video():
    """Chạy trên report YouTube Studio THẬT: đọc đúng 80 video + chẩn đoán ra tầng vỡ."""
    df = doc_bao_cao(REPORT_THAT)
    total, videos = tach_total_va_video(df)
    assert total is not None
    assert len(videos) == 80

    k = chan_doan_kenh(df)
    assert k["che_do"] == "kenh" and k["so_video"] == 80
    # ctr kênh thật ~0.046 (đã quy đổi từ 4.61%) — đảm bảo tầng phiên dịch chạy
    assert 0.02 < k["metrics"]["ctr"] < 0.10

    v = chan_doan_video(df, 1)  # video 1: ctr cao ~9.5% retention thấp ~13.5%
    assert v["tang_vo"] == "retention"


@pytest.mark.skipif(not REPORT_XLSX.exists(), reason="Không có report .xlsx mẫu trên máy này")
def test_doc_report_xlsx_chon_dung_sheet():
    """doc_bao_cao(.xlsx) phải chọn sheet 'Table data' (report YT nhiều sheet) và cho
    KẾT QUẢ GIỐNG bản .csv — bảo vệ nhánh chọn-sheet (đổi nhiều nhất, trước đây chưa test)."""
    dfx = doc_bao_cao(REPORT_XLSX)
    total, videos = tach_total_va_video(dfx)
    assert total is not None and len(videos) == 80

    kx = chan_doan_kenh(dfx)
    kc = chan_doan_kenh(doc_bao_cao(REPORT_THAT))
    assert kx["tang_vo"] == kc["tang_vo"]                       # xlsx ≡ csv
    assert abs(kx["metrics"]["ctr"] - kc["metrics"]["ctr"]) < 1e-9


# ─────────────────────────────── route /chan-doan ───────────────────────────────

def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def test_route_chan_doan():
    from fastapi.testclient import TestClient
    from src.main import app

    tc = TestClient(app, headers={"X-Remote-User": "nv", "X-Remote-Level": "2"})
    assert tc.get("/chan-doan").status_code == 200

    r = tc.post("/chan-doan", files={
        "file": ("bao-cao.csv", _csv_bytes(_bao_cao({"ctr": 0.02, "retention": 0.55})))})
    assert r.status_code == 200
    body = r.json()
    assert body["tang_vo"] == "ctr" and body["matched"]
    assert body["dien_giai"]["answer"] and "critic_count" in body["dien_giai"]

    r2 = tc.post("/chan-doan", files={"file": ("ok.csv", _csv_bytes(_bao_cao()))})
    body2 = r2.json()
    assert "Không phát hiện bất thường" in body2["message"]
    assert body2["dien_giai"] is None

    r3 = tc.post("/chan-doan", files={"file": ("anh.png", b"x")})
    assert r3.status_code == 422

    # loai="cu" cho dữ liệu không phải YouTube (tương thích ngược)
    assert body.get("loai") == "cu"


def _report_yt_csv() -> bytes:
    """Report YouTube tối giản: 1 Total + 6 video (đủ baseline), tên cột thật + đơn vị %."""
    df = pd.DataFrame({
        "Content": ["Total"] + [f"v{i}" for i in range(6)],
        "Video title": [None] + [f"Video {i}" for i in range(6)],
        "Impressions click-through rate (%)": [4.0, 9.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        "Average percentage viewed (%)": [30.0, 12.0, 35.0, 33.0, 34.0, 32.0, 31.0],
        "Views": [10000, 500, 900, 950, 800, 850, 870],
    })
    return _csv_bytes(df)


def test_route_chan_doan_youtube_kenh_va_bang_video():
    from fastapi.testclient import TestClient
    from src.main import app

    tc = TestClient(app, headers={"X-Remote-User": "nv", "X-Remote-Level": "2"})
    # Report YouTube chạy NỀN: POST trả task_id, poll trạng thái lấy kết quả (TestClient chạy
    # BackgroundTask xong trước khi trả nên đã 'xong' ngay).
    r0 = tc.post("/chan-doan", files={"file": ("report.csv", _report_yt_csv())})
    assert r0.status_code == 200 and r0.json()["loai"] == "nen"
    tt = tc.get(f"/chan-doan/trang-thai/{r0.json()['task_id']}").json()
    assert tt["trang_thai"] == "xong"
    body = tt["ket_qua"]
    assert body["loai"] == "youtube"
    assert body["kenh"]["che_do"] == "kenh"            # khối kênh có message + dien_giai
    assert "message" in body["kenh"] and "dien_giai" in body["kenh"]
    assert len(body["videos"]) == 6                    # đủ mọi video
    assert "tong_quan_danh_muc" in body               # Giai đoạn 4: bức tranh danh mục cấp kênh
    v0 = body["videos"][0]
    assert {"chi_muc", "tieu_de", "views", "phan_quyet", "the_diem"} <= set(v0)
    assert set(v0["the_diem"]) == {"noi_dung", "tien", "danh_muc", "cong_thuc"}


def test_route_chan_doan_video_rieng_le():
    from fastapi.testclient import TestClient
    from src.main import app

    tc = TestClient(app, headers={"X-Remote-User": "nv", "X-Remote-Level": "2"})
    # video 0: ctr 9% + retention 12% (giật tít) → có tầng vỡ + diễn giải LLM (mock)
    r = tc.post("/chan-doan/video",
                files={"file": ("report.csv", _report_yt_csv())}, data={"chi_muc": "0"})
    assert r.status_code == 200
    body = r.json()
    assert body["che_do"] == "video" and body["tang_vo"] == "retention"
    assert body["matched"] and body["dien_giai"]["answer"]

    # chi_muc ngoài phạm vi → 422
    r2 = tc.post("/chan-doan/video",
                 files={"file": ("report.csv", _report_yt_csv())}, data={"chi_muc": "99"})
    assert r2.status_code == 422


def test_nap_cau_hinh_llm_xin_theo_app_va_map_env(monkeypatch):
    """Bug 18/08 (Owner phê lần 3): DA từng xin thẳng vai writer/critic — TRÙNG
    TÊN việc của ai-agent nên gateway (hardcode ai-agent) trả nhầm khóa Writer
    ai-agent. Giờ PHẢI xin theo app=data-analytics + việc trong contract
    (dien_giai/phan_bien), rồi map về env WRITER_*/CRITIC_* của factory nội bộ."""
    from src import dien_giai as dg

    # đăng ký khôi phục env (monkeypatch trả về giá trị gốc kể cả khi code dưới
    # ghi đè trực tiếp os.environ) — không rò WRITER_MOCK_MODE=false sang test khác
    for p in ("WRITER", "CRITIC"):
        for s in ("PROVIDER", "MODEL", "BASE_URL", "API_KEY", "MOCK_MODE"):
            monkeypatch.delenv(f"{p}_{s}", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("LLM_RETRY", raising=False)

    goi = []

    class _Resp:
        def __init__(self, vai):
            self._vai = vai

        def json(self):
            return {"provider": "openai_compatible", "model": f"m-{self._vai}",
                    "base_url": "http://bu", "api_key": f"sk-{self._vai}",
                    "timeout": 60, "retry": 0}

    class _Client:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            goi.append((url, params))
            return _Resp(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(dg.httpx, "Client", _Client)
    dg.nap_cau_hinh_llm()

    assert goi == [
        (f"{dg.GATEWAY_URL}/api/cau-hinh/llm/dien_giai", {"app": "data-analytics"}),
        (f"{dg.GATEWAY_URL}/api/cau-hinh/llm/phan_bien", {"app": "data-analytics"}),
    ]
    # việc gateway → env prefix nội bộ: dien_giai→WRITER_*, phan_bien→CRITIC_*
    assert os.environ["WRITER_API_KEY"] == "sk-dien_giai"
    assert os.environ["WRITER_MODEL"] == "m-dien_giai"
    assert os.environ["CRITIC_API_KEY"] == "sk-phan_bien"
    assert os.environ["WRITER_MOCK_MODE"] == "false"
