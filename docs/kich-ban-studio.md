# KỊCH BẢN STUDIO — spec logic biên tập kịch bản (soạn 21/08/2026)

> Sổ chủ đề cho mạch "công cụ xử lý kịch bản": giải nén câu, nâng chất, gỡ mác AI.
> Nguồn tham chiếu: repo `guillaumemeyer/watermarks-remover` (MIT) — CHỈ lấy Layer A,
> KHÔNG lấy Layer B (lý do ở mục 1).

## 0. Ba mục tiêu (user chốt)

1. **Kịch bản hay hơn** — không phải "khác đi".
2. **Giải nén / phẳng câu** — câu ngắn, một ý một câu, đọc thành lời được (voice-over).
3. **Không bị gắn mác AI** — cả ký tự ẩn lẫn văn phong tiếng Việt.

Mục tiêu 1 và 3 KÉO NGƯỢC NHAU nếu làm theo kiểu "paraphrase toàn văn": đổi từ càng
nhiều thì càng xa mác AI nhưng càng nát văn. Lời giải của spec này: **không xáo từ
bừa, mà sửa ĐÚNG CHỖ có bệnh** — chỗ nào máy chỉ ra bệnh mới sửa, chỗ nào lành thì giữ.

## 1. Vì sao không dùng Layer B của repo kia

| Điểm | Repo watermarks-remover | Spec này |
|---|---|---|
| Đơn vị xử lý | Cả file trong 1 prompt (không chunk) | Chunk theo cảnh 800–1.200 từ |
| Mục tiêu prompt | "Đổi từ ở mức token" (temp 0.9) | Biên tập viên: giải nén + bỏ sáo (temp 0.5) |
| Chọn bản tốt | Bản LỆCH GỐC NHẤT thắng | Bản QUA VAN KIỂM CHỨNG mới được nhận |
| Chống cắt cụt | Có guard nhưng KHÔNG chạy trong đường thật (`_select_candidate` chỉ có trong test) | Van độ dài 0,85–1,15 là điều kiện nhận |
| Giữ số liệu/tên | Chỉ "dặn miệng" trong prompt | Bảng bất biến, kiểm nguyên văn sau khi viết |
| Đo mác AI | Regex 100% tiếng Anh (`delve into`, `in conclusion`) | Luật tiếng Việt ngoài code (CSV) |
| Khi hỏng | Vẫn trả bản hỏng | Giữ nguyên bản gốc chunk đó + ghi lý do |

Cái DUY NHẤT đáng lấy nguyên khối: `service/scripts/text_unicode.py` (724 dòng,
stdlib thuần, MIT) — bảng ~60 codepoint vô hình + 16 space homoglyph, có logic chống
dương tính giả cho emoji/cờ/bidi. Chép vào `src/lam_sach_unicode.py`, giữ ghi công MIT.

## 2. Kiến trúc 6 tầng

```
T0  NHẬN & PHÂN ĐOẠN   (không LLM)  → Layer A + bảng bất biến + chunk theo cảnh
T1  CHẨN ĐOÁN          (không LLM)  → điểm mác AI + vị trí bệnh cụ thể   [BASELINE]
T2  BIÊN TẬP           (LLM, song song từng chunk)
T2b NEO PHƯƠNG PHÁP    (tùy chọn)   → search kho tri thức lấy tiêu chuẩn biên tập
T3  KIỂM CHỨNG         (không LLM)  → 4 van an toàn, không qua thì giữ bản gốc
T4  PHẢN BIỆN          (LLM khác)   → critic bắt mất ý / bịa thêm
T5  GHÉP & BÁO CÁO     (không LLM)  → Layer A lần 2 + báo cáo trước/sau
```

### T0 — Nhận & phân đoạn

1. Đọc `.txt` / `.md` / `.docx` (tái dùng `_doc_file` bên agent-app).
2. **Layer A**: quét ký tự vô hình + chuẩn hóa space homoglyph. Lossless, ~10–50 ms.
3. **Trích bảng bất biến** — thứ BẮT BUỘC sống sót nguyên văn qua biên tập:
   - số liệu, %, tiền, đơn vị (`\d[\d.,]*\s*(%|đ|VNĐ|k|tr|triệu|tỷ|USD)?`)
   - mốc thời gian, ngày tháng
   - URL, @handle, hashtag
   - tên riêng / thương hiệu (chữ hoa giữa câu, viết hoa liên tiếp)
   - CTA (dòng chứa "đăng ký", "like", "bình luận", "link dưới mô tả"…)

   Người dùng bổ sung được qua `rules/bat_bien.csv`.
