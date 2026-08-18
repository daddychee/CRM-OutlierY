# SPEC v2 — Trường thông tin nhập cho từng đối tượng

Hợp đồng dữ liệu cho engine v2 + form nhập. Tổng hợp từ các quyết định trong
CLAUDE.md (mục "Đã chốt", 13/07/2026). Dữ liệu thật nằm trong `data/` — ngoài git.

## 1. NHÂN SỰ — chỉ 3 trường nhập trực tiếp

| # | Trường | Kiểu / đơn vị | Ai nhập | Khi nào nhập |
|---|--------|---------------|---------|--------------|
| 1 | Tên | chữ | Leader | Khi tạo |
| 2 | Khâu | `content` \| `editor` \| `clone` | Leader | Khi tạo. Role **Clone** = nhân sự mới chỉ biết làm clone: chuẩn tính VIDEO/ngày, KHÔNG cần thuộc dự án nào — tự nhận tập clone của TẤT CẢ dự án |
| 3 | **Chuẩn tuyển dụng** (thường quy) | content: **kịch bản/ngày** · editor: **phút video/ngày** — số nguyên, bước 1 | Leader + HR | Khi tuyển; đổi khi thoả thuận lại |
| 4 | Màu hiển thị | màu (tuỳ chọn) | Leader | Bất kỳ — để dễ nhìn trên lịch |
| 5 | **Dự án đang làm** (editor) | chọn từ danh sách dự án | Leader | Khi điều người — máy ưu tiên giữ editor ở dự án này |

- **Đơn vị theo khâu**: content đo bằng KỊCH BẢN/ngày (một kịch bản là một unit,
  không phụ thuộc thời lượng video); editor đo bằng PHÚT VIDEO/ngày.
  Thời gian làm một unit: content = `1 ÷ năng suất`; editor = `thời lượng ÷ năng suất`.
- **Hạng mục CLONE của editor** (chốt 13/07): chỉ số riêng `clone_rate` đơn vị
  **VIDEO/ngày** — năng suất trên kênh clone (nhập trên thẻ editor, để trống =
  không nhận việc clone). Thời gian 1 tập clone = `1 ÷ clone_rate`.
- **Năng suất tuần trước** KHÔNG nhập trực tiếp — sinh ra từ **Tổng kết tuần** (mục 3):
  content `= số kịch bản được tính ÷ 6 ngày`; editor `= Σ phút video được tính ÷ 6 ngày`.
  **Lịch phân phối KHÔNG dùng số này** — lịch luôn tính theo **CHUẨN (KPI đã cam
  kết)**, kế hoạch không tự hạ theo người dưới chuẩn; tuần trước chỉ để so sánh
  và cảnh báo Leader/HR (chốt 13/07/2026 khi user duyệt lịch tuần).
- **Cảnh báo Leader/HR**: xuất hiện khi năng suất tuần trước **thấp hơn thường quy**
  (bất kỳ mức nào dưới 100%), hiển thị rõ **% đạt = tuần trước ÷ thường quy**
  (vd "đạt 50% — giảm 50%").
- Nhân sự nghỉ → xoá khỏi danh sách; kỷ lục Best Performance trên dự án giữ nguyên.
- Danh sách nhân sự và danh sách kênh **kéo-chèn sắp xếp được** (grip ⠿) — lưu ý
  thứ tự khai báo cũng là tie-break khi máy chia việc.

## 2. DỰ ÁN = NHÓM KÊNH (tái cấu trúc 13/07/2026)

**Toàn bộ cấu hình sản xuất nằm Ở KÊNH, không phải ở dự án.** Dự án chỉ còn:
tên + danh sách kênh + đội nhân sự chung (kéo-thả). Người thuộc dự án làm được
mọi kênh trong đó; "đang làm" của editor trỏ dự án → ưu tiên mọi kênh của nó.
Engine nhận **mỗi kênh thành một dây sản xuất độc lập** (id `duAn::kenh`).

### 2a. Thông tin từng KÊNH

