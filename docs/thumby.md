# ThumbY — sổ chủ đề: app mô phỏng vị trí hiển thị thumbnail YouTube

> Spec soạn 31/08/2026 (phiên bàn tính khả thi + chốt hướng). App RIÊNG trong V3
> theo lệnh Owner ("đây mới chỉ là điểm khởi đầu" — sẽ mở rộng thành mảng
> packaging trực quan). Cổng **9119** đã ghi PORTS.md. CHƯA CODE — sổ này là
> nguồn sự thật của spec; code xong ghi nhật ký xuống mục 10.

## 1. Mục tiêu & triết lý

- **Bài toán:** designer/team làm xong thumbnail thì chỉ xem nó ở dạng file to
  1280×720; người xem thật nhìn nó ở 168px cạnh 10 thumbnail đối thủ, có badge
  thời lượng che góc, title bị cắt 2 dòng, nền dark. Quyết định bấm/không bấm
  xảy ra ở NGỮ CẢNH đó chứ không phải ở file gốc.
- **ThumbY = máy mô phỏng ngữ cảnh hiển thị:** upload ảnh + gõ title → thấy đúng
  cách nó xuất hiện trên từng thiết bị (PC/điện thoại) và từng vị trí (Home,
  Suggested, Search, trang Kênh), dark/light.
- **Triết lý (van chống bịa áp sang UI):** ThumbY **mô phỏng, không phán xét**.
  Không chấm điểm "thumbnail tốt/xấu" — mọi tầng chấm sau này (nếu làm) phải
  theo lệ deai của Content Ultimate: số đo mô tả, không điểm tổng, thiếu cơ sở
  thì nói thẳng.
- **Lợi thế riêng so với mọi tool ngoài** (CollabPals/1of10/thumbnail.live…):
  hệ mình có RadarY chứa title + view + thumbnail THẬT của các pool/ngách team
  đang đánh → phase 2 dựng feed xung quanh bằng đối thủ thật, 0 quota.

## 2. Quyết định đã chốt / chờ chốt

| Việc | Trạng thái |
|---|---|
| App riêng trong V3, không nhét vào SEO Optimize/RadarY | **CHỐT** (Owner 31/08) |
| Tên ThumbY, slug `thumby`, cổng 9119 | **CHỐT** (Owner 31/08) |
| Quyền vào: **Kinh doanh L2** | **CHỐT** (Owner 31/08 — thay đề xuất L1 mọi bộ phận; khớp dải quyền Niche/SEO cùng mảng KD) |
| Phase 1 chỉ client-side, không lưu server | **CHỐT** theo spec này |
| Phase 2 đường lấy dữ liệu RadarY: **đọc DB chỉ-đọc** (`mode=ro` theo luật sổ địa bạ) | **CHỐT** (Owner 31/08 — bỏ phương án API loopback) |

**Bước ① Tổng hợp yêu cầu — 4 chốt bổ sung (Owner 31/08):**

| Câu hỏi | Chốt |
|---|---|
| Người dùng chính | **Cả hai**: người làm thumbnail tự soi TRƯỚC khi nộp + leader dùng cùng màn hình khi duyệt |
| Phạm vi V1 | **Card mẫu tĩnh** quanh thumbnail; nối RadarY là đợt 2 riêng (đường dữ liệu đã chốt mục 6) |
| Xuất PNG mockup | **Để đợt sau** — V1 xem trực tiếp, ai cần gửi thì screenshot tay |
| A/B compare | **CẦN NGAY V1** — upload 2 ảnh, cùng title, đặt cùng lưới so cạnh nhau |

**Quy trình làm việc (Owner chốt 31/08):** ① Tổng hợp yêu cầu → ② Đề xuất tính
năng → ③ Dựng UI mẫu (mockup, theo lệ mỗi-vòng-duyệt-một-file) → ④ Code →
⑤ Test/nghiệm thu. **TRƯỚC mỗi bước phải trao đổi thảo luận với Owner** —
không tự chạy liền mạch.

## 3. Kiến trúc & hợp đồng app

