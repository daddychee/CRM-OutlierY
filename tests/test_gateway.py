# -*- coding: utf-8 -*-
"""Test gateway P2: đăng nhập qua iam.db, ép đổi mật khẩu, quản trị, proxy + claims.

Test proxy là TÍCH HỢP THẬT: app-mau chạy uvicorn thread ở :9190 (đúng cổng hợp
đồng), gateway chuyển tiếp sang — kiểm claims tiêm đúng và header giả mạo bị vứt.
"""
import importlib.util
import threading
import time
from datetime import date
from pathlib import Path

import bcrypt
import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from nen.common import nas_sync
from nen.gateway.main import app as gateway_app
from nen.iam import iam

ROOT = Path(__file__).resolve().parents[1]
_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def iam_db(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-test", "mk-test", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "nhanvien", "mk-nv-6", "Kinh doanh", 2,
                      phai_doi_mk=False)
    conn.close()
    return tmp_path / "iam.db"


@pytest.fixture()
def client(iam_db):
    return TestClient(gateway_app, follow_redirects=False)


def _login(client, ten="owner-test", mk="mk-test"):
    return client.post("/login", data={"ten": ten, "mat_khau": mk})


@pytest.fixture(scope="module")
def app_mau_server():
    # Hệ dev đang bật sẵn app-mau ở :9190 → dùng luôn, không bind trùng cổng
    try:
        if httpx.get("http://127.0.0.1:9190/health", timeout=2).status_code == 200:
            yield
            return
    except httpx.HTTPError:
        pass
    spec = importlib.util.spec_from_file_location(
        "app_mau_main", ROOT / "apps" / "app-mau" / "src" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    server = uvicorn.Server(uvicorn.Config(
        mod.app, host="127.0.0.1", port=9190, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started, "app-mau khong khoi dong duoc trong test"
    yield
    server.should_exit = True
    t.join(timeout=5)


# ---------- auth ----------

def test_chua_dang_nhap_bi_day_ve_login(client):
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_health_khong_can_dang_nhap(client):
    assert client.get("/health").status_code == 200


def test_dang_nhap_sai_401(client):
    r = _login(client, mk="sai")
    assert r.status_code == 401
    assert "Wrong username" in r.text


def test_dang_nhap_dung_vao_trang_chu(client):
    # UI_FLOW.md mục 1 + mục 9 (URL đẹp, Owner chốt 16/08/2026): "/" PHỤC VỤ
    # thẳng trang Hỏi–đáp (không redirect sang /app/... nữa — thanh địa chỉ giữ
    # "/"). 502 chấp nhận được trong môi trường test khi app ai-agent không chạy.
    assert _login(client).status_code == 303
    r = client.get("/")
    assert r.status_code in (200, 502)


def test_dang_xuat_mat_phien(client):
    _login(client)
    client.get("/logout")
    assert client.get("/").status_code == 303


def test_user_bi_xoa_phien_chet_theo(client, iam_db):
    _login(client)
    conn = iam.ket_noi()
    with conn:
        conn.execute("DELETE FROM tai_khoan WHERE ten='owner-test'")
    conn.close()
    assert client.get("/").status_code == 303   # đọc SỐNG → phiên chết ngay


# ---------- NAS: gateway gọi dong_bo_nen đúng lúc/đúng nhóm (đưa NAS vào v2) ----------
# Monkeypatch THẲNG nas_sync.dong_bo_nen (ghi lại lời gọi) — không cần bật
# NAS_DONG_BO/mock subprocess PowerShell, vì an toàn nội bộ (công tắc, tên hệ
# thống, chuẩn mật khẩu...) là trách nhiệm RIÊNG của nas_sync (test_nas_sync.py);
# ở đây chỉ kiểm GATEWAY nối đúng dây: đúng ten/mật khẩu thật/nhóm.

def test_dang_nhap_dung_goi_nas_dong_bo_nhom_toan_quyen(client, iam_db, monkeypatch):
    """owner-test level 5 >= min_level 3 của hành động nas_cap_cao (phan_quyen.json
    apps.to-chuc) → NHOM_TOAN_QUYEN."""
    from nen.gateway import main as gw
    ghi = []
    monkeypatch.setattr(gw.nas_sync, "dong_bo_nen",
                        lambda ten, mk, nhom: ghi.append((ten, mk, nhom)))
    _login(client)
    assert ghi == [("owner-test", "mk-test", nas_sync.NHOM_TOAN_QUYEN)]


def test_dang_nhap_level_thap_goi_nhom_chi_them(client, iam_db, monkeypatch):
    """nhanvien level 2 < min_level 3 → NHOM_CHI_THEM (đọc + thêm file, không sửa/xóa)."""
    from nen.gateway import main as gw
    ghi = []
    monkeypatch.setattr(gw.nas_sync, "dong_bo_nen",
                        lambda ten, mk, nhom: ghi.append((ten, mk, nhom)))
    _login(client, "nhanvien", "mk-nv-6")
    assert ghi == [("nhanvien", "mk-nv-6", nas_sync.NHOM_CHI_THEM)]


def test_dang_nhap_sai_khong_goi_nas(client, iam_db, monkeypatch):
    from nen.gateway import main as gw
    ghi = []
    monkeypatch.setattr(gw.nas_sync, "dong_bo_nen",
                        lambda ten, mk, nhom: ghi.append((ten, mk, nhom)))
    _login(client, mk="sai")
    assert ghi == []


def test_tu_doi_mat_khau_cung_dong_bo_nas(client, iam_db, monkeypatch):
    """Tự đổi mật khẩu (đã đăng nhập) cũng phải đồng bộ NAS — mật khẩu MỚI, không
    phải mật khẩu cũ vừa hết hiệu lực."""
    from nen.gateway import main as gw
    _login(client)
    ghi = []
    monkeypatch.setattr(gw.nas_sync, "dong_bo_nen",
                        lambda ten, mk, nhom: ghi.append((ten, mk, nhom)))
    r = client.post("/profile/mat-khau",
                    data={"mk_hien_tai": "mk-test", "mk_moi": "MatKhauMoi9",
                          "mk_lai": "MatKhauMoi9"})
    assert r.status_code == 200
    assert ghi == [("owner-test", "MatKhauMoi9", nas_sync.NHOM_TOAN_QUYEN)]


def test_api_chua_dang_nhap_tra_401_json(client):
    r = client.get("/app/app-mau/health", headers={"accept": "application/json"})
    assert r.status_code == 401


# ---------- ép đổi mật khẩu (YC6 kế thừa) ----------

def test_phai_doi_mk_bi_ep_sang_trang_doi(client, iam_db):
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "moi", "mk-tam-6", "Kinh doanh", 2)  # phai_doi mặc định
    conn.close()
    _login(client, "moi", "mk-tam-6")
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/doi-mat-khau"
    # đổi xong thì vào được — "/" giờ PHỤC VỤ thẳng Hỏi–đáp (UI_FLOW.md mục 9),
    # không còn bị ép về /doi-mat-khau nữa
    client.post("/doi-mat-khau", data={"mk_moi": "mk-moi-6", "mk_lai": "mk-moi-6"})
    r = client.get("/")
    assert not (r.status_code == 303
                and r.headers.get("location") == "/doi-mat-khau")


# ---------- khu quản trị nền (UI_FLOW.md mục 5-6) ----------

def test_quan_tri_nhan_vien_403(client):
    # GET /general/accounts đã nghỉ hưu thành redirect về hub (không gate ở
    # redirect — /hr tự gate bằng cờ); BACKEND POST vẫn phải chặn nhân viên.
    _login(client, "nhanvien", "mk-nv-6")
    r = client.post("/general/accounts/create", data={
        "ten": "tk-lau", "mat_khau": "mk-tam-6", "bo_phan": "Kinh doanh", "level": 2})
    assert r.status_code == 403


def test_general_people_accounts_get_ve_hr_hub(client):
    """HR HUB một cửa (Owner chốt 16/08): 2 trang General cũ nghỉ hưu kiểu
    /quan-tri — GET 303 về /hr đúng tab; POST /general/* giữ nguyên (backend hub)."""
    _login(client)
    r = client.get("/general/people")
    assert r.status_code == 303 and r.headers["location"] == "/hr?tab=accounts"
    r = client.get("/general/accounts")
    assert r.status_code == 303 and r.headers["location"] == "/hr?tab=accounts"


def test_quan_tri_owner_vao_va_tao_tai_khoan(client):
    _login(client)
    r = client.post("/general/accounts/create", data={
        "ten": "tk-moi", "mat_khau": "mk-tam-6", "bo_phan": "Kinh doanh", "level": 2})
    assert "Created account tk-moi" in r.text
    conn = iam.ket_noi()
    assert iam.lay_tai_khoan(conn, "tk-moi")["phai_doi_mk"] == 1
    conn.close()


def test_quan_tri_xoa_phai_go_lai_ten(client):
    _login(client)
    r = client.post("/general/accounts/update", data={
        "ten": "nhanvien", "hanh_dong": "xoa", "gia_tri": "go-sai"})
    assert "retype the exact account name" in r.text
    conn = iam.ket_noi()
    assert iam.lay_tai_khoan(conn, "nhanvien") is not None   # chưa bị xóa
    conn.close()


def test_trang_cu_redirect_sang_khu_nen(client):
    """Trang cũ nghỉ hưu (UI_FLOW.md mục 5) — redirect giữ 1 nhịp chuyển tiếp."""
    _login(client)
    for cu, moi in (("/quan-tri", "/general/accounts"),
                    ("/cai-dat", "/general/api-keys"), ("/suc-khoe", "/general")):
        r = client.get(cu)
        assert r.status_code == 303 and r.headers["location"] == moi


def test_nhan_su_hr_l3_vao_duoc(client, iam_db):
    """Luật V1 (UI_FLOW.md mục 6): Nhân sự = Owner + Hành chính Nhân sự L3+.
    v2 từng khóa mất HR — test này ghim để không tái phạm. GET /general/people
    giờ là redirect về hub → kiểm luật trên BACKEND POST."""
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "hr-leader", "mk-hr-6", "Hành chính Nhân sự", 3)
    iam.doi_mat_khau(conn, ow, "hr-leader", "mk-hr-7", ep_doi_lan_sau=False)
    conn.close()
    _login(client, "hr-leader", "mk-hr-7")
    r = client.post("/general/people/create",
                    data={"ho_ten": "Người Test HR", "bo_phan": "Kinh doanh"})
    assert "Created profile" in r.text                           # HR L3 tạo được hồ sơ
    r = client.post("/general/accounts/create", data={           # nhưng KHÔNG đụng tài khoản
        "ten": "tk-hr-lau", "mat_khau": "mk-tam-6", "bo_phan": "Kinh doanh", "level": 2})
    assert r.status_code == 403
    assert client.get("/general/permissions").status_code == 403   # và không vào bảng phân quyền


def test_nhan_su_nhan_vien_thuong_403(client):
    _login(client, "nhanvien", "mk-nv-6")
    r = client.post("/general/people/create",
                    data={"ho_ten": "Người Lậu", "bo_phan": "Kinh doanh"})
    assert r.status_code == 403


def test_phan_quyen_tick_de_luat_mac_dinh(client, iam_db):
    """Trang Phân quyền: tick CHO PHÉP đè luật mặc định (PHẢI có lý do — P5),
    gỡ tick là về mặc định — kiểm bằng chính co_quyen (một cửa kiểm quyền cả hệ)."""
    _login(client)
    conn = iam.ket_noi()
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nhanvien"))
    # nhanvien = Kinh doanh L2 → mặc định ĐƯỢC vào data-analytics (luật KD L2+)
    assert iam.co_quyen(nv, "vao", "data-analytics", conn)
    r = client.post("/general/permissions/grant", data={
        "ten": "nhanvien", "app_slug": "data-analytics",
        "hanh_dong": "vao", "gia_tri": "chan"})
    assert "LÝ DO" in r.text                                    # thiếu lý do → chặn
    r = client.post("/general/permissions/grant", data={
        "ten": "nhanvien", "app_slug": "data-analytics",
        "hanh_dong": "vao", "gia_tri": "chan", "ly_do": "tạm khóa bàn giao"})
    assert "Set data-analytics/vao" in r.text
    assert not iam.co_quyen(nv, "vao", "data-analytics", conn)  # tick CHẶN thắng mặc định
    trang = client.get("/general/permissions").text             # P5: sổ toàn hệ có lý do
    assert "tạm khóa bàn giao" in trang
    client.post("/general/permissions/grant", data={
        "ten": "nhanvien", "app_slug": "data-analytics",
        "hanh_dong": "vao", "gia_tri": "ke_thua"})
    assert iam.co_quyen(nv, "vao", "data-analytics", conn)      # gỡ tick về mặc định
    conn.close()


def test_khu_general_cap_theo_tung_trang(client, iam_db):
    """Khu General cấp TỪNG TRANG bằng ô tick (Owner chốt 19/08 — Director L4).

    Ghim 3 điều: (a) MẶC ĐỊNH không đổi — L4 kể cả có Delegated admin vẫn 403 ở
    mọi trang (bệnh Owner gặp thật: đủ 3 giỏ hub mà vẫn không vào được General);
    (b) tick một trang chỉ mở ĐÚNG trang đó; (c) Permissions/API Keys KHÔNG bao
    giờ mở được — giỏ Owner tuyệt đối, Manager không ngang Owner.
    """
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "director", "mk-dir-9", "Kinh doanh", 4,
                      phai_doi_mk=False)
    iam.sua_tai_khoan(conn, ow, "director", admin_uy_quyen=True)
    conn.close()

    _login(client, "director", "mk-dir-9")
    for duong in ("/general/audit-log", "/general/data-backup",
                  "/general/applications"):
        assert client.get(duong).status_code == 403, f"{duong} phải Owner-only khi chưa tick"
    # '/general' là CỬA: L4 vốn có Niches/Channels (luật cũ) nên được đưa sang đó,
    # KHÔNG phải xem được trang Overview.
    r = client.get("/general")
    assert r.status_code == 303 and r.headers["location"] == "/general/niches"

    _login(client)                                    # Owner tick MỘT trang
    r = client.post("/general/permissions/save", data={
        "ten": "director", "dat__*__general_nhat_ky": "cho",
        "lydo__*__general_nhat_ky": "Director giám sát nhật ký"})
    assert r.status_code == 303 and "bao=Saved%201" in r.headers["location"]

    _login(client, "director", "mk-dir-9")
    assert client.get("/general/audit-log").status_code == 200      # mở đúng trang đã tick
    assert client.get("/general/data-backup").status_code == 403    # trang chưa tick vẫn đóng
    assert client.get("/general/applications").status_code == 403
    assert client.get("/general/permissions").status_code == 403    # giỏ tuyệt đối
    assert client.get("/general/api-keys").status_code == 403
    assert "Audit Log" in client.get("/general/audit-log").text     # nav hiện link đã cấp
    # '/general' là CỬA (nút sidebar chỉ trỏ về đây): đưa tới trang ĐẦU TIÊN có
    # quyền theo thứ tự khai — director L4 sẵn có Niches nên rơi vào đó.
    r = client.get("/general")
    assert r.status_code == 303 and r.headers["location"] == "/general/niches"

    # Người KHÔNG có quyền nền nào: cửa phải trỏ đúng trang vừa được tick.
    _login(client)
    assert client.post("/general/permissions/save", data={
        "ten": "nhanvien", "dat__*__general_nhat_ky": "cho",
        "lydo__*__general_nhat_ky": "xem nhật ký"}).status_code == 303
    _login(client, "nhanvien", "mk-nv-6")
    r = client.get("/general")
    assert r.status_code == 303 and r.headers["location"] == "/general/audit-log"


