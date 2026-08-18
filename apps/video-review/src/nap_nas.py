# -*- coding: utf-8 -*-
"""Nạp video từ NAS — đường file lớn KHÔNG qua trình duyệt/proxy (user chốt 18/08).

Share NAS nằm ngay trên máy chủ nên "nạp từ NAS" = chép đĩa-sang-đĩa cục bộ.
- Root duyệt khai qua env VR_NAS_DIR — CHƯA khai → tính năng ẨN (lệ NAS_DUONG_DAN
  hệ cũ). Client chỉ gửi ĐƯỜNG TƯƠNG ĐỐI trong root; server resolve + kiểm
  nằm-trong-root (chống path traversal — chốt ở server, không tin client).
- Chép chạy NỀN (hàm SYNC → BackgroundTasks/threadpool — bài học khóa event loop
  19/07 hệ cũ), tiến độ % THẬT theo byte đã chép. CHÉP XONG MỚI GHI SỔ video —
  chép hỏng thì không có bản ghi ma nào, chỉ còn thông điệp lỗi trong tác vụ.
- File gốc trên NAS chỉ ĐỌC, không bao giờ bị đụng.
- Registry tác vụ TRONG BỘ NHỚ (đủ cho 1 worker; mất khi restart — giới hạn đã
  biết, cùng lệ tác vụ nền Data Analytics B2).
"""
from __future__ import annotations

import os
import secrets
import threading
from pathlib import Path

from src import kho_video

_TAC_VU: dict[str, dict] = {}
_KHOA = threading.Lock()


def nas_dir() -> Path | None:
    d = os.environ.get("VR_NAS_DIR", "").strip()
    if not d:
        return None
    p = Path(d)
    return p if p.is_dir() else None


def _duong_an_toan(goc: Path, tuong_doi: str) -> Path:
    """Đường client gửi → đường tuyệt đối TRONG root; ngoài root → PermissionError.
    Đường tuyệt đối/ổ đĩa client nhét vào cũng bị resolve rồi rơi ngoài root."""
    td = (tuong_doi or "").replace("\\", "/").strip("/")
    goc_rs = goc.resolve()
    if not td:
        return goc_rs
    con = (goc / td).resolve()
    if con != goc_rs and goc_rs not in con.parents:
        raise PermissionError("Đường ngoài root NAS")
    return con


def liet_ke(tuong_doi: str) -> dict:
    """Một cấp thư mục: thư mục con + file video (lọc đuôi cho phép), kèm cỡ MB."""
    goc = nas_dir()
    if goc is None:
        return {"cau_hinh": False, "muc": []}
    muc = _duong_an_toan(goc, tuong_doi)
    if not muc.is_dir():
        raise FileNotFoundError(tuong_doi)
    goc_rs = goc.resolve()
    ra = []
    for e in sorted(muc.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if e.name.startswith("."):
            continue
        rel = e.relative_to(goc_rs).as_posix()
        if e.is_dir():
            ra.append({"ten": e.name, "loai": "thu_muc", "duong": rel})
        elif e.suffix.lower() in kho_video.DUOI_CHO_PHEP:
            ra.append({"ten": e.name, "loai": "file", "duong": rel,
                       "mb": round(e.stat().st_size / 1048576, 1)})
    duong_hien = "" if muc == goc_rs else muc.relative_to(goc_rs).as_posix()
    return {"cau_hinh": True, "duong": duong_hien, "muc": ra}


def tao_tac_vu(tuong_doi: str, ten: str, nguoi: str, bo_phan: str) -> str:
    """Kiểm hết ở CỬA (file có thật, đuôi, trần) rồi mới đăng ký tác vụ chép nền."""
    goc = nas_dir()
    if goc is None:
        raise FileNotFoundError("NAS chưa cấu hình")
    f = _duong_an_toan(goc, tuong_doi)
    if not f.is_file():
        raise FileNotFoundError(tuong_doi)
    duoi = f.suffix.lower()
    if duoi not in kho_video.DUOI_CHO_PHEP:
        raise ValueError("Chỉ nhận video mp4 / webm / mov / m4v.")
    size = f.stat().st_size
    tran = int(os.environ.get("VR_NAS_MAX_MB", "20480")) * 1024 * 1024
    if size > tran:
        raise OverflowError(f"File quá {tran // 1048576}MB (VR_NAS_MAX_MB).")
    tid = secrets.token_hex(8)
    with _KHOA:
        _TAC_VU[tid] = {"nguoi": nguoi, "bo_phan": bo_phan, "trang_thai": "dang_chay",
                        "tong": size, "da_chep": 0, "ma": None, "loi": "",
                        "nguon": f, "ten": ten or f.stem, "duoi": duoi}
    return tid


def chay_nap(tid: str) -> None:
    """Thân tác vụ — SYNC, BackgroundTasks tự đẩy threadpool. Chép ra file .tam
    trong kho rồi (them_video → os.replace) để chép hỏng không để lại bản ghi."""
    tv = _TAC_VU.get(tid)
    if tv is None:
        return
    tam = kho_video.kho_dir() / f"nap-{tid}.tam"
    try:
        tam.parent.mkdir(parents=True, exist_ok=True)
        with open(tv["nguon"], "rb") as doc, open(tam, "wb") as ghi:
            while True:
                khuc = doc.read(4 * 1024 * 1024)
                if not khuc:
                    break
                ghi.write(khuc)
                tv["da_chep"] += len(khuc)
        ban_ghi = kho_video.them_video(tv["ten"], tv["duoi"], tv["nguoi"],
                                       tv["bo_phan"], tv["tong"])
        ban_ghi["duong_tuyet_doi"].parent.mkdir(parents=True, exist_ok=True)
        os.replace(tam, ban_ghi["duong_tuyet_doi"])
        # người up để file .srt CÙNG TÊN cạnh video trên NAS → tự nhặt theo
        # (user chốt 18/08: phụ đề do người up video lo). Best-effort — phụ đề
        # hỏng không được giết tác vụ nạp video.
        try:
            srt = tv["nguon"].with_suffix(".srt")
            if srt.is_file():
                chu = kho_video.doc_phu_de_bytes(srt.read_bytes())
                if "-->" in chu:
                    kho_video.ghi_phu_de({"duong": ban_ghi["duong"]}, chu, ".srt")
        except OSError:
            pass
        tv["ma"] = ban_ghi["ma"]
        tv["trang_thai"] = "xong"
    except Exception as e:              # lỗi nền chỉ ghi vào tác vụ, không nổ tiến trình
        tv["trang_thai"] = "loi"
        tv["loi"] = str(e)
        try:
            tam.unlink()
        except OSError:
            pass


def trang_thai(tid: str, nguoi: str) -> dict | None:
    """RBAC như lệ tác vụ nền B2: chỉ CHỦ tác vụ xem, khác người → None (404 lặng lẽ)."""
    tv = _TAC_VU.get(tid)
    if tv is None or tv["nguoi"] != nguoi:
        return None
    pt = int(tv["da_chep"] * 100 / tv["tong"]) if tv["tong"] else 100
    return {"trang_thai": tv["trang_thai"], "phan_tram": pt,
            "ma": tv["ma"], "loi": tv["loi"]}
