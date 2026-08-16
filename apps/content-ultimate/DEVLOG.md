# DEVLOG — Author Extract

Nhật ký tiến độ: mỗi mục = một phần cải tiến hoặc fix bug, mới nhất ở trên.
Ngày theo định dạng YYYY-MM-DD.

---

## 2026-07-04 — Self-profile đo ổn định theo ĐOẠN, không theo số file

Người dùng đưa **1 quyển sách >50k từ (1 file)** nhưng tool cảnh báo "pool không đủ" —
vì self-profile đo ổn định theo *số văn bản* (mỗi file = 1 điểm), 1 file = 1 điểm =
không tính được spread. Chốt (đúng nguyên tắc "đo, không cảm" — con số vẫn do Python
tính, chỉ đổi ĐƠN VỊ đo):

1. **Cắt corpus thành đoạn ~4.000 từ** (`chunk_by_words`) làm đơn vị đo ổn định. Chỉ
   đổi sang đo-theo-đoạn khi cắt ra **nhiều đoạn hơn số file** (vd 1 sách dày → ~12
   đoạn); corpus vốn nhiều file / quá ngắn để cắt giữ nguyên cách chia theo file như cũ
   (bảo toàn hành vi cũ, test nhỏ vẫn xanh). `profile.py`: `CHUNK_WORDS=4000`,
   `_split_units` (train/held-out xác định trên đoạn → giờ có held-out để kiểm chứng mù),
   `reproduction_targets` + n-gram đo trên cùng đơn vị đoạn. `corpus_stats` thêm
   `n_stability_units`.
2. **Extract chỉ show kết quả, ẩn quá trình**: bỏ dòng giải thích self-profile mode dài
   dòng trong CLI; **chỉ cảnh báo khi corpus THẬT SỰ ngắn** (`< MIN_STABLE_UNITS=5` đoạn).
   Sách 50k từ → 12 đoạn → **không cảnh báo**; corpus ~1.3k từ → 1 đoạn → vẫn cảnh báo.

Kiểm chứng: sách tổng hợp 46.447 từ (1 file) → 12 đoạn, không cảnh báo, 8 target; corpus
1.300 từ → 1 đoạn, có cảnh báo. 82 test xanh. Đồng bộ `profile.py`+`cli.py` sang bản Windows.

---

## 2026-07-03 — Hook tách khỏi giọng tác giả (phương án 2)

Người dùng: hook viết theo giọng Sagan "chưa được" — hook YouTube có nhiệm vụ riêng.
Chốt: **hook = tầng platform thuần, KHÔNG dùng giọng tác giả.** `build_hook_prompt`
riêng (không exemplar/signature_moves): ngắn, trực diện, câu ngắn nhịp nhanh mạnh, mở
curiosity loop, **bao quát TITLE**. Độ dài **250-500 ký tự** (~15-25 giây; sửa từ nhầm
"250-400 từ" → user xác nhận ký tự). Chapter/End giữ nguyên giọng tác giả. Truyền title
vào prompt hook để bao quát tiêu đề. 80 test xanh.

---

## 2026-07-03 — FIX hồi quy chất lượng: quy ước thời lượng chặt làm phẳng văn

Người dùng phát hiện bản mới (code sau VĐ4) viết kém hơn bản cũ. Đo được: cùng nội dung
Chapter 1, bản cũ 3.757 ký tự (12k tổng, 2 chương → ~3.000/chương) vs bản mới 2.263
(6.5k tổng, 3 chương → ~1.858/chương). Câu dài tương đương (18.4 vs 17.9) — không phải
lỗi câu ngắn mà là **chương bị ép quá ngắn → LLM nén → cắt hình ảnh/mệnh đề → phẳng**.

