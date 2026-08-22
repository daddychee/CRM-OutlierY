# DISCOVERY + MAPPING — sổ chủ đề (soạn 21/08/2026)

> Sổ mạch "cầu × cung": RadarY thu tín hiệu **CẦU** (người ta đang tìm gì) và ghép với
> kho **CUNG** sẵn có (ai đang làm gì) để chỉ ra khoảng trống thật.
> Nguồn gốc: user gửi `CONTENT-ULTIMATE-V3.md` (Discovery Module + S0 Opportunity Score)
> → phản biện + đo thật → **giữ Discovery, bỏ Opportunity Score**, và **đổi nhà: đặt ở
> RadarY chứ không phải Content Ultimate**.

---

## 0. Vì sao đặt ở RadarY (đổi so với đề xuất ban đầu)

Ban đầu định đặt Discovery trong Content Ultimate. Ba số đo thật ngày 21/08 làm đổi ý:

| Dữ kiện | Số |
|---|---|
| Video có title + ngày đăng trong `data/radary/radary.db` | **31.917** |
| Chuỗi view theo thời gian (`ticks`) | **989.775** |
| Kênh · workspace (ngách/pool) | 803 · 21 |
| Quét toàn bộ 31.917 title để đối chiếu 1 từ khóa | **0,21 giây · 0 quota** |

- Vế **cung** đã nằm ở RadarY. Đẩy vài chục từ khóa sang đó rẻ hơn kéo kho video đi.
- RadarY **có scheduler**; Content Ultimate không (chỉ chạy khi user bấm) → chỉ RadarY
  tích lũy được **lịch sử cầu theo thời gian** (velocity thật, không phải ảnh chụp).
- Người cần đọc bản đồ thị trường là **Kinh doanh**, không riêng người viết kịch bản.
- Content Ultimate vẫn dùng được qua `GET /api/mapping` — đúng chiều phụ thuộc: tool
  viết ĐỌC từ đài quan sát, không phải ngược lại.

---

## 1. Ba van chống bịa (quan trọng nhất của module này)

1. **KHÔNG có "search volume".** Autocomplete chỉ nói *có người gõ cụm này*, không nói
   bao nhiêu người. Google không công bố số. Mọi con số volume suy ra từ autocomplete
   đều là bịa → trục cầu chỉ dùng **tín hiệu đếm được**: cụm xuất hiện ở bao nhiêu biến
   thể seed (`do_phu`), hạng trung bình trong danh sách gợi ý (`hang_tb`), số bài HN.
2. **KHÔNG điểm tổng, KHÔNG ngưỡng cứng.** Chia 4 ô bằng **trung vị của chính phiên
   quét** (cầu/cung cao-thấp so với các từ khóa cùng đợt), không phải hằng số kiểu
   "≥ 7.0 là Green". Ngưỡng cứng không có căn cứ đã bị bác ở proposal V3 bản 1.
3. **Cung thấp có HAI nghĩa trái ngược.** `tuvalu` 14 video · view trung vị 781 (ít người
   làm vì ít người xem) vs `why do people…` 4 video · 2 kênh (chưa ai làm). Chỉ khi ghép
   với cầu mới phân biệt được — đó là lý do tồn tại của Mapping.

---

## 2. Nguồn tín hiệu CẦU — đã kiểm thật 21/08

| Nguồn | Kiểm từ máy công ty | Dùng thế nào |
|---|---|---|
| **YouTube autocomplete** `suggestqueries.google.com/complete/search?client=firefox&ds=yt&q=` | **200 OK**, không key. Seed rộng `"life in"` → 10 gợi ý; seed hẹp `"life in tuvalu"` → 1 | Nguồn CHÍNH. Bắt buộc seed **rộng** + biến thể a–z |
| **HN Algolia** `hn.algolia.com/api/v1/search` | **200 OK**, không key | Phụ — lệch tệp (dân công nghệ), chỉ tham khảo |
| **trendspyg** | có thật, **1.6.0 phát hành 19/08/2026**; `pytrends` bản cuối 04/2023 (chết) | Tuỳ chọn — thư viện mới 2 ngày tuổi, để sau MVP |
| **Reddit `.json`** không auth | **403 Blocked** | **BỎ khỏi MVP** |

Nhiễu đã thấy khi đo: seed `"life in"` trả về `life incremental roblox`, `life in prison
roblox` → phải lọc theo ngách/thị trường của workspace.

---

