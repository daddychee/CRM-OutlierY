#!/usr/bin/env bash
# push.sh — Sync code từ Mac lên VPS + restart service
# Chạy từ thư mục gốc tool:  bash deploy/push.sh
set -euo pipefail

VPS=root@45.32.107.108
REMOTE=/opt/niche-research

echo "→ Rsync code lên VPS..."
rsync -avz --delete \
    --exclude '.env' \
    --exclude '.last_project.json' \
    --exclude '__pycache__' \
    --exclude '*.bak' \
    --exclude '.DS_Store' \
    --exclude 'projects/' \
    --exclude '*.pyc' \
    . "$VPS:$REMOTE/"

echo "→ Restart service..."
ssh "$VPS" "systemctl restart niche-research && systemctl status niche-research --no-pager -l"

echo "✅ Deploy xong — https://niche-research.45.32.107.108.sslip.io"
