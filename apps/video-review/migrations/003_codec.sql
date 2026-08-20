-- 003 — nhớ codec video (20/08/2026, sau sự cố "chỉ có tiếng, không có hình").
-- Trình duyệt chỉ giải mã được h264/av1/vp8/vp9; file H.265 (hevc) phát ra TIẾNG
-- mà hình đen, KHÔNG phát sự kiện lỗi nào → app phải tự biết mà báo.
-- Rỗng = chưa dò (bản ghi cũ, hoặc máy không có ffprobe) — không kết luận bừa.
ALTER TABLE video ADD COLUMN codec TEXT NOT NULL DEFAULT '';
