# -*- coding: utf-8 -*-
"""Ghim DEFAULT trong CODE của vector_client (sự cố 31/08/2026).

Bối cảnh: di trú V2→V3, start-all.ps1 không đặt MOCK_MODE → app rơi về default
mock, hỏi–đáp trên hệ thật trả từ KHO MẪU suốt từ cutover 22/08 (tab giám sát
B3 bắt được). Tiền lệ 1161072 (hybrid search): hành vi chuẩn của app phải nằm
trong DEFAULT CODE — .env/env không theo repo sang máy khác.

Test không đụng kho thật: tiêm module giả vào sys.modules trước khi dựng wrapper.
"""
import sys
import types


def _mo_dun_gia(monkeypatch, goi):
    fake_fe = types.ModuleType("fastembed")

    class _TE:
        def __init__(self, model):
            pass

        def embed(self, xs):
            return iter([[0.0] * 8])

    class _SE:
        def __init__(self, model):
            pass

    fake_fe.TextEmbedding = _TE
    fake_fe.SparseTextEmbedding = _SE
    fake_rr = types.ModuleType("fastembed.rerank.cross_encoder")

    class _CE:
        def __init__(self, model):
            pass

    fake_rr.TextCrossEncoder = _CE
    fake_qc = types.ModuleType("qdrant_client")

    class _QC:
        def __init__(self, url=None):
            goi["url"] = url

        def collection_exists(self, name):
            raise ConnectionError("test không nối kho thật")

    fake_qc.QdrantClient = _QC
    monkeypatch.setitem(sys.modules, "fastembed", fake_fe)
    monkeypatch.setitem(sys.modules, "fastembed.rerank.cross_encoder", fake_rr)
    monkeypatch.setitem(sys.modules, "qdrant_client", fake_qc)


def test_khong_env_default_la_chay_that_kho_6343(monkeypatch):
    from src import vector_client as vc
    monkeypatch.delenv("MOCK_MODE", raising=False)
    monkeypatch.delenv("QDRANT_URL", raising=False)
    goi = {}
    _mo_dun_gia(monkeypatch, goi)
    w = vc.QdrantClientWrapper()
    assert w.mock is False, "default phải CHẠY THẬT — mock là chế độ dev/test tự bật"
    assert "6343" in goi["url"], "default phải kho V3 :6343 — :6333 là kho V2 đã tắt"
    assert w._kho_ok is False  # van an toàn 01/08 vẫn ăn: kho chưa nối được, app vẫn lên


def test_env_mock_true_van_thang_default(monkeypatch):
    """Chiều ngược: conftest/test/dev đặt MOCK_MODE=true phải vẫn được tôn trọng."""
    from src import vector_client as vc
    monkeypatch.setenv("MOCK_MODE", "true")
    w = vc.QdrantClientWrapper()
    assert w.mock is True
