# Deploy Content Ultimate lên VPS Ubuntu

Mô hình: app bind `127.0.0.1:8770` → nginx (HTTPS + đăng nhập basic auth) là cổng duy
nhất ra internet. **Quản trị viên** làm 2 việc: cấp/thu tài khoản team (htpasswd trên
server) và nhập API key trong app (tab **⚙ Cài đặt** — chỉ quản trị viên nhìn thấy).

Yêu cầu: Ubuntu 22.04/24.04, quyền sudo, một domain trỏ về IP của VPS (cho HTTPS).

## 1. Cài gói hệ thống + swap

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx apache2-utils certbot python3-certbot-nginx
```

**Ubuntu 22.04 chỉ có Python 3.10** (tool cần ≥3.11 — gặp thật khi deploy 2026-07-08):

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.12 python3.12-venv
# và ở bước 3 dùng:  python3.12 -m venv .venv
```

**Bắt buộc với VPS ≤ 2GB RAM — tạo swap 2GB** (bước S4 gom cụm của board Outline nạp
model embedding, đo đỉnh ~1GB RAM; không có swap sẽ bị hệ điều hành kill giữa chừng):

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. Đưa code lên server

```bash
sudo adduser --system --group --home /opt/content-ultimate contentult
# từ máy Mac (trong folder chứa repo):
rsync -a --exclude .venv --exclude .git "Content Ultimate/" root@<IP>:/opt/content-ultimate/
# (có remote git thì: sudo git clone <repo> /opt/content-ultimate)
```

Lưu ý dữ liệu riêng: `.env`, `runs/`, `library/`, `uploads/` KHÔNG nằm trong git —
nếu muốn mang theo dữ liệu cũ từ máy Mac thì rsync như trên là đủ (rsync chép cả chúng);
nếu clone từ git thì server bắt đầu trắng, key sẽ nhập qua tab Cài đặt ở bước 6.

## 3. Cài app

```bash
cd /opt/content-ultimate
sudo -u contentult python3 -m venv .venv
sudo -u contentult .venv/bin/pip install -e ".[dev,llm,embed]" yt-dlp
sudo chown -R contentult: /opt/content-ultimate
```

(`yt-dlp` cài vào venv — systemd unit đã thêm `.venv/bin` vào PATH.)

## 4. Chỉ định quản trị viên

Thêm vào `/opt/content-ultimate/.env` (tạo file nếu chưa có):

```
ADMIN_USERS=thanh
```

Tên này phải KHỚP tên đăng nhập htpasswd ở bước 5. Nhiều admin thì cách nhau dấu phẩy.
(Không đặt `ADMIN_USERS` = ai đăng nhập cũng thấy tab Cài đặt — chỉ dùng khi chạy máy cá nhân.)

## 5. Chạy service + nginx + HTTPS

```bash
# systemd
sudo cp deploy/content-ultimate.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now content-ultimate
curl -s http://127.0.0.1:8770/ | head -3        # phải thấy HTML trang chủ

# tài khoản team đầu tiên (chính là admin ở bước 4) — file đặt TRONG folder app
# để tính năng "khóa mời" tự thêm tài khoản được
sudo htpasswd -cB /opt/content-ultimate/.htpasswd thanh
sudo chown contentult:www-data /opt/content-ultimate/.htpasswd
sudo chmod 640 /opt/content-ultimate/.htpasswd
echo "HTPASSWD_FILE=/opt/content-ultimate/.htpasswd" | sudo tee -a /opt/content-ultimate/.env

# nginx
sudo cp deploy/nginx-content-ultimate.conf /etc/nginx/sites-available/content-ultimate
sudo nano /etc/nginx/sites-available/content-ultimate    # sửa server_name thành domain
sudo ln -s /etc/nginx/sites-available/content-ultimate /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# HTTPS (certbot tự sửa config + tự gia hạn)
sudo certbot --nginx -d content.example.com
```

- Không có domain riêng: dùng tên miễn phí dạng `<tên>.<IP>.sslip.io`
  (vd `outliery.45.32.107.108.sslip.io`) — certbot cấp chứng chỉ bình thường.
