-- Note review kịch bản (tab Writing Review, 04/09/2026).
-- Gắn theo (run, chương) — KHÔNG theo mã tập, vì kịch bản có trước khi tập được
-- gán mã; đổi mã tập sau không làm mất note. Kho kịch bản của Content Ultimate
-- vẫn CHỈ ĐỌC: note nằm ở sổ của ReviewY, không ghi ngược sang app kia.
CREATE TABLE IF NOT EXISTS note_kich_ban (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  run       TEXT NOT NULL,
  chuong    TEXT NOT NULL DEFAULT '',
  nguoi     TEXT NOT NULL,
  la_may    INTEGER NOT NULL DEFAULT 0,   -- 0 người · 1 máy đo
  muc       TEXT NOT NULL DEFAULT '',     -- nặng / vừa / đạt (chỉ thẻ máy)
  noi_dung  TEXT NOT NULL,
  tao_luc   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_note_kb_run ON note_kich_ban (run, chuong);

-- Mốc chốt kịch bản: chốt rồi mới cho dựng (user chốt "bắt buộc review trước khi dựng").
CREATE TABLE IF NOT EXISTS kich_ban_chot (
  run      TEXT PRIMARY KEY,
  ma_tap   TEXT NOT NULL DEFAULT '',
  nguoi    TEXT NOT NULL,
  chot_luc TEXT NOT NULL DEFAULT (datetime('now'))
);
