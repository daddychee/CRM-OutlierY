# Radary chạy nền 24/7 trên Windows

> Dựng ngày 29–30/07/2026 sau khi điều tra "app không tự cào data theo lịch".

## Vì sao cần cái này

Scheduler quét của Radary **là một thread nằm trong tiến trình app** (`radary/scheduler.py`, khởi
động ở `radary/api.py`), **không phải cron hay Task Scheduler riêng**. Hệ quả: tiến trình chết là
lịch quét chết theo — tắt cửa sổ, đăng xuất, restart máy, app crash đều làm ngừng cào, và trước
đây **không có gì bật lại**.

Bằng chứng lúc điều tra: máy khởi động lúc 20:47 nhưng app chỉ sống lại lúc 22:37 (do bật tay) →
lịch sử chu kỳ quét **đứt đúng 132 phút**. Bản thân scheduler thì hoạt động tốt: 13.026 chu kỳ
trong DB, các pool vẫn cào đều **khi app còn sống**.

## Cách đang chạy

| Thành phần | Giá trị |
|---|---|
| Tác vụ Windows | `RadarY` (Task Scheduler) |
| Kích hoạt | Lúc khởi động máy (**At startup**) — không cần ai đăng nhập |
| Chạy dưới tài khoản | `SYSTEM` |
| Script | `deploy\windows\chay-radary.ps1` |
| Cổng · host | `8001` · `0.0.0.0` (cổng 8000 là của OUTLIERY — **không được đụng**) |
| Log | `logs\nen.log` (trình chạy nền) · `logs\app-<ngày_giờ>.log` + `.err.log` (output app) |

Script tự chạy lại app sau 10 giây nếu app thoát, và **nhường** nếu cổng 8001 đã có tiến trình
khác giữ (không mở bản thứ hai — hai tiến trình cùng ghi `data\radary.db` là đường ngắn nhất tới
hỏng dữ liệu). Giữ 30 file log gần nhất.

## Lệnh hay dùng

```powershell
Get-ScheduledTask -TaskName 'RadarY'                    # còn sống không (State = Running)
Stop-ScheduledTask  -TaskName 'RadarY'                  # dừng hẳn (kể cả app con)
Start-ScheduledTask -TaskName 'RadarY'                  # bật lại
Get-Content 'C:\OutlierY\apps\radary\logs\nen.log' -Tail 20        # nhật ký bật/tắt
Get-ChildItem 'C:\OutlierY\apps\radary\logs' -Filter 'app-*.log' | # log quét mới nhất
  Sort-Object LastWriteTime -Desc | Select -First 1 | Get-Content -Tail 40
```

## Hai cái bẫy đã dính, đừng dính lại

1. **File `.ps1` phải lưu UTF-8 CÓ BOM.** PowerShell 5.1 đọc script không BOM theo cp1252 nên chữ
   tiếng Việt vỡ, kéo theo dấu nháy hỏng → script không parse được, tác vụ kết thúc ngay với
   `LastTaskResult = 1` mà không để lại log nào.

2. **Phải đặt `PYTHONIOENCODING=utf-8` (script đã đặt sẵn).** Khi stdout bị chuyển hướng ra file,
   Python mặc định dùng cp1252, nên mọi câu log **tiếng Việt** của Radary ném `UnicodeEncodeError`.
   Lỗi này ném từ bên trong vòng lặp scheduler → **đủ sức giết luồng quét**. Chạy trong cửa sổ
   terminal thì không thấy, chỉ lộ ra khi bắt đầu ghi log ra file.

Ngoài ra PowerShell 5.1 ghi file bằng `>>` ra **UTF-16** (mở lên đọc như rác) — script dùng
`Out-File -Encoding utf8` và `Start-Process -RedirectStandardOutput` để tránh.

## Việc còn để ngỏ (chưa làm)

- **Chu kỳ chết vì lỗi API không để lại dấu trong DB.** `scan.API.get` xoay key khi gặp 403/429;
  hết key để xoay thì ném `RuntimeError`, `scheduler._loop` chỉ `print` rồi bỏ qua cả chu kỳ —
  bảng `cycles` không có dòng nào. Giờ ít nhất đã có **log file** để truy; muốn truy được từ DB
  thì thêm một dòng tag `ERROR` vào `cycles` (~5 dòng trong `scheduler.py`).
- **Có một khoảng đứt 51 phút (22:44 → 23:35 ngày 29/07) trong khi tiến trình vẫn sống**, chưa rõ
  nguyên nhân. Nghi một chu kỳ nặng giữ `LOCK` lâu (pool Space 198 kênh, một chu kỳ refresh 4.243
  video; scheduler chạy tuần tự, mỗi lúc một chu kỳ). Có log file rồi thì lần tới xem được.
- Key API `#4` (loại "dùng chung", không gắn pool) đang `403 quotaExceeded` và do sắp xếp
  `ORDER BY backup, id` nên nó **đứng đầu danh sách của mọi pool** → chu kỳ nào cũng tốn một lần
  gọi hỏng rồi mới xoay key (note "đã phải xoay API key" ở mọi bản ghi). Chủ dự án đã quyết
  **chưa xử lý** vì mỗi niche đều đã có key riêng.
