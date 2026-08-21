# PROPOSAL V3 — BẢN 2: CỨU CHẤT LƯỢNG VIẾT TRƯỚC

> **Thay thế TRỌNG TÂM của bản 1** (`PROPOSAL-Content-Ultimate-V3-Research-Metric.md`,
> soạn 21/08/2026). Bản 1 **giữ nguyên làm mốc**, không sửa, không xoá.
> Bản 2 soạn 21/08/2026 sau khi điều tra dữ liệu vận hành thật.
>
> **Lý do đổi trọng tâm:** team đã **NGỪNG dùng app từ 07/08/2026** vì "kết quả viết
> không tốt". Bản 1 sửa **đầu phễu** (chọn topic nào), trong khi tổ chức đang chết ở
> **cuối phễu** (bản thảo không dùng được). Làm bản 1 lúc này = chọn được topic hay hơn
> rồi vẫn nhận về bản thảo không dùng được.
>
> **Triệu chứng user xác nhận:** *văn vụn, câu cụt, đọc như liệt kê*.

---

# PHẦN I — ĐIỀU TRA (số đo, không cảm tính)

Toàn bộ số dưới đây đo bằng Python trên dữ liệu vận hành thật, tái lập được bằng các
lệnh ở Phụ lục A. Đúng luật **A1 — Python đo, LLM hiểu/sinh**.

## 1.1. Team dừng lúc nào

Nguồn: `data/content-ultimate/admin/history.jsonl` (51 bản ghi).

| Chỉ số | Giá trị |
|---|---|
| Lượt Writer | **38** (30 done · 5 error · 3 cancelled → **21% lượt hỏng**) |
| Lượt Extractor | 13 (11 done · 2 error) |
| Chạy đều đặn | 15/07 → **07/08 14:25**, gần như mỗi ngày |
| Sau 07/08 | **không một lượt nào** |
| Model dùng | **37/38 lượt = `glm-5.2`**, 1 lượt `glm-5`. **Chưa ai từng chạy Claude Sonnet/Opus** dù dropdown có sẵn |
| Thời gian chờ | 12–40 phút/lượt (trung bình ~20 phút) |
| Người dùng | ngocth · ngocht · namtn · nhun · Content |

## 1.2. Bệnh KHÔNG phải độ dài — cái đó đã chữa xong

| Giai đoạn | Lệch so với mục tiêu ký tự |
|---|---|
| 15–25/07 | +32% · **+113%** · +21% · +27% · +33% · +34% · +36% · +39% |
| 03–07/08 | −2% · −1% · −11% · −4% · **+0%** · +1% · −14% |

Đến đầu tháng 8 tool ra **đúng khuôn độ dài** — và team vẫn bỏ. Kết luận: thứ họ chê
là **chất lượng văn**, không phải khuôn. Mọi việc liên quan `depth_plan` / ngân sách ý
coi như đã đạt, **không đụng tiếp**.

## 1.3. Nhịp văn — đo trực tiếp trên bản đã sinh

Đơn vị: từ/câu · % câu cụt (<8 từ) · % câu dài (>35 từ).

| Hồ sơ / bản viết | từ/câu | % cụt | % dài | Đọc ra |
|---|---|---|---|---|
| **A012_Old-story** (04/08) | **8.9 – 13.7** | **48–55%** | 0.6–6.6 | **vụn nặng — đúng "đọc như liệt kê"** |
| **A013_Derek-Muller** (07/08) | 13.8 | **36.9%** | 5.6 | vụn |
| A011_Discover-Ventures (03–07/08) | 20–22 | 10–23% | 9–18 | tạm ổn |
| A003_Ventures (20–23/07) | **29–35** | 10–15% | **36–49%** | **câu nhồi — bệnh ngược** |

Cùng một stack prompt mà nhịp dao động **8.9 → 34.8 từ/câu** (chênh gần 4 lần).
Biến quyết định không nằm ở prompt.

## 1.4. Truy vết: neo giọng đi tới prompt bằng đường nào

