"""STEP 15 [PY] — FETCH TRANSCRIPTS via transcriptapi.com (for the DNA deep-dive).
Usage: python3 15_fetch_transcripts.py [workdir] [list.md | slug]   Re-run until it prints DONE.

Reads a 00-danh-sach-video-<slug>.md (from S14) — or, if none, the strongest valid outliers in
videos.json — and downloads each transcript into  transcripts/NN_<videoId>.txt  (resumable: it
checkpoints after every video, so a kill / timeout / credit-out just needs a re-run).

API (transcriptapi.com):
  GET https://transcriptapi.com/api/v2/youtube/transcript?video_url=<id>&format=text&include_timestamp=false
  Header:  Authorization: Bearer <TRANSCRIPT_API_KEY>          (1 credit per successful call)
  200 ok · 404 no transcript (skip) · 402 no credits (stop) · 401 bad key (stop) · 429/408/503 retry.

The key is read from TRANSCRIPT_API_KEY (real env first, then the tool's .env file).
COST GUARD: this spends 1 credit per video — it prints the estimate before fetching.
"""
import sys, os, re, json, time
import requests
from _common import compute_outliers, get_env, jload, jsave, safe_filename, winners, get_scan_time

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
ARG  = sys.argv[2] if len(sys.argv) > 2 else None
def p(f): return os.path.join(WORK, f)

TIME_BUDGET = 9999            # set ~30 in a 45s sandbox; loop until DONE
MAX_VIDEOS  = 30
ENDPOINT    = "https://transcriptapi.com/api/v2/youtube/transcript"

KEY = get_env("TRANSCRIPT_API_KEY", WORK)
if not KEY:
    raise SystemExit("No TRANSCRIPT_API_KEY found. Put it in the tool's .env "
                     "(TRANSCRIPT_API_KEY=sk_...) or export it, then re-run.")

VID_RE = re.compile(r"(?:youtu\.be/|v=|/shorts/)([0-9A-Za-z_\-]{11})")
def extract_ids(text):
    ids = []
    for line in text.splitlines():
        m = VID_RE.search(line)
        if m: ids.append(m.group(1)); continue
        # bare-id fallback: only when the WHOLE line is exactly an 11-char id — a substring match
        # would treat ordinary 11-letter words ("Documentary") as video ids and waste API calls (V22)
        s = line.strip()
        if re.fullmatch(r"[0-9A-Za-z_\-]{11}", s): ids.append(s)
    seen = set(); out = []
    for i in ids:
        if i not in seen: seen.add(i); out.append(i)
    return out

# ---- title map (so transcripts are saved under the VIDEO TITLE, not an opaque id) ----
titles = {}
try:
    _vids = json.load(open(p("videos.json"), encoding="utf-8"))
    titles = {x["videoId"]: x.get("title", "") for x in _vids}
except Exception:
    _vids = []

# ---- resolve the video list ----
ids = []
listfile = None
if ARG and os.path.isfile(os.path.join(WORK, ARG)): listfile = os.path.join(WORK, ARG)
elif ARG and os.path.isfile(ARG): listfile = ARG
else:
    # explicit slug -> its md; else the newest 00-danh-sach-video-*.md
    cands = []
    if ARG and os.path.exists(p(f"00-danh-sach-video-{ARG}.md")): cands = [p(f"00-danh-sach-video-{ARG}.md")]
    else:
        import glob
        cands = sorted(glob.glob(p("00-danh-sach-video-*.md")), key=os.path.getmtime, reverse=True)
    if cands: listfile = cands[0]

if listfile:
    ids = extract_ids(open(listfile, encoding="utf-8").read())
    print(f"video list: {os.path.basename(listfile)} -> {len(ids)} ids")
else:
    # fallback: strongest winners straight from videos.json (shared rule, pinned time — V7/V12)
    compute_outliers(_vids, get_scan_time(WORK))
    strong = sorted(winners(_vids), key=lambda x: -x.get("excess", 0))[:MAX_VIDEOS]
    ids = [x["videoId"] for x in strong]
    print(f"no list file — using top {len(ids)} valid outliers from videos.json")

