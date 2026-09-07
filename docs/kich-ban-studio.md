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

## 10. ĐỢT 1 — 22/08/2026 (đo trước, sửa sau; suite 288 pass / 0 fail)

**Bối cảnh đổi**: sổ ghi "team ngừng dùng từ 07/08" đã hết đúng — **22/08 namtn quay lại**,
tạo hồ sơ mới A014_Amazing (11:59) rồi viết một kịch bản (12:19, 21.863/23.000 ký tự,
19,8 phút). Bản mới **vẫn mắc đúng bệnh**: 46,6% câu cụt (exemplar 23,8%), em-dash
16,63/1000, 12,3 từ/câu. Đồng hồ "team dùng lại đều 2 tuần" (điều kiện bật V3 research
layer) bắt đầu chạy từ 22/08.

### 10.1. Em-dash: chẩn đoán ĐỔI sau khi đo (commit `425f4d8`)

Đề xuất ban đầu là *siết luật PACING*. Đo trước khi sửa cho kết quả khác:

| Bằng chứng | Số |
|---|---|
| Model có tuân "tối đa 1 em-dash/đoạn" không? | **KHÔNG** — 26–59% đoạn có ≥2 (A013 1,59/đoạn · A014 1,33 · A011 1,47) |
| Khối `_v2_section_block` (PACING…) | **28,6 em-dash/1000 từ** |
| Cả prompt chương | **11,2/1000** |
| Bản model viết ra | 13–17/1000 |
| Corpus NGƯỜI của chính tác giả | **0,00–1,30/1000** |

⇒ Model **sao lại mật độ của vật liệu dạy**, không tuân câu lệnh. Siết chữ luật sẽ không
ăn. Đã gỡ em-dash khỏi **25 chuỗi prompt** tiếng Anh trong `generator.py`.
**Không đụng**: regex nhận diện mốc (`_SECTION_MARK`/`_IDEA_SEG`), thông báo tiếng Việt
cho UI, và **exemplar của tác giả** (dữ liệu — tác giả dùng em-dash thật thì giữ).
Kiểm chứng: gọi thẳng 6 hàm `build_*_prompt` trước/sau → em-dash 15/9/12/2/10/9 → **0
hết**, và so khớp **từng từ**: không đổi một từ nào, chỉ đổi dấu. Test ghim
`test_prompt_khong_chua_em_dash_22_08`.

*(MASTER §11 ghi luật này từng đo ra "em-dash 2,9 → 0/1000". Số đó đúng ở thí nghiệm
tay hồi 26/07 nhưng KHÔNG còn đúng trên bài đầy đủ: luật cho phép 1/đoạn nên ~40 đoạn =
~11/1000 vẫn "đúng luật", chưa kể model vượt luật.)*

### 10.2. B3 nuôi bộ luật: ĐO XONG → **không thêm dòng nào** (kết luận, không phải bỏ dở)

Khai thác n-gram trên **260k từ văn máy (59 bài) vs 148k từ văn người (722 đoạn)**:

- Khai thác mù chỉ ra cụm tiếng Anh phổ thông (`one of the`, `in the world`) — có mặt cả
  ở văn người, không phải dấu vết máy.
- Đo có định hướng 19 khuôn tu từ máy đã biết: **0 khuôn đạt ngưỡng** (≥5 tác giả, ≥15 lần,
  ≥4× văn người).
- Các ứng viên mạnh nhất (`refuses to` 90 lần · `if you walk/stand/spend` 142 · `not simply`
  81 · `this is not just` 54 · `woven into` 28) **dồn gần như toàn bộ vào A003_Ventures**
  (78/90 · 88/142 · 66/81 · 42/54 · 26/28). A003 chính là hồ sơ **neo hỏng** (corpus 1085
  từ/câu, exemplar là cục transcript thô 27k ký tự).

⇒ Đây là **register mặc định của GLM khi neo giọng hỏng**, không phải bệnh chung. Thêm vào
CSV sẽ đánh oan tác giả khác. Giữ nguyên 21 luật. Hiệu lực bộ luật hiện tại đo được: trung
vị **2 hit/bài**, 18/59 bài **0 hit**; 47/59 bài xếp mức "nặng" **gần như hoàn toàn do
em-dash** (trung vị 11,0/1000). ⇒ **B4 rewrite tự động vẫn chưa cần** — tín hiệu thật nằm
ở em-dash (đã xử) và nhịp (C3), không nằm ở cụm sáo.

### 10.3. Ghi lý do lỗi vào sổ (commit `7f9e3b6`)

`history.jsonl` có 10/53 lượt hỏng, trong đó **4 lượt writer `error: None`** — không truy
được nguyên nhân. Gốc: `_run_cli` khi bước CLI thất bại chỉ ghi vào **log tiến trình sống
trong RAM**, không set `job["error"]`, mà `_finish_job` chỉ chép vào sổ khi trường đó có
giá trị. Nay giữ 8 dòng cuối của CLI, thất bại thì ghi tên bước + mã thoát + 3 dòng cuối.
*(2 lượt extractor hỏng còn lại là rác VPS Linux: `Permission denied: /tmp/...`; 4 lượt là
người tự hủy. Chờ 12–40 phút thì đo ra tỉ lệ thuận độ dài: trung vị 18,1 phút, bài 51k ký
tự mất 39,9 phút — chậm chứ không treo.)*

### 10.4. Dọn 4 test đỏ baseline → suite xanh thật (commit `8acdb80`)