4. **Chunk theo CẢNH, không theo ký tự**: cắt ở heading / dòng trống / mốc thời gian
   `[00:35]`; gộp tới ~1.000 từ; TUYỆT ĐỐI không cắt giữa câu. Mỗi chunk mang theo
   2 câu cuối của chunk trước làm **mồi mạch** (vào prompt, KHÔNG vào output).

### T1 — Chẩn đoán (máy dò mác AI tiếng Việt)

**Luật ngoài code**: `rules/mac_ai_tieng_viet.csv`, cột
`mau_regex, nhan, trong_so, goi_y_sua, ghi_chu`. Thêm cụm mới = thêm dòng Excel,
không sửa code (đúng lệ `diagnosis_rules.csv`).

Bộ khởi đầu (user tự bổ sung theo giọng kênh):

| Nhóm | Ví dụ mẫu |
|---|---|
| Dấu câu | em-dash `—`, `–` giữa câu, nháy cong `"…"` |
| Cụm sáo | "trong thế giới ngày nay", "hãy cùng khám phá", "điều này cho thấy", "có thể nói rằng", "đóng vai trò quan trọng", "không chỉ… mà còn" |
| Chuyển ý máy | "Thứ nhất/Thứ hai/Thứ ba", "Tóm lại", "Nhìn chung", "Hơn nữa", "Bên cạnh đó" |
| Cấu trúc | liệt kê 3 vế trong 1 câu, câu >25 từ, mệnh đề lồng >2 tầng |

**Chỉ số cấu trúc** (tính bằng code, không LLM):

- `do_dai_cau_tb`, `ti_le_cau_dai` (>25 từ)
- `burstiness_cv` = độ lệch chuẩn ÷ trung bình độ dài câu — người viết CV cao,
  máy viết CV thấp (câu đều tăm tắp). Tín hiệu mạnh nhất.
- `mat_do_liet_ke`, `ti_le_doan_deu_nhau`, `MATTR` (đa dạng từ vựng)

Đầu ra: `DiemMacAI(diem 0–100, hit[] có vị trí dòng + cụm, chi_so{})`. Đây là
**baseline TRƯỚC** để cuối bài đối chiếu — không có baseline thì không chứng minh
được là đã cải thiện.

### T2 — Biên tập (LLM, từng chunk, chạy song song)

Prompt truyền vào 4 thứ:

1. Nội dung chunk.
2. **Danh sách cụm bệnh CÓ THẬT trong chunk này** (từ T1) — sửa đúng chỗ, không xáo bừa.
3. **Bảng bất biến của chunk** — "các mục sau phải xuất hiện NGUYÊN VĂN".
4. Mồi mạch (2 câu cuối chunk trước).

Ba nhiệm vụ nêu rõ trong prompt, theo thứ tự ưu tiên:

- **Giải nén**: câu >25 từ tách thành 2–3 câu; bỏ mệnh đề lồng; một ý một câu;
  viết như đang nói cho một người nghe.
- **Bỏ mác**: thay từng cụm sáo trong danh sách bằng cách nói cụ thể; xóa em-dash;
  phá nhịp đều (xen câu 4 chữ giữa các câu dài).
- **Nâng chất**: giữ và làm sắc hook; giữ giọng kênh; KHÔNG thêm ý mới, KHÔNG thêm số liệu.

Ràng buộc cứng trong prompt: giữ độ dài ±10%, giữ thứ tự cảnh, chỉ trả văn bản đã
biên tập. `temperature 0.5`, `LLM_TIMEOUT` 180s, `retry 0` (bài học 19/07 + 06/08:
SDK tự retry là bẫy treo 30 phút).

**Model biên tập PHẢI khác model đã sinh kịch bản gốc** — viết lại bằng chính model
nguồn thì có thể bị đóng dấu lại (repo kia gọi là re-stamp, có `--restamp-control`).

### T2b — Neo phương pháp luận (tùy chọn, thế mạnh riêng)

