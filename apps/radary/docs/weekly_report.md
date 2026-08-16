# Weekly Radar — Đặc tả thực thi (CHẠY THẾ NÀO)

> File này là THỰC THI: luật ngưỡng đã chốt, kết quả backtest, vận hành, roadmap.
> Phần LÝ THUYẾT (7 tiêu chí, phân tầng tín hiệu L0-L3, ba đồng hồ) nằm ở `niche_analytics.md` — không lặp lại ở đây.

## 1. Nhiệm vụ & phạm vi

Radar = tầng **L2** trong chuỗi tín hiệu (xem `niche_analytics.md` §B): phát hiện vận tốc bất thường trong tầm quét 77 kênh, nhịp TUẦN. Nguyên tắc: độ trễ phát hiện < cửa sổ khai thác (3-7 ngày). Đo *vận tốc sớm*, không đo hiệu năng cuối.

Bốn đối tượng bắt + SLA: sao băng chủ đề/sự kiện (≤72h) · mã packaging lan (≤2 tuần) · kênh mạnh gia nhập/pivot (≤2 tuần) · điểm gãy cầu theme (≤3 tuần).

## 2. Luật cảnh báo ĐÃ CHỐT (từ backtest 07/2026)

| Bậc | Điều kiện | Hành động gắn sẵn |
|---|---|---|
| **ALARM-OX** | Video ≤7 ngày, OX≥10× baseline kênh, ≥50K views, VÀ (kênh mạnh HOẶC token mới 90 ngày) | Double Down + thumbnail pipeline trong 72h |
| **ALARM-ABS** | Views/ngày lọt top 0.5% toàn niche (bắt sóng trên kênh baseline cao — bài học Yakutsk) | Kiểm tra chủ đề trong 72h |
| **WATCH** | Gia tốc cung theme z>2σ · ≥3 kênh mạnh first-touch 1 theme/14 ngày · video cũ hồi sinh (Δviews/tuần ≥20K và ≥5× nền) | Theo dõi 2 tuần, chuẩn bị kịch bản |
| **INFO** | Marker title lan ≥3 kênh/28 ngày | Ghi sổ — mã đang lan, dùng trước khi nhờn |

Tải dự kiến: ~2-4 ALARM/tháng. Precision đo được 12% = SÀN (định nghĩa "sóng" của backtest đếm thiếu — case Cape Verde bị tính "không sóng" vì bầy theo sau chết, trong khi chính nó là cơ hội lớn nhất kỳ).

## 3. Kết quả backtest (30 tháng, 2024-01→2026-07)

- Luật ngây thơ (OX đơn thuần) BỊ BÁC BỎ: precision 5% ở mọi ngưỡng 5×/10×/20× → 14-21 báo giả/tháng.
- Luật kép: 3.4 alarm/tháng ở precision 12% (kênh mạnh) — chốt như §2.
- Đối chiếu sự kiện chuẩn: Cape Verde kêu ~25-26/6 (trước video 955K ngày 29/6, trước bầy clone chết 2-4/7) ✓ SLA 72h · Mã "Life in" bắt đúng quý ra đời (Q1/2024) ✓ · Tribe kêu từ 12/2024 ✓ · Yakutsk gốc LỌT LƯỚI ở luật OX → sinh ra luật ALARM-ABS.
- WATCH cung theme: world_cup kêu đúng tuần 29/06/2026 ✓; life_in kêu từ 08/2023.
- Thiên lệch backtest: (1) dùng views cuối → radar live trễ thêm 2-4 ngày so mô phỏng; (2) precision 12% là sàn; (3) sức kênh dùng full-history (nhìn tương lai nhẹ).
- Dữ liệu: `backtest_alarms.json` (423 alarm mô phỏng).

## 4. Kiến trúc pipeline (đã xây — `weekly_radar.py`)

- **Delta hai-snapshot:** mỗi lần chạy lưu views theo ngày → Δviews giữa 2 lần quét = cầu-đang-diễn-ra (giải giới hạn snapshot TC7).
- Quét gia tăng: video mới (playlistItems) + refresh stats video ≤56 ngày + watchlist outlier cũ.
- State: `radar_state/` (videos.json, watchlist.json, alerts_log.json, competitors.txt). Resumable — chạy lại đến khi in DONE.
- Output: `radar_reports/YYYY-MM-DD.md` — 1 trang, ALARM trước, mỗi dòng có căn cứ + hành động + link.
- Vòng tự chấm (Bước 6): mọi alert log với trường `scored=null` → 30 ngày sau chấm đúng/sai → chỉnh ngưỡng.

## 5. Trạng thái & lần chạy đầu (07/07/2026)

- [x] Backtest + chốt ngưỡng
- [x] `weekly_radar.py` chạy DONE — 19 alerts: **sóng TRIBE đang nổ** (3 ALARM độc lập: 605K/7d 39×, 272K/7d 29×, Naga) — khớp cược #1 bảng cược · Cape Verde 955K (35×) · Tristan da Cunha ABS 59K views/ngày.
- [ ] Vá known issues: (1) loader chỉ đọc URL `/channel/UC...` → 63/77 kênh có theo dõi video mới, kênh `@handle` chưa; (2) WATCH cung theme chưa khử xu hướng tăng trưởng nền → kêu rộng; (3) máy dò hồi sinh cần snapshot thứ 2 (thức dậy từ tuần sau).
- [ ] Đặt lịch tự chạy sáng thứ Hai (chờ quyết định).
- [ ] **Roadmap tầng sớm hơn (xem niche_analytics.md §B):** L1 — bổ sung Wikipedia Pageviews API (free, theo ngày, không cần key) cho danh sách chủ đề/quốc gia: cầu công chúng tăng đột biến TRƯỚC khi video đầu tiên kịp chín; L0 — lịch sự kiện biết trước (thể thao, bầu cử, mùa) map với theme để pre-position làm first mover có chủ đích.

## 6. Giới hạn (chống tự lừa)

Mù với video xóa trước lần quét kế · không thấy CTR/impression đối thủ · không thấy sóng sinh ngoài danh sách kênh (cân nhắc search.list định kỳ để tự mở rộng tầm quét) · task đặt lịch chỉ chạy khi app Claude mở (chạy bù khi mở lại).

## 7. Vận hành

- Chạy tay: `python3 weekly_radar.py` trong folder Thumbnail, lặp đến khi DONE (~2 lần, ~5 phút).
- Quota: ~vài trăm units/lần, 2 key hiện có dư dả.
- Nhịp đọc: sáng thứ Hai, 2 phút, chỉ đọc `radar_reports/` file mới nhất.
