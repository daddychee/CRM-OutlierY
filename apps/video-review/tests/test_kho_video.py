# -*- coding: utf-8 -*-
"""Test tầng dữ liệu kho_video — sổ SQLite + liên kết NAS + luật quyền bình luận."""
import itertools

import pytest

from src import kho_video

_DEM = itertools.count(1)


def _them(ten="x", duoi=".mp4", nguoi="an", bo_phan="", noi_dung=b"v"):
    """Đặt file vào NAS giả rồi liên kết — khuôn thêm video duy nhất từ 20/08."""
    goc = kho_video.nas_dir()
    f = goc / f"ban-{next(_DEM)}{duoi}"
    if duoi in kho_video.DUOI_CHO_PHEP:
        f.write_bytes(noi_dung)
    return kho_video.them_video_nas(ten, f.name, nguoi, bo_phan, len(noi_dung),
                                    f.stat().st_mtime if f.exists() else 0.0)


def test_khoi_tao_ghi_schema_version():
    conn = kho_video.ket_noi()
    try:
        v = conn.execute("SELECT v FROM schema_version").fetchone()["v"]
    finally:
        conn.close()
    assert v >= 1


def test_khoi_tao_chay_lai_khong_vo():
    kho_video.khoi_tao()   # idempotent — chạy lần 2 không nổ
    kho_video.khoi_tao()


def test_them_video_nas_ma_bat_bien_va_chi_tro_duong():
    """Liên kết = ghi sổ ĐƯỜNG NAS + vân tay; app không sinh file nào."""
    goc = kho_video.nas_dir()
    (goc / "xuat").mkdir()
    f = goc / "xuat" / "LI049_Round 2.mp4"
    f.write_bytes(b"v" * 10)
    b = kho_video.them_video_nas("Bản dựng Tập 1", "xuat/LI049_Round 2.mp4", "an",
                                 "Vận hành", 10, f.stat().st_mtime)
    assert b["ma"] == "VR-0001"
    assert b["duong"] == "xuat/LI049_Round 2.mp4"
    assert b["ten_file"] == "LI049_Round 2.mp4"      # giữ nguyên tên anh em đặt
    v = kho_video.lay_video("VR-0001")
    assert v["nguon"] == "nas" and v["mime"] == "video/mp4"
    assert kho_video.duong_video(v) == f
    assert not list(kho_video.kho_dir().rglob("*.mp4"))
    assert kho_video.them_video_nas("hai", "xuat/hai.webm", "an", "", 1, 0)["ma"] == "VR-0002"


def test_them_video_nas_duoi_la_bi_chan():
    with pytest.raises(ValueError):
        kho_video.them_video_nas("x", "xuat/virus.exe", "an", "", 1, 0)
    with pytest.raises(ValueError):
        kho_video.them_video_nas("x", "   ", "an", "", 1, 0)


def test_duong_video_chan_so_tro_ra_ngoai_goc_nas():
    """Sổ bị sửa tay trỏ ra ngoài gốc → resolve trả None, không phát bừa file lạ."""
    b = kho_video.them_video_nas("x", "a.mp4", "an", "", 1, 0)
    v = dict(kho_video.lay_video(b["ma"]))
    v["duong"] = "../../Windows/win.ini"
    assert kho_video.duong_video(v) is None
    assert kho_video.tinh_trang_file(v)["co"] is False


def test_tinh_trang_file_bat_mat_file_va_ghi_de():
    b = _them(noi_dung=b"v" * 20)
    v = kho_video.lay_video(b["ma"])
    tt = kho_video.tinh_trang_file(v)
    assert tt["co"] is True and tt["doi"] is False
    kho_video.duong_video(v).write_bytes(b"v" * 999)          # ghi đè bản khác
    assert kho_video.tinh_trang_file(v)["doi"] is True
    kho_video.duong_video(v).unlink()                          # xóa hẳn trên NAS
    assert kho_video.tinh_trang_file(v)["co"] is False


