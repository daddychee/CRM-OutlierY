# tat-may.ps1 - LUOI AN TOAN 20:00 (Owner chot 23/08/2026: van hanh THU CONG -
# ra ve tu shutdown, sang bam nut nguon; tac vu nay chi do hom nao QUEN tat).
# Shutdown that (khong hibernate - hibernate da tat de lay lai 17GB o C).
# Dem nguoc 120s, dang lam viec thi huy bang:  shutdown /a
# App tu len khi bat may nho tac vu OUTLIERY-V3 (at startup, start-all idempotent).
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$log = Join-Path $root 'logs\tat-may.log'
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
$dong = "[{0}] luoi an toan 20:00 - shutdown sau 120s" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
$kq = 'E:\OUTLIERY-V3-backup\ket-qua.jsonl'
if (Test-Path $kq) {
    $tuoi = (Get-Date) - (Get-Item $kq).LastWriteTime
    if ($tuoi.TotalHours -gt 24) { $dong += " | CANH BAO: backup cu $([int]$tuoi.TotalHours)h" }
    else { $dong += " | backup moi ($([int]$tuoi.TotalMinutes) phut truoc)" }
} else { $dong += " | CANH BAO: chua thay ket-qua backup" }
Add-Content -Path $log -Value $dong -Encoding utf8
shutdown /s /t 120 /c "OUTLIERY: may tu tat sau 2 phut (luoi an toan 20:00). Dang lam viec? Mo PowerShell go: shutdown /a"
