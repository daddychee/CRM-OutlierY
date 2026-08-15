# Phương pháp luận phân tích số liệu — Module Chẩn đoán AI Agent

> Tài liệu này ghi lại **tư duy phân tích** (không phải spec code) cho việc nâng cấp
> logic module chẩn đoán số liệu YouTube. Nó là **la bàn**: phiên sau viết luật cụ thể
> phải bám vào đây để không đi lạc. Chốt ngày 20/07/2026 qua phiên bàn với vai một
> data analyst 20 năm kinh nghiệm mảng YouTube.
>
> Nguyên tắc tối cao của cả tài liệu: **"Luật chồng luật là mồ chôn của phân tích."**
> Mỗi luật phải trả lời được câu hỏi *"biết điều này rồi thì tôi làm gì khác đi?"* —
> luật nào không đổi được một quyết định sản xuất hoặc kinh doanh thì loại bỏ.

---

## 1. Vấn đề gốc: đang khai thác 6/63 cột

Report YouTube Studio thật có **63 cột** nhưng engine hiện chỉ dùng khoảng 6-7 cột dễ
nhìn nhất: CTR, retention, tăng trưởng. Đây đều là những chỉ số mà màn hình Studio đã
tự bôi đỏ-xanh cho người dùng thấy. Một engine tự xây không nên tồn tại chỉ để lặp lại
điều Studio đã nói.

Giá trị thật của một hệ chẩn đoán tự xây nằm ở hai việc mà mắt thường và màn hình
Studio không làm được:

- **Nối các cột lại với nhau** để lộ ra quan hệ mà từng cột đơn lẻ không cho thấy.
- **Biến số liệu thành quyết định** sản xuất và kinh doanh, chứ không dừng ở việc mô
  tả triệu chứng.

---

## 2. Bốn tầng phân tích — hiện chỉ đang ở tầng thấp nhất

Engine hiện phân tích ở **tầng video đơn lẻ** ("video này bệnh gì"). Đó là tầng thấp
nhất trong bốn tầng, và ba tầng trên đang bỏ trống:

1. **Chẩn đoán video** — "video X vỡ retention". Hữu ích nhưng chỉ chữa cháy từng cái.
2. **Chẩn đoán danh mục (portfolio)** — "trong toàn bộ video, cái gì thực sự nuôi kênh,
   cái gì đang ăn hại công suất sản xuất?". Đây là phân tích Studio không cung cấp.
3. **Chẩn đoán công thức** — "làm video kiểu nào, độ dài nào, đăng lúc nào thì luôn
   thắng?". Nơi biến may rủi thành chiến lược lặp lại được.
4. **Chẩn đoán kinh tế sản xuất** — "mỗi format đang lãi hay lỗ? Nên nhân bản cái gì,
   khai tử cái gì?".

---

## 3. Bốn nhóm phân tích và chín mục con

> Mỗi mục con dưới đây ghi: nội dung phương pháp, **dữ liệu cần**, và **[Trạng thái]**
> triển khai thực tế (đối soát 20/07/2026). Trạng thái chi tiết + kế hoạch ở mục 10-11.

### A. Nhóm DANH MỤC — "kênh thực sự sống bằng gì"

**A1. Định luật tập trung (Pareto / concentration).** Tính tỷ lệ "top 1 video / tổng"
và "top 3 / tổng". Ví dụ thật: kênh 10.431 engaged views nhưng 1 video đã 6.937 = ~66%
dồn vào một video. Nếu trên 60% lượt xem dồn vào một video, kênh **chưa có mô hình bền
vững** — đang phụ thuộc vào một cú trúng. Đây là quyết định chiến lược, không phải chỉ
số phù phiếm: hoặc nhân bản đúng công thức của cú trúng đó, hoặc chủ động chấp nhận rủi
ro. *Dữ liệu: Views/Engaged views mỗi video.* **[ĐẦY ĐỦ — tổng quan danh mục trong
chan_doan_toan_bo.]**

**A2. Đường cong tuổi thọ video (velocity theo tuổi).** Ghép Video publish time + Chart
data theo ngày để biết một video thường "chín" trong bao nhiêu ngày rồi cạn view. Trả
lời câu hỏi sản xuất: nên đăng dồn hay đăng rải, bao lâu thì một video ngừng sinh view
để biết khi nào cần video mới. Studio không tính cái này. *Dữ liệu: Video publish time +
Chart data (view theo ngày mỗi video).* **[CHƯA ĐỤNG — mới có nhóm tuổi cho baseline,
chưa có đường cong. Đợt 3.]**

**A3. Cấu trúc khán giả (New / Returning / Casual / Regular) — kênh đang XÂY hay đang
ĐỐT lượt xem.** Năm cột cấu trúc khán giả: New / Returning / Casual / Regular / Unique.
Một kênh mà mỗi video toàn người xem mới (vd 4993 new / 340 returning) nghĩa là **đang
mua vui cho người lạ rồi họ đi mất — không tích lũy tài sản**. Kênh bền vững cần tỷ lệ
khán giả quay lại tăng dần. Đây là chỉ số "kênh có đang trở thành thương hiệu không" —
phân tích chiến lược nhất trong report. *Dữ liệu: 5 cột khán giả.* **[NỬA VỜI —
returning_ratio cấp video có; chưa có kết luận chiến lược cấp kênh. Đợt 2.]**

