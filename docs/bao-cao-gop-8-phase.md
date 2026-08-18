# Sổ: Báo cáo GỘP 8 phase — nâng cấp tool Niche Research

> Mạch việc bắt đầu 18/08/2026. Nguồn sự thật là code; sổ này ghi QUYẾT ĐỊNH + trạng thái.
> Bản mẫu sống: `apps/niche-research/projects/LifeIn_US/Report/BAO-CAO-8-PHASE.html`.

## Mục tiêu

Tool hiện trả **báo cáo thuần số** (xlsx 15 sheet + SUMMARY) — team đọc không rõ mục tiêu để
hành động. User gửi **"Phương pháp luận Niche Research & Content Go-To-Market v1.0"** (8 phase,
Decision Gate, phân vai Business/Production — file `Methodology Niche Research.txt`, sẽ nạp kho
tri thức). Yêu cầu: **GỘP** số liệu pipeline và khung marketing thành MỘT báo cáo, rồi code vào
tool để mọi lần chạy tự ra bản gộp.

## Quyết định đã chốt (user chọn 18/08, cả 3 theo khuyến nghị)

1. **8 phase làm xương sống** — mỗi phase 3 tầng theo thứ tự:
   - `[SỐ LIỆU]` — bảng phân tích đầy đủ của pipeline nhúng thẳng (KHÔNG trỏ ra Excel);
   - `[DIỄN GIẢI]` — ngôn ngữ marketing, ra đúng **output bắt buộc** của phase (Canvas /
     Competitor 5 lớp / Gap Map 4 loại / Scorecard 4 tiêu chí / Statement + Thesis +
     Anti-positioning + kiểm 3 câu / Format Hypothesis + skeleton / Packaging Guidelines 5 phần
     + checklist / Launch Roadmap pillar + 8–12 video / KPI + Tracking + Learning Log);
   - `[GATE]` — ĐẠT / CHƯA ĐẠT / ⏸ CHỜ NGƯỜI QUYẾT + điều kiện. Gate cần người (ký P0, chọn
     positioning, duyệt 3 mẫu thumbnail) là checklist chờ người — **máy không tự phán ĐẠT**.
2. **HTML một trang là định dạng chính**; Excel hạ vai phụ lục dữ liệu thô.
3. **Nhúng toàn bộ số liệu, thu gọn bằng `<details>`** (mặc định 5–8 dòng, bấm xổ đủ).

Mapping sheet cũ → phase: Niche Analytics/Summary → trang phán quyết · Questions → P1 ·
Channels + Go-NoGo + Beachhead + Videos → P2 · Title Templates/Patterns/Vocabulary/Topic Lift
→ P4+P5 · Recommended(bets)/Execution Plan → P6 · Early Signals → P7 · Disagreements → mục
trung thực. **Không sheet nào mất nhà.**

## Nguyên tắc giữ nguyên khi code

- **Nguyên tắc vàng PY/LLM** (NICHE-TOOL-ARCHITECTURE.md §0): PY render mọi bảng [SỐ] tất định
  từ JSON; LLM chỉ viết tầng [NGHĨA] qua agent spec + JSON schema, KHÔNG tính lại số.
- Nhãn **GIẢ ĐỊNH** cho nội dung chưa có input người (P0 nháp, năng lực team, North Star).
- Van trung thực: residuals R-1/R-A/R-3, RPM heuristic, cảnh báo pool bẩn — in thẳng vào báo cáo.
- Mỗi kết luận marketing phải **neo ≥1 con số + file nguồn** (bài học memory
  `bao-cao-phai-du-sau-methodology`: sơ sài = gắn nhãn phase không ra output bắt buộc).

## Trạng thái

- ✅ Pool 2 file RadarY gộp 153→112 kênh, tách US 77 / ES 22 / VN 4 (VN dưới chuẩn 8–12;
  9 kênh chờ xác nhận trong `projects/_pool-gop/CAN-XAC-NHAN.md`; nghi kênh nhà: Outland,
  satra globe es nanaa).
