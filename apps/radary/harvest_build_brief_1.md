# BRIEF CODE — Module HARVEST cho Radary

> Dán brief này cho AI coding agent trong VSCode (Claude Code / Cursor).
> Đọc kèm: `docs/spec_harvest.md`, `radary_methodology.md`, `CLAUDE.md`.

---

## 0. Ngữ cảnh dự án (đọc trước khi code)

Radary = FastAPI + SQLite + React (Preact/htm, no build), đa workspace, chạy production trên VPS. Engine lõi thuần stdlib. Đọc `CLAUDE.md` để nắm nguyên tắc — đặc biệt:
- **NP1 Spec-trước:** spec `spec_harvest.md` là nguồn sự thật. Lệch spec = bug. Đổi hành vi → sửa spec trước.
- **NP2 Đơn giản:** chỉ thêm gói khi có lệnh user. Engine lõi không dependency.
- **NP3 Phẫu thuật:** KHÔNG chạm code/DB đang chạy tốt. Harvest là module MỚI, đứng riêng.
- **NP5:** máy đề xuất, người quyết.

## 1. Yêu cầu cốt lõi (một câu)

Xây module `harvest` **độc lập, read-only, advisory**: nhận list kênh → phân rã thành nhóm ngách → snowball mở rộng → xuất REPORT. **TUYỆT ĐỐI không ghi vào DB pool/workspace/tick/event sống.** Output chỉ là report (bảng riêng hoặc file), user tự áp dụng qua luồng pool có sẵn.

## 2. Vị trí trong codebase

- Code lõi: `radary/harvest/` (package mới, cạnh `radary/niche/`).
  - `fingerprint.py` — vân tay title (n-gram, centroid, cosine), long-form ratio, phát hiện ngôn ngữ (function-word, KHÔNG dùng lib ngoài — tự viết cho EN/ES/PT + dấu hiệu ã/õ/ç, ñ/¿).
  - `decompose.py` — phân rã 2 tầng (ngôn ngữ → định dạng), sinh cây + mô tả.
  - `snowball.py` — mở rộng đến hội tụ (centroid đóng băng, cửa 3 search, chấm 2 tầng).
  - `audience.py` — co-occurrence author (LUÔN BẬT), chuẩn hoá tỷ lệ, báo cỡ mẫu.
  - `runner.py` — job nền, checkpoint, ước tính quota, resumable, `RADAR_BUDGET`.
- Tái dùng: `radary/scan.API` (gọi YouTube + xoay key 403→dự phòng), `radary/scheduler` (job nền), pattern của `radary/niche_report` (report nền).
- API: thêm endpoint dưới `radary/api` (nhóm route `/harvest/*`), phân quyền `editor`+ để chạy.
- UI: thêm màn hình "Harvest" trong `web/app.js` (tab mới), theo pattern các tab hiện có (URL hash state, no-cache).

## 3. Data model (đề xuất — bảng MỚI, không đụng bảng cũ)

Bảng riêng cho harvest, cô lập hoàn toàn với `channels`/`videos`/`events`:
- `harvest_jobs` (id, org_id, workspace_id nullable, mode SEED|POOL, input_raw, status, quota_est, quota_used, created_at, checkpoint_json).
- `harvest_results` (job_id, group_key, channel_id, title, subs, voc, long_ratio, core_ov, broad_ov, n_auth, round_found, tier, reason_pro, reason_con).
- `harvest_groups` (job_id, group_key, lang, format_bucket, centroid_json, description, n_channels).

Report đọc từ 3 bảng này. XÓA job = xóa 3 bảng này, KHÔNG ảnh hưởng gì pool sống.

## 4. Luồng thực thi (theo spec §4)

1. Parse input → resolve handle→channelId (dùng `scan.API`). Đếm kênh hợp lệ → chọn SEED (≤5) / POOL (>5). User ghi đè được.
2. **Ước tính quota + hiện cho user duyệt TRƯỚC khi chạy** (comment luôn bật → chi phí cao, cảnh báo rõ).
3. Job nền:
   - POOL: phân rã (`decompose`) → lưu `harvest_groups` → trả report cây → CHỜ user chọn nhóm.
   - Nhóm được chọn (hoặc toàn bộ list ở SEED): snowball (`snowball`) đến hội tụ, checkpoint mỗi vòng.