Hai cái là **bug thật trên Windows** (sửa code, không sửa test cho xanh): `_history_files`
cắt đuôi bằng `Path` làm đổi `/` thành `\` nên bản ghi di sản VPS trong sổ không bao giờ
khớp đường dẫn client gửi → nút tải outline 404 oan; `_save_cookies` dùng `os.replace` lên
file mang cờ chỉ-đọc bị Windows từ chối trong khi POSIX chỉ cần quyền ghi thư mục. Hai cái
là **test lệch pha** với quyết định đã chốt (DEPTH PLAN lấy `min(ngân sách, số ý có thật)`;
cảnh báo "chương nhiều ý quá" đã gỡ có chủ đích khi chuyển từ CẮT Ý sang PHÂN TẦNG ĐỘ SÂU
14/07).

### 10.5. Việc lộ ra, chưa làm

- ⚠ **Bom hẹn giờ kho hồ sơ**: `library/index.json` lưu **đường dẫn tuyệt đối**. A001–A010
  trỏ `/opt/content-ultimate/…` (VPS, đã mất) nên app **chỉ thấy 4/10 hồ sơ**; A011/A012/A013
  trỏ `C:\OutlierY\…` — hệ V2 **đã tắt 22/08 và sẽ xóa ~22/09**. Đến ngày đó ba hồ sơ team
  dùng nhiều nhất tháng 8 sẽ biến mất khỏi app. Cần di trú (chép hồ sơ + corpus sang
  `data/content-ultimate`, cập nhật index) **trước 22/09**, có backup trước.
- **Nghiệm thu thật Đợt 1**: chạy 1 chương bằng LLM, đo em-dash bản ra so với 13–17/1000
  trước đây. Tốn tiền (~600–800đ/kịch bản) nên chờ Owner duyệt.
- Bẫy vận hành tái xác nhận: khởi động tay app V3 **phải đủ bộ env của `start-all.ps1`** —
  thiếu `CU_DATA_DIR` thì `/api/soi-ho-so` trả rỗng dù kho có hồ sơ.

## 11. DI TRÚ SỔ TÁC GIẢ + ĐỢT 2 (C3b) — 22/08/2026 (295 pass / 0 fail)

### 11.1. Di trú sổ đăng ký (commit `fdad6d1`)

`library/index.json` lưu **đường dẫn tuyệt đối**. Qua hai lần đổi máy (VPS `/opt` → ổ C
hệ V2 → ổ D hệ V3) thì 10/14 entry trỏ vào chỗ không còn ⇒ **app chỉ thấy 4/12 hồ sơ**,
dù file vẫn nằm nguyên trong kho V3. Nặng hơn: A011/A012/A013 còn trỏ vào ổ C — hệ V2 đã
tắt 22/08 và sẽ xóa ~22/09, tức 3 hồ sơ team dùng nhiều nhất tháng 8 sắp biến mất.

Sửa **gốc**, không chỉ vá dữ liệu: `duong_that()` giải đường dẫn với luật **kho hiện tại
là nguồn sự thật** — thử ghép 3 rồi 2 đoạn đuôi vào `CU_DATA_DIR` TRƯỚC, kể cả khi đường
cũ còn sống; `duong_luu()` ghi vào sổ bằng đường tương đối. Bẫy đã bắt: đường POSIX di sản
(`/opt/...`) trên Windows **không tính là absolute** nên nhánh cũ không bao giờ chạm tới.
Đã ghi lại index (24 trường, nguyên tử, backup `data/backup/index.json.truoc-di-tru-20260822`).
A005/A006 (rác thử nghiệm `/tmp/vfy2`) **giữ trong sổ**, `list_authors` tự lọc — không xóa
dữ liệu của user. Nghiệm thu qua API thật: 4 → **12 hồ sơ**; UI nhận **12/12 corpus tồn tại**.

### 11.2. C3b — neo giọng dày và ĐÚNG NHỊP (commit `d32915e`)

Module mới `src/voiceprofile/chon_neo.py`, **0 LLM, 0 token, tất định**: cắt corpus thành
khối 60–400 từ ở ranh đoạn → loại khối/file thiếu dấu câu → chọn **tham lam sao cho nhịp
gộp (từ/câu · %câu cụt · %câu dài) gần corpus nhất** → dừng ở ~1.800 từ → loại khối trùng
bằng shingle 8 từ. Nối vào luồng: `build_voice_block` lấy theo **tổng từ** (`TRAN_TU_NEO`)
thay vì đếm 3 mẫu; CLI `write` khi có `--author-dir` thì nạp neo dày, **chỉ đổi biến trong
bộ nhớ, không ghi đè `profile.json`** (bài học 16/07: dựng lại hồ sơ từ transcript đã bị
user bác). Đường web đã sẵn: frontend gửi `author_dir: a.corpus`.

**Đo trên 12 hồ sơ thật — 12/12 khớp nhịp corpus tốt hơn:**

| | neo cũ | neo mới |
|---|---|---|
| Độ dày | 200–330 từ (A003: 4.403 từ transcript thô) | **1.832–2.064 từ** |
| Lệch nhịp so corpus | 0,36 – **65,35** | **0,01 – 0,07** |

Ca rõ nhất là Carl Sagan: 3 mẫu cũ đo 30,2 từ/câu · 0% cụt · 36,4% dài, trong khi corpus
thật là 18,0 · 21,4 · 8,5 — **mẫu cũ lệch hoàn toàn**; neo mới 18,0 · 21,4 · 8,7.

**Phát hiện phụ quan trọng**: ba hồ sơ "hỏng" (A003/A008/A011) có corpus **3/5 file lành**,
chỉ 2 file là transcript thô — exemplar cũ vô tình lấy từ 2 file thô đó. Module tự bỏ 2 file
và dùng 3 file lành (lệch 65,35 → 0,03). Kèm bẫy đã bắt: **lọc theo từng file, không đo gộp**
— corpus A003 đo gộp ra 9,3 dấu kết/1000 (qua ngưỡng) trong khi 2 file thật sự là 0,1.

Khối neo mới có **0 em-dash** (văn tác giả vốn không dùng) — cộng hưởng với Đợt 1.

### 11.3. Còn lại

- **Nghiệm thu thật cả Đợt 1 + Đợt 2**: chạy 1 chương bằng LLM, đo em-dash/1000 và % câu
  cụt so mốc cũ, rồi **người đọc chốt**. Cổng cuối cùng là người, không phải số.
- B3 đã đo xong và kết luận không thêm luật (mục 10.2). Van thứ 5 vẫn chờ sau nghiệm thu.

### 11.4. NGHIỆM THU THẬT — 22/08/2026 (glm-5.2, cùng outline Uzbekistan của bản team 22/08)

Ba nhánh, chỉ tốn 2 lượt gọi model (nhánh A đã có sẵn là bản team viết 22/08):

**Cấp chương (522 từ, tách hiệu ứng từng đợt):**

| nhánh | em-dash/1k | từ/câu | %cụt | bám giọng |
|---|---|---|---|---|
| A. prompt cũ + neo cũ | 15,09 | 9,1 | 58,6 | 29% |
| B. prompt MỚI + neo cũ | **6,11** | 9,6 | 52,9 | 43% |
| C. prompt MỚI + neo DÀY | 19,42 | 17,2 | 40,0 | 71% |

⇒ **Đợt 1 ăn, đo sạch**: A và B cùng nhịp câu (9,1 vs 9,6 từ/câu) nên so được trực tiếp —
em-dash **giảm 59%** chỉ nhờ gỡ em-dash khỏi prompt. Giả thuyết "model sao lại mật độ của
vật liệu dạy" được xác nhận bằng số.

**Cả bài, 5 chương (1.544–1.567 từ — mẫu gấp 3):**

| chỉ số | A (cũ) | C (mới) | văn người |
|---|---|---|---|
| em-dash/1.000 từ | 18,04 | **9,80** (−46%) | 0,04 |
| câu cụt | 45,9% | **37,5%** (−8,4 điểm) | 29,5% |
| từ/câu | 11,7 | **12,8** | 13,2 |
| lệch nhịp so corpus | 0,93 | **0,44** (−53%) | 0 |
| bám giọng (7 chỉ số) | 86% | **57%** ⚠ | — |

**Bám giọng tụt — soi từng chỉ số** thay vì bỏ qua: C trượt đúng hai target
`function_word_freq` (0,364 vs khoảng 0,309–0,345) và `punct_freq_total` (0,072 vs
0,074–0,096). Cả hai là **hệ quả trực tiếp của câu dài hơn và ít em-dash hơn** — tức chính
hai thứ đợt này nhắm tới. Đáng chú ý: `punct_freq_total` của hồ sơ **đếm cả em-dash**, nên
bản sạch em-dash bị thước giọng đánh trượt, dù em-dash là dấu vân tay máy. Hai thước mâu
thuẫn nhau ở đúng điểm này. (`ttr` cả hai bản đều trượt, nhưng C gần đích hơn: 0,413 vs 0,432.)

**Truy nguồn em-dash của nhánh C** (thay vì đoán): neo dày đo ra **0 em-dash**, corpus tác
giả 0,04/1000 ⇒ em-dash KHÔNG đến từ neo. Nó **tương quan với độ dài câu**: nhánh B viết câu
ngắn (9,6 từ) ra 6,11; nhánh C câu dài (17,2 từ) ra 19,42. Đây là register mặc định của GLM
khi nối mệnh đề trong câu dài. Bản cả bài (12,8 từ/câu) ra 9,80 — vẫn trên ngưỡng "nặng" 8,0.

**Sự cố giữa chừng**: chạy tới chương 6 thì **tài khoản GLM hết tiền** (app nhận diện đúng,
không nhầm với nghẽn tốc độ — bài học "z.ai dùng 429 cho cả hai" vẫn giữ). Bản C dừng ở
chương 5; đã so cùng phạm vi 5 chương của bản A cho công bằng.

**Cổng cuối là người**: bản đọc song song 5 chương ở artifact `59bc7dd6`, file gốc tại
`scratchpad/nghiemthu/C_full_neo_day.md`. Chưa có kết luận cuối cho tới khi Owner đọc.

## 12. ĐỢT 3 + A/B MODEL — 23/08/2026

### 12.1. Ba việc của Đợt 3 (commit `fcc3c58`, suite 310 pass)

**Ngân sách ĐỘNG TÁC, không đếm ký tự.** Đo 210.760 từ văn NGƯỜI làm đối chứng:
`Not X.` gấp **55 lần**, `Here is what` gấp 51, `Then there is` gấp 23, `But here is` gấp 18.
Và bằng chứng quyết định: chặn em-dash ở Đợt 1 thì `Here is what` **0 → 3**, `Then there is`
**0 → 2** — năng lượng chui sang cách thực hiện khác của **cùng một động tác tu từ**. Thêm 4
luật vào `rules/deai_en.csv` (luật ngoài code) + chỉ số `dong_tac_tren_1000_tu`.

**Vòng sửa ở CẤP CÂU** (`src/voiceprofile/sua_cau.py`). Chặn bằng LỜI không ăn (luật "tối đa
một em-dash mỗi đoạn" bị vi phạm 26–59%), nên đo bằng MÁY sau khi sinh. Sửa từng câu chứ
không viết lại cả chương — vì đợt trước viết lại từ đầu làm rơi "hai nghìn tấn vàng", rơi tên
Ulugh Beg và đẻ ra lỗi Afghanistan. **Van**: mọi con số và tên riêng phải còn nguyên, độ dài
chênh ≤35%, và ở cấp chương mật độ số/tên riêng **không được giảm**. Đo thật trên Uzbekistan:
động tác **30,19 → 0,00**/1000; tên riêng **21 → 26** (dày hơn, không loãng).

**Hook thành mô-đun riêng** (`src/voiceprofile/hook.py`): sinh 3 phương án, MÁY chấm 4 luật,
chọn bản đạt nhiều nhất. Hook dùng chung công thức với chương nên nó không bao giờ tốt lên —
Đợt 22/08 làm thân bài tốt lên nhưng hook **xấu đi** (gọi tên chủ đề ngay câu đầu = đóng vòng
lặp trước khi mở).

### 12.2. Bug: lỗi ở bước hậu xử lý làm MẤT bản nháp (commit `88505fc`)

Phần Kết bài Kristin Nelson **đã viết ra 2.907 ký tự**, rồi vòng cắt gọi API dính
`contentFilter` của GLM (mã 1301, "nội dung nhạy cảm") → ngoại lệ bay lên runner, bài chỉ lưu
2 phần. Trả tiền cho 2.907 ký tự rồi mất trắng. Van cũ chỉ bảo vệ trường hợp bản sửa **tệ
hơn**, không bảo vệ trường hợp lời gọi **ném lỗi**. Nay bọc cả vòng cắt lẫn vòng nở: hỏng thì
giữ bản nháp, ghi lý do, đi tiếp. Thân phần đã sinh là TÀI SẢN; cắt/nở chỉ là CẢI THIỆN.

⚠ **Phát hiện vận hành kèm theo**: GLM có thể **từ chối viết** chủ đề chuyện đời (hôn nhân
tuổi teen, cái chết). Hồ sơ A012 Old-story chuyên loại này ⇒ cả một nhánh nội dung của team có
nguy cơ dính. Chưa đủ dữ liệu để kết luận là do chủ đề hay do lượt gọi cụ thể.

### 12.3. A/B MODEL — trả lời câu hỏi treo từ 26/07

Bài **Kristin Nelson** (hồ sơ A012, thể loại chuyện đời) chọn có chủ đích vì **bệnh khác** bài
Uzbekistan: bản cũ ở đây gần như sạch động tác máy (2,11/1000) nhưng **vụn nặng** (7,7 từ/câu,
58,1% câu cụt). Và đích **ngược chiều**: tác giả A012 vốn viết câu ngắn (corpus 10,6 từ/câu,
36,5% cụt), nên phép thử là neo có biết **dừng đúng nhịp tác giả** thay vì kéo dài như bài kia.

| chương 1 | từ/câu | % cụt | lệch nhịp |
|---|---|---|---|
| văn NGƯỜI (đích) | 10,6 | 36,5 | 0 |
| A. team 04/08, glm-5.2, chưa sửa | 7,7 | 58,1 | 1,19 |
| E. đã sửa + **glm-5.2** | 8,0 | 55,4 | **1,11** |
| F. đã sửa + **glm-5.3** | **10,4** | **35,7** | **0,01** |

⇒ **Với glm-5.2 cách sửa gần như KHÔNG ăn ở bài này** (nhích 0,3 từ/câu), dù neo đã rút đúng
2.039 từ nhịp 10,6 khớp y hệt corpus. **Cùng cái neo đó, glm-5.3 trúng đích gần như hoàn hảo.**

Đây là câu trả lời cho §11 Master Brief *"nhịp ngắn-vụn là register của GLM dưới stack prompt
này"*: **đúng với 5.2, và 5.3 đã thoát khỏi nó**. Neo giọng đúng chỉ có tác dụng khi model chịu
nghe theo neo.

**Điểm chưa giải thích được (không giấu)**: ở bài Uzbekistan chính glm-5.2 lại kéo nhịp 9,1 →
14,0. Tức 5.2 viết **dài hơn** đích ở bài tả cảnh nhưng **ngắn hơn** đích ở bài kể chuyện đời —
nó bị **thể loại** chi phối mạnh hơn neo, còn 5.3 thì bám neo. Muốn chắc phải chạy 5.3 cho cả
bài Uzbekistan.

Hook cả hai model đều đạt: mở bằng nghịch lý, không gọi tên nhân vật ở câu đầu. Mô-đun chấm 3
phương án ra 3/4 · 3/4 · 2/4 rồi chọn bản cao nhất.

## 13. SÁU BƯỚC ĐÊM 23/08 — làm tuần tự, mỗi bước xanh mới sang bước sau

Owner chốt danh sách trước khi đi ngủ, yêu cầu bám sát và không bỏ bước. Mỗi bước một
commit riêng, test viết TRƯỚC, đo lại trên dữ liệu thật. Suite **330 pass / 0 fail**.

| bước | việc | commit |
|---|---|---|
| 1 | Sửa thước bám giọng | `029b866` |
| 2 | Ngôn ngữ bài viết theo outline | `20da894` |
| 3 | Cửa nhập tự loại file hỏng | `24107bb` |
| 4 | Lõi viết từng chương | `52c90d7` |
| 5 | Giao diện viết từng chương | `1559657` |
| 6 | Dựng lại chỉ số giọng corpus Ventures | `1ab1290` |

**B1 — thước đang đếm dấu vân tay máy vào điểm giọng.** Bỏ `punct_freq_total` (nó là tổng
dấu câu trên ký tự và **em-dash được tính vào đó**, nên bản sạch em-dash bị chấm là kém
giống tác giả — đúng chỗ làm điểm tụt 86% → 57%). Bỏ luôn điểm tổng phần trăm, trả từng
chỉ số. Và chuẩn **nhịp** lấy từ corpus tác giả thay vì ba đoạn mẫu chọn lệch — cho thước
dùng **cùng nguồn với prompt**. Đo thật: chuẩn đổi từ 13,0/23,8% (exemplar) sang 13,6/27,5%
(corpus). *Ponytail: chỉ đo nhịp trên văn lành, không gọi cả thuật toán chọn neo cho một
con số.*

**B2 — hiện trạng đáng lo hơn tưởng**: generator **không có một dòng nào xử lý ngôn ngữ**,
chữ `language` xuất hiện 0 lần và `output_language` chưa bao giờ được đọc. Bài ra tiếng Anh
hoàn toàn nhờ may. Nay lệnh ngôn ngữ chèn cho **cả hook, chương và kết**; với tiếng Anh khối
lệnh RỖNG nên bài hiện có không đổi một byte (có test hồi quy). Kèm **cảnh báo khi giọng
khác ngôn ngữ bài**: nhịp câu tiếng Anh không áp được cho bài tiếng Việt, im lặng chấm điểm
trong ca đó là cho ra số rác.

**B3 — cửa nhập tự loại thay vì cho tick bỏ qua.** Cảnh báo suông có từ 16/07 bị bỏ qua
100%; cửa chặn 21/08 cho tick đi tiếp và **đã có người tick** — đó là gốc của ba hồ sơ hỏng.
Nay tự loại file dưới ngưỡng rồi báo rõ đã loại gì. Loại hết thì báo lỗi chứ không trả
corpus rỗng. Kiểm thật: Ventures giữ 3 file / 14.252 từ, bỏ đúng 2 file transcript thô.

**B4 — lõi viết từng chương.** Tái dùng toàn bộ `done_sections` / `on_section_done` /
checkpoint; diff chỉ là `chi_phan` và `gop_y`. **Bug bắt được lúc nghiệm thu chứ không phải
lúc chạy test**: bản trước nằm trong `done_sections` nên vòng lặp coi phần đó "đã xong" và
bỏ qua — bấm *viết lại* mà không có gì xảy ra. Đã trừ `chi_phan` ra và thêm test phủ đúng
đường đó.

**B5 — giao diện** theo mockup vòng 4: hai chế độ, cột trái danh sách phần, hàng chip đo đặt
cạnh **số của chính tác giả**, khối duyệt có ô góp ý và ba góp ý bấm nhanh. Không route mới:
nội dung từng phần đọc qua `/api/download` sẵn có. Màn thứ hai (chọn chương, nút lưu)
**không làm** — Owner chốt chuyển sang module khác. Minimalist icon: khối mới không dùng
một emoji nào; test emoji **chỉ quét khối mới** vì dọn cả app là "tiện tay sửa".

**B6 — dựng lại chỉ số giọng, 0 token.** Khác thí nghiệm 16/07 đã bị Owner bác ở chỗ dữ liệu
vào **đã lọc**. Kết quả: chỉ số giọng **3 → 8**, từ mỗi câu **1085 → 13,4**. **Không ghi đè**:
ghi ra `profile.moi.json` cạnh bản cũ, backup riêng ở
`data/backup/profiles-truoc-b6-20260823`.

### Việc để lại cho Owner sáng 24/08

**Kiểm chứng mù**: hai bản của cùng một chương, một bản hồ sơ cũ một bản hồ sơ mới, **không
ghi bản nào là bản nào**. Luật A1 cấm tự kết luận bằng văn do chính hệ thống sinh ra, nên
quyết định dùng hồ sơ nào là của Owner.

### 13.1. Bẫy vận hành lộ ra khi chạy kiểm chứng mù (23/08, ~03:30)

**glm-5.3 là model reasoning nên hay đốt hết ngân sách token ở các vòng phụ.** Hai bản chạy
thử đều dính, ở hai chỗ khác nhau:

- bản dùng hồ sơ cũ: **vòng CẮT** phần Kết trả về rỗng (`finish_reason=length`, đã thử tới
  16.384 token) ⇒ Kết giữ nguyên 2.641 ký tự thay vì về khuôn 700.
- bản dùng hồ sơ mới: **vòng NỞ** chương 1 trả về rỗng (đã thử tới 37.500 token) ⇒ chương
  giữ nguyên 1.537 ký tự thay vì kéo lên 3.125.

⇒ **Bản vá "giữ bản nháp khi bước hậu xử lý lỗi" (`88505fc`) làm đúng việc ở CẢ HAI ca**:
không mất một chữ nào đã trả tiền. Nhưng hệ quả là hai bản lệch độ dài (6.271 so với 2.756
ký tự) nên **không so tổng thể được** — chênh lệch đó là do lỗi kỹ thuật, không phải do hồ sơ.

So riêng chương 1 thì hai hồ sơ cho kết quả **gần như nhau**: 17,3 so với 16,9 từ mỗi câu
(đích của corpus là 14,0), câu cụt 20,0% so với 18,8% (đích 15,8%), và **cả hai đều sạch
động tác máy (0,0/1000)**. Chênh lệch quá nhỏ để kết luận trên một mẫu.

**Việc còn lại**: ngân sách token của vòng **nở** vẫn tính theo `target × 3` như cũ; vòng
**cắt** đã sửa để tính theo độ dài bản nháp đầu vào. Nhưng log cho thấy có cơ chế tự nâng
tới 37.500 mà vẫn không đủ, nên đây là giới hạn của model chứ không chỉ là con số cấu hình.
Cần đo riêng trước khi nâng tiếp.

## 14. AUTHOR EXTRACT — NĂM CẢI TIẾN C1→C5 + BÁO CÁO (24/08/2026)

Owner đưa một bản đánh giá của Grok về bài toán "trích xuất giọng văn → cấu trúc hóa →
cho AI viết tương đồng" và duyệt làm cả năm cải tiến. Đánh giá đó mô tả đúng bài toán
nhưng không biết hệ đã ở đâu: **Phase 1 và phần lớn Phase 2 trong roadmap của nó đã xong
từ tháng 7**, và ở vài chỗ app đi xa hơn (exemplar chọn theo nhịp corpus; mọi trích dẫn
của LLM bị Python đối chiếu verbatim). Ba khuyến nghị phải bác, có bằng chứng tại chỗ:

| Grok đề xuất | Vì sao không làm |
|---|---|
| LoRA / fine-tune (mức 3–4) | Corpus thật của kho là **3.726 – 25.392 từ** mỗi tác giả; bảng của chính Grok đòi ≥50.000. Và bằng chứng 23/08: cùng bộ neo, đổi 5.2 → 5.3 kéo lệch nhịp 1,11 → 0,01. Đòn bẩy nằm ở **model + neo**, không ở trọng số |
| "Trích thành cấu trúc rồi nhét vào AI" | Chính là cái bẫy hệ đã sập: `reproduction_targets` tính từ tháng 7 và **chưa bao giờ vào prompt** (xem C3) |
| Style embedding bằng mạng nơ-ron | Burrows's Delta cho phần lớn giá trị với 0 hạ tầng, và **giải thích được** (chỉ ra đúng hư từ nào lệch) — luật của app là mọi con số phải truy nguyên được |

Đo đếm mở đầu (đây là chẩn đoán, không phải cảm tính): `profile.json` có **8 trường**,
`generator.py` đọc đúng **hai** (`exemplars`, `signature_moves`, cộng `output_language`
mới thêm 23/08). Chữ `sentence_len` xuất hiện **0 lần** trong toàn bộ generator.

### 14.1. Hai lỗi thống kê chưa ai bắt (C1 + C2)

**Cửa ổn định chạy ngược với corpus mỏng.** A013 Derek Muller (1 file / 3.726 từ) cắt ra
**đúng một** đơn vị đo → `spread = 0.0` ở mọi đặc trưng → `cv = 0` → giữ **17/17** và mọi
`sd = 0.0`. Trong khi A014 (25.392 từ, 6 file) chỉ giữ 7/17 vì có phương sai thật để đo.
Hồ sơ mỏng nhất kho lại tự khai là chắc chắn nhất: "không có phương sai" bị đọc thành
"phương sai bằng 0" = chắc chắn tuyệt đối. Sửa: đơn vị đo **co giãn** theo corpus (nhắm
`MIN_DON_VI_DO + 1` = 4 đơn vị, vì một đơn vị đi làm held-out), dưới 3 điểm đo thì
`keep=False` + `sd=None` + `do_duoc=False`, và `evaluate_script` **bỏ qua** target
`do_duoc=False` — trước đây `sd=0.0` bị đọc thành band 5%, biến thứ chưa đo được thành
tiêu chuẩn chặt nhất bảng.

| | A013 | A002 | A007/A012 | A010 |
|---|---|---|---|---|
| điểm đo | 1 → **4** | 1 → **14** | 2 → **4** | 2 → **4** |
| chỉ số giữ | 17 → 6 | 16 → 6 | 10 → 5 | 9 → 8 |
| `sd = 0` giả | 17 → **0** | 16 → **0** | 1 → 0 | 0 |

**Chiều quan trọng nhất bị chính cửa đó loại.** A014 có `sentence_len_mean` `keep=False`
(cv cao qua 6 văn bản). Mà `select_exemplars` chỉ nhìn tập `keep=True` → nó chọn đoạn mẫu
bằng hư từ và TTR, **không nhìn nhịp câu**. Đây là gốc của bảng 22/08 (mẫu neo A013 33,3%
câu dài trong khi văn thật 9,3%): `chon_neo` đã vá triệu chứng ở đường viết, nhưng
`profile.json` vẫn giữ nguyên lỗi. cv cao ở nhịp **không phải nhiễu** — nó là đặc điểm của
người viết. Sửa: 4 chiều nhịp thành **bắt buộc**, luôn vào tập chọn mẫu + target, và thêm
2 chiều còn thiếu (`sentence_short_ratio` / `sentence_long_ratio`, dùng đúng ngưỡng 8/35
của `deai` và `chon_neo` để thước đo và neo giọng nói cùng một thứ tiếng).

Đo lại 12 hồ sơ — **lệch nhịp đoạn mẫu so với corpus: trung bình 6,41 → 0,47**, tốt hơn
ở 10/12. A001 3,69 → 0,26 · A003 65,35 → 0,32 (mẫu cũ 639,7 từ/câu: nó lấy nguyên cục
transcript thô làm mẫu) · A010 1,03 → 0,38. Kém hơn 2 hồ sơ, mức chênh nhỏ: A009
0,36 → 0,79 · A014 0,39 → 0,47.

### 14.2. Thước thứ ba: nhận dạng tác giả (C4)

Hai thước cũ không biết tác giả là ai — nhóm A đếm dấu vết máy, nhóm B đo nhịp; hai người
cùng nhịp thì chúng không phân biệt nổi. `delta.py` là Burrows 2002 bản gốc: 150 từ phổ
biến nhất, z-score theo từng từ, khoảng cách = trung bình |z_a − z_b|. Từ có `sd = 0` bị
**bỏ** khỏi trục đo (không vá bằng epsilon); văn dưới 500 từ vẫn xếp hạng nhưng khai
`du_mau = False`.

Chạy trên kho lộ ra chuyện không ai biết: **kho 12 hồ sơ chỉ có 8 giọng thật**.
`A003 = A008 = A011` (đã biết từ 23/08) và **`A007 Storytelling-Investigate = A012 Old
story`** — Delta 0.000, cùng một corpus 8.244 từ mang hai tên. Người viết đang chọn giữa
những cái tên khác nhau mà bên trong là một.

Kiểm leave-one-out (cắt đoạn ~1.500 từ khỏi corpus rồi hỏi "đoạn này của ai"): **11/12**
đúng ở cấp nhóm giọng. Ca sai duy nhất là A001 Carl Sagan bị đọc thành A002 Attenborough
(1,072 vs 1,140 — sát nút, hai giọng tư liệu khoa học vốn gần nhau). Con số thô trước khi
gom nhóm bản sao là 6/12, và 5 ca "sai" đó đều là hồ sơ bị **chính bản sao của nó** chiếm
chỗ: thước đúng, dữ liệu trùng.

### 14.3. Ba tầng đo còn thiếu (C5)

`dien_ngon.py` — 9 chiều Quant Engine không nhìn: lập trường (`you` / `I` / `we` trên
1.000 từ), diễn ngôn (câu mỗi đoạn, liên từ mở câu, câu hỏi), cú pháp (bị động bằng proxy
regex, hapax, mật độ chữ số). Đây là thứ phân biệt hai giọng rõ nhất mà không thước nào
đang đo:

| | A009 LeoKim | A013 Derek Muller | A002 Attenborough | A007 |
|---|---:|---:|---:|---:|
| "you" / 1.000 từ | **37,8** | 8,1 | 1,2 | 0,6 |
| câu mở bằng liên từ | **66%** | 32% | 8% | 3% |

Nằm ở **khóa riêng** `discourse_features`, tuyệt đối không nhập vào `quant_features`: mọi
chiều nhét vào đó sẽ tự động chảy tiếp vào `reproduction_targets` rồi vào thang chấm giọng
— và thang càng nhiều chiều tạp nham thì càng dễ đọc ngược (bài học `punct_freq_total`
23/08 làm điểm tụt 86% → 57% cho bản văn **tốt hơn**). Có test ghim hai tầng không lẫn sang
nhau.

Van lộ ra khi đo thật: A007/A012 cho **786 câu/đoạn**, A010 cho 426 — không phải văn phong
mà vì file corpus không có một dòng trống nào, tức đó là độ dài **file**. Nay báo thẳng và
đánh dấu chiều đó `do_duoc = False`.

### 14.4. Mở kênh dẫn — và kết quả A/B (C3)

`build_nhip_block` đưa **con số của chính tác giả này** vào prompt, kèm câu "các đoạn mẫu
bên dưới đã nằm ở đúng những con số đó" — để model có cả *tell* lẫn *show* cùng một hướng,
thay vì lệnh trừu tượng kiểu "viết câu dài" (con lắc 16/07). Nguồn số: `reproduction_targets`
khi đo được, lùi về đo trên chính các đoạn mẫu sẽ hiện trong prompt.

Hai van: hồ sơ chưa đo được gì → khối **rỗng**, prompt không đổi một byte (test hồi quy
ghim); trần độ dài đoạn 2–8 câu, vì A009 cho 39 câu/đoạn và một lệnh "viết đoạn 39 câu" là
lệnh vô lý — ngoài khoảng thì bỏ dòng đó chứ không đoán bừa số khác.

### 14.5. Báo cáo extract (Owner yêu cầu)

`bao_cao.py` — chạy xong extract là có `bao-cao-extract.md` ngay cạnh `profile.json`.
Trước đây muốn biết một hồ sơ có dùng được không thì phải mở `profile.json` đọc tay, và
không ai đọc: đó là lý do ba hồ sơ dựng trên corpus transcript thô vẫn được dùng viết suốt
ba tuần. Báo cáo trả lời bốn câu hỏi bằng tiếng Việt:

1. **Máy đã đọc gì** — file vào, file bị loại và vì sao, số điểm đo cắt ra.
2. **Đo được gì** — từng chiều kèm *vì sao nó có mặt*: "giữ: ổn định" / "giữ: chiều bắt
   buộc (nhịp câu)" / "chưa đo được". Không con số nào tự nhiên có mặt mà không giải thích.
3. **Khác giọng khác chỗ nào** — Delta tới 3 giọng gần nhất + cảnh báo trùng hồ sơ.
4. **Gì thật sự đi vào prompt** — in nguyên văn khối `VOICE TARGETS` generator gửi đi.

Kèm `bao_cao_kho()` cho Owner nhìn hết 12 hồ sơ trong một bảng, và lệnh CLI `bao-cao`
để dựng lại bất cứ lúc nào (0 token). Báo cáo hỏng **không được** làm hỏng extract — bọc
`try` riêng.

Ba lỗi trình bày bắt được khi **đọc báo cáo thật của A013**, không phải từ test: báo cáo tự
mâu thuẫn (vừa ghi "neo 1.950 từ" vừa cảnh báo "neo chỉ 253 từ" — vì `soi_ho_so` đo 3 đoạn
mẫu trong hồ sơ còn lúc viết thì `cli` thay bằng neo dày); chiều bị artefact định dạng vẫn
in như chiều bình thường; và câu cảnh báo viết tiếng Việt **không dấu** lẫn vào báo cáo có
dấu. Quy ước từ nay: **chuỗi hiển thị có dấu, code và comment giữ không dấu.**

### 14.6. A/B của C3: đo xong thì **bác** — mặc định TẮT

Chạy 15 lượt trên hai hồ sơ ngược chiều nhau, cùng outline cùng neo cùng `glm-5.2`, khác
đúng một biến `CU_NHIP_PROMPT`:

| lệch nhịp so với corpus (càng nhỏ càng đúng giọng) | tắt | bật |
|---|---|---|
| A014 Amazing (corpus 13,2 từ/câu) | **0,61** `[0,28 0,69 0,49 0,99]` | 0,73 `[0,73 0,53 0,84 0,84]` |
| A012 Old story (corpus 10,6) | **0,43** `[0,32 0,55 0,42]` | 0,70 `[0,17 1,16 0,98 0,48]` |
| gộp | **0,53** (n=7) | 0,72 (n=8) |

Bật kém hơn ở 5/7 cặp, và bài **ngắn hơn ~9%** (A014 350 → 318 từ; A012 418 → 376). Nói
con số ra không làm model bám nhịp hơn — nó làm model viết đứt quãng và ít chữ hơn.

Đổi mặc định trong **CODE** về tắt (không chỉ `.env` — bài học 18/07: `.env` không theo
sang máy khác). Giữ nguyên cơ chế và toàn bộ test: bằng chứng 23/08 cho thấy `glm-5.3`
bám neo còn `5.2` thì không, nên **thử lại với 5.3 là việc của đợt sau**, không phải bỏ đi
làm lại. 1/16 lượt dính `contentFilter` GLM (mã 1301) ở A012 — đúng ca đã ghi ở mục 12.2,
không liên quan biến đang đo.

Đây là kết quả quan trọng hơn cả việc nó "thất bại": nếu tin gợi ý của Grok mà không đo,
hệ đã có thêm một khối luật thường trực trong prompt làm bài **xấu đi và ngắn đi**, và sẽ
mất hàng tuần mới truy ra — đúng kiểu bệnh mà `punct_freq_total` và con lắc 16/07 đã gây.

### 14.6b. Đo lại với glm-5.3: **đảo chiều hoàn toàn**

Owner báo đã chuyển sang 5.3, nên đo lại đúng bộ đo đó — 11 lượt, cùng hai hồ sơ:

| | tắt | bật |
|---|---|---|
| glm-5.2 (15 lượt) | **0,53** | 0,72 · bài ngắn hơn ~9% |
| glm-5.3 (11 lượt) | 0,70 | **0,35** · bài *dài hơn* (285 → 336 từ; 603 → 632) |
| A014 từng lượt 5.3 | `[0,58 0,72 0,86 0,24]` | `[0,33 0,51 0,29 0,35]` |
| A012 từng lượt 5.3 | `[0,68 1,14]` | `[0,28]` · 1 lượt dính contentFilter 1301 |

Cùng một đoạn văn, cùng một khối số, **hai model đọc ra hai hướng ngược nhau** — và khớp
với bằng chứng 23/08 (5.3 bám neo; 5.2 bị thể loại chi phối mạnh hơn neo). Con số trong
prompt chỉ ăn với model **chịu nghe theo neo**.

Nên bỏ cờ tay, cho nó **tự quyết theo model**: `MODEL_BAM_NEO = ("glm-5.3",)`, `cli` gán
`profile["_model"]` bằng model đang chạy (biến trong bộ nhớ, không ghi đè hồ sơ) và in một
dòng báo đã gửi kèm số đo. `CU_NHIP_PROMPT` vẫn thắng cả hai chiều khi cần ép tay. Lý do
bỏ cờ tay: cờ đặt sai chiều thì văn vẫn xấu đi mà **không ai biết** — cùng họ bệnh với cảnh
báo transcript thô bị bỏ qua 100% suốt từ 16/07.

**Thêm model mới vào `MODEL_BAM_NEO` chỉ sau khi đã A/B đủ lượt với chính nó** — đừng suy
diễn "đời sau chắc cũng thế".

**Hai điều về 5.3 phải biết trước khi team dùng thật** (đo hôm nay): chậm gấp 3–4 lần
(171–487 giây một chương so với 50–150), và rủi ro mục 13.1 vẫn còn (model reasoning đốt hết
ngân sách token ở vòng cắt/nở rồi trả rỗng — bản vá 88505fc giữ được bản nháp nhưng chương
sẽ không về đúng khuôn độ dài). `contentFilter` GLM vẫn dính ở hồ sơ A012, cả 5.2 lẫn 5.3.

### 14.8. UI tab Author + mô tả giọng (24/08, theo yêu cầu Owner)

**Chạy lại toàn kho.** Backup `data/content-ultimate/backup/profiles-truoc-c1c5-20260823/`
trước, rồi dựng lại 12/12 hồ sơ có corpus bằng C1–C5 (A005/A006 bỏ qua — corpus trỏ
`/tmp` từ thí nghiệm 16/07). `signature_moves` giữ nguyên toàn bộ, không gọi lại LLM.

Chỉ **A009** (12.167 từ) và **A014** (25.392 từ) là sạch. Còn lại cần Owner bổ sung:

| hồ sơ | có | cần thêm |
|---|---:|---:|
| A013 Derek Muller | 3.726 từ | ~8.300 |
| A010 Tribes | 6.853 | ~5.100 |
| A007 / A012 | 8.244 | ~3.800 |

Và một vấn đề chung dễ sửa: **10/12 corpus là văn bản một khối, không có dòng trống
nào** — chiều "số câu mỗi đoạn" vì thế không dùng được. Khi nạp thêm bản thảo, giữ
được ranh giới đoạn thì hệ đo thêm một chiều mà không tốn gì.

**Báo cáo lên UI.** Bốn nhóm số Owner yêu cầu, mỗi nhóm trả lời một câu khác nhau:
mức độ (theo *điểm đo*, không theo số từ) · số từ · độ giãn câu (±SD, kèm từ/câu và %
câu cụt) · giống tác giả khác (Delta + cảnh báo trùng). Route `GET /api/ho-so?ma=`
chạy 0,5 giây, 0 token, **chỉ nhận mã** — không nhận đường dẫn từ client (cùng luật
với `/api/kiem-chung`). Bảng Delta đọc 20.000 từ đầu mỗi corpus thay vì trọn: A001 có
149.240 từ, đọc hết chỉ để lấy một con số thì UI phải chờ.

Bố cục tab Author về đúng khuôn Writing: trái = kết quả đọc được + log, phải = thiết
lập dính màn hình. **Hai tab vẫn tách bạch** (Owner nhắc) — `/author` và `/write` là
hai trang riêng, cơ chế `CU_MODE` không bị chạm. Bỏ luôn trần riêng `#p1{max-width:1140px}`
có từ hồi tab này là form một cột: nay cả ba pane cùng `.app` 1460px.

