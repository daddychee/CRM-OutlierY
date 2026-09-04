# -*- coding: utf-8 -*-
"""Nối dây LỚP PHÒNG THỦ vào điểm-ra LLM (05/09, spec docs/phong-thu-api-ngoai.md):
van chạy TRƯỚC khi đụng client thật; mock không qua van (hành vi cũ không đổi)."""
import pytest

from nen.common import phong_thu
from src.llm.factory import get_provider
from src.llm.openai_compatible import OpenAICompatibleProvider


def test_mock_khong_qua_van_hanh_vi_cu(monkeypatch):
    # secret nằm ngay trong prompt nhưng MOCK không gọi ra ngoài → không chặn
    monkeypatch.setenv("PT_TEST_API_KEY", "sk-bimat-1234567890")
    p = get_provider("writer")   # conftest ép mock
    assert "MOCK" in p.generate("s", "co sk-bimat-1234567890 trong prompt")


def test_base_url_host_la_chan_tu_cua(monkeypatch):
    with pytest.raises(phong_thu.LoiPhongThu, match="allowlist"):
        OpenAICompatibleProvider(model="m", api_key="k",
                                 base_url="https://evil.example.com/v1", mock=False)


def test_base_url_hop_le_dung_duoc_client():
    p = OpenAICompatibleProvider(model="m", api_key="k",
                                 base_url="https://api.z.ai/api/paas/v4", mock=False)
    assert p.client is not None   # van cho qua, client dựng bình thường


def test_van_secret_chan_call_that_truoc_khi_dung_client(monkeypatch):
    monkeypatch.setenv("PT_TEST_API_KEY", "sk-bimat-1234567890")
    p = OpenAICompatibleProvider(model="m", mock=True)
    p.mock = False
    p.client = object()   # van phải chặn TRƯỚC khi đụng client — object trần là đủ
    with pytest.raises(phong_thu.LoiPhongThu, match="PT_TEST_API_KEY"):
        p.generate("he thong", "prompt lo key sk-bimat-1234567890")
    with pytest.raises(phong_thu.LoiPhongThu):
        list(p.generate_stream("he thong", "prompt lo key sk-bimat-1234567890"))


def test_van_tran_call_chan_ca_duong_stream(tmp_path, monkeypatch):
    import json
    from datetime import date
    monkeypatch.setenv("SO_GOI_DIR", str(tmp_path / "sg"))
    monkeypatch.setenv("LLM_TRAN_CALL_NGAY", "1")
    hom_nay = date.today().isoformat()
    d = tmp_path / "sg" / hom_nay[:4] / hom_nay[5:7]
    d.mkdir(parents=True)
    (d / f"{hom_nay}.log").write_text(
        json.dumps({"dich_vu": "llm"}) + "\n", encoding="utf-8")
    p = OpenAICompatibleProvider(model="m", mock=True)
    p.mock = False
    p.client = object()
    with pytest.raises(phong_thu.LoiPhongThu, match="LLM_TRAN_CALL_NGAY"):
        list(p.generate_stream("s", "u"))
