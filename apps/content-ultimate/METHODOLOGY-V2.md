# METHODOLOGY V2 — Công thức kể chuyện có bằng chứng (2026-07-26)

> Bản cập nhật phương pháp luận sau **thí nghiệm G0 mở rộng chạy tay toàn tuyến**
> (run `jupiter-v2`, 25-26/07/2026). Kế thừa [METHODOLOGY.md](./METHODOLOGY.md) (v4 —
> cluster board, user pick) và [CONTENT-ULTIMATE-V2-MASTER.md](./CONTENT-ULTIMATE-V2-MASTER.md)
> (spec triển khai). File này là **sổ phương pháp**: cái gì đúng, vì sao, đo bằng gì,
> cái gì đã chết. CLAUDE.md vẫn là luật nền; A3 đã sửa theo phạm vi ghi ở master brief §4.

---

## 1. Công thức và trạng thái kiểm chứng

**V = (M + (Q→E)) × (A+B)** — gốc: thí nghiệm PhD của Derek Muller (video "confusing"
dạy gấp đôi video "clear"), video The Internet Stamp 70,7x outlier.

| Biến | Nghĩa | Trạng thái sau jupiter-v2 |
|---|---|---|
| **M** | Misconception — đập niềm tin sai để mở não | ✅ **Kiểm chứng 2 sóng**: bigbang (❤716 "My life is a lie") + jupiter (meme ❤8.389 "Gas Giant / Looks Inside / Mostly Liquid"). Hook M-break được user duyệt. |
| **Q→E** | Hỏi trước — giải thích là phần thưởng | ✅ cấp CHƯƠNG (câu hỏi nguyên văn khán giả mở chương, 4/4 hoạt động). ❌ cấp ĐOẠN VĂN — bị bác (xem §5). |
| **A+B** | Hai sợi đan: khái niệm ↔ chuyện kể | ✅ A-B-A-B-A chạy được; chương B (SL-9) là chương user khen sớm nhất. |
| **Payoff** | Ending trả nợ hook thành lời | ⏳ thiết kế xong (guard + end rule), chưa chạy đến ENDING. |

**Vị trí từng biến trong hệ thống — nguyên tắc phân tầng quan trọng nhất:**
CẤU TRÚC được quyết ở **OUTLINE** (M-pick, Question per chương, thứ tự A/B, chương nào
own reveal nào). Writer là **thợ render trung thành** — nhận cấu trúc qua meta line +
guard trong brief, không tự sáng tác cấu trúc. Đây là lý do không viết lại Writer từ
zero: công thức nằm ở tầng lắp ráp, không nằm ở tầng văn.

## 2. Flow V2 (đã chạy tay đủ, chưa code vào sản phẩm)

```
S1→S4b như V1
  + M-MINING v2: beat đính chính (S3 đã label) → pattern CONFIG MỞ → đếm cộng hưởng
    comment → quote verify tồn tại. Đo: bigbang 4/4 sạch · jupiter 0/81 với pattern
    bigbang → NỚI pattern (khoảng cách từ, "neither…nor", "challenging…", "didn't
    teach") → 3/81 sạch, 0 nhiễu. BÀI HỌC: pattern là config theo sóng, cấm hard-code.
  ▼
OUTLINE V2 (tự lắp / auto-draft):
  - Hook: Misconception line (chọn từ bảng M có n cộng hưởng) — CHỈ MỘT niềm tin
    (comment ❤86 "Turns out Jupiter is exactly what they taught us" = khán giả phản
    pháo overclaim).
  - Chương: Question NGUYÊN VĂN khán giả (verify substring sau normalize nháy/…);
    kể cả câu đùa (caramel ❤674) lẫn giả thuyết fan (ice-core ≈ đúng Juno).
  - GUARD chống-rò ghi THẲNG vào brief: "(Note to the writer: X is a TEASE here —
    do NOT name Y; Chapter N owns that reveal.)" — hiệu quả 3/3 chương sau khi cài.
  - Đan sợi A/B; ending own việc trả nợ hook thành lời.
  ▼
WRITER V2 = prompt builder V1 + khối tiêm (§4) — KHÔNG viết lại kiến trúc.
```

