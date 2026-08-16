# Đưa Radary lên VPS chạy 24/24 — runbook cho người mới

> Mô hình: **VPS chạy app trong Docker · truy cập RIÊNG TƯ qua Tailscale** (không domain,
> không lộ internet). Nâng lên công khai (domain + Caddy HTTPS) là bước sau, khi có user ngoài.
> Chi phí: VPS ~$6/tháng (~150K VND). Tailscale miễn phí cho cá nhân.

## 1. Thuê VPS (một lần, ~10 phút)

- Nhà cung cấp gợi ý: **Vultr** hoặc **DigitalOcean** — chọn region **Singapore** (gần VN).
  Hetzner rẻ hơn (~€4) nhưng server ở EU, độ trễ cao hơn chút — vẫn dùng tốt.
- Gói: nhỏ nhất **1 vCPU / 1GB RAM / 25GB** là dư dả (Radary rất nhẹ).
- Hệ điều hành: **Ubuntu 24.04 LTS**.
- Xong sẽ nhận được: **địa chỉ IP** + **mật khẩu root** (hoặc SSH key nếu chọn).

## 2. Cài Tailscale trên thiết bị CỦA BẠN (một lần, 5 phút)

- Mac: tải app tại tailscale.com/download → đăng nhập (Google/GitHub).
- Điện thoại: cài app **Tailscale** (App Store/Google Play) → đăng nhập **cùng tài khoản**.
- VPS sẽ được thêm vào ở bước 4 — cả 3 thiết bị nằm chung một "mạng nhà ảo".

## 3. Đẩy code + dữ liệu lên VPS (chạy trên MAC)

```bash
# mở Terminal tại folder Radary, sửa IP một lần:
#   mở deploy/push.sh → thay DIA_CHI_IP_VPS bằng IP thật
bash deploy/push.sh
```

Script rsync toàn bộ code + folder `data/` (DB, secret.key, kho thumbnail) lên `/opt/radary`.
Lần đầu sẽ hỏi mật khẩu root của VPS.

## 4. Cài đặt trên VPS (chạy MỘT LẦN)

```bash
ssh root@<IP>                          # vào VPS
bash /opt/radary/deploy/vps_setup.sh   # cài Docker + Tailscale + build + chạy
```

- Giữa chừng script in một **đường link đăng nhập Tailscale** — mở bằng trình duyệt,
  đăng nhập cùng tài khoản ở bước 2.
- Kết thúc script in địa chỉ dạng `https://<tên-máy>.<tailnet>.ts.net` — **đó là dashboard**.
- ⚠ Đây là lần đầu Docker build của project chạy thật — nếu lỗi ở bước build,
  copy output `docker compose logs` gửi Claude.

## 5. Kiểm tra & chuyển giao

1. Mở địa chỉ `.ts.net` từ điện thoại (bật Tailscale) → đăng nhập Radary → thấy Board. ✅
2. Cài đặt → **Gửi thử 📲** → điện thoại kêu. ✅
3. Chờ 30-60 phút → Nhật ký quét có dòng mới, heartbeat xanh. ✅
4. **TẮT radar trên Mac** (Ctrl+C cửa sổ start.command, không chạy lại nữa) —
   tránh 2 máy cùng quét tốn quota gấp đôi. Từ giờ VPS là nguồn sự thật;
   bản Mac trở thành backup nguội.

## 6. Backup (quan trọng — làm ngay sau khi chạy ổn)

Toàn bộ tài sản nằm ở `/opt/radary/data` (DB + **secret.key** + kho ảnh). Trên VPS, đặt backup tự động hằng ngày, giữ 7 bản:

```bash
crontab -e
# thêm dòng:
0 3 * * * cd /opt/radary && tar czf /root/radary-backup-$(date +\%u).tgz data/
```

Và thỉnh thoảng (mỗi tuần) kéo một bản về Mac cho an toàn kép — chạy trên Mac:

```bash
rsync -az root@<IP>:/opt/radary/data/ ~/Desktop/radary-backup-data/
```

## 7. Vận hành hằng ngày

| Việc | Lệnh (ssh vào VPS) |
|---|---|
| Xem app sống không | `curl http://127.0.0.1:8000/api/health` hoặc nhìn heartbeat trên dashboard |
| Xem log | `cd /opt/radary && docker compose logs --tail 50` |
| Khởi động lại | `cd /opt/radary && docker compose restart` |
| Cập nhật code mới (sau khi Claude sửa) | trên Mac: `bash deploy/push.sh` → trên VPS: `cd /opt/radary && docker compose up -d --build` |
| VPS reboot | Docker tự kéo app dậy (`restart: unless-stopped`) — không phải làm gì |

## 8. Mở dashboard ra INTERNET — Tailscale Funnel (đã bật 08/07/2026 theo lệnh user)

Funnel = Tailscale phát chính địa chỉ `https://radary.<tailnet>.ts.net` ra internet công cộng:
HTTPS thật, không cần mua domain, KHÔNG mở thêm port nào trên VPS (8000 vẫn chỉ bind 127.0.0.1
— đúng luật trong docker-compose.yml). Ai có link đều mở được TRANG ĐĂNG NHẬP; dữ liệu vẫn
nằm sau lớp tài khoản.

Điều kiện đi kèm (đã bật cùng lúc, đúng yêu cầu "HTTPS + rate-limit" ghi trong compose):
- `RADARY_SECURE_COOKIE=1` — cookie chỉ đi qua HTTPS.
- `RADARY_INVITE_ONLY=1` — người lạ KHÔNG tự đăng ký được; tài khoản mới bắt buộc kèm mã mời
  do owner tạo (tab Quản trị). Tài khoản migrate cũ vẫn bootstrap bình thường.
- Rate-limit đăng nhập/đăng ký: 20 lần thử / 5 phút / (IP, email) — chống brute-force.
- Mật khẩu owner phải MẠNH (nó giữ API key + toàn bộ dữ liệu).

Lệnh (trên VPS, 1 lần):   `tailscale funnel --bg 8000`
Tắt public, quay về riêng tư:   `tailscale funnel --https=443 off`   (serve nội bộ vẫn còn)
Kiểm tra:   `tailscale funnel status`   — thấy "Funnel on" là đang public.

Nâng cấp sau này (khi SaaS thật cần domain riêng): mua domain + Caddy reverse-proxy trỏ
127.0.0.1:8000 — kiến trúc không đổi, chỉ thay lớp vỏ HTTPS.
