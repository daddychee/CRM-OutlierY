# Tasky — FLOW v2 (Owner chốt 24/08/2026) — thay v1, giữ v1 làm mốc

Delta so với [FLOW-v1.md]: 3 câu hỏi mở đã có đáp án + 1 tính năng mới.

## Đ1. BỎ mốc "chốt kế hoạch" — startup, việc thêm liên tục

Vòng đời tuần rút còn **2 trạng thái**:

```
ĐANG CHẠY ──nhân sự gửi kết quả──► CHỜ XÁC NHẬN ──leader đóng──► ĐÃ ĐÓNG
```

Việc thêm được **bất cứ lúc nào**, không có deadline khai báo, không có "phát sinh"
như một hạng riêng. Thay vào đó mỗi việc mang **NGUỒN**:

| Nguồn | Ai tạo | Ý nghĩa quản trị |
|---|---|---|
| `giao` | Leader giao xuống | Việc theo định hướng tuần |
| `tu_them` | Nhân sự tự thêm | Việc đều đặn / phát sinh tự nhận |

**% hiệu suất** = điểm việc *xong-đã-xác-nhận* ÷ **tổng điểm mọi việc trong tuần**
(cả `giao` lẫn `tu_them`). Báo cáo luôn tách 2 dòng để leader đọc được cơ cấu:
`Giao: 8/13đ · Tự thêm: 2/4đ`. Việc tự thêm được tính công đầy đủ — đúng thực tế
startup, người chủ động không bị thiệt.

Chống làm-đẹp-số khi mẫu số động: **không xóa cứng việc** đã tồn tại (chỉ `huy`
kèm lý do, giữ trong sổ); đổi trọng số sau khi việc đã `xong` → ghi vết nhật ký.

## Đ2. Leader tự xác nhận việc của chính mình

Được, nhưng báo cáo dán nhãn **"tự xác nhận"** cạnh số — lãnh đạo đọc là biết số này
không qua nấc kiểm thứ hai. Không chặn, chỉ minh bạch.

## Đ3. Việc lẻ = việc nhân sự tự thêm

Không bắt treo dưới mục tiêu. Khối **"Việc tự thêm"** đứng ngang hàng các mục tiêu
trong cây, tính điểm bình thường. Nhân sự vẫn có thể kéo một việc tự thêm vào dưới
mục tiêu nếu thấy nó phục vụ mục tiêu đó.

## Đ4. MỚI — Gợi ý cách triển khai khi nhận việc (Owner yêu cầu)

Trả lời: **làm được**, ba nấc, đều ra **NHÁP** — người bấm nhận từng dòng mới thành
việc thật. Máy TUYỆT ĐỐI không tự thêm việc vào kế hoạch.

| Nấc | Nguồn gợi ý | Chi phí | Bật khi nào |
|---|---|---|---|
| 1 | **Lịch sử chính Tasky** — việc tương tự các tuần trước (so tiêu đề không dấu + từ khóa) → chìa lại bộ việc con đã dùng, kèm *"đã dùng 6 lần"* | 0đ, không LLM | Vòng 1 |
| 2 | **Mẫu quy trình** leader lưu (một mục tiêu hay lặp → *Lưu thành mẫu*) | 0đ | Vòng 1 |
| 3 | **Kho quy trình công ty** — gọi API chỉ-đọc sang app `ai-agent` (loopback, KHÔNG import chéo — khuôn `plannery_sync`), trả các bước **kèm trích nguồn** | ~200đ/lần | Vòng 2 |

**Van chống bịa**: nấc 1-2 không có mẫu khớp → nói thẳng *"chưa có tiền lệ"*; nấc 3
kho không có tài liệu khớp → *"kho chưa có quy trình cho việc này"* + nút báo
kho-thiếu sang AI Agent. Không nấc nào được chế bước từ suy đoán.

Nấc 1 tự giàu lên theo thời gian mà không ai phải soạn gì — càng dùng càng khôn.

## Giữ nguyên từ v1

Cây 3 tầng · trọng số nhỏ 1 / vừa 2 / lớn 3 · 2 nấc xác nhận · việc chưa xong buộc
chọn hướng (dời / hủy có lý do / đổi người) · cờ **việc kẹt** khi dời ≥2 lần ·
quyền `vao` L1 / `giao_muc_tieu` L3+ / `xac_nhan_ket_qua` L3+ / `bao_cao_bo_phan` L4+ /
`mo_lai_tuan` L5 · dữ liệu `data/tasky/db/tuan/YYYY-Www.json` + `nhat-ky.jsonl` chỉ-thêm ·
app độc lập cổng **9117** · không tự suy "đã xong" từ app khác.

## Đ5. KHÔNG nối PlannerY ở vòng này (Owner chốt 24/08)

Tasky đứng **hoàn toàn độc lập**, cổng 9117. Không đọc, không ghi, không gọi PlannerY.

Lý do giữ hai app tách bạch (khảo sát `apps/plannery` 24/08):
- `Person` của PlannerY **bắt buộc** `role` = content|editor và `standard_rate > 0`
  (kịch bản/ngày · phút video/ngày) — nhân sự HCNS/Kinh doanh không có đơn vị đó.
- Engine PlannerY (592 dòng) **tự phân phối** việc theo năng suất/deadline/vòng
  feedback. Tasky ngược lại: **người khai, người chốt**. Hai triết lý không gộp được.
- `plan.json` là MỘT file ghi trọn kèm `_rev` + 409; PlannerY là app duy nhất của hệ
  có cơ chế chống ghi đè chuẩn (audit 31/07) — không đổ thêm dữ liệu tuần của cả
  công ty vào đó.

**Để ngỏ cho sau** (chỉ bàn lại khi Tasky đã chạy thật vài tuần): kéo MỘT CHIỀU
việc sản xuất đến hạn từ PlannerY sang Tasky làm việc có sẵn (nhãn nguồn, chỉ-đọc,
không ghi ngược). Thiết kế dữ liệu vòng 1 nên chừa sẵn trường `nguon_ngoai` trên
việc để sau này gắn nhãn mà không phải migration.