**Gộp trường nhập.** "Folder bản thảo" + "Bộ văn bản" là hai ô cho cùng một việc (chọn
thư mục, rồi chọn thư mục con của chính nó) → một ô **Tác phẩm**. Bỏ "Folder kết quả":
đường dẫn đó máy tự biết, không bắt người dùng khai. `ex_dir`/`ex_out` thành input ẩn
nên hợp đồng với server không đổi.

**`mo_ta_giong.py` — chỗ duy nhất LLM nói thành lời.** Báo cáo trả lời được "giọng này
đo ra bao nhiêu" nhưng không trả lời được "nên giao việc gì cho giọng này". Năm phần:
giọng nghe thế nào · dùng cho nội dung gì · mood cần set · atmosphere · không hợp với.
Van chặt hơn mọi chỗ khác: hồ sơ **chưa đủ điểm đo thì không gọi model**; LLM chỉ nhận
số đã đo + đoạn văn thật + moves đã kiểm chứng; prompt cấm bịa số; hồ sơ lưu kèm
`so_do_neo` để đối chiếu từng con số trong lời văn; phần nào rỗng thì bỏ hẳn; lỗi model
không được làm hỏng extract. Mặc định **không tick** (luật A6 — luồng cũ không tự tiêu
thêm một lượt LLM), UI có checkbox bật sẵn cho người chạy thấy.

