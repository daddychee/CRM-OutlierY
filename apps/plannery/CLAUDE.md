# CLAUDE.md — PlannerY (tool điều phối sản xuất video)

> **BẢN V3 (19/08/2026)** — copy từ `C:\OutlierY\apps\plannery` (HEAD 275f0a7)
> vào nền OUTLIERY v2: cổng **9116**, dữ liệu `PLANNER_DATA_DIR=data/plannery`
> (bản sao — hệ thật :8123 vẫn là nguồn thật tới cutover), SSO Actions-first +
> vá bẫy users.json thắng header + đóng cửa quản trị nội bộ khi SSO.
> Nhật ký tích hợp + thang quyền: `docs/APPS.md` (app 5/6). 4 chỗ đăng ký:
> PORTS.md · nen/rules/apps.json · nen/rules/phan_quyen.json · start-all.ps1
> (+ `_ALIAS_KHUNG` gateway). Khối dưới đây là sổ V2 gốc — giữ làm sử liệu.

> **ĐÃ LIVE (13/07/2026)**: https://plannery.45.32.107.108.sslip.io — VPS Ubuntu
> 22.04 (45.32.107.108), systemd `plannery.service` chạy `/opt/plannery` như user
> `plannery`, cổng 8123 sau nginx (basic-auth → header `X-Remote-User` → role).
> Quản trị gốc: user nginx `admin` (ADMIN_USERS). Auth model + cách thêm người:
> DEPLOY.md. Deploy lại: `rsync planner/ server.py ui/index.html` lên /opt/plannery
> rồi `systemctl restart plannery`. SSH key đã cài (root@45.32.107.108).


Hướng dẫn hành vi + bối cảnh dự án cho Claude. Repo đã có **phần logic tính**
(`planner/` + `tests/`) và **UI local** (`server.py` + `ui/`, chạy bằng
`Start.command`, lưu kế hoạch vào `data/plan.json`) — xem README.md.
Mọi phiên làm việc sau đọc file này trước khi làm gì khác.

**Đánh đổi:** các nguyên tắc thiên về thận trọng hơn tốc độ. Việc vặt (typo, đổi tên biến
cục bộ) dùng phán đoán — nhưng phần dữ liệu nhân sự (Nguyên tắc 6) áp dụng nguyên vẹn.

---

## Bối cảnh dự án

Tool cho **team sản xuất video YouTube** của user: tính khối lượng công việc, dự đoán
**điểm rơi bàn giao** giữa các khâu, và xếp nhân sự vào dự án. Một chu trình khép kín:

```
Kênh YouTube (team Kinh doanh — đặt tần suất đăng video)
  → Team Content   (sản xuất nội dung/kịch bản phù hợp)
  → Team Editor    (dựng video)
  → bàn giao lại team Kinh doanh (đăng lên kênh) — hoàn tất một chu trình
```

Ba bài toán cốt lõi tool phải giải:

1. **Năng lực sản xuất theo từng người** — mỗi nhân sự năng suất khác nhau, nhập được
   năng suất của từng người làm đầu vào tính toán.
2. **Điểm rơi bàn giao** — từ năng suất + khối lượng việc, tính thời điểm sản phẩm được
   bàn giao cho khâu tiếp theo, **tính cả vòng feedback/chỉnh sửa** (không phải làm một
   lần là xong).
3. **Xếp người linh hoạt** — kéo-thả nhân sự giữa các dự án; khi thêm dự án mới phải
   thấy ngay tác động lên lịch của các dự án đang chạy.

Người dùng là quản lý sản xuất và trưởng các team. Đây là công cụ **lập kế hoạch**,
không phải công cụ chấm công/HR/quản lý task chi tiết.

## Đã chốt (13/07/2026)

