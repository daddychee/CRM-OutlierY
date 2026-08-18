# Description Definition — Cách sinh Description cho YouTube SEO

> Tài liệu định nghĩa & nguyên tắc cho trụ cột **Description** trong hệ thống SEO Optimize.
> Song song với [tag-definition.md](tag-definition.md).
> Cập nhật: 2026-07-04.

---

## 0. TL;DR — Đọc 1 phút

- Description là đòn bẩy **mạnh hơn Tag** (được index, NLP đọc kỹ, ảnh hưởng ranking/CTR). Đáng đầu tư hơn Tag, nhưng vẫn dưới Title/Thumbnail.
- **125 ký tự đầu** là phần quan trọng nhất (search snippet, trên nút "...more") — chứa **primary keyword tự nhiên**.
- **Standard chỉ là PRIOR, không phải bộ lọc.** Nhiều kênh phá standard nhưng vẫn viral → phải **harvest & thống kê block** từ outlier, giữ **tất cả** variant (standard là một trong số đó).
- Mô hình sinh: pick 1 variant (= rule) → **LLM sinh block sinh động** từ kịch bản, **Python chèn block cố định** từ Channel Profile → validate.
- **Chapters** lấy timestamp từ **SRT** (Python) + tiêu đề (LLM) → tăng AVD tới +11%.
- LLM có thể **giả định lý do variant lệch standard**, nhưng chỉ khi có hậu thuẫn thống kê + output có nhãn hypothesis + cấm khẳng định nhân quả (xem §6).

---

## 1. Description YouTube vận hành thế nào (2026)

- **Được index, NLP đọc semantic** → ảnh hưởng topical relevance & ranking (khác Tag là lever yếu).
- **125 ký tự đầu** (≈ 2–3 dòng, trước "...more") = search snippet, quyết định click.
- **Primary keyword ở câu đầu, tự nhiên.** Keyword stuffing đã chết → trigger spam, hại authority.
- **Độ dài tối ưu: 200–500 từ (~1.000–2.500 ký tự)** — KHÔNG maxing 5.000 (hard limit). Đủ giải thích + link, đủ ngắn để scan.
- **Chapters/timestamps** (video >5 phút): tăng AVD tới **+11%**, tạo "key moments" trong search.
- **Hashtag: 3–5** cái liên quan (hard limit 15; >5 dễ trigger spam; 3 đầu hiện trên title).
- **Channel boilerplate để CUỐI**, không để đầu.

---

## 2. Cấu trúc chuẩn (standard = prior, không phải luật)

Cấu trúc 6–7 block được ưa chuộng (top → bottom):

| # | Block | Vai trò |
|---|---|---|
| 1 | **Hook** (~100 ký tự) | Nói rõ video cho gì + primary keyword tự nhiên |
| 2 | **Summary** | Tóm tắt, đan related terms tự nhiên |
| 3 | **Chapters** | Timestamps (video >5 phút) |
| 4 | **Next video** | Link video nên xem tiếp |
| 5 | **Subscribe CTA** | Link đăng ký |
| 6 | **Important links** | Website, social, affiliate |
| 7 | **Hashtags** | 3–5 cái liên quan |

> ⚠️ Đây là **baseline**. Thứ tự & block nào có mặt do **auto-cluster từ outlier** quyết định, không áp cứng.

---

## 3. Triết lý cốt lõi: Standard là PRIOR, Harvest là REALITY

- Thực tế: có kênh **không theo standard nhưng video vẫn viral** → đó chính là lý do phải harvest thống kê block, không tin standard tuyệt đối.
- **Giữ TẤT CẢ variant** harvest được; standard chỉ là **một variant** nằm cùng.
- Khi pick variant, ưu tiên variant có **hậu thuẫn thống kê** (nhiều outlier dùng + views cao), không phải "đúng standard".

> Song song với triết lý Tag: dữ liệu thực tế lái quyết định, standard/tần suất chỉ là tín hiệu, không phải luật.

---

## 4. Block SINH ĐỘNG vs CỐ ĐỊNH (điểm mấu chốt)

Một description gồm 2 loại block xử lý khác hẳn nhau:

| Loại | Block | Xử lý |
|---|---|---|
| **SINH ĐỘNG** (theo từng video) | Hook, Summary, Chapters | **LLM sinh** từ kịch bản |
| **CỐ ĐỊNH** (thuộc về kênh) | Subscribe CTA, Important links, Social, Disclaimer, (Hashtag set) | **Python chèn** nguyên văn từ Channel Profile |
| **BÁN-ĐỘNG** | Next video link | Python chèn từ playlist/next-video của kênh |

> ⚠️ **LLM KHÔNG được "sáng tác" block cố định** — nó sẽ hallucinate URL affiliate, bịa tên sản phẩm. Cực nguy hiểm với kênh thật. Link/CTA phải lấy từ **Channel Profile** khai báo 1 lần/kênh.

---

## 5. Chapters từ SRT (Python timestamp + LLM tiêu đề)

Vì kịch bản đã có chương + xuất được SRT → dùng timestamp chính xác, không để LLM đoán giờ:

```
File SRT (kịch bản có chương)
      ↓ Python
Parse SRT → khớp mốc chương với timestamp → (start_time, đoạn text)
      ↓ LLM
Đặt tiêu đề chapter ngắn gọn, SEO-aware (CHỈ tiêu đề, không đụng timestamp)
      ↓ Python
Format `0:00 Tiêu đề` + validate luật chapter YouTube:
   • bắt đầu 00:00  • ≥ 3 chapter  • mỗi chapter ≥ 10 giây  • thứ tự tăng dần
```