Vùng ngọt chất lượng 1 chương: ~2.500-4.000 ký tự. Dưới sàn → nén phẳng; trên trần →
trôi giọng. Ba fix (đúng nguyên tắc độ-hay > con-số):
1. **Prompt độ dài mềm** (chapter/end): "nhắm khoảng N nhưng ƯU TIÊN khai triển đầy đủ,
   giàu hình ảnh — cứ dài hơn nếu cần, đừng nén phẳng". Hook giữ "tight & punchy".
2. **Cảnh báo chương quá ngắn** (<2.500): "nên giảm số chương hoặc tăng tổng ký tự".
   Song song cảnh báo >4.000 đã có.
3. **Nới hook** 425 → 500 (khoảng 400-600) để hook có chút không gian.
- 79 test xanh (thêm test cảnh báo ngắn, prompt mềm).

---

## 2026-07-03 — Writer: thêm ô "Lưu kịch bản" + nút Save as

Trước đó Writer tự đặt script.md trong folder profile (chưa cho user chọn). Thêm ô
"Lưu kịch bản (.md)" + nút **Save as…** (filedialog): chọn tác giả → gợi ý mặc định
`{folder profile}/script.md`, user Save as để đổi. `start()` dùng đường dẫn user chọn;
outline.txt + checkpoint đặt cạnh file theo tên (nhiều kịch bản 1 folder không đè nhau).

---

## 2026-07-03 — Header thông tin ở đầu file kịch bản

`render_header` thêm front-matter đầu `script.md`: Giọng văn (tác giả), Độ dài yêu cầu,
Độ dài thực tế, Viết bằng (LLM + model). `validate.strip_front_matter` bỏ qua header
khi đo để không nhiễu số liệu. 77 test xanh.

---

## 2026-07-03 — Làm xong 4 vấn đề (VĐ4 + VĐ1 + VĐ2+3)

- **VĐ4 — Thời lượng:** `allocate_section_chars` (hook cố định 425, end clamp 7%/500-1200,
  body chia đều cho chương). `min_chapters_for` + cảnh báo khi chương >4000 (không tự
  chia, chương là đơn vị bảo toàn). Trạng thái rõ: "Đang viết Chapter 2/5 · X/tổng ký tự".
- **VĐ1 — Cấu trúc + registry:** `library.py` — sổ `library/index.json` trong folder
  tool, mã `A001_Tên`, `ensure_author`/`register_profile`/`list_authors`. Bỏ hardcode
  `AUTHOR_ROOT`; corpus + output tự do. CLI `build` tự đăng ký. GUI Extractor gợi ý
  folder `A001_Tên`, Writer đọc registry cho dropdown.
- **VĐ2+3 — Checkpoint/resume:** `save/load/clear_checkpoint` (`{out}.progress.json`,
  khóa theo hash outline). `generate_script` nhận `done_sections` (skip phần đã có) +
  `on_section_done` (lưu checkpoint mỗi chương). CLI `write --continue/--fresh`. GUI
  thêm nút **↻ Tiếp tục**; pills đánh dấu phần đã có từ checkpoint. Fix: bỏ check
  `":" in outline` (sai với format không dấu hai chấm) → dùng parse_outline.
- 75 test xanh (thêm test_library, test_checkpoint, test allocate/parse).

---

## ĐÃ CHỐT (spec 2026-07-03) — 4 vấn đề, thứ tự VĐ4 → VĐ1 → VĐ2+3

**VĐ4 — Thời lượng chapter (làm trước):**
- Hook: cố định ~425 ký tự (khoảng 400-450), KHÔNG scale theo tổng.
- End: clamp(7% × tổng, min 500, max 1200 ký tự).
- Body: (tổng − hook − end) chia ĐỀU cho số chương trong outline (chương tương đồng).
- **Chương là ĐƠN VỊ BẢO TOÀN** — mỗi chương một lượt sinh nguyên vẹn, KHÔNG tự chia
  sub-beat. Nếu mỗi chương tính ra >4000 ký tự → **CẢNH BÁO** (gợi ý số chương tối
  thiểu), KHÔNG tự sửa. User tự chia outline nhỏ hơn.

