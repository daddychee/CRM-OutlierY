-- IAM v2 — migration 001: khởi tạo (chuẩn "migration có phiên bản" từ hiến pháp mục 2)
CREATE TABLE IF NOT EXISTS nguoi (
    ma          TEXT PRIMARY KEY,            -- NS-001 (bất biến, như doc_code)
    ho_ten      TEXT NOT NULL,
    bo_phan     TEXT NOT NULL,
    vi_tri      TEXT NOT NULL DEFAULT '',
    trang_thai  TEXT NOT NULL DEFAULT 'hoat_dong',  -- cho_duyet | hoat_dong | nghi
    tao_luc     TEXT NOT NULL,
    ghi_chu     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tai_khoan (
    ten             TEXT PRIMARY KEY,        -- tên đăng nhập (ASCII, không đổi)
    mk_bcrypt       TEXT NOT NULL,
    nguoi_ma        TEXT REFERENCES nguoi(ma) ON DELETE SET NULL,
    bo_phan         TEXT NOT NULL DEFAULT '',
    level           INTEGER NOT NULL DEFAULT 1,   -- thang 5 kế thừa hệ cũ
    admin_uy_quyen  INTEGER NOT NULL DEFAULT 0,   -- vai Admin ủy quyền (giỏ 2)
    phai_doi_mk     INTEGER NOT NULL DEFAULT 0,   -- YC6 kế thừa
    khoa            INTEGER NOT NULL DEFAULT 0,
    tao_luc         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quyen_override (  -- ô tick lẻ, thắng luật mặc định
    ten_tai_khoan  TEXT NOT NULL,
    app_slug       TEXT NOT NULL,            -- app hoặc '*' cho hành động cấp hệ
    hanh_dong      TEXT NOT NULL,
    cho_phep       INTEGER NOT NULL,         -- 1 = cho, 0 = chặn
    PRIMARY KEY (ten_tai_khoan, app_slug, hanh_dong)
);

CREATE TABLE IF NOT EXISTS nhat_ky_quyen (   -- audit: MỌI thay đổi danh tính/quyền
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    luc       TEXT NOT NULL,
    ai        TEXT NOT NULL,
    hanh_dong TEXT NOT NULL,
    chi_tiet  TEXT NOT NULL
);
