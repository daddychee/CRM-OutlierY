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
- 16/08/2026 — **P3 KÉT + P4 CHUẨN DỮ LIỆU + P5.1 DATA-ANALYTICS + P6 CẦU NỐI +
  P7.1 SCALE — XONG, mỗi phase một commit xanh:**
  · P3 (`1d4aefa`): két 2 ngăn config/secret (Fernet), vai LLM, API loopback
    /api/cau-hinh/llm/<vai>, /cai-dat chỉ Owner (Admin ủy quyền 403 có test).
  · P4 (`772799a`): log JSON-lines năm/tháng; backup theo manifest (sqlite
    VACUUM INTO / kho-file copy / qdrant API-snapshot); DIỄN TẬP RESTORE tự động
    trong test; du_lieu_nen khai trong apps.json.
  · P5.1 (`7c6a515`): app data-analytics di trú TRỌN — 64 test + E2E thật qua
    gateway (report 80 video → tác vụ nền → lịch sử; quyền KD-L2/L4 đúng).
    Khuôn di trú chuẩn cho các app sau: claims 4 header (Dept URL-encode),
    env setdefault trước import, dien_giai tách khỏi RAG có ponytail note.
  · P6 (`c7febf4`): cầu nối — connector bao_cao_kenh + router luật qua danh bạ +
    /api/cau-noi/hoi-so-lieu. Nghiệm thu sống: hỏi kênh outland ra đúng báo cáo
    kèm nguồn + tuổi dữ liệu; kênh lạ từ chối thẳng kèm gợi ý.
  · P7 (`bc97b8e` + trước đó): runbook 3 quyển + KE_HOACH_THAY_THE (rollback 5
    phút) + load test ĐO TỪNG TẦNG: 4 bệnh block-event-loop đã trả (login bcrypt
    sync-def, connector sync-def, cache luật theo mtime, proxy auth threadpool)
    + chính bài đo sai (50 client 1 loop Windows). KẾT QUẢ: 50 phiên đồng thời
    0 lỗi, trung vị 2.14s/phiên 6 request.
  ⚠️ Ghi chú lịch sử git: `bc97b8e` lỡ lẫn khung DỞ của apps/tri-thuc +
  apps/to-chuc (2 agent làm song song, git add -A quét phải — bài học: add theo
  path khi có việc song song). Bản hoàn chỉnh 2 app đó nằm ở commit sau.
- KẾ TIẾP: P5.2 tri-thuc + P5.3 to-chuc/vault (agent đang làm) → test-all toàn
  hệ → nghiệm thu sống tri-thuc (kho test từ backup + Qdrant 6343) → báo cáo Owner.
