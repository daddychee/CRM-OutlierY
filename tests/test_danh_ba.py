# -*- coding: utf-8 -*-
"""Test danh bạ thực thể — mảnh ④, bản DB (Đ1 khối đế 16/08/2026).

API đọc giữ chữ ký thời CSV; `duong` giờ trỏ file SQLite."""
import pytest

from nen.common import danh_ba


@pytest.fixture()
def db(tmp_path, monkeypatch):
    duong = tmp_path / "danh_ba.db"
    monkeypatch.setenv("DANH_BA_DB", str(duong))
    conn = danh_ba.ket_noi()
    yield conn
    conn.close()


def _seed(conn):
    tt = danh_ba.them_thi_truong(conn, "US", "English")
    ng = danh_ba.them_ngach(conn, "Life In", trang_thai="khai_thac")
    ke = danh_ba.them_kenh(conn, "Outland", ng, thi_truong_ma=tt,
                           channel_id="UCSoRLy1", loai_kenh="compilation",
                           trang_thai="monetized", phu_trach="NS-016")
    danh_ba.them_bi_danh(conn, ke, "outland kr")
    return tt, ng, ke


# ---------- chuan_hoa_ten (giữ nguyên thời CSV) ----------

def test_chuan_hoa_bo_dau_va_d():
    assert danh_ba.chuan_hoa_ten("Đời Sống Mỹ") == "doi song my"


def test_chuan_hoa_gon_khoang_trang_va_hoa_thuong():
    assert danh_ba.chuan_hoa_ten("  Life   IN ") == "life in"


def test_chuan_hoa_rong():
    assert danh_ba.chuan_hoa_ten("") == ""


# ---------- sinh mã + niche-trước-kênh ----------

def test_sinh_ma_tu_ten_va_chong_trung(db):
    ng = danh_ba.them_ngach(db, "Life In")
    assert ng == "N-LIFE-IN"
    ke1 = danh_ba.them_kenh(db, "Outland", ng)
    assert ke1 == "K-OUTLAND"
    danh_ba.them_bi_danh(db, ke1, "outland cũ")
    # tên trùng alias người khác giữ → chặn; tên khác sinh mã nối -2 khi đụng mã
    with pytest.raises(ValueError):
        danh_ba.them_kenh(db, "outland cũ", ng)


def test_kenh_bat_buoc_co_ngach_truoc(db):
    with pytest.raises(Exception):        # FK: ngách chưa tồn tại → chặn từ cửa
        danh_ba.them_kenh(db, "Mồ côi", "N-KHONG-CO")


def test_channel_id_unique_nhung_nhieu_null_duoc(db):
    ng = danh_ba.them_ngach(db, "Space")
    danh_ba.them_kenh(db, "A", ng)                       # channel_id NULL
    danh_ba.them_kenh(db, "B", ng)                       # NULL thứ hai vẫn OK
    danh_ba.them_kenh(db, "C", ng, channel_id="UC1")
    with pytest.raises(Exception):
        danh_ba.them_kenh(db, "D", ng, channel_id="UC1")  # UCxxx trùng → chặn


# ---------- tra cứu (chữ ký cũ) ----------

def test_tra_theo_ten_chuan(db, tmp_path):
    _seed(db)
    assert danh_ba.tra_thuc_the("outland")["ma"] == "K-OUTLAND"


def test_tra_theo_bi_danh_khong_phan_biet_hoa(db):
    _seed(db)
    assert danh_ba.tra_thuc_the("OUTLAND KR")["ma"] == "K-OUTLAND"


def test_tra_khong_khop_tra_none_khong_doan(db):
    _seed(db)
    assert danh_ba.tra_thuc_the("kênh lạ hoắc") is None


def test_liet_ke_theo_loai(db):
    _seed(db)
    assert [t["ma"] for t in danh_ba.liet_ke("kenh")] == ["K-OUTLAND"]
    assert [t["ma"] for t in danh_ba.liet_ke("ngach")] == ["N-LIFE-IN"]
    assert [t["ma"] for t in danh_ba.liet_ke("thi_truong")] == ["TT-US"]


# ---------- liên kết app (thay cột cứng CSV) ----------

def test_lien_ket_app_va_tuong_thich_cot_cu(db):
    _, _, ke = _seed(db)
    danh_ba.dat_lien_ket(db, ke, "seo-optimize", "outland-o-01")
    t = danh_ba.tra_thuc_the("outland")
    assert danh_ba.khoa_ung_dung(t, "seo-optimize") == "outland-o-01"
    assert danh_ba.khoa_ung_dung(t, "seo_profile") == "outland-o-01"   # tên cột CSV cũ
    assert danh_ba.khoa_ung_dung(t, "plannery") is None                # chưa nối → None
    danh_ba.dat_lien_ket(db, ke, "seo-optimize", "")                   # rỗng = gỡ
    assert danh_ba.khoa_ung_dung(danh_ba.tra_thuc_the("outland"), "seo-optimize") is None


