# -*- coding: utf-8 -*-
"""RadarY vào V3 (APPS.md app 1/6): hợp đồng app + luật Permissions v2 + vai dịch
từ hành động — ghim luật 04/08 hệ cũ: tick toan_quyen phát MANAGER, KHÔNG BAO GIỜ
lên admin (Manager không ngang Owner)."""
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


def test_hop_dong_radary():
    a = tim_app("radary")
    assert a and a["cong"] == 9111 and a["health"] == "/api/health"
    assert a["tien_to"] == ["/api", "/app.js", "/vendor"]   # đo từ registry V2
    store = {d["ten"]: d for d in a["du_lieu"]}
    assert store["radary-db"]["backup"] == "sqlite-snapshot"     # cấm copy trần db
    assert store["radary-thumbs"]["muc_quy"] == "tai-sinh"       # thumbs không backup
    assert store["radary-secret"]["muc_quy"] == "vang"           # mất khóa = mất key


def test_luat_va_vai_radary_theo_thuong_quy(conn):
    """Ma trận mặc định: mọi bộ phận L1 xem; them_video/tao_pool KD L3;
    toan_quyen L4 (Manager); quan_tri chỉ Owner. Vai dừng-tại-hit-đầu."""
    ow = _owner(conn)
    ca = [
        # (bộ phận, level) -> (vào, them_video, toan_quyen, vai)
        (("Vận hành - Sản xuất", 1), (True, False, False, "viewer")),
        (("Vận hành - Sản xuất", 3), (True, False, False, "viewer")),  # VH L3: không them
        (("Kinh doanh", 3), (True, True, False, "leader")),
        (("Kinh doanh", 4), (True, True, True, "manager")),            # L4 → vai_xoa manager
        (("", 2), (True, False, False, "viewer")),                     # user "trắng" không nổ
    ]
    for i, ((bp, lv), (vao, them, toan, vai)) in enumerate(ca):
        iam.tao_tai_khoan(conn, ow, f"u{i}", "123456", bp, lv)
        u = iam.claims_cua(iam.lay_tai_khoan(conn, f"u{i}"))
        assert iam.co_quyen(u, "vao", "radary", conn) == vao, (bp, lv)
        assert iam.co_quyen(u, "them_video", "radary", conn) == them, (bp, lv)
        assert iam.co_quyen(u, "toan_quyen", "radary", conn) == toan, (bp, lv)
        assert iam.vai_cho_app(u, "radary", conn) == vai, (bp, lv)
    assert iam.vai_cho_app(ow, "radary", conn) == "admin"       # Owner: quan_tri → admin
    assert iam.cac_hanh_dong(ow, "radary", conn) == \
        ["them_video", "tao_pool", "toan_quyen", "quan_tri"]


def test_sidebar_tu_an_app_da_di_tru():
    """APPS.md bước 2: thêm app vào apps.json là sidebar tự ăn — sb_apps dựng từ
    giao hợp đồng × X-Remote-Apps; 3 app lõi + app-mau không lặp ở nhóm Tools."""
    from nen.common.sidebar import sb_apps_tu_claims
    ds = sb_apps_tu_claims(["radary", "ai-agent", "to-chuc", "app-mau"])
    # app khai giao_dien 'khung' → mở qua /open (giữ sidebar — Owner 16/08)
    assert ds == [{"slug": "radary", "ten": "RadarY", "href": "/open/radary"}]
    assert sb_apps_tu_claims([]) == []                # không quyền → không mục
    assert sb_apps_tu_claims(["la-lam"]) == []        # slug lạ ngoài hợp đồng → ẩn