**VĐ1 — Cấu trúc & registry:**
- Bỏ hardcode `AUTHOR_ROOT = /Users/daddychee/Desktop/Author`. Corpus + output do user
  tự chọn đường dẫn tự do.
- Sổ đăng ký `index.json` ĐẶT TRONG FOLDER TOOL (vd `library/index.json`).
- Mã tác giả: `A001`, `A002`... folder profile `A001_Ten` (slug). Dùng lại mã nếu tên
  đã có; mã mới nếu tên mới.
- Writer đọc registry để hiện dropdown (vẫn cho Browse tới profile.json bất kỳ).

**VĐ2+3 — Checkpoint / trạng thái / resume:**
- Mỗi chương viết xong → ghi ngay checkpoint `{out}.progress.json` (outline, provider,
  total_chars, các phần đã xong {heading: body}).
- Thanh trạng thái: "Đang viết Chapter 2/5 · 6.200/12.000 ký tự".
- Nút **WRITE** (viết lại từ đầu) + **Tiếp tục** (chạy tiếp từ checkpoint) tách riêng
  như tool Niche Research.

**CTA:** để sau, bàn chiến lược riêng (chưa code).

**Ràng buộc:** mục tiêu là ĐỘ HAY của văn, điểm % chỉ tham khảo (memory
goal-is-quality-not-score). Tên tool = Author Extract.

---

## 2026-07-03 — FIX BUG: parser outline không nhận format thật (viết ra = outline)

Người dùng báo: nhập outline mà tool "không viết" — script.md chứa nguyên văn outline.
Tái hiện: `parse_outline` trả **0 section** với format thật của người dùng
(`# Title`, `HOOK ...`, `CHAPTER 1 — ...`, `ENDING ...`) vì parser cũ bắt buộc dấu `:`
và không nhận em-dash `—`, markdown `#`, hay outline viết liền không xuống dòng.

- Viết lại `parse_outline`: tìm mốc từ-khóa (`_SECTION_MARK`) trên toàn văn bản bằng
  `finditer` — nhận có/không dấu `:`, em/en-dash, `#`, hoa/thường, và cả khi outline
  không xuống dòng. Phần trước mốc đầu = Title (strip `#` và nhãn `Title:`).
- Tăng cường prompt sinh: nói rõ brief là **DÀN Ý cần khai triển**, LLM phải viết prose
  đủ độ dài, KHÔNG sao chép/liệt kê lại brief. (Nguyên tắc người dùng: outline chỉ là
  dàn ý, LLM phải viết ra độ dài yêu cầu.)
- Thông báo lỗi rõ hơn khi outline không có section nào (kèm ví dụ khung).
- 64 test xanh (thêm test cho format không-dấu-hai-chấm, một-khối, và outline rỗng).

---

## 2026-07-03 — Cải thiện Hướng 1: nới luật câu, ưu tiên độ hay hơn điểm

Người dùng chốt triết lý: **mục tiêu là độ hay của văn, điểm % chỉ tham khảo** (kịch
bản hay mà điểm thấp vẫn OK). Đã ghi vào memory.

- Sửa `YOUTUBE_RULES` trong `generator.py`: bỏ luật ép câu ngắn "sentences sayable in
  one breath" ở Chapter — thay bằng hướng dẫn giữ NHỊP của tác giả (câu dài nhiều mệnh
  đề, xen câu ngắn), cấm làm phẳng thành câu ngắn/từ đơn giản. Hook giữ punchy nhưng
  trong giọng tác giả; End giữ giọng đến câu cuối. **Không nhồi con số target vào prompt**
  (tránh tối ưu theo điểm) — chỉ hướng dẫn về phẩm chất giọng.
- Lý do: bản v1 (GLM) đạt 29% chủ yếu vì câu ngắn hơn Sagan (14.8 vs 21.2) và dễ đọc
  hơn (flesch 72 vs 51) — do chính luật câu-ngắn tự cài. Nới luật để văn tự nhiên theo
  giọng tác giả hơn.
