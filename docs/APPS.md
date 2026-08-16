# APPS.md — sổ chủ đề ĐƯA APP VÀO V3 (Đ4)

> Owner lệnh 16/08/2026: đưa 6 app vào V3, TỪNG APP MỘT, chạy được thật,
> phân quyền theo Permissions v2 (hành động khai trong luật → tự hiện ô tick),
> dữ liệu đúng cấu trúc `data\<slug>\` + khai `du_lieu` (SO_DIA_BA_DU_LIEU.md).
> Thứ tự: RadarY → Content Ultimate → SEO Optimize → (Data Analytics đã ở V3)
> → PlannerY → SpeakY. NAS = nút đáy sidebar.

## Quyết định Owner đã chốt (16/08)

1. **Dữ liệu: SNAPSHOT từ hệ thật** — copy chỉ-đọc từ C:\OutlierY (hệ cũ chạy
   nguyên phục vụ team, song song tới cutover); ngày cutover đồng bộ lần cuối.
   SQLite đang chạy → backup API/mode=ro, KHÔNG copy trần (luật sổ địa bạ).
2. **NAS: CHỈ trang chỉ đường** (ổ + map ổ như V2). KHÔNG đồng bộ tài khoản
   Windows từ V3 khi C:\ còn là nguồn sự thật — bật khi cutover.

## Khung 6 bước MỖI app

1. Chép code từ C:\ (loại .git/__pycache__/data/logs) → `apps\<slug>`, venv riêng.
2. Hợp đồng apps.json: cổng 91xx (PORTS.md trước), tien_to, vao, hanh_dong thật
   + quan_tri + vai_xoa → tự hiện trang Permissions.
3. Snapshot dữ liệu → `data\<slug>\` + khai du_lieu (mức quý theo sổ địa bạ).
4. SSO adapter: đọc claims V3 (X-Remote-Actions + vai chuẩn `admin`), vá bẫy
   đã biết từng app, DEFAULT vai thấp nhất, rà mọi chỗ đọc cookie.
5. **Khóa + quản trị app PHẢI về MỘT CỬA V3 NGAY trong đợt app đó** (luật Owner
   16/08 — "làm gọn từng app trước khi sang app khác"): nguồn khóa = két trang
   API Keys (app lấy qua loopback `/api/cau-hinh/api-khoa/<slug>` mỗi run, không
   fallback sổ nội bộ); mọi cửa quản trị key/thành viên/cấu hình TRONG app đóng
   404 khi SSO — kể cả vai cao nhất nội bộ.
6. **App ngoài (SPA tự render trọn trang) mở qua `/open/<slug>` — sidebar KHÔNG
   BAO GIỜ mất** (Owner 16/08): hợp đồng khai `giao_dien: "khung"`; sidebar +
   khối menu app tự trỏ `/open/<slug>` thay `/app/<slug>`; route render shell
   OUTLIERY (sidebar/topbar chuẩn) + `<iframe src="/app/<slug>/">` cùng origin
   (cookie/back trình duyệt tự ăn); gate y hệt cửa vào app; `/app/<slug>` thẳng
   vẫn sống (bookmark cũ, không redirect — tránh vòng lặp iframe); proxy cắt
   `X-Frame-Options` + CSP `frame-ancestors` CHỈ ở response app khung. App
   native (tự vẽ sidebar OUTLIERY trong template) KHÔNG khai — giữ `/app/<slug>`.
6. Nghiệm thu sống qua 9443 từng vai (Chrome headless cho bẫy proxy) → commit.

## Bảng phân công

| # | App | Cổng | Data | Quyền (khai Permissions) | Trạng thái |
|---|---|---|---|---|---|
| 1 | RadarY | 9111 | data\radary\ (db 88M + niche 41M + reports; thumbs 636M TÁI-SINH không snapshot) | mọi BP L1 xem · them_video/tao_pool KD L3 · toan_quyen Manager chủ quản (vai manager) · quan_tri Owner | **ĐANG LÀM** |
| 2 | Content Ultimate | 9112 | data\content-ultimate\ | VH L2 · sua L3 leader · quan_tri Owner | chờ |
| 3 | SEO Optimize | 9113 | data\seo-optimize\ | KD L2 vai seo · sua L3 · toan_quyen L4 manager · quan_tri Owner | chờ |
| 4 | Data Analytics | 9102 | data\data-analytics\ | đã trong V3 từ đầu | XONG (còn Đ2.2 nối danh bạ) |
| 5 | PlannerY | 9114 | data\plannery\ | mọi BP L1 · them_kenh_video KD L2 seo · sua L3 · quan_tri Owner + VÁ bẫy users.json thắng header | chờ |
| 6 | SpeakY | 9115 | data\speaky\ | VH L2, quyền ở cửa vào; model dùng chung HF cache máy | chờ |
| — | NAS | — | — | nút đáy sidebar, trang chỉ đường | chờ |

## Bẫy phải nhớ khi đưa app (từ V2 + memory)

- Proxy 5 bẫy: importmap/vendor · tên có dấu · ETag cache · guard Origin-vs-Host
  chặn POST (dạy app nhận X-Forwarded-Host) · kiểm bằng Chrome headless.
- SpeakY/Gradio: root_path, X-Forwarded-Host/Proto, Location đúp tiền tố.
- 13 luật quyền (DE.md mục 14): tick chảy mỗi request, cấm map theo tên,
  DEFAULT thấp nhất, test user "trắng", endpoint nhạy cảm sau cổng…
- Sửa nen/common là restart MỌI app import nó.
- App chết không được giết cổng 9000 (van an toàn kiểu Qdrant hệ cũ).

## Nhật ký

- 16/08/2026 — Mở sổ; Owner chốt 2 quyết định; bắt đầu RadarY (cổng 9111).
- 16/08/2026 — **RadarY tích hợp xong bước 1-4+6** (chạy thật 9111, hợp đồng +
  luật Permissions v2, SSO adapter Actions→vai nội bộ, smoke từng vai đạt trên
  snapshot thật — org Outliery, 19 khóa). Chạy: `tools\scripts\start-all.ps1`
  (env `RADARY_DATA_DIR=data\radary` + `RADARY_SCHEDULER=0` + `RADARY_TRUST_PROXY=1`).
  **SCHEDULER V3 TẮT CỐ ĐỊNH**
  (`RADARY_SCHEDULER=0` trong start-all): hệ thật C:\ vẫn tự quét theo lịch bằng
  CÙNG bộ khóa — V3 quét song song là ĐỐT ĐÔI QUOTA + db snapshot lệch khỏi hệ
  thật; nghiệm thu quét bằng POST /run tay; bật lại scheduler CHỈ khi cutover.
  RADARY_SSO_MAP đã GỠ HẲN khỏi V3 (map-tên-chết); cửa login/register/reset cục
  bộ đóng 404 khi TRUST_PROXY=1.
- 16/08/2026 — **RadarY LÀM GỌN xong** (luật Owner "gọn từng app rồi mới sang
  app khác" — việc treo Đ4b HỦY, làm ngay): (1) 14 endpoint quản trị org (keys ×5
  · members ×3 · invites ×3 · LLM ×3) đóng 404 khi SSO KỂ CẢ vai owner nội bộ —
  khóa nhập ở General › API Keys, quyền ở General › Permissions; tab Quản trị
  app.js ẨN HẲN khi `me.sso` (cả lọc tab lẫn chặn render). **LƯU Ý CAPABILITY:
  khối "Xóa niche" nằm trong tab đó cũng mất UI khi SSO** (endpoint DELETE
  workspace vẫn sống — vận hành manager); cần thì chuyển nút xóa sang tab
  Settings từng niche đợt sau. (2) Nguồn khóa = KÉT V3: radary khai `viec_api`
  harvest/quet_dinh_ky (youtube) + dien_giai (llm); gateway loopback MỚI
  `GET /api/cau-hinh/api-khoa/{slug}`; `radary/khoa_v3.py` lấy khóa MỖI run —
  gateway chết/việc chưa cấp → run DỪNG thông điệp rõ "chưa lấy được khóa từ
  OUTLIERY", KHÔNG rơi về bảng nội bộ (bảng `api_keys` NGHỈ — giữ làm sử liệu).
  (3) Migration một lần `scripts/di_tru_khoa_radary.py` (idempotent, marker két,
  GIỮ NGĂN V2: harvest=1→việc harvest, còn lại→quet_dinh_ky, đều xoay vòng; vết
  audit CHỈ ĐUÔI) — **Owner quyết thời điểm chạy thật**; chạy xong mới nghiệm
  thu quét. Suite radary 8 test.
- 16/08/2026 — **Owner DUYỆT RadarY làm gọn** + yêu cầu mới "mở app vẫn còn
  sidebar" (SPA app ngoài trước đó chiếm trọn trang khi vào `/app/<slug>`).
  **KHUNG MỞ APP GIỮ SIDEBAR làm xong** (bước 6 ở trên): route
  `GET /open/{slug}` + `nen_khung_app.html` (iframe cùng origin); radary +
  content-ultimate khai `giao_dien: "khung"` trong apps.json; sidebar 4
  template (to-chuc/DA/ai-agent base.html + hoi_dap.html) đổi `href="/app/{{
  a.slug }}"` → `href="{{ a.href }}"` (nguồn `sb_apps_tu_claims` tính sẵn).
  Test mới `tests/test_khung_app.py` (6 ca: gate/404/native/sidebar-href/strip-
  header) + `test_radary.py` sửa 1 assert. 5 suite: root 136(+6) · radary 8 ·
  ai-agent 308+3skip · DA 64 · to-chuc 58 — tất cả pass. **BẪY GHI LẠI: sửa
  nen/common (sidebar.py, proxy.py) + nen/gateway PHẢI RESTART mọi app import
  (ai-agent/DA/to-chuc/gateway) mới thấy sidebar mới** — Owner tự restart.
  Content Ultimate vẫn ĐỨNG YÊN, chưa đụng tiếp đợt này.