| # | Trường | Kiểu / đơn vị | Ghi chú |
|---|--------|---------------|---------|
| 1 | Tên kênh | chữ, sửa được (có xác nhận) | + **màu** từ palette cố định — block lịch và nhãn ngày đăng tô theo màu kênh |
| 2 | Ngày bắt đầu | ngày | Ngày làm việc đầu tiên của kế hoạch kênh |
| 3 | Thời lượng video | phút | Hệ số khối lượng khâu editor của kênh (content tính theo kịch bản) |
| 4 | ~~Kho kịch bản sẵn~~ | — | ĐÃ BỎ (13/07) — thay bằng tick **✓ đã có KB** từng tập (2c); dữ liệu kho cũ tự chuyển thành tick k tập đầu |
| 5 | Lịch up | video/tuần | CHỈ để sinh ngày đăng mặc định cho kênh (2c) |

### 2a-bis. CLONE (sửa lần 2 cùng ngày — clone là CỜ của kênh chính)

KHÔNG có "kênh clone" riêng. Kênh chính có checkbox **⧉ Kênh có clone**:
- Số tập cần clone **tự trùng danh sách tập** của kênh (video làm lại cho bản dịch).
- Clone **không có lịch đăng, không qua engine EDD**. Hai loại người làm clone:
  (a) **role Clone thuần** — làm clone của MỌI dự án, không cần phân công, chuẩn
  = video/ngày; (b) **editor kiêm clone** (`clone_rate`, tag Clone) — ƯU TIÊN việc
  dự án trước, chỉ NGÀY RẢNH mới nhận clone. Phân bổ **theo NĂNG SUẤT, xong sớm
  nhất có thể** (sửa 13/07 — KHÔNG dàn đều): mỗi ngày mỗi người nhận đủ rate
  tập/ngày rồi mới sang ngày kế; không xếp hết → ⚠ "còn X tập chưa xếp được".
- **Tập nào clone trước**: tự chọn theo thứ tự SẢN XUẤT trên kênh chính (ngày bàn
  giao engine tính; chưa tính được xếp sau), nhưng tập **★ ưu tiên luôn lên đầu
  hàng clone**. Block ghi rõ tên tập ("★ Tên tập · clone").
- Hiển thị: **khối CLONE nằm CUỐI lịch tuần** — hàng quota mỗi ngày + hàng từng
  người clone; thiếu người clone → hàng đỏ nhắc gán chỉ số + kéo vào dự án.
- Clone hiện tách khỏi lịch editor chính (giả định người clone chuyên trách);
  một người vừa dựng chính vừa clone sẽ thấy cả hai lịch — leader tự cân đối.

### 2b. Cấu hình từng khâu của KÊNH (content, editor)

| # | Trường | Kiểu / đơn vị |
|---|--------|---------------|
| 1 | Số vòng feedback | số nguyên ≥ 0 |
| 2 | Chờ feedback mỗi vòng | ngày làm việc (chờ không chiếm người) |
| 3 | Sửa mỗi vòng | ngày làm việc (chính người làm unit đó sửa) |

**Quy tắc "sửa xong trong ngày" + "tối ưu giờ trong ngày" (chốt 13/07, bản cuối)**:
1. Feedback/sửa (≤ 1 ngày công) phải xong NGAY TRONG NGÀY nó diễn ra — vắt sang
   ngày sau thì **NÉN về cuối ngày, phần dư là QUÁ GIỜ** (nhân sự chấp nhận OT;
   hiển thị ⚡OT trên block để leader thấy sức tải). Không dời sang hôm sau.
2. Trường hợp sửa sẵn sàng MUỘN hơn giờ rảnh (đang chờ feedback): khối sửa chỉ
   "đặt chỗ", giờ trống trước đó nhường unit khác chen vào — block làm chính được
   TÁCH quanh chỗ đặt. Không phút nào bỏ trống khi còn việc sẵn sàng.

### 2c. Danh sách TẬP của kênh (tab theo kênh trong thẻ dự án)

Tập nằm TRONG kênh (không còn trường "gắn kênh" rời). Số tập đánh lại theo
ngày đăng trong phạm vi kênh. Nút "sinh ngày đăng mặc định" chạy riêng từng kênh.