## 3. Nhật ký thí nghiệm jupiter-v2 (4 video, 1.9-6.8M view, giọng Sagan A001)

### Hook — 3 bản, 2 luật sinh ra từ chấm của user
| Bản | Lỗi user/tôi bắt được | Luật rút ra |
|---|---|---|
| 1 (270c) | 3 câu đầu TRÌNH BÀY LẠI niềm tin rồi mới bẻ | **M-break phải LÀ câu 1** — não đóng cửa với thứ "đã biết" (đúng cơ chế PhD Derek) |
| 2 (208c) | bẻ xong NÓI TOẠC đáp án ("liquid metal ocean") ở giây 5 | **Cấm lộ reveal** — đáp án là payoff của video |
| 3 (238c) ✅ | — | bẻ → nêu niềm tin bị bẻ → mở 2 trục hỏi (what/how-we-know) khớp 2 trục outline |

### C1 — 3 liều prompt + 3 phương án, nơi lộ gần hết bài học
- **Liều 1** (MID-LOOP đậm): user chấm "lủng củng". Đo: 100% đoạn mở bằng câu hỏi/mệnh
  lệnh; văn thành chuỗi tế bào Hỏi-Đáp tự khởi động lại.
- **Liều 2** (thêm PACING): bản 1 hụt sâu → vòng nở (chạy MÙ, không có luật V2) bơm
  2.392→4.736: rò trọn reveal C3 + kể trước cả chuyện SL-9 của C2. → **Vòng nở/cắt
  phải thừa kế khối V2**; nở xong vượt trần phải cắt về khung.
- **Liều 3 + 3 phương án** (a) cắt tay / (b) guard+Sagan / (c) guard+Attenborough:
  - (b) tự loại: viết "Jupiter is a gas giant." — **phản hook**. → luật prompt + rule
    linter `hook-contradiction`.
  - (c) guard thi triển đẹp nhất ("What that something is, we will come to later").
  - **Chốt C1 = (a)** (giọng user chọn là Sagan; sạch cấu trúc; nhịp tốt nhất nhánh Sagan).

### Phát hiện nhịp — giả thuyết "giọng kỵ công thức" BỊ BÁC BẰNG SỐ
| | TB ký tự/câu | CV | câu cụt <60 |
|---|---|---|---|
| Sagan exemplar gốc | 171 | 0.33 | 0% |
| Attenborough exemplar gốc | 176 | 0.40 | 0% |
| GLM viết Sagan (các liều) | 88-96 | 0.52-0.68 | 33-37% |
| GLM viết Attenborough | 70 | 0.66 | 48% |

Đổi giọng KHÔNG đổi nhịp → ngắn-vụn là register của GLM dưới stack này, không phải
xung khắc giọng×công thức. **Nghi phạm số 1 chưa xử: voice block exemplar quá mỏng**
(Sagan: 11 câu exemplar đấu với ~trăm dòng luật). Thí nghiệm kế: nạp exemplar dày,
đo TB/câu có về 150+ không. Cảm giác "câu quá dài" của user = **răng cưa**: vài câu
NHỒI >200 (kẹp list + 2 lớp em-dash — Sagan gốc: 0 câu) giữa rừng câu cụt — không
phải trung bình dài.

### C2, C3 với cấu hình chốt — số liệu hội tụ
| | C2 liều 1 (chê) | C2 chốt | C3 |
|---|---|---|---|
| Ký tự | 4.521 (vượt trần) | 3.274 ✅ | 4.053 (mép trần) |
| TB/câu · CV | 99 · 0.60 | 112 · **0.38** | 108 · 0.56 |
| Câu nhồi >200 | 3 | 0 | 1 |
| Câu cụt <60 | 22% | **10%** | 32% |
| Rò/kể trước/phản hook | 1 lỗi fact | **0** | 0 (2 lỗi fact số liệu) |

