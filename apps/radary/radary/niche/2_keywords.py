"""STEP 2 — Keyword / title-structure analysis + OUTLIER LIFT.  Niche- & language-agnostic.
Usage: python3 2_keywords.py [workdir]   Reads videos.json -> writes analysis.json"""
import sys, re, json, math
from datetime import datetime, timezone
from collections import Counter, defaultdict
from _common import compute_outliers
WORK = sys.argv[1] if len(sys.argv) > 1 else "."
def p(f): return f"{WORK}/{f}"
v = json.load(open(p("videos.json"), encoding="utf-8"))
compute_outliers(v, datetime.now(timezone.utc))

# tiny universal function-word seed (extended by DYNAMIC stopwords below for any language)
SEED_STOP=set("a an the of in on at to for and or but with from by as is are was were be been being this that these those it its their his her your you we they i he she them us our my me do does did has have had will would can could should may might must not no nor so than then too very just about into over under out up down off again more most some such only own same s t re ve ll d m o de la el en y que un una los las del al le les des et à的 了 是 在 我 你 他".split())
def toks(t):
    t=re.sub(r"[^\w\s]"," ",(t or "").lower(),flags=re.UNICODE)
    return [w for w in t.split() if w and not w.isdigit() and len(w)>1]
ch=lambda x:x.get("channelTitle") or x.get("channelId")
N=len(v)

# dynamic stopwords: tokens appearing in >40% of titles are too generic for this corpus
df=Counter()
for x in v:
    for w in set(toks(x["title"])): df[w]+=1
DYN_STOP=SEED_STOP | {w for w,c in df.items() if c> 0.40*N}
def words(t): return [w for w in toks(t) if w not in DYN_STOP]

uf,uc,uv=Counter(),defaultdict(set),defaultdict(int)
for x in v:
    for w in set(words(x["title"])): uf[w]+=1; uc[w].add(ch(x)); uv[w]+=x["viewCount"]
ng={2:Counter(),3:Counter(),4:Counter()}; ngc={2:defaultdict(set),3:defaultdict(set),4:defaultdict(set)}
for x in v:
    t=toks(x["title"])
    for n in (2,3,4):
        for i in range(len(t)-n+1):
            g=" ".join(t[i:i+n]); ng[n][g]+=1; ngc[n][g].add(ch(x))
def template(title):
    t=re.sub(r"\b(19|20)\d{2}\b","{YEAR}",title)
    t=re.sub(r"\b[A-Z]{2,}\b","{CAPS}",t)
    t=re.sub(r"(?:\b[A-Z][a-z]+\b(?:\s+|$)){1,4}",lambda m:"{NAME} ",t)
    t=re.sub(r"\b\d+\b","{NUM}",t)
    t=re.sub(r"\{CAPS\}(\s+\{CAPS\})+","{CAPS}",t); t=re.sub(r"\{NAME\}(\s+\{NAME\})+","{NAME} ",t)
    return re.sub(r"\s+"," ",t).strip()
tm=Counter(); tmc=defaultdict(set); op=Counter(); opc=defaultdict(set); caps=Counter(); capc=defaultdict(set)
for x in v:
    tp=template(x["title"]); tm[tp]+=1; tmc[tp].add(ch(x))
    t=toks(x["title"])
    if t: o=" ".join(t[:3]); op[o]+=1; opc[o].add(ch(x))
    for w in re.findall(r"\b[A-Z]{3,}\b", x["title"]): caps[w]+=1; capc[w].add(ch(x))

# ---------- OUTLIER LIFT: which words/phrases over-index in valid outliers ----------
out=[x for x in v if x["valid"] and x["ox"]>=3]      # "winners": valid, >=3x
non=[x for x in v if x["valid"] and x["ox"]<2]        # "normal": valid baseline videos
No,Nn=max(len(out),1),max(len(non),1)
def norm_cdf(z): return 0.5*(1+math.erf(z/math.sqrt(2)))
def lift_table(grams_out_set_fn, vocab):
    co=Counter(); cn=Counter(); cch=defaultdict(set)
    for x in out:
        for g in set(grams_out_set_fn(x)): co[g]+=1; cch[g].add(ch(x))
    for x in non:
        for g in set(grams_out_set_fn(x)): cn[g]+=1
    rows=[]
    for g in vocab:
        a=co.get(g,0)
        if a<5 or len(cch[g])<3: continue          # support + cross-channel gate
        po=a/No; pn=(cn.get(g,0)+0.5)/(Nn+0.5)
        lift=po/pn
        if lift<1.2: continue
        # two-proportion z (normal approx) -> one-sided p
        pp=(a+cn.get(g,0))/(No+Nn); se=math.sqrt(max(pp*(1-pp)*(1/No+1/Nn),1e-9))
        z=(po-pn)/se; pval=1-norm_cdf(z)
        rows.append({"key":g,"out":a,"non":cn.get(g,0),"channels":len(cch[g]),"lift":round(lift,2),"p":pval})
    # Benjamini-Hochberg FDR q=0.10
    rows.sort(key=lambda r:r["p"]); m=len(rows); keep=[]
    for i,r in enumerate(rows,1):
        if r["p"]<= (i/m)*0.10 if m else False: r["sig"]=True
        else: r["sig"]=False
        keep.append(r)
    keep.sort(key=lambda r:-r["lift"])
    for r in keep: r.pop("p",None)
    return keep
vocab_uni={w for w in uf if uf[w]>=5}
vocab_big={g for g in ng[2] if ng[2][g]>=5}
lift_uni=lift_table(lambda x:[w for w in set(words(x["title"]))], vocab_uni)
lift_big=lift_table(lambda x:[" ".join(t[i:i+2]) for t in [toks(x["title"])] for i in range(len(t)-1)], vocab_big)

def rows(freq,cmap,n,vmap=None):
    o=[]
    for k,c in freq.most_common(n):
        r={"key":k,"freq":c,"channels":len(cmap[k])}
        if vmap is not None: r["total_views"]=vmap[k]; r["avg_views"]=round(vmap[k]/c)
        o.append(r)
    return o
bundle={"total_videos":N,"total_channels":len({ch(x) for x in v}),
 "n_winners":len(out),"n_normal":len(non),
 "unigrams":rows(uf,uc,250,uv),"bigrams":rows(ng[2],ngc[2],200),"trigrams":rows(ng[3],ngc[3],200),
 "fourgrams":rows(ng[4],ngc[4],150),"templates":rows(tm,tmc,120),"openers":rows(op,opc,80),
 "emphasis":rows(caps,capc,120),"lift_unigrams":lift_uni[:80],"lift_bigrams":lift_big[:80]}
json.dump(bundle,open(p("analysis.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"analysis.json — {N} videos | winners(>=3x):{len(out)} normal(<2x):{len(non)} | lift kw:{len(lift_uni)}")
