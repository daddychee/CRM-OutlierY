#!/usr/bin/env bash
# setup_vps.sh — Cài Niche Research lần đầu trên VPS (Ubuntu 22.04)
# Chạy với:  bash setup_vps.sh
# Yêu cầu:   sudo / root
set -euo pipefail

APP_DIR=/opt/niche-research
APP_USER=nichers
VPS_IP=45.32.107.108
DOMAIN="niche-research.${VPS_IP}.sslip.io"
PORT=8780

echo "=== [1/8] Tạo user + thư mục app ==="
id "$APP_USER" &>/dev/null || useradd -r -s /bin/bash -m -d "$APP_DIR" "$APP_USER"
mkdir -p "$APP_DIR/projects" "$APP_DIR/web/vendor"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "=== [2/8] Python venv + dependencies ==="
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q \
    fastapi "uvicorn[standard]" python-multipart \
    requests openpyxl jsonschema

echo "=== [3/8] Download vendor JS (Preact + HTM, không cần Node.js) ==="
VENDOR="$APP_DIR/web/vendor"
BASE="https://cdn.jsdelivr.net/npm"
curl -fsSL "$BASE/preact@10/dist/preact.module.js"       -o "$VENDOR/preact.module.js"
curl -fsSL "$BASE/preact@10/hooks/dist/hooks.module.js"  -o "$VENDOR/hooks.module.js"
curl -fsSL "$BASE/htm@3/dist/htm.module.js"              -o "$VENDOR/htm.module.js"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/web"

echo "=== [4/8] Tạo file .htpasswd ==="
if [ ! -f "$APP_DIR/.htpasswd" ]; then
    echo "Nhập tên đăng nhập cho web:"
    read -r HTUSER
    htpasswd -c "$APP_DIR/.htpasswd" "$HTUSER"
    chown "$APP_USER:www-data" "$APP_DIR/.htpasswd"
    chmod 640 "$APP_DIR/.htpasswd"
    echo "Thêm người dùng sau: htpasswd $APP_DIR/.htpasswd <tên>"
fi

echo "=== [5/8] nginx config ==="
cp "$(dirname "$0")/nginx-niche-research.conf" /etc/nginx/sites-available/niche-research
sed -i "s/niche-research\.45\.32\.107\.108\.sslip\.io/$DOMAIN/g" \
    /etc/nginx/sites-available/niche-research
ln -sf /etc/nginx/sites-available/niche-research /etc/nginx/sites-enabled/niche-research
nginx -t && systemctl reload nginx

echo "=== [6/8] certbot HTTPS ==="
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
    -m congthanh267@gmail.com || echo "(certbot bỏ qua — chạy lại tay nếu cần)"
# Sau certbot: sửa listen 443 ssl → listen ${VPS_IP}:443 ssl trong sites-enabled
sed -i "s/listen 443 ssl/listen ${VPS_IP}:443 ssl/g" \
    /etc/nginx/sites-enabled/niche-research 2>/dev/null || true
nginx -t && systemctl reload nginx

echo "=== [7/8] systemd service ==="
cp "$(dirname "$0")/niche-research.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now niche-research
systemctl status niche-research --no-pager

echo "=== [8/8] Kiểm tra ==="
sleep 2
curl -s "http://127.0.0.1:${PORT}/" | head -5 && echo "✓ Server đang chạy" \
    || echo "✗ Server chưa phản hồi — xem: journalctl -u niche-research -n 30"

echo ""
echo "✅ Hoàn tất!"
echo "   URL:       https://${DOMAIN}"
echo "   Thêm key:  nano $APP_DIR/.env"
echo "   Restart:   systemctl restart niche-research"
echo "   Log:       journalctl -u niche-research -f"