- ✅ Chạy end-to-end US thật: CONDITIONAL 58 · crackability OPEN · beachhead hidden 114/laos 111
  · bet STRONG "no one talks about" (lift 6,3). Key lấy từ bản cũ theo lệnh user.
- ✅ Bản mẫu báo cáo gộp soạn TAY: `LifeIn_US/Report/BAO-CAO-8-PHASE.html` (95KB, artifact
  e636d2ba) — đây là SPEC SỐNG cho tầng render mới.
- ⚠ Đã biết: pool US nhiễm kênh Urdu (Globe Cover + video Urdu/Hindi cụm yemen/iraq) — cần lọc
  ngôn ngữ sau scan; 2 key YouTube thật trong .env.example+README repo cũ đã push GitHub —
  chờ user rotate; S9 in `Σ` chết cp1252 → chạy orchestrator kèm `PYTHONUTF8=1` (nên vá gốc:
  orchestrator tự set PYTHONIOENCODING cho subprocess).
- ⏳ UI: user chê UI hiện tại "vô nghĩa" (console pipeline + kệ file) → **đề xuất UI trước,
  duyệt rồi mới code** (mockup 18/08). Hướng: UI = quy trình ra quyết định — portfolio ngách,
  hồ sơ ngách render báo cáo gộp + gate tương tác có ký tên, pipeline lùi về hậu trường.

## GỘP MODULE DATA ANALYTICS (chốt chiều 18/08)

User chốt tầm nhìn: báo cáo ngách là one-off → gộp Niche Research + Data Analytics (phân tích
kênh) thành MỘT module Data Analytics, **UI tổ chức theo Niche**: vào Niche → báo cáo nhanh
từng thị trường + nút đọc full/tải về + Ô THỜI GIAN lật báo cáo cũ; trong thị trường → tab
Phân tích kênh (kênh nhà); AI Agent được truy cập báo cáo để hỏi đáp. Mockup v2: artifact
50400e2f. Ba quyết định (AskUserQuestion):

1. **Vỏ UI chung, giữ 2 engine** ✓ — không viết lại pipeline niche lẫn engine 4 trục.
   **Host = `apps/data-analytics`** (giữ tên module, có claims-gateway + 64 test); UI cây
   Niche→Thị trường sống ở đây, gọi niche-research (:8780) qua API như engine con — đúng
   khuôn V3 "cầu nối API, KHÔNG import chéo" (đã ghi trong CLAUDE.md data-analytics).
2. **AI Agent truy cập: phương án NẠP KHO BỊ BÁC** (user: "report rất nhiều bảng biểu" —
   bảng cắt chunk vào vector là mất cấu trúc). **Phương án 2 "truy vấn có cấu trúc" —
   USER ĐÃ DUYỆT 18/08** ("Đồng ý với phương án này"). UI: user yêu cầu đề xuất UI hoàn
   chỉnh TRƯỚC khi gộp → mockup v3 (artifact 50400e2f, nhãn v3-ban-duyet-truoc-gop):
   bản đồ màn hình M1–M6 + ngăn "Chưa phân loại" (di trú báo cáo kênh cũ, không mất
   lịch sử) + bảng quyền (ký gate Business = Manager+ chủ quản; Production = Leader+;
   quản trị module = Owner). CHỜ USER DUYỆT MOCKUP V3 rồi mới code gộp. Thiết kế: trang Hỏi–đáp thêm nguồn "📊 Báo cáo phân tích"; khi câu
   hỏi thuộc phạm vi báo cáo, bước TÌM đổi retriever — (a) `GET /api/agent/registry`
   (danh mục niche/thị trường/kênh + ngày báo cáo), (b) bước "chọn mục cần đọc" (LLM nhỏ
   map câu hỏi → mục trong mục lục báo cáo, cùng họ bước viết-lại-câu-hỏi sẵn có),
   (c) `GET /api/agent/bao-cao/{niche}/{market}?muc=...&ngay=latest` trả đúng LÁT JSON
   (bảng ở dạng cấu trúc, số nguyên văn, kèm ngày). Writer nhận JSON làm bằng chứng, trích
   nguồn `[NICHE-LIFEIN-US 18/08 · decision2]`; vòng phản biện giữ nguyên + tiêu chí mới
   "số phải khớp JSON"; ngoài mục lục → "báo cáo chưa có mục này" (van chống bịa). RBAC:
   API kiểm claims như mọi cầu nối V3. KHÔNG cần dạy tầng LLM function-calling.
