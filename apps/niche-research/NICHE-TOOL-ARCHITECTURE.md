# NICHE INTELLIGENCE TOOL — Kiến trúc tổng hợp (để build bằng Claude Code)

> Một tool duy nhất: từ danh sách kênh đối thủ + API key → **một workbook tổng hợp** để vận hành một
> niche (bản đồ thị trường · quyết định Go/No-Go & đánh chiếm · DNA niche craft). File này là bản thiết
> kế; nó hợp nhất mọi spec đã có: `outlier_method.md`, `synthesis_critique_loop.md`,
> `dong_kiem_protocol.md`, `Execution-Plan-Report-Spec.md`, `padoma_dna_integration.md`.

---

## 0. NGUYÊN TẮC VÀNG — phân công Python vs LLM

> **Python làm mọi thứ ĐO ĐƯỢC. LLM làm mọi thứ PHẢI HIỂU. Không bao giờ đảo vai.**

| | PYTHON (tất định) | LLM (phán đoán ngữ nghĩa) |
|---|---|---|
| Làm gì | I/O API, số học, thống kê, gom nhóm theo luật, render | Hiểu nghĩa, đặt tên, phân loại theo cơ chế, phản biện, viết |
| Vì sao | Rẻ, lặp lại được, unit-test được, không ảo giác số | Không có công thức đúng cho "đây có phải một chủ đề mạch lạc" |
| Cấm | ❌ đừng bắt Python "đoán chủ đề" bằng regex/keyword thô | ❌ đừng bao giờ để LLM cộng/chia/tính OX/lift/CI |
| Kiểm thử | pytest trên số cố định | eval + đối chiếu 2 model |

**Ba hệ quả kiến trúc bất biến:**
1. **Seam = JSON có schema.** Python và LLM chỉ nói chuyện qua file JSON typed. Mỗi tầng: PY ghi JSON →
   LLM đọc JSON + bằng chứng thô, ghi JSON → PY render. LLM luôn bị đóng khung bởi schema đầu ra.
2. **LLM không bao giờ chạm số.** Mọi con số (OX, lift, Σexcess, concentration, Spearman) do Python
   tính sẵn và ĐƯA cho LLM như dữ kiện. LLM chỉ *diễn giải/xếp hạng định tính*, không tính lại.
3. **Verify = hai model.** Các leg kiểm chứng (Auditor bets, phân loại DNA) chạy bởi **model KHÁC** với
   model Builder, cách ly thông tin (residual R-0 của `outlier_method.md`).

---

## 1. PIPELINE — DAG các tầng (mỗi tầng gắn [PY] / [LLM])

```
competitors.txt (+ .env keys)
      │
 [PY] S1  scan videos ............... youtube API ......... videos.json (+ tags, +channel_age)
 [PY] S2  OX v3 compute ............. _common.py ........... (mutate videos: ox/expected/excess/valid/scope)
 [PY] S3  keywords + lift + FDR ..... analysis.json
 [PY] S4  comments + questions ...... gaps.json           (theme = cluster PY; NAMING có thể nhờ LLM ở S4b)
 [LLM]S4b (tuỳ chọn) đặt tên theme ... gaps.json.themes[].label
      │
 ── DECISION 1 (Go/No-Go) ───────────────────────────────────────────────
 [PY] S5  crackability + provenance . crackability.json   (newcomer_rate, Spearman(OX,subs), pattern_repl)
 [PY] S6  monetization heuristic .... monetization.json   (RPM table lookup + sponsor regex)
 [PY] S7  demand & trend ............ demand.json
 [PY] S8  attractiveness score+gate . decision1.json      (weighted + Crackability hard-gate)
      │
 ── DECISION 2 (đánh chiếm) ──────────────────────────────────────────────
 [PY] S9  sub-niche clustering ...... subniche.json       (TF-IDF/graph; số liệu mỗi cụm)
 [LLM]S9b đặt tên cụm + browse/search subniche.json.clusters[].label
 [PY] S10 beachhead scoring ......... decision2.json      (geomean có sàn / competition^0.5)
 [PY] S11 synth candidate bets ...... bets.json           (lift-seed + 4 signals + Builder verdict)
 [LLM]S12 AUDITOR (model khác) ...... bets_audited.json   (merge/name/prune + CLONE NOW/TEST/SKIP)
 [LLM]S13 Execution Plan (verdict) .. execution_plan.json (1 trang: verdict+beachhead+DNA-1dòng+KILL)
      │
 ── SUB-NICHE DEEP-DIVE + DNA (cho sub-niche đã chọn) ────────────────────
 [PY] S14 deep-dive ................. deepdive_<x>.json + 00-danh-sach-video-<x>.md
 [PY] S15 fetch transcripts ......... transcripts/NN.txt   (transcript API)
 [LLM]S16 DNA extraction (2 vòng) ... dna.json            (hook/structure/voice/emotion/terms/avoid)
 [LLM]S17 phân loại CHUẨN MẪU/... ... dna.json (nhãn cơ chế, phi-metric)
      │
 [PY] S18 build report .............. <niche>_report.xlsx  (render MỌI json thành sheet)
```

