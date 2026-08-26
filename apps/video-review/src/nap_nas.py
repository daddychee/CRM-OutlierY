# -*- coding: utf-8 -*-
"""Duyệt NAS + LIÊN KẾT video vào app — KHÔNG chép byte nào (user chốt 20/08/2026).

Quy trình công ty: anh em xuất bản dựng lên NAS rồi vào app chọn đúng file đó.
App chỉ ghi sổ ĐƯỜNG TƯƠNG ĐỐI trong VR_NAS_DIR → thêm video là việc TỨC THÌ
(trước phải chép 2-10GB mất 5-10 phút), kho app không phình, không còn bản trùng.

- Gốc duyệt khai qua env VR_NAS_DIR — CHƯA khai → tính năng ẨN (lệ NAS_DUONG_DAN
  hệ cũ). Client chỉ gửi ĐƯỜNG TƯƠNG ĐỐI trong gốc; server resolve + kiểm
  nằm-trong-gốc (chống path traversal — chốt ở SERVER, không tin client).
- NAS CHỈ ĐỌC tuyệt đối: app không chép, không ghi phụ đề, không xóa, không đổi
  tên. File .srt anh em để cạnh video được ĐỌC trực tiếp lúc phát.
"""
from __future__ import annotations

from pathlib import Path

from src import kho_video

nas_dir = kho_video.nas_dir          # giữ tên quen cho route/test


def liet_ke(tuong_doi: str) -> dict:
    """Một cấp thư mục: thư mục con + file video (lọc đuôi), kèm cỡ MB và cờ
    da_them (file đã có bản ghi sống trong app — chống thêm trùng một bản dựng)."""
    goc = nas_dir()
    if goc is None:
        return {"cau_hinh": False, "muc": []}
    muc = kho_video.duong_nas_an_toan(goc, tuong_doi)
    if not muc.is_dir():
        raise FileNotFoundError(tuong_doi)
    goc_rs = goc.resolve()
    dang_dung = kho_video.cac_duong_nas_dang_dung()
    ra = []
    for e in sorted(muc.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if e.name.startswith("."):
            continue
        rel = e.relative_to(goc_rs).as_posix()
        if e.is_dir():
            ra.append({"ten": e.name, "loai": "thu_muc", "duong": rel})
        elif e.suffix.lower() in kho_video.DUOI_CHO_PHEP:
            ra.append({"ten": e.name, "loai": "file", "duong": rel,
                       "mb": round(e.stat().st_size / 1048576, 1),
                       "da_them": rel in dang_dung})
    duong_hien = "" if muc == goc_rs else muc.relative_to(goc_rs).as_posix()
    return {"cau_hinh": True, "duong": duong_hien, "muc": ra}


def lien_ket(tuong_doi: str, ten: str, nguoi: str, bo_phan: str) -> dict:
    """Ghi sổ video trỏ tới file NAS. Kiểm hết Ở CỬA (trong gốc, có thật, đúng đuôi,
    chưa liên kết) rồi mới ghi — không có tác vụ nền vì không chép byte nào.
    Vân tay (dung lượng + ngày sửa) chụp NGAY LÚC NÀY để sau phát hiện ghi đè."""
    goc = nas_dir()
    if goc is None:
        raise FileNotFoundError("NAS chưa cấu hình")
    f = kho_video.duong_nas_an_toan(goc, tuong_doi)
    if not f.is_file():
        raise FileNotFoundError(tuong_doi)
    if f.suffix.lower() not in kho_video.DUOI_CHO_PHEP:
        raise ValueError("Chỉ nhận video mp4 / webm / mov / m4v.")
    rel = f.relative_to(goc.resolve()).as_posix()
    cu = kho_video.da_lien_ket(rel)
    if cu is not None:
        raise FileExistsError(cu["ma"])
    # CHÉP CHƯA XONG thì chặn ngay tại cửa (sự cố 26/08: liên kết lúc Windows còn
    # đang chép → file trên NAS đứt giữa chừng, reviewer xem tới phút thứ 2 mới chết).
    if kho_video.dang_bi_ghi(f):
        raise BlockingIOError(f.name)
    st = f.stat()
    # dò codec NGAY LÚC THÊM: H.265 phát ra tiếng mà hình đen và KHÔNG báo lỗi gì,
    # biết sớm thì người thêm được cảnh báo ngay thay vì người review ngồi đoán.
    # + quét thử vài lát xem file có đứt/hỏng không (xem kho_video.quet_hong).
    return kho_video.them_video_nas((ten or "").strip() or f.stem, rel, nguoi,
                                    bo_phan, st.st_size, st.st_mtime,
                                    kho_video.doc_codec(f), kho_video.quet_hong(f))
