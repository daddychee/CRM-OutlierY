-- 004 — quy trình duyệt còn ĐÚNG BA BƯỚC (user chốt 20/08/2026):
--   Awaiting review (chưa ai bình luận) → In review (đang xem) → Approved.
-- 'can_sua' (Changes requested) nghỉ hưu: yêu cầu sửa nằm trong BÌNH LUẬN, không
-- cần một trạng thái riêng. Bản ghi cũ đưa về 'dang_duyet' — vẫn là việc đang làm.
UPDATE video SET trang_thai = 'dang_duyet' WHERE trang_thai = 'can_sua';
