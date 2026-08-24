# Tuvalu — Chapter 1: bản đã xử lý + báo cáo

Chạy ngày 21/08/2026 bằng logic 6 tầng trong [kich-ban-studio.md](kich-ban-studio.md).
Mọi con số dưới đây là **đo thật bằng script**, không ước lượng.

---

## 1. Kết quả một dòng

| | Bản gốc | Bản mới | Thay đổi |
|---|---|---|---|
| **Điểm mác AI** | **77,6 — CAO** | **11,5 — THẤP** | **−66,1** |
| Số hit luật | 29 | 1 | −28 |
| Em-dash `—` | 12 | 1 (tiêu đề, cố ý giữ) | −11 |
| Câu > 25 từ | 6 | 1 | −5 |
| Độ dài câu TB | 19,3 từ | 11,3 từ | −41% |
| Số câu | 30 | 46 | +16 (giải nén) |
| Burstiness CV | 0,5231 | 0,5782 | +0,055 (nhịp bớt đều) |
| Độ dài | 3.344 ký tự | 2.950 ký tự | 88,2% (trong ngưỡng) |
| Số liệu bịa thêm | — | **0** | ✅ |
| Bảng bất biến | 12 mục | **12/12 còn nguyên** | ✅ |

**4/4 van kiểm chứng ĐẠT** → bản mới được nhận. (Không đạt van nào thì hệ giữ nguyên
bản gốc, không trả bản hỏng.)

---

## 2. BẢN KỊCH BẢN SAU XỬ LÝ

Chapter 1 — A STRIP OF SAND IN THE MIDDLE OF THE OCEAN

Tuvalu covers about 26 square kilometers of land. That is smaller than the footprint of many international airports. Berlin could swallow the entire country more than ten times over and still have room to spare.

Average elevation across the islands: roughly 2 meters above sea level. In most places you are standing barely above the tide line. The highest ground in the country is a spot on the tiny island of Niulakita, and it reaches about 4.6 meters. That's it. No mountain. No hill. Nowhere to climb. When the sea rises, there is nowhere higher to go.

That land comes in nine islands: six atolls and three reef islands, scattered across hundreds of kilometers of open water. They took millions of years to build, and the building was slow theater.

Undersea volcanoes pushed up from the ocean floor. Coral reefs grew in living rings around their slopes, laying down calcium skeleton layer by layer in the warm shallows. Then the volcanoes began to sink. Slowly. Inevitably. Until only the coral rings were left, hovering at the surface like the outline of mountains that no longer exist.

Picture a volcano drowning in slow motion while its coral necklace stays afloat. That is the shape of Tuvalu.

Every grain of sand underfoot is broken-down coral, not rock. That is why the soil stays thin and poor. It grows coconut, breadfruit, pandanus, and pulaka. Little else will take root here at all.

Now flip the picture. The land is minuscule. The ocean Tuvalu governs covers nearly 900,000 square kilometers, a stretch of Pacific larger than France and Germany combined.

So this is not really a tiny island nation. It is one of the most water-dominant territories on Earth, far more sea than land. On a map it is almost invisible, a scattering of dots you could miss entirely. Beneath the surface, it is enormous.

The difference between an atoll and a reef island decides how you live. An atoll encloses a lagoon: calm, shallow water sheltered from the open ocean, where fish gather and children learn to swim. The three reef islands have no lagoon at all. They sit on bare reef platforms and face the open sea on every side. Live on one of those three, and the Pacific reaches you first, with nothing in between.

Which brings us to the contradiction underneath everything you are about to see. The process that gave Tuvalu its beauty, the coral, the lagoons, the low bright rings of sand, is the same process that makes it the most vulnerable nation on the planet. The thing that built this country is the thing that will drown it. Every part of this story grows out of that one fact.

On this narrow strip of borrowed coral, an entire culture took root anyway. Before we look at that culture up close, I'm curious where in the world you are watching this from right now. Drop your country in the comments below. I want to see how far this little chain of islands is reaching tonight.

---

## 3. Đã làm những gì

### T0 — Quét ký tự ẩn (Layer A)

Chạy `inspect_text.py` của watermarks-remover: **0 ký tự ẩn** ở cả hai bản
(không ZWSP, không NBSP, không bidi, không tag char).

Nghĩa là: bản anh gửi **không mang watermark dạng ký tự ẩn** — văn bản đi qua chat đã
bị chuẩn hóa, hoặc nguồn vốn không nhúng. Toàn bộ dấu vết AI của kịch bản này nằm ở
**văn phong**, không nằm ở byte ẩn. Đó là lý do phần việc thật nằm ở T1–T3.

### T1 — Chẩn đoán: 29 hit trên 20 luật

Bộ luật để **ngoài code** (`rules_mac_ai.csv`, 20 dòng) — anh thêm cụm mới bằng Excel,
không cần sửa Python.

| Nhóm | Số hit | Cụ thể |
|---|---|---|
| Dấu câu | 12 | em-dash `—` chèn giữa câu |
| Cụm sáo narrator | 11 | *To put that in context · here's where · here is the paradox · sits at the heart of · You'll notice that · which means that · Keep that in mind · more than you might think · by almost any measure · quite literally · the very same · reads like · almost nothing else* |
| Chuyển ý kiểu máy | 2 | *And yet,* mở đoạn · *But here's* mở đoạn |
| Cấu trúc | 2 | *Not just X — Y* · tricolon so sánh 3 vế |

### T2 — Biên tập có mục tiêu

Chỉ sửa **đúng 29 chỗ máy chỉ ra**, cộng giải nén câu dài. Không xáo từ ở chỗ lành —
so từng câu sẽ thấy phần lớn từ vựng gốc còn nguyên.

