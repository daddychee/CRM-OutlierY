# finance-hub.md — Sổ chủ đề: Finance Hub (app to-chuc)

> Sổ riêng cho mạch **Finance Hub**. CLAUDE.md của app chỉ giữ mốc trỏ về đây.
> Nguồn sự thật vẫn là code; sổ này ghi **quyết định, lý do, và cái đã bác bỏ**.
>
> Liên quan: `docs/DE.md` mục 10 (giỏ chức năng) + 13.6 (Owner chốt trục Mục tiêu,
> gợi ý tham khảo lõi kế toán mở) · `apps/to-chuc/CLAUDE.md` (nhật ký app).

## 1. Trạng thái

| Ngày | Việc | Kết quả |
|---|---|---|
| 16/08/2026 | Đ2b Finance Hub v1 | 4 tab Ledger/Goals/Categories/Channel P&L chạy, `tai_chinh.py` 284 dòng |
| 26/08/2026 | Nghiên cứu lõi mã nguồn mở + đề xuất 14 tính năng | Owner **đồng ý spec** |
| 26/08/2026 | Mockup vòng 2 (`docs/mockup-de/finance-hub-v2.html`) | Owner **chốt giao diện** |
| 26/08/2026 | Owner bổ sung 4 yêu cầu (D1–D4, mục 5) | mockup vòng 3 `finance-hub-v3.html` |
| 26/08/2026 | Owner chốt 5 câu vòng 2 (mục 8) + mở 3 chủ đề mới (mục 9) | **spec thi công** `docs/finance-hub-spec.md` |
| 26/08/2026 | Owner chốt 3 chủ đề vòng 3 + mockup v4 | chấm công chỉ đo giờ có mặt · quyền mở cho HR · dashboard |
| 26/08/2026 | **CODE XONG đợt A + D** (8 commit, mỗi bước test xanh) | A1 ví · A2 hai đồng tiền · A3 chứng từ · A4 lọc+xuất · D2 thuê bao · D1+D6 lương+đi muộn · D3 chi phí ngách · D5 phiếu lương · D4 lịch · UI-final dashboard |

**Đã chạy trên CRM** (app `to-chuc` cổng 9103 restart 26/08): 9 tab, 116 test app +
232 test root xanh. Sổ tiền vẫn rỗng — chờ Owner nhập dữ liệu vận hành (mục 10).

| 26/08/2026 | **CODE XONG TOÀN BỘ 18 tính năng** (A · B · C · D) | 12 commit, 147 test app |

**Đã chạy trên CRM** — 10 tab: Tổng quan · Sổ thu chi · Ví & chốt kỳ · Ngân sách ·
Kênh · Ngách · Lương · Thuê bao · Tự động · Danh mục.

**Không còn tính năng nào của mockup v4 thiếu module.** Sổ tiền vẫn rỗng — chờ
Owner nhập dữ liệu vận hành (mục 10).

**Sổ tiền đang RỖNG** (0 bút toán, `data/to-chuc/db/so-thu-chi/` chưa có tệp).
Đây là lý do mọi thay đổi cấu trúc bản ghi phải làm **trước** khi mở cho kế toán ghi:
sau bút toán thật đầu tiên, mỗi trường thêm vào là một migration trên dữ liệu tiền.

## 2. Quyết định kiến trúc — trả lời câu hỏi treo ở DE.md 13.6

**Không thay engine bằng beancount/hledger.** Chúng là engine một-người chạy dòng
lệnh trên tệp văn bản; ghép vào web app nhiều người có RBAC nghĩa là viết lại lớp
ghi đồng thời, lớp quyền, lớp kiểm đầu vào — đúng phần đã có — để đổi lấy phần chưa
cần (giá vốn, danh mục đầu tư).

**Mượn 6 khái niệm** của chúng: số dư khẳng định (balance assertion) · chứng từ đính
kèm (document) · tiền tệ gốc + tỷ giá (operating currency) · chiều phân tích
(dimension) · khóa sổ kỳ (month-end close) · giao diện importer.

**Xuất `.beancount`** (~80 dòng): cắm vào Fava là có bảng cân đối, báo cáo kết quả,
treemap chi phí miễn phí. Cũng là đường thoát nếu sau này muốn chuyển hẳn sang
plain-text accounting.