User chấm C2-chốt và C3: "văn hay rồi". CV 0.38 của C2 ≈ hình dáng nhịp tác giả thật
(0.33). Fact-check từng chương vẫn BẮT BUỘC: 3 lỗi fact bị bắt qua 3 chương (escape
velocity ×2→×5; "deeper than Earth-Moon distance"; "millions×" đáy biển) — LLM bịa
số so sánh rất ngọt tay, người duyệt phải soi mọi phép so sánh định lượng.

## 4. STACK PROMPT WRITER V2 — CẤU HÌNH CHỐT (user giao Claude chọn, 26/07)

Tiêm vào prompt builder THẬT (`build_hook_prompt`/`build_section_prompt`), không chép tay:

1. **HOOK — khối THE FALSE BELIEF**: ① câu 1 = cú bẻ (mở bằng phủ định, CẤM warm-up);
   ② nêu ngay niềm tin bị bẻ, chỉ MỘT niềm tin; ③ mở MỘT câu hỏi, CẤM lộ đáp án.
   Vòng cắt hook: + "keep the false-belief break AND the unanswered question intact".
2. **CHƯƠNG — 4 khối, đặt trước DEPTH PLAN, không đụng gì khác**:
   - OPENING (khi có Question:): nêu câu hỏi khán giả bằng giọng tác giả hoặc quote
     nguyên văn; câu đầu KHÔNG trả lời.
   - PACING (2 luật hẹp): câu hỏi tu từ ≤1-2/chương tại khúc ngoặt thật, cấm mở đoạn
     đồng phục (kể cả "Consider…/Think…"); MỘT câu MỘT ý — câu dài do đà, cấm nhét
     list/aside, em-dash ≤1/đoạn.
   - LOOP DISCIPLINE: không trả nợ hộ chương khác; xây tới reveal của chương sau thì
     ghé sát rồi buông.
   - HOOK'S BREAK STANDS: cấm khẳng định lại niềm tin hook đã đập, kể cả nói lướt.
3. **BRIEF mang guard** "(tease only — Chapter N owns…)" cho mọi reveal không thuộc
   chương; chương own reveal thì guard nói rõ "pay it off fully".
4. **VÒNG NỞ/CẮT thừa kế toàn bộ khối V2**; sau nở vượt trần → một vòng cắt về khung.
5. **Giọng độc lập công thức** — chọn per-video như cũ; bài toán nhịp xử riêng.

Những thứ V1 giữ nguyên KHÔNG đụng: voice block (exemplar là ground truth), DEPTH
PLAN + "EVERY OTHER idea MUST STILL APPEAR" (A5), phân bổ hook 375/end 7%, checkpoint.

## 5. SỔ BÁC BỎ (đừng làm lại — nối dài sổ A5 của CLAUDE.md)

1. **M-mining v1 regex mẫu câu trên comment** — 17 match/1.800, đa số nhiễu (đã ghi
   ở master brief §3a). Khán giả không tự khai misconception; họ lộ qua chủ đề hỏi/cãi.
2. **MID-LOOP per-đoạn** ("before each major fact… never stack two explanations") —
   văn thành tế bào Hỏi-Đáp, user: "lủng củng". Tái phạm lớp lỗi luật-hoá-nhịp 07-16.
3. **Hook warm-up** (trình bày niềm tin trước khi bẻ) — ngược cơ chế; user bắt ngay bản 1.
4. **Giả thuyết "giọng Sagan kỵ công thức"** — bác bằng số (§3): lỗi nhịp không đổi
   khi đổi giọng.
5. **Luật chống-rò CHỈ ở tầng prompt** — thua luật A5 "mọi ý phải xuất hiện" khi brief
   nhắc tới lãnh thổ chương khác; guard phải nằm TRONG brief.

## 6. CÂU HỎI MỞ (thí nghiệm kế tiếp, theo thứ tự giá trị)

