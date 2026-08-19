# cap-nhat-app.ps1 — keo ban moi cua MOT app (repo git rieng trong apps/<slug>)
# tu GitHub ve server, chay test, roi restart dich vu. Duong deploy chuan cho
# nhan su lam viec tu xa: ho push nhanh -> mo PR -> Owner duyet/merge tren GitHub
# -> Owner chay script nay tren server. Vi du:  .\cap-nhat-app.ps1 -App seo-optimize
#
# AN TOAN: pull --ff-only (khong bao gio tu merge); test DO la DUNG, khong restart;
# quay lui: cd apps/<slug>; git reset --hard HEAD@{1}
param([Parameter(Mandatory = $true)][string]$App)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dir = Join-Path $root "apps/$App"
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path (Join-Path $dir '.git'))) {
    throw "apps/$App chua phai repo git rieng — chi app da tach repo moi dung script nay"
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Set-Location $dir
git fetch origin
$moi = @(git log --oneline 'HEAD..origin/main')
if ($moi.Count -eq 0) { Write-Host "[$App] Khong co gi moi tren origin/main."; return }
Write-Host "[$App] Se keo $($moi.Count) commit:"; $moi | ForEach-Object { Write-Host "  $_" }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw "pull --ff-only that bai — lich su re nhanh? Xem lai tren GitHub." }

# Test cua app (trong repo con)
if (Test-Path (Join-Path $dir 'tests')) {
    & $py -m pytest tests -q
    if ($LASTEXITCODE -ne 0) {
        throw "TEST APP DO — DUNG, KHONG restart. Ban cu van dang chay. Quay lui: git reset --hard HEAD@{1}"
    }
}
# Test tich hop o repo cha (neu co)
Set-Location $root
$roottest = 'tests/test_' + ($App -replace '-', '_') + '.py'
if (Test-Path $roottest) {
    & $py -m pytest $roottest -q
    if ($LASTEXITCODE -ne 0) { throw "TEST TICH HOP ($roottest) DO — DUNG, KHONG restart." }
}

# Restart dich vu: doc cong tu hop dong app, kill tien trinh dang nghe, start-all bat lai
$cong = & $py -c "import json,io;print({a['slug']: a['cong'] for a in json.load(io.open('nen/rules/apps.json', encoding='utf-8-sig'))['apps']}.get('$App', ''))"
if ($cong) {
    $c = Get-NetTCPConnection -LocalPort ([int]$cong) -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { Stop-Process -Id $c.OwningProcess -Force -Confirm:$false; Start-Sleep -Seconds 1 }
    & (Join-Path $PSScriptRoot 'start-all.ps1')
    Start-Sleep -Seconds 2
    $song = Get-NetTCPConnection -LocalPort ([int]$cong) -State Listen -ErrorAction SilentlyContinue
    if ($song) { Write-Host "[$App] Da cap nhat + restart, cong $cong dang song." }
    else { Write-Host "[$App] CANH BAO: cong $cong chua nghe lai — xem log tien trinh." }
} else {
    Write-Host "[$App] Khong tim thay cong trong apps.json — bo qua buoc restart."
}
