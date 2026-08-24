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

- 20/08/2026 (cùng ngày, sau khi team dùng thật) — **SỰ CỐ "CHỈ CÓ TIẾNG, KHÔNG
  CÓ HÌNH" = FILE H.265**, không phải lỗi liên kết NAS. Video team vừa thêm
  (`Life In/US/LI084/LI084_1080.mp4`) là **hevc Main + aac**: Chrome/Edge trên
  Windows thiếu HEVC Video Extension nên phát TIẾNG, hình đen, và **KHÔNG bắn sự
  kiện `error`** → handler lỗi cũ không đời nào chạy, app hỏng LẶNG LẼ. Đổi sang
  NAS không gây ra lỗi này nhưng LÀM NÓ LỘ RA: trước team chỉ đưa vào app bản
  render đã chọn, giờ chọn được mọi file trên NAS. Đếm thật `Life In/US`: 940
  h264 · 37 av1 (Chrome đọc được) · **9 hevc**, và 9 file đó tụm vào một tay dựng
  (`LI063_Hai`, `LI066_Hai`, `LI072_Hai`, `LI078_Hai`, `LI080_Hai`, `LI076`,
  `LI084`) → bệnh preset xuất, sẽ lặp lại. **User chốt: CHỈ CẢNH BÁO, KHÔNG
  transcode** (server còn chạy 6 app khác; đội dựng xuất lại H.264).
  Làm: migration 003 cột `codec`; `doc_codec` gọi ffprobe CÓ TIMEOUT 20s
  (`VR_FFPROBE` khai trong start-all.ps1 — dùng bản ffmpeg cài sẵn cho SpeakY);
  dò lúc thêm + dò LƯỜI một lần cho bản ghi cũ rồi nhớ vào sổ (đừng probe 9 file
  mỗi lần vào trang); cảnh báo ở BA chỗ — ngay lúc thêm, chip đỏ ở danh sách,
  banner trang xem kèm cách xuất lại. **LƯỚI CHÓT không phụ thuộc ffprobe**:
  `loadedmetadata` mà `videoWidth === 0` → hiện thông điệp (máy thiếu ffprobe
  hoặc codec lạ vẫn không hỏng lặng lẽ). Thiếu ffprobe thì im lặng chứ KHÔNG báo
  bừa. 44 test pass.
  **BÀI HỌC:** codec trình duyệt không đọc được là ca hỏng KHÔNG có sự kiện lỗi —
  chỉ `videoWidth === 0` mới lộ; và mở kho file cho người dùng chọn tự do thì
  phải kiểm định dạng NGAY TẠI CỬA, đừng tin "team toàn xuất H.264".

- 20/08/2026 (tiếp) — **DỌN DẸP SAU REVIEW: mở thư mục NAS + xóa file từ app +
  gom danh sách THEO TẬP** (user: "sau mỗi lần lại nhiều lên"). Số thật lúc làm:
  15 bản ghi / 80 bình luận, và danh sách phình theo VÒNG SỬA chứ không theo tập
  (LI037 fix lần 1 → lần 2, LI049 Round 2 → Round 3, LI073 fix lần 1 → lần 2);
  một thư mục tập nặng 17,2GB vì giữ 3 bản dựng cùng lúc.
  • **Gom theo tập** (`kho_video.ma_tap`): mã rút từ TÊN FILE, lùi về tên thư mục,
    BỎ QUA mã sổ của app (`2026-08-19_VR-0003_li083.mp4` → LI083, không phải
    VR0003 — dính thật lượt đầu). Nhóm `<details>` mở sẵn khi còn bản chưa duyệt,
    tập duyệt xong gập lại; lọc/tìm phải MỞ nhóm ra không thì kết quả nằm trong
    nhóm đã gập và người dùng tưởng không có gì.
  • **Khối "Folder on the NAS"** trên trang xem: đường UNC để dán vào Explorer
    (`VR_NAS_UNC`, trình duyệt KHÔNG mở được `file://` từ trang http — copy dùng
    execCommand vì LAN chạy HTTP) + liệt kê mọi file trong thư mục kèm dung lượng
    và cờ "in app".
  • **XÓA FILE NAS TỪ APP** — user chốt, đây là **NGOẠI LỆ CÓ KIỂM SOÁT** của luật
    "app chỉ đọc NAS", `src/don_nas.py`, SÁU chốt: cờ `xoa` (Manager 4+) · resolve
    trong gốc (ngoài gốc → **404 lặng lẽ**, KHÔNG 403 — sửa sau khi test bắt) ·
    phải là file · **chỉ đuôi video + phụ đề** (dự án Premiere/CapCut cạnh đó
    tuyệt đối không đụng) · client echo đúng tên file (chặn danh sách CŨ xóa nhầm
    hàng, không phải để hành người dùng) · **nhật ký chỉ-thêm ghi TRƯỚC khi xóa**
    (`db/nhat_ky_xoa_nas.csv`, đã khai vào apps.json) — xóa xong mới ghi thì lỗi
    giữa chừng là mất dấu vết, có test giả lập unlink hỏng để ghim. Xóa file đang
    có bản ghi → **gỡ mềm bản ghi luôn** (bình luận giữ nguyên trong sổ). Giao
    diện chặn tay-nhầm bằng 2 bước bấm + ô tích, không dùng hộp thoại trình duyệt.
  55 test pass. Kiểm sống qua cổng 9114: 4 chốt trả đúng 403/422/404/403 mà không
  xóa file nào của team. **Dọn xong 7,46GB bản sao cũ** (VR-0007/0008); VR-0006 bị
  script TỪ CHỐI xóa vì bản gốc trên NAS đã biến mất → bản trong app là bản duy
  nhất — đúng ý đồ chốt chặn.

