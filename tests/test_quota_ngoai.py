# -*- coding: utf-8 -*-
"""Quota dịch vụ ngoài TRA ĐƯỢC THẬT (01/09) — Apify có API /users/me trả
credit tháng (khác YouTube không cho tra). Nền tự hỏi bằng khóa trong két,
cache 30 phút (poll 15s không được dội Apify); lỗi/không khóa → None, không bịa.
"""
import json

import pytest

from nen.common import quota_ngoai


@pytest.fixture()
def san(tmp_path, monkeypatch):
    from nen.ket_cau_hinh import ket
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    quota_ngoai.xoa_cache()
    kc = ket.ket_noi()
    ket.them_api_key(kc, "apify", "apify_api_tokenThuNghiem1234")
    kc.commit()
    kc.close()


def test_doc_credit_va_cache(san, monkeypatch):
    dem = []

    def _gia(url, timeout=8):
        dem.append(url)
        assert "apify_api_tokenThuNghiem1234" in url  # dùng khóa két thật

        class _R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"data": {
                    "plan": {"id": "FREE", "monthlyUsageCreditsUsd": 5},
                    "currentBillingPeriod": {"usageUsd": 0.37}}}).encode()
        return _R()
    monkeypatch.setattr(quota_ngoai.urllib.request, "urlopen", _gia)
    kq = quota_ngoai.apify_credit()
    assert kq["tran_usd"] == 5 and kq["da_dung_usd"] == 0.37
    assert kq["con_usd"] == 4.63 and kq["goi"] == "FREE"
    # lượt 2 ăn cache — không gọi mạng lần nữa
    quota_ngoai.apify_credit()
    assert len(dem) == 1


def test_khong_khoa_apify_tra_none(tmp_path, monkeypatch):
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket-rong.db"))
    quota_ngoai.xoa_cache()
    assert quota_ngoai.apify_credit() is None


def test_mang_chet_tra_none_khong_no(san, monkeypatch):
    def _no(url, timeout=8):
        raise OSError("dut mang")
    monkeypatch.setattr(quota_ngoai.urllib.request, "urlopen", _no)
    assert quota_ngoai.apify_credit() is None