Lưu ý: SRT là cue phụ đề nhỏ, không phải ranh giới chương → Python khớp heading chương của kịch bản với timestamp SRT (match theo text). Nếu kịch bản đã gắn timestamp/chương thì bỏ qua bước khớp.

---

## 6. Grounded Hypothesis — LLM giả định lý do variant lệch standard

**Khả thi, nhưng phải chặn bẫy rationalization ảo** (LLM luôn bịa ra lý do nghe hợp lý kể cả khi không có).

**Nguyên tắc: tách QUAN SÁT (Python, sự thật) khỏi DIỄN GIẢI (LLM, giả thuyết).**

```
Python (sự thật): mỗi variant → block có/vắng, thứ tự, độ dài
                  + SUPPORT (bao nhiêu outlier, median views)
                  + DEVIATION vs standard
      ↓ chỉ chuyển variant đạt ngưỡng (vd ≥3 outlier)
LLM (giả thuyết CÓ NHÃN): lý do khả dĩ + confidence + evidence + caveat
```

**4 rule để hypothesis không thành bịa:**
- **G1** — Chỉ giả định **pattern lặp lại** (≥ N outlier), không giả định trên 1 video.
- **G2** — Output là **hypothesis có nhãn + confidence + evidence**, không phải fact. Không có evidence → "không rõ lý do".
- **G3** — **Cấm khẳng định nhân quả.** Ngôn ngữ: "có thể / tương quan với", KHÔNG "vì / khiến".
- **G4** — **Human-in-the-loop.** Hypothesis hỗ trợ user chọn variant, KHÔNG tự động lái quyết định.

**Schema variant:**
| Trường | Ai điền | Ví dụ |
|---|---|---|
| skeleton | Python | `HOOK→CHAPTERS→LINKS→HASHTAGS` (bỏ SUMMARY, CTA) |
| support | Python | 6 outlier, median 480k views |
| deviation vs standard | Python | −SUMMARY, −CTA, CHAPTERS lên trước LINKS |
| hypothesis | LLM | "Có thể tối giản để đẩy chapters lên trên — *conf: vừa*" |
| evidence | LLM | "6/8 outlier niche này theo dạng này" |
| caveat | LLM | "Description lever yếu; có thể do CTA nằm trong video" |

---

## 7. Phân công Python vs LLM (kiến trúc tool)

| Giai đoạn | **Python** (xác định, theo luật) | **LLM** (phán đoán ngữ nghĩa) |
|---|---|---|
| Harvest | lấy description outlier qua API | — |
| Block extraction | regex tách timestamp/URL/hashtag, đo độ dài | phân loại block prose mơ hồ (hook vs summary) |
| Auto-cluster variant | gom skeleton, đếm support, tính deviation | — |
| Hypothesis | gác ngưỡng, cấp số liệu support | giả định lý do (có nhãn, §6) |
| Sinh block động | — | Hook, Summary từ kịch bản + keyword |
| Chapters | trích timestamp SRT, format, validate luật | đặt tiêu đề chapter |
| Block cố định | chèn từ Channel Profile | — |
| Validate | đếm ký tự, keyword, hashtag, chapter | — |

**Nguyên tắc:** Python lo phần đếm được/theo luật; LLM lo phần cần hiểu ngữ nghĩa; luôn **validate output LLM**.

---

## 8. Pipeline & Validate

```
[Outlier descriptions] ─► Block extraction (Python regex + LLM)
                          ─► Auto-cluster → N variant + support + deviation + hypothesis
                                    ↓
        User pick 1 variant (= rule: thứ tự block + độ dài + vị trí keyword)
                                    ↓
   ┌─ Block động ──► LLM sinh (Hook, Summary) + Chapters (SRT+LLM)
   └─ Block cố định ──► Python chèn (Next video, CTA, Links, Hashtag) từ Channel Profile
                                    ↓
                          Ghép + VALIDATE (Python)

VALIDATE:
  • Tổng 1.000–2.500 ký tự (cảnh báo >3.000; hard cap 5.000)
  • primary keyword trong 125 ký tự đầu
  • hashtag 3–5 (cảnh báo >5; loại nếu >15)
  • chapters đúng luật (00:00 · ≥3 · ≥10s · tăng dần)
  • không keyword stuffing (mật độ keyword hợp lý)
  • block bắt buộc không rỗng; link cố định khớp Channel Profile
```

---

## 8b. Multi-variant (xuyên suốt)

Mỗi video tái sử dụng qua nhiều giai đoạn → Description phải xuất **nhiều bản khả dụng**, không chỉ 1. Nguồn đa dạng:
- **Nhiều format variant** (§3–4): cùng 1 kịch bản sinh nhiều bản theo các skeleton khác nhau (hook-nặng-keyword, story-driven, chapter-heavy...).
- **Nhiều bản hook/summary** cho cùng một variant (đổi góc mở đầu).

→ Khi re-up **cùng 1 video**, chọn variant/hook khác đủ nhiều để **né trùng metadata**. Block cố định (link/CTA) giữ nguyên từ Channel Profile; chỉ block sinh động đổi.

---

## 9. Nguồn tham khảo

- [Touhfa — YouTube Description Best Practices 2026](https://touhfa.art/blog/seo/youtube-description-guide/)
- [VidIQ — YouTube Video Descriptions 2026](https://vidiq.com/blog/post/youtube-video-descriptions/)
- [InfluenceFlow — Metadata & Descriptions Guide 2026](https://influenceflow.io/resources/youtube-metadata-and-descriptions-the-complete-2026-creators-guide-to-video-discoverability/)
- [ClickMinded — YouTube Description Template](https://www.clickminded.com/templates/seo/youtube-description-template/)
- [Sprout Social — Engaging YouTube Descriptions](https://sproutsocial.com/insights/youtube-descriptions/)
