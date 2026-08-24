# Mapping × Outline Extract — phân tích chiến lược

> Bản 2, 23/08/2026. Bản 1 (đề xuất kỹ thuật thuần) đã bị Owner bác đúng chỗ; phần
> phản biện và lý do bác giữ lại ở mục 1 vì nó là bài học, không phải rác.
>
> **Chưa code.** Đây là tài liệu chiến lược để chốt hướng.

---

## 1. Bản 1 sai ở đâu — và vì sao cái sai đó đáng ghi lại

Bản 1 đề xuất: lấy bảng cầu của Mapping để **xếp hạng lại các cluster** của Outline
Extract, rồi thêm khoảng trống thị trường thành chương phụ.

Owner bác bằng một câu: *"chỉ dùng cấu trúc hiện tại thì chỉ có giá trị trung bình
của các video đã nổi — không có tính mới."*

Câu đó đúng, và đúng sâu hơn cách nó được nói. Diễn đạt lại theo ngôn ngữ chiến lược:

> **Đồng thuận của nhóm outlier là chỉ báo TRỄ của nhu cầu, và là chỉ báo SỚM của
> bão hoà.**

Chính việc 5 video đã nổ trên một chủ đề là bằng chứng rằng nhu cầu đó **đã được
phục vụ**. Lấy phần giao của 5 người thắng rồi làm video thứ 6 nghĩa là: sản phẩm
giống nguồn cung hiện có nhất, ra đúng lúc nguồn cung đó dồi dào nhất. Kỳ vọng lợi
nhuận hội tụ về **trung vị của format** — mà trung vị của một format đã có 5 outlier
thì theo định nghĩa **không phải outlier**.

Bản 1 tệ hơn thế: nó tối ưu **đúng hướng sai**. Xếp hạng cluster theo cầu thị trường
là kéo bài viết **về gần tâm** của thứ đã tồn tại. Đó là hồi quy về trung bình có
chủ đích.

Và bản 1 còn bỏ sót: ba cỗ máy trả lời đúng câu hỏi này **đã được xây rồi** trong
RadarY — `tra_cuu.py`, `report_cum.py`, và ma trận Topic × Hook trong `mapping.py`.

---

## 2. Nhưng đừng vứt Outline Extract — nó đúng ở tầng khác

Phản biện ngược lại chính mình: nếu đồng thuận outlier vô dụng, vì sao Outline
Extract vẫn cho ra kịch bản dùng được?

Vì kết quả một video không phải một đại lượng. Tách ra:

```
Kết quả  ≈  PHÂN PHỐI  ×  GIỮ CHÂN
             │              │
             │              └── khung, nhịp, vị trí payoff  → là NGHỀ, học được
             └── đề mới lạ × bao bì × thời điểm             → là CƠ, không sao chép được
```

**Nghề thì phải sao chép. Cơ thì sao chép là chết.**

Đồng thuận của người thắng nói rất chuẩn về *cách kể*: mở thế nào thì người ở lại,
đặt payoff ở phút mấy, chương hai phải là gì thì không rơi. Những thứ đó **khái quát
hoá được** sang chủ đề khác, vì chúng là quy luật chú ý của con người trong ngách
đó, không phải nội dung.

Chúng nói rất tệ về *kể cái gì* — vì cái đó đã bị tiêu thụ mất rồi.

### Luật quy nạp

> **Trung bình hoá người thắng là ĐÚNG ở tầng CÁCH LÀM, và SAI ở tầng LÀM GÌ.**

Kiến trúc hiện tại **nhập hai quyết định này vào một**: chương của outline sinh ra từ
những gì 5 video tình cờ nói. Nghĩa là câu hỏi "kể cái gì" đang được trả lời bằng dữ
liệu chỉ dùng được cho câu hỏi "kể thế nào". Đó là lỗi kiến trúc, không phải lỗi
thiếu dữ liệu — và vì thế **không một lượng dữ liệu Mapping nào bơm vào tầng chương
sửa được nó**.

