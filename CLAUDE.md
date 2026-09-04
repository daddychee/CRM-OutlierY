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
- `apps\` — app nghiệp vụ tự đủ: ai-agent (tên cũ tri-thuc — Owner chốt 16/08:
  app này là AI AGENT từ đầu), data-analytics, to-chuc, app-mau.
- `data\` — TÁCH KHỎI CODE, gitignore, backup theo SO_DIA_BA_DU_LIEU.md.
- `docs\` — hiến pháp, PORTS, sổ địa bạ. `runbook\` — tài liệu vận hành cho người.
- `tools\` — qdrant test, scripts start-all/stop-all.ps1.

## Sổ chủ đề (đọc file nhỏ ĐÚNG task — đừng dò cả file này)

Quy ước từ 16/08/2026 (user chốt): mỗi mạch việc lớn có MỘT sổ .md riêng trong
`docs/`; CLAUDE.md chỉ ghi mốc 1-2 dòng trỏ về sổ. Nhận task loại nào → đọc sổ
đó TRƯỚC khi làm. Task lớn mới chưa có sổ → ĐỀ XUẤT user tạo sổ tương ứng.

- **UI / giao diện**: [docs/UI.md](docs/UI.md) — nguyên tắc, lịch sử đợt, bẫy
  (+ hợp đồng Owner: [docs/UI_FLOW.md](docs/UI_FLOW.md)).
- **Chuyển ngữ EN**: [docs/TRANSLATE.md](docs/TRANSLATE.md) — luật vàng
  dịch/không-dịch, quy trình, trạng thái từng đợt.
- **Khối đế (danh bạ kênh/ngách, API keys, IAM, két)**: [docs/DE.md](docs/DE.md)
  — đề xuất tái thiết + 4 quyết định Owner + nhịp Đ1-Đ4.
- **Model LLM (app nào gọi model nào, đổi model, thinking/reasoning)**:
  [docs/model-llm.md](docs/model-llm.md) — luật resolve model từ két, công tắc
  suy luận theo đời model GLM (đo thật), cách đổi + phải restart gì.
- **Phòng thủ API bên thứ 3 (allowlist host, van secret, trần chi/ngày, che PII)**:
  [docs/phong-thu-api-ngoai.md](docs/phong-thu-api-ngoai.md) — 6 lớp, luật bắt
  buộc, checklist đã-có/còn-thiếu; van code ở `nen/common/phong_thu.py`.

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
- 16/08/2026 — **UI ĐỢT 4 XONG: dịch EN 14 trang nội dung 3 app** (`16d36a3` +
  `b7a5cfa`; toàn hệ 482 pass / 3 skip). Chi tiết, luật vàng, việc còn (đợt 5
  script chat + đợt 6 chuỗi server): xem docs/TRANSLATE.md. Cùng ngày lập cơ chế
  SỔ CHỦ ĐỀ (docs/UI.md + docs/TRANSLATE.md) — mốc từ nay ghi 1-2 dòng trỏ sổ.
- 16/08/2026 — **UI ĐỢT 5 XONG — 3 phê bình Owner** (`74c6ef7` + `03a47b5`; 482 pass /
  3 skip; nghiệm thu sống HTTPS): fix ZOOM chuyển trang (cache font — bẫy FOUT),
  URL GỌN cấp 1 khớp nút bấm (UI_FLOW.md mục 9 mới), icon minimalist hết emoji màu
  markup tĩnh. Chi tiết + bẫy + việc treo: docs/UI.md.
- 16/08/2026 — **SỔ ĐỀ XUẤT TÁI THIẾT KHỐI ĐẾ (docs/DE.md) — CHỜ Owner duyệt.**
  Từ 2 khảo sát (đế v2 + 9 app hệ cũ): trục thực thể kênh/ngách/thị trường
  (danh_ba.db + 2 trang Channels/Niches), mảnh API keys tập trung (YouTube pool
  + LLM + Veo/Flow, trang /general/api-keys), quyền chiều thực thể, 4 quyết định
  Owner đã chốt (phạm vi kênh nhà · đa ngữ 2 kênh nối bản-sao · nhập tay từ đầu ·
  Manager tạo/sửa - Owner xóa). Chi tiết + nhịp Đ1-Đ4: docs/DE.md.
- 16/08/2026 — **ĐỔI TÊN APP tri-thuc → ai-agent ("AI Agent")** theo chốt Owner
  ("app này là AI Agent từ đầu, không có app nào tên tri thức"): thư mục + slug +
  hợp đồng (ten "AI Agent") + data/ai-agent + 86 tham chiếu toàn repo; gateway đỡ
  slug cũ (URL/fetch /app/tri-thuc không vỡ); alias Qdrant kho_tri_thuc GIỮ (tên
  kho dữ liệu, không phải tên app). 482 pass / 3 skip; nghiệm thu sống HTTPS.
- 18/08/2026 — **APP MỚI video-review :9114 — feedback video kiểu Frame.io** (app V3
  đầu tiên VIẾT MỚI, không di trú; Owner chốt hướng TỪNG BƯỚC: nằm ở V3 · phạm vi
  MVP · quyền vao-L1/duyet-L3/xoa-L4 · NAS "chép vào kho" · KHÔNG nhóm dự án vì
  review xong là xóa): bình luận gắn mốc thời gian (bấm là tua) + vẽ chú thích
  khung hình + trạng thái duyệt + gỡ mềm; danh sách TAB "Awaiting review" — video
  up lên chưa ai review nổi bật, mặc định mở khi còn video chờ, tìm không dấu +
  Mine only; UPLOAD TỪNG KHÚC 64MB trần 20GB (video thật team 2-10GB H.264 phát
  native — proxy không phình RAM, KHÔNG sửa proxy; /media trả 206 từng khúc 8MB)
  + DROPZONE kéo-thả theo brand + NẠP TỪ NAS chép nền % thật. 33 test app +
  160 test nền pass; đăng ký đủ PORTS/apps.json/phan_quyen/start-all; 5 commit
  (97f4938→b46fb5d). Chi tiết + quyết định thiết kế + bẫy + việc treo:
  apps/video-review/CLAUDE.md.
- 18/08/2026 — **RADARY POOL THEO THỊ TRƯỜNG** (user chốt: pool = 1 thị trường,
  danh mục từ đế, ngưỡng/alert riêng tự có theo pool): gateway phát danh mục
  loopback + market trên workspace + tách pool chuyển kênh GIỮ LỊCH SỬ + UI 4
  chỗ; root 182 + radary 14 pass. Chi tiết + nghiệm thu chờ Owner:
  [docs/RADARY_THI_TRUONG.md](docs/RADARY_THI_TRUONG.md).
- 18/08/2026 — **NAS TRỌN VÀO V2 (mảnh tầng nền)**: `nen/common/nas_sync.py` mới
  (đồng bộ tài khoản Windows theo mật khẩu OUTLIERY, DI TRÚ từ hệ cũ, KHÔNG đụng
  file nào trong C:\OutlierY) — gateway gọi lúc đăng nhập/tự đổi mật khẩu (3 chỗ:
  `/login`, `/profile/mat-khau`, `/doi-mat-khau`); nhóm Windows tính qua hành động
  IAM mới `nas_cap_cao` (apps.to-chuc, MỘT CỬA `co_quyen()` — ô tick lẻ/cấp truy cập
  tự ăn, không cần code riêng như hệ cũ); to-chuc hết hard-code `tt_nas='tat'`, đọc
  thật. Sổ `data/nen/nas-dong-bo.json` khai trong apps.json (Luật 6). BẪY ĐẶT TÊN
  IAM: khóa hành động chứa `toan_quyen`/`xoa`/`sua`/`tao`/`them` bị `iam.vai_cho_app()`
  dò substring nuốt nhầm vào luật suy vai app (dính thật, test_iam.py bắt được) —
  đổi `nas_cap_cao`. 177 test root + 62 to-chuc pass. Chi tiết: apps/to-chuc/CLAUDE.md.
- 18/08/2026 — **THỊ TRƯỜNG THUỘC TỪNG NGÁCH, USER CHỌN** (commit c5812bc; nen danh
  bạ 30 test + DA 106 test xanh; nghiệm thu sống DB thật). Owner sửa luật: hết cảnh
  "mọi niche mặc định có cả 3 thị trường Hàn/Mỹ/TBN" — gốc bệnh là thi_truong bảng
  TOÀN CỤC không có liên kết ngách↔thị trường. Sửa: danh bạ migration 002 bảng
  ngach_thi_truong (ngách mới = 0 thị trường, dat_thi_truong_ngach thay cả tập) +
  BACKFILL từ thực tế kênh đang đứng (LIFE IN→US+Spain, OLD→US, Korea không dính
  ngách nào); General→Niches thêm cột Markets + checkbox chọn trong modal; DA
  dashboard pills/dropdown New report lọc theo thị trường CỦA ngách (thay lệnh
  "liệt kê đủ danh bạ" sáng cùng ngày), tạo report chặn 400 khi thị trường chưa
  thuộc ngách — DA KHÔNG tự ghi danh bạ (Luật một chiều). LƯU Ý phiên song song:
  main.py/CLAUDE.md commit theo HUNK, 4 fail test_khung_app/test_radary là nền dở
  của phiên khác (stash đối chứng), iam.db test đã bị thay máu còn 2 tài khoản —
  nghiệm thu gateway bằng IAM cách ly + danh bạ thật.
- 19/08/2026 — **SEO OPTIMIZE VÀO V3 (APPS.md app 4/6, cổng 9115)** — đúng khuôn
  6 bước: SSO adapter Actions-first (khóa hành động MỚI `van_hanh` KD L2 → vai
  seo — vai này KHÔNG chỉ-đọc nên không để DEFAULT như niche), tài khoản CHỈ từ
  khối nền (gỡ sync_sso, users.json thành di sản chỉ-đọc — lệnh user 19/08),
  12 cửa quản trị 404 khi SSO, khóa từ két (trich_kenh pool xoay vòng +
  sinh_metadata). Root 191 pass + app 13; nghiệm thu sống 5 vai qua 9115.
  Chi tiết + việc chờ Owner (migration khóa, restart gateway ăn alias):
  docs/APPS.md nhật ký 19/08 + apps/seo-optimize/CLAUDE.md.
  ⚠️ Ghi chú lịch sử git: nội dung mạch SEO nằm trong commit `0c03c3c` (message
  RadarY) — 2 phiên song song chung MỘT index, phiên kia commit đúng lúc phần SEO
  đang stage. Bài học (nối bc97b8e): repo nhiều phiên thì stage xong phải commit
  NGAY, không để index nóng.
- 23/08/2026 — **GLM 5.3 VÀO HỆ + MỘT LUẬT MODEL DUY NHẤT** (sổ:
  [docs/model-llm.md](docs/model-llm.md)). Owner đổi khóa GLM sang `glm-5.3`; 5/10
  việc LLM đi theo ngay, 4 việc còn đặt model riêng (content x2, ai-agent·extract,
  DA·dien_giai) vẫn đè bản cũ, writer giữ `glm-4.5-air` theo chốt. BA VIỆC LÀM:
  (a) **vá lệch nguồn sự thật** — route `api-khoa` trước đây trả model rỗng thẳng,
  không lùi về model của khóa → Owner đổi trên UI mà niche/seo/radary vẫn chạy hằng
  số hardcode, im lặng; giờ hai route cùng luật (việc thắng khóa, khóa thắng mặc
  định), test ghim. (b) **ô Model ở Per-app config: gõ tay → dropdown** + lựa chọn
  "— theo khóa —" (trước đây ô trống = giữ nguyên nên KHÔNG bỏ được model riêng);
  thêm hằng `MODEL_THEO_KHOA`. (c) **công tắc suy luận theo ĐỜI model**: glm-5.3
  KHÔNG tắt được thinking (z.ai 1210, có mặt field `thinking` là 400) phải dùng
  `reasoning_effort` low/high/max; ngược lại glm-5.2 KHÔNG giảm reasoning theo
  `reasoning_effort` nên vẫn phải `thinking:disabled` — sửa 3 app (seo/content/
  niche), nghiệm thu gọi THẬT cả 3 đường (JSON + 2 đường SSE). Mặc định hardcode
  GIỮ ở `glm-5.2` (bản đang chạy ổn) — riêng radary sửa `glm-4-plus` (id đã biến
  mất khỏi /models, diễn giải hỏng lặng lẽ) về `glm-5.2`. Bẫy đọc lỗi: model chưa
  mở cho gói trả **429 1302**, không phải 403 — phân biệt bằng cách gọi model khác
  ngay sau đó. Suite: nền 202 · content 296 · niche 12 · seo 13 · radary 116/1 nền.
- 24/08/2026 — **AUTHOR EXTRACT: NĂM CẢI TIẾN + BÁO CÁO** (sổ:
  [docs/kich-ban-studio.md](docs/kich-ban-studio.md) mục 14; 6 commit, content 371 pass,
  nền 202 pass). Owner đưa bản đánh giá của Grok về "trích xuất giọng văn → cấu trúc hóa
  → cho AI viết tương đồng" và duyệt làm cả năm. **Chẩn đoán mở đầu**: `profile.json` có
  8 trường mà `generator.py` đọc đúng HAI — `reproduction_targets` tính từ tháng 7 và
  CHƯA BAO GIỜ vào prompt (chữ `sentence_len` xuất hiện 0 lần). **C1** cửa ổn định chạy
  ngược: A013 (1 file/3.726 từ) cắt ra ĐÚNG MỘT điểm đo → spread 0.0 → giữ 17/17 và mọi
  sd = 0.0, trong khi A014 (25.392 từ) chỉ giữ 7/17 vì có phương sai thật; nay đơn vị đo
  co giãn, dưới 3 điểm thì `do_duoc=False` và `evaluate_script` bỏ qua (trước đây sd=0.0
  bị đọc thành band 5% — thứ chưa đo được thành tiêu chuẩn chặt nhất bảng). Kho: sd=0 giả
  35 → 0. **C2** nhịp câu là chiều BẮT BUỘC: `select_exemplars` chỉ nhìn tập keep=True nên
  nó chọn mẫu bằng hư từ và TTR, KHÔNG nhìn nhịp — gốc của bảng 22/08; lệch nhịp mẫu↔corpus
  6,41 → 0,47, tốt hơn 10/12. **C4** thước thứ ba `delta.py` (Burrows's Delta, 0 token):
  leave-one-out nhận đúng 11/12, và lộ ra **kho 12 hồ sơ chỉ có 8 giọng thật** — A003=A008=
  A011 (đã biết) và **A007=A012 (chưa ai biết)**. **C5** `dien_ngon.py` 9 chiều lập trường/
  diễn ngôn/cú pháp ở KHÓA RIÊNG (không trộn thang chấm — bài học `punct_freq_total`):
  "you"/1.000 từ A009 37,8 · A013 8,1 · A002 1,2. **C3** mở kênh dẫn số đo vào prompt —
  **A/B 15 lượt BÁC**: lệch nhịp tắt 0,53 vs bật 0,72, bài ngắn hơn ~9% ⇒ mặc định TẮT
  trong CODE, giữ cơ chế + test để thử lại với glm-5.3 (5.3 bám neo, 5.2 thì không).
  **BÁO CÁO** `bao_cao.py`: `build` xong tự ghi `bao-cao-extract.md` cạnh profile (máy đã
  đọc gì · đo được gì kèm VÌ SAO giữ/loại · Delta so kho · in nguyên văn khối đi vào
  prompt) + `bao_cao_kho()` + lệnh CLI `bao-cao`, 0 token. Ba lỗi trình bày bắt được khi
  ĐỌC báo cáo thật chứ không phải từ test. **Còn lại**: chạy lại extract ghi đè 12 hồ sơ
  thật (việc của Owner — đang phục vụ team); dọn 5 tên/2 giọng trùng; nạp thêm corpus cho
  A013/A010/A007/A012.

- 24/08/2026 — **GENERAL: ĐỔI DANH MỤC VÒNG ĐỜI + GIÓNG LƯỚI API KEYS** (commit
  `7b8a4c2`, suite nền 206 pass). Owner duyệt từng ý trước khi code vì khối general
  chạm mọi app. **(1) Loại kênh** còn `compilation/narrator/documentary`; giá trị cũ
  của kênh đã khai (K-OUTLAND `giai_tri`) KHÔNG bị xóa — form sửa thêm option
  grandfather "(legacy — reselect)" theo lệ 04/08. **Data Analytics giữ danh mục
  RIÊNG 6 loại** (`content_type_profiles.csv`) — Owner chốt không rút theo, hồ sơ
  `tre_em` (nới retention ×1.4, RPM thấp là quy luật COPPA) còn nguyên giá trị đọc số.
  **(2) Niche**: Exploiting · Scaling · Maintaining · Paused (bỏ `thu`/Testing; mặc
  định tạo mới → `khai_thac`). **(3) Lifecycle kênh** 5 nấc: Incubating · Testing ·
  Traction · Monetized · **Shadowbanned**; bỏ `ngu_dong`/Dormant; `khai_tu`/Retired
  thành **NẤC ẨN** — `doi_trang_thai_kenh()` mặc định từ chối, chỉ `khai_tu_kenh()`
  (nút Retire, chỉ Owner) đặt được (trước POST thẳng vào đường stepper cũng retire
  được), kênh đã retire vẫn hiện badge + lọc tìm lại được. **(4) API keys**: mọi khối
  dùng CHUNG lưới 6 cột cố định (`table-layout:fixed` + `colgroup`, khối không có
  Model giữ ô trống) → các bảng thẳng một trục; bỏ cột Usage + Added.
  **Migration 003** (đổi CHECK = dựng lại bảng `ngach` + `kenh`): DB thật 4 kênh +
  6 ngách di trú nguyên vẹn, `foreign_key_check` sạch, backup `VACUUM INTO` trước.
  **BÀI HỌC**: migration đổi tập giá trị phải MAP giá trị đã bỏ (`thu`→`khai_thac`,
  `ngu_dong`→`khai_tu`) cho DB đời cũ ở máy khác — không map thì CHECK mới giết
  migration giữa chừng; **test `test_backfill_002` bắt được ca này**, DB thật không
  có bản ghi nào rơi vào đó nên nếu chỉ nghiệm thu trên máy này sẽ không bao giờ lộ.
  **Còn lại**: Owner chọn lại loại cho K-OUTLAND (form không tự đổi để khỏi bịa).

- 31/08/2026 — **THUMBY V1 (:9119) — app mô phỏng vị trí hiển thị thumbnail
  YouTube, XONG + đã sống trên hệ** (4 commit 3d17778→0ad3d68; sổ chi tiết:
  `docs/thumby.md` — spec, 5 bước Owner duyệt từng bước, nhật ký, việc treo).
  Thả ảnh A/B + title → xem đúng cỡ thật ở Suggested 168px / Home / Search /
  Trang kênh / điện thoại, dark+light, squint, tooltip đo điểm cắt title.
  Ảnh KHÔNG rời trình duyệt (app không route ghi — test ghim). Quyền vào KD
  L2. Bài học mới cho app sau: base `.noi-dung` bó 900px — trang rộng phải
  khai block `lop_noi_dung=rong`; alias `/thumby` gateway nằm working tree
  chờ phiên RenderY commit. KẾ TIẾP: GĐ2 nối RadarY (đọc DB chỉ-đọc) —
  thumb video ĐANG NỔ CÙNG CHỦ ĐỀ với title nhập đứng cạnh A/B.
- 31/08/2026 — **GIÁM SÁT SỨC KHỎE HỆ — tab Applications thành trạm điều hành,
  B1+B2+B3 xong test-first** (4 commit 73a690a→c835fd1 + plannery lồng 4aeab76;
  sổ chi tiết: `docs/giam-sat-suc-khoe.md` — kiến trúc, nhật ký, việc còn).
  Hợp đồng sức khỏe 2 tầng: `health` liveness + `suc_khoe` TÙY CHỌN khai module
  ok/canh_bao/loi (khuôn `nen/common/suc_khoe.py`, app-mau làm mẫu, ai-agent
  exemplar — module kho-vector bắt ca kho-rỗng-lặng-lẽ 31/07); trạm đo lỗi tại
  proxy (`nen/common/dem_loi.py`): 5xx/502/504 theo app cửa sổ 5', cột Errors 5′
  + Modules trên tab. Root 253 pass; ai-agent 312 pass. Plannery /health thật
  (hết mượn /api/me); RENDERY còn nợ /health (repo F:, chờ lúc không job dựng).
  KẾ TIẾP: B4 heartbeat việc nền → B5 cảnh báo ntfy → B6 canary; lan suc_khoe
  sang radary/to-chuc/thumby.
- 02/09/2026 — **HỆ KIỂM LOGIC "16 logic = 16 sơ đồ" — Owner chốt sau 4 vòng UI**
  (6 commit nền/UI 19ccad3→…, radary lồng 1981b3d; sổ chi tiết:
  `docs/giam-sat-suc-khoe.md` mục 02/09). Owner chỉ ra khuyết điểm cấp kiến trúc:
  canary chỉ kiểm HẠ TẦNG (radary 2 canary / ~16 logic nghiệp vụ thật), sơ đồ vận
  hành chỉ show input→kết quả **không có logic nào trên sợi dây**. Chốt 2 tầng:
  **① Flow toàn map BẤT BIẾN** + **TRẠM KIỂM trên từng dây** (tổng hợp logic gắn
  `canh:[tu,den]`; ✓ đúng hết · ✗ có sai · số vàng có chưa kiểm · **? = dây chưa
  phủ kiểm, tự tố cáo lỗ hổng** · ×N số logic); **② Hệ kiểm — mỗi logic MỘT sơ đồ,
  hiện LẦN LƯỢT** (bấm dòng bảng/trạm → sơ đồ + panel đổi theo; trạm trên mũi tên
  i = `kiem[i]` ↔ `cho[i]`; panel = logic bằng lời + SỐ ĐO TỪNG CHẶNG thật + kỳ
  vọng ✓/✗ + nút KIỂM LOGIC NÀY). **BA LOẠI KIỂM**: GỌI (canary gọi cửa kiểm, 0
  quota) · VẾT (đọc sổ lần chạy thật — logic tốn tiền) · BẤT BIẾN (dữ liệu đã ghi).
  NỀN: canary đánh giá ĐỦ mọi `cho` (không dừng sớm), `lay_chang` trả số đo chặng,
  **`chua_kiem` = logic GỌI TÊN nhưng chưa có đường kiểm → hiện "CHƯA", trung
  thực không bịa**, `noi:"nen"` gọi cổng nền; `so_goi.kiem_vet` (theo_viec +
  xoay khóa 403, **0 sự kiện 403 → không phán ĐÚNG**). APP: cửa kiểm
  `/api/kiem/{ma}` CHỈ-ĐỌC 0 quota, chỉ loopback — radary 9 mã (dang-nong chạy
  THẬT trên pool, tier-mau qua core.evaluate, ticks-lui, probe…), ai-agent 5 mã
  (rbac ma trận 5×4, van-kho-rong **đếm lời gọi model = 0**, mac-dinh-noi-bo…).
  Kiểm kê logic 12 app bằng 4 agent đọc code thật (mỗi logic kèm `file:line`,
  chỗ không kiểm được ghi thẳng "CHƯA CÓ VẾT — cần thêm X"); **sơ đồ 11/12 app**
  (rendery mã ở `F:/RenderY/autoedit` ngoài repo). Nghiệm thu sống: 30 logic 2
  app qua gateway thật — **21 ĐÚNG / 9 CHƯA**, số đo chặng thật (radary 7.455
  video pool → 4.416 video 2–60 ngày → ngưỡng nổ 5.669 view/ngày → 40 cụm nóng,
  nền nổ 10%). Chụp màn đặt cạnh mockup, sửa 4 lệch. Bug tự tìm: 2 test cache
  radary rò `db.connect()` → Windows khóa file, fixture sau không dọn được DB.
  KẾ TIẾP: lan cửa kiểm sang 10 app còn lại; đóng dần 9 logic `chua_kiem`.
- 05/09/2026 — **LỚP PHÒNG THỦ API BÊN THỨ 3** (sổ mới `docs/phong-thu-api-ngoai.md`
  — spec 6 lớp + checklist): module `nen/common/phong_thu.py` 4 van tại điểm-ra
  LLM (`src/llm` ai-agent + data-analytics, 2 bản đồng bộ): ① allowlist host
  BASE_URL (https bắt buộc, loopback miễn, thêm host qua LLM_HOST_CHO_PHEP) chặn
  từ lúc dựng client; ② secret trong env lọt nguyên văn vào prompt → chặn call;
  ③ trần LLM/ngày LLM_TRAN_USD_NGAY + LLM_TRAN_CALL_NGAY đọc sổ gọi (mặc định
  TẮT — hành vi hệ không đổi tới khi Owner bật .env); ④ che_pii helper (email/SĐT
  + tên→mã NS) chờ mạch nhân sự-vào-LLM. Vi phạm → LoiPhongThu nổi; lỗi nội bộ
  van / thiếu nen (bản lite) → van tự tắt không giết call. VÁ KÈM: đường STREAM
  + adapter anthropic trước nay KHÔNG ghi sổ gọi (Command Center + trần mù đường
  tiêu chính) — giờ mọi call thật 1 dòng sổ, token stream giữ None chưa đo.
  Kèm `tools/scripts/soi-egress.ps1` (audit chỉ-đọc kết nối ra ngoài, Owner chạy
  tay). CÒN TREO: rotate 2 key YouTube lộ GitHub (nợ 18/08); nối van vào 3 app
  tự đủ (content/seo/niche); firewall default-deny = phương án nâng cao có proxy.
- 05/09/2026 — **PHÒNG THỦ API ĐỢT 2 — NỐI VAN 3 APP LỒNG + RESTART CẢ CỤM** (sổ
  `docs/phong-thu-api-ngoai.md` đã cập nhật bảng phủ 5 app; repo cha 85e37f8 +
  content 790f4a3 + seo 9a2c1f2 + niche 785235f). Gateway thêm
  `GET /api/phong-thu/tran-llm` (loopback, khuôn api-khoa) — trần chi/ngày giữ
  luật MỘT chỗ ở nền, app tự đủ hỏi trước mỗi call, fail-open khi gateway chết.
  3 app lồng mỗi app một bản sao `phong_thu_v3.py` (lệ khoa_v3, 3 bản
  byte-identical): content nối oe/llm (init + đổi nhà + complete) +
  voiceprofile/llm (2 transport); seo nối `_post` (secret+trần) + `_openai_compat`
  (host — KHÔNG kiểm ở _post vì test stub URL giả http://x); niche nối call() +
  _openai_compatible_call. Cổng gộp (mwapi/*_BASE_URL) Owner khai → tự tin cậy,
  chỉ ép https. HAI BẪY TEST mới trả: (a) van gọi urlopen tra động là GỌI KÉ stub
  urllib toàn cục của test app — kiem_tran phải BIND SỚM `_urlopen` lúc import;
  (b) van host đặt ở hàm nhận-URL-từ-test (như _post seo) là chặn oan bộ test —
  đặt ở nơi URL THẬT được dựng. Suite: nền cụm 51 · content 800 · seo 749 ·
  niche 22, đều xanh. RESTART SỐNG lúc ~01:20: dừng THEO CỔNG 6 dịch vụ
  (9000/9101/9102/9112/9113/9115) → start-all.ps1 → 6/6 cổng nghe, health 5 app
  200 ok, tran-llm trả chan=false, /login 200. Trần vẫn mặc định TẮT — Owner bật
  bằng LLM_TRAN_USD_NGAY/_CALL_NGAY trong .env, ăn ngay không cần restart app
  (app hỏi gateway mỗi call; gateway đọc env lúc gọi). CÒN TREO: rotate 2 key
  YouTube lộ GitHub (nợ 18/08); seo/imagegen.py chưa qua van (ponytail trong sổ).