| # | Trường | Mặc định | Leader chỉnh |
|---|--------|----------|--------------|
| 1 | Tên nội dung | **để trống** | Leader tự nhập cụ thể — hiện trên lịch tuần cho content/editor theo dõi |
| 2 | **Ngày đăng** | sinh đều từ lịch up | 📅 sửa từng video — nguồn chân lý; engine so bàn giao với ngày này |
| 3 | Kênh | trống | chọn từ danh sách kênh của dự án — để hiển thị/nhóm; lịch vẫn theo ngày đăng từng video |
| 4 | **★ Ưu tiên** | tắt | bật để video được sản xuất SỚM NHẤT có thể — đứng trên EDD, sau "dự án đang làm" |
| 5 | **✓ đã có KB** | tắt | team viết kịch bản tuần trước cho tuần sau — tick là tập bỏ qua khâu Content, editor làm được ngay |

### 2d. Best Performance của KÊNH (khâu editor)

| # | Trường | Ghi chú |
|---|--------|---------|
| 1 | Kỷ lục | ngày công/video — **số thực tế**, nhập tay |
| 2 | Tên editor | chọn từ danh sách editor trong team; lưu dạng chuỗi — GIỮ NGUYÊN khi người đó nghỉ/bị xoá |
| 3 | Ngày ghi nhận | ngày |

- Chỉ nhận số **tốt hơn** kỷ lục hiện tại. Tool chỉ **nhắc** khi số kế hoạch của một
  editor trong dự án tốt hơn kỷ lục — không bao giờ tự ghi.
- Dùng: đối chứng + xếp hạng gợi ý + tie-break chia unit.

## 3. TỔNG KẾT TUẦN — nhập kết quả ngay trên lịch đăng

Cuối tuần, Leader **chỉ đánh dấu video CHƯA hoàn thành** (mặc định = xong):

| Bước | Thao tác | Hệ quả |
|------|----------|--------|
| 1 | Video không bị đánh dấu | Coi là ✓ — unit content + editor tính cho người làm; video rời kế hoạch |
| 2 | Video ✗ **chưa hoàn thành** | Tool hỏi ngược: **do content hay do editor?** — video ở lại kế hoạch |
| 3a | Do **content** | Trừ chỉ số content; **KHÔNG ảnh hưởng editor** (bị chặn nguồn, không tính hụt) |
| 3b | Do **editor** | Trừ chỉ số editor; **KHÔNG ảnh hưởng content** (kịch bản đã xong vẫn được tính) |

- Ghi nhận xong tool **tự sinh BÁO CÁO TUẦN** (bảng: người / khâu / KPI / kết quả /
  % đạt + danh sách video trượt kèm nguyên nhân), lưu lịch sử để leader theo dõi
  chất lượng nhân sự qua các tuần; có nút copy văn bản.

## 3b. CHỐT NGÀY — xác nhận công việc hàng ngày

Cuối mỗi ngày, Leader mở **✅ Chốt ngày**: danh sách từng người + việc được xếp
trong ngày, đánh ✗ ai chưa xong. Có người ✗ → tool sinh **gợi ý cứu tiến độ**
(mục tiêu cuối: đủ video kinh doanh), leader quyết:
1. ➕ **Thêm người**: liệt kê người cùng khâu đang rảnh hôm đó để kéo vào dự án.
2. 📉 **Giảm khối lượng**: chỉ đích danh video sắp đăng của dự án để dời ngày.
3. ✂️ **Giảm chất lượng edit**: bớt 1 vòng feedback khâu Editor (có nút Áp dụng,
   kèm ước tính ngày công tiết kiệm mỗi video).
Kết quả chốt ngày lưu lại (`daily`); chưa mô hình trượt tự động trong ngày —
leader điều chỉnh rồi bấm ⚡ Tự phân phối.

## 4. PHÂN CÔNG (kéo-thả)

| Trường | Ghi chú |
|--------|---------|
| Người ↔ Dự án | Kéo-thả; nghĩa là "người này được nhận unit của dự án này". KHÔNG có % |

Máy chia unit (quy tắc cố định, không nhập): người rảnh ưu tiên unit thuộc
**dự án đang làm** của mình (không nhảy dự án khi dự án nhà còn việc sẵn), rồi
video **★ ưu tiên**, rồi unit có **ngày đăng gần nhất (EDD)**; hai người cùng rảnh cho một unit →
người **đang làm dự án đó**, rồi người giữ **kỷ lục dự án**, rồi thứ tự khai báo;
làm trọn unit, chỉ ngắt khi chờ feedback (sửa quay về đúng người cũ). Không ghim
unit (thêm sau nếu cần). Nút **⚡ Tự phân phối lịch** trên lịch tuần chạy lại phép
chia này — chỉ chia việc trong phân công hiện có, không tự thêm người vào dự án.