Đọc `src/voiceprofile/generator.py`:

1. **Dòng 430** — `exemplars = profile.get("exemplars", [])[:3]`
   → prompt **chỉ nhận tối đa 3 exemplar**, cắt cứng. Hồ sơ có nhiều hơn cũng vô ích.
2. **Không có** `sentence_len_mean`, `reproduction_targets`, `ttr`, `avg_word_len`
   ở bất kỳ đâu trong `generator.py` (grep = rỗng)
   → **mọi target nhịp đo được của hồ sơ KHÔNG BAO GIỜ tới tay model.**
3. Vậy **neo nhịp duy nhất = 3 đoạn exemplar**. Đây là quyết định có chủ ý, ghi ở
   `YOUTUBE_RULES` (dòng ~88-95): *"Nhịp câu phải đến từ EXEMPLAR thật (show, đừng tell);
   luật nền tảng chỉ nói về CẤU TRÚC, không về độ dài câu"* — sửa 16/07 sau khi luật
   hard-code "long clause-rich sentences" làm LLM ra 271–307 ký tự/câu.

## 1.5. Đo chính cái neo đó — và nó đang hỏng

| Hồ sơ | exemplar (từ) | exemplar: từ/câu | → | output: từ/câu | output: % cụt |
|---|---|---|---|---|---|
| A003_Ventures | 4.403 | **880.6** ⟵ *không có dấu chấm* | | 34.8 | 9.6% |
| A011_Discover-Ventures | 200 | 15.4 | | 20.9 | 14.7% |
| A012_Old-story | 219 | 12.2 | | **8.9** | **54.5%** |
| A013_Derek-Muller | 248 | 20.7 | | **13.8** | **36.9%** |

Và phân bố dấu câu trong `profile.json`:

| Hồ sơ | `sentence_len_mean` | dấu phẩy | chấm/hỏi/than | Kết luận |
|---|---|---|---|---|
| **A003 · A008 · A011** (cùng corpus 18.587 token) | **1085.1** | 0.0361 | **≈ 0** | corpus **transcript thô, không dấu chấm câu** |
| **A012** | 10.0 | 0.0395 | 0 | cùng bệnh |
| A013_Derek-Muller | 16.8 | 0.0679 | đủ `;` `:` `—` `()` `?` | **corpus sạch** |

`sentence_len_mean = 1085` là con số không thể có ở người viết — đó là dấu vân tay của
**transcript YouTube auto-caption chưa dọn dấu câu**: cả văn bản bị đo như MỘT câu.

**Ba exemplar của A011 còn trùng lặp nhau** (mẫu 3 chứa nguyên mẫu 1) → thực chất chỉ
~130 từ hữu ích làm neo giọng.

## 1.6. Chuỗi nhân quả hoàn chỉnh

```
corpus nạp vào là transcript thô (không dấu chấm câu)
        │
        ├─► quant_features đo sai      → sentence_len_mean = 1085 (vô nghĩa)
        │        └─► chars_per_idea / length_lab sai → depth_plan tính sai số ý
        │
        └─► exemplar trích ra cũng hỏng
                 ├─ A003: exemplar 880 từ/câu  → model viết câu NHỒI (34.8 từ/câu)
                 └─ A012/A013: exemplar mỏng   → model rơi về register mặc định
                                                  của GLM = CÂU VỤN (37–55% câu cụt)

+ Neo duy nhất là 3 đoạn ~200 từ, đấu với cả trăm dòng luật prompt
  (M-break 3 luật · Question-first · PACING · LOOP DISCIPLINE · DEPTH PLAN · guard)
+ 100% lượt chạy bằng GLM — đúng model mà §11 Master Brief đã đo là ra nhịp ngắn-vụn
```