def test_doi_bo_phan_ho_so_keo_theo_tai_khoan(client, iam_db):
    """Owner báo 19/08: "chuyển bộ phận trong HR nhưng Permissions vẫn vai cũ".
    QUYỀN tính theo tai_khoan.bo_phan còn HR sửa nguoi.bo_phan → phải đồng bộ,
    và cấm sửa bộ phận ở tab Accounts (một nguồn sự thật = hồ sơ)."""
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    ns = iam.tao_nguoi(conn, ow, "Người Chuyển Phòng", "Vận hành - Sản xuất")
    iam.tao_tai_khoan(conn, ow, "chuyenphong", "mk-cp-9", "Vận hành - Sản xuất", 2,
                      nguoi_ma=ns["ma"], phai_doi_mk=False)
    u = iam.claims_cua(iam.lay_tai_khoan(conn, "chuyenphong"))
    assert not iam.co_quyen(u, "vao", "seo-optimize", conn)   # VH L2: chưa vào được SEO

    iam.sua_nguoi(conn, ow, ns["ma"], bo_phan="Kinh doanh")   # HR chuyển phòng
    tk = iam.lay_tai_khoan(conn, "chuyenphong")
    assert tk["bo_phan"] == "Kinh doanh"                      # tài khoản đi theo NGAY
    assert iam.co_quyen(iam.claims_cua(tk), "vao", "seo-optimize", conn)

    try:                                                      # chiều ngược bị chặn
        iam.sua_tai_khoan(conn, ow, "chuyenphong", bo_phan="Vận hành - Sản xuất")
        raise AssertionError("phải chặn sửa bộ phận ở tab Accounts")
    except iam.LoiIam as e:
        assert "hồ sơ" in str(e)
    assert iam.lay_tai_khoan(conn, "chuyenphong")["bo_phan"] == "Kinh doanh"
    conn.close()


