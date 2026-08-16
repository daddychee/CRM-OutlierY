# CONTENT ULTIMATE V2 — MASTER BRIEF (file duy nhất, tự chứa)

> **Dành cho Claude Code trong VSCode.** File này gộp toàn bộ nghiên cứu + quyết định
> + spec triển khai V2, đủ để làm việc mà không cần đọc lại 4 file gốc
> (`DE-XUAT-cong-thuc-veritasium.md`, `TEST-veritasium-tren-run-bigbang.md`,
> `TEST-viet-thu-hook-chuong1.md`, `content_ultimate_v2.md` — giữ làm archive).
> Phần audit prompt ở §6 viết từ CODE THẬT (generator.py/compose.py/suggest.py
> đọc ngày 2026-07-25), không phải từ trí nhớ.
>
> **Đọc trước khi code:** CLAUDE.md của repo vẫn là luật nền — TRỪ một điểm được user
> sửa ngày 2026-07-25, ghi ở §4 (sửa luật A3, có phạm vi rõ). Mọi thứ khác của
> CLAUDE.md (A1, A2, A4, A5, A6, B*, C*) giữ nguyên hiệu lực.

---

# PHẦN I — KIẾN THỨC (toàn bộ nghiên cứu, nén nhưng đủ)

## 1. Công thức và gốc bằng chứng của nó

**V = (M + (Q→E)) × (A+B)** — từ video "Veritasium - why he still gets views"
(The Internet Stamp, 13/07/2026 — bản thân nó 1,06M view / 70,7x outlier).

Gốc là thí nghiệm PhD của Derek Muller (dạy trọng lực, đo pre/post test trên 26 điểm):

| Video cho học sinh xem | Học sinh nói | Điểm 6 → ? |
|---|---|---|
| Giải thích RÕ RÀNG | "clear, concise, easy" | **6.3** (≈0 tác dụng) |
| Mở bằng MISCONCEPTION, gây bối rối | "confusing" | **11** (≈gấp đôi) |