- **Phạm vi tool**: KHÔNG theo dõi tiến độ sản xuất từng video — user đã có tool
  tracking riêng, dùng song song. Tool này chỉ lo: **giao task dựa trên khả năng
  nhân sự cho khớp lịch kinh doanh** (capacity planning + gợi ý điều người + lịch
  tuần). Không build board trạng thái video. Tính lại giữa chừng vẫn theo snapshot
  "còn N video, bắt đầu từ ngày D" (đối chiếu số N từ tool tracking).
- **Đơn vị năng suất (v3 — content đổi theo yêu cầu user)**: đơn vị THEO KHÂU —
  **content: kịch bản/ngày** (một kịch bản là một unit, KHÔNG phụ thuộc thời lượng
  video; thời gian 1 kịch bản = 1 ÷ năng suất) và **editor: phút video hoàn
  thành/ngày** (thời gian 1 video = thời lượng ÷ năng suất; thời lượng khai ở cấp
  dự án — giải luôn câu hỏi hệ số video dài/ngắn cho khâu dựng).
- **Chỉ số nhân sự (v2, sửa cùng ngày sau test UI — bỏ khái niệm "hiện tại")**:
  mỗi người 2 con số — **chuẩn tuyển dụng** (thường quy; Leader + HR đặt khi tuyển)
  và **tuần trước** (content: số kịch bản được tính ÷ 6; editor: Σ phút video được
  tính ÷ 6 — KHÔNG nhập trực tiếp,
  sinh từ **Tổng kết tuần**: cuối tuần Leader đánh dấu ✓/✗ từng video trên lịch
  đăng; video ✗ thì tool hỏi ngược *do content hay do editor* — lỗi khâu nào trừ
  khâu đó, khâu kia KHÔNG bị ảnh hưởng). **Lịch phân phối tính theo CHUẨN (KPI)**
  — sửa 13/07 sau khi user duyệt lịch tuần: kế hoạch không tự hạ theo người dưới
  chuẩn, "tuần trước" CHỈ để cảnh báo. Cảnh báo Leader/HR khi tuần trước
  **thấp hơn thường quy** (mọi mức dưới 100%), hiển thị rõ % đạt = tuần trước ÷
  thường quy. Không ramp tự động theo thâm niên.
- **Kho kịch bản sẵn**: dự án có ô "số kịch bản đã sẵn khi bắt đầu" — k video đầu
  bỏ qua khâu content, editor có việc ngay từ ngày 1 (mô hình content đi trước).
- **Gợi ý điều người**: theo cung–cầu *phút/tuần* từng khâu (cầu = lịch up × thời
  lượng; cung = Σ năng suất người trong dự án — người chia sẻ nhiều dự án phải ghi
  chú rõ, số chuẩn cuối cùng là mô phỏng), kèm what-if chạy engine thật. Đề xuất có
  dạng "thêm/rút NGƯỜI khỏi dự án" (không còn %). Tool **đề xuất trước** thành bản
  nháp (chip nét đứt chờ xác nhận); user ✓ chấp nhận / ✗ bỏ — chưa xác nhận thì
  chưa có hiệu lực vào lịch. Nguyên tắc 2 giữ nguyên: không bao giờ tự áp dụng.
- **Trình tự build (chốt với user)**: dựng **UI mẫu số liệu minh hoạ** để duyệt
  luồng trước (`ui/prototype.html`), duyệt xong mới code engine v2 + nối thật.
- **Ngày đăng từng video + tên nội dung**: lịch up (video/tuần) chỉ để sinh ngày
  đăng **mặc định**; leader sửa được ngày đăng của từng video và đặt **tên nội dung**
  (mặc định ĐỂ TRỐNG — leader tự nhập cụ thể) để content/editor theo dõi trên lịch
  tuần. Engine so bàn giao với ngày đăng cụ thể của từng video (không phải tần suất
  đều) và từ đó tính ngược nhu cầu phân bổ người.
