# -*- coding: utf-8 -*-
"""HỆ KIỂM LOGIC to-chuc (02/09/2026) — cửa kiểm GET /api/kiem/{ma}.

Rà 02/09 (Owner: "chạy lại từng app để không bỏ sót"): app có 41 route + 19 màn
(Finance 10 tab, HR 4 tab, KPI, NAS, Vault) mà CHỈ MỘT kịch bản canary — và nó
chỉ soi "3 file có tồn tại không", không chạm logic nào.

Đây là app nguy hiểm nhất hệ: sai là **trả tiền sai**, **đánh giá người sai**,
hoặc **lộ mật khẩu công ty**. Bảy mã dưới đóng các van đó. Hàm thuần + thư mục
tạm (conftest autouse) → 0 quota, không đụng sổ tiền thật.
"""
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app, client=("127.0.0.1", 50000))


def _kiem(ma):
    r = client.get(f"/api/kiem/{ma}")
    assert r.status_code == 200, r.text
    return r.json()


def test_ma_la_404():
    assert client.get("/api/kiem/khong-co").status_code == 404


def test_khong_loopback_404():
    ngoai = TestClient(app, client=("192.168.1.9", 1))
    assert ngoai.get("/api/kiem/luong-khong-tu-tru").status_code == 404


def test_luong_khong_tu_tru():
    """Owner chốt TUYỆT ĐỐI: máy KHÔNG tự trừ lương theo ngày công / đi muộn.
    Ai đó 'tối ưu' thêm hệ số ngày công là tiền bị cắt tự động theo con số đo
    hiện diện — sai kiểu này im như tờ vì bảng vẫn ra số đẹp."""
    b = _kiem("luong-khong-tu-tru")
    assert b["cung_luong_du_khac_ngay_cong"] is True
    assert b["thieu_du_lieu_de_trong"] is True


def test_kpi_van_chong_bia():
    """Nguồn KPI chết → '—' kèm lý do, TUYỆT ĐỐI không 0 giả. Hiện 0 thì
    Manager đọc thành 'người này không làm gì' → đánh giá sai người thật."""
    b = _kiem("kpi-van-chong-bia")
    assert b["nguon_chet_la_none"] is True
    assert b["khong_co_so_0_gia"] is True


def test_cham_cong_vao_khong_doi():
    """Giờ VÀO là tín hiệu ĐẦU ngày, không bao giờ bị đè. Nếu thành gán thẳng,
    giờ vào bị đẩy theo tín hiệu cuối → mọi người thành đi làm lúc 18h."""
    b = _kiem("cham-cong-vao-ra")
    assert b["vao_giu_tin_hieu_dau"] is True
    assert b["ra_theo_tin_hieu_cuoi"] is True


def test_chot_cong_chi_them():
    """Chốt công kỳ ghi ĐÚNG MỘT LẦN — chốt đè = sửa lịch sử chấm công sau khi
    đã trả lương, đối chiếu về sau mất cơ sở."""
    b = _kiem("chot-cong-chi-them")
    assert b["lan_hai_bi_tu_choi"] is True


def test_so_tien_chi_them():
    """Sổ tiền chỉ-thêm, sửa = bút toán ĐẢO. Nếu đường nào ghi đè dòng cũ thì
    sổ mất tính bất biến → đối soát/kiểm toán sụp mà báo cáo vẫn ra số đẹp."""
    b = _kiem("so-tien-chi-them")
    assert b["dong_goc_con_nguyen"] is True
    assert b["dao_sinh_dong_moi"] is True


def test_vault_dia_khong_ban_ro():
    """Trên đĩa không bao giờ có bản rõ — trộm file/backup là đọc hết, đúng thứ
    AES-GCM sinh ra để chặn."""
    b = _kiem("vault-dia-ma-hoa")
    assert b["dia_khong_chua_ban_ro"] is True
    assert b["chua_mo_khong_doc_duoc"] is True


def test_nguoi_nghi_ra_khoi_bang():
    """Người đã thôi việc không còn trong bảng lương — còn trong bảng là CHI
    TIỀN cho người không còn làm, mà sổ chỉ-thêm nên bút toán đó không xóa."""
    b = _kiem("nguoi-nghi-ra-khoi-bang")
    assert b["nghi_khong_vao_bang"] is True


def test_kiem_chay_lap_khong_ban_so_that():
    """LỖI THẬT tự bắt 02/09: `chot_cong_chi_them` chỉ trỏ CHAM_CONG_DIR sang
    thư mục tạm, quên CHAM_CONG_CHOT_DIR (bản chốt dùng env RIÊNG) → phép kiểm
    GHI BẢN CHỐT GIẢ vào sổ thật, rồi lượt canary sau đỏ oan; tệ hơn: HR không
    chốt được kỳ đó nữa vì "kỳ đã chốt rồi".

    Ghim: chạy lặp phải ra CÙNG kết quả, và sổ chốt thật không mọc file nào."""
    import os
    from pathlib import Path

    from src import cham_cong
    truoc = set(Path(cham_cong._thu_muc_chot()).glob("*.json")) \
        if Path(cham_cong._thu_muc_chot()).is_dir() else set()
    ket = [_kiem("chot-cong-chi-them")["lan_hai_bi_tu_choi"] for _ in range(3)]
    sau = set(Path(cham_cong._thu_muc_chot()).glob("*.json")) \
        if Path(cham_cong._thu_muc_chot()).is_dir() else set()
    assert ket == [True, True, True], f"chạy lặp ra kết quả khác nhau: {ket}"
    assert sau == truoc, f"phép kiểm ghi bẩn sổ chốt thật: {sau - truoc}"


def test_kiem_khong_ghi_ban_so_luong_va_xep_loai():
    """Cùng họ lỗi CHAM_CONG_CHOT_DIR: `luong_khong_tu_tru` trỏ 'TO_CHUC_DB'
    (biến KHÔNG tồn tại) thay vì LUONG_DIR / KPI_DANH_GIA_DIR → ghi bẩn sổ lương
    cơ bản và sổ xếp loại THẬT. Hậu quả: bảng lương thật mọc 2 người ma 'a'/'b'
    lương 10tr, và xếp loại B khống cho kỳ đó.

    Ghim: chạy lặp ra cùng kết quả VÀ hai sổ thật không mọc file nào."""
    from pathlib import Path

    from src import kpi_danh_gia, luong
    def _chup():
        ra = set()
        for d in (Path(luong._duong("luong-co-ban.json")).parent,
                  Path(kpi_danh_gia._thu_muc())):
            if d.is_dir():
                ra |= set(d.glob("*.json"))
        return ra

    truoc = _chup()
    ket = [_kiem("luong-khong-tu-tru")["cung_luong_du_khac_ngay_cong"]
           for _ in range(2)]
    assert ket == [True, True], f"chạy lặp ra kết quả khác nhau: {ket}"
    assert _chup() == truoc, f"phép kiểm ghi bẩn sổ thật: {_chup() - truoc}"
