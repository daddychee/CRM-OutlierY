# soi-egress.ps1 — AUDIT CHI DOC ket noi TCP di ra ngoai theo tien trinh.
# (spec docs/phong-thu-api-ngoai.md, lop 2 — Owner chay tay dinh ky:
#   powershell -ExecutionPolicy Bypass -File tools\scripts\soi-egress.ps1
# Script KHONG doi gi tren may: chi chup Get-NetTCPConnection + phan loai.)
# ASCII khong dau — tranh bay BOM PowerShell 5.1.

$ErrorActionPreference = "SilentlyContinue"

# Dai IP coi la NOI BO / vo hai (LAN + loopback + link-local)
function La-NoiBo([string]$ip) {
    return ($ip -like "10.*" -or $ip -like "192.168.*" -or $ip -like "172.16.*" `
        -or $ip -like "172.17.*" -or $ip -like "172.18.*" -or $ip -like "172.19.*" `
        -or $ip -like "172.2?.*" -or $ip -like "172.30.*" -or $ip -like "172.31.*" `
        -or $ip -like "127.*" -or $ip -eq "::1" -or $ip -like "169.254.*" `
        -or $ip -eq "0.0.0.0" -or $ip -eq "::")
}

Write-Host "=== SOI EGRESS $(Get-Date -Format 'yyyy-MM-dd HH:mm') ==="
Write-Host "Ket noi TCP DI RA NGOAI (Established, dich ngoai LAN), gom theo tien trinh:`n"

$ket = Get-NetTCPConnection -State Established |
    Where-Object { -not (La-NoiBo $_.RemoteAddress) }

$theoPid = $ket | Group-Object OwningProcess
$tongLa = 0
foreach ($g in $theoPid) {
    $proc = Get-Process -Id $g.Name
    $ten = if ($proc) { $proc.ProcessName } else { "pid-$($g.Name)" }
    Write-Host ("[{0}] (pid {1}) — {2} ket noi ra ngoai:" -f $ten, $g.Name, $g.Count)
    $dich = $g.Group | Group-Object RemoteAddress
    foreach ($d in $dich) {
        # Reverse DNS best-effort de doc duoc dich (API lon thuong resolve duoc)
        $host2 = ""
        try { $host2 = ([System.Net.Dns]::GetHostEntry($d.Name)).HostName } catch {}
        $cong = ($d.Group | Select-Object -ExpandProperty RemotePort -Unique) -join ","
        Write-Host ("    {0,-40} cong {1,-12} {2}" -f $d.Name, $cong, $host2)
        # Tien trinh python/node/caddy noi ra ngoai la dang chu y nhat —
        # doi chieu voi allowlist trong docs/phong-thu-api-ngoai.md
        if ($ten -match "python|node|caddy|uvicorn") { $tongLa++ }
    }
}

Write-Host ""
if ($theoPid.Count -eq 0) {
    Write-Host "Khong co ket noi ra ngoai nao dang mo. (Luu y: day la SNAPSHOT —"
    Write-Host "call API ngan co the khong dinh luc chup; chay vai lan gio cao diem.)"
} else {
    Write-Host ("Tong: {0} tien trinh co ket noi ra ngoai." -f $theoPid.Count)
    Write-Host "DOI CHIEU TAY: dich cua python/uvicorn phai thuoc allowlist"
    Write-Host "(api.anthropic.com / api.z.ai / bigmodel / googleapis...) — thay dich"
    Write-Host "la thi tra nguoc app nao goi (data/logs/so-goi cung ngay gio)."
}
