#!/usr/bin/env python3
"""WEEKLY RADAR — cảnh báo sớm dịch chuyển niche (Bước 3 của weekly_report.md)

Chạy:  python3 weekly_radar.py            (re-run đến khi in DONE — resumable)
Cần:   radar_state/competitors.txt  (API keys AIza... + list kênh, format như niche-report)

Luật đã chốt từ backtest 07/2026:
  ALARM  = video ≤7 ngày tuổi, OX≥10× baseline kênh, ≥50K views, và (kênh mạnh HOẶC token mới)
  ABS    = views/ngày lọt top 0.5% toàn niche (bài học Yakutsk — bắt cả kênh baseline cao)
  WATCH  = gia tốc cung theme z>2σ | ≥3 kênh mạnh first-touch 1 theme trong 14 ngày | video cũ hồi sinh
  INFO   = marker packaging lan sang kênh thứ 3 trong 28 ngày

Output: radar_reports/YYYY-MM-DD.md (1 trang, ≤5 lệnh) + radar_state/alerts_log.json (tự chấm sau 30 ngày)
"""
import json, os, re, sys, time, statistics, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter

BASE=os.path.dirname(os.path.abspath(__file__))
ST=os.path.join(BASE,'radar_state'); RP=os.path.join(BASE,'radar_reports')
os.makedirs(ST,exist_ok=True); os.makedirs(RP,exist_ok=True)
TIME_BUDGET=int(os.environ.get('RADAR_BUDGET','28')); T0=time.time()
TODAY=datetime.now(timezone.utc).strftime('%Y-%m-%d')

THEMES={'life_in':r"life in|as[ií] es la vida|vida en|real life|living in|vida no",
 'uncensored':r"uncensored|sin censura|sem censura",
 'women_beauty':r"women|beautiful|mujeres|hermosas|beauty|girls|lindas",
 'taboo_forbidden':r"taboo|banned|illegal|forbidden|don'?t watch|prohibid|censur",
 'tribe':r"\btribe|\btribu|\btribo",'facts_top':r"\bfacts\b|\bdatos\b|\btop \d|\d+ (things|shocking|mind)",
 'cost_cheap':r"cheap|\$\d|barat[oa]|cost of|expensive|price",
 'extreme_climate':r"coldest|hottest|driest|fr[íi]o|calor|desert|frozen|-\d+°",
 'island':r"\bisland|\bisla\b|\bislas|\bilha",'danger_dark':r"danger|dark|deadly|worst|letal|peligros|muerte|death",
 'world_cup':r"world cup|mundial"}
MARKERS={'dont_watch':r"don'?t watch",'banned_x_years':r"banned for \d+",'price_tag':r"\$\d+",
 'temperature':r"-?\d+\s*°",'shouldnt_exist':r"shouldn'?t exist",'last_photo':r"last (photo|day)"}

def jload(p,d=None):
    try: return json.load(open(os.path.join(ST,p)))
    except: return d
def jsave(p,o): json.dump(o,open(os.path.join(ST,p),'w'),ensure_ascii=False)
def budget(): return time.time()-T0>TIME_BUDGET

class API:
    def __init__(s,keys): s.keys=keys; s.i=0
    def get(s,ep,params):
        for _ in range(len(s.keys)*2):
            q=dict(params); q['key']=s.keys[s.i%len(s.keys)]
            url=f'https://www.googleapis.com/youtube/v3/{ep}?'+urllib.parse.urlencode(q)
            try:
                return json.load(urllib.request.urlopen(url,timeout=15))
            except urllib.error.HTTPError as e:
                if e.code in (403,429): s.i+=1; continue
                raise
        raise RuntimeError('quota exhausted on all keys')

def load_keys_channels():
    keys=[]; chans=[]
    for ln in open(os.path.join(ST,'competitors.txt')):
        ln=ln.strip()
        if ln.startswith('AIza'): keys.append(ln)
        elif '/channel/' in ln: chans.append(ln.split('/channel/')[1].split('/')[0])
    return keys,chans

def parse_dur(d):
    m=re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',d or '')
    h,mi,s=(int(x) if x else 0 for x in (m.groups() if m else (0,0,0))); return h*3600+mi*60+s

