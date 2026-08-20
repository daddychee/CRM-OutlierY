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

- 20/08/2026 — **VIDEO KHÔNG CÒN NẰM TRONG APP: LIÊN KẾT THẲNG FILE TRÊN NAS**
  (user chốt: "quy trình bên tôi là anh em up lên NAS rồi đưa video sang app, nên
  dùng luôn video trong NAS chứ không lưu vào app"). Migration 002 thêm cột
  `nguon` ('kho' đời cũ | 'nas') + `nas_mtime`; `duong` của bản ghi nas là đường
  TƯƠNG ĐỐI trong `VR_NAS_DIR`. Thêm video = ghi sổ, TỨC THÌ (trước chép 2-10GB
  mất 5-10 phút), hết trần dung lượng, hết bản trùng. Ba quyết định kèm theo:
  (a) **GỠ HẲN đường upload trình duyệt** (user chốt: một cửa duy nhất) — xóa
  `upload_khuc.py` + route `/upload-video` + dropzone; `/api-vr/nas-nap` (tác vụ
  nền + %) thay bằng `/api-vr/nas-lien-ket` trả `ma` ngay.
  (b) **VÂN TAY FILE** (dung lượng + ngày sửa chụp lúc liên kết): mất file →
  "file missing" ở danh sách + banner trang xem, `/media` 404, BÌNH LUẬN GIỮ
  NGUYÊN; bị ghi đè bản mới cùng tên → "file changed" vì mốc giây bình luận cũ
  trỏ sai chỗ. Chỉ CẢNH BÁO, không tự sửa sổ.
  (c) **Phụ đề hai nguồn**: `.srt` cạnh video trên NAS đọc thẳng (chỉ đọc, nút
  Remove subs ẩn + route trả 409); bản gắn từ app nằm `kho/phu-de/<ma>.srt` và
  THẮNG bản NAS. `scripts/lien_ket_lai_nas.py` dò bản ghi đời cũ theo dung lượng
  + băm 1MB đầu/cuối (KHÔNG theo tên — tên trong kho đã đổi khuôn), 3 bước rời
  liệt-kê → `--chay` → `--xoa-ban-sao`. Chạy thật: 8 bản ghi cũ → 3 khớp NAS
  (LI085 480p / LI049_Round 2 / LI037 fix lần 1), 5 không thấy trên NAS nên GIỮ
  bản sao (VR-0003 LI083, VR-0004 LI085 gốc, VR-0005 LI049 gốc: bản trong app
  giờ là bản DUY NHẤT còn sống — đừng xóa). 38 test pass.
  **BẪY đã dính:** đổi `duong` sang NAS làm phụ đề đã gắn trong app (sidecar cạnh
  bản sao cũ) MỒ CÔI — `--chay` giờ chuyển sidecar vào kho phụ đề TRƯỚC khi động
  vào sổ (VR-0007 đã cứu). **LƯU Ý VẬN HÀNH:** app con KHÔNG tự đọc .env — biến
  `VR_NAS_DIR` phải khai trong `tools/scripts/start-all.ps1` (đã khai
  `F:\OutlierY Nas 2` = share 'Video', ổ vật lý ngay trên máy chủ nên đọc thẳng,
  KHÔNG đi UNC vì tác vụ SYSTEM không có credential mạng).

## Quyết định thiết kế (đừng phá)

- **NAS CHỈ ĐỌC TUYỆT ĐỐI**: app không chép/ghi/xóa/đổi tên gì trong `VR_NAS_DIR`
  — kể cả phụ đề gắn từ app (nằm trong kho app) và kể cả khi xóa video.
- **Video qua proxy = 206 TỪNG KHÚC ≤ VR_KHUC_MB (8MB)**: proxy `nen/common/proxy.py`
  đọc trọn body phản hồi vào RAM (trừ SSE). KHÔNG sửa proxy — app tự cắt khúc,
  trình duyệt xin tiếp. Test `test_media_range_tung_khuc` ghim hành vi cắt.
- **Nét vẽ chú thích lưu THEO BÌNH LUẬN** (`binh_luan.ve_json`, tọa độ chuẩn hóa
  0..1) — không lưu ảnh chụp khung hình, vẽ lại đúng mọi cỡ màn.
- **Gỡ video = GỠ MỀM** (`trang_thai='da_xoa'`), file gốc trên NAS KHÔNG bị đụng —
  bất biến hệ cũ "xóa ưu tiên gỡ mềm". `/api-vr/trang-thai` từ chối 'da_xoa'
  (gỡ phải đi đường `/api-vr/xoa-video` có gate `xoa` riêng).
- **base.html chép từ to-chuc** với 2 khác biệt có chủ đích: (a) mục Tools của
  app này luôn active (path ở app là đường ĐÃ CẮT /app/<slug> nên so kiểu cũ
  không bao giờ khớp); (b) BỎ khối heartbeat chấm công — /api/nhip thuộc to-chuc,
  gọi từ đây qua gateway là 404 mỗi 5 phút.
- JS trang xem KHÔNG dùng API secure-context-only (bài học crypto.randomUUID
  01/08); dữ liệu server nhúng qua `|tojson`; confirm 2-bấm thay hộp thoại
  trình duyệt.

- 18/08/2026 — **PHỤ ĐỀ .SRT XEM CÙNG VIDEO** (user chốt giữa chừng: CHỈ NGƯỜI UP
  VIDEO được up phụ đề — bỏ nhánh Leader+ định làm). `<track>` trình duyệt chỉ ăn
  WebVTT → server chuyển SRT→VTT ngầm khi phát (`srt_sang_vtt`: header + phẩy
  mili-giây→chấm; số thứ tự SRT giữ nguyên = cue id hợp lệ); file phụ đề lưu
  CẠNH video trong kho theo quy ước tên (`<file video>.srt` — không migration
  DB). BA đường gắn, đều là người up video: (1) ô .srt tùy chọn trong form
  upload — phụ đề rác 422 NGAY TẠI CỬA trước khi ghi sổ video; (2) nút
  +Subtitles/Replace/Remove trên trang xem (chỉ chính chủ thấy, server kiểm);
  (3) đường NAS TỰ NHẶT file .srt cùng tên cạnh video (best-effort, không giết
  tác vụ nạp). Đọc phụ đề = ai xem được video; encoding SRT thử utf-8-sig →
  utf-16 → thay ký tự hỏng (không nổ). 39 test pass (6 test phụ đề).

## Thực tế vận hành (user báo 18/08)

- Video team upload: **2-10GB, codec H.264** — trình duyệt phát native (mp4/m4v
  chắc chắn, mov thường được) → KHÔNG cần transcode server-side. Tầng transcode
  chỉ đáng làm nếu team đổi sang xuất HEVC/ProRes (van sẵn có: player báo
  "Re-export as mp4 (H.264)" khi không phát được).

## Việc treo

- (XONG 20/08 — hết upload nên hết bận tâm proxy buffer body request.)
- 5 bản ghi đời cũ còn bản sao trong kho (~7GB): VR-0001/0002 là video thử,
  VR-0003/0004/0005 KHÔNG còn trên NAS nên bản trong app là bản duy nhất —
  muốn dọn thì phải chép ngược lên NAS rồi mới liên kết lại.
- File NAS bị đổi tên/di chuyển hiện chỉ CẢNH BÁO — chưa có đường "trỏ lại file
  mới" trên giao diện (phải sửa sổ bằng tay hoặc thêm lại rồi chép bình luận).
- Phiên bản video (v1 → v2 cùng chuỗi review) + so sánh 2 bản — Frame.io có,
  MVP chưa làm.
- `_icon_app.html` các app KHÁC chưa có nhánh video-review → sidebar app khác
  hiện icon ô vuông mặc định (fallback thiết kế sẵn, không vỡ); muốn đẹp thì
  thả nhánh icon vào từng bản chép.
- Thumbnail danh sách (chụp khung hình đầu) — cần ffmpeg, để sau.
