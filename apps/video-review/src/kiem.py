# -*- coding: utf-8 -*-
"""CỬA KIỂM LOGIC video-review (02/09/2026) — "mỗi logic một sơ đồ".

Rà 02/09: app có 24 route mà chỉ 2 kịch bản, cả hai đo HẠ TẦNG (gốc NAS có đọc
được không, ffprobe có tồn tại không) — không phép nào chạm nghiệp vụ. Trong khi
đây là app mà sai một chốt là MẤT BẢN GỐC trên kho công ty (không Recycle Bin
trên NAS) hoặc leader mất tín hiệu bản dựng chờ duyệt.

Nguyên tắc: CHỈ-ĐỌC, 0 quota, hàm thuần + thư mục tạm — không đụng NAS thật,
không đụng sổ SQLite thật.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from src import don_nas, kho_video


def van_tay_dung_luong() -> dict:
    """CHỈ DUNG LƯỢNG là bằng chứng nội dung đổi. Tin mtime → la 'file bị ghi
    đè' oan mỗi lần NAS nhích ngày sửa (sự cố 26/08: Explorer đặt sẵn dung lượng
    đầy đủ nhưng mtime còn chạy 3 phút); người dùng học cách bỏ qua cảnh báo,
    rồi lần ghi đè THẬT cũng bị bỏ qua.

    Ngược lại dung lượng khác PHẢI báo — nếu không, bình luận gắn mốc giây trỏ
    vào bản khác: leader nói 'sửa giây 42' mà giây 42 giờ là cảnh khác."""
    import os
    tam = Path(tempfile.mkdtemp(prefix="kiem-vr-"))
    (tam / "ban-dung.mp4").write_bytes(b"x" * 1000)
    st = (tam / "ban-dung.mp4").stat()
    # trỏ gốc NAS sang thư mục tạm trong lúc kiểm — không đụng NAS thật
    cu = os.environ.get("VR_NAS_DIR")
    os.environ["VR_NAS_DIR"] = str(tam)
    goc = {"ma": "VR-CANARY", "nguon": "nas", "duong": "ban-dung.mp4",
           "kich_thuoc": 1000, "nas_mtime": st.st_mtime}
    # (a) mtime lệch 1 giờ, dung lượng KHỚP → KHÔNG báo đổi
    a = dict(goc, nas_mtime=st.st_mtime - 3600)
    # (b) dung lượng khác → PHẢI báo đổi
    b = dict(goc, kich_thuoc=999)
    try:
        ra_a = kho_video.tinh_trang_file(a)
        ra_b = kho_video.tinh_trang_file(b)
    except Exception as e:  # noqa: BLE001 — chữ ký khác thì nói thẳng
        return {"loi_dung_ham": f"{type(e).__name__}: {e}",
                "mtime_lech_khong_bao": None, "dung_luong_khac_thi_bao": None}
    finally:
        if cu is None:
            os.environ.pop("VR_NAS_DIR", None)
        else:
            os.environ["VR_NAS_DIR"] = cu
    return {"mtime_lech_khong_bao": ra_a.get("co") is True and not ra_a.get("doi"),
            "dung_luong_khac_thi_bao": bool(ra_b.get("doi")),
            "chi_tiet_a": ra_a, "chi_tiet_b": ra_b}


def ngoai_goc_404() -> dict:
    """Rào ép mọi đường dẫn nằm TRONG gốc NAS — rào duy nhất chặn đọc/xóa file
    bất kỳ trên máy chủ. Đường ngoài gốc phải ném lỗi (route dịch thành 404
    LẶNG LẼ, không 403 — 403 lộ ra 'có thứ gì đó ở đây')."""
    goc = Path(tempfile.mkdtemp(prefix="kiem-vr-goc-"))
    (goc / "trong.mp4").write_bytes(b"x")
    ca = [("trong.mp4", True), ("../../Windows", False),
          ("..\\..\\Windows\\System32", False)]
    sai = []
    for tuong_doi, qua in ca:
        try:
            kho_video.duong_nas_an_toan(goc, tuong_doi)
            that = True
        except (PermissionError, ValueError):
            that = False
        if that != qua:
            sai.append(tuong_doi)
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3]}


def canh_bao_codec() -> dict:
    """H.265/HEVC phát ra TIẾNG + MÀN HÌNH ĐEN và KHÔNG bắn sự kiện lỗi — kiểu
    hỏng tệ nhất. Bảng CODEC_PHAT_DUOC lỡ thêm 'hevc' là tắt cảnh báo toàn hệ
    mà canary hạ tầng (chỉ kiểm ffprobe tồn tại) không hề biết."""
    ca = [("hevc", True), ("h265", True), ("h264", False), ("av1", False),
          ("", False)]
    sai = [c for c, co_canh_bao in ca
           if bool(kho_video.canh_bao_codec(c)) != co_canh_bao]
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3],
            "hevc_khong_trong_bang": "hevc" not in kho_video.CODEC_PHAT_DUOC,
            "so_codec_phat_duoc": len(kho_video.CODEC_PHAT_DUOC)}


def xoa_an_toan() -> dict:
    """Ba chốt của đường dọn NAS — hỏng cái nào cũng MẤT BẢN GỐC (không có
    Recycle Bin trên NAS):
      1. chỉ xóa được đuôi video + phụ đề (không .prproj/.aep/.psd — mất công
         trình dựng);
      2. chỉ nhận đúng chữ 'feedback' (nhận 'FB'/'Feedback cũ' là mở đường xóa
         cả thư mục tập chứa bản master);
      3. duyệt đúng 3 nấc — 'can_sua' đã nghỉ hưu, hồi sinh là hỏng câm."""
    duoi_nguy = {".prproj", ".aep", ".psd", ".exe"}
    lot = sorted(duoi_nguy & set(don_nas.DUOI_XOA_DUOC))
    return {"so_duoi_xoa_duoc": len(don_nas.DUOI_XOA_DUOC),
            "duoi_nguy_hiem_lot": lot,
            "khong_xoa_du_an_dung": not lot,
            "feedback_dung_mot_ten": (
                set(kho_video.TEN_THU_MUC_FEEDBACK) == {"feedback"}),
            "trang_thai": list(kho_video.TRANG_THAI_VIDEO),
            "dung_3_nac": (tuple(kho_video.TRANG_THAI_VIDEO)
                           == ("dang_duyet", "da_duyet", "da_xoa"))}


def phat_206_khuc() -> dict:
    """Phát video trả 206 từng khúc ≤8MB. Trả trọn file 2–10GB mỗi lần tua =
    nghẽn LAN, trình duyệt treo — 'vẫn chạy được' nên không ai báo lỗi."""
    import os
    khuc = int(os.getenv("VR_KHUC_MB", "8"))
    return {"khuc_mb": khuc, "trong_tran": khuc <= 8}


CAC_MA = {"van-tay-dung-luong": van_tay_dung_luong,
          "ngoai-goc-404": ngoai_goc_404,
          "canh-bao-codec": canh_bao_codec,
          "xoa-an-toan": xoa_an_toan,
          "phat-206-khuc": phat_206_khuc}
