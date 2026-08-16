# Niche Analytics — Khung đo lường & tiêu chí (ĐO GÌ, VÌ SAO)

> File này là LÝ THUYẾT ĐO LƯỜNG: tiêu chí, khung phân tích, phân tầng tín hiệu.
> Phần THỰC THI (radar chạy thế nào, luật ngưỡng, backtest, vận hành) nằm ở `weekly_report.md` — không lặp lại ở đây.

> Nguyên tắc gốc: **phân tích tiến hóa không đo "mức", nó đo "quan hệ" — và phải kết thúc bằng quyết định, không phải mô tả.**

## A. Bảy tiêu chí

### TC1 — Tách CUNG khỏi CẦU (sống còn)

Cung = share sản lượng của theme. Cầu còn dư = hiệu năng trung vị age-adjusted (views/ngày, OX).

| | Cầu tăng | Cầu giảm |
|---|---|---|
| **Cung thấp/đi ngang** | KHOẢNG TRỐNG → vào ngay | Mỏ cạn thật → bỏ |
| **Cung tăng** | Sóng đang lớn → vào nhanh | BÃO HÒA → tránh |
| **Cung giảm** | Mỏ bị bỏ quên → kiểm tra rồi vào | Chủ đề chết → bỏ |

### TC2 — Đạo hàm, không phải giá trị (timing)

Đo tốc độ (Δshare/quý) và gia tốc của theme. Phân loại pha vòng đời: **mọc → tăng trưởng → bão hòa → tàn**, chỉ hành động theo pha. Tiền nằm ở điểm uốn.

### TC3 — Ai đang làm nó (đường cong lây lan)

Thứ tự lây: innovator → early adopter → đại chúng → vét đáy. Đo **chất lượng kênh mới gia nhập theme**: kênh mạnh vào = EARLY; kênh yếu tràn vào = LATE. Trả lời: *mình là người thứ mấy*.

### TC4 — Độ tập trung phần thưởng (HHI/top10-share views trong theme)

Winner-take-all → đánh CHẤT (phải sớm nhất/hay nhất). Phân tán → đánh SỐ. Quyết định chiến lược thâm nhập trước khi tốn tiền.

### TC5 — Tiếng nói phía cầu độc lập với creator (comment)

TC1-4 đều là dữ liệu creator sinh ra, tự tham chiếu. Comment đo: (1) **câu hỏi chưa được trả lời** = cầu tiềm ẩn → content gap; (2) **cung bậc cảm xúc theo thời kỳ** = thị trường định giá lại niche → rủi ro hệ thống (vd khủng hoảng authenticity thấy trong comment cả năm trước khi nó giết clone farm).

### TC6 — Cú sốc ngoại sinh và chu kỳ bán rã

Đo **half-life của sóng sự kiện**: bao nhiêu ngày thì người đến sau rơi về nền. Niche này: half-life tính bằng NGÀY (Cape Verde: first mover 955K, ngày thứ 5 <3K).

### TC7 — Biết dữ liệu KHÔNG nói được gì (chống tự lừa)

Survivorship bias (video xóa biến mất); snapshot views ≠ quỹ đạo; không có thumbnail lịch sử; tầm quét giới hạn ở danh sách kênh. Mỗi kết luận kèm dòng *"sai trong trường hợp nào"*.

## B. Chuỗi nhân quả của một sóng — và phân tầng tín hiệu sớm

Sóng thị trường đi theo chuỗi, tín hiệu càng ngược dòng càng sớm:

```
[L0] Sự kiện thế giới có lịch trước  →  [L1] Cầu tìm kiếm của công chúng tăng
→  [L2] Video đầu tiên tăng tốc (có thể ngoài tầm quét)  →  [L3] Bầy đàn sao chép  →  chết sóng
```

| Tầng | Tín hiệu | Độ sớm | Nguồn đo |
|---|---|---|---|
| **L0 — Lịch sự kiện** | World Cup, Olympic, bầu cử, mùa (Yakutsk=mùa đông) | **ÂM (biết trước hàng tuần/tháng)** | Lịch công khai + map theme↔mùa |
| **L1 — Cầu công chúng** | Search/pageview về chủ đề tăng đột biến | 0 đến -3 ngày so với video đầu | Wikipedia Pageviews API (free, theo ngày), Google Trends, YouTube autocomplete |
| **L2 — Vận tốc video** | Video vượt ngưỡng OX/tuyệt đối trong tầm quét | +2-4 ngày sau video đầu | Radar tuần (weekly_report.md) |
| **L3 — Bầy đàn** | ≥3 kênh copy trong 1 tuần | Đã muộn — chỉ dùng làm mốc đóng cửa sổ | Radar tuần (marker/INFO) |