1. **TOPLIST/VENTURES — V2 có viết tốt hơn không? (user hỏi 26/07 — CHƯA CÓ ĐÁP ÁN.)**
   Khác biệt cấu trúc: toplist = NHIỀU payoff nhỏ (mỗi mục một vòng mở-đóng ngắn),
   không phải MỘT vòng nợ lớn xuyên video. Phác thiết kế thí nghiệm:
   - M cấp video vẫn dùng được ("mọi người tưởng #1 là X"), nhưng sóng facts có thể
     KHÔNG có beat đính chính → linter `hook-no-m` phải hạ cấp khi bảng M rỗng
     (đã chốt trong 4 điểm siết); hook fallback = câu hỏi xếp hạng/stake.
   - Q→E ánh xạ thành **mini-loop per mục**: tên mục là câu hỏi ngầm ("vì sao nước
     này đứng #3?") → E ngắn → mục sau. PACING giữ nguyên.
   - A+B trong toplist = xen kẽ mục-số-liệu và mục-có-chuyện.
   - Cổng: chạy 1 sóng Ventures thật, so blind với bản V1 cùng outline. **Chưa chạy
     thì chưa hứa** — ghi rõ để không bán non công thức.
2. **Exemplar dày → nhịp**: nạp thêm exemplar dài từ corpus vào voice block, đo TB/câu.
3. **G1 chấm mù chính thức** (5 mẫu × 2 biến thể × ≥2 giọng) trước khi Question-first
   thành mặc định trong SẢN PHẨM — jupiter-v2 mới là 1 giọng, 1 người chấm, không mù.
4. **Q→E lòng chương liều thấp** — biến thể riêng trong G1 (không mặc định).

## 7. VIỆC CODE V2 — roadmap B1-B7 (master brief §7) + bổ sung từ thí nghiệm

- B1 (mìn meta-line + ý-ma) — không đổi, vẫn làm ĐẦU TIÊN.
- B2 M-mining: pattern list = **config file**, không hằng số.
- B4 Linter: + rule `hook-contradiction` (đỏ); `hook-no-m` hạ cấp khi sóng không có M.
- B5 Auto-draft: TỰ GHI guard vào brief khi chia reveal; Question verify substring
  sau normalize; auto-draft-on-open CHỈ khi picks rỗng + cache draft.json.
- B6 Writer: khối V2 (§4) nối vào cả `build_expand_prompt`/`build_scope_cut_prompt`;
  vòng nở thêm trần target+5%.
- Triển khai ở **bản V2 độc lập** (folder/service riêng), ổn định mới nhập về một mối
  (quyết định user 26/07).

---

## §8 — TRẠNG THÁI CODE (fork V2 độc lập, 2026-07-27)

Fork `Content Ultimate V2/` (branch `v2`, clone từ gốc @8ca8667). Đã vào code sản
phẩm, 243 test xanh, verify sống bằng GLM qua `voiceprofile write` (không harness):

| Việc | Trạng thái | Ghi chú |
|---|---|---|
| B1 mìn meta-line + văn guard | ✅ | parse_outline 2 pass; estimate_ideas loại meta. Mìn lớp 2 (văn guard nhắc "Chapter N's reveal") chỉ lộ khi parse outline THẬT — Moscow bị xé 19 phần trước khi vá |
| B6 khối Writer V2 | ✅ | gate theo meta-line; nở/cắt thừa kế; khối đúng bản chốt §12 (BREAK STANDS bỏ ví dụ Jupiter, tổng quát hoá) |
| B2 đào M | ✅ (CLI) | `oe/m_mine.py` — pattern config + --pattern; chưa nối board |
| Verify sống | ✅ | hook 223c M-break câu 1 · C1 hụt 40% → vòng nở 89% khung, Q nguyên văn mở chương, 0 số bịa · End tự cắt, trả nợ hook |
| B3 compose/B4 linter/B5 auto-draft/board UI | ⬜ | thứ tự đề xuất: B4 linter (rẻ, chặn lỗi tay) → B3 → B5 → UI |

Quy trình team tạm thời (chưa có board V2): `SOP-V2.md` — lắp outline dán tay.
