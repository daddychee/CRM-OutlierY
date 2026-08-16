# Chạy Radary NỀN trên Windows — dùng bởi Task Scheduler (tác vụ "RadarY", chạy lúc khởi động máy).
#
# VÌ SAO CẦN: scheduler quét của Radary là một thread NẰM TRONG tiến trình app (radary/scheduler.py),
# không phải cron riêng. Tiến trình chết (tắt cửa sổ / restart máy / crash) là lịch quét chết theo,
# và trước đây không có gì bật lại — máy khởi động lại lúc 20:47 mà app chỉ sống lại khi bật tay
# lúc 22:37 → đứt 132 phút không cào (điều tra 29/07/2026).
#
# Script lo 4 việc:
#   1. Chạy app đúng cổng/host đã chốt (8001, 0.0.0.0 — cổng 8000 là của OUTLIERY).
#   2. GHI LOG RA FILE. Trước đây log chỉ in ra cửa sổ terminal nên đóng cửa sổ là mất sạch; chu kỳ
#      chết vì lỗi API không để lại dấu vết nào trong DB lẫn trên đĩa để truy.
#   3. ÉP UTF-8 cho tiến trình con (PYTHONIOENCODING/PYTHONUTF8). BẮT BUỘC: khi stdout bị chuyển
#      hướng ra file, Python mặc định dùng cp1252 nên mọi câu log TIẾNG VIỆT của Radary ném
#      UnicodeEncodeError — lỗi này ném từ trong vòng lặp scheduler, tức là ĐỦ SỨC GIẾT luồng quét.
#      (Kiểm chứng thật 29/07/2026 khi chạy thử script này lần đầu.)
#   4. TỰ CHẠY LẠI khi app thoát bất thường, và NHƯỜNG nếu đã có bản chạy tay giữ cổng — hai tiến
#      trình cùng ghi data\radary.db là đường ngắn nhất tới hỏng dữ liệu.
#
# Chạy tay để thử:  powershell -NoProfile -ExecutionPolicy Bypass -File chay-radary.ps1

$ErrorActionPreference = 'Continue'

$goc = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # ...\deploy\windows → ...\radary
Set-Location $goc

$cong = if ($env:PORT) { $env:PORT } else { '8001' }
$env:PORT = $cong
# 127.0.0.1 từ 30/07/2026: Radary giờ hiện trong khung OUTLIERY qua proxy (/app/radary), nên
# trình duyệt nhân viên KHÔNG cần tới thẳng cổng 8001 — đóng lại thì công ty chỉ còn MỘT cửa
# (cổng 8000), bớt hẳn bề mặt tấn công. Đặt RADARY_HOST=0.0.0.0 nếu cần mở lại.
if (-not $env:RADARY_HOST) { $env:RADARY_HOST = '127.0.0.1' }
$env:PYTHONIOENCODING = 'utf-8'    # xem lý do (3) ở đầu file — KHÔNG được bỏ
$env:PYTHONUTF8 = '1'

# MỘT CỔNG ĐĂNG NHẬP DUY NHẤT (30/07/2026): tin danh tính do OUTLIERY truyền sang, để nhân viên
# chỉ đăng nhập MỘT lần ở OUTLIERY. An toàn vì radary bind 127.0.0.1 và auth.py còn kiểm client
# phải là loopback — header giả từ ngoài không vào được.
if (-not $env:RADARY_TRUST_PROXY) { $env:RADARY_TRUST_PROXY = '1' }
# Trỏ tên đăng nhập OUTLIERY vào ĐÚNG tài khoản radary sẵn có (giữ thiết lập + giới hạn
# niche của họ; VAI thì luôn ĐỒNG BỘ TỪ OUTLIERY mỗi request — sửa 04/08/2026, xem
# radary/auth.py: nhánh map cũ "tôn trọng vai đã cấu hình" làm tick cấp quyền ở bảng
# phân quyền OUTLIERY không chảy sang). Thêm người: nối ";tenOutliery=email@radary".
# Tên KHÔNG có trong danh sách → radary tự tạo <ten>@outliery.local với vai OUTLIERY gửi.
# DỌN 04/08/2026: bảng cũ 30/07 viết theo TÊN ĐĂNG NHẬP CŨ (nam, huonggiang,
# nguyenkhanhhuyen, tranvietthanh, whoami...) — nhân sự nhập lại từ 31/07 nên các tên đó
# hết tồn tại, người dùng thật đã rơi nhánh tự-tạo @outliery.local 5 ngày nay. Chỉ giữ
# 2 map CÒN SỐNG; tên chết phải gỡ kẻo sau này tạo user OUTLIERY trùng tên là dính
# nhầm vào tài khoản radary cũ của người khác.
if (-not $env:RADARY_SSO_MAP) {
    $env:RADARY_SSO_MAP = 'thanh=congthanh267@gmail.com' +
        ';phpthao=workwiththao.91@gmail.com'
}

$thuMucLog = Join-Path $goc 'logs'
if (-not (Test-Path $thuMucLog)) { New-Item -ItemType Directory -Path $thuMucLog | Out-Null }
$nhatKy = Join-Path $thuMucLog 'nen.log'    # nhật ký của TRÌNH CHẠY NỀN (start/exit), gọn

function Ghi([string]$dong) {
    # Out-File -Encoding utf8: toán tử '>>' của PowerShell 5.1 ghi UTF-16, mở ra đọc như rác.
    "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $dong |
        Out-File -FilePath $nhatKy -Append -Encoding utf8
}

function DangChay {
    try { return [bool](Get-NetTCPConnection -LocalPort ([int]$cong) -State Listen -ErrorAction Stop) }
    catch { return $false }
}

function DonLogCu {
    # Log nền chạy 24/7 không được phình vô hạn: giữ 30 file output gần nhất.
    Get-ChildItem $thuMucLog -Filter 'app-*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

$python = Join-Path $goc '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }   # chưa có venv thì dùng python hệ thống

Ghi "=== Trình chạy nền khởi động (cổng $cong · host $($env:RADARY_HOST)) ==="

while ($true) {
    DonLogCu
    if (DangChay) {
        Ghi "Cổng $cong đã có tiến trình khác giữ — nhường, kiểm lại sau 30 giây."
        Start-Sleep -Seconds 30
        continue
    }
    $dau = Get-Date -Format 'yyyy-MM-dd_HHmmss'
    $logRa  = Join-Path $thuMucLog "app-$dau.log"
    $logLoi = Join-Path $thuMucLog "app-$dau.err.log"
    Ghi "Khởi động app → log: app-$dau.log"
    # Start-Process ghi THẲNG byte của tiến trình con ra file (không qua bộ mã hóa của PowerShell);
    # -u để log chảy ra ngay, không kẹt trong bộ đệm. Mỗi lần chạy một file riêng vì Start-Process
    # ghi đè chứ không nối thêm — nối chung một file sẽ mất lịch sử mỗi lần app chạy lại.
    $tt = Start-Process -FilePath $python -ArgumentList '-u', 'server.py' `
        -WorkingDirectory $goc -NoNewWindow -PassThru `
        -RedirectStandardOutput $logRa -RedirectStandardError $logLoi
    $tt.WaitForExit()
    Ghi "App đã thoát (mã $($tt.ExitCode)) — chờ 10 giây rồi chạy lại."
    Start-Sleep -Seconds 10
}