## 3. Dữ liệu — 2 bảng mới, không đụng bảng cũ

```sql
CREATE TABLE keywords (
  id INTEGER PRIMARY KEY,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
  cum TEXT NOT NULL,                  -- cụm từ khoá đã chuẩn hoá (lowercase, gọn khoảng trắng)
  seed TEXT DEFAULT '',               -- seed sinh ra nó
  nguon TEXT DEFAULT 'autocomplete',  -- autocomplete | hn | trends | tay
  tao_ts REAL NOT NULL,
  bo_qua INTEGER NOT NULL DEFAULT 0,  -- user gạt khỏi bản đồ (nhiễu) — gỡ mềm
  UNIQUE (workspace_id, cum));

CREATE TABLE keyword_stats (          -- append-only theo ngày, khuôn pool_stats/channel_stats
  keyword_id INTEGER NOT NULL REFERENCES keywords(id),
  ngay TEXT NOT NULL,                 -- YYYY-MM-DD giờ VN
  do_phu INTEGER NOT NULL DEFAULT 0,  -- xuất hiện ở bao nhiêu biến thể seed
  hang_tb REAL NOT NULL DEFAULT 0,    -- hạng trung bình trong danh sách gợi ý (1 = đầu)
  hn_bai INTEGER NOT NULL DEFAULT 0,
  hn_diem INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (keyword_id, ngay));
```

Giữ vĩnh viễn (như `pool_stats`) — chuỗi theo ngày chính là thứ Content Ultimate không
làm được, và là cơ sở để về sau nói "cụm này đang lên hay đang xuống".

---

## 4. Đo CUNG — đọc DB, 0 quota

Cho mỗi cụm, quét `videos` (31.917 dòng, 0,21s):

| Số | Cách tính | Ghi chú |
|---|---|---|
| `so_video` · `so_kenh` | đếm title khớp | khớp theo **ranh giới từ**, không phải `LIKE %x%` — bài học SEO 18/08: "Life" nuốt "Life In" |
| `view_trung_vi` | max(views) mỗi video từ `ticks`, lấy trung vị | trung vị bền outlier hơn trung bình |
| `moi_nhat` | `max(pub_ts)` | cụm chết từ 2 năm trước ≠ cụm đang nóng |
| `vph_trung_vi` | `last_vph` trung vị | velocity thật |

---

## 5. Ghép thành bản đồ

- Trục **cầu** = `do_phu` (chính) + hạng trung bình (phụ), so với **trung vị phiên quét**.
- Trục **cung** = `so_video`, so với **trung vị phiên quét**.
- 4 ô:

| Ô | Nghĩa | Ví dụ đo thật 21/08 |
|---|---|---|
| cầu cao · cung thấp | **KHOẢNG TRỐNG** — ưu tiên | `why do people…` 4 video · 2 kênh |
| cầu cao · cung cao | **ĐỎ LỬA** — phải hơn hẳn mới thắng | |
| cầu thấp · cung cao | **BÃO HOÀ** — tránh | `life in` 2.300 video · 118 kênh · view trung vị 2.867 |
| cầu thấp · cung thấp | **HOANG** — thường có lý do | `tuvalu` 14 video · view trung vị 781 |

Bấm một ô → danh sách video thật đang chiếm chỗ (kênh, view, ngày đăng, link) —
**trình bằng chứng, người chọn** (luật A3), không "khuyên nên làm gì".

---

## 6. Quyền

Theo `apps_registry` hiện hành của RadarY: **mọi bộ phận L1 xem** · **L3+ (leader)** chạy
quét và gạt nhiễu · quản trị vẫn chỉ Owner. Không đẻ luật quyền mới.

---

## 7. Nhịp thi công — mỗi bước một commit xanh

| # | Việc | Cổng nghiệm thu |
|---|---|---|
| **M1** | `radary/discovery.py` — expand seed → cụm (autocomplete + HN), thuần hàm | test với HTTP giả; chạy thật 1 seed ra ≥ 10 cụm |
| **M2** | 2 bảng + `db.keywords_*` | tạo/đọc/ghi idempotent, không đụng bảng cũ |
| **M3** | `radary/mapping.py` — đo cung + ghép 4 ô | chạy trên DB thật: `life in` ra bão hoà, `why do people` ra khoảng trống |
| **M4** | API `POST /api/workspaces/{ws}/discovery/scan` · `GET /api/workspaces/{ws}/mapping` | quyền đúng 3 vai; không có ws → 404 |
| **M5** | Tab **Mapping** trong `web/app.js` | 4 ô bấm ra video thật |
| **M6** | Job theo lịch (scheduler sẵn có) | rate-limit; log lời gọi |