Trước khi biên tập, search kho tri thức (Qdrant) lấy 2–3 chunk về hook / retention /
nhịp kịch bản từ tài liệu bài-học-kinh-nghiệm đã nạp, đưa vào prompt làm **tiêu chuẩn
biên tập của kênh mình**. Van chống bịa: kho không có tài liệu → bỏ hẳn khối này,
KHÔNG để model tự nghĩ ra tiêu chuẩn. Đây là thứ repo ngoài không thể có.

### T3 — Kiểm chứng (van an toàn, không LLM)

Mỗi chunk output phải qua **4 van**, thứ tự rẻ → đắt:

| Van | Điều kiện | Không qua thì |
|---|---|---|
| 1. Độ dài | 0,85 ≤ len(mới)/len(gốc) ≤ 1,15 | Gọi lại 1 lần (chống cắt cụt) |
| 2. Bất biến | Mọi mục trong bảng có mặt nguyên văn | Gọi lại 1 lần, kèm danh sách mục thiếu |
| 3. Không bịa | Không có số liệu MỚI nào không có trong input | Cảnh báo + đánh dấu để người soi |
| 4. Có tiến bộ | `diem_mac_ai(mới) < diem_mac_ai(gốc)` và `burstiness_cv` tăng | Gọi lại 1 lần với danh sách cụm còn sót |

Sau 2 lần vẫn không qua → **GIỮ NGUYÊN chunk gốc**, ghi lý do vào báo cáo.
Nguyên tắc: **không bao giờ trả về bản hỏng, thà không sửa**.

### T4 — Phản biện (critic, model thứ hai)

Tái dùng đúng kiến trúc `src/llm/` + vòng phản biện của agent-app. Critic đọc bản gốc
+ bản mới, phán 4 tiêu chí: mất ý / bịa thêm / còn sáo / có hay hơn không → `ĐẠT`
hoặc `LỖI` kèm chỗ sai. `LỖI` → viết lại 1 lần rồi chốt. Critic tắt được qua `.env`
(`CRITICS=` để trống) khi cần chạy nhanh.

### T5 — Ghép & báo cáo

Ghép chunk theo thứ tự → **Layer A lần 2** (model hay sinh lại NBSP/em-dash) → báo cáo:

- điểm mác AI **trước / sau**, kèm danh sách cụm đã gỡ
- `burstiness_cv` trước/sau, số câu dài đã tách
- độ dài trước/sau, bảng bất biến giữ đủ chưa
- chunk nào bị GIỮ NGUYÊN vì không qua van (và vì sao)
- token + thời gian + chi phí thật

## 3. Chi phí & thời gian (kịch bản 22.000 ký tự)

22.000 ký tự tiếng Việt ≈ 3.500–4.000 từ ≈ **4 chunk**.

| Khâu | Token | Thời gian |
|---|---|---|
| T0 + T1 + T3 + T5 (không LLM) | 0 | < 1 giây |
| T2 biên tập (4 chunk × ~5,5k) | ~22k | 40–70 s (chạy song song) |
| T4 critic (4 chunk) | ~22k | ~30 s |
| **Tổng** | **~45k token** | **1,5–3 phút** |

Với glm-4.5-air ≈ **600–800đ/kịch bản** (chiếu theo mốc đo thật 06/08: ~200–250đ cho
~15k token). So với one-shot của repo kia: rẻ hơn không nhiều nhưng **nhanh gấp 3–5
lần** (song song được) và **không có rủi ro cắt cụt / vượt context**.

## 4. Cấu trúc code đề xuất

```
kich-ban-studio/
  src/
    lam_sach_unicode.py   # Layer A — chép từ watermarks-remover (MIT), giữ ghi công
    bat_bien.py           # trich_bat_bien() / kiem_bat_bien()
    phan_doan.py          # phan_doan() cắt theo cảnh, không cắt giữa câu
    cham_mac_ai.py        # cham_mac_ai() đọc CSV luật, trả điểm + vị trí
    bien_tap.py           # bien_tap_doan() — 1 lời gọi LLM/chunk
    kiem_chung.py         # 4 van an toàn
    phan_bien.py          # critic, tái dùng src/llm/ agent-app
    pipeline.py           # chay() điều phối T0→T5, trả (van_ban, bao_cao)
  rules/
    mac_ai_tieng_viet.csv
    bat_bien.csv
  tests/
```

