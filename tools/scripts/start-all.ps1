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

$dichVu = @(
    @{ Ten = 'qdrant-test'; Cong = 6343
       Exe = (Join-Path $root 'tools\qdrant\qdrant.exe')
       Args = '--config-path "' + (Join-Path $root 'tools\qdrant\config.yaml') + '"'
       Wd = (Join-Path $root 'tools\qdrant') }
    # Phase 1 them: gateway :9000, app-mau :9190 ...
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
