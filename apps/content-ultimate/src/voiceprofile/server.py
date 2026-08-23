"""Web GUI local cho Author Extract — http.server (127.0.0.1) + board.html.

Cung phong cach voi Outline Extract: server nho tu chua, chay pipeline qua subprocess
trong thread, frontend poll /api/status. CHI bind 127.0.0.1 (khong lo LAN), khong CDN.

Chay:  python3 -m voiceprofile.server [--port 8770]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path

from . import library, usage

_REPO_ROOT = Path(os.environ.get("CU_DATA_DIR") or Path(__file__).resolve().parents[2])  # V3: CU_DATA_DIR tro kho du lieu ra data/content-ultimate (Luat 6); mac dinh giu canh repo nhu V2
HTML = Path(__file__).parent / "board.html"

# Job theo NGUOI (2026-07-16, thay JOB global): khoa = ten dang nhap nginx
# (X-Remote-User). Truoc day ca team chung MOT o JOB — nguoi bam sau de trang thai/log
# cua nguoi truoc (C2 tung ghi "chua per-user"). Gio moi nguoi mot o:
#   - moi user toi da 1 job chay (nguoi nay khong cho nguoi kia);
#   - /api/status tra job CUA NGUOI HOI + danh sach `others` (ai khac dang chay gi);
#   - Huy chi huy job cua chinh minh;
#   - hai job KHAC nguoi khong duoc ghi vao CUNG file (guard trong _try_start).
# Chay local khong co nginx -> khong co danh tinh -> mot khoa chung ANON_KEY, hanh vi
# nhu ban cu (mot nguoi mot may).
# Gioi han thuc te: so job song song = so tai khoan team (moi nguoi 1). Moi job la mot
# subprocess cho mang la chinh — VPS chiu nhe nhang; nut that that su la rate-limit cua
# provider LLM (da co retry/backoff trong llm.py).
JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
ANON_KEY = "?"

# Hinh dang /api/status GIU NGUYEN nhu ban 1-job cu — frontend khong phai doi gi.
_JOB_SHAPE: dict = {
    "running": False, "kind": "", "step": "", "step_i": 0, "step_total": 0,
    "log": [], "done": False, "error": None, "script_path": None,
    "user": "", "job_id": "", "started": 0.0,
}


def _job_key(user: str | None) -> str:
    return (user or "").strip() or ANON_KEY


def _try_start(user: str, kind: str, step_total: int = 0, *,
               script_path: str | None = None, out: str | None = None):
    """Dang ky job moi cho user. Tra (job, None) hoac (None, ly do 409).

    Guard TRUNG FILE giua cac user: 2 nguoi cung viet 1 script_path se pha checkpoint
    `{out}.progress.json` va ban ky bien cua nhau — chan ngay tu luc bam nut.
    """
    k = _job_key(user)
    with _LOCK:
        cur = JOBS.get(k)
        if cur and cur["running"]:
            return None, "bạn đang có job chạy — chờ xong hoặc bấm Huỷ trước"
        if script_path:
            c = next((j for j in JOBS.values()
                      if j["running"] and j.get("script_path") == script_path), None)
            if c:
                return None, (f"{c['user'] or 'người khác'} đang viết đúng file này — "
                              "đổi tên file đầu ra hoặc chờ họ xong")
        if out:
            c = next((j for j in JOBS.values()
                      if j["running"] and j.get("out") == out), None)
            if c:
                return None, (f"{c['user'] or 'người khác'} đang extract vào đúng thư mục "
                              "này — chờ họ xong")
        job = {**_JOB_SHAPE, "log": [], "running": True, "kind": kind,
               "step_total": step_total, "user": (user or "").strip(),
               "job_id": usage.new_job_id(), "started": time.time(),
               "script_path": script_path, "out": out,
               "proc": None, "cancelled": threading.Event()}
        JOBS[k] = job                      # job cu (da xong) cua user bi thay the
        return job, None


def _public(job: dict) -> dict:
    """Ban JSON-hoa duoc cua job (bo proc/cancelled)."""
    return {k: v for k, v in job.items() if k not in ("proc", "cancelled")}


def _others_locked(exclude_key: str) -> list[dict]:
    """Ai KHAC dang chay gi — hien tren board de team biet ma khong dam nhau."""
    out = []
    for k, j in JOBS.items():
        if k == exclude_key or not j["running"]:
            continue
        out.append({"user": j["user"] or ANON_KEY, "kind": j["kind"],
                    "step": j.get("step") or "",
                    "script": Path(j["script_path"]).name if j.get("script_path") else ""})
    return out


def _log(job: dict, line: str) -> None:
    with _LOCK:
        job["log"].append(line.rstrip("\n"))


# --- Luu ban ky bien (khong de len nhau) -------------------------------------------

def _outline_title(outline: str) -> str:
    """Dong 'Title:' cua outline (dinh dang chot o CLAUDE.md), fallback dong dau tien."""
    for line in (outline or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.lower().startswith("title:"):
            return s.split(":", 1)[1].strip()[:160]
        return s[:160]
    return ""


def _file_chars(path: str) -> int:
    """So ky tu THAT do tren file da viet — khong uoc luong (luat A1). 0 neu chua co."""
    try:
        return len(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return 0


def _snapshot(job: dict, script_path: str, status: str) -> str:
    """Chep script vua viet vao <thu muc>/history/<ngay-gio>-<user>.md — GIU ban cu.

    Truoc 2026-07-15 moi lan viet de thang len script.md, nen quan ly khong con gi de
    xem lai (moi tac gia chi con DUNG MOT ban). script.md van la ban moi nhat de khong
    pha thoi quen/link cu; ban ky bien nam rieng trong history/.

    Tra ve duong dan ban ky bien, "" neu khong chep duoc (khong duoc phep nem loi:
    job da chay xong, mat ban luu khong duoc lam hong ket qua).
    """
    try:
        src = Path(script_path)
        if not src.is_file():
            return ""
        who = job.get("user") or usage.ANON
        started = job.get("started") or time.time()
        stamp = datetime.fromtimestamp(started).strftime("%Y%m%d-%H%M%S")
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", who) or usage.ANON
        hdir = src.parent / "history"
        hdir.mkdir(parents=True, exist_ok=True)
        suffix = "" if status == "done" else f"-{status}"
        dest = hdir / f"{stamp}-{safe}{suffix}{src.suffix}"
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        outline_src = src.parent / (src.stem + ".outline.txt")
        if outline_src.is_file():
            (hdir / f"{stamp}-{safe}{suffix}.outline.txt").write_text(
                outline_src.read_text(encoding="utf-8"), encoding="utf-8")
        return str(dest)
    except Exception:  # noqa: BLE001 — xem docstring
        return ""


def _finish_job(job: dict, kind: str, status: str, **extra) -> None:
    """Ghi mot dong nhat ky job. Token cua job lay tu usage.jsonl theo job_id."""
    row = {"kind": kind, "status": status,
           "user": job.get("user") or usage.ANON, "job": job.get("job_id") or "",
           "secs": round(max(0.0, time.time() - (job.get("started") or time.time()))),
           **extra}
    if status == "error" and job.get("error"):
        row["error"] = str(job["error"])[:300]
    usage.record_job(row)


# --- Chay CLI subprocess, stream stdout vao JOB.log --------------------------------

def _provider_args(provider: str | None) -> list[str]:
    """Gia tri dropdown 'provider:model' (vd anthropic:claude-sonnet-5) -> cac co CLI.

    Chiu duoc ca dang cu chi co ten provider ('glm') de khoi gay CLI/client cu.
    """
    if not provider:
        return []
    name, _, model = provider.partition(":")
    args = ["--provider", name]
    if model:
        args += ["--model", model]
    return args


def cancel_job(user: str = "") -> bool:
    """Nut Huy: ket thuc job CUA CHINH NGUOI BAM (khong dung duoc job nguoi khac).
    Cac chuong da xong nam trong checkpoint → _run_writer ghep script.md tai ve duoc."""
    with _LOCK:
        job = JOBS.get(_job_key(user))
        if not job or not job["running"]:
            return False
        job["cancelled"].set()
        p = job.get("proc")
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    return True                             # co (flag) da set — runner dung o buoc ke tiep


def _run_cli(job: dict, args: list[str], label: str, abort_on_fail: bool) -> bool:
    if job["cancelled"].is_set():           # user Huy giua 2 buoc → dung truoc khi ton tien
        _log(job, f"(Buoc '{label}' bi bo — job da Huy)")
        return False
    _log(job, f"\n=== {label} ===")
    # CU_USER/CU_JOB: subprocess khong thay header nginx, nen danh tinh di bang bien
    # moi truong — voiceprofile.usage doc chung de gan token vao dung nguoi + dung job.
    ident = {"CU_USER": job.get("user") or "", "CU_JOB": job.get("job_id") or ""}
    proc = subprocess.Popen(
        [sys.executable, "-m", "voiceprofile.cli", *args],
        cwd=str(_REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env={"PYTHONUNBUFFERED": "1", **_env(), **ident},
    )
    with _LOCK:
        job["proc"] = proc
    assert proc.stdout is not None
    duoi: list[str] = []                    # vai dong cuoi — lam LY DO khi that bai
    for line in proc.stdout:
        _log(job, line)
        d = line.strip()
        if d:
            duoi.append(d)
            del duoi[:-8]
    code = proc.wait()
    with _LOCK:
        job["proc"] = None
    if job["cancelled"].is_set():
        _log(job, f"(Buoc '{label}' da bi HUY)")
        return False
    if code != 0:
        # GHI LY DO vao job (so nhat ky doc tu day). Log tien trinh song trong RAM
        # nen mat khi restart — do that 22/08: 4/8 luot writer hong co error=None,
        # khong truy duoc nguyen nhan. Giu nguyen van vai dong cuoi cua CLI.
        ly_do = f"buoc '{label}' that bai (ma {code})"
        if duoi:
            ly_do += ": " + " | ".join(duoi[-3:])
        with _LOCK:
            job["error"] = ly_do
    if code != 0 and abort_on_fail:
        _log(job, f"LOI: buoc '{label}' that bai — dung.")
        return False
    if code != 0:
        _log(job, f"(Buoc '{label}' loi — bo qua, chay tiep)")
    return True


def _env() -> dict:
    import os
    return dict(os.environ)


def _run_extractor(job: dict, corpus: str, name: str, out: str, do_rhetoric: bool,
                   do_clonekit: bool, do_dataset: bool, provider: str | None,
                   do_lab: bool = False, lab_samples: int = 5,
                   do_mo_ta: bool = False) -> None:
    status = "error"
    try:
        Path(out).mkdir(parents=True, exist_ok=True)
        profile = str(Path(out) / "profile.json")
        i = 0

        def step(n, label, args, abort):
            nonlocal i
            i += 1
            with _LOCK:
                job["step"], job["step_i"] = label, i
            return _run_cli(job, args, label, abort)

        ok = step(1, "1. build (self-profile)",
                  ["build", "--author-dir", corpus, "--author", name, "--out", profile], True)
        if ok and do_rhetoric:
            rarg = ["rhetoric", "--author-dir", corpus, "--profile", profile, "--author", name]
            rarg += _provider_args(provider)
            ok = step(2, "2. rhetoric", rarg, False)
        if ok and do_mo_ta:
            # Mo ta giong + huong dan dung (24/08). Mot luot LLM, re; hong thi bo qua —
            # ho so van dung duoc de viet, chi thieu doan mo ta.
            marg = ["mo-ta", "--profile", profile] + _provider_args(provider)
            step(3, "3. mo ta giong", marg, False)
        if ok and do_clonekit:
            ok = step(4, "4. clonekit",
                      ["clonekit", "--author-dir", corpus, "--author", name,
                       "--out", str(Path(out) / "clonekit.md")], False)
        if ok and do_dataset:
            step(5, "5. dataset",
                 ["dataset", "--author-dir", corpus, "--author", name,
                  "--out", str(Path(out) / "dataset.jsonl")], False)
        if ok and do_lab:
            # Buoc 5: do ky tu/brief RIENG cua tac gia nay (luat A5). Ton lab_samples x 4
            # luot LLM — chay CUOI de cac buoc re hon xong truoc; hong thi profile van dung
            # duoc (Writer roi ve hang so chung).
            step(6, f"6. lab do do dai ({lab_samples * 4} chuong thu)",
                 ["lab", "--profile", profile, "--samples", str(lab_samples),
                  *_provider_args(provider)], False)
        status = "done" if ok else "error"
        if ok:
            _log(job, f"\n=== XONG — ket qua trong: {out} ===")
    except Exception as e:  # noqa: BLE001
        with _LOCK:
            job["error"] = str(e)
        _log(job, f"LOI: {e}")
    finally:
        _finish_job(job, "extractor", status, author=name, out=out, provider=provider or "")
        with _LOCK:
            job["running"], job["done"] = False, True


def _run_writer(job: dict, outline: str, profile: str, author_dir: str | None,
                script_path: str, chars: int, provider: str, resume: bool,
                chi_phan: str | None = None, gop_y: str = "") -> None:
    status = "error"
    try:
        out_dir = Path(script_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        outline_file = out_dir / (Path(script_path).stem + ".outline.txt")
        outline_file.write_text(outline, encoding="utf-8")
        args = ["write", "--outline", str(outline_file), "--profile", profile,
                "--out", script_path, "--chars", str(chars), *_provider_args(provider),
                "--continue" if resume else "--fresh"]
        if author_dir:
            args += ["--author-dir", author_dir]
        # Che do viet TUNG PHAN (23/08): viet dung mot phan roi dung, de nguoi kiem
        # ngay thay vi cho ca bai 18 phut. gop_y chi co nghia khi viet lai mot phan.
        if chi_phan:
            args += ["--chi-phan", chi_phan]
            if gop_y:
                args += ["--gop-y", gop_y]
        nhan = f"VIET LAI {chi_phan}" if (chi_phan and gop_y) else (
            f"VIET {chi_phan}" if chi_phan else ("TIEP TUC" if resume else "WRITE"))
        ok = _run_cli(job, args, nhan, True)
        if not ok and job["cancelled"].is_set():
            status = "cancelled"
            # Huy giua chung: ghep script.md tu cac chuong da xong (checkpoint) de tai ve
            try:
                prof = json.loads(Path(profile).read_text(encoding="utf-8"))
                from .generator import write_partial_script
                info = write_partial_script(script_path, outline, prof)
                if info:
                    _log(job, f"=== DA HUY — da luu {info['sections']} phan da viet vao "
                              f"{script_path} (tai ve duoc / bam Tiep tuc de viet not) ===")
                else:
                    _log(job, "=== DA HUY — chua chuong nao xong ===")
            except Exception as e:  # noqa: BLE001
                _log(job, f"(Huy: khong ghep duoc phan da viet: {e})")
        elif ok:
            status = "done"
            _log(job, f"\n=== XONG — script: {script_path} ===")
    except Exception as e:  # noqa: BLE001
        with _LOCK:
            job["error"] = str(e)
        _log(job, f"LOI: {e}")
    finally:
        version = _snapshot(job, script_path, status)
        if version:
            _log(job, f"(Da luu ban ky bien: {Path(version).name} — quan ly xem lai duoc)")
        _finish_job(job, "writer", status, script=script_path, version=version,
                    title=_outline_title(outline), chars_target=int(chars),
                    chars=_file_chars(script_path), provider=provider, resume=bool(resume))
        with _LOCK:
            job["running"], job["done"] = False, True


# --- Native folder/file picker (macOS osascript — khong dung Tk, an toan thread) ----

def _pick_folder(prompt: str = "Chon folder") -> str | None:
    try:
        r = subprocess.run(
            ["osascript", "-e", f'POSIX path of (choose folder with prompt "{prompt}")'],
            capture_output=True, text=True, timeout=180)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _pick_save(prompt: str, default_name: str) -> str | None:
    try:
        r = subprocess.run(
            ["osascript", "-e",
             f'POSIX path of (choose file name with prompt "{prompt}" default name "{default_name}")'],
            capture_output=True, text=True, timeout=180)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _library_payload() -> dict:
    authors = []
    for a in library.list_authors():
        n_moves = n_targets = 0
        try:
            data = json.loads(Path(a["profile"]).read_text(encoding="utf-8"))
            n_moves = len(data.get("signature_moves", []))
            n_targets = len(data.get("reproduction_targets", {}))
        except (json.JSONDecodeError, OSError):
            pass
        authors.append({"code": a["code"], "name": a["name"], "profile": a["profile"],
                        "corpus": a.get("corpus"), "output": str(Path(a["profile"]).parent),
                        "n_moves": n_moves, "n_targets": n_targets,
                        "created_by": (a.get("created_by") or "").strip()})
    # can_pick: osascript/`open` chi co tren macOS — tren VPS headless board an cac
    # nut Browse/Save-as/Open va hien nut Upload thay the.
    return {"authors": authors, "providers": _providers(),
            "can_pick": sys.platform == "darwin"}


# ── Tom tat ho so cho UI (24/08) ───────────────────────────────────────────────────
# Owner: "UI log hien nay toi can dua them ca bao cao sau khi extract: muc do, so tu,
# do gian cau, muc do giong tac gia". Bon nhom so do la bon cau hoi khac nhau:
#   muc do   — co du diem do de tin cac con so khong (C1)
#   so tu    — corpus day hay mong, va bao nhieu file
#   do gian  — nhip cau: so tu moi cau ± do lech chuan, ti le cau cut
#   giong    — Delta: giong nay gan giong nao trong kho, co trung ai khong
# Python do het, khong goi model.

DELTA_TU_MOI_HO_SO = 20000   # doc bao nhieu tu moi corpus de dung bang Delta


def _tom_tat_tu_profile(profile: dict, ma: str, bang_delta: dict | None) -> dict:
    """Bon nhom so tu MOT ho so da co san (khong doc lai corpus)."""
    from .dien_ngon import TEN_CHIEU  # noqa: F401  (giu import gan nhau cho de lan)
    cs = profile.get("corpus_stats") or {}
    qf = [f for f in (profile.get("quant_features") or []) if isinstance(f, dict)]
    rt = profile.get("reproduction_targets") or {}
    gt = {f.get("name"): f.get("value") for f in qf}

    diem = cs.get("n_stability_units") or 0
    tu = cs.get("n_tokens") or 0
    if diem < 3:
        muc = "chua_do_duoc"
    elif tu < 12000 or diem < 5:
        muc = "mong"
    else:
        muc = "du"

    ex = [e for e in (profile.get("exemplars") or []) if isinstance(e, str)]
    ra = {
        "ma": ma,
        "ten": profile.get("author") or "",
        "muc_do": muc,
        "tu": tu,
        "file": cs.get("n_works") or 0,
        "diem_do": diem,
        "chi_so_on_dinh": sum(1 for f in qf if f.get("keep")),
        "tong_chi_so": len(qf),
        "so_target": len(rt),
        "moves": len(profile.get("signature_moves") or []),
        "nhip": {
            "tu_moi_cau": gt.get("sentence_len_mean"),
            "do_gian": gt.get("sentence_len_stdev"),
            "ti_le_cut": (gt.get("sentence_short_ratio") or 0) * 100 or None,
            "ti_le_dai": (gt.get("sentence_long_ratio") or 0) * 100 or None,
        },
        "neo_tu": sum(len(e.split()) for e in ex),
        "mo_ta": {k: v for k, v in (profile.get("mo_ta_giong") or {}).items()
                  if k != "so_do_neo"},
        "giong": {},
        "canh_bao": [],
    }

    from .soi_ho_so import soi_profile
    soi = soi_profile(profile)
    canh = list(soi.get("canh_bao") or [])
    canh += list((profile.get("discourse_features") or {}).get("canh_bao") or [])
    # soi_ho_so do 3 doan mau TRONG ho so, nhung luc viet that `write --author-dir`
    # thay chung bang neo day rut tu corpus (chon_neo). Con corpus tren dia thi hai
    # canh bao ve neo la sai ngu canh — bo di va noi ro neo thuc te lay tu dau.
    cd = (profile.get("corpus_stats") or {}).get("corpus_dir")
    ra["neo_day"] = bool(cd and Path(cd).is_dir())
    if ra["neo_day"]:
        canh = [c for c in canh if "Neo giọng chỉ" not in c and "đoạn mẫu trùng" not in c]
    ra["canh_bao"] = canh
    # Canh bao noi CO GI SAI; yeu cau noi PHAI LAM GI (Owner 24/08). Ho so sach thi
    # danh sach rong — khong bia ra viec cho du muc.
    from .soi_ho_so import yeu_cau_hoan_thien
    ra["yeu_cau"] = yeu_cau_hoan_thien(
        soi, (profile.get("discourse_features") or {}).get("canh_bao") or [])

    if bang_delta and ma in (bang_delta.get("z") or {}):
        from . import delta as D
        gan = sorted(({"ma": k, "delta": round(D.delta_giua(ma, k, bang_delta), 3)}
                      for k in bang_delta["z"] if k != ma), key=lambda r: r["delta"])
        trung = [n for n in D.nhom_ban_sao(bang_delta) if ma in n]
        ra["giong"] = {
            "gan_nhat": gan[0] if gan else None,
            "xa_nhat": gan[-1] if gan else None,
            "trung": [x for x in (trung[0] if trung else []) if x != ma],
        }
    return ra


def _bang_delta_kho() -> dict | None:
    """Bang Delta tren toan thu vien — doc DELTA_TU_MOI_HO_SO tu dau moi corpus.

    Khong doc tron corpus: A001 co 149.240 tu, doc het chi de lay mot con so thi UI
    phai cho. Delta on dinh tu vai nghin tu; cat deu mot moc cho moi ho so cung giu
    duoc tinh cong bang giua cac ho so.
    """
    from . import delta as D
    from .corpus import load_corpus_dir
    kho = {}
    for a in library.list_authors():
        d = a.get("corpus")
        if not d or not Path(d).is_dir():
            continue
        try:
            works = load_corpus_dir(d)
        except (OSError, ValueError):
            continue
        gom, dem = [], 0
        for w in works:
            gom.append(w)
            dem += len(w.split())
            if dem >= DELTA_TU_MOI_HO_SO:
                break
        kho[a["code"]] = gom
    if len(kho) < 2:
        return None
    try:
        return D.xay_bang(kho)
    except ValueError:
        return None


def _api_ho_so(q: dict) -> tuple[int, dict]:
    """GET /api/ho-so?ma=A013 — CHI nhan MA (cung luat voi /api/kiem-chung: client
    khong duoc tro server vao file bat ky)."""
    ma = (q.get("ma") or "").strip()
    a = next((x for x in library.list_authors() if x["code"] == ma), None)
    if not a:
        return 404, {"error": f"khong tim thay ho so {ma!r} trong thu vien"}
    p = Path(a["profile"])
    if not p.is_file():
        return 404, {"error": "ho so chua duoc dung — chay Extractor truoc"}
    try:
        profile = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return 500, {"error": f"khong doc duoc profile.json: {e}"}
    ra = _tom_tat_tu_profile(profile, ma, _bang_delta_kho())
    bc = p.parent / "bao-cao-extract.md"
    ra["bao_cao"] = str(bc) if bc.is_file() else ""
    return 200, ra


def _providers() -> list[dict]:
    try:
        from .llm import available_model_choices
        return available_model_choices()
    except Exception:  # noqa: BLE001
        return []


def _detect_corpus_dirs(author_dir: str) -> list[str]:
    from .dirsuggest import detect_corpus_dirs
    return detect_corpus_dirs(author_dir)


# Chỉ deliverable của Writer/Extractor mới cho tải về. KHÔNG .txt/.json: cookies.txt
# (phiên YouTube), videos.txt (API key), library/index.json là dữ liệu nhạy cảm nằm
# ngay trong folder tool — bài học rà soát bảo mật 2026-07-09.
_DOWNLOAD_EXT = {".md", ".jsonl"}
_DOWNLOAD_DENY = {"cookies.txt", "videos.txt", ".env", ".htpasswd", "invites.json"}


def _safe_download_path(raw: str) -> Path | None:
    """File deliverable (.md/.jsonl) THẬT nằm trong folder tool.

    Chặn traversal (.., symlink ra ngoài) bằng resolve() + is_relative_to gốc repo;
    denylist tên nhạy cảm là lớp phòng thủ thứ hai (dù đuôi đã loại chúng).
    """
    if not raw:
        return None
    try:
        rp = Path(raw).resolve()
        if (rp.is_file() and rp.suffix.lower() in _DOWNLOAD_EXT
                and rp.name not in _DOWNLOAD_DENY
                and rp.is_relative_to(_REPO_ROOT.resolve())):
            return rp
    except OSError:
        pass
    return None


def _save_upload(b: dict) -> dict:
    """Nhan ban thao JSON {name, files:[{name,text}]} tu board -> ghi uploads/<ten>/.

    Duong upload cho VPS (khong co picker native): chi nhan .txt/.md, ten file cat
    ve basename de khong ghi ra ngoai folder dich.
    """
    import re
    files = b.get("files") or []
    if not files:
        return {"error": "khong co file nao"}

    # BO SUNG TAC PHAM cho mot giong DA CO (24/08): client gui MA ho so, server tu tra
    # thu vien lay thu muc corpus that — khong nhan duong dan tu client (cung luat voi
    # /api/kiem-chung). Phai tra thu vien chu khong doan `uploads/<ten>`: A001 co corpus
    # o `authors/Carl Sagan/Cosmos`, doan sai thi file bo sung roi vao thu muc khac va
    # ho so khong he day them mot chu nao.
    ma = str(b.get("vao_ma") or "").strip()
    if ma:
        a = next((x for x in library.list_authors() if x["code"] == ma), None)
        if not a or not a.get("corpus"):
            return {"error": f"khong tim thay ho so {ma!r} trong thu vien"}
        dest = Path(a["corpus"])
        if not dest.is_dir():
            return {"error": f"thu muc corpus cua {ma} khong con: {dest}"}
    else:
        name = re.sub(r"[^\w\s-]", "", str(b.get("name") or "")).strip() or "corpus"
        dest = _REPO_ROOT / "uploads" / name
    dest.mkdir(parents=True, exist_ok=True)

    saved = 0
    for f in files:
        fname = Path(str(f.get("name", ""))).name
        if not fname.lower().endswith((".txt", ".md")):
            continue
        p = dest / fname
        # Bo sung KHONG duoc de len ban cu: trung ten thi them hau to, khong ghi de
        # (cung luat voi kho tai lieu ben ai-agent).
        if ma and p.exists():
            goc, duoi = p.stem, p.suffix
            i = 2
            while (dest / f"{goc}-{i}{duoi}").exists():
                i += 1
            p = dest / f"{goc}-{i}{duoi}"
        p.write_text(str(f.get("text", "")), encoding="utf-8")
        saved += 1
    if not saved:
        return {"error": "khong file nao la .txt/.md"}
    return {"dir": str(dest), "saved": saved}


# --- HTTP handler -------------------------------------------------------------------

def make_handler():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False))

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

        def _user(self) -> str:
            """Ai dang bam nut. CHI tin X-Remote-User do nginx ghi de (luat C2) — chay
            local mot minh khong co header nay thi job ghi so la nac danh."""
            return (self.headers.get("X-Remote-User") or "").strip()

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/status":
                k = _job_key(self._user())
                with _LOCK:
                    job = JOBS.get(k)
                    payload = _public(job) if job else dict(_JOB_SHAPE, log=[])
                    payload["others"] = _others_locked(k)
                self._json(200, payload)
            elif path == "/api/library":
                self._json(200, _library_payload())
            elif path == "/api/ho-so":
                from urllib.parse import parse_qs, urlparse
                q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                self._json(*_api_ho_so(q))
            elif path == "/api/download":
                from urllib.parse import parse_qs, urlparse
                raw = (parse_qs(urlparse(self.path).query).get("path") or [""])[0]
                rp = _safe_download_path(raw)
                if not rp:
                    self._json(404, {"error": "file chưa tồn tại hoặc ngoài vùng cho phép"})
                    return
                data = rp.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{rp.name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._json(404, {})

        def do_POST(self):
            b = self._body()
            path = self.path
            if path == "/api/pick-folder":
                self._json(200, {"path": _pick_folder(b.get("prompt", "Chon folder"))})
            elif path == "/api/pick-save":
                self._json(200, {"path": _pick_save(b.get("prompt", "Luu file"),
                                                    b.get("default", "script.md"))})
            elif path == "/api/detect-corpus":
                ad = b.get("author_dir", "")
                dirs = _detect_corpus_dirs(ad)
                from .dirsuggest import default_author_name, default_output_dir
                name = default_author_name(ad) if ad else ""
                out = ""
                if name:
                    entry = library.ensure_author(name, created_by=self._user())
                    out = default_output_dir(ad, library.author_folder_name(entry))
                # Canh bao transcript tho (2026-07-16): file khong dau cham lam hong nhip
                # cau cua ho so giong (da xay ra that voi Ventures — cau dai gap 3 tac gia).
                # CHI BAO, khong tu bo file cua user (luat A3) — ho tu don folder neu muon.
                from .corpus import transcript_warnings
                warns = []
                for d in ([ad] if ad else []) + [x for x in dirs if x != ad]:
                    try:
                        warns += transcript_warnings(d)
                    except OSError:
                        pass
                self._json(200, {"dirs": dirs, "name": name, "output": out,
                                 "transcript_warnings": sorted(set(warns))})
            elif path == "/api/upload-corpus":
                self._json(200, _save_upload(b))
            elif path == "/api/outline-check":
                from .generator import outline_scope_report
                self._json(200, outline_scope_report(
                    b.get("outline", ""), int(b.get("chars") or 18000)))
            elif path == "/api/checkpoint":
                from .generator import load_checkpoint
                done = load_checkpoint(b.get("script", ""), b.get("outline", ""))
                self._json(200, {"done": list(done)})
            elif path == "/api/build":
                # CUA CHAN transcript tho (21/08/2026). Canh bao suong tu 16/07 da bi bo
                # qua 100%: do that thang 8 cho thay 3/9 ho so trong kho van dung tren
                # corpus khong dau cau (sentence_len_mean = 1085) va van duoc dung de viet
                # suot 3 tuan. Van CHI chan mot lan — user tick xac_nhan la di tiep (A3:
                # user quyet), nhung phai BIET minh dang quyet gi.
                from .corpus import transcript_warnings
                if not b.get("xac_nhan_transcript_tho"):
                    canh = transcript_warnings(b.get("corpus", ""))
                    if canh:
                        self._json(409, {"error": "corpus_transcript_tho", "canh_bao": canh,
                                         "goi_y": "Bỏ các file này ra, hoặc chấm câu lại rồi "
                                                  "nạp lại. Vẫn muốn dựng thì tick xác nhận."})
                        return
                steps = (1 + int(bool(b.get("rhetoric", True)))
                         + int(bool(b.get("clonekit", True)))
                         + int(bool(b.get("dataset", True))) + int(bool(b.get("lab", False)))
                         + int(bool(b.get("mo_ta", False))))
                job, err = _try_start(self._user(), "extractor", steps, out=b["out"])
                if not job:
                    self._json(409, {"error": err}); return
                threading.Thread(target=_run_extractor, kwargs={
                    "job": job, "corpus": b["corpus"], "name": b["name"], "out": b["out"],
                    "do_rhetoric": b.get("rhetoric", True), "do_clonekit": b.get("clonekit", True),
                    "do_dataset": b.get("dataset", True), "provider": b.get("provider"),
                    "do_lab": b.get("lab", False), "do_mo_ta": b.get("mo_ta", False),
                    "lab_samples": max(3, min(10, int(b.get("lab_samples") or 5))),
                }, daemon=True).start()
                self._json(200, {"started": True})
            elif path == "/api/write":
                job, err = _try_start(self._user(), "writer", 0,
                                      script_path=b["script_path"])
                if not job:
                    self._json(409, {"error": err}); return
                threading.Thread(target=_run_writer, kwargs={
                    "job": job, "outline": b["outline"], "profile": b["profile"],
                    "author_dir": b.get("author_dir"), "script_path": b["script_path"],
                    "chars": int(b.get("chars", 18000)), "provider": b["provider"],
                    "resume": b.get("resume", False),
                    "chi_phan": (b.get("chi_phan") or None),
                    "gop_y": str(b.get("gop_y") or ""),
                }, daemon=True).start()
                self._json(200, {"started": True})
            elif path == "/api/cancel":
                self._json(200, {"cancelled": cancel_job(self._user())})
            elif path == "/api/open":
                p = b.get("path", "")
                if p and Path(p).exists():
                    subprocess.Popen(["open", p])
                self._json(200, {"ok": True})
            else:
                self._json(404, {})

    return Handler


def run(port: int) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler())
    url = f"http://127.0.0.1:{port}/"
    print(f"Author Extract — mo giao dien tai {url}  (Ctrl+C de dung)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDa dung.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    run(ap.parse_args().port)


if __name__ == "__main__":
    main()
