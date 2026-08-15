# CLAUDE.md — OUTLIERY PLATFORM v2 (bản đồ gốc)

> Repo này là bản XÂY LẠI hệ OUTLIERY theo kiến trúc tầng nền, chạy SONG SONG hệ
> thật (C:\OutlierY, cổng 8000) — dải cổng 9xxx, dữ liệu test riêng. Khi Owner
> nghiệm thu xong mới thay thế hệ cũ.
>
> **ĐỌC TRƯỚC KHI CODE: [docs/kien_truc_nen.md](docs/kien_truc_nen.md)** — hiến pháp
> kiến trúc (3 tầng, 6 luật tổ chức, hợp đồng app, IAM, bất biến kế thừa).
> Theo Luật 3 (CLAUDE.md phân tầng): file này CHỈ là bản đồ + trạng thái;
> mốc/bài học của app nào ghi vào `apps/<app>/CLAUDE.md` của app đó.

## Luật an toàn tuyệt đối (giai đoạn song song)

1. KHÔNG sửa file trong `C:\OutlierY`; không restart tác vụ nền hệ thật.
2. Qdrant test = :6343 (tools\qdrant, storage data\qdrant) — kho thật :6333 cấm đụng.
3. Dữ liệu test lấy BẢN SAO từ `D:\OUTLIERY-backup` (chỉ đọc backup).
4. Cổng mới phải ghi `docs/PORTS.md` trước khi code; chỉ dải 9xxx.

## Bản đồ

- `nen\` — tầng nền: gateway, iam, ket_cau_hinh, rules (luật cả hệ: danh_muc.csv,
  apps.json), common (danh_ba.py…). Tên `nen` vì `platform` trùng stdlib Python.
- `apps\` — app nghiệp vụ tự đủ: tri-thuc, data-analytics, to-chuc, app-mau.
- `data\` — TÁCH KHỎI CODE, gitignore, backup theo SO_DIA_BA_DU_LIEU.md.
- `docs\` — hiến pháp, PORTS, sổ địa bạ. `runbook\` — tài liệu vận hành cho người.
- `tools\` — qdrant test, scripts start-all/stop-all.ps1.

## Trạng thái (cập nhật mỗi mốc)

- 16/08/2026 — **PHASE 0 XONG**: cây thư mục + git + hiến pháp + PORTS + sổ địa bạ
  dữ liệu + danh bạ thực thể (`nen/rules/danh_muc.csv` seed 4 dòng + `nen/common/
  danh_ba.py`, 13 test pass) + venv + Qdrant test :6343 đã chạy thử readyz-200 song
  song kho thật :6333 + scripts start/stop kiểm chứng. Bài học: package tầng nền
  đặt tên `nen` — `platform` trùng module chuẩn Python (bắt trước khi nổ).
- 16/08/2026 — **PHASE 1 LÕI XONG** (27 test pass, nghiệm thu HTTP thật 6/6):
  gateway :9000 (login/session cookie ký, users.txt tạm đọc SỐNG — TODO-P2 thay
  iam.db; menu từ hợp đồng app; /suc-khoe gọi health từng app) + `nen/common/
  proxy.py` (chuyển thể app_proxy.py hệ cũ, GIỮ đủ 7 bẫy đã vá: vứt header danh
  tính giả, cắt ETag/conditional khi viết lại đường, X-Forwarded-Host/Proto,
  Location chống đúp tiền tố, tên ASCII, client dùng chung, SSE chảy thẳng; vá
  MỚI: client khóa theo event loop — TestClient đa loop làm lộ) + `nen/rules/
  apps.json` + app-mau :9190 (khuôn app chuẩn, hiện claims) + tao_user_test
  (owner/quanly/nhanvien, mk test123). Nghiệm thu: login → menu → proxy tiêm
  claims đúng, header giả 'hacker' bị vứt → sức khỏe 'đang chạy'.
- 16/08/2026 — **PHASE 2 IAM + CADDY TLS XONG** (49 test pass; nghiệm thu HTTPS
  thật): `nen/iam/` (iam.db SQLite WAL + migrations có phiên bản + schema_version;
  2 giỏ quyền — Owner tuyệt đối không tick nào đè được / ủy quyền được; 3 luật sắt
  Admin ủy quyền: không tự nâng, không đụng Owner, mọi thao tác có vết
  nhat_ky_quyen; chống tự khóa; user đầu phải Owner) + `nen/rules/phan_quyen.json`
  (luật ngoài code) + gateway nối iam.db (users.txt nghỉ hưu, ép đổi mật khẩu lần
  đầu YC6) + trang /quan-tri hợp nhất (tài khoản + hồ sơ NS + nhật ký; xóa phải gõ
  lại tên — server kiểm) + `nen/iam/nhap_users_txt.py` (migration hệ cũ, giữ
  nguyên hash, idempotent) + Caddy :9443 tls internal. Nghiệm thu HTTPS: quanly
  (Admin ủy quyền) vào quản trị 200 nhưng nút Owner-only ẩn + không vault;
  nhanvien 403; claims viewer đúng; header giả vứt.
  BẪY MỚI: (a) Caddyfile PHẢI khai tên/IP cụ thể — `https://:9443` trống hostname
  là handshake fail với client không gửi SNI (curl exit 35); (b) PS 5.1 cần
  `SecurityProtocol=Tls12` + Get-Content phải `-Encoding UTF8` khi kiểm chuỗi Việt.
  User nhắc giữa phiên: áp nguyên tắc KARPATHY (tối giản/test-first/surgical) +
  PONYTAIL (thang 7 bậc, diff ngắn nhất, đánh dấu `ponytail:` chỗ cắt góc) — đã
  lưu memory vĩnh viễn, 2 file gốc trong hệ.
- KẾ TIẾP — PHASE 3 Két cấu hình: config ≠ secret (2 ngăn), vai LLM → model,
  API loopback cho app đọc, UI Owner /cai-dat, timeout/retry mặc định một chỗ.
