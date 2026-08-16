# ROADMAP — Radary web/app (chốt với user 07/07/2026)

> Quy trình: mọi tính năng phải nằm ở đây (hoặc `radar_spec.md`) TRƯỚC khi code.
> Kiến trúc nền: SaaS multi-tenant · local trước + Docker sẵn sàng cloud · FastAPI + SQLite (SQLAlchemy, đường lên PostgreSQL) + React.

## 1. Phạm vi ĐÃ ẤN ĐỊNH (quyết định sản phẩm của user — không mở lại nếu không có lệnh)

- **Chỉ YouTube.** Không TikTok/Reels/nền tảng khác — không xây provider abstraction cho việc này.
- **Chỉ long-form (>180s).** Không hỗ trợ Shorts — giữ bộ lọc như spec, không làm toggle.
- **Chỉ trong pool kênh user nhập.** Không module search-discovery tự mở rộng tầm quét — vai của Radary là canh pool, phần tìm kênh là việc của user.
- **Push: ntfy duy nhất.** Không mở rộng Telegram/Discord/email/webhook.
- **Không mobile app.** Giao diện web (responsive, xem được trên điện thoại) + push ntfy là đủ.

## 2. Đã duyệt — nằm trong các Phase build

### Phase 1 — Core engine + DB ✅ HOÀN THÀNH 07/07/2026 (nghiệm thu 13/13 parity check)
- ✅ Schema multi-tenant: `org → members (user+role) → workspace (niche) → channel pool → video/tick → event` — package `radary/` (db, core, scan, report, runner, migrate_legacy), chỉ stdlib, DB tại `data/radary.db`.
- ✅ **Event log append-only** là bảng trung tâm (bảng `events`: tier, retitle, rethumb, dead, config_change) — nền cho tự chấm, audit, billing sau này.
- ⚠️ **BYO API key:** key theo org trong bảng `api_keys`, DB chmod 600. *Điều chỉnh có ghi vết:* mã hóa Fernet cần thư viện `cryptography` (ngoài stdlib) → HOÃN sang Phase 4 (thời điểm app lộ internet — trước đó mức bảo vệ ngang `competitors.txt` hiện tại). Quota budget theo workspace: env `RADAR_BUDGET` (per-workspace config ở Phase 2).
- ✅ **Kho packaging:** lưu thumbnail (theo hash, chỉ khi ảnh đổi) + lịch sử title. Đã vá cả vào `daily_radar.py` production (trường `title_hist`/`thumb_hist`/`thumb_ck`, ảnh `radar_state/daily/thumbs/`) lẫn engine mới (bảng `title_hist`/`thumb_hist`, ảnh `data/thumbs/{ws}/`). Đã bắt được 1 vụ đổi title thật ngay đêm đầu (Cape Verde "Dark→Hard History").
- ✅ Migrate Life in X → workspace #1 (77 kênh, 6.370 video, 13.790 tick, 2 key). Nghiệm thu `verify_phase1.py`: state, evaluate (vph/vpd/rank/bậc/events), board markdown — khớp 100% engine cũ.
- Vận hành chuyển tiếp: production vẫn là `daily_radar.py` + cron; engine mới (`python3 -m radary.runner run`) chỉ chạy tay để kiểm thử, KHÔNG đặt cron song song (tránh tốn quota đôi) cho đến khi Phase 2 nghiệm thu xong và swap.

### Phase 2 — Backend FastAPI ✅ HOÀN THÀNH 07/07/2026 (nghiệm thu 17/17, `verify_phase2.py`)
- ✅ API (`radary/api.py`, chạy `server.py`, docs tự sinh `/docs`): workspaces (list/create/status) · board JSON + board.md · alerts (lọc kind, phân trang) · channels (thêm resolve @handle/URL, xóa mềm) · config (PUT có audit trail event `config_change`) · POST /run chạy chu kỳ tay.
- ✅ Scheduler trong app (`radary/scheduler.py`) thay cron: mỗi phút kiểm job đến hạn, budget 120s/chu kỳ, job lớn tự PAUSE chạy nốt phút sau. Tắt bằng `RADARY_SCHEDULER=0`.
- ✅ Board JSON lưu vào kv sau mỗi chu kỳ = hợp đồng dữ liệu cho React (Phase 3); board.md qua API khớp từng byte file engine ghi.
- Dependency đầu tiên: fastapi + uvicorn trong `.venv` (engine lõi `radary/` vẫn thuần stdlib). Server chỉ bind 127.0.0.1 cho đến Phase 4.
- **Việc còn lại trước khi swap production:** user nghiệm thu chạy song song vài ngày → tắt cron `daily_radar.py` → server thành nguồn quét duy nhất.

