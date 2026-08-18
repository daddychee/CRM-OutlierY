"""STEP 3 — Comment information-gap mining. Niche- & language-agnostic (NO fixed categories).
Usage: python3 3_comments.py <competitors.txt> [workdir]   Resumable fetch -> comments.json, gaps.json
Themes are DISCOVERED from the questions themselves (data-driven), so this works for any niche/language."""
import sys, time, re, json
from collections import Counter, defaultdict
from _common import load_input, API, jload, jsave, compute_outliers, winners, get_scan_time
INPUT=sys.argv[1] if len(sys.argv)>1 else "competitors.txt"
WORK =sys.argv[2] if len(sys.argv)>2 else "."
TIME_BUDGET=9999          # set ~20 in a 45s sandbox; re-run until DONE
COMMENTS_PER_VIDEO=100
MAX_VIDEOS=400            # cap comment-fetch to the strongest outliers (by excess) for huge niches
# Fetch both relevance-sorted AND time-sorted comments so we catch BOTH highly-liked questions
# (signal strength) AND recent questions (emerging gaps). The relevance batch catches established
# demand; the time batch catches trending topics before they accumulate likes.
FETCH_TIME_ORDERED = True   # set False to skip the time-ordered batch (saves quota on large niches)
def p(f): return f"{WORK}/{f}"
keys,_=load_input(INPUT); api=API(keys)
videos=json.load(open(p("videos.json"),encoding="utf-8"))
compute_outliers(videos, get_scan_time(WORK))     # pinned scan time (V12)
big=winners(videos, min_ox=10)                    # valid PRIMARY >=10x + early-confirmed fresh (V7)
big.sort(key=lambda x:-x.get("excess",0))         # prioritise absolute reach, not raw OX
big=big[:MAX_VIDEOS]
print(f"{len(big)} valid >=10x outliers (top {MAX_VIDEOS} by excess); est comments ~{sum(x['commentCount'] for x in big):,}")