### B. Nhóm CÔNG THỨC — "cái gì lặp lại được"

**B1. Độ dài video vs hiệu quả.** Nhóm video theo khoảng độ dài (dưới 8ph / 8-15 / trên
15) rồi so retention, watchtime, RPM trung bình mỗi nhóm. Kết quả là một luật sản xuất
cụ thể: "kênh này ăn nhất ở độ dài X phút" — thứ đổi trực tiếp cách viết kịch bản.
*Dữ liệu: Duration.* **[NỬA VỜI → ĐẦY ĐỦ sau khối Winning Format. Đợt 1.]**

**B2. Thời điểm đăng.** Từ Video publish time (có cả thứ trong tuần) đối chiếu hiệu quả
để tìm khung ngày/thứ đăng cho khởi đầu tốt nhất. Ra quyết định lịch sản xuất. **LƯU Ý:**
report thường chỉ có NGÀY, không có GIỜ — nếu không có giờ thì KHÔNG suggest khung giờ
(van chống bịa). *Dữ liệu: Video publish time.* **[CHƯA ĐỤNG → nằm trong khối Winning
Format. Đợt 1.]**

**B3. Lưới chẩn đoán CTR × Retention × AVD (ma trận bệnh).** Đây **không phải luật thêm**
mà là cách **tổ chức lại** toàn bộ chẩn đoán video (chi tiết kiến trúc ở mục 5). Ở tầng
kênh: vẽ ma trận 2×2 CTR cao/thấp × Retention cao/thấp, đếm mỗi ô có bao nhiêu video →
biết **BỆNH PHỔ BIẾN NHẤT của kênh**, nên dồn sức chữa gì. *Dữ liệu: CTR + Retention mỗi
video.* **[NỬA VỜI — trục Nội dung phân biệt bệnh cấp video qua khóa `benh`; chưa đếm
cấp kênh thành ma trận 2×2. Đợt 2.]**

### C. Nhóm TIỀN — "kiếm được gì thật"

**C1. Bản đồ đơn vị kinh tế (RPM/CPM theo format).** Tính doanh thu trên mỗi 1000 view
theo từng nhóm chủ đề/format. Phát hiện then chốt: video ít view nhưng RPM cao có thể
**lãi hơn** video triệu view RPM bèo. Điều này **đảo ngược ưu tiên sản xuất** — sản xuất
theo lợi nhuận, không theo view phù phiếm. *Dữ liệu: RPM, CPM, Estimated revenue, Ad
impressions, Estimated monetized playbacks.* **[NỬA VỜI — chấm RPM cấp video; chưa có
bản đồ RPM theo nhóm format. HOÃN nếu kênh chưa monetize. Đợt 2.]**

**C2. Rò rỉ chuyển đổi trong phễu tiền.** Phễu: impressions → CTR → views → monetized
playbacks → ad impressions → revenue. Mỗi mũi tên là một tỷ lệ chuyển đổi. Tìm mắt xích
rò rỉ nhất trong phễu tiền, không chỉ phễu view. Vd monetized_playbacks/views thấp bất
thường → vấn đề monetization chứ không phải nội dung. *Dữ liệu: cụm cột phễu tiền.*
**[ĐẦY ĐỦ — trục Tiền tính các tỷ lệ chuyển đổi.]**

**C3. Đòn bẩy tăng trưởng bị bỏ trống.** Cards, End screen, Playlist — đây là các đòn
bẩy **chủ động điều khiển được** (khác retention phải sửa nội dung). End screen CTR thấp
hoặc bằng 0 là **tiền để trên bàn**: chỉ cần thêm end screen là kéo người xem sang video
khác, tăng session watchtime — thứ thuật toán thưởng. *Dữ liệu: Cards/Endscreen/Playlist.*
**[ĐẦY ĐỦ — trục Tiền cờ endscreen/card CTR = 0.]**

### D. Nhóm NỀN THỐNG KÊ

Ngưỡng theo cỡ mẫu, baseline động, và so sánh theo thời gian. Chi tiết ở mục 4 và 6 vì
đây là các quyết định kiến trúc nền. **[ĐẦY ĐỦ — baseline 3 lớp + ngưỡng mẫu động; so
sánh thời gian chờ 2 report kỳ rời.]**

---

## 4. Baseline ba lớp

Mọi phân tích so sánh đều cần một điểm neo. Dùng **ba baseline**, mỗi cái phục vụ một
mục đích khác nhau:

- **Baseline theo NHÓM ĐỘ DÀI** → đánh giá **chất lượng format**. So một video với các
  video cùng khoảng độ dài mới công bằng.
- **Baseline theo NHÓM TUỔI video** → đánh giá **độ tăng trưởng**. Video mới đang được
  thuật toán thử đẩy; video cũ sống bằng đuôi dài — không thể so trực tiếp.
- **Baseline TOÀN KÊNH** → đánh giá **chiến lược tổng thể**.