### Phase 3 — Dashboard ✅ HOÀN THÀNH 07/07/2026 (nghiệm thu 16/16, `verify_phase3.py`)
- ✅ 5 màn hình (`web/`, FastAPI serve thẳng): **Board** (heartbeat + chips + cohort D0-D6 + VPD mọi tuổi + nút Quét ngay, tự refresh 60s) · **Alerts** (timeline lọc theo loại: tier/retitle/rethumb/dead/config/pool) · **Pool** (thêm kênh dán URL/@handle, gỡ mềm) · **Cài đặt** (ngưỡng T1-T4 + ntfy + vùng nguy hiểm xóa workspace có xác nhận tên) · **+ Niche mới** (dán pool → tạo → resolve → quét lần đầu, không đụng file).
- ✅ **Vòng tự chấm bước 1:** nút *Đã đánh/Bỏ qua* trên alert T2+ → bảng `verdicts`. *Còn lại (roadmap):* job tự chấm kết cục sau 7-30 ngày + precision per niche trên dashboard.
- ⚠️ **Onboarding = hiệu chỉnh sống thay vì backtest lịch sử** (điều chỉnh có ghi vết): quét sâu toàn lịch sử pool lúc onboard rất tốn quota và views-cuối ≠ quỹ đạo (thiên lệch backtest đã biết trong `weekly_report.md` §3). Thay bằng: endpoint `/calibration` — phân phối VPH THỰC quan sát được (P50-P99) + đề xuất sàn (P80/P95/P99/3×P99), UI gắn cờ "chưa đủ 14 ngày chỉ để tham khảo" đúng spec. Backtest lịch sử đầy đủ khi onboard → chuyển xuống mục Tương lai xa.
- Kỹ thuật: frontend = mô hình component React qua **Preact + htm vendored** (16KB, không cần Node/npm/build); đổi sang React build đầy đủ khi SaaS cần — component gần như giữ nguyên.

### Phase 4 — Multi-user + Docker ✅ HOÀN THÀNH 07/07/2026 (nghiệm thu 19/19, `verify_phase4.py`)
- ✅ **Auth** (`radary/auth.py`): mật khẩu scrypt (stdlib), session cookie 30 ngày (httponly, samesite=lax; `RADARY_SECURE_COOKIE=1` khi có HTTPS). Đăng ký tạo user + org riêng; email migrate chưa có mật khẩu → đăng ký lần đầu = đặt mật khẩu (bootstrap); email đã có mật khẩu → 409.
- ✅ **Phân tách org**: mọi route workspace/org đều kiểm membership; truy cập workspace của org khác → 404 (không lộ tồn tại). UI có màn đăng nhập/đăng ký + nút Thoát + panel API keys trong Cài đặt.
- ✅ **Mã hóa key Fernet** (`radary/crypto.py`, trả nợ Phase 1): key trong DB là bản mã hóa; server tự nâng cấp key plaintext cũ lúc khởi động. Khóa chủ: env `RADARY_SECRET` hoặc file `data/secret.key` (tự sinh, chmod 600). **BACKUP data/ PHẢI GỒM secret.key — mất khóa = mất key đã mã hóa.** Hệ quả: từ Phase 4 mọi lệnh (kể cả `radary.runner`) chạy qua `.venv`.
- ✅ **Docker**: `Dockerfile` + `docker-compose.yml` (volume `./data`, restart unless-stopped) + `.dockerignore`. ⊘ Build thật chưa test — máy dev chưa cài Docker; chạy `docker compose up -d` khi cài Docker Desktop hoặc trên VPS.
- Nghiệm thu 19/19: cổng khóa 401 · 2 tài khoản không thấy nhau (list + truy cập thẳng + sửa config) · bootstrap/chống chiếm email · key mã hóa trong DB, GET chỉ trả masked, giải mã lại được · guards Phase 1-3 vẫn xanh sau khi thêm auth.

### Phase 3.5 — Chart sóng cho video T2+ ✅ HOÀN THÀNH 08/07/2026 (nghiệm thu trong `verify_phase3.py` §5)
- **Phạm vi: CHỈ video đã đạt T2 trở lên.** Bấm vào video → mở cửa sổ chart; bấm lần nữa (hoặc nền/×) → đóng.
- **Mức 1 — đạo hàm:** đường VPH theo tuổi video (tính từ ticks, cùng phương pháp cửa sổ ≥2h của engine) + đường views tích lũy + nhãn xu hướng ↗ tăng tốc / → đi ngang / ↘ đang tàn (so VPH hiện tại với ~3-6h trước).
- **Mức 2 — tham chiếu lịch sử:** dải phân vị VPH (P25-P75 + P50, P90) của các sóng T2+ ĐÃ KẾT THÚC cùng niche, theo trục tuổi — "video này đang chạy nhanh hơn X% sóng tiền lệ". <3 sóng lịch sử → hiện ghi chú "chưa đủ tiền lệ", KHÔNG vẽ dải (chống tự lừa). Không dự đoán số tuyệt đối (mức 3 vẫn nằm ở Tương lai xa).
- **Marker packaging:** chấm mốc đổi title/thumbnail của đối thủ (từ `title_hist`/`thumb_hist`, bỏ bản chụp đầu tiên) lên đường VPH — thấy "đổi thumb xong VPH hồi sinh".
- Kỹ thuật: SVG tự vẽ (không thư viện), endpoint `GET /workspaces/{ws}/videos/{yt_id}/series` (từ chối video chưa đạt T2+), tính toán ở `radary/series.py` — core.py không đổi.

### Phase 3.6 — Trạng thái Xóa/Ẩn ✅ HOÀN THÀNH 08/07/2026 (nghiệm thu trong `verify_phase3.py` §5)
- **Nhãn thống nhất "Xóa/Ẩn"** cho mọi video không còn mở được (quyết định user: KHÔNG phân loại xóa vs private — bỏ phương án oEmbed).
- **Chart video T2+ chết:** badge "✕ XÓA/ẨN" ở header + vạch marker đỏ tại thời điểm biến mất trên đường VPH (thời điểm lấy từ event `dead`; video chết trước khi có event → xấp xỉ bằng tick cuối).
- **Tín hiệu cấp kênh `channel_purge`:** ≥`purge_min` (mặc định 3, chỉnh được) video cùng kênh Xóa/Ẩn trong MỘT chu kỳ quét → gộp thành 1 event riêng — tín hiệu dọn kho/đổi chiến lược/strike. Chỉ ghi Alerts, KHÔNG push (luật push là đất thiêng).
- Alerts: filter "Video Xóa/Ẩn" + "Kênh ẩn hàng loạt".

