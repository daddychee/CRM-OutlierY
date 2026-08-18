# AUDIT-LOG — Nhật ký rà soát & cải tiến (đọc file này để tiếp tục nếu mất hội thoại)

## ĐỢT 3 (2026-07-02, lần 6) — RÀ CUỐI + SHORTS GATE + ĐẠI TU SUMMARY ✅ (3 yêu cầu user, test OK)

### 1. Rà logic lần cuối — 4 bug tìm được, đã fix hết
- ✅ **B1** `18_build_report.py` — 7 banner CÁCH DÙNG vẫn mô tả MÀU CŨ (XANH/VÀNG/ĐỎ) sau Gói B →
  sửa thành HỒNG/KEM/XANH NGỌC/XANH NHẠT khớp palette mới (Videos/Beachhead/DNA/Recommended/
  Early Signals/Channels/Topic Lift + 2 dòng TOC).
- ✅ **B2** `9_subniche.py` — thang điểm seed trộn lẫn: seed fallback (điểm = #kênh) có thể vượt seed
  lift (điểm = 100+lift) khi corpus >100 kênh → video bị gán nhầm cụm. Fix: cap fallback ở 99.
- ✅ **B3** `11_synthesize_bets.py` — docstring ghi sai "STEP 5 / 5_synthesize_bets.py" → STEP 11.
- ✅ **B4** `run_agent.py` — evidence pack cho summary THIẾU `tags`/`lift_tags` (fix trong mục 3).
- Logic lõi (OX v3, BH-FDR step-up, winners/normals, trend OX-theo-tháng, HHI recent-window,
  PAUSE/resume quota, salvage JSON parser) rà lại toàn bộ — KHÔNG phát hiện lỗi mới.

### 2. SHORTS GATE — chặn Short hoàn toàn (mặc định BẬT)
- `_common.shorts_gate_on()` + chặn NGAY ĐẦU `compute_outliers`: `videos[:] = [không-Short]` (mutate
  in-place → list của MỌI caller đều sạch Short: S3/S4/S5/S7/S8/S9/S11/S14/S15/S18/evidence-pack).
  In cảnh báo to nếu >50% pool là Short (niche Shorts-first).
- `1_scan.py`: không LƯU Short ngay từ scan (tiết kiệm dung lượng; project cũ được compute gate lọc).
- `6_monetization.py` (script duy nhất không gọi compute_outliers): tự lọc riêng.
- Tắt bằng `SHORTS_GATE=off` trong .env (đã ghi vào .env.example). Report in số Short bị chặn ở phần
  ĐỘ PHỦ (Beachhead cột M) + banner Videos.
- Test: 180 video (36 Short) → mọi stage thấy đúng 144; Short không lọt vào winners (n_outliers=0).

### 3. ĐẠI TU SUMMARY — chuyên gia 35 năm + WINNING FORMAT (summary bị chê khó hiểu)
- `run_agent._evidence_pack` thêm số Python đo (LLM chỉ diễn giải, đúng luật vàng):
  `top_tags`+`lift_tags` (B4) · `title_features` (% tiêu đề winners VS normals có CAPS/số/năm/dấu hỏi
  + độ dài trung vị — "quy luật phối ngẫu" đo được) · `format_mix` mở rộng (share % + p25/p75 độ dài
  + n_normals để so) · `cadence` (median uploads/tháng của kênh active 90 ngày) ·
  `browse_share_weighted` (tỷ trọng browse toàn niche, weighted theo size cụm) · `shorts_blocked`.
- `agents/summary.md` viết lại toàn bộ: persona **chuyên gia 35 năm, bậc thầy quy luật phối ngẫu**;
  5 QUY TẮC DỄ HIỂU (SỐ→NGHĨA→LÀM · giải nghĩa thuật ngữ tại chỗ · bảng + câu đọc-bảng · kết luận in
  đậm cuối mục · câu ≤35 từ); cấu trúc 10 mục mới với **§1 WINNING FORMAT 6 tiểu mục bắt buộc**
  (1.1 thời lượng/định dạng · 1.2 chủ đề & sub-format có bảng ví dụ thật + Σexcess · 1.3 công thức
  tiêu đề từ title_features · 1.4 thumbnail = SUY LUẬN CÓ NHÃN từ browse share + emphasis (không có
  dữ liệu ảnh — cấm bịa) · 1.5 tags · 1.6 nhịp đăng) + khung 1 câu "Winning formula = …";
  §6 GIÁ TRỊ CHƯNG CẤT (insight xâu chuỗi: low moat, bẫy concentration, mâu thuẫn keyword-thắng vs
  demonetization); §7 KILL SWITCH bằng số. Giữ nguyên vòng 3 lượt (user đã chốt).
- 3 prompt lượt trong `run_summary` cập nhật khớp: P1 bắt trả khung `winning_format` 6 trường;
  P2 thêm câu hỏi "người thường đọc có hiểu?" + "thumbnail có bịa?"; P3 chỉ định §1 đủ 6 tiểu mục.
- Lưu ý: summary MỚI cần chạy lại agent (`orchestrator.py llm <project> --agent summary`) mới thấy
  format mới; project cũ evidence pack tự có trường mới (Python side), không cần force scan.

## GÓI B (2026-07-02, lần 5) — PALETTE MỚI + LAYOUT NGANG + BỎ CHART ✅ (test end-to-end OK)

Toàn bộ thay đổi trong `scripts/18_build_report.py`:
- **Palette nhiệt độ mới**: Blue Slate #5E6472 (header) · Powder Blush #FFA69E (nóng: >10x/CLONE NOW/NO-GO/CAO) · Vanilla Cream #FAF3DD (ấm: 5-10x/CLONE/CONDITIONAL/PRUNED) · Icy Aqua #B8F2E6 (mát: GO/FDR-sig/Beachhead #1) · Light Blue #AED9E0 (lạnh: SKIP/KHÔNG BASELINE). Font Calibri. Xoá hoàn toàn GRN/GRN_D/WT/RED/YLW/BLK cũ.
- **Bỏ toàn bộ biểu đồ** (BarChart Go-NoGo, BarChart Beachhead, BarChart Questions, ScatterChart Recommended) — xoá luôn import chart + hàm `_bars_green()` + helper cols P/Q trong Recommended.
- **Layout ngang** (scroll phải thay vì xuống): Vocabulary (5 khối: Keywords|Tags|2-gram|3-gram|4-gram, spacer col 6/10/14/18 width=2, merge A1:U1), Title Templates (3 khối: Templates|Openers|Emphasis, spacer col 5/10 width=2, merge A1:N1), Questions (Themes|Top Questions cạnh nhau, spacer col E width=2, merge A1:I1; Raw by Theme đặt bên dưới sau max(end_th, end_tq)).
- `tbl()` nâng cấp: param `sc` (start column, default=1) + `freeze=False` cho block ngang (caller set freeze_panes một lần); column width chỉ tăng không giảm (max-width approach) để các block dùng chung cột không tranh nhau.
- `hd()` nhận param `sc` tương ứng.
- Màu cụ thể: Beachhead CHỌN chip + hàng #1 → AQU; DNA lỗi CAO → PWD; Recommended VCOL: CLONE NOW/STRONG→PWD, CLONE→VNL, TEST→AQU, SKIP/WEAK→None; Early Signals EARLY-CONFIRMED→PWD, THEO DÕI→VNL; Channels KHÔNG BASELINE→LBL, PRUNED?→VNL; Topic Lift FDR-sig→AQU; Summary verdict chip → VZ.get(verdict, BLU) với font màu 1F3864.
Test: 15 sheet đúng thứ tự + tên, không còn màu cũ, không crash, compile OK.
Lưu ý: project cũ dùng layout cũ (stacked vertical) — cần `--force` để build lại report với layout mới.

## ĐỢT 2 (2026-07-02, lần 4) — ĐẠI TU REPORT ✅ (11 yêu cầu user đã chốt, test end-to-end OK)

`18_build_report.py` viết lại toàn bộ + `2_keywords.py` + `3_comments.py` sửa nhỏ:
1. ✅ Banner CÁCH DÙNG mọi sheet viết lại chi tiết hơn, có VÍ DỤ đọc, 100% tiếng Việt.
2. ✅ Tab name 100% TIẾNG ANH, thứ tự mới cố định 15 sheet: `Summary → Videos → Go-NoGo → Beachhead
   → DNA Niche → Questions → Execution Plan → Recommended → Disagreements → Early Signals → Channels
   → Vocabulary → Title Templates → Patterns → Topic Lift` (07/08 cũ = Patterns/Topic Lift, để cuối,
   KHÔNG gộp). Sheet "00 Hướng dẫn đọc" bỏ — funnel + bản đồ workbook (TOC) chuyển vào Summary.
3. ✅ Gộp sheet: 12+13 → **Vocabulary**; 15+16+17 → **Questions**; 18-23 → **DNA Niche** (1 sheet,
   chia section 2 lớp khám phá/trung thành).
4. ✅ Sheet 99 OX bỏ — toàn văn phương pháp OX (KHÔNG rút gọn) đặt BÊN PHẢI bảng Beachhead (cột M).
5. ✅ "Final bets" → tab **Recommended**, tiêu đề trong sheet "VIDEO NÊN LÀM".
6. ✅ Title Templates: thêm cột "Ví dụ tiêu đề thật" (2_keywords.py xuất `examples` ưu tiên video thắng,
   dedupe); section đổi tên "MỞ ĐẦU TIÊU ĐỀ (3 từ đầu phổ biến nhất)" + "TỪ NHẤN MẠNH (viết HOA)".
7. ✅ 3_comments.py lọc câu hỏi engagement/meta TẠI NGUỒN trước khi ghi gaps.json: regex ENGAGE
   ("who else", "can you pin", "ai còn xem"…), độ dài tối thiểu 15 ký tự, và loại câu hỏi 0 từ-nội-dung
   (sau khi trừ stopword động) — themes lẫn top_questions đều sạch.
8. ✅ Trực quan: font Arial → **Calibri**; palette ưu tiên XANH LÁ (1E8449 đậm / D5F5E3 nhạt)=cao/tốt ·
   VÀNG (F9E79F)=trung bình/theo dõi · ĐỎ (F1948A)=thấp/cảnh báo (VZ/VCOL/bracket/cờ kênh đổi theo);
   4 biểu đồ openpyxl: Go-NoGo (bar trụ điểm) · Beachhead (bar ngang xếp hạng) · Questions (bar theme)
   · Recommended (scatter Lift × Tin cậy, cột helper P/Q) — mỗi chart bọc try/except, lỗi chỉ skip.
Test: dataset giả 181 video/6 kênh chạy S3→S18 + artifact LLM giả → đủ 15 sheet, 4 chart, chip màu đúng;
bản KHÔNG có LLM → 13 sheet (DNA/Questions tự skip), fallback đúng; py_compile + regex ENGAGE test OK.
Lưu ý khi chạy thật: project cũ cần `--force` (analysis.json cũ chưa có `examples` — cột ví dụ sẽ trống
nhưng không lỗi; gaps.json cũ chưa lọc engagement).

## ĐỢT 1 — 24 lỗi V1–V24

> Cập nhật: 2026-07-02 (lần 3). **TẤT CẢ 24 LỖI ĐÃ SỬA ✅ và đã test end-to-end trên dataset giả**
> (seed 181 video/6 kênh có outlier + newcomer + fresh trồng sẵn → chạy S3→S5→S6→S7→S8→S9→S10→S11→S18,
> kiểm tra từng output khớp ground truth; py_compile 18 file OK; test parser JSON + GUI import + orchestrator status OK).
> CHƯA test được trên dữ liệu THẬT với YouTube API + LLM key — lần chạy thật đầu tiên nên để ý mục "Cần theo dõi" cuối file.

## V7 — kết luận vòng phản biện (đã cài đúng như chốt)

Quy tắc fresh 2 tầng của user: fresh có `views ≥ 3 × scale` (median CHÍN của kênh) = **early-confirmed**
(chặn dưới toán học của OX lúc chín, miễn nhiễm noise shape) → tính là bằng chứng đầy đủ ở MỌI stage,
cờ `early=true`; fresh còn lại → sheet "09 Tin hieu som" chỉ để theo dõi, không vào winners, không bao giờ vào normal.
Cài tại `_common.py` (`x["early"]`, `x["ox_lb"]`, helper `winners()/normals()`) — mọi stage dùng chung một định nghĩa.

## DANH SÁCH LỖI — trạng thái sau khi sửa (2026-07-02)

### HIGH
- ✅ **V10** `1_scan.py` — 3 đường mất dữ liệu im lặng khi hết quota → PAUSE đúng quy ước (mid-channel, mid-page `vdetails` trả `(rows, error)`, resolve kênh không lưu channels.json dở dang). Kèm: DONE giờ ghi `scan_meta.json` (mốc thời gian scan).
- ✅ **V7** — quy tắc 2 tầng ở trên; các stage lệch nhau (S3/S4/S9/S14/evidence-pack) đều chuyển sang `winners()/normals()` chung.
- ✅ **V1** — bỏ ±12 trend khỏi `7_demand.score`; trend chỉ còn là trụ riêng trong S8.
- ✅ **V2** — `10_decision2`: opportunity = money(global) × per-cluster `outlier_newcomer_share` (S9 tính, dùng `compute_newcomers` chung với S5); fallback về crack_scale cho file cũ.
- ✅ **V15** `orchestrator.py` — khai đủ inputs cho S8/S9/S10/S11/S13/S19/S18 (S18 giờ liệt kê đủ 15 artifact nó render); `cmd_llm` rebuild report kể cả khi file report bị xóa.

### MEDIUM
- ✅ **V3** — trend chạy trên **median OX theo tháng** (khử tuổi bằng chính maturity curve), loại video `scale_borrowed`.
- ✅ **V4** — BH-FDR step-up chuẩn (tìm max-i rồi đánh dấu toàn bộ 1..i).
- ✅ **V5** — vocab lift-bigram lọc stopword (seed + dynamic); S9 lọc anchor bằng `BASE_STOP ∪ analysis.stop_dynamic`; hợp nhất 5 bản toks/STOP chép tay về `_common.tokenize` (S5, S11, S14, S18, evidence-pack).
- ✅ **V6** — corroboration = 1 (lift) + 1 (gap); streams đổi nhãn `lift(outlier)`; docstring giải thích vì sao không đếm kép.
- ✅ **V8** `8_decision1` — trụ thiếu = None, trọng số re-normalize trên trụ có dữ liệu, ghi `pillars_missing`; test: bỏ monetization.json → attractiveness 61 (thay vì ~49 do phạt 0 như cũ).
- ✅ **V9** — replicability dùng `n_outlier_channels` mới của subniche.json (kênh CÓ outlier trong cụm); bar quyết định cũng đổi theo.
- ✅ **V11** — `AGE_EDGES` thêm cạnh 45 → bucket không còn trộn non/chín quanh mốc maturity.
- ✅ **V12** — `get_scan_time()`: mọi stage tính OX với `now` = thời điểm scan (scan_meta.json → mtime videos.json → wall clock); hết drift giữa các lần build.
- ✅ **V16** `run_agent.run_auditor` — strip `builder_verdict/generic_risk/falsifier/topic_group` khỏi input Auditor (R-0); ghi `_meta{auditor_provider, default_provider}` vào bets_audited.json; `agents/auditor.md` sửa lại phần Input cho khớp.
- ✅ **V17** — (a) verdict/confidence/beachhead của summary lấy từ block `final` SAU lượt phản biện (fallback bản nháp, ghi `verdict_source`); (b) sheet 01 đề trung thực "1 model · tự phản biện 3 lượt"; sheet 05 in nhãn "DESIGN-ONLY VERIFY" khi Auditor cùng model mặc định, chỉ nhận "2 model" khi provider khác nhau.
- ✅ **V20** — DNA đọc transcript kiểu đầu(3500)+giữa(1500)+cuối(1500) có đánh dấu đoạn, thay vì cắt 6000 ký tự đầu.

### LOW
- ✅ **V13** — `shape_of` trả kèm nguồn (`exact/neighbor/flat`) → `x["shape_src"]`; report in "% video dùng shape fallback" ở sheet 00 + 99, cảnh báo khi >30%.
- ✅ **V14a** — comment stoplist sửa thành ">8%" khớp code.
- ✅ **V14b** — S6 cue chuyển sang danh sách CỤM TỪ phân cách bằng dấu phẩy, khớp word-boundary unicode (lookaround) — "đầu tư", "passive income" giờ khớp nguyên cụm; đồng thời bỏ trùng cue giữa category.
- ✅ **V14c** — sheet Videos xếp mặc định: bằng chứng trước theo Σexcess (đúng luật vàng), thêm cột Early; dead code `grp` đã xóa (file viết lại).
- ✅ **V14d** — funnel độ phủ: sheet 00 (tóm tắt) + sheet 11 "Channels & do phu" (#valid, #winner, cờ KHÔNG BASELINE) + thống kê trong sheet 99.
- ✅ **V18** `llm_provider._escape_control_chars` — `'\\\\'` → `'\\'`; test hồi quy: string chứa `\"` + newline thô parse đúng.
- ✅ **V19** — đứt stream giữa chừng giờ in cảnh báo "returning PARTIAL output" (cả Anthropic lẫn OpenAI-compatible).
- ✅ **V21** — `up_to_date` so `oldest(outputs) >= newest(inputs)` (đúng ngữ nghĩa Make).
- ✅ **V22** — S15 bare-id fallback chỉ nhận dòng LÀ CHÍNH XÁC 11 ký tự id (fullmatch).
- ✅ **V23** — GUI nhớ `deepdive_anchor` từ .state.json, START truyền lại `--deepdive <anchor>`.
- ✅ **V24** — S14 nhận label → tự map về anchor của cluster (đọc subniche.json); không match thì CẢNH BÁO to rồi mới fallback.

## Việc kèm theo trong đợt sửa (gói D/E/F — user duyệt "fix tất cả")

- ✅ **D — tái cấu trúc report**: `18_build_report.py` viết lại toàn bộ. Sheet đánh số 00→99 theo khối:
  00 Hướng dẫn đọc (funnel + bảng TOC: sheet nào trả lời gì/hành động/nguồn số/lưu ý) · 01-06 KẾT LUẬN ·
  07-11 BẰNG CHỨNG (thêm **09 Tin hieu som**) · 12-17 NGUYÊN LIỆU · 18-23 DNA · 99 Phương pháp (Việt hóa
  toàn bộ, chuyển từ đầu xuống cuối). Mỗi sheet có banner "CÁCH DÙNG" 1-3 dòng. Sheet lift gộp từ đơn +
  cụm 2 từ + TAG vào "08 De tai thang (lift)" có cột Loại.
- ✅ **E — funnel độ phủ** (xem V14d).
- ✅ **F — tags**: S3 xuất `tags` (tần suất + độ phủ kênh) và `lift_tags` vào analysis.json; render ở sheet 08 (lift) + 12 (nền).

## Cần theo dõi ở lần chạy THẬT đầu tiên (chưa test được vì cần API/LLM key)

1. S1 với quota thật: xác nhận PAUSE/resume hoạt động khi hết quota giữa kênh (thay vì DONE thiếu dữ liệu như cũ).
2. S12 Auditor: kiểm tra bets_audited.json có `_meta` và sheet 05 in đúng nhãn 1-model/2-model.
3. S19 summary: model có trả block `final` ở lượt 2 không (nếu không, verdict fallback bản nháp + `verdict_source:"draft"` — vẫn đúng, chỉ kém lý tưởng).
4. Project CŨ (scan trước bản vá): chưa có `scan_meta.json` → `get_scan_time` dùng mtime videos.json (đúng); subniche.json cũ chưa có `n_outlier_channels` → S10 tự fallback. Muốn số liệu chuẩn mới: chạy `resume` (S3+ sẽ tự stale vì code mới hơn? KHÔNG — up_to_date so mtime input/output, code đổi không làm stale → dùng `--force` một lần cho project cũ).

## Ghi chú vận hành

- `--force` một lần cho các project đang dở để mọi artifact được tính lại bằng logic mới.
- Mọi phát hiện/lỗi mới → cập nhật file này NGAY (quy ước của user).
