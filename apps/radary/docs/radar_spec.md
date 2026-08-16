# RADAR SPEC — Video Outlier on Niche (bản tối ưu sau vòng lặp phản biện, 07/07/2026)

> Nhiệm vụ: phát hiện video đang tăng trưởng bất thường trong niche, đủ sớm cho vòng sản xuất 8 tiếng. Người dùng là follower nhanh — không cần đoán trước, cần thấy sớm và tin được.
> Trạng thái: SPEC ĐÓNG BĂNG — chưa code, chờ lệnh.

## 1. Phạm vi & đơn vị

- Nguồn: danh sách kênh đối thủ (77 kênh, gồm cả dạng `@handle` — loader phải resolve handle). Long-form (>180s), bỏ Shorts.
- **Đơn vị theo dõi: VIDEO.** Không gom chủ đề ở tầng tracking; chủ đề chỉ là chú thích ở tầng báo cáo.
- Máy chạy 24/7 của user, cron; timezone Asia/Ho_Chi_Minh cho mọi ranh giới ngày và lịch báo cáo.

## 2. Chỉ số chuẩn (mọi bảng đều hiển thị đủ)

| Chỉ số | Định nghĩa | Vai trò |
|---|---|---|
| **VPH** | Δviews ÷ số giờ giữa 2 lần quét (cửa sổ tối thiểu 2h để khử răng cưa cache API) | **THƯỚC XẾP HẠNG CHÍNH** — chuẩn hóa được giữa các video quét nhịp khác nhau |
| **VPD** | Δviews 24h trượt | Thước tham chiếu sản xuất: "VPD còn cao là còn đáng làm, bất kể tuổi" |
| VPD-sp | views lũy kế ÷ tuổi (ngày) | Chỉ dùng cho video mới thấy lần đầu (chưa có delta) |
| Views, tuổi (ngày+giờ), kênh, title, link | — | Tham chiếu |

- **Baseline = thời điểm quét đầu tiên (t0).** Mọi delta tính từ timestamp quét — bộ đếm giờ/ngày tích hợp, mỗi snapshot lưu kèm epoch time.

## 3. Cohort tuổi (lõi phát hiện)

- Video ≤7 ngày tuổi chia vào cohort theo số ngày tuổi: D0, D1, ... D6. **Tuổi tính rolling 24h từ timestamp đăng** (tuổi <24h = D0, 24-48h = D1...), KHÔNG theo ngày lịch — tránh video đăng 23:50 và 00:10 lệch cohort oan.
- **Thăng/hạ bậc do di cư cohort** (video già đi, sang cohort mới nên đổi hạng) **không kích hoạt push** — chỉ thay đổi do VPH mới được push.
- Trong mỗi cohort: **xếp hạng theo VPH giảm dần** (không phải views lũy kế — views lũy kế ưu ái video đã tắt).
- Video >7 ngày: rời cohort nhưng KHÔNG rời tầm nhìn — vẫn nằm trong bảng "VPD cao mọi tuổi" nếu VPD vượt sàn T1. Không có logic đặc biệt cho video già: chỉ số VPD tự nói (quyết định của user: video già mà VPD cao thì tự nó hiện lên, còn cháy chậm chia thị phần thì user tự quyết bằng mắt).
- Cohort D0-D1 được quét nhịp cao nhất (nơi mật độ thông tin/giờ lớn nhất — quy luật 48h).

## 4. Thang bậc T1-T4 (điều kiện = HẠNG trong cohort VÀ SÀN tuyệt đối)

| Bậc | Điều kiện | Hành động |
|---|---|---|
| T1 QUAN SÁT | top 20% cohort VÀ VPH ≥ ~400 (≈10K/24h) | nâng nhịp quét (không push) |
| T2 ỨNG VIÊN | top 3 cohort VÀ VPH ≥ ~1.2K (≈30K/24h) | **push ntfy ngay** (thông tin sớm — user yêu cầu) + chuẩn bị asset |
| T3 SÓNG | top 1 cohort VÀ VPH ≥ ~4K (≈100K/24h) | **XÁC NHẬN 15-30 phút → push ntfy → sản xuất 8h** |
| T4 BÙNG NỔ | VPH ≥ ~12K (≈300K/24h), khỏi cần hạng | **push ntfy TỨC THÌ** (không chờ xác nhận) + cân nhắc 2 góc đánh |

