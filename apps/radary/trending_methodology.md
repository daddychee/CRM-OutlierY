# RADARY — Phương pháp luận DÒ TREND NGOÀI (Trending)

*Tổng hợp từ phiên nghiên cứu 23/08/2026 — mọi con số dưới đây đo trên dữ liệu thật, kèm cách
đo để chạy lại. Bổ sung cho `radary_methodology.md` (dựng pool) — file đó lo **pool sạch**,
file này lo **đề đúng**.*

**Trạng thái: CHƯA CODE.** Đã chạy tay đầu-cuối cho pool LIFE IN — US, kết quả ở §6.

---

## 0. Bài toán

Mapping trả lời rất tốt câu "trong pool đang có gì". Nhưng khi dùng nó để **chọn đề cho video
mới** thì lộ ra giới hạn mà không tham số nào chỉnh được:

> **Pool không đo NHU CẦU của khán giả. Pool đo QUYẾT ĐỊNH của đối thủ.**

Một video nằm trong pool là bằng chứng rằng ai đó **đã quyết định làm nó vài tuần trước**:

```
Sự kiện thật                                    ← T0
  ↓ giờ            tin tức đưa
  ↓ giờ–ngày       người ta TÌM KIẾM             ← nhu cầu xuất hiện Ở ĐÂY
  ↓ ngày           thảo luận (Reddit, X)
  ↓ ngày–tuần      người sáng tạo QUYẾT ĐỊNH làm
  ↓ tuần           sản xuất
  ↓                video đăng
  ↓ tuần           đủ view để Radary quét thấy   ← pool nhìn thấy Ở ĐÂY
```

Khoảng cách hai mốc là **hàng tuần đến hàng tháng**, và pool còn chỉ thấy video **đã thành
công** — tức đã qua vòng cạnh tranh. Đây là giới hạn **cấu trúc**, không phải giới hạn thuật
toán: không có cách nào làm cho tín hiệu trong pool sớm lên được.

Hệ quả cho việc chọn đề, phát biểu gọn:

> **Đồng thuận của nhóm outlier là chỉ báo TRỄ của nhu cầu, và là chỉ báo SỚM của bão hoà.**

Việc 5 video đã nổ trên một chủ đề chính là bằng chứng rằng nhu cầu đó **đã được phục vụ**.

---

## 1. Nguyên lý nền: đảo chiều TRA CỨU → QUÉT

`tra_cuu.py` hiện là **tra cứu**: đưa một cụm, nó trả Trends/News/Wikipedia/YouTube cho cụm đó.
Nghĩa là **người dùng phải đã nghi ngờ cụm đó rồi**. Nó không phát hiện được thứ chưa ai nghĩ tới.

Trending là chiều ngược lại:

> **Bắt đầu từ THẾ GIỚI, lọc dần về ngách.** Không phải bắt đầu từ ngách rồi tra ra ngoài.

Và phễu phải **xếp theo chi phí tăng dần** — tầng rẻ lọc mạnh trước, tầng đắt chỉ chạm phần
sống sót.

---

## 2. Chọn nguồn sinh ứng viên: vì sao Google chứ không Wikipedia

Đã thử cả hai trên cùng một ngày (21–23/08/2026):

| | Wikipedia top-viewed | **Google Trending Now** |
|---|---|---|
| Loại danh sách | **Xem nhiều nhất** (tuyệt đối) | **Đang lên** (đã dò bất thường sẵn) |
| Kết quả thật | `Main_Page`, `Special:Search`, `Deaths_in_2026`, Hayden Panettiere, phim… | `guyana`, `peru earthquake`, `greenland`… |
| Số ứng viên | 1.000/ngày, phần lớn là trang phổ biến **thường trực** | **2.996/tuần/thị trường**, mỗi mục là một cú nhô |
| Kèm theo | không có gì | lượng tìm kiếm · **giờ bắt đầu · giờ kết thúc** · truy vấn con |

Khác biệt không nằm ở "ai được search trước", mà ở **loại danh sách**: Wikipedia buộc mình tự dò
bất thường trên một bảng bị các trang phổ biến thường trực chiếm chỗ; Google đưa thẳng thứ đang
lên. Top-1000 Wikipedia một ngày **gần như không có thực thể địa lý nào** — nó nghiêng hẳn về
người nổi tiếng, phim, người mất.