Chữ ký chính:

```python
lam_sach(text) -> tuple[str, dict]
trich_bat_bien(text, luat) -> list[BatBien]
phan_doan(text, muc_tieu_tu=1000) -> list[Doan]
cham_mac_ai(text, luat) -> DiemMacAI               # diem, hit[], chi_so{}
bien_tap_doan(doan, bat_bien, cum_benh, mach_truoc, llm) -> str
kiem_chung(goc, moi, bat_bien, luat) -> KetQuaVan  # dat: bool, ly_do: list[str]
chay(text, cau_hinh) -> tuple[str, BaoCao]
```

## 5. Sáu nguyên tắc bất biến (không được sửa về sau)

1. **Luật ngoài code** — thêm cụm mác AI / mẫu bất biến bằng CSV, không đụng Python.
2. **Không bao giờ trả bản hỏng** — không qua van thì giữ nguyên bản gốc, ghi lý do.
3. **Bảng bất biến sống nguyên văn** — số liệu, tên, URL, CTA; số liệu MỚI = cờ đỏ.
4. **Model biên tập ≠ model sinh gốc** (chống đóng dấu lại).
5. **Mọi lời gọi LLM có timeout, retry = 0** — SDK mặc định retry là bẫy treo.
6. **Chunk theo cảnh, không cắt giữa câu** — mạch kịch bản là thứ chết trước tiên.

## 6. Giới hạn trung thực (nói trước, không hứa quá)

- Máy nâng được **độ đọc** (giải nén, nhịp, gỡ sáo), KHÔNG tự nâng được **ý tưởng**.
  Muốn "hay hơn" theo nghĩa insight thì phải qua T2b — neo vào phương pháp luận đã
  nạp trong kho, hoặc người biên tập chốt.
- Không công cụ nào **chứng minh** được đã qua mặt detector của nhà cung cấp. Repo kia
  nói thẳng điều đó; spec này giữ nguyên sự thành thật ấy: báo cáo chỉ nêu **điểm mác
  AI theo luật của mình**, không tuyên bố "đã sạch".
- Watermark thống kê (nếu nhà cung cấp bật) nằm trong lựa chọn token; biên tập có mục
  tiêu sẽ gỡ ÍT hơn paraphrase toàn văn. Đây là đánh đổi CÓ CHỦ Ý: đổi một phần khả
  năng gỡ watermark lấy chất lượng kịch bản.

## 7. Kế hoạch thi công (chốt 21/08: function trong CONTENT ULTIMATE V3, kịch bản tiếng Anh)

Nơi đặt: `d:\AI AGENT OUTLIERY\apps\content-ultimate` (app 2/6, cổng 9112, đã di trú xong).
Kịch bản là **tiếng Anh** → bộ luật tiếng Anh, gác bộ tiếng Việt.

### Leo thang Ponytail — app đã có sẵn 5/8 mảnh

| Mảnh cần | Bậc dừng | Dùng cái có sẵn |
|---|---|---|
| Tách câu, đếm từ | 2 | `voiceprofile/textutils.py` — `split_sentences`, `tokenize_words` |
| Chỉ số cấu trúc | 2 | `voiceprofile/quant.py::_raw_features` — **đã đo `punct_em_dash_freq`**, `sentence_len_mean`, `sentence_len_stdev` (= burstiness), `ttr`, `flesch_reading_ease` |
| Van "không viết lại từ đầu" | 2 | `voiceprofile/generator.py::kept_ratio` — đo % câu gốc sống sót; **tốt hơn van đếm ký tự** |
| Gọi LLM | 2 | `voiceprofile/llm.py::llm_text` + `server::_llm_cfg` + `khoa_v3` (khóa từ két V3) |
| Quyền | 2 | `server::_vai_sso` / `_can_manage` |
| Quét ký tự ẩn | 6 | **1 dòng regex** `[\u200b-\u200f\u2060-\u206f\ufeff]`, KHÔNG chép 724 dòng `text_unicode.py`. Kịch bản do chính app sinh qua API → đo thật hôm 21/08 ra 0 carrier. `ponytail:` trần = không bắt homoglyph/bidi; nâng cấp = chép Layer A khi thật sự gặp ca đó |
| Bộ luật cụm sáo | 7 | Viết mới: `rules/deai_en.csv` |
| Hàm chấm điểm | 7 | Viết mới: ~60 dòng (không phải 200 như bản scratchpad — chỉ số đã có) |

