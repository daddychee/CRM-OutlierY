# NICHE ANALYTICS — Hạng mục yêu cầu tổng quát

> **Công cụ tự sinh BÁO CÁO PHÂN TÍCH NICHE.** User cung cấp danh sách kênh seed + API key → tool tự quét, tự tính, tự xuất báo cáo hoàn chỉnh. User là người đọc và người ra quyết định — không nhập liệu, không tính tay.
>
> **Phân định nhiệm vụ:** Niche Analytics ≠ Radar. Radar (`radar_spec.md`) là công cụ tracking realtime, phát hiện video outlier hàng ngày. Niche Analytics là **bản đồ chiến lược định kỳ** — chụp toàn cảnh niche, đo dịch chuyển, kết luận vào/ra. Hai tool độc lập, có thể dùng chung dữ liệu quét nhưng không phụ thuộc nhau.

## 1. Mục tiêu

1. Từ một danh sách kênh, tự sinh báo cáo phân tích niche đầy đủ — tương đương bộ phân tích đã làm tay cho niche "Life in" (báo cáo dịch chuyển 2023-2026), nhưng chạy lại được bằng một lệnh cho bất kỳ niche nào, bất kỳ ngôn ngữ nào.
2. Báo cáo phải kết thúc bằng **bảng cược** (đề xuất quyết định có điều kiện sai) — không dừng ở mô tả.
3. Chạy lại định kỳ để đo *dịch chuyển giữa hai kỳ báo cáo* — báo cáo sau tự đối chiếu và tự chấm bảng cược của báo cáo trước.

## 2. Đầu vào (tất cả những gì user cung cấp)

- `competitors.txt`: API keys + danh sách kênh (URL /channel/, @handle, /user/ — tool tự resolve).
- Tùy chọn: config ngưỡng/timezone (có default hợp lý, không bắt buộc).

## 3. Hạng mục báo cáo tool phải tự sinh

Mỗi hạng mục: *nguồn dữ liệu → phép tính → output*. Không hạng mục nào chờ user đưa số.

### 3.1. Tổng quan & cấu trúc niche
Số kênh (sống / ẩn video / đã chết), sóng gia nhập theo cohort, sản lượng theo quý, format (duration) theo thời gian, ngôn ngữ. Phát hiện đợt càn quét (nhiều kênh biến mất trong thời gian ngắn).

### 3.2. Outlier & hiệu năng
Mô hình outlier age-adjusted (OX v3: baseline kênh leave-one-out, cửa sổ recent, tách format) — bảng video outlier hợp lệ, excess views, scope, confidence.

### 3.3. Cung–cầu theo theme
Theme trích **tự động** (cluster từ vựng + LLM đặt tên — không hardcode, không phụ thuộc ngôn ngữ). Share sản lượng (cung) đối chiếu hiệu năng trung vị age-adjusted (cầu) theo quý → xếp mỗi theme vào ma trận 4 ô: khoảng trống / sóng đang lớn / bão hòa / chết.

### 3.4. Vòng đời theme
Tốc độ + gia tốc share (có khử xu hướng tăng trưởng nền của niche) → gán pha: mọc / tăng trưởng / bão hòa / tàn, kèm mốc thời gian chuyển pha.

### 3.5. Chất lượng người gia nhập theme
Sức kênh (hiệu năng trung vị của kênh) × thời điểm first-touch theme → pha lây lan EARLY / MASS / LATE — trả lời "mình là người thứ mấy".

### 3.6. Độ tập trung phần thưởng
HHI + top1/top10 share views trong theme → nhãn chiến lược thâm nhập: ĐÁNH CHẤT / LAI / ĐÁNH SỐ.

### 3.7. Tiếng nói khán giả (phía cầu độc lập với creator)
Comment của outlier, sample theo thời kỳ. LLM trích: (a) cụm **câu hỏi chưa được trả lời** = content gap; (b) **cung bậc cảm xúc theo era** = thị trường định giá lại niche (cảnh báo rủi ro hệ thống khi sentiment đổi pha).