- 62 test vẫn xanh. Chạy lại `script_v2.md` để so v1/v2.
- **Kết quả v1 → v2 (GLM, cùng outline):** 29% → **50%**. Đặc trưng "dày" nhích về Sagan:
  sentence_len 14.8 → 18.5 (đạt band), function_word đạt, flesch 72.5 → 66.7 (khó đọc
  hơn, gần Sagan hơn). Văn v2 câu dài quét rộng đúng nhịp Sagan (định tính tốt hơn hẳn).
  Còn trượt: flesch/avg_word_len/ttr/noun_specificity — là "gu từ vựng" của GLM (từ đơn
  giản), thuộc đặc tính model → Hướng 2 (thử Claude) sẽ nhắm vào đây.

---

## 2026-07-03 — Func 2 (Writer): sinh kịch bản YouTube theo giọng tác giả

Xây Function 2 theo spec đã chốt: outline (Title/Hook/Chapter 1..n/End) + chọn Author
từ thư viện + độ dài + chọn LLM → sinh tuần tự từng phần (chống trôi giọng) → ghép một
file `script.md` → đo một lần trên bản cuối (X/14 target = Y%). Prompt có lớp luật
YouTube (hook mở loop, chương giữ nhịp, end đóng loop); giọng câu do profile quyết.

### Đã làm
- [x] `llm.py`: `.env` thành kho key (nhiều provider cùng lúc); 4 provider
      Claude/GLM/OpenAI/Gemini (3 sau qua endpoint OpenAI-compatible dùng chung
      `_openai_chat`); thêm `llm_text()` cho sinh văn bản tự do bên cạnh `llm_json()`.
- [x] `generator.py` (Module 5): parse outline (Title/Hook/Chapter N/End), sinh tuần
      tự từng phần với neo giọng (exemplar + moves ở system) + nối mạch (đuôi 60 từ
      phần trước), lớp luật YouTube theo loại phần.
- [x] `validate.py` (Module 6, phần đo): đo script cuối vs reproduction_targets, công
      bằng độ dài (`targets_for_length` đo lại target trên cửa sổ cùng cỡ script), báo
      X/N = Y%, target trượt xếp lên đầu.
- [x] CLI: lệnh `write` + `validate`; `rhetoric` chuyển sang `--provider` chọn từ kho key.
- [x] GUI: 2 tab (Extractor + Writer) + sơn màu theo mockup (theme clam, accent vàng)
      + dãy pill tiến độ theo chương cho Writer.
- [x] **Fix bug:** `RoundedButton` ban đầu đặt `self._w`/`self._h` — trùng thuộc tính
      nội bộ Tkinter (widget path), làm hỏng `pack`/`delete`. Đổi thành `self._cw`/`_ch`.
      Thêm guard `winfo_exists()` trong `_draw` tránh vẽ lại sau khi canvas bị hủy.
- [x] Nút bấm bo tròn bằng Canvas tự vẽ (`RoundedButton`) vì ttk không hỗ trợ
      border-radius; primary vàng, hover/disabled đổi màu.
- [x] Test: 62 test xanh (thêm test_generator, test_validate, cập nhật test_llm/test_gui).
- [x] Chạy thật một kịch bản Sagan end-to-end bằng GLM: sinh 3 phần (Hook 1567 +
      Chapter 1683 + End 1483 ký tự, khớp target ~1500), ghép `script.md` 4814 ký tự,
      validate công bằng độ dài → **4/14 target = 29%**.

### Kết quả nghiệm thu (trung thực)
- Pipeline hoạt động đúng cơ chế: sinh theo chương, neo giọng, ghép file, đo, báo %.
- **Văn định tính TỐT** (bắt rõ moves: "Every forest ends. Every ocean meets a shore",
  "north of the North Pole" analogy, inclusive "we") **nhưng định lượng chỉ 29%.**