- **Máy đã có dịch vụ giữ cổng 443** (vd Tailscale serve — gặp thật 2026-07-08):
  nginx sẽ báo `bind() to 0.0.0.0:443 failed (98)` trong `/var/log/nginx/error.log`
  và HTTPS không lên. Sửa: trong site file đổi `listen 443 ssl;` thành
  `listen <IP-công-khai>:443 ssl;` rồi `systemctl restart nginx`.

## 6. Nhập API key (trong app, không cần SSH)

Đăng nhập bằng tài khoản admin → trang chủ có card **⚙ Cài đặt** → dán key:
Claude (Anthropic), GLM (z.ai), transcriptapi.com, YouTube Data API. Key lưu vào `.env`
trên server; dropdown model (Claude Sonnet/Opus, GLM 5.0/5.2) tự hiện theo key đã có.

## 7. Quản trị viên cấp / thu quyền user

**Cách chính — khóa mời trong app (không cần SSH):** tab ⚙ Cài đặt → mục
**👥 Mời thành viên** → "＋ Tạo khóa mời" → Copy link gửi cho thành viên → họ mở
link, tự đặt tên + mật khẩu. Khóa dùng 1 lần, hạn 7 ngày, thu hồi được khi chưa dùng;
trang `/invite` public nhưng app chặn brute-force theo IP (20 lần/5 phút).

Cách dự phòng / thu quyền (SSH):

```bash
sudo htpasswd -B /opt/content-ultimate/.htpasswd alice     # thêm user / đổi mật khẩu
sudo htpasswd -D /opt/content-ultimate/.htpasswd alice     # thu quyền
```

Có hiệu lực ngay, không cần restart gì.

## 8. Cập nhật phiên bản

```bash
rsync -a --exclude .env --exclude runs --exclude library --exclude uploads --exclude .venv \
      "Content Ultimate/" root@<IP>:/opt/content-ultimate/     # hoặc: git pull
sudo systemctl restart content-ultimate
```

## YouTube chặn bot IP server — S1 báo "không lấy được video nào"

IP datacenter (VPS) bị YouTube nghi bot ("Sign in to confirm you're not a bot" — gặp
thật 2026-07-09). Cách chữa chuẩn của yt-dlp: đặt **cookies YouTube** tại
`/opt/content-ultimate/cookies.txt` — heatmap.py tự dùng khi file tồn tại.

Xuất cookies (một trong hai cách, làm trên máy CÁ NHÂN có đăng nhập YouTube):

1. **Extension trình duyệt:** cài "Get cookies.txt LOCALLY" (Chrome Web Store) → mở
   youtube.com → bấm icon extension → Export → được file cookies.txt.
2. **yt-dlp:** `yt-dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download <url bất kỳ>`
   (macOS sẽ hỏi quyền Keychain — bấm Allow).

Đưa lên server + phân quyền:

```bash
scp cookies.txt root@<IP>:/opt/content-ultimate/cookies.txt
ssh root@<IP> 'chown contentult: /opt/content-ultimate/cookies.txt && chmod 600 /opt/content-ultimate/cookies.txt'
```

Lưu ý: cookies = phiên đăng nhập YouTube của tài khoản đó (nhạy cảm — file để 600,
KHÔNG vào git; nên dùng tài khoản Google phụ). Cookies hết hạn sau vài tuần/tháng →
S1 lại báo bot-check → xuất lại file mới, thay lên server là xong.

## Giới hạn hiện tại (biết trước khi đưa team dùng)

- **1 job nặng tại 1 thời điểm cho mỗi loại** (1 job Extractor/Writer + 1 pipeline
  Outline): người bấm sau khi đang có job chạy sẽ nhận thông báo "đang chạy" (409) —
  chờ xong rồi bấm lại. Log job hiển thị chung cho mọi người đang mở trang.
- Mỗi lần chạy pipeline/LLM là tiền thật (transcript credit, YouTube quota, token LLM)
  — các stage đều resume được, đừng xoá `runs/` để "chạy lại cho sạch".
- RAM (đo thật 2026-07-08): server nghỉ ~10MB; job Writer/Extractor ~30-150MB (LLM
  chạy ở phía API, không tốn máy mình); riêng **S4 fastembed đỉnh ~1GB** → VPS 1GB
  phải có swap (bước 1) và đừng chạy 2 pipeline outline cùng lúc (app đã tự khóa).
- Backup định kỳ 4 thứ trên server: `.env`, `runs/`, `library/`, `uploads/`.
