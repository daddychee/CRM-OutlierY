"""Shared helpers + OUTLIER MODEL v3 for the Niche Report pipeline.
Language- and niche-agnostic. Single source of truth for OX; see references/outlier_method.md.

VENDORED vào Radary 08/07/2026 từ tool `Niche Report` (scripts/_common.py).
Thay đổi DUY NHẤT so với bản gốc: requests → urllib (stdlib) trong API.get —
giữ nguyên toàn bộ OUTLIER MODEL v3 đã kiểm chứng."""
import json, os, re, time, statistics
import urllib.request, urllib.parse, urllib.error
from collections import defaultdict

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
            url=f"https://www.googleapis.com/youtube/v3/{endpoint}?"+urllib.parse.urlencode(params, doseq=True)
            try:
                with urllib.request.urlopen(url, timeout=25) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                try: reason=json.load(e).get("error",{}).get("errors",[{}])[0].get("reason","")
                except Exception: reason=""
                if e.code==403 and ("quota" in reason.lower() or reason in
                    ("quotaExceeded","dailyLimitExceeded","rateLimitExceeded")):
                    self.i+=1; continue
                return {"_error": reason or e.code, "_status": e.code}
            except Exception: time.sleep(1); continue
        return {"_error":"exhausted"}

def jload(p, default): return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default
def jsave(p, obj): json.dump(obj, open(p,"w",encoding="utf-8"), ensure_ascii=False)

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
AGE_EDGES       = [7,14,30,90,180,365,10**9]  # day upper-edges for the maturity curve

def _fmt(s):
    if s is None: return "Long"
    if s<=SHORT_MAX_SEC: return "Short"
    if s<=MID_MAX_SEC:  return "Mid"
    return "Long"

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

def compute_outliers(videos, now):
    """Adds to each video: dur_s, fmt, age, scale, expected, ox, excess, nbase,
    scope(primary/fresh/legacy), valid, confidence(high/medium/low), bracket, scale_borrowed.
    OX_v3 = views / (channel_scale * shape(age)).  shape = niche maturity curve per format."""
    from datetime import datetime
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
        bi=_bidx(age if age else MATURITY_DAYS)
        if (fmt,bi) in shape: return shape[(fmt,bi)]
        for d in range(1,len(AGE_EDGES)):
            for c in (bi-d,bi+d):
                if (fmt,c) in shape: return shape[(fmt,c)]
        return 1.0

    # per-channel floors (Long-form matured recent views drive the floor)
    chan_m=defaultdict(list)
    for x in videos:
        if rec(x) and mature(x): chan_m[x["channelId"]].append(x["viewCount"])
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
        sh=shape_of(x["fmt"], x["age"]); exp=sc*sh if sc else 0
        x["scale"]=round(sc) if sc else 0
        x["expected"]=round(exp) if exp else 0
        x["ox"]=round(x["viewCount"]/exp,2) if exp else 0
        x["excess"]=round(x["viewCount"]-exp) if exp else 0
        x["nbase"]=nbase.get(k,0); x["scale_borrowed"]=borrowed
        x["scope"]=("primary" if (rec(x) and mature(x)) else "fresh" if rec(x) else "legacy")
        cm=chan_m.get(x["channelId"],[])
        min_abs = max(ABS_FLOOR, _pct(cm,25)) if cm else ABS_FLOOR
        min_base= 0.2*(statistics.median(cm) if cm else niche_med)
        x["valid"]=(x["nbase"]>=MIN_BASE_VIDEOS and x["viewCount"]>=min_abs
                    and sc>=min_base and not borrowed and x["scope"]!="legacy")
        x["confidence"]=("low" if (x["nbase"]<12 or x["scope"]=="fresh" or borrowed)
                         else "medium" if x["nbase"]<20 else "high")
        o=x["ox"]
        x["bracket"]=(">10x Viral" if o>=10 else "5-10x Strong" if o>=5
                      else "2-5x Above" if o>=2 else "<2x Normal")
    return videos
