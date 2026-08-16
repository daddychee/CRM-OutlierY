-- Danh bạ thực thể (mảnh ④) — DB thay CSV seed (DE.md mục 3, Owner chốt 16/08/2026).
-- Niche có TRƯỚC kênh (kenh.ngach_ma NOT NULL). Mã bất biến như doc_code.

CREATE TABLE thi_truong (
  ma       TEXT PRIMARY KEY,
  ten      TEXT NOT NULL,
  ngon_ngu TEXT NOT NULL DEFAULT '',
  ghi_chu  TEXT NOT NULL DEFAULT '',
  tao_luc  TEXT NOT NULL
);

CREATE TABLE ngach (
  ma        TEXT PRIMARY KEY,
  ten_chuan TEXT NOT NULL UNIQUE,
  trang_thai TEXT NOT NULL DEFAULT 'thu'
             CHECK (trang_thai IN ('khai_thac','thu','nghi')),
  ghi_chu   TEXT NOT NULL DEFAULT '',
  tao_luc   TEXT NOT NULL
);

CREATE TABLE kenh (
  ma          TEXT PRIMARY KEY,
  ten_chuan   TEXT NOT NULL,
  channel_id  TEXT UNIQUE,                 -- UCxxx; NULL khi chưa lập kênh YouTube
  ngach_ma    TEXT NOT NULL REFERENCES ngach(ma),
  thi_truong_ma TEXT REFERENCES thi_truong(ma),
  loai_kenh   TEXT NOT NULL DEFAULT '',    -- khóa content_type_profiles của Data Analytics
  trang_thai  TEXT NOT NULL DEFAULT 'uom_mam'
              CHECK (trang_thai IN ('uom_mam','sandbox','hoat_dong','monetized','ngu_dong','khai_tu')),
  kenh_goc_ma TEXT REFERENCES kenh(ma),    -- bản dịch → kênh gốc (Owner: 2 kênh riêng)
  phu_trach   TEXT NOT NULL DEFAULT '',    -- mã NS-xxx từ IAM, '' = chưa gán
  bo_phan_chu_quan TEXT NOT NULL DEFAULT '',
  ghi_chu     TEXT NOT NULL DEFAULT '',
  tao_luc     TEXT NOT NULL,
  nguoi_tao   TEXT NOT NULL DEFAULT ''
);

-- Bí danh UNIQUE TOÀN CỤC (đã chuẩn hóa) — hai thực thể không giành một alias.
CREATE TABLE bi_danh (
  bi_danh     TEXT PRIMARY KEY,
  thuc_the_ma TEXT NOT NULL,
  tao_luc     TEXT NOT NULL
);

-- Khóa của thực thể ở từng app (thay 5 cột cứng CSV + CAC_COT_KHOA hardcode).
CREATE TABLE lien_ket_app (
  thuc_the_ma TEXT NOT NULL,
  app_slug    TEXT NOT NULL,
  khoa        TEXT NOT NULL,
  tao_luc     TEXT NOT NULL,
  PRIMARY KEY (thuc_the_ma, app_slug)
);
