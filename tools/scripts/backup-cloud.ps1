# backup-cloud.ps1 - day GOI LOI len Google Drive (tang 3 cua nguyen tac 3-2-1).
#
# TAI SAO CHI GOI LOI: backup day du 21GB thi 98% la thu TAO LAI DUOC -
#   video-review (ban dung, review xong xoa, ban goc con o may dung/NAS)
#   nen\qdrant  (dung lai bang scripts\nap_lai_kho.py tu kho tai lieu)
# Phan KHONG tao lai duoc chi ~423MB: kho tai lieu, iam.db, ket khoa+db,
# danh ba, cham cong, seo episodes, content, niche, radary db, tasky, plannery.
#
# BAT BUOC MA HOA: goi nay chua ket.key (chia mo ket API key) + iam.db (hash
# mat khau ca cong ty) + ho so nhan su. Len cloud khong ma hoa = trao chia khoa.
# Mat khau doc tu file NGOAI repo; ghi RA GIAY cat ket sat, KHONG cat trong
# vault (vong lap chet: mo backup can vault, co vault can mo backup).
#
# Chay: tools\scripts\backup-cloud.ps1   (tac vu 19:30, sau backup noi bo 19:00)

$ErrorActionPreference = 'Stop'

$NGUON   = 'E:\OUTLIERY-V3-backup'
$TAM     = 'E:\OUTLIERY-cloud-tam'
$MK_FILE = 'D:\OUTLIERY-tools\bao-mat\mk-cloud.txt'
$RCLONE  = 'D:\OUTLIERY-tools\rclone\rclone.exe'
$SEVENZ  = 'C:\Program Files\7-Zip\7z.exe'
$REMOTE  = 'gdrive:OUTLIERY-backup'
$GIU_NGAY = 30
$LOG     = 'D:\AI AGENT OUTLIERY\logs\backup-cloud.log'

function Ghi($msg) {
    $dong = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Output $dong
    New-Item -ItemType Directory -Force (Split-Path $LOG) | Out-Null
    Add-Content -Path $LOG -Value $dong -Encoding utf8
}

# --- Kiem dieu kien truoc khi lam gi (that bai som, thong bao ro) ---
foreach ($p in @($SEVENZ, $RCLONE)) {
    if (-not (Test-Path $p)) { Ghi "LOI: thieu cong cu $p"; exit 1 }
}
if (-not (Test-Path $NGUON)) { Ghi "LOI: chua co backup noi bo $NGUON"; exit 1 }
if (-not (Test-Path $MK_FILE)) {
    Ghi "LOI: chua dat mat khau ma hoa tai $MK_FILE - xem runbook 01-su-co.md"
    exit 1
}
$mk = (Get-Content $MK_FILE -Raw).Trim()
if ($mk.Length -lt 12) { Ghi "LOI: mat khau ma hoa qua ngan (<12 ky tu)"; exit 1 }

# --- Nen goi loi, LOAI TRU 2 muc tao lai duoc ---
New-Item -ItemType Directory -Force $TAM | Out-Null
$ten = "outliery-loi-{0}.7z" -f (Get-Date -Format 'yyyy-MM-dd')
$goi = Join-Path $TAM $ten
if (Test-Path $goi) { Remove-Item $goi -Force }

Ghi "Nen goi loi -> $ten"
& $SEVENZ a -t7z -mx=5 -mhe=on "-p$mk" $goi "$NGUON\*" '-xr!video-review' '-xr!qdrant' | Out-Null
if ($LASTEXITCODE -ne 0) { Ghi "LOI: 7-Zip ma $LASTEXITCODE"; exit 1 }

$mb = [math]::Round((Get-Item $goi).Length / 1MB, 1)
# Van an toan: goi loi phai ~200-400MB. Ra vai GB = loai tru sai, dung ngay
# keo doi ngay 15GB len Drive va an het quota.
if ($mb -gt 2048) {
    Ghi "LOI: goi $mb MB - qua lon, nghi loai tru sai. Da dung, KHONG day len."
    Remove-Item $goi -Force; exit 1
}
Ghi "Goi xong: $mb MB (da ma hoa AES-256, ma hoa ca ten file)"

# --- Day len Google Drive ---
Ghi "Day len $REMOTE ..."
& $RCLONE copy $goi $REMOTE --config "D:\OUTLIERY-tools\rclone\rclone.conf" --log-level ERROR
if ($LASTEXITCODE -ne 0) {
    Ghi "LOI: rclone ma $LASTEXITCODE - GIU file tam de lan sau day lai"
    exit 1
}
Ghi "Da day xong $ten"

# --- Xoay vong: xoa ban cu hon $GIU_NGAY ngay tren Drive va o local ---
& $RCLONE delete $REMOTE --min-age "${GIU_NGAY}d" --config "D:\OUTLIERY-tools\rclone\rclone.conf" --log-level ERROR
Get-ChildItem $TAM -Filter "*.7z" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-3) } |
    Remove-Item -Force -EA SilentlyContinue

$so = (& $RCLONE lsf $REMOTE --config "D:\OUTLIERY-tools\rclone\rclone.conf" | Measure-Object).Count
Ghi "Xong. Tren Drive dang giu $so ban."