def test_niches_channels_tick_mo_cho_team(client, iam_db):
    """Niches/Channels — 2 tab team cần nhất (Owner 19/08). Mặc định GIỮ luật cũ
    Manager L4+; ô tick THẮNG cả hai chiều: mở cho L2, hoặc chặn đúng một L4."""
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "mgr4", "mk-mgr-9", "Kinh doanh", 4, phai_doi_mk=False)
    conn.close()

    _login(client, "nhanvien", "mk-nv-6")                    # L2: mặc định đóng
    assert client.get("/general/niches").status_code == 403
    assert client.get("/general/channels").status_code == 403
    _login(client, "mgr4", "mk-mgr-9")                       # L4: mặc định mở (luật cũ)
    assert client.get("/general/niches").status_code == 200
    assert client.get("/general/channels").status_code == 200

    _login(client)
    assert client.post("/general/permissions/save", data={
        "ten": "nhanvien", "dat__*__general_niches": "cho",
        "lydo__*__general_niches": "team dùng danh bạ ngách",
        "dat__*__general_channels": "cho",
        "lydo__*__general_channels": "team dùng danh bạ kênh"}).status_code == 303
    assert client.post("/general/permissions/save", data={   # chặn đúng một L4
        "ten": "mgr4", "dat__*__general_channels": "chan",
        "lydo__*__general_channels": "tạm khóa bàn giao"}).status_code == 303

    _login(client, "nhanvien", "mk-nv-6")
    assert client.get("/general/niches").status_code == 200      # tick MỞ cho L2
    assert client.get("/general/channels").status_code == 200
    _login(client, "mgr4", "mk-mgr-9")
    assert client.get("/general/niches").status_code == 200      # không tick → giữ L4+
    assert client.get("/general/channels").status_code == 403     # tick CHẶN thắng level


