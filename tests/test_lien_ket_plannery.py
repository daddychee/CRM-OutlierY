# -*- coding: utf-8 -*-
"""Ghi liên kết PlannerY vào danh bạ (K-xxx ↔ ch_xxx, N-xxx ↔ pr_xxx) — chiều
"đế biết khóa của app", chỉ Owner chạy nên đi bằng script chứ app không tự ghi.
Ghim: mặc định chỉ liệt kê · idempotent · KHÔNG tự đè liên kết đang trỏ khóa khác."""
import json

import pytest

from nen.common import danh_ba
from scripts import lien_ket_plannery as lk


@pytest.fixture()
def moi_truong(tmp_path, monkeypatch):
    monkeypatch.setenv("DANH_BA_DB", str(tmp_path / "danh_ba.db"))
    monkeypatch.setenv("PLANNER_DATA_DIR", str(tmp_path))
    conn = danh_ba.ket_noi()
    ng = danh_ba.them_ngach(conn, "Life In")
    kenh = danh_ba.them_kenh(conn, "Outland", ng)
    conn.commit()
    conn.close()
    (tmp_path / "plan.json").write_text(json.dumps({
        "projects": [{"id": "pr_1", "name": "Life In", "ngach_ma": ng,
                      "channels": [{"id": "ch_1", "name": "Outland", "kenh_ma": kenh},
                                   {"id": "ch_2", "name": "Chưa ghép"}]}],
    }, ensure_ascii=False), encoding="utf-8")
    return {"ngach": ng, "kenh": kenh}


def _lien_ket(ma):
    return ({t["ma"]: t for t in danh_ba.doc_danh_muc()}[ma].get("lien_ket") or {}).get("plannery")


def test_mac_dinh_chi_liet_ke(moi_truong, capsys):
    assert lk.chay(ghi=False) == 0
    assert "chỉ liệt kê" in capsys.readouterr().out
    assert _lien_ket(moi_truong["kenh"]) is None      # chưa ghi gì


def test_ghi_va_chay_lai_khong_nhan_doi(moi_truong):
    assert lk.chay(ghi=True) == 0
    assert _lien_ket(moi_truong["kenh"]) == "ch_1"
    assert _lien_ket(moi_truong["ngach"]) == "pr_1"
    # kênh chưa ghép mã đế thì không sinh liên kết rác
    assert len(lk.gom(json.loads((lk._duong_plan()).read_text(encoding="utf-8")))) == 2
    assert lk.chay(ghi=True) == 0                     # idempotent
    assert _lien_ket(moi_truong["kenh"]) == "ch_1"


def test_khong_tu_de_lien_ket_dang_tro_khoa_khac(moi_truong, capsys):
    conn = danh_ba.ket_noi()
    danh_ba.dat_lien_ket(conn, moi_truong["kenh"], "plannery", "ch_cu")
    conn.commit()
    conn.close()
    lk.chay(ghi=True)
    assert _lien_ket(moi_truong["kenh"]) == "ch_cu"   # giữ nguyên, không đè
    assert "KHÔNG tự đè" in capsys.readouterr().out
