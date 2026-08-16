# CLAUDE.md — Radary

## Project này là gì

Radary là **radar phát hiện video outlier cho MỌI niche YouTube** — không gắn với ngách nào cụ thể. Đầu vào của mỗi niche là một **pool kênh đối thủ**; radar quét pool đó, xếp hạng video theo VPH (views/giờ) trong cohort tuổi, thăng bậc T1→T4 và push điện thoại (ntfy) đủ sớm cho vòng sản xuất 8 tiếng. Radar chỉ trả lời **"CÓ SÓNG, to cỡ nào"** — thẩm định vì sao nổ và có đánh hay không là việc của user.

- Niche "Life in X" (77 kênh) là **niche đầu tiên / testbed** — nơi spec v3 được backtest và đóng băng. Nó là dữ liệu kiểm chứng cho engine, KHÔNG phải giới hạn của tool.
- **Sản phẩm đích là web/app** (dashboard + quản lý pool kênh theo niche + push). Code phải hướng kiến trúc đó ngay từ đầu, không phải "script trước, web tính sau".

## Kiến trúc đã chốt (user quyết định 07/07/2026)

- **Sản phẩm đích: SaaS nhiều user.** Giai đoạn đầu chạy 1 user, nhưng DB/API thiết kế multi-tenant ngay từ đầu: `org → members → workspace (niche) → channel pool → video/tick → event`. Không đập lại khi thêm auth.
- **Key YouTube BYO theo niche (chốt 11/07/2026 sau sự cố quotaExceeded):** key gán theo từng niche hoặc toàn org, kèm **key DỰ PHÒNG** tự được đôn lên khi key chính 403/hết quota (dự phòng xếp cuối vòng xoay của `scan.API`). Flow chuẩn: tạo dự án → gắn key → mới pool. **BÀI HỌC ĐẮT: quota 10K/ngày của YouTube tính theo DỰ ÁN Google Cloud, không theo key** — key muốn cộng quota phải từ project khác nhau; dán key trùng bị chặn 409; tab Quản trị có nút "kiểm" hỏi thẳng YouTube từng key.
- **Phạm vi ấn định (user chốt 07/07/2026):** chỉ YouTube · chỉ long-form >180s · chỉ trong pool kênh · push = ntfy duy nhất · không mobile app (web responsive). Chi tiết + tính năng theo phase: `docs/roadmap.md`.
- **Hạ tầng (từ 08/07/2026): ĐANG CHẠY PRODUCTION trên VPS Vultr** `root@45.32.107.108` (Docker, Ubuntu 22.04, 1GB). Truy cập: **https://radary.tail5ff5a2.ts.net** — công khai internet qua Tailscale Funnel, đi kèm gia cố bắt buộc (đăng ký chỉ bằng mã mời `RADARY_INVITE_ONLY=1` · rate-limit login 20 lần/5phút · secure cookie). Port 8000 vẫn chỉ bind localhost. Tắt public: `tailscale funnel --https=443 off`. Runbook: `docs/deploy_vps.md`.
- **Phân quyền 3 bậc (user chốt 08/07/2026, đổi tên + siết 23/07/2026):** `owner` (key toàn org + Harvest, LLM, mời/gỡ thành viên, xóa workspace) > `leader` (tên cũ `editor` — alias giữ trong ROLE_RANK, dữ liệu migrate tự động; vận hành pool/config/quét/verdict/Hỏi Radar/AI đọc biểu đồ; **được gắn key cho niche trong phạm vi mình** — mở khóa flow New Niche) > `viewer` (chỉ xem Board/Alerts/Report). **Tab Data Pool · Harvest · +New Niche = leader trở lên** (chặn cả API: GET channels/hồ sơ kênh/harvest đều 403 với viewer). Chặn tại API — UI ẩn nút chỉ là phụ. Vào org bằng mã mời 1-lần/7-ngày. **Phạm vi theo niche (08/07):** thành viên/mã mời gắn được vào đúng 1 niche (`workspace_id` NULL = toàn org); niche ngoài phạm vi → 404 không lộ tồn tại; owner đổi vai + phạm vi TẠI CHỖ trong tab Quản trị.
- **Lớp LLM diễn giải (user chốt 08/07/2026):** BYO key theo org, đa provider (Claude/GLM, adapter urllib trong `radary/llm.py`). 4 chỗ dùng: narrative báo cáo ngách · Nhận định AI báo cáo tuần (thread nền) · Hỏi Radar (Board) · AI đọc biểu đồ (modal chart) — chung trần 30 lượt/người/ngày. Ranh giới CỨNG kế thừa nguyên tắc 5: LLM không sinh số ngoài dữ liệu cung cấp, KHÔNG khuyên "nên đánh/không đánh"; lỗi/thiếu key → mọi thứ chạy như thường, chỉ thiếu phần chữ.
- **Stack: FastAPI + SQLite + React.** Backend Python tái dùng engine đã kiểm chứng; SQLite cho multi-niche (giữ đường migrate PostgreSQL khi SaaS mở rộng); React cho dashboard.
- Engine cron cũ (`daily_radar.py`) trên Mac tiếp tục chạy production cho niche Life in X song song — **không được làm gián đoạn nó** cho đến khi user nghiệm thu bản VPS và tự tắt cron.

