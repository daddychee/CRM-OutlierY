#!/usr/bin/env python3
"""
Niche Research — orchestrator (the DAG driver from the architecture doc, §4).

Runs the deterministic [PY] pipeline end-to-end and produces the multi-sheet workbook:

    python3 orchestrator.py run competitors.txt
    python3 orchestrator.py run competitors.txt --work ./PROJECT --out report.xlsx
    python3 orchestrator.py run competitors.txt --skip-comments

Engineering rules honored:
  • DAG + idempotent  — a stage is skipped when all its outputs are newer than all its inputs (like Make).
  • Resumable I/O      — S1 scan / S3 comments checkpoint per page; we loop them until they print DONE.
  • Schema gate        — after each stage, outputs are validated against contracts/<name>.schema.json
                         (best-effort: needs `jsonschema`; if absent, a shallow key check is used).
  • LLM stages         — S4b/S9b/S12/S13/S16/S17 need a real model and are NOT run here. They are listed
                         with their agent spec; the report renders whatever JSON exists and shows a banner
                         where an LLM artifact is missing. Run the agents in agents/*.md, then rebuild.

Python does everything measurable; the LLM does everything that must be understood. This driver only
covers the Python half + the render — exactly the split argued in the architecture doc §0.
"""
import argparse, os, re, sys, shutil, subprocess, time, json, glob

# Console Windows mặc định cp1252 — orchestrator in ✓/Σ/tiếng Việt sẽ chết
# UnicodeEncodeError giữa chừng (dính thật 18/08). Ép UTF-8 cho chính tiến trình
# này; tiến trình con đã có PYTHONUTF8=1 trong run_once.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
CONTRACTS = os.path.join(HERE, "contracts")

def check_deps():
    """Auto-install requests/openpyxl on first run — a fresh PC (esp. Windows) won't have them yet,
    and a bare ModuleNotFoundError from a subprocess stage is a confusing way to discover that."""
    missing = []
    for mod in ("requests", "openpyxl"):
        try: __import__(mod)
        except ImportError: missing.append(mod)
    if not missing: return
    print(f"Installing missing packages: {', '.join(missing)} ...")
    cmd = [sys.executable, "-m", "pip", "install", *missing]
    if subprocess.run(cmd).returncode != 0:
        subprocess.run(cmd + ["--break-system-packages"])  # externally-managed env fallback
    for mod in missing:
        try: __import__(mod)
        except ImportError:
            print(f"ERROR: could not install {mod}. Run manually:  {sys.executable} -m pip install {mod}")
            sys.exit(1)

# --- project layout (kept in sync with scripts/_common.py) ---------------------------------------
DATA_DIRNAME        = "niche-data"    # all intermediate JSON + checkpoints + logs
REPORT_DIRNAME      = "Report"        # the deliverable .xlsx
TRANSCRIPTS_DIRNAME = "Transcripts"   # readable, title-named transcripts

# files older versions wrote to the PROJECT ROOT — migrated into niche-data/ so the scan is reused
_MIGRATE = ["videos.json", "channels.json", "analysis.json", "gaps.json", "comments.json",
            "crackability.json", "decision1.json", "decision2.json", "demand.json",
            "monetization.json", "subniche.json", "bets.json", "bets_audited.json", "dna.json",
            "execution_plan.json", "scan_done.json", "scan_state.json", "_done_comments.json",
            "run.log", ".state.json"]

def migrate_layout(project, data):
    """Move a legacy flat project (everything dumped in the root) into niche-data/. Crucially this
    preserves the expensive scan/comments so nothing is re-fetched. Idempotent & best-effort."""
    os.makedirs(data, exist_ok=True)
    names = list(_MIGRATE)
    names += [os.path.basename(x) for x in glob.glob(os.path.join(project, "deepdive_*.json"))]
    names += [os.path.basename(x) for x in glob.glob(os.path.join(project, "00-danh-sach-video-*.md"))]
    moved = 0
    for n in names:
        src, dst = os.path.join(project, n), os.path.join(data, n)
        if os.path.exists(src) and not os.path.exists(dst):
            try: shutil.move(src, dst); moved += 1
            except Exception: pass
    return moved