- Dựng từ khuôn `apps/app-mau` (:9190): FastAPI + Jinja, bind **127.0.0.1:9119**,
  nhận claims từ gateway (`X-Remote-User` / vai / `X-Remote-Actions`), có
  `/health`. App **native** (tự vẽ sidebar/topbar OUTLIERY trong template) →
  đi đường `/app/thumby`, KHÔNG khai `giao_dien: "khung"`.
- Khai hợp đồng trong `nen/rules/apps.json`: slug `thumby`, cổng, `tien_to`,
  `vao` + (sau này) `hanh_dong`. Thêm vào start-all + tác vụ nền theo lệ.
- **Phase 1 KHÔNG có `data\thumby\`** — không lưu gì server-side, không khai
  `du_lieu` sổ địa bạ. Khi nào bắt đầu lưu (phase 2+) mới khai, đúng luật.
- Venv riêng theo lệ app V3. Test: `apps/thumby/tests/` + root
  `tests/test_thumby.py` (test tích hợp nền + luật) nếu theo khuôn chung.

## 4. Quyền (Permissions v2)

- `vao`: **Kinh doanh, level ≥ 2** (Owner chốt 31/08). Không có hành động ghi ở
  phase 1 → không ô tick nào ngoài cửa vào; `quan_tri` Owner theo mặc định hệ.
  Manager+ (L4) vào theo lệ chung `duoc_vao_app`.
- Phase 2+ nếu có "lưu bộ thumbnail / log A/B" → khai `hanh_dong` mới lúc đó
  (tự hiện ô tick), DEFAULT vai thấp nhất, theo 13 luật quyền DE.md mục 14.

## 5. Phase 1 — MVP mockup tĩnh (ước ~1-2 ngày code)

### 5.1 Luồng người dùng
1. Vào `/app/thumby` → một trang duy nhất.
2. Kéo-thả/chọn ảnh (jpg/png/webp). Ảnh đọc bằng FileReader, **chỉ nằm trong
   trình duyệt** — không có endpoint upload.
3. Nhập: **title** · **tên kênh** · **thời lượng** (vd `12:34`) · **view**
   (vd `1,2 Tr lượt xem`) · **thời gian đăng** (vd `3 giờ trước`). Có giá trị
   mặc định sẵn để chỉ cần thả ảnh là thấy ngay.
4. Chọn **thiết bị** (PC / Điện thoại) + **theme mockup** (Dark mặc định /
   Light) → thấy đồng thời các vị trí (scroll dọc từng khối, không tab ẩn).
5. Nút **Shuffle**: đảo vị trí thumbnail của mình trong lưới video mẫu (chống
   quen mắt vị trí cố định).
5b. **A/B compare (chốt vào V1 — Bước ①):** upload thêm ảnh B (tùy chọn) →
   cả A và B cùng xuất hiện trong MỘT lưới Home (vị trí tách nhau, Shuffle đảo
   cả hai), các layout còn lại render cặp khối A/B cạnh nhau. Cùng title —
   V1 so THUMBNAIL, không so title (so title là chuyện của SEO Optimize).
6. Ảnh không đạt 16:9 → hiển thị đúng hành vi YouTube (crop/letterbox theo
   object-fit thực tế) + dòng cảnh báo tỉ lệ, KHÔNG chặn.

### 5.2 Các layout phải nhái (5 vị trí × 2 theme)

Giá trị px dưới đây là THAM CHIẾU (đo tháng 08/2026) — lúc code phải đo lại
bằng DevTools trên YouTube thật rồi ghi số chốt vào sổ này; chấp nhận
mockup-drift, chỉnh CSS định kỳ, mục tiêu là đúng TỈ LỆ + độ đọc được,
không pixel-perfect vĩnh viễn.

| Layout | Điểm phải đúng |
|---|---|
| **Home PC** | Lưới 3-4 cột, card ~360-400px; thumb 16:9 bo góc ~12px; avatar kênh 36px; title Roboto 500 ~16px, **tối đa 2 dòng cắt "…"**; meta (kênh · view · thời gian) ~14px màu nhạt |
| **Suggested sidebar** (cạnh trang xem) | Thumb ~168×94 bo 8px bên trái; title 500 ~14px 2 dòng; meta ~12px; đây là khung NHỎ NHẤT — chỗ lộ chữ-trên-ảnh không đọc được |
| **Search PC** | Thumb ~360×202; title ~18px; thêm 2 dòng mô tả xám nhỏ |
| **Home điện thoại** | Khung máy ~390px; thumb full-width KHÔNG bo (hoặc bo rất nhẹ); dưới: avatar trái + title ~14px 2 dòng + meta |
| **Trang kênh** | Lưới video của tab Videos, thumb nhỏ hơn Home |

Chi tiết dùng chung mọi layout:
- **Badge thời lượng**: nền đen ~80% alpha, chữ trắng ~12px, bo 4px, cách mép
  4px, góc phải-dưới — che đúng góc ảnh (thứ designer hay quên chừa).
- **Theme mockup**: dark nền `#0f0f0f` chữ `#f1f1f1` meta `#aaa`; light nền
  `#fff` chữ `#0f0f0f` meta `#606060`. Theme mockup là THUỘC TÍNH của preview,
  **độc lập** với theme OUTLIERY của khung app (khung vẫn theo
  `outliery_theme` như mọi app).
