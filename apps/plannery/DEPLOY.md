# Triển khai lên VPS (tiếng Việt)

## ✅ ĐÃ TRIỂN KHAI (13/07/2026)

- **URL**: https://plannery.45.32.107.108.sslip.io (HTTPS qua Let's Encrypt/sslip.io)
- **VPS**: Ubuntu 22.04, 45.32.107.108. Code ở `/opt/plannery`, chạy như user
  `plannery`, systemd unit `plannery.service`, cổng nội bộ 8123.
- **Auth**: nginx basic-auth là cổng duy nhất (app bind 127.0.0.1); username đã
  xác thực truyền xuống app qua header `X-Remote-User`, app tra `data/users.json`
  ra role. Quản trị gốc = username `admin` (biến môi trường `ADMIN_USERS`).
- **Thêm người (kiểu RadarY — mã mời)**: đăng nhập admin → tab **QUẢN TRỊ** →
  chọn vai trò → **＋ Tạo mã mời** (link tự copy) → gửi link cho người đó → họ vào
  `/invite`, tự đặt tên đăng nhập + mật khẩu → server tạo tài khoản nginx + gán role.
  Bảng thành viên đổi role inline (chip/select), gỡ người, thu hồi mã. Mã dùng 1 lần,
  hạn 7 ngày. `/invite` và `/api/register` là 2 location nginx `auth_basic off`.
- **Deploy lại code**: `rsync -az planner/ server.py ui/index.html` lên
  `/opt/plannery` rồi `systemctl restart plannery`.
- **⚠️ Gotcha nginx**: sau `certbot`, `sites-enabled/plannery` là FILE THẬT (không
  còn symlink tới sites-available) — sửa nginx phải sửa đúng `sites-enabled/plannery`.
  Site này phải `listen 45.32.107.108:443` (cùng IP với content-ultimate).
- **Backup**: `data/plan.json` + `data/backups/` (40 bản) trên VPS. Nên thêm cron
  đẩy `/opt/plannery/data` ra ngoài máy hằng đêm.
- **Lưu ý gia hạn cert**: block nginx `plannery` dùng `listen 45.32.107.108:443`
  (phải cùng IP với site content-ultimate, nếu không request bị định tuyến nhầm) —
  kiểm lại dòng này còn nguyên sau lần `certbot renew` đầu tiên.

---

## (Tham khảo) Các bước gốc


## Yêu cầu tài nguyên — RẤT NHẸ

| Hạng mục | Cần | Ghi chú |
|---|---|---|
| CPU | 1 vCPU | Engine tính lịch < 10ms cho vài chục video |
| RAM | ~50–100MB khi chạy | 512MB VPS là dư dả |
| Disk | < 50MB (code + data + 40 bản backup) | plan.json thường < 1MB |
| Python | 3.10+ | Chỉ dùng thư viện chuẩn — KHÔNG cần pip install gì |
| Hệ điều hành | Linux bất kỳ | Code portable (pathlib, không lệnh Mac) |

**Nếu VPS đang chạy được Content Ultimate thì thừa sức chạy tool này** — tool nhẹ
hơn nhiều (không gọi API AI, không xử lý media).

## Các bước

1. Copy thư mục code lên VPS (KHÔNG copy `data/` nếu muốn bắt đầu sạch; muốn mang
   dữ liệu theo thì copy cả `data/plan.json`).
2. Đổi mã vai trò trong `data/roles.json` (tự sinh ở lần chạy đầu) — **bắt buộc
   đổi khỏi mã mặc định** trước khi cho team dùng. `chmod 600 data/roles.json`.
3. Chạy service (systemd):

```ini
# /etc/systemd/system/planner.service
[Unit]
Description=Production Planner
After=network.target

[Service]
WorkingDirectory=/opt/production
Environment=PLANNER_HOST=127.0.0.1
Environment=PLANNER_PORT=8123
ExecStart=/usr/bin/python3 server.py --no-browser
Restart=always
User=planner

[Install]
WantedBy=multi-user.target
```

4. **Reverse proxy + HTTPS bắt buộc** (Caddy gọn nhất — tự lo chứng chỉ):

```
# Caddyfile
plan.ten-mien-cua-ban.com {
    reverse_proxy 127.0.0.1:8123
    basic_auth {           # lớp khoá ngoài cùng cho CẢ trang (kể cả chế độ Xem)
        team $2a$14$...    # caddy hash-password
    }
}
```

Tham khảo thêm Phần C của `../Content Ultimate/CLAUDE.md` (đã trả học phí một lần).

5. Backup: server tự giữ `data/plan.backup.json` + `data/backups/` (40 bản).
   Thêm cron mỗi đêm đẩy ra ngoài máy:
   `0 2 * * * tar czf /backup/planner-$(date +\%F).tgz /opt/production/data`

## Mô hình bảo mật hiện tại

- Mã vai trò nằm trong `data/roles.json` trên server (ngoài git, ngoài mã nguồn);
  client gửi mã qua header mỗi lần lưu; server kiểm **ma trận quyền theo vùng dữ
  liệu** (SPEC mục 6) — UI chỉ là lớp tiện dụng, chặn thật ở server.
- Chống ghi đè chéo nhiều người: khoá `_rev` — lưu đè bản cũ bị 409 và trang tự
  tải lại bản mới.
- Ghi file nguyên tử (tmp + replace) + khoá luồng — không hỏng file khi lưu đồng thời.
- Giới hạn body 5MB; server chỉ phục vụ đúng 2 file tĩnh cố định (không đọc path
  từ request → không có path traversal).
- CHƯA có (giao cho reverse proxy): HTTPS, rate-limit, log truy cập theo người.
  Mã vai trò là mã chung theo vai (không định danh từng người) — đủ cho team nhỏ,
  muốn truy vết từng người thì nâng cấp sau.