# ---------- vòng đời + sửa ----------

def test_doi_trang_thai_va_khai_tu_go_mem(db):
    _, _, ke = _seed(db)
    danh_ba.doi_trang_thai_kenh(db, ke, "ngu_dong")
    danh_ba.khai_tu_kenh(db, ke)
    t = danh_ba.tra_thuc_the("outland")
    assert t["trang_thai"] == "khai_tu"                  # gỡ mềm — dòng còn nguyên
    with pytest.raises(ValueError):
        danh_ba.doi_trang_thai_kenh(db, ke, "bay-bong")


def test_sua_truong_van_hanh_khong_doi_ma(db):
    _, _, ke = _seed(db)
    danh_ba.sua_thuc_the(db, "kenh", ke, ten_chuan="Outland US", phu_trach="NS-001",
                         ma="K-HACK")                    # 'ma' bị lọc bỏ — bất biến
    t = danh_ba.liet_ke("kenh")[0]
    assert t["ma"] == "K-OUTLAND" and t["ten_chuan"] == "Outland US"
    assert t["phu_trach"] == "NS-001"


# ---------- bí danh unique toàn cục ----------

def test_bi_danh_unique_toan_cuc(db):
    _, ng, ke = _seed(db)
    ke2 = danh_ba.them_kenh(db, "Wheel", ng)
    with pytest.raises(ValueError):
        danh_ba.them_bi_danh(db, ke2, "Outland KR")      # alias đã thuộc kênh khác


# ---------- cache theo mtime + cửa Excel ----------

def test_cache_moi_khi_ghi_thi_thay_ngay(db):
    _seed(db)
    assert len(danh_ba.liet_ke("kenh")) == 1
    ng2 = danh_ba.them_ngach(db, "Space")
    danh_ba.them_kenh(db, "Astro", ng2)
    assert len(danh_ba.liet_ke("kenh")) == 2             # mtime đổi → cache tự tươi


def test_xuat_csv_du_cot_ngay_tao(db):
    _seed(db)
    ra = danh_ba.xuat_csv()
    assert "K-OUTLAND" in ra and "ten_chuan" in ra and "tao_luc" in ra


# ---------- thị trường CỦA NGÁCH (002 — Owner chốt 18/08/2026) ----------

def test_ngach_moi_khong_co_thi_truong_mac_dinh(db):
    """Luật 18/08: hết cảnh mọi niche 'mặc định' cả danh mục thị trường —
    ngách mới tạo phải 0 thị trường tới khi user chọn."""
    _seed(db)
    ng2 = danh_ba.them_ngach(db, "Space")
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == ng2)
    assert n["thi_truong_cua"] == []


def test_dat_thi_truong_ngach_thay_ca_tap_va_chan_ma_la(db):
    tt_us, ng, _ = _seed(db)
    tt_kr = danh_ba.them_thi_truong(db, "Korea", "Korean")
    danh_ba.dat_thi_truong_ngach(db, ng, [tt_us, tt_kr, tt_us])   # dedup
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == ng)
    assert sorted(n["thi_truong_cua"]) == sorted([tt_us, tt_kr])
    danh_ba.dat_thi_truong_ngach(db, ng, [tt_kr])                 # thay cả tập
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == ng)
    assert n["thi_truong_cua"] == [tt_kr]
    import pytest as _pt
    with _pt.raises(ValueError):
        danh_ba.dat_thi_truong_ngach(db, ng, ["TT-LA"])           # mã lạ chặn từ cửa
    with _pt.raises(ValueError):
        danh_ba.dat_thi_truong_ngach(db, "N-LA", [tt_kr])         # ngách lạ chặn


def test_backfill_002_tu_kenh_dang_dung(tmp_path, monkeypatch):
    """Backfill migration: ngách nhận thị trường mà KÊNH của nó đang đứng —
    dựng DB bằng schema 001 rồi mở lại cho 002 chạy đè."""
    import sqlite3
    from pathlib import Path
    duong = tmp_path / "cu.db"
    conn = sqlite3.connect(duong)
    sql_001 = (Path(danh_ba.MIGRATIONS) / "001_khoi_tao.sql").read_text(encoding="utf-8-sig")
    conn.executescript(sql_001)
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS schema_version (phien_ban INTEGER);"
        "DELETE FROM schema_version; INSERT INTO schema_version VALUES (1);"
        "INSERT INTO thi_truong VALUES ('TT-US','US','English','','2026-01-01');"
        "INSERT INTO ngach VALUES ('N-LIFE','Life In','thu','','2026-01-01');"
        "INSERT INTO kenh VALUES ('K-OUT','Outland',NULL,'N-LIFE','TT-US','','uom_mam',NULL,'','','','2026-01-01','');")
    conn.commit(); conn.close()
    monkeypatch.setenv("DANH_BA_DB", str(duong))
    conn = danh_ba.ket_noi()          # migrate chạy 002 → backfill
    conn.close()
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == "N-LIFE")
    assert n["thi_truong_cua"] == ["TT-US"]
