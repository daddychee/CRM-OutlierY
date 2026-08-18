# APPS.md — sổ chủ đề ĐƯA APP VÀO V3 (Đ4)

> Owner lệnh 16/08/2026: đưa 6 app vào V3, TỪNG APP MỘT, chạy được thật,
> phân quyền theo Permissions v2 (hành động khai trong luật → tự hiện ô tick),
> dữ liệu đúng cấu trúc `data\<slug>\` + khai `du_lieu` (SO_DIA_BA_DU_LIEU.md).
> Thứ tự: RadarY → Content Ultimate → SEO Optimize → (Data Analytics đã ở V3)
> → PlannerY → SpeakY. NAS = nút đáy sidebar.

## Quyết định Owner đã chốt (16/08)

1. **Dữ liệu: SNAPSHOT từ hệ thật** — copy chỉ-đọc từ C:\OutlierY (hệ cũ chạy
   nguyên phục vụ team, song song tới cutover); ngày cutover đồng bộ lần cuối.
   SQLite đang chạy → backup API/mode=ro, KHÔNG copy trần (luật sổ địa bạ).
2. **NAS: CHỈ trang chỉ đường** (ổ + map ổ như V2). KHÔNG đồng bộ tài khoản
   Windows từ V3 khi C:\ còn là nguồn sự thật — bật khi cutover.

## Khung 6 bước MỖI app

1. Chép code từ C:\ (loại .git/__pycache__/data/logs) → `apps\<slug>`, venv riêng.
2. Hợp đồng apps.json: cổng 91xx (PORTS.md trước), tien_to, vao, hanh_dong thật
   + quan_tri + vai_xoa → tự hiện trang Permissions.
3. Snapshot dữ liệu → `data\<slug>\` + khai du_lieu (mức quý theo sổ địa bạ).
4. SSO adapter: đọc claims V3 (X-Remote-Actions + vai chuẩn `admin`), vá bẫy
   đã biết từng app, DEFAULT vai thấp nhất, rà mọi chỗ đọc cookie.
5. **Khóa + quản trị app PHẢI về MỘT CỬA V3 NGAY trong đợt app đó** (luật Owner
   16/08 — "làm gọn từng app trước khi sang app khác"): nguồn khóa = két trang
   API Keys (app lấy qua loopback `/api/cau-hinh/api-khoa/<slug>` mỗi run, không
   fallback sổ nội bộ); mọi cửa quản trị key/thành viên/cấu hình TRONG app đóng
   404 khi SSO — kể cả vai cao nhất nội bộ.
6. **App ngoài (SPA tự render trọn trang) mở qua `/open/<slug>` — sidebar KHÔNG
   BAO GIỜ mất** (Owner 16/08): hợp đồng khai `giao_dien: "khung"`; sidebar +
   khối menu app tự trỏ `/open/<slug>` thay `/app/<slug>`; route render shell
   OUTLIERY (sidebar/topbar chuẩn) + `<iframe src="/app/<slug>/">` cùng origin
   (cookie/back trình duyệt tự ăn); gate y hệt cửa vào app; `/app/<slug>` thẳng
   vẫn sống (bookmark cũ, không redirect — tránh vòng lặp iframe); proxy cắt
   `X-Frame-Options` + CSP `frame-ancestors` CHỈ ở response app khung. App
   native (tự vẽ sidebar OUTLIERY trong template) KHÔNG khai — giữ `/app/<slug>`.
6. Nghiệm thu sống qua 9443 từng vai (Chrome headless cho bẫy proxy) → commit.

## Bảng phân công

| # | App | Cổng | Data | Quyền (khai Permissions) | Trạng thái |
|---|---|---|---|---|---|
| 1 | RadarY | 9111 | data\radary\ (db 88M + niche 41M + reports; thumbs 636M TÁI-SINH không snapshot) | mọi BP L1 xem · them_video/tao_pool KD L3 · toan_quyen Manager chủ quản (vai manager) · quan_tri Owner | **XONG** (chờ Owner chạy migration khóa) |
| 2 | Content Ultimate | 9112 | data\content-ultimate\ | VH L2 · sua L3 leader · quan_tri Owner | **XONG** (chờ Owner chạy migration khóa) |
| 3 | Niche Research | 9113 | data\niche-research\ (projects VÀNG + data/invites di sản) | KD L2 xem · tao KD L3 leader · toan_quyen KD L4 manager · quan_tri Owner | **ĐANG LÀM** (18/08 — Owner chen lên trước SEO; chờ nghiệm thu + cấp khóa) |
| 4 | SEO Optimize | 9115 | data\seo-optimize\ (~15M: profiles/episodes/formats/niches/runs + users.json di sản + audit) | KD L2 van_hanh (vai seo) · sua L3 · toan_quyen L4 manager · quan_tri Owner | **XONG** (19/08 — chờ Owner chạy migration khóa + soi UI qua 9443) |
| — | Data Analytics | 9102 | data\data-analytics\ | đã trong V3 từ đầu | XONG (còn Đ2.2 nối danh bạ) |
| 5 | PlannerY | 9116 | data\plannery\ (plan.json BẢN SAO 19/08 — V2 :8123 vẫn là nguồn thật tới cutover) | mọi BP L1 xem · khai_kenh_video KD L2 (vai seo — đổi tên từ them_kenh_video vì bẫy substring vai_cho_app) · sua L3 leader · toan_quyen L4 manager · quan_tri Owner + ĐÃ VÁ bẫy users.json thắng header | **XONG** (19/08 — chờ restart gateway lấy URL đẹp /plannery) |
| 6 | SpeakY | 91xx | data\speaky\ | VH L2, quyền ở cửa vào; model dùng chung HF cache máy | chờ |
| — | NAS | — | — | nút đáy sidebar, trang chỉ đường | chờ |

## Bẫy phải nhớ khi đưa app (từ V2 + memory)

- Proxy 5 bẫy: importmap/vendor · tên có dấu · ETag cache · guard Origin-vs-Host
  chặn POST (dạy app nhận X-Forwarded-Host) · kiểm bằng Chrome headless.
- SpeakY/Gradio: root_path, X-Forwarded-Host/Proto, Location đúp tiền tố.
- 13 luật quyền (DE.md mục 14): tick chảy mỗi request, cấm map theo tên,
  DEFAULT thấp nhất, test user "trắng", endpoint nhạy cảm sau cổng…
- Sửa nen/common là restart MỌI app import nó.
- App chết không được giết cổng 9000 (van an toàn kiểu Qdrant hệ cũ).

## Nhật ký

- 19/08/2026 — **PLANNERY XONG (app 5/6)** — cổng 9116 (`python server.py
  --no-browser`, stdlib ThreadingHTTPServer; Wd = apps/plannery), giao diện khung,
  `tien_to ["/api"]` (SPA fetch đường tuyệt đối — proxy viết lại byte như V2).
  (1) **PLANNER_DATA_DIR** mới: dữ liệu tách về data/plannery (bản sao plan.json
  hệ thật 19/08, _rev 908, 9 người/6 dự án — V2 :8123 vẫn là NGUỒN THẬT tới
  cutover, kế hoạch 2 hệ sẽ lệch dần, cutover chép lại file là xong).
  (2) **SSO adapter Actions-first** (`server._vai_tu_actions`): quan_tri→admin ·
  toan_quyen→manager · sua→leader · **khai_kenh_video→seo** (ĐỔI TÊN từ
  them_kenh_video V2 — "them" dính bẫy substring vai_cho_app tự thăng leader);
  fallback X-Remote-Role (nhận cả 'owner' V2 → admin). Thang quyền: mọi BP L1
  xem · KD L2 vai seo · L3 leader · **L4 manager MỚI** (V2 chỉ có leader vì
  thiếu nấc — luật 04-05/08 "Manager toàn quyền VẬN HÀNH": vai manager của app
  sửa full data, tài khoản nội bộ vẫn admin/Owner) · L5 admin; vai_xoa=manager.
  (3) **VÁ BẪY users.json thắng header** (DE.md:462): SSO bật → identity() đi
  ĐƯỜNG HEADER TRƯỚC users.json/ADMIN_USERS; sổ riêng chỉ còn nghĩa standalone.
  Vá luôn lỗ V2: X-Remote-* giờ CHỈ nhận từ loopback (trước đây nhánh
  ADMIN_USERS đứng TRƯỚC kiểm loopback — bind 0.0.0.0 là thành admin tự phong);
  tự động hóa loopback (khuôn plannery_sync V2 gửi mỗi X-Remote-User=admin)
  phải gửi kèm `X-Remote-Role: admin`. (4) **Đóng cửa nội bộ khi SSO** (khuôn
  _chot_quan_tri niche): /api/users · /api/register · /api/role · /invite ·
  /logout → 404 vô điều kiện, kể cả admin. (5) Test: tests/test_sso.py 5 test
  (Actions-first, vá-bẫy sổ riêng, standalone giữ nguyên, header ngoài loopback
  bị bỏ, đóng cửa qua HTTP thật); 3 fail test_engine.py là BASELINE V2 có sẵn
  (đối chứng chạy trên C:\ nguyên bản — engine đi trước test từ hồi V2, không
  thuộc mạch này). Nghiệm thu sống :9116 5 vai + đối chiếu iam.cac_hanh_dong 6
  tài khoản thật khớp từng cờ. CHỜ: restart gateway để ăn `_ALIAS_KHUNG` có
  'plannery' (URL đẹp /plannery + link sidebar — dòng sửa main.py đi cùng đợt
  NAS/SEO của phiên song song; /app/plannery đã sống nóng không cần restart);
  to-chuc muốn nối KPI thì trỏ PLANNERY_PLAN=data/plannery/plan.json.

- 19/08/2026 — **SEO OPTIMIZE XONG (app 4/6)** — đúng khuôn 6 bước, cổng 9115
  (`python -m seo.server`, stdlib thuần — KHÔNG uvicorn; Wd = apps/seo-optimize,
  SEO_DATA_DIR=data/seo-optimize vì V2 neo mọi store vào common.ROOT cạnh code).
  (1) **SSO adapter Actions-first** (`server.vai_tu_claims`): quan_tri→owner ·
  toan_quyen→manager · sua→leader · **van_hanh→seo** · còn lại viewer fail-closed;
  khóa hành động MỚI `van_hanh` (KD L2) vì "vai seo" của app KHÔNG phải chỉ-đọc
  (sinh metadata tốn token) — không thể để DEFAULT như niche; tên cố ý né substring
  them/tao/sua (bẫy vai_cho_app). Fallback Role nhận 'admin'→owner.
  (2) **LỆNH USER 19/08 "mọi truy xuất tài khoản từ khối nền, không tự tạo trong
  app"**: GỠ `users.sync_sso` khỏi `_sso()` — app không ghi/tạo bản ghi tài khoản
  nào nữa (V2 upsert mỗi request); users.json snapshot = DI SẢN CHỈ-ĐỌC (giữ giới
  hạn thị trường đã gán); `_authed`/`_me` KHÔNG rơi về chế-độ-mở owner của
  access.py khi SSO bật (không danh tính → 401, test ghim). Gán giới hạn thị
  trường cho leader/seo giờ KHÔNG có UI (pane Tài khoản đóng) — cần thì làm
  đường vận hành riêng, Owner quyết.
  (3) **12 cửa quản trị đóng 404 khi SSO** kể cả vai owner (login/forgot/resets×2/
  change-password/users/user-save/user-passwd/user-disable/user-remove/admin-keys
  GET+POST); board tự ẩn pane Tài khoản+API key nhờ whoami gỡ perm 'users' khi
  sso (board gate bằng may('users') — không sửa board.html 452KB).
  (4) **Nguồn khóa = KÉT** (`seo/khoa_v3.py`): viec_api trich_kenh (youtube, pool
  XOAY VÒNG — cơ chế con trỏ yt_get giữ nguyên, chỉ đổi nguồn danh sách) +
  sinh_metadata (llm, map nhà glm/claude/chatgpt → danh pháp seo/llm.py); không
  fallback .env/api.txt. `scripts/di_tru_khoa_seo.py` idempotent (marker
  api.di_tru.seo_khoa, đọc .env hệ cũ CHỈ ĐỌC, audit chỉ đuôi 4) — **Owner chạy**.
  (5) **2 bẫy khởi động vá**: run() gọi load_keys() lúc boot chỉ để ĐẾM key —
  khóa chưa cấp phát từng giết cả app (giờ app sống, lỗi rõ hiện lúc bấm extract);
  webbrowser.open() tắt khi SSO (chạy nền qua start-all là bật trình duyệt oan
  trên máy chủ). (6) `/api/health` MỚI không cần đăng nhập (V2 chỉ có /api/version
  sau cổng); selftest nội bộ app vẫn xanh (51 endpoint khai quyền). Test: root
  +5 (tests/test_seo_optimize.py — hợp đồng/ma trận vai/tick lẻ/viec_api/di trú)
  = 191 pass · app 13 (tests/test_sso_v3.py). Nghiệm thu sống 9115: health 200 ·
  5 vai đúng theo Actions · cửa quản trị 404 với owner · viewer bị 403 generate ·
  users.json mtime BẤT BIẾN sau mọi request · gateway proxy nhận hợp đồng KHÔNG
  cần restart (hop_dong cache mtime). CÒN CHỜ OWNER: chạy di_tru_khoa_seo.py
  (hoặc cấp khóa tay ở General › API Keys); restart gateway để ăn alias URL đẹp
  /seo-optimize (_ALIAS_KHUNG — trước đó /open/seo-optimize + /app/... vẫn chạy);
  soi UI board qua 9443 từng vai.
- 19/08/2026 — **RadarY V3 BẬT SCHEDULER chạy SONG SONG V2** (user chốt: "API
  hoàn toàn đủ" — đảo chốt tắt-cố-định 16/08). Điều kiện đi kèm: pool đã chia
  thị trường + số liệu đã đồng bộ từ backup V2; **ntfy TẮT TOÀN V3** (user
  lệnh — tránh push trùng V2, pool gốc 1+2 vốn kế thừa enabled từ V2 đã tắt
  có vết); start-all RADARY_SCHEDULER=1. Chi tiết: RADARY_THI_TRUONG.md.
- 18/08/2026 — RadarY thêm trục POOL THEO THỊ TRƯỜNG (sổ riêng:
  [RADARY_THI_TRUONG.md](RADARY_THI_TRUONG.md) — pool gắn 1 thị trường từ đế,
  tách pool giữ lịch sử, chờ Owner nghiệm thu qua 9443).
- 16/08/2026 — Mở sổ; Owner chốt 2 quyết định; bắt đầu RadarY (cổng 9111).
- 16/08/2026 — **RadarY tích hợp xong bước 1-4+6** (chạy thật 9111, hợp đồng +
  luật Permissions v2, SSO adapter Actions→vai nội bộ, smoke từng vai đạt trên
  snapshot thật — org Outliery, 19 khóa). Chạy: `tools\scripts\start-all.ps1`
  (env `RADARY_DATA_DIR=data\radary` + `RADARY_SCHEDULER=0` + `RADARY_TRUST_PROXY=1`).
  **SCHEDULER V3 TẮT CỐ ĐỊNH**
  (`RADARY_SCHEDULER=0` trong start-all): hệ thật C:\ vẫn tự quét theo lịch bằng
  CÙNG bộ khóa — V3 quét song song là ĐỐT ĐÔI QUOTA + db snapshot lệch khỏi hệ
  thật; nghiệm thu quét bằng POST /run tay; bật lại scheduler CHỈ khi cutover.
  RADARY_SSO_MAP đã GỠ HẲN khỏi V3 (map-tên-chết); cửa login/register/reset cục
  bộ đóng 404 khi TRUST_PROXY=1.
- 16/08/2026 — **RadarY LÀM GỌN xong** (luật Owner "gọn từng app rồi mới sang
  app khác" — việc treo Đ4b HỦY, làm ngay): (1) 14 endpoint quản trị org (keys ×5
  · members ×3 · invites ×3 · LLM ×3) đóng 404 khi SSO KỂ CẢ vai owner nội bộ —
  khóa nhập ở General › API Keys, quyền ở General › Permissions; tab Quản trị
  app.js ẨN HẲN khi `me.sso` (cả lọc tab lẫn chặn render). **LƯU Ý CAPABILITY:
  khối "Xóa niche" nằm trong tab đó cũng mất UI khi SSO** (endpoint DELETE
  workspace vẫn sống — vận hành manager); cần thì chuyển nút xóa sang tab
  Settings từng niche đợt sau. (2) Nguồn khóa = KÉT V3: radary khai `viec_api`
  harvest/quet_dinh_ky (youtube) + dien_giai (llm); gateway loopback MỚI
  `GET /api/cau-hinh/api-khoa/{slug}`; `radary/khoa_v3.py` lấy khóa MỖI run —
  gateway chết/việc chưa cấp → run DỪNG thông điệp rõ "chưa lấy được khóa từ
  OUTLIERY", KHÔNG rơi về bảng nội bộ (bảng `api_keys` NGHỈ — giữ làm sử liệu).
  (3) Migration một lần `scripts/di_tru_khoa_radary.py` (idempotent, marker két,
  GIỮ NGĂN V2: harvest=1→việc harvest, còn lại→quet_dinh_ky, đều xoay vòng; vết
  audit CHỈ ĐUÔI) — **Owner quyết thời điểm chạy thật**; chạy xong mới nghiệm
  thu quét. Suite radary 8 test.
- 16/08/2026 — **Owner DUYỆT RadarY làm gọn** + yêu cầu mới "mở app vẫn còn
  sidebar" (SPA app ngoài trước đó chiếm trọn trang khi vào `/app/<slug>`).
  **KHUNG MỞ APP GIỮ SIDEBAR làm xong** (bước 6 ở trên): route
  `GET /open/{slug}` + `nen_khung_app.html` (iframe cùng origin); radary +
  content-ultimate khai `giao_dien: "khung"` trong apps.json; sidebar 4
  template (to-chuc/DA/ai-agent base.html + hoi_dap.html) đổi `href="/app/{{
  a.slug }}"` → `href="{{ a.href }}"` (nguồn `sb_apps_tu_claims` tính sẵn).
  Test mới `tests/test_khung_app.py` (6 ca: gate/404/native/sidebar-href/strip-
  header) + `test_radary.py` sửa 1 assert. 5 suite: root 136(+6) · radary 8 ·
  ai-agent 308+3skip · DA 64 · to-chuc 58 — tất cả pass. **BẪY GHI LẠI: sửa
  nen/common (sidebar.py, proxy.py) + nen/gateway PHẢI RESTART mọi app import
  (ai-agent/DA/to-chuc/gateway) mới thấy sidebar mới** — Owner tự restart.
  Content Ultimate vẫn ĐỨNG YÊN, chưa đụng tiếp đợt này.
