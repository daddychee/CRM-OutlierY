# CHANGELOG — Radary

Mô tả các đợt update chính, mới nhất trước. Chi tiết quyết định thiết kế + vòng phản biện của
từng tính năng ghi vết ở `docs/roadmap.md`; luật nghiệp vụ ở `docs/radar_spec.md` (đóng băng v3).

## V2 — 22→24/07/2026 · bản đóng gói bàn giao 24/07

### 24/07/2026 — Alerts gom theo sóng · vá job Harvest kẹt · tải pool CSV
- **Tab Alerts thiết kế lại toàn bộ** (sửa lỗi UX list vô tận: 1 video từng chiếm 24 dòng): 7 sub-tab,
  bỏ "Tất cả", mặc định Thăng/hạ bậc. Thăng/hạ bậc = mỗi video một THẺ SÓNG (sparkline quỹ đạo bậc,
  Đang sống/Đã lắng, 1 nút thẩm định/video, bung được sự kiện gốc); Đổi title/thumbnail gom theo KÊNH;
  còn lại danh sách phẳng. Module mới `radary/alertsview.py` — chỉ đọc, sổ cái `events` giữ nguyên.
- **Harvest: job ERROR thử-lại được** từ checkpoint (nút "▶ Thử lại từ chỗ dừng") — trước đó job lỗi
  kẹt vĩnh viễn dù code đã vá, phải làm lại từ đầu.
- **Data Pool: nút ⬇ Tải danh sách (.csv)** — tên kênh/URL/ID/⭐, mở được Excel (BOM UTF-8), cột URL
  dán lại được vào Radary/Harvest. Thuần client, 0 quota.
- Fix production: chữ `<7` thô trong template htm bị parse thành tag → sập tab Alerts; thêm chốt chặn
  tĩnh vào verify_phase3 + LUẬT htm vào CLAUDE.md.
- Đóng gói bàn giao V2 sạch dữ liệu (không DB/key/state, định danh hạ tầng thay placeholder).

### 23/07/2026 — Module Harvest v1 · Phân quyền v2 · Heatmap giờ đăng · Khối Metrics
- **HARVEST v1** (spec `spec_harvest_1.md` đóng băng, 2 vòng phản biện): tìm & thẩm định kênh mới bằng
  snowball centroid đóng băng + đo trùng khán giả; kho key riêng radar không đụng; job nền checkpoint
  resumable; 3 bước UI (nhập → Phân loại Workspace → Report + tải .md). READ-ONLY với dữ liệu sống.
  Trong ngày vá luôn sự cố đầu tiên: `allThreadsRelatedToChannelId` bị YouTube khai tử → đọc comment
  theo từng video, lỗi comment không giết job.
- **Phân quyền v2**: đổi vai `editor` → `leader` (migrate tự động); Data Pool/Harvest/+New Niche yêu cầu
  leader trở lên (chặn tại API); leader gắn được key cho niche trong phạm vi mình → mở khóa flow tạo niche.
- **Heatmap giờ đăng** (0 quota, từ pub_ts có sẵn): lưới thứ × giờ, hover xem kênh từng ô, xem theo kênh,
  VN⇄UTC, 30/90/Tất cả ngày, đọc-hộ mô tả (không khuyến nghị giờ đăng).
- **Khối Metrics kiểu vidIQ trên Board** (thay bảng Top kênh/ngày + panel heatmap rời): 2 hàng tile
  nhãn tiếng Anh + pill %, phạm vi pool⇄kênh đổi cả số lẫn heatmap; nút mở kênh trên YouTube.
  Bảng mới `channel_snap` chụp subs/views trọn đời kênh 1 lần/ngày (~2 units/pool); % thiếu lịch sử
  hiện "—" — không ước đoán. Đổi nhãn tab: Board · Alerts · Report · Data Pool · Harvest · Tuning ·
  Setting · +New Niche.

### 22→23/07/2026 — Nhịp pool + một ngôn ngữ biểu đồ
- **Nhịp pool trên Board**: 2 đồ thị sóng views/VPH TB toàn pool, range W/M/Y + tùy chọn; bảng
  `pool_stats`/`channel_stats` bucket 6h GIỮ VĨNH VIỄN, căn giờ VN 00-06-12-18, views phân bổ tuyến tính
  giữa 2 lần quét (duyệt qua bản xem trước dữ liệu thật).
- Toàn bộ chart (web + 3 SVG báo cáo tuần) theo MỘT ngôn ngữ thị giác kiểu uPlot/Tremor: gradient mờ,
  crosshair, grid chấm — không thêm thư viện.
- Trung thực số liệu: mọi số ước lượng mang dấu `~` (VPD kỳ vọng của video <24h có cờ `est_vpd`).

## V1 — 07→17/07/2026 · nền tảng (Phase 1-7, chạy production)
- Port engine radar đã backtest (spec v3, niche testbed "Life in X") từ script cron sang **app đa
  workspace**: FastAPI + SQLite (multi-tenant org→member→workspace) + dashboard Preact không build-step.
- Phase theo `docs/roadmap.md`: engine parity (1) → API + scheduler (2) → dashboard + onboarding niche
  (3) → auth scrypt + mã hóa key Fernet + phân quyền 3 bậc + mã mời (4-5) → báo cáo tuần 7 phần +
  báo cáo ngách tự sinh (6) → lớp LLM diễn giải BYO key, cấm sinh số/cấm khuyên (7).
- Key YouTube BYO theo niche + key dự phòng tự đôn khi 403 (bài học quotaExceeded 10-11/07: quota tính
  theo DỰ ÁN Google Cloud). Chart sóng T2+ với dải tiền lệ P25-75/P50/P75/P90.
- **Deploy production 08/07**: VPS Vultr Docker, public qua Tailscale Funnel kèm gia cố (mã mời bắt
  buộc, rate-limit login, secure cookie). 17/07: backup source lên GitHub private.