## Bản đồ project — nguồn sự thật

| File | Vai trò |
|---|---|
| `docs/radar_spec.md` | **SPEC ĐÓNG BĂNG v3** — luật nghiệp vụ lõi (viết trên niche testbed "Life in X"; engine tổng quát hóa nhưng hành vi mặc định phải khớp spec). Muốn đổi hành vi → sửa spec trước, code sau |
| `docs/niche_analytics.md` | LÝ THUYẾT ĐO LƯỜNG — 7 tiêu chí, phân tầng tín hiệu L0-L3. Vì sao đo, không phải chạy thế nào |
| `docs/weekly_report.md` | Đặc tả radar tuần (thực thi, backtest, roadmap L0/L1) |
| `docs/roadmap.md` | Phạm vi đã ấn định + tính năng đã duyệt theo phase (1-7) + tương lai xa + danh sách cố-tình-không-làm. **Mọi quyết định 08/07/2026 (báo cáo, phân quyền, LLM, gỡ kênh) ghi vết ở đây** |
| `CHANGELOG.md` | Mô tả các đợt update chính cho NGƯỜI ĐỌC (V1 nền tảng · V2 22-24/07…) — mỗi đợt update đáng kể phải thêm mục vào đây (user yêu cầu 24/07/2026); chi tiết quyết định vẫn ở roadmap |
| `docs/niche_report_spec.md` | SPEC báo cáo ngách tự sinh (hạng mục 3.1-3.10, phân công Code vs LLM, nguyên tắc chất lượng) — nguồn cho Phase 6/7 |
| `spec_harvest_1.md` + `radary_methodology.md` | **SPEC HARVEST ĐÓNG BĂNG 23/07/2026** (2 vòng phản biện ghi §10) + phương pháp luận đã kiểm chứng bằng dữ liệu thật (3 công cụ: phân rã/snowball/audit; 4 cửa sinh ứng viên — chỉ cửa 3 mạnh; 5 thiên vị comment). Đổi hành vi Harvest → sửa spec trước |
| `daily_radar.py` | Engine PRODUCTION đang chạy (cron 30 phút) — giữ nguyên đến khi Phase 2 nghiệm thu xong |
| `radary/` | **App chính (Phase 1-7 + mở rộng ✅)** — package đa workspace trên SQLite: `db` (schema + migration nhẹ; `api_keys` có phạm vi niche/dự phòng, `members`/`invites` có phạm vi, `channels.favorite`, `channel_snap` snapshot hồ sơ kênh 1 dòng/kênh/ngày GIỮ VĨNH VIỄN) · `core` (luật thuần, đổi phải qua spec + chạy `verify_phase1.py`) · `scan` (API/jobs/packaging; xoay key khi 403 → dự phòng tự thay; `pool_pulse` nén nhịp pool + kênh thành bucket 6h **căn giờ VN 00-06-12-18, phân bổ tuyến tính giữa 2 tick** vào `pool_stats`/`channel_stats` GIỮ VĨNH VIỄN — 14 ngày gần idempotent, cũ hơn hóa thạch; `snap_channels` chụp subs/viewCount trọn đời kênh 1 lần/ngày ~2 units/pool, lỗi chỉ làm thiếu Metrics hôm đó KHÔNG giết chu kỳ) · `report` (board md+JSON · tab Báo cáo · **báo cáo tuần 7 phần**: nhịp so tuần trước/theo ngày/sổ cái/kênh tạo sóng/mang sang tuần mới/ứng viên chớm nở/hiệu chỉnh + 3 đồ thị SVG tự vẽ nhúng data-URI + Nhận định AI chèn nền) · `series` (chart sóng T2+: VPH + views tích lũy, dải tiền lệ P25-75/P50/P75/P90 cho CẢ HAI) · `api` (FastAPI, auth + phân quyền + phạm vi; scheduler cô lập lỗi theo workspace; UI no-cache; `/metrics` tiles Board — % thiếu lịch sử trả None, UI hiện '—' không bịa) · `alertsview` (tầng TRÌNH BÀY tab Cảnh báo — CHỈ ĐỌC, gom sự kiện theo ĐƠN VỊ: tier→sóng/video (Đang sống/Đã lắng, verdict theo video qua event T2+ đại diện), retitle/rethumb→kênh, dead/purge/pool/config→phẳng, ''→trộn thời gian; `events` vẫn append-only) · `auth` (scrypt + session + ROLE_RANK + require_org_wide) · `crypto` (Fernet — khóa chủ `data/secret.key`, MẤT = MẤT KEY, backup kèm) · `niche/` (pipeline Niche Report vendored — OX v3/LIFT/bets, thay đổi duy nhất requests→urllib) · `niche_report` (báo cáo ngách tự sinh, chạy nền) · `llm` (Claude/GLM: narrative, Nhận định tuần, Hỏi Radar, đọc biểu đồ — cấm sinh số/cấm khuyên) · `heatmap` (giờ ĐĂNG × thứ từ pub_ts có sẵn — chỉ đọc, 0 quota, giờ VN/UTC, lọc kênh, `peak` cho tile Most posted hours) · `scheduler` · `runner` · `migrate_legacy` · **`harvest/`** (tìm & thẩm định kênh — READ-ONLY tuyệt đối với bảng sống, chỉ ghi 3 bảng `harvest_*`; kho key riêng `api_keys.harvest=1` radar không đụng; `fingerprint` thuần stdlib (function-word EN/ES/PT, centroid df, voc) · `decompose` cây 2 tầng · `snowball` centroid đóng băng + hội tụ ≤1/vòng + trần 6 vòng · `audience` co-occurrence chỉ xếp hạng · `runner` job nền 1-job/org, checkpoint resumable, PAUSE khi hết quota/budget, **job ERROR cũng thử-lại-được từ checkpoint** (sự cố 24/07/2026: job kẹt ERROR vĩnh viễn dù code đã vá — nút "▶ Thử lại từ chỗ dừng"); ngưỡng trục MẠNH luật kép trong `runner.STRONG` — TODO user hiệu chỉnh) |
| `Dockerfile` + `docker-compose.yml` | Đóng gói production — **đang chạy thật trên VPS**. Volume `./data`, port chỉ bind 127.0.0.1; compose bật `RADARY_SECURE_COOKIE=1` + `RADARY_INVITE_ONLY=1` |
| `deploy/` + `docs/deploy_vps.md` | VPS đang chạy: `push.sh` (Mac → VPS; **từ 08/07 KHÔNG đồng bộ `data/` — DB sống ở VPS, đè là MẤT dữ liệu**) + `vps_setup.sh` + runbook. Cập nhật code = `bash deploy/push.sh` rồi trên VPS `cd /opt/radary && docker compose up -d --build`. §8: Funnel public + điều kiện gia cố |
| `server.py` | Khởi động app (bản dev local; bản THẬT chạy trong Docker trên VPS): `.venv/bin/python server.py` → http://127.0.0.1:8000. Env: `PORT`, `RADARY_SCHEDULER=0`, `RADAR_BUDGET`, `RADARY_INVITE_ONLY` |
| `web/` | Dashboard — Preact + htm vendored, KHÔNG build step: `index.html` + `app.js` (nhãn tab user chốt 23/07/2026: Board · Alerts · Report · Data Pool · **Harvest** [3 bước: nhập-chạy-nền-ngay → Phân loại Workspace (✕ kênh khỏi nháp) → Report gọn + ⬇ tải full .md; stepper xanh theo tiến độ; khóa hash giữ nguyên tiếng Anh cũ] · Tuning (Cài đặt) · Setting (Quản trị, thêm mục Key Harvest dán loạt) · +New Niche — 8 màn hình: Board [Nhịp pool 2 đồ thị sóng views/VPH TB range W/M/Y+custom → khối **Metrics kiểu vidIQ** (user duyệt mockup v3 23/07/2026, THAY bảng Top kênh/ngày + panel heatmap rời: nhãn-trên-số-dưới tiếng Anh, hàng 1 = 4 tile hiệu suất Total views/Views gained 7d/Subscribers/Top outlier + pill % xanh-đỏ, hàng 2 = 6 tile hồ sơ gồm Current avg VPH/Surging/Most posted hours; dropdown phạm vi pool⇄kênh đổi CẢ số lẫn heatmap giờ đăng nằm trong cùng panel — hover ô = popup kênh·số video, 📖 đọc-hộ; % cần snapshot/lịch sử chưa đủ → '—' không bịa) → Hỏi Radar → cohort; VPD kỳ vọng (video <24h) mang dấu `~`; ⭐ kênh yêu thích, Xem-tất-cả cohort] · Alerts [**gom theo đơn vị, user duyệt mockup 24/07/2026** — 7 sub-tab (BỎ "Tất cả" — chức năng tab nào ở tab đó, user chốt 24/07), mặc định mở Thăng/hạ bậc; Thăng/hạ bậc = thẻ SÓNG/video (sparkline quỹ đạo bậc thay chuỗi mũi tên, Đang sống/Đã lắng, 1 nút thẩm định/video, bung sự kiện gốc); Đổi title/thumbnail = gom theo KÊNH (số lần + số video); Xóa/Ẩn·Kênh ẩn loạt·Pool·Config = danh sách phẳng. Sửa lỗi UX: 1 video từng lặp 24 dòng → 1 thẻ] · Báo cáo [ghim tổng quan, đồ thị, 🖨 Xuất PDF qua hộp thoại in] · Pool [nút ⭐ + ⬇ tải danh sách .csv client-side (BOM UTF-8, cột URL dán lại được vào Radary/Harvest)] · Cài đặt [key riêng của niche: 1 chính + N dự phòng] · Quản trị (owner) [thành viên+phạm vi, mã mời, key nhóm theo dự án + nút kiểm, LLM] · +Niche mới [flow tạo→key→pool]) + `vendor/`. **Trạng thái UI lưu URL hash** (`#tab=…&ws=…&r=…`) — F5 đứng yên, link chia sẻ được. Server gắn no-cache cho UI. Mọi chart (LineChart trên web + 3 SVG báo cáo tuần trong `report.py`) theo MỘT ngôn ngữ thị giác chốt 22/07/2026 — kiểu uPlot/Tremor: gradient mờ dần, crosshair, grid chấm mảnh, KHÔNG thêm thư viện chart. Sửa xong kiểm tra `node --check web/app.js`. **LUẬT htm (trả giá 24/07/2026):** không bao giờ viết `<` thô trong text của template htm — `<7 ngày` bị parse thành TAG `<7>` → `createElement` ném lỗi → sập cả tab khi render (node --check KHÔNG bắt được vì là lỗi runtime); viết "dưới 7" hoặc `&lt;`; verify_phase3 có chốt chặn tĩnh `<`+số |
| `data/` | Bản LOCAL chỉ để dev/verify. **DB SỐNG nằm trên VPS `/opt/radary/data`** (radary.db chmod 600 CÓ API key + secret.key + thumbs + reports + niche/{ws} work-dir) — backup = folder đó + Vultr auto-backup |
| `verify_phase{1,2,3,4}.py` | Nghiệm thu: parity luật · API E2E (§4b Cảnh báo gom-đơn-vị) · dashboard+onboarding+verdict-theo-video · auth+mã hóa+phân quyền+mã mời+báo cáo+LLM+gia cố internet — chạy lại CẢ BỐN sau mọi thay đổi `core/report/api/db/auth/crypto/llm/niche_report/harvest/alertsview` (bài 4 chạy bằng `.venv/bin/python`; `alertsview` có self-test `python -m radary.alertsview`) |
| `verify_harvest.py` | Nghiệm thu Harvest OFFLINE (Fake API, 0 quota): 18 case — hội tụ, PAUSE/resume checkpoint, mọi-key-403, kho key trống, READ-ONLY bảng sống, report idempotent. Case vàng SỐNG (tốn ~10-15K units) chạy tay qua UI khi user ra lệnh |
| `requirements.txt` + `.venv/` | Dependency tầng web (fastapi, uvicorn) — engine lõi vẫn thuần stdlib |
| `radar_state/` | **DỮ LIỆU SỐNG** production (state JSON, API key trong `competitors.txt`) — không xóa, không commit key |
| `radar_reports/` | Output production: board, alerts.log, báo cáo tuần |
| `legacy/weekly_radar.py` | Bản tuần cũ — chỉ tham khảo, không phát triển tiếp |

