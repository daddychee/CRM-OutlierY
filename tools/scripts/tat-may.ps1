# tat-may.ps1 - LUOI AN TOAN 20:00 (Owner chot 23/08/2026: van hanh THU CONG -
# ra ve tu shutdown, sang bam nut nguon; tac vu nay chi do hom nao QUEN tat).
# Shutdown that (khong hibernate - hibernate da tat de lay lai 17GB o C).
# NANG CAP 31/08 (Owner chot): "truoc khi tat se WARNING cho nhan su - CHI tat
# khi khong co job dang chay":
#   1. Ghi co sap_tat.json -> UI content-ultimate hien banner do cho nhan su.
#   2. Hoi http://127.0.0.1:9112/api/tinh-trang-ban moi 5 phut (toi da 12 vong =
#      60 phut): con job writer/extractor/sinh-khung dang chay thi CHUA tat.
#   3. Het job -> shutdown /s /t 120 (huy bang: shutdown /a).
#   4. Sau 60 phut van con job -> KHONG TAT (ghi log) - dung luat Owner.
# App khong tra loi (da tat/loi) -> coi nhu khong job, tat nhu cu.
# App tu len khi bat may nho tac vu OUTLIERY-V3 (at startup, start-all idempotent).
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$log = Join-Path $root 'logs\tat-may.log'
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
function Ghi($t) {
    Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $t) -Encoding utf8
}

# kiem backup nhu cu
$dong = 'luoi an toan 20:00 - bat dau trinh tu tat'
$kq = 'E:\OUTLIERY-V3-backup\ket-qua.jsonl'
if (Test-Path $kq) {
    $tuoi = (Get-Date) - (Get-Item $kq).LastWriteTime
    if ($tuoi.TotalHours -gt 24) { $dong += " | CANH BAO: backup cu $([int]$tuoi.TotalHours)h" }
    else { $dong += " | backup moi ($([int]$tuoi.TotalMinutes) phut truoc)" }
} else { $dong += ' | CANH BAO: chua thay ket-qua backup' }
Ghi $dong

# 1. co sap-tat cho UI (mtime la nguon su that; co cu >2h tu het hieu luc)
$co = Join-Path $root 'data\content-ultimate\sap_tat.json'
try {
    Set-Content -Path $co -Value ('{"luc":"' + (Get-Date -Format 'yyyy-MM-dd HH:mm') + '"}') -Encoding utf8
    Ghi 'da ghi co sap_tat.json - UI bat dau canh bao nhan su'
} catch { Ghi "khong ghi duoc co sap_tat: $_" }

# 2. cho het job (toi da 12 vong x 5 phut)
$duocTat = $true
for ($v = 1; $v -le 12; $v++) {
    $ban = 0; $viec = ''
    try {
        $r = Invoke-RestMethod -Uri 'http://127.0.0.1:9112/api/tinh-trang-ban' -TimeoutSec 10
        $ban = [int]$r.dang_chay
        if ($r.viec) { $viec = ($r.viec -join '; ') }
    } catch { Ghi 'app 9112 khong tra loi - coi nhu khong co job'; break }
    if ($ban -le 0) { Ghi 'khong co job dang chay - duoc phep tat'; break }
    Ghi "vong $v/12: con $ban job dang chay ($viec) - cho 5 phut"
    if ($v -eq 12) {
        $duocTat = $false
        Ghi 'HET 60 PHUT van con job - KHONG TAT (luat Owner 31/08: chi tat khi khong co job)'
    } else {
        Start-Sleep -Seconds 300
    }
}

# 3. tat (hoac khong)
if ($duocTat) {
    Ghi 'shutdown /s /t 120'
    shutdown /s /t 120 /c "OUTLIERY: may tu tat sau 2 phut (luoi an toan 20:00, da kiem khong con job). Dang lam viec? Mo PowerShell go: shutdown /a"
} else {
    try { Remove-Item -Path $co -Force -ErrorAction SilentlyContinue } catch {}
}
