# start-all.ps1 — bat cac dich vu nen cua platform v2 (giai doan dev, chay tay).
# Them dich vu moi: them 1 muc vao $dichVu (PHAI ghi cong vao docs\PORTS.md truoc).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pidDir = Join-Path $root 'logs\pids'
New-Item -ItemType Directory -Force -Path $pidDir | Out-Null

function Test-Cong($port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port); $c.Close(); return $true
    } catch { return $false }
}

$py = Join-Path $root '.venv\Scripts\python.exe'
$dichVu = @(
    @{ Ten = 'qdrant-test'; Cong = 6343
       Exe = (Join-Path $root 'tools\qdrant\qdrant.exe')
       Args = '--config-path "' + (Join-Path $root 'tools\qdrant\config.yaml') + '"'
       Wd = (Join-Path $root 'tools\qdrant') }
    @{ Ten = 'app-mau'; Cong = 9190; Exe = $py
       Args = '-m uvicorn main:app --app-dir "apps/app-mau/src" --host 127.0.0.1 --port 9190'
       Wd = $root }
    @{ Ten = 'gateway'; Cong = 9000; Exe = $py
       Args = '-m uvicorn nen.gateway.main:app --host 127.0.0.1 --port 9000'
       Wd = $root }
    @{ Ten = 'data-analytics'; Cong = 9102; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/data-analytics" --host 127.0.0.1 --port 9102'
       Wd = $root }
    @{ Ten = 'caddy-tls'; Cong = 9443
       Exe = (Join-Path $root 'tools\caddy\caddy.exe')
       Args = 'run --config "' + (Join-Path $root 'tools\caddy\Caddyfile') + '"'
       Wd = (Join-Path $root 'tools\caddy') }
)

foreach ($dv in $dichVu) {
    if (Test-Cong $dv.Cong) {
        Write-Host ("[=] {0} da chay san (cong {1})" -f $dv.Ten, $dv.Cong)
        continue
    }
    if (-not (Test-Path $dv.Exe)) {
        Write-Host ("[!] {0}: thieu {1} - bo qua" -f $dv.Ten, $dv.Exe); continue
    }
    $p = Start-Process -FilePath $dv.Exe -ArgumentList $dv.Args `
        -WorkingDirectory $dv.Wd -WindowStyle Hidden -PassThru
    $p.Id | Out-File -FilePath (Join-Path $pidDir ($dv.Ten + '.pid')) -Encoding ascii
    Write-Host ("[+] {0} da bat (PID {1}, cong {2})" -f $dv.Ten, $p.Id, $dv.Cong)
}