Hai file docs phân vai rõ: `niche_analytics.md` = ĐO GÌ/VÌ SAO, `weekly_report.md` + `radar_spec.md` = CHẠY THẾ NÀO. Không lặp nội dung chéo file.

## Nguyên tắc 1 — Spec trước, code sau (Think Before Coding)

Project này vận hành theo chu trình đã chứng minh hiệu quả: **đề xuất → vòng lặp phản biện → spec đóng băng → mới code**. Spec v3 là kết quả của 5+ vòng phản biện có ghi vết. Đừng phá chu trình đó bằng cách code thẳng từ một ý tưởng chưa qua phản biện.

- Nêu giả định ra thành lời. Không chắc thì hỏi, không tự chọn ngầm một cách hiểu.
- Yêu cầu mơ hồ có nhiều cách hiểu → trình bày các cách hiểu, để user chọn.
- Muốn đổi hành vi radar: sửa `radar_spec.md` trước (kèm lý do vào mục "Loop phản biện"), code sau. Spec và code lệch nhau là bug.
- Mỗi quyết định thiết kế quan trọng phải ghi vết vào spec như các vòng phản biện cũ — để 3 tháng sau còn truy được "vì sao chọn thế này".
- Thấy user đang tự làm khó (giải pháp phức tạp hơn cần thiết) → nói ra, kèm phương án đơn giản hơn.