def test_o_tick_slug_rong_bi_tu_choi(client, iam_db):
    """Sự cố thật 19/08: template mới chạy trên tiến trình cũ → slug render rỗng
    → form ghi app_slug='' = ô tick chết lặng lẽ. Giờ phải TỪ CHỐI, không ghi."""
    _login(client)
    r = client.post("/general/permissions/save", data={
        "ten": "nhanvien", "dat____giam_sat": "cho", "lydo____giam_sat": "x"})
    assert r.status_code == 303 and "loi=" in r.headers["location"]
    conn = iam.ket_noi()
    assert conn.execute(
        "SELECT COUNT(*) FROM quyen_override WHERE app_slug=''").fetchone()[0] == 0
    conn.close()


def test_tick_duyet_ho_so_co_hieu_luc(client, iam_db):
    """Ô tick 'Approve HR profiles' PHẢI ăn — bản cũ gọi co_quyen thiếu conn nên
    ô này chết lặng lẽ: Owner tick mà người được cấp vẫn 403 (sửa 19/08)."""
    _login(client)
    assert client.post("/general/permissions/save", data={
        "ten": "nhanvien", "dat__*__duyet_ho_so": "cho",
        "lydo__*__duyet_ho_so": "kiêm nhiệm hồ sơ"}).status_code == 303

    _login(client, "nhanvien", "mk-nv-6")
    r = client.post("/general/people/create",
                    data={"ho_ten": "Người Của Tick", "bo_phan": "Kinh doanh"})
    assert r.status_code == 200 and "Created profile" in r.text
    # nhưng vẫn KHÔNG được đụng tài khoản (giỏ quan_tai_khoan riêng)
    assert client.post("/general/accounts/create", data={
        "ten": "tk-lau-2", "mat_khau": "mk-tam-6",
        "bo_phan": "Kinh doanh", "level": 2}).status_code == 403


def test_bang_phan_quyen_gop_app_da_gop_giao_dien(client, iam_db):
    """App có gop_vao (Niche Research → Data Analytics, Owner chốt 18/08) KHÔNG
    đứng riêng trong bảng, nhưng ô tick của nó vẫn ghi về ĐÚNG app của nó."""
    _login(client)
    trang = client.get("/general/permissions?ten=nhanvien").text
    assert ">Niche Research</summary>" not in trang.replace("\n", "")
    assert "dat__niche-research__tao" in trang        # hàng vẫn còn, nằm trong khối app chủ
    r = client.post("/general/permissions/save", data={
        "ten": "nhanvien", "dat__niche-research__tao": "cho",
        "lydo__niche-research__tao": "chạy nghiên cứu hộ"})
    assert r.status_code == 303 and "bao=Saved%201" in r.headers["location"]
    conn = iam.ket_noi()
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nhanvien"))
    assert iam.co_quyen(nv, "tao", "niche-research", conn)
    conn.close()


def test_phan_quyen_acting_va_trang_p2_p4(client, iam_db):
    """P3 acting qua trang: L2 → L4 đổi mặc định ngay (X-Remote-Level hiệu lực);
    Owner không hạ được; trang render P2/P4 cho người được chọn."""
    _login(client)
    r = client.post("/general/permissions/acting", data={
        "ten": "nhanvien", "cap": "4", "ly_do": "thay quyền kỳ nghỉ"})
    assert "Acting level for nhanvien = 4" in r.text
    conn = iam.ket_noi()
    nv = iam.hieu_luc(iam.claims_cua(iam.lay_tai_khoan(conn, "nhanvien")), conn)
    assert nv["level"] == 4 and nv["level_that"] == 2
    conn.close()
    trang = client.get("/general/permissions?ten=nhanvien").text
    assert "acting: L2 → L4" in trang                           # badge P3
    assert "Nạp tài liệu" in trang and "KPI Review" in trang    # P4 hành động thật
    r = client.post("/general/permissions/acting", data={       # Owner không hạ được
        "ten": "owner-test", "cap": "2"})
    assert "chính mình" in r.text or "Owner" in r.text
    client.post("/general/permissions/acting", data={"ten": "nhanvien", "cap": ""})
    conn = iam.ket_noi()
    assert iam.hieu_luc(iam.claims_cua(
        iam.lay_tai_khoan(conn, "nhanvien")), conn)["level"] == 2
    conn.close()


def test_proxy_tiem_x_remote_actions(client, iam_db, monkeypatch):
    """Gateway tính hành động được phép của app đang vào và tiêm X-Remote-Actions
    (app CHỈ TIN CỜ). Bắt tại chỗ nối chuyen_tiep — không cần app sống."""
    import nen.gateway.main as gw
    bat: dict = {}

    async def _gia(request, **kw):
        bat.update(kw)
        from fastapi.responses import Response as R
        return R("ok")

    monkeypatch.setattr(gw, "chuyen_tiep", _gia)
    _login(client)
    client.get("/app/ai-agent/hoi-dap")
    assert bat["hanh_dong"] == ["nap_tai_lieu", "nguon_ngoai", "giam_sat",
                                "duyet_qa", "quan_tri"]         # Owner đủ 5
    assert bat["vai"] == "admin"
    _login(client, "nhanvien", "mk-nv-6")
    client.get("/app/ai-agent/hoi-dap")
    assert bat["hanh_dong"] == [] and bat["vai"] == "viewer"    # KD L2: rỗng, fail-closed


def test_phan_quyen_khong_tick_duoc_gio_owner(client):
    """Luật sắt: giỏ Owner tuyệt đối (vault, két...) không tick nào đè được."""
    _login(client)
    r = client.post("/general/permissions/grant", data={
        "ten": "nhanvien", "app_slug": "*", "hanh_dong": "vault", "gia_tri": "cho"})
    assert "không tick được" in r.text


def test_mien_quantri_ve_khu_nen(client):
    """UI_FLOW.md mục 7: vào miền quantri.outliery.test là tới thẳng khu nền."""
    _login(client)
    r = client.get("/", headers={"host": "quantri.outliery.test"})
    assert r.status_code == 303
    assert r.headers["location"] == "/general"