**Chốt: nguồn ứng viên là Google Trending Now.** Wikipedia vẫn dùng, nhưng ở vai khác —
**xác minh loại thực thể** (§4.2).

### Công cụ

`trendspyg` 1.6.0 (đã cài, đã dùng cho `tra_cuu.google_trends`):

| Hàm | Cho gì | Chi phí |
|---|---|---|
| `download_google_trends_rss(geo)` | ~10 trend đang nóng **kèm bài báo nguồn** | RSS, không cần trình duyệt, rất rẻ |
| `download_google_trends_csv(geo, hours=168, category)` | **2.996** trend/tuần kèm lượng + cửa sổ + truy vấn con | 1 lượt trình duyệt |

Cột trả về của bản CSV: `Trends` · `Search volume` · `Started` · `Ended` · `Trend breakdown` ·
`Explore link`.

---

## 3. Kiến trúc ba bước

```
Trending(pool)
 ├ 1  QUÉT NGOÀI      Google Trending Now  →  lọc LOẠI  →  ~10-25 ứng viên
 │                    (1 lời gọi/tuần/thị trường · 2 lời gọi Wikipedia)
 ├ 2  ĐỐI CHIẾU POOL  cung × hiệu suất → bốn ô   (0 quota, đọc DB nhà)
 └ 3  ĐÀO SÂU         [NGƯỜI bấm] → mapping / tra_cuu / report_cum  ← giữ nguyên như đang có
```

Ba lý do kiến trúc này đúng:

1. **Phễu tăng dần theo chi phí.** Bước 1 một lời gọi cho cả tuần · bước 2 **0 quota** · bước 3
   mới là chỗ đắt (Trends explore ~17s, quota YouTube) và chỉ chạy cho cái người dùng chọn.
2. **Bước 2 là thứ duy nhất không ai có ngoài mình.** Google cho ai cũng thấy như nhau; pool là
   tài sản riêng.
3. **Không phải viết lại gì.** Mapping/`tra_cuu`/`report_cum` giữ nguyên vai, chỉ chuyển từ "cửa
   vào" thành "bước đào sâu".

**Ràng buộc thứ tự:** lọc LOẠI phải nằm ở **bước 1**, không phải bước 2. Nếu để bước 2 lọc thì
kết quả "không có trong pool" vô nghĩa vì nó lẫn hai thứ khác hẳn nhau — *chưa ai làm* (cơ hội)
và *không liên quan ngách* (rác). Pool không phân biệt được hai cái đó.

---

## 4. BƯỚC 1 — Quét ngoài

### 4.1 Lọc loại thực thể — khai theo POOL, không hằng số trong code

Bộ lọc "địa lý" chỉ đúng cho ngách nơi-chốn. SPACE cần nhiệm vụ/thiên thể, Health cần
bệnh/thực phẩm, Investigation cần vụ việc. Hằng số hoá thì hàm chỉ chạy cho một loại ngách.

Pool đã có `ngach` và `market`; thêm một trường **"loại thực thể quan tâm"** là đủ, và giữ đúng
lệ *luật ngoài code*.

### 4.2 Xác minh loại qua mô tả Wikipedia

Khớp chuỗi với danh mục địa danh cho **69/2.996 (2,3%)** — nhưng lẫn nhầm tên riêng
(`air jordan 5`, `antigua gfc`, `jordan spieth`). Xác minh bằng `action=query&prop=pageterms`
(gộp **50 mục/lời gọi** → chỉ **2 lời gọi** cho 69 ứng viên), giữ mục có mô tả chứa
*country / island / city / nation / region / territory / republic / archipelago / province*.

### 4.3 Ba thứ đọc thẳng từ dữ liệu, không phải tính

| Đọc từ | Cho biết |
|---|---|
| Cột `Ended` = `nan` | **cửa sổ còn mở** — không phải tự suy |
| Cột `Started` | tuổi của cú nhô |
| `Trend breakdown` | **nguyên nhân**: `peru` → *picchu* (tò mò du lịch) · `oman` → *trump oman, trump iran* (địa chính trị) |

Cột nguyên nhân chính là phép phân biệt **"bắc cầu được hay không"**: một cú sốc tin tức và một
cú tò mò du lịch cùng là "tên nước đang trending", nhưng chuyển thành phim tài liệu thì khác hẳn.

