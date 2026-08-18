# -*- coding: utf-8 -*-
"""Content Ultimate vào V3 (APPS.md app 2/6): hợp đồng app + luật Permissions v2.
Ghim chốt V2 31/07 + 04/08: VH L2 vào · sua VH L3 (vai leader = TRẦN vận hành,
Manager không ngang Owner) · quan_tri chỉ Owner · KHÔNG khai xoa (không trỏ
chức năng thật)."""
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


def test_hop_dong_content_ultimate():
    a = tim_app("content-ultimate")
    assert a and a["cong"] == 9112 and a["health"] == "/api/health"
    assert a["tien_to"] == ["/api", "/oe", "/author", "/outline", "/write",
                            "/manage", "/settings", "/logout"]   # đo từ registry V2 (vụ 6d9f069)
    store = {d["ten"]: d for d in a["du_lieu"]}
    assert store["cu-cookies"]["muc_quy"] == "vang"              # SECRET có danh phận
    assert store["cu-admin"]["duong"].endswith("admin")          # KPI đọc history.jsonl


def test_luat_khong_khai_xoa_va_ma_tran_vao(conn):
    assert set(iam.hanh_dong_cua_app("content-ultimate")) == {"sua", "quan_tri"}
    ow = _owner(conn)
    ca = [
        # (bộ phận, level) -> (vào, sua, vai)
        (("Kinh doanh", 2), (False, False, "creator-khong-vao")),  # KD không thuộc VH
        (("Vận hành - Sản xuất", 1), (False, False, "-")),          # VH L1 chưa đủ
        (("Vận hành - Sản xuất", 2), (True, False, "viewer")),
        (("Vận hành - Sản xuất", 3), (True, True, "leader")),
        (("Vận hành - Sản xuất", 4), (True, True, "leader")),       # Manager VH = trần leader
        (("Kinh doanh", 4), (True, True, "leader")),                # L4 bỏ rào bộ phận (luật engine)
    ]
    for i, ((bp, lv), (vao, sua, _)) in enumerate(ca):
        iam.tao_tai_khoan(conn, ow, f"u{i}", "123456", bp, lv)
        u = iam.claims_cua(iam.lay_tai_khoan(conn, f"u{i}"))
        assert iam.co_quyen(u, "vao", "content-ultimate", conn) == vao, (bp, lv)
        assert iam.co_quyen(u, "sua", "content-ultimate", conn) == sua, (bp, lv)
    # vai dịch hit-đầu: sua→leader; KHÔNG có đường nào ra manager/admin ngoài quan_tri
    u3 = iam.claims_cua(iam.lay_tai_khoan(conn, "u3"))
    u4 = iam.claims_cua(iam.lay_tai_khoan(conn, "u4"))
    assert iam.vai_cho_app(u3, "content-ultimate", conn) == "leader"
    assert iam.vai_cho_app(u4, "content-ultimate", conn) == "leader"   # Manager KHÔNG admin
    assert iam.vai_cho_app(ow, "content-ultimate", conn) == "admin"    # Owner qua quan_tri


def test_tick_sua_phat_leader_khong_len_admin(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Vận hành - Sản xuất", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.vai_cho_app(nv, "content-ultimate", conn) == "viewer"
    iam.gan_override(conn, ow, "nv", "content-ultimate", "sua", True, "trực nhật ký thay leader")
    assert iam.vai_cho_app(nv, "content-ultimate", conn) == "leader"   # KHÔNG admin
    assert iam.cac_hanh_dong(nv, "content-ultimate", conn) == ["sua"]
    iam.gan_override(conn, ow, "nv", "content-ultimate", "quan_tri", True, "thử nấc quản trị")
    assert iam.vai_cho_app(nv, "content-ultimate", conn) == "admin"    # chỉ quan_tri mới admin


def test_viec_api_content_khai_dung():
    """viec_api sinh từ TÍNH NĂNG THẬT (đọc code): 2 việc LLM (viết kịch bản +
    phân tích outline) · transcript (S1b) · youtube (S1c comment)."""
    a = tim_app("content-ultimate")
    assert [(v["ma"], v["loai"]) for v in a["viec_api"]] == [
        ("viet_kich_ban", "llm"), ("phan_tich_outline", "llm"),
        ("lay_transcript", "transcript"), ("lay_comment", "youtube")]
    from nen.ket_cau_hinh import ket
    for _, loai in [(v["ma"], v["loai"]) for v in a["viec_api"]]:
        assert loai in ket.LOAI_API          # loại phải có trong két (transcript mới thêm)
        assert loai in ket.TEN_LOAI_API      # và có nhãn hiển thị trên trang API Keys


def test_di_tru_khoa_content_idempotent(tmp_path, monkeypatch):
    """Migration .env → két: đúng loại/nhà, GLM dùng chung 2 việc LLM, marker
    chống nạp đôi, không lộ plaintext qua liet_ke; ADMIN_USERS/HTPASSWD bỏ qua."""
    import importlib.util
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    from nen.ket_cau_hinh import ket
    spec = importlib.util.spec_from_file_location(
        "di_tru_khoa_content",
        str(__import__("pathlib").Path(__file__).resolve().parents[1]
            / "scripts" / "di_tru_khoa_content.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    env = tmp_path / ".env"
    env.write_text("GLM_API_KEY=sk-glm-1111\nGLM_MODEL=glm-5.2\n"
                   "TRANSCRIPT_API_KEY=tr-2222\nYOUTUBE_API_KEY=AIza-3333\n"
                   "ADMIN_USERS=thanh\nHTPASSWD_FILE=/x/.htpasswd\n", encoding="utf-8")
    c = ket.ket_noi()
    try:
        ds = mod.di_tru(env, c)
        assert sorted((m["loai"], m["duoi"]) for m in ds) == [
            ("llm", "1111"), ("transcript", "2222"), ("youtube", "3333")]
        cp = ket.doc_cap_phat(c)["content-ultimate"]
        assert cp["viet_kich_ban"]["khoa"] == cp["phan_tich_outline"]["khoa"]  # chung khóa GLM
        assert cp["viet_kich_ban"]["model"] == "glm-5.2"
        assert len(cp["lay_transcript"]["khoa"]) == 1 and len(cp["lay_comment"]["khoa"]) == 1
        assert mod.di_tru(env, c) == []                 # idempotent
        assert len(ket.liet_ke_api_keys(c)) == 3        # ADMIN_USERS/HTPASSWD không vào
        # không TOÀN BỘ plaintext ra UI (dau 10 là lộ có chủ đích từ 18/08 —
        # LUẬT cấm lộ trọn khóa, không phải cấm prefix)
        assert not any("sk-glm-1111" in str(v) for k in ket.liet_ke_api_keys(c)
                       for v in k.values())
    finally:
        c.close()
