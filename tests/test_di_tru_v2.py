# -*- coding: utf-8 -*-
"""Test di trú nhân sự V2 → iam.db — ghim: dry-run không ghi, nhập đủ + idempotent,
seed đụng mã phải --don-seed, đổi tên tick radary/xoa→toan_quyen, IT→Kinh doanh,
hash bcrypt giữ nguyên (đăng nhập được bằng mật khẩu cũ)."""
import json

import bcrypt
import pytest

from nen.iam import iam
from nen.iam.di_tru_v2 import di_tru

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def moi_truong(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    nguon = tmp_path / "agent-app"
    (nguon / "nhan-su").mkdir(parents=True)
    (nguon / "kho-tai-lieu").mkdir()
    hash_giang = bcrypt.hashpw(b"mk-giang", bcrypt.gensalt()).decode()
    (nguon / "users.txt").write_text(
        f"thanh:{bcrypt.hashpw(b'mk-thanh', bcrypt.gensalt()).decode()}:Ban quản trị:5\n"
        f"huonggiangsss:{hash_giang}:Kinh doanh:4\n"
        f"lamtn:{bcrypt.hashpw(b'mk-lam', bcrypt.gensalt()).decode()}:Kinh doanh:4\n"
        f"Tungtb:{bcrypt.hashpw(b'mk-tung', bcrypt.gensalt()).decode()}:Vận hành - Sản xuất:2:1\n",
        encoding="utf-8")
    (nguon / "nhan-su" / "ho_so.json").write_text(json.dumps({
        "NS-001": {"ma": "NS-001", "trang_thai": "dang_lam", "ten_dang_nhap": "huonggiangsss",
                   "planner_id": "", "ho_ten": "Đặng Hương Giang", "bo_phan": "Kinh doanh",
                   "chuc_danh": "Quản lý kênh", "ngay_vao": "2025-09-17",
                   "sdt": "0567", "email": "g@x.com", "ghi_chu": "Lead SEO"},
        "NS-004": {"ma": "NS-004", "trang_thai": "dang_lam", "ten_dang_nhap": "lamtn",
                   "planner_id": "", "ho_ten": "Nguyễn Tùng Lâm", "bo_phan": "IT",
                   "chuc_danh": "IT", "ngay_vao": "2025-10-01",
                   "sdt": "", "email": "", "ghi_chu": ""},
        "NS-012": {"ma": "NS-012", "trang_thai": "dang_lam", "ten_dang_nhap": "Tungtb",
                   "planner_id": "ns_ns012", "ho_ten": "Bùi Thanh Tùng",
                   "bo_phan": "Vận hành - Sản xuất", "chuc_danh": "Editor (Dựng video)",
                   "cap_bac": "2", "ngay_vao": "2026-06-08",
                   "sdt": "", "email": "", "ghi_chu": ""},
    }, ensure_ascii=False), encoding="utf-8")
    (nguon / "kho-tai-lieu" / "phan_quyen.json").write_text(json.dumps({
        "huonggiangsss": {"hd:seo:quan_tri": True},
        "lamtn": {"hd:radary:xoa": False},
    }), encoding="utf-8")
    return nguon


def test_mac_dinh_chi_liet_ke(moi_truong):
    rp = di_tru(moi_truong)
    assert not rp["da_ghi"] and len(rp["nguoi_moi"]) == 3 and len(rp["tk_moi"]) == 4
    conn = iam.ket_noi()
    assert conn.execute("SELECT COUNT(*) c FROM nguoi").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM tai_khoan").fetchone()["c"] == 0
    conn.close()


def test_chay_nhap_du_va_idempotent(moi_truong):
    rp = di_tru(moi_truong, chay=True)
    assert rp["da_ghi"]
    conn = iam.ket_noi()
    # hash giữ nguyên → đăng nhập bằng mật khẩu cũ; thanh không hồ sơ → nguoi_ma NULL
    assert iam.xac_thuc(conn, "huonggiangsss", "mk-giang")["level"] == 4
    assert iam.lay_tai_khoan(conn, "thanh")["nguoi_ma"] is None
    assert iam.lay_tai_khoan(conn, "Tungtb")["phai_doi_mk"] == 1
    giang = dict(conn.execute("SELECT * FROM nguoi WHERE ma='NS-001'").fetchone())
    assert giang["trang_thai"] == "hoat_dong" and giang["vi_tri"] == "Quản lý kênh"
    assert giang["cap_bac"] == "manager" and giang["email"] == "g@x.com"
    assert iam.lay_tai_khoan(conn, "huonggiangsss")["nguoi_ma"] == "NS-001"
    # IT → Kinh doanh (hồ sơ) — vị trí IT giữ nguyên
    lam = dict(conn.execute("SELECT * FROM nguoi WHERE ma='NS-004'").fetchone())
    assert lam["bo_phan"] == "Kinh doanh" and lam["vi_tri"] == "IT"
    # cap_bac từ hồ sơ số "2" + planner_id chảy theo
    tung = dict(conn.execute("SELECT * FROM nguoi WHERE ma='NS-012'").fetchone())
    assert tung["cap_bac"] == "staff" and tung["planner_id"] == "ns_ns012"
    # tick: seo giữ slug chờ app; radary/xoa đổi tên toan_quyen; ly_do bắt buộc có
    r = conn.execute("SELECT * FROM quyen_override WHERE ten_tai_khoan='lamtn'").fetchone()
    assert (r["app_slug"], r["hanh_dong"], r["cho_phep"]) == ("radary", "toan_quyen", 0)
    assert r["ly_do"]
    assert conn.execute("SELECT COUNT(*) c FROM quyen_override WHERE app_slug='seo'"
                        ).fetchone()["c"] == 1
    conn.close()
    # chạy lại: không nhân đôi
    rp2 = di_tru(moi_truong, chay=True)
    assert not rp2["nguoi_moi"] and not rp2["tk_moi"] and not rp2["tick_moi"]
    assert len(rp2["nguoi_bo_qua"]) == 3 and len(rp2["tk_bo_qua"]) == 4


def test_seed_dung_ma_phai_don_seed(moi_truong):
    conn = iam.ket_noi()
    with conn:
        conn.execute("INSERT INTO nguoi (ma, ho_ten, bo_phan, trang_thai, tao_luc) "
                     "VALUES ('NS-001','Người Seed Thử','Hành chính Nhân sự','hoat_dong','x')")
        conn.execute("INSERT INTO tai_khoan (ten, mk_bcrypt, nguoi_ma, bo_phan, level, "
                     "admin_uy_quyen, phai_doi_mk, khoa, tao_luc) "
                     "VALUES ('thaophp','h','NS-001','Hành chính Nhân sự',4,0,1,0,'x')")
        conn.execute("INSERT INTO tai_khoan (ten, mk_bcrypt, nguoi_ma, bo_phan, level, "
                     "admin_uy_quyen, phai_doi_mk, khoa, tao_luc) "
                     "VALUES ('bot','h',NULL,'Ban quản trị',5,0,0,0,'x')")
    conn.close()
    # thiếu --don-seed → DỪNG không ghi (kể cả chay=True)
    rp = di_tru(moi_truong, chay=True)
    assert rp["seed_nguoi"] and rp["seed_tk"] == ["thaophp (nối NS-001)"] and not rp["da_ghi"]
    conn = iam.ket_noi()
    assert conn.execute("SELECT ho_ten FROM nguoi WHERE ma='NS-001'"
                        ).fetchone()["ho_ten"] == "Người Seed Thử"
    conn.close()
    # có --don-seed → seed bay, V2 vào, bot (không nối seed) giữ nguyên
    rp = di_tru(moi_truong, chay=True, don_seed=True)
    assert rp["da_ghi"]
    conn = iam.ket_noi()
    assert conn.execute("SELECT ho_ten FROM nguoi WHERE ma='NS-001'"
                        ).fetchone()["ho_ten"] == "Đặng Hương Giang"
    assert iam.lay_tai_khoan(conn, "thaophp") is None
    assert iam.lay_tai_khoan(conn, "bot")["level"] == 5
    conn.close()