def test_doi_trang_thai_va_go_mem():
    b = _them()
    kho_video.doi_trang_thai(b["ma"], "da_duyet")
    assert kho_video.lay_video(b["ma"])["trang_thai"] == "da_duyet"
    with pytest.raises(ValueError):
        kho_video.doi_trang_thai(b["ma"], "bay_bay")
    # gỡ mềm → biến khỏi danh sách nhưng bản ghi còn
    kho_video.doi_trang_thai(b["ma"], "da_xoa")
    assert all(v["ma"] != b["ma"] for v in kho_video.danh_sach_video())
    assert kho_video.lay_video(b["ma"]) is not None


def test_binh_luan_vong_doi_va_quyen():
    b = _them()
    bl = kho_video.them_binh_luan(b["ma"], "an", "cắt cảnh này", ts_giay=12.5,
                                  ve_json='{"net": []}')
    assert bl["ts_giay"] == 12.5
    # người khác KHÔNG duyệt → cấm giải/xóa
    with pytest.raises(PermissionError):
        kho_video.giai_binh_luan(bl["id"], "binh", False)
    # chính chủ giải được; leader (co_duyet) mở lại được
    kho_video.giai_binh_luan(bl["id"], "an", False)
    assert kho_video.ds_binh_luan(b["ma"])[0]["trang_thai"] == "da_giai"
    kho_video.mo_lai_binh_luan(bl["id"], "chi", True)
    kho_video.xoa_binh_luan(bl["id"], "chi", True)
    assert kho_video.ds_binh_luan(b["ma"]) == []


def test_binh_luan_chan_rong_va_ve_json_hong_va_video_ma():
    b = _them()
    with pytest.raises(ValueError):
        kho_video.them_binh_luan(b["ma"], "an", "   ")
    with pytest.raises(ValueError):
        kho_video.them_binh_luan(b["ma"], "an", "ok", ve_json="{hong")
    with pytest.raises(KeyError):
        kho_video.them_binh_luan("VR-9999", "an", "ok")


def test_ds_binh_luan_moc_truoc_chung_sau():
    b = _them()
    kho_video.them_binh_luan(b["ma"], "an", "chung")               # không mốc
    kho_video.them_binh_luan(b["ma"], "an", "muon", ts_giay=30)
    kho_video.them_binh_luan(b["ma"], "an", "som", ts_giay=5)
    ds = [x["noi_dung"] for x in kho_video.ds_binh_luan(b["ma"])]
    assert ds == ["som", "muon", "chung"]


def test_danh_sach_dem_binh_luan_mo():
    b = _them()
    bl = kho_video.them_binh_luan(b["ma"], "an", "một")
    kho_video.them_binh_luan(b["ma"], "an", "hai")
    kho_video.giai_binh_luan(bl["id"], "an", False)
    hang = kho_video.danh_sach_video()[0]
    assert hang["so_mo"] == 1
    assert hang["so_tong"] == 2      # so_tong đếm CẢ đã giải — tín hiệu "đã có người review"


def test_ma_tap_gom_dung_ban_cua_cung_tap():
    """Mã tập lấy từ tên file, lùi về thư mục; mã sổ VR-000N KHÔNG được coi là tập."""
    goi = lambda tf, d="": kho_video.ma_tap({"ten_file": tf, "duong": d + tf, "ten": tf})
    assert goi("LI037 fix lần 1.mp4") == goi("LI037 fix lần 2.mp4") == "LI037"
    assert goi("LI049_Round 3.mp4") == "LI049"
    assert goi("LI082_4K.mp4") == "LI082"
    # file đời cũ do app tự đặt tên: bỏ qua VR-0003, lấy mã thật trong slug
    assert goi("2026-08-19_VR-0003_li083.mp4") == "LI083"
    # không nhận ra thì lùi về tên thư mục, cuối cùng mới chịu thua
    assert goi("ban dung cuoi.mp4", "Life In/US/LI073/") == "LI073"
    assert goi("ban dung cuoi.mp4", "Life In/US/ky-yeu/") == ""
