# RADARY — Phương pháp luận Tìm & Làm sạch Pool đối thủ (qua YouTube Data API)

*Tổng hợp từ phiên nghiên cứu — đã kiểm chứng trên dữ liệu thật. Ngày: 2026-07-23.*

---

## 0. Bối cảnh & phạm vi

Radary là radar phát hiện video outlier cho YouTube niche (chỉ YouTube · long-form >180s · trong pool kênh). Mỗi niche = 1 workspace = 1 pool kênh đối thủ. Vấn đề: **làm sao dựng và giữ pool ĐÚNG NGÁCH, đủ lớn, không loãng** — vì baseline VPH (T1-T4) phụ thuộc trực tiếp vào chất lượng pool.

Phiên này xây và kiểm chứng **3 công cụ độc lập nhưng ghép được**:
1. **PHÂN RÃ** pool hỗn tạp → các workspace thuần (rẻ, sạch nhất)
2. **MỞ RỘNG** pool bằng snowball đến hội tụ (khám phá kênh mới)
3. **AUDIT** pool có sẵn (phát hiện kênh lạc / lệch định dạng)

Firecrawl đã được xét và **loại khỏi lõi**: YouTube API đã cho dữ liệu sạch, Firecrawl chỉ hợp tầng L0/L1 (sự kiện ngoài YouTube) tương lai.

---

## 1. Nguyên lý nền: 3 trục đo "giống nhau"

| Trục | Đo bằng | Độ tin | Chi phí | Vai trò |
|---|---|---|---|---|
| **Vân tay nội dung** | Từ khóa title trùng centroid ngách (voc) | Cao, ổn định | Rẻ | **Xương sống** — quyết định IN/OUT |
| **Định dạng độ dài** | long-form ratio (>180s), độ dài median | Cao, khách quan | Rẻ | Lọc cứng — gạt vlog/shorts/sleep |
| **Khán giả chung** | Co-occurrence author comment (chuẩn hoá tỷ lệ) | Phụ thuộc ngách | Đắt (comment) | **Xác nhận** — chỉ xếp hạng, KHÔNG loại |

**Triết lý chốt (user quyết): "Nội dung làm nền, khán giả xác nhận."**
- Vân tay + định dạng là xương sống lọc pool (sạch, không thiên vị, rẻ).
- Khán giả chung chỉ NÂNG kênh có bằng chứng lên hạng cao, KHÔNG có quyền loại kênh (tránh phạt oan kênh lớn do mẫu comment nhỏ).
- Giữ Nguyên tắc 5 Radary: mọi output là ĐỀ XUẤT cho user duyệt, không tự thêm vào pool. Mỗi kênh kèm "giống vì X" + "có thể sai vì Y" (TC7).

---

## 2. CÔNG CỤ 1 — PHÂN RÃ pool hỗn tạp → workspace thuần

**Khi dùng:** có sẵn 1 pool lớn không chắc thuần, muốn tách thành các niche mạch lạc (mỗi cái 1 workspace + mô tả).

**Thuật toán 2 tầng CỨNG (không snowball, không comment, không thị giác):**

- **Tầng 1 — Ngôn ngữ** (ranh giới tuyệt đối). Phát hiện ngôn ngữ chính mỗi kênh qua *function words* trong title (EN/ES/PT... rạch ròi; langdetect không build được → tự viết bộ vote function-word + dấu hiệu ã/õ/ç cho PT, ñ/¿ cho ES). Video khác ngôn ngữ KHÔNG BAO GIỜ chung workspace (baseline/khán giả/thuật toán đề xuất đều khác).
- **Tầng 2 — Định dạng độ dài** (trong mỗi ngôn ngữ). 4 nhóm tự nhiên theo long-form ratio + độ dài median:
  - `long-form documentary` (lr≥0.7)
  - `sleep/ambient` (med≥40 phút — ngách xem-để-ngủ, khác hẳn)
  - `short-form/clip` (lr≤0.3 — kênh official NASA/ESA đăng clip)
  - `mixed`

**Đầu ra:** cây phân rã → **user tự cắt** (máy trưng cây + điểm, người quyết gộp/tách — quyết định chiến lược, không phải toán học). Mỗi nhóm lá = 1 workspace kèm **mô tả tự sinh** (ngôn ngữ, dải độ dài, số kênh, dải subs, top từ khóa, kênh đại diện) để dán thẳng vào Radary.

**Kết quả kiểm chứng (pool "Space" 86 kênh):** tách ra EN 73 / ES 8 / PT 5; trong EN lộ 4 nhóm rất khác nhau (documentary 33, sleep/ambient 15, mixed 15, short-form 10). Chi phí chỉ **~1,300 units** (không comment). → Đây là công cụ RẺ và SẠCH nhất, nên là bước ĐẦU TIÊN khi có pool bẩn.

