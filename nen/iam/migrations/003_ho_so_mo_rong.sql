-- 003: hồ sơ nhân sự MỞ RỘNG (DE.md mục 12.1 — Owner duyệt mockup H1b): lưu trữ
-- đầy đủ Ngày sinh / CCCD / Địa chỉ thường trú / Ngày vào làm / Cấp bậc.
-- CCCD NHẠY CẢM: app chỉ render bản CHE, xem đủ qua route gateway có vết
-- (khuôn audit vault). Hồ sơ cũ thiếu trường → DEFAULT '' , hiển thị '—'.
ALTER TABLE nguoi ADD COLUMN ngay_sinh TEXT NOT NULL DEFAULT '';
ALTER TABLE nguoi ADD COLUMN cccd TEXT NOT NULL DEFAULT '';
ALTER TABLE nguoi ADD COLUMN dia_chi TEXT NOT NULL DEFAULT '';
ALTER TABLE nguoi ADD COLUMN ngay_vao TEXT NOT NULL DEFAULT '';
ALTER TABLE nguoi ADD COLUMN cap_bac TEXT NOT NULL DEFAULT '';
