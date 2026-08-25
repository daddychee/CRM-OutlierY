# Tasky — FLOW v3 (Owner đưa phương pháp luận 24/08/2026) — bản đang theo

> v1, v2 giữ làm mốc. v3 ĐƠN GIẢN HÓA MẠNH theo phương pháp luận Owner gửi:
> *"Leader đưa công việc tuần cho nhân sự · nhân sự viết checklist cách mình sẽ
> triển khai · làm xong tick · báo cáo quản lý xem khối lượng và tỉ lệ hoàn thành.
> Sau một thời gian, tự viết được bộ quy trình cho từng loại công việc — LÚC ĐÓ
> mới dùng làm gợi ý."*

## 1. App làm đúng bốn việc

```
① Leader giao TASK tuần cho từng nhân sự
② Nhân sự nhận task → viết CHECKLIST cách mình sẽ triển khai (gạch đầu dòng)
③ Làm xong bước nào tick bước đó
④ Quản lý xem: khối lượng việc tuần của từng người + tỉ lệ hoàn thành
```

Hết. Không mục tiêu tầng trên, không trọng số, không điểm số.

## 2. Cây dữ liệu — CHỈ 2 TẦNG

```
TASK (leader giao · hoặc nhân sự tự thêm)
├── bước checklist 1   [x]
├── bước checklist 2   [x]
└── bước checklist 3   [ ]
```

Checklist do **nhân sự tự viết** — đây vừa là cách làm việc, vừa là **nguyên liệu
cho bộ quy trình sau này** (§5). Không ai viết hộ, máy không gợi ý ở vòng 1.

## 3. Đo cái gì

| Số | Cách tính | Ai đọc |
|---|---|---|
| **Tỉ lệ hoàn thành** | task xong ÷ task được giao trong tuần | Quản lý (số chính) |
| **Tiến độ trong task** | bước đã tick ÷ tổng bước | Nhân sự (thấy mình đang ở đâu) |
| **Khối lượng** | số task + tổng số bước checklist | Quản lý (ai đang gánh nhiều) |

**Van chống bịa**: người chưa nhận task nào → hiện `—`, không hiện 0%.
Task chưa có checklist → ghi rõ *"chưa viết cách triển khai"*, không tính là 0%.

## 4. Vòng đời tuần (2 trạng thái, không mốc chốt — Đ1 v2 giữ nguyên)

```
ĐANG CHẠY ──(hết tuần)──► ĐÓNG TUẦN: leader xác nhận task xong + chọn hướng cho task chưa xong
```

- **Xác nhận ở CẤP TASK, không ở từng bước.** Nhân sự tick bước thoải mái; task
  báo xong → leader xác nhận một lần. Báo cáo quản lý chỉ tính task **đã xác nhận**.
  Leader tự làm task của mình → tự xác nhận, báo cáo dán nhãn *"tự xác nhận"* (Đ2 v2).
- **Đóng nhầm thì THU LẠI được** (Owner yêu cầu 24/08): nút *Mở lại* cạnh chip
  *Đã đóng*. Quyền như lúc đóng (leader quản người đó, hoặc Owner); nhật ký giữ vết
  cả hai chiều — ai đóng, ai mở, lúc nào.
- Task chưa xong khi đóng tuần → chọn: **dời sang tuần sau** / **hủy** (ghi lý do).
  Dời ≥2 lần → cờ **việc kẹt**.
- Việc thêm bất cứ lúc nào, không deadline khai báo (Đ1 v2). Task mang nhãn nguồn
  `giao` (leader) hoặc `tu_them` (nhân sự tự nhận) — cả hai đều tính đủ.

## 5. ĐẶC BIỆT — Bộ quy trình tự viết ra từ checklist thật

Đây là thứ khiến app khác một cái to-do list. Máy **không** chế quy trình; nó chỉ
**đọc lại việc người đã làm** rồi rút ra cái lặp đi lặp lại.

**Vòng 1 (làm ngay, không có UI gợi ý):** chuẩn bị dữ liệu để sau này gom được.
- Mỗi task có **loại việc** — leader chọn từ danh sách **tự lớn dần** (gõ tên mới là
  thành loại mới, giống tag từ khóa của AI Agent). Đây là khóa gom nhóm; thiếu nó thì
  sau này không rút quy trình được, và không thể bù bằng migration.
- Mọi checklist được giữ nguyên văn kèm loại việc, người viết, tuần, task đã xong hay không.

**Vòng 2 (chỉ bật khi có đủ nguyên liệu):**
- Một loại việc tích được **≥3 checklist của task ĐÃ HOÀN THÀNH** → hệ chuẩn hóa các
  bước (bỏ dấu, thường hóa, gộp bước gần giống) và rút ra **bước nào lặp ở ≥2/3 số lần**.
