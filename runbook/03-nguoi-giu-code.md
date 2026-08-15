# HỒ SƠ CHO NGƯỜI GIỮ CODE — OUTLIERY Platform v2

> Bạn là dev/người giữ app mới nhận bàn giao. Đọc theo thứ tự này, đừng nhảy cóc.

## 1. Đọc gì trước (30 phút)
1. `CLAUDE.md` (gốc repo) — bản đồ + trạng thái.
2. `docs/kien_truc_nen.md` — HIẾN PHÁP: 3 tầng, 6 luật tổ chức, bất biến. Mọi
   thay đổi phải theo đây; muốn đổi hiến pháp phải hỏi Owner.
3. `docs/SO_DIA_BA_DU_LIEU.md` — dữ liệu nào quý, backup ra sao. Code là công cụ,
   DATA là tài sản: nghi ngờ gì về dữ liệu thì DỪNG.
4. `apps/<app>/CLAUDE.md` của app bạn sắp sửa.

## 2. Luật làm việc (không thương lượng)
- **Test trước — chỉ code tiếp khi test xanh.** Chạy toàn hệ:
  `powershell -File tools\scripts\test-all.ps1`
  Chạy một app: `cd apps\<app>` rồi `..\..\.venv\Scripts\python.exe -m pytest -q`.
- **Karpathy + Ponytail** (bắt buộc, Owner chốt): nghĩ trước khi code, nêu giả
  định; code tối thiểu; sửa có phẫu thuật; leo thang 7 bậc trước khi viết mới
  (có cần không → repo có sẵn chưa → stdlib → nền tảng → dependency đã cài →
  một dòng được không → viết tối thiểu); chỗ cắt góc đánh dấu `ponytail:` kèm
  trần + đường nâng cấp.
- **App tự đủ**: chỉ import `nen/common`; CẤM import chéo app; muốn dữ liệu app
  khác → connector (xem `nen/common/cau_noi.py` làm mẫu).
- **Không bao giờ** sửa gì trong `C:\OutlierY` (hệ cũ đang chạy thật cho team).
- Mỗi mốc một commit tiếng Việt không dấu, message nói VÌ SAO.

## 3. Chạy hệ dev
`tools\scripts\start-all.ps1` / `stop-all.ps1`. Cổng: xem `docs/PORTS.md` —
thêm dịch vụ = ghi PORTS.md TRƯỚC khi code. User test: owner/quanly/nhanvien,
mật khẩu test123 (`python -m nen.gateway.tao_user_test`).

## 4. Thêm một app mới vào hệ
1. Khai `nen/rules/apps.json` (slug, cổng, tiền tố, health, du_lieu) +
   `nen/rules/phan_quyen.json` (điều kiện vào + vai).
2. Dựng `apps/<slug>/` theo khuôn `apps/app-mau` (nhỏ) hoặc
   `apps/data-analytics` (đầy đủ): nhận claims X-Remote-User/Level/Role/Dept
   (Dept phải urllib.parse.unquote), trả /health, data vào `data/<slug>/{db,kho}`.
3. Thêm dịch vụ vào `tools/scripts/start-all.ps1`. Test + nghiệm thu qua gateway.

## 5. Bẫy đã biết (đừng dẫm lại)
Xem mục Trạng thái trong CLAUDE.md gốc — mỗi mốc đều ghi bẫy: package tên `nen`
vì `platform` trùng stdlib; Caddyfile phải khai tên/IP (trống hostname là chết
handshake với client không SNI); PS 5.1 — TLS1.2 phải bật tay, Get-Content cần
-Encoding UTF8, KHÔNG để dấu ngoặc kép trong commit message; client httpx dùng
chung phải khóa theo event loop; header HTTP chỉ nhận ASCII (bộ phận đi qua
URL-encode).
