-- Két v3 — Owner chốt 18/08 (check trùng key): thêm cột 'hash' = SHA-256 hex
-- của GIÁ TRỊ bí mật. Fernet mỗi lần mã hóa ra bản mã khác nhau nên không so
-- được bản mã — hash tất định mới phát hiện được cùng một khóa dán 2 lần.
-- Backfill cho dòng cũ đi cùng lượt backfill_dau_khoa (mở trang API Keys).
ALTER TABLE bi_mat ADD COLUMN hash TEXT NOT NULL DEFAULT '';
