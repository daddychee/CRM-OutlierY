# -*- coding: utf-8 -*-
"""Sổ gọi LLM (01/09): call THẬT ghi 1 dòng per app·vai; MOCK không ghi
(không đổ số giả vào sổ usage); sổ chết không hỏng call."""
from src.llm.factory import get_provider


def test_provider_gan_vai_mock_khong_ghi_that_ghi(tmp_path, monkeypatch):
    monkeypatch.setenv("SO_GOI_DIR", str(tmp_path / "sg"))
    monkeypatch.setenv("WRITER_PROVIDER", "openai_compatible")
    monkeypatch.setenv("WRITER_MODEL", "glm-4.5-air")
    p = get_provider("writer")   # conftest ép WRITER_MOCK_MODE=true
    assert p.vai == "writer"
    p.generate("s", "u")
    assert not list((tmp_path / "sg").rglob("*.log")), "mock không được ghi sổ"
    p._ghi_so(123, True)
    f = next((tmp_path / "sg").rglob("*.log"))
    nd = f.read_text(encoding="utf-8")
    assert '"app": "ai-agent"' in nd and '"viec": "writer"' in nd
    assert '"model": "glm-4.5-air"' in nd


def test_ghi_so_nuot_loi(monkeypatch, tmp_path):
    monkeypatch.setenv("SO_GOI_DIR", "Z:/khong-ton-tai/x")
    p = get_provider("writer")
    p._ghi_so(1, True)  # không raise là đạt


def test_stream_that_cung_ghi_so(tmp_path, monkeypatch):
    """Vá 05/09: đường stream (đường tiêu CHÍNH của hỏi–đáp) trước đây không ghi
    dòng nào → trần/ngày + Command Center mù. Giờ call thật qua stream = 1 dòng
    sổ (token None = chưa đo, KHÔNG phải 0 giả)."""
    from types import SimpleNamespace
    monkeypatch.setenv("SO_GOI_DIR", str(tmp_path / "sg"))
    monkeypatch.setenv("WRITER_PROVIDER", "openai_compatible")
    monkeypatch.setenv("WRITER_MODEL", "glm-4.5-air")

    def create(**kw):
        assert kw.get("stream") is True
        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="abc"))])
        return iter([chunk])

    p = get_provider("writer")   # mock — rồi thay client giả để đi nhánh thật
    p.mock = False
    p.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert "".join(p.generate_stream("s", "u")) == "abc"
    f = next((tmp_path / "sg").rglob("*.log"))
    nd = f.read_text(encoding="utf-8")
    assert '"dich_vu": "llm"' in nd and '"viec": "writer"' in nd
    assert '"token_vao"' not in nd, "stream chưa đo token — không được ghi 0 giả"