## Nguyên tắc 2 — Đơn giản trước (Simplicity First)

Bài học đã trả giá trong chính project này: đề xuất "danh sách lão thành" phức tạp của Claude đã bị thay bằng "bảng VPD-cao-mọi-tuổi" đơn giản hơn của user — và bản đơn giản đúng hơn. Mã tối thiểu giải đúng bài toán được nêu, không có gì suy đoán.

- **Lõi phát hiện (`core.py`) thuần stdlib** — không dependency nào chạm vào luật radar. Tầng app dùng đúng 3 gói đã duyệt (fastapi, uvicorn, cryptography) trong `.venv`; thêm gói mới phải có lệnh user. `daily_radar.py` cũ vẫn copy-là-chạy.
- **State = JSON file, không DB.** Chỉ nâng cấp storage khi dữ liệu thực sự vượt sức JSON (chưa xảy ra: tick thô giữ 14 ngày rồi nén nến ngày).
- Không thêm tính năng, config, tầng trừu tượng, hay xử lý lỗi cho kịch bản không thể xảy ra khi chưa được yêu cầu.
- Logic đặc biệt là nợ: ưu tiên để chỉ số tự nói (ví dụ: không có luật riêng cho video già — VPD cao thì tự hiện lên bảng).
- Trước khi nộp: tự hỏi "một kỹ sư senior có bảo cái này overcomplicated không?"

