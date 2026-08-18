# Video Review (:9114) — feedback video kiểu Frame.io

App nghiệp vụ V3 cho quy trình duyệt bản dựng video của team:

1. **Upload bản dựng** (mp4/webm/m4v; .mov tùy codec trình duyệt) — trần
   `VR_MAX_MB` (mặc định 2048MB). **File lớn đi đường NAS**: khối "Load from NAS"
   duyệt thư mục server-side trong root `VR_NAS_DIR` (.env — chưa khai thì khối
   ẩn), chọn file → server CHÉP thẳng vào kho (nền, % thật theo byte, trần riêng
   `VR_NAS_MAX_MB` mặc định 20GB) — không qua trình duyệt/proxy, file gốc trên
   NAS giữ nguyên.
2. **Bình luận gắn mốc thời gian** — bấm bình luận là player tua tới đúng giây;
   thanh mốc dưới video hiện chấm từng bình luận.
3. **Vẽ chú thích trên khung hình** (nút ✎ Draw khi xem) — nét vẽ lưu theo bình
   luận (tọa độ 0..1, vẽ lại đúng mọi cỡ màn hình).
4. **Trạng thái duyệt**: In review / Changes requested / Approved.

## Quyền (phan_quyen.json — app chỉ tin cờ X-Remote-Actions)

- `vao` (level 1+): xem, bình luận, upload, giải/xóa bình luận CỦA MÌNH.
- `duyet` (Leader 3+): đổi trạng thái duyệt + thao tác bình luận người khác.
- `xoa` (Manager 4+): gỡ video — **GỠ MỀM**, file giữ nguyên trong kho.

## Dữ liệu (Luật 6)

- `data/video-review/kho/<năm>/<tháng>/YYYY-MM-DD_<ma>_<tên>.ext` — file video.
- `data/video-review/db/video_review.db` — SQLite, migration `migrations/*.sql`
  + bảng `schema_version`. Backup: sqlite-snapshot (VACUUM INTO), kho file: copy.

## Video qua proxy — vì sao trả 206 từng khúc

Proxy gateway đọc TRỌN body phản hồi vào RAM (trừ SSE). `/media/{ma}` vì thế trả
206 từng khúc ≤ `VR_KHUC_MB` (mặc định 8MB) kể cả khi trình duyệt xin `bytes=0-`;
trình duyệt tự xin khúc kế tiếp nên tua mượt mà gateway không phình RAM.
Upload thì gateway vẫn buffer body request (trần 2GB chấp nhận được trên LAN —
nâng nữa phải dạy proxy stream request, xem CLAUDE.md).

## Chạy + test

```
python -m uvicorn src.main:app --app-dir "apps/video-review" --host 127.0.0.1 --port 9114
cd apps/video-review && pytest      # mỗi app một process pytest riêng
```