**Con lắc 16/07:** trước đó luật nền tảng *tell* "viết câu dài" cho mọi tác giả → user
chê "câu văn phẳng và quá dài". Gỡ luật đó đi, chuyển sang *show* bằng exemplar — nhưng
"show" chỉ có 3 đoạn ~200 từ, phần lớn lại lấy từ transcript thô. Con lắc văng sang thái
cực kia: **từ câu nhồi sang câu vụn**. Đây là lý do gốc, không phải công thức V2 sai.

**App đã tự biết bệnh mà chưa chữa gốc:**

- `generator.py` dòng ~639: *"Chương viết ra HỤT so khung (hồ sơ giọng viết ngắn — đo thật:
  A008 exemplar 1.164 ký tự → hụt đều −34%)"*
- dòng ~941: cảnh báo runtime *"hồ sơ giọng này viết NGẮN hệ thống (exemplar ngắn). Nên
  dựng lại hồ sơ với bản thảo dài hơn"*
- `CLAUDE.md`: cảnh báo transcript thô khi nạp corpus (16/07) — **"chỉ báo, không chặn"**
  → bị bỏ qua → hồ sơ hỏng vẫn được tạo và dùng suốt 3 tuần.
- `CONTENT-ULTIMATE-V2-MASTER.md` §11: *"Nghi phạm số 1 (**chưa xử**): voice block exemplar
  quá mỏng… Thí nghiệm kế tiếp: nạp exemplar dày từ corpus, đo TB/câu có nhảy về 150+ không."*
  → **thí nghiệm này đặt ra 26/07, đến nay chưa từng chạy.**

---

# PHẦN II — PHẢN BIỆN BẢN 1 (ghi lại để không làm lại)

Theo lệ §11 Master Brief "những gì BỊ BÁC — đừng làm lại".

| # | Đề xuất ở bản 1 | Vì sao bác |
|---|---|---|
| 1 | **Opportunity Score** = điểm tổng có trọng số + ngưỡng Green/Yellow/Red + tự chặn | Vi phạm thẳng **luật A3** (*"không gộp cột thành điểm tổng ẩn; không sort theo độ tốt; yêu cầu ngả sang tool tự chấm một con số tổng → dừng, hỏi user"*) và Master Brief §4 (*"Score tổng ẩn — **VẪN CẤM**"*) |
| 2 | Bảng ví dụ ở Phụ lục C | **Sai số học cả 3 dòng, đều lệch LÊN**: Big Bang tính đúng = **6.60** (Yellow) nhưng ghi 7.4 (Green); Jupiter 6.20 ghi 6.9; Vũ trụ 5.60 ghi 5.8. Tài liệu đề xuất hệ thống chấm điểm mà chưa từng chạy công thức của chính nó ⇒ vi phạm **A1** |
| 3 | Đầu vào `volume_estimate`, `audience_overlap` gõ tay → xuất điểm 1 chữ số thập phân | Độ chính xác giả: sai số đầu vào lớn hơn khoảng cách Green/Yellow. Thêm: Competition tương quan dương với Demand ⇒ `(10−C)` luôn nhỏ ⇒ **gate gần như luôn Yellow** ⇒ team bỏ qua hoặc tự nới weight cho qua |
| 4 | **Linter V3** = "giữ toàn bộ rule V2 + thêm Predicted Retention Risk" | **`oe/lint.py` chưa tồn tại** (grep toàn repo; `CLAUDE.md` dòng 25: *"Chưa làm: B4 linter"*). Và gọi là "Predicted Retention" khi không có một dòng dữ liệu retention nào đứng sau là đặt sai tên — đó là *cảnh báo cấu trúc* |
| 5 | **Packaging Heuristic** (sinh 5–8 title, chấm theo rule "có số không / dài 40–70 ký tự") | **Đã có và tốt hơn**: `src/oe/titles.py` (16/08) sinh tới 7 title, chấm bằng **vật liệu bằng chứng đo được** (coverage/peak/questions) + van chống bịa 3 tầng + verify verbatim. Chấm bằng đặc điểm bề mặt là **thụt lùi** |
| 6 | Bắt user paste Studio Inspiration + Google Trends mỗi run | Hệ đã có **RadarY** (cào kênh/outlier), **Niche Research 8 phase** (demand/gaps/crackability + gate ký người), **Data Analytics** (report Studio thật, engine 4 trục), **SEO Optimize** (19 key YouTube). Xây tay = đẻ **nguồn sự thật thứ hai** về "topic nào đáng làm", chắc chắn lệch với gate 8 phase |
| 7 | Benchmark ngoài "5–10 phút: strong 50–60%" | Trái lệ đã chốt 21/07: **baseline TỰ KÊNH là xương sống**, benchmark ngoài chỉ tham chiếu |