## Nguyên tắc 3 — Thay đổi phẫu thuật, tôn trọng dữ liệu sống (Surgical Changes)

Radar chạy production 24/7 ở HAI nơi: cron cũ trên Mac (`radar_state/`) và app mới trên VPS (`/opt/radary/data` — DB, secret.key). Cả hai chứa lịch sử tick không tái tạo được (baseline t0, dedup push, hysteresis). Một lần ghi ẩu là mất dữ liệu thật và push trùng ra điện thoại thật. Chạm vào DB production trên VPS ngoài đường API phải có lệnh tường minh của user từng lần.

- Chỉ chạm vào phần buộc phải chạm. Không refactor code đang chạy tốt nhân tiện lúc sửa việc khác.
- Mọi lệnh phải **an toàn khi chạy lại** (idempotent): `init` không được xóa dữ liệu cũ; ghi file qua tmp + `os.replace` (đã có sẵn `jsave` — dùng nó).
- Không bao giờ xóa/reset file trong `radar_state/` khi chưa hỏi user. Video bị YouTube gỡ đánh dấu `dead` chứ không xóa — biến mất cũng là tín hiệu. **Ngoại lệ duy nhất (user chốt 08/07/2026): user chủ động "gỡ kênh" khỏi pool = xóa video/tick/packaging của kênh đó** (dọn pool bẩn) — nhưng `events` là sổ cái append-only, KHÔNG BAO GIỜ xóa, và mọi nút gỡ/xóa trên UI đều phải có bước xác nhận trước.
- Giữ tương thích state cũ khi đổi schema JSON: đọc được state hiện có hoặc migrate rõ ràng, không bắt user chạy lại từ đầu.
- `competitors.txt` chứa API key, `config.json` chứa ntfy topic bí mật — không in ra log/report, không commit.
- Thấy dead code không liên quan: nhắc, đừng tự xóa. Chỉ dọn import/biến do chính thay đổi của mình làm thừa.