### 4.4 LUẬT: không xếp bảng theo lượng tìm kiếm

Đo thật: thứ đáng giá đều **nhỏ** — `guyana` 100+, `haiti` 2K+, `brunei` 5K+ — trong khi bảng bị
`hayden panettiere` 10M+ và các trận bóng 200K+ chiếm đầu. **Xếp theo lượng là chôn sạch thứ mình
cần.**

---

## 5. BƯỚC 2 — Đối chiếu pool

### 5.1 Hai câu hỏi, độ chắc KHÁC NHAU

| Bước 2 trả lời | Độ chắc |
|---|---|
| **Vừa ngách không** — pool có video về loại đề hình dạng này không | **Chắc.** Bằng chứng thực nghiệm rằng khán giả mình tiêu thụ dạng đề này |
| **Sớm hay muộn** — đã có bao nhiêu video về đúng đề này | **Đã bác — xem 5.2** |

Đo trên LIFE IN — US: **2.513/3.631 video (69%)** có tên quốc gia trong tiêu đề. Pool tự chứng
minh nó tiêu thụ đề-quốc-gia.

### 5.2 Trục "sớm/muộn" ĐÃ BỊ BÁC BẰNG SỐ

Thiết kế đầu dùng *đếm video trong pool* → nhãn sớm / đang mở / muộn. Chạy thật thì
**`SỚM` bằng 0, gần như toàn bộ ra `MUỘN`**.

Lý do rõ khi nhìn số: pool có 3.631 video và **đã phủ gần hết các quốc gia**. Ở độ hạt "tên
nước", pool đã bão hoà, nên câu hỏi "đã ai làm chưa" luôn trả lời "rồi". **So sai độ hạt.**

### 5.3 Thay bằng CUNG × HIỆU SUẤT — bốn ô

So với trung vị view/ngày của **chính pool** (LIFE IN — US = 17):

| Ô | Ý nghĩa | Ví dụ đo thật |
|---|---|---|
| **THIẾU CUNG** — ít video, chạy tốt | ★ đáng làm | `chad` 2v **20×** · `liberia` 2v **12×** · `haiti` 6v **8×** · `guyana` 10v **7×** · `jamaica` 9v **6×** · `suriname` 10v **6×** |
| Đã khai thác — nhiều video, chạy tốt | có cửa nhưng đông | `russia` 67v 4× · `iran` 44v 4× · `sweden` 65v 3× |
| **ĐÃ THỬ, KHÔNG ĂN** — ít video, chạy kém | ✗ tránh | `senegal` 2v **0×** · `el salvador` 6v **0×** · `gabon` 2v 1× |
| Bão hoà — nhiều video, chạy kém | ✗ tránh | `uzbekistan` 45v 1× · `japan` 61v 1× · `thailand` 51v 1× |

**Ô thứ ba là lý do phải có trục hiệu suất.** Chỉ đếm video thì `senegal` (2 video) trông như mỏ
vàng bỏ ngỏ; thêm hiệu suất thì thấy pool **đã thử và chết** — 2 video, 1 view/ngày. Đây cũng
chính là cách gỡ **bẫy sống sót** đã nêu cho ma trận Topic × Hook: phân biệt *chưa ai làm* với
*làm rồi mà phẳng*, bằng dữ liệu nhà, 0 quota.

---

## 6. Kết quả chạy thật — LIFE IN — US, 23/08/2026

| Tầng | Còn lại |
|---|---|
| Trending Now (US, 168h) | 2.996 |
| Lọc thực thể địa lý | 69 |
| Xác minh loại qua Wikipedia | (loại `air jordan 5`, `antigua gfc`…) |
| Có số đối chiếu pool | 40 |
| **Giao: cửa sổ ĐANG MỞ × ô THIẾU CUNG** | **2** |

| Ứng viên | Cửa sổ | Pool | Nguyên nhân |
|---|---|---|---|
| **guyana** | ĐANG MỞ | 10 video, **7×** trung vị | *chưa rõ — breakdown rỗng* |
| **jamaica** | ĐANG MỞ | 9 video, **6×** trung vị | `latoya malcolm, miss universe` |

