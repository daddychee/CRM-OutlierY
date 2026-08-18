# RADARY_THI_TRUONG.md — sổ chủ đề POOL THEO THỊ TRƯỜNG (RadarY V3)

> Mạch việc: tách đo lường RadarY theo THỊ TRƯỜNG. Bối cảnh: pool hiện trộn kênh
> nhiều thị trường (Life in X: US 77 / ES 22 / VN 4 — phát hiện 18/08 mạch Niche
> Research) nên mọi số liệu (board, metrics, ngưỡng T1-T4, báo cáo) tính trên
> tổng hợp. Sổ này giữ quyết định + thiết kế + trạng thái; CLAUDE.md gốc và
> APPS.md chỉ trỏ về đây.

## Quyết định user đã chốt (18/08/2026)

1. **Pool = thị trường.** Mỗi workspace (niche-pool) RadarY gắn ĐÚNG MỘT thị
   trường. User tạo pool phải chọn thị trường — không sợ nhiều workspace (máy +
   API V3 đáp ứng được). Tách pool trộn hiện có thành các pool theo thị trường.
2. **Ngưỡng/alert theo thị trường** — đạt TỰ NHIÊN qua mô hình pool-per-market:
   mỗi workspace đã có sẵn config T1-T4 + ntfy + hiệu chỉnh riêng. KHÔNG đổi
   luật lõi radar (radar_spec.md đóng băng giữ nguyên — không sửa core).
3. **Danh mục thị trường đối chiếu từ ĐẾ** (General › Niches, bảng `thi_truong`
   mã TT-xx). Dropdown, không gõ tự do (DE.md luật 2 — app không tự đẻ sổ phân
   loại). Thiếu thị trường nào → Owner thêm ở General trước.

## Thiết kế

- **Gateway** thêm `GET /api/danh-ba/thi-truong` (loopback-only, khuôn
  `/api/cau-hinh/api-khoa`) trả `[{ma, ten, ngon_ngu}]` từ `danh_ba.liet_ke`.
- **radary/thi_truong_v3.py** (khuôn khoa_v3): đọc danh mục qua gateway, cache
  60s, lỗi → RuntimeError thông điệp rõ, KHÔNG fallback sổ nội bộ.
- **Schema**: `workspaces.market TEXT NOT NULL DEFAULT ''` (mã TT-xx; '' = pool
  cũ chưa gán). Migration nhẹ idempotent trong `db._migrate` (khuôn favorite).
- **API radary**:
  - `GET /api/thi-truong` — danh mục cho dropdown UI (auth; ngoài V3 trả `[]`
    → hành vi standalone không đổi).
  - `POST /api/workspaces` nhận `market`; khi `RADARY_TRUST_PROXY=1` thì BẮT
    BUỘC + server tra lại danh mục đế (giá trị lạ 422 — dropdown kiểm ở server,
    bất biến kế thừa). Standalone: tùy chọn (tương thích V2).
  - `PATCH /api/workspaces/{ws}/market` (leader+) — gán thị trường cho pool có
    TRƯỚC tính năng; ghi event `config_change` có vết.
  - `POST /api/workspaces/{ws}/channels/move` (manager+ cả 2 đầu, cùng org,
    `confirm` bắt buộc) — TÁCH POOL: chuyển kênh sang pool đích **GIỮ LỊCH SỬ**:
    `channels`/`videos` đổi workspace_id (ticks/title_hist/thumb_hist theo
    video_id — tự nguyên vẹn); `channel_stats` cộng dồn sang đích theo tên kênh
    (UPSERT); `channel_snap` chuyển theo ch_yt_id (trùng ngày → giữ bản đích);
    `events` KHÔNG đụng (append-only, ở lại làm sử liệu) + ghi event `pool`
    move_out/move_in cả 2 bên; `pool_stats` KHÔNG tách (nhịp pool cũ = sử liệu
    giai đoạn trộn — VPH/nhịp pool per-market chỉ có từ lúc tách, trung thực
    hiện "—", không bịa).
- **UI** (web/app.js, Preact htm — LUẬT: không viết `<` thô trong template):
  New Niche thêm dropdown Thị trường bắt buộc; switcher workspace + Tuning hiện
  nhãn thị trường (Tuning cho đổi, leader+); Data Pool thêm chọn kênh → "Chuyển
  sang pool khác" (confirm, manager+).
