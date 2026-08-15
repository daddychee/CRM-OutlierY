"""Test lịch sử báo cáo chẩn đoán Tầng 1 — module (giống lich_su) + route + RBAC.
Mock LLM qua MOCK_MODE (conftest). BAO_CAO_DIR/BAO_CAO_GOC_DIR trỏ tmp (conftest)."""

import json
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from src import bao_cao_lich_su as bl
from src.main import app


def _rec(id_="a1b2c3d4", tang="retention"):
    return {"id": id_, "ten_file_goc": "report.csv", "duong_dan_goc": "/x",
            "kenh": {"tang_vo": tang, "so_video": 6, "metrics_chinh": {"ctr": 0.046},
                     "luat_khop": ["YT-04"]}}


# ─────────────────────────── module (khuôn lich_su) ───────────────────────────

def test_luu_va_doc_moi_nhat_truoc():
    bl.luu_bao_cao("nv", _rec("id-1"), "2026-07-20T10:00:00")
    bl.luu_bao_cao("nv", _rec("id-2"), "2026-07-20T11:00:00")
    ds = bl.doc_bao_cao_list("nv")
    assert [r["id"] for r in ds] == ["id-2", "id-1"]           # mới nhất TRƯỚC
    assert ds[0]["nguoi_chay"] == "nv" and ds[0]["thoi_gian"] == "2026-07-20T11:00:00"


def test_doc_mot_bao_cao_theo_id():
    bl.luu_bao_cao("nv", _rec("xyz"), "T1")
    assert bl.doc_mot_bao_cao("nv", "xyz")["id"] == "xyz"
    assert bl.doc_mot_bao_cao("nv", "khong-co") is None


def test_ten_file_an_toan_chong_traversal():
    bl.luu_bao_cao("../../etc/passwd", _rec(), "T1")
    thu_muc = Path(os.environ["BAO_CAO_DIR"])
    # không có file nào nằm NGOÀI thư mục (không leo ../)
    assert all(f.parent == thu_muc for f in thu_muc.glob("*.json"))
    assert bl.doc_bao_cao_list("../../etc/passwd")               # vẫn đọc lại được của chính tên đó


def test_ghi_nguyen_tu_khong_de_lai_tmp():
    bl.luu_bao_cao("nv", _rec(), "T1")
    assert not list(Path(os.environ["BAO_CAO_DIR"]).glob("*.tmp"))