### Phase 3.7 — Nhật ký quét ✅ HOÀN THÀNH 08/07/2026 (nghiệm thu trong `verify_phase2.py` §2 + `verify_phase3.py` §5)
- Mỗi chu kỳ ghi 1 dòng vào bảng `cycles` (append-only, tách khỏi `events` để không nhiễu timeline tín hiệu): giờ, jobs chạy, **kênh quét/pool** (khi discover chạy), số video refresh, video mới, quota, tag DONE/PAUSE.
- **Bất ổn (⚠):** chu kỳ PAUSE hết budget · kênh không đọc được (xóa/đổi?) · phải xoay API key (403/quota).
- **Đặc biệt (★):** video lên T2+ · kênh ẩn hàng loạt · video Xóa/Ẩn · đối thủ đổi title/thumbnail · video mới vào radar.
- Không có gì → **✅ ổn định**. Hiển thị: panel "Nhật ký quét" cuối tab Board (~12 dòng gần nhất), API `GET /workspaces/{ws}/cycles`.

### Phase 3.8 — Hồ sơ kênh trong Pool ✅ HOÀN THÀNH 08/07/2026 (nghiệm thu trong `verify_phase3.py` §5b; pattern scrape kiểm chứng sống với 7 links thật)
- Bấm kênh trong Pool → modal (bấm lần nữa/nền/× đóng — pattern chuẩn): avatar, tên, @handle, subs (số làm tròn công khai của YouTube) · videos · tổng views · quốc gia · ngày lập, description đầy đủ.
- **Links ngoài (TikTok/Spotify/…): BEST-EFFORT scrape trang About công khai** — API chính thức không có mục này. Hợp đồng: lấy được thì hiện; YouTube đổi cấu trúc trang → mục Links tự ẩn êm (`links_ok: false`), KHÔNG làm chết modal; đã biết là vùng xám ToS, tần suất thấp + cache 24h. Business email: KHÔNG THỂ (YouTube chặn captcha) — ngoài phạm vi vĩnh viễn.
- Cache bảng `channel_info` TTL 24h — quota ~1 unit/kênh/ngày khi mở. Dữ liệu subs/videos/views là gạch nền cho tầng TC3 (kênh mạnh gia nhập) sau này.

### Phase 3.9 — Chống trùng khi thêm kênh vào Pool ✅ HOÀN THÀNH 08/07/2026 (test trong `verify_phase3.py` §2)
- Thêm kênh phân loại 3 nhóm: **mới** (insert) · **đã tồn tại** (báo "⚠ kênh đã tồn tại" kèm tên, không đụng gì) · **khôi phục** (từng gỡ mềm → bật lại). Chỉ kích discover + ghi event khi có mới/khôi phục.
- *Điều chỉnh có ghi vết (lệnh user 08/07/2026):* **gỡ kênh = XÓA luôn video + tick + lịch sử packaging của kênh đó** trong workspace (trước đây giữ lại). Bảng `events` vẫn append-only không xóa (dấu vết alerts giữ nguyên); dòng kênh vẫn soft (active=0) để còn đường "khôi phục" — khôi phục sẽ quét lại video từ đầu. Kèm quy tắc UI: **mọi hành động gỡ/xóa (kênh, API key, mã mời) đều phải xác nhận trước khi thực thi**.

### Phase 5 — Tab Báo cáo + Phân quyền (chốt với user 08/07/2026, 4 quyết định qua hỏi-đáp)
- **Tab Báo cáo** (màn hình thứ 6): tổng quan ngách ghim trên đầu, báo cáo tuần xếp dưới (mới nhất trước), click mục nào đọc mục đó ngay trong tab.
  - Nguồn báo cáo tuần: engine ĐÃ sinh mỗi CN 08:00 (`data/reports/{ws}/weekly/*.md`) — tab chỉ là tầng đọc, không đổi engine.
  - **Tổng quan ngách = TÀI LIỆU user đưa vào lúc onboard niche, GHIM TRÊN ĐẦU vĩnh viễn** (*điều chỉnh có ghi vết 08/07/2026*: bản đầu định sinh tổng quan từ data tươi rồi đóng băng khi có tuần đầu — user bác: "đây không phải báo cáo dựa trên data tươi, đây là tổng quan của ngách" kiểu `niche_analytics.md`, phần số liệu tươi đã có sẵn ở Cài đặt → Căn cứ hiệu chỉnh nên không lặp). Dán markdown khi tạo niche (tùy chọn) hoặc thêm/sửa sau trong tab (editor trở lên); lưu kv `overview_doc` theo workspace.
  - Kỹ thuật: kv `overview_doc` · API `GET /workspaces/{ws}/reports` (danh sách) + `GET /workspaces/{ws}/reports/{id}` (nội dung md, id whitelist chặn path traversal) + `PUT /workspaces/{ws}/overview` (editor+) · render md→HTML mini ngay trong `web/app.js` (không thêm thư viện).