### 3.8. Lịch sử sóng & cú sốc
Burst detection theo chủ thể → phân loại Type A (kích hoạt ngoại sinh) / Type B (cascade nội bộ) bằng vân tay thời gian → **half-life sóng của niche** (căn cứ đặt SLA sản xuất) + danh mục biến kích hoạt đã quan sát.

### 3.9. Packaging intelligence
Title template thắng, keyword LIFT (over-index có kiểm định FDR), đường cong lây lan marker (mã nào đang nhờn / mới mọc / còn trống) — đầu vào cho pipeline thumbnail & Double Down.

### 3.10. BẢNG CƯỢC (hạng mục bắt buộc cuối báo cáo)
Tổng hợp 3.3-3.9 theo luật cứng + LLM soạn câu lệnh. Mỗi dòng: `[LỆNH] — căn cứ (hạng mục nào) — ĐIỀU KIỆN SAI — ngày review`. Kỳ báo cáo sau tự chấm cược kỳ trước (đúng / sai / chưa rõ) trước khi ra cược mới.

## 4. Output & tần suất

- **Định dạng:** 1 file markdown tường thuật + 1 workbook xlsx (data sheets) + biểu đồ. Mọi con số trong phần tường thuật phải truy vết được về sheet.
- **Tần suất:** theo lệnh (khảo sát niche mới) hoặc định kỳ tháng/quý (đo dịch chuyển). Không phải công cụ hàng ngày — việc đó của radar.
- **Đích vận hành:** `python3 niche_report.py <competitors.txt>` → ra trọn bộ 3.1-3.10.

## 5. Phân công Code vs LLM

- **Code (Python) tính toàn bộ số liệu:** quét, OX, share, HHI, LIFT/FDR, burst fingerprint, đường cong marker.
- **LLM chỉ làm phần ngữ nghĩa:** đặt tên cụm theme, đọc/gom comment, viết narrative, soạn câu cược từ số có sẵn.
- **Ranh giới cứng: LLM không được sinh số.**

## 6. Nguyên tắc chất lượng bắt buộc (áp cho mọi hạng mục)

1. Mọi so sánh hiệu năng phải age-adjust / chuẩn hóa theo thời điểm đăng (bias snapshot đã đánh lừa phân tích tay 2 lần).
2. Báo cáo tự in **giới hạn dữ liệu**: survivorship (kèm số kênh chết đo được ở 3.1), tầm quét pool, views là snapshot.
3. Kết luận nào cũng kèm điều kiện sai — không có điều kiện sai thì không được in.
4. Ngưỡng/luật mới phải backtest trên lịch sử trước khi đưa vào báo cáo.
5. Brackets/nhãn mang tính heuristic phải được ghi rõ là heuristic — không overclaim.

## 7. Trạng thái hiện thực hóa

| Mảnh | Hiện có | Trạng thái |
|---|---|---|
| Quét + outlier v3 + LIFT + comment gap (3.1, 3.2, 3.7 một phần, 3.9 một phần) | skill `niche-report` (4 scripts) | ✅ chạy được, xuất xlsx — nền móng chính |
| Dịch chuyển theo quý, cohort, pivot kênh (3.1, 3.3, 3.4) | scripts phân tích tay 07/2026 (WORK) | ✅ logic đã kiểm chứng, cần đóng gói thành module |
| TC3/TC4 adopter + HHI (3.5, 3.6) | scripts phân tích tay | ✅ như trên |
| Burst A/B + half-life (3.8) | script phân tích tay (country_bursts) | ✅ như trên, cần tổng quát hóa chủ thể (đang bó theo quốc gia) |
| Sentiment theo era (3.7) | phân tích tay + LLM | ⬜ cần quy trình hóa |
| Theme tự động đa ngôn ngữ (3.3) | đang dùng regex hardcode | ⬜ cần thay bằng clustering |
| Bảng cược tự sinh + tự chấm (3.10) | làm tay | ⬜ |
| Đối chiếu giữa 2 kỳ báo cáo | — | ⬜ |

*Tham chiếu: báo cáo mẫu làm tay = `Bao cao dich chuyen niche 2023-2026.md` (chuẩn đầu ra cần đạt); radar = `radar_spec.md` (công cụ riêng, không thuộc phạm vi file này).*