### Đã bác bỏ (đừng đề xuất lại)

- **Bút toán kép đầy đủ + hệ thống tài khoản** — chi phí là người ghi phải hiểu Nợ/Có.
  Trục **ví** (A1) cho 90% lợi ích với 10% chi phí học.
- **Kết nối ngân hàng tự động** — GoCardless/SimpleFIN/Plaid không phủ ngân hàng VN.
- **Hóa đơn, báo giá, công nợ khách hàng** — không bán cho khách, doanh thu từ AdSense.
- **Kho hàng, tài sản cố định, đa chi nhánh** — không có thực thể tương ứng.
- **Đọc biên lai bằng AI** — kết luận 01/08: OCR rụng dấu tiếng Việt. Đính kèm tệp (A3)
  giải quyết đúng nhu cầu thật là lưu trữ và tra lại.

## 3. Bất biến (mọi tính năng phải giữ)

1. **Sổ chỉ-thêm.** Dòng đã ghi không sửa, không xóa. Sai → bút toán đảo có vết.
2. **Luật ngoài code.** Danh mục khoản, ví, tỷ giá, đơn giá API, luật gợi ý: CSV/JSON
   sửa bằng Excel, không phải sửa Python.
3. **Van chống bịa số liệu.** Nguồn chết hoặc dưới ngưỡng mẫu → "—" kèm lý do, tuyệt
   đối không 0 giả, không con số suy đoán.
4. **Máy đề nghị, người chốt.** Không bút toán nào do máy tự ghi vào sổ tiền.
5. **Phân bổ tính lúc đọc**, không sinh bút toán — sổ gốc giữ nguyên bản.
6. **Quyền qua giỏ `ke_toan`** ở gateway; app chỉ tin cờ, không tự tính lại (Luật 4).
7. **Không chạm bí mật.** Finance đọc *metadata* dịch vụ trả phí, không bao giờ đọc
   mật khẩu — mật khẩu chỉ sống trong Vault.

## 4. Mười bốn tính năng đã chốt (mã dùng chung cho spec và mockup)

### Đợt A — nền, làm khi sổ còn rỗng

| Mã | Tính năng | Mượn từ | Ghi chú thi công |
|---|---|---|---|
| A1 | **Ví tiền** — bút toán ghi vào ví nào | Firefly III, Bigcapital, Actual | `rules/danh_muc_vi.csv`; bút toán thêm `vi`; tab Ví hiện số dư |
| A2 | **Hai đồng tiền** USD/VND | beancount operating currency | bút toán thêm `tien_te` + `ty_gia` chốt tại ngày ghi; sổ tỷ giá theo ngày; chênh lệch tỷ giá = mã khoản riêng |
| A3 | **Chứng từ đính kèm tệp** | beancount `document`, Midday | `data/to-chuc/db/chung-tu/<năm>/<id>/`; bút toán đảo kế thừa chứng từ gốc |
| A4 | **Lọc + xuất CSV + xuất `.beancount`** | Fava | việc treo từ 16/08 |

### Đợt B — ra quyết định

| Mã | Tính năng | Mượn từ | Ghi chú thi công |
|---|---|---|---|
| B1 | **Phân bổ chi phí chung theo kênh** | ERPNext cost center | quy tắc: chia đều / theo doanh thu / theo lượt xem / theo số video; bảng P&L hai cột trực tiếp ‖ sau phân bổ |
| B2 | **Đơn vị kinh tế** chi phí/video, chi phí/1K view, hoàn vốn | tự xây | nối Data Analytics + PlannerY |
| B3 | **Mức đốt & thời gian còn sống** | Midday | 3 số trên Tổng quan + ngưỡng cảnh báo trong cài đặt |
| B4 | **Ngân sách theo kỳ + chuyển tiếp** | Actual, Firefly III | thay tab Mục tiêu; vượt hạn mức **cảnh báo, không chặn** |
| B5 | **Đối soát chi trả AdSense** | beangulp, Midday, balance assertion | CSV → bút toán nháp gắn kênh → người duyệt; trạng thái thu: ước tính ‖ đã chốt ‖ đã về ví |

### Đợt C — tự động & kỷ luật

