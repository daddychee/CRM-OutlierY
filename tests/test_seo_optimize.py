# -*- coding: utf-8 -*-
"""SEO Optimize vào V3 (APPS.md app 4 — 19/08): hợp đồng app + luật Permissions v2
— ghim thang V2 03-04/08: KD L2 van_hanh (app dịch → vai seo) · sua KD L3 (leader) ·
toan_quyen KD L4 (vai manager — Manager không ngang Owner) · quan_tri chỉ Owner.
Khóa hành động 'van_hanh' CỐ Ý tránh substring them/tao/sua/xoa/toan_quyen
(bẫy iam.vai_cho_app dò substring — đã dính nas_cap_cao)."""
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
        conn, None, "owner", "MatKhau123", "Ban quản trị", 5, phai_doi_mk=False))


def test_hop_dong_seo_optimize():
    a = tim_app("seo-optimize")
    assert a and a["cong"] == 9115 and a["health"] == "/api/health"
    assert a["tien_to"] == ["/api"]              # board.html tự chứa, chỉ fetch /api (registry V2)
    assert a["giao_dien"] == "khung"             # SPA mở qua /open giữ sidebar
    store = {d["ten"]: d for d in a["du_lieu"]}
    assert store["seo-profiles"]["muc_quy"] == "vang"
    assert store["seo-profiles"]["duong"] == "data/seo-optimize/profiles"
    assert store["seo-users"]["duong"] == "data/seo-optimize/users.json"
    assert store["seo-runs"]["muc_quy"] == "bac"  # kết quả sinh — tái sinh được (tốn token)


def test_luat_va_vai_seo_theo_thuong_quy(conn):
    """Ma trận mặc định: KD L2 vào + van_hanh (header viewer — app dịch Actions →
    vai seo nội bộ); sua KD L3; toan_quyen KD L4 (vai manager); quan_tri chỉ Owner."""
    ow = _owner(conn)
    ca = [
        # (bộ phận, level) -> (vào, van_hanh, sua, toan_quyen, vai header)
        (("Vận hành - Sản xuất", 2), (False, False, False, False, "-")),
        (("Kinh doanh", 1), (False, False, False, False, "-")),
        (("Kinh doanh", 2), (True, True, False, False, "viewer")),
        (("Kinh doanh", 3), (True, True, True, False, "leader")),
        (("Kinh doanh", 4), (True, True, True, True, "manager")),   # vai_xoa manager
        (("", 2), (False, False, False, False, "-")),               # user "trắng" không nổ
    ]
    for i, ((bp, lv), (vao, vh, sua, toan, vai)) in enumerate(ca):
        iam.tao_tai_khoan(conn, ow, f"u{i}", "MatKhau123", bp, lv, _cho_bo_phan_rong=True)
        u = iam.claims_cua(iam.lay_tai_khoan(conn, f"u{i}"))
        assert iam.co_quyen(u, "vao", "seo-optimize", conn) == vao, (bp, lv)
        assert iam.co_quyen(u, "van_hanh", "seo-optimize", conn) == vh, (bp, lv)
        assert iam.co_quyen(u, "sua", "seo-optimize", conn) == sua, (bp, lv)
        assert iam.co_quyen(u, "toan_quyen", "seo-optimize", conn) == toan, (bp, lv)
        if vai != "-":
            assert iam.vai_cho_app(u, "seo-optimize", conn) == vai, (bp, lv)
    assert iam.vai_cho_app(ow, "seo-optimize", conn) == "admin"     # Owner: quan_tri → admin
    assert iam.cac_hanh_dong(ow, "seo-optimize", conn) == \
        ["van_hanh", "sua", "toan_quyen", "phan_cong", "quan_tri"]
    # GIAO VIỆC (trục B, thêm 24/08): Manager trở lên — Leader KHÔNG. Đây là chỗ ĐẢO
    # luật `chan_owner` của V2 (02/08 nới cho leader), user chốt lại 24/08.
    u3 = iam.claims_cua(iam.lay_tai_khoan(conn, "u3"))          # Kinh doanh L3
    u4 = iam.claims_cua(iam.lay_tai_khoan(conn, "u4"))          # Kinh doanh L4
    assert not iam.co_quyen(u3, "phan_cong", "seo-optimize", conn)
    assert iam.co_quyen(u4, "phan_cong", "seo-optimize", conn)
    # ...và hành động mới KHÔNG được đẩy vai (bẫy substring nas_cap_cao)
    assert iam.vai_cho_app(u4, "seo-optimize", conn) == "manager"


