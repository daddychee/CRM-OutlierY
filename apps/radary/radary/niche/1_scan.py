"""STEP 1 — Scan competitor videos. Incremental & resumable: saves after EVERY 50-video page,
so it survives short timeouts and never stalls on a huge channel. Caps to the most-recent
MAX_PER_CHANNEL uploads per channel (aligns with the recent-window baseline in the OX model).
Usage: python3 1_scan.py <competitors.txt> [workdir]   Re-run until it prints DONE."""
import sys, time
from _common import load_input, API, jload, jsave
INPUT=sys.argv[1] if len(sys.argv)>1 else "competitors.txt"
WORK =sys.argv[2] if len(sys.argv)>2 else "."
TIME_BUDGET=9999          # set ~30 in a 45s sandbox; high = run to completion
MAX_PER_CHANNEL=300       # most-recent uploads per channel (0 = unlimited)
def p(f): return f"{WORK}/{f}"
keys,chans=load_input(INPUT); api=API(keys)
print(f"{len(keys)} keys | {len(chans)} channels in input")

def crow(it):
    return {"title":it["snippet"]["title"],"uploads":it["contentDetails"]["relatedPlaylists"].get("uploads"),
            "subs":it.get("statistics",{}).get("subscriberCount"),"videoCount":it.get("statistics",{}).get("videoCount")}

# ---- resolve channels -> uploads playlist (cached) ----
chinfo=jload(p("channels.json"),None)
if chinfo is None:
    chinfo={}; ids=[v for k,v in chans if k=="id"]
    for i in range(0,len(ids),50):
        d=api.get("channels",{"part":"snippet,contentDetails,statistics","id":",".join(ids[i:i+50]),"maxResults":50})
        for it in d.get("items",[]): chinfo[it["id"]]=crow(it)
    for kind,val in chans:
        if kind=="id": continue
        if kind=="handle": d=api.get("channels",{"part":"snippet,contentDetails,statistics","forHandle":val})
        elif kind=="user": d=api.get("channels",{"part":"snippet,contentDetails,statistics","forUsername":val})
        else:
            s=api.get("search",{"part":"snippet","q":val,"type":"channel","maxResults":1})
            cid=(s.get("items") or [{}])[0].get("snippet",{}).get("channelId")
            d=api.get("channels",{"part":"snippet,contentDetails,statistics","id":cid}) if cid else {}
        for it in d.get("items",[]): chinfo[it["id"]]=crow(it)
    jsave(p("channels.json"),chinfo); print(f"resolved {len(chinfo)} channels")

videos=jload(p("videos.json"),[]); done=set(jload(p("scan_done.json"),[])); state=jload(p("scan_state.json"),{})
start=time.time()
def vdetails(ids):
    out=[]
    for i in range(0,len(ids),50):
        d=api.get("videos",{"part":"snippet,statistics,contentDetails","id":",".join(ids[i:i+50]),"maxResults":50})
        for it in d.get("items",[]):
            sn,st,cd=it["snippet"],it.get("statistics",{}),it.get("contentDetails",{})
            out.append({"videoId":it["id"],"channelId":sn.get("channelId"),"channelTitle":sn.get("channelTitle"),
                "title":sn.get("title"),"publishedAt":sn.get("publishedAt"),"tags":sn.get("tags",[]),
                "lang":sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),"duration":cd.get("duration"),
                "viewCount":int(st.get("viewCount",0) or 0),"likeCount":int(st.get("likeCount",0) or 0),
                "commentCount":int(st.get("commentCount",0) or 0)})
    return out
def save(): jsave(p("videos.json"),videos); jsave(p("scan_done.json"),list(done)); jsave(p("scan_state.json"),state)
for cid,info in chinfo.items():
    if cid in done: continue
    pid=info.get("uploads")
    if not pid: done.add(cid); save(); continue
    st=state.get(cid,{"token":None,"n":0})
    while True:
        if time.time()-start>TIME_BUDGET: save(); print("PAUSE — re-run to continue"); sys.exit(0)
        if MAX_PER_CHANNEL and st["n"]>=MAX_PER_CHANNEL: break
        params={"part":"contentDetails","playlistId":pid,"maxResults":50}
        if st["token"]: params["pageToken"]=st["token"]
        d=api.get("playlistItems",params)
        if d.get("_error"): break
        ids=[i["contentDetails"]["videoId"] for i in d.get("items",[])]
        if ids:
            det=vdetails(ids)
            for vv in det: vv["channelSubs"]=info.get("subs")
            videos+=det; st["n"]+=len(ids)
        st["token"]=d.get("nextPageToken"); state[cid]=st; save()
        if not st["token"]: break
    done.add(cid); state.pop(cid,None); save()
    print(f"{info['title'][:32]:34} n={st['n']:>4} total={len(videos)}")
# dedupe by videoId (guards against overlap / re-runs)
seen={}; [seen.__setitem__(x['videoId'],x) for x in videos]
if len(seen)!=len(videos): videos=list(seen.values()); jsave(p("videos.json"),videos)
if len(done)>=len(chinfo): print(f"DONE — {len(done)} channels, {len(videos)} unique videos -> videos.json")
