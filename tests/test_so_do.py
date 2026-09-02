# -*- coding: utf-8 -*-
"""SƠ ĐỒ VẬN HÀNH SỐNG per app (02/09/2026 — Owner đặt hàng).

Sơ đồ khai NGOÀI code nen/rules/so_do/<slug>.json:
  {"nut": [{ma, ten, cot, loai?, suc_khoe?|canary?|tuyen?}], "canh": [[tu, den, nhan?]]}
- cot: 0..n — layout theo cột trái→phải (người dùng → tính năng → lõi → ngoài).
- binding trạng thái (UI tô màu SỐNG): suc_khoe=<tên module> / canary=<mã> /
  tuyen=<mã đường truyền>; không binding → nút trung tính.
Thêm/sửa sơ đồ = sửa JSON, không sửa code. API tổng-hợp trả kèm để màn App vẽ.
"""
import json

import pytest

from nen.common import so_do


@pytest.fixture()
def san(tmp_path, monkeypatch):
    d = tmp_path / "so_do"
    d.mkdir()
    (d / "stub-app.json").write_text(json.dumps({
        "nut": [
            {"ma": "team", "ten": "Team", "cot": 0, "loai": "nguoi"},
            {"ma": "hoi-dap", "ten": "Hỏi–đáp", "cot": 1,
             "canary": "tim-kiem-tra-ket-qua"},
            {"ma": "kho", "ten": "Kho vector", "cot": 2, "loai": "kho",
             "suc_khoe": "kho-vector"},
            {"ma": "zai", "ten": "Z.ai", "cot": 3, "loai": "ngoai",
             "tuyen": "z-ai"},
            {"thieu": "ma va ten"},
        ],
        "canh": [["team", "hoi-dap"], ["hoi-dap", "kho"],
                 ["hoi-dap", "zai", "writer"]],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SO_DO_LUAT_DIR", str(d))
    return d


def test_doc_bo_nut_thieu_truong_va_canh_mo_coi(san):
    sd = so_do.doc("stub-app")
    assert [n["ma"] for n in sd["nut"]] == ["team", "hoi-dap", "kho", "zai"]
    # cạnh trỏ nút không tồn tại → bỏ (sửa JSON tay dễ gõ nhầm, không được vỡ UI)
    (san / "stub-app.json").write_text(json.dumps({
        "nut": [{"ma": "a", "ten": "A", "cot": 0}],
        "canh": [["a", "khong-co"]]}, ensure_ascii=False), encoding="utf-8")
    sd = so_do.doc("stub-app")
    assert sd["canh"] == []


def test_khong_co_file_tra_none(san):
    assert so_do.doc("khong-ton-tai") is None


def test_tat_ca_vao_api_tong_hop(san, tmp_path, monkeypatch):
    import bcrypt
    from fastapi.testclient import TestClient

    from nen.iam import iam
    _goc = bcrypt.gensalt
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _goc(4))
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "owner-test", "mk-test", "Ban quản trị", 5,
                      phai_doi_mk=False)
    conn.close()
    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: [])
    monkeypatch.setattr(gw, "_apify_credit", lambda: None)
    client = TestClient(gw.app, follow_redirects=False)
    client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})
    b = client.get("/general/api/giam-sat/tong-hop").json()
    assert "so_do" in b
    assert [n["ma"] for n in b["so_do"]["stub-app"]["nut"]][0] == "team"


def test_so_do_ai_agent_that_hop_le():
    """Sơ đồ mẫu ai-agent trong repo: mọi binding phải trỏ thứ CÓ THẬT —
    suc_khoe trỏ module app khai, canary trỏ mã trong kịch bản."""
    sd = so_do.doc("ai-agent")
    assert sd, "thiếu nen/rules/so_do/ai-agent.json"
    from nen.common import canary
    ma_canary = {k["ma"] for k in canary.doc_kich_ban("ai-agent")}
    module_thuc = {"kho-vector", "catalog", "llm-writer", "search-canary"}
    for n in sd["nut"]:
        if n.get("canary"):
            assert n["canary"] in ma_canary, n
        if n.get("suc_khoe"):
            assert n["suc_khoe"] in module_thuc, n
