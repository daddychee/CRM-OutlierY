# -*- coding: utf-8 -*-
"""Niche Research vào V3 (APPS.md app 3 — Owner chen lên 18/08): hợp đồng app +
luật Permissions v2 — ghim thang V2 31/07+04/08: KD L2 xem · tao KD L3 (leader) ·
toan_quyen KD L4 (vai manager — Manager không ngang Owner) · quan_tri chỉ Owner."""
import bcrypt
import pytest

from nen.common.hop_dong import tim_app
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    c = iam.ket_noi()
    yield c
    c.close()


def _owner(conn):
    return iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner", "mk-owner", "Ban quản trị", 5, phai_doi_mk=False))


def test_hop_dong_niche_research():
    a = tim_app("niche-research")
    assert a and a["cong"] == 9113 and a["health"] == "/api/health"
    assert a["tien_to"] == ["/api", "/web"]              # đo từ registry V2
    assert a["giao_dien"] == "khung"                     # SPA mở qua /open giữ sidebar
    store = {d["ten"]: d for d in a["du_lieu"]}
    assert store["niche-projects"]["muc_quy"] == "vang"  # nghiên cứu ngách = VÀNG
    assert store["niche-projects"]["duong"] == "data/niche-research/projects"
    assert store["niche-invites"]["duong"] == "data/niche-research/data"


def test_luat_va_vai_niche_theo_thuong_quy(conn):
    """Ma trận mặc định: KD L2 vào; tao KD L3; toan_quyen KD L4 (vai manager);
    quan_tri chỉ Owner. Vai dịch dừng-tại-hit-đầu; user 'trắng' không nổ."""
    ow = _owner(conn)
    ca = [
        # (bộ phận, level) -> (vào, tao, toan_quyen, vai)
        (("Vận hành - Sản xuất", 2), (False, False, False, "-")),   # BP khác không vào
        (("Kinh doanh", 1), (False, False, False, "-")),            # KD L1 chưa đủ
        (("Kinh doanh", 2), (True, False, False, "viewer")),
        (("Kinh doanh", 3), (True, True, False, "leader")),
        (("Kinh doanh", 4), (True, True, True, "manager")),         # L4 → vai_xoa manager
        (("", 2), (False, False, False, "-")),                      # user "trắng" không nổ
    ]
    for i, ((bp, lv), (vao, tao, toan, vai)) in enumerate(ca):
        iam.tao_tai_khoan(conn, ow, f"u{i}", "123456", bp, lv)
        u = iam.claims_cua(iam.lay_tai_khoan(conn, f"u{i}"))
        assert iam.co_quyen(u, "vao", "niche-research", conn) == vao, (bp, lv)
        assert iam.co_quyen(u, "tao", "niche-research", conn) == tao, (bp, lv)
        assert iam.co_quyen(u, "toan_quyen", "niche-research", conn) == toan, (bp, lv)
        if vai != "-":
            assert iam.vai_cho_app(u, "niche-research", conn) == vai, (bp, lv)
    assert iam.vai_cho_app(ow, "niche-research", conn) == "admin"   # Owner: quan_tri → admin
    assert iam.cac_hanh_dong(ow, "niche-research", conn) == \
        ["tao", "toan_quyen", "quan_tri"]


def test_tick_toan_quyen_phat_manager_khong_len_admin(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.vai_cho_app(nv, "niche-research", conn) == "viewer"
    iam.gan_override(conn, ow, "nv", "niche-research", "toan_quyen", True,
                     "trực thay Manager")
    assert iam.vai_cho_app(nv, "niche-research", conn) == "manager"  # vai_xoa — KHÔNG admin
    assert "toan_quyen" in iam.cac_hanh_dong(nv, "niche-research", conn)
    assert iam.vai_cho_app(nv, "radary", conn) == "viewer"           # app khác không lây
    iam.gan_override(conn, ow, "nv", "niche-research", "quan_tri", True,
                     "thử nấc quản trị")
    assert iam.vai_cho_app(nv, "niche-research", conn) == "admin"    # chỉ quan_tri mới admin


def test_viec_api_niche_khai_dung():
    """viec_api sinh từ TÍNH NĂNG THẬT (đọc pipeline): quet_kenh (scripts 1/3/5-7
    đọc YouTube Data API bằng key AIza… từ CHÍNH file competitors.txt — thiết kế
    V2, V3 két bơm thay) · phan_tich (run_agent qua llm_provider) · lay_transcript
    (S15 deepdive, transcriptapi.com)."""
    a = tim_app("niche-research")
    assert [(v["ma"], v["loai"]) for v in a["viec_api"]] == [
        ("quet_kenh", "youtube"), ("phan_tich", "llm"),
        ("lay_transcript", "transcript")]
    from nen.ket_cau_hinh import ket
    for v in a["viec_api"]:
        assert v["loai"] in ket.LOAI_API and v["loai"] in ket.TEN_LOAI_API


def test_di_tru_khoa_niche_idempotent(tmp_path, monkeypatch):
    """Migration .env → két: chỉ nạp khóa CÓ GIÁ TRỊ thật, marker chống nạp đôi;
    .env KHÔNG có khóa nào (thực trạng hệ cũ 18/08 — chỉ ADMIN_USERS) → không
    nạp gì và KHÔNG đặt marker (sau này có key thật chạy lại vẫn ăn)."""
    import importlib.util
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    from nen.ket_cau_hinh import ket
    spec = importlib.util.spec_from_file_location(
        "di_tru_khoa_niche",
        __file__.replace("tests", "scripts").replace("test_niche_research.py",
                                                     "di_tru_khoa_niche.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    c = ket.ket_noi()
    try:
        # thực trạng hệ cũ: .env chỉ có ADMIN_USERS → không nạp gì, không marker
        rong = tmp_path / "rong.env"
        rong.write_text("ADMIN_USERS=sep\nGROK_API_KEY=\n", encoding="utf-8")
        assert mod.di_tru(rong, c) == []
        assert ket.lay_cau_hinh(c, mod.MARKER) == ""     # marker KHÔNG đặt

        env = tmp_path / ".env"
        env.write_text("GLM_API_KEY=sk-glm-abcdef-1111\nGLM_MODEL=glm-5.2\n"
                       "TRANSCRIPT_API_KEY=tr-abcdef-2222\nADMIN_USERS=sep\n"
                       "GROK_API_KEY=\n", encoding="utf-8")
        ds = mod.di_tru(env, c)
        assert sorted((m["loai"], m["duoi"]) for m in ds) == \
            [("llm", "1111"), ("transcript", "2222")]
        cp = ket.doc_cap_phat(c)["niche-research"]
        assert len(cp["phan_tich"]["khoa"]) == 1
        assert cp["phan_tich"]["model"] == "glm-5.2"
        assert len(cp["lay_transcript"]["khoa"]) == 1
        assert mod.di_tru(env, c) == []                  # idempotent — marker chặn nạp đôi
        assert len(ket.liet_ke_api_keys(c)) == 2
        # không TOÀN BỘ plaintext ra UI (dau 10 + duoi 4 là lộ có chủ đích)
        assert not any(kt in str(v)
                       for kt in ("sk-glm-abcdef-1111", "tr-abcdef-2222")
                       for k in ket.liet_ke_api_keys(c) for v in k.values())
    finally:
        c.close()