- Nguyên nhân lệch (đúng như dự đoán khi thảo luận voice-vs-YouTube): kịch bản
  **dễ đọc hơn Sagan** (flesch 72.5 vs 50.9), **câu ngắn hơn** (14.8 vs 21.2 từ),
  **từ ngắn hơn** — lớp luật YouTube "sayable in one breath" kéo về phía dễ đọc.
- Nhiễu do văn bản ngắn: các đặc trưng punct thưa (semicolon/em_dash/hyphen/paren) có
  sd rất nhỏ nên band hẹp, dễ trượt trên 872 từ. Đặc trưng "dày" (sentence_len, flesch,
  ttr, function_word) là tín hiệu đáng tin hơn — và chúng cho thấy pattern nhất quán.
- **Ý nghĩa:** vòng đo đã làm đúng việc — nếu chỉ dán prompt, người dùng đọc thấy "hay"
  và tưởng đạt; số liệu cho biết nó thực sự dễ đọc hơn Sagan ~40%. Đây là thông tin để
  quyết định sửa hay chấp nhận. 29% là bản NHÁP một-lượt, chưa qua vòng sửa (Phase 3).

### Hướng cải thiện đã xác định (chưa làm — chờ người dùng)
- Phase 3 (auto-revise): đưa target trượt làm phản hồi, sinh lại chương gây lệch.
- Thêm hướng dẫn giữ câu dài hơn cho phần non-hook (giảm xung đột độ dài câu).
- Thử Claude thay GLM (có thể bắt giọng tốt hơn cho bản chốt).
- Cân nhắc chỉ chấm/đánh trọng số các target "dày" khi kịch bản ngắn.

---

## 2026-07-03 — Func 1 (Extractor) hoàn thiện (nền cho Func 2)

- Self-profile mode: bỏ yêu cầu baseline, giữ đặc trưng ổn định nội tại (cv ≤ 0.30 +
  bền held-out), xuất `reproduction_targets` ±1 SD. Fix `noun_specificity_proxy` (loại
  từ đầu câu), chuẩn hóa khoảng cách chọn exemplar, báo cáo trung thực `stable_on_heldout`.
- Module 3 (Rhetoric Extractor) + 3b (Evidence Grounder): LLM đề xuất signature moves,
  Python xác minh từng trích dẫn với corpus (chuẩn hóa chống nhiễu OCR); move thiếu
  chứng cứ bị loại.
- Provider LLM: Anthropic Claude + GLM (z.ai), chọn qua `.env`.
- GUI Tkinter + `Start.command`. Đổi tên hiển thị thành **Author Extract**.
- Dọn cấu trúc thư mục: tool universal, corpus/kết quả tác giả nằm ở
  `/Users/daddychee/Desktop/Author/`.

## 2026-07-04 — FIX bug: file corpus không phải UTF-8 (Word/cp1252) làm build crash

Người dùng chạy build cho David Attenborough → `UnicodeDecodeError: byte 0x95` (bullet
của Windows-1252, file xuất từ Word). `load_corpus_dir` đọc cứng utf-8. Thêm
`read_text_any`: thử utf-8 → utf-8-sig → cp1252 → latin-1 (latin-1 đọc được mọi byte).
Verify: file Attenborough (53.530 từ) trước crash giờ đọc OK. 82 test xanh.

## 2026-07-04 — Giao diện web (thay Tkinter) — đồng bộ phong cách Outline Extract

Người dùng muốn GUI đẹp như Outline Extract (dùng web GUI, không phải Tkinter). Chuyển
Author Extract sang cùng kiến trúc:
- `server.py`: `http.server` bind 127.0.0.1 (không lộ LAN), chạy pipeline qua subprocess
  trong thread, frontend poll `/api/status`. API: build / write / library / detect-corpus
  / pick-folder / pick-save (native macOS qua `osascript`, tránh xung đột thread Tkinter)
  / checkpoint / open.
