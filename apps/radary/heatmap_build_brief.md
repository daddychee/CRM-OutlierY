# BRIEF CODE — Heatmap Giờ Đăng (Radary)

> Dán cho AI coding agent trong VSCode (Claude Code / Cursor).
> Đọc kèm: `CLAUDE.md`, `docs/weekly_report.md`, code `radary/report` + `radary/series` (tham chiếu cách vẽ SVG nhúng data-URI đã có).

---

## 0. Ngữ cảnh (đọc trước)

Radary = FastAPI + SQLite + React (Preact/htm, no build). Đã có sẵn 3 đồ thị SVG tự vẽ nhúng data-URI trong báo cáo tuần (`radary/report`) và chart sóng trong `radary/series`. Tính năng này **tái dùng đúng pattern đó** — không thêm thư viện vẽ chart.

Nguyên tắc bám: **NP2 đơn giản** (không thêm dependency, engine SVG tự vẽ như đã có) · **NP3 phẫu thuật** (chỉ ĐỌC dữ liệu tick/video có sẵn, không ghi) · **NP6 tách tầng** (engine tính số, render riêng).

## 1. Yêu cầu cốt lõi (một câu)

Thêm **Heatmap Giờ ĐĂNG × Thứ**: với mọi video trong pool của một workspace, đọc `publishedAt`, gom theo (giờ × thứ-trong-tuần), vẽ heatmap 7 hàng (T2–CN) × 24 cột (0h–23h), đậm = nhiều video. Kèm 1 dòng đọc-hộ "khung giờ đông nhất".

## 2. SỰ THẬT KỸ THUẬT bắt buộc nắm (kẻo làm sai)

- Đây là **giờ ĐĂNG** (`publishedAt` từ YouTube API — ĐÃ CÓ trong dữ liệu Radary). **KHÔNG phải giờ XEM.**
- Giờ XEM của kênh đối thủ **KHÔNG lấy được** (cần YouTube Analytics API, chỉ chạy cho kênh mình sở hữu). Nếu ai đó yêu cầu "giờ xem" → không làm được, đừng cố.
- **KHÔNG tốn thêm quota** — dùng lại `publishedAt` đã lưu, không gọi thêm YouTube API.

## 3. Vị trí trong codebase

- Engine: thêm hàm trong `radary/report` (hoặc module nhỏ `radary/heatmap.py`) — thuần stdlib, chỉ đọc.
- Render: hàm vẽ SVG nhúng data-URI, đặt cạnh code vẽ 3 đồ thị tuần hiện có (tái dùng helper SVG nếu đã có).
- API: 1 endpoint đọc `/workspace/{ws}/heatmap` trả JSON ma trận 7×24 + meta (hoặc nhúng thẳng vào payload báo cáo tuần).
- UI: thêm block heatmap vào tab **Báo cáo** (nơi đã có đồ thị + nút Xuất PDF), theo pattern hiện có.

## 4. Nghiệp vụ / logic tính

1. Lấy mọi video trong pool workspace (từ DB tick/video sống — CHỈ ĐỌC), trường `publishedAt` (epoch).
2. Với mỗi video: đổi epoch → (thứ, giờ). **Timezone: theo `Asia/Ho_Chi_Minh`** (quy ước Radary — KHÔNG để UTC như ảnh mẫu; hoặc cho user chọn UTC/VN, mặc định VN).
3. Đếm số video mỗi ô → ma trận 7×24.
4. Chuẩn hoá màu: đậm dần theo số video trong ô (max theo ô đông nhất). Ô 0 video = nền tối.
5. Đọc-hộ: tìm khung giờ đông nhất (ví dụ "cụm dày 18–20h VN mọi thứ") — thuần mô tả số liệu, KHÔNG khuyên "nên đăng lúc X" (giữ NP5: mô tả, không chỉ đạo hành động sản xuất).

## 5. Tham số / tuỳ chọn

- Phạm vi thời gian: mặc định toàn bộ video trong pool; cân nhắc cho lọc "N tháng gần nhất" (nhịp đăng cũ ít giá trị).
- Múi giờ: VN (mặc định) / UTC (tuỳ chọn).
- Chỉ long-form >180s (đúng phạm vi Radary) hay tính cả video ngắn → mặc định long-form, khớp bộ lọc chung.

## 6. Ràng buộc bắt buộc

- `publishedAt` có thể THIẾU ở vài video (livestream/premiere) → dùng `.get()` phòng thủ, bỏ qua video thiếu, KHÔNG crash (bài học sự cố `duration`).
- CHỈ ĐỌC — không ghi/sửa DB. Render tách khỏi engine (NP6).
- SVG nhúng data-URI, không thêm lib chart, hợp nút "Xuất PDF" đã có.
- No-cache UI như các tab khác; `node --check web/app.js` sau khi sửa.

## 7. Nghiệm thu (thêm vào verify hiện có hoặc `verify_heatmap.py`)

- Ma trận 7×24 tổng số ô = tổng video có `publishedAt` hợp lệ (không mất, không nhân đôi).
- Video thiếu `publishedAt` → bỏ qua, không lỗi.
- Đổi timezone VN↔UTC → ô dịch đúng số giờ.
- Read-only: chạy xong, 0 thay đổi trong DB.
- Pool rỗng → heatmap trống, không crash.

## 8. KHÔNG làm

- KHÔNG gọi thêm YouTube API (dùng data có sẵn).
- KHÔNG làm "giờ xem" (bất khả thi).
- KHÔNG sinh khuyến nghị "nên đăng lúc X để thắng" — chỉ mô tả nhịp đăng của pool (NP5).