Từ 2.996 xuống 2 — mật độ dùng được cho một cửa người duyệt.

`jamaica` minh hoạ đúng vì sao **bước 3 phải do người bấm**: nguyên nhân là một cuộc thi hoa hậu.
Có bắc cầu sang phim tài liệu đời sống được không? **Máy không quyết được câu đó.**

---

## 7. Bài học đã trả giá bằng dữ liệu (đừng làm lại)

### 7.1 Xếp hạng cluster theo cầu thị trường — SAI HƯỚNG

Đề xuất đầu là dùng bảng cầu của Mapping để xếp lại cluster của Outline Extract. Nó **kéo bài
viết về gần tâm** của thứ đã tồn tại — hồi quy về trung bình có chủ đích. Xem §0.

### 7.2 "Nâng nền sau cú sốc" — ĐO KHÔNG RA, đừng xây tiếp lên nó

Giả thuyết: sau cú sốc, nền quan tâm đứng cao hơn trước, tạo "sóng thứ hai" ít cạnh tranh hợp với
chu kỳ sản xuất chậm. Đo 81 quốc gia bằng Wikipedia pageviews 13 tháng:

- **0/3** ca đo được có nâng nền (Bahrain 3,6× · Greenland 19,6× · Nepal 5,9× đều tụt về
  **0,71–0,81**, thấp hơn cả độ trôi tự nhiên).
- **Nhóm đối chứng cứu khỏi một kết luận sai:** lưu lượng bài quốc gia trên Wikipedia **giảm chung
  ~15%/năm**. Không có đối chứng thì mọi "sau < trước" bị đọc nhầm thành "cú sốc tàn lụi".
- **Nhưng công cụ đo có thể sai:** cùng ca Greenland, Google Trends cho **×1,67** trong khi
  Wikipedia cho **×0,79** — ngược chiều. Wikipedia đo *một lần tra cứu*, Trends đo *quan tâm còn
  lại*. Mà Trends ở nền 3→5 trên thang 0–100 thì hai đơn vị nguyên, quá thô để tin.

**Kết luận: câu hỏi chưa trả lời được bằng công cụ ngoài.** Không dùng nó làm nền móng cho bất cứ
tính năng nào.

### 7.3 Tốc độ tàn — cái này thì CHẮC

Sau **1 tháng chỉ còn giữ trung vị 57%** đỉnh; chỉ **1/13** còn ≥3× nền ở tháng đo cuối.
Ivory Coast 6,9× → 1,4× (giữ 21%).

Và **độ dài cửa sổ là thuộc tính của NGUYÊN NHÂN, không phải của chủ đề**:

| | Đỉnh | Sau 1 tháng | Giữ |
|---|---|---|---|
| Cape Verde (giải đấu đang diễn ra) | 25× | **20×** | **79%** |
| Paraguay, Senegal | 3,8–5,2× | 2,8–3,8× | 74–75% |
| Ivory Coast | 6,9× | 1,4× | 21% |

Nên câu hỏi đúng không phải *"có bùng không"* mà **"do cái gì gây ra, và cái đó kéo dài bao lâu"**.

### 7.4 Chủ đề xuyên niche: hai chế độ, đừng lẫn

- **Bình thường:** từ vựng chủ đề **cục bộ** trong niche. Đo 5 pool US: chủ đề (`doi_tuong`) phủ
  trung bình **1,14 niche**, chỉ **3%** có mặt ở ≥3 niche.
- **Khi có cú sốc:** một thực thể tạm thời thành phổ quát. Đo có trục thời gian thì thấy thật:
  `panama` LIFE IN 02/2026 (5,4×) → RETIREMENT 05/2026 (9,1×); `switzerland` LIFE IN 04/2026 →
  TRAVEL DOC 05/2026 (cách 1 tháng).

Bài học phép đo: **phép đo cộng dồn toàn lịch sử KHÔNG thấy được cú sốc** — một chủ đề bùng 6
tuần ở 5 niche, chia cho 10 năm titles, thành số lẻ. Bóp trục thời gian là bóp đúng trục mang
tín hiệu.

> **Việc một chủ đề đang lan xuyên niche chính là DẤU HIỆU của một cú sốc đang diễn ra** — nó là
> máy dò trạng thái, không phải thuộc tính tĩnh để tra cứu.