3. **Gate ký làm từ Đợt 1** ✓ — trạng thái sống cấp niche×thị trường (`gates.json`),
   không mất khi chạy lại pipeline.

**CHỐT IA CUỐI (mockup v5, nhãn v5-menu-2-cap):** user chê v4 vẫn rối → menu đúng 2 cấp
kiểu tab General: **dropdown chọn Niche → danh sách [Overall | Kênh 1..N]**. "Thị trường"
KHÔNG còn là cấp điều hướng — chỉ là lá cờ thuộc tính trên dòng. Overall = mỗi market một
DÒNG (phán quyết · Đọc báo cáo/⬇/↻; đang chạy → dòng thành progress bar + log xổ tại chỗ);
Kênh = màn Data Analytics hiện có (4 trục + Analyze + ô ngày lịch sử) thêm dải so-với-ngách;
⚙ = pool/key/gán kênh↔market. Mockup v4 (nhiều màn, tab) NGHỈ — v5 là bản chốt IA.

**UI ĐÃ DUYỆT 18/08 — quy ước cuối (lời user):** minimalist icon (line-SVG, hạn chế emoji) ·
BUTTON/MENU tiếng ANH (Overall · New report · Download · Settings…) · NỘI DUNG báo cáo +
dashboard tiếng VIỆT. 2 tính năng bắt buộc: (1) xem lại báo cáo cũ (ô 🗓) + DOWNLOAD full
báo cáo; (2) báo cáo mới sinh ra TỰ CẬP NHẬT dashboard (poll trạng thái tác vụ nền → refresh
tile/row, đúng khuôn task-poll của Data Analytics). → BẮT ĐẦU CODE GỘP.

**BẢN CHỐT UI (artifact 02a5a49f "Bản chốt UI Data Analytics"):** sidebar bản-dropdown-đã-duyệt
(Life In ▾ · Overall · kênh 1..N có chấm đỏ khi trễ report tuần · ＋ Tạo report · ⚙) bên TRÁI
+ dashboard Shopify bên PHẢI (Overall = tiles niche + beachhead + radar + Best&Worst cụm;
Kênh = tiles kỳ + line views + phán quyết + Best&Worst video). BÀI HỌC QUY TRÌNH: user bắt
lỗi tôi GHI ĐÈ mockup đã duyệt (v5 mất khi lên v6/v7) — từ giờ MỖI VÒNG DUYỆT MỘT FILE/LINK
RIÊNG; v5 đã khôi phục ở artifact f3dedd1e, v7 dashboard+modal ở 50400e2f. ĐÂY LÀ SPEC UI
ĐỂ CODE.

**TẠO REPORT MỚI (mockup v7, nhãn v7-them-tao-report):** user duyệt v6, chỉ thiếu cửa tạo
report → nút **＋ Report mới** cố định trên band, modal 2 nhánh: 📊 Niche (chọn/tạo niche +
chip thị trường + dán pool đối thủ + key dùng-lại) · 📺 Kênh (chọn/tạo kênh gắn cờ thị trường
+ kéo-thả file Studio + tên tự gợi ý "Kênh — tuần N"). Submit → về dashboard, dòng tương ứng
thành tiến độ inline. Niche/kênh mới tạo NGAY trong modal, không có màn quản trị riêng.