**Rate-limit bắt buộc từ M1:** autocomplete dùng CHUNG IP với harvest của RadarY và với
`youtube-transcript-api` của Content Ultimate. App đã từng dính "Sign in to confirm you're
not a bot" trên VPS. Mặc định ≤ 1 lời gọi/giây, tổng ≤ 60/phiên quét.

---

## 8. Không làm (YAGNI)

Reddit (403) · trendspyg trong MVP · embedding cluster (dùng token overlap trước) ·
điểm tổng/ngưỡng cứng · tự động đưa cụm vào outline (user tick).

---

## 9. NGHIỆM THU THẬT 21/08/2026 — pool LIFE IN — US (3.246 video)

### Kết quả

| Lần quét | Lời gọi | Cụm | Thời gian |
|---|---|---|---|
| Hẹp (trần 12, không từ hỏi) | 12 | 110 | 11 s |
| Rộng (trần 40, có từ hỏi) | 36 | 332 | 35 s |

Đầu bảng sau lần quét rộng — **tín hiệu dùng được**:

| Cụm | Cầu | Video trong pool | View giữa | Ô |
|---|---|---|---|---|
| `life in rio` · `life in rural china` · `life in the countryside` · `life in adventure` | 2 | **0** | — | **Khoảng trống** |
| `life in vietnam` | 2 | **30** (26 kênh) | 4.732 | Đỏ lửa |
| `life in china` | 2 | 15 | 2.973 | Đỏ lửa |
| `life in new zealand` | 2 | 9 | 5.140 | Đỏ lửa |

### Ba bài học vận hành

1. **Trần quét quyết định chất lượng trục cầu.** Trần 12 → gần như mọi cụm `do_phu = 1`,
   trung vị = 1, phân ô vô nghĩa. Phải ≥ 27 lời gọi (seed + 26 chữ cái) thì `do_phu`
   mới phân hoá. Đây là lý do trần mặc định của nút trên UI đặt ở 20 và nên nâng khi
   quét nghiêm túc.

2. **`tu_hoi` chỉ hợp với seed là DANH TỪ chủ đề, không hợp với seed dạng mẫu câu.**
   Bật từ hỏi cho seed `life in` kéo về `can i cancel my life insurance`,
   `a life sent in xenoblade 3`, `can i create life in 1 hour`. Với seed `jupiter`
   thì `why jupiter…` lại đúng. UI để mặc định TẮT.

3. **Chỉ số "mới lạ" KHÔNG phải bộ lọc lạc đề.** Đã thử dùng vốn từ pool để dìm cụm
   lạc đề — dìm được `life incremental` (game) nhưng dìm luôn `life in rio`,
   `life in kiev`, `life in the countryside`: hợp ngách hoàn hảo, chỉ là pool chưa có
   video, tức đúng khoảng trống cần tìm. **Máy không phân biệt được "lạc đề" với
   "mới lạ"** — cả hai đều là từ chưa có trong pool. Giữ làm cột thông tin, lọc nhiễu
   là việc của người (nút ✕). Ghim bằng `test_tu_la_KHONG_duoc_dung_de_xep_hang`.

### Trạng thái

M1–M5 xong, đã chạy thật trên cổng 9111 (restart 21/08). **M6 (job theo lịch) chưa
làm** — nên bật sau khi dùng tay vài lần để biết mỗi ngách cần seed nào và trần bao nhiêu.


---

## 10. BẢN 2 — ĐỔI SANG "TRA CỨU MỘT TỪ KHOÁ" (user chốt 21/08, chiều)

Bản 1 (bản đồ 4 ô + hàng trăm cụm) **đã bỏ**. Phê bình của user: *"Mapping hiện tại chỉ
là duplicate của radary, không có gì gọi là discovery, không có gì để make decision"* —
đúng, và đo được: `do_phu = 1` ở 324/332 cụm (trục cầu là bit), còn vế cung chỉ đếm
trong pool nên `0 video` bị gán nhầm là "khoảng trống".

### Mô hình mới

Nhập **MỘT từ khoá** → hai khối, đều theo **thị trường của pool đang mở**:

| Khối | Nội dung | Chi phí |
|---|---|---|
| **A · Trong pool** | số video/kênh · % video và % view của pool · **xu hướng theo lứa đăng** (video ra mỗi tháng + view/ngày của lứa đó, 12–18 tháng) · velocity 46 ngày so với toàn pool · kênh đang đẩy · bài gần nhất | **0 quota**, < 1s |
| **B · Ngoài** | **Google Trends** interest 12 tháng + chiều lên/xuống + truy vấn đang lên · **YouTube video nổi 90 ngày** · **kênh nhỏ đang thắng** (< 50k subs mà lọt top view) | ~102 units + ~17s |

### Giới hạn dữ liệu (nói trước, không hứa quá)

`ticks` chỉ có **46 ngày** → không dựng được đường view lịch sử. Xu hướng khối A vì thế
dựng theo **lứa đăng**: video về từ khoá đăng tháng nào ăn bao nhiêu **view/ngày**
(view ÷ tuổi, bỏ video dưới 7 ngày vì chưa ổn định). `pub_ts` có từ 2009 nên nhìn được
12–24 tháng. Kèm velocity 46 ngày cho ngắn hạn — user chốt "cả hai".

### Nghiệm thu thật 21/08 — pool LIFE IN — US

`life in` : chiếm **59,3% số video và 68,2% view** của pool; lứa đăng bùng nổ từ tháng 6
(84 → 396 video/tháng, view/ngày trung vị 6 → 53); một kênh đẩy **215 video**.

`life in alaska` (0,3s + 18s, 102 units):

| | |
|---|---|
| Pool mình | 2 video · 1 kênh · **0% view pool** |
| Google Trends | **lên +65%** / 12 tháng |
| YouTube 90 ngày | view trung vị **726k** |
| Kênh nhỏ đang thắng | Highliner YTC **12.100 subs → 2,48M view** · Wildstay 36k · Nations Uncovered 13,8k |

### Thị trường — sửa sau khi user nhắc "không làm Việt Nam, chủ yếu Mỹ"

Máy chủ đặt tại Việt Nam nên autocomplete và YouTube API **mặc định xếp theo IP VN**.
Đo thật cùng seed: mặc định ra `life in africa`, ép `gl=us` ra `life in alaska`. Nay cả
ba tầng (seed / autocomplete / search) đều neo vào `market` của pool lấy từ ĐẾ; pool
chưa gắn thị trường thì **không đoán "US"** mà hiện banner cảnh báo.

**Lỗi dữ liệu trong đế (Owner nên sửa ở General › Niches):** `TT-US` khai ngôn ngữ
`"US"`, `TT-SPAIN` khai `"Spainish"`. Code chịu được bằng cách suy ngôn ngữ từ mã vùng.

### Dọn dữ liệu

Đã xoá 898 cụm + 898 dòng thống kê + 34 bản ghi thị trường của bản 1 (gồm các cụm tiếng
Việt quét nhầm). Backup trước khi xoá: `data/radary/radary-truoc-don-keywords-*.db`.
Schema 3 bảng giữ lại — `keyword_market` còn dùng làm cache đo thị trường.

---

## 11. BẢN 3 — bốn việc user nêu 21/08 (chiều muộn)

### 1. Từ khoá thị trường US lọt sang Spain

Không phải lỗi dữ liệu — **state UI không reset khi đổi pool**: tra ở US rồi chuyển
sang Spain thì kết quả cũ vẫn nằm nguyên trên màn hình. Nay `useEffect([ws])` xoá sạch
`A/B/cum`, và mỗi lời gọi ghi nhớ `ws` lúc bấm để bỏ kết quả về muộn sau khi đã đổi pool.

Kèm sửa gốc thứ hai: `hop_ngon_ngu` ban đầu chỉ phân biệt Việt / không-Việt nên title
**tiếng Anh vẫn lọt vào pool Spain**. Nay có `nhan_dien_ngon_ngu()` đếm từ chức năng
(en/es/vi). **Bẫy đã dính:** dải ký tự tiếng Việt ban đầu gồm cả `à á è é ì í ò ó ù ú ý`
nên `La vida en España — dónde vivir` bị nhận nhầm là tiếng Việt. Đã thu hẹp về ký tự
chỉ tiếng Việt mới có (`ă â đ ê ô ơ ư` + thanh hỏi/ngã/nặng).

### 2. Kênh và video phải click ra được