## Nguyên tắc 4 — Mục tiêu kiểm chứng được, ngưỡng theo dữ liệu (Goal-Driven Execution)

Project này đã bác bỏ luật ngây thơ bằng backtest 30 tháng (precision 5% → bị loại) và chốt luật kép bằng số đo. Chuẩn đó áp dụng cho mọi thay đổi: định nghĩa "thế nào là đúng" trước khi làm, và kiểm bằng dữ liệu chứ không bằng cảm giác.

- Trước khi code một thay đổi: nêu tiêu chí thành công kiểm chứng được ("chạy `status` phải in X", "case Cape Verde phải kêu trong 72h").
- **Bộ case vàng để đối chứng hồi quy** (từ niche testbed Life in X): Cape Verde (T4, 0 ngày trễ) · Yakutsk (lọt lưới OX → sinh ALARM-ABS) · Lesotho (nổ sau tin 3 ngày) · Euro 2024 (đối chứng ÂM — không được kêu). Đổi luật phát hiện → kiểm lại bộ này. Niche mới nên có bộ case vàng riêng sau 2 tuần chạy sống.
- **Không chỉnh ngưỡng theo cảm giác.** Sàn T1-T4 chỉnh theo phân phối VPH thực (P50/P90) từ báo cáo tuần, chu kỳ 2 tuần đầu rồi hàng tháng.
- Kế thừa TC7 (chống tự lừa): mỗi kết luận phân tích kèm dòng *"sai trong trường hợp nào"*. Kết quả xấu báo thẳng kèm số liệu, không làm mềm.
- Test với `RADAR_BUDGET=25` khi chạy sandbox; không test bằng cách bắn push thật (tắt `ntfy_enabled` hoặc dùng topic test).

## Nguyên tắc 5 — Phân vai người–máy cố định

Đây là quyết định thiết kế của user, không phải thiếu sót cần bổ sung: **radar báo sóng, người thẩm định sóng.**

