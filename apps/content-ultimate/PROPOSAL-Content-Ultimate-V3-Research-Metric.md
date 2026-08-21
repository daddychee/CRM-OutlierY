> ⚠ **BẢN NÀY ĐÃ ĐƯỢC THAY THẾ TRỌNG TÂM** (21/08/2026) — xem
> `PROPOSAL-V3-ban2-CUU-CHAT-LUONG-VIET.md`. Lý do: điều tra dữ liệu vận hành cho thấy
> team đã NGỪNG dùng app từ 07/08 vì chất lượng VĂN VIẾT, không phải vì thiếu tầng
> research. Bản này giữ nguyên làm mốc; phần phản biện từng điểm nằm ở PHẦN II của bản 2.

# PROPOSAL — Content Ultimate V3  
## Research + Metric Layer (bổ sung cho V2 Master Brief)

> **Mục tiêu:** Biến Content Ultimate từ hệ thống “cấu trúc kể chuyện có bằng chứng”  
> thành hệ thống **chọn đúng trận (demand + metric) rồi mới cấu trúc đúng công thức**.  
> Tài liệu này tự chứa, dựa trên audit V2 Master Brief (2026-07) + nghiên cứu framework  
> lượng hóa + dữ liệu retention/trend 2025-2026.  
>  
> **Nguyên tắc kế thừa:** Giữ nguyên toàn bộ công thức V = (M + (Q→E)) × (A+B),  
> M-mining v2, Structure Linter, meta-line handling, Writer stack “liều 3 + guard”,  
> và các bài học G0/Jupiter đã chốt. Chỉ **mở rộng phía trước và phía sau** pipeline.

---

# PHẦN I — TÓM TẮT ĐIỀU HÀNH

### Gap lớn nhất hiện tại
Tool V2 cực mạnh ở **supply-side structure** (mining comment/beat → outline → script  
theo công thức đã kiểm chứng). Điểm yếu lớn nhất là **thiếu demand-side research  
gắn metric/trend trước khi chọn topic và packaging**.

Hậu quả: có thể viết ra video “đúng công thức Veritasium” nhưng:
- Ít người search / không có gap thật trên audience channel.
- Packaging (title/thumbnail) yếu → CTR thấp dù retention nội dung tốt.
- Không có feedback loop từ retention curve thật để cải thiện vòng sau.

### Đề xuất cốt lõi
1. **Thêm lớp S0 — Opportunity & Demand Research** (bắt buộc trước S1).
2. **Mở rộng competitive run + Packaging Heuristic**.
3. **Gắn Predicted Retention Risk vào Linter**.
4. **Feedback loop sau đăng** (retention curve → lesson learned).
5. **Yêu cầu user cung cấp data Studio/Trends** (semi-auto, realistic).

### Kết quả mong đợi
- Topic được chọn có Opportunity Score rõ ràng.
- Outline không chỉ “đúng cấu trúc” mà còn được tối ưu cho metric mục tiêu.
- Tool trở thành vòng lặp học hỏi từ dữ liệu thật của channel, không chỉ từ  
  experiment tay trên bigbang/jupiter.

---

# PHẦN II — THAM KHẢO FRAMEWORK ĐÃ LƯỢNG HÓA

Các framework dưới đây đã được formalize và/hoặc đo bằng experiment / dữ liệu lớn.  
Dùng để định vị V2 và chỉ ra chỗ còn thiếu.

| Framework | Nguồn / Cách lượng hóa | Điểm mạnh liên quan V2 | Khoảng trống so với V2 |
|-----------|------------------------|------------------------|------------------------|
| **Veritasium / Muller** | PhD pre/post-test (6.3 → 11) | M + confusion → learning. Đúng gốc tool | Không đo trực tiếp CTR / retention algorithm |
| **Information Gap Theory** (Loewenstein 1994) | Curiosity = knowledge gap. Peak ở gap vừa phải. Experiment 2020s xác nhận | Nền tảng tâm lý của M và Q→E | Khó đo “kích thước gap” tự động |
| **SUCCESs** (Made to Stick) | Simple · Unexpected · Concrete · Credible · Emotional · Stories | Unexpected ≈ M; Concrete + Stories ≈ sợi B | Không có số retention YouTube cụ thể |
| **Hook data 2025-2026** | Phân tích 500–4.000+ video | Pattern Interrupt thường thắng Curiosity Gap về 30s retention; Shocking Statistic, Outcome-First, Contrarian Claim mạnh | Chủ yếu tối ưu 15-30s đầu |
| **Narrative structures** | Curiosity Loop, Problem Stack, Reveal Ladder, Transformation Arc… | Q→E lặp + A+B gần với Curiosity Loop / Problem Stack | Cần map rõ vào outline |
| **Retention curve diagnostics** | Opening cliff, ledge, plateau, end-screen dive. Shape > average % | Linter đã bắt một phần (hook-no-m, a-chain…) | Chưa dự đoán cliff từ structure |
| **PVSS** | Proof · Value · Structure · Stakes | Có thể bổ sung nhẹ vào hook | Dễ biến thành checklist khô |

