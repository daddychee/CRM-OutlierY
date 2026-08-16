"""Test bảng "câu kho chưa trả lời được" (Ý 1 Đợt 3) — log tự động + gộp/đếm + quyền xem."""

import csv
import json
import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

from pathlib import Path

from fastapi.testclient import TestClient

import src.main as app_module
from src.main import app
from src.kho_thieu import doc_tat_ca_nguon, ghi_cau_kho_thieu, gop_va_dem
from src.qa_pipeline import KHONG_CO_TAI_LIEU, la_cau_khong_tra_loi_duoc

# V2: claims từ gateway thay users.txt — bảng bộ phận×level giữ nguyên ý cũ.
from claims_v2 import client_claims, client_khach

HO_SO = {"ql": ("Kinh doanh", 4), "nv": ("Kinh doanh", 2)}


def _users_file(tmp_path, monkeypatch, noi_dung=None):
    """V2: không còn USERS_FILE — giữ chữ ký để call-site cũ nguyên vẹn (no-op)."""


def _dang_nhap(ten, mk="mk"):
    return client_claims(app, ten, *HO_SO[ten])


def _so():
    return Path(os.environ["KHO_TAI_LIEU"]) / "cau_kho_thieu.csv"


def _gia_lap_kho_thieu(monkeypatch, bi_chan: bool):
    """Mock kho luôn có tài liệu công khai → ép qa.hoi trả 'kho rỗng' đóng hộp."""
    monkeypatch.setattr(app_module.qa, "hoi", lambda *a, **k: {
        "answer": KHONG_CO_TAI_LIEU, "sources": [], "critic_count": 0,
        "reviews": [], "rewritten": False, "bi_chan_quyen": bi_chan})


