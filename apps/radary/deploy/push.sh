#!/bin/bash
# Đẩy Radary từ máy Mac lên VPS (code + toàn bộ data/ gồm DB, secret.key, kho ảnh).
# DÙNG: sửa dòng VPS= bên dưới MỘT LẦN, rồi:  bash deploy/push.sh
set -euo pipefail

VPS="root@45.32.107.108"        # VPS Vultr (Radary)
DEST="/opt/radary"

cd "$(dirname "$0")/.."
if [[ "$VPS" == *DIA_CHI_IP* ]]; then
  echo "⚠ Chưa điền IP máy chủ — mở deploy/push.sh, sửa dòng VPS=root@<IP> rồi chạy lại."; exit 1
fi

echo "→ Đồng bộ code lên $VPS:$DEST …"
ssh "$VPS" "mkdir -p $DEST"
# 'data' bị loại từ 08/07/2026: DB sống giờ nằm trên VPS — push đè lên là MẤT dữ liệu mới.
# (Lần seed đầu đã đồng bộ data/ rồi; muốn đẩy lại data phải làm tay và hiểu rõ hậu quả.)
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude 'radar_state' \
  --exclude 'radar_reports' --exclude 'legacy' --exclude '.git' \
  --exclude 'data' \
  ./ "$VPS:$DEST/"

echo "→ Xong. Bước kế tiếp (chạy TRÊN VPS — ssh $VPS):"
echo "   bash $DEST/deploy/vps_setup.sh      # lần đầu: cài Docker + Tailscale + khởi động"
echo "   cd $DEST && docker compose up -d --build   # các lần cập nhật sau"
