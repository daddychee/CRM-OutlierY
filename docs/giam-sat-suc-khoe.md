# Sổ chủ đề — GIÁM SÁT SỨC KHỎE HỆ (tab Applications thành trạm điều hành)

> Mở sổ 31/08/2026. Mục tiêu Owner đặt: tab App contracts không chỉ báo app
> sống/chết mà check sức khỏe TỪNG MODULE trong từng app + báo ngay khi tính
> năng chạy sai logic. Đã khảo sát open source trước khi code (kết luận: Uptime
> Kuma / Gatus / Healthchecks / GlitchTip chỉ lo tầng probe/alert; tầng "module
> nào đang hỏng" bắt buộc app tự khai — nên MƯỢN 3 pattern (deep health,
> dead-man's switch, condition assertion) và tự xây phần vỏ trong nền V3).
> Kỷ luật mạch này: TEST TRƯỚC (đỏ) → code cho xanh → cả suite → commit riêng.

## Kiến trúc chốt

- **Hợp đồng sức khỏe 2 tầng** trong apps.json:
  - `health` (bắt buộc, có sẵn) = liveness — sống/chết, gateway ping 3s.
  - `suc_khoe` (TÙY CHỌN, mới) = endpoint sức khỏe SÂU theo khuôn
    `nen/common/suc_khoe.py`: `{app, phien_ban, trang_thai, mo_dun:[{ten,
    trang_thai: ok|canh_bao|loi, chi_tiet}]}`. App không khai → hành vi cũ
    y nguyên (không luật mới).
- **Van chống bịa cho giám sát**: check nổ exception là DỮ LIỆU ('loi' + lý
  do), endpoint sức khỏe không bao giờ 500; khai `suc_khoe` mà không trả lời
  được → gateway ghi 'loi' (khai là phải giữ lời); MOCK → 'canh_bao' nói thẳng.
- **Trạm đo lỗi ở proxy** (`nen/common/dem_loi.py` + móc trong
  `nen/common/proxy.py`): mọi request app đi qua chuyen_tiep → 5xx của app /
  cổng chết (502) / timeout (504, trước đây nổ thô thành 500 không vết) đều
  ghi nhận theo CỔNG, cửa sổ trượt 5 phút; vết bền JSON-lines qua nhat_ky
  (app=gateway, hanh_dong=loi_app, trần 60 dòng/cửa sổ chống bão). Bộ đếm
  trong RAM (1 worker, restart về 0 — giới hạn đã biết, khuôn _TAC_VU).
- Tab `/general/applications`: cột **Modules** (xổ chi tiết từng module) +
  cột **Errors 5′** (N lỗi / M request + lỗi gần nhất giờ·status·đường dẫn).
  Template guard `is defined` — bài học Jinja auto-reload 19/08.

## Nhật ký

- **31/08/2026 — B1+B2+B3 xong, test-first từng bước** (repo cha 73a690a B1 ·
  a1063b7 B2 · f049422 B3; plannery repo lồng 4aeab76). Baseline trước khi làm:
  237 pass / 1 fail (test_content_ultimate ghim hợp đồng — của mạch OUTLINE
  30-31/08, không đụng). Sau: root 253 pass / 1 fail đó; app ai-agent 312 pass.
  - B1: khuôn suc_khoe + app-mau làm mẫu `/api/suc-khoe` + gateway _do_dich_vu
    đọc tầng sâu + cột Modules. Điều tra health lệch: content-ultimate /
    niche-research / seo-optimize khai `/api/health` ĐỀU SỐNG THẬT (agent grep
    không thấy vì layout khác — probe runtime mới là sự thật); plannery +
    rendery mượn `/api/me` (endpoint auth) làm health → plannery đã có /health
    thật (commit ở repo lồng) + apps.json đổi; RENDERY CÒN NỢ (code ở
    F:/RenderY repo riêng, app có job dựng nền — không sửa/restart bừa).
  - B2: dem_loi + móc proxy + cột Errors 5′ (7 test: cửa sổ trượt, vết bền,
    trần chống bão, 5xx/502/504 qua proxy thật, tab render).
  - B3 exemplar ai-agent: `/api/suc-khoe` module kho-vector = lưới sự cố 31/07
    (kho Qdrant RỖNG 3 ngày, hỏi–đáp chết lặng lẽ) trồi lên hợp đồng — catalog
    có tài liệu + kho 0 point → loi kèm chỉ đường nap_lai_kho.py; không gọi
    LLM trong health.
  - Phiên song song: mạch két API-keys (main.py/ket.py/nen_api_keys.html) đang
    treo uncommitted → commit bằng phẫu thuật index (dựng nội dung index =
    HEAD + đúng vùng sửa của mạch này, hash-object + update-index), không quét
    hunk của mạch két. Bẫy gặp: anchor nhiều dòng chết vì CRLF — anchor 1 dòng.
  - DEPLOY CHỜ TAY OWNER: classifier chặn Stop-Process — cần dừng 3 tiến trình
    theo cổng (9000 gateway, 9116 plannery, 9101 ai-agent) rồi
    `schtasks /run /tn OUTLIERY-V3` (start-all tự bỏ qua app còn sống). Máy
    reboot 9:00 hằng ngày cũng tự ăn bản mới nếu không restart tay.

- **31/08/2026 (tối) — DEPLOY + PHÁT HIỆN THẬT ĐẦU TIÊN của tab giám sát.**
  Restart gateway/plannery/ai-agent (dừng theo cổng, Owner duyệt; schtasks
  OUTLIERY-V3 dựng lại) — nghiệm thu sống: 9000 lên, plannery /health 200,
  ai-agent /api/suc-khoe 200. Module kho-vector lập tức báo **canh_bao:
  ai-agent đang chạy MOCK_MODE trên hệ thật** — start-all.ps1 KHÔNG đặt
  MOCK_MODE (default trong vector_client.py:203 là true), trong khi qdrant-test
  :6343 vẫn được start-all dựng và kho_v1 có **157 point thật** (dense 1024 +
  sparse, status green). Nghĩa là hỏi–đáp V3 từ cutover 22/08 nhiều khả năng
  trả từ KHO MẪU. Đây đúng loại "chạy sai logic lặng lẽ" mà Owner đặt hàng tab
  này bắt. CHỜ OWNER QUYẾT: đặt `$env:MOCK_MODE='false'` (+ QDRANT_URL nếu
  cần) trong khối ai-agent của start-all.ps1 rồi restart ai-agent — không tự
  đổi vì đụng hành vi hỏi–đáp đang chạy (có thể phiên khác đang lo mạch nạp kho).

- **31/08/2026 (khuya) — FIX MOCK LẶNG LẼ, hỏi–đáp về kho thật** (commit
  c2512b7). Owner chốt là sót di trú → sửa theo tiền lệ 1161072 (default trong
  CODE): vector_client MOCK_MODE default false + QDRANT_URL default :6343
  (:6333 là V2 đã tắt); test ghim default bằng module giả (không đụng kho thật),
  suite app 314 pass. BẪY GỠ KÈM: (a) KHÔNG set $env:MOCK_MODE global trong
  start-all — data-analytics cũng đọc biến này (LLM diễn giải), set global là
  lây; (b) tác vụ SYSTEM có Temp riêng C:\Windows\Temp KHÔNG có model
  fastembed (cache thật nằm Temp của Administrator — họ bẫy HF_HOME SpeakY
  31/07) → copy 6.8GB về data/fastembed_cache + start-all set
  FASTEMBED_CACHE_PATH. Restart ai-agent: lên sau ~30s nạp model, suc-khoe
  chuyển **ok "157 point / 19 tài liệu"**; nghiệm thu search read-only:
  "cách nuôi kênh" → KD-2026-71369B (ngâm kênh) + KD-2026-1814CB (GA) đúng
  nguồn. Vòng khép: tab giám sát bắt bệnh → sửa → chính tab xác nhận khỏi.

- **31/08/2026 (khuya, tiếp) — B4 + B5 XONG, deploy sống** (commit ecde652
  llm-writer · f4ccc40 B4 · 854d1ee B5; root 268 pass / 1 fail baseline, app
  ai-agent 316 pass). (a) DA KHÔNG cùng bệnh mock — dien_giai nạp cấu hình từ
  KÉT qua gateway, mock chỉ là fallback két trống; NHƯNG két đang TRỐNG vai
  writer cho CẢ ai-agent lẫn DA (critic ai-agent có glm-5) → hỏi–đáp writer
  đang mock. Thêm module `llm-writer` vào suc-khoe ai-agent: tab tự soi, kèm
  lời chỉ đường điền két — CHỜ OWNER điền vai writer (General → API keys).
  (b) B4 heartbeat: nen/common/nhip_viec.py + luật nen/rules/nhip_viec.json
  (start-all 90' + backup-dem 26h) + POST /api/nhip-viec/<ma> chỉ loopback +
  khối Scheduled jobs trên tab; ping đã nối cuối start-all.ps1 + backup.ps1
  (try/catch — gateway chết không hỏng job). Nghiệm thu end-to-end: lần
  restart deploy chính nó ping nhịp start-all đầu tiên (22:27:26).
  (c) B5 vòng giám sát nền: giam_sat.vong trong event loop gateway (chu kỳ
  GIAM_SAT_CHU_KY 60s, ngủ-trước-đo-sau, bất tử), so_sanh() HÀM THUẦN
  edge-trigger: chết 2 chu kỳ mới báo (chống flap) / module loi báo một lần /
  nhịp trễ báo một lần / hồi phục báo lại; phát = sổ sự cố bền
  data/logs/giam-sat TRƯỚC + ntfy sau (canh_bao.py stdlib, khuôn radary).
  CHỜ OWNER bật push: bỏ comment GIAM_SAT_NTFY_TOPIC trong start-all (đổi
  topic khó đoán — ntfy.sh công khai theo topic) + subscribe trên điện thoại.

- **31/08/2026 (đêm) — "TIẾP TOÀN BỘ": suc_khoe phủ 9/13 app + B6 canary +
  fix nguồn KPI** (repo cha tới sau b18b6b6…; radary 1f971f4, plannery b630494;
  root 269 pass / 1 fail baseline outline; to-chuc thêm 1 fail test_finance
  baseline mạch Finance). Đã khai suc_khoe: ai-agent, radary, to-chuc,
  video-review, plannery, tasky, thumby, rendery, app-mau — mỗi app module
  theo bệnh thật: radary du-lieu (0 workspace = bẫy RADARY_DATA_DIR 22/08) +
  quet (scheduler/tick cuối >26h); to-chuc kpi-nguon; video-review nas +
  ffprobe (tự vàng khi C:\OutlierY bị xóa ~22/09); tasky nas-goc; thumby
  radary-db (chết chỉ canh_bao — mô phỏng vẫn chạy); plannery plan-json (repo
  lồng, KHÔNG import nen.* — khuôn là HỢP ĐỒNG JSON); rendery /health thật +
  hang-doi + nas (F:/RenderY không git — kiểm 0 job running trước khi đụng).
  B6 canary search ai-agent: search câu phổ quát thật, 0 kết quả → loi (bắt
  tầng truy xuất lệch dù health khác xanh), cache 10'. Restart 8 app — nghiệm
  thu sống 8/8, deep health trả thật (radary 26 ws/33k video tick 0.0h;
  plannery 8 người/6 dự án _rev 1123; rendery 0 dựng/3 xong/3 lỗi).
  **PHÁT HIỆN THẬT #3 và vòng khép lần 3**: to-chuc báo loi "nguồn KPI ĐÃ nối
  mà mất" — default main.py trỏ hộp thư data/to-chuc/nguon/ không tồn tại
  (chủ đích thời V2-song-song); cutover xong → trỏ THẲNG data/plannery/
  plan.json + data/content-ultimate/admin/history.jsonl (chỉ-đọc), SpeakY giữ
  '—' (khai tử). Restart to-chuc → ok "3/3 nguồn KPI đọc được". CÒN LẠI 4 app
  chưa khai suc_khoe: content-ultimate / niche-research / seo-optimize (repo
  lồng — làm khi có mạch mở các repo đó) + data-analytics (chờ điền két rồi
  thêm module llm giống ai-agent).

- **01/09/2026 (0h) — PHỦ TRỌN 13/13 APP** (DA repo cha; content 8386074 ·
  niche 2f78eff · seo fc98d76 ở repo lồng). data-analytics: llm-dien-giai (hỏi
  két 3s — trống → canh_bao chỉ đường, cùng họ bệnh ai-agent) + bao-cao;
  seo-optimize: khoa (load_keys từ két, nổ → canh_bao không loi — app vẫn phục
  vụ dữ liệu đã có) + du-lieu, route vào _OPEN như /api/health; niche-research:
  khoa (đếm khóa mọi việc trong két) + du-lieu (đếm dự án); content-ultimate:
  ho-so-giong tái dùng _soi_kho_ho_so (corpus hỏng = gốc bệnh 'viết không tốt'
  21/08), logic ở _suc_khoe_json hàm thuần. Nghiệm thu sống 4/4: DA canh_bao
  két-thiếu-writer đúng bệnh chờ Owner; content "12 hồ sơ, 12 neo mỏng" (C3
  treo hiện thẳng trên tab); niche 5 khóa/7 dự án; seo 2 khóa. Suite: DA 137 ·
  seo 25 · niche 14 · content 786/1 fail test_cli_write baseline (stash kiểm
  chứng). GHI NHẬN SAI KỶ LUẬT một lần: commit niche khi còn 1 fail (test
  thiếu NICHE_TRUST_PROXY) — vá bằng commit sau, không amend. Baseline fail
  các mạch khác đêm nay: root test_content_ultimate (outline) + to-chuc
  test_finance + content test_cli_write — đều có trước, đã ghi chú từng nơi.

- **01/09/2026 — ĐỀ XUẤT COMMAND CENTER (vòng mockup 1, CHỜ DUYỆT).** Owner đặt
  hàng nâng tab thành trung tâm chỉ huy dashboard realtime. Mockup vòng 1 (lệ
  mỗi-vòng-một-file): artifact 3d9d6284 + file scratchpad
  command-center-mockup-v1.html — brand Breakout Signal, dark-first + light,
  dữ liệu trạng thái THẬT đêm 31/08. Phương án kỹ thuật đề xuất: trang mới
  /general/command-center; nguồn dữ liệu dùng lại toàn bộ (B1-B6); thêm (1)
  ring buffer 24h trong vòng B5 + ghi sổ mỗi giờ cho uptime, (2) SSE
  /general/api/giam-sat/stream (full health 60s + đếm lỗi 15s; mồi 2KB +
  no-transform theo bài học streaming V2, fallback poll), (3) đo p50/p95
  latency tại proxy chuyen_tiep. 6 tính năng phase 2 vẽ sẵn chỗ trong mockup:
  quota YouTube theo két · đĩa/NAS · nhịp kinh doanh ngày · hành động nhanh
  (restart app, Owner-only 2 lớp) · MTTR/lịch sử sự cố · lưới ngoài Gatus.
  CHƯA CODE — chờ Owner duyệt mockup + chốt danh sách phase 2.
  → **Vòng 2 (01/09, artifact f648a5e6 + file v2 riêng, v1 giữ nguyên làm mốc)**
  theo góp ý Owner: (1) ĐA MÀN — Tổng quan / App chi tiết / Quota & Calls / Sổ
  sự cố; (2) màn app có tầng ĐO LOGIC 4 lớp: canary logic (gọi tính năng thật
  input mẫu, so kỳ vọng — bắt ca "HTTP 200 nhưng kết quả rỗng" họ bài học nút
  chia chương Content 30/08; kịch bản khai ngoài code nen/rules/canary/*.json)
  · nút chết (quét tĩnh fetch/form UI ↔ bảng route server + đếm 404/405 POST
  tại proxy) · bất biến dữ liệu · chỉ số kết quả (tỉ lệ thao tác thành công từ
  log — 21% lượt viết hỏng từng là chỉ số bệnh 07/08); (3) màn QUOTA: YouTube
  per-key dùng/còn/sống (usage đếm client-side từ sổ gọi của hệ, "sống" theo
  call thật gần nhất — không probe đốt quota, tự thử lại sau reset 0:00 PT) +
  LLM usage per app/vai (sổ llm_usage JSON-lines ghi tại provider wrapper) +
  bảng dịch vụ ngoài. Ca chia-chương-đỏ + số quota trong mockup là VÍ DỤ TÁI
  HIỆN để duyệt UI.
  → **Vòng 3 (01/09, artifact f772c9d2, file v3 riêng)** theo góp ý Owner "trung
  tâm điều hành xem HOẠT ĐỘNG LIÊN TỤC, không phải trạng thái tĩnh + bổ sung
  đường truyền": (1) HERO CHART màn tổng — request/phút + lỗi/phút 60 phút,
  chảy liên tục (SSE), crosshair rê chuột xem từng phút; (2) khối ĐƯỜNG TRUYỀN
  6 tuyến đo mỗi 60s: Z.ai · YouTube API · LAN nội bộ (p95 loopback) · NAS F:
  · NAS G: (đọc thử 4KB) · ntfy — mỗi tuyến latency hiện tại + sparkline 60′
  + pill thông/chờ; (3) màn app thêm chart request+p95+lỗi cùng trục thời
  gian; (4) màn quota thêm chart UNITS CỘNG DỒN trong ngày vs nhịp hôm qua vs
  trần 50k (thấy cạn TRƯỚC khi cạn); (5) màn sự cố thêm cột 14 ngày. Kỹ thuật
  đo đường truyền khi thi công: vòng nền B5 thêm 1 lượt đo tuyến (TCP/HTTPS
  connect tới đích ngoài đo ms — không tải nội dung; NAS đọc file 4KB đo ms;
  LAN = p95 sẵn có từ dem_loi), ring buffer 60′ chung khuôn.
  → **Vòng 4 (01/09, artifact 2f1ea5dd, file v4 riêng) — ĐỔI HƯỚNG THẨM MỸ theo
  3 mẫu Owner gửi** (chê v3 "xấu quá"): SkySpark NOC + Grafana trắng + big-screen
  neon. Ngôn ngữ mới: mật độ CAO kiểu phòng điều khiển — section header thanh
  lớn IN HOA viền accent, panel có header strip riêng, SỐ LỚN Space Grotesk
  (glow nhẹ ở dark), gauge bán nguyệt (uptime, quota còn), alarm bars ngang
  đỏ/cam/lá, ô ONLINE/OFFLINE, combo bar+line (request giờ + p95), donut lỗi
  theo loại, stacked bar sự cố 14 ngày, hero live + crosshair giữ từ v3.
  HAI THEME = HAI MẪU Owner thích: dark = NOC big-screen, light = Grafana trắng
  sạch (cùng khóa outliery_theme). Màn App/Quota/Sự cố sẽ theo cùng ngôn ngữ
  sau khi Owner duyệt hướng.
  → **Vòng 5 (01/09, artifact 79c0eb2d, file v5 riêng) — OWNER DUYỆT HƯỚNG NOC,
  trải trọn bộ 4 màn**: Tổng quan (giữ v4) + App chi tiết (alarm bars 4 tầng đo
  logic, ô đếm module/nút-chết/canary/404, gauge tỉ-lệ-viết-thành-công 79%,
  combo request+p95 12 giờ, bảng canary/nút chết/bất biến kiểu NOC) + Quota &
  Calls (gauge còn 38%, ô key sống/chết/nóng/reset, chart units cộng dồn hôm
  nay↔hôm qua↔trần, hbars per key, bảng LLM per app/vai, dịch vụ ngoài) + Sổ
  sự cố (4 meter: 7 ngày/đang mở/MTTR 41′/ốm nhất, stacked 14 ngày, bảng dòng
  có cột MTTR + trạng thái MỞ/THEO DÕI/KHÉP). Nav 4 màn hoạt động, click ô
  Content trên bản đồ mở màn app. SẴN SÀNG THI CÔNG P1 khi Owner chốt.

- **01/09/2026 (chiều) — THI CÔNG P1 COMMAND CENTER XONG, sống tại
  /general/command-center** (7 commit 3d7dd10→…; test-first từng mảnh; root
  287 pass / 1 fail baseline outline). Kỷ luật Owner chốt: Karpathy + canary
  là trung tâm + đối chiếu mockup tới khi khớp.
  - M1: proxy đo TTFB → p50/p95 per app; POST/PUT/DELETE trả 404/405 = NÚT
    CHẾT runtime, đếm riêng khỏi 5xx; theo_loai (5xx/502/504) cho donut.
  - M2 CANARY LOGIC (trọng tâm): nen/common/canary.py — kịch bản ngoài code
    nen/rules/canary/<slug>.json, mỗi logic MỘT MÃ TÊN; kỳ vọng
    [đường_json, toán_tử, giá_trị] (resolver ten=xxx — thứ tự module đổi
    không vỡ); 'sai' = gọi được mà KẾT QUẢ lệch (bắt ca HTTP-200-rỗng);
    kết quả bền data/canary/; tự động mỗi CANARY_CHU_KY 1800s trong vòng
    giám sát + POST /general/api/canary/<slug>/chay (nút CHẠY NGAY trên UI).
    22 kịch bản / 13 app — nghiệm thu sống 22/22 ĐÚNG ngay lượt đầu.
  - M3: nen/common/duong_truyen.py (5 tuyến thật tcp/doc, luật ngoài code;
    đo thật Z.ai 92ms · YouTube 53 · ntfy 268 · NAS 2) + ring buffer 1440
    tick + edge cảnh báo tuyến đứt/thông + GET /general/api/giam-sat/tong-hop
    (chọn POLL 15s thay SSE cho P1 — cùng UX, ít bẫy đệm LAN, ít code).
  - M4: template nen_command_center.html = đúng khung mockup v5 (builder
    replace có assert từng anchor) + JS render dữ liệu thật; 4 màn Tổng/App/
    Quota/Sự cố; ô chưa có nguồn (quota usage, LLM usage, quét tĩnh, MTTR)
    giữ chỗ nhãn P2 theo mockup. Đối chiếu: chụp Chrome headless 4 màn thật
    (session ký SESSION_SECRET chỉ-đọc + BOOT_DATA hook) đặt cạnh mockup —
    bố cục khớp; lệch = dữ liệu thật thay số minh họa + ô P2 đã đánh dấu.
  - **PHÁT HIỆN THẬT #4 (dashboard tự bắt khi đối chiếu)**: ai-agent FLAP
    'suc-khoe không đọc được ↔ hồi phục' mỗi ~10-11 phút suốt chiều 01/09 —
    canary search lượt đầu sau cache 10' chạy RERANKER (default bật) 5-9s
    vượt timeout 3s → báo lỗi oan. Fix: RERANK_SEARCH=false trong start-all
    (tiền lệ V2 kho nhỏ; kho lớn xóa 1 dòng là bật lại) + deep health timeout
    riêng 10s (liveness giữ 3s). Đo sau vá: search lạnh 0.235s.
  - Trang Applications có link → Command Center. Hết mạch P1.

- **01/09/2026 (tối) — APPLICATIONS NGHỈ HƯU, CHỈ CÒN COMMAND CENTER + theme
  trùng cả hệ** (commit f4e4f50, Owner chốt "Command Center bao trọn"). 
  /general/applications redirect 303 → /general/command-center (bookmark cũ
  sống); nav General nhãn "Command Center"; alias /ung-dung trỏ theo; template
  nen_ung_dung.html xóa; pin quyền test_gateway chuyển sang đường mới (khóa
  quyền general_ung_dung GIỮ NGUYÊN — không đổi hệ quyền). Theme: stamp
  data-theme từ khóa chung outliery_theme trước khi CSS parse (khuôn nen_base),
  nút gạt SÁNG/TỐI ghi khóa chung — cả hệ đổi theo, nghe storage event (lệ
  22/08). Chụp light kiểm mắt: đúng Grafana-clean như mockup. Root 287 pass.

- **01/09/2026 (tối, tiếp) — VÀO KHUNG GENERAL + QUOTA NỐI THẬT VỚI KÉT**
  (commit a336310, 2 góp ý Owner). (1) Template extends nen_base — Command
  Center hiện như MỘT TAB khối General (nav muc, header, user), main nới
  1340px (bài học ThumbY), CSS scope #cc; bỏ topbar trùng. (2) API tổng-hợp
  thêm khối `ket` (_ket_tom_tat): khóa che đuôi 4 + cấp phát app·việc + cấu
  hình LLM per việc — test soi TUYỆT ĐỐI không key trần. Màn Quota giờ là
  gương của tab API Keys: 28 khóa thật (20 YouTube + 2 LLM…), bảng cấp-cho
  từng app·việc, 11 việc LLM ĐÃ CẤP (dien_giai/extract/critic/viet_kich_ban/
  chia_beat…) + 2 dòng CHỜ KÉT (writer ai-agent + DA) khớp cảnh báo suc_khoe
  — Owner nhìn 1 màn biết vai nào thiếu. Root 288 pass.

- **01/09/2026 (tối muộn) — SỔ GỌI API NỐI THẬT (Owner phê "đã yêu cầu mà
  chưa nối" — nhận lỗi: tôi tự xếp P2 sai ưu tiên; sửa ngay trong ngày).**
  (repo cha 5d1000f + radary 175bd7c + seo d48209d + content f8cc68d).
  - nen/common/so_goi.py + POST /api/so-goi loopback: mỗi call ra ngoài 1
    dòng JSON-lines {app, dich_vu, ĐUÔI key 4, viec/model, units, ms, ok,
    ma_loi}; tổng hợp hôm nay per key/việc; SỐNG/CHẾT theo call thật gần
    nhất (không probe đốt quota). Key trần không bao giờ rời app.
  - Móc 5 điểm gọi TẬP TRUNG: radary API.get (units=cost, 403 ghi lỗi trước
    khi xoay key) · seo yt_get (search=100, khác=1) · content httpx.post
    (điểm LLM duy nhất) · ai-agent + DA llm providers (helper _ghi_so ở base,
    factory gán vai; mock KHÔNG ghi — không đổ số giả). Content hóa ra có
    voiceprofile/usage nội bộ riêng — sổ nền bổ sung góc nhìn hệ.
  - Két tracking ĐỦ (ý 1+2 Owner): _ket_tom_tat thêm `viec` — MỌI cấp phát
    hiện diện kể cả việc không-LLM và việc TẮT 0 khóa (test ghim: rút hết
    khóa vẫn hiện TẮT, không biến mất) + `theo_loai` đếm động (loại khóa mới
    thêm vào két tự có mặt, UI không enum cứng).
  - UI Quota: gauge còn-hôm-nay = units sổ gọi ÷ (số key yt × 10k); bảng khóa
    cột "Hôm nay" (units + bar + call cuối + SỐNG/403); bảng cấp phát đầy đủ;
    LLM hôm nay từ sổ. Suite: root 294 · radary 213 · seo 28 · content 783 ·
    ai-agent 321 · DA 137 (fail baseline như cũ).
  → Nghiệm thu sống trong 5 phút đầu: 111 dòng sổ từ quét RadarY thật — bắt
  ngay key api-001 (••-9cc) trả 403 CẠN QUOTA, RadarY tự xoay key (UI hiện đỏ
  403 / xanh SỐNG per key). Chart units cộng dồn theo giờ chạy thật (theo_gio
  trong so_goi — trần tự tính theo số key youtube trong két). Két đủ MỌI loại:
  20 youtube · 2 llm · 1 transcript · 2 serp · 1 apify · 2 stock; cấp phát đủ
  mọi việc kể cả ai-agent·writer TẮT (0 KHÓA) hiện đỏ.
  → Owner bắt thiếu SERP + Apify/reddit — móc nốt 2 điểm gọi tập trung của
  radary (serp._goi wrapper 1 unit/call, hết quota ghi lỗi trước khi xoay;
  reddit._goi ghi cả HTTP lỗi lẫn thành công), helper chung so_goi_nen cho
  scan/serp/reddit (radary 390cf96 + gộp helper). Suite 212 pass. Ứng viên
  P2: Apify có API du_credit thật — hiện credit còn trên màn Quota.
  → Owner "làm luôn" — nen/common/quota_ngoai.py (c84bfc6 + vá kỳ-rỗng):
  đọc khóa apify từ két → /users/me → credit còn/trần USD, cache 30′, dòng
  đầu bảng Dịch vụ ngoài (đỏ SẮP CẠN khi <$1). Bẫy đo thật: tài khoản chưa
  tiêu kỳ này → currentBillingPeriod RỖNG = đã dùng $0 (không trả None oan).
  Nghiệm thu sống: FREE · còn $5/$5.
- **02/09/2026 — SƠ ĐỒ VẬN HÀNH SỐNG per app** (commit 92562b6, Owner đặt
  hàng "hiện sơ đồ vận hành từng app"). Luật ngoài code nen/rules/so_do/
  <slug>.json: nút theo CỘT (người dùng → tính năng → lõi → dịch vụ ngoài) +
  cạnh có nhãn; binding suc_khoe/canary/tuyen → khối TÔ MÀU trạng thái đo
  thật — nhìn sơ đồ thấy ngay nghẽn ở khâu nào. Nút thiếu trường/cạnh mồ côi
  bỏ qua (sửa JSON tay không vỡ UI); test ghim mọi binding của sơ đồ mẫu phải
  trỏ thứ CÓ THẬT. Mẫu ai-agent nghiệm thu sống: Hỏi–đáp XANH (canary đúng) ·
  Kho vector XANH (157 point) · Writer VÀNG ("writer đang MOCK") — đúng chỗ
  nghẽn hiện trên sơ đồ · Z.ai nét đứt 100ms. CHỜ OWNER duyệt khuôn để trải
  12 app còn lại (tôi soạn nháp JSON, Owner chỉnh luồng nghiệp vụ nếu lệch).

## Việc còn (cập nhật khuya 31/08)

- [ ] **TAY OWNER — điền két vai writer** cho ai-agent (+ DA nếu muốn Analyze
      thật): General → API keys; xong thì module llm-writer tự chuyển ok.
- [ ] **TAY OWNER — bật ntfy**: start-all.ps1 dòng GIAM_SAT_NTFY_TOPIC +
      subscribe topic; chưa bật thì cảnh báo vẫn nằm sổ + tab.


- [ ] **Nghiệm thu sống sau restart**: tab Applications hiện Modules ai-agent
      (kho thật :6343 → ok "N point / M tài liệu"); plannery Status xanh với
      /health mới; thử 1 request lỗi xem cột Errors 5′.
- [ ] **Kiểm data-analytics cùng bệnh MOCK?** — app cũng đọc MOCK_MODE cho
      tầng LLM diễn giải (src/llm/factory.py); start-all không set → xem
      default của nó là gì, diễn giải Analyze trên hệ có đang mock không.
- [ ] **B3 lan dần**: khai `suc_khoe` cho radary (giờ quét cuối + quota),
      to-chuc (chấm công hôm nay), rendery/thumby (ffmpeg + đĩa), plannery
      (plan.json đọc được + _rev)… mỗi app một commit, test trong app.
- [ ] **Rendery /health thật** (repo F:/RenderY/autoedit — sửa + restart lúc
      không có job dựng; apps.json đang tạm giữ /api/me).
- [ ] **B4 heartbeat việc nền** (pattern Healthchecks): sổ việc-phải-chạy-đúng-
      hạn (backup 19:00, quét RadarY, BatMay 9:00) + POST /api/nhip-viec/<ma>;
      quá hạn → đỏ trên tab.
- [ ] **B5 cảnh báo ngay**: lift ntfy_send của radary lên nen/common + luật
      (chết ≥2 ping liên tiếp / module loi / heartbeat trễ) + gộp chống spam.
- [ ] **B6 canary tính năng thật** (pattern Gatus conditions): 15'/lần gọi vài
      đường end-to-end với kỳ vọng cụ thể (search có chunk, SSO đúng vai).
- [ ] Gatus binary đứng NGOÀI gateway làm lưới cuối (gateway chết thì ai báo?)
      — cân nhắc sau khi B5 chạy.
