# stop-all.ps1 — tat cac dich vu platform v2 theo PID file (chi tat thu minh bat).
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pidDir = Join-Path $root 'logs\pids'
if (-not (Test-Path $pidDir)) { Write-Host 'Khong co PID file nao.'; exit 0 }
Get-ChildItem $pidDir -Filter *.pid | ForEach-Object {
    $ten = $_.BaseName
    $procId = (Get-Content $_.FullName | Select-Object -First 1).Trim()
    try {
        Stop-Process -Id ([int]$procId) -Force -ErrorAction Stop
        Write-Host ("[-] {0} (PID {1}) da tat" -f $ten, $procId)
    } catch { Write-Host ("[=] {0} (PID {1}) khong con chay" -f $ten, $procId) }
    Remove-Item $_.FullName -Force
}