- **Số liệu theo thị trường** = số liệu per-pool sẵn có (Board/Metrics/Heatmap/
  Báo cáo tuần/Niche report từng workspace). So sánh CHÉO nhiều thị trường trong
  một màn = backlog, chờ user cần thật.

## Ràng buộc an toàn (kế thừa, không phá)

- V3 chạy song song hệ thật: dữ liệu `data/radary` là SNAPSHOT — tách pool lúc
  này là NGHIỆM THU TÍNH NĂNG; sau cutover chạy lại việc tách trên dữ liệu thật
  bằng chính UI này (vì vậy làm thành tính năng lặp lại được, không script một
  lần). `RADARY_SCHEDULER=0` giữ nguyên; nghiệm thu quét bằng POST /run tay.
- Backup/manifest KHÔNG đổi: không store mới, không đổi đường dữ liệu
  (`radary.db` vẫn sqlite-snapshot vàng — apps.json giữ nguyên).
- `events` append-only tuyệt đối; mọi ghi trong 1 transaction; move idempotent
  về mặt an toàn (chạy lại → 409/404 rõ ràng, không ghi đôi).

## Trạng thái

- 18/08/2026 — Mở sổ. User chốt 3 quyết định (mục trên). Khảo sát: 8 workspace,
  schema chưa có trục thị trường; đế có TT-US / TT-KOREA / TT-SPAIN.
- 18/08/2026 — **THI CÔNG XONG TRỌN THIẾT KẾ** (1 commit): gateway
  /api/danh-ba/thi-truong + thi_truong_v3.py + cột workspaces.market (migration
  nhẹ idempotent) + 4 route (GET /api/thi-truong · POST workspaces bắt buộc
  market khi V3 · PATCH market có vết · POST channels/move giữ lịch sử) + UI
  4 chỗ (NewNiche dropdown · switcher nhãn · Tuning đổi thị trường · Data Pool
  tích chọn + chuyển pool). Test: root 182 pass (tests/test_radary_thi_truong.py
  mới) + radary app 14 pass (tests/test_thi_truong.py — tạo/gán/move/hồi quy
  standalone). app.js smoke Chrome headless 9111 render OK (máy không có node).
  BẪY GHI LẠI: (a) conftest radary đã TỒN TẠI — suýt ghi đè, phải gộp (kiểm
  git status trước khi Write file mới); (b) db.DEFAULT_DB chốt lúc import →
  fixture dọn db phải dọn theo db.DEFAULT_DB thật, không theo tmp của mình
  (test_lam_gon import trước với env riêng); (c) 4 test ghim /open/<slug> vỡ
  sẵn từ PA3 4f37839 — sửa pin theo luật /<slug> đã commit, commit tách riêng.

## Nghiệm thu còn chờ (user/Owner)

1. Restart tác vụ radary V3 (API mới cần tiến trình mới; app.js thì không cần).
2. Qua 9443: tạo pool mới → dropdown thị trường hiện đúng TT từ General;
   thử bỏ trống → bị chặn; Tuning gán thị trường cho pool cũ.
3. Data Pool (vai Manager/Owner): tích vài kênh → chuyển sang pool thị trường
   mới → kiểm Board/Metrics pool đích có kênh + lịch sử nhịp kênh, pool nguồn
   sạch; Alerts pool nguồn còn nguyên sổ cái.
4. Tách thật pool trộn (Life in X…) làm trên V3 để nghiệm thu; SAU CUTOVER
   chạy lại việc tách trên snapshot cuối bằng chính UI này (sổ đã ghi).

## Nợ đã thấy khi khảo sát (KHÔNG thuộc mạch này — ghi để khỏi quên)

- `api.py` add_channels/channel_profile/overview_refresh + `niche_report.py`
  còn đọc key từ bảng nội bộ `db.api_keys` (bảng đã tuyên bố NGHỈ ở mạch làm
  gọn 16/08; snapshot còn 19 key cũ nên vẫn chạy). Thuộc mạch migration khóa —
  chờ Owner chạy `scripts/di_tru_khoa_radary.py` rồi rà nốt các điểm đọc này.
