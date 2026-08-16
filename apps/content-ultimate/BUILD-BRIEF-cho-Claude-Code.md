# BUILD BRIEF — TOOL TÁI TẠO GIỌNG VĂN TÁC GIẢ
### Tài liệu bàn giao cho Claude Code (tự chứa). Có thể đổi tên thành `CLAUDE.md` đặt ở gốc repo.

---

## 0. CÁCH DÙNG TÀI LIỆU NÀY
Đây là bản cô đọng của một phiên thiết kế, đủ để Claude Code dựng tool mà không cần đọc lại hội thoại gốc. Hai tài liệu nền sâu hơn nằm cùng thư mục (tùy chọn mang theo):
- `Phuong-phap-luan-tai-tao-giong-van.md` — phương pháp luận v2 (lý do của từng bước).
- `Kien-truc-tool-v3.md` — kiến trúc v3 đầy đủ (sơ đồ luồng + giải thích module).

---

## 1. MỤC TIÊU
Xây tool **lai (Python ↔ LLM) vòng-kín** để: nhập danh sách tác phẩm của một tác giả → tạo **hồ sơ giọng văn có chứng cứ** → cấp cho LLM viết **kịch bản** (ví dụ content vũ trụ tiếng Việt) theo giọng đó, với **vòng tự kiểm chứng & tự sửa** đến khi đạt ngưỡng.
Ca dùng đầu tiên: tác giả **Carl Sagan** (tiếng Anh) → đầu ra **tiếng Việt**.

## 2. BỐI CẢNH & LỊCH SỬ ĐIỂM (để hiểu vì sao thiết kế thế này)
- Hồ sơ giọng văn làm bằng *trí nhớ LLM* (không đọc văn bản thật, tự chấm bằng đoạn tự viết): **4/10**.
- Phương pháp luận v1 → v2 (siết ngưỡng, sửa ca khác ngôn ngữ, đối chứng): **5.3 → 7.9**.
- Kiến trúc lai tĩnh: **8.5**. Kiến trúc v3 vòng-kín (trên giấy): **~9.3**.
- 0.2–0.5 điểm cuối **chỉ đạt được bằng chạy thật** với dữ liệu kênh thật, không bằng thiết kế.

## 3. BA NGUYÊN TẮC BẤT BIẾN (đừng vi phạm khi code)
1. **Tương phản, không mô tả.** Mọi đặc trưng phải được đo *so với baseline*, chỉ giữ cái lệch rõ rệt.
2. **Đo, không cảm.** Số liệu phong cách do **Python** tính (xác định, tái lập). **Không** để LLM tự "ước lượng" con số — LLM bịa số nghe hợp lý.
3. **Kiểm chứng mù, không tự chấm.** Không dùng văn bản do chính hệ sinh ra để chứng minh hồ sơ đúng.

## 4. PHÂN VAI (điểm cốt lõi của kiến trúc)
- **Python lo phần ĐẾM ĐƯỢC** (offline, xác định): thống kê phong cách, tương phản baseline, n-gram đặc trưng, cross-validation, kiểm tra trùng lặp.
- **LLM lo phần HIỂU/SINH ĐƯỢC**: rút signature moves, viết kịch bản, đóng vai giám khảo rubric.
- **Nối hai bên bằng vòng lặp tự sửa có ngưỡng dừng.** Linh hồn nằm trong exemplar gốc → luôn nhúng exemplar cho LLM, không chỉ đưa con số.

## 5. KIẾN TRÚC (8 MODULE — spec để dựng)
1. **Corpus Manager** — nạp 3 corpus: tác giả, baseline cùng ngành, baseline ngôn ngữ-đầu-ra. Chia train/held-out.
2. **Quant Engine (Python)** — phân bố độ dài câu; tần suất hư từ; dấu câu; tỉ lệ POS; TTR; độ dễ đọc; độ cụ thể danh từ; **z-score so baseline** (chỉ giữ đặc trưng phân biệt); n-gram đặc trưng (log-likelihood); **cross-validation** trên held-out (loại đặc trưng chập chờn); **chọn exemplar** tiêu biểu.
3. **Rhetoric Extractor (LLM)** — đề xuất signature moves từ văn bản thật.
   - **3b. Evidence Grounder (Python)** — mỗi move phải dẫn ≥N lần xuất hiện thật; move không lặp bị loại.
4. **Target Spec (trung tính ngôn ngữ)** — trừu tượng hóa đặc trưng *chuyển ngữ được* thành **đích đo lại được** trên đầu ra (tỉ lệ nhịp dài/ngắn, mẫu câu-ngắn-dội, cấu trúc zoom-out→in, mật độ ẩn dụ, thế đứng với người đọc).
5. **Generator (LLM)** — sinh kịch bản theo: target spec + signature moves đã chứng cứ + **exemplar gốc (few-shot)** + chủ đề/format + template kịch bản (hook→leo thang→chốt).
6. **Auto-Validator (vòng kín)** — Python đo lại đầu ra so target (lệch ≤ ±1 SD); anti-plagiarism (không chia sẻ 5-gram với gốc); **judge ensemble ≥3 lượt** qua **calibration gate** (phải phân loại đúng bộ đoạn có nhãn trước khi được tin); **ablation control** (bản tắt đặc trưng phải kém hơn rõ rệt). Chưa đạt → phản hồi có cấu trúc → quay lại (5).
7. **Quality Oracle** — rubric kịch bản + **dữ liệu retention/CTR thật** làm chuẩn vàng khi có. Giọng & chất lượng chấm tách, phải cùng đạt.
8. **Experiment Log** — lưu metric mọi vòng, seed cố định, giữ bản tốt nhất, chống thụt lùi.

