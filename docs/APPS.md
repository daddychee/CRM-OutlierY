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
5. Khóa API từ trang API Keys (cấp phát → app nhận lúc khởi động qua loopback).
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