**QUICK VIEW KIỂU SHOPIFY (mockup v6, nhãn v6-dashboard-shopify) — user duyệt IA v5 rồi
gửi ảnh Shopify Sales Report làm mẫu quick view.** Dashboard = hàng TILE số → biểu đồ chính
→ khối Best&Worst xanh/đỏ. OVERALL tiles: Điểm hấp dẫn /100 + verdict · View trung vị ·
Mốc trúng p90 · Cung/tháng · Cửa vào (%kênh mới, OPEN/CLOSED) · RPM band (nhãn heuristic);
chart: bản đồ beachhead + radar 5 trụ; Best&Worst = top/bottom CỤM theo điểm beachhead;
lọc thị trường bằng chip All/🇺🇸/🇪🇸/🇻🇳 (thay cấp menu). KÊNH tiles: Views kỳ · Giờ xem ·
Retention trung vị · Video "sống" vs ngách (benchmark từ báo cáo niche) · 4 trục · Doanh thu
(— khi chưa monetize, van chống bịa lên tile); chart: line views theo ngày + mốc sống ngách;
bar phán quyết; Best&Worst = top/bottom VIDEO theo OX so baseline kênh + chip phán quyết.
Cách làm: PY tính hết, template đổ tile + SVG tĩnh (không lib JS ngoài), 2 theme.