Năm ví dụ tiêu biểu:

| # | Gốc | Mới | Lý do |
|---|---|---|---|
| 1 | "**To put that in context**, you could fit the entire country inside Berlin's city limits more than ten times over." | "Berlin could swallow the entire country more than ten times over and still have room to spare." | Bỏ câu dẫn; đổi sang thể chủ động, hình ảnh mạnh hơn |
| 2 | "...roughly 2 meters above sea level, **which means that** in most places you're standing barely above the tide line itself." | "...roughly 2 meters above sea level. In most places you are standing barely above the tide line." | Tách câu 27 từ thành 2; bỏ mệnh đề lồng |
| 3 | "There is no mountain, no hill, no high ground to retreat to. When the sea rises, there is **quite literally** nowhere higher to go." | "No mountain. No hill. Nowhere to climb. When the sea rises, there is nowhere higher to go." | Ba câu cụt = nhịp người viết; bỏ trạng từ nhấn thừa |
| 4 | "Then the volcanoes began to sink **—** slowly, inevitably **—** until only the coral rings remained..." | "Then the volcanoes began to sink. Slowly. Inevitably. Until only the coral rings were left..." | Em-dash → câu cụt: cùng hiệu ứng nhấn, không còn vân tay |
| 5 | "**And here is the paradox that sits at the heart of** everything you're about to see: **the very same** process..." | "Which brings us to the contradiction underneath everything you are about to see. The process..." | Gỡ 3 cụm sáo chồng nhau trong một câu |

Câu dài nhất của bản gốc (46 từ, đoạn "And here is the paradox…") được tách thành 3 câu.

### T3 — Bốn van kiểm chứng (chạy bằng code, không phải cảm tính)

| Van | Ngưỡng | Đo được | Kết quả |
|---|---|---|---|
| 1. Độ dài | 0,85 – 1,15 | **0,882** | ✅ Không cắt cụt |
| 2. Bất biến nguyên văn | 12/12 mục | **12/12** | ✅ |
| 3. Không bịa số | 0 số mới | **0** | ✅ |
| 4. Có tiến bộ | điểm giảm + CV tăng | **−66,1 · +0,055** | ✅ |

**Bảng bất biến đã giữ đủ:** `26` · `2 meters` · `4.6 meters` · `900,000` · `1` (Chapter 1)
· Tuvalu · Berlin · Niulakita · Pacific · France · Germany · Earth.
Cùng với: nine islands, six atolls, three reef islands, coconut/breadfruit/pandanus/pulaka,
và **CTA cuối bài giữ nguyên** ("Drop your country in the comments below").

### T5 — Quét ký tự ẩn lần hai

Bản mới: **0 ký tự ẩn**. (Bước này bắt lỗi model sinh lại NBSP/em-dash sau khi viết —
lần này sạch.)

---

## 4. Kiểm chéo bằng công cụ ngoài

Chạy `score_stylometry.py` của watermarks-remover trên cả hai bản:

| | Bản gốc | Bản mới |
|---|---|---|
| Score repo | 0,2125 — **CLEAN** | 0,1225 — **CLEAN** |

**Nó gọi bản gốc là "CLEAN"** trong khi bản đó có 12 em-dash và 17 cụm narrator AI.
Lý do: bộ luật của repo là regex tiếng Anh học thuật (*delve into*, *in conclusion*,
*a rich tapestry*), không có luật nào cho văn phong **narrator YouTube**. Nó thậm chí
báo một dương tính giả: khớp "in the world" vào mẫu "in today's fast-paced world".

Đây là bằng chứng thực nghiệm cho khuyến nghị hôm qua: **lấy Layer A của repo, bỏ phần
chấm điểm và bỏ Layer B, tự làm luật riêng theo giọng kênh mình.**

---

## 5. Giới hạn — nói trước để anh không hiểu nhầm

1. **Tôi là model biên tập trong lần chạy này.** Nếu kịch bản gốc do Claude sinh, thì
   nguyên tắc "model biên tập ≠ model nguồn" đã bị vi phạm — về lý thuyết có thể bị
   đóng dấu lại. Khi vào production phải gọi model khác (GLM/DeepSeek) qua API.
2. **Điểm 11,5 là điểm theo luật của mình**, không phải chứng nhận qua mặt detector nào.
   Không công cụ nào chứng minh được điều đó, và tôi không tuyên bố như vậy.
3. **20 luật là bản khởi đầu** viết từ chính kịch bản này. Chạy thêm 5–10 kịch bản nữa
   sẽ lòi ra các cụm quen tay khác của kênh — đó mới là bộ luật dùng được lâu dài.
4. **Bản mới ngắn hơn 12%.** Giải nén câu thì tổng chữ giảm là bình thường (bỏ mệnh đề
   nối, bỏ trạng từ thừa). Nếu anh cần giữ đúng thời lượng đọc, hạ ngưỡng van 1 xuống
   0,95–1,15, hệ sẽ ép model viết bù.
5. **Chưa có tầng T2b** (neo phương pháp luận từ kho tri thức) — lần chạy này thuần
   biên tập, chưa dùng tiêu chuẩn hook/retention nào của kênh anh.

---

## 6. Tệp liên quan

Script và dữ liệu của lần chạy này nằm ở thư mục tạm của phiên:
`scratchpad/tuvalu/` — gồm `goc.txt`, `moi.txt`, `cham_mac_ai.py`, `rules_mac_ai.csv`,
`ketqua.json`. Nói một tiếng là tôi chuyển vào repo thành module chính thức.
