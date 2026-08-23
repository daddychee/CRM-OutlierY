# -*- coding: utf-8 -*-
"""Mở thư mục NAS chứa bản dựng + DỌN file sau khi review xong (user chốt 20/08).

Đây là NGOẠI LỆ CÓ KIỂM SOÁT của nguyên tắc "app chỉ đọc NAS": mỗi tập đẻ ra
nhiều bản (fix lần 1, lần 2, Round 3…) nên sau khi duyệt xong phải dọn được,
mà bắt Manager mở Explorer gõ đường dẫn thì không ai làm.

SÁU chốt chặn cho một lệnh xóa (thứ tự kiểm ở server, không tin client một chữ):
  1. cờ hành động 'xoa' (Manager 4+) — route lo, như mọi thao tác hủy khác;
  2. đường phải resolve NẰM TRONG VR_NAS_DIR (chống ../ và ổ đĩa lạ);
  3. phải là FILE, không phải thư mục;
  4. chỉ đuôi VIDEO + PHỤ ĐỀ mới xóa được — dự án Premiere/CapCut, thư mục
     nguồn… tuyệt đối không đụng dù nằm ngay cạnh;
  5. client phải echo lại ĐÚNG TÊN FILE — chốt này chặn UI CŨ/hàng lệch (danh sách
     tải từ 10 phút trước, file đã đổi) chứ không phải để hành người dùng; lớp
     chặn tay-nhầm là hai bước bấm + ô tích ở giao diện;
  6. mọi lệnh xóa ghi nhật ký CHỈ-THÊM trước khi xóa — xóa xong mới ghi thì lỗi
     giữa chừng là mất dấu vết.

Bản ghi trong app đang trỏ file bị xóa sẽ được GỠ MỀM luôn (bình luận giữ nguyên
trong sổ) — đó chính là ý "dọn dẹp cho danh sách bớt dài".
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from src import kho_video

DUOI_XOA_DUOC = set(kho_video.DUOI_CHO_PHEP) | set(kho_video.DUOI_PHU_DE)


def unc_goc() -> str:
    """Đường UNC của gốc NAS (VR_NAS_UNC) để người dùng dán vào Explorer —
    trình duyệt không mở được file:// từ trang http nên chỉ đưa đường để copy."""
    return os.environ.get("VR_NAS_UNC", "").strip().rstrip("/" + chr(92))


def duong_unc(tuong_doi: str) -> str:
    goc = unc_goc()
    if not goc:
        return ""
    return goc + chr(92) + (tuong_doi or "").replace("/", chr(92))


def _nhat_ky() -> Path:
    return kho_video.kho_dir().parent / "db" / "nhat_ky_xoa_nas.csv"


def ghi_nhat_ky(nguoi: str, duong: str, co: int, ma: str) -> None:
    """Chỉ-THÊM: ai, xóa gì trên NAS, lúc nào, bao nhiêu byte, thuộc bản ghi nào."""
    f = _nhat_ky()
    f.parent.mkdir(parents=True, exist_ok=True)
    moi = not f.exists()
    with open(f, "a", newline="", encoding="utf-8-sig") as ra:
        w = csv.writer(ra)
        if moi:
            w.writerow(["luc", "nguoi", "duong_nas", "byte", "ma_video"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nguoi, duong, co, ma])


def liet_ke_thu_muc(duong_video_tuong_doi: str) -> dict:
    """Mọi file trong THƯ MỤC chứa bản dựng này — để thấy cái gì đang chiếm chỗ
    trước khi dọn. Trả cả file không xóa được (dự án, nguồn) nhưng gắn cờ rõ."""
    goc = kho_video.nas_dir()
    if goc is None:
        return {"cau_hinh": False, "muc": []}
    f = kho_video.duong_nas_an_toan(goc, duong_video_tuong_doi)
    thu_muc = f.parent if f.is_file() else f
    if not thu_muc.is_dir():
        raise FileNotFoundError(duong_video_tuong_doi)
    goc_rs = goc.resolve()
    if thu_muc != goc_rs and goc_rs not in thu_muc.parents:
        raise PermissionError("Thư mục ngoài gốc NAS")
    dang_dung = kho_video.cac_duong_nas_dang_dung()
    muc, tong = [], 0
    for e in sorted(thu_muc.iterdir(), key=lambda x: (x.is_dir(), x.name.lower())):
        if e.is_dir():
            continue
        try:
            co = e.stat().st_size
        except OSError:
            continue
        rel = e.relative_to(goc_rs).as_posix()
        tong += co
        muc.append({"ten": e.name, "duong": rel, "byte": co,
                    "xoa_duoc": e.suffix.lower() in DUOI_XOA_DUOC,
                    "dang_dung": rel in dang_dung})
    rel_tm = "" if thu_muc == goc_rs else thu_muc.relative_to(goc_rs).as_posix()
    return {"cau_hinh": True, "thu_muc": rel_tm, "unc": duong_unc(rel_tm),
            "tong_byte": tong, "muc": muc}


def xoa_file(tuong_doi: str, xac_nhan: str, nguoi: str) -> dict:
    """Xóa MỘT file trên NAS sau khi qua đủ chốt chặn (xem docstring đầu file).
    Bản ghi app đang trỏ file này bị gỡ mềm luôn. Trả thông tin để UI cập nhật."""
    goc = kho_video.nas_dir()
    if goc is None:
        raise FileNotFoundError("NAS chưa cấu hình")
    try:
        f = kho_video.duong_nas_an_toan(goc, tuong_doi)      # chốt 2
    except PermissionError:
        # ngoài gốc → trả như KHÔNG CÓ FILE: đường ngoài vùng không đáng được một
        # thông điệp riêng (cùng lệ 404 lặng lẽ của khối duyệt NAS)
        raise FileNotFoundError(tuong_doi)
    if not f.is_file():                                       # chốt 3
        raise FileNotFoundError(tuong_doi)
    if f.suffix.lower() not in DUOI_XOA_DUOC:                 # chốt 4
        raise PermissionError("Chỉ xóa được file video và phụ đề — file khác app "
                              "không đụng tới.")
    if (xac_nhan or "").strip() != f.name:                    # chốt 5
        raise ValueError("Tên xác nhận không khớp tên file.")
    rel = f.relative_to(goc.resolve()).as_posix()
    ban_ghi = kho_video.da_lien_ket(rel)
    ma = ban_ghi["ma"] if ban_ghi else ""
    co = f.stat().st_size
    ghi_nhat_ky(nguoi, rel, co, ma)                           # chốt 6 — ghi TRƯỚC
    f.unlink()
    if ma:
        kho_video.doi_trang_thai(ma, "da_xoa")   # gỡ mềm — bình luận vẫn còn trong sổ
    return {"ten": f.name, "byte": co, "ma_go": ma}