Mọi tên kênh giờ là link `youtube.com/channel/<id>`, mọi video là `youtu.be/<id>` — ở
cả khối A (kênh đang đẩy, bài gần nhất) lẫn khối B (video nổi, kênh nhỏ đang thắng, và
"bài tốt nhất" của từng kênh nhỏ). Cần thêm `kenh_yt` / `kenh_id` / `video_tot_nhat`
vào dữ liệu trả về.

### 3. Truy vấn đang lên phải diễn hoạ rõ ràng

- `DuongXuHuong` — đường interest 12 tháng có vùng tô + nhãn mốc thời gian (dùng chung
  cho Google Trends và Wikipedia).
- `ThanhTruyVan` — thanh ngang cho truy vấn đang lên (xanh) và truy vấn phổ biến (xanh
  dương), dài theo mức tăng; ≥5000% hiện chữ "bùng nổ" thay vì số vô nghĩa.

**Phát hiện khi làm:** Trends trả related **rỗng** với từ khoá hẹp (`life in alaska`).
Nên bổ sung khối **"biến thể người ta gõ"** từ autocomplete — luôn có dữ liệu, 0 quota,
~9 giây, và bấm vào là tra cứu luôn từ khoá đó. Đo thật: `life in alaska winter` (5
hướng gõ) · `life in fairbanks alaska` (3) · `life in alaska cabin` · `… documentary`.

### 4. Nguồn ngoài Google Trends — đã kiểm thật từ máy này

| Nguồn | Kết quả | Quyết định |
|---|---|---|
| **Google News RSS** | **200**, không key, ~1s | **Đã thêm** — báo chí đang nói gì về chủ đề |
| **Wikipedia pageviews** | **200**, không key, lịch sử theo tháng nhiều năm | **Đã thêm** — mức quan tâm thật, độc lập YouTube. Hiện kèm TÊN BÀI để người tự đánh giá bài có khớp chủ đề không |
| **YouTube autocomplete** | sẵn có | **Đã thêm** vào khối B (biến thể) |
| **Reddit** | `.json` **403**, `.rss` cũng **403** | Chỉ còn đường OAuth (PRAW) — cần Owner tạo app ở reddit.com/prefs/apps |
| **X / Twitter** | free tier không cho đọc search | Bản Basic ~100$/tháng — **không khuyến nghị** |

Ví dụ thật `life in alaska` (24s, 102 units): Trends **+65%** · Wikipedia bài
*Life Below Zero* **−46%** · 8 bài báo · YouTube 90 ngày view giữa **726k** · kênh
12.100 subs làm **2,48M view**.

---

## 12. TỪ KHOÁ ĐANG NỔI + bản đồ bong bóng (21/08, tối)

User hỏi: *"biểu đồ từ khoá đang nổi này có tracking realtime, xem mật độ từ khoá nào
đang lên đang giảm — làm được không?"* → **Được, và không phải chờ tích luỹ**: `pub_ts`
của video trong pool có từ 2009 nên mật độ mỗi cụm theo tháng dựng được ngay; pool lại
được scheduler quét liên tục nên số tự cập nhật mỗi vòng quét ("realtime" theo nhịp pool).

Đo **hai chiều** để không nhầm *nhiều người làm* với *đang ăn*:

| Chiều | Cách đo |
|---|---|
| **Lượng** | số video mới dùng cụm trong 30 ngày qua, so với 30 ngày liền trước |
| **Chất** | view/ngày trung vị của video 90 ngày gần đây dùng cụm đó |

Đo thật pool **LIFE IN — US** (3.254 video):

| Cụm | Xu hướng | Video 30n | View/ngày |
|---|---|---|---|
| `living in` | **↑ +316%** | 19 → 79 | **108** |
| `life in` | ↑ +61% | 314 → 504 | 48 |
| `real life in` | ↑ +41% | 196 → 276 | 43 |
| `documentary about` | **↓ −95%** | 20 → 1 | 12 |
| `15 mind` | **↓ −100%** | 6 → 0 | — |

Pool **SPACE — US**: `what happens` ↑+52% (view/ngày 117) · `james webb` ↑+32% ·
`what is` đi ngang nhưng view/ngày **170** — cụm ổn định ăn khách nhất.

### Bản đồ bong bóng (theo mẫu "beachhead map" user gửi)

X = số video trong pool (**thang log** — lệch hàng trăm lần) · Y = % thay đổi 30 ngày ·
cỡ bong bóng = số video mới 30 ngày · xanh lên / đỏ giảm. **Góc trên-trái = đang lên mà
còn ít người làm.** Bấm một bong bóng là tra cứu cụm đó.

