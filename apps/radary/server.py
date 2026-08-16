"""Khởi động Radary: python3 server.py (dùng .venv/bin/python) hoặc docker compose up.

ENV: PORT (mặc định 8000) · RADARY_HOST (mặc định 127.0.0.1; Docker đặt 0.0.0.0)
     RADARY_SCHEDULER=0 tắt quét nền · RADAR_BUDGET giây/chu kỳ
     RADARY_SECRET khóa chủ mã hóa key (mặc định: file data/secret.key tự sinh)
     RADARY_SECURE_COOKIE=1 khi chạy sau HTTPS.
"""
import os
import uvicorn

if __name__ == '__main__':
    uvicorn.run('radary.api:app', host=os.environ.get('RADARY_HOST', '127.0.0.1'),
                port=int(os.environ.get('PORT', '8000')))