- Không thêm tính năng "tự đánh giá nên đánh hay không", chấm điểm packaging, hay auto-quyết-định sản xuất — việc đó thuộc pipeline khác (thumbnail/Double Down) và thuộc user.
- **Lớp LLM (Phase 7) tuân thủ nguyên tắc này bằng ranh giới cứng trong system prompt** (`radary/llm.py`): chỉ DIỄN GIẢI số liệu có sẵn, không sinh số, bị hỏi "nên đánh không" phải từ chối và chỉ nêu dữ kiện. Mọi thay đổi prompt LLM phải giữ nguyên ranh giới này.
- Push phải đắt giá: dedup 1 push/video/bậc, trần 5 T2/ngày. Push sai làm mất lòng tin nhanh hơn mọi thứ — mọi thay đổi làm tăng lượng push phải qua phản biện.
- Output cho người đọc trong ≤2 phút: board 1 trang, alert nào cũng đủ căn cứ + hành động + link.

## Nguyên tắc 6 — Niche-agnostic + kiến trúc web/app ngay từ đầu

Tool phục vụ mọi ngách và đích đến là web/app — hai ràng buộc này định hình code từ dòng đầu tiên:

- **Engine không hardcode giả định niche nào.** Ngưỡng T1-T4, pool kênh, bộ lọc (vd long-form >180s), nhịp quét — tất cả là config theo niche. Số liệu của "Life in X" chỉ là giá trị mặc định/ví dụ.
- **Mỗi niche = một workspace độc lập:** pool kênh + config + state + report riêng. Thêm niche mới = tạo workspace, không sửa code.
- **Tách 3 tầng rõ:** thu thập/phát hiện (engine) — state — trình bày (dashboard/board/push). Logic phát hiện không được import/lệ thuộc code render.
- **State là hợp đồng dữ liệu:** tầng web đọc đúng state engine ghi. Đặt tên trường rõ nghĩa, kèm epoch timestamp, đừng nhét dữ liệu vào chuỗi Markdown đã format.
- Tầng mới trong roadmap (L1 Wikipedia Pageviews, L0 lịch sự kiện — xem `weekly_report.md` §5) build thành module/plug-in cạnh engine, không đan vào vòng quét chính.
- Engine giữ vai backend ghi state; web/app là tầng đọc + điều khiển (quản lý pool, chỉnh config, xem board) + push. Không viết lại engine để phục vụ UI.

## Quy ước chung

- **Ngôn ngữ:** docs, báo cáo, push, comment code — tiếng Việt (giữ thuật ngữ kỹ thuật tiếng Anh: VPH, cohort, push...).
- **Timezone:** mọi ranh giới ngày và lịch báo cáo theo `Asia/Ho_Chi_Minh`; snapshot lưu epoch time.
- **Quota API:** quota tính theo DỰ ÁN Google Cloud (10K/project/ngày, hồi 14:00 giờ VN) — hệ thống thực dùng ~2.5-3.5K units/ngày cho 5 pool. Thêm loại quét mới phải ước tính quota trước (tham chiếu: refresh báo cáo ngách ~1 unit/50 video + 1/kênh — pool 180 kênh ≈ 2-3K units/lần). Sự cố 403: xem nút "kiểm" key trong Quản trị; scheduler tự cô lập pool lỗi, không chặn pool khác.
- Job lớn chia nhỏ resumable (in `PAUSE — chạy lại để tiếp`), tôn trọng `RADAR_BUDGET`.
- **Chu trình deploy chuẩn:** sửa code trên Mac → chạy đủ 4 bài verify → `bash deploy/push.sh` → trên VPS `cd /opt/radary && docker compose up -d --build` → smoke test health + tính năng mới qua https://radary.tail5ff5a2.ts.net. Không sửa code trực tiếp trên VPS.

## Sự cố production đã trả giá — đọc trước khi sửa `scan`/key

