# -*- coding: utf-8 -*-
"""Dò file gốc trên NAS cho bản ghi ĐỜI CŨ (nguon='kho') rồi đổi sang LIÊN KẾT.

Bối cảnh: trước 20/08/2026 app CHÉP video vào kho, nên mỗi bản dựng có hai bản —
một trên NAS, một trong app. Script này ghép lại rồi cho phép dọn bản sao.

Ba bước rời, xem kết quả bước trước rồi mới chạy bước sau:

    python scripts/lien_ket_lai_nas.py                 # 1. CHỈ LIỆT KÊ, không đụng gì
    python scripts/lien_ket_lai_nas.py --chay          # 2. đổi sang liên kết NAS
    python scripts/lien_ket_lai_nas.py --xoa-ban-sao   # 3. xóa bản sao trong kho app

Luật an toàn:
- Ứng viên chỉ được nhận khi TRÙNG DUNG LƯỢNG TUYỆT ĐỐI **và** trùng 1MB đầu +
  1MB cuối (không nhận theo tên — tên trong kho đã bị đổi khuôn).
- Nhiều ứng viên hoặc không ứng viên nào → BỎ QUA, giữ nguyên bản ghi kho.
- Bước --chay ghi nhật ký JSON (mã, đường kho cũ, đường NAS mới); bước --xoa-ban-sao
  đọc nhật ký MỚI NHẤT và kiểm lại từng điều kiện trước khi xóa một byte nào.
- Phụ đề .srt cạnh bản sao cũ được CHUYỂN vào kho phụ đề của app trước khi xóa.
- Không bao giờ ghi/xóa bất cứ thứ gì trong NAS.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))
sys.path.insert(0, str(_APP.parents[1]))

from src import kho_video     # noqa: E402

MIENG = 1024 * 1024


def _nhat_ky_dir() -> Path:
    return Path(os.environ.get("VR_DB_PATH", str(
        kho_video.ROOT / "data" / "video-review" / "db" / "video_review.db"))).parent


def _van_tay(p: Path, size: int) -> str:
    """Băm 1MB đầu + 1MB cuối — đủ chắc để nói 'cùng một file' mà không đọc 5GB."""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read(MIENG))
        if size > MIENG:
            f.seek(max(0, size - MIENG))
            h.update(f.read(MIENG))
    return h.hexdigest()


def _quet_nas(goc: Path) -> dict:
    theo_co = {}
    for thu_muc, _, files in os.walk(goc):
        for ten in files:
            if ("." + ten.rsplit(".", 1)[-1]).lower() not in kho_video.DUOI_CHO_PHEP:
                continue
            p = Path(thu_muc) / ten
            try:
                theo_co.setdefault(p.stat().st_size, []).append(p)
            except OSError:
                pass
    return theo_co


def doi_chieu() -> list:
    kho_video.khoi_tao()          # đảm bảo migration 002 (cột nguon/nas_mtime) đã áp
    goc = kho_video.nas_dir()
    if goc is None:
        raise SystemExit("VR_NAS_DIR chưa khai (hoặc trỏ vào thư mục không tồn tại).")
    goc_rs = goc.resolve()
    print(f"Quét NAS: {goc_rs} …")
    theo_co = _quet_nas(goc_rs)
    print(f"  {sum(len(v) for v in theo_co.values())} file video trên NAS")

    conn = kho_video.ket_noi()
    try:
        hang = [dict(h) for h in conn.execute(
            "SELECT * FROM video WHERE nguon='kho' ORDER BY id").fetchall()]
    finally:
        conn.close()

    ket = []
    for v in hang:
        ban_sao = kho_video.kho_dir() / v["duong"]
        if not ban_sao.is_file():
            ket.append({"ma": v["ma"], "ten": v["ten"], "trang_thai": "mất bản sao",
                        "chi_tiet": str(ban_sao)})
            continue
        co = ban_sao.stat().st_size
        ung_vien = theo_co.get(co, [])
        if not ung_vien:
            ket.append({"ma": v["ma"], "ten": v["ten"], "trang_thai": "không thấy trên NAS",
                        "chi_tiet": f"{co/1048576:.1f}MB"})
            continue
        vt = _van_tay(ban_sao, co)
        khop = [p for p in ung_vien if _van_tay(p, co) == vt]
        if len(khop) == 1:
            ket.append({"ma": v["ma"], "ten": v["ten"], "trang_thai": "khớp",
                        "kho_cu": str(ban_sao), "co": co,
                        "nas_moi": khop[0].relative_to(goc_rs).as_posix(),
                        "mtime": khop[0].stat().st_mtime})
        else:
            ket.append({"ma": v["ma"], "ten": v["ten"],
                        "trang_thai": "khớp NHIỀU bản — bỏ qua" if khop else "không khớp nội dung",
                        "chi_tiet": ", ".join(p.relative_to(goc_rs).as_posix() for p in khop)})
    return ket


def _in_bang(ket: list) -> None:
    for r in ket:
        dong = f"  {r['ma']} · {r['ten'][:38]:38} · {r['trang_thai']}"
        if r["trang_thai"] == "khớp":
            dong += f"  →  {r['nas_moi']}  ({r['co']/1048576:.1f}MB)"
        elif r.get("chi_tiet"):
            dong += f"  ({r['chi_tiet']})"
        print(dong)
    so_khop = sum(1 for r in ket if r["trang_thai"] == "khớp")
    print(f"\n  Tổng {len(ket)} bản ghi kho · khớp {so_khop}")


def _cuu_phu_de(ban_sao: Path, ma: str) -> None:
    """Sidecar '<file>.srt' cạnh bản sao cũ → kho phụ đề app (kho/phu-de/<ma>.srt)."""
    for d in kho_video.DUOI_PHU_DE:
        cu = ban_sao.with_name(ban_sao.name + d)
        if not cu.is_file():
            continue
        dich = kho_video.kho_dir() / "phu-de" / f"{ma}{d}"
        dich.parent.mkdir(parents=True, exist_ok=True)
        if dich.exists():
            cu.unlink()
        else:
            os.replace(cu, dich)
            print(f"  {ma}: giữ phụ đề → {dich}")


def chay(ket: list) -> Path:
    khop = [r for r in ket if r["trang_thai"] == "khớp"]
    if not khop:
        raise SystemExit("Không có bản ghi nào khớp — không đổi gì.")
    # Phụ đề đã gắn trong app nằm CẠNH bản sao cũ — đổi đường sang NAS là nó mồ côi,
    # nên chuyển vào kho phụ đề TRƯỚC khi động vào sổ (dính thật lượt đầu: VR-0007).
    for r in khop:
        _cuu_phu_de(Path(r["kho_cu"]), r["ma"])
    conn = kho_video.ket_noi()
    try:
        for r in khop:
            conn.execute("UPDATE video SET nguon='nas', duong=?, ten_file=?, nas_mtime=?,"
                         " kich_thuoc=? WHERE ma=?",
                         (r["nas_moi"], r["nas_moi"].rsplit("/", 1)[-1], r["mtime"],
                          r["co"], r["ma"]))
        conn.commit()
    finally:
        conn.close()
    thu_muc = _nhat_ky_dir()
    thu_muc.mkdir(parents=True, exist_ok=True)
    nk = thu_muc / f"lien-ket-lai-{datetime.now():%Y%m%d-%H%M%S}.json"
    nk.write_text(json.dumps(khop, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã đổi {len(khop)} bản ghi sang liên kết NAS.")
    print(f"Nhật ký (cần cho bước xóa bản sao): {nk}")
    return nk


def xoa_ban_sao() -> None:
    cac_nk = sorted(_nhat_ky_dir().glob("lien-ket-lai-*.json"))
    if not cac_nk:
        raise SystemExit("Chưa có nhật ký liên kết — chạy --chay trước.")
    ds = json.loads(cac_nk[-1].read_text(encoding="utf-8"))
    print(f"Đọc nhật ký {cac_nk[-1].name} ({len(ds)} bản ghi)")
    thu = 0
    for r in ds:
        v = kho_video.lay_video(r["ma"])
        ban_sao = Path(r["kho_cu"])
        if v is None or v["nguon"] != "nas" or v["duong"] != r["nas_moi"]:
            print(f"  {r['ma']}: sổ không còn trỏ đúng file NAS — BỎ QUA")
            continue
        nas = kho_video.duong_video(v)
        if nas is None or not nas.is_file() or nas.stat().st_size != r["co"]:
            print(f"  {r['ma']}: file NAS không còn / khác dung lượng — BỎ QUA")
            continue
        if not ban_sao.is_file():
            print(f"  {r['ma']}: bản sao đã dọn trước đó")
            continue
        _cuu_phu_de(ban_sao, r["ma"])   # lưới hai: bản ghi liên kết từ lượt cũ
        co = ban_sao.stat().st_size
        ung_vien = theo_co.get(co, [])
        if not ung_vien:
            ket.append({"ma": v["ma"], "ten": v["ten"], "trang_thai": "không thấy trên NAS",
                        "chi_tiet": f"{co/1048576:.1f}MB"})
            continue
        vt = _van_tay(ban_sao, co)
        khop = [p for p in ung_vien if _van_tay(p, co) == vt]
        if len(khop) == 1:
            ket.append({"ma": v["ma"], "ten": v["ten"], "trang_thai": "khớp",
                        "kho_cu": str(ban_sao), "co": co,
                        "nas_moi": khop[0].relative_to(goc_rs).as_posix(),
                        "mtime": khop[0].stat().st_mtime})
        else:
            ket.append({"ma": v["ma"], "ten": v["ten"],
                        "trang_thai": "khớp NHIỀU bản — bỏ qua" if khop else "không khớp nội dung",
                        "chi_tiet": ", ".join(p.relative_to(goc_rs).as_posix() for p in khop)})
    return ket


def _in_bang(ket: list) -> None:
    for r in ket:
        dong = f"  {r['ma']} · {r['ten'][:38]:38} · {r['trang_thai']}"
        if r["trang_thai"] == "khớp":
            dong += f"  →  {r['nas_moi']}  ({r['co']/1048576:.1f}MB)"
        elif r.get("chi_tiet"):
            dong += f"  ({r['chi_tiet']})"
        print(dong)
    so_khop = sum(1 for r in ket if r["trang_thai"] == "khớp")
    print(f"\n  Tổng {len(ket)} bản ghi kho · khớp {so_khop}")


def _cuu_phu_de(ban_sao: Path, ma: str) -> None:
    """Sidecar '<file>.srt' cạnh bản sao cũ → kho phụ đề app (kho/phu-de/<ma>.srt)."""
    for d in kho_video.DUOI_PHU_DE:
        cu = ban_sao.with_name(ban_sao.name + d)
        if not cu.is_file():
            continue
        dich = kho_video.kho_dir() / "phu-de" / f"{ma}{d}"
        dich.parent.mkdir(parents=True, exist_ok=True)
        if dich.exists():
            cu.unlink()
        else:
            os.replace(cu, dich)
            print(f"  {ma}: giữ phụ đề → {dich}")


def chay(ket: list) -> Path:
    khop = [r for r in ket if r["trang_thai"] == "khớp"]
    if not khop:
        raise SystemExit("Không có bản ghi nào khớp — không đổi gì.")
    # Phụ đề đã gắn trong app nằm CẠNH bản sao cũ — đổi đường sang NAS là nó mồ côi,
    # nên chuyển vào kho phụ đề TRƯỚC khi động vào sổ (dính thật lượt đầu: VR-0007).
    for r in khop:
        _cuu_phu_de(Path(r["kho_cu"]), r["ma"])
    conn = kho_video.ket_noi()
    try:
        for r in khop:
            conn.execute("UPDATE video SET nguon='nas', duong=?, ten_file=?, nas_mtime=?,"
                         " kich_thuoc=? WHERE ma=?",
                         (r["nas_moi"], r["nas_moi"].rsplit("/", 1)[-1], r["mtime"],
                          r["co"], r["ma"]))
        conn.commit()
    finally:
        conn.close()
    thu_muc = _nhat_ky_dir()
    thu_muc.mkdir(parents=True, exist_ok=True)
    nk = thu_muc / f"lien-ket-lai-{datetime.now():%Y%m%d-%H%M%S}.json"
    nk.write_text(json.dumps(khop, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã đổi {len(khop)} bản ghi sang liên kết NAS.")
    print(f"Nhật ký (cần cho bước xóa bản sao): {nk}")
    return nk


def xoa_ban_sao() -> None:
    cac_nk = sorted(_nhat_ky_dir().glob("lien-ket-lai-*.json"))
    if not cac_nk:
        raise SystemExit("Chưa có nhật ký liên kết — chạy --chay trước.")
    ds = json.loads(cac_nk[-1].read_text(encoding="utf-8"))
    print(f"Đọc nhật ký {cac_nk[-1].name} ({len(ds)} bản ghi)")
    thu = 0
    for r in ds:
        v = kho_video.lay_video(r["ma"])
        ban_sao = Path(r["kho_cu"])
        if v is None or v["nguon"] != "nas" or v["duong"] != r["nas_moi"]:
            print(f"  {r['ma']}: sổ không còn trỏ đúng file NAS — BỎ QUA")
            continue
        nas = kho_video.duong_video(v)
        if nas is None or not nas.is_file() or nas.stat().st_size != r["co"]:
            print(f"  {r['ma']}: file NAS không còn / khác dung lượng — BỎ QUA")
            continue
        if not ban_sao.is_file():
            print(f"  {r['ma']}: bản sao đã dọn trước đó")
            continue
        # phụ đề nằm cạnh bản sao cũ: chuyển vào kho phụ đề app trước khi xóa video
        for d in kho_video.DUOI_PHU_DE:
            cu = ban_sao.with_name(ban_sao.name + d)
            if cu.is_file():
                dich = kho_video.kho_dir() / "phu-de" / f"{r['ma']}{d}"
                dich.parent.mkdir(parents=True, exist_ok=True)
                if dich.exists():
                    cu.unlink()
                else:
                    os.replace(cu, dich)
                    print(f"  {r['ma']}: giữ phụ đề → {dich}")
        co = ban_sao.stat().st_size
        ban_sao.unlink()
        thu += co
        print(f"  {r['ma']}: đã xóa bản sao ({co/1073741824:.2f}GB)")
    print(f"\nThu hồi {thu/1073741824:.2f}GB. File gốc trên NAS không bị đụng.")


if __name__ == "__main__":
    if "--xoa-ban-sao" in sys.argv:
        xoa_ban_sao()
    else:
        kq = doi_chieu()
        _in_bang(kq)
        if "--chay" in sys.argv:
            chay(kq)
        else:
            print("\n(chỉ liệt kê — thêm --chay để đổi sang liên kết)")