Baseline luôn dùng **trung vị (median)**, không dùng trung bình, để bền với outlier.

**Nguyên tắc lùi (fallback):** baseline càng cắt nhỏ thì mẫu mỗi nhóm càng ít. Khi một
nhóm dưới ngưỡng cỡ mẫu tối thiểu, median của nhóm đó **không đáng tin để làm baseline**.
Lúc đó engine tự động **lùi về baseline lớp trên** (ví dụ nhóm độ dài thiếu mẫu thì dùng
baseline toàn kênh) và **khai báo rõ đang dùng baseline nào**. Đây không phải phức tạp
hóa — đây là thành thật về độ tin cậy, đúng tinh thần van chống bịa.

---

## 5. Quyết định kiến trúc trung tâm: chấm bốn trục song song → một phán quyết

Đây là quyết định quan trọng nhất, đổi bản chất engine từ **"máy dò triệu chứng"**
(báo từng luật rời rạc) thành **"máy ra phán quyết"**.

**Cơ chế:** mỗi video có một **thẻ điểm**. Bốn trục — Danh mục, Công thức, CTR-Retention-
AVD, Tiền — mỗi trục chấm độc lập và cho ra một trạng thái (đạt ✓ / cảnh báo ⚠ / hỏng ✗
/ chưa đủ dữ liệu). Một tầng tổng hợp đọc bốn trạng thái đó rồi kết luận thành **một
trong khoảng sáu phán quyết hành động hữu hạn**: nhân bản, giữ, sửa bao bì, sửa nội
dung, đổi ngách vì tiền, hoặc bỏ.

**Bốn trục vào, một trong sáu phán quyết ra** — chính đây là cơ chế chống "cỗ máy đẻ
luật". Số phán quyết cuối cùng phải ít và mỗi phán quyết neo vào một hành động cụ thể.

Ví dụ một phán quyết đúng kiểu analyst: *"Bao bì tốt (CTR ✓), giữ chân tốt (Retention ✓),
session ngon (AVD ✓), nhưng RPM đáy → đây là video giỏi kéo view rẻ tiền, đừng nhân bản
format này cho mục tiêu doanh thu."* Kết luận này chỉ có được khi bốn trục chấm song song
rồi tổng hợp.

### Trục CTR × Retention × AVD — và cái bẫy đếm trùng

Thêm AVD (thời gian xem trung bình) vào lưới là **đúng**, vì YouTube đề cao phân phối
cho kênh có session time tốt. Nhưng có một bẫy kỹ thuật phải xử lý:

**Retention và AVD không độc lập**, chúng liên hệ qua độ dài: `AVD ≈ Retention × Duration`.
Một video 8 phút giữ chân 50% và một video 20 phút giữ chân 20% có thể **cùng AVD 4 phút**.
Nếu ném cả ba vào lưới như ba trục ngang hàng lặp lại nhau, sẽ **đếm trùng bằng chứng** —
cùng một bệnh bị kết tội gấp đôi lúc tổng hợp.

Cách xử lý là **tách vai câu hỏi** để mỗi trục có tiếng nói riêng:

- **Retention** hỏi: *"video có giữ chân tốt so với độ dài của chính nó không?"* — đây
  là chất lượng nội dung thuần.
- **AVD** giữ **hai vai**:
  - *"session time có đủ tốt để YouTube đẩy không?"* (so với baseline AVD của kênh).
  - *"video này nên dài hơn hay ngắn lại?"* — câu hỏi mà Retention không trả lời được.
    Ví dụ: video 6 phút giữ chân 55% (retention xuất sắc) nhưng AVD chỉ 3 phút 18 giây →
    nội dung tốt nhưng **đang bỏ session time trên bàn**, chủ đề này chịu được video 12
    phút nên hãy làm dài hơn. Ngược lại video 20 phút AVD 9 phút nhưng retention 30% →
    session ngon nhưng lê thê, hãy cắt bớt.

Khi Retention và AVD **mâu thuẫn nhau, đó là thông tin có ý nghĩa, không phải nhiễu**.
Vì AVD giữ cả hai vai, tầng tổng hợp **bắt buộc phải có cơ chế chống đếm trùng** khi gộp
điểm AVD với điểm Retention (đây là việc của phiên viết spec).

---

## 6. Thứ tự xây khác thứ tự phán quyết

Một phân biệt quan trọng để không hiểu lầm vai trò bốn nhóm:

- **Khi ra quyết định**, bốn nhóm **ngang hàng** và cùng có quyền phủ quyết. CTR, Retention,
  AVD đẹp mà RPM thấp thì vẫn là một quyết định sản xuất **sai** — vì đích cuối cùng là
  doanh thu và tăng trưởng, không nhóm nào được quyền bỏ qua nhóm khác.
- **Khi viết code**, nhóm thống kê vẫn phải chạy trước về mặt kỹ thuật — **không phải vì
  nó quan trọng hơn**, mà vì ba nhóm kia gọi hàm của nó. RPM-theo-format cần biết "format"
  là gì (phân nhóm) và cần biết nhóm đó có đủ mẫu để tin không (ngưỡng). Danh mục cần
  baseline để nói "video này dưới chuẩn". Đây là quan hệ **phụ thuộc hàm**, không phải
  thứ bậc quan trọng.

