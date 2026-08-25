# -*- coding: utf-8 -*-
"""B4 + B5 — màn Giao việc, màn Báo cáo, phạm vi xem (FLOW-v3 §9.1) + kho quy trình."""
import pytest
from fastapi.testclient import TestClient

from src import main, tuan
from src.main import app

client = TestClient(app)

# Sổ nhân sự giả — thay nen/iam trong test (app không tự giữ user, IAM là của tầng nền)
SO = [{"ten": "huytq", "level": 3, "bo_phan": "Vận hành", "ho_ten": "Trần Quốc Huy"},
      {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Nguyễn Thu Hà"},
      {"ten": "ducm", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Lê Minh Đức"},
      {"ten": "ngocpb", "level": 2, "bo_phan": "Kinh doanh", "ho_ten": "Phạm Bảo Ngọc"},
      {"ten": "lannh", "level": 3, "bo_phan": "Hành chính Nhân sự", "ho_ten": "Nguyễn Hoàng Lan"}]

LEADER_H = {"X-Remote-User": "huytq", "X-Remote-Level": "3", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
            "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
            "X-Remote-Apps": "tasky"}
NV_H = {"X-Remote-User": "hant", "X-Remote-Level": "2", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
        "X-Remote-Actions": "vao", "X-Remote-Apps": "tasky"}
MANAGER = {"X-Remote-User": "ducl", "X-Remote-Level": "4", "X-Remote-Dept": "Kinh%20doanh",
           "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan,bao_cao_cong_ty"}
HR = {"X-Remote-User": "lannh", "X-Remote-Level": "3",
      "X-Remote-Dept": "H%C3%A0nh%20ch%C3%ADnh%20Nh%C3%A2n%20s%E1%BB%B1",
      "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan,bao_cao_nhan_su"}

LEADER = {"ten": "huytq", "level": 3, "bo_phan": "Vận hành"}
NHANVIEN = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
NV_KHAC_BP = {"ten": "ngocpb", "level": 2, "bo_phan": "Kinh doanh"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}


@pytest.fixture(autouse=True)
def _so_nhan_su_gia(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: (list(SO), ""))


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _xong(ma, tieu_de="Dựng 6 video", loai="Dựng video", nguoi=NHANVIEN):
    """Một việc đi trọn vòng: giao → nhận → checklist → báo xong → xác nhận."""
    v = tuan.them_viec_giao(ma, LEADER, nguoi, tieu_de, loai)
    tuan.nhan_viec(ma, v["id"], nguoi)
    tuan.them_buoc(ma, v["id"], nguoi, "Rà transcript")
    tuan.them_buoc(ma, v["id"], nguoi, "Dựng thô")
    tuan.bao_xong(ma, v["id"], nguoi)
    tuan.xac_nhan_viec(ma, v["id"], LEADER)
    return v


# ---------- gate ----------

def test_nhan_vien_khong_vao_duoc_man_giao_viec_va_bao_cao():
    assert client.get("/giao-viec", headers=NV_H).status_code == 403
    assert client.get("/bao-cao-tuan", headers=NV_H).status_code == 403


def test_thieu_header_hanh_dong_thi_fail_closed():
    """Không có X-Remote-Actions → 403, app không tự suy quyền từ level."""
    r = client.get("/giao-viec", headers={"X-Remote-User": "huytq", "X-Remote-Level": "5"})
    assert r.status_code == 403


# ---------- màn giao việc ----------

def test_chi_hien_cap_duoi_cung_bo_phan(ma):
    """Ô giao việc nay nằm TRONG Goal (25/08) — phải có Goal thì mới có ô đó."""
    from src import muc_tieu as mt_lo
    mt_lo.tao({"ten": "huytq", "level": 4, "bo_phan": "Vận hành"}, "Goal A", "kq")
    r = client.get("/muc-tieu", headers=LEADER_H)
    assert r.status_code == 200
    assert "Nguyễn Thu Hà" in r.text and "Lê Minh Đức" in r.text
    assert "Phạm Bảo Ngọc" not in r.text      # khác bộ phận
    # CHÍNH MÌNH nay có trong danh sách — Manager tự giao việc cho mình được
    # (Owner chốt 25/08); ngang cấp NGƯỜI KHÁC thì vẫn không.
    assert "Trần Quốc Huy" in r.text


def test_giao_viec_qua_api_va_level_lay_tu_so_khong_lay_tu_form(ma):
    r = client.post("/api-tasky/giao", headers=LEADER_H,
                    data={"nguoi": "hant", "tieu_de": "Dựng 6 video",
                          "loai_viec": "Dựng video", "tuan_xem": ma})
    assert r.status_code == 200
    assert tuan.viec_cua(ma, "hant")[0]["trang_thai"] == tuan.CHO_NHAN


def test_khong_giao_duoc_sang_bo_phan_khac(ma):
    r = client.post("/api-tasky/giao", headers=LEADER_H,
                    data={"nguoi": "ngocpb", "tieu_de": "x", "loai_viec": "y", "tuan_xem": ma})
    assert r.status_code == 403


def test_khong_giao_duoc_cho_nguoi_ngoai_so_nhan_su(ma):
    r = client.post("/api-tasky/giao", headers=LEADER_H,
                    data={"nguoi": "khongcoai", "tieu_de": "x", "loai_viec": "y", "tuan_xem": ma})
    assert r.status_code == 400


def test_xac_nhan_va_tra_lai(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc A", "Dựng video")
    tuan.nhan_viec(ma, v["id"], NHANVIEN)
    tuan.bao_xong(ma, v["id"], NHANVIEN)

    assert client.post("/api-tasky/tra-lai", headers=LEADER_H,
                       data={"id": v["id"], "tuan_xem": ma}).status_code == 200
    assert tuan.viec_cua(ma, "hant")[0]["trang_thai"] == tuan.DANG_LAM

    tuan.bao_xong(ma, v["id"], NHANVIEN)
    assert client.post("/api-tasky/xac-nhan", headers=LEADER_H,
                       data={"id": v["id"], "tuan_xem": ma}).status_code == 200
    assert tuan.thong_ke_nguoi(ma, "hant")["ti_le"] == 100


def test_huy_thieu_ly_do_bi_chan(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc B", "Dựng video")
    r = client.post("/api-tasky/huy", headers=LEADER_H, data={"id": v["id"], "tuan_xem": ma})
    assert r.status_code == 400 and "lý do" in r.json()["detail"]


def test_doi_sang_tuan_sau_va_doi_nguoi_qua_api(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc C", "Dựng video")
    r = client.post("/api-tasky/doi", headers=LEADER_H,
                    data={"id": v["id"], "ly_do": "chờ editor", "nguoi_moi": "ducm", "tuan_xem": ma})
    assert r.status_code == 200
    sau = tuan.tuan_lien_ke(ma, 1)
    assert tuan.viec_cua(sau, "ducm")[0]["so_lan_doi"] == 1


def test_doi_sang_nguoi_bo_phan_khac_bi_chan(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc D", "Dựng video")
    r = client.post("/api-tasky/doi", headers=LEADER_H,
                    data={"id": v["id"], "nguoi_moi": "ngocpb", "tuan_xem": ma})
    assert r.status_code == 403


def test_con_viec_treo_thi_khong_dong_duoc_tuan(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc E", "Dựng video")
    r = client.post("/api-tasky/dong-tuan", headers=LEADER_H, data={"nguoi": "hant", "tuan_xem": ma})
    assert r.status_code == 400 and "chưa xử lý" in r.json()["detail"]

    tuan.huy_viec(ma, v["id"], LEADER, "giao nhầm người")
    assert client.post("/api-tasky/dong-tuan", headers=LEADER_H,
                       data={"nguoi": "hant", "tuan_xem": ma}).status_code == 200


# ---------- phạm vi báo cáo (§9.1) ----------

def test_leader_chi_thay_bo_phan_minh(ma):
    _xong(ma)
    r = client.get("/bao-cao-tuan", headers=LEADER_H)
    assert "Nguyễn Thu Hà" in r.text and "Phạm Bảo Ngọc" not in r.text


def test_manager_thay_moi_bo_phan(ma):
    """Giữ lệ 04/08: Manager XEM ngang nhau mọi bộ phận.

    Từ 25/08 tab công ty không bóc từng người (trùng tab Bộ phận) → kiểm quyền ở
    chính chỗ nó sống: mở lần lượt từng bộ phận."""
    _xong(ma)
    a = client.get("/bao-cao-tuan?pham_vi=bo-phan&bo=Vận hành", headers=MANAGER)
    b = client.get("/bao-cao-tuan?pham_vi=bo-phan&bo=Kinh doanh", headers=MANAGER)
    assert "Nguyễn Thu Hà" in a.text and "Phạm Bảo Ngọc" in b.text


def test_hr_leader_thay_toan_cong_ty(ma):
    _xong(ma)
    a = client.get("/bao-cao-tuan?pham_vi=bo-phan&bo=Vận hành", headers=HR)
    b = client.get("/bao-cao-tuan?pham_vi=bo-phan&bo=Kinh doanh", headers=HR)
    assert "Nguyễn Thu Hà" in a.text and "Phạm Bảo Ngọc" in b.text


def test_bao_cao_khong_lo_checklist_chi_hien_so(ma):
    _xong(ma)
    r = client.get("/bao-cao-tuan", headers=MANAGER)
    assert "Rà transcript" not in r.text


def test_nguoi_chua_co_viec_hien_dau_gach_trong_bao_cao(ma):
    _xong(ma)
    r = client.get("/bao-cao-tuan?pham_vi=bo-phan", headers=MANAGER)
    assert "— chưa có việc" in r.text


# ---------- kho quy trình (nền §5) ----------

def test_kho_quy_trinh_chua_du_ba_lan_thi_khong_de_xuat(ma):
    _xong(ma, "Việc 1")
    _xong(ma, "Việc 2")
    kho = tuan.kho_quy_trinh()
    assert kho[0]["so_checklist"] == 2 and kho[0]["du_de_rut"] is False
    assert kho[0]["con_thieu"] == 1
    r = client.get("/bao-cao-tuan?pham_vi=bo-phan", headers=MANAGER)
    assert "chưa đủ tiền lệ" in r.text


def test_du_ba_lan_thi_rut_ra_buoc_lap_nhieu_nhat(ma):
    for i in range(3):
        _xong(ma, f"Việc {i}")
    kho = tuan.kho_quy_trinh()
    assert kho[0]["du_de_rut"] is True and kho[0]["lan_lap"] == 3
    assert kho[0]["buoc_hay_nhat"] in ("Rà transcript", "Dựng thô")


def test_viec_chua_xac_nhan_khong_vao_kho_quy_trinh(ma):
    """Chỉ học từ việc ĐÃ HOÀN THÀNH — checklist của việc dở dang chưa chứng minh gì."""
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc dở", "Dựng video")
    tuan.nhan_viec(ma, v["id"], NHANVIEN)
    tuan.them_buoc(ma, v["id"], NHANVIEN, "Bước gì đó")
    assert tuan.kho_quy_trinh() == []


# ---------- sidebar ----------

def test_sidebar_chi_hien_muc_nguoi_do_co_quyen(ma):
    """Mục con dựng trong vòng lặp sb_apps (X-Remote-Apps) và chỉ hiện khi có CỜ
    hành động tương ứng — nhân viên không thấy đường vào Giao việc / Báo cáo."""
    # so trên THUỘC TÍNH href, không so chuỗi trần: JS trong trang có
    # location.href = "/muc-tieu" nên chuỗi trần khớp cả với nhân viên
    r_nv = client.get("/tasky", headers=NV_H)
    assert 'href="/muc-tieu"' not in r_nv.text and 'href="/bao-cao-tuan"' not in r_nv.text
    r_ld = client.get("/tasky", headers=LEADER_H)
    assert 'href="/muc-tieu"' in r_ld.text and 'href="/bao-cao-tuan"' in r_ld.text


# ---------- thu lại việc đóng tuần (Owner yêu cầu 24/08) ----------

def test_dong_nham_thi_mo_lai_duoc(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc F", "Dựng video")
    tuan.huy_viec(ma, v["id"], LEADER, "giao nhầm")
    client.post("/api-tasky/dong-tuan", headers=LEADER_H, data={"nguoi": "hant", "tuan_xem": ma})
    assert tuan.thong_ke_nguoi(ma, "hant")["da_dong"] is True

    r = client.post("/api-tasky/mo-lai-tuan", headers=LEADER_H,
                    data={"nguoi": "hant", "tuan_xem": ma})
    assert r.status_code == 200
    assert tuan.thong_ke_nguoi(ma, "hant")["da_dong"] is False


def test_chua_dong_thi_khong_mo_lai_duoc(ma):
    r = client.post("/api-tasky/mo-lai-tuan", headers=LEADER_H,
                    data={"nguoi": "hant", "tuan_xem": ma})
    assert r.status_code == 400 and "chưa đóng" in r.json()["detail"]


def test_khong_mo_lai_tuan_cua_nguoi_minh_khong_quan(ma):
    """Leader Vận hành không thu lại được tuần của người Kinh doanh."""
    v = tuan.them_viec_giao(ma, OWNER, NV_KHAC_BP, "Việc KD", "Nghiên cứu")
    tuan.huy_viec(ma, v["id"], OWNER, "dọn")
    tuan.dong_tuan(ma, "ngocpb", OWNER)
    with pytest.raises(PermissionError):
        tuan.mo_lai_tuan(ma, "ngocpb", LEADER)


def test_owner_mo_lai_duoc_tat(ma):
    tuan.dong_tuan(ma, "hant", LEADER)
    tuan.mo_lai_tuan(ma, "hant", OWNER)
    assert tuan.thong_ke_nguoi(ma, "hant")["da_dong"] is False


def test_mo_lai_de_lai_vet_ai_mo(ma, tmp_path):
    import json
    tuan.dong_tuan(ma, "hant", LEADER)
    tuan.mo_lai_tuan(ma, "hant", LEADER)
    dong = [json.loads(d) for d in
            (tmp_path / "db" / "nhat-ky.jsonl").read_text(encoding="utf-8").splitlines()]
    cuoi = dong[-1]
    assert cuoi["hanh_dong"] == "mo_lai_tuan" and cuoi["ai"] == "huytq"
    assert cuoi["dong_boi"] == "huytq"       # giữ vết ai đã đóng trước đó


def test_nut_mo_lai_hien_canh_chip_da_dong(ma):
    """Nút Đóng tuần / Mở lại chuyển sang màn Báo cáo (gộp màn Giao việc 25/08)."""
    tuan.dong_tuan(ma, "hant", LEADER)
    r = client.get("/bao-cao-tuan?pham_vi=bo-phan", headers=LEADER_H)
    assert "Đã đóng" in r.text and 'data-mo-lai="hant"' in r.text


# ---------- màn Giao việc dựng lại theo ngôn ngữ mới ----------

def test_gom_viec_cua_quan_theo_ba_nhom(ma):
    v1 = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Chờ nhận", "x")       # cần xử lý
    v2 = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Đang làm", "x")
    tuan.nhan_viec(ma, v2["id"], NHANVIEN)                                # đang chạy
    v3 = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Báo xong", "x")
    tuan.nhan_viec(ma, v3["id"], NHANVIEN)
    tuan.bao_xong(ma, v3["id"], NHANVIEN)                                 # cần xử lý
    n = tuan.nhom_cho_leader(ma, LEADER, [{"ten": "hant"}])
    assert len(n["can_xu_ly"]) == 2 and len(n["dang_chay"]) == 1
    assert v1["id"] in [x["id"] for x in n["can_xu_ly"]]


def test_canh_bao_bo_qua_muc_bang_khong(ma):
    """Chip '0 quá hạn' là nhiễu — chỉ hiện thứ thật sự có."""
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Chờ nhận", "x")
    cb = tuan.nhom_cho_leader(ma, LEADER, [{"ten": "hant"}])["canh_bao"]
    chu = [c["chu"] for c in cb]
    assert "1 chưa nhận" in chu and not any(c.startswith("0 ") for c in chu)


def test_leader_khong_thay_viec_ngoai_pham_vi(ma):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc của Hà", "x")
    n = tuan.nhom_cho_leader(ma, LEADER, [])
    assert n["can_xu_ly"] == [] and n["dang_chay"] == [] and n["xong"] == []


# ---------- gộp màn Giao việc (25/08) ----------

def test_duong_cu_giao_viec_van_song_bang_redirect(ma):
    """Team đã bookmark /giao-viec — không để chết, chuyển sang Goal."""
    r = client.get("/giao-viec", headers=LEADER_H, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/muc-tieu"




def test_viec_ngoai_goal_van_xac_nhan_duoc_o_bao_cao(ma):
    """Bỏ tab Việc lẻ (25/08) — việc ngoài Goal chuyển sang Báo cáo để không mất chỗ."""
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc ngoài Goal", "x")
    tuan.nhan_viec(ma, v["id"], NHANVIEN)
    tuan.bao_xong(ma, v["id"], NHANVIEN)
    r = client.get("/bao-cao-tuan?pham_vi=bo-phan", headers=LEADER_H)
    assert "Chờ bạn xử lý" in r.text and "Việc ngoài Goal" in r.text


def test_ly_do_tu_choi_doc_duoc_o_bao_cao(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc bị từ chối", "x")
    tuan.tu_choi_viec(ma, v["id"], NHANVIEN, "Đang gánh 3 việc gấp")
    r = client.get("/bao-cao-tuan?pham_vi=bo-phan", headers=LEADER_H)
    assert "Đang gánh 3 việc gấp" in r.text and "Cần giao lại" in r.text