**Hệ quả chiến lược:** L0 là tầng duy nhất cho phép làm **first mover có chủ đích** (chuẩn bị video TRƯỚC sự kiện — vd lịch World Cup biết trước hàng tháng). L1 là tầng cảnh báo sớm rẻ nhất chưa khai thác. L2-L3 là vị trí follower nhanh — vẫn ăn được nếu vào ≤72h.

### B.1. Bằng chứng lịch sử cho giả thuyết L0 (kiểm chứng 07/07/2026, data 3 năm)

**GT-Mùa (content lạnh, n=88) — ĐỨNG, hệ số khiêm tốn.**
- Cung: 61% video lạnh đăng T11-T2 (gấp 2.1× mùa hè) — creator đã hành xử theo mùa.
- Cầu (chuẩn hóa theo tháng đăng để khử bias video trẻ): video lạnh đăng đúng mùa đông đạt hiệu năng tương đối **1.28×** vs trái mùa **0.72×** — lợi thế đúng mùa ≈ 1.8×.
- Nuance trung thực: 2/8 outlier lạnh lớn nhất nổ *trái mùa* (Lesotho 4.3M đăng T4, Groenlandia 3.2M đăng T5) → mùa là **gió xuôi**, không phải điều kiện cần; packaging đủ mạnh vẫn thắng trái mùa.

**GT-Sự-kiện-có-lịch (bóng đá) — ĐỨNG MẠNH, và là lợi thế CHƯA BỊ KHAI THÁC.**
- WC 2026: 18 video nhắc giải, TẤT CẢ trong cửa sổ T5-T8/2026 (0 video ngoài); vpd trung vị 445 — cao nhất mọi theme.
- Timeline Cape Verde quanh sự kiện (CV đá WC 23/6): 3 video evergreen 2024-25 trần 38K → **ngày sự kiện 23/6: 376K → 29/6: 955K** → bầy copy 2-4/7 chết dưới 3.2K. Cùng chủ đề, sự kiện nhân hiệu năng ~25×.
- Đối chứng: Euro + Copa América 2024 (cùng loại sự kiện, lịch biết trước) — **0 video** trong toàn niche. Niche đã bỏ lỡ nguyên một sự kiện lớn năm 2024; 2026 mới học được trend-jacking.
- Không kênh nào pre-position Cape Verde dù lịch công khai trước hàng tháng → cửa "first mover có chủ đích" của L0 còn nguyên, chưa ai chiếm.

**GT-Cầu-công-chúng (Wikipedia pageviews, L1) — CHƯA KIỂM CHỨNG.** API không truy được từ môi trường phân tích hiện tại; là việc số 1 khi build L1 (data lịch sử vẫn còn, backtest được với case Cape Verde).

*Điều kiện sai của cả cụm: nếu quét lại với danh mục sự kiện 2027 (lịch thể thao, mùa) mà các cửa sổ sự kiện không cho lift ≥2× nền theme, giả thuyết L0 phải hạ cấp thành "yếu tố phụ".*

### B.2. BIẾN KÍCH HOẠT của L0 (tìm ra 07/07/2026, từ phân tích 62 burst quốc gia)

**Vấn đề:** test L0 thuần lịch cho kết quả sai — lịch mở cửa sổ nhưng không đảm bảo có sóng.

**Phương pháp tìm:** trích quốc gia từ title toàn bộ 5.717 video → tìm 62 cụm nổ (≥3 video, ≥2 kênh, ≤14 ngày, ≥300K views) → phân loại bằng **vân tay cấu trúc thời gian**:

- **Type A — kích hoạt NGOẠI SINH (31 cụm):** nổ gần đồng loạt (gap 0-2 ngày), video ĐẦU TIÊN không phải video đỉnh → các kênh cùng phản ứng với một tín hiệu bên ngoài niche, người thắng là người làm hay nhất chứ không phải sớm nhất tuyệt đối.
- **Type B — cascade NỘI BỘ (15 cụm):** video đầu = video đỉnh, người sau ăn ít dần (gap 2-6 ngày) → một kênh khám phá chủ đề evergreen, còn lại copy. Đây là trò chơi của radar L2, không phải L0.

