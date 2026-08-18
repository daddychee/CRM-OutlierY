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

# RadarY (APPS.md app 1/6): du lieu tro data/radary (RADARY_DATA_DIR);
# SCHEDULER TAT o V3 — he that C:\ van tu quet theo lich, V3 cung quet la
# doi quota YouTube + lech du lieu snapshot (nghiem thu thi POST /run tay).
$env:RADARY_DATA_DIR = (Join-Path $root 'data/radary')
$env:RADARY_SCHEDULER = '0'
$env:RADARY_TRUST_PROXY = '1'

# Content Ultimate (APPS.md app 2/6): du lieu tro data/content-ultimate; SSO bat.
# App KHONG co scheduler nen (pipeline chi chay khi user bam) - khac RadarY.
$env:CU_DATA_DIR = (Join-Path $root 'data/content-ultimate')
$env:CU_TRUST_PROXY = '1'

# Niche Research (APPS.md app 3 - Owner chen len 18/08): du lieu tro
# data/niche-research; SSO bat; WATCH SCHEDULER TAT o V3 (he that C:\ van tu
# watch theo lich tren CUNG du an - V3 chay song song la dot doi quota YouTube;
# nghiem thu watch bang POST /api/watch/{name}/run tay).
$env:NICHE_DATA_DIR = (Join-Path $root 'data/niche-research')
$env:NICHE_TRUST_PROXY = '1'
$env:NICHE_SCHEDULER = '0'
# Bay UTF-8 may Windows nay: app in tieng Viet ra stdout -> cp1252 chet luc khoi dong.
$env:PYTHONIOENCODING = 'utf-8'
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
    @{ Ten = 'ai-agent'; Cong = 9101; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/ai-agent" --host 127.0.0.1 --port 9101'
       Wd = $root }
    @{ Ten = 'data-analytics'; Cong = 9102; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/data-analytics" --host 127.0.0.1 --port 9102'
       Wd = $root }
    @{ Ten = 'to-chuc'; Cong = 9103; Exe = $py
       Args = '-m uvicorn src.main:app --app-dir "apps/to-chuc" --host 127.0.0.1 --port 9103'
       Wd = $root }
    @{ Ten = 'radary'; Cong = 9111; Exe = $py
       Args = '-m uvicorn radary.api:app --app-dir "apps/radary" --host 127.0.0.1 --port 9111'
       Wd = $root }
    @{ Ten = 'content-ultimate'; Cong = 9112; Exe = $py
       Args = '-m contentultimate.server --port 9112 --no-browser'
       Wd = $root }
    @{ Ten = 'niche-research'; Cong = 9113; Exe = $py
       Args = '-m uvicorn server:app --app-dir "apps/niche-research" --host 127.0.0.1 --port 9113'
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
