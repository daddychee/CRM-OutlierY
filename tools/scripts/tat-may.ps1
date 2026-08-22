# tat-may.ps1 - B1 (chot 22/08/2026): 20:00 hang ngay may tu HIBERNATE de tiet
# kiem dien; 9:00 sang tac vu OUTLIERY-BatMay (WakeToRun) danh thuc lai.
# RadarY V3 scheduler tu quet bu khi may day (job qua han la chay ngay).
# Muon lam viec khuya: Disable tac vu OUTLIERY-TatMay hoac bam phim nguon sau 20:00.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$log = Join-Path $root 'logs\tat-may.log'
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
$dong = "[{0}] chuan bi hibernate" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# kiem backup 19:00 da chay chua (chi ghi log, khong chan viec tat)
$kq = 'D:\OUTLIERY-v2-backup\ket-qua.jsonl'
if (Test-Path $kq) {
    $tuoi = (Get-Date) - (Get-Item $kq).LastWriteTime
    if ($tuoi.TotalHours -gt 24) { $dong += " | CANH BAO: backup cu $([int]$tuoi.TotalHours)h" }
    else { $dong += " | backup moi ($([int]$tuoi.TotalMinutes) phut truoc)" }
} else { $dong += " | CANH BAO: chua thay ket-qua backup" }
Add-Content -Path $log -Value $dong -Encoding utf8
shutdown /h