---

## 3. CÔNG CỤ 2 — MỞ RỘNG pool bằng Snowball có kiểm soát

**Khi dùng:** có seed nhỏ (vài kênh), muốn dựng pool đối thủ đầy đủ.

**Thuật toán:**
1. **Vòng 0:** search keyword ban đầu → lọc 2 tầng → pool gốc. Dựng **centroid ĐÓNG BĂNG** từ seed gốc.
2. **Mỗi vòng:** lấy title THẬT của cả pool → rút n-gram đặc trưng (khung title, bỏ tên riêng/số) → search sâu (`type=channel` + `type=video` long) → loại kênh đã gặp → **lọc Tầng 1 bằng centroid GỐC** (chống trôi) → thêm kênh đạt chuẩn.
3. **Dừng** khi vòng đẻ ≤1 kênh mới đạt chuẩn (hội tụ hình học).

**4 "cửa" sinh ứng viên — SỰ THẬT sau kiểm chứng:**
- **Cửa 3 (search sâu theo title thật): ĐỘNG CƠ CHÍNH & DUY NHẤT mạnh.** Rút từ khóa từ title THẬT của pool (không phải keyword tự nghĩ) → bắt đúng ngôn ngữ ngách.
- **Cửa 1 (featured channels):** endpoint `channelSections.list`, type=`multipleChannels`, đọc `contentDetails.channels[]`. TỒN TẠI (tài liệu xác nhận) nhưng **VÔ DỤNG thực tế** — test 0/24 kênh có gắn (YouTube ẩn featured từ ~2023). Chỉ thử vì rẻ (~1-3 units).
- **Cửa 2 & 4 (author dẫn đường):** **BẤT KHẢ THI qua API** — không có endpoint "author đã comment ở đâu". Co-occurrence chỉ CHẤM ĐIỂM kênh đã tìm, KHÔNG khám phá kênh mới. (Muốn author dẫn đường phải cào ngoài API → phá ràng buộc Radary.)

**Kết quả kiểm chứng (ngách "Life in Country", 3 seed):**
Đà kênh mới qua các vòng: **17 → 8 → 4 → 0** (hội tụ tuyệt đối ở vòng 3). Pool cuối 18 kênh ≥5K sub. → Chứng minh snowball hội tụ HÌNH HỌC.

---

## 4. CÔNG CỤ 3 — AUDIT pool có sẵn

**Khi dùng:** kiểm 1 pool đang chạy có kênh lạc / lệch không.

Dùng đúng phần chấm điểm của công cụ 1+2, bỏ khâu khám phá:
- Đo vân tay + long-form từng kênh so centroid pool → **kênh nghi lạc** (sim thấp) xếp theo mức lệch.
- Phân cụm để lộ pool bị trộn mấy ngách (**coherence** — nếu tách thành nhiều cụm rõ → pool cần tách workspace).
- Cờ kênh long-form <50% (lệch bộ lọc >180s của Radary).

**Giới hạn thành thật:** audit bắt "lạc về nội dung/ngôn ngữ/định dạng", KHÔNG bắt kênh chết (bỏ đăng lâu) hay reup lậu — cần thêm tín hiệu ngày-đăng-gần-nhất.

---

## 5. Bài học phương pháp (đã trả giá bằng dữ liệu)

### 5.1 Comment là cửa sổ khán giả DUY NHẤT của API — nhưng thiên vị nặng
- Không có watch history / subscriber list (khoá từ 2019). Chỉ comment.
- 5 thiên vị: (1) người comment ≠ người xem (~0.1-1%); (2) `order=relevance` thiên fan cứng; (3) trần trang cắt đuôi khán giả; (4) author ẩn biến mất; (5) mẫu nhỏ làm kênh LỚN giả core=0.
- **Khử:** tăng mẫu (484→1722 author), trộn `relevance`+`time`, nhiều trang, **chuẩn hoá theo TỶ LỆ** (không đếm tuyệt đối), báo cỡ mẫu N kèm mỗi điểm.
- Bằng chứng khử hiệu quả: The Global Truth v1 core=8 → v2 core=17; nhiều kênh v1 core=0 thực ra có giao khi mẫu đủ lớn.

### 5.2 Co-occurrence PHỤ THUỘC mức tương tác ngách
- Ngách tương tác cao (Life in Country) → hoạt động tốt.
- Ngách xem thụ động (Old Money documentary) → core=0 hàng loạt, vô dụng.
- → Module phải coi Tầng 2 (khán giả) là trục CÓ ĐIỀU KIỆN, không luôn bật.

