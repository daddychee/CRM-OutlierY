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
- 16/08/2026 — **P5.2 TRI-THUC + P5.3 TO-CHUC/VAULT XONG (2 agent song song, kiểm
  lại + nghiệm thu sống): TOÀN HỆ 471 TEST PASS / 4 SKIP / 0 FAIL.**
  · tri-thuc :9101 (306 test): 48 route RAG đầy đủ — hỏi–đáp stream/đa chiều/góc
    nhìn ngoài, kho tài liệu 7 route, kho-thiếu 7, nguồn ngoài 13, lịch sử 5,
    giám sát; hoi_dap.html script byte-identical; claims thay auth.
  · to-chuc :9103 (31 test): KPI (trang /kpi mới Manager+) + chấm công + NAS +
    VAULT (chỉ Owner). kpi.py bỏ import chéo → đọc file + ca nguồn-chết→None.
  · NGHIỆM THU SỐNG RAG THẬT: kho test = bản sao backup 18 tài liệu → Qdrant
    :6343 = 157 point 0 lỗi (nap_kho_test.py); Owner hỏi AdSense → trích ĐÚNG
    KD-2026-1814CB + 71369B (y hệt nghiệm thu kinh điển hệ cũ); nhân viên VH-L2
    cùng câu → 0 nguồn CHẶN LẶNG LẼ; hỏi ngâm kênh QUA GATEWAY trọn chuỗi proxy
    claims → trích đúng 71369B. Writer đang mock (chưa nhập key vào két — Owner
    nhập ở /cai-dat khi test thật).
  · Việc treo P5 (đã ghi trong báo cáo agent + CLAUDE.md từng app): dọn sidebar
    link hệ cũ trong base.html các app; gate tick-lẻ về co_quyen(); điểm hứng
    chấm công toàn hệ ở gateway; /khoi-phuc safekey vào IAM; nas_sync vào gateway;
    connector API thay đọc-file-chéo của kpi.
  BẪY MỚI PHIÊN NÀY: Out-File PS 5.1 ghi BOM làm FastAPI 422 input-null (dùng
  [IO.File]::WriteAllText không BOM); route /hoi nhận FORM không phải JSON.
- 16/08/2026 — **CHỐT UI/FLOW VỚI OWNER + ĐƯA UX VỀ ĐÚNG V1** (commit d64a00e; toàn hệ
  473 pass / 3 skip). Bối cảnh: Owner phê bình đúng — v2 tự chế trang chủ "bảng chọn
  app" khác hẳn V1, tên thư mục kỹ thuật (tri-thuc…) rò ra màn hình, thẻ Tổ chức bấm
  là 404 (redirect /nas khi chưa cấu hình NAS_DUONG_DAN), sidebar DA rỗng.
  **[docs/UI_FLOW.md](docs/UI_FLOW.md) ra đời = HỢP ĐỒNG giao diện**: UI/flow v2 chép
  đúng V1, khác một mục phải hỏi Owner trước. Owner chốt 3 điểm: app phụ chưa di trú
  ẨN HẲN; trang mới v2 (Sức khỏe hệ, quản trị IAM) nhét vào popup Management; launcher
  XÓA HẲN. Đã làm: "/" → 303 thẳng Hỏi–đáp; proxy phát claims **X-Remote-Apps** (slug
  được vào + cờ nas/quan-tri — GATEWAY quyết sidebar, app không tự đoán quyền;
  `nen/common/sidebar.py` dùng chung, DA + to-chuc nối context processor vì trước
  thiếu sb_user nên sidebar trống); sửa link chéo app trong hoi_dap.html NGOÀI 5 khối
  script đóng băng; thêm dòng Sức khỏe hệ vào Management 4 template; gateway mount
  /static chuẩn (fonts + theme.js). Nghiệm thu ĐÚNG ĐƯỜNG NGƯỜI DÙNG BẤM: Owner 12
  đích sidebar đều 200, nhân viên thường bị ẩn đúng (không DA/quản trị/Vault), HTTPS
  trọn luồng. BẪY MỚI: (a) comment CSS trong `<style>` của hoi_dap.html chứa NGUYÊN
  VĂN chữ `<script>` → regex tách khối script nuốt cả sidebar (dính 2 lần trước khi
  tìm ra — tách khối phải loại `<script>` nằm trong `<style>`); (b) file V1 trên máy
  Windows là CRLF, bản v2 LF — so byte khối script phải quy đồng newline; (c) fixture
  test dùng app-mau ĐANG CHẠY SẴN :9190 → sửa code app-mau phải restart tiến trình
  sống rồi mới tin kết quả test.
