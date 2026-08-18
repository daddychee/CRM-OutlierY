# CLAUDE.md — app video-review (nhật ký + bài học riêng app, Luật 3)

## Mốc

- 18/08/2026 — **DỰNG APP MỚI v0.1** (app V3 đầu tiên KHÔNG di trú từ hệ cũ —
  viết mới theo khuôn to-chuc): upload bản dựng → bình luận gắn mốc thời gian
  (bấm là tua) + vẽ chú thích canvas trên khung hình (tọa độ 0..1) → trạng thái
  duyệt 3 nấc + gỡ mềm. 18 test pass. Đăng ký đủ 4 chỗ: PORTS.md (9114) ·
  apps.json (hợp đồng + 2 store du_lieu) · phan_quyen.json (vao L1 / duyet L3 /
  xoa L4) · start-all.ps1. Sidebar Tools tự nhận qua hợp đồng, không sửa gateway.

- 18/08/2026 — **NẠP TỪ NAS** (user chốt sau khi bàn 5 vấn đề upload; chọn
  "chép vào kho"): `src/nap_nas.py` — duyệt thư mục server-side trong root
  `VR_NAS_DIR` (đường tương đối + kiểm nằm-trong-root, ngoài root = 404 lặng
  lẽ), chép NỀN có % thật theo byte (BackgroundTasks hàm sync → threadpool),
  CHÉP XONG MỚI ghi sổ (hỏng giữa chừng = không có bản ghi ma, file tạm tự dọn),
  file gốc NAS chỉ-đọc; trần riêng `VR_NAS_MAX_MB` 20GB vì không qua proxy.
  26 test pass (8 test NAS mới). Khối UI ẩn tới khi Owner khai VR_NAS_DIR (.env).
- 18/08/2026 — **UPLOAD CÓ % TIẾN ĐỘ**: XMLHttpRequest upload.onprogress (fetch
  không đo được), form thuần giữ làm fallback khi JS chết (lệ LAN-HTTP); % đo
  chặng trình duyệt→gateway nên 100% xong còn "Processing…" một nhịp (gateway
  buffer rồi mới chuyển app) — hành vi đúng, đừng tưởng treo.
- 18/08/2026 — **LOGIC HIỂN THỊ "CHƯA ĐƯỢC REVIEW" + LỌC DANH SÁCH** (user chốt:
  quyền giữ nguyên, không cần nhóm dự án vì video review xong sẽ xóa; cần video
  up lên chưa ai review phải NỔI). Trạng thái HIỂN THỊ suy từ bình luận:
  dang_duyet + so_tong=0 → **cho_review** (Awaiting review, chip accent + viền
  trái dòng) · có bình luận (kể cả đã giải) → dang_review (chip xám). Hàng tab
  đếm số theo trạng thái, MẶC ĐỊNH mở tab Awaiting khi còn video chờ; tìm
  KHÔNG DẤU (NFD + đ→d, dải combining U+0300–U+036F viết dạng escape trong regex — nhét
  ký tự tổ hợp THÔ vào regex/script từng vỡ heredoc cp1252 ngay phiên này) +
  lọc Mine only. Lọc client-side trên bảng đã render. 27 test pass.

- 18/08/2026 — **UPLOAD TỪNG KHÚC 20GB + DROPZONE KÉO-THẢ** (user: video thật
  2-10GB, trần 2GB không dùng được; khối upload phải đẹp hơn). `src/upload_khuc.py`:
  client cắt file bằng File.slice thành khúc `VR_KHUC_UP_MB` (64MB) gửi TUẦN TỰ —
  mỗi request qua proxy chỉ nặng 1 khúc, hết bom RAM gateway, KHÔNG sửa proxy
  (bật chunked transfer ở proxy sẽ vỡ app stdlib Content Ultimate). Phiên upload
  registry bộ nhớ, offset phải khớp byte đã nhận (chống ghi lệch), ĐỦ byte mới
  ghi sổ + os.replace; phiên bỏ dở >24h tự quét dọn kèm .tam mồ côi. Trần mới
  `VR_MAX_MB` 20480 (đường chunked + hiển thị); đường form một phát còn là
  fallback JS-chết với trần RIÊNG `VR_MAX_FORM_MB` 2048 (vẫn đi trọn qua proxy).
  UI: dropzone kéo-thả theo token brand (dashed → accent khi hover/kéo/đã chọn,
  icon SVG line theo luật icon minimalist — thay luôn 2 emoji 📁🎬 danh sách NAS
  bằng SVG, tên file qua textNode chống XSS), chip tên file + dung lượng, % tiến
  độ chảy trên nút. Chrome chặn submit khi input required bị display:none
  ("not focusable") → JS phải removeAttribute('required') khi nâng cấp form.
  33 test pass (6 test chunked mới).

## Quyết định thiết kế (đừng phá)

- **Video qua proxy = 206 TỪNG KHÚC ≤ VR_KHUC_MB (8MB)**: proxy `nen/common/proxy.py`
  đọc trọn body phản hồi vào RAM (trừ SSE). KHÔNG sửa proxy — app tự cắt khúc,
  trình duyệt xin tiếp. Test `test_media_range_tung_khuc` ghim hành vi cắt.
- **Nét vẽ chú thích lưu THEO BÌNH LUẬN** (`binh_luan.ve_json`, tọa độ chuẩn hóa
  0..1) — không lưu ảnh chụp khung hình, vẽ lại đúng mọi cỡ màn.
- **Gỡ video = GỠ MỀM** (`trang_thai='da_xoa'`), file giữ nguyên trong kho —
  bất biến hệ cũ "xóa ưu tiên gỡ mềm". `/api-vr/trang-thai` từ chối 'da_xoa'
  (gỡ phải đi đường `/api-vr/xoa-video` có gate `xoa` riêng).
- **base.html chép từ to-chuc** với 2 khác biệt có chủ đích: (a) mục Tools của
  app này luôn active (path ở app là đường ĐÃ CẮT /app/<slug> nên so kiểu cũ
  không bao giờ khớp); (b) BỎ khối heartbeat chấm công — /api/nhip thuộc to-chuc,
  gọi từ đây qua gateway là 404 mỗi 5 phút.
- JS trang xem KHÔNG dùng API secure-context-only (bài học crypto.randomUUID
  01/08); dữ liệu server nhúng qua `|tojson`; confirm 2-bấm thay hộp thoại
  trình duyệt.

## Thực tế vận hành (user báo 18/08)

- Video team upload: **2-10GB, codec H.264** — trình duyệt phát native (mp4/m4v
  chắc chắn, mov thường được) → KHÔNG cần transcode server-side. Tầng transcode
  chỉ đáng làm nếu team đổi sang xuất HEVC/ProRes (van sẵn có: player báo
  "Re-export as mp4 (H.264)" khi không phát được).

## Việc treo

- Gateway buffer body request khi upload (RAM tạm = cỡ file) — trần VR_MAX_MB
  2GB chấp nhận trên LAN; muốn nâng phải dạy proxy stream request body.
- Phiên bản video (v1 → v2 cùng chuỗi review) + so sánh 2 bản — Frame.io có,
  MVP chưa làm.
- `_icon_app.html` các app KHÁC chưa có nhánh video-review → sidebar app khác
  hiện icon ô vuông mặc định (fallback thiết kế sẵn, không vỡ); muốn đẹp thì
  thả nhánh icon vào từng bản chép.
- Thumbnail danh sách (chụp khung hình đầu) — cần ffmpeg, để sau.