# ---- fetch (resumable) ----
done=set(jload(p("_done_comments.json"),[])); comments=jload(p("comments.json"),{}); start=time.time()
todo=[x for x in big if x["videoId"] not in done]
print(f"fetching comments for {len(todo)} videos ({len(done)} already done)...")
n_fetched=0
for k,x in enumerate(todo,1):
    vid=x["videoId"]
    if time.time()-start>TIME_BUDGET:
        jsave(p("comments.json"),comments); jsave(p("_done_comments.json"),list(done))
        print(f"PAUSE — {n_fetched}/{len(todo)} fetched this run — re-run to continue"); sys.exit(0)
    if x.get("commentCount",0)<5: done.add(vid); continue
    d=api.get("commentThreads",{"part":"snippet","videoId":vid,"maxResults":COMMENTS_PER_VIDEO//2 if FETCH_TIME_ORDERED else COMMENTS_PER_VIDEO,"order":"relevance","textFormat":"plainText"})
    if FETCH_TIME_ORDERED and not d.get("_error"):
        d2=api.get("commentThreads",{"part":"snippet","videoId":vid,"maxResults":COMMENTS_PER_VIDEO//2,"order":"time","textFormat":"plainText"})
        if not d2.get("_error"):
            existing_ids = set(i["snippet"]["topLevelComment"]["id"] for i in d.get("items",[]))
            for item in d2.get("items",[]):
                tid = item["snippet"]["topLevelComment"]["id"]
                if tid not in existing_ids:
                    d.setdefault("items",[]).append(item)
    if d.get("_error"):
        if d.get("_error")=="exhausted":
            # all keys hit quota: do NOT mark done (retry next run once quota resets / a key is added)
            jsave(p("comments.json"),comments); jsave(p("_done_comments.json"),list(done))
            print(f"PAUSE — quota exhausted on all keys after {n_fetched}/{len(todo)} — add a key or wait, then re-run")
            sys.exit(0)
        done.add(vid); continue   # video-level error (e.g. comments disabled) — skip permanently
    try:
        comments[vid]=[{"t":i["snippet"]["topLevelComment"]["snippet"].get("textDisplay",""),
                        "like":i["snippet"]["topLevelComment"]["snippet"].get("likeCount",0)} for i in d.get("items",[])]
    except Exception: comments[vid]=comments.get(vid,[])
    done.add(vid); n_fetched+=1
    if k%10==0 or k==len(todo):
        print(f"  {k}/{len(todo)} videos processed ({n_fetched} fetched, {sum(len(c) for c in comments.values()):,} comments so far)")
        sys.stdout.flush()
        jsave(p("comments.json"),comments); jsave(p("_done_comments.json"),list(done))  # periodic checkpoint
jsave(p("comments.json"),comments); jsave(p("_done_comments.json"),list(done))
need=[x["videoId"] for x in big if x.get("commentCount",0)>=5]
if sum(1 for q in need if q in done)<len(need):
    print(f"fetched {len(comments)} videos so far — re-run to continue"); sys.exit(0)

# ---- detect genuine viewer QUESTIONS (language-agnostic) ----
bigmap={x["videoId"]:x for x in big}
QMARK="?؟？;।"                                   # question marks across scripts (incl. Greek ; , Arabic ؟)
def clean(t): return re.sub(r"\s+"," ", re.sub(r"http\S+"," ", re.sub(r"<[^>]+>"," ", t or ""))).strip()
def sents(t): return re.split(r"(?<=[.!?؟।])\s+|\n+", t)
# Engagement/meta "questions" are NOT information gaps ("who else is here because of the thumbnail?",
# "can you pin this?"...) — they poison theme mining, so drop them at the source (user request 2026-07).
ENGAGE=re.compile(
    r"(who else|anyone else|anybody else|is it just me|am i the only|who'?s (still )?(here|watching)"
    r"|who is (still )?(here|watching)|who (came|is here|s here) (from|because|after)|why am i (here|watching)"
    r"|how many (people|of us|of you)|can (you|u) (pin|heart)|pin (me|this)|notification (squad|gang)"
    r"|like if|who remembers|who( ?i)s watching (this )?in \d{4}|what time is it for you"
    r"|ai còn xem|còn ai xem|có ai (đang )?(xem|coi)|điểm danh)", re.I)
def is_q(s):
    if len(s)<15 or len(s)>200: return False        # <15 chars = "First?", "Why?" — no content
    if not any(s.rstrip().endswith(q) for q in QMARK): return False  # rely on '?'-type marks => works any language
    if re.search(r"(subscrib|comment below|like if|@\w)", s.lower()): return False  # drop obvious CTA/mentions
    if ENGAGE.search(s): return False               # engagement bait, not a real info need
    return True
questions=[]
for vid,cs in comments.items():
    for c in cs:
        for s in sents(clean(c["t"])):
            s=s.strip()
            if is_q(s): questions.append((s, c.get("like",0), vid))

# ---- DATA-DRIVEN themes: cluster questions by their most distinctive shared phrase ----
def toks(s): return [w for w in re.sub(r"[^\w\s]"," ",s.lower(),flags=re.UNICODE).split() if len(w)>2]
df=Counter()
for s,_,_ in questions:
    for w in set(toks(s)): df[w]+=1
# generic-question stoplist emerges as words in >8% of questions; keep content words
STOP={w for w,c in df.items() if c>0.08*max(len(questions),1)}
# a question with ZERO content words left ("what is this?", "how do you do that?") carries no niche
# signal — drop it so themes AND top_questions only contain questions about the SUBJECT (user request)
_pre=len(questions)
questions=[(s,l,vid) for (s,l,vid) in questions if any(w not in STOP for w in toks(s))]
if _pre-len(questions): print(f"filtered {_pre-len(questions)} content-free/engagement questions")
NQ=max(len(questions),1)
ngc=Counter(); ngq=defaultdict(list)
for s,like,vid in questions:
    tk=[w for w in toks(s) if w not in STOP]
    grams=set()
    for n in (2,3):
        for i in range(len(tk)-n+1): grams.add(" ".join(tk[i:i+n]))
    for g in grams: ngc[g]+=1; ngq[g].append((like,s,vid))
themes=[]
used=set()
for g,c in ngc.most_common():
    if c<4: break
    if any(g in t or t in g for t in used): continue   # de-dup overlapping phrases
    used.add(g)
    exs=sorted(ngq[g],key=lambda z:-z[0])[:8]
    themes.append({"theme":g,"count":c,"pct":round(c/NQ*100,1),
        "examples":[{"q":e[1],"like":e[0],"video":bigmap.get(e[2],{}).get("title","")[:55],"url":f"https://youtu.be/{e[2]}"} for e in exs]})
    if len(themes)>=40: break
out={"total_comments":sum(len(c) for c in comments.values()),"total_questions":len(questions),
 "themes":themes,
 "top_questions":[{"q":s,"like":l,"video":bigmap.get(v,{}).get("title","")[:55],"url":f"https://youtu.be/{v}"}
                  for l,s,v in sorted([(l,s,v) for s,l,v in questions],key=lambda z:-z[0])[:50]]}
jsave(p("gaps.json"),out)
print(f"DONE — {len(questions)} viewer questions from {out['total_comments']:,} comments, {len(themes)} themes -> gaps.json")