- **Font**: Roboto 400/500 **bundle local** trong app (LAN không tải font
  ngoài); wordmark/khung app vẫn Inter + Space Grotesk theo brand.
- Tùy chọn bật **thanh đỏ đã-xem** dưới thumbnail (tăng độ thật của feed).
- Video mẫu xung quanh: bộ ~12 card tĩnh đóng gói sẵn trong app (ảnh
  placeholder tự vẽ + title giả tiếng Anh trung tính — KHÔNG lấy ảnh thật của
  ai tránh lằng nhằng bản quyền), đảo bằng Shuffle.

### 5.2b Bảng tính năng V1 CHỐT (Bước ② — Owner tick 31/08)

Owner duyệt CẢ 7 tính năng thêm; cộng với nhóm lõi 5.1/5.2 thành phạm vi V1:

| # | Tính năng thêm | Ghi chú thực thi |
|---|---|---|
| 1 | **Squint test** | Nút bật CSS filter blur toàn lưới — thumbnail tốt là cái vẫn nổi khi nhìn lướt |
| 2 | **Thanh đỏ đã-xem** | Toggle; chỉ gắn vài card MẪU (không gắn ảnh của mình — mình là video "mới") |
| 3 | **Soi cỡ thật vs phóng to** | Khối riêng: thumbnail đúng 168px cạnh bản 2× — kiểm chữ-trên-ảnh |
| 4 | **Tooltip phần title bị cắt** | Hover title đã cắt → thấy phần mất, TỪNG layout (Home cắt khác Suggested) |
| 5 | **Nhớ ô nhập lần trước** | localStorage (try/catch — LAN HTTP có thể chặn); CHỈ text, không lưu ảnh |
| 6 | **Đếm ký tự title** | Kèm mốc tham chiếu ~70 ký tự — số mô tả, không phán (lệ mục 1) |
| 7 | **Đổi cỡ lưới Home PC** | Nút 3/4/5 cột mô phỏng bề rộng màn khác nhau |