Nhánh có thể dừng ở S13 (Execution Plan) nếu chưa chọn sub-niche; S14–S17 chạy sau khi chọn.

---

## 2. HỢP ĐỒNG DỮ LIỆU (JSON seams — nguồn chân lý giữa các tầng)

Mỗi file có JSON Schema trong `contracts/`. Đây là API nội bộ — đổi schema = đổi hợp đồng, phải versioned.

| Artifact | Ghi bởi | Đọc bởi | Nội dung lõi |
|---|---|---|---|
| `competitors.txt` | user | S1 | keys `AIza…` + channel URLs |
| `videos.json` | S1/S2 | mọi tầng | video + tags + OX v3 fields |
| `analysis.json` | S3 | S11,S14,S18 | lift_unigrams/bigrams, core kw, templates, openers, emphasis |
| `gaps.json` | S4 | S11,S18 | themes[], top_questions |
| `channels.json` | S1 | S5,S18 | subs, videoCount, **publishedAt (tuổi kênh)** |
| `crackability.json` | S5 | S8,S18 | newcomer_rate, authority_dependence, verdict OPEN/SEMI/CLOSED |
| `monetization.json` | S6 | S8,S18 | rpm_band, sponsor_density, override-gate |
| `decision1.json` | S8 | S13,S18 | 5 trụ + attractiveness + GO/NO-GO |
| `subniche.json` | S9/S9b | S10,S14,S18 | clusters[] {label, size, HHI, crack, money, Σexcess, browse_vs_search} |
| `decision2.json` | S10 | S13,S18 | beachhead ranking + lý do |
| `bets.json` | S11 | S12 | candidate bets + 4 signals + falsifier |
| `bets_audited.json` | S12 | S18 | final_bets[] + disagreements[] |
| `execution_plan.json` | S13 | S18 | verdict 1 trang |
| `deepdive_<x>.json` | S14 | S18 | keywords 3 tầng · tags · content_outliers |
| `00-danh-sach-video-<x>.md` | S14 | S15 | URL list đã-thẩm-định-bằng-OX |
| `transcripts/NN.txt` | S15 | S16 | transcript thô |
| `dna.json` | S16/S17 | S18 | hook_patterns/structures/emotions/voice/strong_lines/hook_keywords/terms/avoid |
| `<niche>_report.xlsx` | S18 | user | tài liệu tổng hợp cuối |

---

## 3. BẢN ĐỒ MODULE (Claude Code scaffold theo đây)