---

## 3. Tính mới đến từ đâu — hình thức hoá ví dụ Christmas Island

Ví dụ của Owner chứa trọn vẹn ba loại chênh lệch, và đó không phải ngẫu nhiên — nó
là ba con đường duy nhất tạo được tính mới có thể đo:

**a) Chênh lệch THỜI ĐIỂM.** SpaceX hạ cánh xuống đảo → cú sốc cầu từ **ngoài** nền
tảng. Pool không thấy vì pool được định nghĩa bằng ngách, mà Christmas Island không
thuộc ngách. Nguồn tín hiệu: Google News, Trends đang lên, Wikipedia pageview vọt.
*Cả ba đã có trong `tra_cuu.py`.*

**b) Chênh lệch KHUNG.** Chủ đề đã bão hoà nhưng mọi người đóng gói giống nhau. Ô
trống trong ma trận Topic × Hook. *Đã có: `cap_goi_y`.*

**c) Chênh lệch CÂU HỎI.** Điều khán giả thật sự muốn biết ≠ điều người làm nội dung
đang cung. Christmas Island: nhà sáng tạo nói về SpaceX, còn người ta gõ **cua**,
**chi phí sống**, **đảo đó có giàu không**. *Đã có: Trends related queries + khối
"Câu hỏi thật người ta hỏi" + Reddit.*

Ba loại này là **ba ván bài khác nhau về kinh tế**, không được trộn:

| Chênh lệch | Cửa sổ | Cạnh tranh | Rủi ro chính | Ai thắng |
|---|---|---|---|---|
| Thời điểm | Ngày–tuần | Thấp rồi bùng rất nhanh | **Sai khán giả**: người đến vì sự kiện, không vì ngách; view cao mà không nuôi kênh | Nhanh nhất |
| Khung | Tháng | Trung bình | Ô trống vì **vô lý**, không phải vì chưa ai làm | Sắc sảo nhất |
| Câu hỏi | Bền | Cao | Câu hỏi có thật nhưng **không đủ nuôi 20 phút** | Sâu nhất |

Và đây là chỗ ví dụ Christmas Island hay nhất: **một mình sự kiện là bẫy**. Làm
video "SpaceX hạ cánh ở Christmas Island" thì đón đúng cơn sốt nhưng khán giả đến vì
SpaceX, xem xong đi mất, kênh ngách không lớn lên. Ván bài đúng là **bắc cầu**: dùng
sự kiện làm cửa vào, trả lời bằng tò mò bền (cua, chi phí sống, đảo có giàu không).

> Sự kiện mua **lượt hiển thị**. Câu hỏi bền mua **thời lượng xem và người đăng ký**.
> Video outlier là video mua được cả hai bằng một lần bấm.

Đó chính là bản chất Mapping mà Owner nói ở mục 2b, viết thành công thức.

---

## 4. Phản biện hai đề xuất của Owner

Owner yêu cầu phản biện, nên tôi phản biện cả những điểm Owner đưa ra.

### 4.1 "Xuất report đưa thẳng vào Outline Extract, LLM gợi ý chèn thêm vào đâu"

**Mạnh:** rẻ, đã xây xong, không đụng kiến trúc. `report_cum.py` cố ý xuất Markdown
"để đưa cho AI đọc" — quyết định đó đúng.

**Yếu — và yếu ở chỗ chí mạng:** nó là **miếng vá trên một bộ xương vốn đã trung
bình**. Nếu ĐỀ đã tầm thường thì chèn một sự kiện nóng vào chương 6 không biến video
thành outlier; nó tạo ra một video trung bình có một chương thú vị.

Nặng hơn: LLM đọc report rồi chọn chỗ chèn **không có cách nào biết hệ quả giữ
chân**. Nó rất dễ đặt vật liệu mới nhất vào phút 14 — nơi chỉ còn 20% người xem. Vật
liệu quý bị chôn ở chỗ không ai đến.