- **Phân quyền 3 bậc** (quyết định user): `owner` (API keys, mời/quản thành viên, xóa workspace) > `editor` (thêm/sửa pool, config, chạy quét, verdict) > `viewer` (chỉ xem — board/alerts/báo cáo/chart; KHÔNG verdict). Chặn tại API (viewer gọi endpoint ghi → 403), UI ẩn nút chỉ là phụ.
  - **Vào org bằng MÃ MỜI do owner tạo** (quyết định user): mã gắn sẵn vai + hạn 7 ngày + dùng 1 lần; người mới đăng ký kèm mã → vào thẳng org đúng vai (không tạo org riêng). Không cần email server.
  - **Phạm vi theo niche (lệnh user 08/07/2026):** mã mời chọn thêm PHẠM VI — "toàn org" (mặc định, như cũ) hoặc **1 workspace chỉ định**. Thành viên bị giới hạn chỉ thấy/thao tác đúng niche đó (list + truy cập thẳng niche khác → 404 không lộ tồn tại; không tạo được niche mới). Cột `members.workspace_id`/`invites.workspace_id` NULL = toàn org — dữ liệu cũ giữ nguyên nghĩa. V1: 1 niche/người (cần nhiều-niche-chọn-lọc → mở rộng sau).
  - **Sửa thành viên TẠI CHỖ (lệnh user bổ sung cùng ngày, kèm ảnh UI):** owner đổi vai (viewer↔editor) và đổi phạm vi niche ngay trên từng dòng ở tab Quản trị (`PATCH /orgs/{org}/members/{uid}`). Rào: không tự sửa chính mình, không sửa owner khác qua đường này (chuyển owner = việc riêng, chưa làm).
  - Nền có sẵn từ Phase 1/4: `members.role`, `require_org_member` đã trả role — chỉ thêm bảng `invites` + enforcement.
  - **Tab Quản trị riêng cho owner** (*bổ sung theo lệnh user 08/07/2026*): quản thành viên (danh sách, gỡ) + mã mời (tạo/thu hồi) + API keys của org — gom hết đồ org-level về một tab; Cài đặt chỉ còn cấu hình workspace (ngưỡng, ntfy, vùng nguy hiểm).
  - **Panel "Niche của org" trong Quản trị** (*lệnh user 12/07/2026*): danh sách mọi niche kèm số video + nút xóa từng niche — qua `DELETE /workspaces/{ws}` (owner + gõ đúng tên xác nhận, mức khó nhất giữ nguyên). **Đây là cửa XÓA DUY NHẤT** — "Vùng nguy hiểm" ở tab Cài đặt đã gỡ theo lệnh user cùng ngày.
  - Nghiệm thu bổ sung vào `verify_phase4.py`: viewer 403 trên mọi endpoint ghi · editor không xem được keys · flow mã mời (đúng org/vai, hết hạn/dùng rồi → lỗi rõ) · tổng quan ghim đầu danh sách, viewer không sửa được.

### Phase 6 — Báo cáo ngách tự sinh v1 (lệnh user 08/07/2026, spec: `docs/niche_report_spec.md`)
- **Tổng quan ngách = BÁO CÁO TỰ SINH từ pool đối thủ** (*điều chỉnh có ghi vết lần 2, 08/07/2026*: user bác cả bản dán tay — "bạn tự sinh ra report dựa trên list đối thủ được nhập vào chứ không phải tôi nhập tay". Bản dán tay sáng nay chỉ sống nửa ngày). User bấm **nút refresh** khi thêm đối thủ / pool đủ lớn — không tự chạy định kỳ (đúng spec: công cụ định kỳ theo lệnh, không phải hằng ngày).
- **Tái dùng pipeline đã kiểm chứng** từ tool `Niche Report` (đúng §7 spec: "logic đã kiểm chứng, cần đóng gói thành module"): vendor `1_scan` (quét resumable, cap 300 video gần nhất/kênh) · `2_keywords` (LIFT + kiểm định FDR BH q=0.10) · `5_synthesize_bets` (bảng cược candidate 4 tín hiệu phản biện + falsifier) · `_common` (OUTLIER MODEL v3 age-adjusted, leave-one-out) vào `radary/niche/`. **Thay đổi duy nhất khi vendor: `requests` → `urllib` stdlib** (giữ nguyên tắc không thêm dependency).
- V1 phủ hạng mục **3.1 (cấu trúc) · 3.2 (outlier OX v3) · 3.9 (packaging LIFT/template) · 3.10 (bảng cược candidate)** + mục "Giới hạn dữ liệu" bắt buộc (§6 spec). CHƯA có (ghi rõ trong báo cáo): 3.3-3.6 (theme matrix cần clustering đa ngôn ngữ + LLM đặt tên), 3.7 (comment mining), 3.8 (burst half-life), tự chấm cược kỳ trước, xlsx. LLM-các-phần-ngữ-nghĩa cần quyết định riêng về provider/key — chưa mở.
- Vận hành: quét chạy NỀN trong app (thread, không chặn request), trạng thái ghi kv `niche_report_status`, kết quả markdown ghi đè kv `overview_doc` (vẫn ghim đầu tab Báo cáo). Work dir `data/niche/{ws}/` (chứa competitors.txt có API key — chmod 600, không commit). Quota ~1 unit/50 video: pool 77 kênh ≈ ~900-1.000 units/lần refresh.
- Radar KHÔNG đổi: bảng `videos`/tick/cohort không nhận video từ scan này (2 tool độc lập, đúng phân định trong spec).