**Điểm ĐÚNG của bản 1, giữ lại:** gap demand-side là thật · vòng học từ retention thật
là hướng đúng · "shape > average %" đúng.

---

# PHẦN III — MẠCH C: CỨU CHẤT LƯỢNG VIẾT (ưu tiên đợt này)

Nguyên tắc: **chữa đúng cái làm team bỏ tool**, rẻ, đo được, không đụng công thức V2.

> ## ✅ TRẠNG THÁI 21/08/2026 — C1 · C2 · C4 ĐÃ DỰNG XONG
>
> Gộp chung với mạch De-AI của `docs/kich-ban-studio.md` (mục 9) vì cả hai cần **cùng
> một cái thước**. Đã có trên tab Writing: nút **🔍 Kiểm chứng kịch bản** + bảng 3 nhóm
> (dấu vết máy · nhịp so exemplar · bám giọng) + **cảnh báo hồ sơ hỏng ngay khi chọn
> tác giả** + **cửa chặn corpus transcript thô** ở `/api/build`.
>
> | Việc | Trạng thái | File |
> |---|---|---|
> | C1 soi hồ sơ | ✅ | `src/voiceprofile/soi_ho_so.py` · `GET /api/soi-ho-so` |
> | C2 chặn nguồn hỏng | ✅ | `POST /api/build` → 409 `corpus_transcript_tho` |
> | C4 thước đo sau WRITE | ✅ | `src/voiceprofile/deai.py` · `POST /api/kiem-chung` |
> | C3 dựng lại neo giọng | ⬜ **kế tiếp** — giờ đã có thước để chứng minh ăn hay không |
> | C5 A/B GLM vs Claude | ⬜ | 1 chương × 2 model |
>
> Test `tests/test_deai.py` 31 ca; suite content **282 pass / 4 fail** = đúng baseline
> cũ, không tăng. Smoke thật trên server tạm (cổng 8799, `CU_DATA_DIR` tạm).
>
> **Đo được ngay khi bật (21/08):** A013 bản 07/08 — 17,4 em-dash/1000 từ · 14,0 từ/câu
> (exemplar 20,9) · **38% câu cụt** (exemplar 8,3%) · **bám giọng 18%**. A012 bản 04/08 —
> **54,5% câu cụt · bám giọng 0%**. Văn NGƯỜI (exemplar 4 hồ sơ): **0,00 em-dash/1000 từ**.

## C1 — Soi lại toàn bộ hồ sơ giọng (chẩn đoán)

- **Làm gì:** quét 9 hồ sơ trong `uploads/A0*/profile.json`, chấm cờ hồ sơ hỏng theo 3 dấu
  hiệu **đo được**: `sentence_len_mean` bất thường (>60 hoặc <8) · tần suất dấu kết câu
  ≈ 0 · exemplar dưới ngưỡng dày (< ~800 từ) hoặc trùng lặp nhau.
- **Chạm:** file mới `voiceprofile/soi_ho_so.py` + 1 bảng trên trang Author. Không sửa
  logic build hồ sơ.
- **Cổng nghiệm thu:** bảng chỉ đúng A003/A008/A011/A012 là hỏng, A013 là sạch — khớp
  bảng §1.5 của tài liệu này.
- **Chi phí:** 0 token. **Rủi ro:** không.

## C2 — Chặn nguồn: hết đẻ thêm hồ sơ hỏng

