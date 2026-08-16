#!/bin/bash
# Cài đặt Radary trên VPS Ubuntu MỚI (chạy 1 lần): Docker + Tailscale + khởi động app.
# DÙNG (trên VPS, sau khi đã chạy deploy/push.sh từ Mac):  bash /opt/radary/deploy/vps_setup.sh
set -euo pipefail
cd /opt/radary

echo "== [1/4] Cài Docker =="
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
docker --version

echo "== [2/4] Cài Tailscale (mạng riêng — KHÔNG lộ app ra internet) =="
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
if ! tailscale status >/dev/null 2>&1; then
  echo ">> Mở link hiện ra bên dưới bằng trình duyệt và đăng nhập (cùng tài khoản với Mac/điện thoại):"
  tailscale up
fi

echo "== [3/4] Build + chạy Radary (docker compose) =="
docker compose up -d --build
sleep 3
curl -sf http://127.0.0.1:8000/api/health && echo " <- app SỐNG ✅" || { echo "✗ app chưa lên — gửi output 'docker compose logs' cho Claude"; exit 1; }

echo "== [4/4] Mở cổng HTTPS riêng tư qua Tailscale =="
tailscale serve --bg 8000 || tailscale serve --bg --https=443 http://127.0.0.1:8000
echo ""
echo "XONG ✅ — địa chỉ dashboard (chỉ thiết bị trong Tailscale của bạn vào được):"
tailscale serve status 2>/dev/null || true
echo "(dạng https://<tên-máy>.<tailnet>.ts.net — mở từ Mac/điện thoại đã cài Tailscale)"
echo "Backup: folder /opt/radary/data — xem docs/deploy_vps.md mục 6."