**Phán quyết:** hợp lệ như **giải pháp tạm**, sai như **đích đến**. Nhưng có một
phiên bản sắc hơn của chính ý này thì ĐÚNG:

> Đừng để report chọn chèn vào **chương 6**. Để report quyết định **hook và 90 giây
> đầu** — chỗ mà đề và phân phối được định đoạt.

Cùng một cơ chế, đổi điểm tác động, đổi hẳn giá trị.

### 4.2 "Ma trận Topic × Hook là chất liệu tốt"

**Mạnh:** đây là **cỗ máy duy nhất trong toàn hệ sinh ra được một đề chưa tồn tại**.
Mọi thứ khác trong hệ đều mô tả cái đã có. `cap_goi_y` là thứ gần nhất với sáng tạo
có căn cứ.

**Yếu — bẫy sống sót (survivorship).** Pool chứa video đã được theo dõi. Một ô trống
có thể nghĩa là "chưa ai làm", cũng có thể nghĩa là **"làm rồi và chết"**. Từ trong
pool không phân biệt được hai cái. Mã hiện tại dán nhãn "tổ hợp chưa kiểm chứng" —
trung thực, nhưng trung thực không làm quyết định an toàn hơn.

**Cách chữa, và nó rẻ:** với ô trống ứng viên, gọi **một** lượt tra thị trường
(`ngoai_youtube` với cụm ghép topic+hook) để phân biệt *chưa ai làm* với *làm rồi mà
phẳng*. Có sẵn cơ chế ngân sách quota (`NGAN_SACH_NONG` 5 cụm/ngày/pool). Một ô
trống đã kiểm chứng đáng giá gấp nhiều lần mười ô trống suy luận.

**Yếu thứ hai:** không phải ô trống nào cũng có nghĩa. Hook "rẻ nhất" × topic "tỷ
phú" trống vì nó vô lý. Cần cửa người — luật A3 vốn đã bắt buộc.

---

## 5. Kiến trúc quy nạp — ba tầng

Từ luật ở mục 2, kiến trúc tự suy ra. Không phải "nối hai app", mà là **tách một
quyết định đang bị nhập làm hai**.

### Tầng 1 — ĐỀ: *"làm gì, và vì sao là bây giờ"*

- **Chỉ** dùng dữ liệu NGOÀI pool: Trends, News, Wikipedia, YouTube market,
  câu hỏi thật (PAA), Reddit, ô trống ma trận.
- **Tuyệt đối không** dùng đồng thuận cluster — đó là quá khứ.
- Đầu ra: một **ĐỀ** = topic × hook × *vì sao là bây giờ* + **tập câu hỏi thật**.

### Tầng 2 — KHUNG: *"kể thế nào để giữ chân"*

- **Chỉ** dùng dữ liệu outlier: cluster, coverage, peaks, heatmap, beats.
- Đây là chỗ trung bình hoá người thắng **là đúng** — chuyển giao nghề.
- Đầu ra: xương sống chương + vị trí payoff.

### Tầng 3 — CHỮ

- Hồ sơ giọng. Độc lập với hai tầng trên.

### Luật nối hai tầng — phần quan trọng nhất

> **Câu hỏi ở Tầng 1 trở thành CỘT SỐNG của chương ở Tầng 2. Cluster ở Tầng 2 chỉ
> được dùng làm CÁCH KỂ cho câu hỏi đó — không bao giờ được là LÝ DO TỒN TẠI của
> chương.**

Đảo chiều so với hiện nay: bây giờ cluster đẻ ra chương, còn câu hỏi (nếu có) chỉ là
trang trí. Sau khi đảo, câu hỏi đẻ ra chương, cluster cho biết kể nó thế nào.

**Chỗ hạ cánh đã có sẵn:** `compose_outline` đang nhận `questions: {tên: câu hỏi
nguyên văn}`, `misconception`, và `promise/vai: {tên: tra_hua|payoff}`. Đường ống cho
outline-dẫn-bằng-câu-hỏi **đã tồn tại trong mã**, chỉ chưa ai đổ dữ liệu vào.

