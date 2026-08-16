# METHODOLOGY — Outline Extractor (v4, cluster board — user tự pick)

> v4 hạ kỳ vọng có chủ đích (quyết định của user 2026-07-03): KHÔNG tin PY+LLM tự pick được
> outline tốt. Tool chỉ làm việc nó chắc chắn làm tốt — **tổng hợp bằng chứng thành một bảng
> cluster có phân loại**, để USER tự pick và tự ghép outline. Cùng triết lý với Outlier
> Discovery: "không score, không model — analyst tự chọn". Bản v1 lưu ở `METHODOLOGY.md.bak`.

## Bài toán

**Input:** danh sách link video cùng một chủ đề/sóng trend (add link vào `videos.txt`,
convention giống `competitors.txt`: trộn API key + URL/ID).
**Output:** **board GUI web-local** — Python mở server chỉ bind `127.0.0.1` rồi tự mở browser
(user vẫn double-click Start.command/Start.bat như các tool khác; user chốt 2026-07-03 sau khi
thử mockup HTML — ưu tiên kéo-thả mượt, Tkinter không đáp ứng được). Mỗi cluster một dòng với
**tick box** + các cột bằng chứng ĐỘC LẬP (không trộn thành 1 điểm, không xếp hạng hộ). Tick chọn → tool **tự động xuất**:
- `outline.txt` — bản SẠCH (tên mục + mô tả), đưa thẳng vào Author Extract;
- `outline_evidence.md` — cùng outline nhưng kèm citation đầy đủ, cho người review;
- `picks.json` — trạng thái tick, mở lại GUI giữ nguyên lựa chọn.
Không xuất xlsx.

**Ranh giới cứng (như "không score" của Outlier Discovery):** tool KHÔNG tự chọn cluster nào
vào outline, KHÔNG gộp các cột thành một điểm tổng, KHÔNG sắp thứ hạng "tốt nhất". Mọi yêu cầu
đi theo hướng đó phải dừng lại hỏi user.

## Nguyên tắc vàng (kế thừa Niche Research §0)

**Python làm mọi thứ ĐO ĐƯỢC, LLM làm mọi thứ PHẢI HIỂU.**

- Python: tải data, tìm điểm nhô, đo tương đồng (embeddings), đếm mọi tín hiệu, dựng bảng.
- LLM: chia beat, đặt tên cluster, tóm tắt câu hỏi khán giả. Không chấm điểm, không khuyên
  "nên pick cái nào".
- LLM không tự viết timestamp (beat neo theo chỉ số dòng transcript, Python quy đổi);
  LLM không bịa số; mọi nhãn LLM gắn phải kèm trích dẫn Python verify được.

## Các cột phân loại của bảng cluster

3 cột gốc user đề ra + các cột gợi ý thêm. Mỗi cột trả lời MỘT câu hỏi, đo độc lập:

### Nhóm A — cốt lõi (bắt buộc có từ MVP)

| Cột | Trả lời câu hỏi | Cách đo (Python) |
|---|---|---|
| `coverage k/N` | Ý này lặp ở bao nhiêu video? (khung chung của sóng) | Đếm số video có ≥1 beat thuộc cluster |
| `peak ✦ (z×w)` | Ý này trùng điểm nhô Most Replayed? | Peak loại `value` overlap beat của cluster; ghi z-score × source_weight lớn nhất |
| `questions (n)` | Khán giả đặt câu hỏi liên quan? | Lọc comment chứa dấu hỏi/từ để hỏi → embedding-match về cluster gần nhất (ngưỡng cosine); đếm + giữ 3 câu tiêu biểu |
| `pos 0.xx` | Ý này thường nằm ở đâu trong video? | Median vị trí tương đối (t_start/duration) qua các video — giúp user tự xếp thứ tự outline |
| `top-video ★` | Có mặt trong video mạnh nhất bộ input? | Cluster chứa beat của video có source_weight cao nhất |

### Nhóm B — gợi ý thêm từ comment (rẻ, cùng một lần tải comment)

