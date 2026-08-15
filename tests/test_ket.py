# -*- coding: utf-8 -*-
"""Test két cấu hình (P3) — ghim: 2 ngăn config/secret, mã hóa thật, LLM theo vai."""
import pytest

from nen.ket_cau_hinh import ket


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    c = ket.ket_noi()
    yield c
    c.close()


def test_cau_hinh_set_get(conn):
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    assert ket.lay_cau_hinh(conn, "llm.writer.model") == "glm-4.5-air"
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-5")   # ghi đè
    assert ket.lay_cau_hinh(conn, "llm.writer.model") == "glm-5"
    assert ket.lay_cau_hinh(conn, "khong.co", "mac-dinh") == "mac-dinh"


def test_bi_mat_ma_hoa_that_trong_db(conn):
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-bi-mat-tuyet-doi-9999")
    # DB không được chứa plaintext ở BẤT KỲ đâu
    for r in conn.execute("SELECT gia_tri_ma FROM bi_mat").fetchall():
        assert "bi-mat-tuyet-doi" not in r["gia_tri_ma"]
    # nhưng giải mã ra đúng
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-bi-mat-tuyet-doi-9999"
    assert ket.lay_bi_mat(conn, "khong.co") is None


def test_liet_ke_khong_lo_secret(conn):
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-9999xyza")
    ds = ket.liet_ke(conn)
    assert ds["bi_mat"][0]["duoi"] == "xyza"
    assert "gia_tri_ma" not in ds["bi_mat"][0]
    assert not any("sk-9999" in str(v) for v in ds["bi_mat"][0].values())


def test_cau_hinh_llm_gop_du_va_mac_dinh_an_toan(conn):
    ket.dat_cau_hinh(conn, "llm.writer.provider", "openai_compatible")
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_cau_hinh(conn, "llm.writer.base_url", "https://api.z.ai/api/paas/v4")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-test-1234")
    ch = ket.cau_hinh_llm(conn, "writer")
    assert ch["model"] == "glm-4.5-air"
    assert ch["api_key"] == "sk-test-1234"
    assert ch["timeout"] == 60 and ch["retry"] == 0   # luật nền: bài học hệ cũ
    # vai chưa khai → rỗng, không bịa
    assert ket.cau_hinh_llm(conn, "vai-la")["provider"] == ""


def test_khoa_fernet_tu_sinh_va_tai_dung(conn, tmp_path):
    ket.dat_bi_mat(conn, "k", "gia-tri-1")
    assert (tmp_path / "ket.key").exists()
    # mở kết nối mới (cùng key file) vẫn giải mã được
    c2 = ket.ket_noi()
    assert ket.lay_bi_mat(c2, "k") == "gia-tri-1"
    c2.close()