def test_tick_toan_quyen_phat_manager_khong_len_admin(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "MatKhau123", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.vai_cho_app(nv, "seo-optimize", conn) == "viewer"
    iam.gan_override(conn, ow, "nv", "seo-optimize", "toan_quyen", True,
                     "trực thay Manager")
    assert iam.vai_cho_app(nv, "seo-optimize", conn) == "manager"   # vai_xoa — KHÔNG admin
    assert "toan_quyen" in iam.cac_hanh_dong(nv, "seo-optimize", conn)
    assert iam.vai_cho_app(nv, "radary", conn) == "viewer"          # app khác không lây
    iam.gan_override(conn, ow, "nv", "seo-optimize", "quan_tri", True,
                     "thử nấc quản trị")
    assert iam.vai_cho_app(nv, "seo-optimize", conn) == "admin"     # chỉ quan_tri mới admin


def test_viec_api_seo_khai_dung():
    """viec_api sinh từ TÍNH NĂNG THẬT: trich_kenh (extract-profile/extract-format
    gọi common.yt_get pool key xoay vòng) · sinh_metadata (generate/gen-cta qua
    seo/llm.py)."""
    a = tim_app("seo-optimize")
    assert [(v["ma"], v["loai"]) for v in a["viec_api"]] == [
        ("trich_kenh", "youtube"), ("sinh_metadata", "llm")]
    from nen.ket_cau_hinh import ket
    for v in a["viec_api"]:
        assert v["loai"] in ket.LOAI_API and v["loai"] in ket.TEN_LOAI_API


def test_di_tru_khoa_seo_idempotent(tmp_path, monkeypatch):
    """Pool YouTube nhiều key → việc trich_kenh chế độ XOAY VÒNG; key LLM →
    sinh_metadata kèm model GLM; marker chống nạp đôi; .env không khóa → không
    đặt marker; không plaintext lọt ra liệt kê két."""
    import importlib.util
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    from nen.ket_cau_hinh import ket
    spec = importlib.util.spec_from_file_location(
        "di_tru_khoa_seo",
        __file__.replace("tests", "scripts").replace("test_seo_optimize.py",
                                                     "di_tru_khoa_seo.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    c = ket.ket_noi()
    try:
        # .env chỉ có cấu hình chạy, không secret → không nạp gì, KHÔNG đặt marker
        rong = tmp_path / "rong.env"
        rong.write_text("PORT=8760\nLLM_PROVIDER=glm\nGLM_API_KEY=\n", encoding="utf-8")
        assert mod.di_tru(rong, c) == []
        assert ket.lay_cau_hinh(c, mod.MARKER) == ""

        env = tmp_path / ".env"
        env.write_text(
            "LLM_PROVIDER=glm\nPORT=8760\n"
            "GLM_API_KEY=sk-glm-abcdef-1111\nGLM_MODEL=glm-4.5-air\n"
            "OPENAI_API_KEY=sk-oa-abcdef-2222\n"
            "YOUTUBE_API_KEYS=AIzaSyAAAAAAAAAAAAAAAAAAA-3333,"
            "AIzaSyBBBBBBBBBBBBBBBBBBB-4444\n", encoding="utf-8")
        ds = mod.di_tru(env, c)
        assert sorted((m["loai"], m["duoi"]) for m in ds) == \
            [("llm", "1111"), ("llm", "2222"), ("youtube", "3333"), ("youtube", "4444")]
        cp = ket.doc_cap_phat(c)["seo-optimize"]
        assert len(cp["trich_kenh"]["khoa"]) == 2
        assert cp["trich_kenh"]["che_do"] == "xoay_vong"      # pool xoay vòng đúng ngăn V2
        assert len(cp["sinh_metadata"]["khoa"]) == 2          # glm chính + openai dự phòng
        assert cp["sinh_metadata"]["model"] == "glm-4.5-air"
        assert mod.di_tru(env, c) == []                       # idempotent — marker chặn
        assert len(ket.liet_ke_api_keys(c)) == 4
        assert not any(kt in str(v)
                       for kt in ("sk-glm-abcdef-1111", "AIzaSyAAAAAAAAAAAAAAAAAAA-3333")
                       for k in ket.liet_ke_api_keys(c) for v in k.values())
    finally:
        c.close()
