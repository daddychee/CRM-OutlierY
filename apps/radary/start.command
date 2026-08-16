#!/bin/bash
# Khởi động Radary — bấm đúp file này trong Finder là chạy.
# Đóng cửa sổ Terminal này = tắt Radary (radar ngừng quét).
cd "$(dirname "$0")"
echo "📡 Đang khởi động Radary… Mở trình duyệt vào: http://127.0.0.1:8000"
echo "   (Giữ cửa sổ này mở để radar tiếp tục quét. Muốn tắt: bấm Ctrl+C hoặc đóng cửa sổ.)"
./.venv/bin/python server.py