**Benchmark retention thực tế (2026, educational):**
- 5–10 phút: strong 50–60%, exceptional 60%+.
- First 30s: <70% còn lại = đỏ; 80%+ = xuất sắc.
- Algorithm quan tâm cả **shape** của curve, không chỉ average %.

**Research / Trend tools phổ biến:**
- YouTube Studio Inspiration / Research tab (audience-specific + content gaps).
- Google Trends (YouTube Search mode) + autocomplete.
- Opportunity score = f(volume, competition, trend velocity, channel fit).

---

# PHẦN III — KIẾN TRÚC MỚI ĐỀ XUẤT

### Flow V3

```
S0  Opportunity & Demand Research          ← MỚI (bắt buộc)
  │  (topic scoring + competitive selection + packaging heuristic)
  ▼
S1 → S3  (NGUYÊN TRẠNG)
  ▼
S4 / S4b + M-mining v2  (giữ + mở rộng tín hiệu)
  ▼
AUTO-DRAFT V2 + Linter V3 (thêm Predicted Retention Risk)
  ▼
BOARD V3  (user duyệt + metric target)
  ▼
Writer V2 (giữ stack “liều 3 + guard”)
  ▼
script.md
  ▼
[Post-publish] Feedback Loop  ← MỚI (retention curve → lesson)
```

### Nguyên tắc thiết kế S0
- **Semi-auto**: Tool không giả vờ có full YouTube API. User paste / upload data  
  từ Studio + Trends + autocomplete.
- **Transparent scoring**: Mọi điểm số đều có công thức công khai, không “điểm tổng ẩn”.
- **Fail-fast**: Topic không đạt threshold → dừng, không cho vào pipeline structure.
- **Kế thừa bằng chứng**: Vẫn ưu tiên misconception có resonance thật.

---

# PHẦN IV — SPEC CHI TIẾT CÁC MODULE MỚI

## 4.1. S0 — Opportunity & Demand Research

### Input bắt buộc từ user
| Trường | Bắt buộc | Ghi chú |
|--------|----------|---------|
| Seed topic(s) | Có | 1–5 ý tưởng |
| Channel size / authority | Có | Ảnh hưởng competition scoring |
| Primary metric target | Có | Ví dụ: 30s retention ≥ 75%, AVD ≥ 50%… |
| Studio Inspiration data | Có | Paste text / screenshot description |
| Google Trends (YouTube mode) | Có | Interest over time + related queries |
| Autocomplete / related searches | Khuyến khích | |
| Existing audience search terms | Khuyến khích | Từ Studio |

### Xử lý (Python thuần + heuristic)
1. **Normalize** dữ liệu user paste → structured dict.
2. **Tính 4 trục điểm** (0–10 mỗi trục):
   - **Demand**: volume ước lượng + rising indicator.
   - **Competition**: số video mạnh + median views top results + channel size adjustment.
   - **Trend Velocity**: rising / stable / declining / seasonal (từ Trends).
   - **Channel Fit**: overlap với audience hiện tại + content history.
3. **Misconception Potential** (ước lượng sơ): keyword overlap với pattern M-mining +  
   comment mẫu nếu user cung cấp.
4. **Opportunity Score** = weighted sum (công thức công khai, có thể chỉnh):

```
Opportunity = 0.30·Demand + 0.25·(10−Competition) + 0.25·TrendVelocity + 0.20·ChannelFit
```

5. **Ngưỡng**:
   - ≥ 7.0 → Green (vào pipeline).
   - 5.0–6.9 → Yellow (cần research thêm hoặc góc nhìn hẹp hơn).
   - < 5.0 → Red (dừng).

### Output
- Bảng ranked topics + điểm từng trục + lý do.
- Gợi ý góc nhìn (angle) nếu score Yellow.
- Danh sách competitive videos đề xuất cho run (outliers + top + recent).

## 4.2. Competitive Run Expansion

- Không chỉ “6 video cùng chủ đề”.
- Ưu tiên:
  1. Outlier (view / subscriber ratio cao).
  2. Top performers theo search.
  3. Video gần đây (≤ 12 tháng) có engagement tốt.
- Tool gợi ý list; user xác nhận hoặc bổ sung.
- Khi mining, ưu tiên video có comment density cao để M-mining và Question mining chất lượng hơn.