### Christmas Island chạy qua ba tầng

| | |
|---|---|
| **Tầng 1** | Sự kiện: SpaceX hạ cánh → cửa sổ đang mở (News + Trends). Câu hỏi thật: cua, chi phí sống, đảo có giàu không (PAA + Trends related). **ĐỀ:** *"Hòn đảo SpaceX vừa hạ cánh — nơi 50 triệu con cua làm chủ"* — sự kiện làm cửa vào, tò mò bền làm nội dung. |
| **Tầng 2** | Pool LIFE IN cho biết: 15 phút về một hòn đảo giữ chân được thì mở bằng con số sốc, chương 2 phải là đời sống thường ngày, payoff đặt quanh phút 7. |
| **Kết quả** | **Đề mới, khung đã kiểm chứng.** Đó là công thức của outlier — không phải đề cũ khung cũ, cũng không phải đề mới khung tự chế. |

---

## 6. Điều gì chứng minh mô hình này SAI

Một chiến lược không nêu được cách bác bỏ nó thì là niềm tin, không phải chiến lược.

Mô hình trên đứng trên một giả định: **outlier thắng nhờ ĐI SỚM vào một đề**. Nếu
giả định đó sai — nếu outlier trong chính pool của mình phần lớn là video **đi sau**
trên một chủ đề đã đông mà vẫn nổ — thì đòn bẩy không nằm ở đề, mà nằm ở **bao bì và
nghề**. Khi đó:

- Kiến trúc ba tầng là thừa.
- Và **mục 4.1 của Owner (chèn report vào outline) mới là hướng đúng**, vì lúc đó
  Mapping chỉ nên đổ vào title/hook/packaging.

Điều này **đo được, bằng dữ liệu đang có, không tốn quota**: với các video outlier
trong pool, đối chiếu `pub_ts` của chúng với đường cầu của chính cụm đó theo thời
gian (`mapping.tu_khoa_noi` / `tra_cuu.xu_huong_pool` đã dựng mật độ cụm theo tháng
từ `pub_ts`). Câu hỏi: **outlier nằm ở sườn lên, ở đỉnh, hay ở sườn xuống của cụm?**

Đây là ngã ba quyết định toàn bộ phần còn lại, và nó rẻ.

---

## 7. Hành động

### Đợt 0 — THÍ NGHIỆM QUYẾT ĐỊNH *(0 quota, 0 token, ~1 ngày)*

*"Outlier của chính mình là đi sớm hay đi sau?"* — thiết kế chi tiết ở §8.

- **Đi sớm thắng** → tầng ĐỀ là đòn bẩy chính → làm kiến trúc ba tầng (Đợt 1→3).
- **Đi sau vẫn thắng** → nghề/bao bì là đòn bẩy → bỏ kiến trúc ba tầng, dồn Mapping
  vào title/hook, và làm mục 4.1 theo bản sắc hơn.

**Không xây gì thêm trước khi có kết quả này.** Đây đúng là chỗ bản 1 đã sai: xây
trước, chứng minh sau.

### Đợt 1 — MÀN CHỌN ĐỀ *(nếu Đợt 0 nghiêng về "đi sớm")*

Một màn **đứng trước** Outline Extract: ăn `report_cum` + `cap_goi_y` + tín hiệu
ngoài pool, người chọn một ĐỀ và một tập câu hỏi. Kết quả là đầu vào của run OE.
Đổi thứ tự thao tác, không đổi bộ máy OE.

### Đợt 2 — CÂU HỎI THÀNH CỘT SỐNG CHƯƠNG

Đổ tập câu hỏi của Tầng 1 vào `picks.questions` sẵn có. Cluster tụt xuống vai trò
"cách kể". Đây là đợt hiện thực hoá luật nối ở mục 5.

### Đợt 3 — MA TRẬN CÓ MẪU SỐ