**Ba lỗi hiển thị chỉ lộ khi chụp màn hình kiểm:** nhãn chồng nhau · nhãn bị cắt ở mép
phải · và nặng nhất: nhãn chỉ gắn cho 6 cụm ĐẦU nên **cụm đang giảm không bao giờ có
tên** — mất đúng nửa thông tin của bản đồ. Nay gắn nhãn cho 3 cụm lên mạnh nhất + 2 cụm
giảm mạnh nhất + cụm nhiều video nhất, nhãn tự tránh nhau và quay vào trong khi ở nửa phải.

### Cụm tiếng Việt vẫn lọt — vá

Pool **chưa gắn thị trường** thì đế không cho biết ngôn ngữ, nên trước đó không lọc gì:
pool gốc LIFE IN (102 video `vi` · 35 `en` · 2 `es`) ra cụm `sự thật`, `cuộc sống thực`.
Nay khối này có **dropdown chọn ngôn ngữ lọc** khi pool chưa gắn thị trường (chọn
English → `travel to`, `real life in`), **nhớ lựa chọn theo pool** qua localStorage, và
hiện luôn thành phần ngôn ngữ của pool để biết mình đang nhìn cái gì. Pool có thị trường
thì vẫn tự động theo đế, không hỏi.

### Điều kiện đủ mẫu — sửa sau khi đo

Ban đầu đòi **cả hai** kỳ ≥ 3 video mới tính %, nên cụm đang chết hẳn (`15 mind`: 6 → 0)
bị xếp "ít mẫu" — mất đúng tín hiệu giảm mạnh nhất. Nay chỉ cần **kỳ trước** đủ mẫu
(nó là mẫu số).

---

## 13. HAI LOẠI TỪ KHOÁ — mẫu câu và ĐỐI TƯỢNG (21/08, tối muộn)

User: *"thiếu các từ khoá về objective. Tôi không hiểu anh lấy từ khoá như thế nào"*.

### Cách lấy — nay ghi thẳng trên giao diện

Tất cả đếm trên **tiêu đề video trong chính pool**, 0 quota:

| Loại | Cách lấy |
|---|---|
| **Mẫu câu** | cụm 2–3 từ lặp lại nhiều nhất (`life in`, `travel documentary`, `beautiful women`) |
| **ĐỐI TƯỢNG** | từ đứng **ngay sau giới từ** (`in`/`to`/`of`…) và **≥75%** số lần xuất hiện là ở vị trí đó |

### Vì sao trước đó thiếu hẳn đối tượng

Tên nước/địa danh thường **một từ** (`Vietnam`, `Alaska`) nên không lọt vào n-gram 2–3 từ.
Thử nhận diện bằng "chữ viết hoa giữa câu" — **thất bại**, vì title YouTube viết Hoa Mọi
Từ (`Documentary`, `Travel`, `Women` đều viết hoa).

Cách chạy được: đối tượng gần như **luôn** đứng sau giới từ (`life IN vietnam`,
`travel TO norway`), còn tính từ mô tả thì không. Đo tỉ lệ để tách.
**Ngưỡng 0,5 chưa đủ** — `extremely` đạt 0,64 (vì `of extremely beautiful women` rất phổ
biến trong ngách này). Nâng lên **0,75** loại được nó mà vẫn giữ hết địa danh
(`vietnam` 1,00 · `sweden` 0,98 · `uzbekistan` 1,00), cộng bỏ trạng từ đuôi `-ly`.

### Kết quả — pool LIFE IN — US, 59 cụm = 30 đối tượng + 29 mẫu câu

| Đối tượng | Xu hướng | Video 30n | View/ngày |
|---|---|---|---|
| `tajikistan` | **↑ +280%** | 5 → 19 | **207** |
| `indonesia` | ↑ +267% | 6 → 22 | 64 |
| `colombia` | ↑ +250% | 4 → 14 | 91 |
| `laos` | ↑ +175% | 8 → 22 | 137 |
| `bhutan` | ↑ +100% | 5 → 10 | **198** |

Pool **Spain** ra `europa · áfrica · españa · letonia · irán · japón · francia ·
argentina · finlandia · suecia`. Pool **SPACE — US** ra ít đối tượng (`photon`,
`spaceflight`) — đúng bản chất: ngách khoa học không đặt tên theo địa danh, không ép.