| Cột | Trả lời câu hỏi | Cách đo |
|---|---|---|
| `quoted (n)` | Khán giả trích lại nguyên văn câu thoại nào? | Comment chứa chuỗi khớp transcript (fuzzy match ≥ ~8 từ) → câu đắt, nguyên liệu hook |
| `timestamped (n)` | Comment nhắc mm:ss rơi vào cluster? | Parse mm:ss trong comment (dedupe ghim + reply chain) → map về beat |
| `debate ⚡` | Ý này gây tranh cãi? | Comment khớp cluster chứa pattern phản đối ("sai", "không đúng", "nhưng mà"...) vượt tỷ lệ ngưỡng — cờ cảnh báo kèm cơ hội engagement, user tự cân nhắc |
| `requests (n)` | Khán giả xin nội dung gì tiếp? | Comment dạng "làm video về X đi" → KHÔNG vào bảng cluster, gom vào bảng phụ **NEXT IDEAS** (ý tưởng video sau, không phải mục outline) |

### Nhóm C — gợi ý thêm từ metadata (miễn phí, đã có sẵn từ S1)

| Cột | Trả lời câu hỏi | Cách đo |
|---|---|---|
| `title-match 🏷` | Ý này được chính creator đưa lên title? | Keyword cluster khớp word-boundary với title ≥1 video — phần đã được packaging hóa, tức creator tin nó bán được click |
| `chapter-match` | Creator tự đặt chapter cho ý này? | Tên cluster khớp tên chapter (field `chapters`) — cách chính creator tóm tắt cấu trúc video |
| `confusion ⚠` | Video gốc trình bày rối ở ý này? | Peak loại `confusion` (tua lại vì khó hiểu — phân loại 2 lớp: Python loại `navigation` theo chapter, LLM phân xử value/confusion kèm trích dẫn verify) — cơ hội: cùng ý nhưng mình nói rõ hơn |
| `trend ↑` (optional, tắt mặc định) | Keyword đang rising? | Google Trends query cùng batch + anchor keyword; pytrends dễ vỡ nên chỉ là cột phụ, lỗi thì bỏ trống |

### Bảng phụ GAPS — câu hỏi không thuộc cluster nào

Câu hỏi khán giả không match được cluster nào (dưới ngưỡng cosine) = **nhu cầu chưa video nào
trong sóng trả lời** — gom thành bảng GAPS riêng. Đây thường là chỗ đáng giá nhất cho video
của mình: lấp lỗ hổng mà không phải rời khung sóng.

## Pipeline 5 giai đoạn

### S1 — Ingest (Python)
`videos.txt` → metadata (YouTube Data API) + `source_weight` từ CSV tool trước (fallback
log-view) + transcript có timestamp (transcriptapi.com / caption track) + comments + chapters.
Ghi: `videos.json`, `transcripts/`, `comments/`.

### S2 — Peak detection (Python)
Heatmap 100 bucket (yt-dlp `--write-info-json`); bỏ ~5% đầu/detrend; đỉnh = local max
prominence z ≥ 1.0 so với chính video đó; cửa sổ transcript = max(±45s, ±1.5 bucket);
loại `navigation` theo chapter ngay tại đây. Ghi: `peaks.json`.

### S3 — Beat extraction & peak labeling (LLM)
Chia beat neo `seg_start_idx/seg_end_idx`; phân xử peak thành 4 loại kèm trích dẫn (Python
verify chuỗi tồn tại — pattern Evidence Grounder của Author Extract, default `value` khi không
verify được):
- `value` — xem lại vì hay → vào điểm.
- `confusion` — tua lại vì khó hiểu → loại điểm, giữ làm ghi chú "làm rõ hơn".
- `navigation` — điểm nhảy chapter → loại.
- `sponsor` — **đoạn quảng cáo tài trợ** → loại. Cần thiết vì dữ liệu thật (run bigbang,
  video LbLLWmmL3YE) cho thấy đỉnh Most-Replayed MẠNH NHẤT (z=5.14) rơi trúng đoạn sponsor
  ("protect the oceans… your contribution… YouTube channel"). Python bắt sơ bộ bằng cụm từ
  sponsor phổ biến ("sponsor", "promo code", "use code", "thanks to … for supporting") +
  vị trí (thường phút 1–2 hoặc giữa video), LLM xác nhận. Nếu không lọc, sponsor sẽ giả làm
  "đoạn hay nhất" và bơm điểm peak sai cho cluster.