**Góp ý UI 18/08 (mockup v4, nhãn v4-toi-gian-bieu-do):** user chê v3 "rối, nhiều chữ" +
2 điểm: (1) bỏ tab log — CHẠY INLINE trong thẻ thị trường (bấm ▶ → thẻ thành progress bar
+ log xổ tại chỗ; pool/key sau nút ⚙); (2) Hỏi đáp KHÔNG phải màn của module — là tích hợp
bên app AI Agent (Đợt 3). Nhắc nguyên tắc MINIMALIST ICON. **Tích hợp diagram-design theo
lệnh user:** clone `daddychee/diagram-design` → `_references/diagram-design` (đã gitignore),
cài skill vào `.claude/skills/diagram-design` CẢ 2 repo (token đổi sang brand OUTLIERY:
paper #F7F8FA / ink #16181C / accent #2C6FC4 trong references/style-guide.md). Ngữ pháp áp
dụng: mật độ 4/10, accent chỉ 1–2 điểm nhìn trước. Báo cáo gộp sẽ thêm biểu đồ: radar 5 trụ
(phán quyết) · scatter beachhead cạnh-tranh×điểm cỡ=reach (P2) · quadrant subs×nhịp (P2) ·
bar median-vs-p90 (P1) · gantt roadmap (P6) · line snapshot theo quý (P7, khi ≥2 kỳ).

Đã code (mở màn Đợt 1): vá UTF-8 hai tầng trong `orchestrator.py` (reconfigure stdout
tiến trình cha + PYTHONUTF8/encoding utf-8 cho stage con) — hết họ lỗi Σ/✓ chết cp1252;
verify `status` chạy sạch.

## Trạng thái code Đợt 1 (18/08, 3 commit: cba6591 · 16f646b · b8605ef)

- ✅ `niche-research/scripts/snapshot.py` — đóng băng lần chạy theo ngày; LifeIn_US có
  snapshot 2026-08-18 (10 artifact + BAO-CAO-8-PHASE.html + xlsx). Vá UTF-8 orchestrator 2 tầng.
- ✅ `data-analytics/src/niche_bridge.py` — đọc snapshot (bậc 1 đĩa, env NICHE_PROJECTS_DIR),
  tile + beachhead + Best&Worst, van chống bịa từng ô; download chỉ file trong sổ index.
- ✅ **Trang `/niche`** (src/dashboard.py + templates/dashboard.html, extends base app):
  rail = dropdown niche (danh bạ nền) + kênh + New report (tạm trỏ /chan-doan — nhánh
  Niche run nối sau); pane = mỗi thị trường 1 section: verdict VN + 6 tile + Best&Worst
  cụm + 🗓 chọn snapshot + Read report (mở HTML inline) + Download HTML/Excel.
  Ánh xạ ngách×TT→project: `data/data-analytics/niche_projects.json` (đã seed
  N-LIFE-IN/TT-US→LifeIn_US; env NICHE_PROJECTS_MAP cho test). Suite 75 pass.
  ⚠ Test xanh ≠ chạy đúng: CẦN KIỂM MẮT qua cổng thật (/data-analytics/niche) —
  token --th-* đến từ khung gateway, màu ok/warn tạm dùng accent/d97c6c (ponytail token).

## Trạng thái Đợt 1b (18/08 tiếp — commit 30c0598 + bec7594, suite 84 pass)

- ✅ **Pane KÊNH** `/niche/kenh/{ma}`: tile metrics_chinh (views/giờ xem/CTR/retention/
  doanh thu-van-chống-bịa/tầng vỡ) + ô 🗓 chọn report + dải so-ngách (benchmark từ snapshot
  niche đúng thị trường kênh) + Best&Worst video + line views (dựng từ FILE GỐC, guarded,
  không LLM) + nút Full analysis → trang lịch sử sẵn có. Nối kênh danh bạ ↔ report bằng
  chuan_hoa_ten + bí danh trên trường ten_kenh.
- ✅ **Run + tự cập nhật** (tính năng 2): nút Run (L3+) → POST /api/resume service :9113
  (NICHE-RESEARCH ĐÃ LÀ SERVICE V3, PORTS.md :9113, key YouTube service tự lấy từ KÉT —
  hết cần dán key vào competitors.txt) → JS poll 3s → xong thì data-analytics tự ĐÓNG BĂNG
  snapshot (gọi scripts/snapshot.py CLI, chống đúp bằng registry+lock; ponytail: chuyển
  thành /api/snapshot của niche server khi restart kèm code mới) → location.reload().
- ✅ **DỜI NHÀ projects**: LifeIn_US/ES/VN + _pool-gop từ apps/niche-research/projects →
  `data/niche-research/projects` (nhà V3, service :9113 đọc ở đây); bridge default đổi theo.
  Thư mục LifeIn_US cũ bên apps/ còn lại vì user đang mở Excel (~$ lock) — MOVED.txt ghi chú,
  xóa tay sau.

## Trạng thái CUỐI 18/08 — module code XONG phần lõi (9 commit, suite 94 pass)

Thêm 4 slice cuối (c77be8b · dc034e9 · 83c0435 · fc03169+e3f2c5e):
- ✅ Radar 5 trụ + bản đồ beachhead SVG trong Overall (PY tính toạ độ, accent 2 cụm đầu).
- ✅ Modal New report 2 nhánh: Niche = chọn/tạo project (sinh tên từ ngách+TT, ghi
  niche_projects.json nguyên tử) + pool CỘNG DỒN không trùng + chạy /api/run service
  (key từ KÉT) + poll tự cập nhật; Channel = trỏ form nạp report sẵn có.
- ✅ Gate ký 8 phase (`src/gates.py` + sổ data/data-analytics/gates/): business L4+ /
  production L3+ / auto theo báo cáo; chip rail + Sign + phương án P3; chữ ký sống qua
  các lần chạy lại.
- ✅ API cầu nối AI Agent (`src/agent_api.py`): /api/agent/registry ·
  /api/agent/bao-cao/{project}?muc=&ngay= (11 mục whitelist, lát JSON nguyên cấu trúc,
  mục lạ 400 "Hợp lệ: …") · /api/agent/kenh-report/{id}. HỢP ĐỒNG cho app ai-agent làm
  retriever nguồn "📊 Báo cáo" (phần tích hợp hỏi–đáp nằm BÊN app ai-agent — mạch riêng).
- Bài học trong ngày: pipe `| tail` nuốt exit code pytest → commit lọt test đỏ 1 lần
  (fc03169, sửa ngay e3f2c5e) — từ giờ `set -o pipefail` khi test-trước-commit; import
  hàm trực-tiếp giữa module làm monkeypatch không ăn → gọi qua module.

## PA2 — MỘT MẶT TIỀN (user chốt 18/08 tối, commit f2fe347 + 7ef4e15, suite 96 pass)

User bác trạng thái nửa vời (trang cũ làm mặt tiền + nút "Niche dashboard" chắp vá) → bàn 3
phương án, chốt PA2 gộp triệt để: (1) sidebar 4 app + khung gateway đều ẩn "Niche Research"
(nen/common/sidebar.py KHONG_LAP_TOOLS — restart ai-agent + data-analytics; to-chuc/
video-review ăn theo lần restart kế vì to-chuc đang dở tay phiên song song) và trỏ
"Data Analytics" → /niche; (2) form nạp report kênh VÀO modal New report tab Channel —
**chọn kênh từ DANH BẠ (hết ô gõ tay)**, đủ file/loại kênh/ngày/kỳ, POST /chan-doan sẵn có,
chạy nền + poll, xong tự mở /niche/kenh/<ma>; (3) GET /chan-doan chỉ còn redirect /niche
(POST + trang-thai + bao-cao-lich-su + mọi route con GIỮ NGUYÊN — backend của modal +
pane Kênh; chan_doan.html thành template legacy không render). Bài học: hai lần sửa nhầm
khung sidebar — hệ có NHIỀU nơi vẽ sidebar (khung gateway + base.html từng app, nguồn
danh sách = nen/common/sidebar.py), sửa sidebar phải grep đủ cả họ.

## CÒN LẠI (các mạch sau)

1. App ai-agent: retriever nguồn "📊 Báo cáo" theo hợp đồng /api/agent (Đợt 3 phần còn lại).
2. Đợt 4: benchmark ngách vào engine 4 trục (baseline thứ ba) — đụng diagnosis_engine,
   đọc docs/analytic_methodology.md trước.
3. Kiểm mắt qua cổng thật /data-analytics/niche (test xanh ≠ chạy đúng) + token ok/warn
   cho khung app (ponytail trong dashboard.html).
4. Tay user: rotate 2 key YouTube lộ trong git repo cũ (daddychee/niche-research) +
   đóng Excel để xóa thư mục LifeIn_US cũ bên apps/ (MOVED.txt).
5. Chạy ES/VN khi pool sẵn sàng (ES chạy được ngay qua nút Run — key từ KÉT).

## Việc còn Đợt 1b→4

1. Pane KÊNH (tile kỳ + line views + Best&Worst video theo OX baseline kênh + dải so-ngách).
   ĐÃ KHẢO SÁT (18/08, trước /compact): bản ghi bao-cao-lich-su CÓ SẴN `ten_kenh` +
   `loai_kenh` + `kenh{tang_vo, so_video, metrics_chinh{ctr,retention,views,watchtime,
   revenue}, luat_khop}` + `ky_bat_dau/ky_ket_thuc` → nối kênh danh bạ ↔ report bằng
   `ten_kenh` (so qua danh_ba.chuan_hoa_ten + bí danh); tile lấy từ metrics_chinh;
   line chart dùng `doc_chart_data` (diagnosis_engine, đọc file gốc); Best&Worst video
   tái dùng `chan_doan_toan_bo` từ file gốc như trang lịch sử (rẻ, không LLM);
   danh sách report của kênh: `doc_bao_cao_moi_nguoi()` lọc theo ten_kenh.
2. Modal New report 2 nhánh thật (Niche run: cầu chạy pipeline niche-research + progress
   inline + poll tự cập nhật khi xong — tính năng 2 user yêu cầu).
3. SVG radar + scatter beachhead vào pane Overall (diagram-design grammar).
4. Gates ký (gates.json + API) trong Read report · benchmark ngách vào engine 4 trục (Đợt 4).
5. Đợt 3: cầu AI Agent (phương án 2 đã duyệt).

## Việc còn (sau khi UI được duyệt)

1. `19_build_bao_cao.py` [PY]: render HTML gộp từ mọi JSON (khuôn = bản mẫu LifeIn_US;
   tầng [SỐ] + khung, chừa slot [NGHĨA]).
2. `agents/bao_cao_writer.md` [LLM]: viết tầng [NGHĨA] từng phase → JSON theo schema
   (`contracts/bao_cao.schema.json`), neo số bắt buộc, không đụng bảng.
3. Trạng thái gate per-project (`niche-data/gates.json`): ai ký, lúc nào, phương án chọn —
   ghi nguyên tử; UI đọc/ghi qua API.
4. UI mới trên server.py :8780 theo mockup đã duyệt.
5. Nạp methodology vào kho tri thức (kiểm encoding file gốc — bản đính kèm chat bị mojibake).
6. Dọn pool: loại kênh Urdu, xác nhận 9 kênh treo, bổ sung kênh VN, chạy ES.

## 18/08 (tiếp) — PA2b: sửa "link hỏng" qua cổng + điều hướng lên đầu trang

User kiểm mắt `localhost:9443/niche` → `{"detail":"Not Found"}` + chê tỉ lệ, yêu cầu
bỏ rail trong, đưa điều hướng lên đầu như tab General.

**Gốc bệnh link hỏng:** gateway V3 route URL đẹp cấp gốc bằng bảng `_ALIAS` cứng trong
`nen/gateway/main.py` (đăng ký route lúc import) — `tien_to` trong apps.json CHỈ là bảng
viết-lại đường dẫn của proxy, KHÔNG phải bảng route. Thêm `/niche` vào apps.json (hôm qua)
là sửa nhầm tầng. `/niche` không có alias → 404 ngay tại gateway; sidebar `href="/niche"`
trong HTML app khác cũng không được proxy viết lại (không nằm trong tien_to app đó) → bấm
là chết. BÀI HỌC: URL đẹp cấp-1 = `_ALIAS` gateway; `tien_to` = viết lại nội dung/Location.

**Sửa KHÔNG đụng gateway** (main.py gateway đang dở tay phiên song song NAS — không sửa,
không restart): (a) `GET /chan-doan` (data-analytics) phục vụ THẲNG dashboard — ủy quyền
sang `dashboard.trang_niche`, vì alias sẵn có `/data-analytics` → `('data-analytics',
'chan-doan')`; hết redirect /niche (redirect qua cổng là 404). (b) sidebar 5 khuôn đổi
`href="/data-analytics"` (alias nằm trong `bo_qua` nên không bị viết lại, sống từ mọi app).
(c) PA3 (alias `/niche` đẹp hơn) vẫn treo chờ gateway sạch.

**UI theo lệnh user:** bỏ hẳn `.nd-rail` — thanh `.nd-top` trên đầu: [select niche]
[tab Overall | từng kênh — pill như nav.muc của General, cuộn ngang khi nhiều kênh]
[New report + nút General bên phải]; pane nội dung trần 1120px căn giữa (cân tỉ lệ màn
rộng). Empty-state pane Kênh hết link `/chan-doan` — nút mở modal chọn sẵn đúng kênh
(`moKenhModal`). `trang_kenh` bổ sung `ds_thi_truong` vào context (modal nhánh Niche cần).

Suite 97 pass. Restart :9102 — LƯU Ý khuôn start: cwd = GỐC repo + `--app-dir
apps/data-analytics` (start-all.ps1); cwd = thư mục app là chết import `nen.common`.
Kiểm sống: :9102/chan-doan 200 ra dashboard (nd-top, không nd-rail, tab Overall active,
niche LIFE IN từ danh bạ), gateway /data-analytics 303 login (route tồn tại, hết 404).

## 18/08 (tiếp 2) — Overall dựng lại theo mockup + kéo báo cáo gộp ra overview

User kiểm mắt tiếp: (1) vẫn hẹp hơn RadarY/Content → BỎ trần 1120px, full bề ngang
(padding 24px); (2) "đưa nội dung báo cáo tổng hợp ra làm overview như hình" + chê
dashboard xấu hơn mockup đã duyệt → dựng lại trọn pane Overall:
- BANNER PHÁN QUYẾT trên cùng mỗi thị trường: chip "PHÁN QUYẾT — VÀO CÓ ĐIỀU KIỆN ·
  58/100" + headline CỐ ĐỊNH THEO ENUM phán quyết (copy phương pháp, không bịa) + thân:
  gate_reason pipeline nguyên văn + mũi nhọn dẫn đầu (top beachhead) + dòng điều kiện
  gate P3 khi CONDITIONAL.
- LƯỚI TILE 3×2 + BẢN ĐỒ BEACHHEAD cột phải cao 2 hàng (đúng mockup): tile có tiêu đề
  + chú giải từ SỐ THẬT — "chênh 42× trung vị" (moc_trung_x = p90/median PY tính),
  "video trưởng thành (n=2.412)", "video thắng thuộc kênh <24 tháng · OPEN"
  (young_months), "travel — heuristic, chưa phải doanh thu đo" (category + copy cố định).
- 5 TRỤ + BEST&WORST: cột "Vì sao" deterministic từ ranked (cạnh tranh 0,30 · 33 kênh ·
  125 video) + hàng giữa "65 — trung bình 20 cụm" (diem_cum_tb/so_cum PY tính).
- DẢI "TỔNG QUAN SỐ CỦA PIPELINE" cuối khối: 9 ô từ analysis/demand/gaps/channels/
  decision1 (75 kênh · 3.815 video · 2.412 trưởng thành · 648 outlier · 104 tín hiệu
  sớm · 12.869 comment · 1.081 câu hỏi · HHI 0,073 · 264 cung/tháng) — ô thiếu nguồn
  = "—" (test ghim video_truong_thanh None khi demand giả thiếu n_matured).
- PILL THỊ TRƯỜNG All | US | SPAIN trên band (mockup); ?tt= lọc server; gán thêm
  TT-SPAIN → LifeIn_ES vào niche_projects.json (chưa snapshot → khối "Chưa có báo cáo
  + Run analysis" — Run là chạy được, key từ KÉT). LƯU Ý: hình mockup có "1.193 đủ
  điều kiện đánh giá" — KHÔNG tái lập được từ artifact nào → không hiển thị, dùng
  n_matured 2.412 (demand) làm cột "Trưởng thành".
- Sửa bug _ten_thi_truong: danh bạ trả ten=None → .get(ten, ma) vẫn ra None → in
  "None" lên UI; giờ fallback mã bỏ tiền tố TT- ("US"/"SPAIN"/"KOREA").
- test_agent_api ca thiếu-artifact đổi analysis → bets (seed giờ có analysis.json thật).
Bridge thêm: pipeline{9 khóa} + moc_trung_x + cua_vao_thang + rpm_nhan + so_cum +
diem_cum_tb — TẤT CẢ nhặt/chia từ artifact, không tính lại chỉ số. Suite 99 pass;
kiểm HTML thật :9102 đủ banner/pills/strip/vì-sao, 0 chữ "None".

## 18/08 (tiếp 3) — hạ cỡ chữ + tab 3 nội dung + pill đủ thị trường danh bạ

Ba phản hồi kiểm mắt tiếp của user: (1) chữ dashboard to hơn app khác → hạ cả thang
(~12-20%: h1 1.25→1.02rem, tile 1.7→1.32rem, thân .87→.8rem…). (2) "3 ảnh 3 nội dung
cần show, hiển thị bằng quẹt chuyển tab" → mỗi khối thị trường 3 TAB: Overview (banner
+ tile + radar + B&W + strip như cũ) · Evidence (bảng SỐ LIỆU—DEMAND EVIDENCE cột
bằng chứng/số/đọc-ra/nguồn — cột đọc-ra CHỈ ghi khi suy từ enum/tỉ lệ: trend FLAT →
"giành phần, không đón sóng", chênh ≥5× → "ăn theo cú trúng"; + bảng câu hỏi khán giả
like cao nhất + theme comment — nguyên văn gaps.json) · Full report (iframe báo cáo
gộp 8 phase, nạp LƯỜI khi mở tab — Audience Canvas và mọi tầng NGHĨA nằm ở đây, vì
canvas là nội dung LLM/tay không có trong artifact JSON). (3) General có 3 thị trường
mà dashboard chỉ hiện 2 → pills liệt kê ĐỦ danh bạ (mapped trước), market chưa gán dự
án hiện khối "Chưa gán dự án nghiên cứu — bấm New report" + nút New report (KHÔNG nút
Run mồ côi project None — test ghim). Suite 101 pass; kiểm HTML thật: 4 pill
All/US/SPAIN/KOREA, 3 tab, câu hỏi thật 750 like, iframe data-src đúng.