Giao diện: nút lọc **Đối tượng / Mẫu câu / Tất cả** (mặc định **Đối tượng** — nó trả lời
"làm video về CÁI GÌ"), áp cho cả bản đồ bong bóng lẫn bảng.

---

## 14. Rà nguồn mới (21/08) — kiểm bốn, nhận một

User hỏi còn nguồn nào đưa vào được nữa. Kiểm thật từ máy này, **chỉ nhận cái có giá trị**:

| Nguồn | Kiểm | Giá trị cho ngách | Quyết định |
|---|---|---|---|
| **Bing / DuckDuckGo suggest** | 200, không key, ~0,3s | **Cao** — trả cụm YouTube autocomplete KHÔNG có: `during winter`, `anchorage alaska`, `alaska today`, `life expectancy in alaska` | **ĐÃ THÊM** |
| YouTube comments (`commentThreads`) | ✓ 1 unit/video | **Thấp** — 150 comment ở 5 video top chỉ ra 2 câu hỏi, đều lạc đề (*"didn't get served one ad"*). Khác ngách khoa học nơi khán giả hỏi nhiều | bỏ qua |
| Google Trends daily RSS | ✓ 1 giây, có số traffic | **Thấp** — trả tin tức chung của cả nước (`fidelity crypto`, `voting`, `tesla autopilot`), không thuộc ngách | bỏ qua |
| Wikipedia related pages | **403** | — | bỏ qua |
| Reddit (OAuth/PRAW) | cần Owner tạo app ở reddit.com/prefs/apps | chưa đo được | chờ, chỉ làm khi có credentials |

**Ghi nhớ khi đọc kết quả:** Bing là gợi ý của **tìm kiếm web**, không phải YouTube — dùng
để MỞ RỘNG ý tưởng, không thay tín hiệu YouTube. Giao diện phân biệt bằng màu (tím =
YouTube kèm số hướng gõ, nâu = Bing) và chỉ giữ cụm Bing **mới** so với danh sách YouTube.

### Bệnh cũ lộ lại: `database is locked`

Route tra cứu ghi cache + lịch sử; lúc scheduler của RadarY giữ khoá ghi SQLite thì lệnh
ghi nhận `database is locked` và cả request **500** — người dùng vừa chờ 20 giây, tiêu 102
units, rồi mất trắng kết quả chỉ vì không ghi nổi cache. Nay mọi đường ghi cache/lịch sử
đi qua `_ghi_bo_qua_khoa`: hỏng thì bỏ qua và **vẫn trả kết quả** (mất cache thì lần sau
hỏi lại, không mất gì khác).

### 22/08 — Từ khoá của pool này chui sang lịch sử pool khác

User báo: *"từ khoá ở thị trường nào thì giữ nguyên ở thị trường đó, không nhét chung"*.
Trong bảng lịch sử của **LIFE IN — US** có `áfrica` (đã tra ở **LIFE IN — Spain** 8 phút
trước), `life in vietnam`, `Faroe`… Soi `tra_cuu_log` ra dấu vết rất đặc trưng — cùng một
cụm nằm ở hai pool, bản sau cách bản trước vài phút:

| Cụm | Pool trước | Pool sau | Cách nhau |
|---|---|---|---|
| `UZBEKISTAN` | ws1 LIFE IN 10:05 | ws20 LIFE IN — US 10:06 | 1 phút |
| `áfrica` | ws18 LIFE IN — Spain 10:35 | ws20 LIFE IN — US 10:43 | 7 phút |
| `indonesia` | ws20 LIFE IN — US 10:06 | ws22 SPACE — US 10:33 | 26 phút |
| `Faroe` | ws20 LIFE IN — US 17:41 | ws21 SPACE — Spain 18:28 | 47 phút |

**Gốc:** khi đổi pool, `App` ghi `writeHash({ tab, ws })` — `ws` trong hash thành pool
MỚI, còn `q` của pool cũ **vẫn nằm nguyên**. `useEffect([ws])` của Mapping kiểm "từ khoá
này có thuộc pool đang mở không" bằng cách so `h0.ws` với `ws` — mà `h0.ws` vừa bị ghi
thành chính pool mới, nên phép so **luôn đúng**. Nó tự gọi `traCuu(q, true)`; server thấy
`xem_lai=1` nhưng pool mới chưa có bản lưu nên rơi xuống nhánh tính mới và `tra_cuu_luu`
ghi thẳng vào lịch sử pool đó. Người dùng không bấm gì cả.