- `board.html`: tự chứa, mượn palette Outline Extract (nền tối `#0E1117`, accent vàng
  `#E3AC45`, **dark/light tự động** theo hệ thống, font Avenir Next). 2 tab Extractor +
  Writer với thanh tiến độ, pills theo chương, panel verdict %, log.
- `Start.command` mở web trong trình duyệt; entry point `author-extract`. Tkinter
  (`author-extract-gui`) giữ làm fallback; server dùng lại hàm thuần từ `gui.py`.
- Verify: server serve board.html + /api/status + /api/library OK; build chạy qua web
  tạo profile.json thành công; detect-corpus trả tên + folder `A001_Tên` đúng. 82 test xanh.

## 2026-07-04 — CLAUDE.md cập nhật đầy đủ + bản cài Windows độc lập

- **CLAUDE.md:** cập nhật trạng thái (Func 1+2 xong), `.env` = kho key (không phải công
  tắc), giao diện web, thêm mục "Function 2 — quyết định thiết kế đã chốt" (hook tách
  giọng, độ hay > điểm, vùng ngọt chương, checkpoint), sửa A2 (bỏ hardcode AUTHOR_ROOT
  → corpus/output tự do + registry A001), B2 (Module 5,6 đã build).
- **Bản Windows độc lập** ở folder `Author Extract (Windows)` (KHÔNG ghép chung bản mac):
  copy toàn bộ code (trừ .venv/.env/library/cache); patch `server.py` + `gui.py` cho
  cross-platform — folder/file picker qua **Tkinter trong subprocess riêng** (thay
  osascript của mac; có main-thread riêng nên an toàn), mở file qua `os.startfile`
  (Windows) / open / xdg-open. Thêm `Start.bat` (tự cài venv lần đầu + chạy server),
  `.env` template (không key), `README-Windows.txt`. Verify: tạo venv riêng → 82 test
  xanh, server serve board.html + /api/status OK, không còn osascript. Đã dọn venv/cache
  để giao bản sạch.

## 2026-07-09 — Phương pháp 3 tầng kiểm soát độ dài (thay prompt ký-tự-mềm)

**Vấn đề (user báo + đo thật):** script Norway yêu cầu 25k ra 43,5k (174%); từng chương
5.526-8.649 ký tự vs vùng ngọt 2.500-4.000; End 3.000 vs clamp 1.200. Mâu thuẫn
"viết ngắn thì phẳng, viết hay thì dài".

**Chẩn đoán:** LLM không đếm được ký tự khi viết → mọi chỉ thị ký tự (kể cả mềm) đều
không kiểm soát được. Độ dài = SỐ Ý × độ khai triển; brief từ board nhồi 4-7 ý/chương.
Mâu thuẫn là giả: cố định độ khai triển (luôn đầy đủ), điều tiết SỐ Ý.

**Thí nghiệm trước khi code** (scratchpad, cùng glm-5 + hồ sơ A003 + outline run):
prompt ngân-sách-3-ý, không nhắc ký tự → chương 1 = 3.735 ký tự MỘT lượt (giữa vùng
ngọt, không cần vòng sửa); bản cũ 5.526. File: Desktop/So-sanh-Norway-3-tang.md.

**Chốt 3 tầng:** (1) `outline_scope_report` — Python ước ý brief (heuristic ~58 ký
tự/ý, hiệu chỉnh từ 2 brief thật) vs `idea_budget` (~1.250 ký tự/ý đo từ thí nghiệm,
clamp 2-4; end min 1) — cảnh báo lúc nạp outline (UI `/api/outline-check`) + đầu
generate; user quyết. (2) prompt chapter/end giao "AT MOST K ý, khai triển đầy đủ,
hết ý dừng", không nhắc ký tự. (3) vượt trần ×1.15 → MỘT vòng `build_scope_cut_prompt`
"bỏ hẳn ý, không nén" (tối đa 1 lượt LLM phụ/phần; hook miễn). Phân biệt rõ với
Module 6 auto-revise theo điểm — vẫn không làm.