Ví von: trong một hội đồng bốn người ngang quyền, vẫn phải có người bật đèn phòng họp
trước — việc bật đèn không khiến người đó quyền cao hơn.

---

## 7. Chiều thời gian: khai thác được, nhưng cẩn thận cửa sổ trượt

Report có thể xuất theo các mốc chuẩn (7 / 28 / 90 / 365 ngày / lifetime) và Custom. Nghĩa
là phân tích theo thời gian **làm được ngay** bằng cách xuất nhiều kỳ, không cần chờ tích
lũy snapshot.

**Bẫy phải nhớ:** "Last 28 days" là **cửa sổ trượt**, không phải kỳ cố định. Hai lần xuất
28-ngày cách nhau một tuần **chồng lấn 21 ngày** — không phải hai kỳ độc lập để trừ nhau.
So sánh ngây thơ sẽ báo **tăng trưởng ảo**.

**Luật:** so sánh theo thời gian chỉ chạy trên **hai kỳ cùng độ dài, không chồng lấn**
(tháng này vs tháng trước, hoặc dùng Custom range rời nhau). Chính khả năng Custom là thứ
làm cho phân tích thời gian trở nên đúng đắn.

Lưu ý thêm: cửa sổ thời gian cũng **định nghĩa lại "tuổi video"**. Trong report 28 ngày,
một video đăng 3 ngày trước và một video đăng 300 ngày trước đều xuất hiện nhưng con số
của chúng mang ý nghĩa khác hẳn — đó là lý do baseline theo nhóm tuổi tồn tại.

---

## 8. Nguyên tắc lọc mẫu nhỏ — van chống bịa cho số liệu

Đây là lỗi thống kê kinh điển cần chặn: **ngưỡng cứng trên mẫu nhỏ**. Video 1.131 view
báo retention 13% thì có ý nghĩa; video 30 view báo retention 13% thì **vô nghĩa vì mẫu
quá nhỏ**.

**Luật nền của toàn engine:** một video chưa đạt lượng view tối thiểu thì engine **không
kết luận** về retention/CTR của nó — chỉ xếp vào trạng thái "chưa đủ dữ liệu". Ngưỡng nên
**động** (theo phần trăm median view của kênh) chứ không cứng, vì kênh sẽ lớn lên và
ngưỡng cứng sẽ lỗi thời. Đây chính là tinh thần "van chống bịa" đã dựng cho module hỏi-đáp,
áp cho số liệu: **thà nói "chưa đủ dữ liệu để kết luận" còn hơn kết luận sai.**

---

## 9. Việc tiếp theo

Tài liệu này chốt **phương pháp**. Phiên sau sẽ viết **spec luật và công thức cụ thể**
đúng khuôn `diagnosis_rules.csv` để Claude Code triển khai. Giữ đúng phân vai: phần bàn
phương pháp và soạn spec làm ở phiên Cowork; phần gõ code làm trong VSCode bằng Claude Code.

---

# 10. Trạng thái triển khai 9 phương pháp (đối soát 20/07/2026)

Đánh giá dựa trên các khối yêu cầu đã gửi Claude Code + kết quả đã chạy xanh. Chia 3 mức:
ĐẦY ĐỦ / NỬA VỜI (mới cấp video, thiếu tổng hợp cấp kênh) / CHƯA ĐỤNG.

- A1 Pareto — **ĐẦY ĐỦ.** Trong chan_doan_toan_bo, tổng quan danh mục (top1/top3 % view).
- A2 Tuổi thọ velocity — **CHƯA ĐỤNG.** Mới có tuoi_video_ngay + nhóm tuổi cho baseline;
  CHƯA tính đường cong "video chín/chết trong bao nhiêu ngày" từ Chart data theo ngày.
- A3 New/Returning — **NỬA VỜI.** returning_ratio ở trục Danh mục cấp video; CHƯA có kết
  luận chiến lược cấp kênh "đang xây hay đốt người lạ".
- B4 Độ dài vs hiệu quả — **NỬA VỜI → ĐẦY ĐỦ sau khối Winning Format** (đang chờ chạy).
- B5 Thời điểm đăng — **CHƯA ĐỤNG → nằm trong khối Winning Format** (đang chờ chạy).
- B6 Ma trận CTR×Retention 2×2 — **NỬA VỜI.** Trục Nội dung phân biệt bệnh cấp video (khóa
  benh); CHƯA đếm cấp kênh thành ma trận 2×2 để biết bệnh phổ biến nhất của kênh.
- C7 RPM theo format — **NỬA VỜI.** Trục Tiền chấm RPM từng video; CHƯA có bản đồ RPM trung
  bình theo nhóm format. (Kênh chưa monetize thì hoãn.)
- C8 Rò rỉ phễu tiền — **ĐẦY ĐỦ** (trục Tiền tính monetized_playbacks/views, revenue/views).
- C9 Đòn bẩy bỏ trống — **ĐẦY ĐỦ** (trục Tiền cờ endscreen/card CTR = 0 → tiền để trên bàn).