- **Loạt chốt bổ sung (13/07, đợt cuối ngày)**: (1) sửa/thêm kênh có hộp xác nhận;
  mọi thao tác XOÁ (nhân sự/dự án/kênh/video) phải nhập **code quyền** — tạm
  `123ABC`, hằng `DELETE_CODE` trong `ui/index.html`, chống xoá nhầm chứ chưa phải
  bảo mật thật; (2) đổi ngày đăng → **thứ tự tập tự sắp lại theo ngày** (renumber);
  (3) nút **★ Ưu tiên** gán cho TỪNG VIDEO (sửa cùng ngày — không phải cấp dự
  án/kênh) — engine xếp: rảnh sớm nhất → dự án đang làm → video ★ → EDD;
  (4) màu chọn từ **palette 10 màu cố định**, bỏ color picker tự do; (5) nhãn viết hoa chữ đầu (Content/Editor), cỡ chữ nền 15px; (6) Tổng kết
  tuần chỉ khai video ✗ + tự sinh **Báo cáo tuần** (lưu lịch sử); (7) **Chốt ngày**:
  leader xác nhận cuối ngày từng người, ai ✗ → gợi ý cứu tiến độ (thêm người rảnh /
  dời ngày đăng / bớt vòng feedback — có nút áp dụng, tool không tự làm).
- **Phân quyền + bảo vệ dữ liệu (13/07, chuẩn bị VPS)**: 5 vai trò (Quản trị / HR /
  Leader / Nhân sự / Xem — ma trận trong SPEC.md mục 6), đổi bằng mã `ROLE_CODES`;
  code xoá `123ABC` cũ đã được THAY bằng hệ vai trò này. Bản local gate ở UI —
  lên VPS phải chuyển enforcement về server. Backup: mỗi lần lưu giữ bản trước +
  kho `data/backups/` 40 bản + nút ⬇ Sao lưu tải JSON về máy. Đã BỎ nút nạp dữ
  liệu mẫu (user chạy dữ liệu thật). Nhãn ngày đăng trên lịch tuần = "Kênh · Tên
  tập" (khớp bảng kế hoạch).