def main():
    keys,chan_ids=load_keys_channels(); api=API(keys)
    V=jload('videos.json',{})            # videoId -> {ch,chId,title,p,dur,snaps:{date:views}}
    run=jload('run_state.json',{'date':None,'fetched':[],'phase':'uploads'})
    if run['date']!=TODAY: run={'date':TODAY,'fetched':[],'phase':'uploads'}

    # ---- PHA 1: video mới từ uploads playlist ----
    if run['phase']=='uploads':
        for cid in chan_ids:
            if cid in run['fetched']: continue
            if budget(): jsave('run_state.json',run); print('PAUSE — re-run'); return
            up='UU'+cid[2:]
            try: d=api.get('playlistItems',{'part':'contentDetails,snippet','playlistId':up,'maxResults':50})
            except Exception: run['fetched'].append(cid); continue
            for it in d.get('items',[]):
                vid=it['contentDetails']['videoId']
                if vid not in V:
                    sn=it['snippet']
                    V[vid]={'ch':sn.get('channelTitle',''),'chId':cid,'title':sn.get('title',''),
                            'p':it['contentDetails'].get('videoPublishedAt',sn.get('publishedAt','')),'dur':None,'snaps':{}}
            run['fetched'].append(cid)
        run['phase']='stats'; run['fetched']=[]; jsave('videos.json',V); jsave('run_state.json',run)

    # ---- PHA 2: refresh stats (video ≤56 ngày + watchlist outlier cũ) ----
    if run['phase']=='stats':
        cutoff=(datetime.now(timezone.utc)-timedelta(days=56)).strftime('%Y-%m-%d')
        watch=set(jload('watchlist.json',[]))
        need=[vid for vid,v in V.items() if (v['p'][:10]>=cutoff or vid in watch) and TODAY not in v['snaps']]
        for i in range(0,len(need),50):
            if budget(): jsave('videos.json',V); jsave('run_state.json',run); print(f'PAUSE stats {i}/{len(need)} — re-run'); return
            d=api.get('videos',{'part':'statistics,contentDetails','id':','.join(need[i:i+50]),'maxResults':50})
            for it in d.get('items',[]):
                v=V[it['id']]; v['snaps'][TODAY]=int(it.get('statistics',{}).get('viewCount') or 0)
                if v['dur'] is None: v['dur']=parse_dur(it['contentDetails']['duration'])
        run['phase']='rules'; jsave('videos.json',V); jsave('run_state.json',run)

    # ---- PHA 3: luật cảnh báo ----
    now=datetime.now(timezone.utc)
    def latest(v): return v['snaps'].get(TODAY) or (list(v['snaps'].values())[-1] if v['snaps'] else 0)
    def age(v):
        try: return max((now-datetime.fromisoformat(v['p'].replace('Z','+00:00'))).days,1)
        except: return 9999
    longs={vid:v for vid,v in V.items() if (v['dur'] or 999)>180}
    # baseline & sức kênh (video 30-180 ngày)
    chbase=defaultdict(list); chvpd=defaultdict(list)
    for v in longs.values():
        a=age(v)
        if 30<=a<=180 and latest(v)>0: chbase[v['ch']].append(latest(v)); chvpd[v['ch']].append(latest(v)/a)
    base={c:statistics.median(x) for c,x in chbase.items() if len(x)>=5}
    strength={c:statistics.median(x) for c,x in chvpd.items() if len(x)>=5}
    medS=statistics.median(strength.values()) if strength else 0
    # novelty tokens
    dfc=Counter(w for v in longs.values() for w in set(re.findall(r'[a-zà-ÿ]{4,}',v['title'].lower())))
    def tokens_new(v):
        cut=(now-timedelta(days=97)).strftime('%Y-%m-%d'); mine_p=v['p'][:10]
        out=[]
        for w in re.findall(r'[a-zà-ÿ]{4,}',v['title'].lower()):
            if dfc[w]>=40: continue
            prior=any(w in x['title'].lower() for x in longs.values() if cut<=x['p'][:10]<mine_p)
            if not prior: out.append(w)
        return out
    vpd_all=sorted((latest(v)/age(v) for v in longs.values() if latest(v)>0),reverse=True)
    abs_cut=vpd_all[max(len(vpd_all)//200,5)] if vpd_all else 1e9   # top 0.5%
    alerts=[]
    # ALARM video mới
    for vid,v in longs.items():
        a=age(v); vw=latest(v)
        if a<=7 and vw>=50000:
            b=base.get(v['ch']); ox=vw/b if b else None
            strong=strength.get(v['ch'],0)>medS; nov=tokens_new(v)
            if ox and ox>=10 and (strong or nov):
                alerts.append({'level':'ALARM','why':f"OX={ox:.0f}x, {vw:,} views/{a}d"+(", kênh mạnh" if strong else "")+(f", token mới:{','.join(nov[:3])}" if nov else ''),
                               'vid':vid,'title':v['title'],'ch':v['ch'],
                               'action':'Chạy Double Down + thumbnail pipeline trong 72h'})
            elif vw/a>=abs_cut:
                alerts.append({'level':'ALARM','why':f"ABS top-0.5% niche: {vw/a:,.0f} views/ngày",'vid':vid,'title':v['title'],'ch':v['ch'],
                               'action':'Kiểm tra chủ đề — có thể là sóng trên kênh lớn (kiểu Yakutsk)'})
    # WATCH hồi sinh (cần ≥2 snapshot)
    for vid,v in longs.items():
        sn=sorted(v['snaps'].items())
        if len(sn)>=2 and age(v)>90:
            (d0,v0),(d1,v1)=sn[-2],sn[-1]
            days=max((datetime.fromisoformat(d1)-datetime.fromisoformat(d0)).days,1)
            wk=(v1-v0)/days*7; hist_wk=v0/max(age(v),1)*7
            if wk>=20000 and wk>=5*hist_wk:
                alerts.append({'level':'WATCH','why':f"video {age(v)//30} tháng tuổi hồi sinh: +{wk:,.0f} views/tuần (nền {hist_wk:,.0f})",
                               'vid':vid,'title':v['title'],'ch':v['ch'],'action':'Thuật toán đang đào lại mỏ — cân nhắc video cùng chủ đề'})
    # WATCH cung theme + first-touch kênh mạnh
    wkc=defaultdict(Counter); first_touch=defaultdict(dict)
    for v in longs.values():
        try: w=(datetime.fromisoformat(v['p'].replace('Z','+00:00')).replace(tzinfo=None)-datetime(2023,1,2)).days//7
        except: continue
        for t,rx in THEMES.items():
            if re.search(rx,v['title'],re.I):
                wkc[w][t]+=1
                if v['ch'] not in first_touch[t] or v['p']<first_touch[t][v['ch']]: first_touch[t][v['ch']]=v['p']
    mw=max(wkc) if wkc else 0
    cut14=(now-timedelta(days=14)).strftime('%Y-%m-%d')
    for t in THEMES:
        s=[wkc[w][t] for w in range(0,mw+1)]
        if len(s)>30:
            ma=sum(s[-4:])/4; hist=[sum(s[i-3:i+1])/4 for i in range(4,len(s)-4)]
            mu=statistics.mean(hist); sd=statistics.pstdev(hist) or 1
            if (ma-mu)/sd>2:
                alerts.append({'level':'WATCH','why':f"cung theme '{t}' tăng {ma:.0f}/tuần vs nền {mu:.0f} (z={(ma-mu)/sd:.1f})",
                               'vid':'','title':'','ch':'','action':'Creator đang dồn vào — kiểm tra cầu trước khi theo'})
        ft=[c for c,p in first_touch[t].items() if p[:10]>=cut14 and strength.get(c,0)>medS]
        if len(ft)>=3:
            alerts.append({'level':'WATCH','why':f"{len(ft)} kênh mạnh first-touch theme '{t}' trong 14 ngày: {', '.join(ft[:3])}",
                           'vid':'','title':'','ch':'','action':'Kênh mạnh đánh hơi — chuẩn bị kịch bản'})
    # INFO marker lan
    cut28=(now-timedelta(days=28)).strftime('%Y-%m-%d')
    for mk,rx in MARKERS.items():
        chs={v['ch'] for v in longs.values() if v['p'][:10]>=cut28 and re.search(rx,v['title'],re.I)}
        if len(chs)>=3:
            alerts.append({'level':'INFO','why':f"marker '{mk}' xuất hiện ở {len(chs)} kênh trong 28 ngày",'vid':'','title':'','ch':'','action':'Mã đang lan — cân nhắc dùng trước khi nhờn'})
    # watchlist cho tuần sau: outlier hiện hành
    wl=[vid for vid,v in longs.items() if base.get(v['ch']) and latest(v)/base[v['ch']]>=10]
    jsave('watchlist.json',wl[:800])
    # log + report
    log=jload('alerts_log.json',[])
    for a in alerts: log.append({**a,'date':TODAY,'scored':None})
    jsave('alerts_log.json',log)
    order={'ALARM':0,'WATCH':1,'INFO':2}
    alerts.sort(key=lambda a:order[a['level']])
    lines=[f"# Radar tuần — {TODAY}",'',f"Quét {len(longs)} video long-form / {len(chan_ids)} kênh. Luật: backtest 07/2026.",'']
    if not alerts: lines.append('**Không có tín hiệu vượt ngưỡng tuần này.**')
    for a in alerts[:12]:
        head=f"**[{a['level']}]** {a['why']}"
        if a['title']: head+=f" — *{a['title'][:70]}* ({a['ch']})"
        lines+= [head, f"→ {a['action']}"+(f" | https://youtu.be/{a['vid']}" if a['vid'] else ''),'']
    lines.append(f"\n---\n*{sum(1 for a in alerts if a['level']=='ALARM')} ALARM / {sum(1 for a in alerts if a['level']=='WATCH')} WATCH / {sum(1 for a in alerts if a['level']=='INFO')} INFO. Log: radar_state/alerts_log.json*")
    open(os.path.join(RP,f'{TODAY}.md'),'w').write('\n'.join(lines))
    run['phase']='done'; jsave('run_state.json',run)
    print(f"DONE — {len(alerts)} alerts -> radar_reports/{TODAY}.md")

if __name__=='__main__': main()
