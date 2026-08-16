"""S5 — Board GUI web-local. Python http.server (127.0.0.1) + trang board tĩnh + auto-compose.

Chạy:  python3 -m oe.s5_server --run <tên> [--port 8730]

CHỈ bind 127.0.0.1 (không lộ LAN). Không asset CDN — trang tự chứa, offline.
- Tick/kéo cluster → gán slot → tự ghi outline.txt + outline_evidence.md + picks.json.
- Màn nhập video: dán URL → /api/ingest chạy cả pipeline (S1→S4b) → board hiện cluster.
  Key YouTube/transcript đọc từ videos.txt gốc + .env (user chỉ dán URL).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import common
from .compose import compose_outline, compose_evidence
from .llm import LLM
from .s4c_consolidate import merge_clusters

HTML = Path(__file__).parent / "board.html"
# 03/08/2026: máy Windows công ty — venv là .venv\Scripts\python.exe, không phải
# .venv/bin/python (đường Linux của VPS cũ, WinError 2 chết S4/S4b). Chọn theo
# platform + lưới cuối: không thấy thì dùng chính python đang chạy server (tác vụ
# nền vốn chạy bằng python venv).
_VENV_PY = common.ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32"
                                    else "bin/python")
VENV_PY = _VENV_PY if _VENV_PY.exists() else Path(sys.executable)

# Pipeline THEO RUN (2026-07-22): trước đây 1 dict global → 2 người ingest đè trạng thái
# nhau. Giờ mỗi run một trạng thái, tối đa MAX_PIPE run chạy song song.
PIPELINES: dict[str, dict] = {}
PIPE_LOCK = threading.Lock()
# ponytail: 2 khoá toàn cục thay vì hàng đợi/worker-pool — YT_LOCK cho S1/S1b/S1c
# (1 luồng gọi YouTube một lúc → không nhân rủi ro bot-check IP), EMBED_LOCK cho
# S4/S4b (fastembed ~500MB RAM, chỉ cho 1 suất). Nâng cấp: per-API-key nếu cần.
YT_LOCK = threading.Lock()
EMBED_LOCK = threading.Lock()
# 1 vCPU → 1 pipeline (VPS hiện tại); sau nâng cấp 2 vCPU chỉ cần restart là thành 2.
MAX_PIPE = max(1, min(2, os.cpu_count() or 1))


def _blank(run_name: str | None = None) -> dict:
    return {"running": False, "step": "", "step_i": 0, "step_total": 0,
            "log": [], "done": False, "error": None, "run": run_name, "completed": []}


def status_of(run_name: str) -> dict:
    """Trạng thái pipeline của MỘT run: đang chạy trong process này, hoặc đọc lại
    .pipeline.json (process cũ đã chết → running luôn False để GUI hiện nút Tiếp tục)."""
    with PIPE_LOCK:
        st = PIPELINES.get(run_name)
    if st:
        return st
    prev = _load_status(run_name)
    if prev:
        prev["running"] = False
        return prev
    return _blank(run_name)


def start_pipeline(run_name: str, urls_text: str = "", *, resume: bool = False):
    """Khởi động pipeline cho run trong thread nền. Trả (ok, lỗi-nếu-có).

    Chặn: cùng run đang chạy (double-click), hoặc đã đủ MAX_PIPE run song song.
    """
    with PIPE_LOCK:
        running = [r for r, s in PIPELINES.items() if s.get("running")]
        if run_name in running:
            return False, "run này đang chạy — chờ xong hoặc theo dõi tiến độ"
        if len(running) >= MAX_PIPE:
            return False, (f"đang có {len(running)} pipeline chạy (tối đa {MAX_PIPE}) — "
                           f"chờ run '{running[0]}' xong rồi bấm lại")
        st = _blank(run_name)
        st["running"] = True
        PIPELINES[run_name] = st
    threading.Thread(target=_run_pipeline, args=(run_name, urls_text),
                     kwargs={"resume": resume}, daemon=True).start()
    return True, None


def list_runs() -> list[str]:
    """Các run đã có cluster (mở được board), mới nhất trước — cho ô đổi run trên board."""
    if not common.RUNS.exists():
        return []
    ds = [d for d in common.RUNS.iterdir() if (d / "clusters.json").exists()]
    ds.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return [d.name for d in ds]


def _status_file(run_name: str) -> Path:
    return common.run_dir(run_name) / ".pipeline.json"


def _persist(run_name: str, st: dict) -> None:
    try:
        common.write_json(_status_file(run_name), st)
    except Exception:                                   # noqa: BLE001 — persist là best-effort
        pass


def _load_status(run_name: str) -> dict | None:
    f = _status_file(run_name)
    return common.read_json(f) if f.exists() else None


def _ensure_angle(rd: Path) -> None:
    """Backfill/đồng bộ `angle` + `role` cho cluster từ beats (chạy khi mở board, idempotent).

    - angle = summary của beat peak mạnh nhất (góc gốc tại điểm tua-lại nhiều nhất).
    - role = vùng content (hook/body/ending) tính từ beat type + chốt vị trí; recompute mỗi lần
      để sửa run cũ bị dồn hết về 'chapters' khi pos=None (bug 2026-07-14). Chỉ ghi khi có đổi.
    """
    from .s4_cluster import _beat_role
    from collections import Counter
    cp, bp = rd / "clusters.json", rd / "beats.json"
    if not (cp.exists() and bp.exists()):
        return
    clusters = common.read_json(cp)
    if not clusters:
        return
    bmap = {}
    for vid, bs in common.read_json(bp).items():
        for i, b in enumerate(bs):
            bmap[f"{vid}#{i}"] = b
    changed = False
    for c in clusters:
        ms = [bmap[g] for g in c.get("member_gids", []) if g in bmap]
        if "angle" not in c:
            pb = max(ms, key=lambda m: m.get("peak_z_w", 0.0)) if ms else {}
            c["angle"] = pb.get("summary", "") if pb.get("peak_z_w", 0.0) > 0 else ""
            changed = True
        if ms:                                          # tính lại role từ beat type (+ pos nếu biết)
            votes = Counter(_beat_role(m.get("type")) for m in ms)
            role = max(("chapters", "hook", "ending"), key=lambda r: (votes.get(r, 0), r == "chapters"))
            pos = c.get("pos")
            if role == "hook" and pos is not None and pos > 0.30:
                role = "chapters"
            elif role == "ending" and pos is not None and pos < 0.55:
                role = "chapters"
            if c.get("role") != role:
                c["role"] = role
                changed = True
    if changed:
        common.write_json(cp, clusters)


def _board_data(rd: Path) -> dict:
    _ensure_angle(rd)
    def _load(name, default):
        p = rd / name
        return common.read_json(p) if p.exists() else default
    return {
        "clusters": _load("clusters.json", []),
        "videos": _load("videos.json", {}),
        "picks": _load("picks.json", {}),
        "gaps": _load("gaps.json", []),
        "next_ideas": _load("next_ideas.json", []),
        "meta": _load("run_meta.json", {}),   # V3: AVD kênh nhập ở màn tạo run
        "has_data": (rd / "clusters.json").exists(),
        "run": rd.name,                 # board hiển thị + gửi lại trong mọi API call
        "runs": list_runs(),            # ô đổi run (per-user board 2026-07-22)
    }


def _save(rd: Path, picks: dict) -> dict:
    clusters = common.read_json(rd / "clusters.json")
    meta_p = rd / "run_meta.json"
    meta = common.read_json(meta_p) if meta_p.exists() else {}
    outline = compose_outline(picks, clusters)
    evidence = compose_evidence(picks, clusters, meta)
    (rd / "outline.txt").write_text(outline, encoding="utf-8")
    (rd / "outline_evidence.md").write_text(evidence, encoding="utf-8")
    common.write_json(rd / "picks.json", picks)
    return {"outline": outline, "evidence": evidence}


def _merge(rd: Path, names: list[str]) -> dict:
    """Gộp các cluster user chọn thành 1 (LLM, on-demand).

    Cụm gộp KHÔNG tự vào outline — đưa lên ĐẦU list để user đọc rồi tự quyết pick (giữ luật A3:
    tool trình bày, user chọn). Cụm gộp là cluster bình thường → gộp tiếp với cụm khác được.
    """
    clusters = common.read_json(rd / "clusters.json")
    chosen_set = set(names)
    chosen = [c for c in clusters if c["name"] in chosen_set]
    if len(chosen) < 2:
        return {"error": "cần ≥2 cluster để gộp"}
    merged = merge_clusters(LLM(common.ROOT / ".env"), chosen)
    rest = [c for c in clusters if c["name"] not in chosen_set]
    common.write_json(rd / "clusters.json", [merged] + rest)   # cụm gộp lên đầu
    # cụm đã gộp biến mất → gỡ khỏi outline (KHÔNG tự thêm cụm gộp; user tự pick sau khi đọc)
    pp = rd / "picks.json"
    if pp.exists():
        p = common.read_json(pp)
        if p.get("hook") in chosen_set:
            p["hook"] = None
        if p.get("ending") in chosen_set:
            p["ending"] = None
        p["chapters"] = [n for n in p.get("chapters", []) if n not in chosen_set]
        common.write_json(pp, p)
    return {"ok": True, "merged_name": merged["name"], "merged_from": merged["merged_from"]}


def _pipeline_steps(videos_txt: Path, run_name: str):
    """(python, module, args, nhãn, khoá) cho từng stage. S4/S4b cần venv (fastembed).

    Khoá: S1/S1b/S1c giữ YT_LOCK (chỉ 1 run gọi YouTube một lúc — chạy song song
    yt-dlp từ cùng IP là cách nhanh nhất ăn bot-check); S4/S4b giữ EMBED_LOCK
    (fastembed ngốn RAM, chỉ 1 suất). Các bước còn lại chạy tự do.
    """
    sp = sys.executable
    vp = str(VENV_PY)
    return [
        (sp, "oe.s1_ingest", [str(videos_txt), "--run", run_name], "S1 metadata + heatmap", YT_LOCK),
        (sp, "oe.s1b_transcripts", ["--run", run_name], "S1b transcript", YT_LOCK),
        (sp, "oe.s1c_comments", [str(videos_txt), "--run", run_name], "S1c comment", YT_LOCK),
        (sp, "oe.s2_peaks", ["--run", run_name], "S2 đỉnh", None),
        (sp, "oe.s3_label_peaks", ["--run", run_name], "S3a phân loại đỉnh", None),
        (sp, "oe.s3_beats", ["--run", run_name], "S3b chia beat", None),
        (vp, "oe.s4_cluster", ["--run", run_name], "S4 gom cụm", EMBED_LOCK),
        (vp, "oe.s4b_signals", ["--run", run_name], "S4b tín hiệu comment", EMBED_LOCK),
    ]


def _run_pipeline(run_name: str, urls_text: str, *, resume: bool = False):
    """Chạy cả pipeline trong thread; cập nhật PIPELINES[run] + persist .pipeline.json để resume.

    resume=True: giữ danh sách stage đã hoàn thành từ .pipeline.json, chỉ chạy stage còn thiếu
    (mỗi stage vốn idempotent nên chạy lại an toàn; completed chỉ để bỏ qua nhanh sau khi bị dừng).
    """
    with PIPE_LOCK:
        st = PIPELINES.setdefault(run_name, _blank(run_name))
    try:
        prev = _load_status(run_name) if resume else None
        completed = list(prev.get("completed", [])) if prev else []
        rd = common.run_dir(run_name, create=True)
        run_vtxt = rd / "videos.txt"
        if urls_text.strip():                           # lần đầu: ghi videos.txt từ URL user dán
            _ids, keys = common.parse_videos_txt(common.ROOT / "videos.txt") \
                if (common.ROOT / "videos.txt").exists() else ([], [])
            # V3: khoa YouTube tu KET OUTLIERY (viec 'lay_comment', nhieu khoa
            # xoay vong); V2: doc .env nhu cu (YOUTUBE_API_KEY tab Cai dat).
            from contentultimate import khoa_v3
            if khoa_v3.bat():
                for k in khoa_v3.khoa_theo_viec("lay_comment"):
                    if k not in keys:
                        keys.append(k)
            else:
                envf = common.ROOT / ".env"
                if envf.exists():
                    for eline in envf.read_text(encoding="utf-8").splitlines():
                        if eline.strip().startswith("YOUTUBE_API_KEY="):
                            k = eline.split("=", 1)[1].strip()
                            if k and k not in keys:
                                keys.append(k)
            lines = ["# auto từ màn nhập video"] + keys + [""] + \
                    [u.strip() for u in urls_text.splitlines() if u.strip()]
            run_vtxt.write_text("\n".join(lines) + "\n", encoding="utf-8")

        steps = _pipeline_steps(run_vtxt, run_name)
        st.update(running=True, done=False, error=None, run=run_name,
                  step_total=len(steps), completed=completed,
                  log=(prev.get("log", []) if resume and prev else []))
        if resume:
            st["log"].append(f"↻ Tiếp tục — đã xong {len(completed)}/{len(steps)} bước.")

        for i, (py, mod, args, label, lk) in enumerate(steps, 1):
            st.update(step=label, step_i=i)
            if label in completed:                      # key theo nhãn (robust nếu module trùng)
                st["log"].append(f"✓ {label} (đã xong, bỏ qua)")
                _persist(run_name, st)
                continue
            if lk and not lk.acquire(blocking=False):   # báo user vì sao đứng yên rồi mới chờ
                st["log"].append(f"⏳ {label}: chờ lượt — run khác đang "
                                 f"{'tải từ YouTube' if lk is YT_LOCK else 'chạy embedding'}…")
                _persist(run_name, st)
                lk.acquire()
            try:
                st["log"].append(f"▶ [{i}/{len(steps)}] {label}…")
                _persist(run_name, st)                  # ghi TRƯỚC khi chạy → biết đang dở bước nào
                r = subprocess.run([py, "-m", mod, *args], cwd=common.ROOT,
                                   capture_output=True, text=True)
            finally:
                if lk:
                    lk.release()
            if r.returncode != 0:
                err = (r.stderr or "").strip().splitlines()[-1:] or ["lỗi"]
                raise RuntimeError(f"{label}: {err[0][:200]}")
            tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
            st["log"].append(f"  {tail[0][:120]}")
            completed.append(label)
            st["completed"] = completed
            _persist(run_name, st)                      # ghi SAU mỗi bước → resume chính xác
        st.update(running=False, done=True, step="xong", step_i=len(steps))
        st["log"].append("✓ Pipeline xong — board sẵn sàng.")
        _persist(run_name, st)
    except Exception as e:                              # noqa: BLE001
        st.update(running=False, done=False, error=str(e))
        st["log"].append(f"✗ {e} — bấm 'Tiếp tục' để chạy lại từ bước dở.")
        _persist(run_name, st)


def make_handler(rd_holder: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            # KHÔNG cache API: /api/status phải luôn tươi, nếu không poll đọc bản cũ → treo.
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

        def do_GET(self):
            # board.html gọi /oe/api/* (đường của server hợp nhất) — alias về /api/*
            path = self.path.split("?", 1)[0].replace("/oe/api/", "/api/", 1)
            if path in ("/", "/index.html"):
                self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/board":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                rn = (q.get("run") or [""])[0].strip()
                if rn:                                   # đổi run từ ô chọn trên board
                    rd_holder["rd"] = common.run_dir(rn)
                self._send(200, json.dumps(_board_data(rd_holder["rd"]), ensure_ascii=False))
            elif path == "/api/status":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                rn = (q.get("run") or [""])[0].strip() or rd_holder["rd"].name
                self._send(200, json.dumps(status_of(rn), ensure_ascii=False))
            else:
                self._send(404, "{}")

        def do_POST(self):
            path = self.path.split("?", 1)[0].replace("/oe/api/", "/api/", 1)
            if path == "/api/save":
                b = self._body()
                rn = str(b.pop("run", "") or "").strip()
                if rn:
                    rd_holder["rd"] = common.run_dir(rn)
                result = _save(rd_holder["rd"], b)
                self._send(200, json.dumps(result, ensure_ascii=False))
            elif path == "/api/merge":
                try:
                    b = self._body()
                    rn = str(b.get("run") or "").strip()
                    if rn:
                        rd_holder["rd"] = common.run_dir(rn)
                    result = _merge(rd_holder["rd"], b.get("names", []))
                except Exception as e:                   # noqa: BLE001 — trả lỗi cho GUI hiện
                    result = {"error": str(e)[:200]}
                self._send(200, json.dumps(result, ensure_ascii=False))
            elif path in ("/api/ingest", "/api/resume"):
                b = self._body()
                run_name = (b.get("run") or "").strip() or "video-outlier"
                rd_holder["rd"] = common.run_dir(run_name, create=True)
                ok, err = start_pipeline(run_name, b.get("videos", ""),
                                         resume=path.endswith("resume"))
                if not ok:
                    self._send(409, json.dumps({"error": err}, ensure_ascii=False))
                    return
                self._send(200, json.dumps(
                    {"started": True, "run": rd_holder["rd"].name}, ensure_ascii=False))
            else:
                self._send(404, "{}")

    return Handler


def run(run_name: str, port: int) -> None:
    rd_holder = {"rd": common.run_dir(run_name, create=True)}
    # run dở dang (server bị dừng giữa chừng)? — status_of đọc lại .pipeline.json khi
    # board hỏi, không cần nạp global nữa; ở đây chỉ báo cho người mở terminal biết.
    prev = _load_status(run_name)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(rd_holder))
    url = f"http://127.0.0.1:{port}/"
    has = (rd_holder["rd"] / "clusters.json").exists()
    print(f"Board GUI: {url}  (Ctrl+C để dừng)", flush=True)
    print(f"Run: {run_name} · {rd_holder['rd']}" + ("" if has else "  (chưa có data — dùng màn nhập video)"), flush=True)
    if prev and not prev.get("done") and prev.get("completed"):
        print(f"  ↻ Có run dở dang ({len(prev['completed'])} bước xong) — mở board rồi bấm 'Tiếp tục'.", flush=True)
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng server.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="S5 board GUI web-local")
    ap.add_argument("--run", default="bigbang")
    ap.add_argument("--port", type=int, default=8730)
    a = ap.parse_args(argv)
    run(a.run, a.port)


if __name__ == "__main__":
    main()