4. Sinh report cuối vào `harvest_results`. Hiện UI.
5. User đọc report, tự thêm/bớt/xóa kênh qua tab Pool hiện có. Harvest KHÔNG làm bước này.

## 5. Ngưỡng (từ spec §5, để trong config, không hardcode rải rác)

- Tầng 1 vào pool: `voc≥15` VÀ `long_ratio≥0.6` VÀ `subs≥5000` (user chỉnh).
- Luật kép: hạng A khi mạnh ≥2 trục (aud≥2 / voc≥15 / subs≥5K / long≥60%).
- Hội tụ snowball: vòng đẻ ≤1 kênh mới đạt chuẩn.
- Phân rã định dạng: sleep-ambient med≥2400s; long-form lr≥0.7; short lr≤0.3.
- Cỡ mẫu author tin cậy: ≥30 (dưới ngưỡng gắn cờ ⚠).

## 6. Ràng buộc BẮT BUỘC (vi phạm = làm lại)

- Mọi trường YouTube response dùng `.get()` phòng thủ (sự cố `duration` thiếu ở livestream giết cả pool — CLAUDE.md).
- Job resumable, checkpoint sau mỗi kênh/vòng, in `PAUSE — chạy lại để tiếp` khi cạn `RADAR_BUDGET`.
- Xoay key 403→dự phòng (tái dùng `scan.API`, không viết lại).
- Ghi file qua tmp + `os.replace` (dùng `jsave` sẵn có).
- API key/secret KHÔNG log, KHÔNG commit.
- KHÔNG import code render vào engine (tách tầng — NP6).

## 7. Nghiệm thu (viết test TRƯỚC, kiểu verify_phaseN.py)

Tạo `verify_harvest.py`:
- SEED mode: 3 kênh Life-in-Country → hội tụ (đà kênh mới giảm về ≤1), pool ≥15 kênh.
- POOL mode: pool Space 86 kênh → phân rã ra ≥3 nhóm ngôn ngữ, EN tách ≥3 nhóm định dạng.
- Đối chứng ÂM: kênh long-form thấp (NASA/Yes Theory) KHÔNG lọt hạng A.
- Read-only: chạy full job, assert 0 dòng bị ghi/sửa/xóa trong `channels`/`videos`/`events`/pool sống.
- Idempotent: chạy lại job = kết quả như cũ, không nhân đôi.
- Quota: chạy với `RADAR_BUDGET=25` không crash, in PAUSE đúng.

## 8. Thứ tự làm (nhỏ, kiểm được từng bước)

1. `fingerprint.py` + test đơn vị (vân tay, ngôn ngữ, long-form) — thuần stdlib.
2. `decompose.py` + test trên Space (offline fixture nếu có).
3. `audience.py` + `snowball.py` + test hội tụ.
4. `runner.py` (job nền, checkpoint, quota).
5. API endpoints + phân quyền.
6. UI tab Harvest.
7. `verify_harvest.py` chạy xanh toàn bộ.

Sau mỗi bước: chạy lại các `verify_phase{1,2,3,4}.py` hiện có để chắc KHÔNG làm hỏng gì đang chạy.

## 9. Ranh giới — KHÔNG làm (spec §8)

Không tạo workspace tự động · không ghi pool sống · không tự gỡ kênh · không khuyến nghị "nên đánh" · không đo thể loại faceless/narrator (API mù, user đã bỏ).

## 10. Câu hỏi mở cần user chốt trước khi code phần liên quan (spec §9)

Ngưỡng SEED/POOL=5 · TTL report · gộp nhóm để snowball chung · snowball song song/tuần tự. Nếu chưa chốt, để mặc định trong config và ghi TODO, đừng tự quyết ngầm.