| Mã | Tính năng | Mượn từ | Ghi chú thi công |
|---|---|---|---|
| C1 | **Khoản định kỳ** | Wallos, Actual, Firefly III | *gộp vào D2* — mỗi dịch vụ trả phí là một khoản định kỳ |
| C2 | **Luật gợi ý phân loại** | Firefly III rules | CSV; chỉ điền sẵn ô trong form, không áp thầm |
| C3 | **Tiền API từ nhật ký quota** | lợi thế riêng | đơn giá theo API+model trong CSV; một bút toán tổng hợp/tháng |
| C4 | **Lương từ chấm công + KPI** | tự xây | *mở rộng thành D1* |
| C5 | **Chốt kỳ + đối chiếu số dư** | beancount month-end close | còn ví lệch → khóa chốt; sau chốt, bút toán ngày cũ bị đánh dấu *điều chỉnh kỳ trước* |

## 5. Bốn bổ sung của Owner (26/08) — D1…D4

### D1 — Bảng lương chiết xuất từ chấm công HR Hub (đăng nhập CRM)

**Owner nêu:** lương tính từ chấm công của HR Hub, mà chấm công lấy từ đăng nhập CRM.

Nguồn đã có, không phải dựng mới:
- `cham_cong.bang_cong_thang(thang)` — hiện diện trên cổng, đã chạy từ 01/08.
- `cham_cong.chot_ky(thang, nguoi_chot)` — công đã chốt, chỉ-thêm.
- `kpi_danh_gia` — xếp loại A/B/C của kỳ.
- IAM — hồ sơ người, bộ phận, vị trí.

Thiết kế: bảng lương là **bảng đề nghị đọc-tính**, không phải sổ thứ hai. Owner duyệt
thì sinh bút toán `CHI-LUONG` theo từng người. Ba cột nguồn hiện rõ để đối chiếu:
công chốt / xếp loại / hệ số. **Van trung thực giữ nguyên** — chấm công là *hiện diện
trên hệ công cụ*, không phải máy vân tay; ai chưa có xếp loại thì ô để trống kèm lý do,
không suy ra số. Lương chưa duyệt **không** vào chi phí kênh/ngách.

Đơn giá ngày công `= lương kỳ ÷ ngày công chuẩn của kỳ` — số này là đầu vào của D3.

### D2 — Danh sách tài khoản trả phí (không kèm mật khẩu)

**Owner nêu:** biết thời gian gia hạn, bỏ gia hạn…

**Quyết định tách kho có chủ đích:** metadata dịch vụ (chu kỳ, ngày gia hạn, phí, tự
động gia hạn, trạng thái) **không** nằm trong Vault mã hóa. Lý do: Finance phải đọc
được mà không mở Vault và không chạm mật khẩu; Vault chỉ giữ bí mật, mở là phải có
master và bị ghi audit từng lượt xem.

- Sổ mới `data/to-chuc/db/dich-vu-tra-phi.json` — trường: `ten`, `nha_cung_cap`,
  `nhom`, `phi`, `tien_te`, `chu_ky`, `ngay_gia_han`, `tu_dong_gia_han`, `trang_thai`
  (đang dùng ‖ sắp bỏ ‖ đã hủy), `kenh_ma`/`ngach_ma`, `danh_muc`, `vault_id`, `ghi_chu`.
- `vault_id` chỉ là **id trỏ sang** mục Vault — không sao chép tài khoản, không mật khẩu.
  Người cần đăng nhập thì sang Vault (Owner), Finance không phải cửa lấy mật khẩu.
- **Gộp C1 vào đây:** dịch vụ có chu kỳ *là* khoản định kỳ — đến hạn thì hiện ở hàng
  chờ "đến hạn, chưa ghi", bấm là mở form điền sẵn. Máy vẫn không tự ghi.
- Trạng thái *sắp bỏ* làm được việc thật: nó là quyết định cắt chi phí, hiện lên
  Tổng quan để tháng sau khỏi mất tiền oan.

### D3 — Chi phí sản xuất theo ngách, tính bằng ngày công

**Owner nêu:** chi phí sản xuất cho niche = số ngày công làm cho niche đó.

