-- 005 — nhớ kết quả quét hỏng file (26/08/2026, sự cố LI088.2).
-- File chép DỞ/ĐỨT giữa chừng lên NAS vẫn đủ dung lượng và đọc được header nên
-- ffprobe báo h264 bình thường; chỉ khi giải mã tới vùng hỏng mới lộ. Trình duyệt
-- xem tới đó là chết giữa chừng — reviewer mất thời gian mới biết.
-- Rỗng = sạch hoặc chưa quét; có chữ = tóm tắt chỗ hỏng để hiện cảnh báo.
ALTER TABLE video ADD COLUMN hong TEXT NOT NULL DEFAULT '';