### Bốn bước, mỗi bước một commit xanh

**B1 — Lõi `voiceprofile/deai.py` + `rules/deai_en.csv`** *(~60 dòng + CSV, không LLM, không UI)*
Gọi `_raw_features` lấy chỉ số, quét CSV lấy cụm sáo, trả `{diem, muc, hits[], chi_so{}}`.
→ *Verify:* `tests/test_deai.py` — kịch bản Tuvalu ra **77,6** · văn sạch ra điểm thấp ·
thêm 1 dòng CSV làm đổi điểm mà không sửa `.py` · `kept_ratio` chặn bản viết lại từ đầu.

**B2 — Nối vào server** *(~15 dòng)*
Thêm `_deai_scan(b, rd) -> (status, dict)` đúng khuôn `_sinh_titles` / `_cham_title`,
đăng ký `elif path == "/oe/api/deai-scan"`, thêm khối kết quả vào trang `/write`.
→ *Verify:* test khuôn `_H` (handler giả) như `test_lam_gon_v3.py`; smoke thật qua 9112
với vai creator; suite content không tăng fail (baseline 4 fail: 2 env Windows + 2 generator).

**B3 — Dùng thật, nuôi bộ luật** *(không code)*
Chạy trên 10 kịch bản cũ → thống kê cụm lặp → thêm dòng CSV.

**B4 — Biên tập tự động** *(CHỈ làm nếu B3 chứng minh là cần)*
`/oe/api/deai-rewrite`: chunk theo section (outline đã có sẵn ranh giới), `llm_text` với
prompt biên tập, van nhận = `kept_ratio` + bất biến + điểm giảm.
→ *Verify:* test mock `llm_text` trả nửa bài → van PHẢI chặn.

### Không làm (YAGNI)

Layer A đầy đủ · detector watermark thống kê · xử lý ảnh/PDF/C2PA · hàng đợi worker ·
UI chỉnh trọng số (sửa CSV bằng Excel) · back-translation · bộ luật tiếng Việt.

## 8. Quan hệ với author extract (voiceprofile) — chốt 21/08

### Xung đột có thật, ở hai chỗ

Cả hai module đều gọi `quant._raw_features`. Trong 14 `reproduction_targets` mà
`validate.evaluate_script()` chấm **có `punct_em_dash_freq`, `sentence_len_mean`,
`sentence_len_stdev`** — đúng những chỉ số bộ luật De-AI phạt.

1. Tác giả dùng em-dash / câu dài → `validate` nói ĐẠT, De-AI nói BỆNH. Creator không
   biết nghe ai.
2. De-AI "giải nén / phẳng câu" thành công → `sentence_len_mean` tụt → **bản sạch mác
   lại TRƯỢT validate**. Module mới phá chính chỉ số nghiệm thu của app.

### Giải: bộ chấm tách HAI NHÓM, De-AI không sở hữu thang phong cách

| Nhóm | Chấm bằng | Đụng voiceprofile |
|---|---|---|
| **A — dấu vết LLM phổ quát** (cụm sáo, ký tự ẩn, "Not just X — Y", tricolon máy) | Hằng số, luật CSV | Không — không tác giả người nào lặp đều những cụm này |
| **B — chỉ số phong cách** (em-dash, độ dài câu, TTR, Flesch) | **Gọi `validate.evaluate_script()`** | Mượn, không sở hữu. "Bệnh" = lệch giọng tác giả, KHÔNG phải "câu dài" |

Hai chế độ chạy:
- **Có profile** (kịch bản Content Ultimate): chấm A + B-neo-profile; bước viết lại dùng
  `generator.build_voice_block` (viết theo giọng tác giả) thay vì paraphrase chung chung.
- **Không profile** (tài liệu bất kỳ — yêu cầu "module riêng" của Owner): chấm A; nhóm B
  chỉ **báo cáo mô tả, không phán bệnh**. Không baseline thì không kết luận.

### Vị trí trong chuỗi: ÁP CHÓT, không phải cuối

