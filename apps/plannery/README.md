# Production — tool điều phối sản xuất video

Tool lập kế hoạch cho team sản xuất video YouTube: tính điểm rơi bàn giao giữa các
khâu (Content → Editor → bàn giao Kinh doanh) và cảnh báo quá tải / trễ lịch up.

**Trạng thái:** đã có phần logic tính (`planner/`) + test + UI local kéo-thả.
Khởi động bằng `Start.command` (hoặc `python3 server.py`) — tự mở browser.
Kế hoạch lưu ở `data/plan.json` (ngoài git), tự lưu sau mỗi thay đổi.

## Luồng nhập liệu

```
Dự án → Kênh (đặt tên sau được) → số video cần → lịch up (video/tuần)
      → phân công nhân sự (% công suất) → TÍNH: lịch bàn giao kèm tên nhân sự
```

## Mô hình tính (chốt 13/07/2026)

- **Năng suất**: mỗi người nhập *ngày-công/video* ở khâu của mình (số lẻ được, vd 1.5).
- **Lịch làm việc**: Thứ 2 – Thứ 7, nghỉ Chủ nhật — việc rơi vào Chủ nhật tự đẩy sang thứ Hai.
- **Vòng feedback**: mỗi khâu N vòng; mỗi vòng = *chờ feedback* + *sửa*, cả hai đều
  tính vào lịch. Trong lúc chờ, người đó làm video khác (chờ không chiếm công suất).
- **Chia tải**: quản lý đặt % công suất khi phân công; việc D ngày công @ x% chiếm
  D/x ngày lịch. Tổng % một người vượt 100% → cảnh báo quá tải.
- **Quy tắc xếp việc** (tất định): video mới tới khâu nào thì giao cho người của khâu
  đó *rảnh sớm nhất* (hoà → theo thứ tự khai báo); một người rảnh mà có nhiều việc sẵn
  sàng thì làm *video số nhỏ trước*; vòng sửa do chính người làm video đó sửa.
- **Deadline**: lịch up F video/tuần → video thứ k phải xong sau `k × 6/F` ngày làm
  việc kể từ ngày bắt đầu dự án; trễ thì cảnh báo, **không tự giãn lịch**.
- **Dự án chen ngang**: lập snapshot mới (số video còn lại + ngày bắt đầu mới + % chia
  lại) rồi tính lại toàn bộ — engine không mô hình % thay đổi theo thời gian.

Tool chỉ **tính và cảnh báo** — không tự di chuyển nhân sự. Mỗi video trả về danh sách
đoạn thời gian (làm chính / chờ feedback / sửa) để trả lời "vì sao ra ngày này".

### Ví dụ tính tay đối chứng (có trong test)

Content A 2 ngày/video (1 vòng: chờ 1 + sửa 0.5), Editor 1 3 ngày/video (2 vòng:
chờ 1 + sửa 1), 1 video, bắt đầu thứ Hai 13/07/2026:

```
content : 2 + (1 + 0.5)        = xong ngày công 3.5  → thứ Năm 16/07
editor  : 3.5 + 3 + 2×(1 + 1)  = bàn giao ngày công 10.5
        → ngày làm việc thứ 11 (bỏ CN 19/07) = thứ Sáu 24/07
```

## Cấu trúc

```
planner/
  models.py     # schema đầu vào: Person, StageConfig, Project, Assignment, PlanInput
  workcal.py    # quy đổi ngày công ↔ ngày lịch (T2–T7)
  engine.py     # compute_schedule(PlanInput) → PlanResult (lịch + cảnh báo)
ui/index.html   # UI một trang: kéo-thả phân công, bảng lịch, truy ngược phép tính
server.py       # server local (stdlib, chỉ bind 127.0.0.1), API + lưu data/plan.json
Start.command   # bấm đúp để chạy (tự mở browser)
tests/          # ví dụ tính tay — chỉ dùng tên giả
demo.py         # chạy thử engine ngoài UI: python3 demo.py
data/           # dữ liệu THẬT của team — được .gitignore, không đưa lên git
```

## Dùng UI

1. Chạy `Start.command` → browser mở `http://127.0.0.1:8123`.
2. Bấm **Nạp dữ liệu mẫu** để xem thử, hoặc tự thêm nhân sự + dự án.
3. Kéo biểu tượng **⠿** trên thẻ nhân sự, thả vào ô phân công của dự án;
   chỉnh % công suất ngay trên chip. Mọi thay đổi tự tính lại + tự lưu.
4. Bấm vào một dòng video trong bảng lịch để xem **vì sao ra ngày này**
   (từng đoạn làm chính / chờ feedback / sửa).

## Chạy test / demo

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest        # đối chiếu số tính tay
python3 demo.py                   # in lịch mẫu ra terminal
```

## Chưa làm (chờ chốt / yêu cầu rõ)

- Hệ số loại video (dài/ngắn); phạm vi một/nhiều kênh; mô hình người feedback.
- Chạy VPS cho cả team dùng chung (hiện là local một máy).