## 4.3. Packaging Heuristic (module nhẹ)

**Mục tiêu:** Đưa starting point tốt cho title/thumbnail, không thay thế A/B test thật.

- Input: Misconception mạnh nhất + core promise + specificity.
- Generate 5–8 title variants theo pattern:
  - Counterintuitive / M-break.
  - Specific number + consequence.
  - Question gap.
  - Outcome-first.
- Score sơ bằng rule công khai:
  - Có contradiction / unexpected?
  - Có số hoặc chi tiết cụ thể?
  - Độ dài 40–70 ký tự?
  - Có mở vòng tò mò không trả lời?
- Output: ranked list + lý do. User vẫn phải test thật (như Internet Stamp).

## 4.4. Linter V3 — Predicted Retention Risk

Giữ toàn bộ rule V2. Thêm lớp **risk prediction**:

| Risk | Điều kiện | Level | Gợi ý |
|------|-----------|-------|-------|
| `opening-cliff-risk` | hook-no-m hoặc hook-answers hoặc không có M-break rõ | Đỏ | Siết hook theo 3 luật M-break |
| `mid-ledge-risk` | ≥ 3 chương A nặng liền nhau khi có B candidate | Đỏ | Đan sợi B |
| `low-tension-risk` | > 50% Question là (gen) hoặc question-cov < 40% | Vàng | Ưu tiên câu hỏi nguyên văn |
| `payoff-leak-risk` | Guard “tease only” bị thiếu khi có reveal ở chương sau | Vàng | Auto-draft phải ghi guard |
| `metric-mismatch` | Outline không phục vụ primary metric target của user | Vàng | Cảnh báo |

Không có điểm tổng. Chỉ list rule pass/fail + risk.

## 4.5. Feedback Loop sau đăng (Post-publish)

1. User paste key moments / mô tả retention curve (hoặc timestamp cliff/ledge).
2. Tool map với outline + script (nếu còn).
3. Sinh “Lesson learned” structured:
   - Cliff nào khớp với rule nào?
   - M nào có resonance thật trên audience channel (không chỉ trên run chung)?
   - Pattern nào cần thêm vào M-mining config?
4. Ghi vào DEVLOG / evidence của run để lần sau auto-draft học được.

---

# PHẦN V — THAY ĐỔI LOGIC & YÊU CẦU USER

### Thay đổi logic
- **Topic selection** trở thành cổng bắt buộc (S0). Không còn “lấy topic rồi structure”.
- Auto-draft nhận thêm `primary_metric_target` → điều chỉnh nhẹ trọng số (ví dụ ưu tiên M mạnh hơn nếu target là 30s retention).
- Packaging không còn hoàn toàn ngoài phạm vi tool (có heuristic, vẫn semi-manual).
- Linter từ “cấu trúc đúng” → “cấu trúc đúng + rủi ro retention dự đoán”.

### Yêu cầu research từ user (không thể bỏ)
1. Paste dữ liệu Studio Inspiration + Google Trends trước mọi run mới.
2. Xác nhận “M này có phải misconception của **audience channel mình** không” (n chung có thể cao nhưng n riêng thấp).
3. Sau mỗi 3–5 video: import retention thật để calibrate.
4. Khi score Yellow: user phải research thêm góc nhìn hẹp hơn hoặc competitive set khác.

### Những gì giữ nguyên / không đụng
- Toàn bộ Writer stack (B1 meta-line, estimate_ideas, hook 3 luật, Question-first, pacing hẹp, guard).
- M-mining v2 (pattern config mở rộng được).
- Structure Linter core rules.
- Quyền duyệt cuối cùng của user.
- Không ép B-thread khi thiếu nguyên liệu.

---

# PHẦN VI — ROADMAP TRIỂN KHAI + CỔNG NGHIỆM THU

| # | Việc | File / Module | Cổng qua |
|---|------|---------------|----------|
| **R0** | Spec S0 + Opportunity Score công thức | docs + `oe/opportunity.py` (mới) | User duyệt công thức weighting |
| **R1** | Implement S0 MVP (parse paste data + score) | `oe/opportunity.py`, board | Chạy trên 3 topic mẫu → score hợp lý |
| **R2** | Competitive selection helper + Packaging Heuristic | `oe/suggest.py` mở rộng | Title variants có citation pattern |
| **R3** | Linter V3 + Predicted Risk | `oe/lint.py` | Outline V1 bigbang vẫn bắt đủ lỗi cũ + thêm risk |
| **R4** | Board V3 (hiển thị Opportunity + metric target + risk) | `board.html`, server | User thấy score + risk trước khi approve |
| **R5** | Feedback Loop MVP | module mới + DEVLOG | Paste curve → sinh lesson structured |
| **G2** | Thí nghiệm end-to-end: 2 topic (1 Green, 1 Yellow) → full pipeline → so retention thật sau đăng | — | User chấm: topic Green có CTR/retention tốt hơn baseline |

