"""Snapshot một lần chạy pipeline thành bản có ngày — nền cho ô 🗓 xem lại báo cáo cũ.

Vấn đề gốc: pipeline ghi đè niche-data/ mỗi lần chạy → báo cáo là one-off, không có
lịch sử. Script này đóng băng BỘ ARTIFACT BÁO CÁO của lần chạy hiện tại vào
<project>/snapshots/<YYYY-MM-DD>/ + ghi sổ snapshots/index.json (chỉ-ghi-thêm,
cùng ngày chạy lại = làm tươi bản của ngày đó, không nhân bản).

KHÔNG snapshot videos.json (nặng, không cần cho dashboard/báo cáo — bản render đầy đủ
đã nằm trong Report/). Muốn tái lập số từ gốc thì chạy lại pipeline.

Usage:  python snapshot.py <project_dir>            # vd: projects/LifeIn_US
        python snapshot.py <project_dir> --list     # liệt kê snapshot đã có
Chạy độc lập được (không import orchestrator) — đúng quy ước mỗi tầng PY một script.
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Bộ artifact đủ dựng dashboard + báo cáo gộp; thiếu file nào bỏ qua file đó
# (pipeline có thể chưa chạy hết) — sổ index ghi rõ file nào có mặt.
ARTIFACTS = [
    "decision1.json", "decision2.json", "bets.json", "bets_audited.json",
    "gaps.json", "demand.json", "crackability.json", "monetization.json",
    "subniche.json", "analysis.json", "channels.json", "summary.json",
]
DATA_DIR = "niche-data"      # khớp orchestrator.py
REPORT_DIR = "Report"


def _utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def snapshot(project: Path, ngay: str | None = None) -> dict:
    """Đóng băng lần chạy hiện tại. Trả bản ghi index của snapshot vừa tạo."""
    data = project / DATA_DIR
    if not data.is_dir():
        raise SystemExit(f"Không thấy {data} — dự án chưa chạy pipeline?")
    ngay = ngay or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dich = project / "snapshots" / ngay
    dich.mkdir(parents=True, exist_ok=True)

    co_mat: list[str] = []
    for ten in ARTIFACTS:
        nguon = data / ten
        if nguon.is_file():
            shutil.copy2(nguon, dich / ten)
            co_mat.append(ten)
    bao_cao: list[str] = []
    rp = project / REPORT_DIR
    if rp.is_dir():
        for f in rp.iterdir():
            if f.is_file():
                shutil.copy2(f, dich / f.name)
                bao_cao.append(f.name)

    ban_ghi = {
        "id": ngay,
        "tao_luc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifacts": co_mat,
        "bao_cao": bao_cao,
    }
    # index.json: đọc-sửa-ghi nguyên tử; cùng id → thay bản ghi cũ (làm tươi trong ngày)
    index_path = project / "snapshots" / "index.json"
    index = []
    if index_path.is_file():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    index = [b for b in index if b.get("id") != ngay] + [ban_ghi]
    index.sort(key=lambda b: b["id"])
    tmp = index_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(index_path)
    return ban_ghi


def main() -> None:
    _utf8_stdout()
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    project = Path(sys.argv[1]).resolve()
    if "--list" in sys.argv[2:]:
        index_path = project / "snapshots" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else []
        for b in index:
            print(f"{b['id']}  artifacts={len(b['artifacts'])}  bao_cao={len(b['bao_cao'])}")
        print(f"{len(index)} snapshot")
        return
    b = snapshot(project)
    print(f"DONE — snapshot {b['id']}: {len(b['artifacts'])} artifact + {len(b['bao_cao'])} file báo cáo")


if __name__ == "__main__":
    main()