### Phase 7 — Lớp LLM diễn giải (chốt với user 08/07/2026 qua hỏi-đáp)
- **Hai tính năng, chung một nền:** (A) **narrative cho báo cáo ngách** — sau khi pipeline tính xong bảng số, LLM viết "Tóm tắt điều hành" chèn đầu báo cáo (bảng số gốc giữ nguyên để truy vết); (B) **Hỏi Radar** — ô hỏi-đáp trên Board, server gom board + alerts + calibration hiện tại → LLM diễn giải theo yêu cầu.
- **Ranh giới cứng** (theo `niche_report_spec.md` §5 + nguyên tắc 5): LLM **không sinh số** (mọi số phải trích từ dữ liệu cung cấp) · **không khuyên "nên đánh/không đánh"** (system prompt cấm — radar báo sóng, người thẩm định) · lỗi/thiếu key → mọi thứ chạy như cũ, không bao giờ chặn pipeline.
- **Đa provider theo lệnh user: Claude VÀ GLM (Zhipu).** Org chọn provider + model + key trong tab Quản trị (BYO key, mã hóa Fernet như YouTube key, chỉ owner quản). Adapter gọi thẳng HTTP bằng urllib thuần — không thêm dependency (nhất quán với quyết định vendor Phase 6).
- **Quyền dùng Hỏi Radar: editor trở lên** (quyết định user — người làm việc thật mới đốt tiền key; viewer vẫn đọc narrative trong báo cáo miễn phí). Rate limit 30 câu/ngày/người.
- Kỹ thuật: bảng `llm_config` (org-level) · `radary/llm.py` (adapter + prompt) · `POST /workspaces/{ws}/ask` · bước narrative trong `niche_report._run`.

### Phase 3.12 — Báo cáo tuần 7 phần + Nhận định AI (lệnh user 12/07/2026: "cần diễn biến tuần qua + tiềm năng tuần mới")
- Cấu trúc mới: **1. Nhịp tuần** (5 chỉ số so tuần trước) · **2. Diễn biến theo ngày** · **3. Sổ cái sóng T2+** (giữ) · **4. Kênh tạo sóng** · **5. Mang sang tuần mới** (T2+ còn sống + xu hướng ↗→↘ từ series.trend) · **6. Ứng viên chớm nở** (T1 <72h, VPH đang tăng) · **7. Hiệu chỉnh sàn** (giữ) + dòng giới hạn dữ liệu.
- **Nhận định AI** chèn đầu báo cáo qua thread NỀN sau khi render (không chặn chu kỳ quét; thiếu key/lỗi → báo cáo thuần số vẫn nguyên): (a) diễn biến tuần qua, (b) tiềm năng tuần mới từ mục 5+6, (c) "nhận định sai khi nào" — ranh giới Phase 7 giữ nguyên.

### Phase 5.2 — Reset mật khẩu (lệnh user 12/07/2026)
- Không có email server → **mã reset do owner phát** (nhất quán mã mời): owner bấm "reset MK" trên dòng thành viên (tab Quản trị) → mã `rs-…` 1-lần/24h → gửi người quên. Người đó vào màn đăng nhập → "Quên mật khẩu?" → email + mã + mật khẩu mới (≥8) → tự đặt lại, owner không thấy mật khẩu; **mọi session cũ của tài khoản bị hủy** và tự đăng nhập lại. Endpoint public `/auth/reset` có rate-limit như login. Owner duy nhất tự quên → nhờ Claude reset qua server (ghi nhận, chưa tự động hóa).

### Phase 5.1 — Key YouTube theo niche + key dự phòng (lệnh user 11/07/2026, sau sự cố quotaExceeded)
- **Gán key theo niche:** cột `api_keys.workspace_id` (NULL = toàn org như cũ). Workspace dùng = key gán riêng cho nó + key toàn org → pool lớn tách quota khỏi pool nhỏ. Tự thao tác trong tab Quản trị (owner): đổi phạm vi/loại key TẠI CHỖ, không cần dán lại key.
- **Key dự phòng:** cột `api_keys.backup`. `db.api_keys` xếp key CHÍNH trước, DỰ PHÒNG cuối — cơ chế xoay key khi 403/quota có sẵn trong `scan.API` sẽ tự đôn dự phòng lên khi key chính cạn, hết sự cố tự quay về chính (mỗi chu kỳ xoay lại từ đầu danh sách).
- Nhắc vận hành (từ sự cố 10-11/07): quota 10K/ngày tính theo DỰ ÁN Google Cloud — key muốn nhân quota phải nằm ở project khác nhau.
- **UX theo flow user chốt 11/07/2026: "Tạo dự án → add key → mới pool".** Mỗi niche có panel key riêng trong Cài đặt (owner): **1 ô KEY CHÍNH** (thay được, có xác nhận) + **danh sách KEY DỰ PHÒNG thêm nhiều ô**; màn +Niche mới có sẵn 2 ô key (chính/dự phòng) gắn ngay lúc tạo. Thiếu key (riêng + toàn org đều trống) → thêm kênh bị chặn với hướng dẫn rõ. Tab Quản trị giữ bảng key tổng của org.