**Vá hai tầng** (mỗi tầng tự đứng được):

- **Server** — `xem_lai=1` mà không có bản lưu thì trả cờ `khong_co_ban_luu`, **không tính
  mới, không ghi**. "Xem lại" theo đúng nghĩa đen. Chốt ở server nên link chia sẻ,
  bookmark, hay bất kỳ đường nào khác cũng không lách được.
- **UI** — hash/localStorage nhớ thêm `qws` = pool **sinh ra** từ khoá, và so với nó thay
  vì so với pool đang mở. Đổi pool thì `qws` vẫn trỏ pool cũ → không tự tra.

**Bài học:** khi một khoá trong URL/state dùng để kiểm "dữ liệu này có thuộc ngữ cảnh hiện
tại không", nó phải là khoá **của dữ liệu**, không phải khoá của ngữ cảnh — nếu ngữ cảnh
tự cập nhật khoá đó thì phép kiểm thành vô hiệu và luôn trả về đúng.

## 22/08 — Tab "Đang nóng": sửa gốc cách chọn ứng viên từ khoá

User (kinh nghiệm niche LIFE IN — US): *"còn quá nhiều từ khóa hot đang bị bỏ qua"*.
Đo thật xác nhận, nặng hơn dự đoán: lấy 1.132 video 60 ngày của ws20, "video nổ" =
vượt trội view/ngày → **177 cụm bị video nổ thiên vị (lift ≥2× nền) thì 173 cụm KHÔNG
nằm trong danh sách ứng viên hiện tại — sót 98%**, trong đó `scientists can't explain`
max 1,53 triệu view.

**Ba lỗi gốc:**
1. Ứng viên chọn theo TẦN SUẤT TÍCH LUỸ (top-60 mẫu câu + top-40 đối tượng trên toàn
   lịch sử) rồi mới đo xu hướng — cụm đang nóng thì tích luỹ thấp, bị cắt TRƯỚC khi
   được đo. Tiêu chí chọn ngược với thứ cần tìm.
2. "Nóng" định nghĩa bằng nguồn cung (số video đăng) thay vì hiệu suất view.
3. Đối tượng đa từ bị băm nát (faroe islands → faroe).

**Logic mới (`mapping.tu_khoa_nong`, 0 quota):** ứng viên = MỌI n-gram 1-3 từ trong
video 2-60 ngày tuổi; video "nổ" = top 10% **view/ngày của chính phiên** (đo phân phối
thật 3 pool: p90 = 21-30× trung vị, đuôi rất dài → cắt theo phân vị bền hơn hệ số
nhân); cụm nóng = ≥4 video mới, ≥2 video nổ, tỉ lệ nổ ≥2× nền. Ngưỡng nổ so sánh
NGHIÊM NGẶT `>` (test bắt được: phân phối bết làm `>=` gom cả nhóm phổ biến vào "nổ",
nền phồng 100%). Gộp họ cụm hai tầng: substring cùng support + vân tay (số mới, số nổ,
video ví dụ) — một title Belarus từng đẻ 4 dòng. Nhãn hiển thị đối_tượng/công_thức
(từ từng đứng sau giới từ hay không), phiên <30 video mới → nói thẳng không kết luận.

**Ngân sách thị trường (user chốt "cho phép tiêu quota"):** mở tab → tối đa
`NGAN_SACH_NONG=5` cụm nóng CHƯA có bản lưu được tự soi khối B **chạy nền** sau
response (102 units/cụm, tắt Trends vì trình duyệt ~17s/cụm); bản B ghi vào
`tra_cuu_log` nên bấm cụm là mở bản đầy đủ, lần sau 0 quota. Đếm cả bản B tra tay
trong ngày vào ngân sách — đếm thừa an toàn hơn đếm thiếu. Chỉ leader+ kích được
probe (viewer vẫn xem danh sách + bản đã lưu).

**UI:** chip thứ tư "Đang nóng" cạnh Đối tượng/Mẫu câu/Tất cả (chip trơn — nguyên tắc
minimalist icon, không emoji); bảng riêng vì hệ quy chiếu khác hai tab cũ (hiệu suất
view ≠ số video đăng): Cụm · Loại · Video mới · Nổ k/n=% · Video nổ nhất (link) ·
Thị trường ngoài (view 90n / đang soi… / —). Nghiệm thu sống ws20: 40 cụm,
`scientists can't explain` 3/4=75% đứng đầu, probe nền điền 7,2M view 90n.
