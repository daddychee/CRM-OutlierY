"""STEP 18 — Build the Excel report (OX v3 + lift keywords + reach-weighted patterns + info gap).
Usage: python3 18_build_report.py [workdir] [out.xlsx]

Sheet order: Summary · Videos · Go-NoGo · Beachhead · DNA Niche · Questions · Execution Plan
             Recommended · Disagreements · Early Signals · Channels · Vocabulary · Title Templates
             Patterns · Topic Lift

Palette (nhiệt độ: nóng → lạnh = viral mạnh → ưu tiên thấp):
  Blue Slate  #5E6472 — header nền (chữ trắng)
  Powder Blush #FFA69E — >10x viral · CLONE NOW · NO-GO · DECLINING  (NÓNG)
  Vanilla Cream #FAF3DD — 5-10x · CLONE · CONDITIONAL                (ẤM)
  Icy Aqua   #B8F2E6 — 2-5x · TEST · GO · FDR-sig                  (MÁT)
  Light Blue  #AED9E0 — SKIP · KHÔNG BASELINE · LOW · fallback      (LẠNH)

Layout ngang (scroll phải thay vì scroll xuống): Vocabulary · Title Templates · Questions"""
import sys, json, re, os
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from _common import (compute_outliers, winners, tokenize, get_scan_time, MIN_BASE_VIDEOS,
                     SHORT_MAX_SEC, MID_MAX_SEC, RECENT_WINDOW_MONTHS, MATURITY_DAYS, OUTLIER_OX)
WORK=sys.argv[1] if len(sys.argv)>1 else "."
OUT =sys.argv[2] if len(sys.argv)>2 else f"{WORK}/niche_report.xlsx"
def p(f): return f"{WORK}/{f}"
def _load(f): return json.load(open(p(f),encoding="utf-8")) if os.path.exists(p(f)) else None
v=json.load(open(p("videos.json"),encoding="utf-8"))
b=json.load(open(p("analysis.json"),encoding="utf-8"))
chinfo=json.load(open(p("channels.json"),encoding="utf-8"))
gaps=_load("gaps.json")
_n_raw=len(v)
compute_outliers(v, get_scan_time(WORK))   # pinned scan time (V12): same OX as every other stage
SHORTS_BLOCKED=_n_raw-len(v)               # shorts gate removed these in place (0 on new scans — S1 already filters)

F="Calibri"
HF =PatternFill("solid",fgColor="5E6472")   # Blue Slate  — header background
HFONT=Font(name=F,bold=True,color="FFFFFF",size=11)
TT =Font(name=F,bold=True,size=15,color="1F3864")
H2 =Font(name=F,bold=True,size=12,color="5E6472")   # Blue Slate section headings
NM =Font(name=F,size=10); GY=Font(name=F,size=9,italic=True,color="595959")
th=Side(style="thin",color="BFBFBF"); BR=Border(left=th,right=th,top=th,bottom=th)
# palette — hot→cool = viral/urgent → low-priority
PWD=PatternFill("solid",fgColor="FFA69E")   # Powder Blush — hot (>10x, CLONE NOW, NO-GO)
VNL=PatternFill("solid",fgColor="FAF3DD")   # Vanilla Cream — warm (5-10x, CLONE, CONDITIONAL)
AQU=PatternFill("solid",fgColor="B8F2E6")   # Icy Aqua     — cool/positive (2-5x, GO, FDR-sig)
LBL=PatternFill("solid",fgColor="AED9E0")   # Light Blue   — cold/neutral (skip, no-baseline)
BLU=PatternFill("solid",fgColor="D9E1F2")   # neutral fallback

def hd(ws,r,n,sc=1):
    for c in range(sc,sc+n):
        x=ws.cell(row=r,column=c); x.fill=HF; x.font=HFONT
        x.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True); x.border=BR

def _xl(v):
    if isinstance(v,(list,tuple)): return ", ".join(str(_xl(x)) for x in v)
    if isinstance(v,dict): return "; ".join(f"{k}: {_xl(val)}" for k,val in v.items())
    if isinstance(v,(str,int,float,bool)) or v is None: return v if v is not None else ""
    return str(v)

def tbl(ws,sr,h,rows,w,sc=1,freeze=True):
    """sc = starting column (1-based). freeze=False for horizontal block tables."""
    for j,t in enumerate(h,sc): ws.cell(row=sr,column=j,value=_xl(t))
    hd(ws,sr,len(h),sc); r=sr+1
    for row in rows:
        for j,val in enumerate(row,sc):
            val=_xl(val)
            c=ws.cell(row=r,column=j,value=val); c.font=NM; c.border=BR
            c.alignment=Alignment(wrap_text=True,vertical="top")
            if isinstance(val,(int,float)) and not isinstance(val,bool):
                c.alignment=Alignment(horizontal="right")
                if isinstance(val,int) and abs(val)>=1000: c.number_format="#,##0"
        r+=1
    for j,wd in enumerate(w,sc):  # only increase column width, never shrink (horizontal blocks share rows)
        cl_=get_column_letter(j); cur=ws.column_dimensions[cl_].width or 0
        if wd>cur: ws.column_dimensions[cl_].width=wd
    if freeze: ws.freeze_panes=ws.cell(row=sr+1,column=1)
    return r

def cl(s): return re.sub(r"\s+"," ",s).strip()

def usage(ws,row,lines):
    for i,ln in enumerate(lines):
        c=ws.cell(row=row+i,column=1,value=("CÁCH DÙNG: " if i==0 else "   ")+ln); c.font=GY
    return row+len(lines)+1

TOC=[]   # (sheet, trả lời câu hỏi gì, hành động, nguồn số, lưu ý) -> rendered into Summary at the end
def toc(sheet,question,action,source,caveat): TOC.append((sheet,question,action,source,caveat))

# ---------------- shared evidence + coverage funnel (audit V14d) ----------------
win=winners(v); win_ids={x["videoId"] for x in win}
n_early=sum(1 for x in win if x.get("early"))
prim=[x for x in v if x.get("scope")=="primary"]
valid_prim=[x for x in prim if x.get("valid")]
fresh=[x for x in v if x.get("scope")=="fresh"]
watch=[x for x in fresh if x.get("valid") and not x.get("early") and x.get("ox",0)>=OUTLIER_OX]
shape_fb=sum(1 for x in prim if x.get("shape_src")!="exact")
per_ch=defaultdict(lambda:{"scanned":0,"valid":0,"win":0})
for x in v:
    d=per_ch[x["channelId"]]; d["scanned"]+=1
    if x.get("valid") and x.get("scope")=="primary": d["valid"]+=1
    if x["videoId"] in win_ids: d["win"]+=1
ch_no_base=[cid for cid in chinfo if per_ch[cid]["valid"]==0]

wb=Workbook(); wsSUM=wb.active; wsSUM.title="Summary"   # filled at the very end (needs the TOC)

d1=_load("decision1.json"); crack=_load("crackability.json"); mon=_load("monetization.json")
dem=_load("demand.json"); d2=_load("decision2.json"); plan=_load("execution_plan.json")
summ=_load("summary.json"); sub=_load("subniche.json")
VZ={"GO":AQU,"NO-GO":PWD,"CONDITIONAL":VNL,"CÂN NHẮC":VNL,"CLONE NOW":PWD,"OPEN":AQU,"CLOSED":PWD,"SEMI":VNL,
    "HIGH":AQU,"MEDIUM":VNL,"LOW":LBL,"RISING":AQU,"DECLINING":PWD,"FLAT":VNL}

# ============================ VIDEOS ============================
ws=wb.create_sheet("Videos")
ws["A1"]="TOÀN BỘ VIDEO + OX v3 — mặc định xếp: bằng chứng trước (winner theo Σexcess), phần còn lại sau"
ws["A1"].font=TT; ws.merge_cells("A1:P1")
r=usage(ws,2,["Mỗi hàng = 1 video đã scan. OX = views thực tế ÷ views KỲ VỌNG (kỳ vọng đã tính theo quy mô kênh + tuổi video + format).",
              "Excess = số views VƯỢT kỳ vọng (tuyệt đối). Săn ý tưởng: lọc Valid=TRUE và (Scope=primary hoặc Early=YES), rồi sort Excess giảm dần.",
              "VÍ DỤ vì sao xếp theo Excess chứ không theo OX: video OX=12 trên kênh 10k sub chỉ vượt ~110k views; video OX=4 trên kênh 1M sub vượt ~3M views — cái sau mới là cơ hội lớn.",
              "Màu ưu tiên (nóng → lạnh): HỒNG = nổ >10x (nghiên cứu trước) · KEM = 5-10x · XANH NGỌC = 2-5x · trắng = bình thường. Scope=legacy/fresh không phải bằng chứng (trừ Early=YES).",
              "Video Short (≤3 phút) đã bị CHẶN HOÀN TOÀN khỏi phân tích (gate mặc định) — cơ chế phân phối Shorts khác hẳn long-form nên views không so sánh được."])
