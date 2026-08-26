# backup.ps1 — chay backup theo manifest (nen/rules/apps.json muc du_lieu).
# Dich: env BACKUP_DIR (mac dinh E:\OUTLIERY-V3-backup - O KHAC voi o D chua ban
# goc; doi 26/08/2026 vi backup cung o voi du lieu song la mot o chet mat ca hai).
# Dang ky Task Scheduler khi thay the that; giai doan test chay tay.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root   # -m nen.common.sao_luu can CWD = root (goi tu ngoai la ModuleNotFoundError)
& (Join-Path $root '.venv\Scripts\python.exe') -m nen.common.sao_luu
