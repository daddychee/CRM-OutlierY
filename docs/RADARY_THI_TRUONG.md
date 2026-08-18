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

- 18/08/2026 — **VÒNG 2 THEO PHẢN HỒI USER: TAB NHỎ POOL THEO THỊ TRƯỜNG CỦA
  NGÁCH** ("Trong tab Pool có tab nhỏ theo thị trường của ngách được tạo ở
  general. Kênh được chuyển từ pool này sang pool khác hoặc nhập mới hoàn
  toàn"). Cơ chế: workspace thêm trục `ngach` (mã N-xxx từ đế — cùng khuôn
  market, đúng hướng Đ4 workspace↔N-xxx, cấm map theo tên): gateway thêm
  `GET /api/danh-ba/ngach` (ngách + tập thị trường của ngách từ
  `ngach_thi_truong` — user chọn ở General, không mặc định);
  `thi_truong_v3.ds_ngach()`; validation nâng thành CẶP `_kiem_de` (ngách tồn
  tại + market THUỘC ngách; ngách 0 thị trường → 422 chỉ đường General);
  `GET /api/ngach` join tên đẹp cho UI; PATCH market nhận cặp. UI Pool: dải
  tab nhỏ = các thị trường của ngách — tab có pool hiện tên + số video (bấm
  chuyển xem/quản pool đó ngay trong tab Pool), tab CHƯA có pool = nút ＋ tạo
  pool (leader+, tên tự sinh `<ngách> — <thị trường>`); thêm kênh/gỡ/⭐/hồ sơ/
  move đều chạy theo tab đang mở; pool chưa gán ngách → note chỉ sang Tuning,
  Tuning giờ gán CẶP ngách+thị trường (2 dropdown lồng + nút Gán); NewNiche
  đổi thành ngách → thị trường của ngách. Suite: radary app 16 + root 183
  pass; nghiệm thu SỐNG: restart radary 9111 + gateway 9000 (SESSION_SECRET
  trong .env nên phiên sống), /api/danh-ba/* trả 4 thị trường + 2 ngách thật
  (LIFE IN: KR/ES/US · OLD: US — Owner đã khai ở General), /api/ngach join
  tên chuẩn, Chrome headless render OK. Migration cột ngach tự áp db thật.

- 18/08/2026 — **VÒNG 3 — USER SỬA LOGIC: NGÁCH-TRƯỚC, TUNING KHÔNG GÁN**
  ("Niche được sinh ra trong khối General, khối Tuning ko có quyền để gán
  ngách. Nếu ngách Life In có 3 ngôn ngữ thị trường thì pool cũng phải có 3").
  Mô hình chốt: **General là nguồn CẤU TRÚC duy nhất — RadarY chỉ phản chiếu**,
  không có bước gán ngách phía RadarY. Tab Pool giờ: (1) ô chọn **Ngách**
  (danh sách từ đế) + nhóm "Pool cũ — <tên>" cho pool trộn chưa xếp; (2) chọn
  ngách → dải tab nhỏ hiện ĐỦ mọi thị trường của ngách — tab đã có pool bấm
  là quản, tab chưa có = nút ＋ leader bấm là DỰNG NGAY (tên tự sinh
  `<ngách> — <thị trường>`, không hỏi lại — cấu trúc đến từ General); (3) mở
  pool cũ → tích kênh → chuyển về pool thị trường (dest gắn nhãn
  `<ngách> — <thị trường>`); (4) GỠ khối "Ngách · thị trường" khỏi Tuning
  (Tuning chỉ còn ngưỡng/ntfy); NewNiche tự điền tên theo ngách—thị trường.
  Backend KHÔNG đổi (không cần restart — app.js đọc từ đĩa); PATCH
  /workspaces/{ws}/market GIỮ làm API vận hành (có test) nhưng KHÔNG còn UI —
  đường chính thống là dựng pool từ cấu trúc. Suite radary 24 pass, headless OK.

- 18/08/2026 — **VÒNG 4 — USER CHỐT MÔ HÌNH CUỐI: WORKSPACE = NGÁCH** ("không
  phải chuyển giữa các pool khác niche — trong 1 niche tồn tại các pool theo
  thị trường; Life in X, Space, Storm chính là các ngách"; "sửa niche Life in X
  thành LIFE IN; từ nay CHỈ tạo niche trong General mới có tên pool trong
  Radary"). Đã làm: (a) DATA: workspace 1 đổi tên `Life in X` → `LIFE IN`
  (đúng ten_chuan đế) + nối `ngach=N-LIFE-IN`, market='' = POOL GỐC "chưa
  phân loại", event vết (sửa thẳng db V3 — snapshot test, có vết). (b) BỎ ô
  chọn ngách + nhóm "Pool cũ" của vòng 3 — tab Pool bám workspace-ngách đang
  chọn ở switcher; trong ngách: tab **"Chưa phân loại"** (kênh của workspace
  gốc) + các tab thị trường của ngách; **chuyển kênh CHỈ trong nội bộ ngách**
  (dest = tab anh em, có cả chiều trả về gốc). (c) Workspace chưa nối General
  → banner gợi ý khớp tên + 1 nút "Nhận … là ngách này" (leader+): PATCH
  market rỗng (`cho_phep_goc`) → server nối MÃ + **tự đổi tên pool theo tên
  ngách General** (luật tên-từ-General). (d) "+ New Niche" V3: ô tên tự do
  BỎ — tên tự sinh `<ngách> — <thị trường>` hiện preview; standalone giữ
  nguyên. Suite radary 25 pass; restart 9111; headless OK.

- 18/08/2026 — **VÒNG 5 — 3 YÊU CẦU VẬN HÀNH + ƯU TIÊN "xem từng thị trường +
  volume cả ngách"**: (1) DẢI TAB THỊ TRƯỜNG LÊN CẤP APP (dưới header, hiện ở
  Board/Alerts/Report/Pool/Tuning): bấm tab = chuyển pool thị trường — Board
  xem theo thị trường được (yêu cầu 1); Pool bỏ dải tab nội bộ (một dải duy
  nhất, nhận nganhs qua props). (2) Đếm theo SỐ KÊNH trên dải tab +
  list_workspaces thêm trường `channels` (yêu cầu 2 — Data Pool quản kênh).
  (3) Nút **Σ Cả ngách** trên Board → `GET /api/ngach/{ma}/volume`: cộng nhịp
  views MỌI pool của ngách user thấy (pool_stats gộp theo ngày, VPH TB trọng
  số n_young) + bảng volume theo thị trường (kênh/video/views 7d/28d từ
  channel_stats — số đo thật, không bịa; lưu ý trung thực: nhịp pool đích chỉ
  tích từ lúc tách, quá khứ pool trộn nằm ở "Chưa phân loại"). Suite radary
  26 pass; restart 9111; kiểm sống volume LIFE IN: 72 kênh · 4.922 video ·
  3,74M views 7d · 21,2M views 28d; 3 pool thị trường Korea/Spain/US đã dựng
  (0 kênh — chờ phân loại theo phương án mục dưới).

- 19/08/2026 — **VÒNG 6 — 4 CHỐT VẬN HÀNH + CHIA THẬT LIFE IN.** User chốt:
  (1) switcher CHỈ ngách (pool thị trường vào bằng dải tab — switcher lọc
  `!market`, đứng ở pool thị trường thì switcher hiện ngách mẹ); (2) BỎ tab
  "Chưa phân loại" khỏi Board — đổi pool chỉ ở Data Pool (Board của ngách
  mặc định = Σ Cả ngách; "Chưa phân loại" chỉ còn trên dải tab của Data Pool);
  (3) user DUYỆT phương án phân loại và giao máy TỰ CHIA LIFE IN (chưa chắc
  → để lại); (4) khi xong mọi niche sẽ BỎ tính năng "Chưa phân loại" (ghi
  việc treo — chỉ ẨN UI, pool gốc giữ làm sử liệu nhịp thời kỳ trộn).
  **ĐÃ CHIA THẬT LIFE IN** bằng script `scripts/phan_loai_thi_truong_radary.py`
  (0 quota — chấm ngôn ngữ TOÀN BỘ tiêu đề video đã quét; ngưỡng bảo thủ ≥5
  title + ≥80%; van hệ-chữ-khác/tiếng Việt; **van NGHI TIẾNG BỒ** bắt 3 kênh
  BR suýt chấm nhầm sang Spain — Minuto Em Foco/FEITO GEO/Explore World Docs,
  đúng họ bài học Globe Cover) + áp qua API move (vết claude-phan-loai):
  **US 45 kênh (3.186 video) · Spain 17 kênh (1.540 video) · để lại 10 kênh**
  (7 ít dữ liệu/0 video · 3 nghi PT; tổng vẫn 72 kênh/4.922 video — không mất
  data). Kiểm volume sau chia: US 1,79M views 7d · Spain 1,61M · chưa phân
  loại 0,15M. Script tổng quát hóa (argv ws_goc, kết quả JSON cạnh db) —
  dùng lại cho các niche khác + sau cutover.

- 19/08/2026 — **VÒNG 7 — BACKUP-TRƯỚC-CHIA-SAU + CHIA 3 NICHE MỚI.** User hỏi
  thứ tự backup: chốt **backup TRƯỚC** (thao tác ghi hàng loạt phải có đường
  lùi; VACUUM INTO — đúng luật cấm copy trần db đang mở). Hai snapshot tại
  `data/radary/snapshots/`: `radary-truoc-chia-space-storm-travel-20260819.db`
  (82,3MB — sau LIFE IN, trước 3 niche) + `radary-sau-chia-4-niche-20260819.db`
  (mốc sau chia — lùi được cả 2 chiều; Owner nghiệm thu xong thì dọn tùy ý).
  User tạo N-SPACE (US+Spain) / N-STORM (chỉ US) / N-TRAVEL-DOCUMENTA
  (US+Spain) ở General → chạy trọn quy trình (nối ngách tên theo General +
  dựng pool + phân loại + move có vết): **SPACE** US 156 · Spain 24 · để lại
  18 (8 nghi tiếng Bồ-Brazil, 2 Nga, 1 Hàn 우주 신호 — SPACE không khai Korea
  nên đúng luật để lại, 1 Trung, còn lại ít title chấm được); **STORM** US 50
  · để lại 8 (title kiểu cảnh báo thời tiết ít từ chức năng — tên kênh đọc
  rõ là US, user chuyển tay nhanh); **TRAVEL DOCUMENTARY** US 38 · Spain 1 ·
  để lại 1 (kênh CJK). Tổng toàn hệ giữ nguyên 606 kênh — không mất data.
  4 pool còn lại (Investigation / Old Investigate / OLD Newbie / Health):
  user chốt QUÁ BẨN, ĐỂ SAU — không đụng.

- 19/08/2026 — **VÒNG 8 — LUẬT PT=SPAIN + GỠ NGA/HÀN + THỨ TỰ TAB ƯU TIÊN.**
  User chốt: kênh Bồ/Brazil GỘP thị trường Tây Ban Nha (cùng họ ngôn ngữ);
  kênh Hàn/Nga TẠM GỠ khỏi pool; thứ tự UI: US trước → Spain → khác → "Chưa
  phân loại" → **Σ Cả ngách CUỐI dải** (bảng volume cùng thứ tự, backend sort).
  Đã áp: LIFE IN +3 PT → Spain (20 kênh · 2.079 video); SPACE +9 PT → Spain
  (33 kênh · 1.037 video) + GỠ 4 kênh Nga/Hàn (KOSMO/Апогей/Тихий Космос/
  우주 신호 — active=0, video purge theo lệ gỡ kênh, còn 2 snapshot cứu).
  Script chuẩn cập nhật luật pt-cộng-es (bỏ nhánh "nghi tiếng Bồ").
  **CHẨN ĐOÁN "radar không chạy" (user hỏi)**: KHÔNG phải lỗi — khóa đã cấp
  đủ (quet_dinh_ky 15 · harvest 14 · dien_giai 1, đọc từ két OK); V3 không
  quét vì `RADARY_SCHEDULER=0` CỐ ĐỊNH theo thiết kế song song (hệ thật V2
  cổng 8123 ĐANG quét bằng CÙNG bộ khóa — V3 quét song song = đốt đôi quota
  10K/dự án/ngày, bài học quotaExceeded 10-11/07 hệ cũ). **USER CHỐT 19/08:
  GIỮ NGUYÊN — V2 tiếp tục quét, V3 không tự quét, khi cần số mới thì quét
  TAY từng pool** (nút "Quét ngay" trên Board của pool đó, hoặc POST /run;
  leader trở lên; tốn quota thật — nên giờ thấp điểm). Chuyển vai quét sang
  V3 = quyết định cutover sau này.

- 19/08/2026 — **FIX 500 "Quét ngay"** (user báo): `report.render_board` ghi
  radar_board.md bằng `open(...,'w')` TRẦN → Windows mặc định cp1252 chết dấu
  tiếng Việt ('ầ') → 500 MỌI lượt quét trên V3 (V2 chạy VPS Linux nên chưa
  từng lộ — đúng họ bẫy UTF-8 trong memory). Vá gốc 15 chỗ open() text thiếu
  encoding (report/api/niche_report/migrate_legacy) + lưới `PYTHONUTF8=1`
  toàn dịch vụ trong start-all. Nghiệm thu sống: /run pool nhỏ tag DONE đủ
  6 job, 6 units. KÈM: tiến trình 9111 giờ ghi log ra
  `data/logs/radary-9111.log` (trước chạy ẩn không giữ log — mò bệnh phải
  tái hiện; giữ redirect này về sau).

## PHƯƠNG ÁN PHÂN LOẠI LẠI KÊNH POOL BẨN (đã duyệt 19/08 — chạy thật cho LIFE IN, xem vòng 6)

Bối cảnh: user không muốn phí data đã quét; V3 dừng quét 2 ngày (by design —
scheduler tắt), V2 vẫn chạy để đối chiếu. Nguyên tắc: cơ chế move đã GIỮ TRỌN
lịch sử video/tick/nhịp kênh → phân loại xong KHÔNG mất data cũ.

**3 bước, 0 quota YouTube, người duyệt là chốt chặn:**
1. **Máy gợi ý từ data ĐÃ QUÉT** (script offline đọc db V3): mỗi kênh active
   trong pool gốc chấm thị trường theo 3 nguồn — (a) NGÔN NGỮ TIÊU ĐỀ toàn bộ
   video của kênh trong bảng `videos` (hàng nghìn title đã quét: Hangul →
   Korea, dấu tiếng Việt → VN, function-words ES → Spain, còn lại EN → US —
   tái dùng fingerprint sẵn có của Harvest); (b) `country` trong hồ sơ kênh
   cache (`channel_info`); (c) đối chiếu bảng tách US 77/ES 22/VN 4 mạch
   Niche Research 18/08. Ra bảng: kênh → gợi ý + độ đồng thuận + bằng chứng.
2. **Người duyệt trên UI**: tab "Chưa phân loại" hiện cột gợi ý + nút "tích
   theo gợi ý <thị trường>" — user soi mắt bỏ tick kênh nghi (bài học Globe
   Cover: kênh Urdu lọt pool US — vì vậy KHÔNG auto-move).
3. **Bấm chuyển bằng move sẵn có** → lịch sử đi theo kênh.

Đối chiếu V2 (tùy chọn, sau bước 3): so danh sách kênh V2 (đọc từ backup
gương `D:\OUTLIERY-backup` — KHÔNG đụng db sống) với V3 → kênh team thêm
trong 2 ngày V3 đứng im → dán bổ sung vào đúng pool thị trường (resolve tốn
~1 unit/kênh, không đáng kể). SAU CUTOVER: snapshot cuối rồi chạy lại đúng
quy trình 1-2-3 trên dữ liệu mới nhất — vì vậy làm thành TÍNH NĂNG lặp lại
được, không phải script một lần.

## Nghiệm thu còn chờ (user/Owner) — cập nhật vòng 4

1. Vào **V3** (https://outliery.test:9443, KHÔNG phải cổng 8000) → RadarY →
   chọn niche **LIFE IN** trên switcher (tên mới) → tab **Data Pool** →
   **Ctrl+F5** một lần cho chắc.
2. Thấy dải tab: **Chưa phân loại · ~4.9k video** + **＋ Korea · ＋ Spain ·
   ＋ US** (đúng khai báo General). Bấm ＋ US → pool "LIFE IN — US" dựng ngay.
3. Ở tab Chưa phân loại: tích kênh → "Chuyển kênh đã chọn" sang US/Spain/Korea
   (vai Manager/Owner — chuyển CHỈ trong nội bộ ngách). Nhập kênh mới: đứng ở
   tab thị trường rồi dán vào ô Thêm kênh.
4. Các niche khác (Space, Storm…): tạo niche tương ứng ở General › Niches +
   khai thị trường → mở Data Pool của niche đó → banner "Niche này chưa nối
   với General" đã gợi ý sẵn → bấm "Nhận … là ngách này" (pool tự đổi tên
   theo General).
5. SAU CUTOVER: chạy lại việc nối + tách trên snapshot cuối bằng chính UI này.

## Nợ đã thấy khi khảo sát (KHÔNG thuộc mạch này — ghi để khỏi quên)

- `api.py` add_channels/channel_profile/overview_refresh + `niche_report.py`
  còn đọc key từ bảng nội bộ `db.api_keys` (bảng đã tuyên bố NGHỈ ở mạch làm
  gọn 16/08; snapshot còn 19 key cũ nên vẫn chạy). Thuộc mạch migration khóa —
  chờ Owner chạy `scripts/di_tru_khoa_radary.py` rồi rà nốt các điểm đọc này.

- 19/08/2026 — **ĐỒNG BỘ SỐ LIỆU V2 → V3 trước khi user quét** (user yêu cầu;
  kèm phản hồi user "khuyên backup trước mà chia trước" → nhận lỗi LIFE IN chia
  18/08 khi chưa có snapshot, đã ghi memory kỷ luật backup-trước-mặc-định).
  Nguồn: backup gương đêm 18/08 22:59 (`D:\OUTLIERY-backup\HIEN-TAI\1-radary-so-lieu`
  — đúng luật chỉ đọc backup, không đụng db sống hệ thật; integrity ok).
  Snapshot V3 TRƯỚC đồng bộ: `radary-truoc-dong-bo-v2-20260819.db`. Kết quả:
  +619 video mới · 21.498 video cập nhật trường mutable (chỉ khi V2 có tick mới
  hơn — không giẫm lượt quét tay) · +88.436 tick · +64 bucket pool_stats ·
  +4.161 channel_stats · +1.132 channel_snap; 0 kênh mới từ team; 33 kênh
  inactive V3 (gỡ cũ + 4 Nga/Hàn) KHÔNG tái nhập; số liệu mới đổ ĐÚNG pool thị
  trường hiện tại (map kênh theo gia đình ngách). events/kv/board KHÔNG chép
  (sổ cái V2 ở lại V2, board V3 tự dựng lượt quét tới). Volume sau đồng bộ:
  SPACE US 56M v7d · STORM US 23,7M · LIFE IN Spain 3,0M / US 2,5M · TRAVEL US
  5,0M. Script: scratchpad dong_bo_v2_sang_v3.py (idempotent OR-IGNORE — cần
  đồng bộ lại trước cutover thì chạy lại với backup mới).

- 19/08/2026 — **NẠP DANH SÁCH 81 KÊNH LIFE IN của user (từ ảnh) + phân bổ.**
  Snapshot trước nạp: `radary-truoc-nap-81-kenh-lifein-20260819.db`. Check
  trùng: 0 trùng nội bộ; 40/81 ĐÃ CÓ trong LIFE IN (đúng pool từ đợt chia);
  39 nạp mới vào Chưa phân loại (resolve 2 units); 2 ID không resolve (chép
  từ ảnh có thể sai ký tự — chờ user dán text). Quét discover 54 units → chấm
  ngôn ngữ (script thêm nhận diện HÀN — LIFE IN có khai Korea) → chuyển
  +18 US (338 video) · +8 Spain (147 video). KẾT QUẢ LIFE IN: US 63 · Spain
  28 · Korea 0 · Chưa phân loại 20 (= 6 kênh TIẾNG VIỆT — ngách chưa khai
  thị trường VN, chờ user quyết · Globe Cover Urdu (đúng bài học cũ) ·
  còn lại ít/0 video hoặc title không chấm được: b13ed, TRIBE EXPRORER…).