def retitle_transcripts(tdir, titles):
    """Rename any legacy code-named transcript files (NN_<id>.txt) to '<NN> - <title>.txt' using the
    index + a videoId->title map. Best-effort; keeps files that are already titled."""
    idx_p = os.path.join(tdir, "index.json")
    if not os.path.exists(idx_p): return 0
    try: index = json.load(open(idx_p, encoding="utf-8"))
    except Exception: return 0
    renamed = 0
    for vid, meta in index.items():
        if meta.get("status") != "ok" or not meta.get("file"): continue
        old = os.path.join(tdir, meta["file"])
        if not os.path.exists(old): continue
        m = re.match(r"^(\d{2})[ _]", meta["file"])
        seq = m.group(1) if m else "00"
        title = meta.get("title") or titles.get(vid, "")
        if not title: continue
        new_name = f"{seq} - {_safe(title)}.txt"
        if new_name == meta["file"]: continue
        try:
            os.rename(old, os.path.join(tdir, new_name)); meta["file"] = new_name; renamed += 1
        except Exception: pass
    if renamed:
        json.dump(index, open(idx_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return renamed

def _safe(s, maxlen=90):
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s).strip(". ")
    return (s[:maxlen].rstrip() or "untitled")

_ANSI = re.compile(r"\033\[[0-9;]*m")
_LOG_FH = None   # set by cmd_run — every run.log line is timestamped and ANSI-stripped

def open_log(work):
    global _LOG_FH
    _LOG_FH = open(os.path.join(work, "run.log"), "a", encoding="utf-8")
    _LOG_FH.write(f"\n===== run started {datetime.now().isoformat(timespec='seconds')} =====\n")
    _LOG_FH.flush()

def log(msg=""):
    """print() that ALSO appends to <project>/run.log, so anything shown on screen (including
    transcript-API failures like 402/401) is still inspectable after the GUI window is closed."""
    print(msg)
    if _LOG_FH:
        for line in str(msg).split("\n"):
            _LOG_FH.write(_ANSI.sub("", line) + "\n")
        _LOG_FH.flush()

def _c(code, s): return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s
def bold(s): return _c("1", s)
def cyan(s): return _c("36", s)
def green(s): return _c("32", s)
def yellow(s): return _c("33", s)
def red(s): return _c("31", s)
def dim(s): return _c("2", s)

STATE_FILE = ".state.json"     # lives inside the PROJECT folder — remembers the args of the last `run`,
                               # so a stopped/crashed/closed session can be CONTINUED without re-picking files.

def save_state(work, **kw):
    try:
        json.dump(kw, open(os.path.join(work, STATE_FILE), "w", encoding="utf-8"), indent=1)
    except Exception:
        pass  # never let bookkeeping break a real run

def load_state(work):
    fp = os.path.join(work, STATE_FILE)
    if not os.path.exists(fp): return None
    try:
        return json.load(open(fp, encoding="utf-8"))
    except Exception:
        return None

BANNER = r"""
  _  _ _    _            ___                            _
 | \| (_)__| |_  ___    | _ \___ ___ ___ __ _ _ _ __| |_
 | .` | / _| ' \/ -_)   |   / -_|_-</ -_) _` | '_/ _| ' \
 |_|\_|_\__|_||_\___|   |_|_\___/__/\___\__,_|_| \__|_||_|
                           market map · Go/No-Go · beachhead
"""

# ---- DAG. Each stage: id, title, kind, argv-builder, inputs, outputs, resumable, optional ----
def stages(input_path, work, skip_comments, deepdive=None, llm=False):
    py = sys.executable
    def s(id, title, kind, script, inputs, outputs, extra=None, resumable=False, optional=False, needs_input=False, always=False):
        argv = [py, os.path.join(SCRIPTS, script), work] if not needs_input else [py, os.path.join(SCRIPTS, script), input_path, work]
        if extra: argv += extra
        return dict(id=id, title=title, kind=kind, script=script, argv=argv,
                    inputs=[os.path.join(work, i) if not os.path.isabs(i) else i for i in inputs],
                    outputs=[os.path.join(work, o) for o in outputs],
                    resumable=resumable, optional=optional, always=always)
    def agent(id, title, name, inputs, outputs):
        # LLM stages: real network calls (cost + latency), ALWAYS optional — a failure must never
        # kill the deterministic pipeline. run_agent.py picks the provider from .env (any of
        # Claude/ChatGPT/GLM/Grok/custom — see scripts/llm_provider.py).
        return s(id, title, "LLM", "run_agent.py", inputs, outputs, extra=[name], optional=True)

    out = [
        s("S1", "scan competitor videos", "PY", "1_scan.py", [input_path], ["videos.json", "channels.json"],
          resumable=True, needs_input=True),
        s("S3", "keywords + outlier LIFT", "PY", "2_keywords.py", ["videos.json"], ["analysis.json"]),
    ]
    if not skip_comments:
        out.append(s("S4", "comments -> viewer questions", "PY", "3_comments.py", ["videos.json"], ["gaps.json"],
                     resumable=True, optional=True, needs_input=True))
    out += [
        s("S5", "crackability (Go-gate)", "PY", "5_crackability.py", ["videos.json", "channels.json"], ["crackability.json"]),
        s("S6", "monetization heuristic", "PY", "6_monetization.py", ["videos.json", "analysis.json"], ["monetization.json"]),
        s("S7", "demand & trend", "PY", "7_demand.py", ["videos.json"], ["demand.json"]),
        # inputs must list EVERYTHING a stage reads, or up_to_date() skips it while an input is fresh
        # and the artifact silently goes stale (audit V15) — S8 also reads videos.json for the HHI.
        s("S8", "DECISION 1 (Go/No-Go)", "PY", "8_decision1.py", ["videos.json", "demand.json", "monetization.json", "crackability.json"], ["decision1.json"]),
        s("S9", "sub-niche clustering", "PY", "9_subniche.py", ["videos.json", "analysis.json", "channels.json"], ["subniche.json"]),
    ]
    if llm:
        # namer mutates subniche.json IN PLACE, so a same-file in==out pair would look "up to date"
        # forever — a separate marker output tracks whether THIS subniche.json has been labeled yet.
        out.append(agent("S9b", "name sub-niche clusters (LLM)", "namer", ["subniche.json"], ["_s9b_namer.done"]))
    out.append(s("S10", "DECISION 2 (beachhead)", "PY", "10_decision2.py",
                 ["subniche.json", "crackability.json", "monetization.json"], ["decision2.json"]))
    out.append(s("S11", "synthesize candidate bets", "PY", "11_synthesize_bets.py",
                 ["videos.json", "analysis.json", "gaps.json"], ["bets.json"], optional=True))
    if llm:
        out.append(agent("S12", "AUDITOR — Builder != Auditor (LLM)", "auditor", ["bets.json"], ["bets_audited.json"]))
        out.append(agent("S13", "Execution Plan (LLM)", "plan",
                         ["decision1.json", "decision2.json", "bets_audited.json"], ["execution_plan.json"]))
        # S19 reads every decision file, so it runs LAST — turns the numbers into an actionable guide
        # via a 3-pass self-critique loop (draft -> critique -> refine) on the one configured model.
        out.append(agent("S19", "FINAL SUMMARY — actionable guide, 3-pass critique (LLM)", "summary",
                         ["videos.json", "channels.json", "analysis.json", "gaps.json", "decision1.json",
                          "decision2.json", "subniche.json", "bets.json", "bets_audited.json",
                          "execution_plan.json", "crackability.json", "monetization.json", "demand.json"],
                         ["summary.json"]))
    # the report renders EVERY artifact — list them all, or a re-run after an LLM stage updated one
    # would skip S18 as "up-to-date" and ship a stale Excel (audit V15; missing files are ignored).
    out.append(s("S18", "build Excel report", "PY", "18_build_report.py",
                 ["videos.json", "analysis.json", "channels.json", "gaps.json", "crackability.json",
                  "monetization.json", "demand.json", "decision1.json", "subniche.json", "decision2.json",
                  "bets.json", "bets_audited.json", "execution_plan.json", "summary.json", "dna.json"],
                 ["__REPORT__"]))

    if deepdive is not None:
        anchor = [deepdive] if deepdive else None      # "" -> auto-pick top beachhead
        out += [
            s("S14", "deep-dive: pick DNA videos", "PY", "14_deepdive.py", ["videos.json"], [], extra=anchor, always=True),
            s("S15", "fetch transcripts (transcriptapi.com)", "PY", "15_fetch_transcripts.py", ["videos.json"],
              ["transcripts/index.json"], extra=anchor, resumable=True, optional=True, always=True),
        ]
        if llm:
            out.append(agent("S16/17", "DNA extraction (LLM)", "dna", ["transcripts/index.json"], ["dna.json"]))
            # DNA can change the Execution Plan's angle — rebuild both after it, if both ran.
            out.append(agent("S13b", "Execution Plan refresh w/ DNA (LLM)", "plan", ["dna.json"], ["execution_plan.json"]))
            out.append(s("S18b", "rebuild Excel report w/ DNA", "PY", "18_build_report.py",
                         ["dna.json"], ["__REPORT__"], always=True))
    return out

# LLM stages — listed in the footer when --llm is NOT used, so the user knows what's available.
LLM_STAGES = [
    ("S9b", "name sub-niche clusters", "subniche labels"),
    ("S12", "Auditor (critique bets)", "bets_audited.json"),
    ("S13", "Execution Plan", "execution_plan.json"),
    ("S16/17", "DNA extraction", "dna.json (needs --deepdive)"),
    ("S19", "FINAL SUMMARY (expert guide)", "Report/SUMMARY.md"),
]

def newest(paths):
    ts = [os.path.getmtime(p) for p in paths if os.path.exists(p)]
    return max(ts) if ts else None

def oldest(paths):
    ts = [os.path.getmtime(p) for p in paths if os.path.exists(p)]
    return min(ts) if ts else None

def up_to_date(st, report_path):
    # Make semantics: EVERY output must be newer than every input -> compare the OLDEST output
    # against the NEWEST input (the old newest-vs-newest let one refreshed output mask a stale
    # sibling on multi-output stages — audit V21).
    outs = [report_path if o.endswith("__REPORT__") else o for o in st["outputs"]]
    if not all(os.path.exists(o) for o in outs): return False
    in_t = newest(st["inputs"]); out_t = oldest(outs)
    return in_t is not None and out_t is not None and out_t >= in_t

def validate(st, work):
    """Best-effort schema gate against contracts/<output>.schema.json."""
    problems = []
    for o in st["outputs"]:
        if o.endswith("__REPORT__"): continue
        name = os.path.basename(o)
        schema_p = os.path.join(CONTRACTS, name.replace(".json", ".schema.json"))
        if not os.path.exists(schema_p) or not os.path.exists(o): continue
        try:
            data = json.load(open(o, encoding="utf-8"))
            schema = json.load(open(schema_p, encoding="utf-8"))
        except Exception as e:
            problems.append(f"{name}: unreadable ({e})"); continue
        try:
            import jsonschema  # optional
            jsonschema.validate(data, schema)
        except ImportError:
            for k in schema.get("required", []):
                if isinstance(data, dict) and k not in data:
                    problems.append(f"{name}: missing required key '{k}'")
        except Exception as e:
            problems.append(f"{name}: {str(e).splitlines()[0]}")
    return problems

def run_once(st, num, total):
    log(bold(cyan(f"\n>>> [{num}/{total}] {st['id']}  {st['title']}")))
    log(dim("    " + " ".join(os.path.basename(a) for a in st["argv"])))
    sys.stdout.flush()
    # PYTHONUTF8: console Windows mặc định cp1252 — script in ký tự ngoài bảng mã
    # (Σ, →, tiếng Việt) sẽ chết UnicodeEncodeError SAU khi đã ghi output (dính thật
    # 18/08: S9 crash ở dòng print trang trí). Ép UTF-8 cho MỌI stage con.
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    proc = subprocess.Popen(st["argv"], cwd=SCRIPTS, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1,
                            encoding="utf-8", errors="replace")
    lines = []
    for line in proc.stdout:
        lines.append(line); log("    " + line.rstrip("\n"))
    proc.wait()
    return proc.returncode, "".join(lines)

def run_stage(st, num, total):
    if st["resumable"]:
        last = None
        for attempt in range(1, 60):
            rc, out = run_once(dict(st, title=st["title"] + (f"  (pass {attempt})" if attempt > 1 else "")), num, total)
            if rc != 0: return rc
            if "DONE" in out: return 0
            if "PAUSE" in out:
                if out == last: log(yellow("    no forward progress — stopping.")); return 0
                last = out; time.sleep(0.4); continue
            return 0
        return 0
    rc, _ = run_once(st, num, total)
    return rc

def cmd_run(args):
    check_deps()
    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(red(f"ERROR: input file not found: {input_path}")); sys.exit(1)
    project = os.path.abspath(args.work) if args.work else os.path.dirname(input_path)
    # organized layout: intermediates in niche-data/, deliverable in Report/, transcripts in Transcripts/
    work = os.path.join(project, DATA_DIRNAME)         # scripts read/write JSON here
    report_dir = os.path.join(project, REPORT_DIRNAME)
    tdir = os.path.join(project, TRANSCRIPTS_DIRNAME)
    migrate_layout(project, work)                      # tidy any legacy flat project first (reuses scan)
    os.makedirs(work, exist_ok=True); os.makedirs(report_dir, exist_ok=True)
    os.environ["NICHE_TRANSCRIPTS_DIR"] = tdir          # tells 15_fetch where readable transcripts go
    retitle_transcripts(tdir, {})                       # rename any legacy code-named transcripts

    open_log(work)   # every message from here on is also appended to niche-data/run.log
    log(cyan(BANNER))
    stem = os.path.splitext(os.path.basename(input_path))[0]
    report = os.path.abspath(args.out) if args.out else os.path.join(report_dir, f"{stem}_report.xlsx")

    log(f"{bold('Input:')}       {input_path}")
    log(f"{bold('Project:')}     {project}")
    log(f"{bold('Report:')}      {report}")
    log(dim(f"(intermediates in {DATA_DIRNAME}/ · transcripts in {TRANSCRIPTS_DIRNAME}/ · log in {DATA_DIRNAME}/run.log)"))

    deepdive = args.deepdive if args.deepdive is not None else None
    llm = bool(getattr(args, "llm", False))
    # Remember these args (in niche-data/.state.json) so a stopped/closed/crashed run can be
    # CONTINUED later with `orchestrator.py resume <project>` (or the GUI's Refresh button)
    # without the user having to re-locate the original competitors.txt.
    save_state(work, project=project, input=input_path, out=report,
               skip_comments=bool(args.skip_comments), deepdive=deepdive, llm=llm)
    plan = stages(input_path, work, args.skip_comments, deepdive=deepdive, llm=llm)
    if deepdive is not None:
        log(yellow("\n⚠ COST GUARD — the deep-dive fetches YouTube transcripts via transcriptapi.com "
                   "(1 credit per video, up to 30). Needs TRANSCRIPT_API_KEY in .env."))
    if llm:
        log(yellow("⚠ LLM stages enabled — namer/Auditor/plan/SUMMARY call the one model set in .env "
                   "(LLM_PROVIDER, e.g. anthropic or glm). Costs tokens; each stage is optional and "
                   "failures don't stop the deterministic pipeline."))
    total = len(plan)
    for i, st in enumerate(plan, 1):
        # fill the report output placeholder
        st["outputs"] = [report if o.endswith("__REPORT__") else o for o in st["outputs"]]
        if st["script"] == "18_build_report.py":
            st["argv"] = [sys.executable, os.path.join(SCRIPTS, "18_build_report.py"), work, report]
        if not args.force and not st.get("always") and up_to_date(st, report):
            log(bold(cyan(f"\n>>> [{i}/{total}] {st['id']}  {st['title']}")))
            log(green("    up-to-date — skipping (use --force to rebuild)."))
            continue
        rc = run_stage(st, i, total)
        if rc != 0:
            if st["optional"]:
                log(yellow(f"    optional stage {st['id']} failed — continuing.")); continue
            log(red(f"    stage {st['id']} failed (exit {rc}). Fix and re-run; progress is saved.")); sys.exit(rc)
        probs = validate(st, work)
        if probs:
            log(yellow("    schema gate warnings: " + "; ".join(probs)))

    log(green(bold(f"\n✓ Pipeline done — report: {report}")))
    if not llm:
        log(dim("\nLLM stages NOT run (deterministic only). Enable them with --llm (or the GUI checkbox) "
                "once a model is configured in .env (LLM_PROVIDER + its API key):"))
        for sid, title, io in LLM_STAGES:
            log(dim(f"    {sid:6} {title:34} [{io}]"))

# ============================ STATUS / RESUME — the "Refresh" mechanism ============================
def resolve_project(path_arg):
    """Accept a project FOLDER (or its competitors .txt) and return (project, data_dir, state).
    Reads state from niche-data/.state.json, falling back to a legacy root .state.json."""
    p = os.path.abspath(path_arg)
    project = p if os.path.isdir(p) else os.path.dirname(p)
    data = os.path.join(project, DATA_DIRNAME)
    state = load_state(data) or load_state(project)   # new location first, then legacy
    return project, data, state

def _subniche_labeled(data):
    fp = os.path.join(data, "subniche.json")
    if not os.path.exists(fp): return False
    try:
        d = json.load(open(fp, encoding="utf-8")); cl = d.get("clusters", [])
        return bool(cl) and all(c.get("label") for c in cl)
    except Exception:
        return False

def cmd_status(args):
    """Read-only checklist: what's done, stale, or missing for this project — the info a 'Refresh'
    button needs before it decides what to (re)run. Never runs anything itself."""
    project, data, state = resolve_project(args.project)
    print(cyan(BANNER))
    print(f"{bold('Project:')} {project}")
    if not os.path.isdir(project):
        print(red("ERROR: not a folder.")); sys.exit(1)
    if not state:
        print(yellow(f"No previous run recorded here (no {DATA_DIRNAME}/{STATE_FILE}). "
                     f"Run  python3 orchestrator.py run <competitors.txt>  at least once first."))
        return
    input_path, report = state.get("input"), state.get("out")
    missing_input = " (FILE MISSING — was it moved?)" if not (input_path and os.path.isfile(input_path)) else ""
    print(f"{bold('Input:')}  {input_path}{missing_input}")
    print(f"{bold('Report:')} {report}")

    plan = stages(input_path, data, state.get("skip_comments", False),
                 deepdive=state.get("deepdive"), llm=bool(state.get("llm")))
    print(bold(f"\nStages{' (LLM enabled: ' + str(bool(state.get('llm'))) + ')' if 'llm' in state else ''}:"))
    n_incomplete = 0
    for st in plan:
        outs = [report if o.endswith("__REPORT__") else o for o in st["outputs"]]
        if not all(os.path.exists(o) for o in outs):
            mark = red("✗ missing"); n_incomplete += 1
        elif up_to_date(dict(st, outputs=outs), report):
            mark = green("✓ done")
        else:
            mark = yellow("⏳ stale (inputs changed since last build)"); n_incomplete += 1
        print(f"  {st['id']:5} {st['title']:38} {mark}")

    shown = {st["id"] for st in plan}   # LLM stages already listed above if --llm was used this run
    checks = [
        ("S9b", "sub-niche cluster labels", lambda: _subniche_labeled(data)),
        ("S12", "Auditor -> bets_audited.json", lambda: os.path.exists(os.path.join(data, "bets_audited.json"))),
        ("S13", "Execution Plan", lambda: os.path.exists(os.path.join(data, "execution_plan.json"))),
        ("S16/17", "DNA extraction -> dna.json", lambda: os.path.exists(os.path.join(data, "dna.json"))),
    ]
    remaining = [(sid, t, c) for sid, t, c in checks if sid not in shown]
    if remaining:
        print(bold("\nLLM stages (run with --llm, or `orchestrator.py llm <project>` — see agents/*.md):"))
        for sid, title, check in remaining:
            try: ok = check()
            except Exception: ok = False
            print(f"  {sid:5} {title:38} {green('✓ done') if ok else dim('○ not run yet')}")

    if n_incomplete:
        print(yellow(f"\n{n_incomplete} Python stage(s) incomplete —> "
                     f'run:  python3 orchestrator.py resume "{project}"'))
    else:
        print(green("\nAll Python (deterministic) stages complete."))

def cmd_resume(args):
    """The 'Refresh' action: replay the LAST run's args from niche-data/.state.json. Safe to call
    any number of times — the DAG is idempotent, so it only (re)does what's missing or stale."""
    project, data, state = resolve_project(args.project)
    if not state:
        print(red(f"ERROR: no previous run recorded in {project} (no {DATA_DIRNAME}/{STATE_FILE}). "
                  f"Run `orchestrator.py run <competitors.txt>` at least once first.")); sys.exit(1)
    if not state.get("input") or not os.path.isfile(state["input"]):
        print(red(f"ERROR: the original competitors file is missing or moved: {state.get('input')}. "
                  f"Point at it directly with `orchestrator.py run <file>` instead.")); sys.exit(1)
    ns = argparse.Namespace(input=state["input"], work=state.get("project") or project, out=state.get("out"),
                            skip_comments=bool(state.get("skip_comments", False)),
                            force=False, deepdive=state.get("deepdive"), llm=bool(state.get("llm", False)))
    cmd_run(ns)

def cmd_watch(args):
    """Watch cycle (Tầng 2/3 monitoring): re-scan views + demand + snapshot/diff tín hiệu.
    KHÁC resume: chỉ chạy phần RẺ (S1/S7/S20), không đụng LLM, không build report.
    S1 skip kênh đã có trong scan_done.json nên phải xóa checkpoint trước để ép re-scan;
    dedup theo videoId trong 1_scan.py giữ bản mới (views tươi thắng views cũ)."""
    check_deps()
    project, data, _state = resolve_project(args.project)
    input_path = os.path.join(project, "competitors.txt")
    if not os.path.isfile(input_path):
        print(red(f"ERROR: không có {input_path} — dự án chỉ chứa báo cáo upload, không watch được."))
        sys.exit(1)
    os.makedirs(data, exist_ok=True)
    open_log(data)
    py = sys.executable
    log(bold(cyan(f"WATCH CYCLE — {os.path.basename(project)}")))

    def st(id, title, script, argv_extra, resumable=False):
        return dict(id=id, title=title, kind="PY", script=script,
                    argv=[py, os.path.join(SCRIPTS, script)] + argv_extra,
                    inputs=[], outputs=[], resumable=resumable, optional=False, always=True)

    # 0) baseline từ dữ liệu hiện có (no-op nếu đã có snapshot)
    run_stage(st("S20", "watch baseline", "20_watch.py", [data, "--baseline"]), 1, 4)
    # 1) xóa checkpoint scan để ép re-scan toàn bộ kênh
    for f in ("scan_done.json", "scan_state.json"):
        fp = os.path.join(data, f)
        if os.path.exists(fp): os.remove(fp)
    # 2) re-scan (resumable — hết quota thì PAUSE, lượt sau chạy tiếp)
    rc = run_stage(st("S1", "watch re-scan views", "1_scan.py", [input_path, data], resumable=True), 2, 4)
    if rc != 0:
        log(red("watch: scan lỗi — dừng, không snapshot dữ liệu dở dang")); sys.exit(1)
    # 3) demand & trend trên dữ liệu tươi
    run_stage(st("S7", "watch demand & trend", "7_demand.py", [data]), 3, 4)
    # 4) snapshot + diff → signals.json (tự cập nhật last_run trong .watch.json)
    run_stage(st("S20", "watch snapshot + diff", "20_watch.py", [data]), 4, 4)
    log(green("WATCH DONE"))


def cmd_llm(args):
    """Run ONE LLM agent directly against an existing project — the flexible entry point for
    picking a provider per stage (e.g. GLM for the Auditor, Claude for everything else) without
    re-running the whole pipeline. Safe to call repeatedly."""
    check_deps()
    project, data, state = resolve_project(args.project)
    if not state:
        print(red(f"ERROR: no previous run recorded in {project}. Run `orchestrator.py run <file>` first.")); sys.exit(1)
    open_log(data)
    if args.provider: os.environ["LLM_PROVIDER"] = args.provider
    if args.auditor_provider: os.environ["AUDITOR_LLM_PROVIDER"] = args.auditor_provider
    tdir = os.path.join(project, TRANSCRIPTS_DIRNAME)
    if os.path.isdir(tdir): os.environ.setdefault("NICHE_TRANSCRIPTS_DIR", tdir)

    # default sweep runs namer -> auditor -> plan -> summary (summary reads the others, so it goes last)
    todo = [args.agent] if args.agent else [a for a in ("namer", "auditor", "plan", "summary")
                                            if not {"namer": os.path.exists(os.path.join(data, "_s9b_namer.done")),
                                                    "auditor": os.path.exists(os.path.join(data, "bets_audited.json")),
                                                    "plan": os.path.exists(os.path.join(data, "execution_plan.json")),
                                                    "summary": os.path.exists(os.path.join(data, "summary.json"))}[a]]
    if not todo:
        print(green("Nothing pending — namer/auditor/plan/summary have all run. "
                    "Pass --agent dna explicitly once transcripts exist, or --agent <x> to force a redo."))
        return
    for a in todo:
        print(bold(cyan(f">>> running agent: {a}")))
        rc, _ = run_once(dict(id=a.upper(), title=f"agent {a}",
                              argv=[sys.executable, os.path.join(SCRIPTS, "run_agent.py"), data, a]), 1, 1)
        if rc != 0:
            print(red(f"agent {a} failed (exit {rc})")); continue
    report = state.get("out")
    if report:   # rebuild even if the file was deleted/moved — 18_build_report recreates it (V15)
        rc, _ = run_once(dict(id="S18", title="rebuild report",
                              argv=[sys.executable, os.path.join(SCRIPTS, "18_build_report.py"), data, report]), 1, 1)
        if rc == 0: print(green(f"\n✓ report rebuilt: {report}"))

def main(argv=None):
    ap = argparse.ArgumentParser(prog="orchestrator", description="Niche Research — run the analysis DAG into one Excel report.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="run the full deterministic pipeline")
    r.add_argument("input", help="competitors.txt (API key(s) + channel URLs/IDs)")
    r.add_argument("--work", default=None, help="project dir for JSON + report (default: the input file's folder)")
    r.add_argument("--out", default=None, help="report .xlsx path (default: <project>/<input>_report.xlsx)")
    r.add_argument("--skip-comments", action="store_true", help="skip the comment/info-gap stage")
    r.add_argument("--force", action="store_true", help="rebuild every stage even if up-to-date")
    r.add_argument("--deepdive", nargs="?", const="", default=None, metavar="ANCHOR",
                   help="after the report, fetch transcripts (transcriptapi.com) for a sub-niche's outliers. "
                        "Give a keyword to target it, or leave blank to auto-pick the top beachhead. Costs credits.")
    r.add_argument("--llm", action="store_true",
                   help="also run the judgement stages (S9b namer, S12 Auditor, S13 Execution Plan, "
                        "and S16/17 DNA if --deepdive transcripts exist) using the provider(s) "
                        "configured in .env — see scripts/llm_provider.py. Costs tokens.")
    r.set_defaults(func=cmd_run)

    st = sub.add_parser("status", help="show what's done/stale/missing for a project (read-only)")
    st.add_argument("project", help="project folder (or its competitors.txt)")
    st.set_defaults(func=cmd_status)

    rs = sub.add_parser("resume", help="continue a stopped/closed run — replays the remembered args; "
                                       "safe to call repeatedly (idempotent)")
    rs.add_argument("project", help="project folder that was `run` at least once before")
    rs.set_defaults(func=cmd_resume)

    w = sub.add_parser("watch", help="watch cycle: re-scan views + demand + snapshot/diff signals "
                                     "(monitoring — cheap subset, no LLM, no report rebuild)")
    w.add_argument("project", help="project folder that has competitors.txt")
    w.set_defaults(func=cmd_watch)

    lm = sub.add_parser("llm", help="run one or all pending LLM agents on an existing project — "
                                    "flexible per-stage provider control (e.g. GLM for the Auditor)")
    lm.add_argument("project", help="project folder that was `run` at least once before")
    lm.add_argument("--agent", choices=["namer", "auditor", "plan", "dna", "summary"], default=None,
                    help="run just this agent (default: run namer/auditor/plan/summary, whichever are pending)")
    lm.add_argument("--provider", default=None,
                    help="override LLM_PROVIDER for this invocation (anthropic|openai|glm|grok|custom)")
    lm.add_argument("--auditor-provider", default=None,
                    help="override AUDITOR_LLM_PROVIDER for this invocation — keep this DIFFERENT "
                         "from --provider for a real critique, not a rubber stamp")
    lm.set_defaults(func=cmd_llm)

    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        print(cyan(BANNER)); ap.print_help(); return
    args.func(args)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(yellow("\ninterrupted — progress is saved; re-run to continue.")); sys.exit(130)