Bản chạy thật đầu tiên (A014) lộ ngay một lỗi kiểu chữ: model viết *"Câu trung bình
14,2936 từ nhưng biến thiên mạnh (9,1934)"* — bốn chữ số thập phân đi thẳng vào báo cáo
cho người biên tập. Nay làm tròn trước khi đưa cho model, và tỉ lệ đổi sang phần trăm
kèm tên trường nói rõ đơn vị.

### 14.7. Còn lại của mạch này

- **Chạy lại extract cho 12 hồ sơ trong kho thật.** Toàn bộ số đo ở mục này dựng trong
  scratchpad (chỉ đọc kho). Hồ sơ đang dùng vẫn là bản cũ với `sd = 0` giả; chạy lại là
  việc của Owner vì nó ghi đè `profile.json` đang phục vụ team.
- **Dọn hồ sơ trùng**: `A003 = A008 = A011` và `A007 = A012`. Năm cái tên, hai giọng.
- **Corpus mỏng cần nạp thêm**: A013 Derek Muller 3.726 từ · A010 Tribes 6.853 · A007/A012
  8.244. Ngưỡng để nói được điều gì về độ ổn định là ~2.400 từ, nhưng để 4 điểm đo tách
  bạch thì nên ≥12.000.
- **Thử lại C3 với glm-5.3** (một biến, cùng bộ đo, đủ lượt như lần này).
- **Dùng Delta cho kiểm chứng mù**: hai bản của cùng một chương, hỏi thước xem bản nào gần
  tác giả hơn — thay cho thang % đã bỏ.