**Đối chiếu mốc thời gian Type A với tin tức xác minh được:**

| Burst | Ngày | Tin tức trước đó | Độ trễ |
|---|---|---|---|
| Lesotho 4.3M | 05/04/2025 | 02/04/2025 thuế quan "Liberation Day", Lesotho chịu mức cao nhất ~50%; trước đó Trump chế giễu Lesotho là nước "chưa ai từng nghe tên" | **3 ngày** |
| Cape Verde 14 video/12 kênh | 23/06/2026 | Trận World Cup — nước tí hon vô danh đấu người khổng lồ | **0 ngày** |
| Yakutsk/Russia 2.1M | 01/2026 | Kỷ lục lạnh -71°C lên báo | ~ngày |
| Đối chứng âm: Euro 2024 | 06/2024 | Pháp, Đức, Tây Ban Nha — ai cũng biết rồi | **0 video** |

**BIẾN KÍCH HOẠT = CÚ SỐC TÒ MÒ ĐẠI CHÚNG = [độ vô danh của chủ thể] × [đột biến hiện diện trong tin tức].**

Sản phẩm của niche là câu trả lời cho câu hỏi *"cuộc sống ở X thế nào?"* — nên sóng chỉ nổ khi tin tức khiến hàng triệu người **đặt câu hỏi đó về một nơi họ không chỉ được trên bản đồ**. Sự kiện về chủ thể đã nổi tiếng không sinh câu hỏi → không sóng (Euro 2024). Lời chế giễu "chưa ai nghe tên Lesotho" chính là máy phát câu hỏi hoàn hảo — và 3 ngày sau, video trả lời câu hỏi đó ăn 4.3M views.

**Công thức vận hành (L0 + gate):**
1. Lịch sự kiện → shortlist **chủ thể vô danh** tham gia (không phải sự kiện lớn nhất — chủ thể LẠ nhất)
2. Chuẩn bị asset trước (script khung + thumb theo mã niche) — chi phí chìm thấp
3. **CHỈ publish khi gate L1 xác nhận salience spike** (pageviews/news volume của chủ thể vượt N× baseline của chính nó) — trong 0-48h
4. Đo obscurity bằng baseline pageviews thấp; đo spike bằng đột biến tương đối — chủ thể càng vô danh, spike tương đối càng dốc, sóng càng lớn

*Điều kiện sai: nếu ≥50% Type A burst tương lai không kèm salience spike đo được của chủ thể trong 7 ngày trước đó → công thức sai, quay lại tìm biến khác.*

## C. Ba đồng hồ — ba câu hỏi

| Đồng hồ | Câu hỏi | Công cụ |
|---|---|---|
| **Tuần** | Có gì đang mọc? (phát hiện) | Radar (`weekly_report.md`) |
| **Tháng** | Sóng hay nhiễu? (xác nhận) | Cập nhật bảng cược |
| **Quý** | Vào đâu, bỏ đâu? (chiến lược) | Báo cáo dịch chuyển (TC1-4 đầy đủ) |

## D. Ba mục đích duy nhất của research niche

1. **Allocation** — vào theme nào, bỏ theme nào → TC1, TC4
2. **Selection** — làm video gì tiếp → TC5 + thư viện outlier
3. **Timing** — bao giờ vào, bao giờ rút → TC2, TC3, TC6 + tầng L0/L1

## E. Định dạng đầu ra bắt buộc: BẢNG CƯỢC (falsifiable bets)

```
[LỆNH] theme X — căn cứ (tiêu chí nào) — điều kiện sai — ngày review
VD: VÀO tribe quý này — cầu 469 vpd, cung <6% (TC1), EARLY (TC3) — sai nếu 3 video test <30% baseline — review 30 ngày
```

Không có bảng cược = bài văn, không phải công cụ.

---
*Liên kết: `weekly_report.md` (thực thi radar L2 + roadmap L0/L1) · `Bao cao dich chuyen niche 2023-2026.md` (đồng hồ quý, bảng cược hiện hành) · `claude.md` (nguyên lý thumbnail) · folder Double Down (khai thác sau khi bắt được sóng).*
