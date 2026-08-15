-- Két cấu hình v2 — migration 001. CONFIG ≠ SECRET (2 ngăn, hiến pháp mục 2.3).
CREATE TABLE IF NOT EXISTS cau_hinh (      -- không mật: model nào, timeout bao nhiêu
    khoa     TEXT PRIMARY KEY,
    gia_tri  TEXT NOT NULL,
    sua_luc  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bi_mat (        -- mật: API key — mã hóa, không bao giờ log
    khoa        TEXT PRIMARY KEY,
    gia_tri_ma  TEXT NOT NULL,             -- Fernet(giá trị)
    duoi        TEXT NOT NULL DEFAULT '',  -- 4 ký tự cuối để UI nhận diện ••••abcd
    sua_luc     TEXT NOT NULL
);
