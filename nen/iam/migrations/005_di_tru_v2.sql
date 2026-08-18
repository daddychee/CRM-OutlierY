-- 005: di trú nhân sự V2 (KE_HOACH_THAY_THE bước 2b) — 3 trường hồ sơ V2 chưa có
-- chỗ chứa: sdt/email (V2 giữ trên HỒ SƠ, khác email/dien_thoai của tai_khoan là
-- hồ sơ CÁ NHÂN tự sửa) + planner_id (nối KPI ↔ PlannerY, ns_ns005…). ghi_chu đã
-- có từ 001. Hồ sơ cũ thiếu trường → DEFAULT '' , hiển thị '—'.
ALTER TABLE nguoi ADD COLUMN sdt TEXT NOT NULL DEFAULT '';
ALTER TABLE nguoi ADD COLUMN email TEXT NOT NULL DEFAULT '';
ALTER TABLE nguoi ADD COLUMN planner_id TEXT NOT NULL DEFAULT '';