def test_tick_toan_quyen_phat_manager_khong_len_admin(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.vai_cho_app(nv, "radary", conn) == "viewer"
    iam.gan_override(conn, ow, "nv", "radary", "toan_quyen", True, "trực thay Manager")
    assert iam.vai_cho_app(nv, "radary", conn) == "manager"     # vai_xoa — KHÔNG admin
    assert "toan_quyen" in iam.cac_hanh_dong(nv, "radary", conn)
    assert iam.vai_cho_app(nv, "ai-agent", conn) == "viewer"    # app khác không lây
    iam.gan_override(conn, ow, "nv", "radary", "quan_tri", True, "thử nấc quản trị")
    assert iam.vai_cho_app(nv, "radary", conn) == "admin"       # chỉ quan_tri mới admin


# ---------- LÀM GỌN (Owner 16/08): khóa về KÉT V3, quản trị về một cửa ----------

def test_viec_api_radary_khai_dung():
    a = tim_app("radary")
    assert [(v["ma"], v["loai"]) for v in a["viec_api"]] == \
        [("harvest", "youtube"), ("quet_dinh_ky", "youtube"), ("dien_giai", "llm")]


@pytest.fixture()
def ket_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    from nen.ket_cau_hinh import ket
    c = ket.ket_noi()
    yield ket, c
    c.close()


def test_loopback_api_khoa_tra_cap_phat_va_chan_ngoai(ket_tmp):
    """GET /api/cau-hinh/api-khoa/{app}: khóa plaintext cho app DÙNG (khuôn
    llm/{vai}) — chỉ loopback; máy LAN gọi thẳng bị chặn."""
    import asyncio

    import httpx

    from nen.gateway.main import app as gateway_app
    ket, c = ket_tmp
    k1 = ket.them_api_key(c, "youtube", "AIza-that-7f2a")
    k2 = ket.them_api_key(c, "youtube", "AIza-that-c9d1")
    ket.luu_cap_phat_viec(c, "radary", "harvest", [k1, k2], "xoay_vong")

    async def goi(client_addr):
        transport = httpx.ASGITransport(app=gateway_app, client=client_addr)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as cl:
            return await cl.get("/api/cau-hinh/api-khoa/radary")

    r = asyncio.run(goi(("127.0.0.1", 50000)))
    assert r.status_code == 200
    muc = r.json()["harvest"]
    assert [k["key"] for k in muc["khoa"]] == ["AIza-that-7f2a", "AIza-that-c9d1"]
    assert muc["che_do"] == "xoay_vong"
    assert asyncio.run(goi(("192.168.1.50", 50000))).status_code == 403


def test_di_tru_khoa_radary_idempotent_dung_ngan(ket_tmp, tmp_path):
    """Migration khóa nội bộ radary → két: Fernet giải đúng, trùng giá trị nạp
    MỘT lần, GIỮ NGĂN V2 (harvest=1 → việc harvest; 0 → quet_dinh_ky), marker
    chống nạp đôi, két không bao giờ lộ plaintext qua liet_ke."""
    import importlib.util
    import sqlite3

    from cryptography.fernet import Fernet
    ket, c = ket_tmp
    spec = importlib.util.spec_from_file_location(
        "di_tru_khoa_radary",
        __file__.replace("tests", "scripts").replace("test_radary.py",
                                                     "di_tru_khoa_radary.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sk = tmp_path / "secret.key"
    sk.write_bytes(Fernet.generate_key())
    f = Fernet(sk.read_bytes())
    db = tmp_path / "radary.db"
    rc = sqlite3.connect(db)
    rc.execute("CREATE TABLE api_keys (id INTEGER PRIMARY KEY, org_id INT, key TEXT, "
               "note TEXT, workspace_id INT, backup INT DEFAULT 0, harvest INT DEFAULT 0)")
    ma = lambda v: f.encrypt(v.encode()).decode("ascii")
    rc.execute("INSERT INTO api_keys (org_id, key, harvest) VALUES (1, ?, 1)",
               (ma("AIza-harvest-1111"),))
    rc.execute("INSERT INTO api_keys (org_id, key, harvest) VALUES (1, ?, 1)",
               (ma("AIza-harvest-1111"),))          # TRÙNG giá trị → chỉ nạp 1
    rc.execute("INSERT INTO api_keys (org_id, key, harvest, backup) VALUES (1, ?, 0, 1)",
               (ma("AIza-scan-2222"),))
    rc.execute("INSERT INTO api_keys (org_id, key, harvest) VALUES (1, ?, 0)",
               ("AIza-scan-tran-3333",))            # thời tiền-Fernet: plaintext
    rc.commit(); rc.close()

    ds = mod.di_tru(db, sk, c)
    assert sorted((m["viec"], m["duoi"]) for m in ds) == \
        [("harvest", "1111"), ("quet_dinh_ky", "2222"), ("quet_dinh_ky", "3333")]
    cp = ket.doc_cap_phat(c)["radary"]
    assert len(cp["harvest"]["khoa"]) == 1 and cp["harvest"]["che_do"] == "mot_khoa"
    assert len(cp["quet_dinh_ky"]["khoa"]) == 2
    assert cp["quet_dinh_ky"]["che_do"] == "xoay_vong"
    assert mod.di_tru(db, sk, c) == []              # idempotent — marker chặn nạp đôi
    assert len(ket.liet_ke_api_keys(c)) == 3
    assert not any("AIza-" in str(v) for k in ket.liet_ke_api_keys(c)
                   for v in k.values())             # không plaintext ra UI
