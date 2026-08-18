"""Shared helpers + OUTLIER MODEL v3 for the Niche Report pipeline.
Language- and niche-agnostic. Single source of truth for OX; see references/outlier_method.md."""
import requests, json, os, re, time, statistics
from collections import defaultdict

# ============================ PROJECT LAYOUT (single source of truth) ============================
DATA_DIRNAME        = "niche-data"    # all intermediate JSON + checkpoints + logs live here
REPORT_DIRNAME      = "Report"        # the deliverable .xlsx
TRANSCRIPTS_DIRNAME = "Transcripts"   # readable, title-named transcript .txt files

def safe_filename(s, maxlen=90):
    """Turn a video title into a filesystem-safe file name (keeps it readable, not a code)."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)   # strip characters illegal on Win/mac/Linux
    s = s.strip(". ")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip()
    return s or "untitled"

# ============================ INPUT / API ============================
def load_input(path):
    txt = open(path, encoding="utf-8").read()
    keys = re.findall(r"AIza[0-9A-Za-z_\-]{35}", txt)
    chans = []
    for line in txt.splitlines():
        line = line.strip()
        m = re.search(r"/channel/(UC[0-9A-Za-z_\-]{22})", line)
        if m: chans.append(("id", m.group(1))); continue
        m = re.search(r"youtube\.com/@([0-9A-Za-z_.\-]+)", line) or re.search(r"(?:^|\s)@([0-9A-Za-z_.\-]+)", line)
        if m: chans.append(("handle", m.group(1))); continue
        m = re.search(r"/user/([0-9A-Za-z_\-]+)", line)
        if m: chans.append(("user", m.group(1))); continue
        m = re.search(r"/c/([0-9A-Za-z_\-]+)", line)
        if m: chans.append(("custom", m.group(1))); continue
        if re.fullmatch(r"UC[0-9A-Za-z_\-]{22}", line): chans.append(("id", line))
    seen=set(); out=[]
    for c in chans:
        if c not in seen: seen.add(c); out.append(c)
    if not keys: raise SystemExit("No YouTube API key (AIza...) found in input file.")
    return keys, out

class API:
    def __init__(self, keys): self.keys=keys; self.i=0
    def _key(self): return self.keys[self.i % len(self.keys)]
    def get(self, endpoint, params, retries=8):
        for _ in range(retries):
            params["key"]=self._key()
            try: r=requests.get(f"https://www.googleapis.com/youtube/v3/{endpoint}", params=params, timeout=25)
            except Exception: time.sleep(1); continue
            if r.status_code==200: return r.json()
            try: reason=r.json().get("error",{}).get("errors",[{}])[0].get("reason","")
            except Exception: reason=r.text[:80]
            if r.status_code==403 and ("quota" in reason.lower() or reason in
                ("quotaExceeded","dailyLimitExceeded","rateLimitExceeded")):
                self.i+=1; continue
            return {"_error": reason or r.status_code, "_status": r.status_code}
        return {"_error":"exhausted"}

def jload(p, default): return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default
def jsave(p, obj, indent=1): json.dump(obj, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=indent)

def parse_duration(d):
    if not d: return None
    m=re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m: return None
    h,mn,s=(int(x) if x else 0 for x in m.groups())
    return h*3600+mn*60+s

# ============================ OUTLIER MODEL v3 ============================
# Tunable (all printed into the report for transparency):
SHORT_MAX_SEC   = 180      # <=180s = Short (YouTube Shorts max since Oct 2024)
MID_MAX_SEC     = 1200     # 180s..1200s = Mid (3-20 min); >1200s = Long
RECENT_WINDOW_MONTHS = 18  # baseline only from videos this recent (avoids growth-era mixing)
MATURITY_DAYS   = 45       # younger than this = "fresh", not used as primary baseline
TRIM_TOP_FRAC   = 0.10     # drop top decile when estimating channel scale (anti self-inflation)
MIN_BASE_VIDEOS = 8        # min same-format recent-matured videos for a reliable baseline
ABS_FLOOR       = 2000     # hard floor for MIN_ABS_VIEWS even if channel P25 is lower
# 45 is an edge on purpose: MATURITY_DAYS=45 must not fall INSIDE a bucket, or the 30-90d bucket
# would mix still-growing (30-45d) with matured (45-90d) videos and systematically inflate the OX
# of 45-90d videos (audit V11).
AGE_EDGES       = [7,14,30,45,90,180,365,10**9]  # day upper-edges for the maturity curve
OUTLIER_OX      = 3        # the "winner" bar used across all stages (S3/S4/S5/S9/S11/S14/S18)

def _fmt(s):
    if s is None: return "Long"
    if s<=SHORT_MAX_SEC: return "Short"
    if s<=MID_MAX_SEC:  return "Mid"
    return "Long"

def shorts_gate_on(work=None):
    """HARD SHORTS GATE (user request 2026-07): Shorts (<=SHORT_MAX_SEC) are excluded from the ENTIRE
    analysis — different distribution mechanics (Shorts feed) make their view counts incomparable to
    long-form, and the user's strategy is long-form only. Default ON; set SHORTS_GATE=off in .env to
    include Shorts again (e.g. for a Shorts-first niche)."""
    return str(get_env("SHORTS_GATE", work, "on")).lower() not in ("off", "0", "false", "no")

def _bidx(age):
    for i,e in enumerate(AGE_EDGES):
        if age<=e: return i
    return len(AGE_EDGES)-1

def _trimmed_median(vals, exclude=None):
    v=sorted(vals)
    if exclude is not None:
        try: v.remove(exclude)
        except ValueError: pass
    if not v: return None
    k=int(len(v)*TRIM_TOP_FRAC)
    if k>0 and len(v)-k>=1: v=v[:len(v)-k]
    return statistics.median(v) if v else None

def _pct(vals,p):
    if not vals: return 0
    v=sorted(vals); i=min(len(v)-1, int(p/100.0*len(v))); return v[i]

def _ranks(xs):
    """Fractional (average) ranks — ties share the mean rank. For Spearman."""
    order=sorted(range(len(xs)), key=lambda i:xs[i])
    ranks=[0.0]*len(xs); i=0
    while i<len(order):
        j=i
        while j+1<len(order) and xs[order[j+1]]==xs[order[i]]: j+=1
        avg=(i+j)/2.0+1
        for k in range(i,j+1): ranks[order[k]]=avg
        i=j+1
    return ranks

def spearman(a,b):
    """Spearman rank correlation, pure-Python. Returns None if <3 usable pairs."""
    pairs=[(x,y) for x,y in zip(a,b) if x is not None and y is not None]
    if len(pairs)<3: return None
    ra=_ranks([p[0] for p in pairs]); rb=_ranks([p[1] for p in pairs])
    n=len(pairs); ma=sum(ra)/n; mb=sum(rb)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(ra,rb))
    da=sum((x-ma)**2 for x in ra)**0.5; db=sum((y-mb)**2 for y in rb)**0.5
    if da==0 or db==0: return None
    return round(num/(da*db),3)

def channel_age_days(iso, now):
    """Age in days from an ISO timestamp; None if unparseable."""
    from datetime import datetime
    try:
        dt=datetime.fromisoformat((iso or "").replace("Z","+00:00"))
        return max((now-dt).total_seconds()/86400, 0.0)
    except Exception:
        return None

_ENV_LOADED = {}  # cache: work-dir → parsed dict (avoid re-reading .env on every get_env call)

def load_env(start=None):
    """Read a .env file (KEY=VALUE lines) from the tool root and merge into os.environ (without
    overwriting existing env vars). Returns the parsed dict. Looks in this file's parent-of-parent
    (the tool root) and the given start dir. Cached per work-dir to avoid repeated file I/O."""
    import os
    cache_key = start or "_default"
    if cache_key in _ENV_LOADED: return _ENV_LOADED[cache_key]
    parsed={}
    roots=[]
    here=os.path.dirname(os.path.abspath(__file__))
    roots.append(os.path.dirname(here))          # tool root (…/Niche Research)
    if start: roots.append(os.path.abspath(start))
    for root in roots:
        path=os.path.join(root,".env")
        if not os.path.exists(path): continue
        for line in open(path,encoding="utf-8"):
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1); k=k.strip(); v=v.strip().strip('"').strip("'")
            parsed[k]=v
            os.environ.setdefault(k,v)
    _ENV_LOADED[cache_key] = parsed
    return parsed

def get_env(name, work=None, default=None):
    """Get a config value from the real environment, else from a .env file (cached)."""
    import os
    if os.environ.get(name): return os.environ[name]
    load_env(work)
    return os.environ.get(name, default)

def compute_outliers(videos, now):
    """Adds to each video: dur_s, fmt, age, scale, expected, ox, excess, nbase,
    scope(primary/fresh/legacy), valid, confidence(high/medium/low), bracket, scale_borrowed.
    OX_v3 = views / (channel_scale * shape(age)).  shape = niche maturity curve per format.
    SHORTS GATE: when on (default), Shorts are removed from the list IN PLACE before anything is
    computed — every caller's list shrinks, so Shorts can't leak into any stage (evidence, demand,
    HHI, clustering, bets, report)."""
    from datetime import datetime
    if shorts_gate_on():
        n0 = len(videos)
        videos[:] = [x for x in videos if _fmt(parse_duration(x.get("duration"))) != "Short"]
        blocked = n0 - len(videos)
        if blocked:
            print(f"  SHORTS GATE: chặn {blocked}/{n0} video Short (<= {SHORT_MAX_SEC}s) khỏi toàn bộ phân tích"
                  + (" — CẢNH BÁO: >50% pool là Short, niche này có vẻ Shorts-first (SHORTS_GATE=off để gỡ)"
                     if blocked > n0/2 else ""))
    cutoff = RECENT_WINDOW_MONTHS*30.44
    for x in videos:
        s=parse_duration(x.get("duration")); x["dur_s"]=s; x["fmt"]=_fmt(s)
        try:
            dt=datetime.fromisoformat((x.get("publishedAt") or "").replace("Z","+00:00"))
            x["age"]=max((now-dt).total_seconds()/86400, 0.5)
        except Exception: x["age"]=None
    rec    = lambda x: x["age"] is not None and x["age"]<=cutoff
    mature = lambda x: x["age"] is not None and x["age"]>=MATURITY_DAYS

    # Pass 1: rough scale per (channel,fmt) from recent+matured (trimmed)
    grp=defaultdict(list)
    for x in videos:
        if rec(x) and mature(x): grp[(x["channelId"],x["fmt"])].append(x["viewCount"])
    rough={k:_trimmed_median(vs) for k,vs in grp.items()}
    nbase={k:len(vs) for k,vs in grp.items()}

    # maturity curve shape(fmt,bucket) = median(views/rough_scale) over recent videos
    bvals=defaultdict(list)
    for x in videos:
        if not rec(x): continue
        sc=rough.get((x["channelId"],x["fmt"]))
        if sc: bvals[(x["fmt"], _bidx(x["age"]))].append(x["viewCount"]/sc)
    shape={k:statistics.median(v) for k,v in bvals.items() if len(v)>=5}
    def shape_of(fmt,age):
        """Returns (shape_value, source). source records HOW the value was obtained so the report can
        say what fraction of videos got an exact age-bucket vs a silent fallback (audit V13):
        exact = this (fmt, age-bucket) had >=5 samples · neighbor = borrowed a nearby bucket ·
        flat = no bucket at all -> 1.0 (expected loses its age adjustment entirely)."""
        bi=_bidx(age if age else MATURITY_DAYS)
        if (fmt,bi) in shape: return shape[(fmt,bi)], "exact"
        for d in range(1,len(AGE_EDGES)):
            for c in (bi-d,bi+d):
                if (fmt,c) in shape: return shape[(fmt,c)], "neighbor"
        return 1.0, "flat"

    # per-channel PER-FORMAT floors — split by format so a Short on a mostly-Long channel
    # doesn't get gated by Long-form P25 views (cross-format floor was biasing Shorts low).
    chan_m=defaultdict(list)
    for x in videos:
        if rec(x) and mature(x): chan_m[(x["channelId"], x["fmt"])].append(x["viewCount"])
    all_sc=[s for s in rough.values() if s]
    niche_med=statistics.median(all_sc) if all_sc else 0

    for x in videos:
        k=(x["channelId"],x["fmt"]); vals=grp.get(k,[])
        if rec(x) and mature(x):
            sc=_trimmed_median(vals, exclude=x["viewCount"])  # leave-one-out
        else:
            sc=rough.get(k)
        borrowed=False
        if not sc: sc=niche_med or 1; borrowed=True
        sh,sh_src=shape_of(x["fmt"], x["age"]); exp=sc*sh if sc else 0
        x["shape_src"]=sh_src
        x["scale"]=round(sc) if sc else 0
        x["expected"]=round(exp) if exp else 0
        x["ox"]=round(x["viewCount"]/exp,2) if exp else 0
        x["excess"]=round(x["viewCount"]-exp) if exp else 0
        x["nbase"]=nbase.get(k,0); x["scale_borrowed"]=borrowed
        x["scope"]=("primary" if (rec(x) and mature(x)) else "fresh" if rec(x) else "legacy")
        cm_fmt=chan_m.get((x["channelId"],x["fmt"]),[])
        min_abs = max(ABS_FLOOR, _pct(cm_fmt,25)) if cm_fmt else ABS_FLOOR
        # (removed the sc>=0.2*channel_median gate: it compared a channel's scale to a fraction of
        #  its OWN median, so it was ~always true — inert — and a niche-relative version would wrongly
        #  drop the small-channel outliers that crackability is specifically meant to detect.)
        x["valid"]=(x["nbase"]>=MIN_BASE_VIDEOS and x["viewCount"]>=min_abs
                    and not borrowed and x["scope"]!="legacy")
        x["confidence"]=("low" if (x["nbase"]<12 or x["scope"]=="fresh" or borrowed)
                         else "medium" if x["nbase"]<20 else "high")
        # EARLY-CONFIRMED (audit V7, user's rule): a FRESH video that ALREADY reaches k x the channel's
        # MATURED median (scale). Views only accumulate, so its eventual mature OX is >= k no matter how
        # noisy the young-age shape is — a lower bound, immune to shape misfit. These count as full
        # evidence; other fresh videos are watch-only ("TÍN HIỆU SỚM" in the report), never "normal".
        x["ox_lb"]=round(x["viewCount"]/sc,2) if (x["scope"]=="fresh" and sc) else None
        x["early"]=bool(x["valid"] and x["scope"]=="fresh" and sc and x["viewCount"]>=OUTLIER_OX*sc)
        o=x["ox"]
        x["bracket"]=(">10x Viral" if o>=10 else "5-10x Strong" if o>=5
                      else "2-5x Above" if o>=2 else "<2x Normal")
    return videos

# ---------------- evidence universes (ONE definition for every stage — audit V7) ----------------
def winners(videos, min_ox=OUTLIER_OX):
    """Evidence-grade outliers: valid PRIMARY videos with OX>=min_ox, PLUS fresh videos already at
    min_ox x the channel's matured median (lower-bound certain — see compute_outliers 'early').
    Requires compute_outliers() to have run."""
    return [x for x in videos
            if (x.get("valid") and x.get("scope")=="primary" and x.get("ox",0)>=min_ox)
            or (x.get("valid") and x.get("scope")=="fresh" and (x.get("scale") or 0)>0
                and x.get("viewCount",0)>=min_ox*x["scale"])]

def normals(videos):
    """Evidence-grade baseline: valid PRIMARY videos with OX<2. Fresh videos are NEVER 'normal' —
    they simply haven't had time yet (they'd poison the lift denominator)."""
    return [x for x in videos if x.get("valid") and x.get("scope")=="primary" and x.get("ox",0)<2]

def compute_newcomers(outlier_channel_ids, chinfo, now, young_months=24):
    """Newcomer channels among a set: BOTH small (subs <= median of the outlier channels' subs) AND
    young (< young_months). One implementation shared by S5 (global) and S9 (per-cluster) so the
    definition can't drift. Returns (newcomer_id_set, median_subs)."""
    def subs_of(cid):
        try: return int(chinfo.get(cid, {}).get("subs") or 0)
        except Exception: return 0
    sub_vals=[subs_of(c) for c in outlier_channel_ids if subs_of(c)>0] or [subs_of(c) for c in chinfo] or [0]
    med=statistics.median(sub_vals)
    newc=set()
    for c in outlier_channel_ids:
        a=channel_age_days(chinfo.get(c, {}).get("publishedAt"), now)
        if a is not None and a<young_months*30.44 and subs_of(c)<=med:
            newc.add(c)
    return newc, med

def get_scan_time(work):
    """The pinned 'now' for compute_outliers: scan completion time (scan_meta.json, written by S1),
    else videos.json mtime, else wall clock. Pinning makes OX/scope/valid IDENTICAL across every
    stage and every rebuild of the same scan — no more threshold drift when a project is resumed
    days later (audit V12)."""
    from datetime import datetime, timezone
    try:
        iso=json.load(open(os.path.join(work,"scan_meta.json"),encoding="utf-8")).get("completed_at")
        if iso: return datetime.fromisoformat(iso.replace("Z","+00:00"))
    except Exception: pass
    try:
        return datetime.fromtimestamp(os.path.getmtime(os.path.join(work,"videos.json")), tz=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

# ---------------- shared tokenizer (audit V5: 5 hand-copied stop-lists had drifted apart) ----------------
BASE_STOP=set(("the of in on at to for and or but with from by as is are was were be been being this that "
    "these those it its his her your you we they i he she them us our my me do does did has have had will "
    "would can could should may might must not no nor so than then too very just about into onto over under "
    "out up down off again more most some such only own same s t re ve ll d m o when which who what why how "
    "where vs com de la el en un una los las del al le les des et und der die das que y a an").split())

def tokenize(t, minlen=3, stop=None):
    """Lowercase, strip punctuation, drop short tokens + stopwords. THE one implementation for
    S3/S5/S11/S18/evidence-pack. Pass a custom stop-set (e.g. BASE_STOP | dynamic) when needed."""
    s=stop if stop is not None else BASE_STOP
    return [w for w in re.sub(r"[^\w\s]"," ",(t or "").lower(),flags=re.UNICODE).split()
            if len(w)>=minlen and w not in s]
