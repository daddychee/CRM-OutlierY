# -*- coding: utf-8 -*-
<#
  BẢN THỬ FINANCE HUB — chạy song song bản thật để sửa trong giờ làm việc.

  Vì sao cần: app to-chuc thật ở cổng 9103 đang phục vụ team; restart nó là làm
  gián đoạn mọi người. Bản thử có tiến trình riêng, dữ liệu riêng, cổng riêng —
  restart bao nhiêu lần cũng không ai bị ảnh hưởng.

  KHÁC BẢN THẬT ba điểm, cố ý:
    · dữ liệu   data/thu-nghiem-finance  (BẢN SAO — ghi vào đây không đụng team)
    · cổng      9203 app, 9204 cổng vào
    · danh tính cổng vào tiêm sẵn Owner nên khỏi đăng nhập, ĐỔI LẠI phải có
                khóa trong URL và chỉ nghe LAN nội bộ.

  Dùng:  .\finance-thu-nghiem.ps1            bật (hoặc restart nếu đang chạy)
         .\finance-thu-nghiem.ps1 -Tat       tắt hẳn
#>
param([switch]$Tat)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = Join-Path $root '.venv\Scripts\python.exe'
$congApp = 9203
$congVao = 9204

function Dung-Cong([int]$cong) {
  # CHỈ dừng theo CỔNG đang nghe — không bao giờ Stop-Process theo tên
  $c = Get-NetTCPConnection -LocalPort $cong -State Listen -ErrorAction SilentlyContinue
  if ($c) {
    Stop-Process -Id $c.OwningProcess -Force
    Start-Sleep -Milliseconds 800
    Write-Host ("[-] da dung cong {0}" -f $cong)
  }
}

Dung-Cong $congApp
Dung-Cong $congVao
if ($Tat) { Write-Host "[=] ban thu da tat. Ban that o 9103 khong bi dung toi."; exit 0 }

$thu = Join-Path $root 'data\thu-nghiem-finance'
if (-not (Test-Path $thu)) { throw "Chua co ban sao du lieu: $thu" }

# ── env: TRỎ HẾT sang bản sao. Thiếu một biến là bản thử ghi vào dữ liệu thật ──
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:TC_TRUST_PROXY = '1'
$env:NAS_DONG_BO = 'false'          # bản thử không đụng tài khoản Windows

$env:CHAM_CONG_DIR      = "$thu\to-chuc\db\cham-cong"
$env:CHAM_CONG_CHOT_DIR = "$thu\to-chuc\db\cham-cong-chot"
$env:KPI_DANH_GIA_DIR   = "$thu\to-chuc\db\kpi-danh-gia"
$env:SO_THU_CHI_DIR     = "$thu\to-chuc\db\so-thu-chi"
$env:MUC_TIEU_PATH      = "$thu\to-chuc\db\muc-tieu.json"
$env:TY_GIA_DIR         = "$thu\nhan-su\ty-gia"
$env:CHUNG_TU_DIR       = "$thu\to-chuc\db\chung-tu"
$env:DICH_VU_PATH       = "$thu\to-chuc\db\dich-vu-tra-phi.json"
$env:HAN_MUC_PATH       = "$thu\to-chuc\db\han-muc.json"
$env:CHOT_KY_PATH       = "$thu\to-chuc\db\chot-ky-tien.json"
$env:DON_GIA_API_PATH   = "$thu\to-chuc\db\don-gia-api.json"
$env:LUONG_DIR          = "$thu\nhan-su\luong"
$env:TAI_SAN_DIR        = "$thu\nhan-su\tai-san"
$env:VAULT_DIR          = "$thu\vault"
$env:IAM_DB             = "$thu\nen\iam.db"
$env:DANH_BA_DB         = "$thu\nen\danh_ba.db"
$env:LOGS_DIR           = "$thu\logs"

Start-Process -FilePath $py -WindowStyle Hidden `
  -ArgumentList "-m uvicorn src.main:app --app-dir `"apps/to-chuc`" --host 127.0.0.1 --port $congApp" `
  -WorkingDirectory $root | Out-Null

$khoaTep = Join-Path $thu 'khoa-vao.txt'
if (-not (Test-Path $khoaTep)) {
  -join ((1..24) | ForEach-Object { 'abcdefghijkmnpqrstuvwxyz23456789'[(Get-Random -Max 32)] }) |
    Out-File $khoaTep -Encoding ascii -NoNewline
}
$env:FTN_KHOA = (Get-Content $khoaTep -Raw).Trim()
$env:FTN_CONG_APP = $congApp
$env:FTN_CONG_VAO = $congVao

Start-Process -FilePath $py -WindowStyle Hidden `
  -ArgumentList "`"$root\tools\scripts\finance_thu_nghiem_cong.py`"" `
  -WorkingDirectory $root | Out-Null

Start-Sleep -Seconds 4
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -like '192.168.*' } | Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "[+] BAN THU FINANCE da chay"
Write-Host ("    Mo:  http://{0}:{1}/finance?key={2}" -f $ip, $congVao, $env:FTN_KHOA)
Write-Host ("    Du lieu rieng: {0}" -f $thu)
Write-Host "    Ban that 9103 KHONG bi dung toi."
