#!/usr/bin/env bash
# deploy_now.sh — Deploy Niche Research lên VPS lần đầu (hoặc update)
# Chạy từ thư mục gốc tool:
#   cd "/Users/daddychee/Desktop/Claude Tool/Niche Research"
#   bash deploy/deploy_now.sh
set -euo pipefail

VPS_IP=45.32.107.108
VPS_USER=root
APP_DIR=/opt/niche-research
DOMAIN="niche-research.${VPS_IP}.sslip.io"
PORT=8780

# Mật khẩu VPS (chỉ dùng local, không upload lên đâu)
VPS_PASS='q+6Dh9bjvoYbWhPu'

TOOL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Tool dir: $TOOL_DIR"

# ── Kiểm tra sshpass ──────────────────────────────────────────────────────────
if ! command -v sshpass &>/dev/null; then
    echo "Cài sshpass..."
    brew install sshpass
fi

SSH="sshpass -p $VPS_PASS ssh -o StrictHostKeyChecking=no $VPS_USER@$VPS_IP"
SCP="sshpass -p $VPS_PASS scp -o StrictHostKeyChecking=no -r"
RSYNC="sshpass -p $VPS_PASS rsync -avz --delete -e 'ssh -o StrictHostKeyChecking=no'"

echo ""
echo "=== [1/8] Kiểm tra VPS ==="
$SSH "lsb_release -d && python3 --version && nginx -v 2>&1 | head -1"

echo ""
echo "=== [2/8] Tạo thư mục + user trên VPS ==="
$SSH bash <<'REMOTE'
id nichers &>/dev/null || useradd -r -s /bin/bash -m -d /opt/niche-research nichers
mkdir -p /opt/niche-research/{projects,web/vendor}
REMOTE

echo ""
echo "=== [3/8] Rsync code lên VPS ==="
sshpass -p "$VPS_PASS" rsync -avz --delete \
    -e "ssh -o StrictHostKeyChecking=no" \
    --exclude '.env' \
    --exclude '.last_project.json' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.bak' \
    --exclude '.DS_Store' \
    --exclude 'projects/' \
    "$TOOL_DIR/" "$VPS_USER@$VPS_IP:$APP_DIR/"

echo ""
echo "=== [4/8] Python venv + dependencies ==="
$SSH bash <<REMOTE
cd $APP_DIR
if [ ! -f .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q fastapi "uvicorn[standard]" python-multipart requests openpyxl jsonschema
echo "✓ pip done"
REMOTE

echo ""
echo "=== [5/8] Download vendor JS (Preact + HTM) ==="
$SSH bash <<'REMOTE'
VENDOR=/opt/niche-research/web/vendor
BASE=https://cdn.jsdelivr.net/npm
[ -f "$VENDOR/preact.module.js" ] && echo "vendor already exists, skip" && exit 0
curl -fsSL "$BASE/preact@10/dist/preact.module.js"      -o "$VENDOR/preact.module.js"
curl -fsSL "$BASE/preact@10/hooks/dist/hooks.module.js" -o "$VENDOR/hooks.module.js"
curl -fsSL "$BASE/htm@3/dist/htm.module.js"             -o "$VENDOR/htm.module.js"
echo "✓ vendor JS ok"
REMOTE

echo ""
echo "=== [6/8] Quyền file ==="
$SSH "chown -R nichers:nichers $APP_DIR"

echo ""
echo "=== [7/8] nginx config ==="
$SSH bash <<REMOTE
cp $APP_DIR/deploy/nginx-niche-research.conf /etc/nginx/sites-available/niche-research
ln -sf /etc/nginx/sites-available/niche-research /etc/nginx/sites-enabled/niche-research
nginx -t && systemctl reload nginx
echo "✓ nginx ok"
REMOTE

echo ""
echo "=== [8/8] Tạo .htpasswd (nếu chưa có) ==="
if ! $SSH "[ -f $APP_DIR/.htpasswd ]" 2>/dev/null; then
    echo ""
    echo "Chưa có .htpasswd. Nhập tên đăng nhập cho web:"
    read -r HTUSER
    $SSH "htpasswd -c $APP_DIR/.htpasswd $HTUSER && chown nichers:www-data $APP_DIR/.htpasswd && chmod 640 $APP_DIR/.htpasswd"
else
    echo "(đã có .htpasswd — bỏ qua)"
fi

echo ""
echo "=== systemd service ==="
$SSH bash <<REMOTE
cp $APP_DIR/deploy/niche-research.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable niche-research
systemctl restart niche-research
sleep 2
systemctl status niche-research --no-pager -l | tail -15
REMOTE

echo ""
echo "=== Kiểm tra nhanh ==="
$SSH "curl -s -o /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:$PORT/" || true

echo ""
echo "=== Certbot HTTPS (nếu chưa có) ==="
$SSH bash <<REMOTE
if certbot certificates 2>/dev/null | grep -q "$DOMAIN"; then
    echo "(cert đã tồn tại — bỏ qua certbot)"
else
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m congthanh267@gmail.com || true
    # Sửa listen 443 → listen IP:443 (tránh conflict với port 443 đã dùng)
    sed -i 's/listen 443 ssl/listen ${VPS_IP}:443 ssl/g' \
        /etc/nginx/sites-enabled/niche-research 2>/dev/null || true
    nginx -t && systemctl reload nginx
fi
REMOTE

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅  DEPLOY THÀNH CÔNG                               ║"
echo "╟──────────────────────────────────────────────────────╢"
echo "║  URL:  https://$DOMAIN  ║"
echo "║  Thêm LLM key:  nano $APP_DIR/.env                  ║"
echo "║  Log:  journalctl -u niche-research -f               ║"
echo "╚══════════════════════════════════════════════════════╝"