- 16/08/2026 — BẪY MỚI khi agent ghi start-all.ps1: chuỗi `data\radary` bị nuốt
  `\r` thành byte xuống dòng thật (0x0D) → comment gãy đôi thành lệnh, script
  chết trước khi bật service nào. Sửa bằng thay byte, đường dẫn trong .ps1 từ
  nay dùng GẠCH CHÉO XUÔI `data/radary` (Join-Path/Python đều hiểu) — cùng họ
  bẫy PowerShell 5.1 (memory powershell-51-utf8-bom-va-log).
- 16/08/2026 — RadarY NGHIỆM THU ĐỘC LẬP đạt (curl 9111 + qua cổng): health
  200 · không claims 401 · viewer đọc orgs · manager(toan_quyen) /keys 403
  (Manager không ngang Owner) · owner(quan_tri) 200 · login cục bộ body hợp lệ
  404 (422 khi thiếu body = validation chạy trước guard, route vẫn bất khả
  dụng) · /app/* không auth 401 trần là chuẩn chung nền. 5 suite xanh
  124+3+308/3+64+58. CÒN CHỜ OWNER: soi UI RadarY qua 9443 (SPA/Console),
  tick thử ở Permissions, POST /run tay 1 pool giờ thấp điểm (đốt quota thật).