Join peak↔beat: max overlap, tất định. Ghi: `beats.json`.

### S4 — Cluster & đếm tín hiệu (Python) + đặt tên & viết brief (LLM)
Embeddings cluster beat cross-video (tái lập được — pattern S9/S9b Niche Research); Python đếm
TOÀN BỘ các cột A/B/C ở trên; match câu hỏi/quote comment về cluster bằng embeddings.
LLM viết cho mỗi cluster:
- **Tên cluster** — sẽ thành tiêu đề chapter (`CHAPTER n — <tên>`).
- **Brief 2–4 câu** theo giọng chỉ dẫn nội dung ("Introduce... / Explain... / Reveal..."),
  đúng văn phong mẫu outline của user — mô tả CẦN KỂ GÌ, dựa trên các beat trong cluster,
  không thêm ý ngoài bằng chứng. **Ngôn ngữ brief/tên cluster/beat summary = TIẾNG ANH** (user
  chốt 2026-07-04: mọi outline luôn tiếng Anh, ghi đè luật "= ngôn ngữ video" — vì outline đi
  vào Author Extract English→English). UI/log của tool vẫn tiếng Việt; chỉ deliverable tiếng Anh.
Ghi: `clusters.json`.

### S5 — Board GUI (web-local: Python server + browser) & auto-compose
- **Kiến trúc:** Python stdlib `http.server` bind `127.0.0.1` (không expose LAN) + 1 file HTML/JS
  tĩnh (giao diện đã chốt bằng mockup) + vài endpoint JSON (`/clusters`, `/picks`, `/save`).
  Không asset CDN — mọi thứ đóng gói local, chạy offline. `Start.command`/`Start.bat` khởi động
  server rồi `webbrowser.open` — trải nghiệm double-click y hệt các tool khác.
- **Board:** bảng 1 dòng = 1 cluster: tick + các cột nhóm A/B/C; click header để sort theo cột
  bất kỳ (không có sort mặc định theo "độ tốt"); **header cột có tooltip giải thích ý nghĩa**
  (bài học mockup: cột phải tự giải thích, không bắt user tra tài liệu); link evidence mở tab
  YouTube đúng `&t=743s` xem đoạn thật trước khi quyết; kéo thả dòng vào slot, kéo đổi thứ tự
  chapter (có vạch chèn), kèm nút ↑/↓. GAPS và NEXT IDEAS là tab riêng.
- **Panel "Outline của tôi":** cluster đã tick rơi vào 3 loại slot — **HOOK** (1 slot) ·
  **CHAPTER 1..N** (danh sách, nút ↑/↓ đổi thứ tự) · **ENDING** (1 slot). Gán slot mặc định
  bằng dữ liệu đo được (nhãn beat hook/payoff/CTA từ S3 + `pos`: nhỏ nhất → gợi ý HOOK,
  lớn nhất → gợi ý ENDING), user kéo/đổi slot tùy ý — gợi ý theo số đo, quyết định của user.
  Ô nhập **Title** ở đầu panel (tool không sáng tác title — packaging ngoài phạm vi; user tự
  nhập hoặc dán từ production queue của Content Verdict). HOOK/ENDING trống → cảnh báo đỏ
  trong GUI nhưng vẫn xuất phần đã có, không chèn placeholder vào file.