- Kết quả hiện cho **leader duyệt**: *"5 người đã làm loại việc này, 4 người đều có bước
  X — đưa vào quy trình chuẩn?"* Leader sửa/bỏ/thêm rồi chốt.
- Quy trình chuẩn đã chốt mới được dùng làm **gợi ý** khi giao task cùng loại — hiện
  dạng nháp, nhân sự bấm nhận từng bước, vẫn sửa được. Máy không bao giờ tự điền.
- Dưới 3 lần → **không đề xuất gì**, nói thẳng *"chưa đủ tiền lệ"*.

Không LLM ở cả hai vòng — đếm và gom bằng chuỗi. Nếu về sau muốn diễn đạt bước cho gọn
thì mới cần model, và đó là quyết định riêng.

## 6. Quyền (giữ từ v1)

`vao` L1 · `giao_task` L3+ (bộ phận mình) · `xac_nhan_ket_qua` L3+ ·
`bao_cao_bo_phan` L4+ (Manager xem mọi bộ phận) · `mo_lai_tuan` L5.
Tên hành động tránh 5 từ khóa `xoa/toan_quyen/sua/tao/them` (bẫy `nas_toan_quyen` 18/08).

## 7. Kỹ thuật (giữ từ v1/v2)

App độc lập `apps/tasky`, cổng **9117**, SSO claims từ gateway.
Dữ liệu `data/tasky/db/tuan/YYYY-Www.json` + `nhat-ky.jsonl` chỉ-thêm, ghi nguyên tử.
KHÔNG nối PlannerY (Đ5 v2) — chừa sẵn trường `nguon_ngoai` trên task, chưa dùng.

## 8. Ba màn hình

1. **Tuần của tôi** — danh sách task được giao + task tự thêm; mở task ra viết/tick checklist.
2. **Giao việc** (leader) — giao task cho người trong bộ phận, chọn loại việc; cuối tuần xác nhận + đóng tuần.
3. **Báo cáo** (quản lý) — bảng người × khối lượng × tỉ lệ hoàn thành, kèm task kẹt.

## 9. PHÂN QUYỀN (Owner nêu 24/08) — thay mục 6

### 9.1 Bốn luật Owner nêu

| # | Luật | Cài ở đâu |
|---|---|---|
| 1 | Nhân sự chỉ xem việc **của mình** | Lọc SERVER theo claims, không chỉ ẩn nút |
| 2 | Level cao giao việc cho level thấp | Luật riêng app: `level người giao > level người nhận` |
| 3 | Leader xem báo cáo **bộ phận mình** | `bao_cao_bo_phan` L3+, phạm vi = bộ phận trong claims |
| 4 | Lãnh đạo xem báo cáo **toàn công ty** | `bao_cao_cong_ty` L5 |

**Phạm vi báo cáo — Owner chốt 24/08:**

| Ai | Thấy gì |
|---|---|
| Nhân sự (L1-2) | Chỉ việc của mình |
| Leader (L3) | Báo cáo **bộ phận mình** |
| Manager (L4) | Báo cáo **mọi bộ phận** — GIỮ lệ 04/08 App_Rule.md, không sinh ngoại lệ |
| **HR Leader+ (L3+, Hành chính Nhân sự)** | Báo cáo **toàn công ty** — HR giữ chấm công + xếp loại KPI nên số Tasky là đầu vào tự nhiên |
| Owner (L5) | Tất cả |

Hành động IAM (đều tránh 5 từ khóa `xoa/toan_quyen/sua/tao/them` — bẫy 18/08):
`vao` L1 · `giao_viec` L3+ · `xac_nhan_ket_qua` L3+ · `bao_cao_bo_phan` L3+ ·
`bao_cao_cong_ty` L4 · `bao_cao_nhan_su` L3 **+ `bo_phan: "Hành chính Nhân sự"`**.

Nhánh HR khai bằng trường `bo_phan` sẵn có của `iam.co_quyen` (luật ngoài code,
không phải nhớ tick từng người); ô tick lẻ vẫn thắng nếu Owner muốn mở/chặn một ca cụ thể.

### 9.2 Luật giao việc — kiểm ở SERVER, không tin dropdown

Người giao hợp lệ khi **cả hai** đúng:
1. `level(người giao) > level(người nhận)` — nghiêm ngặt lớn hơn, ngang cấp KHÔNG giao được;
2. **cùng bộ phận** — trừ Owner (L5) giao được mọi bộ phận.