## 5. Tool TỰ TÍNH — không nhập

Lịch tuần từng người (block unit + ô rảnh); hàng "Ngày đăng" kèm tên nội dung;
ngày bàn giao từng video so với ngày đăng (kịp/trễ); cảnh báo: trễ lịch đăng,
khâu thiếu người, nhân sự dưới thường quy (kèm % đạt); cung–cầu phút/tuần từng
khâu; đề xuất thêm/rút người (bản nháp — user ✓/✗); nhắc cập nhật kỷ lục.

## 6. PHÂN QUYỀN (chốt 13/07/2026 — chuẩn bị lên VPS)

Ai cũng XEM được tất cả; quyền sửa theo vai trò (đổi vai trò bằng mã, nút 👤):

| Vai trò | Mã (tạm) | Được làm |
|---------|----------|----------|
| **Quản trị** | `QT-123ABC` | Tất cả: thêm/bớt/xoá mọi thứ |
| **HR** | `HR-123ABC` | Thêm/bớt/sửa NHÂN SỰ (tên, khâu, KPI, màu) + **PHÂN CÔNG người ↔ dự án** + **TỔNG KẾT TUẦN & Báo cáo** (mở 15/07). Không đụng cấu hình kênh/dự án |
| **Leader** | `LD-123ABC` | Dự án/kênh (thêm/xoá/sửa), phân công kéo-thả, "đang làm", khâu, kỷ lục, ★, và toàn bộ thao tác lịch tuần (phân phối/chốt ngày/tổng kết/báo cáo/sửa từ lịch) |
| **SEO / Nhân sự** | `NS-123ABC` | Trong kênh: thêm/sửa/**XOÁ** video (tên, ngày đăng, ★, ✓KB, ⚡gấp) + thời lượng kênh. Không đụng cấu hình kênh/dự án khác (15/07: mở quyền xoá video cho SEO) |
| **Xem** | (để trống) | Chỉ xem — mặc định khi mở trang |

- Lịch tuần: toàn team chỉ xem; các nút thao tác chỉ hiện với Leader/Quản trị.
- **ENFORCEMENT Ở SERVER (13/07)**: mã vai trò nằm trong `data/roles.json` (ngoài
  git/mã nguồn — ĐỔI MÃ trước khi deploy); đăng nhập qua `POST /api/role`; mỗi lần
  lưu gửi header `X-Role-Code`, server kiểm **ma trận quyền theo vùng dữ liệu**
  (HR: people; Leader: mọi thứ trừ hồ sơ nhân sự — được sửa "đang làm" + thứ tự;
  Member: chỉ videos + thời lượng kênh, không xoá; viewer: 403). Kèm khoá phiên
  bản `_rev` chống hai người ghi đè nhau (409 → trang tự tải bản mới), ghi file
  nguyên tử + lock. Độ mịn quyền hiện ở mức VÙNG (member đổi trường con của video
  chưa chặn từng field) — tinh chỉnh khi lên VPS nếu cần. Xem DEPLOY.md.

## 7. BẢO VỆ DỮ LIỆU

1. Mỗi lần lưu: bản cũ → `data/plan.backup.json` + bản theo thời gian trong
   `data/backups/plan-YYYYMMDD-HHMMSS.json` (tự giữ 40 bản gần nhất).
2. Nút **⬇ Sao lưu** trên header: tải toàn bộ dữ liệu về máy dạng JSON — leader nên
   tải định kỳ (cuối tuần) và cất nơi khác.
3. `data/` nằm ngoài git (nguyên tắc 6); máy Mac nên bật Time Machine.
4. Khôi phục: copy bản backup đè lên `data/plan.json` rồi refresh (server đọc file).
5. Đã bỏ nút "Nạp dữ liệu mẫu" — không còn đường ghi đè dữ liệu thật bằng mẫu.

## 8. GIAO DIỆN — theo design system Content Ultimate (tab Outline Extract)

Tham chiếu: `../Content Ultimate/src/oe/board.html`. Dùng nguyên bộ token:

- **Dark mặc định**: nền `#0E1117`, panel `#151A22`, raised `#1C232E`,
  border `#2A3340`; chữ `#E6E2D8`, muted `#9AA1AD`, faint `#6B7280`.
- **Accent vàng hổ phách `#E3AC45`** (accent-ink `#161006`, accent-soft 14%);
  ok `#83A96F`, danger `#D97C6C`, link `#7CB8CC`. Có light-mode qua
  `prefers-color-scheme` (accent `#9A6E15`…).
- Font: display "Avenir Next"/Segoe UI; **số liệu dùng mono** (SF Mono,
  `tabular-nums`).
- Pattern: eyebrow uppercase letterspacing; brand có chữ accent; tab bo góc
  trên liền panel; bảng header dính, uppercase, sort được; chip mono viền;
  ô kéo-thả nét đứt, sáng accent khi kéo qua; nút chính nền accent chữ tối;
  save-state chấm xanh; toast giữa đáy.

## 9. ĐANG LÀM — chốt logic 14/07/2026, code theo thứ tự (1)clone (2)video gấp (3)sort

**a) Clone 2 khâu + ngôn ngữ/version (điểm 1+2) — XONG 14/07, node-test + deploy**
- Kênh: bỏ `has_clone` bool → `clone_langs: [{name, versions}]` (số version BIẾN SỐ
  theo từng ngôn ngữ). Kênh "có clone" khi clone_langs không rỗng. Migrate
  has_clone:true → [{name:"Bản dịch", versions:1}].
- Số tập clone = số tập gốc × Σ(versions mỗi ngôn ngữ). Mỗi bản clone = 2 khâu:
  **dịch kịch bản** (content, `clone_rate` KB/ngày — DỊCH RIÊNG từng version) →
  **dựng lại** (editor, `clone_rate` video/ngày). Dựng theo sau bản dịch của nó.
- Nhân sự content thêm ô clone (KB/ngày); editor giữ clone (video/ngày); role
  "clone" = editor dựng lại (mọi dự án). Khối CLONE cuối lịch tuần tách 2 nhóm
  Dịch / Dựng lại. clone_done chuyển thành per-task (lang#version).

**b) Video gấp — crash schedule (điểm 3) — XONG 14/07, test-first 3 ca + deploy**
- Nút "＋ Video gấp" mỗi kênh: tên tập + NGÀY CẦN ĐĂNG (gấp) + thời lượng.
- Số người = trần( thời lượng ÷ (số ngày tới hạn × năng suất/người) ). CHỈ khâu
  editor chia nhỏ được (dựng chia theo phút, N người song song, video xong = phần
  cuối cùng). Khâu content KHÔNG chia (1 kịch bản 1 người) — bí thì gợi ý ✓KB.
- Người: CHỈ editor thuộc dự án của kênh, rảnh sớm + năng suất cao trước; không đủ
  → cảnh báo (không tự kéo người ngoài dự án).
- Chen lịch: PREEMPT nhưng lượng hoá lưới 0.5 NGÀY — video gấp chỉ bắt đầu ở đầu
  nửa ngày; unit đang làm chạy tới mốc 0.5 kế thì tạm dừng, phần dư đẩy ra sau.
- Tool ĐỀ XUẤT (N người + ai + ngày xong dự kiến), user ✓ mới áp (nguyên tắc 2).
- THỰC THI: engine xếp video gấp ở PRE-PASS (trước vòng lặp chính), ưu tiên cao
  nhất → đẩy việc thường lùi (từ-đầu recompute: gấp tự đứng đầu, không cần cắt
  giữa unit). Editor chia = N Segment song song, effort = phút ÷ Σnăng suất; đóng
  gói output gộp segment theo NGƯỜI → video gấp hiện N StageResult editor. Video
  gấp BỎ vòng feedback (rushed). Đề xuất N tính today→deadline (ước tính); badge
  kịp/trễ trong bảng là số engine thật.

**c) Sort lịch tuần (điểm 4)**: toggle "Xem theo: Người / Kênh". Người = hiện tại;
Kênh = gom theo kênh, mỗi kênh hiện tập đang chạy tuần + ai làm. Thuần hiển thị.

**d) Đăng xuất/đổi tài khoản (điểm 5) — XONG 14/07**: nút "Đổi tài khoản" (production)
→ `/logout` trả 401 + WWW-Authenticate realm "PlannerY" (trình duyệt quên đăng nhập)
+ trang "Đăng nhập lại". nginx location `= /logout` auth_basic off.