**Thứ tự bắt buộc:** R0 → R1 → R3 (linter) → R2/R4 → R5 → G2.

Nguyên tắc cũ vẫn giữ: rớt cổng nào → dừng nhánh đó + ghi sổ.

---

# PHẦN VII — RỦI RO & CHỐT CHẶN

1. **Data paste kém chất lượng** → score sai.  
   **Chặn:** Template paste rõ ràng + validation (thiếu Trends → không cho Green).

2. **Opportunity Score trở thành “điểm tổng ẩn”**.  
   **Chặn:** Luôn hiển thị 4 trục riêng + công thức. User có thể chỉnh weight.

3. **Packaging Heuristic tạo title “đúng rule nhưng vô hồn”**.  
   **Chặn:** Chỉ là starting point. Nhắc rõ user phải A/B test thật.

4. **Feedback loop quá muộn / user không paste curve**.  
   **Chặn:** Không bắt buộc cho mọi video, nhưng khuyến khích mạnh sau 3 video đầu.

5. **Scope creep** (muốn full API YouTube).  
   **Chặn:** Giữ semi-auto. Chỉ nâng cấp khi có API key / quota rõ ràng.

6. **M-mining trên competitive set mới bị nhiễu**.  
   **Chặn:** Giữ pattern config + verify quote tồn tại (A1).

---

# PHẦN VIII — DEFINITION OF DONE (V3)

- [ ] S0 chạy được: user paste data → bảng Opportunity Score + ranking rõ ràng.
- [ ] Topic Red bị chặn không vào pipeline structure.
- [ ] Linter V3 bắt được risk opening-cliff / mid-ledge / low-tension trên fixture cũ.
- [ ] Board hiển thị metric target + risk bên cạnh checklist 4 câu cũ.
- [ ] Packaging Heuristic sinh ≥ 5 title variants có lý do.
- [ ] Feedback Loop MVP: paste mô tả curve → lesson structured ghi được.
- [ ] Toàn bộ thay đổi không phá vỡ round-trip outline.txt v2 và meta-line handling.
- [ ] G2: ít nhất 1 topic Green cho retention/CTR tốt hơn baseline của channel (user chấm).

**Thước cuối cùng vẫn là Quality Oracle (retention/CTR thật).**  
V3 không hứa view. V3 hứa: **topic được chọn có bằng chứng demand + metric,  
cấu trúc vẫn có bằng chứng công thức, và hệ thống học được từ dữ liệu thật của channel.**

---

# PHẦN IX — PHỤ LỤC

### A. Công thức Opportunity Score (mặc định, có thể chỉnh)

```
Demand          = f(volume_estimate, rising_flag)          # 0–10
Competition     = f(strong_videos, median_views, channel_size)  # 0–10 (cao = khó)
TrendVelocity   = {rising: 9–10, stable: 6–7, seasonal: 5–8, declining: 1–3}
ChannelFit      = f(audience_overlap, content_history)     # 0–10

Opportunity = 0.30·Demand + 0.25·(10 − Competition) + 0.25·TrendVelocity + 0.20·ChannelFit
```

### B. Mapping framework → module V3

| Framework | Module tiếp nhận |
|-----------|------------------|
| Information Gap / Muller M | M-mining + Hook 3 luật (giữ) |
| SUCCESs Unexpected + Concrete | Packaging Heuristic + sợi B |
| Retention curve shape | Linter Predicted Risk |
| Studio Inspiration + Trends | S0 Opportunity |
| Curiosity Loop / Problem Stack | Auto-draft ordering + Question-first |

### C. Ví dụ quyết định S0

| Topic | Demand | Comp | Trend | Fit | Score | Quyết định |
|-------|--------|------|-------|-----|-------|------------|
| “Big Bang không phải vụ nổ” | 8.5 | 7 | 6 | 9 | 7.4 | Green |
| “Jupiter lõi như thế nào” | 7 | 8 | 8 | 8 | 6.9 | Yellow → cần góc hẹp hơn |
| “Vũ trụ giãn nở nhanh hơn ánh sáng?” | 9 | 9 | 5 | 7 | 5.8 | Yellow / research thêm |

---

**Tài liệu này đủ để bắt đầu implement R0–R1 mà không cần đọc lại V2 Master Brief.**  
Mọi quyết định thiết kế mới đều ghi rõ phạm vi để không làm vỡ các cổng đã qua (B1–B7, G1).

*Proposal soạn ngày 2026-08-21.*