**Hệ quả vận hành:** máy dò lan-xuyên-niche chỉ mạnh khi các pool **xa nhau**. Hiện LIFE IN,
TRAVEL DOC, RETIREMENT đều là ngách "nơi chốn" — gần nhau nên cùng bùng là gần như hiển nhiên.
Muốn dò cú sốc thật cần ít nhất một pool ở xa (tin tức, thể thao, kinh tế).

---

## 8. Ngưỡng & tham số (mặc định, chỉnh theo ngách)

| Tham số | Giá trị | Căn cứ |
|---|---|---|
| Cửa sổ quét Trending | `hours=168` (7 ngày) | đủ để không sót, chưa quá cũ |
| Ngưỡng "ít video" | ≤ 10 video trong pool | đo LIFE IN — US; chỉnh theo cỡ pool |
| Ngưỡng "chạy tốt" | ≥ 2× trung vị view/ngày **của chính pool** | trung vị pool, không phải hằng số |
| Cờ chưa đủ mẫu | < 5 video | xem §9.1 |
| Gộp Wikipedia pageterms | 50 mục/lời gọi | giới hạn API |
| Ngân sách bước 3 | dùng lại `NGAN_SACH_NONG` (5 cụm/ngày/pool) | không đẻ cơ chế thứ hai |

---

## 9. Khiếm khuyết đã biết

**9.1 Mẫu quá nhỏ ở đúng ô đẹp nhất.** `chad` 20× là trung vị của **2 video**. Phải gắn cờ "chưa
đủ mẫu" khi n < 5, không thì ô THIẾU CUNG toàn ảo ảnh thống kê.

**9.2 Hiệu suất là chuyện quá khứ.** 7× của `guyana` là các video cũ đã chạy — không phải bằng
chứng rằng video mới sẽ chạy.

**9.3 Nối nhầm thực thể.** `jordan` lọt vào từ trend `jordan spieth comments pga tour`; bộ lọc
loại cho qua vì Jordan *là* một quốc gia. Cần thêm phép kiểm **ngữ cảnh**, không chỉ kiểm loại.

**9.4 Trend tên-nước-trơ-trọi không kèm breakdown** → không biết vì sao nó nóng (`guyana` đang mở
mà không rõ lý do). Phải lấy thêm `news_articles` từ RSS.

**9.5 Chỉ mới quét `geo=US`.** Chủ đề nóng ở thị trường khác có thể không hiện.

**9.6 Trending Now bắt CÚ NHÔ, không bắt ĐÀ LÊN CHẬM.** Chủ đề lên từ từ suốt 3 tháng sẽ không
bao giờ "trending" — nên nó **bổ sung** cho đường 12 tháng của `tra_cuu`, không thay thế.

---

## 10. Ghi sổ — để câu hỏi treo tự trả lời

Câu hỏi lớn còn treo — *đi sớm có thật sự thắng không* (§7.2) — sẽ **tự trả lời bằng dữ liệu của
chính mình**, nếu ngay từ đầu hàm này ghi lại:

> mỗi ứng viên nó đưa ra · ô nào (thiếu cung / đã thử không ăn / …) · cửa sổ lúc đó · **người có
> chọn làm không** · và video ra sau đó chạy thế nào

Sau 6 tháng có bảng đối chiếu **quyết định thật ↔ kết quả thật**, không cần thí nghiệm ngoài nào.
Chi phí: một dòng ghi thêm vào CSV. **Không ghi từ đầu thì sáu tháng nữa vẫn phải đoán.**

---

## 11. Trạng thái & bước tiếp

**Chưa code.** Đã chạy tay đầu-cuối, kết quả §6.

1. Bước 1 + 2 (đọc thuần, 0 quota YouTube) + sổ ghi ứng viên §10.
2. Lấy `news_articles` cho ứng viên không có breakdown (§9.4).
3. Kiểm ngữ cảnh chống nối nhầm thực thể (§9.3).
4. Nối bước 3 vào `mapping` / `tra_cuu` / `report_cum` đã có — **người bấm, từng cái một**.

**Giữ Nguyên tắc 5 Radary:** mọi output là ĐỀ XUẤT cho người duyệt. Máy bày bằng chứng, không xếp
hạng hộ, không tự chọn đề.
