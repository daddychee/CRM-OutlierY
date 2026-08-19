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

## 18/08 (tiếp 4) — 4 tab chuẩn + diễn giải hover

User chốt bộ tab cuối: **Overview / Audience / Winning Format / Positioning** + "giải
thích không ghi cứng, đưa chuột vào mới hiện". Làm:
- 3 tab NGHĨA nhúng ĐÚNG MỤC báo cáo gộp qua anchor sẵn có trong HTML (id p0..p8):
  Audience → #p1 (evidence + Audience Profile Canvas đều nằm Phase 1), Winning Format
  → #p4, Positioning → #p3; iframe nạp LƯỜI khi mở tab (secTab hết khóa cứng 'full').
  Tầng NGHĨA sống trong báo cáo — dashboard KHÔNG chép lại (một nguồn sự thật).
- Fallback: snapshot không có báo cáo gộp HTML (Run mới chỉ sinh artifact JSON) → tab
  Audience rơi về bảng gaps/demand thật (câu hỏi + theme + bảng bằng chứng), 2 tab
  NGHĨA ẨN + ghi chú "canvas sinh khi build báo cáo" — test ghim.
- DIỄN GIẢI → HOVER (title + class co-tip cursor:help): banner chỉ còn chip + headline
  + ⓘ (đoạn Pipeline/mũi nhọn/điều kiện vào title); 5 tile bỏ dòng chú giải (vào
  title); Best&Worst bỏ cột "Vì sao" (vào title từng hàng). Tab Evidence/Full report
  nghỉ (nội dung đã nằm trong Audience #p1 + nút Read report ở header).
Suite 102 pass; kiểm HTML thật: đúng 4 tab, 3 anchor, 1 title Pipeline, 0 đoạn in cứng.
CÒN TREO mạch này: khi có 19_build_bao_cao.py + bao_cao_writer (NGHĨA vào JSON) thì
Audience/WF/Positioning đổi từ iframe sang render native + Run tự build báo cáo HTML.

## 18/08 (tiếp 5) — 3 tab NGHĨA diễn giải lại NATIVE (hết nhúng iframe)

User bác cách nhúng: "Audience/WF/Positioning phải diễn giải như tab Overview chứ
không phải show trong báo cáo — cắt ra, diễn giải lại". Làm bản native trọn:
- **Winning Format** — 100% từ analysis.json: bảng câu mở đầu title thắng (openers,
  hover = ví dụ title thật) · khuôn title (templates) · chip từ CAPS (emphasis) ·
  bảng từ/cụm/tag LIFT cao gộp 3 nguồn, sig FDR xếp trước có dấu ✓.
- **Positioning** — decision2 (BEACHHEAD CHỌN + reason) + bets.json (bảng bets kèm
  verdict STRONG accent, hover = excess/tập trung/tuổi) + các card Phương án A/B/C +
  Anti-positioning CẮT từ báo cáo gộp.
- **Audience** — Audience Profile Canvas CẮT từ báo cáo (bảng 3 nhóm × 6 hàng, giữ
  nhãn GIẢ ĐỊNH) + bảng demand evidence + câu hỏi like cao + theme.
- Cơ chế cắt: `niche_bridge.trich_nghia()` — parser KHOAN DUNG trên HTML báo cáo do
  chính mình build (anchor p0..p8 ổn định): canvas = bảng đầu sau tiêu đề; phương án
  = các card <h4> trong #p3, cắt trước layer gate. Khối nào không cắt được → bỏ khối
  đó + ghi chú "sinh khi build báo cáo" (test ghim cả fallback không-HTML: tab vẫn
  sống bằng artifact, chỉ vắng tầng NGHĨA). bao_cao_writer ra đời thì trich_nghia
  nghỉ hưu — đọc NGHĨA từ JSON.
- Mỗi khối NGHĨA kèm link nhỏ "đọc trong báo cáo ↗" (#p1/#p4/#p3, tab mới).
Suite 103 pass (agent_api ca thiếu-artifact dời sang subniche — mục duy nhất seed
không ghi). Kiểm HTML thật: 0 iframe, canvas/WF/PA/bets đủ, 3 link báo cáo.

## 18/08 (tiếp 6) — TÁCH 2 KHỐI kiểu Content Ultimate (user chốt: "UI vẫn quá rối")

Bấm Data Analytics → trang CHỌN MODULE 2 khối (chon_module.html, đúng khuôn landing
Content Ultimate: eyebrow + h1 accent + a.card): ① Niche Research (/niche) ·
② Channel Research (/niche/kenh — route MỚI: lưới thẻ kênh danh bạ theo niche, bấm
vào trang chẩn đoán). GET /chan-doan = landing (đích alias gateway — bài học PA2b);
":9102/" → /chan-doan. Thanh trên tách theo CHẾ ĐỘ: crumb "Data Analytics / <module>"
+ select niche; tab kênh CHỈ còn ở Channel Research (trang Niche hết lẫn kênh); nút
New report mở đúng nhánh modal theo chế độ (moModal(t)). Suite 104 pass; kiểm sống 3
trang thật. Ghi chú: trang chọn module là NƠI DUY NHẤT thêm module thứ 3 sau này
(thẻ card mới), không đụng 2 dashboard.

## 18/08 (tiếp 7) — thanh trên tinh gọn theo 3 ảnh + sidebar 2 nấc + đồng nhất URL

Theo 3 ảnh user đánh dấu: (Ảnh 1) thanh trên CHỈ còn: tên module "Niche Research" +
dropdown niche + DROPDOWN THỊ TRƯỜNG + dropdown ngày báo cáo — bỏ crumb Data
Analytics, bỏ New report, bỏ General. (Ảnh 2) xóa nguyên dòng band (h1 + pill) —
KHÔNG còn "All": luôn đúng MỘT thị trường (mặc định = market đầu đã gán dự án),
đổi qua dropdown. (Ảnh 3) download gộp còn 1 HTML + 1 Excel (hết Excel đúp); nút
Run NGHỈ HƯU — pool làm mới mỗi lần báo cáo nên nút đúng là "+ New report" mở modal
nhánh Niche CHỌN SẴN thị trường (moNicheModal); market chưa gán cũng vậy.
SIDEBAR 2 NẤC (yêu cầu hệ thống): Data Analytics bấm là xổ 2 dòng con Niche
Research / Channel Research; Content Ultimate xổ 3 dòng Outline Board / Author
Extract / Writing — <details> thuần không JS, áp 5 khuôn (4 base.html + khung
gateway); khung /open nhận ?duong=<đường con> để iframe mở thẳng module (sửa
TEMPLATE nen_khung_app, không đụng main.py gateway đang dở phiên song song).
ĐỒNG NHẤT URL (user bắt 18/08 "cùng nút mà URL khác"): một nút = MỘT URL ở mọi
sidebar vì cùng một luật ở 2 nguồn (sidebar.py sb_apps_tu_claims + ds_tools gateway):
app native → /app/<slug>, app khung → /open/<slug>, DA → /data-analytics; 3 HỌ URL
này là thiết kế (native/iframe/alias) — gom về một họ URL đẹp cần bảng _ALIAS
gateway (PA3, chờ gateway sạch). Lệch thấy trên máy là TIẾN TRÌNH CŨ: đã restart
ai-agent + video-review (ăn KHONG_LAP_TOOLS niche-research + sidebar mới); to-chuc
chờ phiên song song tự restart. BẪY UNICODE mới: chuỗi tiếng Việt trong test vs
code lệch tổ hợp dấu NFC/NFD → assert in thất bại dù mắt thấy giống — so sánh phải
normalize NFC 2 vế (test_dropdown ghim). Suite 104 pass.

## 18/08 (tiếp 8) — VÁ sidebar 2 nấc: bấm tên app phải ĐIỀU HƯỚNG

User bắt bug ngay: từ RadarY bấm Content Ultimate / Data Analytics thì URL không
đổi, không ra trang đầu — vì bản 2 nấc dùng <details>/<summary>: tên app thành nút
XỔ NHÓM, nuốt mất điều hướng. Vá cả 5 khuôn: tên app trở lại LINK THẬT (Data
Analytics → /data-analytics landing 2 khối; Content Ultimate → /open/content-ultimate
trang chủ 3 card); dòng con KHÔNG cần bấm để xổ nữa — TỰ HIỆN khi đang đứng trong
app đó (DA: path /niche|/chan-doan|/bao-cao-lich-su; CU: app.slug trong khung, dòng
con active theo ?duong=); mũi tên chỉ còn là chỉ báo (xoay khi nhóm đang mở).
Luồng chuẩn: bấm tên app → sang trang đầu app → dòng con tự xổ ở đó. Kiểm sống
:9102 đủ claims (bẫy harness: sidebar chỉ render khi có X-Remote-Dept — curl thiếu
header này là tưởng sidebar biến mất). Suite 104 pass; template hot-reload, không
cần restart thêm.

## 18/08 (tiếp 9) — PA3 CHẠY THẬT: đồng nhất URL mọi nút Tools = /<slug>

User truy tiếp "4 URL của 4 app vì sao không đồng nhất". GỐC BỆNH (điều tra): gateway
có BA cơ chế route ra đời 3 thời điểm — (1) proxy generic /app/<slug>/... (app native),
(2) khung /open/<slug> (app SPA, Owner 16/08), (3) bảng _ALIAS URL đẹp cấp-1 (11 mục
chọn tay 16/08 — trong 4 nút Tools chỉ Data Analytics có). Sidebar sinh href THEO LOẠI
APP → 3 họ URL lộ ra người dùng: /app/video-review/danh-sach · /open/radary ·
/open/content-ultimate · /data-analytics.
SỬA (PA3, làm luôn vì diff NAS của phiên song song chỉ nằm vùng login/profile — vùng
alias tách bạch): (a) _ALIAS thêm /video-review → danh-sach; (b) _ALIAS_KHUNG mới
(radary, content-ultimate, niche-research) — mỗi slug một route /<slug> phục vụ CÙNG
trang khung với /open/<slug> (đường cũ giữ cho bookmark); (c) ds_tools (khung) +
sb_apps_tu_claims (sidebar.py) về MỘT luật href = /<slug>; (d) link con CU đổi
/content-ultimate?duong=... Kiểm sống 4 URL + /open cũ đều 303 login (tồn tại, hết
404). SESSION_SECRET có trong .env → restart gateway không văng phiên.
GIT: commit main.py bằng cách TÁCH HUNK (backup file đầy đủ → restore HEAD → áp lại
đúng 3 sửa → git add → trả file đầy đủ về đĩa) — stage sạch phần mình, 5 hunk NAS
của phiên song song vẫn nguyên ngoài stage. LƯU Ý: to-chuc chưa restart (phiên kia
giữ) → sidebar trang to-chuc còn URL họ cũ tới lần restart kế; test_gateway.py đang
dở tay phiên kia — test alias khung bổ sung sau.

## 18/08 (tiếp 10) — trang khung nhận sidebar ĐẦY ĐỦ (user bắt: RadarY/CU mất khối Database)

Sau khi URL về /<slug>, RadarY + Content Ultimate đi qua trang khung gateway
(nen_khung_app.html) — sidebar khung là bản RÚT GỌN từ đầu (chỉ Home + Tools +
Management), thiếu cặp tab Home/Database, New chat, Search, Recents mà mọi app
native có qua base.html. Vá MỘT khuôn phủ cả 3 app khung: chép nguyên cấu trúc
sidebar base.html sang khung — tabs Home/Database (Database chỉ Manager+ như luật
can_upload), pane Home (New chat / + Tools giữ nguyên + Search disabled + Recents
"No chats yet" + View all history → /history — phiên chat thuộc ai-agent, trang
khung không truy chéo, y hệt các app khác), pane Database (Input/Library/Gap),
JS chuyển tab y khuôn. Template gateway nạp nóng — không cần restart.

## 18/08 (tiếp 11) — New Research + snapshot lên thanh trên + KIỂM ĐẦU VÀO pipeline

Ba yêu cầu user: (1) nút là NEW RESEARCH (không phải New report) và là hành động
CHÍNH (chinh) — Read report về nút thường; tiêu đề modal đổi theo tab (New Research /
New channel report). (2) chữ "snapshot <ngày>" DỜI lên thanh trên cạnh dropdown ngày,
bỏ khỏi header khối. (3) "kiểm tra lại xem tạo research có cần nhập liệu ban đầu gì
ngoài link đối thủ" — ĐÃ KIỂM /api/run service + argparse orchestrator: đầu vào DỮ
LIỆU duy nhất = competitors.txt (niche/thị trường lấy từ danh bạ, key YouTube/LLM từ
KÉT); NHƯNG có 4 TÙY CHỌN CHẠY bị UI giấu — nghĩa là các lần bấm nút trước chạy
KHÔNG có tầng LLM (namer/auditor/plan/summary) và không deepdive. Form New Research
giờ có 4 checkbox: Quét comment (mặc định BẬT) · Tầng LLM (mặc định BẬT) · Deepdive
transcript (tắt) · Force (tắt); route + niche_run chuyển nguyên 4 cờ sang service
(test ghim mặc định + tường minh). LƯU Ý: resume (pool trống) không nhận cờ — cờ áp
cho lần chạy trọn.
BUG BẮT ĐƯỢC KHI KIỂM SỐNG: mặc định thị trường rơi vào SPAIN (mapped chưa snapshot,
đứng trước US theo alphabet) → trang mặc định TRỐNG TRƠN — sửa _uu_tien: thị trường
CÓ BÁO CÁO xếp trước. Suite 105 pass; kiểm HTML thật: banner về, US selected, chip
snapshot trên thanh, 4 checkbox đủ.

## 18/08 (tiếp 12) — REPORT LIST cuối mỗi kênh (Channel Research)

User chốt: cuối trang mỗi kênh cần danh sách báo cáo để đọc full + xem bản cũ.
Thêm khối "Reports" dưới thẻ chẩn đoán: mọi bản ghi của kênh (ngày · tên · kỳ ·
người chạy), bấm dòng = xem lại ngay trên dashboard (?id=), nút Full analysis từng
bản mở trọn bảng phán quyết (/bao-cao-lich-su/<id>), bản đang mở đánh dấu "đang
xem". Suite 106 pass; kiểm sống kênh OUTLAND thật. LƯU Ý PHIÊN SONG SONG: commit
này CHỈ gồm dashboard.html + sổ — dashboard.py/test_* đang mang luật mới
"thị trường thuộc từng ngách (thi_truong_cua)" của phiên kia chưa commit; assert
report-list tôi thêm trong test_dashboard.py sẽ đi cùng commit của phiên đó.

## 19/08 — NEW RESEARCH PHƯƠNG ÁN 2 (pool sẵn có RadarY) + BƯỚC CHECK API

User chốt 2 việc: (1) tạo research CHỈ chạy từ POOL SẴN CÓ theo ngách × thị trường
(bỏ dán tay — user "thiên về chỉ làm phương án 2"); (2) sau Run analysis → bước 1
"kiểm tra API khả dụng" → xong mới báo Researching.
• POOL SẴN CÓ: RadarY V3 là nhà của pool — workspace (Data Pool) đã gắn ngach/market
  theo MÃ DANH BẠ + API /api/workspaces (đếm kênh) + /workspaces/{id}/channels.
  Cầu mới src/radary_bridge.py (đọc loopback kèm claims, lệ không-import-chéo):
  ds_pool lọc đúng ngách×thị trường, kenh_cua_pool dựng dòng 'Title | URL' từ kênh
  ACTIVE. Modal: select pool (tự nạp theo GET /niche/pool khi mở tab/đổi niche-tt)
  + nút Manage pools → /radary; POST tao-report nhận pool_ws → server lấy kênh từ
  RadarY đổ vào luật cộng dồn sẵn có (`pool` text GIỮ làm đường API/script — UI
  không lộ). Kiểm sống thật: N-LIFE-IN × TT-US → pool "LIFE IN — US · 63 kênh".
• CHECK API: niche_run.kiem_khoa đọc cấp phát KÉT qua gateway loopback
  /api/cau-hinh/api-khoa/niche-research — ĐÚNG nguồn khoa_v3 của service sẽ dùng
  lúc chạy; CHỈ trả boolean theo việc (quet_kenh luôn, phan_tich khi bật LLM,
  lay_transcript khi deepdive), không lộ key (test ghim). JS: Run analysis →
  "Đang kiểm tra API…" → thiếu thì dừng + chỉ chỗ cấp (General › API Keys) →
  đủ thì "API sẵn sàng — Researching…" + poll "Researching… Xs".
• PHÁT HIỆN VẬN HÀNH nhờ preflight: cấp phát niche-research trong KÉT đang RỖNG
  cả 3 việc (curl gateway thật xác nhận khoa=[]) — bấm Run lúc này là 503; Owner
  cần cấp khóa YouTube (Quét kênh) + LLM (Agent phân tích) ở General › API Keys.
Suite 113 pass (test_radary_bridge mới 5 + kiem-api 2).

## 19/08 (tiếp) — modal theo MODULE (user bắt "New Research dính cả Channel")

Sau khi tách 2 khối, modal vẫn là bản chung 2 tab Niche/Channel → đứng Niche Research
thấy form Channel và ngược lại. Sửa: MỖI MODULE CHỈ RENDER ĐÚNG NHÁNH FORM CỦA MÌNH
theo che_do (Niche → nr-niche + tiêu đề New Research; Channel → nr-kenh + New channel
report), bỏ hẳn tab chuyển trong modal + hàm nrTab; moModal mở là dùng, nhánh niche
tự nạp pool. Test đổi theo: exclusivity 2 trang (nr-niche ↔ nr-kenh không lẫn) +
trang Niche hết chứa tên kênh. Suite 113 pass; kiểm sống cả 2 trang.

## 19/08 (tiếp 2) — SỰ CỐ CHẠY ĐÚP LifeIn_ES + VÁ ĐUA _spawn

User hỏi "có phải tôi đang tạo báo cáo 2 lần cho Life In Spain?" — soi tiến trình:
ĐÚNG, 2 orchestrator giống hệt (run LifeIn_ES --force --deepdive --llm) sinh CÙNG
GIÂY 01:58:35. GỐC BỆNH: guard chống chạy đúp trong _spawn của service niche-research
bị đua TOCTOU — kiểm _procs TRONG lock nhưng Popen + đăng ký NGOÀI lock → 2 POST
/api/run cùng lúc đều thấy "chưa chạy", cả hai spawn, bản ghi sau đè bản trước nên
service chỉ biết 1 con (con kia mồ côi, /api/stop không với tới). (Nguồn 2 POST cùng
giây phía client chưa tái hiện được — guard server giờ chặn tuyệt đối nên vô hại.)
KẾT CỤC MAY: cả 2 chạy XONG trót lọt trước khi kịp can thiệp; vì cùng ghi MỘT bộ
file (mỗi stage ghi trọn file, bản sau đè) nên đĩa còn đúng MỘT bản lành — "giữ 1
bỏ 1" tự đạt; thiệt hại = đốt đôi quota YouTube/LLM một lần. VÁ: _GiuCho giữ chỗ
trong _procs NGAY TRONG LOCK lúc kiểm (poll()=None để status coi là đang chạy trong
cửa sổ spawn) + Popen lỗi thì trả chỗ (không kẹt 'running'); restart :9113 lúc rảnh.
Snapshot ES đóng băng qua bridge (done_moi=true); dashboard TT-SPAIN sống: PHÁN
QUYẾT VÀO · 62/100, verdict pipeline "GO — enter via Vida real y tradiciones…".

## 19/08 (tiếp 3) — TẦNG 1 BUILDER BÁO CÁO GỘP HTML chạy end-to-end (user: "code đến cuối")

Trả lời "thiếu báo cáo HTML do đâu": pipeline 20 stage kết ở 18_build_report (Excel +
SUMMARY) — bản HTML của US là bản SOẠN TAY 18/08; máy sinh chưa tồn tại. ĐÃ CODE:
• apps/niche-research/scripts/19_build_bao_cao.py — HTML gộp 8 phase THUẦN PY từ
  artifact niche-data: anchor tq/p0..p8/honesty như bản mẫu; mỗi phase 3 lớp SỐ→
  NGHĨA→GATE; bảng dài trong <details>; số VN, thiếu nguồn ghi "nguồn thiếu";
  tầng NGHĨA = SLOT nhãn "GIẢ ĐỊNH / CHỜ WRITER" (không bịa) — RIÊNG artifact LLM
  pipeline đã sinh khi --llm (execution_plan / dna / SUMMARY.md) nhúng NGUYÊN VĂN
  kèm nhãn nguồn; mục honesty ghi van chống bịa + nguồn từng mục. Ghi nguyên tử
  tmp+replace vào Report/BAO-CAO-8-PHASE.html.
• Móc vào bridge: niche_run._snapshot chạy builder TRƯỚC snapshot.py (best-effort)
  → từ nay MỌI run tự có HTML; snapshot.py quét Report/ nên tự vào sổ bao_cao.
• Backfill ES end-to-end THẬT: build + snapshot lại (id 2026-08-18 — snapshot dấu
  ngày UTC) → bao_cao = [BAO-CAO-8-PHASE.html, xlsx, SUMMARY.md]; dashboard Spain
  đủ Read report/HTML/Excel + link "đọc trong báo cáo ↗"; mở inline 200.
• BUG TỰ BẮT khi kiểm: builder dùng nháy ĐƠN class='layer' còn bound trich_nghia
  chỉ tìm nháy kép → extractor vớ nhầm bảng cụm P2 thành "canvas" — vá bound ĐA MỐC
  (class="layer / class='layer / </section>); kiểm lại: ES trả {} (đúng — canvas chờ
  writer), US vẫn đủ canvas + phương án. Suite 113 pass.
CÒN (tầng 2, đợt riêng): bao_cao_writer [LLM] sinh NGHĨA vào JSON theo schema —
builder đọc JSON đó đổ vào slot thay nhãn chờ; US giữ bản mẫu soạn tay làm chuẩn
đối chiếu (không ghi đè — lệ mockup).

## 19/08 (tiếp 4) — TẦNG 2 bao_cao_writer [LLM] — BÁO CÁO HOÀN THIỆN end-to-end

User chốt "code luôn tầng 2": scripts/20_bao_cao_writer.py — LLM viết tầng NGHĨA
ra niche-data/bao_cao_nghia.json THEO SCHEMA (tq headline+đoạn · canvas 3 nhóm × 6
hàng · phương án A/B/C + anti · winning_format · tổng hợp + falsifiers rút lui).
Đầu vào là DIGEST artifact chắt sẵn (không transcript thô — dna/gaps đã distill);
LUẬT NEO trong prompt: mỗi luận điểm kèm số/chuỗi có thật trong digest, thiếu căn
cứ phải ghi 'GIẢ ĐỊNH:'; validate_json + kiểm tối thiểu (canvas ≥4 hàng, ≥2 phương
án) mới ghi file (nguyên tử). Khóa: KÉT khoa_v3.env_llm (việc phan_tich — Owner ĐÃ
cấp phát, writer báo 'khoa LLM: KET'); KÉT thiếu → thử .env V2 như pipeline cũ.
Builder đổ NGHĨA vào slot với badge "DIỄN GIẢI — bao_cao_writer [LLM] · glm · giờ
sinh"; thiếu file → slot giữ nhãn chờ như tầng 1. Chuỗi snapshot bridge: WRITER →
BUILDER → SNAPSHOT (mỗi best-effort). Khối NGHĨA dùng markup nháy kép đúng khuôn
extractor — trich_nghia cắt được từ báo cáo máy sinh y như bản mẫu tay (vá thêm
marker cắt phương án 2 kiểu nháy).
ĐO THẬT trên LifeIn_ES: max_tokens 4096 CỤT JSON giữa chừng → nâng 8192 (ghi chú
trong code); chạy lại DONE (provider=glm), build + snapshot 2026-08-19; extractor
trả canvas 3 nhóm (neo số thật: 9.659 comment · 457 câu hỏi · 249 like) + 3 phương
án + anti 5 mục; US bản mẫu tay nguyên vẹn. Suite 113 pass.