def test_file_hong_tra_rong():
    p = bl._duong_dan("hong")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{hỏng", encoding="utf-8")
    assert bl.doc_bao_cao_list("hong") == []


def test_luu_va_tai_file_goc():
    duong = bl.luu_file_goc("bc123", "Table data.csv", b"noi-dung-goc")
    p = Path(duong)
    assert p.is_file() and p.read_bytes() == b"noi-dung-goc"
    assert p.name.startswith("bc123__") and p.name.endswith(".csv")


# ─────────────────────────── Issue 2 §1: ten_kenh (định danh nối báo cáo qua thời gian) ────

def test_danh_sach_ten_kenh_dedup_moi_nhat_truoc():
    bl.luu_bao_cao("nv", {**_rec("r1"), "ten_kenh": "Outland"}, "2026-08-01T10:00:00")
    bl.luu_bao_cao("nv2", {**_rec("r2"), "ten_kenh": "Wheel"}, "2026-08-01T11:00:00")
    bl.luu_bao_cao("nv", {**_rec("r3"), "ten_kenh": "Outland"}, "2026-08-01T12:00:00")   # trùng tên
    bl.luu_bao_cao("nv", {**_rec("r4"), "ten_kenh": ""}, "2026-08-01T13:00:00")           # rỗng → bỏ qua
    # thoi_gian mới nhất trước: r4(13:00,rỗng→bỏ) → r3(12:00,'Outland') → r2(11:00,'Wheel')
    # → r1(10:00,'Outland' đã có → bỏ)
    assert bl.danh_sach_ten_kenh() == ["Outland", "Wheel"]   # mới nhất trước, dedup, bỏ rỗng


def test_danh_sach_ten_kenh_rong_khi_chua_co_bao_cao_nao():
    assert bl.danh_sach_ten_kenh() == []


# ─────────────────────────── route + RBAC ───────────────────────────

# V2: app nhận CLAIMS từ gateway thay vì tự đăng nhập — bảng level giữ nguyên ý cũ.
LEVEL = {"sep": 5, "ql": 4, "nv": 2, "nv2": 2}


def _users(tmp_path, monkeypatch):
    """V2: không còn USERS_FILE — giữ chữ ký để mọi call-site cũ nguyên vẹn (no-op)."""


def _login(ten):
    return TestClient(app, headers={"X-Remote-User": ten,
                                    "X-Remote-Level": str(LEVEL.get(ten, 1)),
                                    "X-Remote-Role": "viewer"})


def _report_yt() -> bytes:
    df = pd.DataFrame({
        "Content": ["Total"] + [f"v{i}" for i in range(6)],
        "Video title": [None] + [f"Video {i}" for i in range(6)],
        "Impressions click-through rate (%)": [4.0, 9.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        "Average percentage viewed (%)": [22.0, 12.0, 45.0, 46.0, 44.0, 47.0, 43.0],
        "Views": [10000, 500, 900, 950, 800, 850, 870],
    })
    import io
    buf = io.StringIO(); df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def _chan_doan_kq(c, data=None):
    """Chẩn đoán report YouTube CHẠY NỀN → poll trạng thái → trả ket_qua đầy đủ. TestClient chạy
    BackgroundTask xong TRƯỚC khi POST trả về nên trạng thái đã 'xong' ngay lượt hỏi đầu."""
    tid = c.post("/chan-doan", files={"file": ("report.csv", _report_yt())},
                 data=data or {}).json()["task_id"]
    return c.get(f"/chan-doan/trang-thai/{tid}").json()["ket_qua"]


def _chan_doan_bid(c, data=None):
    return _chan_doan_kq(c, data)["bao_cao_id"]


def test_ten_kenh_khong_bat_buoc_o_api_nhung_luu_dung_khi_co(tmp_path, monkeypatch):
    """§1: form HTML bắt buộc (UI), nhưng API KHÔNG chặn cứng (đúng khuôn 'ngày chạy/loại kênh
    để trống cũng được') — không truyền vẫn lưu OK (chỉ đơn giản không so kỳ được sau này)."""
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid1 = _chan_doan_bid(c)                                      # không truyền ten_kenh
    assert bl.doc_mot_bao_cao("nv", bid1)["ten_kenh"] == ""
    bid2 = _chan_doan_bid(c, {"ten_kenh": "Outland"})
    assert bl.doc_mot_bao_cao("nv", bid2)["ten_kenh"] == "Outland"


def test_route_kenh_goi_y_tra_ten_da_dung_va_yeu_cau_dang_nhap(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    assert c.get("/chan-doan/kenh-goi-y").json() == []            # chưa có báo cáo nào
    _chan_doan_bid(c, {"ten_kenh": "Outland"})
    assert c.get("/chan-doan/kenh-goi-y").json() == ["Outland"]
    r = TestClient(app).get("/chan-doan/kenh-goi-y", follow_redirects=False)
    assert r.status_code == 401   # V2: thiếu claims gateway → 401 (không còn redirect login)


# ─────────────────────────── Issue 2 §2: kỳ báo cáo (ky_bat_dau/ky_ket_thuc) ────────────────

def test_phan_giai_ky_uu_tien_chart_data_hon_nhap_tay():
    from src.main import _phan_giai_ky_bao_cao
    from src.diagnosis_engine import doc_chart_data
    ch = doc_chart_data(str(Path(__file__).resolve().parent / "du-lieu-mau" / "Space.xlsx"))
    dau, cuoi, nguon = _phan_giai_ky_bao_cao(ch, "2020-01-01", "2020-01-02")   # nhập tay khác hẳn
    assert nguon == "chart_data" and dau != "2020-01-01"           # Chart data THẮNG nhập tay


def test_phan_giai_ky_dung_nhap_tay_khi_khong_co_chart_data():
    from src.main import _phan_giai_ky_bao_cao
    assert _phan_giai_ky_bao_cao(None, "2026-07-01", "2026-07-28") == \
        ("2026-07-01", "2026-07-28", "nhap_tay")


def test_phan_giai_ky_rong_khi_thieu_ca_chart_lan_nhap_tay():
    from src.main import _phan_giai_ky_bao_cao
    assert _phan_giai_ky_bao_cao(None, "", "") == ("", "", "")
    assert _phan_giai_ky_bao_cao(None, "2026-07-01", "") == ("", "", "")   # thiếu 1 ô → bỏ cả 2


def test_route_luu_ky_bao_cao_tu_nhap_tay_khi_khong_co_chart(tmp_path, monkeypatch):
    """report .csv (không có Chart data) + user nhập kỳ tay → lưu đúng, nguon_ky='nhap_tay'."""
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c, {"ten_kenh": "Outland", "ky_bat_dau": "2026-07-01",
                             "ky_ket_thuc": "2026-07-28"})
    rec = bl.doc_mot_bao_cao("nv", bid)
    assert (rec["ky_bat_dau"], rec["ky_ket_thuc"], rec["nguon_ky"]) == \
        ("2026-07-01", "2026-07-28", "nhap_tay")


def test_route_khong_ky_bao_cao_khi_khong_co_chart_lan_nhap_tay(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c, {"ten_kenh": "Outland"})   # không Chart data, không nhập tay
    rec = bl.doc_mot_bao_cao("nv", bid)
    assert (rec["ky_bat_dau"], rec["ky_ket_thuc"], rec["nguon_ky"]) == ("", "", "")


# ─────────────────────────── Issue 2 §4: route /chan-doan/so-sanh ───────────────────────────

def test_route_so_sanh_tra_ve_ket_qua_dung(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid1 = _chan_doan_bid(c, {"ten_kenh": "Outland", "ky_bat_dau": "2026-06-01",
                              "ky_ket_thuc": "2026-06-28"})
    bid2 = _chan_doan_bid(c, {"ten_kenh": "Outland", "ky_bat_dau": "2026-08-01",
                              "ky_ket_thuc": "2026-08-28"})
    r = c.post("/chan-doan/so-sanh", data={"id_a": bid1, "id_b": bid2})
    assert r.status_code == 200
    body = r.json()
    assert "loi" not in body and body["ten_kenh"] == "Outland"
    assert "views" in body["chi_so"]   # cả 2 lần chạy đều dùng _report_yt() → có views


def test_route_so_sanh_khong_tim_thay_bao_cao_404(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c, {"ten_kenh": "Outland"})
    r = c.post("/chan-doan/so-sanh", data={"id_a": bid, "id_b": "khong-ton-tai"})
    assert r.status_code == 404


def test_route_so_sanh_khac_kenh_tra_loi_khong_phai_loi_http(tmp_path, monkeypatch):
    """so_sanh_ky() trả {'loi': ...} là kết quả HỢP LỆ (van chống bịa), KHÔNG phải lỗi HTTP —
    route vẫn 200, frontend tự đọc field 'loi' để hiện thông báo."""
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid1 = _chan_doan_bid(c, {"ten_kenh": "Outland"})
    bid2 = _chan_doan_bid(c, {"ten_kenh": "Wheel"})
    r = c.post("/chan-doan/so-sanh", data={"id_a": bid1, "id_b": bid2})
    assert r.status_code == 200 and "loi" in r.json()


def test_route_so_sanh_yeu_cau_dang_nhap(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    r = TestClient(app).post("/chan-doan/so-sanh", data={"id_a": "x", "id_b": "y"})
    assert r.status_code == 401


def test_chan_doan_nen_tra_task_id_va_luu_lich_su(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    # POST trả NGAY mã tác vụ (không kèm kết quả) — chạy nền
    r = c.post("/chan-doan", files={"file": ("report.csv", _report_yt())}).json()
    assert r["loai"] == "nen" and r["task_id"]
    # TestClient chạy BackgroundTask xong trước khi trả → trạng thái đã 'xong'
    tt = c.get(f"/chan-doan/trang-thai/{r['task_id']}").json()
    assert tt["trang_thai"] == "xong" and tt["bao_cao_id"]
    assert tt["ket_qua"]["loai"] == "youtube"
    # đã lưu 1 bản ghi cho nv (đóng tab vẫn xong nhờ chạy nền)
    ds = bl.doc_bao_cao_list("nv")
    assert len(ds) == 1 and ds[0]["id"] == tt["bao_cao_id"]
    assert ds[0]["kenh"]["tang_vo"] and "ctr" in ds[0]["kenh"]["metrics_chinh"]


def test_chan_doan_nen_rbac_va_loi(tmp_path, monkeypatch):
    import src.main as app_mod
    _users(tmp_path, monkeypatch)
    tid = _login("nv").post("/chan-doan",
                            files={"file": ("report.csv", _report_yt())}).json()["task_id"]
    # người khác hỏi trạng thái tác vụ của nv → 404 lặng lẽ (không lộ tồn tại)
    assert _login("ql").get(f"/chan-doan/trang-thai/{tid}").status_code == 404
    assert _login("nv").get(f"/chan-doan/trang-thai/{tid}").status_code == 200
    # lỗi trong lúc chạy nền → trạng thái 'loi', không ném ra ngoài
    monkeypatch.setattr(app_mod, "_chay_chan_doan_youtube",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nổ nền")))
    c = _login("nv")
    t2 = c.post("/chan-doan", files={"file": ("report.csv", _report_yt())}).json()["task_id"]
    r = c.get(f"/chan-doan/trang-thai/{t2}").json()
    assert r["trang_thai"] == "loi" and "nổ nền" in r["loi"]


def test_llm_chet_khong_giet_chan_doan(tmp_path, monkeypatch):
    """Model diễn giải chết (Z.ai 429/1113 hết credit — sự cố thật 15/08/2026) → engine
    VẪN chấm + lưu lịch sử, tác vụ 'xong'; lỗi model chỉ còn là cảnh báo dien_giai_loi."""
    import src.main as app_mod
    _users(tmp_path, monkeypatch)
    monkeypatch.setattr(app_mod.dien_giai, "dien_giai_chan_doan",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError(
                            "Error code: 429 - {'error': {'code': '1113', 'message': "
                            "'Insufficient balance or no resource package. Please recharge.'}}")))
    c = _login("nv")
    tid = c.post("/chan-doan", files={"file": ("report.csv", _report_yt())}).json()["task_id"]
    tt = c.get(f"/chan-doan/trang-thai/{tid}").json()
    assert tt["trang_thai"] == "xong" and tt["bao_cao_id"]        # không chết theo LLM
    kenh = tt["ket_qua"]["kenh"]
    assert kenh["matched"] and kenh["dien_giai"] is None          # luật vẫn khớp, thiếu diễn giải
    assert "credit" in kenh["dien_giai_loi"] and "Két" in kenh["dien_giai_loi"]
    assert len(bl.doc_bao_cao_list("nv")) == 1                    # lịch sử vẫn lưu


def test_ten_bao_cao_luu_va_hien(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c, data={"ten_bao_cao": "Kênh A tháng 7"})
    assert bl.doc_mot_bao_cao("nv", bid)["ten_bao_cao"] == "Kênh A tháng 7"
    assert "Kênh A tháng 7" in c.get("/bao-cao-lich-su").text            # danh sách
    assert "Kênh A tháng 7" in c.get(f"/bao-cao-lich-su/{bid}").text     # chi tiết


def test_ten_bao_cao_rong_dung_ten_file(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    assert bl.doc_mot_bao_cao("nv", bid)["ten_bao_cao"] == ""            # rỗng lưu rỗng
    assert "report.csv" in c.get("/bao-cao-lich-su").text               # hiển thị fallback tên file


def test_route_danh_sach_va_xem_mot(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    assert "Lịch sử báo cáo" in c.get("/bao-cao-lich-su").text
    r = c.get(f"/bao-cao-lich-su/{bid}")
    assert r.status_code == 200 and "report.csv" in r.text
    assert c.get("/bao-cao-lich-su/khong-co").status_code == 404


def test_lich_su_dung_chung_moi_nguoi_deu_xem(tmp_path, monkeypatch):
    """01/08/2026 (user chốt 'các user khác không xem được lịch sử cũ'): lịch sử là
    DÙNG CHUNG cho mọi ai qua gate Data Analytics — nhân viên thường xem được báo
    cáo người khác (danh sách + chi tiết + panel gộp mọi người kèm nguoi_chay);
    link không cần ?nguoi= vẫn tự tìm ra chủ báo cáo."""
    _users(tmp_path, monkeypatch)
    bid = _chan_doan_bid(_login("nv"))

    c_ql = _login("ql")
    assert c_ql.get("/bao-cao-lich-su?nguoi=nv").status_code == 200   # lọc theo người
    assert c_ql.get(f"/bao-cao-lich-su/{bid}?nguoi=nv").status_code == 200
    # nhân viên thường xem của người khác — giờ ĐƯỢC (trước 403)
    c_nv2 = _login("nv2")
    assert c_nv2.get("/bao-cao-lich-su?nguoi=nv").status_code == 200
    trang = c_nv2.get("/bao-cao-lich-su").text
    assert "Người chạy" in trang and ">nv<" in trang                  # bảng chung ghi ai chạy
    # chi tiết KHÔNG cần ?nguoi= — route tự quét mọi người ra chủ báo cáo
    assert c_nv2.get(f"/bao-cao-lich-su/{bid}").status_code == 200
    # panel gọn: gộp mọi người + trường nguoi_chay
    d = c_nv2.get("/api/bao-cao-lich-su").json()["bao_cao"]
    assert any(r["id"] == bid and r["nguoi_chay"] == "nv" for r in d)


def test_tai_file_goc_dung_chung(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c_nv = _login("nv")
    bid = _chan_doan_bid(c_nv)

    # chính chủ tải được, đúng nội dung gốc
    r = c_nv.get(f"/bao-cao-goc/{bid}")
    assert r.status_code == 200 and r.content == _report_yt()
    # lịch sử dùng chung: người khác qua gate cũng tải được (kể cả không ?nguoi=)
    assert _login("ql").get(f"/bao-cao-goc/{bid}?nguoi=nv").status_code == 200
    assert _login("nv2").get(f"/bao-cao-goc/{bid}").status_code == 200
    # id không tồn tại → 404
    assert c_nv.get("/bao-cao-goc/khong-co").status_code == 404


# ═══ Cache diễn giải (video + kênh) + xem lại đầy đủ từ file gốc ═══

def _spy_llm(monkeypatch):
    """Đếm số lần gọi LLM diễn giải (mock) — để chứng minh cache không gọi lại API."""
    import src.main as app_mod
    dem = {"n": 0}
    that = app_mod.dien_giai.dien_giai_chan_doan
    def spy(kq, user=None, loai_kenh_ctx=""):
        dem["n"] += 1
        return that(kq, user=user, loai_kenh_ctx=loai_kenh_ctx)
    monkeypatch.setattr(app_mod.dien_giai, "dien_giai_chan_doan", spy)
    return dem


def test_cache_dien_giai_video_theo_cap_id_chi_muc():
    dg = lambda a: {"answer": a, "sources": [], "critic_count": 1, "rewritten": False}
    bl.luu_bao_cao("nv", _rec("bc-A"), "T1")
    bl.luu_bao_cao("nv", _rec("bc-B"), "T2")
    bl.luu_dien_giai_video("nv", "bc-A", 3, dg("A3"))
    bl.luu_dien_giai_video("nv", "bc-B", 3, dg("B3"))
    # KHÓA là (bao_cao_id, chi_muc) — cùng chi_muc 3 ở 2 báo cáo KHÁC nhau KHÔNG lẫn cache
    assert bl.doc_dien_giai_video("nv", "bc-A", 3)["answer"] == "A3"
    assert bl.doc_dien_giai_video("nv", "bc-B", 3)["answer"] == "B3"
    assert bl.doc_dien_giai_video("nv", "bc-A", 5) is None        # chi_muc chưa cache


def test_route_video_cache_khong_goi_llm_lan_hai(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    dem = _spy_llm(monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    dem["n"] = 0   # bỏ qua lần gọi lúc chẩn đoán kênh
    # video 0 (ctr 9% + ret 12% = giật tít) → có luật khớp → lần đầu gọi LLM 1 lần rồi cache
    r1 = c.post("/chan-doan/video", data={"chi_muc": "0", "bao_cao_id": bid})
    assert r1.status_code == 200 and r1.json()["dien_giai"]["answer"] is not None
    assert dem["n"] == 1
    r2 = c.post("/chan-doan/video", data={"chi_muc": "0", "bao_cao_id": bid})
    assert r2.status_code == 200
    assert dem["n"] == 1                              # lần hai: đọc CACHE, không gọi thêm
    assert r2.json()["dien_giai"] == r1.json()["dien_giai"]


def _report_yt_video_it_view() -> bytes:
    """Giống _report_yt() nhưng video 0 chỉ 5 view (dưới ngưỡng du_mau_ket_luan động, ở đây
    100) — GIỮ NGUYÊN ctr/retention y hệt ca 'giật tít' của _report_yt() để chứng minh gate
    chặn ĐÚNG vì thiếu view, không phải vì ratio tình cờ không khớp luật nào."""
    df = pd.DataFrame({
        "Content": ["Total"] + [f"v{i}" for i in range(6)],
        "Video title": [None] + [f"Video {i}" for i in range(6)],
        "Impressions click-through rate (%)": [4.0, 9.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        "Average percentage viewed (%)": [22.0, 12.0, 45.0, 46.0, 44.0, 47.0, 43.0],
        "Views": [10000, 5, 900, 950, 800, 850, 870],
    })
    import io
    buf = io.StringIO(); df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def test_route_video_khong_du_view_khong_goi_llm(tmp_path, monkeypatch):
    """Vá 'video 50 view và 60k view ra cùng kết luận' (15/08): video quá ít view → matched=[]
    ngay từ engine (không chấm luật trên mẫu quá mỏng), KHÔNG gọi LLM — tiết kiệm token, không
    viết action-plan không đáng tin cho video gần như chưa ai xem."""
    _users(tmp_path, monkeypatch)
    dem = _spy_llm(monkeypatch)
    c = _login("nv")
    tid = c.post("/chan-doan", files={"file": ("report.csv", _report_yt_video_it_view())}).json()["task_id"]
    bid = c.get(f"/chan-doan/trang-thai/{tid}").json()["ket_qua"]["bao_cao_id"]
    dem["n"] = 0   # bỏ qua lượt gọi lúc chẩn đoán kênh
    r = c.post("/chan-doan/video", data={"chi_muc": "0", "bao_cao_id": bid})
    assert r.status_code == 200
    body = r.json()
    assert body["du_du_lieu"] is False
    assert body["matched"] == []
    assert body["dien_giai"] is None
    assert "chưa đủ dữ liệu" in body["message"].lower()
    assert dem["n"] == 0                              # KHÔNG gọi LLM cho video thiếu dữ liệu


def test_dien_giai_kenh_luu_vao_ban_ghi(tmp_path, monkeypatch):
    # Chẩn đoán qua route lưu NGUYÊN dien_giai_kenh vào bản ghi (để xem lại không gọi API)
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    rec = bl.doc_mot_bao_cao("nv", bid)
    assert rec is not None and rec.get("dien_giai_kenh") is not None
    assert rec["dien_giai_kenh"]["answer"] is not None


def test_xem_lai_dung_bang_4_truc_khong_goi_api(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    dem = _spy_llm(monkeypatch)
    r = c.get(f"/bao-cao-lich-su/{bid}")
    assert r.status_code == 200
    assert "veBangVideo(" in r.text                  # dựng lại bảng phán quyết 4 trục từ file gốc
    assert "Chẩn đoán CẢ KÊNH" in r.text
    assert dem["n"] == 0                             # xem lại KHÔNG gọi API (đọc cache)


def test_bao_cao_cu_khong_cache_kenh_van_dung_duoc(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    # mô phỏng báo cáo CŨ (lưu trước khi có tính năng cache): xóa dien_giai_kenh
    ds = bl.doc_bao_cao_list("nv")
    for rec in ds:
        rec.pop("dien_giai_kenh", None)
    bl._ghi_nguyen_tu(bl._duong_dan("nv"), ds)
    dem = _spy_llm(monkeypatch)
    r = c.get(f"/bao-cao-lich-su/{bid}")
    assert r.status_code == 200 and "veBangVideo(" in r.text   # vẫn dựng bảng, không vỡ
    assert dem["n"] == 0                                        # KHÔNG gọi API để bù


def test_file_goc_mat_khong_vo_trang(tmp_path, monkeypatch):
    from pathlib import Path
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    Path(bl.doc_mot_bao_cao("nv", bid)["duong_dan_goc"]).unlink()   # xóa file gốc
    r = c.get(f"/bao-cao-lich-su/{bid}")
    assert r.status_code == 200
    assert "Không tìm thấy file gốc" in r.text                 # fallback note
    assert "Chẩn đoán cả kênh (đã lưu)" in r.text              # tóm tắt cũ vẫn hiện


# ═══ Cờ da_co_bao_cao (Analyze / Xem báo cáo) + nút Phân tích lại (lam_moi) ═══

def test_route_chan_doan_co_da_co_bao_cao_false_luc_moi(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    body = _chan_doan_kq(c)
    # Report vừa chẩn đoán (id mới) → chưa video nào có báo cáo → tất cả cờ False
    assert body["videos"] and all(v["da_co_bao_cao"] is False for v in body["videos"])


def test_gan_da_co_bao_cao_dung_theo_cap_id_chi_muc(tmp_path, monkeypatch):
    import src.main as app_mod
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    r = c.post("/chan-doan/video", data={"chi_muc": "0", "bao_cao_id": bid})
    assert r.json().get("dien_giai")                 # video 0 (giật tít) có diễn giải → được cache
    videos = [{"chi_muc": i} for i in range(6)]
    app_mod._gan_da_co_bao_cao(videos, "nv", bid)
    assert videos[0]["da_co_bao_cao"] is True         # đã cache
    assert all(videos[i]["da_co_bao_cao"] is False for i in range(1, 6))   # còn lại chưa


def test_route_video_lam_moi_goi_llm_ghi_de_cache(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    dem = _spy_llm(monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    dem["n"] = 0
    c.post("/chan-doan/video", data={"chi_muc": "0", "bao_cao_id": bid})     # cache lần đầu
    assert dem["n"] == 1
    c.post("/chan-doan/video", data={"chi_muc": "0", "bao_cao_id": bid})     # đọc cache, không gọi
    assert dem["n"] == 1
    c.post("/chan-doan/video", data={"chi_muc": "0", "bao_cao_id": bid, "lam_moi": "1"})  # ép mới
    assert dem["n"] == 2                              # lam_moi=1 → BỎ cache, gọi LLM mới (ghi đè)


# ═══ Tầng 2: LLM diễn giải khung 9 mục có neo (cache theo báo cáo, van chống bịa) ═══

def _spy_muc(monkeypatch):
    """Đếm số lần gọi LLM diễn giải MỤC + bắt (ma, bối cảnh) — chứng minh chỉ gọi mục có KQ."""
    import src.main as app_mod
    dem = {"n": 0, "goi": []}
    that = app_mod.dien_giai.dien_giai_muc_kenh
    def spy(muc, boi_canh_khac, user=None, loai_kenh_ctx=""):
        dem["n"] += 1
        dem["goi"].append((muc["ma"], boi_canh_khac, loai_kenh_ctx))
        return that(muc, boi_canh_khac, user=user, loai_kenh_ctx=loai_kenh_ctx)
    monkeypatch.setattr(app_mod.dien_giai, "dien_giai_muc_kenh", spy)
    return dem


def test_9muc_llm_chi_goi_cho_muc_co_ket_qua(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    dem = _spy_muc(monkeypatch)
    c = _login("nv")
    b = _chan_doan_kq(c)
    bc = {m["ma"]: m for m in b["bao_cao_kenh"]}
    co = {ma for ma, m in bc.items() if m["trang_thai"] == "co_ket_qua"}
    assert co == {"A1", "B3"}                       # report tối giản → chỉ Pareto + ma trận có KQ
    assert dem["n"] == len(co)                       # LLM gọi ĐÚNG số mục có kết quả
    for ma, m in bc.items():
        if m["trang_thai"] == "co_ket_qua":
            assert m.get("dien_giai") and m["dien_giai"]["answer"]
        else:
            assert not m.get("dien_giai")            # mục chưa đủ/chưa có số liệu KHÔNG diễn giải


def test_9muc_prompt_co_so_lieu_muc_va_boi_canh_muc_khac(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    import src.main as app_mod
    prompts = []
    wr, _ = app_mod.dien_giai._lay_writer()          # V2: writer nằm trong module dien_giai
    that = wr.generate
    monkeypatch.setattr(wr, "generate",
                        lambda s, u: (prompts.append(u), that(s, u))[1])
    _login("nv").post("/chan-doan", files={"file": ("report.csv", _report_yt())})
    p_a1 = next((p for p in prompts if "MỤC ĐANG DIỄN GIẢI: [A1]" in p), None)
    assert p_a1 is not None
    assert "Top 1" in p_a1                            # số liệu THÔ của chính mục A1
    assert "BỐI CẢNH" in p_a1 and "[B3]" in p_a1      # bản tóm tắt các mục KHÁC để nối ý


# ═══ 08/08 (§12.2, §12.3): tương quan + xu hướng tháng nối vào bối cảnh diễn giải 9-mục ═══

def test_dong_tong_quan_bo_sung_render_dung_dinh_dang():
    from src.main import _dong_tong_quan_bo_sung

    dong = _dong_tong_quan_bo_sung({
        "tuong_quan": [{"bien_1": "duration_min", "bien_2": "retention", "he_so": -0.48, "so_mau": 28}],
        "xu_huong_thang": {"retention": [{"thang": "2026-06", "trung_vi": 0.254, "so_video": 9},
                                         {"thang": "2026-07", "trung_vi": 0.201, "so_video": 12}]},
    })
    assert any("duration_min↔retention = -0.48 (n=28)" in d for d in dong)
    assert any("2026-06=0.254 (n=9) → 2026-07=0.201 (n=12)" in d for d in dong)


def test_dong_tong_quan_bo_sung_rong_khi_thieu_du_lieu():
    from src.main import _dong_tong_quan_bo_sung

    assert _dong_tong_quan_bo_sung(None) == []
    assert _dong_tong_quan_bo_sung({"tuong_quan": [], "xu_huong_thang": None}) == []


def test_9muc_report_toi_gian_khong_du_du_lieu_tuong_quan_khong_bao_loi(tmp_path, monkeypatch):
    """Fixture report tối giản (6 video, không có Duration/Publish time) → tương quan + xu
    hướng tháng đều rỗng — chan_doan_toan_bo/diễn giải KHÔNG được vỡ vì thiếu cột."""
    _users(tmp_path, monkeypatch)
    dem = _spy_muc(monkeypatch)
    c = _login("nv")
    b = _chan_doan_kq(c)
    assert dem["n"] > 0                                # vẫn diễn giải bình thường
    for _, boi_canh_khac, _ in dem["goi"]:
        assert "Tương quan số liệu toàn kênh" not in boi_canh_khac
        assert "Xu hướng" not in boi_canh_khac


def test_9muc_cache_va_xem_lai_khong_goi_llm(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    rec = bl.doc_mot_bao_cao("nv", bid)
    assert set(rec["dien_giai_9muc"].keys()) == {"A1", "B3"}   # cache đúng mục có KQ
    dem = _spy_muc(monkeypatch)
    r = c.get(f"/bao-cao-lich-su/{bid}")
    assert r.status_code == 200 and dem["n"] == 0             # xem lại đọc CACHE, không gọi LLM


def test_9muc_lam_moi_goi_llm_ghi_de_cache(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    c = _login("nv")
    bid = _chan_doan_bid(c)
    dem = _spy_muc(monkeypatch)
    r = c.post("/chan-doan/muc-lam-moi", data={"bao_cao_id": bid})
    assert r.status_code == 200 and set(r.json()["dien_giai_9muc"].keys()) == {"A1", "B3"}
    assert dem["n"] == 2                             # Làm mới → gọi LLM MỚI cho 2 mục có KQ