## 15. KIẾN TRÚC OUTLINE — 30-31/08/2026 (thay board tick bằng 4 khối; suite 288→778)

Mạch lớn nhất từ mục 9: **bỏ cách lắp outline bằng tay** (tick/kéo cluster) — thay bằng
tầng KIẾN TRÚC: máy đề xuất trọn khung, người điều chỉnh từng thẻ. Logic từng nhiệm vụ:

### 15.1 Engine 4 lượt (`src/oe/kien_truc.py`)
- **A KHUNG — pillar BỊT MẮT**: brief + research → spine + hợp đồng beat (tên/emo/budget).
  Lý do bịt mắt: để pillar trong context thì "cụ thể thắng trừu tượng" — corpus tự chiếm
  ghế của brief. 1301 contentFilter → retry 1 lần → lỗi nói rõ cách gỡ (sửa câu chủ quyền).
- **B GẮN BẰNG CHỨNG — 0 LLM**: mỗi beat ≤2 pillar theo cosine (fastembed, ngưỡng 0.30 đo
  thật 13 cặp). Beat không bằng chứng → nhãn CAU_KHONG_CUNG, KHÔNG xóa im lặng.
- **C KHÁM PHÁ**: ≤2 beat đề xuất từ kho, gate `kho_de_xuat` chờ Owner duyệt.
- **D VIẾT BRIEF — context cách ly**: mỗi beat chỉ thấy spine + hợp đồng + pillar CỦA NÓ
  (chống Frankenstein 8-nguồn/chương). Budget = metadata nhịp, KHÔNG phải lệnh ép ký tự;
  chương EXPENDABLE xếp về đuôi để cắt tròn chương.