```
S1→S5 nghiên cứu → outline (M, Q, badge) → Title + độ dài → WRITE (generator)
   → DE-AI SCAN (+ rewrite tùy chọn)  → VALIDATE (chấm lại giọng tác giả)  → xuất
```

**Van thứ 5:** bản sau De-AI chỉ được nhận nếu điểm `evaluate_script` KHÔNG TỤT.

Phát hiện kèm theo: `evaluate_script` hiện **chỉ gọi được từ `voiceprofile/cli.py`,
chưa có trong web server** — luồng web của creator chưa từng chạy bước chấm giọng. Làm
module này thì đằng nào cũng phải kéo nó lên web để làm van, nên De-AI **mang theo luôn**
phần nghiệm thu giọng mà web đang thiếu.

Chấm cuối = phát hiện muộn (21.000 ký tự viết xong mới biết đầy em-dash). Không vì thế mà
nhét vào đường sinh đang chạy ổn: module nhận **một chương** cũng như nhận cả kịch bản —
SOP bước 7 vốn đã duyệt từng chương, dán chương vào scan là xong, không thêm dòng code nào.

**Model viết lại phải KHÁC model đã viết kịch bản** (chống re-stamp) → tham số riêng của
module, không dùng lại `_llm_cfg` mặc định.

---

## 9. THI CÔNG 21/08/2026 — B1 + B2 ĐÃ DỰNG (kèm 3 điều chỉnh so với mục 7-8)

### 9.1. Trả lời câu hỏi treo: `evaluate_script` lên web — CÓ, nhưng đổi vai

Câu hỏi đặt ra là *"kéo `evaluate_script` lên web có trong phạm vi không, để van thứ 5
hoạt động thật?"*. **Có** — nhưng **van thứ 5 KHÔNG bật ngay**, vì một dữ kiện chưa biết
lúc đặt câu hỏi:

> Đo 21/08 trên 9 hồ sơ trong kho: **A003 · A008 · A011 có `sentence_len_mean = 1085`**
> (dấu vân tay transcript chưa dọn dấu câu). `reproduction_targets` của chúng vô nghĩa.
> Bật van *"điểm evaluate_script không được tụt"* trên hồ sơ đó = **van chạy trên số rác**:
> bản De-AI làm tốt (câu ngắn lại, nhịp đa dạng hơn) sẽ bị đánh trượt, bản vụn có thể lọt.

Nên `cham_giong()` có **CỬA**: hồ sơ không `do_duoc` → trả `khong_du_co_so` kèm lý do,
**không phán số**. Van chặn thật bật sau khi hồ sơ được dựng lại (mạch C3 của
`apps/content-ultimate/PROPOSAL-V3-ban2-CUU-CHAT-LUONG-VIET.md`).

### 9.2. Ba nhóm TÁCH BẠCH thay cho một điểm mác AI

Mục 8 đã chốt tách nhóm A/B; bản thi công tách thành **ba** và bỏ điểm tổng:

| Nhóm | Đo gì | Chuẩn đối chiếu |
|---|---|---|
| **A · dấu vết máy** | cụm sáo (CSV) · ký tự vô hình · **mật độ em-dash/1000 từ** | hằng số — không tác giả nào lặp đều những cụm này |
| **B · nhịp** | từ/câu · %câu cụt · %câu dài · biến thiên | **exemplar của chính hồ sơ**; hồ sơ hỏng → chỉ MÔ TẢ, không phán bệnh |
| **C · bám giọng** | `validate.evaluate_script` | `reproduction_targets`, có cửa chặn ở 9.1 |

**Không có "điểm mác AI 0-100"** — thay bằng **mật độ trên 1000 từ**, vì mật độ so sánh
được giữa các bản còn điểm tổng thì không ai kiểm chứng được (cùng lớp lỗi với bảng điểm
ở Phụ lục C của proposal V3 bản 1: sai số học cả 3 dòng mà không ai phát hiện).

### 9.3. Một ngưỡng đã THỬ VÀ BỊ BÁC — đừng thêm lại

