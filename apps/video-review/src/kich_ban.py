# -*- coding: utf-8 -*-
"""CẦU ĐỌC KHO KỊCH BẢN của Content Ultimate (tab Writing Review).

CHỈ ĐỌC — không sửa một byte nào trong kho của app kia. Đọc:
  authors/<Ax_Ten>/script-<run>.md            văn bản kịch bản
  authors/<Ax_Ten>/script-<run>.md.progress.json   sections (Hook / Chapter n) + total_chars
  authors/<Ax_Ten>/script-<run>.outline.txt   tên chương (dòng "CHAPTER n — Tên")
  admin/history.jsonl                          ai viết, xong lúc nào

KHÔNG TIN CỜ "done": history ghi status=done kể cả khi chương hụt (đo thật
02/09: nepal-2 done nhưng Chapter 3 chỉ 19 ký tự / 12.347 trên mục tiêu 22.000).
Bản thiếu VẪN HIỆN nhưng ghi rõ thiếu gì và không đủ điều kiện duyệt — người
quyết định là leader, máy chỉ nói sự thật đo được.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# Chương coi là RỖNG dưới ngưỡng này (19 ký tự của nepal-2 là placeholder, không
# phải chương thật). Ngưỡng đo từ dữ liệu thật, không phải số đẹp.
NGUONG_CHUONG_RONG = 200
# Đủ điều kiện duyệt khi đạt tỉ lệ này so với total_chars mục tiêu.
TI_LE_DU = 0.9


def goc_cu() -> Path:
    """Gốc kho Content Ultimate. Env CU_DATA_DIR để test trỏ thư mục tạm."""
    d = os.environ.get("CU_DATA_DIR", "").strip()
    return Path(d) if d else Path("data/content-ultimate").resolve()


def _title_outline(outline: Path) -> str:
    """Dòng 'Title: <run>' của outline. Tên file KHÔNG đáng tin: bản chạy lại
    của cùng một run có thể tên script.md (đo thật 04/09 — script.md và
    script-nepal-2.md đều là run nepal-2), lấy tên từ file sẽ đẻ run ma."""
    if not outline.exists():
        return ""
    for dong in outline.read_text(encoding="utf-8", errors="replace").splitlines()[:5]:
        if dong.lower().startswith("title:"):
            return dong.split(":", 1)[1].strip()
    return ""


def _ten_chuong(outline: Path) -> dict[str, str]:
    """{'Chapter 1': 'A Country Built Like a Wall'} đọc từ outline.txt."""
    if not outline.exists():
        return {}
    ra = {}
    for dong in outline.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^CHAPTER\s+(\d+)\s*[-—–]\s*(.+?)\s*$", dong.strip())
        if m:
            ra[f"Chapter {m.group(1)}"] = m.group(2)
    return ra


def _lich_su() -> dict[str, dict]:
    """{run: {nguoi, xong_luc}} — lượt writer xong GẦN NHẤT của mỗi run."""
    f = goc_cu() / "admin" / "history.jsonl"
    if not f.exists():
        return {}
    ra: dict[str, dict] = {}
    for dong in f.read_text(encoding="utf-8", errors="replace").splitlines():
        dong = dong.strip()
        if not dong:
            continue
        try:
            d = json.loads(dong)
        except ValueError:
            continue
        if d.get("kind") != "writer" or d.get("status") != "done":
            continue
        run = d.get("title") or ""
        if not run:
            continue
        cu = ra.get(run)
        if cu is None or d.get("ts", 0) > cu["ts"]:
            ra[run] = {"ts": d.get("ts", 0), "nguoi": d.get("user", ""),
                       "script": d.get("script", "")}
    return ra


def _doc_mot(tien_do: Path, nguoi: str = "", ts: float = 0.0) -> dict:
    """Một bản kịch bản -> thẻ dữ liệu cho UI. Mọi con số ĐO TỪ FILE, không suy đoán."""
    d = json.loads(tien_do.read_text(encoding="utf-8", errors="replace"))
    sections = d.get("sections") or {}
    muc_tieu = int(d.get("total_chars") or 0)
    outline = Path(str(tien_do).replace(".md.progress.json", ".outline.txt"))
    ten_ch = _ten_chuong(outline)
    chuong = []
    for khoa, van in sections.items():
        van = van or ""
        chuong.append({"khoa": khoa, "ten": ten_ch.get(khoa, ""), "van": van,
                       "ky_tu": len(van), "rong": len(van) < NGUONG_CHUONG_RONG})
    ky_tu = sum(c["ky_tu"] for c in chuong)
    thieu_ch = [c["khoa"] for c in chuong if c["rong"]]
    du_dai = muc_tieu > 0 and ky_tu >= muc_tieu * TI_LE_DU
    ly_do = []
    if thieu_ch:
        ly_do.append(f"thiếu {len(thieu_ch)} chương")
    if not du_dai:
        ly_do.append("hụt độ dài")
    ten_tep = tien_do.name.replace(".md.progress.json", "")
    run = _title_outline(outline) or (
        ten_tep[len("script-"):] if ten_tep.startswith("script-") else ten_tep)
    return {"run": run, "tac_gia": tien_do.parent.name, "nguoi": nguoi, "ts": ts,
            "ky_tu": ky_tu, "muc_tieu": muc_tieu, "chuong": chuong,
            "so_chuong": len(chuong), "thieu_chuong": thieu_ch,
            "du_dieu_kien": not ly_do, "thieu": " · ".join(ly_do),
            "duong": str(tien_do.parent / f"{ten_tep}.md")}


def cac_ban() -> list[dict]:
    """Mọi kịch bản trong kho Content Ultimate, mới nhất trước."""
    goc = goc_cu() / "authors"
    if not goc.is_dir():
        return []
    ls = _lich_su()
    theo_run: dict[str, dict] = {}
    for thu_muc in sorted(goc.iterdir()):
        if not thu_muc.is_dir():
            continue
        for tien_do in sorted(thu_muc.glob("*.md.progress.json")):
            try:
                b = _doc_mot(tien_do)
            except (ValueError, OSError):
                continue
            h = ls.get(b["run"], {})
            b["nguoi"], b["ts"] = h.get("nguoi", ""), h.get("ts", 0.0)
            b["sua_luc"] = tien_do.stat().st_mtime
            # Một run có thể có nhiều tệp (lượt chạy lại) — giữ bản MỚI NHẤT,
            # không hiện hai dòng cho cùng một run.
            cu_ban = theo_run.get(b["run"])
            if cu_ban is None or b["sua_luc"] > cu_ban["sua_luc"]:
                theo_run[b["run"]] = b
    ra = sorted(theo_run.values(), key=lambda b: -(b["ts"] or b["sua_luc"]))
    return ra


def mot_ban(run: str) -> dict | None:
    for b in cac_ban():
        if b["run"] == run:
            return b
    return None


# ---------- note review + mốc chốt (sổ của ReviewY, kho CU vẫn chỉ đọc) ----------

def them_note(run: str, chuong: str, nguoi: str, noi_dung: str,
              la_may: bool = False, muc: str = "") -> int:
    from src import kho_video
    conn = kho_video.ket_noi()
    try:
        cur = conn.execute(
            "INSERT INTO note_kich_ban (run, chuong, nguoi, la_may, muc, noi_dung) "
            "VALUES (?,?,?,?,?,?)",
            (run, chuong, nguoi, 1 if la_may else 0, muc, noi_dung))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def cac_note(run: str, chuong: str | None = None) -> list[dict]:
    from src import kho_video
    conn = kho_video.ket_noi()
    try:
        if chuong is None:
            q = "SELECT * FROM note_kich_ban WHERE run=? ORDER BY id"
            ds = conn.execute(q, (run,)).fetchall()
        else:
            q = "SELECT * FROM note_kich_ban WHERE run=? AND chuong=? ORDER BY id"
            ds = conn.execute(q, (run, chuong)).fetchall()
        return [dict(h) for h in ds]
    finally:
        conn.close()


def dem_note(run: str) -> dict[str, int]:
    """{chương: số note} — cho con số trên tab chương."""
    ra: dict[str, int] = {}
    for n in cac_note(run):
        ra[n["chuong"]] = ra.get(n["chuong"], 0) + 1
    return ra


def chot(run: str, nguoi: str, ma_tap: str = "") -> None:
    """Leader chốt kịch bản — mốc 'được phép dựng'."""
    from src import kho_video
    conn = kho_video.ket_noi()
    try:
        conn.execute("INSERT INTO kich_ban_chot (run, ma_tap, nguoi) VALUES (?,?,?) "
                     "ON CONFLICT(run) DO UPDATE SET ma_tap=excluded.ma_tap, "
                     "nguoi=excluded.nguoi, chot_luc=datetime('now')",
                     (run, ma_tap.upper(), nguoi))
        conn.commit()
    finally:
        conn.close()


def moc_chot(run: str) -> dict | None:
    from src import kho_video
    conn = kho_video.ket_noi()
    try:
        h = conn.execute("SELECT * FROM kich_ban_chot WHERE run=?", (run,)).fetchone()
        return dict(h) if h else None
    finally:
        conn.close()


def chot_theo_tap() -> dict[str, dict]:
    """{mã tập: bản kịch bản đã chốt} — Overview dùng để hiện trạm Writing."""
    from src import kho_video
    conn = kho_video.ket_noi()
    try:
        ds = conn.execute("SELECT * FROM kich_ban_chot WHERE ma_tap != ''").fetchall()
    finally:
        conn.close()
    ra = {}
    for h in ds:
        d = dict(h)
        ra[d["ma_tap"]] = {"run": d["run"], "chot_luc": d["chot_luc"],
                           "nguoi": d["nguoi"], "ban": "v1"}
    return ra