def test_cookie_mien_cha_khi_vao_bang_ten_mien(client):
    """Cookie đặt Domain=.outliery.test khi vào bằng miền → một đăng nhập chạy
    mọi miền con; vào bằng IP thì cookie host-only như cũ."""
    r = client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"},
                    headers={"host": "outliery.test"})
    assert "domain=.outliery.test" in (r.headers.get("set-cookie") or "").lower()
    r2 = client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})
    assert "domain" not in (r2.headers.get("set-cookie") or "").lower()


# ---------- proxy + claims (tích hợp thật) ----------

def test_proxy_app_la_404(client):
    _login(client)
    assert client.get("/app/khong-co/").status_code == 404


def test_proxy_tiem_claims_va_vut_header_gia(client, app_mau_server):
    _login(client)
    r = client.get("/app/app-mau/", headers={
        "X-Remote-User": "hacker",       # giả mạo từ trình duyệt — phải bị vứt
        "X-Remote-Role": "owner",
        "X-Remote-Level": "5",
    })
    assert r.status_code == 200
    assert "owner-test" in r.text        # claims thật từ session gateway
    assert "hacker" not in r.text        # header giả không lọt qua
    # Danh pháp Permissions v2: vai cao nhất là ADMIN — header không còn phát
    # vai "owner" (chữ đó chỉ còn nghĩa Owner hệ OUTLIERY).
    assert "Vai: <b>admin</b>" in r.text


def test_proxy_phat_x_remote_apps(client, app_mau_server):
    """UI_FLOW.md mục 2: gateway phát danh sách app user được vào qua
    X-Remote-Apps — sidebar các app dựng từ claims này, không tự đoán quyền.
    Header giả từ trình duyệt phải bị vứt (nằm trong _HEADER_CAM)."""
    _login(client)
    r = client.get("/app/app-mau/", headers={"X-Remote-Apps": "vault,gia-mao"})
    assert r.status_code == 200
    assert "gia-mao" not in r.text                    # header giả bị vứt
    assert "app-mau" in r.text                        # owner vào được app-mau
    assert "quan-tri" in r.text                       # owner mở được trang quản trị


def test_proxy_health_qua_gateway(client, app_mau_server):
    _login(client)
    r = client.get("/app/app-mau/health")
    assert r.status_code == 200
    assert r.json()["app"] == "app-mau"


def test_tong_quan_de_bao_dung_trang_thai(client, app_mau_server):
    """Trang Tổng quan đế (thay suc-khoe cũ): dịch vụ sống/chết + đế đã nạp gì."""
    _login(client)
    r = client.get("/general")
    assert r.status_code == 200
    assert "running" in r.text            # app-mau sống
    assert "Accounts (IAM)" in r.text     # khối đế: số tài khoản
    assert "Latest backup" in r.text


def test_profile_tu_cap_nhat_va_doi_mk_can_mk_hien_tai(client):
    """UI_FLOW.md mục 8: Profile tự cập nhật display name; đổi mật khẩu PHẢI gõ
    đúng mật khẩu hiện tại (luật V1 — v2 từng thiếu bước này)."""
    _login(client, "nhanvien", "mk-nv-6")
    r = client.post("/profile", data={"ten_hien_thi": "Nguyễn Văn Test",
                                      "email": "t@x.vn", "dien_thoai": "0900"})
    assert "Profile saved" in r.text and "Nguyễn Văn Test" in r.text
    r = client.post("/profile/mat-khau", data={
        "mk_hien_tai": "SAI-MK", "mk_moi": "mk-moi-7", "mk_lai": "mk-moi-7"})
    assert "Current password is incorrect" in r.text
    r = client.post("/profile/mat-khau", data={
        "mk_hien_tai": "mk-nv-6", "mk_moi": "mk-moi-7", "mk_lai": "mk-moi-7"})
    assert "Password changed" in r.text
    client.get("/logout")
    assert _login(client, "nhanvien", "mk-moi-7").status_code == 303


def test_proxy_phat_x_remote_name(client, app_mau_server, iam_db):
    """Display name chảy sang app qua claims X-Remote-Name (URL-encode)."""
    _login(client)
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.sua_ho_so_ca_nhan(conn, ow, ten_hien_thi="Chủ Doanh Nghiệp")
    conn.close()
    r = client.get("/app/app-mau/", headers={"X-Remote-Name": "gia-mao"})
    assert r.status_code == 200
    assert "gia-mao" not in r.text        # header giả bị vứt


# ---------- giỏ chức năng HR/Finance (DE.md mục 10) ----------

def test_proxy_phat_co_hr_finance(client, app_mau_server, iam_db):
    """Gateway phát cờ khu chức năng 'hr'/'finance' vào X-Remote-Apps — app to-chuc
    CHỈ TIN cờ này. Mặc định: Owner + HR L3+ → hr; Owner + Kế toán L2+ → finance.
    Ô TICK nhan_su/ke_toan trên trang Permissions THẮNG luật mặc định (cả hai
    chiều cho lẫn chặn) — helper _gio_chuc_nang, KHÔNG sửa iam.co_quyen."""
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "hr2", "mk-hr2-6", "Hành chính Nhân sự", 3,
                      phai_doi_mk=False)
    iam.tao_tai_khoan(conn, ow, "ketoan", "mk-kt-6", "Kế toán", 2, phai_doi_mk=False)
    conn.close()

    _login(client)                                       # Owner: đủ cả hai cờ
    t = client.get("/app/app-mau/").text
    assert ",hr" in t and "finance" in t

    _login(client, "hr2", "mk-hr2-6")                    # HR L3: hr có, finance không
    t = client.get("/app/app-mau/").text
    assert ",hr" in t and "finance" not in t

    _login(client, "ketoan", "mk-kt-6")                  # Kế toán L2: finance, không hr
    t = client.get("/app/app-mau/").text
    assert "finance" in t and ",hr" not in t

    _login(client, "nhanvien", "mk-nv-6")                # KD L2: không cờ nào
    t = client.get("/app/app-mau/").text
    assert ",hr" not in t and "finance" not in t

    conn = iam.ket_noi()                                 # tick lẻ thắng mặc định
    iam.gan_override(conn, ow, "nhanvien", "*", "ke_toan", True, "kiêm nhiệm Kế toán")
    iam.gan_override(conn, ow, "hr2", "*", "nhan_su", False, "chặn thử đè luật HR")
    conn.close()
    _login(client, "nhanvien", "mk-nv-6")
    assert "finance" in client.get("/app/app-mau/").text
    _login(client, "hr2", "mk-hr2-6")
    assert ",hr" not in client.get("/app/app-mau/").text


