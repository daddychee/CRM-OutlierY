# Video Review (:9114) — feedback video kiểu Frame.io

App nghiệp vụ V3 cho quy trình duyệt bản dựng video của team:

1. **Thêm bản dựng TỪ NAS** — anh em xuất bản dựng lên NAS như thường lệ, vào app
   duyệt thư mục (gốc khai bằng `VR_NAS_DIR` trong .env; chưa khai thì khối ẩn +
   trang báo cho Owner) rồi chọn file. App chỉ **LIÊN KẾT** — ghi sổ đường tương
   đối, **không chép byte nào, không upload, không giới hạn dung lượng**, thêm là
   xem được ngay. **NAS chỉ ĐỌC**: app không bao giờ ghi/xóa/đổi tên gì trong đó.
2. **Bình luận gắn mốc thời gian** — bấm bình luận là player tua tới đúng giây;
   thanh mốc dưới video hiện chấm từng bình luận.
3. **Vẽ chú thích trên khung hình** (nút ✎ Draw khi xem) — nét vẽ lưu theo bình
   luận (tọa độ 0..1, vẽ lại đúng mọi cỡ màn hình).
4. **Trạng thái duyệt**: In review / Changes requested / Approved.
5. **Phụ đề**: file `.srt` để cạnh video trên NAS được đọc thẳng; người đăng gắn
   thêm bản khác từ app thì bản đó nằm trong kho app và thắng bản trên NAS.

## Vân tay file — vì sao có cảnh báo "file changed / file missing"

Vì video không nằm trong app, file gốc có thể bị đổi sau lưng: dung lượng + ngày
sửa được chụp lúc liên kết, mỗi lần mở lại đem so.

- File mất (xóa/đổi tên/di chuyển) → danh sách hiện `file missing`, trang xem báo
  rõ, `/media` trả 404 — **bình luận vẫn còn nguyên trong sổ**.
- File bị **ghi đè bản mới cùng tên** → cảnh báo vì mốc giây của bình luận cũ trỏ
  sai chỗ; nên thêm bản mới thành mục riêng thay vì đè.

App **chỉ cảnh báo, không tự sửa sổ** — người dùng quyết.

## Quyền (phan_quyen.json — app chỉ tin cờ X-Remote-Actions)

- `vao` (level 1+): xem, bình luận, thêm video từ NAS, giải/xóa bình luận CỦA MÌNH.
- `duyet` (Leader 3+): đổi trạng thái duyệt + thao tác bình luận người khác.
- `xoa` (Manager 4+): gỡ video — **GỠ MỀM**, file trên NAS không bị đụng.

## Dữ liệu (Luật 6)

- `data/video-review/db/video_review.db` — SQLite (migration `migrations/*.sql` +
  bảng `schema_version`). **Đây là thứ duy nhất phải backup**: sổ video (đường NAS
  + vân tay), bình luận, nét vẽ. Backup: sqlite-snapshot (VACUUM INTO).
- `data/video-review/kho/phu-de/<ma>.srt` — phụ đề gắn từ app.
- `data/video-review/kho/<năm>/<tháng>/` — bản sao video ĐỜI CŨ (trước 20/08/2026),
  giữ tới khi dọn; bản ghi của chúng có `nguon='kho'`.
- Video gốc: **trên NAS**, do NAS lo lưu trữ và backup.

## Video qua proxy — vì sao trả 206 từng khúc

Proxy gateway đọc TRỌN body phản hồi vào RAM (trừ SSE). `/media/{ma}` vì thế trả
206 từng khúc ≤ `VR_KHUC_MB` (mặc định 8MB) kể cả khi trình duyệt xin `bytes=0-`;
trình duyệt tự xin khúc kế tiếp nên tua mượt mà gateway không phình RAM. Từ 20/08
không còn đường upload nên gateway hết phải buffer body request cỡ GB.

## Chạy + test

```
python -m uvicorn src.main:app --app-dir "apps/video-review" --host 127.0.0.1 --port 9114
cd apps/video-review && pytest      # mỗi app một process pytest riêng
```

## Dọn bản sao đời cũ

`python scripts/lien_ket_lai_nas.py` (mặc định chỉ LIỆT KÊ) dò file gốc trên NAS
theo dung lượng cho các bản ghi `nguon='kho'`, `--chay` đổi sang liên kết,
`--xoa-ban-sao` xóa bản sao trong kho sau khi đã liên kết và kiểm khớp.
