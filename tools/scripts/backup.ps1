# backup.ps1 — chay backup theo manifest (nen/rules/apps.json muc du_lieu).
# Dich: env BACKUP_DIR (mac dinh D:\OUTLIERY-v2-backup - KHONG dung backup he cu).
# Dang ky Task Scheduler khi thay the that; giai doan test chay tay.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
& (Join-Path $root '.venv\Scripts\python.exe') -m nen.common.sao_luu
