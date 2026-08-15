"""Test kho-thiếu: ẩn câu đã gom khỏi bảng chờ (loc_bang_cho, so bằng _chuan_hoa) +
xóa nhóm (xoa_nhom + route). Xóa nhóm xong câu tự hiện lại vì bảng chờ tính ĐỘNG từ
log mỗi lần load — không lưu trạng thái riêng nên không cần cơ chế khôi phục."""

import os

os.environ["MOCK_MODE"] = "true"

from fastapi.testclient import TestClient

from src.main import app
from src.kho_thieu import doc_nhom, ghi_cau_kho_thieu, ghi_nhom, loc_bang_cho, xoa_nhom


def _seed(cau):
    ghi_cau_kho_thieu(cau, "Kinh doanh", [], "2026-07-20T10:00:00")


# ─────────────── PHẦN A — loc_bang_cho ẩn câu đã gom ───────────────

def test_loc_bang_cho_an_cau_thuoc_nhom_chua_giai():
    _seed("Câu X hỏi gì?"); _seed("Câu Y hỏi gì?")
    # nhóm CHƯA giải gom "câu x hỏi gì" — KHÁC hoa/dấu để chứng minh _chuan_hoa khớp
    nhom = [{"da_giai_quyet": False, "cac_cau": [{"cau": "câu x hỏi gì"}]}]
    con_lai = [n["cau_hoi"] for n in loc_bang_cho(nhom)]
    assert "Câu Y hỏi gì?" in con_lai            # câu chưa gom vẫn hiện
    assert "Câu X hỏi gì?" not in con_lai        # đã gom → ẩn khỏi bảng chờ


def test_loc_bang_cho_nhom_da_giai_khong_an():
    _seed("Câu X hỏi gì?")
    nhom = [{"da_giai_quyet": True, "cac_cau": [{"cau": "Câu X hỏi gì?"}]}]
    # nhóm ĐÃ giải không tính → câu KHÔNG bị ẩn theo diện "đã gom"
    assert any(n["cau_hoi"] == "Câu X hỏi gì?" for n in loc_bang_cho(nhom))


# ─────────────── PHẦN B — xoa_nhom ───────────────

def test_xoa_nhom_loai_dung_id_giu_nhom_khac():
    ghi_nhom([{"id": "aaa", "ten_chu_de": "A"}, {"id": "bbb", "ten_chu_de": "B"}])
    xoa_nhom("aaa")
    assert [n["id"] for n in doc_nhom()] == ["bbb"]   # loại đúng aaa, giữ bbb
    xoa_nhom("khong-co-id-nay")                        # id lạ → vô hại, không sập
    assert [n["id"] for n in doc_nhom()] == ["bbb"]


# ─────────────── PHẦN B — route xóa nhóm (Manager+, redirect whitelist) ───────────────

def _login(tmp_path, monkeypatch, dong):
    f = tmp_path / "users.txt"
    f.write_text(dong, encoding="utf-8")
    monkeypatch.setenv("USERS_FILE", str(f))
    c = TestClient(app)
    c.post("/dang-nhap", data={"ten": dong.split(":")[0], "mat_khau": "mk"})
    return c


def test_route_xoa_nhom_303_va_ve_whitelist(tmp_path, monkeypatch):
    ghi_nhom([{"id": "aaa", "ten_chu_de": "A"}])
    c = _login(tmp_path, monkeypatch, "ql:mk:Kinh doanh:4\n")
    r = c.post("/kho-thieu/xoa-nhom", data={"nhom_id": "aaa", "ve": "giam-sat"},
               follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/giam-sat"
    assert doc_nhom() == []                            # nhóm đã xóa thật → câu tự về bảng chờ

    ghi_nhom([{"id": "ccc", "ten_chu_de": "C"}])
    r2 = c.post("/kho-thieu/xoa-nhom", data={"nhom_id": "ccc", "ve": "chèn-bậy"},
                follow_redirects=False)
    assert r2.status_code == 303 and r2.headers["location"] == "/kho-thieu"  # ngoài whitelist


def test_route_xoa_nhom_chi_manager(tmp_path, monkeypatch):
    ghi_nhom([{"id": "aaa", "ten_chu_de": "A"}])
    c = _login(tmp_path, monkeypatch, "nv:mk:Kinh doanh:2\n")   # level 2 < Manager
    assert c.post("/kho-thieu/xoa-nhom", data={"nhom_id": "aaa"}).status_code == 403
    assert doc_nhom()[0]["id"] == "aaa"                # bị chặn ở server → không xóa