Ô trống ứng viên được kiểm chứng bằng một lượt tra thị trường trước khi hiện ra như
cơ hội. Gỡ bẫy sống sót ở mục 4.2.

### Việc vận hành, không cần code

Chọn video nguồn cho OE **từ chính pool** — đo thật 23/08: 73/149 video nguồn của 50
run đã nằm sẵn trong pool RadarY (49%), trùng chính xác theo `yt_id`. Thói quen này
đẩy tỷ lệ nối lên gần 100% mà không tốn dòng code nào.

---

## Phụ lục — những gì đã có sẵn (đo 23/08/2026)

| | |
|---|---|
| RadarY | 21 pool · 32.751 video · 803 kênh; `pub_ts`, `duration_s`, chuỗi `ticks` |
| Ngoài pool | `tra_cuu.py`: Google Trends (12 tháng + related), Google News, Wikipedia pageviews 13 tháng, YouTube search ngoài pool, Reddit, câu hỏi thật |
| Report | `report_cum.py`: Markdown khối A (trong pool) / B (YouTube market) / C (ngoài nền tảng) + mục **"Ranh giới dữ liệu — báo cáo KHÔNG trả lời được"** |
| Ma trận | `mapping.py`: `cap_no` (cặp đã nổ, có video ví dụ) · `cap_goi_y` (ô trống, dán nhãn chưa kiểm chứng) |
| OE | 50 run · 149 video nguồn; cluster có `coverage_k/n`, `questions`, `peak_score`, `role`, `pos` |
| Đường ống sẵn | `compose_outline` đã nhận `questions`, `misconception`, `promise/vai` — chưa ai đổ dữ liệu vào |

## Trạng thái

**Chưa code.** Chờ Owner chốt: chạy Đợt 0 trước, hay bỏ qua thí nghiệm và đi thẳng
vào một hướng.

---

## 8. Thiết kế thí nghiệm Đợt 0

### 8.1 Giả thuyết, và nhóm đối chứng có thật

- **H1:** outlier thắng nhờ vào sớm trên đường cầu của một cụm.
- **H0:** thời điểm của outlier không khác video thường trên cùng cụm — đòn bẩy nằm
  ở bao bì/nghề.

Điều đầu tiên có thể giết thí nghiệm là *pool chỉ chứa video đã nổi thì không có
nhóm đối chứng*. **Đã kiểm trước, và pool có đối chứng thật** (đo 23/08):

| Pool | n | view/ngày p10 | trung vị | p90 | p90/trung vị |
|---|---|---|---|---|---|
| LIFE IN — US | 3.630 | 1 | 17 | 635 | **36,4×** |
| SPACE — US | 6.981 | 5 | 134 | 4.172 | 31,0× |
| TRAVEL DOCUMENTARY — US | 2.063 | 10 | 130 | 3.389 | 26,1× |
| LIFE IN — Spain | 2.338 | 3 | 81 | 1.496 | 18,5× |
| STORM | 357 | 42 | 192 | 1.035 | 5,4× |

12 pool có ≥300 video kèm `pub_ts` và view. Pool đầy video thường và video chết —
đúng thứ cần để so.

### 8.2 Định nghĩa (chốt trước khi chạy)

- **Outlier** = view/ngày ≥ phân vị 90 **của chính pool đó**. Dùng lại đúng định
  nghĩa `tu_khoa_nong` đang dùng — không đẻ định nghĩa thứ hai.
- **Cụm của một video** = n-gram 1–3 từ rút từ tiêu đề bằng `_ngram_nong`, giữ cụm
  có ≥ 12 video trong pool (dưới ngưỡng thì đường cong là nhiễu).
- **Vị trí trên đường** `vi_tri` ∈ [0,1] = tỷ lệ video của cụm đó đăng **trước** nó.
  0 = người đầu tiên, 1 = người cuối.

### 8.3 Hai chặng — và vì sao phải có chặng B

**Chặng A — đường CUNG (0 quota, toàn bộ 12 pool).** Định vị outlier trên đường mật
độ video theo tháng (`xu_huong_pool` đã dựng sẵn từ `pub_ts`).

