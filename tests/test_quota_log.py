# -*- coding: utf-8 -*-
"""Test quota log chuẩn P4 (nen/common/quota_log.py) — nguồn cho trang API Keys:
ghi JSON-lines một dòng/lượt, đọc + lọc theo ngày/API/khóa/app, tổng lượt hôm nay
theo đuôi khóa; chưa có log → rỗng, KHÔNG bịa số."""
from datetime import date

import pytest

from nen.common import quota_log


@pytest.fixture(autouse=True)
def _logs_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))


def test_ghi_va_doc_loc():
    quota_log.ghi("youtube", "7f2a", "seo-optimize", "channel_video_ids",
                  luot=120, quota_tieu=360)
    quota_log.ghi("llm", "9k2f", "ai-agent", "writer", luot=14)
    quota_log.ghi("youtube", "b3e8", "radary", "harvest", luot=2400,
                  quota_tieu=2400)
    assert len(quota_log.doc()) == 3                       # mặc định hôm nay
    assert [d["khoa_duoi"] for d in quota_log.doc()] == ["b3e8", "9k2f", "7f2a"]
    assert len(quota_log.doc(api="youtube")) == 2
    assert quota_log.doc(khoa_duoi="9k2f")[0]["viec"] == "writer"
    assert quota_log.doc(app="radary")[0]["quota_tieu"] == 2400
    assert quota_log.doc(ngay="2020-01-01") == []          # ngày không log → rỗng


def test_luot_hom_nay_gop_theo_duoi():
    assert quota_log.luot_hom_nay() == {}                  # chưa log → rỗng thật
    quota_log.ghi("youtube", "7f2a", "seo-optimize", "extract", luot=100)
    quota_log.ghi("youtube", "7f2a", "seo-optimize", "extract", luot=20)
    quota_log.ghi("llm", "9k2f", "ai-agent", "writer")     # luot mặc định 1
    assert quota_log.luot_hom_nay() == {"7f2a": 120, "9k2f": 1}


def test_dong_hong_khong_vo_trang(tmp_path):
    quota_log.ghi("llm", "9k2f", "ai-agent", "writer")
    hom_nay = date.today()
    f = (tmp_path / "logs" / "quota" / f"{hom_nay:%Y}" / f"{hom_nay:%m}"
         / f"{hom_nay.isoformat()}.log")
    with open(f, "a", encoding="utf-8") as fh:
        fh.write("dong-rac-khong-json\n")
    assert len(quota_log.doc()) == 1                       # dòng hỏng bị bỏ qua