**Thứ tự khối preview (Owner chốt):** khắc nghiệt nhất lên đầu —
PC: **Trang xem + Suggested 168px** → Home (lưới, có A/B + Shuffle) → Search →
Trang kênh → khối soi-cỡ-thật (#3). Điện thoại: danh sách xem-tiếp → Home feed.

### 5.3 Ràng buộc kỹ thuật + bẫy đã biết áp vào app này
- **LAN HTTP không secure context** (memory 01/08): cấm `crypto.randomUUID`,
  `navigator.clipboard` trần; nút "Copy/Tải mockup PNG" nếu làm phải có
  fallback (`execCommand` / thẻ `<a download>`); **nghiệm thu thêm một lượt
  qua `http://192.168.1.250:9000`**, không chỉ localhost.
- **Nghe sự kiện `storage`** đổi theme khung cùng cả hệ (test quét cả cây của
  mạch RadarY 22/08 sẽ bắt app mới nếu quên).
- **Minimalist icon** — không emoji trong chip/nút (lệ Owner nhắc 22/08).
- **License**: layout CSS TỰ VIẾT; được đọc PrevYou
  (github.com/bdebon/youtube-thumbnail-tester-chrome-extension, MIT) để tham
  khảo; KHÔNG chép tetreum/youtube-thumbnail-preview (repo không có license).
- Karpathy + Ponytail như mọi app: tối giản, test-first, diff ngắn.

### 5.4 Test phase 1 (tối thiểu)
- Khuôn app: `/health`; không claims → 401; vào đúng vai L1 mọi bộ phận.
- Template render đủ 5 khối layout + đủ ô nhập; KHÔNG có endpoint nhận file
  (quét route khẳng định không có upload).
- JS: guard secure-context có fallback (test ghim kiểu `test_auth.py` V2 —
  chỉ 1 lời gọi API nguy hiểm, nằm sau guard).
- Test theme `storage` theo khuôn quét cả cây hiện có.

## 6. Phase 2 — feed đối thủ thật từ RadarY (làm SAU khi phase 1 chạy)

- **Giá trị:** thay 12 card giả bằng video THẬT của pool/ngách đang đánh —
  trả lời đúng câu "thumbnail mình đứng cạnh 8 video đang nổ trong pool US
  của Life In thì có chìm không".
- Chọn pool/ngách từ dropdown (đọc danh sách pool RadarY theo quyền người
  dùng); lấy title + view + ngày đăng + thumbnail; nút Shuffle rút ngẫu nhiên
  từ pool; **A/B**: 2 thumbnail của mình đặt cùng lưới so cạnh nhau.
- **Đường dữ liệu — CHỐT (Owner 31/08): đọc `data\radary\` CHỈ-ĐỌC** (SQLite
  mở `mode=ro` theo luật sổ địa bạ; thumbs đọc file trực tiếp). Đánh đổi chấp
  nhận: dính schema nội bộ RadarY → khi RadarY đổi schema phải sửa ThumbY theo;
  cô lập phần đọc vào MỘT module (`radary_reader.py`) để đổi schema chỉ sửa
  một chỗ.
- Thumbs cache RadarY 636M là dữ liệu TÁI-SINH (ghi chú APPS.md) — ThumbY chỉ
  ĐỌC, tuyệt đối không ghi/dọn cache của RadarY.
- RBAC: chỉ hiện pool người dùng được xem theo quyền RadarY — tránh rò dữ
  liệu ngách qua đường ThumbY.

## 7. Đường mở rộng (backlog có chủ đích — lý do app đứng riêng)

Ghi để định hướng, CHƯA cam kết:
1. **Chấm độ-đọc-được ở 168px**: đo contrast + cỡ chữ trên ảnh khi thu nhỏ —
   số đo mô tả, không điểm tổng (lệ deai).
2. **Đối chiếu phong cách với nhóm thắng trong pool** (nối mạch phát hiện
   CAPS 18/08: title CAPS nặng ở nhóm thắng ÍT hơn nhóm thường).
3. Lưu lịch sử thumbnail theo kênh/video → nhìn tiến hóa packaging (lúc này
   mới sinh `data\thumby\` + khai sổ địa bạ + hành động quyền).
4. Nối Video Review / PlannerY: thumbnail đi kèm đúng video trong pipeline
   sản xuất.
5. Layout Shorts shelf (team hiện long-form là chính — để sau).

## 8. Những gì KHÔNG làm

- Không nhái pixel-perfect chạy theo mọi lần YouTube đổi UI.
- Không tự sinh/sửa thumbnail bằng AI (khác bài toán — NanoThumbnail đã có,
  và không phải nhu cầu hiện tại).
- Không extension trình duyệt kiểu PrevYou (phải cài từng máy, vỡ theo DOM
  YouTube, không tận dụng được RadarY).
- Không phán "thumbnail này tốt" (mục 1).

## 9. Nghiệm thu phase 1

- [ ] Qua gateway `:9000` (và 9443) từng vai: L1 mọi bộ phận vào được; chưa
      đăng nhập → chặn đúng khuôn.
- [ ] Chrome headless soi qua proxy (bẫy importmap/ETag/Origin nếu có POST).
- [ ] Một lượt trên máy LAN thật `http://192.168.1.250:9000` — JS sống
      (bài học secure context).
- [ ] Thả 1 thumbnail thật của team: soi 5 layout × 2 theme, badge thời lượng
      đè góc đúng, title dài cắt 2 dòng đúng.
- [ ] Đặt mockup Home PC cạnh screenshot YouTube thật cùng cỡ màn — liệt kê
      chỗ khác nhau (lệ đối-chiếu-mockup trong memory).
- [ ] pytest app + root xanh; suite các app khác không bị đụng.

## 10. Nhật ký

- 31/08/2026 — Soạn spec (sổ này) + ghi cổng 9119 vào PORTS.md. Nguồn tham
  khảo đã khảo sát: PrevYou (MIT, extension tiêm vào YouTube thật) ·
  thumbnail.live (Eleventy) · tetreum/youtube-thumbnail-preview (no license) ·
  các tool đóng CollabPals/1of10/view2.be/thumbpreviewer (chuẩn tính năng
  5-6 layout × 2 theme × A/B). CHƯA CODE.
- 31/08/2026 (tiếp) — Owner chốt: tên ThumbY · quyền vào Kinh doanh L2 ·
  phase 2 đọc DB RadarY chỉ-đọc · quy trình 5 bước có trao đổi trước mỗi bước
  (mục 2). Bắt đầu Bước ① Tổng hợp yêu cầu.
- 31/08/2026 (tiếp 2) — **Bước ① XONG**: 4 chốt bổ sung (người dùng cả hai vai ·
  V1 card mẫu tĩnh · PNG để sau · A/B vào ngay V1 — bảng mục 2); A/B đưa vào
  luồng 5.1 (mục 5b). Kế tiếp: Bước ② Đề xuất tính năng.
- 31/08/2026 (tiếp 3) — **Bước ② XONG**: Owner duyệt cả 7 tính năng thêm +
  thứ tự Suggested-168px-đứng-đầu (mục 5.2b). Kế tiếp: Bước ③ Dựng UI mẫu —
  mockup HTML tĩnh, theo lệ MỖI VÒNG DUYỆT MỘT FILE (bản duyệt rồi giữ nguyên
  trạng, vòng sau file mới).
- 31/08/2026 (tiếp 4) — **Bước ③ vòng 1**: Owner chốt gu "đẹp, đơn giản giống
  RadarY" → mockup `docs/mockup/thumby-v1.html` (artifact f61c002b) dựng đúng
  token RadarY (`apps/radary/web/index.html` — light #f5f5f5/#2c6fc4, dark
  #090c12/#4c8fe0, Inter + Space Grotesk wordmark, panel bo 12px, một accent);
  khu preview YouTube scoped token riêng (#0f0f0f/#fff, Roboto) độc lập theme
  app. Bán tương tác: theme app + nền YT + PC/Mobile + 3/4/5 cột + squint +
  thanh đã-xem + Shuffle + title/đếm ký tự sống; upload/tooltip vẽ tĩnh.
  CHỜ Owner duyệt — có góp ý thì vòng 2 là file mới thumby-v2.html.
- 31/08/2026 (tiếp 5) — **Bước ③ vòng 2** (`docs/mockup/thumby-v2.html`, artifact
  a3cbe4b5; v1 giữ nguyên trạng theo lệ). Góp ý Owner vòng 1: (a) "bố cục + tính
  năng đã đúng ý" NHƯNG các vị trí xếp dọc cuộn dài mệt → v2 đổi sang **THANH VỊ
  TRÍ dính trên đầu** (pill tab: Suggested/Home/Search/Kênh/Soi cỡ thật; điện
  thoại: Xem tiếp/Home feed — đổi Thiết bị là bộ tab đổi theo, mỗi lúc chỉ hiện
  một vị trí); (b) Owner TÁI XÁC NHẬN GĐ2 nối RadarY "thumb liên quan đứng cạnh
  A/B" → v2 đặt sẵn chỗ đứng UI: segment **"Card xung quanh: Mẫu tĩnh | Pool
  RadarY (khóa, nhãn giai đoạn 2)"** trong thanh điều khiển — GĐ2 mở khóa nút
  này + dropdown chọn pool, không vẽ lại UI. CHỜ Owner duyệt vòng 2.
- 31/08/2026 (tiếp 6) — **Owner DUYỆT mockup vòng 2 → Bước ③ XONG.**
  `thumby-v2.html` = bản UI chốt (mốc giữ nguyên trạng, đối chiếu khi code xong
  theo lệ đối-chiếu-mockup). Sang Bước ④ Code — kế hoạch trao đổi trước.
- 31/08/2026 (tiếp 7) — **Bước ④ CODE XONG** (2 commit V3: 3d17778 app + 37505bd
  quyền/root-test; suite app 6 + root 238 pass — 1 fail test ghim tien_to
  content-ultimate là baseline phiên song song /kientruc d2968c5, không liên quan).
  App đúng khuôn tasky: server chỉ render, nghiệp vụ client-side, KHÔNG route ghi
  (test ghim mọi route ⊆ GET/HEAD); tooltip đo ĐIỂM CẮT title thật bằng tìm nhị
  phân trên phần tử line-clamp; Roboto bundle local 2 file woff2 (Google trả
  variable font — 400/500 cùng file, khai 2 @font-face trỏ chung); localStorage
  bọc try/catch; nút Ẩn chip A/B (thêm lúc code — mockup ghi chú sẵn). PHÁT HIỆN
  VẬN HÀNH: apps.json + phan_quyen.json đều đọc SỐNG theo mtime — thêm app không
  cần restart gateway, CHỈ dòng _ALIAS "/thumby" (URL đẹp sidebar) là code cần
  restart; dòng này đang ở working tree CHƯA COMMIT (gateway main.py dính mạch
  RenderY chưa commit của phiên song song — chờ phiên đó commit, alias sẽ được
  quét kèm hợp lệ). App :9119 ĐÃ BẬT tay (Start-Process, stateless không cần
  env), smoke đạt: /health OK · không claims 401 · có claims 200 · static font
  OK. CÒN: restart gateway (classifier chặn tự kill — chờ Owner) → nghiệm thu
  Bước ⑤ theo mục 9.
- 31/08/2026 (tiếp 8) — **RESTART GATEWAY (Owner duyệt) + NGHIỆM THU MÁY XONG.**
  Diễn biến: kill gateway theo cổng 9000 → start-all bật lại nhưng gateway CHẾT
  NGAY không dấu vết (cửa sổ ẩn nuốt lỗi; start-all vẫn bật được content-ultimate
  9112 đang tắt) → bật lại tay có -RedirectStandardError ra log: lần này lên
  sạch, log không lỗi (nghi vấn transient sau kill; KINH NGHIỆM: bật dịch vụ tay
  nên kèm redirect stderr ra file — cửa sổ ẩn chết là mất bằng chứng). Nghiệm
  thu máy: /login 200 · /thumby chưa đăng nhập 401 ĐỒNG NHẤT /tasky //nas ·
  LAN 192.168.1.250:9000 200 · Caddy 9443 200 · :9119 health OK · radary gọi
  két key qua gateway 200. CÒN LẠI CẦN MẮT OWNER (không có credential thật,
  không tạo tài khoản trên iam.db sống theo lệ): đăng nhập KD L2 thấy nút
  ThumbY + trang mở được; thả thumbnail thật soi 5 vị trí × 2 nền; đặt cạnh
  mockup thumby-v2.html đối chiếu (lệ đối-chiếu-mockup).
