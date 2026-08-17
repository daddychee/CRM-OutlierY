-- Két v3 — Owner chốt 17/08: hiển thị khóa API dạng "dau···duoi" (3 ký tự đầu +
-- 3-4 cuối) thay vì chỉ "••••duoi" — chỉ đuôi không đủ nhận diện khi nhiều khóa
-- na ná nhau. Thêm cột 'dau' ngang hàng 'duoi' (đã có từ migration 001).
ALTER TABLE bi_mat ADD COLUMN dau TEXT NOT NULL DEFAULT '';