1. **`KeyError: 'duration'` làm pool Space đứng 2.7h (12/07/2026):** video **livestream/premiere chưa kết thúc** được YouTube trả về KHÔNG có trường `duration` → đọc thẳng `it['contentDetails']['duration']` làm crash cả chu kỳ quét, lặp mỗi phút, heartbeat đứng, "Quét ngay" 500 — 1 video treo lịch premiere giết cả pool. **LUẬT rút ra: mọi trường trong response YouTube API coi như CÓ THỂ THIẾU — luôn `.get()` phòng thủ**; giá trị chưa biết để `None` cho lần quét sau điền, không đoán. Triệu chứng nhận diện: key còn quota nhưng cycles không ghi dòng mới + traceback lặp trong `docker compose logs`.
2. **quotaExceeded diện rộng (10-11/07/2026):** quota tính theo DỰ ÁN Google Cloud, không theo key — chi tiết ở mục "Key YouTube BYO" bên trên. Chẩn đoán bằng nút "kiểm" key trong Quản trị; mức tiêu thực của hệ ~2.5-3.5K units/ngày.
3. **Dán nhầm key cũ tưởng key mới (11/07/2026):** user dán lại key đã cạn → tưởng hệ hỏng. Đã chặn 409 khi dán key trùng — đừng gỡ hàng rào này.
4. **Harvest chết bởi `commentThreads` 400 (23/07/2026, leader chạy job đầu tiên):** tham số `allThreadsRelatedToChannelId` đã bị YouTube bỏ → 400 Bad Request → job ERROR. Sửa: đọc comment theo TỪNG VIDEO (`videoId`, lấy từ video đã đo trong `measure_channel`), và **mọi lỗi comment chỉ được làm thiếu dữ liệu khán giả, không được giết job** (Tầng 2 chỉ xếp hạng — try/except nuốt êm trong `audience.channel_authors`). LUẬT chung: endpoint/tham số YouTube có thể bị khai tử bất kỳ lúc nào — tài liệu cũ không tin được, phải có case verify mô phỏng lỗi cho mọi lời gọi phụ trợ.

## Lỗi quy trình Claude đã mắc — đọc để không lặp lại

1. **Code trước khi hỏi dù yêu cầu mơ hồ (23/07/2026):** user nói "muốn biết thêm mốc giờ" trên đồ thị Nhịp pool — Claude tự chọn một cách hiểu (thêm giờ vào tooltip), code + deploy luôn, và hiểu SAI ý (user muốn khung giờ THỰC theo giờ VN + số đo thực). User phải nhắc "vi phạm nguyên tắc, hỏi trước khi code". **LUẬT: yêu cầu có >1 cách hiểu → trình bày các cách hiểu cho user chọn TRƯỚC (nguyên tắc 1), kể cả khi sửa chỉ vài dòng.** Với thay đổi hiển thị số liệu, dựng bản xem trước bằng dữ liệu thật để user duyệt trước khi chạm code production đã chứng minh hiệu quả.
2. **Khóa phiên gần 20 phút bằng lệnh chờ (23/07/2026):** để xác nhận pool quét xong, Claude nhúng `sleep 420` vào lệnh ssh → vượt trần timeout của tool, lệnh rơi xuống nền, rồi tiếp tục poll chờ thêm ~11 phút — user bị treo, không dừng được, trong khi truy vấn tức thời chỉ mất vài giây và kết quả vốn đã đạt. **LUẬT: không `sleep` dài trong lệnh chờ xác nhận — kiểm ngay; chưa đạt thì BÁO trạng thái trung thực ("sẽ tự xong trong nhịp quét tới") và trả quyền cho user, kiểm lại lượt sau.**
3. **Hiển thị số kỳ vọng như số thật (phát hiện 23/07/2026, user bắt lỗi):** VPD của video <24h tuổi = VPH×24 (kỳ vọng) nhưng bảng không đánh dấu — user tưởng toàn bộ chỉ số là tam suất. Đã sửa: cờ `est_vpd` + dấu `~`. **LUẬT: mọi con số ước lượng/kỳ vọng đưa lên UI phải mang dấu hiệu phân biệt với số đo thật (`~`, ghi chú) — trung thực dữ liệu là nguyên tắc sống còn của radar.**