def test_post_ve_hr_303_ve_hub(client, iam_db):
    """HR HUB một cửa: form của hub POST thẳng route General kèm field ẩn ve=hr
    (whitelist) → 303 về /hr đúng tab kèm bao/loi; ve lạ/thiếu → render General
    như cũ (test cũ không vỡ)."""
    _login(client)
    r = client.post("/general/people/create", data={
        "ho_ten": "Người Hub", "bo_phan": "Kinh doanh", "ve": "hr"})
    assert r.status_code == 303
    assert r.headers["location"].startswith("/hr?tab=accounts&bao=")
    r = client.post("/general/accounts/create", data={
        "ten": "tk-hub", "mat_khau": "mk-tam-6", "bo_phan": "Kinh doanh",
        "level": 2, "ve": "hr"})
    assert r.status_code == 303
    assert r.headers["location"].startswith("/hr?tab=accounts&bao=")
    r = client.post("/general/accounts/update", data={     # lỗi cũng về hub, qua loi=
        "ten": "tk-hub", "hanh_dong": "xoa", "gia_tri": "go-sai", "ve": "hr"})
    assert r.status_code == 303
    assert "/hr?tab=accounts&loi=" in r.headers["location"]
    r = client.post("/general/people/create", data={       # ve ngoài whitelist → như cũ
        "ho_ten": "Người Thường", "bo_phan": "Kinh doanh", "ve": "la-hoac"})
    assert r.status_code == 200 and "Created profile" in r.text


def test_people_update_sua_ho_so_va_quyen(client, iam_db):
    """POST /general/people/update (iam.sua_nguoi — trả nợ 'hồ sơ chỉ tạo được'):
    HR/Owner đổi được trạng thái (gỡ mềm 'nghi', KHÔNG có xóa); nhân viên thường 403."""
    _login(client)
    client.post("/general/people/create",
                data={"ho_ten": "Hồ Sơ Sửa", "bo_phan": "Kinh doanh"})
    conn = iam.ket_noi()
    ma = iam.liet_ke_nguoi(conn)[-1]["ma"]
    conn.close()
    r = client.post("/general/people/update", data={
        "ma": ma, "trang_thai": "nghi", "ve": "hr"})
    assert r.status_code == 303
    assert r.headers["location"].startswith("/hr?tab=accounts&bao=")
    conn = iam.ket_noi()
    ns = next(n for n in iam.liet_ke_nguoi(conn) if n["ma"] == ma)
    conn.close()
    assert ns["trang_thai"] == "nghi"
    # THÔI VIỆC đi trọn đường route (mục 'Đã thôi việc' — Owner chốt 19/08):
    # không khai ngày → iam tự lấy hôm nay; nhận lại làm → xóa vết, hồ sơ CÒN.
    assert ns["ngay_thoi_viec"] == date.today().isoformat()
    r = client.post("/general/people/update", data={
        "ma": ma, "trang_thai": "nghi", "ngay_thoi_viec": "2026-08-10",
        "ly_do_thoi_viec": "Hết hợp đồng", "ve": "hr"})
    assert r.status_code == 303
    conn = iam.ket_noi()
    ns = next(n for n in iam.liet_ke_nguoi(conn) if n["ma"] == ma)
    conn.close()
    assert ns["ngay_thoi_viec"] == "2026-08-10" and ns["ly_do_thoi_viec"] == "Hết hợp đồng"
    client.post("/general/people/update", data={
        "ma": ma, "trang_thai": "hoat_dong", "ve": "hr"})
    conn = iam.ket_noi()
    ns = next(n for n in iam.liet_ke_nguoi(conn) if n["ma"] == ma)
    conn.close()
    assert ns["trang_thai"] == "hoat_dong" and ns["ngay_thoi_viec"] == ""
    client.post("/general/people/update", data={"ma": ma, "trang_thai": "nghi", "ve": "hr"})
    r = client.post("/general/people/update", data={       # trạng thái lạ → loi
        "ma": ma, "trang_thai": "xoa-han", "ve": "hr"})
    assert r.status_code == 303 and "/hr?tab=accounts&loi=" in r.headers["location"]
    _login(client, "nhanvien", "mk-nv-6")                  # nhân viên thường bị chặn
    assert client.post("/general/people/update", data={
        "ma": ma, "trang_thai": "hoat_dong"}).status_code == 403


def test_people_terminate_go_mem_va_khoa_dang_nhap(client, iam_db):
    """TERMINATE (Owner chốt 19/08 — THAY nút xóa tài khoản): một lượt bấm =
    hồ sơ về 'nghi' + ngày/lý do + KHÓA đăng nhập, KHÔNG xóa gì. Người không có
    giỏ tài khoản (HR L3) vẫn thôi việc được — hồ sơ chuyển, thông báo nói thẳng
    đăng nhập còn mở. Nhân viên thường 403."""
    _login(client)
    r = client.post("/general/accounts/create-full", data={
        "ho_ten": "Người Nghỉ", "bo_phan": "Kinh doanh", "vi_tri": "SEO",
        "username": "nguoinghi", "mat_khau": "mk-tam-6", "level": 2, "ve": "hr"})
    assert r.status_code == 303
    conn = iam.ket_noi()
    ma = next(n["ma"] for n in iam.liet_ke_nguoi(conn) if n["ho_ten"] == "Người Nghỉ")
    conn.close()

    r = client.post("/general/people/terminate", data={
        "ma": ma, "ngay_thoi_viec": "2026-08-10",
        "ly_do_thoi_viec": "Hết hợp đồng", "ve": "hr"})
    assert r.status_code == 303 and "/hr?tab=accounts&bao=" in r.headers["location"]
    conn = iam.ket_noi()
    ns = next(n for n in iam.liet_ke_nguoi(conn) if n["ma"] == ma)
    tk = iam.lay_tai_khoan(conn, "nguoinghi")
    conn.close()
    assert ns["trang_thai"] == "nghi" and ns["ngay_thoi_viec"] == "2026-08-10"
    assert ns["ly_do_thoi_viec"] == "Hết hợp đồng"
    assert tk and tk["khoa"] == 1                          # đăng nhập bị khóa, KHÔNG xóa

    # HR L3 (không có giỏ quan_tai_khoan): hồ sơ vẫn chuyển, đăng nhập còn mở
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "hr-lead", "mk-hr-6", iam.HR_BO_PHAN, 3,
                      phai_doi_mk=False)
    ns2 = iam.tao_nguoi(conn, ow, "Người Nghỉ 2", "Kinh doanh", "SEO")
    iam.tao_tai_khoan(conn, ow, "nguoinghi2", "mk-tam-6", "Kinh doanh", 2,
                      nguoi_ma=ns2["ma"], phai_doi_mk=False)
    conn.close()
    _login(client, "hr-lead", "mk-hr-6")
    r = client.post("/general/people/terminate", data={"ma": ns2["ma"], "ve": "hr"})
    assert r.status_code == 303
    assert "still%20open" in r.headers["location"]          # nói thẳng, không im lặng
    conn = iam.ket_noi()
    ns2m = next(n for n in iam.liet_ke_nguoi(conn) if n["ma"] == ns2["ma"])
    assert ns2m["trang_thai"] == "nghi" and ns2m["ngay_thoi_viec"] != ""   # ngày tự điền
    assert iam.lay_tai_khoan(conn, "nguoinghi2")["khoa"] == 0
    conn.close()

    _login(client, "nhanvien", "mk-nv-6")
    assert client.post("/general/people/terminate",
                       data={"ma": ma}).status_code == 403


