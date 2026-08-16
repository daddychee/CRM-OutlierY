-- 002: hồ sơ cá nhân tự cập nhật (UI_FLOW.md mục 8 — trang Profile).
-- Display name hiện ở chip đáy sidebar; email/điện thoại tự khai.
-- Bộ phận + level KHÔNG nằm đây — Owner quản ở trang Accounts.
ALTER TABLE tai_khoan ADD COLUMN ten_hien_thi TEXT NOT NULL DEFAULT '';
ALTER TABLE tai_khoan ADD COLUMN email TEXT NOT NULL DEFAULT '';
ALTER TABLE tai_khoan ADD COLUMN dien_thoai TEXT NOT NULL DEFAULT '';