- 17/08/2026 — **CONTENT ULTIMATE XONG (app 2/6)** — làm gọn đúng khuôn RadarY:
  (1) **Quản trị nội bộ ĐÓNG khi SSO** (7 route: GET/POST `/api/settings`,
  GET/POST `/api/invites`, POST `/api/users`, trang `/settings`, `/invite`) —
  404 kèm "quản trị chuyển về OUTLIERY — General › API Keys / Permissions", KỂ
  CẢ vai admin nội bộ; UI: thẻ ⚙ Cài đặt ẩn khỏi trang chủ, dòng nhắc "Thành
  viên & quyền → Cài đặt" ở tab Quản lý đổi thành chỉ đường OUTLIERY. **Tab
  Quản lý GIỮ NGUYÊN** (nhật ký chạy · token · bảo mật · lịch sử kịch bản =
  VẬN HÀNH, không phải quản trị) — leader vào 200, creator 403.
  (2) **Nguồn khóa = KÉT V3**: `viec_api` khai 4 việc theo tính năng thật —
  viet_kich_ban (llm) · phan_tich_outline (llm) · lay_transcript (**loại mới
  `transcript`** thêm vào két cho transcriptapi.com) · lay_comment (youtube);
  `contentultimate/khoa_v3.py` (khuôn radary) lấy khóa MỖI lần chạy, ánh xạ về
  đúng biến env app đang đọc; **4 điểm đọc khóa** rẽ qua két khi `CU_TRUST_PROXY=1`:
  `oe/llm.py` (GLM), `voiceprofile/llm.py::_load_env` (mọi provider),
  `oe/transcript.py::load_key`, `oe/s5_server.py` (bơm khóa YouTube vào
  videos.txt của run) — **không nhánh fallback .env nào**.
  (3) `scripts/di_tru_khoa_content.py` idempotent (marker, audit CHỈ ĐUÔI) —
  **Owner chạy**, nguồn .env hệ cũ (snapshot không có .env).
  (4) **Không có scheduler/job nền** (khác RadarY): pipeline chỉ chạy khi user
  bấm; `--no-browser` trong start-all chặn Timer mở trình duyệt.
  (5) **BẪY UTF-8 (đã vá)**: app in tiếng Việt ra stdout → cp1252 giết tiến
  trình lúc khởi động → start-all thêm `$env:PYTHONIOENCODING = 'utf-8'`.
  (6) **2 fail `test_generator` = BASELINE V2**, KHÔNG do V3: `generator.py` và
  `test_generator.py` md5 GIỐNG HỆT bản C:\ (byte-identical), fail lặp lại khi
  đổi `CU_DATA_DIR`, và chính docstring code ghi đã ĐỔI THUẬT TOÁN chọn k
  (2026-07-14 "cộng mention lên trên ⇒ vượt có hệ thống") sau khi test được
  viết → test cũ chưa cập nhật. Không sửa (không đụng logic nghiệp vụ V2).
  Suite content **245 pass / 4 fail** (2 env Windows: path-separator + chmod
  read-only; 2 baseline nêu trên) — **không tăng fail so với lúc nhận**.
