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