def test_kho_thieu_that_ghi_kem_context(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    _gia_lap_kho_thieu(monkeypatch, bi_chan=False)
    c = _dang_nhap("nv")

    lich_su = [{"hoi": "câu 1", "dap": "x"}, {"hoi": "câu 2", "dap": "y"},
               {"hoi": "câu 3", "dap": "z"}, {"hoi": "câu 4", "dap": "t"}]
    c.post("/hoi", data={"question": "chính sách nghỉ phép?",
                         "history": json.dumps(lich_su)})

    dong = list(csv.reader(_so().open(encoding="utf-8-sig")))
    assert len(dong) == 2  # header + 1
    assert dong[1][1] == "chính sách nghỉ phép?"
    assert dong[1][2] == "Kinh doanh"                       # bộ phận người hỏi
    assert dong[1][3] == "câu 4 ← câu 3 ← câu 2"            # đúng 3 câu gần nhất, mới trước
    assert dong[1][0]                                        # có thời gian


def test_la_cau_khong_tra_loi_duoc():
    assert la_cau_khong_tra_loi_duoc("Tài liệu chưa nêu cụ thể điều này. [KD-1]") is True
    assert la_cau_khong_tra_loi_duoc(KHONG_CO_TAI_LIEU) is True          # kho 0 chunk
    assert la_cau_khong_tra_loi_duoc("Tài liệu KHÔNG NÊU khung giờ.") is True
    assert la_cau_khong_tra_loi_duoc(
        "Đăng video khung 19h-21h theo quy trình [KD-2026-0042].") is False


def test_bug_A_writer_that_tra_chua_neu_van_ghi(tmp_path, monkeypatch):
    """BUG A (điều tra 19/07): writer thật trả "Tài liệu chưa nêu cụ thể X" KHÁC hằng
    KHONG_CO_TAI_LIEU (hằng chỉ trả khi 0 chunk) — so bằng tuyệt đối trượt, không ghi sổ."""
    _users_file(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module.qa, "hoi", lambda *a, **k: {
        "answer": "Tài liệu chưa nêu cụ thể điều này. [KD-2026-71369B]",
        "sources": [], "critic_count": 0, "reviews": [], "rewritten": False,
        "bi_chan_quyen": False})
    _dang_nhap("nv").post("/hoi", data={"question": "lịch nghỉ phép tháng 8?"})
    dong = list(csv.reader(_so().open(encoding="utf-8-sig")))
    assert dong[1][1] == "lịch nghỉ phép tháng 8?"


def test_bi_chan_quyen_khong_ghi(tmp_path, monkeypatch):
    """Câu bị chặn quyền: tài liệu ĐÃ CÓ — ghi vào sổ sẽ báo nhầm 'cần soạn tài liệu'."""
    _users_file(tmp_path, monkeypatch)
    _gia_lap_kho_thieu(monkeypatch, bi_chan=True)
    _dang_nhap("nv").post("/hoi", data={"question": "cách tạo google adsense?"})
    assert not _so().exists()


def test_tra_loi_duoc_khong_ghi(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)  # qa mock thật: kho mẫu có tài liệu → trả lời được
    _dang_nhap("nv").post("/hoi", data={"question": "quy trình đăng video?"})
    assert not _so().exists()


def test_khach_thieu_bo_phan_khong_ghi(monkeypatch):
    # V2: 'chế độ mở' hệ cũ không còn — ca tương đương là claims THIẾU bộ phận
    _gia_lap_kho_thieu(monkeypatch, bi_chan=False)
    client_khach(app).post("/hoi", data={"question": "x"})
    assert not _so().exists()


def test_stream_kho_thieu_cung_ghi(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)

    def stream_gia(*a, **k):
        yield {"type": "token", "data": KHONG_CO_TAI_LIEU}
        yield {"type": "done", "data": {"critic_count": 0, "bi_chan_quyen": False}}

    monkeypatch.setattr(app_module.qa, "hoi_stream", stream_gia)
    r = _dang_nhap("nv").post("/hoi-dap/stream",
                              data={"question": "lương thưởng tết?", "history": "[]"})
    assert r.status_code == 200
    dong = list(csv.reader(_so().open(encoding="utf-8-sig")))
    assert dong[1][1] == "lương thưởng tết?"


def test_gop_va_dem_cau_giong_nhau():
    muc = [
        {"thoi_gian": "2026-07-19T09:00:00", "cau_hoi": "Chính sách nghỉ phép?",
         "bo_phan": "Kinh doanh", "context": "ctx1"},
        {"thoi_gian": "2026-07-19T10:00:00", "cau_hoi": "chính sách nghỉ phép",
         "bo_phan": "IT", "context": "ctx2"},  # khác hoa/thường + dấu câu → vẫn gộp
        {"thoi_gian": "2026-07-19T08:00:00", "cau_hoi": "câu khác hẳn",
         "bo_phan": "IT", "context": ""},
    ]
    nhom = gop_va_dem(muc)
    assert len(nhom) == 2
    assert nhom[0]["so_lan"] == 2                            # câu hỏi nhiều lần lên đầu
    assert nhom[0]["gan_nhat"] == "2026-07-19T10:00:00"
    assert "Kinh doanh" in nhom[0]["bo_phan"] and "IT" in nhom[0]["bo_phan"]
    assert nhom[0]["contexts"] == ["ctx1", "ctx2"]


def test_trang_kho_thieu_quyen_va_gop_ca_phan_hoi(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    # nguồn 1: sổ tự động
    ghi_cau_kho_thieu("chính sách nghỉ phép?", "Kinh doanh", [], "2026-07-19T09:00:00")
    # nguồn 2: phản hồi 👎 — 1 câu CHỈ có 👎 (vào bảng) + 1 câu bị chặn (loại)
    c_nv = _dang_nhap("nv")
    c_nv.post("/phan-hoi", data={"question": "trả lời dở về lương", "answer": "a",
                                 "rating": "te", "bi_chan_quyen": "false"})
    c_nv.post("/phan-hoi", data={"question": "câu bị chặn quyền", "answer": "a",
                                 "rating": "te", "bi_chan_quyen": "true"})

    assert c_nv.get("/kho-thieu").status_code == 403         # level 2 → chặn

    r = _dang_nhap("ql").get("/kho-thieu")                   # Manager 4 → vào
    assert r.status_code == 200
    assert "chính sách nghỉ phép?" in r.text                 # từ log tự động
    assert "trả lời dở về lương" in r.text                   # 👎-riêng vẫn hiện
    assert "câu bị chặn quyền" not in r.text                  # 👎 bị chặn quyền → loại


def test_khong_dem_dup_cau_vua_log_vua_bi_che(tmp_path, monkeypatch):
    """Bug đếm đúp (điều tra 19/07): 1 lượt hỏi vào CẢ log tự động LẪN 👎 → phải đếm 1.
    Câu 👎 chỉ khác hoa thường/dấu câu vẫn phải nhận là trùng (cùng hàm chuẩn hóa)."""
    _users_file(tmp_path, monkeypatch)
    ghi_cau_kho_thieu("Tôi tên là gì?", "Kinh doanh", [], "2026-07-19T11:32:52")
    c = _dang_nhap("nv")
    c.post("/phan-hoi", data={"question": "tôi tên là gì", "answer": "a",
                              "rating": "te", "bi_chan_quyen": "false"})   # trùng câu đã log
    c.post("/phan-hoi", data={"question": "câu chỉ bị chê", "answer": "a",
                              "rating": "te", "bi_chan_quyen": "false"})   # 👎-riêng → giữ

    nhom = gop_va_dem(doc_tat_ca_nguon())
    dem = {n["cau_hoi"]: n["so_lan"] for n in nhom}
    assert dem == {"Tôi tên là gì?": 1, "câu chỉ bị chê": 1}


def test_co_tay_ghi_dung_dong(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    r = _dang_nhap("nv").post("/co-tay", data={
        "question": "lịch nghỉ phép tháng 8?", "answer": "Tài liệu chưa nêu...",
        "sources": "KD-2026-7EACA7", "context": "câu 2 ← câu 1"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    so = Path(os.environ["KHO_TAI_LIEU"]) / "co_tay_kho_thieu.csv"
    dong = list(csv.reader(so.open(encoding="utf-8-sig")))
    assert len(dong) == 2  # header + 1
    assert dong[1][1:] == ["lịch nghỉ phép tháng 8?", "Kinh doanh",
                           "câu 2 ← câu 1", "KD-2026-7EACA7"]
    assert dong[1][0]  # có thời gian


def test_co_tay_khach_khong_ghi(monkeypatch):
    r = client_khach(app).post("/co-tay", data={"question": "x"})  # thiếu bộ phận
    assert r.status_code == 200
    assert not (Path(os.environ["KHO_TAI_LIEU"]) / "co_tay_kho_thieu.csv").exists()


def test_bang_gop_co_tay_danh_dau_va_dedup(tmp_path, monkeypatch):
    """Cờ tay trùng câu log tự động → đếm 1 nhưng nhóm mang dấu cờ (icon cau-flag); cờ tay
    câu riêng vẫn hiện + được ưu tiên xếp trên câu chỉ-auto dù số lần thấp hơn."""
    _users_file(tmp_path, monkeypatch)
    ghi_cau_kho_thieu("chính sách lương?", "Kinh doanh", [], "2026-07-19T09:00:00")
    ghi_cau_kho_thieu("câu chỉ auto", "Kinh doanh", [], "2026-07-19T12:00:00")
    ghi_cau_kho_thieu("câu chỉ auto", "Kinh doanh", [], "2026-07-19T13:00:00")
    c = _dang_nhap("nv")
    c.post("/co-tay", data={"question": "Chính sách lương",   # trùng (khác hoa/dấu câu)
                            "context": "ctx cờ tay"})
    c.post("/co-tay", data={"question": "câu riêng cờ tay"})

    nhom = gop_va_dem(doc_tat_ca_nguon())
    dem = {n["cau_hoi"]: (n["so_lan"], n["co_tay"]) for n in nhom}
    assert dem == {"chính sách lương?": (1, True),   # dedup + mang dấu
                   "câu riêng cờ tay": (1, True),
                   "câu chỉ auto": (2, False)}
    assert [n["co_tay"] for n in nhom[:2]] == [True, True]  # cờ tay trên, dù auto 2 lần

    r = _dang_nhap("ql").get("/kho-thieu")
    assert "cau-flag" in r.text and "câu riêng cờ tay" in r.text


def test_hoi_2_lan_that_van_dem_2(tmp_path, monkeypatch):
    """Đối chứng: hỏi 2 lần THẬT (2 dòng log khác thời gian) vẫn phải đếm 2."""
    _users_file(tmp_path, monkeypatch)
    ghi_cau_kho_thieu("lịch nghỉ phép?", "Kinh doanh", [], "2026-07-19T09:00:00")
    ghi_cau_kho_thieu("lịch nghỉ phép?", "Kinh doanh", [], "2026-07-19T10:00:00")
    nhom = gop_va_dem(doc_tat_ca_nguon())
    assert nhom[0]["so_lan"] == 2 and nhom[0]["gan_nhat"] == "2026-07-19T10:00:00"


def test_trang_rong_bao_kho_dap_ung_tot(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    r = _dang_nhap("ql").get("/kho-thieu")
    assert "The knowledge base is doing well" in r.text


# ═══ Nút xóa câu không phù hợp (31/07/2026) ═══

def test_manager_xoa_cau_khoi_bang_cho(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    ghi_cau_kho_thieu("Chung kết WC tối nay có đăng không?", "Kinh doanh", [], "2026-07-31T09:00:00")
    ghi_cau_kho_thieu("chính sách nghỉ phép?", "Kinh doanh", [], "2026-07-31T09:01:00")
    ql = _dang_nhap("ql")
    assert "Chung kết WC" in ql.get("/kho-thieu").text

    r = ql.post("/kho-thieu/xoa-cau", data={"cau_hoi": "Chung kết WC tối nay có đăng không?"})
    assert r.status_code == 200 and r.json()["ok"] is True

    trang = ql.get("/kho-thieu").text
    assert "Chung kết WC" not in trang            # câu đã xóa biến khỏi bảng chờ
    assert "chính sách nghỉ phép" in trang        # câu khác không bị vạ lây
    # sổ loại trừ có VẾT ai xóa / lúc nào — khôi phục được bằng cách sửa file
    so = json.loads((Path(os.environ["KHO_TAI_LIEU"]) / "cau_kho_thieu_da_xoa.json")
                    .read_text(encoding="utf-8"))
    assert so[0]["ai"] == "ql" and so[0]["thoi_gian"]
    # log gốc CHỈ-GHI-THÊM không bị đụng — lịch sử còn nguyên
    assert "Chung kết WC" in _so().read_text(encoding="utf-8-sig")


def test_xoa_cau_an_moi_bien_the_giong_nhau(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    ghi_cau_kho_thieu("GA là gì?", "Kinh doanh", [], "2026-07-31T09:00:00")
    ghi_cau_kho_thieu("ga là gì", "Kinh doanh", [], "2026-07-31T09:02:00")
    ql = _dang_nhap("ql")
    ql.post("/kho-thieu/xoa-cau", data={"cau_hoi": "GA là gì?"})
    trang = ql.get("/kho-thieu").text
    assert "GA là gì" not in trang and "ga là gì" not in trang   # cùng khóa chuẩn hóa → ẩn cả


def test_nhan_vien_khong_duoc_xoa_cau(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    ghi_cau_kho_thieu("câu nào đó", "Kinh doanh", [], "2026-07-31T09:00:00")
    r = _dang_nhap("nv").post("/kho-thieu/xoa-cau", data={"cau_hoi": "câu nào đó"})
    assert r.status_code == 403                   # yeu_cau_quan_ly chặn ở SERVER