- 20/08/2026 (tiếp 2) — **QUY TRÌNH TẬP CHÍNH THỨC** (user chốt, thay cách làm tự
  phát trước đó). Kho NAS: `<tập>/Feedback/` là nơi nhân sự up bản duyệt, đặt tên
  theo mã tập — bản gốc `LI001`, bản sửa `LI001.1`, `LI001.2`… Duyệt còn **ĐÚNG BA
  BƯỚC**: Awaiting review (chưa ai bình luận) → In review → Approved; `can_sua`
  NGHỈ HƯU (migration 004 đưa bản ghi cũ về dang_duyet, gỡ nút + tab + nhãn) vì yêu
  cầu sửa vốn nằm trong bình luận. **Tập có bản Approved = xong → LÚC ĐÓ mới được
  dọn cả khối Feedback.**
  • `ma_tap` phải NHẢY QUA thư mục 'Feedback' khi lùi lên tìm mã, không thì cả kho
    gom vào một nhóm tên 'Feedback'. `thu_muc_feedback()` trả '' cho bản ghi đời cũ
    (trỏ thẳng thư mục tập) → **những bản ghi đó KHÔNG có đường dọn cả thư mục**,
    vì trong thư mục tập có bản master của team.
  • `xoa_khoi_feedback` = dọn cả khối, chốt riêng: thư mục phải **tên đúng
    'Feedback'** (thư mục tập/kho phim gốc không đời nào xóa được, có test quét cả
    3 cấp trên), mã tập client gửi phải khớp mã suy từ đường thật, tập phải đã
    Approved; mỗi file ghi nhật ký TRƯỚC khi xóa; bản ghi trong khối bị gỡ mềm,
    bình luận giữ nguyên.
  • Chốt 7 áp cho CẢ lệnh xóa từng file: chưa Approved thì Manager cũng không xóa
    được gì (nếu sau này cần dọn bản up nhầm trước lúc duyệt thì phải mở ngoại lệ
    có chủ đích, đừng gỡ chốt).
  • Nút Approve tự lật thành "Reopen review" tại chỗ; nhóm tập đã duyệt hiện nhãn
    "episode signed off" và nút "Clean up feedback folder" (chỉ Manager+).
  64 test pass. Kiểm sống sau restart: migration 004 chạy (12 dang_duyet, 0 can_sua),
  giao diện sạch chữ 'Changes requested', LI037 hiện 'episode signed off' nhưng
  KHÔNG có nút dọn — đúng, vì tập đó theo cấu trúc cũ, chưa có khối Feedback.