- 16/08/2026 — BẪY MỚI khi agent ghi start-all.ps1: chuỗi `data\radary` bị nuốt
  `\r` thành byte xuống dòng thật (0x0D) → comment gãy đôi thành lệnh, script
  chết trước khi bật service nào. Sửa bằng thay byte, đường dẫn trong .ps1 từ
  nay dùng GẠCH CHÉO XUÔI `data/radary` (Join-Path/Python đều hiểu) — cùng họ
  bẫy PowerShell 5.1 (memory powershell-51-utf8-bom-va-log).
- 16/08/2026 — RadarY NGHIỆM THU ĐỘC LẬP đạt (curl 9111 + qua cổng): health
  200 · không claims 401 · viewer đọc orgs · manager(toan_quyen) /keys 403
  (Manager không ngang Owner) · owner(quan_tri) 200 · login cục bộ body hợp lệ
  404 (422 khi thiếu body = validation chạy trước guard, route vẫn bất khả
  dụng) · /app/* không auth 401 trần là chuẩn chung nền. 5 suite xanh
  124+3+308/3+64+58. CÒN CHỜ OWNER: soi UI RadarY qua 9443 (SPA/Console),
  tick thử ở Permissions, POST /run tay 1 pool giờ thấp điểm (đốt quota thật).
- 18/08/2026 — Owner hỏi "tại sao Niche Research chưa được config (API Keys)":
  vì app CHƯA ĐƯỢC ĐƯA VÀO V3 — không nằm trong danh sách 6 app Owner chốt 16/08
  (RadarY/Content/SEO/DA/PlannerY/SpeakY). Per-app config chỉ hiện app có hợp
  đồng + viec_api. GHI HÀNG ĐỢI: **Niche Research = ứng viên app #7** (KD L2 xem
  · L3+ tạo · manager xóa · quan_tri Owner — thang V2 sẵn), vào mạch sau
  SEO/PlannerY/SpeakY hoặc sớm hơn nếu Owner xếp — chờ Owner chốt thứ tự.
- 18/08/2026 — **Owner CHỐT: Niche Research CHEN LÊN làm app #3** (trước SEO —
  SEO→#4, PlannerY→#5, SpeakY→#6). **TÍCH HỢP XONG đúng khuôn 6 bước**: chạy
  9113 (`server:app` uvicorn, `NICHE_DATA_DIR=data/niche-research` — projects +
  data trỏ hết qua env, V2 không đặt env thì cạnh code như cũ); hợp đồng
  apps.json (tien_to `/api` `/web` từ registry V2, `giao_dien: "khung"`, health
  MỚI `/api/health` — app V2 không có); luật phan_quyen.json KD L2 vào · tao L3
  · toan_quyen L4 (`vai_xoa: "manager"`) · quan_tri Owner; SSO adapter
  Actions-first (quan_tri→admin · toan_quyen→manager · tao→leader · còn lại
  **seo** DEFAULT fail-closed; fallback Role danh pháp mới; SSO bật không bao
  giờ rơi về ADMIN_USERS). **LÀM GỌN cùng đợt**: 10 cửa quản trị (settings ×2 ·
  users ×4 · invite ×2 · register ×2) đóng 404 khi SSO kể cả admin nội bộ, UI ẩn
  nút ⚙; nguồn khóa = KÉT (`khoa_v3.py`, viec_api 3 việc theo tính năng thật:
  quet_kenh youtube · phan_tich llm · lay_transcript transcript) — **YouTube key
  của app này nằm trong CHÍNH competitors.txt user dán (thiết kế V2, regex
  AIza…) → V3 bơm khóa két vào file mỗi run** (dedup, thiếu khóa → 503 rõ,
  KHÔNG fallback .env); LLM/transcript bơm qua env tiến trình con đúng danh
  pháp `scripts/llm_provider.py` (claude→anthropic · glm · chatgpt→openai ·
  gemini/deepseek→custom). **WATCH SCHEDULER TẮT ở V3** (`NICHE_SCHEDULER=0`
  trong start-all — hệ thật C:\ vẫn tự watch cùng dự án, chạy song song là đốt
  đôi quota; nghiệm thu bằng POST /api/watch/{name}/run tay).
  `scripts/di_tru_khoa_niche.py` idempotent NHƯNG **.env hệ cũ (đọc 18/08) chỉ
  có ADMIN_USERS — KHÔNG có khóa nào để di trú** (GROK_API_KEY không có giá trị
  → KHÔNG thêm nhà grok vào két); snapshot projects cũng 0 key AIza → **khóa
  cho niche-research cấp TAY ở General › API Keys**. Suite mới: root
  tests/test_niche_research.py (5) + apps/niche-research/tests (11).