def iso(s):
    if s is None: return ""
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}" if s>=3600 else f"{(s%3600)//60:02d}:{s%60:02d}"
vr=[[x["channelTitle"],x["title"],(x.get("publishedAt") or "")[:10],x["fmt"],x["viewCount"],x["expected"],x["ox"],x["excess"],
     x["bracket"],x["scope"],"YES" if x.get("early") else "",x["confidence"],"TRUE" if x["valid"] else "FALSE",
     x["commentCount"],iso(x["dur_s"]),f"https://youtu.be/{x['videoId']}"] for x in v]
vr.sort(key=lambda row:(0 if ("YES"==row[10] or (row[12]=="TRUE" and row[9]=="primary" and row[6]>=OUTLIER_OX)) else 1, -row[7]))
end=tbl(ws,r,["Kênh","Tiêu đề","Đăng","Format","Views","Expected","OX","Excess","Bracket","Scope","Early","Conf","Valid","Comments","Dài","Link"],vr,
    [18,46,11,7,11,11,8,11,11,9,7,7,7,9,8,26])
for rr in range(r+1,end):
    val=ws.cell(row=rr,column=9).value
    fl=PWD if val==">10x Viral" else VNL if val=="5-10x Strong" else AQU if val=="2-5x Above" else None
    if fl and ws.cell(row=rr,column=13).value=="TRUE":
        for c in range(1,17): ws.cell(row=rr,column=c).fill=fl
toc("Videos","Từng video đứng đâu so với kỳ vọng?","Tra chi tiết bằng chứng; lọc Valid + primary/Early, sort Excess",
    "videos.json + OX v3","OX của scope=legacy/fresh không phải bằng chứng")

# ============================ GO-NOGO ============================
if d1 or crack or mon or dem:
    ws=wb.create_sheet("Go-NoGo"); ws["A1"]="QUYẾT ĐỊNH 1 — GO / NO-GO (có nên vào niche này?)"; ws["A1"].font=TT; ws.merge_cells("A1:E1")
    r=usage(ws,2,["Nhìn VERDICT + lý do gate trước tiên. Điểm attractiveness (0-100) = trung bình có trọng số của các trụ CÓ DỮ LIỆU",
                  "(trụ thiếu = N/A, KHÔNG bị tính 0 điểm). Crackability = cửa cho người mới: CLOSED = NO-GO bất kể điểm cao đến đâu.",
                  "VÍ DỤ đọc: attractiveness 72 + crackability OPEN + trend RISING = vào được; attractiveness 80 nhưng CLOSED = đứng ngoài.",
                  "Lưu ý: RPM là ƯỚC LƯỢNG theo category (heuristic), không phải doanh thu đo được; trend chỉ là chiều hướng (R-1)."])
    if d1:
        ws.cell(row=r,column=1,value="VERDICT").font=H2
        c=ws.cell(row=r,column=2,value=d1.get("decision"))
        c.fill=VZ.get(d1.get("decision"),BLU); c.font=Font(name=F,bold=True,size=14,color="1F3864"); r+=1
        ws.cell(row=r,column=1,value="Attractiveness (0-100)").font=NM; ws.cell(row=r,column=2,value=d1.get("attractiveness")).font=NM; r+=1
        ws.cell(row=r,column=1,value="Gate / lý do").font=NM
        gc=ws.cell(row=r,column=2,value=d1.get("gate_reason")); gc.font=NM; gc.alignment=Alignment(wrap_text=True)
        ws.merge_cells(start_row=r,start_column=2,end_row=r,end_column=5); r+=1
        if d1.get("pillars_missing"):
            ws.cell(row=r,column=1,value=f"Trụ thiếu dữ liệu: {', '.join(d1['pillars_missing'])} — trọng số đã re-normalize").font=GY; r+=1
        r+=1
        r=tbl(ws,r,["Trụ","Điểm (0-100)","Trọng số"],
              [[k,(d1["pillars"].get(k) if d1["pillars"].get(k) is not None else "N/A"),d1["weights"].get(k)]
               for k in d1.get("weights",{})],[22,16,10])+1
    if crack:
        ws.cell(row=r,column=1,value="CRACKABILITY (người mới vào có thắng được không?)").font=H2; r+=1
        r=tbl(ws,r,["Verdict","Tỷ lệ newcomer thắng","Phụ thuộc authority","Độ lặp công thức","Lý do"],
              [[crack.get("verdict"),crack.get("newcomer_rate"),crack.get("authority_dependence"),
                crack.get("pattern_replicability"),crack.get("reason")]],[22,18,18,16,60])+1
    if mon:
        ws.cell(row=r,column=1,value="MONETIZATION (heuristic — ước lượng theo category)").font=H2; r+=1
        rpm=mon.get("rpm_band_usd",[0,0])
        r=tbl(ws,r,["Category","RPM ước lượng (USD)","Băng","Mật độ sponsor","Verdict"],
              [[mon.get("category"),f"{rpm[0]}-{rpm[1]}",mon.get("rpm_label"),mon.get("sponsor_density"),mon.get("verdict")]],[22,18,10,15,12])+1
    if dem:
        ws.cell(row=r,column=1,value="DEMAND & TREND (trend đo trên OX đã khử tuổi; KHÔNG cộng vào điểm demand — là trụ riêng)").font=H2; r+=1
        r=tbl(ws,r,["Median views","Reach p90","Upload/tháng","Trend","Độ mạnh trend"],
              [[dem.get("demand_median_views"),dem.get("reach_p90_views"),dem.get("supply_per_month"),
                dem.get("trend"),dem.get("trend_strength")]],[22,16,14,12,14])+1
    ws.column_dimensions["A"].width=30; ws.freeze_panes="A1"
    toc("Go-NoGo","Có nên vào niche này không?","Theo VERDICT; nếu CONDITIONAL thì chỉ vào khi có beachhead sắc (sheet Beachhead)",
        "decision1/crackability/monetization/demand.json","RPM heuristic; trend chỉ là chiều hướng (R-1)")

# ============================ BEACHHEAD (+ phương pháp OX ở cột phải) ============================
ws=wb.create_sheet("Beachhead"); ws["A1"]="QUYẾT ĐỊNH 2 — BEACHHEAD (đánh sub-niche nào TRƯỚC?)"; ws["A1"].font=TT; ws.merge_cells("A1:K1")
r=usage(ws,2,["Hàng XANH NGỌC = đầu cầu đề xuất — lấy làm lãnh thổ cho 10-20 video đầu tiên của bạn.",
              "'Kênh có outlier' mới là độ lặp thật (kênh chỉ đăng đề tài đó mà không thắng thì KHÔNG tính). '% newcomer thắng' = cơ hội cho người mới TRONG cụm đó.",
              "VÍ DỤ đọc: cụm có Điểm 78 · 5 kênh có outlier · newcomer 40% = nhiều kênh khác nhau đã thắng và người mới cũng thắng được — đúng chỗ để vào.",
              "Ranh giới cụm là MỀM (dựa trên anchor từ khóa, không phải taxonomy chuẩn). Muốn hiểu Điểm/OX/Σexcess được tính thế nào → đọc cột PHƯƠNG PHÁP bên phải (cột M)."])
if d2 and d2.get("ranked"):
    ws.cell(row=r,column=1,value="CHỌN").font=H2
    pc=ws.cell(row=r,column=2,value=d2.get("decision")); pc.fill=AQU; pc.font=Font(name=F,bold=True,size=13,color="1F3864")
    ws.cell(row=r+1,column=1,value="Vì sao").font=NM; wc=ws.cell(row=r+1,column=2,value=d2.get("reason")); wc.alignment=Alignment(wrap_text=True)
    ws.merge_cells(start_row=r+1,start_column=2,end_row=r+1,end_column=11)
    bh_hdr=r+3
    end=tbl(ws,bh_hdr,["#","Sub-niche","Điểm","Reach","HHI (cạnh tranh)","Kênh có outlier","% newcomer thắng","Tổng kênh","Σ excess","Browse/Search","Tiêu đề tiêu biểu"],
        [[r_["rank"],r_.get("label") or r_.get("anchor"),r_["beachhead_score"],r_["reach"],r_["competition"],
          r_.get("n_outlier_channels"),r_.get("outlier_newcomer_share"),r_["n_channels"],r_["sum_excess"],
          r_.get("browse_vs_search")," | ".join(r_.get("top_titles",[])[:2])] for r_ in d2["ranked"]],
        [4,24,8,8,13,13,14,9,13,12,56])
    for rr in range(bh_hdr+1,end):
        if ws.cell(row=rr,column=1).value==1:
            for c in range(1,12): ws.cell(row=rr,column=c).fill=AQU
else:
    ws.cell(row=r,column=1,value="Chưa có decision2.json — chạy đủ pipeline (S9/S10) rồi build lại report.").font=H2
toc("Beachhead","Vào bằng cửa nào trước?","Lấy hàng #1 làm lãnh thổ 10-20 video đầu; đối chiếu Recommended cùng cụm",
    "decision2.json + subniche.json","repl = kênh CÓ outlier; opportunity = money x %newcomer cụm")
# ---- PHƯƠNG PHÁP OX v3 & GIỚI HẠN — đầy đủ, đặt bên PHẢI bảng beachhead (user yêu cầu) ----
OXC=13   # column M
ws.cell(row=1,column=OXC,value="PHƯƠNG PHÁP OX v3 & GIỚI HẠN TRUNG THỰC — số được tính thế nào, tin được đến đâu").font=TT
OXL=[(H2,"CÔNG THỨC"),
 (NM,"OX = views / EXPECTED ;  EXPECTED = scale_kênh × shape(tuổi).  scale = trimmed median các video"),
 (NM,f"   GẦN ĐÂY (≤{RECENT_WINDOW_MONTHS} tháng) + ĐÃ CHÍN (≥{MATURITY_DAYS} ngày) cùng format của kênh, leave-one-out."),
 (NM,"shape = đường chín theo tuổi của niche (mốc 45 ngày là 1 cạnh bucket — không trộn non/chín)."),
 (NM,""),(H2,"VIDEO FRESH (<45 NGÀY) — quy tắc 2 tầng"),
 (NM,f"EARLY-CONFIRMED: views ≥ {OUTLIER_OX}×scale (median chín của kênh) → OX lúc chín chắc chắn ≥{OUTLIER_OX} (chặn dưới)"),
 (NM,"   → được tính là BẰNG CHỨNG đầy đủ ở mọi tầng, gắn cờ Early."),
 (NM,"Fresh còn lại: chỉ hiển thị ở sheet Early Signals để theo dõi; KHÔNG vào tập winners và KHÔNG BAO GIỜ vào tập normal."),
 (NM,""),(H2,"VÌ SAO PHẢI CẦU KỲ VẬY (so với views/median ngây thơ)"),
 (NM,"1. Chỉnh theo tuổi: video 5 năm và video 5 ngày được so với mức mà TUỔI đó thường đạt."),
 (NM,"2. Cửa sổ gần đây: baseline là phong độ HIỆN TẠI của kênh, không phải thời kênh còn bé."),
 (NM,"3. Leave-one-out + trim top 10%: chùm hit không tự thổi phồng baseline của chính nó."),
 (NM,f"4. Tách format: Short≤{SHORT_MAX_SEC}s | Mid≤{MID_MAX_SEC}s | Long; sàn views per-channel-per-format."),
 (NM,"5. Keyword theo LIFT (over-index trong winners vs normal) + BH-FDR step-up chuẩn, không phải tần suất."),
 (NM,"6. Pattern/bets xếp theo Σexcess TUYỆT ĐỐI trên ≥3 kênh, không theo OX thô."),
 (NM,""),(H2,"ĐỘ PHỦ DỮ LIỆU CỦA LẦN SCAN NÀY"),
 (NM,f"{len(v):,} video · {len(chinfo)} kênh · valid-primary: {len(valid_prim):,} ({round(100*len(valid_prim)/max(len(prim),1))}% của primary)"
     +(f" · Short bị chặn hoàn toàn: {SHORTS_BLOCKED}" if SHORTS_BLOCKED else " · Short đã bị chặn từ lúc scan (gate mặc định)")),
 (NM,f"winners ≥{OUTLIER_OX}x: {len(win)} (trong đó early-confirmed: {n_early}) · fresh đang theo dõi: {len(watch)}"),
 (NM,f"kênh KHÔNG đóng góp baseline (0 video valid): {len(ch_no_base)}/{len(chinfo)}"
     +(f" — {', '.join((chinfo[c].get('title') or c)[:20] for c in ch_no_base[:6])}{'…' if len(ch_no_base)>6 else ''}" if ch_no_base else "")),
 (NM,f"video primary dùng shape fallback (bucket tuổi thiếu mẫu): {shape_fb}/{len(prim)}"
     +(" — CẢNH BÁO: >30%, expected kém tin cậy" if prim and shape_fb/len(prim)>0.3 else "")),
 (NM,""),(H2,"GIỚI HẠN KHÔNG THỂ GỠ (residuals — in ra để không tự lừa)"),
 (NM,"R-1 Một snapshot không tách được tuổi/cohort/thời kỳ → OX đúng DƯỚI giả định cửa sổ gần đây."),
 (NM,"R-2 OX là tương đối theo kênh: OX to trên kênh tí hon là thật nhưng reach nhỏ → xem Σexcess (Patterns)."),
 (NM,"R-3 Lift là LIÊN HỆ, không nhân quả (thumbnail/thời sự/mùa vụ cũng đẩy views) → A/B để xác nhận."),
 (NM,"R-4 Survivorship: video flop bị xoá làm baseline đẹp lên → kênh coverage thấp bị cắm cờ, OX thiên bảo thủ."),
 (NM,"R-A Subs hiện tại ≠ subs lúc đăng → newcomer_rate là ước lượng bảo thủ."),
 (NM,"RPM/monetization là HEURISTIC theo category — không phải doanh thu đo được."),
 (NM,""),(H2,"LUẬT VÀNG"),
 (NM,"1 outlier = manh mối. ≥3 outlier tương tự Ở CÁC KÊNH KHÁC NHAU (sheet Patterns) = công thức đặt cược được."),
 (NM,"Kết quả của tool là ĐẶT CƯỢC CÓ THÔNG TIN để A/B test — không phải chân lý.")]
for i,(f_,t) in enumerate(OXL,3):
    ws.cell(row=i,column=OXC,value=t).font=f_
ws.column_dimensions[get_column_letter(OXC-1)].width=3
ws.column_dimensions[get_column_letter(OXC)].width=112
ws.freeze_panes="A1"

# ============================ DNA NICHE (gộp toàn bộ khối DNA vào 1 sheet) ============================
dna=_load("dna.json")
if dna:
    ws=wb.create_sheet("DNA Niche")
    ws["A1"]=f"DNA NICHE — {dna.get('niche','')} (gộp: tổng quan · hook · cấu trúc & cảm xúc · giọng & kho câu · từ khoá & thuật ngữ · lỗi cần tránh)"
    ws["A1"].font=TT; ws.merge_cells("A1:E1")
    r=usage(ws,2,["DNA là phán đoán craft từ transcript (đầu + giữa + cuối bài), KHÔNG chấm theo số. Sheet chia 2 LỚP:",
                  "LỚP KHÁM PHÁ (hook, cấu trúc) = bám convention để được phân phối — cứ COPY công thức. LỚP TRUNG THÀNH (giọng văn, cảm xúc, kho câu) = chỗ để KHÁC BIỆT, xây hào.",
                  "Phân loại video nguồn: CHUẨN MẪU = mẫu chuẩn để clone · THAM KHẢO = học một phần · LỆCH NICHE = tránh.",
                  "VÍ DỤ dùng: viết kịch bản mới → chọn 1 hook pattern + 1 cấu trúc (copy) + giữ đúng cảm xúc chủ đạo, nhưng câu chữ viết bằng giọng CỦA BẠN — không đạo nguyên văn kho câu."])
    def sec(row,label,note=None):
        ws.cell(row=row,column=1,value=label).font=H2; row+=1
        if note: ws.cell(row=row,column=1,value=note).font=GY; row+=1
        return row
    r=sec(r,"NGUỒN / TRẠNG THÁI")
    c=ws.cell(row=r,column=1,value=_xl(dna.get("source",""))); c.font=NM; c.alignment=Alignment(wrap_text=True); r+=2
    if dna.get("layers_note"):
        r=sec(r,"HAI LỚP (khám phá vs trung thành)")
        c=ws.cell(row=r,column=1,value=_xl(dna.get("layers_note"))); c.font=NM; c.alignment=Alignment(wrap_text=True); r+=2
    if dna.get("hook_patterns"):
        r=sec(r,"HOOK PATTERNS [LỚP KHÁM PHÁ]","Chọn 1-2 pattern khớp nội dung của bạn, dùng đúng công thức trong 15-30s đầu.")
        r=tbl(ws,r,["Pattern","Loại","Công thức","Phù hợp nội dung","Ví dụ nguyên văn"],
              [[h.get("name"),h.get("type"),h.get("formula"),h.get("fit"),h.get("example")] for h in dna["hook_patterns"]],
              [26,44,42,22,60])+1
    if dna.get("structures"):
        r=sec(r,"CẤU TRÚC BÀI THÀNH CÔNG [LỚP KHÁM PHÁ]","Khung kịch bản — chọn 1 khung, đừng trộn nhiều khung trong 1 video.")
        r=tbl(ws,r,["Cấu trúc","Arc","Phù hợp nội dung"],
              [[s.get("name"),s.get("arc"),s.get("fit")] for s in dna["structures"]],[26,44,42])+1
    if dna.get("emotions"):
        r=sec(r,"CẢM XÚC CHỦ ĐẠO [LỚP TRUNG THÀNH]","Thứ khán giả quay lại để ĐƯỢC CẢM THẤY — giữ nhất quán giữa các video, đừng đổi tuỳ tiện.")
        r=tbl(ws,r,["Cảm xúc","Xuất hiện","Video CHUẨN MẪU"],
              [[e.get("emotion"),e.get("clusters"),e.get("exemplars")] for e in dna["emotions"]],[26,44,42])+1
    if dna.get("voice"):
        r=sec(r,"GIỌNG VĂN CHỦ ĐẠO [LỚP TRUNG THÀNH]","Học CƠ CHẾ, viết bằng giọng của bạn — đây là chỗ khác biệt.")
        r=tbl(ws,r,["Khía cạnh","Chi tiết"],[[vv.get("aspect"),vv.get("detail")] for vv in dna["voice"]],[26,90])+1
    if dna.get("strong_lines"):
        r=sec(r,"KHO CÂU MẠNH (ưu tiên CHUẨN MẪU)","KHÔNG copy nguyên văn (đạo) — hiểu vì sao câu mạnh rồi viết lại theo giọng riêng.")
        r=tbl(ws,r,["Câu nguyên văn","Video","Phân loại","Cảm xúc","Hay vì"],
              [[l.get("line"),l.get("video"),l.get("klass"),l.get("emotion"),l.get("why")] for l in dna["strong_lines"]],
              [26,44,42,22,60])+1
    if dna.get("hook_keywords"):
        r=sec(r,"TỪ KHOÁ CỬA-SỔ-HOOK / 6 PHÚT ĐẦU (theo nhóm)","Rải nhóm từ này vào 6 phút đầu kịch bản — từ transcript, KHÁC từ khoá tiêu đề.")
        r=tbl(ws,r,["Nhóm","Từ khoá / cụm"],[[k.get("group"),k.get("terms")] for k in dna["hook_keywords"]],[26,90])+1
    if dna.get("terms"):
        r=sec(r,"THUẬT NGỮ NICHE","Dùng đúng thuật ngữ để nghe 'trong nghề'.")
        r=tbl(ws,r,["Thuật ngữ","Nghĩa","Ví dụ câu"],[[t.get("term"),t.get("meaning"),t.get("example")] for t in dna["terms"]],[26,44,60])+1
    if dna.get("avoid"):
        r=sec(r,"LỖI CẦN TRÁNH (ưu tiên từ video LỆCH NICHE)","Checklist rà kịch bản trước khi quay — hàng HỒNG (mức CAO) là lỗi giết video.")
        end=tbl(ws,r,["Lỗi","Bằng chứng","Hậu quả","Mức"],
            [[a.get("mistake"),a.get("evidence"),a.get("consequence"),a.get("severity")] for a in dna["avoid"]],[26,44,42,22])
        for rr in range(r+1,end):
            if str(ws.cell(row=rr,column=4).value).lower().startswith("cao"):
                for c in range(1,5): ws.cell(row=rr,column=c).fill=PWD
    ws.freeze_panes="A1"
    toc("DNA Niche","Bí quyết giữ chân của sub-niche là gì?","Copy lớp khám phá (hook/cấu trúc), KHÁC BIỆT lớp trung thành (giọng)",
        "dna.json + Transcripts/","phán đoán craft — nên có người xác nhận")

# ============================ QUESTIONS (gộp 3 sheet gap cũ) ============================
if gaps:
    ws=wb.create_sheet("Questions")
    ws["A1"]=(f"KHOẢNG TRỐNG THÔNG TIN — {gaps['total_questions']} câu hỏi thật của khán giả từ {gaps['total_comments']:,} comment "
              f"(đã lọc câu hỏi engagement/meta; theme tự khám phá từ dữ liệu)")
    ws["A1"].font=TT; ws.merge_cells("A1:I1")
    r=usage(ws,2,["Mỗi THEME = một nhu cầu chưa được trả lời tốt → là góc video trực tiếp. Chỉ lấy từ comment của video outlier ≥10x.",
                  "Cách dùng: (1) chọn theme lớn nhất KHỚP với bet ở sheet Recommended → bet đó mạnh hơn; (2) đọc phần NGUYÊN VĂN để lấy đúng NGÔN NGỮ của khán giả cho tiêu đề/hook.",
                  "VÍ DỤ: theme 'pin lắp thế nào' 45 câu + bet 'quantum computing' → video 'Quantum computing: 5 câu hỏi ai cũng thắc mắc' dùng lại chính từ ngữ trong comment."])
    # Horizontal layout: Themes (sc=1) | Spacer col E | Top Questions (sc=6) — scroll right thay vì xuống
    data_r=r
    ws.cell(row=data_r,column=1,value="THEME (tự khám phá — xếp theo số câu hỏi)").font=H2
    end_th=tbl(ws,data_r+1,["Theme","# câu hỏi","% tổng","Ví dụ"],
        [[t["theme"],t["count"],f'{t["pct"]}%'," | ".join(cl(e["q"])[:40] for e in t["examples"][:2])] for t in gaps["themes"]],
        [28,8,7,40],sc=1,freeze=False)
    ws.column_dimensions["E"].width=2
    ws.cell(row=data_r,column=6,value="CÂU HỎI ĐƯỢC LIKE NHIỀU NHẤT (like cao = mỗi câu là 1 ý tưởng video)").font=H2
    end_tq=tbl(ws,data_r+1,["Câu hỏi","Likes","Video","Link"],
          [[cl(q["q"]),q["like"],q["video"],q["url"]] for q in gaps["top_questions"]],
          [40,8,28,26],sc=6,freeze=False)
    ws.freeze_panes="A2"
    r=max(end_th,end_tq)+1
    ws.cell(row=r,column=1,value="NGUYÊN VĂN THEO THEME (đọc để copy đúng lời lẽ của khán giả vào tiêu đề/hook)").font=H2; r+=1
    for t in gaps["themes"]:
        ws.cell(row=r,column=1,value=f'{t["theme"]} ({t["count"]})').font=H2; r+=1
        r=tbl(ws,r,["Câu hỏi","Likes","Video","Link"],[[cl(e["q"]),e["like"],e["video"],e["url"]] for e in t["examples"]],[30,10,28,26])+1
    toc("Questions","Khán giả đang hỏi gì mà chưa ai trả lời?","Biến theme lớn thành video; copy ngôn ngữ thật của khán giả vào tiêu đề/hook",
        "gaps.json","chỉ từ comment của outlier ≥10x; đã lọc câu hỏi engagement")

# ============================ EXECUTION PLAN ============================
ws=wb.create_sheet("Execution Plan"); ws["A1"]="KẾ HOẠCH THỰC THI (verdict 1 trang)"; ws["A1"].font=TT; ws.merge_cells("A1:C1")
r=usage(ws,2,["Bản nén 1 trang để HÀNH ĐỘNG — mọi thứ ở đây đều đã có bằng chứng ở các sheet khác.",
              "Điều kiện KILL = tiêu chí bỏ niche, viết sẵn TRƯỚC khi bắt đầu để khỏi tự lừa mình về sau (ví dụ: '10 video đầu không video nào đạt OX ≥ 2 → dừng').",
              "Danh sách 'Video nên làm đầu tiên' lấy từ bets đã qua phản biện — làm theo thứ tự, mỗi video là 1 phép thử A/B có chủ đích."])
if plan:
    rows=[("VERDICT",plan.get("verdict")),
          ("Vì sao",("  •  ".join(plan.get("reasons",[])) if isinstance(plan.get("reasons"),list) else plan.get("reasons"))),
          ("Đầu cầu",plan.get("beachhead")),("DNA (1 dòng)",plan.get("dna_one_line")),
          ("Điều kiện KILL",plan.get("kill")),("Độ tin cậy",plan.get("confidence")),("Giả định",plan.get("assumptions"))]
    for lbl,val in rows:
        ws.cell(row=r,column=1,value=lbl).font=H2
        vv=ws.cell(row=r,column=2,value=val if isinstance(val,str) else json.dumps(val,ensure_ascii=False)); vv.font=NM; vv.alignment=Alignment(wrap_text=True)
        ws.merge_cells(start_row=r,start_column=2,end_row=r,end_column=3); r+=2
    if plan.get("first_videos"):
        r=tbl(ws,r,["Video nên làm đầu tiên"],[[x] for x in plan["first_videos"]],[90])
else:
    ws.cell(row=r,column=1,value="Chưa chạy — đây là tầng LLM (S13).").font=H2
    ws.cell(row=r+1,column=1,value="Chạy: python3 orchestrator.py llm <project> --agent plan  rồi build lại report.").font=NM
ws.column_dimensions["A"].width=20; ws.column_dimensions["B"].width=90; ws.freeze_panes="A1"
toc("Execution Plan","Cụ thể làm gì trong 10 video đầu?","Làm theo danh sách; dừng theo điều kiện KILL",
    "execution_plan.json","LLM diễn giải số Python — không tự tính số mới")

# ============================ RECOMMENDED (VIDEO NÊN LÀM) + DISAGREEMENTS ============================
audited=_load("bets_audited.json"); cand=_load("bets.json")
VCOL={"CLONE NOW":PWD,"CLONE":VNL,"STRONG":PWD,"TEST":AQU,"SKIP":None,"WEAK":None}
def _confn(cv):
    cv=str(cv or "").upper()
    return 3 if ("HIGH" in cv or "CAO" in cv) else 1 if ("LOW" in cv or "THẤP" in cv or "TENTATIVE" in cv) else 2
if audited or cand:
    ws=wb.create_sheet("Recommended")
    if audited:
        am=audited.get("_meta",{})
        two=bool(am) and am.get("auditor_provider") and am.get("auditor_provider")!=am.get("default_provider")
        lbl=(f"Auditor = {am.get('auditor_provider','?')} KHÁC model mặc định — leg phản biện độc lập thật" if two
             else f"Auditor cùng model mặc định ({am.get('auditor_provider','không rõ — file cũ')}) — DESIGN-ONLY VERIFY, "
                  f"đặt AUDITOR_LLM_PROVIDER để có phản biện 2 model thật")
        ws["A1"]="VIDEO NÊN LÀM — bets đã qua Auditor phản biện (mặc định REFUTE; input đã bóc kết luận Builder — R-0)"
        r=usage(ws,2,[lbl,
            "Ưu tiên theo verdict (màu nóng = gấp): CLONE NOW (HỒNG, làm NGAY) → CLONE (KEM, làm sớm) → TEST (XANH NGỌC, thử 1 video) → SKIP (xem sheet Disagreements).",
            "Cột 'Sai nếu…' = điều kiện tự bác bỏ của từng bet — dán vào ghi chú khi A/B: nếu điều đó xảy ra, dừng bet đó không tiếc.",
            "VÍ DỤ đọc 1 hàng: đề tài lift 4.2 · 5 kênh · Σexcess 12M · tin cậy HIGH → làm 1-2 video theo angle gợi ý, đo OX sau 45 ngày."])
        rws=[[x.get("topic"),x.get("verdict"),x.get("angle"),x.get("provenance"),x.get("lift"),
              x.get("n_channels"),x.get("sum_excess"),x.get("concentration"),x.get("coherence"),
              x.get("median_age_days"),x.get("confidence"),x.get("reason"),x.get("falsifier"),
              " | ".join(x.get("examples",[])[:2])] for x in audited.get("final_bets",[])]
    else:
        ws["A1"]="VIDEO NÊN LÀM — ỨNG VIÊN (CHƯA PHẢN BIỆN) — chạy Auditor (--llm) để gộp/loại và chốt verdict"
        r=usage(ws,2,["Đây mới là ứng viên do Python tổng hợp — verdict là ngưỡng số, KHÔNG phải phán đoán. Chạy Auditor trước khi đặt cược tiền/thời gian."])
        rws=[[x.get("term"),x.get("builder_verdict"),"(angle do Auditor đặt)",x.get("streams"),x.get("lift"),
              x.get("n_channels"),x.get("sum_excess"),x.get("concentration"),x.get("coherence"),
              x.get("median_age_days"),"TENTATIVE" if x.get("generic_risk") else "—",
              x.get("gap_match") or "",x.get("falsifier"),
              " | ".join(e.get("title","")[:40] for e in x.get("evidence",[])[:2])] for x in (cand or {}).get("bets",[])]
    ws["A1"].font=TT; ws.merge_cells("A1:N1")
    bet_hdr=r
    end=tbl(ws,r,["Đề tài","Verdict","Angle","Nguồn tín hiệu","Lift","#kênh","Σexcess",
                  "Tập trung","Mạch lạc","Tuổi (ngày)","Tin cậy","Lý do","Sai nếu…","Ví dụ"],rws,
            [26,11,40,16,7,6,12,10,10,9,11,40,40,46])
    for rr in range(r+1,end):
        vd=ws.cell(row=rr,column=2).value
        fl=VCOL.get(vd)
        if fl:
            for c in range(1,15): ws.cell(row=rr,column=c).fill=fl
        if vd=="CLONE NOW":
            ws.cell(row=rr,column=2).font=Font(name=F,bold=True,size=10)
    toc("Recommended","Nên làm video về đề tài nào?","Làm CLONE NOW/CLONE trước; mỗi bet kèm điều kiện tự bác bỏ ('Sai nếu…')",
        "bets_audited.json (fallback bets.json)","corroboration: lift=1 nguồn, +gap=2 (không đếm kép)")
    ws=wb.create_sheet("Disagreements")
    ws["A1"]="BẤT ĐỒNG CÒN LẠI — mọi bet bị REFUTE/UNCERTAIN kèm lý do (công khai, không giấu)"; ws["A1"].font=TT; ws.merge_cells("A1:C1")
    r=usage(ws,2,["Đọc để biết Auditor đã LOẠI những gì và vì sao — đây là phần 'phản biện' được in công khai.",
                  "Nếu bạn vẫn tin một bet bị loại: được, nhưng đó là quyết định CÓ Ý THỨC của bạn — hãy tự đặt điều kiện KILL riêng trước khi làm."])
    if audited:
        drows=[[d.get("topic"),d.get("label"),d.get("reason")] for d in audited.get("disagreements",[])]
    else:
        drows=[[x.get("term"),"WEAK (pre-audit)","generic_risk — Auditor cần xác nhận/loại"]
               for x in (cand or {}).get("bets",[]) if x.get("builder_verdict")=="WEAK"]
    tbl(ws,r,["Đề tài","Nhãn","Lý do"],drows,[26,18,90])
    toc("Disagreements","Cái gì đã bị loại, vì sao?","Rà lại trước khi bỏ hẳn một hướng","bets_audited.json","phụ lục trung thực — bắt buộc in")

# ============================ EARLY SIGNALS ============================
ws=wb.create_sheet("Early Signals")
ws["A1"]=f"TÍN HIỆU SỚM — video <{MATURITY_DAYS} ngày tuổi: EARLY-CONFIRMED đã tính vào bằng chứng, THEO DÕI thì chưa"
ws["A1"].font=TT; ws.merge_cells("A1:I1")
r=usage(ws,2,[f"Hàng HỒNG (EARLY-CONFIRMED) = views đã ≥ {OUTLIER_OX}× median CHÍN của kênh → OX lúc chín chắc chắn ≥ {OUTLIER_OX} (chặn dưới toán học) — dùng làm bằng chứng được NGAY.",
              "Hàng KEM (THEO DÕI) = OX theo shape tuổi non cao nhưng CHƯA vượt median kênh — chỉ quan sát, chưa phải bằng chứng; bấm 🔄 Refresh sau vài tuần để tool tự chấm lại.",
              "VÍ DỤ dùng: 2 kênh khác nhau cùng có EARLY-CONFIRMED về một đề tài trong 3 tuần = sóng đang lên — cân nhắc chen vào TRƯỚC khi bão hòa."])
er=[["EARLY-CONFIRMED",x["channelTitle"],x["title"],round(x["age"] or 0),x["viewCount"],x["scale"],
     x.get("ox_lb"),x["ox"],f"https://youtu.be/{x['videoId']}"] for x in sorted([w for w in win if w.get("early")],key=lambda z:-z.get("excess",0))]
wr=[["THEO DÕI",x["channelTitle"],x["title"],round(x["age"] or 0),x["viewCount"],x["scale"],
     x.get("ox_lb"),x["ox"],f"https://youtu.be/{x['videoId']}"] for x in sorted(watch,key=lambda z:-z.get("viewCount",0))[:40]]
end=tbl(ws,r,["Trạng thái","Kênh","Tiêu đề","Tuổi (ngày)","Views","Median chín kênh","Views/median","OX (shape non)","Link"],
        er+wr,[16,18,46,10,11,13,11,11,26])
for rr in range(r+1,end):
    if ws.cell(row=rr,column=1).value=="EARLY-CONFIRMED":
        for c in range(1,10): ws.cell(row=rr,column=c).fill=PWD
    else:
        for c in range(1,10): ws.cell(row=rr,column=c).fill=VNL
toc("Early Signals","Sóng nào đang nổi trong 6 tuần gần nhất?","Hàng hồng dùng được ngay; hàng kem đợi chín hoặc theo dõi thủ công",
    "videos.json (fresh)","cột 'Views/median' là chặn dưới của OX lúc chín")

# ============================ CHANNELS ============================
ws=wb.create_sheet("Channels")
ws["A1"]="KÊNH & ĐỘ PHỦ DỮ LIỆU — kết luận của tool chỉ đứng vững trên phần dữ liệu này"; ws["A1"].font=TT; ws.merge_cells("A1:J1")
r=usage(ws,2,[f"Kênh '#Valid=0' (hàng XANH NHẠT) KHÔNG đóng góp baseline — thiếu {MIN_BASE_VIDEOS} video chín cùng format. Nhiều hàng xanh nhạt = kết luận toàn cục yếu đi → thêm kênh đối thủ rồi Refresh.",
              "Coverage = số video đã scan ÷ tổng video của kênh (Short đã bị chặn nên coverage có thể thấp hơn thực với kênh đăng nhiều Short). Hàng KEM (PRUNED?, coverage <0.7) = scan chưa phủ hết upload.",
              "VÍ DỤ đọc: kênh 500k sub, coverage 0.95, 40 valid, 6 winner = nguồn bằng chứng tốt; kênh 1M sub nhưng 0 valid = to mà không đóng góp gì cho baseline."])
crows=[]
for cid,i in chinfo.items():
    st=per_ch[cid]; vc=int(i.get("videoCount") or 0)
    cov=round(st["scanned"]/vc,2) if vc else 0
    pruned="PRUNED?" if (vc and 0<cov<0.7) else ""
    nobase="KHÔNG BASELINE" if st["valid"]==0 else ""
    crows.append([i["title"],int(i.get("subs") or 0),vc,st["scanned"],cov,st["valid"],st["win"],nobase or pruned,
        f"https://www.youtube.com/channel/{cid}"])
crows.sort(key=lambda r:-r[1])
end=tbl(ws,r,["Kênh","Subscribers","Tổng video","Đã scan","Coverage","#Valid (primary)","#Winner","Cờ","Link"],crows,[30,13,11,9,10,13,9,15,44])
for rr in range(r+1,end):
    flag=ws.cell(row=rr,column=8).value
    if flag=="KHÔNG BASELINE":
        for c in range(1,10): ws.cell(row=rr,column=c).fill=LBL
    elif flag=="PRUNED?":
        for c in range(1,10): ws.cell(row=rr,column=c).fill=VNL
toc("Channels","Dữ liệu phủ được bao nhiêu thị trường?","Kiểm tra trước khi tin điểm số; thêm kênh nếu quá nhiều hàng xanh nhạt/kem",
    "channels.json + videos.json","subs hiện tại ≠ subs lúc đăng (R-A)")

# ============================ VOCABULARY (gộp từ vựng nền + cụm từ lặp lại) ============================
ws=wb.create_sheet("Vocabulary")
ws["A1"]="TỪ VỰNG CỦA NICHE — từ khóa lõi · tags · cụm 2/3/4 từ (KHÔNG phải danh sách chọn đề tài)"; ws["A1"].font=TT; ws.merge_cells("A1:U1")
r=usage(ws,2,["Đây là BẢN ĐỒ NGÔN NGỮ của niche — dùng để phủ SEO, đặt tags, viết mô tả, và 'nói đúng giọng' của thị trường.",
              "KHÔNG dùng sheet này để chọn đề tài (tần suất ≠ hiệu quả): muốn chọn ĐỀ TÀI thắng → sheet Topic Lift; muốn công thức TIÊU ĐỀ → sheet Title Templates.",
              "Phần cụm 2/3/4 từ GIỮ nguyên stopword có chủ đích — vì đây là CẤU TRÚC câu ('how to survive…', 'the truth about…'), không phải chủ đề."])
# Horizontal layout: 5 blocks side by side — scroll right thay vì scroll xuống
uni=sorted(b.get("unigrams",[]),key=lambda x:(-x["channels"],-x["freq"]))
data_r=r
blocks=[
    (1,  "TỪ KHÓA LÕI (theo độ phủ kênh)",             ["Từ khóa","# video","# kênh","Tổng views","Views TB"],
     [[x["key"],x["freq"],x["channels"],x.get("total_views",0),x.get("avg_views",0)] for x in uni],[22,9,8,13,11]),
    (7,  "TAGS PHỔ BIẾN (do đối thủ đặt)",              ["Tag","# video","# kênh"],
     [[x["key"],x["freq"],x["channels"]] for x in b.get("tags",[])[:100]],[22,9,8]),
    (11, "CỤM 2 TỪ (cấu trúc ngôn ngữ)",               ["Cụm từ","# video","# kênh"],
     [[x["key"],x["freq"],x["channels"]] for x in b.get("bigrams",[])[:100]],[22,9,8]),
    (15, "CỤM 3 TỪ",                                    ["Cụm từ","# video","# kênh"],
     [[x["key"],x["freq"],x["channels"]] for x in b.get("trigrams",[])[:100]],[22,9,8]),
    (19, "CỤM 4 TỪ",                                    ["Cụm từ","# video","# kênh"],
     [[x["key"],x["freq"],x["channels"]] for x in b.get("fourgrams",[])[:100]],[22,9,8]),
]
for sc_,lbl,hdr,rws,w in blocks:
    ws.cell(row=data_r,column=sc_,value=lbl).font=H2
    tbl(ws,data_r+1,hdr,rws,w,sc=sc_,freeze=False)
# spacer columns between blocks
for sp in [6,10,14,18]:
    ws.column_dimensions[get_column_letter(sp)].width=2
ws.freeze_panes="A2"
toc("Vocabulary","Niche này nói bằng từ vựng gì?","Nền cho SEO/tag/mô tả + khung câu — không dùng chọn đề tài",
    "analysis.json (unigrams/tags/n-grams)","tần suất ≠ hiệu quả; n-gram giữ stopword có chủ đích")

# ============================ TITLE TEMPLATES ============================
ws=wb.create_sheet("Title Templates")
ws["A1"]="CÔNG THỨC TIÊU ĐỀ — template · mở đầu tiêu đề · từ nhấn mạnh (kèm ví dụ tiêu đề thật)"; ws["A1"].font=TT; ws.merge_cells("A1:N1")
r=usage(ws,2,["Dùng SAU KHI đã chọn đề tài ở sheet Topic Lift/Recommended — sheet này trả lời 'VIẾT tiêu đề thế nào'.",
              "TEMPLATE: {NUM}/{NAME}/{YEAR}/{CAPS} là chỗ điền biến. VÍ DỤ: template '{NUM} things about {NAME}' + đề tài 'black holes' → '7 things about Black Holes'.",
              "Ưu tiên hàng có # kênh cao (nhiều kênh cùng dùng = convention của niche, không phải thói quen 1 kênh). Cột 'Ví dụ tiêu đề thật' ưu tiên lấy từ video THẮNG."])
# Horizontal layout: 3 blocks side by side — scroll right thay vì scroll xuống
SEC14=[
    (1,  "TEMPLATE TIÊU ĐỀ (cấu trúc đã trừu tượng hóa)","templates",
     "Khung tiêu đề hoàn chỉnh — chọn 1 template, điền đề tài + biến vào chỗ trống."),
    (6,  "MỞ ĐẦU TIÊU ĐỀ (3 từ đầu phổ biến nhất)","openers",
     "3 từ ĐẦU TIÊN của tiêu đề — phần người xem đọc trước nhất, quyết định có click hay không."),
    (11, "TỪ NHẤN MẠNH (viết HOA trong tiêu đề)","emphasis",
     "Từ được kênh CỐ TÌNH VIẾT HOA để hút mắt (INSANE, NEVER…). Dùng tiết chế: 1 từ HOA/tiêu đề là đủ."),
]
data_r=r
for sc_,lbl,key,note in SEC14:
    ws.cell(row=data_r,column=sc_,value=lbl).font=H2
    ws.cell(row=data_r+1,column=sc_,value=note).font=GY
    tbl(ws,data_r+2,["Nội dung","# video","# kênh","Ví dụ tiêu đề thật"],
        [[x["key"],x["freq"],x["channels"]," | ".join(x.get("examples",[]))] for x in b.get(key,[])],
        [28,7,7,36],sc=sc_,freeze=False)
# spacer columns between blocks
for sp in [5,10]:
    ws.column_dimensions[get_column_letter(sp)].width=2
ws.freeze_panes="A2"
toc("Title Templates","Viết tiêu đề thế nào?","Ghép đề tài (Topic Lift) vào template/mở đầu có # kênh cao",
    "analysis.json (templates/openers/emphasis + ví dụ thật)","template hóa thô — đọc kèm ví dụ thật cùng hàng")

# ============================ PATTERNS ============================
ws=wb.create_sheet("Patterns")
ws["A1"]="PATTERNS LẶP LẠI — cụm từ khóa của outlier xuất hiện ở ≥3 KÊNH, xếp theo Σ excess (reach tuyệt đối)"
ws["A1"].font=TT; ws.merge_cells("A1:E1")
r=usage(ws,2,["LUẬT VÀNG: 1 outlier = manh mối; ≥3 outlier tương tự Ở CÁC KÊNH KHÁC NHAU = công thức lặp lại được → mới đáng đặt cược.",
              "Xếp theo Σexcess (tổng views vượt kỳ vọng) chứ KHÔNG theo OX thô — OX cao trên kênh tí hon là artifact thống kê, không phải cơ hội.",
              "VÍ DỤ đọc: 'quantum' · 9 outlier · 5 kênh · Σexcess 40M = 5 kênh khác nhau đều nổ khi làm đề tài này, tổng cộng vượt kỳ vọng 40M views."])
kw_ch=defaultdict(set); kw_ex=defaultdict(int); kw_n=defaultdict(int); kw_titles=defaultdict(list)
for x in win:
    for w in set(tokenize(x["title"])):
        kw_ch[w].add(x["channelId"]); kw_ex[w]+=max(x["excess"],0); kw_n[w]+=1; kw_titles[w].append((x["excess"],x["channelTitle"],x["title"]))
pat=[]
for w in kw_ch:
    if len(kw_ch[w])>=3 and kw_n[w]>=3:
        ex=sorted(kw_titles[w],reverse=True)[:3]
        pat.append([w,kw_n[w],len(kw_ch[w]),kw_ex[w]," | ".join(f"{c}: {t[:40]}" for _,c,t in ex)])
pat.sort(key=lambda r:-r[3])
tbl(ws,r,["Cụm từ khóa","# outlier","# kênh","Σ excess views","Ví dụ tiêu biểu"],pat[:60],[20,10,9,16,80])
toc("Patterns","Công thức nào đang lặp lại thành công?","Nguyên liệu chính để chọn bet — ưu tiên Σexcess cao + nhiều kênh",
    "videos.json (winners)","lift/pattern là LIÊN HỆ, không nhân quả (R-3)")

# ============================ TOPIC LIFT ============================
ws=wb.create_sheet("Topic Lift")
ws["A1"]=(f"ĐỀ TÀI THẮNG THEO LIFT — over-index trong winners (≥{OUTLIER_OX}x) so với normal (<2x) · "
          f"winners:{b.get('n_winners','?')} (early:{b.get('n_early_confirmed',0)}) vs normal:{b.get('n_normal','?')}")
ws["A1"].font=TT; ws.merge_cells("A1:G1")
r=usage(ws,2,["Lift = từ/tag này xuất hiện trong video THẮNG nhiều gấp mấy lần so với video bình thường. Lift 3.0 = gấp 3 lần → tín hiệu đề tài mạnh.",
              "Dùng để CHỌN ĐỀ TÀI video thử nghiệm: chỉ tin hàng XANH NGỌC (FDR=yes — qua kiểm định thống kê) và ≥3 kênh; lift cao nhưng FDR=— chỉ là gợi ý yếu.",
              "VÍ DỤ đọc: 'quantum computing' lift 5.1 · FDR=yes · 5 kênh = video nhắc đề tài này thắng gấp 5 lần bình thường, trên 5 kênh khác nhau — đáng thử.",
              "Lift là LIÊN HỆ, không nhân quả (R-3) — thumbnail/thời sự/mùa vụ cũng đẩy views; xác nhận bằng A/B."])
lr=[["Từ đơn",x["key"],x["lift"],x["out"],x["non"],x["channels"],"yes" if x.get("sig") else "—"] for x in b.get("lift_unigrams",[])]
lr+=[["Cụm 2 từ",x["key"],x["lift"],x["out"],x["non"],x["channels"],"yes" if x.get("sig") else "—"] for x in b.get("lift_bigrams",[])]
lr+=[["Tag",x["key"],x["lift"],x["out"],x["non"],x["channels"],"yes" if x.get("sig") else "—"] for x in b.get("lift_tags",[])]
end=tbl(ws,r,["Loại","Từ khóa / tag","Lift","#outlier","#normal","#kênh","FDR sig"],lr,[10,26,9,10,10,9,9])
for rr in range(r+1,end):
    if ws.cell(row=rr,column=7).value=="yes":
        for c in range(1,8): ws.cell(row=rr,column=c).fill=AQU
toc("Topic Lift","Từ khóa/tag nào gắn với video thắng?","Chọn đề tài + từ đặt tiêu đề; ưu tiên FDR=yes, ≥3 kênh",
    "analysis.json (lift, BH-FDR step-up chuẩn)","cụm 2 từ đã lọc stopword — không còn 'the truth'")

# ============================ NICHE ANALYTICS (7 tiêu chí tiến hóa) ============================
wsNA=wb.create_sheet("Niche Analytics")
wsNA["A1"]="NICHE ANALYTICS — 7 TIÊU CHÍ PHÂN TÍCH TIẾN HÓA NICHE"
wsNA["A1"].font=TT; wsNA.merge_cells("A1:G1")
r=usage(wsNA,2,["Nguyên tắc: báo cáo đo QUAN HỆ (không phải mức) → kết thúc bằng QUYẾT ĐỊNH, không phải mô tả.",
                "Số views/kênh là mức, ai cũng đếm được; tiền nằm ở quan hệ giữa các đường cong.",
                "Cuối sheet: BẢNG CƯỢC — mỗi bet có điều kiện sai được, mỗi quyết định có ngày review."])

# ── TC1: TÁCH CUNG KHỎI CẦU ──────────────────────────────────────────────────
r+=1
wsNA.cell(row=r,column=1,value="TC1 — TÁCH CUNG KHỎI CẦU (sinh tồn: thiếu nó mọi thứ vô nghĩa)").font=H2
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
wsNA.cell(row=r,column=1,value="Cung = share sản lượng creator đang đổ vào; Cầu còn dư = hiệu năng trung bình age-adjusted của theme (OX/Lift). Lỗi chết người: chỉ nhìn một vế.").font=GY
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1

# Quadrant matrix 2x2
def _qcell(row,col,text,fill):
    c=wsNA.cell(row=row,column=col,value=text); c.fill=fill; c.font=Font(name=F,bold=True,size=10,color="1F3864")
    c.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True); c.border=BR