Cơ chế: não tưởng đã biết → không chú ý ("không khó để chú ý video rõ ràng vì tôi
ĐÃ BIẾT họ nói gì" — nói bởi học sinh vừa trượt bài test). Đập vỡ cái "tưởng đã
biết" trước, não mới mở cửa.

**Ba biến:**
- **M (Misconception)** — vì sao họ BẤM và ở lại 30s đầu. Sống ở title/thumbnail +
  câu mở hook. Misconception lớn nhất về packaging: title KHÔNG phải để nói chủ đề
  (bằng chứng: "Throwing shade balls" → "Why are there 96 million black balls on
  this lake?" = video viral nhất kênh; một video đổi mỗi thumbnail đi từ tệ nhất
  kênh → tốt nhất kênh).
- **Q→E (Question trước, Explanation sau)** — vì sao họ ở lại giữa video. Trường học
  làm ngược (đáp án trước, hỏi sau). Nêu câu hỏi trước → phần giải thích thành phần
  thưởng. Chuỗi vòng mở-đóng lặp suốt video, không chỉ ở hook.
- **A+B (hai sợi đan nhau)** — vì sao họ sống sót qua đoạn kỹ thuật. Kỹ thuật điện
  ảnh: sợi A (khái niệm) mỏi → cắt sang B (hiện trường/nhân vật/chuyện); B kỹ thuật
  quá → về A. Giá trị của B là ĐỔI KÊNH CẢM NHẬN, không phải liên quan chủ đề.

**Đọc đúng ký hiệu:** + là chuỗi nối tiếp; **× là phép nhân — (A+B)=0 thì V=0 bất kể
hook hay cỡ nào**, và ngược lại M=0 thì không ai bấm để mà giữ. Hai vế không bù được.

**Bốn thứ công thức KHÔNG nói (tự vá trong V2):**
1. Packaging là quá trình LẶP (Internet Stamp đổi title/thumbnail 4 lần/5 ngày,
   VPH +347%) — ngoài phạm vi tool, nhưng đừng tưởng công thức đã phủ.
2. **M phải là misconception THẬT của khán giả** — đoán sai thì hook sập. Đây là chỗ
   Content Ultimate mạnh hơn Derek: mình ĐO được từ comment (§2), anh ta phải đoán.
3. B-plot của Derek là quay thật — kênh script+voice phải dịch B thành sợi kể
   chuyện/nhân vật/lịch sử trong văn bản.
4. Không có biến payoff — ending phải TRẢ NỢ vòng tò mò của hook (return viewership).

## 2. Bằng chứng đo trên dữ liệu thật (run `bigbang`: 6 video, 1.800 comment)

**Audit outline V1 của run bigbang — trượt cả 3 biến:**
- Hook trả lời ngay ở giây 0 ("we have a good understanding… provided we define it
  as…") — vòng tò mò đóng trước khi mở.
- 0/7 phần mở bằng câu hỏi; brief toàn "Introduce/Explain/Reveal" (explanation-first).
- 7/7 phần cùng sợi A trừu tượng; Ch2/Ch3 trùng lõi (cùng inflation của Guth);
  2 tên chương bị cụt (brief thô tràn vào tên); ending mở 3 nợ mới không trả nợ cũ;
  title nói chủ đề.

**Công thức "sống" trong sóng:**
- Comment #1 TOÀN SÓNG 11.594❤ (AstroKobi): "We weren't lied to. We were told the
  most accurate interpretation at the time…" = khán giả phản ứng với M-framing.
- 9.000❤ (Kurzgesagt): "I just cannot wrap my head around what's the 'nothing'
  outside the universe is" = vòng tò mò chưa trả lời lớn nhất sóng.
- 2.817❤ (PBS): "who gets totally confused half way through but just keeps watching
  anyway?" = thí nghiệm PhD của Derek tái hiện ngoài đời.
- 716❤: "Video start 'The big bang wasn't an explosion' — *My life is a lie*" =
  khoảnh khắc M phát nổ, ghi bằng chữ.
- 324/1.800 comment (18%) chứa câu hỏi = kho Q nguyên văn, mỗi câu kèm likes.

**Bảng cộng hưởng misconception theo theme** (Python đếm, ước lượng dưới):
before-Big-Bang 70 · singularity 60 · from-nothing 25 · explosion 23 ·
expanding-into-what 12 · faster-than-light 4.

## 3. Hai kết quả thí nghiệm đã chốt (2026-07-25)

**(a) M-mining v1 BỊ BÁC — ghi vào sổ ĐÃ THỬ VÀ BÁC BỎ:**
regex mẫu câu ("I thought / I was taught / misconception…") trên 1.800 comment →
**17 match (0,9%), đa số nhiễu** ("I thought you were family friendly"). Khán giả
không tự khai misconception bằng mẫu câu; họ để lộ qua CHỦ ĐỀ họ hỏi/cãi.
**Đừng làm lại pattern-phrase trên comment.**
→ **M-mining v2 (cách đúng, đã chạy thử sạch):** mỏ neo từ BEAT ĐÍNH CHÍNH trong
`beats.json` — S3 (LLM) đã label sẵn từ transcript: pattern hẹp
`not X but Y / no longer believe / X is wrong / school-taught / myth` bắt đúng
4/4 beat của sóng, 0 nhiễu → Python đếm cộng hưởng comment theo keyword của từng
candidate → LLM chỉ đặt tên theme + 1 dòng tóm, quote verify tồn tại (chuẩn A1).

**(b) Test cặp viết thử — công thức THẮNG 2/2 (user chấm):**
- Hook M-first (396 chars) thắng hook trả-lời-ngay (402 chars).
- Chương Question-first mở bằng "Were we lied to?" (theme 11.594❤, giọng Sagan,
  2.620 chars) thắng chương explanation-first (2.550 chars).
- Giới hạn khai báo: n=1 người chấm, 1 chương, 1 giọng, viết tay chưa qua Writer
  → đủ để đầu tư thí nghiệm thật (cổng G1 §7), chưa phải bằng chứng cuối.

---

# PHẦN II — QUYẾT ĐỊNH & SPEC V2

## 4. ⚠ SỬA LUẬT A3 (quyết định user 2026-07-25 — ghi để Claude Code không bối rối)

CLAUDE.md luật A3 nói "tool trình bằng chứng — USER pick, yêu cầu ngả sang tool tự
pick phải dừng hỏi user". **User đã được hỏi và quyết:** ưu tiên bỏ bước pick tay
hoặc có cơ chế chống pick nhầm. Bối cảnh: A3 ra đời (METHODOLOGY v4, 2026-07-03) vì
"KHÔNG tin PY+LLM tự pick được outline tốt" — khi đó KHÔNG có khuôn cấu trúc nào làm
đích. **V2 có khuôn đo được (công thức đã kiểm chứng)** → auto-pick chuyển từ bài
toán thẩm mỹ mù thành bài toán LẮP RÁP CÓ RÀNG BUỘC — làm được.

**Phạm vi sửa (chốt):**

| | V1 (A3 cũ) | V2 (A3 sửa) |
|---|---|---|
| Lắp outline | user tick từng cluster từ zero | **mặc định: AUTO-DRAFT V2** — tool tự lắp bản nháp theo công thức, user DUYỆT/SỬA (một bước approve thay vì N bước pick) |
| Chống pick nhầm | không có | **STRUCTURE LINTER** (Python thuần, §5.4) chạy trên MỌI outline (auto lẫn tay); lỗi cấu trúc → cảnh báo đỏ + phải bấm xác nhận mới xuất ("chặn mềm") |
| Score tổng ẩn | cấm | **VẪN CẤM** — linter là danh sách RULE công khai từng tiêu chí pass/fail, không phải một con điểm |
| Bằng chứng | hiển thị | **VẪN hiển thị** — mọi mục auto-draft kèm citation như pick tay |
| Quyền sửa của user | toàn quyền | **VẪN toàn quyền** — auto-draft nạp vào panel sửa được, không tự lưu đè |
| LLM bịa tên cluster | cấm (parse_suggestion verify) | VẪN cấm — giữ nguyên cơ chế verify tên thật |

Nghĩa là: **cái bị bỏ là LAO ĐỘNG pick tay, không phải QUYỀN quyết của user.**

## 5. FLOW V2 — spec triển khai theo module

### 5.0. Sơ đồ

```
S1→S3 (NGUYÊN TRẠNG)
  ▼
S4/S4b: cluster + tín hiệu cũ  +  M-MINING v2 (mới, §5.1)
  ▼
AUTO-DRAFT V2 (nâng cấp suggest.py, §5.3)  ──►  BOARD V2 (§5.2): user duyệt/sửa
  ▼                                              linter chặn mềm (§5.4)
outline.txt v2 (§5.5: + Misconception:/Question:)
  ▼
Writer V2 (§6: hook nhận M, chương Question-first sau cổng G1, end trả nợ hook)
  ▼
script.md
```

### 5.1. M-mining v2 (`oe/s4b_signals.py` + module nhỏ mới nếu cần)

```
1. HARVEST (Python): quét beats.json, lấy beat có summary khớp
   r"(not (an? )?\w+ but|no longer believe|is wrong|weren'?t?.*(taught|told)|
      school-taught|myth|misconception)"  → M-candidates (đã đo: 4/4 sạch trên bigbang).
2. KEYWORDS (Python): trích danh từ/cụm nội dung từ candidate (vd explosion,
   singularity, nothing, before) — tái dùng hạ tầng embedding nếu tiện, keyword
   word-boundary là đủ cho MVP.
3. RESONANCE (Python): đếm comment (mọi video trong run) match theme; giữ top-3
   quote theo likes. n = ước lượng dưới — trình bày đúng như vậy.
4. LABEL (LLM, 1 lượt/run): tên theme + 1 dòng "khán giả đang tưởng gì" cho
   candidate có n>0; MỌI quote phải là text comment thật (Python verify chuỗi
   tồn tại — pattern Evidence Grounder).
5. GHI: clusters.json thêm per-cluster {"m_signal": {"n": int, "theme": str,
   "quotes": [str]}} (cluster chứa beat candidate); bảng MISCONCEPTIONS =
   candidate KHÔNG thuộc cluster nào được pick trong sóng → mỏ hook.
```

Chi phí: 0 API mới (beats + comments có sẵn từ S1/S3), +1 lượt LLM ngắn/run.

### 5.2. Board V2 (`oe/board.html` + route trong `contentultimate/server.py`)

- Cột mới `M-signal (n)` (sort được như cột khác) + tab **MISCONCEPTIONS** cạnh GAPS.
- Mỗi chương trong panel: dòng `Question:` (editable) — mặc định điền nguyên văn câu
  hỏi khán giả top-likes của cluster (`questions` đã có sẵn từ S4b); không có →
  để trống, auto-draft sẽ điền bản LLM đảo brief, đánh dấu `(gen)`.
- Toggle sợi 🅰/🅱 per chương (mặc định A; board báo ứng viên B = cluster có beat
  narrative / `quoted (n)` cao — user hoặc auto-draft gán).
- Ô HOOK thêm dòng `Misconception:` (chọn từ bảng MISCONCEPTIONS hoặc M-signal của
  cluster hook).
- Checklist 4 câu (hiển thị pass/fail từng dòng, KHÔNG điểm tổng): M mở màn? ·
  ≥nửa số chương có Question? · sợi B có mặt & không có chuỗi ≥3 chương A nặng liền
  nhau? · ending trả nợ hook?
- Nút **✨ Auto-draft V2** (thay nút ✨ cũ) — §5.3.

### 5.3. Auto-draft V2 (nâng `oe/suggest.py` — hạ tầng ĐÃ CÓ SẴN, tận dụng)

`suggest.py` hiện đã có: `build_candidates` (backbone coverage≥2 + peak singles +
cluster có questions, không điểm tổng ẩn) → LLM chọn/xếp → `parse_suggestion`
verify tên cluster THẬT (loại tên bịa) → nạp panel. **Giữ nguyên khung đó**, nâng:

- `build_candidates`: đưa thêm `m_signal` + cờ `b_candidate` (beat narrative/quoted
  cao) vào từng dòng ứng viên.
- Prompt LLM thêm ràng buộc công thức: (1) hook = cluster có m_signal mạnh nhất
  (fallback: role=hook như cũ); (2) mỗi chapter kèm `question` — BẮT BUỘC lấy từ
  danh sách câu hỏi thật đưa kèm, hoặc đảo brief (đánh dấu gen); (3) xếp thứ tự
  đan sợi: không đặt 2 chương nặng-khái-niệm cạnh nhau khi có ứng viên B; (4) ending
  role=ending + phải "answers the hook"; (5) tránh 2 chương trùng lõi (đưa cosine
  cặp brief > 0.85 cho LLM thấy — Python tính, tái dùng embeddings S4).
- `parse_suggestion`: nhận thêm trường `question`/`misconception`/`thread` — verify:
  question thuộc kho câu hỏi thật hoặc mang cờ gen; misconception thuộc bảng đã đào.
- Kết quả nạp panel như cũ (không tự lưu) — **nhưng flow mặc định của board là bấm
  ✨ ngay khi mở** (config `AUTO_DRAFT_ON_OPEN=true`, tắt được).

### 5.4. Structure Linter (Python thuần, module mới `oe/lint.py` — cốt lõi "không pick nhầm")

Chạy trên `picks` mỗi lần thay đổi (auto lẫn tay), trả list `{rule, level, msg}`:

| Rule | Level | Điều kiện fail |
|---|---|---|
| `hook-no-m` | đỏ | hook không có Misconception line và cluster hook m_signal=0 |
| `hook-answers` | vàng | brief hook chứa mẫu trả-lời-ngay (heuristic: mở đầu bằng khẳng định kết luận — MVP: cảnh báo khi hook KHÔNG chứa dấu "?") |
| `question-cov` | vàng | <50% chương có Question |
| `question-gen` | vàng | >50% Question là `(gen)` (nguy cơ slop câu hỏi tu từ) |
| `a-chain` | đỏ | ≥3 chương A nặng liền nhau (nặng = badge nguyên liệu ⚠/● sẵn có) trong khi tồn tại ứng viên B chưa dùng |
| `no-b` | vàng | sóng có ứng viên B mà outline 0 chương B (sóng không có B → chỉ ghi chú, không cảnh báo) |
| `dup-core` | đỏ | 2 chương pick có cosine brief > 0.85 (vụ Ch2/Ch3 bigbang) |
| `payoff` | vàng | ending không tham chiếu theme của hook (MVP: keyword-overlap; nâng cấp: embedding) |
| `broken-name` | đỏ | tên chương là brief cụt (>60 chars hoặc kết thúc bằng từ chức năng — vụ 2 tên cụt bigbang) |
| `hook-end-missing` | đỏ | thiếu HOOK/ENDING (đã có sẵn V1 — gộp vào linter) |

Đỏ → **chặn mềm**: vẫn xuất được nhưng phải bấm "Xuất dù có cảnh báo" (ghi vào
evidence là xuất kèm cảnh báo gì). Vàng → hiện, không chặn. KHÔNG có điểm tổng.

### 5.5. outline.txt v2 + `compose.py`

Format khối GIỮ NGUYÊN (hợp đồng!); chỉ thêm meta line theo đúng tiền lệ
`_angle_line`/`_cta_line` (compose.py:69-80 — copy pattern đó):

```
HOOK
Misconception: <1 dòng, từ m_pick>
<brief>          ← Angle:/CTA: như cũ nếu có

CHAPTER 1 — <tên>
Question: <câu hỏi — nguyên văn khán giả, hoặc (gen)>
<brief>
```

- `picks.json` thêm: `m_pick` (str), `questions` ({chapter_name: str}),
  `thread` ({chapter_name: "A"|"B"}). Thread KHÔNG ghi vào outline.txt — nó chỉ
  điều khiển THỨ TỰ chương và tone brief; Writer không cần biết.
- `compose_evidence`: in kèm likes của Question/Misconception + kết quả linter.

---

# PHẦN III — AUDIT PROMPT WRITER (từ code thật) & VIỆC PHẢI SỬA

## 6. Từng prompt builder trong `voiceprofile/generator.py`

### 6.1. `parse_outline` + `_META_LINE` (dòng 116-144) — **VIỆC SỐ 1, LÀM TRƯỚC TIÊN**

- Hiện trạng: `_META_LINE = r"^[ \t]*(?:angle|cta)[ \t]*:.*$"` — chỉ che Angle/CTA.
- **Quả mìn cụ thể nếu quên vá:** `_SECTION_MARK` săn `hook|chapter N|end|ending|
  intro|outro|conclusion` Ở BẤT KỲ ĐÂU. Câu hỏi khán giả RẤT HAY chứa từ mốc:
  *"What happens at the **end** of the universe?"*, *"the **intro** song"* →
  dòng `Question:` sẽ XÉ outline thành phần ma — đúng tai nạn `CTA:` 2026-07-15.
- **Sửa:** `_META_LINE = r"^[ \t]*(?:angle|cta|question|misconception)[ \t]*:.*$"`.
  Che bằng `_MASK_CH="x"` như cũ (KHÔNG che bằng khoảng trắng — comment dòng 128-130
  giải thích vì sao). Thêm test: outline có `Question: ...at the end of time?` phải
  ra đúng số section.

### 6.2. `estimate_ideas` (dòng 258) — **PHÁT HIỆN AUDIT QUAN TRỌNG NHẤT**

- Hiện trạng: đếm ý từ brief thô. Meta line MỚI (Question:/Misconception:) nằm trong
  brief của section (parse giữ chúng trong brief — thiết kế đúng) → **bị đếm thành
  Ý MA** → `depth_plan` chọn k sai → lặp lại đúng bệnh của vụ Pillar (07-15: brief
  588 chars/3 nhịp bị đếm thành 10 ý).
- **Sửa:** `estimate_ideas` (và mọi chỗ đo brief làm số: `outline_scope_report`,
  giãn nguyên liệu trên board) phải đếm trên `_mask_meta(brief)` — hoặc strip hẳn
  meta line trước khi đếm. Thêm test: brief có 3 nhịp + 2 meta line → vẫn ước 3 ý.

### 6.3. `build_hook_prompt` (dòng 352) — đáp ứng V2: **70%, sửa nhỏ**

- ĐÃ CÓ: platform thuần (không voice block) ✓ · 250-500 + vòng cắt riêng ✓ ·
  "Open a curiosity loop" ✓ · brief là nguyên liệu-không-checklist, chỉ lấy MỘT
  sợi ✓ · đã biết lờ dòng Angle:/CTA: ✓.
- THIẾU: không biết khái niệm misconception. **Sửa (thêm ~5 dòng):** khi brief chứa
  dòng `Misconception:` → chỉ thị: *"Open by BREAKING this false belief in the
  first 1-2 lines (state what people believe, then that it's wrong). Then open ONE
  question the video will answer. Do NOT answer it."* — và thêm `Misconception:`
  vào danh sách dòng được phép dùng làm nguyên liệu (hiện prompt bảo "Ignore any
  'Angle:' or 'CTA:' line except as background" — Misconception thì NGƯỢC LẠI:
  ưu tiên số 1).
- `build_hook_cut_prompt`: thêm 1 mệnh đề "keep the false-belief break AND the
  unanswered question intact" — còn lại giữ nguyên.

### 6.4. `build_section_prompt` (dòng 414) — đáp ứng V2: **50%, sửa có cổng**

- ĐÃ CÓ (bất ngờ tốt): `YOUTUBE_RULES["chapter"]` đã bắt "end on a small open loop
  that pulls the viewer into the next" → ĐUÔI chương đã đúng tinh thần Q→E.
  DEPTH PLAN + "EVERY OTHER idea MUST STILL APPEAR" là thứ đang giữ độ dài (A5) —
  **TUYỆT ĐỐI KHÔNG GỠ, KHÔNG DIỄN ĐẠT LẠI.**
- THIẾU: ĐẦU chương không có chỉ thị nào → LLM mặc định mở kiểu giảng giải.
- **Sửa (SAU cổng G1, §7):** thêm MỘT mệnh lệnh, chỉ khi brief có dòng `Question:`:
  *"OPENING: begin this section by RAISING the 'Question:' line below (rephrase it
  naturally in the author's voice, or quote the viewer's wording). Do NOT answer it
  in your first sentence — let the section build to the answer."*
  Đặt TRƯỚC scope_rule, không đụng gì khác. Nếu G1 rớt trên giọng nào → flag
  per-profile tắt mệnh lệnh này cho giọng đó.
- `YOUTUBE_RULES["end"]` đã có "close the curiosity loop opened in the hook" ✓ —
  V2 chỉ cần hook thật sự MỞ loop (6.3) là end tự trả nợ; có thể thêm nhẹ:
  "name the answer to the hook's question explicitly before the final beat."
- `build_scope_cut_prompt`/`build_expand_prompt`: giữ nguyên; chỉ cần
  `estimate_ideas` đã vá (6.2) là chúng tự đúng vì gọi chung `depth_plan`.

### 6.5. Những thứ audit xác nhận KHÔNG cần đổi

`build_voice_block` (exemplar là ground truth — đúng bài học "show đừng tell") ·
cơ chế checkpoint/resume · allocate hook 375/end clamp 7% · vòng NỞ (EXPAND_*) ·
`kept_ratio` · toàn bộ lengthlab để nguyên trạng thái tắt.

---

# PHẦN IV — TRIỂN KHAI

## 7. Roadmap + cổng nghiệm thu (thứ tự BẮT BUỘC)

| # | Việc | File đụng | Cổng qua |
|---|---|---|---|
| ✅G0 | Test cặp viết tay | — | Đã qua 25/07: công thức thắng 2/2 |
| **B1** | Vá `_META_LINE` (+question+misconception) + vá `estimate_ideas` đếm trên bản che | `generator.py` + tests | pytest xanh; 2 test mới: meta-line-chứa-từ-mốc không xé outline; meta line không thành ý ma |
| **B2** | M-mining v2 + bảng MISCONCEPTIONS + cột M-signal | `s4b_signals.py`, `s4c`, board, server | chạy trên bigbang + ≥1 run mới; mọi quote verify tồn tại; số khớp §2 (bigbang: 4 candidate) |
| **B3** | compose meta lines + picks fields + evidence kèm likes | `compose.py`, board | round-trip: compose → parse_outline → đúng số section, brief còn nguyên meta |
| **B4** | Linter `oe/lint.py` + chặn mềm + checklist panel | mới + board | chạy trên outline bigbang V1 phải bắt được: hook-no-m, question-cov, a-chain, dup-core (Ch2/Ch3), broken-name (2 tên cụt) — **outline V1 là test fixture tự nhiên** |
| **B5** | Auto-draft V2 (nâng suggest.py) + AUTO_DRAFT_ON_OPEN | `suggest.py`, board | draft từ run bigbang qua linter không lỗi đỏ; user duyệt bản draft thấy dùng được |
| **G1** | Thí nghiệm Writer thật: 5 mẫu × 2 biến thể (Question-first vs hiện tại), cùng nội dung, gọi THẲNG `build_section_prompt` (đừng chép tay prompt — bài học 07-16), ≥2 giọng tác giả | script thí nghiệm | user chấm văn ≥ hiện tại VÀ ký tự không lỏng hơn ±7% đáng kể. **Rớt → Question-first thành tùy chọn per-chương, không mặc định; ghi ĐÃ THỬ VÀ BÁC BỎ** |
| **B6** | Sửa prompt hook (6.3) + chương (6.4, nếu qua G1) + end | `generator.py` | so trước/sau trên bộ mẫu G1 |
| **B7** | Ghi kết quả (kể cả xấu) vào CLAUDE.md/DEVLOG; cập nhật METHODOLOGY về A3 sửa | docs | — |

Nguyên tắc: rớt cổng nào → dừng nhánh đó + ghi sổ; các nhánh khác vẫn sống.
B1 đứng đầu vì mọi nhánh sau đều ghi meta line — không vá trước là gieo lại
tai nạn 07-15.

## 8. Rủi ro đã nhìn thấy + chốt chặn

1. **Slop câu hỏi tu từ** (6 chương × "Ever wondered…?"): Question ưu tiên NGUYÊN
   VĂN khán giả; linter `question-gen` cảnh báo khi >50% là (gen); user xóa dòng
   Question của chương bất kỳ — mở bằng khẳng-định-đảo-ngược vẫn hợp lệ.
2. **M giả** (misconception khán giả không hề tin): M chỉ được chọn từ bảng có n
   cộng hưởng thật; n hiển thị cạnh mọi lựa chọn.
3. **B khi đói nguyên liệu**: không ứng viên B → linter ghi chú, KHÔNG ép (ép = bịa
   nội dung ngoài bằng chứng).
4. **Auto-draft thành hộp đen**: mọi mục draft kèm citation; linter công khai từng
   rule; prompt suggest verify tên cluster thật — LLM không bịa được chương.
5. **Question-first không hợp mọi giọng**: mới thắng trên 1 giọng (Sagan) — vì thế
   G1 bắt ≥2 giọng, có flag per-profile.
6. **Chi phí** (A6/C3): V2 thêm ~2 lượt LLM/run (label theme + auto-draft), 0 API
   mới, 0 quota mới. Auto-draft chỉ chạy khi bấm/mở board, idempotent.

## 9. Definition of Done (một run chạy trọn flow V2)

- [ ] Board có bảng MISCONCEPTIONS ≥1 theme quote-verify được; cột M-signal sort được.
- [ ] Bấm ✨ (hoặc mở board) ra draft đầy đủ HOOK(+Misconception) / CHAPTERs(+Question,
      thứ tự có sợi B nếu có nguyên liệu) / ENDING — mọi mục có citation.
- [ ] Linter: outline V1 bigbang bắt đủ 5 lỗi đã biết; outline draft V2 không lỗi đỏ.
- [ ] outline.txt v2 round-trip qua parse_outline không sinh phần ma; ý ma = 0
      (estimate_ideas không đếm meta).
- [ ] Script ra: hook đập misconception câu 1 và không trả lời; chương mở bằng câu
      hỏi (nếu bật); ending có câu trả nợ hook; độ dài trong khung như V1.
- [ ] Mọi số n/quote/likes truy ngược được về `runs/<run>/`.

**Thước cuối cùng của "V2 thành công" vẫn là retention/CTR thật khi đăng bài**
(Quality Oracle — module 7, chưa build). V2 không hứa view; V2 hứa: cấu trúc kể
chuyện — như nội dung và giọng văn — từ nay có bằng chứng đo được đứng sau, và
người dùng không còn phải tự lắp outline bằng tay từ zero.

---

# PHẦN V — SỔ BÀI HỌC G0 MỞ RỘNG (run `jupiter-v2`, 2026-07-26, chạy tay toàn tuyến)

Thí nghiệm: 4 video Jupiter (1,9-6,8M view) → pipeline thật → M-mining tay → outline
V2 tự lắp → hook + C1 viết bằng prompt builder thật + khối V2 tiêm. User chấm từng bước.
File: `THI-NGHIEM-v2/` (script + các bản out_*). **Mọi mục dưới đây là luật cho code V2.**

## 10. Những gì ĐO ĐƯỢC là ĐÚNG (giữ nguyên khi code)

- **M-mining v2 neo beat**: 3 candidate/81 beat, 0 nhiễu; resonance đếm được
  (gas-vs-liquid n=24 + meme ❤8.389; fuzzy-core quote ❤2.033; school n=37).
  **Pattern list phải là CONFIG MỞ RỘNG ĐƯỢC** — bộ regex tune trên bigbang bắt 0/81
  trên jupiter ("not a gas **planet** but" — 2 từ giữa là trượt); nới khoảng cách từ
  + thêm mẫu mới bắt 3/3 sạch. Đừng hard-code.
- **Question nguyên văn khán giả 4/4 hoạt động** — kể cả câu đùa ("caramel rivers…
  I was lied to!!" ❤674) lẫn giả thuyết fan (ice-core ≈ đúng dữ liệu Juno). Verify
  bằng substring sau normalize (nháy cong/thẳng, "…"), KHÔNG so chuỗi cứng.
- **Hook M-break: 3 luật chốt bởi user** — ① câu 1 PHẢI là cú bẻ (mở bằng phủ định;
  cấm warm-up trình bày lại niềm tin — não khán giả đóng cửa với thứ "đã biết");
  ② nêu niềm tin bị bẻ ngay sau, ĐẬP ĐÚNG MỘT niềm tin (comment ❤86 phản pháo video
  overclaim "school taught everything wrong"); ③ cấm lộ đáp án — reveal là payoff của
  video (bản nháp 2 lộ "liquid metal ocean" giây 5 → vòng tò mò chết).
- **Guard chống-rò đặt TRONG brief hiệu quả 2/2** — "(Note to the writer: X is a
  TEASE here — do NOT name Y; Chapter N owns that reveal)". Luật ở tầng prompt
  (LOOP DISCIPLINE) đơn độc KHÔNG đủ vì xung đột A5 "mọi ý trong brief phải xuất
  hiện": brief nhắc "pressure"/"comets" là model triển khai đến tận nóc = nói toạc.
  → Auto-draft V2 (§5.3) phải TỰ GHI guard vào brief khi phát reveal cho chương.
- **Vòng nở/cắt phải THỪA KẾ khối V2** — bản nở chạy mù chính là nguồn rò payoff
  chương khác + văn khảm (câu mới chêm giữa câu cũ giữ nguyên → cụt-cụt-NHỒI-cụt).
  Đã vá trong script thí nghiệm; khi sửa `generator.py` (B6) phải nối khối V2 vào
  cả `build_expand_prompt` lẫn `build_scope_cut_prompt`. Kèm: nở vọt quá khung
  (2.984→4.521; 2.392→4.736) → sau nở phải có vòng cắt về ≤ trần.

## 11. Những gì BỊ BÁC — đừng làm lại

- **MID-LOOP per-đoạn (Q→E lòng chương liều đậm)**: "before each major fact, let the
  question breathe… never stack two explanations" → 100% đoạn mở bằng câu hỏi/mệnh
  lệnh, văn thành chuỗi tế bào Hỏi-Đáp tự khởi động lại — user: "lủng củng". Tái phạm
  lớp lỗi luật-hoá-nhịp 07-16. **Thay bằng PACING 2 luật hẹp**: (1) câu hỏi tu từ
  tối đa 1-2/chương tại khúc ngoặt thật, cấm mở đoạn đồng phục (kể cả "Consider…/
  Think…"); (2) MỘT câu MỘT ý — câu dài phải dài do đà, cấm nhét list/aside thứ hai,
  em-dash tối đa 1/đoạn. Kết quả đo: câu nhồi >200 từ 5 → 0, em-dash 2,9 → 0/1000.
- **Giả thuyết "giọng Sagan kỵ công thức" — BÁC BẰNG SỐ**: chạy cùng outline + cùng
  liều với Attenborough (exemplar gốc TB 176/câu, 0% câu cụt — y hệt Sagan 171/0%)
  → bản ra TB 70/câu, 48% câu cụt — còn vụn hơn Sagan (88-96). Nhịp ngắn-vụn là
  register của GLM dưới stack prompt này, KHÔNG phụ thuộc giọng.
  **Nghi phạm số 1 (chưa xử): voice block exemplar quá mỏng** — Sagan chỉ 11 câu
  exemplar đấu với cả trăm dòng luật. Thí nghiệm kế tiếp: nạp exemplar dày từ corpus,
  đo TB/câu có nhảy về 150+ không. (Khớp bài học A008: exemplar ngắn → viết ngắn.)
- **Linter thiếu rule `hook-contradiction`**: bản (b) viết nguyên văn "Jupiter is a
  gas giant." ở C1 — khẳng định lại đúng niềm tin hook vừa đập. Thêm rule đỏ:
  chương nào assert lại misconception của hook → chặn mềm. (Prompt chương cũng thêm
  1 câu: "Never re-assert the belief the hook broke.")

## 12. CẤU HÌNH CÔNG THỨC CHỐT (user giao Claude chọn, 2026-07-26)

Stack prompt Writer V2 = bản "liều 3 + guard" đã thắng trong thí nghiệm:
1. **Hook**: build_hook_prompt + khối M-break 3 luật (§10) — đã được user duyệt.
2. **Chương**: build_section_prompt + OPENING Question-first (khi có Question:)
   + PACING 2 luật hẹp + LOOP DISCIPLINE + câu chống phản-hook. KHÔNG mid-loop đậm.
3. **Brief** (từ auto-draft): Question nguyên văn + guard "tease only" cho reveal
   của chương khác + M chỉ ở hook.
4. **Nở/cắt**: thừa kế toàn bộ khối V2; nở xong vượt trần → cắt về khung.
5. **Giọng**: theo lựa chọn user per-video (công thức độc lập giọng — đã chứng minh);
   bài toán nhịp xử riêng bằng thí nghiệm exemplar-dày, không trộn vào công thức.
