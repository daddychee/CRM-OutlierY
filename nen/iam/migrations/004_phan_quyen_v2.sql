-- 004: Permissions v2 (DE.md mục 14 — mockup P1-P5 Owner duyệt).
-- CẤP TRUY CẬP (acting): truy cập như cấp 1-4, chức danh thật không đổi,
-- KHÔNG BAO GIỜ áp lên Owner thật (chống tự khóa — chặn ở iam.dat_cap_truy_cap).
CREATE TABLE IF NOT EXISTS cap_truy_cap (
    ten     TEXT PRIMARY KEY,           -- tên tài khoản
    cap     INTEGER NOT NULL,           -- 1..4
    ly_do   TEXT NOT NULL DEFAULT '',
    ai_gan  TEXT NOT NULL DEFAULT '',
    luc     TEXT NOT NULL DEFAULT ''
);
-- Ngoại lệ PHẢI CÓ LÝ DO (mockup P5: người/app/hành động/đặt/lý do/ngày·ai gán)
ALTER TABLE quyen_override ADD COLUMN ly_do TEXT NOT NULL DEFAULT '';
ALTER TABLE quyen_override ADD COLUMN ai_gan TEXT NOT NULL DEFAULT '';
ALTER TABLE quyen_override ADD COLUMN luc TEXT NOT NULL DEFAULT '';