_qcell(r,  2,"↑ CẦU THẤP",BLU); _qcell(r,  3,"↑ CẦU CAO",BLU)
_qcell(r+1,1,"CUNG THẤP",BLU);  _qcell(r+1,2,"Mờ cạn thật — BỎ",LBL); _qcell(r+1,3,"KHOẢNG TRỐNG — VÀO NGAY",AQU)
_qcell(r+2,1,"CUNG CAO",BLU);   _qcell(r+2,2,"BÃO HÒA — TRÁNH",PWD);   _qcell(r+2,3,"SÓNG ĐANG LỚN — VÀO NHANH",VNL)
for col in [2,3]: wsNA.column_dimensions[get_column_letter(col)].width=24
wsNA.column_dimensions["A"].width=14; wsNA.row_dimensions[r+1].height=28; wsNA.row_dimensions[r+2].height=28
r+=4

# Theme quadrant table (based on lift = demand proxy, out+non = supply proxy)
unis=[x for x in b.get("lift_unigrams",[]) if x.get("lift") and (x.get("out",0)+x.get("non",0))>0][:40]
if unis:
    supplies=sorted(x["out"]+x["non"] for x in unis)
    med_supply=supplies[len(supplies)//2] if supplies else 1
    def _quad(lift,supply_total):
        hi_d=(lift or 0)>=2.0; hi_s=(supply_total>=med_supply)
        if hi_d and not hi_s: return "KHOẢNG TRỐNG",AQU
        if hi_d and hi_s:     return "SÓNG ĐANG LỚN",VNL
        if not hi_d and hi_s: return "BÃO HÒA",PWD
        return "Mờ cạn thật",LBL
    qrows=[]
    for x in unis[:20]:
        supply_total=x["out"]+x["non"]; quad,qfill=_quad(x["lift"],supply_total)
        qrows.append((x["key"],round(x["lift"],2),x["out"],x["non"],supply_total,quad,qfill))
    qrows.sort(key=lambda z:(-{"KHOẢNG TRỐNG":3,"SÓNG ĐANG LỚN":2,"Mờ cạn thật":1,"BÃO HÒA":0}[z[5]],-z[2]))
    wsNA.cell(row=r,column=1,value="Phân vùng từng từ khóa (Lift = cầu, #video = cung):").font=H2; r+=1
    end_q=tbl(wsNA,r,["Từ khóa","Lift (cầu)","# winner","# normal","Tổng video (cung)","Phân vùng"],
              [[z[0],z[1],z[2],z[3],z[4],z[5]] for z in qrows[:20]],[22,10,8,8,15,18],freeze=False)
    for rr in range(r+1,end_q):
        quad_val=wsNA.cell(row=rr,column=6).value
        fill_map={"KHOẢNG TRỐNG":AQU,"SÓNG ĐANG LỚN":VNL,"BÃO HÒA":PWD,"Mờ cạn thật":LBL}
        if quad_val in fill_map:
            for c in range(1,7): wsNA.cell(row=rr,column=c).fill=fill_map[quad_val]
    r=end_q
else:
    wsNA.cell(row=r,column=1,value="Không có dữ liệu lift — cần chạy S3 (2_keywords.py) trước.").font=GY; r+=1
r+=1

# ── TC2: ĐẠO HÀM (TIMING) ────────────────────────────────────────────────────
wsNA.cell(row=r,column=1,value="TC2 — ĐẠO HÀM, KHÔNG PHẢI GIÁ TRỊ (timing)").font=H2
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
wsNA.cell(row=r,column=1,value="Tiền nằm ở điểm uốn: ai đọc mức thì vào lúc đỉnh, ai đọc gia tốc thì vào lúc mọc.").font=GY
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
if dem:
    trend=dem.get("trend","?"); strength=dem.get("trend_strength",0); supply=dem.get("supply_per_month",0)
    phase=("MỌC — TĂNG TRƯỞNG" if trend=="RISING" and supply<10
           else "SÓNG ĐANG LỚN" if trend=="RISING"
           else "TÀN — TRÁNH" if trend=="DECLINING"
           else "BÃO HÒA")
    phase_fill={"MỌC — TĂNG TRƯỞNG":AQU,"SÓNG ĐANG LỚN":VNL,"BÃO HÒA":LBL,"TÀN — TRÁNH":PWD}[phase]
    tc2rows=[("Xu hướng (trend)",trend),("Độ mạnh trend",f"{strength:+.3f} (≥0.05=RISING, ≤-0.05=DECLINING)"),
             ("Cung/tháng",f"{supply} video upload/tháng — thước đo cạnh tranh"),
             ("Cầu trung vị",f"{dem.get('demand_median_views',0):,} views (video recent-matured điển hình)"),
             ("Pha vòng đời",phase)]
    end_t=tbl(wsNA,r,["Chỉ số","Giá trị / Diễn giải"],tc2rows,[22,60],freeze=False)
    for rr in range(r+1,end_t):
        if wsNA.cell(row=rr,column=1).value=="Pha vòng đời":
            for c in range(1,3): wsNA.cell(row=rr,column=c).fill=phase_fill
    r=end_t
else:
    wsNA.cell(row=r,column=1,value="Không có dữ liệu — cần chạy S7 (7_demand.py).").font=GY; r+=1
r+=1

# ── TC3: AI ĐANG LÀM (đường cong lây lan) ────────────────────────────────────
wsNA.cell(row=r,column=1,value="TC3 — AI ĐANG LÀM NÓ (đường cong lây lan theo cohort)").font=H2
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
wsNA.cell(row=r,column=1,value="Trật tự lây: innovator → early adopter → đại chúng → vét đáy. Nếu người mới vào toàn kênh yếu → bạn đến muộn.").font=GY
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
if crack:
    nr=crack.get("newcomer_rate",0); ad=crack.get("authority_dependence"); pr=crack.get("pattern_replicability",1)
    if nr>0.65:   diffusion_pos="Innovator / Early adopter ← IDEAL: vào ngay"; df=AQU
    elif nr>0.45: diffusion_pos="Crossing the chasm ← còn cơ hội sớm"; df=VNL
    elif nr>0.25: diffusion_pos="Đại chúng đang vào ← muộn, cần differentiated"; df=LBL
    else:         diffusion_pos="Late majority / Vét đáy ← tránh hoặc exit"; df=PWD
    tc3rows=[("Newcomer rate",f"{nr:.0%} outlier đến từ kênh nhỏ+trẻ (<2 năm, dưới trung vị sub)"),
             ("Authority dependence",f"{ad if ad is not None else 'N/A':.2f} (Spearman OX~subs; >0.6 = kênh lớn thống trị)"
              if ad is not None else "N/A — không đủ dữ liệu"),
             ("Pattern replicability",f"{pr:.1f} kênh/cluster (trung vị) — công thức có lan được sang kênh khác không"),
             ("Vị trí trên đường cong",diffusion_pos)]
    end_c=tbl(wsNA,r,["Chỉ số","Giá trị / Diễn giải"],tc3rows,[22,65],freeze=False)
    for rr in range(r+1,end_c):
        if wsNA.cell(row=rr,column=1).value=="Vị trí trên đường cong":
            for c in range(1,3): wsNA.cell(row=rr,column=c).fill=df
    r=end_c
else:
    wsNA.cell(row=r,column=1,value="Không có dữ liệu — cần chạy S5 (5_crackability.py).").font=GY; r+=1
r+=1

# ── TC4: ĐỘ TẬP TRUNG PHẦN THƯỞNG (HHI/Gini) ────────────────────────────────
wsNA.cell(row=r,column=1,value="TC4 — ĐỘ TẬP TRUNG PHẦN THƯỞNG (HHI per sub-niche)").font=H2
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
wsNA.cell(row=r,column=1,value="HHI cao → winner-take-all → ĐÁNH CHẤT (1 video xuất sắc). HHI thấp → phân tán → ĐÁNH SỐ (volume lớn).").font=GY
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
if sub and sub.get("clusters"):
    def _hhi_strat(hhi):
        if hhi>0.5: return "ĐÁNH CHẤT — winner-take-all",PWD
        if hhi>0.2: return "ĐÁNH CHẮC — cạnh tranh vừa",VNL
        return "ĐÁNH SỐ — phân tán",AQU
    hrows=[]
    for cl_ in sub["clusters"][:12]:
        strat,sfill=_hhi_strat(cl_["hhi"])
        lbl_=cl_.get("label") or cl_.get("anchor","?")
        hrows.append((lbl_,cl_["hhi"],cl_["n_channels"],cl_["n_outliers"],
                      cl_.get("outlier_newcomer_share","?"),strat,sfill))
    hrows.sort(key=lambda z:-z[1])
    wsNA.cell(row=r,column=1,value=f"HHI per sub-niche ({len(hrows)} cụm — xếp HHI giảm dần):").font=H2; r+=1
    end_h=tbl(wsNA,r,["Sub-niche","HHI","#kênh","#outlier","Newcomer share","Chiến lược"],
              [[z[0],z[1],z[2],z[3],z[4],z[5]] for z in hrows],[30,7,7,8,14,26],freeze=False)
    for rr in range(r+1,end_h):
        strat_val=wsNA.cell(row=rr,column=6).value or ""
        if "CHẤT" in strat_val:
            for c in range(1,7): wsNA.cell(row=rr,column=c).fill=PWD
        elif "CHẮC" in strat_val:
            for c in range(1,7): wsNA.cell(row=rr,column=c).fill=VNL
        elif "SỐ" in strat_val:
            for c in range(1,7): wsNA.cell(row=rr,column=c).fill=AQU
    r=end_h
else:
    wsNA.cell(row=r,column=1,value="Không có dữ liệu — cần chạy S9 (9_subniche.py).").font=GY; r+=1
r+=1

# ── TC5: TIẾNG NÓI PHÍA CẦU (comment) ───────────────────────────────────────
wsNA.cell(row=r,column=1,value="TC5 — TIẾNG NÓI PHÍA CẦU ĐỘC LẬP VỚI CREATOR (comment)").font=H2
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
wsNA.cell(row=r,column=1,value="Mọi metric 1-4 do creator sinh ra. Comment là kênh duy nhất khán giả nói trực tiếp: câu hỏi chưa trả lời = content gap; cảm xúc thay đổi = rủi ro hệ thống.").font=GY
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
if gaps and gaps.get("themes"):
    gp5rows=[[t["theme"],t["count"],f'{t["pct"]}%'," | ".join(e.get("q","")[:40] for e in t.get("examples",[])[:2])]
             for t in gaps["themes"][:8]]
    r=tbl(wsNA,r,["Theme câu hỏi","# câu hỏi","% tổng","Ví dụ (gap chưa có video trả lời)"],gp5rows,[24,10,8,60],freeze=False)
else:
    wsNA.cell(row=r,column=1,value="Không có dữ liệu comment — bỏ --skip-comments để chạy S4 (3_comments.py).").font=GY; r+=1
r+=1

# ── TC6 & TC7 side-by-side ───────────────────────────────────────────────────
data_67=r
wsNA.cell(row=data_67,column=1,value="TC6 — CÚ SỐC NGOẠI SINH & CHU KỲ BÁN RÃ").font=H2
wsNA.cell(row=data_67+1,column=1,value="Đo không phải 'có sóng' mà là HALF-LIFE: bao nhiêu ngày hiệu năng người đến sau rơi về nền.").font=GY
wsNA.cell(row=data_67+2,column=1,value="Ví dụ: Cape Verde first mover 955K views, người vào sau 5 ngày <3K — half-life tính bằng NGÀY.").font=GY
wsNA.cell(row=data_67+3,column=1,value="⚠ Chưa tính được từ API snapshot 1 lần — cần chuỗi thời gian đa điểm. Theo dõi trend thủ công bằng search volume ngoài tool.").font=Font(name=F,size=9,italic=True,color="D97B6C")
wsNA.merge_cells(start_row=data_67,  start_column=1,end_row=data_67,  end_column=3)
wsNA.merge_cells(start_row=data_67+1,start_column=1,end_row=data_67+1,end_column=3)
wsNA.merge_cells(start_row=data_67+2,start_column=1,end_row=data_67+2,end_column=3)
wsNA.merge_cells(start_row=data_67+3,start_column=1,end_row=data_67+3,end_column=3)

wsNA.column_dimensions["D"].width=2
wsNA.cell(row=data_67,column=5,value="TC7 — BIẾT DỮ LIỆU KHÔNG NÓI ĐƯỢC GÌ (chống tự lừa)").font=H2
wsNA.merge_cells(start_row=data_67,start_column=5,end_row=data_67,end_column=7)
residuals_7=[
    ("Survivorship bias","Video xóa/kênh terminate biến mất khỏi API — chỉ thấy người sống sót"),
    ("R-1 snapshot","1 lần quét trộn lẫn age/cohort/period — trend chỉ là chiều hướng, không nhân quả"),
    ("R-A subs hiện tại","Subs hiện tại ≠ subs lúc đăng — newcomer_rate là ước tính bảo thủ"),
    ("R-3 lift ≠ nhân quả","Lift là liên hệ, không phải nguyên nhân — thumbnail/thời sự cũng đẩy views"),
    ("Không có thumbnail lịch sử","API không trả thumbnail cũ — suy luận thumbnail là SUY LUẬN có nhãn"),
    ("RPM = heuristic","Doanh thu ước tính theo category — gắn nhãn 'ước lượng' khi dùng"),
]
for i,(label,desc) in enumerate(residuals_7):
    wsNA.cell(row=data_67+1+i,column=5,value=label).font=Font(name=F,bold=True,size=10)
    wsNA.cell(row=data_67+1+i,column=6,value=desc).font=NM
    wsNA.cell(row=data_67+1+i,column=6).alignment=Alignment(wrap_text=True)
    wsNA.merge_cells(start_row=data_67+1+i,start_column=6,end_row=data_67+1+i,end_column=7)
for c in [5,6,7]: wsNA.column_dimensions[get_column_letter(c)].width={"E":20,"F":35,"G":20}[get_column_letter(c)]
r=data_67+max(5,len(residuals_7)+2)+1

# ── BẢNG CƯỢC (falsifiable bets) ─────────────────────────────────────────────
r+=1
wsNA.cell(row=r,column=1,value="BẢNG CƯỢC — MỖI BET CÓ THỂ SAI ĐƯỢC (không có bảng cược = bài văn, không phải công cụ)").font=TT
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
wsNA.cell(row=r,column=1,value="Định dạng: [LỆNH] đề tài X → lý do (tiêu chí nào) → điều kiện sai → ngày review. Nếu điều kiện sai xảy ra: dừng bet, không tiếc.").font=GY
wsNA.merge_cells(start_row=r,start_column=1,end_row=r,end_column=7); r+=1
bet_list=[]
if audited and audited.get("final_bets"):
    bet_list=audited["final_bets"]
elif cand and cand.get("bets"):
    bet_list=cand["bets"]
if bet_list:
    import datetime as _dt
    review_date=(_dt.date.today()+_dt.timedelta(days=30)).isoformat()
    VBET={"CLONE NOW":PWD,"CLONE":VNL,"STRONG":AQU,"TEST":AQU,"SKIP":LBL,"WEAK":LBL}
    if audited and audited.get("final_bets"):
        bet_rows=[[x.get("topic") or x.get("term"),x.get("verdict"),
                   x.get("lift"),x.get("n_channels"),x.get("sum_excess"),
                   x.get("reason",""),x.get("falsifier",""),review_date] for x in bet_list[:15]]
    else:
        bet_rows=[[x.get("term"),x.get("builder_verdict"),
                   x.get("lift"),x.get("n_channels"),x.get("sum_excess"),
                   x.get("streams",""),x.get("falsifier",""),review_date] for x in bet_list[:15]]
    end_b=tbl(wsNA,r,["Đề tài","Verdict","Lift","#kênh","Σexcess","Lý do / Tín hiệu","Sai nếu…","Ngày review"],
              bet_rows,[26,11,7,7,12,36,40,12],freeze=False)
    for rr in range(r+1,end_b):
        v_val=str(wsNA.cell(row=rr,column=2).value or "")
        fl=VBET.get(v_val.upper())
        if fl:
            for c in range(1,9): wsNA.cell(row=rr,column=c).fill=fl
    r=end_b
else:
    wsNA.cell(row=r,column=1,value="Chưa có bets — cần chạy ít nhất S11 (11_synthesize_bets.py).").font=GY; r+=1

wsNA.freeze_panes="A2"
wsNA.column_dimensions["A"].width=22; wsNA.column_dimensions["B"].width=18
wsNA.column_dimensions["C"].width=10; wsNA.column_dimensions["G"].width=40
TOC.insert(0,("Niche Analytics","7 tiêu chí tiến hóa: cung/cầu · timing · HHI · diffusion · gaps · bets",
               "Đọc trước khi ra quyết định vào/ra; bảng cược cuối sheet","demand/crack/subniche/gaps/bets",
               "TC6 half-life chưa tính được từ API snapshot đơn"))

# ============================ SUMMARY (filled last, shown first) ============================
ws=wsSUM
ws["A1"]="TỔNG KẾT — ĐỌC SHEET NÀY TRƯỚC TIÊN"; ws["A1"].font=TT; ws.merge_cells("A1:E1")
r=usage(ws,2,["Đọc từ trên xuống: PHÁN QUYẾT → dữ liệu nền → bản đồ workbook (cột A-E) → toàn văn đánh giá (cột G, bên phải).",
              "Mỗi nhận định trong bản đánh giá phải trỏ về 1 con số + file nguồn; nhận định không có số → tra sheet bằng chứng (Patterns / Topic Lift / Videos) trước khi tin."])
if summ:
    mt=summ.get("_meta",{})
    ws.cell(row=r,column=1,value="PHÁN QUYẾT").font=H2
    vc=ws.cell(row=r,column=2,value=summ.get("verdict"))
    vc.fill=VZ.get(summ.get("verdict"),BLU); vc.font=Font(name=F,bold=True,size=14,color="1F3864")
    r+=1
    for lbl,key in [("Độ tin cậy","confidence"),("Đầu cầu","beachhead"),("Attractiveness","attractiveness")]:
        if summ.get(key) is not None:
            ws.cell(row=r,column=1,value=lbl).font=NM; ws.cell(row=r,column=2,value=_xl(summ.get(key))).font=NM; r+=1
    ws.cell(row=r,column=1,value="Phương pháp").font=NM
    ws.cell(row=r,column=2,value=f"1 model · tự phản biện {mt.get('passes',3)} lượt · model={mt.get('model','?')} · verdict lấy từ: "
            f"{'SAU phản biện' if mt.get('verdict_source')=='post-critique' else 'bản nháp (model không trả final)'} "
            f"· {mt.get('n_rejected',0)} khuyến nghị bị loại").font=GY; r+=2
else:
    ws.cell(row=r,column=1,value="Chưa chạy tầng LLM (S19) — chạy: python3 orchestrator.py llm <project> --agent summary rồi build lại report.").font=H2; r+=2
ws.cell(row=r,column=1,value="DỮ LIỆU NỀN (kết luận chỉ đứng vững trên phần dữ liệu này — chi tiết ở sheet Channels)").font=H2; r+=1
for t in [f"{len(chinfo)} kênh · {len(v):,} video đã scan · {len(valid_prim):,} video valid-primary làm bằng chứng",
          f"{len(win)} winner ≥{OUTLIER_OX}x (trong đó {n_early} early-confirmed fresh) · {len(watch)} tín hiệu sớm đang theo dõi (sheet Early Signals)",
          f"{len(ch_no_base)}/{len(chinfo)} kênh không đóng góp baseline · shape fallback: {shape_fb}/{len(prim)} video primary"]:
    ws.cell(row=r,column=1,value="• "+t).font=NM; r+=1
r+=1
ws.cell(row=r,column=1,value="THỨ TỰ ĐỌC ĐỀ XUẤT: Summary → Go-NoGo → Beachhead → Recommended → bằng chứng (Patterns · Topic Lift · Videos · Early Signals) → Execution Plan").font=GY; r+=2
ws.cell(row=r,column=1,value="BẢN ĐỒ WORKBOOK").font=H2; r+=1
tbl(ws,r,["Sheet","Trả lời câu hỏi gì","Hành động","Nguồn số","Lưu ý / độ tin cậy"],
    [list(t) for t in TOC],[24,36,40,26,40])
if summ:
    ws.cell(row=2,column=7,value="TOÀN VĂN ĐÁNH GIÁ (SUMMARY.md — bản đầy đủ nằm trong thư mục Report/)").font=H2
    rr=3
    for line in (summ.get("markdown","") or "").split("\n"):
        c=ws.cell(row=rr,column=7,value=line); c.font=NM; c.alignment=Alignment(wrap_text=True); rr+=1
    ws.column_dimensions["F"].width=3
    ws.column_dimensions["G"].width=115
ws.freeze_panes="A2"

wb.move_sheet(wsNA, -(len(wb.worksheets)-1))   # Niche Analytics = sheet đầu tiên
wb.save(OUT); print(f"saved {OUT} — {len(wb.sheetnames)} sheets: {' | '.join(wb.sheetnames)}")
print(f"winners={len(win)} (early:{n_early}) watch={len(watch)} | kênh 0-baseline={len(ch_no_base)} | shape_fallback={shape_fb}/{len(prim)}")