- **CLONE 2 KHÂU (14/07 — nâng từ mô hình cờ has_clone)**: kênh có `clone_langs:
  [{name, versions}]` (số version biến số theo ngôn ngữ; migrate has_clone→[{Bản
  dịch,1}]). Mỗi tập gốc × Σversions = task clone; mỗi task = **dịch** (content
  `clone_rate` KB/ngày, dịch RIÊNG từng version) → **dựng lại** (editor `clone_rate`
  video/ngày, sau khi dịch xong). Content cũng có ô clone. Khối CLONE cuối lịch
  tuần tách 2 nhóm Dịch/Dựng; clone_done + clone_translated per-task (lang#ver);
  chốt ngày xác nhận riêng dịch/dựng. Node-test logic 2 khâu trước khi deploy.
- **CLONE (13/07, bản cũ — đã thay bằng 2 khâu ở trên)**: kênh
  có checkbox `has_clone`; số tập clone TỰ TRÙNG danh sách tập của kênh.
  Clone không có lịch đăng, KHÔNG qua engine EDD. Quy tắc (sửa lần 3 cùng ngày):
  người có role Clone (editor + `clone_rate` video/ngày, hiện tag "Clone") **ưu
  tiên việc dự án trước, giờ rảnh mới nhận clone** — chỉ ngày không có block lịch
  chính, tối đa clone_rate/ngày, chia đều xoay vòng; tập tự chọn theo thứ tự sản
  xuất kênh chính, ★ lên đầu; không xếp hết → ⚠ còn X tập. Khối CLONE cuối lịch
  tuần, block ghi tên tập. Tính ở UI (công thức tất định, SPEC 2a-bis); `is_clone`
  cũ đã gỡ khỏi engine, dữ liệu kiểu cũ tự migrate.
- **Kịch bản + feedback (13/07, đợt tối)**: (1) mỗi tập có tick **✓ đã có KB**
  (team viết KB tuần trước cho tuần sau) → bỏ khâu content của tập đó; ô "kho kịch
  bản sẵn" ĐÃ BỎ khỏi UI (engine giữ field, dữ liệu cũ tự migrate thành tick);
  (2) **sửa/feedback phải xong trong ngày** (bản cuối sau 2 vòng sửa cùng ngày):
  vòng sửa vắt ngày bị NÉN về cuối ngày, phần dư = **QUÁ GIỜ** (`Segment.overtime`,
  UI hiện ⚡OT) — nhân sự chấp nhận OT, không dời sang hôm sau; sửa sẵn sàng muộn
  (chờ feedback) thì "đặt chỗ" để giờ trống nhường việc khác, block làm chính TÁCH
  quanh chỗ đặt (cơ chế reservation) — test tay riêng, không phút nào bỏ trống.
- **Phân quyền server-side + chuẩn bị VPS (13/07, đợt cuối)**: mã vai trò chuyển
  từ client vào `data/roles.json` (server xác thực /api/role + header X-Role-Code;
  ma trận quyền theo vùng — check_permission trong server.py); khoá `_rev` chống
  ghi đè chéo (409 → client tự reload); ghi nguyên tử + threading.Lock + trần body
  5MB; HOST/PORT qua env PLANNER_HOST/PLANNER_PORT. Hướng dẫn VPS: **DEPLOY.md**
  (systemd + Caddy reverse proxy + HTTPS + cron backup). Clone tồn đọng tự trôi
  sang tuần sau (phân bổ neo tuần hiện tại, trần 8 tuần).
- **Video GẤP (14/07 — crash schedule, test-first)**: Video có `urgent`+`assigned_editors`;
  nút ⚡ mỗi kênh đề xuất N editor (thêm người nhanh nhất tới khi kịp hạn) → user ✓.
  Engine pre-pass xếp trước, ưu tiên cao nhất (đẩy việc thường lùi); khâu editor
  CHIA N người song song (effort = phút ÷ Σnăng suất), content 1 người không chia,
  bỏ vòng feedback. Đóng gói output gộp segment theo người → hiện N editor. 26 test.
- **Giao diện**: theo design system của Content Ultimate, tab Outline Extract
  (`../Content Ultimate/src/oe/board.html`) — dark mặc định + light tự động,
  accent vàng `#E3AC45`, số liệu font mono; chi tiết token trong SPEC.md mục 6.
- **Best Performance của dự án**: mỗi dự án lưu kỷ lục khâu editor
  `{ngày-công/video, tên editor (chuỗi — GIỮ NGUYÊN khi người đó nghỉ/bị xoá),
  ngày ghi nhận}`; chỉ thay khi có số TỐT HƠN. Nguồn: **nhập tay** từ tool tracking
  (số đã xảy ra thật); tool chỉ **nhắc** khi số kế hoạch (thời lượng ÷ năng suất
  hiện tại) của một editor trong dự án tốt hơn kỷ lục — không bao giờ tự ghi.
  Công dụng: đối chứng trên thẻ dự án + xếp hạng gợi ý + tie-break chia unit
  (hai người cùng rảnh → người giữ kỷ lục nhận unit; EDD vẫn quyết thứ tự thời gian).
- **UI hướng tới**: bảng dự án + kéo-thả nhân sự (đã có), thêm **lịch tuần**
  (hàng = người, cột = T2–T7, block = unit nguyên đang làm, ô trống = rảnh; người
  thuộc nhiều dự án thấy unit các dự án xen kẽ theo EDD) và panel gợi ý. Lịch tuần
  có hàng **"Ngày đăng"** — bấm một video để xem ai viết / ai dựng / kịp hay trễ,
  các block liên quan được tô sáng.
- **Vòng feedback**: mỗi khâu N vòng (cấu hình theo dự án); mỗi vòng = thời gian *chờ*
  feedback + thời gian *sửa*, **cả hai đều tính vào lịch** (ngày làm việc). Trong lúc
  chờ, người đó làm việc khác — chờ không chiếm công suất. Vòng sửa của video nào do
  chính người làm video đó sửa.
- **Lịch làm việc**: Thứ 2 – Thứ 7, nghỉ Chủ nhật.
- **Chia tải (v2 — THAY mô hình %, chốt cùng ngày sau khi user test UI)**: không có
  % công suất — mỗi kịch bản/video là một **unit nguyên**, một người làm trọn một
  unit rồi mới nhận unit kế (chỉ ngắt khi chờ feedback; sửa quay về đúng người cũ).
  Người thuộc nhiều dự án = MỘT hàng đợi trộn unit các dự án; khi rảnh ưu tiên
  unit thuộc **dự án "đang làm"** của mình (chốt 13/07 — editor không nhảy dự án
  khi dự án nhà còn việc; trường `home_project_id`, đứng TRÊN kỷ lục khi chọn
  người), trong đó lấy unit có **ngày đăng gần nhất (EDD)**, hoà → video số nhỏ,
  rồi thứ tự dự án.
  Không ghim unit cho người cụ thể (thêm sau nếu thấy thiếu). Hệ quả engine v2:
  mô phỏng **chung toàn bộ dự án một lượt** (một hàng đợi/người), không còn tính
  từng dự án độc lập; cảnh báo "tổng % > 100" bỏ — thay bằng cảnh báo trễ từ
  mô phỏng + màn dò cung–cầu phút/tuần.
- **Luồng nhập liệu**: bắt đầu từ dự án — Dự án → Kênh (đặt tên sau được) → số video
  cần → lịch up (video/tuần) → tính toán ra lịch bàn giao kèm tên nhân sự.
- **Dự án chen ngang / tính lại**: không mô hình % thay đổi theo thời gian; lập
  snapshot mới (số video còn lại + ngày bắt đầu mới + % chia lại) rồi tính lại toàn bộ.

## Những điều CHƯA chốt — hỏi user trước khi tự quyết

Đụng đến mục nào dưới đây mà chưa được chốt thì dừng lại hỏi, đừng chọn âm thầm:

- ~~Phạm vi / thuật ngữ dự án–kênh~~ → TÁI CẤU TRÚC 13/07 (chiều): **KÊNH là dây
  sản xuất hoàn chỉnh** — toàn bộ cấu hình (bắt đầu, thời lượng, kho kịch bản,
  vòng feedback, kỷ lục, danh sách tập) nằm Ở KÊNH; dự án chỉ là NHÓM (tên +
  kênh + đội nhân sự kéo-thả). Engine: mỗi kênh = một `Project` (id `duAn::kenh`,
  `group_id` = dự án); phân công người ↔ dự án nhân bản ra mọi kênh; "đang làm"
  trỏ dự án khớp mọi kênh trong đó (test riêng). Schema v3 — SPEC.md mục 2.
- **Vòng sửa theo đơn vị mới**: đang giữ "ngày cố định mỗi vòng"; có nên tỷ lệ theo
  thời lượng video không — đổi khi có số liệu thật nói khác.
- **UI thật chưa theo kịp engine v2**: engine v2 + server API đã chuyển sang schema
  SPEC.md (13/07/2026), nhưng `ui/index.html` vẫn là form v1 (ngày-công/video, %)
  — sẽ báo lỗi input khi dùng. Việc kế tiếp: build lại UI theo bản mẫu
  `ui/prototype.html` + design system Content Ultimate (SPEC.md mục 6), gồm cả
  luồng Tổng kết tuần (SPEC mục 3) chưa có ở đâu ngoài spec.
- **Người feedback**: ai feedback chưa được mô hình như một nguồn lực — hiện chỉ tính
  thời gian chờ cố định mỗi vòng.
- **Stack & nơi chạy**: hiện chạy local theo "Thói quen nhà" (Python thuần + web UI,
  server chỉ bind 127.0.0.1). Chưa chốt có lên VPS cho cả team dùng chung không —
  nếu lên VPS phải hỏi "ai được xem gì" trước (nguyên tắc 6).

---

## Nguyên tắc

### 1. Think Before Coding — hỏi nghiệp vụ trước, code sau

**Đừng đoán nghiệp vụ sản xuất video. Đừng giấu chỗ chưa hiểu. Nói rõ đánh đổi.**

- Nêu giả định rõ ràng trước khi code; không chắc thì hỏi — đặc biệt với mô hình tính
  (năng suất, feedback, lịch) vì sai mô hình là sai toàn bộ con số phía sau.
- Nhiều cách hiểu một yêu cầu → trình bày các cách kèm đánh đổi, đừng tự chọn âm thầm.
- Bài toán xếp lịch rất dễ phình thành "giải thuật tối ưu hoá" — nếu có cách đơn giản
  hơn (công thức tính tay được, quy tắc xếp tuần tự) thì nói ra, phản biện khi hợp lý.
- Danh sách "Chưa chốt" ở trên là checklist sống: chốt được điều gì với user thì
  chuyển nó xuống mục "Đã chốt" (tạo mới khi cần) kèm ngày chốt.

### 2. Tool tính — NGƯỜI quyết

**Tool trình con số và cảnh báo; quyết định xếp ai vào đâu là của người quản lý.**

- Mọi ngày bàn giao, % tải, cảnh báo trễ là kết quả **tính tất định** từ input
  (năng suất, khối lượng, lịch): cùng input ra cùng output, và mỗi con số phải
  **truy ngược được** — user hỏi "vì sao ra ngày này?" thì tool chỉ ra được phép tính.
- Không auto-assign: tool được phép *gợi ý* người phù hợp, nhưng thao tác gán là
  kéo-thả của user. Thêm dự án mới → chỉ tính lại lịch và cảnh báo xung đột, **không
  tự động di chuyển nhân sự** khỏi dự án đang chạy.
- Quá tải / deadline không khả thi → hiển thị cảnh báo rõ ràng, không âm thầm giãn
  lịch cho "đẹp số".
- Áp dụng cho cả chính bạn (Claude): muốn biết lịch ra sao với bộ input nào đó, chạy
  phần tính toán mà xem — không "ước lượng" rồi trình bày như đã tính.

### 3. Simplicity First — kỷ luật MVP

**Code tối thiểu giải đúng bài toán. Đây là máy tính lập lịch, không phải ERP.**

- MVP = nhập nhân sự + năng suất, nhập dự án + khối lượng, tính điểm rơi (gồm vòng
  feedback), kéo-thả phân công. **Chưa cần**: chấm công, notification, phân quyền
  nhiều cấp, tự động tối ưu phân bổ, tích hợp lịch/công cụ ngoài — đừng build trước
  khi được yêu cầu rõ.
- Mô hình tính đơn giản mà giải thích được > giải thuật thông minh khó giải thích.
  Chỉ nâng cấp khi mô hình đơn giản **sai thật trên số liệu thật** của team.
- Không abstraction cho code dùng một lần; không tham số/config chưa ai hỏi;
  không error-handling cho tình huống không thể xảy ra.
- Viết 200 dòng mà rút được còn 50 → viết lại. Tự hỏi: "kỹ sư có kinh nghiệm có bảo
  cái này overcomplicated không?" — có thì đơn giản hoá.

### 4. Surgical Changes — format dữ liệu là hợp đồng

**Chỉ động vào phần bắt buộc phải sửa. Chỉ dọn rác do chính mình tạo ra.**

- Khi đã có schema dữ liệu (nhân sự, dự án, phân công, lịch), **đổi schema là việc
  lớn**: nói rõ trước, kèm đường migrate — vì file kế hoạch là thứ team người thật
  đang dùng hằng ngày, đổi format âm thầm là mất dữ liệu của họ.
- Không "cải thiện" code/comment/format lân cận; không refactor thứ không hỏng;
  giữ style hiện có kể cả khi bạn sẽ viết khác.
- Import/biến/hàm thừa do thay đổi CỦA BẠN tạo ra → xoá; dead code có từ trước →
  báo, để nguyên.
- Phép thử: mỗi dòng diff truy ngược được về yêu cầu của user.

### 5. Goal-Driven Execution — lịch phải kiểm được bằng tay

**Định nghĩa tiêu chí "xong" đo được. Lặp cho tới khi kiểm chứng thật.**

- Logic tính điểm rơi verify bằng **ví dụ tính tay**: team giả với năng suất biết
  trước → ngày bàn giao kỳ vọng tự tính ra giấy được → viết test khớp con số đó rồi
  mới code. "Sửa bug" → test tái hiện bug trước, rồi làm pass.
- Bộ case bắt buộc có test khi build phần tính: (a) vòng feedback n lần, (b) một
  người gánh 2 dự án song song, (c) dự án mới chen ngang giữa chừng, (d) hai người
  cùng khâu nhưng năng suất khác nhau.
- Thay đổi UI/server → chạy app thật, bấm/kéo-thả thử rồi mới báo xong — không chỉ
  đọc code. Test đỏ thì nói thẳng là đỏ.
- Việc nhiều bước → nêu kế hoạch ngắn trước khi làm:
  ```
  1. [Bước] → verify: [cách kiểm]
  2. [Bước] → verify: [cách kiểm]
  ```

### 6. Dữ liệu nhân sự nằm ngoài git

**Repo chỉ chứa code và dữ liệu mẫu. Tên thật, năng suất thật, dự án thật — ngoài git.**

- Dữ liệu runtime (danh sách nhân sự, năng suất từng người, dự án, phân công) lưu
  trong thư mục data được `.gitignore` **ngay từ commit đầu tiên**, không chờ tới lúc lộ.
- Test/fixture chỉ dùng tên giả ("Content A", "Editor 1") — không hard-code tên người
  thật hay số liệu thật của team vào `src/` hoặc `tests/`.
- Năng suất cá nhân là thông tin nhạy cảm trong nội bộ team (so sánh người với người).
  Nếu sau này deploy cho nhiều người dùng chung, phải hỏi user "ai được xem gì" trước
  khi mở dữ liệu ra — không mặc định ai cũng thấy hết.

---

## Thói quen "nhà" (rút từ các tool anh em trong `Claude Tool/`)

Chưa phải quyết định của project này — chỉ là **mặc định khi user không nói khác**:

- Python + web UI local mở qua browser; khởi động bằng `Start.command`; venv tên
  `.venv`; test bằng `pytest`.
- Nhiều tool có bản Windows tách folder riêng (`... Win`) → viết code portable ngay
  từ đầu (pathlib, không hard-code `/Users/...`, không phụ thuộc lệnh chỉ có trên Mac)
  để đỡ khổ khi tới lượt.
- README/hướng dẫn sử dụng viết **tiếng Việt** cho người trong team.
- Nếu đi hướng VPS cho team dùng chung, tham khảo Phần C của
  `../Content Ultimate/CLAUDE.md` (headless, auth qua reverse proxy, nhiều người bấm
  cùng lúc) — đã trả học phí một lần rồi, đừng trả lại.

---

**Các nguyên tắc này đang phát huy tác dụng nếu:** không con số lịch nào bị "ước lượng"
thay vì tính; tool chưa bao giờ tự ý di chuyển nhân sự; diff không có thay đổi thừa;
không tên/năng suất người thật nào lọt vào git; câu hỏi làm rõ đến TRƯỚC khi code chứ
không phải sau khi sai; và phần tính lịch luôn có ví dụ tính tay đối chứng.