Khảo sát PlannerY (`data/plannery/plan.json`) — dữ liệu nối sẵn, không phải khai lại:
- `projects[]` có **`ngach_ma`** (nối thẳng danh bạ ngách) và `channels[].kenh_ma`.
- `assignments[]` = `{person_id, project_id}` — người ↔ ngách. Hiện 15 phân công / 8 người.
- `people[].id` = `ns_<mã NS>` — khớp hồ sơ IAM, đúng khóa KPI đang dùng.

Công thức:

```
chi phí ngách N (kỳ K)
  = Σ  ngày công người P trong K  ×  đơn giá ngày công của P (D1)  ×  tỷ trọng(P → N)

tỷ trọng(P → N) = số ngách P được phân công … chia đều
                  (nếu PlannerY có video thật gắn người thì chia theo số video —
                   dữ liệu chính xác hơn thắng)
```

Van chống bịa: người **không** có phân công nào → ngày công về "chung hệ", không rải
bừa cho các ngách. Người có phân công nhưng kỳ đó 0 ngày công → 0, không ước lượng.
Kết quả hiện thành **cột chi phí nhân công** cạnh chi phí tiền mặt trong bảng ngách,
và là một quy tắc phân bổ mới của B1 ("theo ngày công").

### D4 — Lịch tài chính: chốt 10–12, trả lương 15

**Owner nêu:** báo cáo tổng vào ngày 10–12 hằng tháng (ngày YouTube tổng tiền); lịch
trả lương ngày 15.

Kỳ kế toán **vẫn là tháng dương lịch** — đổi kỳ là đổi mọi phép cộng. Cái thay đổi là
**lịch việc**:

| Mốc | Việc | Khối |
|---|---|---|
| ngày 10–12 tháng M+1 | Google chốt tiền tháng M → nạp CSV, đối soát, ghi doanh thu thật | B5 |
| sau đối soát | đối chiếu số dư ví → chốt kỳ M | C5 |
| ngày 15 tháng M+1 | duyệt bảng lương kỳ M → sinh bút toán `CHI-LUONG` | D1 |

Ràng buộc có chủ đích: **không cho chốt kỳ trước khi đối soát AdSense xong** (chốt
trên doanh thu ước tính là chốt lên số sai) và **không duyệt lương trước khi công
được chốt**. Trạng thái mốc hiện trên Tổng quan; trễ hạn thì nhắc, không tự chạy.

## 6. Schema sau khi làm đợt A (bút toán)

```jsonc
{
  "id": "BT-260826-a1b2",      // bất biến
  "ngay": "2026-08-26",
  "loai": "thu | chi | dao",
  "danh_muc": "CHI-PROXY",     // rules/danh_muc_thu_chi.csv
  "so_tien": 86.0,             // NGUYÊN TỆ
  "tien_te": "USD",            // A2 — mới
  "ty_gia": 26300,             // A2 — chốt tại ngày ghi, không đổi về sau
  "vi": "payoneer",            // A1 — mới, rules/danh_muc_vi.csv
  "muc_tieu": "Nuôi kênh SPACE Q3",
  "kenh_ma": "K-COSMIC-DEPTH", // "" = chung hệ
  "trang_thai_thu": "",        // B5 — ước tính | da_chot | da_ve_vi (chỉ dòng thu)
  "chung_tu": "INV-2026-08-13",
  "tep_dinh_kem": ["hoa-don.jpg"],   // A3 — mới
  "nguoi_ghi": "lanne",
  "ghi_chu": "proxy 911 gói tháng",
  "tham_chieu": "",            // id bút toán gốc, chỉ dòng đảo
  "tao_luc": "2026-08-26T10:11:00"
}
```

Không thêm `ngach_ma`: ngách suy ra từ `kenh_ma` qua danh bạ — một nguồn sự thật.

## 7. Thứ tự thi công

1. **A1 → A2 → A3 → A4** một mạch khi sổ còn rỗng, rồi mở cho kế toán ghi thật.
2. **D2** (dịch vụ trả phí, gộp C1) — sổ tự đầy, và là chi phí đang chảy hằng tháng.
3. **D1** (bảng lương) → **D3** (chi phí ngách theo ngày công) — D3 cần đơn giá của D1.
4. **B1** (P&L hết nói dối) → **B3** → **B2**.
5. **D4** (lịch tài chính) + **C5** (chốt kỳ) — đi cùng nhau.
6. **B5** → **B4** → **C3** → **C2**.