- **Làm gì:** nâng `transcript_warnings` (16/07) từ *chỉ báo* thành **chặn có xác nhận**:
  corpus không có dấu kết câu → không cho build hồ sơ cho tới khi user tick "tôi hiểu
  corpus này là transcript thô".
- **Vì sao đổi quyết định cũ:** quyết định "chỉ báo" là đúng ở thời điểm ra đời, nhưng dữ
  liệu 3 tuần cho thấy nó **bị bỏ qua 100%** và hậu quả là toàn bộ hồ sơ chủ lực hỏng.
  Đây là chặn **nguồn nhập**, không phải tool tự quyết hộ nội dung ⇒ **không đụng A3**.
- **Chạm:** `voiceprofile/corpus.py` (ngưỡng) + `/api/detect-corpus` + board Author.
- **Cổng nghiệm thu:** nạp lại chính corpus 18.587 token của A003 → bị chặn; corpus
  Derek Muller → qua bình thường.
- **Chi phí:** 0 token.

## C3 — Dựng lại neo giọng (việc chữa bệnh chính)

Hai phần, làm theo thứ tự, **mỗi phần một cổng**:

- **C3a — khôi phục dấu câu cho corpus thô.** Transcript không dấu chấm → một lượt LLM
  chỉ chèn dấu câu, **cấm đổi một từ nào** (van verbatim: so token trước/sau, khác từ →
  loại). Đây là điều kiện tiên quyết: không có dấu câu thì mọi số đo nhịp đều rác.
- **C3b — exemplar DÀY** — chính thí nghiệm §11 đặt ra 26/07 chưa từng chạy:
  nâng trần `[:3]` ở `generator.py:430` thành tham số, chọn exemplar theo **tổng số từ**
  (mục tiêu ~1.500–2.500 từ) thay vì đếm 3 mẫu, và **loại mẫu trùng nhau**.
- **Cổng nghiệm thu (đo, không cảm tính):** chạy lại **cùng outline, cùng model, cùng
  hồ sơ** trước/sau — A013 phải đi từ 13.8 từ/câu · 36.9% cụt về gần exemplar
  (20.7 · 8.3%); A012 phải thoát khỏi vùng 50% câu cụt. Không đạt → không merge.
- **Chi phí:** C3a ~1 lượt LLM/corpus. C3b: 0 (chỉ đổi cách chọn exemplar) + chi phí
  chạy lại 1–2 bài để đo.

## C4 — Thước đo nhịp ngay sau mỗi lần WRITE

- **Làm gì:** viết xong in 3 số (từ/câu · % cụt · % dài) **so với chính exemplar của hồ sơ
  đang dùng**, kèm một dòng đánh giá "khớp / vụn hơn giọng gốc / nhồi hơn giọng gốc".
- **Vì sao cần:** hôm nay "tốt / không tốt" hoàn toàn là cảm tính, nên không ai biết bản
  nào tệ ở đâu, và không có cách nào biết một bản vá có ăn thua hay không. Đây là
  **Quality Oracle bản nhẹ** — chỉ báo, không chặn, không tự sửa (A3).
- **Chạm:** `voiceprofile/quant.py` (tái dùng hàm đo sẵn có) + panel kết quả tab Writing.
- **Chi phí:** 0 token.

## C5 (tuỳ chọn, rẻ) — A/B dứt điểm câu hỏi "có phải tại model"

- Cùng **một chương**, cùng outline, cùng hồ sơ: `glm-5.2` vs `claude-sonnet-5`.
- Trả lời câu treo từ §11: *"nhịp ngắn-vụn là register của GLM dưới stack prompt này"* —
  team đang chạy **37/38 lượt bằng GLM**, chưa ai kiểm chứng.
- Kết quả có 2 đường ra rõ ràng: nếu Claude ra nhịp đúng ⇒ vấn đề là **chọn model cho
  khâu viết**, không phải công thức; nếu cả hai đều vụn ⇒ dồn hết vào C3.