### Phase 3.13 — Nhịp pool trên Board ✅ (chốt với user 12/07/2026 qua hỏi-đáp, code 22/07/2026)
- Panel 2 đồ thị TRƯỚC Cohort D0: **sóng views** (tổng views cộng thêm của pool theo thời gian) + **sóng VPH trung bình** (Δviews/giờ/video của các video 0-6 ngày tuổi — vùng sóng radar canh, heuristic ghi rõ trên chart). Toàn pool gộp (user chọn); mặc định 7 ngày điểm 6h.
- **Lưu vĩnh viễn để xem range rộng** (user yêu cầu): bảng `pool_stats(ws, bucket_ts 6h, dviews, vph_avg, n_young)` — engine upsert 14 ngày bucket gần nhất mỗi chu kỳ (idempotent từ ticks trước khi prune); range 1T/3T/1N/5N/custom gộp theo ngày lúc đọc. Trung thực: backfill tối đa 14 ngày — đồ thị dài hạn tích lũy từ 12/07/2026 trở đi.
- API `GET /workspaces/{ws}/pulse?days=N|start&end` (viewer đọc được, 0 quota); UI tái dùng LineChart (thêm prop nhãn trục thời gian).
- **Vòng phản biện 23/07/2026 (user chất vấn "khung giờ chính xác" + "số thật vs số kỳ vọng"):**
  - Bucket đổi sang **căn giờ VN chuẩn 00-06-12-18** (trước đó lệch múi UTC thành 01-07-13-19 VN) + **phân bổ tuyến tính**: views cộng thêm giữa 2 lần quét chia đều cho các khung nằm giữa, thay vì dồn cục vào lần quét (video nguội quét 4-24h/lần làm khung phồng giả). User duyệt qua bản xem trước artifact dựng từ data thật VPS. Ghi rõ trên UI: đây là ước lượng phân bổ (YouTube không có log từng view), chỉ dựng lại được cho 14 ngày gần.
  - **Rà soát VPH/VPD theo yêu cầu user**: VPH trên board = tốc độ đo THẬT (delta 2 lần đọc API cách ~3h, không phải tam suất); VPD của video <~24h tuổi = VPH×24 (kỳ vọng) nhưng KHÔNG được đánh dấu — user chốt: **giữ số, gắn dấu `~`** (cờ `est_vpd` từ core ra board JSON; bảng md đóng băng không đổi — chỉ UI).
  - **Panel Top 3 kênh tăng trưởng theo ngày** (panel riêng dưới Nhịp pool, user chốt): 7 ngày × top 3 (tên kênh · views trong ngày · % so hôm trước); dòng Hôm nay đang-chạy cập nhật theo chu kỳ quét, so **cùng thời điểm hôm qua**. Nguồn: bảng mới `channel_stats(ws, bucket_6h_VN, ch, dviews)` cùng cơ chế giữ-vĩnh-viễn/hóa-thạch như pool_stats.
- Thi công (22/07/2026): `scan.pool_pulse` cuối mỗi chu kỳ — 14 ngày gần REPLACE (idempotent), cũ hơn INSERT OR IGNORE (backfill 1 lần từ nến ngày rồi hóa thạch); bucket đang mở bị UI bỏ để không vẽ cú tụt giả; xóa niche purge cả `pool_stats`. 5 case mới trong verify_phase2 §3b.
- Nhãn range (user chốt 22/07/2026, 2 vòng): **W / M / Y + Tùy chọn** — bỏ mốc 5 năm và 3 tháng, bỏ kiểu "7N/1T" vì chữ N vừa là Ngày vừa là Năm gây nhầm.
- Kèm lệnh user 22/07/2026 "làm đẹp biểu đồ, tham khảo git thiết kế trên GitHub": LineChart nâng thẩm mỹ theo ngôn ngữ uPlot/Tremor/shadcn-charts (area gradient mờ dần, crosshair theo con trỏ, grid chấm mảnh, tooltip card đậm-giá-trị) — KHÔNG thêm dependency, vẫn SVG tự vẽ; áp cho mọi chart dùng LineChart (modal video + Nhịp pool).

### Phase HARVEST ✅ (spec đóng băng + code 23/07/2026 — nguồn sự thật: `spec_harvest_1.md` §10 + `radary_methodology.md`)
- Module `radary/harvest/` độc lập, READ-ONLY với dữ liệu sống, advisory (NP5): nhập list kênh → SEED (≤5, snowball thẳng) / POOL (phân loại 2 tầng ngôn ngữ→định dạng, user cắt cây + ✕ kênh khỏi nháp) → snowball centroid đóng băng đến hội tụ (≤1 kênh mới/vòng, trần 6 vòng) → report gọn trên UI + tải full .md.
- Kho key TÁCH RIÊNG (`api_keys.harvest=1`, dán loạt trong Setting) — radar và Harvest không bao giờ tiêu key của nhau. Không cổng duyệt quota (user bỏ 23/07) — chỉ cảnh báo key trống/hết, PAUSE resumable.
- Nghiệm thu: `verify_harvest.py` 18 case offline (Fake API) + 4 case bề mặt API trong phase 2. Case vàng SỐNG (Life-in-Country hội tụ, Space phân rã, NASA/Yes Theory đối chứng âm) chạy tay khi user cấp key — tốn ~10-15K units.
- TODO mở: ngưỡng trục MẠNH luật kép (`runner.STRONG`: aud≥2/voc≥22/subs≥20K/long≥0.75) — spec để trùng cổng vào sẽ làm mọi kênh đều hạng A nên tạm nâng, user hiệu chỉnh sau 2 tuần chạy thật; audit pool đang chạy (công cụ 3) để v2.

### Phân quyền v2 ✅ (user chốt 23/07/2026)
- Đổi tên vai `editor` → **`leader`** (ROLE_RANK giữ alias editor cùng bậc; `_migrate` tự UPDATE members/invites — idempotent).
- **Data Pool · Harvest · +New Niche = leader trở lên**, chặn tại API: GET channels + hồ sơ kênh + mọi route harvest (kể cả xem report) → viewer 403. Viewer còn: Board/Alerts/Report/Tuning-xem.
- **Sửa bug "chỉ owner tạo được niche"** (user báo 23/07): nguyên nhân kép — thành viên gắn phạm vi 1 niche bị chặn bởi thiết kế (đúng, giữ); còn leader toàn-org tạo được VỎ niche nhưng không gắn được key (add_key owner-only) → flow đứt. Sửa: **leader được gắn key cho MỘT niche trong phạm vi mình** (key toàn org + kho Harvest vẫn owner-only); form key trong New Niche mở cho leader.