Mỗi bước một commit xanh, chạy `pytest` trước khi commit (lệ đã có của repo).

## 8. Quyết định vòng 2 (Owner, 26/08)

| # | Câu hỏi | Owner chốt | Hệ quả thi công |
|---|---|---|---|
| 1 | Ngày công chuẩn | **Ngày làm việc của tháng, công ty nghỉ Chủ nhật** | `ngày trong tháng − số Chủ nhật − ngày lễ`; số này ĐỔI theo tháng (07=27 · 08=26 · 09=26 · 10=27 · 02=24) nên đơn giá ngày cũng đổi. Lương cơ bản vẫn cố định theo tháng. Ngày lễ để `rules/ngay_nghi_le.csv`; lễ rơi Chủ nhật không trừ hai lần |
| 2 | Ngưỡng cảnh báo runway | *Owner hỏi lại nghĩa là gì* → giải thích ở dưới, **đề xuất 6 tháng** | cấu hình được, không nằm trong code |
| 3 | API tỷ giá miễn phí | có — **VCB chính, ExchangeRate-API mở dự phòng** (đo thật 26/08, cả hai chạy từ máy này) | mục 3 spec |
| 4 | Người kiêm nhiều ngách | **Đồng ý**: chia đều, tự đổi sang chia theo số video khi PlannerY có video gắn tên | không hỏi lại |
| 5 | Spec | **Ghi spec trước phần đã có** | `docs/finance-hub-spec.md` — hiện trạng ở mục 0, spec A1–A4 + D1–D4, test bắt buộc, thứ tự commit |

### 8.1 "Ngưỡng cảnh báo runway" nghĩa là gì

*Runway* = số tháng công ty còn nuôi được bộ máy nếu doanh thu giữ nguyên:
`số dư ví khả dụng ÷ mức đốt ròng trung bình tháng`. Ví dụ số trong mockup:
172.723.000 ₫ ÷ 26.300.000 ₫ = **6,6 tháng**.

*Ngưỡng cảnh báo* là con số mà khi runway tụt xuống dưới, ô đó chuyển vàng/đỏ và
hiện lên đầu trang — để Owner biết trước, không phải phát hiện lúc hết tiền.

**Đề xuất 6 tháng.** Lý do lấy từ chính mô hình: một kênh mới từ lúc đổ tiền tới
lúc có doanh thu mất khoảng 3–6 tháng, nên dưới 6 tháng nghĩa là không đủ vốn nuôi
trọn một lứa kênh mới. Số này để trong cấu hình, đổi lúc nào cũng được.

### 8.2 Tỷ giá — đo thật ngày 26/08/2026

| Nguồn | Kết quả | Vai |
|---|---|---|
| `vietcombank.com.vn/api/exchangerates?date=now` | USD: mua tiền mặt 25.890 · **mua chuyển khoản 25.920** · bán 26.300 | **chính** — miễn phí, không khóa, cập nhật 08:06 mỗi sáng |
| `open.er-api.com/v6/latest/USD` | VND 26.059,9 | dự phòng — miễn phí, không khóa, ngày một lần |

**Dùng giá MUA CHUYỂN KHOẢN, không dùng giá bán.** Công ty *nhận* USD rồi bán cho
ngân hàng, nên số VND thực nhận là giá ngân hàng mua. Mockup đang để 26.300 (giá bán)
— lấy giá bán sẽ thổi doanh thu lên ~1,5%, tức khoảng 1,6 triệu ₫ trên doanh thu
108 triệu ₫ một tháng. Sẽ sửa khi code.

Không nguồn nào chạy được → form bắt nhập tay, ghi nhãn nguồn `tay`. Tỷ giá đã chốt
trên bút toán không bao giờ cập nhật lại.

## 9. Ba chủ đề — Owner CHỐT 26/08 (vòng 3)

### 9.1 Chấm công, KPI, thưởng phạt

**Owner chốt nguyên văn:** *"Tôi chỉ đo chấm công bằng giờ có mặt. Tức là mở CRM,
còn trong phiên thì tôi không quan tâm. Chỉ cảnh báo về số giờ đi muộn trong tháng.
Không trừ vào bảng Lương. HR sẽ là người quyết định."*

