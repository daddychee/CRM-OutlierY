ALTER TABLE video ADD COLUMN loai TEXT NOT NULL DEFAULT 'duyet';
ALTER TABLE video ADD COLUMN ma_tap TEXT NOT NULL DEFAULT '';
ALTER TABLE video ADD COLUMN yt_id TEXT NOT NULL DEFAULT '';
ALTER TABLE video ADD COLUMN dang_luc TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS giu_chan (
  ma_tap      TEXT PRIMARY KEY,
  video_ma    TEXT NOT NULL,
  hook_30     REAL,
  avd_giay    REAL,
  giu_tb      REAL,
  duong_cong  TEXT NOT NULL DEFAULT '',
  nguon_anh   TEXT NOT NULL DEFAULT '',
  lech_neo    REAL,
  nguoi_nhap  TEXT NOT NULL DEFAULT '',
  tao_luc     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nhan_xet_may (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  video_ma  TEXT NOT NULL,
  ts_giay   REAL,
  ts_het    REAL,
  benh      TEXT NOT NULL,
  muc       TEXT NOT NULL DEFAULT 'nhe',
  loi       TEXT NOT NULL DEFAULT '',
  so_lieu   TEXT NOT NULL DEFAULT '',
  nen_lam   TEXT NOT NULL DEFAULT '',
  trich_kb  TEXT NOT NULL DEFAULT '',
  phan      TEXT NOT NULL DEFAULT '',
  phan_nguoi TEXT NOT NULL DEFAULT '',
  da_doc    INTEGER NOT NULL DEFAULT 0,
  tao_luc   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nx_video ON nhan_xet_may(video_ma);
CREATE INDEX IF NOT EXISTS idx_video_tap ON video(ma_tap);