- **Chống spam push:** mỗi video chỉ push 1 lần/bậc (dedup); trần 5 push T2/ngày, tràn thì ghi board không push. Ước lượng từ data T4-T7/2026: ~24 video/tuần chạm 30K tổng → push T2 thực tế ~3-8 lần/tuần.
- T2 push không cần quét xác nhận (hành động rẻ — chỉ chuẩn bị); T3 mới gác bằng xác nhận vì kéo theo sản xuất.

- Sàn là khởi điểm từ kinh nghiệm thực địa ("trend thật = trăm nghìn views/48h"), sẽ chỉnh sau 2 tuần dữ liệu sống.
- **Xuống bậc chậm hơn lên bậc (hysteresis):** rớt điều kiện 2 kỳ quét liên tiếp mới hạ bậc — chống nhấp nháy.
- **Xác nhận outlier ngay (yêu cầu user):** T3 kích hoạt một lần quét xác nhận sau 15-30 phút — VPH giữ được → push; T4 to đến mức bỏ qua xác nhận, push liền, xác nhận sau.

## 5. Adaptive sampling (càng nóng quét càng nhanh)

| Trạng thái | Nhịp quét |
|---|---|
| Nền — phát hiện video mới toàn niche | mỗi 3h (uploads playlist) — video mới nhất không bị mù quá 3h |
| Cohort D0-D1 | mỗi 2h |
| Cohort D2-D6 | mỗi 4h |
| T1 | mỗi 1-2h |
| T2/T3/T4 | mỗi 30-60 phút |
| Bảng VPD-cao-mọi-tuổi | mỗi 24h |

- Sàn 30 phút (view count API cache ~30-60 phút — quét nhanh hơn là đọc lại số cũ).
- Video <2h tuổi: chưa đủ cửa sổ VPH 2h → dùng VPH-since-publish, gắn cờ `ước lượng` trong board.
- Quota ước tính: ~900-1.000 units/ngày (uploads 3h chiếm phần lớn), dư dả với 2 key (20K).

## 6. Output & push

- **Push tức thì (ntfy.sh):** T2 (thông tin sớm), T3 (đã xác nhận), T4 (tức thì). Nội dung: bậc, title, kênh, VPH, VPD, tuổi, hạng cohort, link. Topic ntfy phải là **chuỗi dài ngẫu nhiên** (topic ntfy công khai theo tên — ai đoán được tên đọc được tin). (Hướng dẫn cài app sau khi code xong.)
- **Bảng trạng thái** `radar_board.md`: ghi đè mỗi lần quét — cohort ranking đầy đủ + bảng VPD-cao-mọi-tuổi + dòng heartbeat (lần quét cuối lúc nào — im lặng quá lâu = máy chết, user nhìn phát biết).
- **Diff-log** `alerts.log`: append-only, chỉ ghi thay đổi bậc (lên/xuống, video mới vào bảng). Không có gì thay đổi = không ghi.
- **Báo cáo tuần:** chủ nhật 08:00 — sổ cái sóng tuần (video nào lên T2+, số phận sau đó, kênh nào vào theo, đúng/sai của từng push), scorecard ngưỡng, đề xuất chỉnh sàn.

## 7. Cold start (48h đầu)

- Lần quét #1: chỉ lưu snapshot (chưa có delta) → cờ sơ bộ bằng VPD-sp (video 2 ngày tuổi 500K views hiển nhiên là outlier dù chưa có delta).
- Xếp hạng VPH chính thức từ lần quét #2. Tuần đầu = kỳ hiệu chỉnh sống: ghi phân phối VPH thực để vẽ lại 4 sàn.