- **7 van tất định** sau mỗi thao tác (phủ brief, pillar mồ côi, nhịp, budget, số lá,
  trung tâm cảm xúc, trần pillar) — CẢNH BÁO không chặn (luật A3).
- Mọi output LLM là TIẾNG ANH kể cả briefing gõ tiếng Việt (Owner chốt giữa mạch,
  pin trong cả 4 prompt + test).

### 15.2 Verify BẮT BUỘC (Owner chốt: "căn cứ vào đây để sinh khung")
- `phieu_xac_minh` bóc claim từ briefing thành phiếu FACT-PACK (`FACT: ... | NGUON: <url>`).
- **Auto Verify** = LLM + web_search z.ai (route `/api/kientruc/xacminh`) + 2 van đo thật
  31/08: link google/bing/ddg `/search` KHÔNG tính là nguồn; model phán "tương lai/chưa
  xảy ra" → nhắc phiếu tay (search model có thể chưa quét tới tin nóng).
- **Manual Verify** = copy phiếu dán sang AI có web, dán kết quả về ô Research notes.
- `_kt_sinh` CHẶN khi research trống — khung phải đứng trên fact đã kiểm.

### 15.3 UI 4 khối đi lại tự do (`src/oe/kientruc.html`, route `/kientruc`)
Stepper EN (Owner duyệt mockup + chốt tên): **Brief / Verify / Outline Board / Finalize**;
checkpoint 4 giai đoạn (1 Frame · 2 Evidence · 3 Discovery · 4 Briefs) xanh dần; khóa hết
thẻ → tự sang Finalize. Kho ý tưởng 4 tab (Pillar/Gaps/Ý video sau/Misconception — hàng
gọn 1 dòng, click xổ); double-click pillar mở popup đầy đủ; F5 giữ khối (localStorage
`kt_khoi`); render Google-Translate-safe (`datHTML` trả changed-bool, chỉ rebind khi đổi).
Vòng điều chỉnh từng thẻ: Khóa / Sửa tay / Góp ý + sinh lại (giữ `ban_cu` quay lui) / Bỏ /
Lên / Xuống. Chốt = `dung_outline` ghi `outline.txt` + `material.json` + `picks.total_chars`.