def test_create_full_tron_goi_va_rollback(client, iam_db):
    """MỘT DÒNG = MỘT CON NGƯỜI (Owner gộp 16/08): create-full ra cả hồ sơ +
    tài khoản nối nguoi_ma, bộ phận tài khoản LẤY TỪ HỒ SƠ; username trùng bị
    chặn TRƯỚC khi tạo hồ sơ; lỗi tạo tài khoản → ROLLBACK hồ sơ vừa tạo
    (không mồ côi — bài học V2 GĐ2), có vết."""
    _login(client)
    r = client.post("/general/accounts/create-full", data={
        "ho_ten": "Người Trọn Gói", "bo_phan": "Kinh doanh", "vi_tri": "SEO",
        "username": "trongoi", "mat_khau": "mk-tam-6", "level": 2, "ve": "hr"})
    assert r.status_code == 303
    assert r.headers["location"].startswith("/hr?tab=accounts&bao=")
    conn = iam.ket_noi()
    tk = iam.lay_tai_khoan(conn, "trongoi")
    ns = next(n for n in iam.liet_ke_nguoi(conn) if n["ho_ten"] == "Người Trọn Gói")
    so_nguoi = len(iam.liet_ke_nguoi(conn))
    conn.close()
    assert tk["nguoi_ma"] == ns["ma"]
    assert tk["bo_phan"] == "Kinh doanh"          # bộ phận ăn theo hồ sơ
    assert tk["phai_doi_mk"] == 1                 # mật khẩu tạm phải đổi lần đầu

    r = client.post("/general/accounts/create-full", data={    # username TRÙNG
        "ho_ten": "Người Trùng", "bo_phan": "Kinh doanh",
        "username": "trongoi", "mat_khau": "mk-tam-6", "ve": "hr"})
    assert r.status_code == 303 and "loi=" in r.headers["location"]
    conn = iam.ket_noi()
    assert len(iam.liet_ke_nguoi(conn)) == so_nguoi            # không đẻ hồ sơ
    conn.close()

    r = client.post("/general/accounts/create-full", data={    # mật khẩu ngắn
        "ho_ten": "Người Lỗi TK", "bo_phan": "Kinh doanh",
        "username": "loi-tk", "mat_khau": "mk", "ve": "hr"})
    assert r.status_code == 303 and "loi=" in r.headers["location"]
    conn = iam.ket_noi()
    assert len(iam.liet_ke_nguoi(conn)) == so_nguoi            # rollback hồ sơ
    assert iam.lay_tai_khoan(conn, "loi-tk") is None
    assert any(d["hanh_dong"] == "rollback_tao_nguoi"
               for d in iam.doc_nhat_ky(conn, 10))
    conn.close()


def test_create_full_va_grant_theo_quyen(client, iam_db):
    """HR L3 (chỉ giỏ nhan_su): tạo hồ sơ KHÔNG kèm tài khoản qua create-full
    được; kèm username → 403 không tạo gì; POST grant cũng 403 (tài khoản vẫn
    độc quyền giỏ quan_tai_khoan). Owner grant cho hồ sơ sẵn → nối đúng, bộ phận
    theo hồ sơ; hồ sơ đã có tài khoản → từ chối (1 người = 1 tài khoản)."""
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "hr-b", "mk-hr-6", "Hành chính Nhân sự", 3,
                      phai_doi_mk=False)
    conn.close()
    _login(client, "hr-b", "mk-hr-6")
    r = client.post("/general/accounts/create-full", data={
        "ho_ten": "Hồ Sơ HR Tạo", "bo_phan": "Kinh doanh", "ve": "hr"})
    assert r.status_code == 303 and "bao=" in r.headers["location"]
    conn = iam.ket_noi()
    so_nguoi = len(iam.liet_ke_nguoi(conn))
    ma = iam.liet_ke_nguoi(conn)[-1]["ma"]
    conn.close()
    r = client.post("/general/accounts/create-full", data={
        "ho_ten": "HR Lấn Quyền", "bo_phan": "Kinh doanh",
        "username": "lan-quyen", "mat_khau": "mk-tam-6", "ve": "hr"})
    assert r.status_code == 403
    r = client.post("/general/accounts/grant", data={
        "ma": ma, "username": "lan-quyen", "mat_khau": "mk-tam-6", "level": 2})
    assert r.status_code == 403
    conn = iam.ket_noi()
    assert len(iam.liet_ke_nguoi(conn)) == so_nguoi            # 403 không đẻ gì
    assert iam.lay_tai_khoan(conn, "lan-quyen") is None
    conn.close()

    _login(client)
    r = client.post("/general/accounts/grant", data={
        "ma": ma, "username": "cap-sau", "mat_khau": "mk-tam-6", "level": 2,
        "ve": "hr"})
    assert r.status_code == 303
    assert r.headers["location"].startswith("/hr?tab=accounts&bao=")
    conn = iam.ket_noi()
    tk = iam.lay_tai_khoan(conn, "cap-sau")
    conn.close()
    assert tk["nguoi_ma"] == ma and tk["bo_phan"] == "Kinh doanh"
    r = client.post("/general/accounts/grant", data={          # đã có tài khoản
        "ma": ma, "username": "cap-nua", "mat_khau": "mk-tam-6", "ve": "hr"})
    assert r.status_code == 303 and "loi=" in r.headers["location"]