ids = ids[:MAX_VIDEOS]
# transcripts go into the project's readable Transcripts/ folder (orchestrator passes it via env);
# fall back to WORK/transcripts when run standalone.
TDIR = os.environ.get("NICHE_TRANSCRIPTS_DIR") or p("transcripts")
os.makedirs(TDIR, exist_ok=True)
index = jload(os.path.join(TDIR, "index.json"), {})     # videoId -> {file, status, title}
done = {vid for vid, meta in index.items() if meta.get("status") in ("ok", "no_transcript")}
todo = [i for i in ids if i not in done]
print(f"COST GUARD — {len(todo)} transcripts to fetch (~{len(todo)} credits); {len(done)} already done.")

sess = requests.Session()
sess.headers["Authorization"] = f"Bearer {KEY}"
start = time.time()

def _detail(r):
    """transcriptapi.com puts the ACTIONABLE reason in detail.message/reason/action_url —
    e.g. 402 can mean 'no credits left' OR 'no active paid plan yet' (different fixes)."""
    try:
        d = r.json().get("detail", {})
        if isinstance(d, dict):
            parts = [d.get("message") or ""]
            if d.get("action_url"): parts.append(f"-> {d['action_url']}")
            return " ".join(p for p in parts if p).strip()
    except Exception:
        pass
    return (r.text or "")[:200]

def fetch(vid, retries=4):
    for attempt in range(retries):
        try:
            r = sess.get(ENDPOINT, params={"video_url": vid, "format": "text",
                                           "include_timestamp": "false"}, timeout=40)
        except Exception:
            time.sleep(2); continue
        if r.status_code == 200: return ("ok", r.text)
        if r.status_code == 404: return ("no_transcript", "")
        if r.status_code == 402: return ("payment_required", _detail(r))
        if r.status_code == 401: return ("unauthorized", _detail(r))
        if r.status_code in (429, 408, 503):
            time.sleep(2 * (attempt + 1) + (5 if r.status_code == 429 else 0)); continue
        return (f"http_{r.status_code}", _detail(r))
    return ("retry_exhausted", "")

idx_path = os.path.join(TDIR, "index.json")
n_ok = sum(1 for m in index.values() if m.get("status") == "ok")
for k, vid in enumerate(todo):
    if time.time() - start > TIME_BUDGET:
        print("PAUSE — re-run to continue"); sys.exit(0)
    status, body = fetch(vid)
    if status == "payment_required":
        print(f"STOP — 402 Payment Required on this TRANSCRIPT_API_KEY: {body or 'no reason given'}")
        print("       Fix at https://transcriptapi.com/billing, then re-run (already-fetched transcripts are kept).")
        jsave(idx_path, index); sys.exit(0)
    if status == "unauthorized":
        print(f"STOP — 401 unauthorized: {body or 'check TRANSCRIPT_API_KEY in .env'}")
        jsave(idx_path, index); sys.exit(1)
    if status == "ok":
        seq = len([m for m in index.values() if m.get("status") == "ok"]) + 1
        title = titles.get(vid, "")
        fn = f"{seq:02d} - {safe_filename(title) if title else vid}.txt"
        open(os.path.join(TDIR, fn), "w", encoding="utf-8").write(body)
        index[vid] = {"file": fn, "status": "ok", "title": title}
        n_ok += 1
        print(f"  ok  {(title or vid)[:50]:50}  -> {fn}  ({len(body):,} chars)")
    else:
        index[vid] = {"file": None, "status": status, "title": titles.get(vid, "")}
        print(f"  --  {(titles.get(vid) or vid)[:50]:50}  {status}")
    jsave(idx_path, index)                              # checkpoint after every video
    time.sleep(0.25)                                    # stay well under 300/min

no_transcript = sum(1 for m in index.values() if m.get("status") == "no_transcript")
errors = sum(1 for m in index.values() if m.get("status") not in ("ok", "no_transcript"))
print(f"DONE — {n_ok} transcripts saved, {no_transcript} without transcript, {errors} errors -> {os.path.basename(TDIR)}/  (index.json)")
