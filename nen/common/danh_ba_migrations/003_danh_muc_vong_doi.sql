-- 003: đổi TẬP GIÁ TRỊ vòng đời (Owner chốt 24/08/2026).
--   Ngách:  khai_thac · mo_rong (Scaling) · duy_tri (Maintaining) · nghi
--           — bỏ 'thu' (Testing): 0 ngách dùng trên DB thật lúc di trú.
--   Kênh:   uom_mam · sandbox · hoat_dong · monetized · shadow_ban (mới)
--           + khai_tu GIỮ (nấc ẨN cho gỡ mềm) — bỏ 'ngu_dong' (Dormant): 0 kênh dùng.
-- MAP giá trị đã bỏ (DB đời cũ ở máy khác / bản khôi phục vẫn có thể còn): 'thu'
-- → 'khai_thac' (nấc đầu, = mặc định mới), 'ngu_dong' → 'khai_tu' (kênh ngủ đông
-- ≈ đã gỡ khỏi vận hành). KHÔNG map thì CHECK mới làm migration chết giữa chừng.
-- Đổi CHECK constraint trong SQLite = phải dựng lại bảng. KHÔNG map/đổi giá trị
-- nào của dữ liệu đang có; chỉ index tự sinh (PK/UNIQUE) được tái tạo theo schema.
PRAGMA foreign_keys=OFF;

CREATE TABLE ngach_moi (
  ma        TEXT PRIMARY KEY,
  ten_chuan TEXT NOT NULL UNIQUE,
  trang_thai TEXT NOT NULL DEFAULT 'khai_thac'
             CHECK (trang_thai IN ('khai_thac','mo_rong','duy_tri','nghi')),
  ghi_chu   TEXT NOT NULL DEFAULT '',
  tao_luc   TEXT NOT NULL
);
INSERT INTO ngach_moi (ma, ten_chuan, trang_thai, ghi_chu, tao_luc)
  SELECT ma, ten_chuan,
         CASE trang_thai WHEN 'thu' THEN 'khai_thac' ELSE trang_thai END,
         ghi_chu, tao_luc FROM ngach;
DROP TABLE ngach;
ALTER TABLE ngach_moi RENAME TO ngach;

CREATE TABLE kenh_moi (
  ma          TEXT PRIMARY KEY,
  ten_chuan   TEXT NOT NULL,
  channel_id  TEXT UNIQUE,
  ngach_ma    TEXT NOT NULL REFERENCES ngach(ma),
  thi_truong_ma TEXT REFERENCES thi_truong(ma),
  loai_kenh   TEXT NOT NULL DEFAULT '',
  trang_thai  TEXT NOT NULL DEFAULT 'uom_mam'
              CHECK (trang_thai IN ('uom_mam','sandbox','hoat_dong','monetized',
                                    'shadow_ban','khai_tu')),
  kenh_goc_ma TEXT REFERENCES kenh(ma),
  phu_trach   TEXT NOT NULL DEFAULT '',
  bo_phan_chu_quan TEXT NOT NULL DEFAULT '',
  ghi_chu     TEXT NOT NULL DEFAULT '',
  tao_luc     TEXT NOT NULL,
  nguoi_tao   TEXT NOT NULL DEFAULT ''
);
INSERT INTO kenh_moi SELECT ma, ten_chuan, channel_id, ngach_ma, thi_truong_ma,
  loai_kenh,
  CASE trang_thai WHEN 'ngu_dong' THEN 'khai_tu' ELSE trang_thai END,
  kenh_goc_ma, phu_trach, bo_phan_chu_quan, ghi_chu, tao_luc, nguoi_tao FROM kenh;
DROP TABLE kenh;
ALTER TABLE kenh_moi RENAME TO kenh;

PRAGMA foreign_keys=ON;
