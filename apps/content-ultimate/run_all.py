"""Chạy cả pipeline S1→S4 rồi mở board GUI (S5). Tự chọn python hệ thống / venv cho từng stage.

    python3 run_all.py <videos.txt> [--run <tên>] [--skip-transcripts]

S1/S1b/S2/S3 dùng python hiện tại; S4 (embedding fastembed) dùng .venv/bin/python. Mỗi stage
idempotent nên chạy lại rẻ. Xong thì mở board ở http://127.0.0.1:8730.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PY = ROOT / ".venv" / "bin" / "python"


def _run(py: str, mod: str, *args: str) -> None:
    print(f"\n===== {mod} =====", flush=True)
    r = subprocess.run([py, "-m", mod, *args], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"{mod} lỗi (exit {r.returncode})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("videos_txt")
    ap.add_argument("--run", default=None)
    ap.add_argument("--skip-transcripts", action="store_true", help="bỏ S1b (tiết kiệm credit)")
    ap.add_argument("--port", type=int, default=8730)
    a = ap.parse_args()
    run = a.run or Path(a.videos_txt).stem
    if not VENV_PY.exists():
        sys.exit(f"Chưa có venv: tạo bằng  python3 -m venv .venv && .venv/bin/pip install -e \".[dev,llm,embed]\"")

    sys_py = sys.executable
    _run(sys_py, "oe.s1_ingest", a.videos_txt, "--run", run)
    if not a.skip_transcripts:
        _run(sys_py, "oe.s1b_transcripts", "--run", run)
    _run(sys_py, "oe.s1c_comments", a.videos_txt, "--run", run)
    _run(sys_py, "oe.s2_peaks", "--run", run)
    _run(sys_py, "oe.s3_label_peaks", "--run", run)
    _run(sys_py, "oe.s3_beats", "--run", run)
    _run(str(VENV_PY), "oe.s4_cluster", "--run", run)     # cần fastembed
    _run(str(VENV_PY), "oe.s4b_signals", "--run", run)    # cần fastembed
    _run(sys_py, "oe.s5_server", "--run", run, "--port", str(a.port))


if __name__ == "__main__":
    main()