**Tổng: 3 đầy đủ (A1, C8, C9), 4 nửa vời (A3, B4, B6, C7), 2 chưa đụng (A2, B5).**
Điểm yếu chung: engine giỏi CHẤM TỪNG VIDEO nhưng yếu ở tầng RÚT RA KẾT LUẬN CHIẾN LƯỢC CẤP
KÊNH. Winning Format + các khối tổng-hợp-cấp-kênh dưới đây lấp phần này.

---

# 11. Kế hoạch thứ tự triển khai phần còn thiếu

Nguyên tắc xếp thứ tự: (a) cái nào dùng lại hạ tầng đã có thì làm trước (rẻ); (b) cái nào
đổi được quyết định sản xuất mạnh nhất ưu tiên; (c) cái phụ thuộc dữ liệu chưa có (giờ đăng,
monetize) hoãn tự nhiên.

**Đợt 1 — Winning Format (ĐANG CHỜ CHẠY).** Gộp B4 (độ dài) + B5 (thứ/giờ đăng) + kiểu tiêu
đề. Một khối "Công thức thắng của kênh" nổi bật. Mỗi chiều kèm SỐ MẪU + van chống bịa (thiếu
mẫu → "chưa đủ dữ liệu", không suggest trên may rủi). Đây là khối giá trị cao nhất, làm trước.

**Đợt 2 — Tổng hợp cấp kênh còn thiếu (3 mảnh, dùng lại dữ liệu đã có, rẻ):**
- A3 New/Returning cấp kênh: 1 khối kết luận "kênh đang XÂY hay ĐỐT" (tỷ lệ returning TB kênh
  + xu hướng). Nổi bật cạnh Pareto.
- B6 Ma trận CTR×Retention 2×2: đếm video mỗi ô (dùng lại khóa benh đã có) → "bệnh phổ biến
  nhất của kênh là X, có N video". Cho biết nên dồn sức chữa gì.
- C7 RPM theo format: bản đồ RPM TB theo nhóm độ dài (HOÃN nếu kênh chưa monetize — tự bỏ qua).

**Đợt 3 — Velocity (A2), nặng hơn vì cần ghép Chart data theo ngày:**
- Đường cong tuổi thọ: mỗi video chín trong bao nhiêu ngày, cạn lúc nào → nhịp đăng. Cần
  parse Chart data (view theo ngày mỗi video), khớp với publish time. Làm sau vì phức tạp hơn
  và cần report có Chart data đủ dài.

**Phụ thuộc dữ liệu (hoãn tự nhiên):** khung giờ đăng (B5) cần report có GIỜ — phần lớn report
chỉ có ngày. RPM theo format (C7) cần kênh đã monetize. Cả hai: engine báo trung thực "dữ liệu
không có" thay vì bịa.

**Nguyên tắc xuyên suốt (nhắc lại):** mọi tổng hợp cấp kênh phải KÈM SỐ MẪU và chỉ kết luận
khi đủ tin cậy. Winning format / bệnh phổ biến / nhịp đăng trên mẫu nhỏ = bịa. Thà nói "chưa
đủ video để kết luận" — đúng tinh thần van chống bịa cho số liệu.

---

# 12. Đợt nâng cấp — 08/08/2026 (đối chiếu với một bản phân tích ngoài trên kênh Outland)

Nguồn gốc đợt này: user đưa CÙNG một report YouTube Studio (kênh Outland, 28 video) qua hai
đường — (1) module chẩn đoán của app (engine luật + GLM diễn giải), (2) một phiên phân tích
ngoài đọc thẳng dữ liệu thô. Bản (2) tìm ra 5 phát hiện có số liệu cụ thể (tương quan độ dài↔
APV = −0,48, xu hướng retention giảm dần theo tháng, hai cụm chủ đề tiêu đề chênh nhau gần
gấp đôi APV...) mà bản (1) không thấy được. Đối chiếu code lộ ra: KHÔNG PHẢI vì model GLM
yếu hơn — engine hiện tại đơn giản là chưa TÍNH những con số đó, và LLM diễn giải bị cấm suy
diễn ngoài luật đã khớp (đúng van chống bịa mục 8, không sửa). Vá đúng chỗ là bổ sung phép
tính vào engine (Python, xác định, không phụ thuộc model) rồi mới đưa số mới vào đề bài diễn
giải — giữ nguyên kiến trúc "máy tính, LLM chỉ diễn giải" của mục 5.

### 12.1. Baseline "Từng video" đang so sai nhóm — nối vào mục 4

**Vấn đề:** mục 4 đã định nghĩa baseline ba lớp và nguyên tắc lùi, `chon_baseline()` đã viết
đúng cơ chế đó cho bốn trục (mục 5). Nhưng đường "chẩn đoán 1 video" cũ (20 luật gốc, vẫn là
đường chạy khi bấm Analyze từng video) chấm luật bằng baseline **toàn kênh phẳng**, không
dùng `chon_baseline()`. Ví dụ thật trên Outland: video 33 phút và video 15 phút bị so cùng
một retention trung vị gộp, trong khi tương quan độ dài↔APV đo được là −0,48 — nghĩa là video
càng dài retention % càng thấp một cách **hệ thống**, không phải vì video đó tệ.

