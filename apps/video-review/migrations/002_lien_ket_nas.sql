-- 002 — video LIÊN KẾT NAS (user chốt 20/08/2026): app KHÔNG chép video vào kho nữa,
-- chỉ trỏ tới file gốc trên NAS (quy trình công ty: anh em up NAS rồi đưa sang app).
--   nguon='nas' → cột duong = đường TƯƠNG ĐỐI trong VR_NAS_DIR
--   nguon='kho' → bản ghi đời cũ, duong = đường tương đối trong kho app (còn bản sao)
ALTER TABLE video ADD COLUMN nguon TEXT NOT NULL DEFAULT 'kho';
-- Dấu vân tay file NAS lúc liên kết (ngày sửa, giây epoch). Cùng với kich_thuoc để
-- phát hiện editor GHI ĐÈ bản mới cùng tên — bình luận gắn mốc giây sẽ lệch.
ALTER TABLE video ADD COLUMN nas_mtime REAL;
