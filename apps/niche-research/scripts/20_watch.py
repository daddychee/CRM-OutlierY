"""S20 — Watch snapshot + diff (Tầng 2/3 monitoring).

Chụp snapshot GỌN từ videos.json (sau compute_outliers) + demand.json + channels.json
vào snapshots/YYYY-MM-DD.json, rồi diff với snapshot liền trước → sự kiện:

  NEW_OUTLIER     video vượt ngưỡng OX>=3 (mới xuất hiện hoặc từ dưới ngưỡng đi lên);
                  sub=early_confirmed nếu lần trước video còn <45 ngày tuổi
  TREND_FLIP      demand.json đổi chiều trend (RISING/FLAT/DECLINING)
  NEW_CHALLENGER  kênh newcomer (nhỏ VÀ trẻ — định nghĩa chung _common.compute_newcomers)
                  có outlier ĐẦU TIÊN

Sự kiện append vào signals.json (mới nhất trước, giữ tối đa 200). Python đo mọi thứ,
không LLM (§0). Mỗi sự kiện trỏ về video/kênh + con số nguồn.

Chạy:  python3 scripts/20_watch.py <niche-data-dir> [--baseline]
  --baseline: nếu CHƯA có snapshot nào thì chụp từ dữ liệu hiện có (đề ngày theo mtime
              của videos.json) để lần watch đầu tiên đã diff được. Có rồi thì no-op.

Cuối lượt thường (không --baseline): cập nhật last_run trong .watch.json nếu file tồn tại
— server scheduler đọc mốc này để tính chu kỳ kế.
"""
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import compute_outliers, compute_newcomers, jload, jsave

WORK = sys.argv[1] if len(sys.argv) > 1 else "."
BASELINE = "--baseline" in sys.argv[2:]

OX_TH = 3.0            # ngưỡng outlier chuẩn của tool
MAX_EVENTS_PER_RUN = 10  # chống flood NEW_OUTLIER trong 1 lượt
MAX_SIGNALS = 200
YOUNG_MONTHS = 24      # khớp 5_crackability.py

p = lambda *a: os.path.join(WORK, *a)
SNAP_DIR = p("snapshots")


def build_snapshot():
    """videos.json → snapshot gọn. Trả None nếu thiếu dữ liệu."""
    vj = p("videos.json")
    if not os.path.exists(vj):
        return None
    videos = jload(vj, [])
    if not videos:
        return None
    # Dùng mtime của videos.json làm "now" — tuổi/OX phản ánh THỜI ĐIỂM SCAN,
    # không phải lúc script này chạy (quan trọng khi chụp baseline từ data cũ).
    scan_dt = datetime.fromtimestamp(os.path.getmtime(vj), tz=timezone.utc)
    compute_outliers(videos, scan_dt)

    vids = {}
    ch_outliers = {}
    for x in videos:
        if not x.get("valid"):
            continue
        vids[x["videoId"]] = {
            "t":   (x.get("title") or "")[:120],
            "ch":  x.get("channelId"),
            "v":   x.get("viewCount", 0),
            "ox":  x.get("ox", 0),
            "ex":  x.get("excess", 0),
            "age": round(x["age"], 1) if x.get("age") is not None else None,
        }
        if x.get("ox", 0) >= OX_TH:
            ch_outliers[x["channelId"]] = ch_outliers.get(x["channelId"], 0) + 1

    demand = jload(p("demand.json"), {}) or {}
    return {
        "ts":          scan_dt.timestamp(),
        "date":        scan_dt.strftime("%Y-%m-%d"),
        "trend":       demand.get("trend"),
        "videos":      vids,
        "ch_outliers": ch_outliers,
    }