**Vì sao phải sửa:** đúng câu hỏi tối cao mở đầu tài liệu — "biết điều này rồi thì tôi làm gì
khác đi?" — nếu chẩn đoán chỉ ra sai baseline, hành động sửa cũng sai chỗ (vd bị khuyên "sửa
nội dung mở đầu" trong khi con số chỉ đang phản ánh việc video dài hơn mặt bằng, không phải
video kém hơn).

**Phương pháp:** đổi `chan_doan_video()` dùng `chon_baseline(..., muc_dich="format")` (đã có
sẵn, đã dùng ở mục 5) thay cho gán cứng nhánh `toan_kenh`. Giữ nguyên nguyên tắc lùi của mục
4: nhóm độ dài đủ mẫu → dùng nhóm; thiếu mẫu → lùi về toàn kênh, và **khai báo rõ nguồn
baseline** trong kết quả để phần diễn giải nói đúng "so với các video cùng độ dài" thay vì
mập mờ "so với kênh". Không đổi bộ 20 luật, không đổi ngưỡng — chỉ đổi baseline nào được đưa
vào chấm.

### 12.2. Tương quan liên tục — bổ sung nhóm B (Công thức)

**Vấn đề:** mọi phép so sánh ở mục 3 hiện làm bằng NHÓM RỜI RẠC (bucket ngắn/vừa/dài, mới/
đang chạy/đuôi dài) rồi so trung vị — không có phép đo nào cho biết quan hệ giữa hai biến
mạnh tới đâu theo một dải liên tục. Bản đối chiếu ngoài tính được ba tương quan có thể đổi
quyết định sản xuất ngay: độ dài↔APV = −0,48, độ dài↔AVD tuyệt đối = −0,25 (dài hơn không chỉ
giữ % thấp hơn mà giữ ÍT PHÚT hơn), CTR↔APV = −0,30 (tiêu đề càng "ăn khách" theo nghĩa CTR
càng cao thì giữ chân càng tệ — bao bì đang hút sai khán giả). Bucket rời rạc dễ bỏ lỡ các
tương quan này khi mẫu mỗi ô mỏng.

**Vì sao phải thêm:** đây là phần đúng tinh thần "nối các cột lại với nhau" mà mục 1 đặt làm
giá trị cốt lõi của một engine tự xây — Studio không tính tương quan chéo cột, và bucket hiện
tại tuy đúng hướng nhưng thô hơn cần thiết khi mẫu không lớn.

**Phương pháp:** thêm một hàm thuần Python (pandas `.corr()`, không cần thư viện mới) tính hệ
số tương quan Pearson giữa các cặp biến đã có sẵn trong bảng video — chỉ tính khi đủ mẫu
(đúng mục 8, dưới ngưỡng thì bỏ qua cặp đó, không suy diễn từ vài điểm). Gắn vào tầng "tổng
quan danh mục" đã có, đưa THẲNG con số (không diễn giải trước) vào đề bài LLM — giữ đúng
ranh giới mục 5: máy tính, LLM chỉ đọc số đã có.

### 12.3. Xu hướng theo tháng đăng — mở rộng mục 7 (Chiều thời gian)