Định dùng `burstiness_cv < 0.70` làm cờ "câu đều tăm tắp = máy" (bản máy đo được
0,51-0,67). **Đo lại chính exemplar NGƯỜI viết: 0,36 - 0,60** (A004 0,36 · A013 0,42 ·
A012 0,51 · A011 0,60) — mẫu ngắn liền mạch thì phương sai vốn thấp, so cv của mẫu ngắn
với bài dài là so hai thứ khác nhau. Đã gỡ; cv vẫn **báo cáo như số mô tả**, không dùng
phán bệnh. Có test ghim `test_khong_co_nguong_cv_tuyet_doi`.

### 9.4. Số đo thật lúc nghiệm thu (21/08)

| Bản | em-dash/1000 từ | từ/câu | % câu cụt | bám giọng |
|---|---|---|---|---|
| Exemplar NGƯỜI (4 hồ sơ) | **0,00** | 12-29 | 8-23% | — |
| Bản thật A013 07/08 | **17,4** | 14,0 (exemplar 20,9) | 38,0% (exemplar 8,3%) | **18%** |
| Bản thật A011 07/08 | **13,5** | 21,8 | 13,3% | hồ sơ hỏng → không chấm |
| Bản thật A012 04/08 | 1,3 | 9,1 (exemplar 12,2) | **54,5%** | **0%** |
| Tuvalu ch1 sau De-AI tay | **18,8** | 19,2 | 24,1% | hồ sơ hỏng → không chấm |

Hai kết luận rút ra: (1) **em-dash là dấu vân tay máy mạnh nhất trong bối cảnh này** —
văn người 0,00/1000 trong khi bản máy 13-17/1000; (2) bản Tuvalu "đã xử lý" **vẫn 18,8
em-dash/1000** → khâu biên tập tay chưa gỡ em-dash, và luật PACING hiện cho phép
*"at most one em-dash per paragraph"* nên 40 đoạn = 40 em-dash vẫn **đúng luật**.
Sửa một dòng prompt ở nguồn rẻ hơn gỡ bằng LLM hậu kỳ cho mỗi bài.

### 9.5. Đã dựng những gì

| Thành phần | File | Ghi chú |
|---|---|---|
| Soi hồ sơ giọng | `src/voiceprofile/soi_ho_so.py` | 2 câu hỏi tách bạch: `do_duoc` (tin được số đo) vs `neo_du` (neo đủ dày); bắt trùng lặp exemplar bằng shingle 8 từ |
| Bộ chấm 3 nhóm | `src/voiceprofile/deai.py` | 0 LLM, 0 đồng |
| Luật ngoài code | `rules/deai_en.csv` | 21 dòng khởi đầu; thêm cụm = thêm dòng Excel |
| API | `POST /api/kiem-chung` · `GET /api/soi-ho-so` | chỉ nhận **mã tác giả**, không nhận đường dẫn từ client |
| Giao diện | tab Writing: nút 🔍 Kiểm chứng + bảng 3 nhóm + cảnh báo hồ sơ hỏng ngay khi chọn tác giả | chỉ báo, không chặn xuất bản (A3) |
| **Cửa chặn corpus thô** | `POST /api/build` trả 409 `corpus_transcript_tho` | cảnh báo suông từ 16/07 đã bị bỏ qua 100% → nay chặn một lần, user tick xác nhận thì đi tiếp |

Test: `tests/test_deai.py` **31 ca**. Suite content **282 pass / 4 fail** — đúng baseline
cũ (2 lỗi môi trường Windows + 2 baseline `test_generator`), **không tăng fail**.
Smoke thật: server tạm cổng 8799 + `CU_DATA_DIR` tạm — `/write` render đủ id mới,
2 API trả đúng, lỗi trả 400 không phải 500.

### 9.6. Còn lại của mạch này

- **B3 nuôi bộ luật**: bộ CSV khởi đầu chỉ bắt 0-2 cụm/bài trên văn du lịch thật — cần
  chạy trên 10 kịch bản cũ, thống kê cụm lặp, thêm dòng. (Hiện em-dash gánh phần lớn tín hiệu.)
- **B4 rewrite tự động**: chỉ làm nếu B3 chứng minh là cần.
- **Siết luật em-dash trong PACING** (`generator.py` ~dòng 177) — việc rẻ, đo lại được
  ngay bằng chính bộ vừa dựng.
- Van thứ 5 (chặn theo `evaluate_script`) — bật sau C3.