```
niche-tool/
├── .env                       # YOUTUBE_API_KEY, TRANSCRIPT_API_KEY, MAX_COMMENTS
├── contracts/                 # JSON Schema cho MỌI artifact ở §2 (thẩm định I/O mỗi tầng)
│   ├── videos.schema.json ... dna.schema.json ...
├── scripts/                   # === PYTHON (tất định) ===
│   ├── _common.py             # OX v3 (single source of truth) + API client + jload/jsave
│   ├── 1_scan.py              # S1  (đã có; giữ tags + thêm channel publishedAt)
│   ├── 2_keywords.py          # S3  (đã có)
│   ├── 3_comments.py          # S4  (đã có)
│   ├── 5_crackability.py      # S5  (MỚI)
│   ├── 6_monetization.py      # S6  (MỚI)
│   ├── 7_demand.py            # S7  (MỚI, nhẹ)
│   ├── 8_decision1.py         # S8  (MỚI — score + gate)
│   ├── 9_subniche.py          # S9  (MỚI — cluster)
│   ├── 10_decision2.py        # S10 (MỚI — beachhead)
│   ├── 11_synthesize_bets.py  # S11 (đã có: 5_synthesize_bets.py)
│   ├── 14_deepdive.py         # S14 (đã có: 9_subniche_deepdive.py)
│   ├── 15_fetch_transcripts.py# S15 (đã có: 10_fetch_transcripts.py)
│   └── 18_build_report.py     # S18 (đã có: 4_build_report.py — render mọi json)
├── agents/                    # === LLM (task specs, không phải code) ===
│   ├── auditor.md             # S12: Builder≠Auditor; input bets.json → bets_audited.json
│   ├── subniche_namer.md      # S9b: cụm số liệu → label + browse/search
│   ├── execution_plan.md      # S13: mọi decision json → verdict 1 trang
│   └── dna_extractor.md       # S16/S17: transcripts → dna.json (prompt-dna-v4, 2 vòng, phi-metric)
├── references/                # method docs (đã có) — LLM đọc để tuân thủ
│   ├── outlier_method.md · synthesis_critique_loop.md · dong_kiem_protocol.md
│   ├── Execution-Plan-Report-Spec.md · padoma_dna_integration.md
└── orchestrator.py            # điều phối DAG (§4): gọi PY, spawn LLM-agent, kiểm schema, resume
```

Quy ước: **mọi tầng PY là 1 script chạy độc lập** `python3 N_xxx.py WORK [args]`, đọc/ghi JSON trong
`WORK/`. Mọi tầng LLM là **1 file `agents/*.md`** mô tả input JSON + output schema + guardrails +
model. Orchestrator ghép chúng; Claude Code có thể chạy tay từng bước hoặc để orchestrator lo.

---

## 4. ĐIỀU PHỐI (orchestrator.py) — engineering rules

- **DAG + idempotent:** mỗi tầng khai báo `inputs[]`, `outputs[]`. Bỏ qua nếu output mới hơn input
  (như Make). Chạy lại an toàn.
- **Resumable I/O:** S1/S3/S15 (gọi API) checkpoint sau mỗi page/video; giết giữa chừng → chạy lại
  tiếp tục (đã có ở 1_scan/3_comments). Sandbox giết shell ~45s → gọi lặp đến khi in `DONE`.
- **Schema gate:** sau mỗi tầng, validate output theo `contracts/*.schema.json`. Sai schema ⇒ dừng
  sớm, không để lỗi trôi xuống tầng sau.
- **Spawn LLM có kiểm soát:** tầng [LLM] = gọi 1 agent với (a) đúng JSON input, (b) yêu cầu ghi ĐÚNG
  output schema. Auditor (S12) **bắt buộc model khác** Builder; nếu chỉ 1 model, ghi nhãn "design-only
  verify" (leg số suy biến — xem `dong_kiem_protocol.md §4`).
- **Cost guard:** LLM chỉ chạy ở tầng cần hiểu (S9b,S12,S13,S16,S17). Ước tính token/quota trước S15
  (transcript tốn tiền) và S1 (YouTube quota). In cảnh báo.
- **Fail isolation:** một sub-niche/video lỗi không được giết cả run; log + skip + báo tổng kết.

---

## 5. ĐẶC TẢ TỪNG TẦNG LLM (agents/*.md) — input · output · guardrail · model

**S12 auditor.md** — *Builder ≠ Auditor.*
- IN: `bets.json` (candidate + 4 signals) + bằng chứng thô (titles/channels). KHÔNG cho xem lập luận Builder.
- OUT (schema): `bets_audited.json` = `final_bets[]{topic,verdict,angle,provenance,…,reason,falsifier,terms}` + `disagreements[]`.
- Guardrail: mặc định REFUTE; merge biến thể; loại seed generic bằng `coherence`+titles; verdict CLONE NOW/CLONE/TEST/SKIP; công khai mọi REFUTE/UNCERTAIN; **không tính lại số**.
- Model: khác Builder (vd Builder=Opus → Auditor=Sonnet).

**S9b subniche_namer.md** — IN: `subniche.json.clusters[]` (số liệu + top keywords/titles). OUT: mỗi cụm thêm `label` (người-đọc-hiểu) + `browse_vs_search`. Guardrail: đặt tên theo nội dung chung, không theo từ đơn generic. Model: nhỏ.

