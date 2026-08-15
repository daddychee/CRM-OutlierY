# -*- coding: utf-8 -*-
"""Test hợp đồng app (nen/rules/apps.json)."""
import json

from nen.common import hop_dong


def test_hop_dong_that_co_app_mau():
    apps = hop_dong.doc_hop_dong()
    assert any(a["slug"] == "app-mau" for a in apps)


def test_tim_app_khong_co_tra_none():
    assert hop_dong.tim_app("khong-ton-tai") is None


def test_muc_thieu_truong_bat_buoc_bi_bo_qua(tmp_path):
    f = tmp_path / "apps.json"
    f.write_text(json.dumps({"apps": [
        {"slug": "du", "ten": "Đủ", "cong": 9001, "health": "/health"},
        {"slug": "thieu-cong", "ten": "Thiếu cổng", "health": "/health"},
    ]}), encoding="utf-8")
    apps = hop_dong.doc_hop_dong(f)
    assert [a["slug"] for a in apps] == ["du"]
    assert apps[0]["tien_to"] == []  # mặc định được điền