Nhân sự **tự thêm việc cho chính mình** thì không qua luật này (không phải "giao").

### 9.3 Nhận / từ chối việc (Owner yêu cầu)

```
Leader giao → CHỜ NHẬN ─┬─ nhân sự bấm Nhận  → ĐANG LÀM (bắt đầu viết checklist)
                        └─ nhân sự Từ chối   → bắt GHI LÝ DO → bấm XÁC NHẬN TỪ CHỐI
                                              → việc trả về leader (giao lại / sửa / hủy)
```

- **Bấm Nhận là BẮT BUỘC** (Owner chốt 24/08): việc chưa nhận thì chưa viết được checklist.
  Leader nhờ đó biết chắc việc đã đến tay người ta, không phải đoán.
- Lý do từ chối **bắt buộc**, không cho bỏ trống; hai bước (ghi lý do → xác nhận) để
  không bấm nhầm. Việc bị từ chối **không vào mẫu số** tỉ lệ hoàn thành của nhân sự.
- Toàn bộ vết (ai giao, ai từ chối, lý do, lúc nào) vào `nhat-ky.jsonl` chỉ-thêm.
- Báo cáo leader có cột **bị từ chối** — giao việc sai người/sai sức là tín hiệu quản trị,
  không phải thứ để giấu.
- Việc chưa nhận sau khi hết tuần: theo luật §4 (dời hoặc hủy kèm lý do).

### 9.4 Xem checklist của người khác

Chỉ **người giao việc đó** (leader/manager cùng bộ phận) và **Owner** xem được checklist
chi tiết — cần cho việc xác nhận. Đồng nghiệp ngang cấp không xem nhau (luật 1).
Báo cáo cấp bộ phận/công ty chỉ hiện **số**, không mở checklist.

### 9.5 Chiều nối tương lai — ĐẢO so với Đ5 v2 (Owner chốt 24/08)

Sau này **dữ liệu chảy Tasky → PlannerY**, KHÔNG phải ngược lại. Tasky là nơi người khai
việc; PlannerY nhận. Vòng 1 vẫn không nối gì; giữ sẵn trường `nguon_ngoai` trên task.

## 10. PHỐI HỢP NGANG GIỮA CÁC BỘ PHẬN (Owner chốt 24/08)

Giao việc là **lệnh** (trên xuống, trong bộ phận). Phối hợp là **yêu cầu** (ngang
hàng, liên bộ phận) — người gửi KHÔNG có quyền trên người nhận, nên bên kia có
quyền từ chối và việc đó là bình thường.

```
Quản lý bộ phận A ──yêu cầu──► Quản lý bộ phận B
                                 ├─ Từ chối (bắt ghi lý do) → về A, hết chuyện
                                 └─ Đồng ý → B LÀ CHỦ việc, chọn một trong hai:
                                      · tự làm (viết checklist như việc thường)
                                      · chẻ việc con giao người bộ phận B
                                        (đường giao việc thường, giữ liên kết ngược)
                                    → B báo xong → **A NGHIỆM THU** hoặc trả lại
```

| Điều | Luật |
|---|---|
| Ai gửi được | Cả hai phải L3+, **khác bộ phận**, chênh **tối đa 1 bậc** (Manager KD ↔ Manager VH, Manager KD ↔ Leader VH) |
| Cùng bộ phận | Không đi cửa này — đã có đường giao việc thường |
| Ai nghiệm thu | **Bên yêu cầu** (người cần kết quả). Bên làm KHÔNG tự ký cho mình dù là Manager và là chủ việc |
| Tính công | **Bên nhận việc** — ai làm nấy được tính. Bên nhờ chỉ theo dõi, tránh đếm đúp khối lượng công ty |
| Phân phối tiếp | Việc con vẫn qua đúng luật giao việc thường: chỉ giao được trong bộ phận mình. Nhận việc phối hợp KHÔNG cho quyền giao sang bộ phận khác |

Trạng thái mới `cho_phoi_hop`; việc mang `nguon = "phoi_hop"`, `bo_phan_gui`, và việc
con mang `tu_yeu_cau` = id yêu cầu gốc để truy ngược.

Thông báo thêm 3 sự kiện: bên nhận thấy *"N yêu cầu phối hợp đang chờ trả lời"*
(quá hạn → đỏ); bên gửi thấy *"chờ bạn nghiệm thu"* và *"bị bộ phận kia từ chối"*.

## 11. HẠN CHÓT + DẤU GẤP (Owner yêu cầu 24/08)

Hai trường tùy chọn trên mọi việc: `han` (ngày, YYYY-MM-DD) và `gap` (dấu **GẤP**).

