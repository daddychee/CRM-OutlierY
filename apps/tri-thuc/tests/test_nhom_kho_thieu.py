"""Test YC7 — gom nhóm câu kho-thiếu + tự đánh dấu đã giải quyết."""

import json
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.main import app
from src.kho_thieu import doc_nhom, tao_nhom

USERS = "ql:mk:Kinh doanh:4\nnv:mk:Kinh doanh:2\n"


def _users_file(tmp_path, monkeypatch):
    f = tmp_path / "users.txt"
    f.write_text(USERS, encoding="utf-8")
    monkeypatch.setenv("USERS_FILE", str(f))


def _dang_nhap(ten):
    c = TestClient(app)
    c.post("/dang-nhap", data={"ten": ten, "mat_khau": "mk"})
    return c


def _chunk(ma):
    return {"content": "x", "document_id": ma, "document_keyword": f"{ma}.docx",
            "similarity": 0.9, "document_metadata": {"doc_code": ma}}


def _rag_tra(cac_ma):
    return SimpleNamespace(search=lambda cau, filters=None, user=None: [_chunk(m) for m in cac_ma])


def test_tao_nhom_ghi_file_kem_baseline():
    nhom = tao_nhom("Lịch nghỉ", ["lịch nghỉ tháng 8?", "nghỉ ốm thế nào?"],
                    _rag_tra(["KD-1", "KD-2"]), "2026-07-19T15:00:00")
    assert nhom["id"] and nhom["da_giai_quyet"] is False
    tren_dia = doc_nhom()
    assert len(tren_dia) == 1 and tren_dia[0]["ten_chu_de"] == "Lịch nghỉ"
    assert tren_dia[0]["cac_cau"][0] == {"cau": "lịch nghỉ tháng 8?",
                                         "doc_codes_goc": ["KD-1", "KD-2"]}
    # file JSON hợp lệ trên đĩa (ghi nguyên tử)
    p = Path(os.environ["KHO_TAI_LIEU"]) / "nhom_kho_thieu.json"
    assert json.loads(p.read_text(encoding="utf-8"))[0]["id"] == nhom["id"]


def test_route_gom_chi_manager(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    r = _dang_nhap("ql").post("/kho-thieu/gom", follow_redirects=False,
                              data={"ten_chu_de": "Chủ đề A",
                                    "cau": ["câu 1?", "câu 2?"]})
    assert r.status_code == 303 and r.headers["location"] == "/kho-thieu"
    assert [c["cau"] for c in doc_nhom()[0]["cac_cau"]] == ["câu 1?", "câu 2?"]

    assert _dang_nhap("nv").post("/kho-thieu/gom", data={
        "ten_chu_de": "x", "cau": ["y"]}).status_code == 403   # level 2 → chặn


def test_trang_hien_nhom_dang_cho(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    tao_nhom("Chủ đề B", ["câu B?"], _rag_tra(["KD-1"]), "2026-07-19T15:00:00")
    r = _dang_nhap("ql").get("/kho-thieu")
    assert r.status_code == 200 and "Chủ đề B" in r.text and "câu B?" in r.text


# ---- (b) tự đánh dấu đã giải quyết + nút bổ sung tài liệu nối trang nhập ----

from src.kho_thieu import cap_nhat_nhom_da_giai


def test_nhom_tu_chuyen_da_giai_khi_moi_cau_co_tai_lieu_moi():
    tao_nhom("Lịch nghỉ", ["câu 1?", "câu 2?"], _rag_tra(["KD-1"]), "T1")
    # kho chưa thêm gì (search vẫn chỉ ra KD-1 = baseline) → CHƯA giải
    assert cap_nhat_nhom_da_giai(_rag_tra(["KD-1"]))[0]["da_giai_quyet"] is False
    # kho có tài liệu MỚI KD-9 → mọi câu giải → chuyển mục + LƯU xuống file
    assert cap_nhat_nhom_da_giai(_rag_tra(["KD-1", "KD-9"]))[0]["da_giai_quyet"] is True
    assert doc_nhom()[0]["da_giai_quyet"] is True


def test_nhom_chi_giai_mot_phan_thi_chua_chuyen():
    tao_nhom("Nửa vời", ["câu A?"], _rag_tra(["KD-1"]), "T1")
    tao_nhom("Nửa vời 2", ["câu B?"], _rag_tra(["KD-1", "KD-9"]), "T2")  # baseline rộng hơn
    kq = cap_nhat_nhom_da_giai(_rag_tra(["KD-1", "KD-9"]))
    trang_thai = {n["ten_chu_de"]: n["da_giai_quyet"] for n in kq}
    assert trang_thai == {"Nửa vời": True, "Nửa vời 2": False}  # nhóm 2 chưa có gì mới


def test_trang_nhap_dien_san_goi_y(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    r = _dang_nhap("ql").get("/?goi_y_tieu_de=L%E1%BB%8Bch%20ngh%E1%BB%89&goi_y_tu_khoa=ngh%E1%BB%89%20ph%C3%A9p")
    assert r.status_code == 200
    assert 'value="Lịch nghỉ"' in r.text                 # tiêu đề điền sẵn, sửa được
    assert 'value="nghỉ phép"' in r.text                 # từ khóa vào input ẩn → JS ra chip


def test_trang_kho_thieu_co_nut_bo_sung(tmp_path, monkeypatch):
    """Tạo nhóm qua CHÍNH route (baseline do client app chụp) → trang tính lại
    bằng đúng client đó nên nhóm còn 'đang chờ' → phải có nút Bổ sung tài liệu."""
    _users_file(tmp_path, monkeypatch)
    c = _dang_nhap("ql")
    c.post("/kho-thieu/gom", data={"ten_chu_de": "Chủ đề C", "cau": ["câu C?"]})
    r = c.get("/kho-thieu")
    assert doc_nhom()[0]["da_giai_quyet"] is False       # kho chưa thêm gì — còn chờ
    assert "Bổ sung tài liệu" in r.text and "goi_y_tieu_de=" in r.text