### 15.4 Phiên per-user + xem phiên đồng đội (31/08)
- Mỗi user MỘT bản nháp `kien_truc_<slug>.json` trên cùng run (Owner chốt "phiên không đè
  nhau"); task registry key `run|user`; outline.txt lúc CHỐT vẫn là bản chung của run.
- **Xem phiên đồng đội**: leader+ (SSO Actions) chọn phiên ở select cạnh run — CHỈ ĐỌC
  (banner + khóa control 4 pane); an toàn tự nhiên: mọi POST ghi file của CHÍNH người gọi.
  Creator không thấy danh sách, không đọc được (kiểm ở server `_kt_giam_sat`).

### 15.5 Ống vật liệu sang Writer (Mảnh A đợt "Viết đúng thể loại")
`goi_vat_lieu()` = pillar nguyên văn + research lines argmax-embed theo beat (key khớp
`parse_outline`: Hook/Chapter n/End) → `material.json` → `/api/write` → CLI tự đọc
`.material.json` cạnh outline → khối FACTUAL MATERIAL + luật fact tầng viết ("Never
invent specifics"). Đo thật: hết bịa số khi material không có số (GIGO xác nhận);
hook 300 → 2.149 ký tự nhờ budget từ brief (`_budget_tu_brief`).

### 15.6 Thể loại + giọng KÊNH (Mảnh B/C)
- Hồ sơ thể loại `rules/the_loai/*.json` (luật ngoài code): khuôn khung narrative|catalog,
  register per-block đo từ 2 kênh mẫu. Owner sửa nguyên tắc: thể loại chỉ quy định HÌNH
  THỨC — góc hook thuộc về BRIEFING (không áp "hook thảm họa" cho travel-doc).
- Giọng KÊNH (`voiceprofile/kenh.py`): dán link video kênh → transcript (youtube-transcript-api)
  → dọn ASR (van 85-115% từ gốc, <45 từ/câu) → corpus → extract như tác giả; guard chống
  trùng tên đè hồ sơ tác giả có sẵn. Nằm ở tab Author Extract (Owner chốt).

### 15.7 Trang Video Outlier riêng (`videooutlier.html`, route `/outline`)
"+ Video Outlier" và "Outline Board" là 2 tab KHÁC nhau (Owner nhắc): trang mới = tạo run
(tên/AVD/model/links) + checklist 8 bước pipeline thật (nhãn từ s5_server) + box cookies
tự mở khi tín hiệu YouTube chặn IP + danh sách run 2 cột cao bằng nhau; log pipeline ẩn,
double-click mới hiện. Board tick cũ hạ về `/outline-cu` (di sản, không nav) — dọn hẳn
sau khi team chạy trơn luồng mới.

### 15.8 Writing: popup sửa văn + công thức quốc tế
- Bỏ ô "Yêu cầu đặc biệt" TRƯỚC khi viết (vòng góp ý đã sống ở Outline Board) — thay bằng
  popup double-click vào bài: trái đọc văn, phải ô yêu cầu áp lên VĂN ĐÃ VIẾT → Viết lại
  (tái dùng W_YEUCAU/vietLaiPhan, bản cũ giữ quay lui). Fix văn cách dòng đôi (pre-wrap +
  `\n→<br>` render đúp).
- Công thức viết: CHỈ framework quốc tế có thật (Owner: "phải research, không bịa") —
  V2·M (nhà, mặc định) · AIDA · PAS · BAB · SCQA (Minto) · HSO (Brunson) · 3-Act
  (Aristotle/Syd Field) · SDT; bỏ 3 kỹ thuật tự chế. Ví dụ trong popup trích TÁC PHẨM
  KINH ĐIỂN format thống nhất: nguyên bản EN → dịch Việt → phân tích biện pháp → nguồn
  footer mờ (Caples 1926 · An Inconvenient Truth · thư WSJ 1974 · 1984 Orwell · Jobs
  Stanford 2005 · Star Wars 1977 · Chekhov-attributed có caveat); van tự áp cho chính
  mình: chỉ trích nguyên văn câu chắc từng chữ, còn lại mức cấu trúc + nguồn tra được.
- Model chọn RIÊNG cho Verify vs Sinh (nhớ localStorage) + tooltip gợi ý từng model
  (chỉ ghi điều đã đo nội bộ; nhắc Auto Verify chỉ chạy web search qua z.ai/GLM).

### 15.9 Bug đã vá trong mạch (31/08)
1. **UnboundLocalError `b`** giết kết nối 4 nhánh POST kientruc → parse body per-branch +
   test tầng route thật (ThreadingHTTPServer) — "test xanh ≠ chạy đúng".
2. **Brief rỗng lặng lẽ** (đo thật nepal-2: 8/11 beat rỗng): gói chung lượt D "thành công"
   nhưng model đổi tiêu đề/thiếu block → parse trượt, không exception → fallback cũ không
   chạy. Lưới mới: MỌI beat còn brief rỗng sau gói chung được viết CÁCH LY từng beat.
3. **Khóa-mà-rỗng kẹt vĩnh viễn**: user khóa các thẻ rỗng → mọi lượt sinh tôn trọng khóa.
   Luật mới: khóa bảo vệ nội dung ĐÃ CÓ — thẻ khóa brief rỗng vẫn được viết bù, trạng
   thái khóa giữ nguyên.
4. **Đồng hồ tiến độ** `[Ns]` mỗi dòng — sinh 30' không có số đo thì không chẩn đoán được.
   Nghi phạm tốc độ đã khoanh: 3 lời gọi lớn tuần tự + Z.ai chậm giờ tải + bẫy
   finish_reason=length nhân đôi max_tokens chạy lại từ đầu (llm.py).
5. Parser khung `_RE_BLOCK` khoan dung (`## CHAPTER 1 —`, `###`, `:`) — GLM viết lệch
   header là chuyện thường (bài học parser 24/07 tái xác nhận).

### 15.10 Việc treo
- Chờ Owner gửi 3-5 link video kênh neo (travel-doc + Life-in) → hồ sơ giọng K đầu tiên →
  "trận chung kết" tibet-2 mới vs bản Claude (bảng thước mục 0 proposal).
- C3 neo giọng dày từ corpus cho thước kiem-chung (không gấp).
- A/B Claude-làm-writer (cần key Anthropic, sau khi có neo giọng).
- Dọn `/outline-cu` sau khi team chạy trơn 1-2 video.

### 15.11 AUDIT TOÀN TOOL 31/08 (2 agent quét + vá cùng ngày; suite 780 pass)

Owner yêu cầu audit toàn bộ. 40 phát hiện, chia ba nhóm:

**ĐÃ VÁ (cùng ngày, có test ghim):**
- Engine outline: brief gán SAI beat khi tên lồng nhau ("The River"/"The River of
  Bones" nhận cùng brief — parse 2 pass, mỗi khối dùng 1 lần); chapter khóa nuốt
  HOOK khi "giữ" (khớp tên không kiểm loại); beat khóa chèn đảo LIFO; `da_bo` bị
  xóa mỗi lượt sinh (biểu thức chết `(giu and []) or []` — giờ server truyền lại);
  parse_khung 0 beat → state RỖNG đè bản cũ (giờ retry rồi raise, không ghi đè);
  pillar beat khóa bị gán trùng cho beat mới; budget model bỏ sót → chia đều;
  van_so_la nối thiếu dấu cách tạo số ma; lượt C hết nuốt lỗi lặng lẽ.
- Server: thao tác beat TRONG lúc sinh nền bị lượt sinh đè phẳng → chặn từ cửa;
  "giữ thẻ khóa" mà không đọc được bản nháp → trước im lặng mất hết khóa, giờ lỗi
  rõ; clusters.json hỏng hết giết route (500 board trắng); quay lui hết mất bản
  hiện tại (xoay vòng); chốt đè outline chung → backup `outline.truoc.txt` + ghi
  `chot_boi/chot_luc` vào picks; briefing xacminh cắt 8000 ký tự; buoc[] hết phình.
- UI Outline Board: HỒI QUY đồng hồ [Ns] làm 4 chip checkpoint đứng im (startsWith
  → includes); đổi run/phiên không dừng poll cũ (2 vòng đá nhau + phiên chỉ-đọc bị
  mở khóa lại); copy phiếu thất bại vẫn báo "Đã copy".
- Tầng viết: brief mở "Chapter one…"/"Ending…" thành MỐC MA (phần thừa không
  material + checkpoint đè nhau) — luật heading mới: separator / đứng một mình /
  keyword TOÀN HOA; vòng cắt hook ép về 250-500 bất kể Budget kiến trúc (mất 86%
  hook — giờ cắt theo budget), End cũng vậy; "viết lại MỘT phần" khi checkpoint
  mất/lệch hash → script.md bị ghi đè còn 1 chương (giờ phần khác nạp nguyên văn từ
  script.md); 409 /api/write bị UI nuốt (poll job cũ như job mới); mat_path
  `.replace()` làm material rơi im lặng; guard trùng file so chuỗi thô; registry
  giọng ghi tràn (giờ tmp+os.replace); kenh.py chỉ NoTranscriptFound mới rơi về
  ASR; pill "done" nhầm dòng "vượt trần"; download hỏng path Windows.

**GHI NHẬN — CHƯA VÁ (cần Owner quyết hoặc không gấp):**
1. **Quyền chốt outline**: bất kỳ ai (kể cả creator) chốt được và đè bản chung của
   run — đã có backup + dấu vết, nhưng LUẬT ai-được-chốt chờ Owner (đề xuất:
   leader+ hoặc "người sinh khung gần nhất").
2. `_rd_for` cho mọi user nhảy vào run bất kỳ (by design team chung run — đi kèm
   điểm 1 khi quyết).
3. Slug tên user đụng độ (`al_ice`/`al-ice` chung file state) — tên thật của team
   hiện không đụng; đổi format file = migration, làm khi cần.
4. Job writer không sống qua restart server (registry RAM; subprocess mồ côi vẫn
   ghi file) — máy hibernate 20:00 sẽ giết job đang chạy; có checkpoint + nút Tiếp
   tục nên chấp nhận, việc treo nếu muốn bền: persist job registry.
5. `van_phu_brief` so brief tiếng Việt với văn EN → MISSING oan (so cross-language
   không làm được 0-LLM — hạn chế trung thực, đã ghi).
6. `van_so_la` gom số từ TOÀN nguồn nên số bịa đúng-giá-trị-khác-ngữ-cảnh lọt —
   nâng cấp sau (per-beat scope).
7. `register.py` (văn register theo thể loại) là code chết — Mảnh B tầng viết chưa
   nối; nằm trong việc treo C3/A-B.
8. `moKhoi` gán lại function declaration — chạy được vì file không strict mode;
   thêm 'use strict' là vỡ (bom ghi nhận, đừng thêm strict vào kientruc.html).
9. KT_TASKS không dọn entry cũ (đã cắt buoc 200 dòng; dọn theo TTL làm sau).
10. `_budget_tu_brief` đọc "~1.5k" thành 15 — khuyên ghi số trần trong brief.

### 15.12 OWNER QUYẾT 4 ĐIỀU (31/08 tối) — đã thi công ngay

1. **Quyền outline**: người TẠO outline được finalize + chỉnh sửa; người cùng cấp
   CHỈ XEM; Leader/Manager được sửa/chốt đè. Thi công: chốt đầu tiên trên run →
   thành chủ outline (picks.chot_boi); người khác cùng cấp bị chặn chốt lại với
   lỗi rõ; Leader+ luôn chốt được (backup outline.truoc.txt giữ nguyên). Xem phiên
   đồng đội MỞ CHO MỌI CẤP (trước chỉ leader+) — vẫn chỉ-đọc tuyệt đối.
2. **Tắt máy an toàn**: warning nhân sự trước khi tắt, CHỈ tắt khi không job.
   Thi công: tat-may.ps1 ghi cờ sap_tat.json (UI kientruc + board hiện banner đỏ,
   poll 60s) → hỏi /api/tinh-trang-ban (job writer/extractor + sinh khung) mỗi 5'
   tối đa 60' → hết job mới shutdown; còn job sau 60' → KHÔNG tắt, ghi log.
   (Tác vụ OUTLIERY-TatMay hiện Disabled — script là lưới khi bật lại/chạy tay.)
3. **Brief phải TIẾNG ANH**: cảnh báo sống dưới ô briefing khi >5% ký tự có dấu
   tiếng Việt (không chặn — luật A3); lý do: van Phủ-brief so chữ không xuyên
   ngôn ngữ được.
4. **Trung tâm thông báo** Outline Board: mọi toast được LƯU vào panel — nút
   "Thông báo" ở header + badge chưa đọc, xem lại lịch sử cảnh báo của phiên
   (50 mục, per-browser). Banner sắp-tắt dùng chung khung.

### 15.13 A/B SINH KHUNG glm-5.3 vs glm-5.2 (02/09, cùng brief tibet-2, n=1 mỗi bên)

| | glm-5.3 | glm-5.2 |
|---|---|---|
| Thời gian trọn 4 lượt | 500s (~8'20) | 320s (~5'20) |
| Beat | 10, brief đủ 10/10 | 6 (+1 đề xuất), 1 brief rỗng |
| Tổng brief | 6.410 ch | 4.156 ch |
| Mật độ số liệu trong brief | 4,7/1000 từ | 10,3/1000 từ |
| ContentFilter | 0 | 1 beat (Tourist Door — 400 level 1) |
| Van | 6 ĐẠT + budget CẢNH_BÁO | 6 ĐẠT + budget CẢNH_BÁO |

Nhận xét (n=1 — chưa phải kết luận chắc, luật A/B nhiều lượt): 5.3 khung DÀY hơn
(10 beat phủ rộng, EXPENDABLE xếp đúng đuôi, tên chương cụ thể có số); 5.2 nhanh
hơn ~40% + brief đậm số hơn, nhưng khung mỏng và DÍNH contentFilter với chủ đề
Tibet (5.3 cùng chủ đề không dính — điểm cộng lớn cho niche nhạy cảm TQ).
Lượt 5.2 đồng thời là kiểm chứng sống 2 lưới 31/08: gói chung bị chặn → viết
cách ly 7 beat tự chạy có tiến độ; beat chết filter → báo lỗi thật trong bước.

### 15.14 PHẢN BIỆN HỌ BỆNH THINKING + QUYẾT ĐỊNH TẮT MẶC ĐỊNH (02/09)

Ba sự cố sản xuất trong 2 ngày cùng gốc (content rỗng → 5.3 cấm disable → chương
19 ký tự) đều được vá ở tầng LƯỚI CỨU — phản biện: đó là chữa triệu chứng, bệnh
nằm ở LƯỢT ĐẦU: Z.ai TỰ BẬT thinking cho mọi model GLM. Số đo:
- Usage 2 ngày: 88% output token là suy nghĩ ngầm (209.546/237.456) — trả tiền
  gấp ~8 lần phần chữ nhận được.
- Cặp đo sống cùng prompt (glm-5.2): BẬT = 26,3s, 2.000/2.000 token suy nghĩ,
  0 ký tự văn (tái hiện đúng bệnh); TẮT = 5,2s, 192 token, 918 ký tự văn.
QUYẾT ĐỊNH: tắt thinking MẶC ĐỊNH từ lượt đầu cho mọi call GLM ("sửa ở nguồn");
`GLM_THINKING=auto` trong .env để trả về hành vi provider khi thí nghiệm; chuỗi
cứu 2 nấc (disabled → 400/1210 → reasoning_effort=low) giữ nguyên làm lưới.
VỀ CÂU "CÓ CỐ CHẤP GLM?": V3 hiện CHỈ có key GLM — chưa phải lựa chọn. Khuyến
nghị: giữ GLM (đã tắt thinking) làm ngựa kéo vì rẻ; Owner cấp key Claude/Gemini
để (a) A/B chất lượng thật (việc treo từ 23/08), (b) đường thoát contentFilter
1301 với đề tài nhạy cảm TQ — rủi ro CHIẾN LƯỢC không vá được bằng code.

### 15.15 ĐÁNH GIÁ GLM vs GEMINI (02/09, Owner hỏi)
Đo sống GLM-5.2 (thinking off): thân 200 từ = 6,3s/$0.0011, 19,1 từ/câu, 0% cụt,
0 dash; hook bám FACTUAL MATERIAL = KHÔNG số lạ. Gemini KHÔNG đo được: key trong
.env V2 đã CHẾT ("Please pass a valid API key" — vì thế bị comment). Bằng chứng
nội bộ Gemini: 30/08 là đường thoát 1301, viết 2/6 video Tibet khi GLM từ chối.
Giá niêm yết (web 02/09): GLM-5.2 $1.40/$4.40 · GLM-5 $0.60/$1.92 · Gemini Flash
hiện hành $1.50/$7.50 · Pro $2/$12 /1M tok. Ước bài 22k ký tự: GLM-5.2 ~$0.11,
Flash ~$0.14, Pro ~$0.19; GLM CÓ thinking (trước khi tắt) từng ~$0.30 = đắt hơn
cả Pro — thuế thinking mới là biến chi phí lớn, không phải đơn giá.
Nhắc từ bảng 23/08: trong họ GLM, 5.3 bám neo giọng gần hoàn hảo (lệch nhịp 0,01
vs 1,11 của 5.2) — nhưng số đó đo khi thinking auto; 5.3-effort-low chưa đo lại.
CHỜ OWNER: cấp key Gemini mới (+ Claude nếu muốn) để đo viết thật 3 nhà cùng thước.

### 15.16 ĐỢT UX TỪ GÓP Ý TEAM + MỔ RUN PAKISTAN (05/09; suite 810 pass)

Team góp ý 7 điểm; mổ run Pakistan (LI102) xác nhận 2 bệnh khung: briefing dán
18 ý nhưng khung chỉ 8 chương → model NHỒI ý không liên quan chung chương
("Skin Cream + Transgender Rights"), ý ẩm thực RỚT (van Phủ-brief bắt MISSING
nhưng nằm chìm trong bảng van). Content tầng viết OK (10 phần, 5-6 đoạn/phần,
nhịp 13-21 từ/câu). Đã làm:
1. AUTOSAVE nháp briefing/research theo run (localStorage, xóa khi bấm sinh) —
   hết cảnh "bấm nhầm mất hết ý đã chọn".
2. Ô GÓP Ý CẤP KHUNG + nút "Sinh lại KHUNG (giữ thẻ khóa)" đầu vùng điều chỉnh
   — "nhóm chương 1-2-3 quanh câu hỏi A" giờ là một câu lệnh, engine nối vào
   prompt lượt A (EDITOR'S STRUCTURAL NOTES).
3. BANNER ĐỎ khi khung bỏ sót ý brief + nút "Sinh lại, phủ các ý này" (tự điền
   góp ý khung từ danh sách MISSING).
4. Luật prompt lượt A: ONE TOPIC PER CHAPTER — cấm ghép ý không liên quan; brief
   nhiều ý hơn khung → ưu tiên theo spine + bỏ ý có khai báo (MISSING), cấm đẻ
   chương không ai yêu cầu.
5. KÉO-THẢ sắp xếp thẻ (act "chuyen"; thẻ khóa vẫn kéo được — vị trí do người
   xếp) — giữ nút Lên/Xuống.
6. Nút "GỘP THẺ DƯỚI" trên chapter đang mở (act "gop"): hợp nhất tất định
   pillar/budget/nhãn, LLM viết lại brief MỘT MẠCH; làm trên bản sao — LLM lỗi
   không mất thẻ. Tách-1-thẻ-làm-2 chưa làm (đợt sau nếu team cần).
PHẢN BIỆN GIỮ NGUYÊN (không code): hook ~2000 ký tự là chủ đích Owner 31/08 —
núm chỉnh là dòng Budget của HOOK trong outline (sửa được trước khi viết);
"không chia đoạn" không tái hiện trên bài mới (đã vá 31/08); Google-Translate
reset là bản chất DOM động, đã giảm tối đa.

### 15.17 FEEDBACK BÀI RAU UNG-THƯ (07/09; 2 run no-cancer + cancer-cells; 812 pass)
Đã fix: budget model chia vượt +15..31% tổng → engine scale tỷ lệ về đúng
total_chars khi lệch >10% + sửa budget từng thẻ trên board (click số) + dòng
tổng-vs-mục-tiêu; brief giọng báo-cáo → luật STORYTELLING instruction (≤2 số
đắt nhất) vào cả 2 prompt viết brief; nút ＋ nhanh trên hàng gọn pillar (kho 33
cụm trộn nguyên-tắc + từng-loại-quả — chọn theo loại giờ 1 click/hàng).
GHI NHẬN CHỜ OWNER: (a) bài viết TIẾNG VIỆT — niche mới? Luật brief-EN + bộ
thước deai_en + register đang đo cho EN, mở niche Việt cần chốt riêng; (b) team
tự so hook GLM vs Claude cùng giọng → "GLM khô hơn" — bằng chứng chất lượng
đầu tiên từ team ủng hộ cắm key Anthropic để A/B trong tool; (c) đổi dẫn chứng
hook = góp ý thẻ Hook ("use X stat instead") hoặc popup sửa văn — đã có, cần
phổ biến thao tác.

### 15.18 THÍ NGHIỆM "ÉP GIỌNG LÀM GIẢM CHẤT LƯỢNG?" (07/09, Owner nghi vấn)
Cùng chương (Pakistan C3 Lions), cùng glm-5.2 thinking-off, cùng material+fact,
3 nhánh × 3 lượt: A neo đầy đủ (profile A003) · B bỏ neo giữ V2 · C prompt tối giản.

| | từ/câu | % cụt | dash/1k | dài vs budget 2.800 | phương sai 3 lượt |
|---|---|---|---|---|---|
| A neo đầy đủ | 19,1-19,9 | 6-12% | 0 | hụt (1.9-2.1k) | THẤP NHẤT |
| B bỏ neo giọng | 26-34 | 13-22% | 0-8,6 | 2.4-2.8k | vừa |
| C tối giản | 14-16 | 10-26% | 0 | PHÌNH 3.0-3.2k | vừa |

KẾT LUẬN: (1) Về KỶ LUẬT VĂN, neo đang GIÚP — bỏ neo là em-dash (dấu máy số 1)
quay lại + câu tràng giang 26-34 từ/câu + pattern "Not X. Not Y."; tối giản thì
phình +15% và in cả heading sai format. (2) Nghi ngờ của Owner ĐÚNG MỘT PHẦN về
cảm nhận: nhánh neo cho văn ĐỀU + AN TOÀN, ít câu lóe; B/C có những hình ảnh táo
bạo hơn ("a watch does not pace a patio at two in the morning"). Cái "khô" khả
năng chính là MODEL + stack luật dày, không riêng neo — bản Claude team khen
cũng KHÔNG neo nhưng KHÁC model, chưa tách bạch được nếu thiếu key Claude.
(3) PHÁT HIỆN PHỤ NGHIÊM TRỌNG: nhánh neo-đầy-đủ (prompt 7,8k) RÒ FACT ngoài
material 3/3 lượt (Bilal Mansoor Khawaja / 4.000 thú / 2.500 USD — fact thật thế
giới nhưng CHƯA verify) trong khi prompt tối giản 3,5k = 0/3 → luật material bị
PHA LOÃNG trong prompt dày. Đã thêm nhắc luật cuối prompt — KIỂM LẠI 2 lượt VẪN
RÒ (chặn bằng lời không ăn, tái xác nhận bài học 23/08). VIỆC ĐỀ XUẤT: van MÁY
sau viết — đếm số/tên riêng ngoài material, vi phạm → một vòng sửa có kiểm soát
(cần Owner duyệt vì tốn thêm lượt gọi khi vi phạm).

### 15.19 ĐỢT GIỌNG VĂN — GIẤY PHÉP CÂU LÓE (07/09, Owner chốt hướng)
Chẩn từ 15.18: stack luật toàn lệnh CẤM → văn đều-an-toàn, thiếu cú lóe. Biến
thể VIVIDNESS LICENSE (mỗi phần MỘT hình ảnh/so sánh đậm, bám vật lý của
material; cấm sáo ngữ + em-dash + tuồn số ngoài material). A/B 3 lượt vs 3 lượt
nền, cùng chương Pakistan C3, glm-5.2: dash vẫn 0/1k, cụt 0-17%, nhịp 21-26
từ/câu (lượt 3 hơi vượt — theo dõi); văn CÓ cú lóe thật: "They collect lions." /
"2.500 USD/tháng — roughly what many Pakistani workers earn in a year" / kết mở
"how many more walls are hiding something that shouldn't be there". ĐÃ SHIP vào
build_section_prompt (chỉ khi có material — đúng ngữ cảnh đã đo). n=3, GLM dao
động → theo dõi 2-3 bài team thật trước khi coi là chốt. Việc kế của mạch giọng:
kiểm phủ neo-dày (chon_neo) trên đường viết per-section; Claude A/B khi có key.