| Điều | Luật |
|---|---|
| Ai đặt | Người giao lúc giao / gửi yêu cầu phối hợp; đổi sau bằng `danh_dau` — **người giao hoặc Owner**. Việc nhân sự TỰ THÊM thì chính chủ tự đặt |
| Người làm | KHÔNG tự gỡ dấu GẤP của việc được giao (gấp là cam kết với người cần kết quả) |
| Hạn sai định dạng | Báo lỗi thẳng, KHÔNG âm thầm bỏ qua — người giao tưởng đã đặt hạn mà thật ra không thì tệ hơn |
| Việc đã ngã ngũ | Hết nhắc hạn (xác nhận/hủy/từ chối/dời) — không dọa người ta bằng việc đã xong |

**Nhãn hạn** (tính ở lõi, UI chỉ hiển thị): `Quá hạn N ngày` / `Hạn hôm nay` (đỏ) ·
`Hạn ngày mai`, còn ≤3 ngày (vàng) · xa hơn thì chỉ hiện ngày, không tô màu.

**Sắp xếp**: việc GẤP lên đầu, rồi quá hạn / đến hạn hôm nay, rồi hạn gần dần — thứ
cần làm trước nằm trên đầu màn hình, không phải cuộn tìm.

**Thông báo** thêm 3 dòng đỏ: *N việc đã quá hạn* · *N việc đến hạn hôm nay* ·
*N việc được đánh dấu GẤP* (không đếm trùng việc đã nằm trong hai nhóm trên);
leader thêm *N việc của bộ phận đã quá hạn*.

## 12. MỤC TIÊU + DASHBOARD (Owner chốt 24-25/08)

### 12.1 Chuỗi ba tầng

```
Owner giao NHIỆM VỤ cho Manager  →  Manager dựng thành MỤC TIÊU  →  chẻ VIỆC  →  giao nhân sự
   (việc thường, Owner L5             (có KẾT QUẢ CẦN ĐẠT,             (checklist do
    giao mọi bộ phận)                  hạn riêng, xuyên tuần)           nhân sự tự viết)
```

Mục tiêu giữ `tu_nhiem_vu` = id việc Owner giao → Owner theo dõi được nhiệm vụ mình
giao đã dựng thành mục tiêu chưa, đang tới đâu. Việc giữ `muc_tieu_id`.

| Điều | Luật |
|---|---|
| Ai đặt mục tiêu | **Manager L4+** (Owner chốt: công việc bắt đầu từ Manager). Leader vẫn giao việc lẻ như cũ |
| Kết quả cần đạt | **Bắt buộc** khai bằng chữ (*"AVD ≥ 45%"*, *"8 video xuất bản"*) — không khai thì sau không chốt được |
| Tiến độ | **việc đã NGHIỆM THU ÷ tổng việc con**. KHÔNG trọng số: việc *"họp phân tích đối thủ"* không đóng góp được X% AVD, ép gán là bịa số (Owner bác 25/08) |
| Xong hết việc | **KHÔNG tự thành "đạt"** — chuyển sang chờ Manager kết luận |
| Chốt kết quả | Đạt / Một phần / Không đạt + **nhận xét bắt buộc khi chưa đạt trọn**. Lưu kèm tên người chốt |
| Chốt nhầm | Mở lại được (cùng khuôn thu-lại-đóng-tuần), có vết |
| Việc lẻ | **Không bắt buộc** thuộc mục tiêu — ép thì đẻ ra mục tiêu rác kiểu "việc linh tinh" |

### 12.2 LUẬT MÀU (Owner cho dùng màu tự do, nhưng phải có luật)

Đo bằng validator dataviz (Machado 2009, OKLab ΔE) trên cả hai nền — kết quả buộc
hai điều dưới, không phải sở thích:

**Cấm tô màu theo bộ phận / theo người.** Thử mọi bộ bốn hue trong dải sáng cho nền
tối đều có ít nhất một cặp ΔE < 15 (mắt thường không phân biệt nổi). Bộ phận tách
bằng **khối riêng + tên**.

**Màu chỉ mang bốn nghĩa, dùng y hệt ở mọi màn:**

| Token | Nghĩa duy nhất | Ví dụ |
|---|---|---|
| `--accent` | đang chạy · tiến độ | thanh tiến độ, việc đang làm, chip mục tiêu |
| `--ok` | đã xong · đạt | việc nghiệm thu, mục tiêu chốt Đạt |
| `--warn` | chờ người · sắp tới hạn | chờ nhận, chờ xác nhận, chờ chốt, hạn ≤3 ngày |
| `--danger` | quá hạn · kẹt · không đạt | quá hạn, dời ≥2 lần, mục tiêu Không đạt |