- 20/08/2026 (tiếp 3) — **NÚT XÓA CỨNG Ở NHÓM ĐÃ NGHIỆM THU** (user yêu cầu).
  Phân biệt rành mạch BA mức dọn, đừng gộp lại:
  1. **Gỡ mềm** (`trang_thai='da_xoa'`) — bản ghi ẩn khỏi danh sách, bình luận còn,
     file NAS còn. Vẫn là hành vi mặc định khi xóa một video lẻ.
  2. **Clean up feedback folder** — xóa FILE trong `<tập>/Feedback` trên NAS, bản
     ghi + bình luận GIỮ NGUYÊN (chỉ gỡ mềm) để còn lịch sử duyệt.
  3. **Delete permanently** (mới) — xóa CỨNG: bản ghi + bình luận biến mất khỏi sổ,
     kèm ô tích tùy chọn dọn luôn khối Feedback. Chỉ hiện ở nhóm ĐÃ Approved và chỉ
     Manager+; hai lớp xác nhận = **gõ lại đúng mã tập** + tích ô (khuôn xóa cứng
     của kho tài liệu hệ cũ). `cac_video_cua_tap` quét CẢ bản đã gỡ mềm — không để
     lại bản ghi ẩn cùng tập trong sổ.
  Nhật ký riêng `db/nhat_ky_xoa_ban_ghi.csv` (chỉ-thêm, đã khai apps.json): ai, bản
  ghi nào, MẤT BAO NHIÊU BÌNH LUẬN — vì đây là đường duy nhất làm bình luận biến
  mất, không có nó thì mất trắng không dấu vết. 69 test pass; kiểm sống 4 chốt trả
  403/422/403/403 mà sổ vẫn nguyên 15 bản ghi + 80 bình luận.
  **Ca đã lường:** tập đời cũ (không có khối Feedback) tích ô xóa file → 403 nói rõ
  "file trên NAS phải tự dọn", KHÔNG bao giờ mở đường xóa thư mục tập.

- 24/08/2026 — **SỰ CỐ "MẤT CỜ AWAITING REVIEW"** (user báo: nhân sự up bản mới cho
  leader xem nhưng mục nhảy thẳng In review). **KHÔNG phải do tập đã có round 1** —
  dấu vết trong sổ nói khác: VR-0016 up 15:17:40 bởi hieuvn, rồi CHÍNH hieuvn nhắn
  2 câu lúc 15:18:03 và 15:18:14 ("ANH DỊCH ĐƯỢC KHÔNG ANH", "E ĐANG HẾT CAPCUT
  PRO"); leader (bot) mãi 17:59:47 mới review thật. App coi **"đã có bình luận" =
  "đã có người review"** nên cờ Awaiting tắt sau 20 GIÂY, leader mất tín hiệu suốt
  2,5 tiếng.
  Sửa: `danh_sach_video` thêm `so_khac` = bình luận của **NGƯỜI KHÁC người đăng**;
  `hien_thi` dùng so_khac chứ không dùng so_tong. Ghi chú của chính người up không
  còn là review. Thêm: **nhãn NHÓM ưu tiên 'Awaiting'** — còn bản nào chưa ai xem
  thì cả tập kêu, kể cả khi bản mới nhất đã được review (đừng để bản cũ bị bỏ quên
  lặng lẽ). 72 test pass.
  **BÀI HỌC (cùng họ với bug A/B của Kho-thiếu hệ cũ):** đừng lấy "có dữ liệu" làm
  proxy cho "đã có người làm việc" — phải hỏi AI làm. Dấu vết thời gian trong sổ
  là thứ chứng minh nguyên nhân, không phải suy đoán từ mô tả triệu chứng.
- 24/08/2026 — **CHỐT MỘT TÊN 'Feedback' DUY NHẤT**: soi dữ liệu thật thấy team
  đặt `LI086/FB/`; tôi đã cho nhận cả 'fb' nhưng **user chốt giữ một quy ước, tự
  nhắc anh em đặt đúng** → `TEN_THU_MUC_FEEDBACK = frozenset({'feedback'})`.
  Thư mục tên khác vẫn GOM ĐÚNG TẬP nhưng không được coi là khối feedback → không
  có nút dọn cả thư mục, và API trả 403 nếu ai đó trỏ thẳng vào. Có test ghim cả
  hai vế. **Hệ quả cần người làm tay: `Life In/US/LI086/FB` phải đổi tên thành
  `Feedback` trên NAS thì tập đó mới dọn được bằng app** (app không đổi tên thư
  mục — chỉ đọc và xóa file trong khối đúng tên).

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