def test_people_cccd_va_tai_lieu_co_vet(client, iam_db, tmp_path, monkeypatch):
    """Hồ sơ mở rộng (DE.md mục 12.1): CCCD đầy đủ CHỈ qua route riêng + MỖI lượt
    xem một dòng nhật ký (khuôn vault); tài liệu gốc upload whitelist đuôi 422,
    tên traversal bị slug hóa, xem có vết, nhân viên thường 403."""
    monkeypatch.setenv("HO_SO_TAI_LIEU_DIR", str(tmp_path / "kho-tl"))
    _login(client)
    client.post("/general/people/create", data={
        "ho_ten": "Người Đầy Đủ", "bo_phan": "Kinh doanh", "vi_tri": "SEO",
        "ngay_sinh": "1998-04-12", "cccd": "079098012345",
        "dia_chi": "123 Lê Lợi", "ngay_vao": "2026-07-31", "cap_bac": "staff"})
    conn = iam.ket_noi()
    ma = iam.liet_ke_nguoi(conn)[-1]["ma"]
    conn.close()

    r = client.get(f"/general/people/cccd/{ma}")
    assert r.status_code == 200 and r.text == "079098012345"
    client.get(f"/general/people/cccd/{ma}")
    conn = iam.ket_noi()
    so_xem = sum(1 for d in iam.doc_nhat_ky(conn, 50)
                 if d["hanh_dong"] == "xem_cccd" and d["chi_tiet"] == ma)
    conn.close()
    assert so_xem == 2                                     # MỖI lượt một dòng vết

    r = client.post("/general/people/tai-lieu", data={"ma": ma, "loai": "cccd"},
                    files={"file": ("virus.exe", b"x", "application/octet-stream")})
    assert r.status_code == 422                            # đuôi lạ bị chặn
    r = client.post("/general/people/tai-lieu",
                    data={"ma": ma, "loai": "cccd", "ve": "hr"},
                    files={"file": ("..\\..\\scan cccd.pdf", b"PDF",
                                    "application/pdf")})
    assert r.status_code == 303
    assert r.headers["location"].startswith("/hr?tab=accounts&bao=")
    ten = [f.name for f in (tmp_path / "kho-tl" / ma).iterdir()]
    assert len(ten) == 1 and ten[0].startswith("cccd_") and ten[0].endswith(".pdf")
    assert ".." not in ten[0] and "\\" not in ten[0]       # traversal đã slug hóa

    assert client.get(f"/general/people/tai-lieu/{ma}/{ten[0]}").status_code == 200
    assert client.get(
        f"/general/people/tai-lieu/{ma}/..%5Ciam.db").status_code == 404
    conn = iam.ket_noi()
    assert any(d["hanh_dong"] == "xem_tai_lieu_ns" and ten[0] in d["chi_tiet"]
               for d in iam.doc_nhat_ky(conn, 20))
    assert any(d["hanh_dong"] == "nop_tai_lieu_ns" for d in iam.doc_nhat_ky(conn, 20))
    conn.close()

    _login(client, "nhanvien", "mk-nv-6")                  # ngoài giỏ nhan_su: 403
    assert client.get(f"/general/people/cccd/{ma}").status_code == 403
    assert client.get(f"/general/people/tai-lieu/{ma}/{ten[0]}").status_code == 403


def test_proxy_phat_co_accounts(client, app_mau_server, iam_db):
    """Cờ 'accounts' (tab Accounts của HR Hub) phát theo giỏ quan_tai_khoan:
    Owner có, HR L3 (chỉ quyen_nhan_su) KHÔNG — giữ luật 'tài khoản độc quyền
    Owner/Admin ủy quyền'."""
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "hr3", "mk-hr3-6", "Hành chính Nhân sự", 3,
                      phai_doi_mk=False)
    conn.close()
    _login(client)
    assert "accounts" in client.get("/app/app-mau/").text
    _login(client, "hr3", "mk-hr3-6")
    t = client.get("/app/app-mau/").text
    assert "accounts" not in t and ",hr" in t              # HR: có hub, không tab Accounts


def test_alias_hr_finance_tro_to_chuc(client, iam_db):
    """URL đẹp /hr + /finance trỏ app to-chuc (bo_qua tự bảo vệ vì lấy từ khóa
    _ALIAS). KHÔNG gọi sống cổng 9103 — máy dev có thể đang chạy bản to-chuc CŨ
    (luật: không restart service trong đợt code) → kiểm dây nối tĩnh:
    alias + route đã đăng ký + tien_to hợp đồng app có /hr /finance để proxy
    viết lại được đường con (/hr/chot-cong → /app/to-chuc/...)."""
    from nen.common.hop_dong import tim_app
    from nen.gateway.main import _ALIAS, _ALIAS_BO_QUA
    from nen.gateway.main import app as gw
    assert _ALIAS["/hr"] == ("to-chuc", "hr")
    assert _ALIAS["/finance"] == ("to-chuc", "finance")
    assert "/hr" in _ALIAS_BO_QUA and "/finance" in _ALIAS_BO_QUA
    duong = {r.path: getattr(r, "methods", set()) for r in gw.routes}
    assert "GET" in duong["/hr"] and "GET" in duong["/finance"]
    tc = tim_app("to-chuc")
    assert "/hr" in tc["tien_to"] and "/finance" in tc["tien_to"]


def test_khung_ghi_lai_duong_dan_iframe_de_F5_giu_cho():
    """Owner 24/08: "author extract an F5 lai chuyen ve trang chu, cac tab con lai
    cung vay". App khung nam trong iframe nen di ben TRONG app khong doi URL khung;
    F5 nap lai khung voi ?duong= cu = ve trang mac dinh. Khung phai doc duong dan that
    cua iframe (cung origin) roi replaceState."""
    import pathlib
    html = pathlib.Path("nen/gateway/templates/nen_khung_app.html").read_text(encoding="utf-8")
    assert "iframe.khung-app" in html and "history.replaceState" in html
    assert "contentWindow.location" in html
    assert "history.pushState" not in html,         "di trong app khong duoc de them muc lich su o khung (comment nhac pushState thi duoc)"