**Mỗi chỗ dùng màu PHẢI kèm chữ + icon line** — cặp `--warn`/`--danger` đo được
ΔE 10.1, dưới ngưỡng, nên màu một mình không đủ phân biệt. Icon: line-SVG một nét,
`stroke-width` 1.8, **không emoji**.

**Biểu đồ**: một chuỗi số liệu → một màu `--accent`. Donut trạng thái dùng đúng bốn
token trên + chú thích bằng chữ. Lưới nhiệt: một hue, đổi độ đậm (sequential).

### 12.3 Dashboard — Frappe Charts (Owner chốt 25/08 sau khi so hai bản thật)

Vendor `src/static/vendor/frappe-charts.min.umd.js` (MIT, ~68KB) — chép về vì máy
LAN không ra Internet; xem `NGUON.md`. **Cái giá đã biết:** thư viện vẽ bằng màu
truyền vào JS, không đọc CSS var → đổi theme phải **đọc token rồi vẽ lại**.

Bề rộng nội dung giữ **`.noi-dung` max-width 900px** như mọi app khác — dashboard
xếp lưới trong khổ đó, không tự nới rộng.

## 13. GỘP MÀN GIAO VIỆC (Owner chốt 25/08)

Owner soi lại: *"cái giao việc đúng là hơi thừa thật nhỉ"*. Đối chiếu thì ba khối bị
nhân đôi, bốn khối không trùng — nên **tán ra hai màn** chứ không xóa trắng:

| Khối cũ | Đi đâu |
|---|---|
| Form giao việc lẻ · phối hợp liên bộ phận · xác nhận/trả lại/dời/hủy/xóa | → tab **“Việc lẻ”** trong màn Goal |
| Bảng bộ phận + nút Đóng tuần / Mở lại | → màn **Báo cáo** (nơi đã có bảng từng người) |
| Ba nhóm việc, chip status gộp | → giữ nguyên cách trình bày ở cả hai nơi |

- `/giao-viec` **redirect 303** sang `/muc-tieu` — team đã bookmark, không để chết.
- Sidebar còn hai mục con: **Goal** và **Báo cáo**.
- Tab *Việc lẻ* chỉ chứa việc **không thuộc Goal nào** (việc thuộc Goal đã nằm trong
  cây của nó — không hiện hai lần).
- Thông báo trước trỏ `/giao-viec` nay trỏ `/muc-tieu?chon=le`.

## 14. NĂM CẢI TIẾN THEO DÙNG THẬT (Owner 25/08)

1. **Đọc được lý do từ chối.** Việc bị từ chối trước đó rơi ra ngoài cả ba nhóm nên
   biến mất khỏi màn hình. Nay nó nằm ở *Cần bạn xử lý* (trong Goal) và *Chờ bạn xử
   lý* (Báo cáo), hiện nguyên văn: **“Thu Hà từ chối: …”** để leader giao lại.
2. **Một việc, nhiều người + tự giao cho mình.** Chọn N người → sinh **N bản việc**
   cùng tên, chung `cung_viec`; mỗi người tự viết checklist, tự nhận, tự được nghiệm
   thu → mọi luật và tỉ lệ hiện có giữ nguyên. `duoc_giao_cho` thêm nhánh *tự giao
   cho chính mình* (Manager cũng là người làm việc).
3. **Tab Goal một cỡ cố định** (198×62) + **màu nhãn tự chọn** từ bảng 6 màu
   (`MAU_NHAN`, không cho nhập hex tự do — hex tự do sẽ đẻ ra màu trùng nền hoặc
   trùng màu cảnh báo). Màu này là **nhãn cá nhân**, chỉ tô dải bên trái tab; nghĩa
   trạng thái vẫn là bốn token accent/ok/warn/danger và luôn kèm chữ (§12.2).
4. **Nhãn theo góc nhìn**: người giao thấy *“giao Thu Hà”* / *“tôi làm”*; người nhận
   ở màn Việc của tôi thấy việc của mình như cũ.
5. **Bỏ tab “Việc lẻ”.** Phối hợp liên bộ phận và dấu GẤP chuyển vào trong Goal —
   yêu cầu gửi từ Goal nào thì **gắn vào Goal đó** (`muc_tieu_id`), theo dõi ngay
   trong cây. Việc ngoài Goal vẫn tồn tại (nhân sự tự thêm) nhưng Manager xử lý
   chúng ở **Báo cáo**, khối *Chờ bạn xử lý* — nếu không có khối này thì bỏ tab Việc
   lẻ sẽ làm chúng mất chỗ đứng.