### 5.3 Kích thước pool là thuộc tính của NGÁCH, không phải thuật toán
- Ngách hẹp (Life in Country) hội tụ sau 2-3 vòng, pool ~18-20 kênh — đó là kích thước THẬT.
- Ngách rộng/phân mảnh (nấu ăn/gaming) mới cần nhiều vòng snowball.
- **Đừng nhồi kênh bẩn cho pool to** — pool 20 kênh sạch > 150 kênh bẩn (Nguyên tắc 4: báo thẳng kết quả xấu).

### 5.4 Chống trôi ngữ nghĩa (drift)
- Snowball cập nhật pool mỗi vòng → centroid dễ trôi dần khỏi ý định gốc, mỗi bước đều "trông hợp lý".
- **Chống:** đóng băng centroid từ seed gốc / giữ "mỏ neo ngữ nghĩa" (vài kênh lõi tuyệt đối), đo pool mới có còn gần mỏ neo. Trôi → dừng.

### 5.5 search.list là kẻ đắt đỏ
- search = 100 units/lần; channels/videos/playlistItems/commentThreads = 1 unit/lần.
- Trong phiên, search chiếm ~1/3 tổng quota dù ít lần gọi. → Mỗi query search phải đáng giá.

---

## 6. Ngưỡng & tham số đã dùng (mặc định, chỉnh theo ngách)

- Tầng 1 vào pool: `voc≥15` (từ khóa title trùng) VÀ `long_ratio≥0.6` VÀ `subs≥5K` (user chốt 5K chặn rác).
- Trục mạnh (luật kép, ≥2 trục vào hạng A): khán giả `aud≥2` · vân tay `voc≥15` · quy mô `subs≥5K` · long-form `≥60%`.
- Hội tụ snowball: vòng đẻ ≤1 kênh mới đạt chuẩn.
- Phân rã định dạng: sleep/ambient `med≥2400s`; long-form `lr≥0.7`; short `lr≤0.3`.

---

## 7. Ghép 3 công cụ = quy trình đầy đủ

```
Pool hỗn tạp ──[CÔNG CỤ 1: PHÂN RÃ]──> nhiều workspace thuần + mô tả
                                              │
                          user chọn ngách đáng làm
                                              │
Seed nhỏ / workspace mỏng ──[CÔNG CỤ 2: SNOWBALL]──> pool đầy đủ đến hội tụ
                                              │
Pool đang chạy ──[CÔNG CỤ 3: AUDIT định kỳ]──> phát hiện kênh lạc/lệch → gỡ
```

Đây chính là "2 vòng quy nạp–hồi quy" user hình dung: **phân rã (làm sạch/định hình) + mở rộng (khám phá)**, đan xen, con người cắt cây & duyệt ở các điểm quyết định.

---

## 8. Chi phí đã tiêu (phiên này)

~31,000 units tổng, trải trên 6-7 key từ nhiều dự án Google Cloud (tự xoay khi 403). Chỗ ngốn nhất: đo comment độ sâu đầy đủ v2 (~13K) và snowball (~12K). Phân rã Space chỉ ~1,300 (không comment) — rẻ nhất.

**→ Hàm ý vận hành module:** ưu tiên phân rã + vân tay (rẻ), chỉ dùng comment khi thật cần xếp hạng đối thủ trực diện. Ước tính quota TRƯỚC mỗi loại quét (quy ước Radary).

---

## 9. Trạng thái & bước tiếp

- Logic 3 công cụ ĐÃ ĐỦ vững để viết spec module cho Radary (chu trình spec-trước-code-sau).
- Chưa làm: viết spec chính thức; tích hợp ngày-đăng-gần-nhất cho audit; thử phân rã/snowball trên ngách rộng.
- **Bảo mật:** 6-7 key YouTube (đuôi 1TOI, gR_M, wsXI, NtAM, BW68, O3p0, RyvA) đã đi qua chat NHIỀU → NÊN tái tạo/xoá trong Google Cloud Console.

## Phụ lục — Deliverables đã tạo trong phiên
- `pool_de_xuat.md` — ngách Old Money (co-occurrence yếu)
- `pool_life_in_country.md` (v1), `pool_v2.md` (v2 khử thiên vị)
- `pool_final.md` — snowball 3 vòng, bằng chứng hội tụ 17→8→4→0
- `space_audit.md` — audit pool Space (4 cụm trộn)
- `space_workspaces.md` — cây phân rã Space → 9 workspace + mô tả
