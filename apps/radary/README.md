# DAILY RADAR — Hướng dẫn vận hành

Radar video outlier theo `radar_spec.md` v3. Đã init và chạy thử thành công 07/07/2026 (77 kênh, 6.364 video, alert đầu tiên: T2 Tristan da Cunha).

## 1. Cài lên máy 24/7 (một lần)

1. Copy **toàn bộ folder Thumbnail** (hoặc tối thiểu: `daily_radar.py` + `radar_state/`) sang máy chạy 24/7. Cần Python 3.9+ (chỉ dùng thư viện chuẩn, không cài gì thêm).
2. File `radar_state/competitors.txt` chứa API key + danh sách kênh — đã có sẵn. Muốn thêm/bớt kênh: sửa file này rồi chạy `python3 daily_radar.py init` (init không xóa dữ liệu cũ).
3. Đặt cron chạy mỗi 30 phút:

```
crontab -e
# thêm dòng (sửa đường dẫn cho đúng):
*/30 * * * * cd /duong/dan/toi/Thumbnail && python3 daily_radar.py >> radar_state/daily/cron.log 2>&1
```

Máy Windows: dùng Task Scheduler, action = `python daily_radar.py`, repeat 30 phút, start in = folder Thumbnail.

## 2. Bật push điện thoại (ntfy) — 3 phút

1. Cài app **ntfy** (App Store / Google Play).
2. Mở `radar_state/daily/config.json`, xem dòng `ntfy_topic` — topic riêng của bạn đã được sinh ngẫu nhiên (dạng `radar-lifein-xxxxxxxxxxxx`). **Không đổi thành tên dễ đoán** — topic ntfy công khai theo tên.
3. Trong app ntfy: Subscribe to topic → nhập đúng topic đó.
4. Trong `config.json` đổi `"ntfy_enabled": false` → `true`.
5. Xong. Từ giờ T2/T3/T4 sẽ kêu điện thoại: title, kênh, VPH, VPD, tuổi, hạng cohort, link.

## 3. Đọc output

| File | Là gì | Nhịp |
|---|---|---|
| `radar_reports/radar_board.md` | Bảng trạng thái: cohort D0-D6 xếp theo VPH, bảng VPD-cao-mọi-tuổi, heartbeat + lịch job kế tiếp | Ghi đè mỗi lần chạy |
| `radar_reports/alerts.log` | Nhật ký thăng/hạ bậc (chỉ ghi khi CÓ thay đổi) | Append |
| `radar_reports/weekly/` | Báo cáo tuần: sổ cái sóng + kết cục + phân phối VPH để chỉnh sàn | Chủ nhật 08:00 |
| `radar_state/daily/cron.log` | Log kỹ thuật | — |

Đọc nhanh: mở `radar_board.md` — dòng đầu là heartbeat (giờ chạy cuối; nếu cũ hơn 1 tiếng nghĩa là cron chết). Ký hiệu `~` trước VPH = ước lượng (video <2h dữ liệu).

## 4. Ý nghĩa bậc (nhắc lại từ spec)

| Bậc | Nghĩa | Bạn làm gì |
|---|---|---|
| T1 | Top 20% cohort, ≥~10K/24h | Không làm gì — radar tự quét dày hơn |
| T2 | Top 3 cohort, ≥~30K/24h | **Push.** Chuẩn bị asset (khung script + neo thumb) |
| T3 | Top 1 cohort, ≥~100K/24h, đã xác nhận 20 phút | **Push.** Kích hoạt sản xuất 8h |
| T4 | ≥~300K/24h | **Push tức thì.** Cân nhắc 2 góc đánh |

## 5. Chỉnh ngưỡng (sau 2 tuần chạy sống)

Mở `radar_state/daily/config.json`: `T1_vph/T2_vph/T3_vph/T4_vph` (sàn VPH), `T2_daily_cap` (trần push T2/ngày), `allages_vpd_floor` (sàn bảng VPD mọi tuổi). Báo cáo tuần sẽ in phân phối VPH thực (P50/P90) để đối chiếu — đó là căn cứ chỉnh, không chỉnh theo cảm giác.

## 6. Lệnh tiện ích

```
python3 daily_radar.py status   # đếm video theo bậc + lịch job
python3 daily_radar.py init     # resolve lại kênh sau khi sửa competitors.txt
```

## 7. Sự cố thường gặp

- **Board không cập nhật:** xem heartbeat + `cron.log`. Thường do cron sai đường dẫn hoặc máy sleep.
- **In `PAUSE — chạy lại để tiếp`:** bình thường — lần cron kế tiếp tự chạy nốt (job lớn được chia nhỏ).
- **Quota 403:** script tự xoay 2 key; nếu cả 2 cạn (hiếm — radar dùng ~1K/20K units/ngày) thì chờ reset 0h giờ Thái Bình Dương.
- **Video bị xóa giữa chừng:** tự đánh dấu `dead`, giữ lịch sử (video nổ rồi biến mất cũng là tín hiệu).