- **Chi phí:** 1 chương × 2 model.

## Thứ tự bắt buộc

```
C1 (biết hồ sơ nào hỏng)  →  C2 (hết đẻ thêm)  →  C4 (có thước đo)
        →  C3a (dấu câu)  →  C3b (exemplar dày)  →  đo lại bằng C4
                                  └─ song song rẻ: C5
```

C4 đứng **trước** C3 có chủ đích: phải có thước trước khi sửa, nếu không lại rơi vào
vòng "sửa theo cảm giác" đúng như con lắc 16/07.

## Định nghĩa HOÀN THÀNH của mạch C

- [ ] Bảng soi hồ sơ chỉ đúng hồ sơ hỏng (khớp §1.5).
- [ ] Corpus transcript thô không build được hồ sơ nếu không xác nhận.
- [ ] Mỗi bản viết ra kèm 3 số nhịp so với exemplar hồ sơ.
- [ ] A013 chạy lại: % câu cụt từ 36.9% về **≤ 15%**; A012 từ 54.5% về **≤ 20%**.
- [ ] **Cổng cuối cùng là người, không phải số:** team đọc 1 bản mới và nói dùng được.
- [ ] Suite content **không tăng số fail** so với baseline hiện tại (245 pass / 4 fail).

---

# PHẦN IV — V3 RESEARCH LAYER (HOÃN — bản rút gọn khi quay lại)

Giữ lại đây để không phải bàn lại. **Điều kiện kích hoạt: team đã quay lại dùng tool
thật ít nhất 2 tuần.** Khi đó làm đúng 3 việc, theo thứ tự:

| # | Việc | Ghi chú chốt |
|---|---|---|
| V3-1 | **Linter cấu trúc** (nợ B4 từ 07/2026) — rule pass/fail công khai, **không điểm tổng** | Fixture tự nhiên: outline V1 `bigbang` phải bắt `hook-no-m`, `question-cov`, `a-chain`, `dup-core`, `broken-name`, `hook-contradiction` |
| V3-2 | **Vòng học từ retention thật** — đọc report YouTube Studio qua Data Analytics (`diagnosis_engine`, `bao_cao_lich_su`), **không paste chữ** | Phải làm **trước** mọi thang điểm: không có nó thì mọi trọng số/ngưỡng đều là số bịa |
| V3-3 | **Phiếu bằng chứng nhu cầu** — gọi `/api/agent/registry` + `/api/agent/bao-cao/{project}` của DA, hiện 5–6 cột số thật, **user pick** | Cổng chặn (nếu cần) dùng **gate ký người** của Niche Research đã có, không đẻ ngưỡng máy mới |

**Bỏ hẳn, không bàn lại:** Opportunity Score có trọng số + ngưỡng · Packaging Heuristic ·
nhãn "Predicted Retention" · bắt user paste Trends/Studio mỗi run.

**Cổng nghiệm thu thay cho G2 của bản 1:** *backtest ngược* — chấm các video **đã đăng**
(đã biết retention/CTR thật); nếu hệ xếp video đã thành công vào Yellow/Red thì thang
điểm sai, sửa hoặc bỏ. (Chính `bigbang` — fixture chuẩn của repo — bị bản 1 chấm 6.60 = Yellow.)

---

# PHẦN V — RÀNG BUỘC BẮT BUỘC (mọi việc trong tài liệu này)

Tool là **một function nằm trong Content Ultimate**, chịu luật chung của app và của
khối nền V3:

1. **A1** — Python đo, LLM hiểu/sinh. Không con số nào do LLM ước lượng rồi trình bày
   như đã đo (bài học: chính bản 1 vấp lỗi này).
2. **A3** — tool trình bằng chứng, **user pick**. Không điểm tổng, không xếp hạng hộ,
   không tự sửa. C2 chặn ở **cửa nhập corpus**, không phải chặn quyết định nội dung.
