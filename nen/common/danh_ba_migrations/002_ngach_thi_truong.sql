-- 002: thị trường THUỘC TỪNG NGÁCH, do user CHỌN (Owner chốt 18/08/2026) —
-- sửa bệnh "mọi niche mặc định có cả 3 thị trường" (bảng thi_truong là danh mục
-- toàn cục, trước không có liên kết ngách↔thị trường nên UI liệt kê tất cho mọi ngách).
-- Ngách mới tạo = 0 thị trường tới khi user chọn. Backfill từ THỰC TẾ: ngách nhận
-- các thị trường mà kênh của nó đang đứng (không bịa mặc định).
CREATE TABLE ngach_thi_truong (
  ngach_ma      TEXT NOT NULL REFERENCES ngach(ma) ON DELETE CASCADE,
  thi_truong_ma TEXT NOT NULL REFERENCES thi_truong(ma),
  tao_luc       TEXT NOT NULL,
  PRIMARY KEY (ngach_ma, thi_truong_ma)
);

INSERT INTO ngach_thi_truong (ngach_ma, thi_truong_ma, tao_luc)
  SELECT DISTINCT ngach_ma, thi_truong_ma, datetime('now')
  FROM kenh WHERE thi_truong_ma IS NOT NULL;