### Phase 3.11 — Board pool lớn + AI đọc biểu đồ (lệnh user 08/07/2026)
- **"Xem tất cả N video"**: cohort/bảng mọi-tuổi mặc định hiện top 15 (board đọc ≤2 phút), bấm là mở trọn — board JSON vốn không cắt, đây thuần UI. Vá khe hở pool trăm kênh: vùng T1 (20% cohort) có thể vượt 15 dòng.
- **"🧠 AI đọc biểu đồ"** trong modal chart (editor+, chung trần 30 lượt LLM/ngày với Hỏi Radar): LLM nhận ĐÚNG dữ liệu chart đang vẽ (vph_series/trend/markers/bands tiền lệ, rút mẫu) → diễn giải pha sóng, so tiền lệ P50/P90, tác động marker, kèm "sai trong trường hợp nào". Ranh giới Phase 7 giữ nguyên.

### Phase 3.10 — Kênh yêu thích ⭐ (lệnh user 08/07/2026)
- Ngôi sao cạnh kênh trong Pool (bật/tắt = editor trở lên, trạng thái chung cả workspace); mọi video đang tracking của kênh ⭐ hiện sao vàng trên Board (cohort + VPD-mọi-tuổi). Cột `channels.favorite`; board JSON thêm `ch_id`/`fav` (enrich lúc đọc — bấm sao thấy ngay, không chờ chu kỳ quét).

## 3. Tương lai xa (ghi giữ cửa — CHƯA code, chưa có thứ tự)

- **Tầng L0/L1 sản phẩm hóa:** workspace khai báo "thực thể chủ đề" (quốc gia, sự kiện, game...) → theo dõi Wikipedia Pageviews + lịch sự kiện công khai → cảnh báo "cú sốc tò mò" trước khi video đầu tiên kịp chín (theo lý thuyết `niche_analytics.md` §B). Khác biệt hóa chính so với vidIQ/1of10 (họ chỉ ở L2-L3).
- **Tầng theme:** auto-tag chủ đề video (LLM) ở tầng báo cáo → chạy TC1-TC4: cung/cầu theme, pha vòng đời, chất lượng kênh gia nhập → trả lời "mình là người thứ mấy vào sóng".
- **Comment mining (TC5):** câu hỏi chưa được trả lời trong comment đối thủ = content gap; dịch chuyển cảm xúc = rủi ro hệ thống của niche.
- **Phân tích re-packaging:** dữ liệu thumb/title đã lưu từ 07/07/2026 → báo cáo "video hồi sinh sau khi đổi thumbnail" (tín hiệu packaging mạnh, thị trường chưa ai có).
- **Backtest lịch sử khi onboard niche:** quét sâu uploads toàn pool + mô phỏng luật trên lịch sử để đề xuất sàn ngay ngày đầu (thay vì chờ 14 ngày hiệu chỉnh sống) — cần giải bài toán quota + thiên lệch views-cuối.
- **Vòng tự chấm bước 2:** job chấm kết cục alert sau 7-30 ngày (video đạt X views? kênh khác vào theo?) → precision per niche → auto-tune có phê duyệt.
- **Billing/plans:** giới hạn theo #workspace, #kênh, nhịp quét, ngày retention — các van đã là field config từ Phase 1.
- **Migrate PostgreSQL** khi nhiều org ghi đồng thời.

## 4. Cố tình KHÔNG làm (chống scope creep)

- Realtime websocket dashboard — API YouTube cache 30-60 phút, "realtime" là độ chính xác giả; polling là đủ.
- Mobile app native — web responsive + ntfy đủ.
- AI tự quyết "nên đánh không" — vi phạm nguyên tắc 5; AI chỉ được đính kèm ngữ cảnh, không khuyên.
- Microservices / Kafka / Postgres ngay bây giờ — monolith FastAPI + SQLite chịu được hàng trăm workspace.

### Heatmap giờ đăng ✅ (brief `heatmap_build_brief.md`, user chốt 23/07/2026 qua 3 vòng mockup)
- Panel Board dưới Nhịp pool: lưới 7 thứ × 24 giờ, giờ ĐĂNG theo `pub_ts` có sẵn (KHÔNG phải giờ xem — giờ xem đối thủ bất khả thi), 0 quota, chỉ long-form >180s.
- Chốt UI qua mockup: CHỈ một lưới pool cố định · hover ô = popup kênh + số video (không cần bấm) · dropdown chọn kênh → lưới đổi tại chỗ, chọn Toàn pool quay về · 📖 Đọc-hộ bấm-mới-hiện (mô tả cụm dày, KHÔNG khuyên giờ đăng — NP5) · chip 30/90 (mặc định)/Tất cả · giờ VN⇄UTC.
- Trung thực: in rõ "tính trên N video radar đã bắt (cũ nhất …) — nhịp đăng gần đây, không phải lịch sử trọn đời kênh"; video thiếu pub_ts bỏ qua êm.
- Engine `radary/heatmap.py` thuần stdlib chỉ-đọc + self-test; 5 case brief §7 trong verify_phase2 §3d (tổng ô = tổng video, tập con 90 ngày, dịch múi giờ, lọc kênh, days lạ 400).

