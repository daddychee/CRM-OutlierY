# -*- coding: utf-8 -*-
"""Bổ sung tác phẩm cho một giọng đã có (24/08, Owner yêu cầu).

Owner: "Tôi cần 1 UI để bổ sung tài liệu cho giọng văn. Hãy nghiên cứu kỹ xem có tích
hợp cùng được điểm nào trong UI cũ thay vì tạo mới hoàn toàn."

Tái dùng gần hết: /api/upload-corpus nhận file, /api/build chạy lại, poll + log + thẻ
số đã có. Mắt xích thiếu duy nhất: upload phải vào ĐÚNG thư mục corpus của hồ sơ đó —
A001 có corpus ở `authors/Carl Sagan/Cosmos`, không phải `uploads/<tên>`.
"""
import json

import pytest

from voiceprofile import server as vp


@pytest.fixture()
def kho(tmp_path, monkeypatch):
    goc = tmp_path / "kho"
    (goc / "authors" / "Carl Sagan" / "Cosmos").mkdir(parents=True)
    (goc / "authors" / "Carl Sagan" / "Cosmos" / "co.txt").write_text("cu", encoding="utf-8")
    monkeypatch.setattr(vp, "_REPO_ROOT", goc)
    monkeypatch.setattr(vp.library, "list_authors", lambda: [
        {"code": "A001", "name": "Carl Sagan",
         "corpus": str(goc / "authors" / "Carl Sagan" / "Cosmos"),
         "profile": str(goc / "authors" / "Carl Sagan" / "profile.json")}])
    return goc


def test_bo_sung_vao_DUNG_thu_muc_corpus_cua_ho_so(kho):
    r = vp._save_upload({"vao_ma": "A001", "files": [{"name": "moi.txt", "text": "van moi"}]})
    assert r["saved"] == 1
    dich = kho / "authors" / "Carl Sagan" / "Cosmos"
    assert r["dir"] == str(dich)
    assert (dich / "moi.txt").read_text(encoding="utf-8") == "van moi"
    assert (dich / "co.txt").exists(), "khong duoc dung file cu"


def test_khong_nhan_duong_dan_tu_client(kho):
    """Cung luat voi /api/kiem-chung: client gui MA, server tu tra thu vien."""
    r = vp._save_upload({"vao_ma": "../../etc", "files": [{"name": "x.txt", "text": "x"}]})
    assert "error" in r and "khong tim thay" in r["error"].lower()


def test_ten_file_bi_cat_ve_basename(kho):
    vp._save_upload({"vao_ma": "A001",
                     "files": [{"name": "../../thoat.txt", "text": "x"}]})
    assert (kho / "authors" / "Carl Sagan" / "Cosmos" / "thoat.txt").exists()
    assert not (kho / "thoat.txt").exists()


def test_khong_ghi_de_file_trung_ten(kho):
    """Nap hai lan cung ten file thi giu ca hai — bo sung khong duoc lam mat ban cu."""
    vp._save_upload({"vao_ma": "A001", "files": [{"name": "co.txt", "text": "ban moi"}]})
    d = kho / "authors" / "Carl Sagan" / "Cosmos"
    assert (d / "co.txt").read_text(encoding="utf-8") == "cu"
    assert any(p.name != "co.txt" and p.read_text(encoding="utf-8") == "ban moi"
               for p in d.glob("*.txt"))


def test_luong_tao_moi_khong_doi(kho):
    """Khong co vao_ma -> van ghi uploads/<ten> nhu cu."""
    r = vp._save_upload({"name": "Tac Gia Moi", "files": [{"name": "a.txt", "text": "x"}]})
    assert r["dir"] == str(kho / "uploads" / "Tac Gia Moi")


def test_ui_co_nut_bo_sung_va_dung_lai_luong_build():
    import pathlib
    ui = (pathlib.Path(vp.__file__).parent / "board.html").read_text(encoding="utf-8")
    assert 'id="hs_bosung"' in ui, "thieu nut Bo sung tac pham"
    assert "vao_ma" in ui, "UI phai gui ma ho so, khong gui duong dan"
    assert "guiBuild(" in ui, "phai dung lai luong build san co, khong viet luong moi"