## 6. STACK ĐỀ XUẤT
- Ngôn ngữ: **Python 3.11+**.
- NLP tiếng Anh: `spaCy` (hoặc `nltk`). NLP **tiếng Việt**: `underthesea` hoặc `pyvi` (tách từ/câu, POS) — lưu ý tiếng Việt nhiễu hơn, test kỹ tách câu.
- Thống kê: `numpy`, `pandas`, `scipy`/`scikit-learn` (z-score, log-likelihood).
- LLM: gọi qua API (module 3, 5, 6). Muốn **offline hoàn toàn**: chạy LLM nội bộ qua `Ollama`.
- CLI: `typer` hoặc `argparse`. Lưu hồ sơ: JSON.

## 7. HỢP ĐỒNG I/O

### Input
- Thư mục chứa tác phẩm tác giả (`.txt`/`.md`), **văn bản gốc đúng ngôn ngữ tác giả**.
- Thư mục baseline cùng ngành; thư mục baseline ngôn ngữ-đầu-ra.
- Config: ngôn ngữ tác giả, ngôn ngữ đầu ra, N (số lần lặp tối thiểu cho evidence), ngưỡng hội tụ.

### Output — `profile.json` (đề xuất schema)
```json
{
  "author": "Carl Sagan",
  "source_language": "en",
  "output_language": "vi",
  "corpus_stats": { "n_works": 5, "n_tokens": 42000 },
  "quant_features": [
    { "name": "sentence_len_mean", "value": 18.4, "baseline": 15.1,
      "zscore": 2.1, "stable_on_heldout": true, "keep": true }
  ],
  "distinctive_ngrams": [ { "ngram": "we are", "loglik": 31.2 } ],
  "signature_moves": [
    { "move": "zoom-out vũ trụ rồi thu về con người",
      "evidence": ["...trích 1...", "...trích 2..."], "occurrences": 7,
      "type": "signature", "transferable": true }
  ],
  "language_neutral_targets": {
    "long_short_rhythm_ratio": 1.8,
    "short_after_long_rate": 0.22,
    "metaphor_density_per_100w": 1.3,
    "reader_address_stance": "inclusive_we"
  },
  "exemplars": ["...đoạn gốc tiêu biểu 1...", "..."]
}
```

### CLI (ví dụ)
```
voiceprofile build  --author-dir ./sagan --baseline-dir ./baseline_sci \
                    --out profile.json
voiceprofile write  --profile profile.json --topic "Trái Đất nhìn từ xa" \
                    --format "kịch bản video 90s" --out script.md
voiceprofile validate --profile profile.json --script script.md
```

## 8. LỘ TRÌNH (dựng theo thứ tự — MVP trước)
1. **MVP**: module 1–2 + chọn exemplar → xuất `profile.json`. *Chạy được offline ngay trên corpus Sagan.* (Đây là mốc đáng làm đầu tiên — chứng minh đo thật, không phải cảm.)
2. Thêm 3 + 3b → hồ sơ có chứng cứ.
3. Thêm 4–6 → generator + vòng kín tự sửa.
4. Cắm 7 khi có dữ liệu kênh; bật 8.

## 9. TIÊU CHÍ NGHIỆM THU (quy tắc hội tụ)
Một kịch bản coi là ĐẠT khi, duy trì qua **≥2 vòng liên tiếp**:
- Mọi target định lượng nằm trong **±1 SD** vùng tác giả (đo phía ngôn ngữ đầu ra so baseline đầu ra).
- Test phân biệt mù: giám khảo đoán đúng **45–55%** (đã qua calibration gate, ≥3 lượt độc lập).
- Rubric **giọng ≥4/5** VÀ rubric **chất lượng kịch bản ≥4/5**.
- Anti-plagiarism: không chia sẻ 5-gram nào với văn gốc.
- Ablation: bản tắt đặc trưng bị chấm thấp hơn rõ rệt.

## 10. BẠN (NGƯỜI DÙNG) CẦN CUNG CẤP
- [ ] Corpus tác phẩm Sagan (văn bản gốc tiếng Anh).
- [ ] 2–3 tác giả baseline cùng ngành (vd Tyson, Greene) để tương phản.
- [ ] Corpus baseline văn khoa học **tiếng Việt** (cho đo phía đầu ra).
- [ ] API key LLM (hoặc cài Ollama nếu muốn offline).
- [ ] (Tùy chọn, để vượt 9.3) dữ liệu retention/CTR thật từ kênh.

## 11. CẢNH BÁO ĐẠO ĐỨC/BẢN QUYỀN
Tool mô phỏng *phong cách*, không tái bản tác phẩm. Lưu corpus cục bộ cho phân tích cá nhân thì được; **không** phát hành lại văn bản gốc; ghi nhãn đầu ra "lấy cảm hứng từ giọng văn [tác giả]", không gán cho tác giả; thận trọng dùng tác giả còn bản quyền cho mục đích thương mại.

---

## 12. PROMPT KHỞI ĐỘNG (dán vào Claude Code để bắt đầu)
> Tôi muốn dựng một tool Python lai (Python đo lường + LLM sinh) để tái tạo giọng văn tác giả, theo `BUILD-BRIEF-cho-Claude-Code.md` trong repo này (đọc kỹ trước). Bắt đầu từ MVP ở Mục 8.1: module Corpus Manager + Quant Engine + chọn exemplar, xuất `profile.json` theo schema Mục 7. Tuân thủ 3 nguyên tắc bất biến Mục 3 — đặc biệt: Python tính số, KHÔNG để LLM ước lượng số. Đề xuất cấu trúc thư mục, viết code có test cho Quant Engine, rồi chạy thử trên corpus mẫu tôi sẽ cung cấp.