### Metrics kiểu vidIQ trên Board ✅ (user duyệt mockup v3 ngày 23/07/2026 — thay bảng Top kênh/ngày)
- **Vòng duyệt:** mockup v1 (tile to) bị bác "quá to và thô" → v2 đúng tỉ lệ app 1180px → v3 theo đúng cách sắp xếp vidIQ user chỉ định: nhãn nhỏ TRÊN, số to DƯỚI, badge %/pill Ranked cùng dòng số, hàng 1 = 4 tile hiệu suất rộng, hàng 2 = tile hồ sơ hẹp hơn. Nhãn tiếng Anh (user chốt). User ra lệnh "thay thế cho phần top kênh tạo view hàng ngày" → panel Metrics (kèm heatmap giờ đăng bên trong) thay CẢ bảng Top kênh lẫn panel heatmap rời; `/pulse` bỏ `top_channels`.
- **Khả thi trung thực (đã chốt khi thảo luận):** không có hạng toàn cầu (DB riêng của Social Blade) và không ước tính earnings (số bịa) → thay bằng **Ranked #x/N trong pool theo views 7 ngày** + **Most posted hours** (từ heatmap, mô tả — không khuyến nghị, giữ NP5).
- **Tile hàng 1:** Total views · Views gained (7 days) so 7 ngày liền trước (channel_stats — số đo thật) · Subscribers · Top outlier (7 days) = bậc cao nhất đạt trong 7 ngày + pill "% vs P50" (VPH đỉnh so sóng trung vị tiền lệ từ `series.reference_bands`). **Hàng 2:** Current avg VPH (video 0-6d) · Surging T1+ · Videos tracked · Avg. video length · Upload frequency (~) · Most posted hours.
- **Snapshot ngày `channel_snap`:** `scan.snap_channels` chụp subs/viewCount/videoCount trọn đời kênh 1 lần/ngày theo tz workspace (~1 unit/50 kênh ≈ 2 units/pool), giữ vĩnh viễn; lỗi snapshot chỉ làm thiếu Metrics hôm đó, KHÔNG giết chu kỳ. % so ~7 ngày trước tính trên GIAO 2 tập kênh (kênh thêm/gỡ không làm méo); kênh ẩn subs → NULL, loại khỏi %.
- **Trung thực dữ liệu:** mọi % thiếu lịch sử (chưa đủ 7 ngày snapshot / 14 ngày nhịp) trả None → UI hiện '—' kèm tooltip lý do — không ước đoán; Upload frequency mang dấu `~` (trung bình 30 ngày).
- Nghiệm thu: verify_phase2 §3e (8 case — unit snap_channels Fake API idempotent + trường thiếu, E2E hợp đồng trường, parity gain7 với DB, số học % giao 2 tập kênh, phạm vi kênh + rank, /pulse hết top_channels, heatmap.peak) + self-test heatmap. Bổ sung: `/metrics` trả `channel_yt_id` → nút "▶ Xem kênh trên YouTube ↗" mở thẳng `/channel/UC…` khi xem 1 kênh (user yêu cầu 23/07); CSS `button.btn`→`.btn` để anchor ăn style nút.

### Cảnh báo gom theo đơn vị ✅ (user duyệt mockup ngày 24/07/2026 — sửa lỗi UX list vô tận)
- **Lỗi gốc:** tab Cảnh báo đổ thẳng sổ cái `events` ra UI, 1 dòng/event. Đo thật Life in X: 424 event bậc trên 73 video = **5,8 dòng/video**, video tệ nhất **24 dòng** (thăng–hạ qua lại), ~59 event/ngày → không tập trung được + list dài vô tận. Ràng buộc: `events` là sổ cái append-only KHÔNG xóa → sửa ở tầng TRÌNH BÀY, không sửa cách ghi.
- **Vòng duyệt (nhiều lần hiểu sai, ghi để nhớ):** Claude gộp bừa 8 sub-tab thành 2 nhóm → user bác "hiểu sai, quay lại phương án trước" + "cần tối giản" → làm lại giữ các sub-tab, áp thiết kế gọn cho từng cái. Sau khi chạy thật, user bắt tiếp lỗi: tab "Tất cả" (mặc định) trộn thẻ sóng + mọi loại → nhìn như "dồn hết vào tab Thăng/hạ bậc" → **chốt cuối 24/07: BỎ hẳn "Tất cả", còn 7 sub-tab** (Thăng/hạ bậc mặc định · Đổi title · Đổi thumbnail · Video Xóa/Ẩn · Kênh ẩn hàng loạt · Đổi cấu hình · Đổi pool) — "chức năng của tab nào phải ở tab đó". Mockup dữ liệu thật + revert-được là cách khớp ý.
- **Gom theo ĐƠN VỊ (module `radary/alertsview.py`, chỉ đọc):** `tier`→**sóng/video** (thẻ + sparkline quỹ đạo bậc thay chuỗi mũi tên, chia Đang sống [T2+ hoặc <7 ngày] / Đã lắng, chỉ video peak≥2, bung sự kiện gốc) · `retitle`/`rethumb`→**theo kênh** (1 kênh/dòng, số lần + số video) · `dead`/`channel_purge`/`pool_change`/`config_change`→**phẳng** · kind rỗng/lạ→về waves (mặc định). Kết quả thật: 424 event bậc → 28 thẻ (15 sống).
- **Verdict theo VIDEO:** dùng lại bảng `verdicts` (khóa event_id) — chấm vào event T2+ ĐẠI DIỆN (id mới nhất to≥2) của video, không thêm bảng. 1 nút thẩm định/thẻ thay vì rải theo từng event.
- Nghiệm thu: self-test `python -m radary.alertsview` (gộp/loại T1/verdict đại diện/kind lạ→mặc định) + verify_phase2 §4b (7 case: mode waves/channels, thẻ đủ trường, gộp giảm dòng, verdict round-trip, kind rỗng→waves) + verify_phase3 vòng verdict cập nhật theo shape mới.
