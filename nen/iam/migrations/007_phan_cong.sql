-- 007: PHÂN CÔNG (trục B — "ai làm việc trên ĐỐI TƯỢNG nào"), Owner chốt 24/08/2026.
--
-- Trục A (NĂNG LỰC — "được làm LOẠI việc gì") đã có: phan_quyen.json + quyen_override.
-- Trục B trả lời câu còn lại: trên KÊNH nào, THỊ TRƯỜNG nào, DỰ ÁN nào. Trước 24/08 mỗi
-- app tự giữ một mẩu (SEO: profile.created_by + users.json; RadarY: members; PlannerY:
-- phân công trong plan.json) — nên cấp quyền ở nền xong vẫn phải vào từng app gán lại, và
-- hai bên lệch nhau thì hỏng CÂM (sự cố 24/08: đổi chủ kênh 400 vì tên người mới không có
-- trong sổ di sản V2 của app).
--
-- Nền CỐ Ý không biết "kênh" là gì: chỉ giữ cặp NGƯỜI ↔ MÃ ĐỐI TƯỢNG. `loai` do app khai,
-- `ma` là khóa của app. Nền chỉ kiểm một điều — người nhận phải VÀO ĐƯỢC app đó.
--
-- ma='*' = toàn bộ đối tượng loại này (giao cả thị trường thay vì bấm từng kênh).
CREATE TABLE IF NOT EXISTS phan_cong (
    app_slug      TEXT NOT NULL,          -- 'seo-optimize'
    loai          TEXT NOT NULL,          -- 'kenh' | 'thi_truong' | 'du_an'… (app khai)
    ma            TEXT NOT NULL,          -- khóa đối tượng bên app; '*' = tất cả
    ten_tai_khoan TEXT NOT NULL,
    ghi_chu       TEXT NOT NULL DEFAULT '',
    ai_gan        TEXT NOT NULL DEFAULT '',
    luc           TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (app_slug, loai, ma, ten_tai_khoan)
);

-- Đường tra NÓNG: mỗi request app hỏi "người này được ghi lên gì" (iam.pham_vi).
CREATE INDEX IF NOT EXISTS idx_phan_cong_nguoi ON phan_cong (ten_tai_khoan, app_slug);