## 8. Lưu trữ & vệ sinh dữ liệu

- Tick thô (mỗi lần quét): giữ 14 ngày → sau đó nén thành nến ngày. State JSON, không cần DB.
- Video bị xóa/private giữa chừng: đánh dấu `dead`, giữ lịch sử (đấy cũng là tín hiệu — video nổ rồi biến mất).
- Key rotation khi 403/429 (kế thừa weekly_radar).

## 9. Giới hạn nói trước

- Mù ngoài danh sách kênh (module search-discovery là plug-in tương lai, 1 lần/ngày, ~100-300 units).
- View count công khai có trễ cache 30-60 phút — "realtime" thực tế = độ phân giải 30 phút.
- VPH kỳ đầu của video vừa đăng nhiễu (thuật toán ramp) — vì thế T3 mới cần bước xác nhận.
- Radar chỉ trả lời "CÓ SÓNG, to cỡ nào" — đánh giá vì sao nổ và có đánh hay không do **user tự thẩm định** (quyết định thiết kế của user); việc mổ xẻ packaging thuộc pipeline thumbnail/Double Down.

## 10. Vòng tự học

- Mọi biến cố bậc được log kèm timestamp → chủ nhật tự chấm: T3/T4 push có thành sóng thật không (video đạt ≥X views ngày 7? có kênh khác vào theo?), T2 nào lẽ ra phải push.
- Sau 2 tuần: vẽ lại 4 sàn từ phân phối VPH thực. Sau đó chu kỳ chỉnh hàng tháng.

## Loop phản biện đã chạy (tóm tắt để truy vết quyết định)

- **v1 → phản biện 1:** xếp hạng bằng Δviews thô bị lệch khi các video quét nhịp khác nhau → đổi thước chính thành **VPH chuẩn hóa theo giờ**.
- **v1 → phản biện 2:** cắt cứng ngày 7 mù với video già VPD cao → thay "danh sách lão thành" phức tạp bằng **bảng VPD-cao-mọi-tuổi** (giải pháp của user — đơn giản hơn đề xuất của Claude).
- **v1 → phản biện 3:** top-3 của cohort nhỏ (~15-25 video) nhiễu → bắt buộc kèm sàn tuyệt đối; top-1 tuần ế không có ý nghĩa nếu không đạt sàn.
- **v1 → phản biện 4:** cache API làm VPH 30-phút răng cưa → cửa sổ VPH tối thiểu 2h + sàn nhịp quét 30 phút.
- **v1 → phản biện 5:** push sai làm mất lòng tin nhanh hơn mọi thứ → T3 phải qua quét xác nhận 15-30 phút; chỉ T4 được bỏ qua.
- **v2 → soát cuối:** cold start (mục 7), heartbeat chống chết im lặng (mục 6), vệ sinh dữ liệu (mục 8), timezone (mục 1).
- **v3 — vòng lặp cuối (07/07, theo yêu cầu user):**
  1. T2 cũng push (user cần tin sớm) → thêm dedup 1 push/video/bậc + trần 5 T2/ngày; kiểm bằng data: ~24 video/tuần chạm 30K tổng → thực tế ~3-8 push T2/tuần, không spam.
  2. Cohort đổi sang **rolling 24h** thay vì ngày lịch (video 23:50 vs 00:10 từng lệch cohort oan).
  3. Thăng/hạ bậc do **di cư cohort không push** — chỉ VPH-driven mới push (chống alert ma khi video già đi qua ranh giới).
  4. Nâng quét nền 6h → **3h** (video mới không bị mù quá 3h; quota vẫn dư).
  5. Video <2h tuổi: VPH-since-publish gắn cờ ước lượng.
  6. Topic ntfy = chuỗi ngẫu nhiên dài (bảo mật kênh push).
  7. Bỏ mối lo CTR/impression khỏi giới hạn — user tự thẩm định sóng, radar chỉ báo sóng.
  → **SPEC ĐÓNG BĂNG v3. Chờ lệnh code.**