Hệ quả:
- **Ngày công = ngày có mở CRM.** `cham_cong.bang_cong_thang()` `so_ngay` đã đếm
  đúng như vậy từ 01/08 — không phải sửa gì.
- **`tong_giay` (thời lượng trong phiên) nghỉ hưu khỏi mọi bảng lương.** Giữ trong
  code (nhịp tim, beacon vẫn chạy vô hại), chỉ không dùng và không hiện.
- **Đi muộn chỉ CẢNH BÁO** (khối D6 mới): số buổi + tổng phút trong tháng, hiện ở HR
  Hub và trên phiếu lương. Không vào công thức lương.
- **Máy không tự trừ tiền của ai.** Bỏ hệ số `công / ngày làm việc` khỏi công thức
  lương. Đường duy nhất để công vắng hay đi muộn ảnh hưởng lương là ô **điều chỉnh
  của HR** (số tiền + **lý do bắt buộc**) — luôn có tên người quyết đứng sau.
- Luật KPI có căn cứ số (`kpi_luat.csv`, điểm đề xuất, chấm lệch phải ghi lý do) —
  đề xuất vẫn để đó, **chưa làm đợt này**; Owner chưa yêu cầu.

### 9.2 Phân quyền

**Owner chốt:** *"Quyền xem sửa thuộc về HR và nhân sự bộ phận tài chính vì nhân sự
bộ phận này mới chỉ có 2 người. Tôi sẽ thay đổi khi cơ cấu phình to sau này. Xuất ra
phiếu lương kèm báo cáo hiệu suất cụ thể của nhân sự và HR là người xuất và gửi."*

| Ai | Vào Finance | Tab Lương | Xuất/gửi phiếu | Duyệt chi lương | Vault |
|---|---|---|---|---|---|
| Owner | ✔ | ✔ | ✔ | ✔ | ✔ |
| Kế toán L2+ (giỏ `ke_toan`) | ✔ | ✔ | ✔ | ✖ | ✖ |
| HR L3+ (giỏ `nhan_su`) | ✔ | ✔ | ✔ | ✖ | ✖ |

- Thi công: `_gio_chuc_nang` ở gateway phát cờ `finance` **thêm vế `nhan_su`**.
- **Bỏ** đề xuất tách giỏ `finance_luong` của vòng trước — cơ cấu 2 người không cần
  thêm một tầng quyền. Ghi lại đây để sau này phình to thì biết chỗ mà tách.
- **Duyệt chi lương giữ ở Owner** (spec đề xuất, chờ Owner xác nhận): bước đó sinh
  bút toán vào sổ tiền, khác với lập và gửi phiếu.
- **D5 mới — phiếu lương kèm báo cáo hiệu suất**: HTML in được (Ctrl+P ra PDF), tải
  cả kỳ dạng zip. **Không dùng WeasyPrint** — máy Windows này thiếu GTK, 3 test
  `test_remake_dep` fail đúng vì lý do đó từ 29/07.
- Còn treo: nhân viên xem phiếu lương của chính mình — chưa cần vì HR gửi phiếu.

### 9.3 Dashboard — **đồng ý**

`frappe-charts` 1.6.2 vendor riêng cho to-chuc, sáu biểu đồ, mỗi cái trả lời một câu
hỏi. Chi tiết + bẫy theme ở `finance-hub-spec.md` mục 11.

## 10. Việc treo

- **Giờ vào chuẩn để tính đi muộn** — `rules/gio_lam_viec.csv`, tạm `08:30`, dung sai
  10 phút. **Owner xác nhận.**
- **Ai duyệt chi lương** — spec để Owner; nếu Owner muốn giao HR thì nói, sửa một dòng.
- `rules/ngay_nghi_le.csv` cần Owner điền lễ 2026–2027.
- Trường `luong_co_ban` trong hồ sơ IAM (D1 cần) — thêm ở đợt nào, ai được xem.
- Mockup đang để tỷ giá 26.300 (giá bán) — sửa thành giá mua chuyển khoản khi code.
- Luật KPI có căn cứ số (9.1) — để dành, chưa làm.
