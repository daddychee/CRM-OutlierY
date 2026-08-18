-- 001 — khởi tạo sổ video + bình luận (Video Review v0.1)
-- video.ma là MÃ BẤT BIẾN (VR-0001…) nối sổ ↔ file trong kho — không bao giờ đổi.
CREATE TABLE IF NOT EXISTS video (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ma         TEXT UNIQUE NOT NULL,
  ten        TEXT NOT NULL,
  ten_file   TEXT NOT NULL,
  duong      TEXT NOT NULL,             -- đường tương đối trong kho (năm/tháng/file)
  mime       TEXT NOT NULL,
  kich_thuoc INTEGER NOT NULL,
  nguoi_tao  TEXT NOT NULL,
  bo_phan    TEXT NOT NULL DEFAULT '',
  trang_thai TEXT NOT NULL DEFAULT 'dang_duyet',  -- dang_duyet|can_sua|da_duyet|da_xoa
  tao_luc    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS binh_luan (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  video_ma   TEXT NOT NULL,
  nguoi      TEXT NOT NULL,
  noi_dung   TEXT NOT NULL,
  ts_giay    REAL,                      -- NULL = bình luận chung, không gắn mốc
  ve_json    TEXT,                      -- nét vẽ chú thích trên khung hình (JSON, tọa độ 0..1)
  trang_thai TEXT NOT NULL DEFAULT 'mo',-- mo|da_giai
  tao_luc    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bl_video ON binh_luan(video_ma);
