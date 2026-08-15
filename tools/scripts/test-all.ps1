# test-all.ps1 — chay TOAN BO test: tang nen (root) + TUNG app (process rieng).
# Ket qua tung khoi + tong ket cuoi. Exit 0 khi tat ca xanh.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = Join-Path $root '.venv\Scripts\python.exe'
$ketQua = @()

function Chay-Test($ten, $duong) {
    Write-Host ""
    Write-Host ("======== TEST: {0} ========" -f $ten)
    Push-Location $duong
    & $py -m pytest -q --tb=short 2>&1 | Select-Object -Last 4 | ForEach-Object { Write-Host $_ }
    $ma = $LASTEXITCODE
    Pop-Location
    $script:ketQua += @{ Ten = $ten; Ok = ($ma -eq 0) }
}

Chay-Test 'nen (gateway/iam/ket/danh-ba/sao-luu)' $root
Get-ChildItem (Join-Path $root 'apps') -Directory | ForEach-Object {
    if (Test-Path (Join-Path $_.FullName 'tests')) {
        Chay-Test ("app " + $_.Name) $_.FullName
    }
}

Write-Host ""
Write-Host "======== TONG KET ========"
$hong = 0
foreach ($k in $ketQua) {
    $nhan = if ($k.Ok) { '[XANH]' } else { $hong++; '[DO  ]' }
    Write-Host ("{0} {1}" -f $nhan, $k.Ten)
}
if ($hong -gt 0) { Write-Host ("=> {0} khoi DO" -f $hong); exit 1 }
Write-Host '=> TAT CA XANH'; exit 0