**S13 execution_plan.md** — IN: `decision1.json`+`decision2.json`+`bets_audited.json`. OUT: `execution_plan.json` (VERDICT+3 lý do, beachhead+1 câu, DNA 1 dòng, 10 video đầu, KILL, confidence+giả định). Guardrail: chỉ diễn giải số PY đã tính; gắn nhãn confidence; không tô hồng.

**S16/S17 dna_extractor.md** — *phi-metric.*
- IN: `transcripts/` của outlier sub-niche + `00-danh-sach-video`. KHÔNG dùng views/sub/OX để chấm.
- OUT (schema `dna.schema.json`): hook_patterns/structures/emotions/voice/strong_lines/hook_keywords/terms/avoid + nhãn CHUẨN MẪU/THAM KHẢO/LỆCH mỗi video.
- Guardrail: theo `prompt-dna-v4` 2 vòng; trích **nguyên văn** câu mạnh (không chế); phân loại theo *cơ chế giữ chân*, không theo số; tách rõ **lớp khám phá vs trung thành** (`padoma_dna_integration.md`).
- Model: mạnh (craft); nhãn phân loại nên 2-model hoặc người xác nhận.

---

## 6. VÌ SAO SPLIT NÀY TỐI ƯU (biện luận dev 20 năm)

- **Đúng công cụ cho đúng việc:** OX/lift/Spearman là toán — Python cho kết quả *bit-identical* mỗi lần,
  unit-test được, không tốn token, không ảo giác. "Đây có phải một chủ đề" là ngữ nghĩa — không có công
  thức, LLM là công cụ đúng. Ép sai vai = vừa đắt vừa sai (LLM cộng số sai; regex "đoán chủ đề" ra
  "most/true/scientists").
- **Seam JSON = khả kiểm + thay thế:** vì LLM chỉ nhận/nhả JSON typed, có thể (a) test từng tầng độc
  lập, (b) đổi model không đụng Python, (c) người can thiệp tay ở bất kỳ seam nào (sửa `bets_audited.json`
  trước khi render). LLM không bao giờ là hộp đen giữa dòng.
- **Số bất biến, chữ có thể tái tạo:** rerun cho cùng số (Python tất định); phần LLM có thể chạy lại/đổi
  model mà không phá tính đúng của số — vì số đã chốt ở tầng PY trước đó.
- **Chi phí tuyến tính theo giá trị:** 90% khối lượng (scan, thống kê, render) chạy Python gần như miễn
  phí; token LLM chỉ tiêu ở 5 tầng thực sự cần hiểu.
- **Verify không tự lừa:** leg phản biện dùng model KHÁC + trọng-tài-bằng-code cho tranh chấp số →
  giảm điểm mù chung (R-0).

---

## 7. THỨ TỰ BUILD cho Claude Code (tăng dần, test từng bước)

1. **Kết dính lõi đã có:** đổi tên các script hiện có về sơ đồ §3, thêm `contracts/` + `orchestrator.py`
   (chỉ chạy S1–S3 + S18) → ra report cơ bản. *Test:* rerun idempotent, schema gate.
2. **Decision 1:** `5_crackability.py` (rẻ nhất, quyết định nhất) → `6_monetization` → `7_demand` →
   `8_decision1`. *Test:* Go/No-Go trên data thật.
3. **Decision 2:** `9_subniche` + agent `subniche_namer` → `10_decision2` → agent `execution_plan`.
   *Test:* beachhead + verdict 1 trang.
4. **Bets loop:** `11_synthesize_bets` → agent `auditor` (2 model). *Test:* Final bets + Bất đồng.
5. **Deep-dive + DNA:** `14_deepdive` → `15_fetch_transcripts` → agent `dna_extractor` → `18_build_report`
   render DNA sheets. *Test:* workbook tổng hợp đầy đủ.

Mỗi bước: Python có pytest trên fixture số cố định; agent có 1–2 eval case. Không sang bước sau khi
bước trước chưa xanh — đúng tinh thần "chắc từng bước" đã theo suốt dự án.

---

## 8. RÀNG BUỘC TRUNG THỰC (kế thừa toàn hệ)

Mọi số dưới giả định APC-A của OX (R-1); RPM là heuristic; sub-niche ranh mềm; DNA là phán đoán craft;
newcomer_rate lệch do `subs tại lúc đăng` không có từ API (R-A). Report luôn in nhãn confidence + phụ lục
bất đồng. Kết quả là **đặt cược có thông tin để A/B test**, không phải chân lý.