- **Auto-compose:** MỖI lần tick/bỏ tick/đổi slot/thứ tự → ghi lại ngay (ghi đè, idempotent):
  - `outline.txt` — bản SẠCH cho Author Extract, **format khóa cứng** (hợp đồng — đổi phải
    hỏi user):

    ```
    Title: <user nhập trong GUI>

    HOOK
    <brief 2–4 câu của cluster ở slot HOOK>

    CHAPTER 1 — <tên cluster>
    <brief 2–4 câu>

    CHAPTER 2 — <tên cluster>
    <brief 2–4 câu>
    ...
    ENDING
    <brief 2–4 câu của cluster ở slot ENDING>
    ```

    Đánh số chapter tự động theo thứ tự panel; dòng trống giữa các block; KHÔNG lẫn citation
    (citation trong input sinh văn chỉ làm nhiễu LLM phía sau);
  - `outline_evidence.md` — song song, mỗi mục kèm `[video_id @ mm:ss · peak z×w · k/N · pos]`
    + ghi chú ⚠ confusion — dấu vết truy ngược không bao giờ mất;
  - `picks.json` — trạng thái tick + thứ tự, GUI mở lại khôi phục đúng phiên làm việc.
- Compose là bước LẮP RÁP thuần Python — không LLM, không thêm bớt ý.
- Pipeline chạy từ GUI qua subprocess, log stream theo dòng (`PYTHONUNBUFFERED=1`) đẩy về
  browser (SSE hoặc polling đơn giản) — script chạy lâu phải in tiến độ định kỳ, không để GUI
  trông như treo (bài học Niche Research).

## Ghi chú từ video thật đầu tiên (đo 2026-07-03, id TGRxwskKn10, Space Matters, 2M view)

Kiểm chứng trên video thật trước khi code (luật B1) lộ 3 điều định hình các stage:

- **Heatmap OK:** yt-dlp trả `heatmap` = 100 bucket `{start_time, end_time, value 0..1}`,
  bucket = duration/100 (ở đây 17.3s). Bucket đầu 0.83 cao nhất → xác nhận artifact
  "ai cũng xem từ đầu". S2 tìm 9 đỉnh, mạnh nhất @06:45 z=3.23. **Nhưng:** `--dump-single-json`
  bị YouTube trả "page needs to be reloaded"; phải dùng `--write-info-json` ra file tạm
  (đã cô lập trong `oe/heatmap.py`).
- **Caption THƯỜNG VẮNG:** video 2M view này KHÔNG có caption nào (kể cả auto) → transcript
  không thể dựa vào caption track, transcriptapi.com (tốn credit) là đường CHÍNH không phải
  fallback. Tách transcript ra stage riêng có credit.
- **Chapters THƯỜNG NULL:** video này `chapters=null`, description cũng không có timestamp →
  lọc `navigation` bằng chapter chỉ chạy khi video CÓ chapters; không có thì bỏ qua êm, dồn
  gánh value/confusion cho S3 (LLM). `is_navigation` mặc định False.

## Giới hạn biết trước (MVP có chủ đích)

- Heatmap không có trong Data API chính thức, chỉ có ở video đủ view — video trong sóng mới
  vài ngày có thể chưa có heatmap → cột peak bỏ trống, các cột comment/coverage vẫn chạy.
  Lấy heatmap cô lập trong MỘT module (dễ vỡ khi YouTube đổi format); pytrends cô lập tương tự.
- Phân loại value/confusion là suy luận có kiểm chứng trích dẫn, không phải ground truth —
  nhãn luôn đi kèm bằng chứng để user tự cân nhắc.
- Câu hỏi/quote match bằng embeddings có ngưỡng — sẽ sót và sẽ nhầm một ít; con số n là ước
  lượng dưới (chỉ đếm cái match chắc), không phải đếm đủ.
- Không dịch; tiếng transcript = tiếng video input.
- Tool không đảm bảo outline hay — nó đảm bảo mọi lựa chọn của user đều có số liệu thật đứng sau.

## Vị trí trong hệ tool

```
Outlier Discovery → Niche Research → Content Verdict → [Outline Extractor] → Author Extract → RoughCut
   (tìm video hot)    (chọn niche)     (chọn topic)      (bảng cluster, user pick) (giọng văn)   (sản xuất)
```

Phục vụ mô hình network đánh trend: 1 board cho cả sóng → nhiều account, mỗi account pick
tổ hợp cluster hơi khác nhau (cùng khung, khác skin — Andrew §4.1/§4.6), cột GAPS cho 20%
video test (§4.2 80/20).