3. **A5** — độ sâu giao bằng Ý, không bằng số câu/ký tự. Mạch C **không đụng** `depth_plan`.
4. **Khuôn V3** (đã di trú 17/08, cổng 9112): claims quyền `vao`/`sua`/`quan_tri` ·
   khóa lấy từ **KÉT** qua `khoa_v3.viec_api` (thêm việc mới phải khai, Owner chạy
   migration) · **không đẻ route quản trị mới** (7 route quản trị đã đóng 404) ·
   giao diện `khung` giữ sidebar · không job nền.
5. **Sửa xong phải Stop/Start tác vụ nền** mới ăn bản mới.
6. **Không nghiệm thu ghi/xoá trên hệ thật** — dùng fixture `bigbang` và bản sao hồ sơ,
   không chạy pipeline đè lên run team đang làm dở.
7. Làm trên **bản V3** (`d:\AI AGENT OUTLIERY\apps\content-ultimate`), không sửa chéo
   bản hệ cũ ở ổ C.

---

# PHẦN VI — PHỤ LỤC

## A. Lệnh tái lập số đo

```bash
# 1) Lịch sử chạy writer: ai, khi nào, lệch ký tự bao nhiêu
cd "d:/AI AGENT OUTLIERY/data/content-ultimate"
python -c "import json,datetime; rows=[json.loads(l) for l in open('admin/history.jsonl',encoding='utf-8') if l.strip()]; w=[r for r in rows if r.get('kind')=='writer']; [print(datetime.datetime.fromtimestamp(r['ts']).strftime('%Y-%m-%d %H:%M'), r.get('status'), r.get('chars_target'), r.get('chars'), r.get('provider')) for r in sorted(w,key=lambda x:x['ts'])]"

# 2) Nhịp câu của một bản đã sinh (từ/câu · %cụt · %dài)
#    tách câu theo [.!?] rồi đếm từ — đo trên uploads/A0*/history/*.md

# 3) Dấu vân tay corpus hỏng
python -c "import json; d=json.load(open('uploads/A011_Discover-Ventures/profile.json',encoding='utf-8')); print([f for f in d['quant_features'] if 'sentence_len_mean' in str(f.get('name'))])"
```

## B. Neo tài liệu

| Kết luận | Neo |
|---|---|
| Exemplar bị cắt còn 3 | `src/voiceprofile/generator.py:430` |
| Target nhịp không vào prompt | grep `sentence_len` / `reproduction_targets` trong `generator.py` = rỗng |
| Vì sao gỡ luật độ dài câu 16/07 | `generator.py` → `YOUTUBE_RULES` (~dòng 88-95) |
| App đã biết bệnh exemplar ngắn | `generator.py` ~639 và ~941 |
| Cảnh báo transcript thô chỉ báo, không chặn | `CLAUDE.md` mục "Cảnh báo transcript thô khi nạp corpus" |
| Nghi phạm số 1 chưa xử | `CONTENT-ULTIMATE-V2-MASTER.md` §11 |
| Cấm điểm tổng | `CLAUDE.md` §A3 · `CONTENT-ULTIMATE-V2-MASTER.md` §4 |
| Linter chưa tồn tại | `CLAUDE.md` dòng 25 |
| Packaging đã có | `src/oe/titles.py` (16/08/2026) |

## C. Câu còn treo

- Vì sao 21% lượt Writer hỏng (5 error + 3 cancelled)? Chưa điều tra — nếu là lỗi lặp
  cùng một nguyên nhân thì đây là việc rẻ đáng làm cùng mạch C.
- Thời gian chờ 12–40 phút/lượt: ma sát thật với người dùng, chưa ai đo tại sao lâu.
- `ngocth` và `ngocht` là hai tài khoản khác nhau trong log — cần xác nhận có phải cùng
  một người sau đợt nhập lại nhân sự 31/07 không.

*Bản 2 soạn 21/08/2026. Bản 1 giữ nguyên tại `PROPOSAL-Content-Ultimate-V3-Research-Metric.md`.*