def diff(prev, cur, chinfo, now_dt):
    events = []
    chname = lambda c: (chinfo.get(c, {}) or {}).get("title") or c

    # --- NEW_OUTLIER (xếp theo excess — reach tuyệt đối, không OX thô) ---
    pv = prev.get("videos", {})
    news = []
    for vid, d in cur["videos"].items():
        if d["ox"] >= OX_TH:
            old = pv.get(vid)
            if old is None or old["ox"] < OX_TH:
                news.append((vid, d, old))
    news.sort(key=lambda t: t[1]["ex"], reverse=True)
    for vid, d, old in news[:MAX_EVENTS_PER_RUN]:
        sub = "early_confirmed" if (old and old.get("age") is not None and old["age"] < 45) else None
        events.append({
            "type": "NEW_OUTLIER", "video_id": vid, "title": d["t"],
            "channel": chname(d["ch"]), "ox": d["ox"], "views": d["v"],
            "prev_ox": old["ox"] if old else None, "sub": sub,
        })
    if len(news) > MAX_EVENTS_PER_RUN:
        print(f"    (NEW_OUTLIER: giữ top {MAX_EVENTS_PER_RUN}/{len(news)} theo excess — tránh flood)")

    # --- TREND_FLIP ---
    if prev.get("trend") and cur.get("trend") and prev["trend"] != cur["trend"]:
        events.append({"type": "TREND_FLIP", "from": prev["trend"], "to": cur["trend"]})

    # --- NEW_CHALLENGER ---
    prev_ch = prev.get("ch_outliers", {})
    first_timers = [c for c, n in cur["ch_outliers"].items() if n > 0 and prev_ch.get(c, 0) == 0]
    if first_timers:
        newcomers, _ = compute_newcomers(list(cur["ch_outliers"].keys()), chinfo, now_dt, YOUNG_MONTHS)
        for c in first_timers:
            if c in newcomers:
                events.append({
                    "type": "NEW_CHALLENGER", "channel_id": c, "channel": chname(c),
                    "n_outliers": cur["ch_outliers"][c],
                })
    return events


def _sig_key(e):
    ident = e.get("video_id") or e.get("channel_id") or f"{e.get('from')}>{e.get('to')}"
    return f"{e['type']}:{ident}:{e.get('date','')}"


def append_signals(events, date_str):
    """Append có dedup — chạy lại cùng ngày (idempotent) không nhân đôi tín hiệu."""
    if not events:
        return
    sig = jload(p("signals.json"), {}) or {}
    lst = sig.get("signals", [])
    seen = {_sig_key(s) for s in lst}
    ts = time.time()
    added = 0
    for e in events:
        row = {**e, "ts": ts, "date": date_str}
        if _sig_key(row) in seen:
            continue
        lst.insert(0, row)
        added += 1
    if added:
        jsave(p("signals.json"), {"signals": lst[:MAX_SIGNALS]})


def touch_last_run():
    wf = p(".watch.json")
    if os.path.exists(wf):
        cfg = jload(wf, {}) or {}
        cfg["last_run"] = time.time()
        jsave(wf, cfg)


snaps = sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")))

if BASELINE:
    if snaps:
        print("DONE — baseline đã tồn tại, bỏ qua")
        sys.exit(0)
    snap = build_snapshot()
    if snap is None:
        print("DONE — chưa có videos.json, không có gì để chụp baseline")
        sys.exit(0)
    os.makedirs(SNAP_DIR, exist_ok=True)
    jsave(os.path.join(SNAP_DIR, f"{snap['date']}.json"), snap)
    print(f"DONE — baseline {snap['date']}: {len(snap['videos'])} video valid, trend={snap['trend']}")
    sys.exit(0)

snap = build_snapshot()
if snap is None:
    print("ERROR: thiếu videos.json — chạy scan trước")
    sys.exit(1)

os.makedirs(SNAP_DIR, exist_ok=True)
cur_path = os.path.join(SNAP_DIR, f"{snap['date']}.json")
prev_snaps = [s for s in snaps if os.path.basename(s) != f"{snap['date']}.json"]

n_events = 0
if prev_snaps:
    prev = jload(prev_snaps[-1], {})
    chinfo = jload(p("channels.json"), {}) or {}
    now_dt = datetime.fromtimestamp(snap["ts"], tz=timezone.utc)
    events = diff(prev, snap, chinfo, now_dt)
    append_signals(events, snap["date"])
    n_events = len(events)
    for e in events:
        print(f"    [{e['type']}] " + (e.get("title") or e.get("channel") or f"{e.get('from')}→{e.get('to')}"))

jsave(cur_path, snap)
touch_last_run()
prev_note = f"diff với {os.path.basename(prev_snaps[-1])}" if prev_snaps else "chưa có snapshot trước — chỉ chụp"
print(f"DONE — snapshot {snap['date']}: {len(snap['videos'])} video valid, {n_events} tín hiệu ({prev_note})")