> **Bẫy chí mạng của chặng A: nhân quả ngược.** Một video nổ sẽ *sinh ra* người bắt
> chước, nên nó nằm đầu đường cong **vì nó tạo ra đường cong**, chứ không phải vì
> "vào sớm thì thắng". Chặng A một mình **không chứng minh được H1**.

**Phép phân biệt trong chính chặng A:** xem outlier nằm ở đâu.

| Outlier tụ ở | Đọc là |
|---|---|
| Đúng `vi_tri = 0` (luôn là video đầu tiên) | **Nhân quả ngược** — người thắng đẻ ra sóng. Không kết luận được. |
| Khoảng 0,05–0,30 (vào sớm nhưng không phải đầu tiên) | **Ủng hộ H1** — cưỡi lên con sóng mình không tạo ra. |
| Rải đều như video thường | **Ủng hộ H0** |

**Chặng B — đường CẦU (Trends, ~30 cụm, chỉ chạy nếu chặng A chưa đủ kết luận).**
Định vị video trên đường **cầu** của Google Trends thay vì đường **cung** của pool.
Cầu do bên ngoài quyết định, video không tạo ra nó — nên đây mới là phép thử thật.
`tra_cuu.google_trends` đã có; ~17s/từ khoá, chạy một lần rồi lưu.

### 8.4 Nhiễu phải khống chế

| Nhiễu | Xử lý |
|---|---|
| **Tuổi video** | Dùng view/ngày, và so trong cùng dải tuổi |
| **Kênh lớn thắng bất kể thời điểm** | Báo kết quả **tách theo cỡ kênh**; hiệu ứng chỉ tính là thật nếu còn sống ở nhóm kênh nhỏ |
| **Cụm to vs cụm nhỏ** | Chuẩn hoá theo tỷ lệ, không theo số đếm; loại cụm < 12 video |
| **Chuỗi `ticks` bắt đầu từ lúc theo dõi, không từ lúc đăng** | view/ngày là *trung bình cả đời*, không phải vận tốc tức thời. Đủ để xếp hạng, không đủ để nói về đường tăng trưởng — ghi rõ là ranh giới. |

### 8.5 Quy tắc quyết định — ĐĂNG KÝ TRƯỚC

Viết ra **trước khi chạy**, để không tự hợp lý hoá bất cứ kết quả nào (bài học ngưỡng
`burstiness_cv` 21/08: ngưỡng nghe hợp lý mà không đo nhóm đối chứng thì sai).

1. Trung vị `vi_tri` của outlier **≤ 0,25**, hiệu ứng còn sống ở nhóm kênh nhỏ, và
   **không** tụ ở đúng 0 → **H1** → làm kiến trúc ba tầng (Đợt 1→3).
2. Phân phối `vi_tri` của outlier ≈ của video thường (kiểm định trên toàn mẫu) →
   **H0** → bỏ kiến trúc ba tầng; dồn Mapping vào title/hook và làm mục 4.1 của Owner
   theo bản sắc hơn.
3. Outlier tụ ở đúng `vi_tri = 0` → **chưa kết luận** → bắt buộc chạy chặng B trước
   khi quyết.

### 8.6 Tự kiểm phép đo

Trước khi tin kết quả, phép đo phải dựng lại được một sự thật đã biết: video thuộc
cụm bị `phan_loai_quyet_dinh` gắn nhãn **"nguội"** phải cho view/ngày thấp bất kể
`vi_tri`. Không dựng lại được thì phép đo hỏng, kết quả vứt.

### 8.7 Đầu ra

Một file `docs/do-som-hay-muon.md`: bảng phân phối `vi_tri` theo pool và theo cỡ
kênh, biểu đồ chữ, kết luận theo đúng một trong ba nhánh §8.5, và mục **"phép đo này
không trả lời được gì"**.

**Không sửa một dòng mã sản phẩm nào trong Đợt 0.**