**Vấn đề:** mục 7 đã đặt nền cho phân tích theo thời gian nhưng dừng ở mức "so hai kỳ rời
nhau, không chồng lấn" — chưa có phép đo xu hướng LIÊN TỤC qua nhiều tháng. Bản đối chiếu
ngoài phát hiện trên Outland: retention trung vị giảm dần theo tháng đăng (T6 25,4% → T7
20,1% → T8 17,4%) đúng lúc độ dài trung vị tăng dần (28' → 29' → 33') — một xu hướng suy
thoái âm thầm mà chẩn đoán từng video hay từng kỳ đơn lẻ không nhìn thấy vì chỉ xét một lát
cắt tại một thời điểm.

**Vì sao phải thêm:** đúng nguyên tắc mục 7 đã nêu — report xuất được theo nhiều mốc nên phân
tích thời gian "làm được ngay", chỉ là chưa có ai dùng nó để dò xu hướng nhiều điểm liên tiếp
thay vì so 2 kỳ.

**Phương pháp:** nhóm video theo tháng của ngày chạy/ngày đăng (cột đã có sẵn từ tầng nền
thống kê, mục 3-D), tính trung vị mỗi tháng cho các biến chính (retention, độ dài, RPM). CHỈ
kết luận "đang tăng/giảm/ổn định" khi có từ ba tháng trở lên VÀ mỗi tháng đủ mẫu tối thiểu —
đúng mục 8, không suy diễn xu hướng từ một, hai điểm dữ liệu.

### 12.4. Từ khóa tiêu đề: theo đúng biến, gộp đúng nghĩa — nối vào B1 (Winning Format)

**Vấn đề:** khối từ khóa của Winning Format (đã ĐẦY ĐỦ theo mục 10) hiện so từ khóa theo
LƯỢT XEM và so khớp CHỮ. Bản đối chiếu ngoài chỉ ra hai giới hạn: (1) một cụm chủ đề nhiều
view nhưng retention/RPM tệ không phải "công thức thắng" thật sự — cần so theo đúng biến mục
tiêu, không chỉ view; (2) hai cụm chủ đề tiêu đề của Outland không chung một từ nào nhưng
cùng một Ý ("secrets"/"bizarre"/"godless" đều gợi tò mò-niềm tin sai lệch) lại tách biệt hẳn
về hiệu quả — APV 27-45% so với cụm "beautiful + cheap" chỉ 13-22%, chênh gần gấp đôi. So
khớp chữ đơn thuần không gộp được hai nhóm này lại để thấy khác biệt.

**Vì sao phải sửa:** khớp đúng nguyên tắc tối cao — biết ĐÚNG chủ đề nào thắng (không chỉ
đúng lượt xem) mới quyết được nên nhân bản chủ đề gì; nếu chỉ theo view sẽ nhân bản nhầm
"công thức câu view rẻ" thay vì công thức vừa giữ chân vừa ra tiền.

**Tự phản biện trước khi chốt phương pháp (09/08/2026):** bản nháp đầu có 4 chỗ yếu — (1)
"cờ mâu thuẫn view-cao/retention-thấp" nếu suy từ "không lọt danh sách nổi bật ở biến kia"
là suy diễn quá tay (vắng mặt ≠ ngược hướng thật), đúng loại lỗi mục 8 cấm; (2) chạy 3 lượt
dò từ khóa (view/retention/rpm) trên mẫu vốn đã mỏng (kênh vài chục video) không hiệu chỉnh
multiple-comparison → tăng cờ dương giả; (3) "đã monetize" đang được tính trong `cham_truc_tien`
từ `bl3` — `goi_y_winning_format(df_map)` không nhận `bl3`, nên "tái dùng nhãn `chua_monetize`"
kéo theo đổi chữ ký + call site, không phải việc lẻ trong `_wf_tu_khoa`; tự chế lại phép kiểm
"đã monetize" riêng ở đây sẽ tạo hai nơi định nghĩa khác nhau — đúng họ bug đồng bộ hai kho
từng gặp (Qdrant/catalog), giờ tái diễn ở tầng logic; (4) chưa chốt việc thêm biến có phá
hợp đồng `_wf()` phẳng `{trang_thai, noi_dung, so_video, ghi_chu}` hay không — nếu lồng cấu
trúc sẽ chạm UI. Kết luận: tách thành 3 bước độc lập, chỉ đi bước sau khi bước trước đã kiểm
bằng report thật và pass.

**Phương pháp — 3 bước, kiểm data thật rồi mới sang bước sau:**

- **Bước 1 (đã code, xem log 09/08/2026 dưới mục 10):** tổng quát hoá biến chia nhóm
  thắng/thua — thay vì hard-code `views`, tách logic đếm-từ-nổi-bật ra hàm riêng
  `_tu_khoa_theo_bien(df_map, gia_tri, cot_tieu_de)`, gọi độc lập cho `views` và `retention`
  (mỗi biến áp đúng `MIN_DONG_NHOM` của chính nó). Gộp kết quả vào MỘT chuỗi `noi_dung` —
  giữ nguyên hợp đồng phẳng của `_wf()`, không đụng UI. CHƯA có RPM, CHƯA có cờ mâu thuẫn.
- **Bước 2 (đã code 09/08/2026 — bước 1 chứng minh có ích trên report thật, xem log dưới mục
  10):** thêm RPM. Phát hiện khi trích logic "đã monetize": `cham_truc_tien` kiểm trên `bl3`
  (baseline đã tính), còn `rpm_theo_format` (đã có sẵn từ trước, cùng file) kiểm trực tiếp
  trên `so.columns` — hai cách khác nhau nhưng CÙNG NGHĨA, và `goi_y_winning_format` chỉ có
  `so`/`df_map` chứ không có `bl3` nên đúng bản để tái dùng là bản của `rpm_theo_format`. Trích
  thành `_da_monetize(so)` — MỘT hàm dùng chung cho cả `rpm_theo_format` (sửa lại gọi hàm này)
  và `_wf_tu_khoa` (mới), tránh hai nơi định nghĩa "đã monetize" lệch nhau. Kênh chưa monetize
  → RPM không tính, không hiện "chưa đủ dữ liệu" (đúng như tự phản biện đã chốt).
- **Bước 3 (đã code 09/08/2026 — user hỏi thẳng "có logic nào để tránh bias không?" trước khi
  duyệt, xem log dưới mục 10):** cờ mâu thuẫn — soát lại thêm 3 nguồn bias trước khi code
  (ngoài lỗi "vắng mặt ≠ ngược hướng" đã bắt ở bản tự phản biện đầu): (i) không kiểm soát được
  biến gây nhiễu (độ dài/tuổi video) vì thiết kế thuần đếm-từ, không hồi quy đa biến — khắc
  bằng NGÔN NGỮ: output luôn viết "đi cùng", cấm viết "vì...nên"; (ii) CHỈ báo một chiều tiêu
  cực là tự thiên vị loại insight nói ra — khắc bằng làm ĐỐI XỨNG hai cờ: `⚠ canh_bao` (từ nổi
  bật ở view-cao MÀ CŨNG nổi bật ở retention-thấp — khả năng câu view rẻ) và `💡 co_hoi` (từ
  nổi bật ở retention-cao MÀ CŨNG nổi bật ở view-thấp — giữ chân tốt nhưng độ phủ thấp, đáng
  thử đổi tiêu đề); (iii) nhóm đối chứng nhỏ dễ nhiễu — hạn chế kế thừa từ `_wf_tu_khoa` gốc,
  không có sửa mới, chỉ nhắc lại. Cách tính: `_tu_khoa_theo_bien` thêm tham số `nguong_dem`
  (mặc định 2) + đổi trả về DANH SÁCH ĐẦY ĐỦ (không cắt top-4 nữa — cắt ở tầng hiển thị) để
  hàm mới `_tu_mau_thuan` dùng lại đúng logic đếm, chỉ đảo dấu biến B (`-bien_b`) để lật nhóm
  thắng/thua rồi soát các từ ĐÃ nổi bật ở biến A có lọt nhóm thấp của B không — đòi
  `NGUONG_DEM_MAU_THUAN = 3` (không phải 2) vì đây là tuyên bố mạnh hơn "nổi bật" thường, và
  KHÔNG quét lại toàn bộ từ vựng (chỉ soát tối đa 4 từ đã hiển thị) nên không phải một vòng
  multiple-testing mới. Khi có cờ, `ghi_chu` luôn kèm dòng nhắc "chưa loại trừ do độ dài/tuổi
  video khác nhau — không phải kết luận nhân quả".
- **(b) Bảng nhóm-nghĩa (đã code 09/08/2026 — user chốt "soạn nốt" thay vì để trống chờ tự
  soạn):** `rules/tu_khoa_nhom_nghia.csv` (khuôn `content_type_profiles.csv`, cột
  `tu,nhom_nghia`, đọc qua `pd.read_csv(..., comment="#")` nên comment giới hạn ở đầu file
  không vỡ parse). Nạp bằng `_tai_nhom_nghia(path=...)` — CÙNG khuôn dependency-injection với
  `doc_content_profile(path=...)` (`tests/test_loai_kenh.py`): rỗng/không tồn tại → `{}` →
  hành vi y hệt bước 1 (an toàn tuyệt đối). Gắn vào ĐÚNG một chỗ trong `_tu_khoa_theo_bien`
  (bước đếm từ, `t = nhom_nghia.get(t, t)`) nên phủ cả bước 1/2/3 và `_tu_mau_thuan` mà không
  sửa logic đếm/ngưỡng ở nơi khác; `_wf_tu_khoa` nạp bảng MỘT LẦN rồi truyền xuống (tránh đọc
  file lặp 5 lần/report). Nội dung khởi tạo LẤY THẲNG từ ví dụ trong tài liệu này (mục mở đầu
  §12.4): "secrets/secret/bizarre/godless/vault" → "tò mò / niềm tin sai lệch",
  "beautiful/cheap" → "thẩm mỹ giá rẻ"; cộng thêm "1970s"/"70s" → "thập niên 70" (không phải
  suy diễn đồng nghĩa — hai cách viết CÙNG một mốc thời gian, gộp an toàn tuyệt đối). GHI RÕ
  giới hạn ngay comment đầu file: gộp TOÀN CỤC, không phân biệt loại kênh (vd "cheap" hợp kênh
  làm đẹp nhưng lệch nghĩa ở kênh tài chính) — không tự động kiểm được, tự cân nhắc khi thêm
  dòng theo đúng ngách của kênh đang chẩn đoán. Kiểm trên report Outland thật: "vault" và
  "1970s" trong danh sách nổi bật gộp đúng về tên nhóm, "beautiful"/"cheap" tổng hợp qua test
  end-to-end riêng (đi qua `goi_y_winning_format` không truyền tham số, đúng đường công khai).
  **Bẫy phát hiện khi nối dây:** vài test cũ của bước 1-3 dùng chữ "secret"/"vault" làm tiêu đề
  mẫu — trùng khớp với chính bảng nhóm-nghĩa vừa soạn nên bị gộp ngoài ý muốn, làm rớt assert
  cũ; đổi toàn bộ dữ liệu mẫu các test đó sang "mystic castle" (không trùng bảng thật) để test
  không phụ thuộc ngầm vào nội dung file luật production.

### 12.5. Thứ tự triển khai đề xuất

`12.1` độc lập, rẻ nhất, tái dùng `chon_baseline()` có sẵn → làm trước. `12.2` và `12.3` dùng
chung một kiểu hạ tầng tính toán (thống kê thuần trên bảng video đã có) và cùng nạp vào đề
bài diễn giải (mục 5) — làm chung một đợt. `12.4` tách thành 3 bước nhỏ + bảng nhóm-nghĩa (b),
từng bước kiểm report thật trước khi sang bước kế — **ĐÃ XONG CẢ 4 phần (09/08/2026)**, xem
log dưới mục 10. Không việc nào trong đợt này đổi mô hình LLM hay phá van chống bịa — tất cả
là mở rộng phần TÍNH TOÁN xác định, đúng ranh giới mục 5 đã chốt.