- 16/08/2026 — **KHU QUẢN TRỊ NỀN + PHÂN QUYỀN V1 + 2 MIỀN XONG** (commit a88c384 /
  0c08a4f + caddy; toàn hệ 480 pass / 3 skip; nghiệm thu sống HTTPS 2 miền). Làm theo
  3 phê bình Owner (chưa thấy UI khối nền / phân quyền lệch V1 / URL multiplex) +
  bản chốt UI_FLOW.md mục 5-7:
  · KHU /nen 8 TRANG mỗi trang MỘT việc: /nen (tổng quan ĐẾ: dịch vụ sống/chết gồm
    Qdrant + tài khoản theo level + hồ sơ + danh bạ + két key + backup gần nhất —
    số thật, nguồn chết trả None không bịa 0) · tai-khoan · nhan-su · phan-quyen
    (bảng TICK: chọn người → app × hành động, tick lẻ đè mặc định qua co_quyen sẵn
    có, công tắc Admin ủy quyền mặc định TẮT, giỏ Owner tuyệt đối không tick được)
    · cau-hinh (két LLM) · du-lieu (sổ địa bạ sống từ apps.json + tuổi backup) ·
    nhat-ky · ung-dung. /quan-tri /cai-dat /suc-khoe nghỉ hưu → 303, template cũ xóa.
  · SỬA LỖI PHÂN QUYỀN LỆCH V1: iam.quyen_nhan_su = Owner + Hành chính Nhân sự L3+
    (bản trước khóa mất HR); MỘT hàm dùng chung gate + tao_nguoi + cờ sidebar
    'quan-tri'. Test ghim: HR L3 vào nhan-su 200 + tạo hồ sơ, 403 tai-khoan/phan-quyen.
  · 2 MIỀN: outliery.test (chat/app) + quantri.outliery.test (→ /nen) qua Caddy tls
    internal; hosts máy chủ +2 dòng; cookie Domain=.outliery.test khi vào bằng miền
    (MỘT login chạy mọi miền con — đo sống: login miền chính, cùng cookie mở miền
    quản trị), vào bằng IP giữ host-only.
  Việc treo: Caddy root CA cho máy nhân viên khi mở LAN (hoặc domain thật lúc thay
  thế); DNS Server role zone outliery.lan lúc thay thế; mỗi-app-một-miền (bỏ tầng
  viết-lại đường proxy) để giai đoạn thay thế.
- 16/08/2026 — **UI ĐỢT 2 XONG: TIẾNG ANH + USER MENU KIỂU CLAUDE + TAB DATABASE +
  PROFILE** (4 commit dbff341/98507b9/f2be73a/9140710; toàn hệ 482 pass / 3 skip;
  nghiệm thu sống từng vai qua 2 miền). Theo UI_FLOW.md mục 8 Owner chốt từng điểm:
  · VỎ ĐIỀU HƯỚNG sang TIẾNG ANH (General: Overview/Accounts/People/Permissions/
    AI Models/Data & Backup/Audit Log/Applications; Tools/Recents/New chat; Staff
    thay Nhân viên; login/messages gateway EN). Chuỗi VN TRONG 5 khối script chat
    đóng băng để ĐỢT RIÊNG (Owner đã cho phép can thiệp logic khi cần chuẩn).
  · Tab Monitoring → **Database**: Input (Datafeed cũ) / Library / Gap; NGUỒN NGOÀI
    GỘP vào Input = 2 tab con Upload | External source (gộp điều hướng, route +
    logic từng luồng giữ nguyên); mục Nhân sự rời sidebar (People trong General).
  · **USER MENU kiểu Claude** thay popup Management: chip đáy sidebar "Display
    name — Rank" cho MỌI NGƯỜI; menu Profile/Theme/NAS(ẩn khi chưa cấu hình)/
    Log out + Owner: Tracking/General/Vault + HR L3+: General mở thẳng People.
    GIỮ 4 ID sb-mgmt* vì JS popup nằm TRONG khối script đóng băng của hoi_dap —
    đổi markup không đổi ID là logic cũ chạy y nguyên.
  · **Trang /profile** tự phục vụ: display name (→ chip, chảy qua claims mới
    X-Remote-Name URL-encode) + email/điện thoại (iam migration 002); bộ phận/
    level CHỈ ĐỌC (chống tự thăng quyền); đổi mật khẩu BẮT gõ mật khẩu hiện tại
    (luật V1 — v2 từng thiếu). Khu General về cơ chế theme chung outliery_theme.
  BẪY MỚI: (a) template trong repo trộn EOL — index.html CRLF, hoi_dap LF: script
  sửa hàng loạt phải dò EOL từng file; (b) test ghim schema_version==1 tự vỡ khi
  thêm migration → ghim LUẬT (= số file .sql); (c) nhãn UI nằm trong assertion
  test (Chưa có cuộc nào…) — dịch nhãn phải quét cả tests. VIỆC TREO đợt sau:
  dịch chuỗi VN trong 5 khối script chat (phá đóng băng có chủ đích + nghiệm thu
  chat kỹ — Owner đã cho phép); nhãn EN các trang nội dung app (kho, nguồn, KPI…).
