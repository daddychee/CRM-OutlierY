-- 006: mục "ĐÃ THÔI VIỆC" (Owner chốt 19/08: "nhân sự đã nghỉ không xóa hẳn mà
-- cho vào mục đã thôi việc"). Trạng thái 'nghi' đã có từ 001 nhưng KHÔNG có chỗ
-- ghi NGÀY nghỉ + LÝ DO → mục thôi việc chỉ là bộ lọc trạng thái, không tra được
-- ai nghỉ lúc nào. Hồ sơ cũ thiếu trường → DEFAULT '', UI hiển thị '—'.
-- Tên cột là ngay_THOI_VIEC (không phải ngay_nghi) để khỏi lẫn với "ngày nghỉ
-- phép" của tab Leaves — hai khái niệm khác hẳn nhau.
ALTER TABLE nguoi ADD COLUMN ngay_thoi_viec TEXT NOT NULL DEFAULT '';
ALTER TABLE nguoi ADD COLUMN ly_do_thoi_viec TEXT NOT NULL DEFAULT '';
