# Sổ: Trạng thái kênh (vòng đời) vào chẩn đoán — Data Analytics

> Mạch việc bắt đầu 29/08/2026. Nguồn sự thật là code; sổ này ghi QUYẾT ĐỊNH + trạng thái.
> Liên quan: `docs/bao-cao-gop-8-phase.md` (khuôn báo cáo 8 phase), `docs/DE.md` (tầng nền danh bạ).

## Vấn đề (user nêu 29/08/2026)

> "Trong khối general, khi tạo kênh tôi đã có list trạng thái kênh: Kênh mới, kênh đang có đà,
> kênh chưa bật kiếm tiền… Nhưng trạng thái đó không mang sang được sang Data Analytics, cụ thể
> là phần niche research. Hiện tại chỉ có 1 loại báo cáo đánh giá cho các trạng thái kênh khác nhau."

**Xác minh bằng code (không phải cảm nhận):**

- Trạng thái CÓ và khai đủ ở tầng nền — `nen/common/danh_ba.py:32`:
  `TRANG_THAI_KENH = ("uom_mam", "sandbox", "hoat_dong", "monetized", "shadow_ban")`
  + `TRANG_THAI_KENH_AN = ("khai_tu",)`. Cột `trang_thai` nằm sẵn trong bảng `kenh`,
  `_nap()` dùng `SELECT *` nên **mọi dict kênh đã mang sẵn `trang_thai` + `loai_kenh`**.
- Data Analytics đọc `trang_thai` **đúng MỘT lần**, `apps/data-analytics/src/dashboard.py:59`:
  `if k.get("ngach_ma") == ngach_ma and k.get("trang_thai") != "khai_tu"` — chỉ để **ẩn kênh khai tử**.
  Sau đó KHÔNG đi tiếp vào bất kỳ tầng chẩn đoán nào.
- Ngược lại, form Diagnose (`templates/dashboard.html:222-225`) bắt user **chọn lại Channel type
  bằng tay**, dù danh bạ đã có `loai_kenh`. Hai trường của cùng một kênh: một nằm im trong DB,
  một bắt gõ lại mỗi lần chạy.

**Dữ liệu thật (data/nen/danh_ba.db, 29/08):** kênh trải khắp 4 nấc vòng đời — OUTLAND
`monetized`, Zzz History Club `uom_mam`, DESTINO ESPACIO/Celestial Fables/Pa­íses Ocultos
`sandbox`, Cosmic Depth/The Space Archive `hoat_dong`. Không nấc nào ảnh hưởng đến cách đọc số.

⇒ Kênh ươm mầm 3 video và kênh monetized 200 video đi qua **cùng một bộ luật, cùng một khuôn báo cáo**.

## Hạ tầng đã sẵn — không phát minh cơ chế mới

`apps/data-analytics/rules/content_type_profiles.csv` đã là đúng khuôn cần dùng: luật NGOÀI code,
mỗi dòng khai `loai_kenh, ten_hien_thi, chi_so, kieu, he_so, do_tin_cay, nguon`. Bốn `kieu` đã
chạy thật từ 21/07: `noi_nguong` (nới ngưỡng có hệ số) · `ky_vong_cao/thap` · `ky_vong_ngan/dai`
· `ghi_chu`. Trạng thái kênh chỉ cần **thêm trục thứ hai vào đúng khuôn đã kiểm chứng**.

## Ba mức — user chốt 29/08

| Mức | Nội dung | Trạng thái |
|---|---|---|
| 1 | Ngừng bắt gõ lại: `loai_kenh` + `trang_thai` tự chảy từ danh bạ vào form Diagnose; hiện badge; lưu vào bản ghi | **ĐANG LÀM** |
| 2 | `rules/lifecycle_profiles.csv` — trạng thái thành trục đọc số thứ hai, chồng lên `loai_kenh` | Chờ user chốt 2 câu hỏi nghiệp vụ |
| 3 | Gate ký (`gates.py`) ràng theo vòng đời | **HOÃN** — đụng luồng ký đang chạy, đợi Mức 2 chạy thật vài tuần |

## Mức 2 — bảng điều chỉnh ĐỀ XUẤT (user là người chốt, chưa code)

| Trạng thái | Điều chỉnh đề xuất | Căn cứ |
|---|---|---|
| `uom_mam` | Nâng mạnh `MIN_DONG_BASELINE`; trục Tiền + Danh mục → `chua_ap_dung` (KHÁC `thieu_du_lieu`) | Kênh 5 video không có baseline nội bộ để so — hiện trả hàng loạt `chua_du_du_lieu`, đúng nhưng vô dụng |
| `sandbox` | Đọc như tín hiệu **thăm dò**, không phán quyết `bo`; nới ngưỡng báo động | Kênh đang test format — phán "bỏ" lúc này sai nghiệp vụ |
| `hoat_dong` | Mặc định hiện tại, **byte-identical** | Van an toàn |
| `monetized` | Trục Tiền lên **bắt buộc**; thiếu cột RPM = cảnh báo thật, không phải `chua_monetize` | Kênh monetized mà report thiếu cột tiền đang bị báo nhầm "chưa bật kiếm tiền" |
| `shadow_ban` | Ưu tiên trục **Độ phủ** (impressions/velocity); chặn phán quyết `sua_noi_dung` | Impressions sụt là bệnh phân phối — engine hiện dễ đổ oan cho nội dung |

**Về khuôn báo cáo 8 phase:** KHÔNG tách thành 5 khuôn. Giữ 8 phase làm xương sống, mỗi phase tự
khai thêm trạng thái `chua_ap_dung_o_trang_thai_nay` — cùng cơ chế 3 trạng thái
`co_ket_qua / chua_co_so_lieu / chua_du_de_phan_tich` đã có sẵn. Kênh ươm mầm thấy P5 Monetization
ghi rõ "chưa áp dụng ở giai đoạn ươm mầm" thay vì một bảng rỗng khó hiểu.

## Bất biến PHẢI giữ (theo lệ đã chốt cho `loai_kenh` 21/07/2026)

1. **Baseline tự kênh là xương sống** — không bao giờ bỏ.
2. **`trang_thai` rỗng → kết quả byte-identical** như hiện tại. Có test hồi quy ghim.
3. **Luật ngoài code** — thêm/sửa trạng thái = sửa CSV bằng Excel, không sửa Python.
4. **Minh bạch** — mọi điều chỉnh hiện trên banner kèm `nguon` + `do_tin_cay`; ngưỡng
   `uoc_luong` phải ghi rõ là ước lượng, kiểm lại bằng số thật khi kho report lớn.
5. **Van chống bịa** — thiếu căn cứ thì nói thẳng "chưa áp dụng", không bịa số.

## HAI CÂU HỎI NGHIỆP VỤ CÒN CHỜ USER (chặn Mức 2)

1. **`he_so` từng trạng thái**: tôi đề xuất mức khởi đầu (như `loai_kenh` từng làm trẻ em ×1.4)
   và gắn nhãn `uoc_luong`, hay user cấp luật?
2. **Nguồn sự thật của trạng thái**: engine có nên **cảnh báo khi số liệu mâu thuẫn** trạng thái
   khai báo (khai `uom_mam` mà report 200 video; khai `monetized` mà không cột tiền nào)?
   Cảnh báo, **KHÔNG tự sửa** — đúng lệ `doi_chieu_ngay_chay` đã làm.

## Nhật ký

### 29/08/2026 — điều tra + Mức 1

- Điều tra xác nhận vấn đề bằng code + DB thật (mục trên).
- User chốt: làm Mức 1 + mở sổ này. Hai câu hỏi nghiệp vụ để lại chờ chốt riêng.

**MỨC 1 XONG** — test: data-analytics 114→118 pass, root 234→235 pass.

Việc đã làm (7 điểm chạm, thuần cộng thêm — mọi tham số mới có mặc định nên
call-site cũ không đổi):

1. `nen/common/danh_ba.py` — thêm `NHAN_TRANG_THAI_KENH` = MỘT nguồn nhãn vòng đời
   dùng chung. Trước đó nhãn khai CỨNG trong `nen_channels.html`; Data Analytics
   cần đúng bộ nhãn đó, để hai nơi tự khai là mời drift.
2. `nen/gateway/templates/nen_channels.html` + `nen/gateway/main.py` — gateway đọc
   nhãn từ nguồn chung thay vì tự khai.
3. `apps/data-analytics/src/main.py` — `templates.env.globals["nhan_tt_kenh"]`
   (hằng số tĩnh → globals gọn hơn context processor, phủ mọi template). Nền lỗi
   → dict rỗng, badge lùi về mã thô, KHÔNG giết app.
4. Tile kênh (Channel Research) + pane kênh hiện **chip vòng đời + loại kênh**.
   CSS `.tt-chip` khai đủ CẶP token 2 theme (lệ 30/07 — không hex trần). Màu là
   semantic theo giai đoạn: traction/monetized = accent · testing = warn ·
   shadowban = danger · incubating = trung tính.
5. Form Diagnose: mỗi `<option>` mang `data-loai` + `data-tt`; JS `nrkDongBoKenh()`
   **tự điền Channel type từ danh bạ** — hết bắt gõ lại thứ General đã khai. User
   vẫn override được: danh bạ chưa khai loại thì KHÔNG ghi đè lựa chọn tay.
6. Dòng "Lifecycle: <chip>" trong form, kèm chữ **"chưa ảnh hưởng cách đọc số"** —
   nói thẳng giới hạn Mức 1, không để người dùng tưởng engine đã đọc.
7. `trang_thai_kenh` chảy route → task nền → bản ghi lịch sử, **đóng băng lúc chạy**
   (kênh lên nấc mới sau này không viết lại quá khứ — cùng lệ `loai_kenh`).

Test ghim (5 test mới):
- `test_trang_thai_kenh_KHONG_doi_ket_qua_chan_doan` — **lưới chặn của Mức 1**:
  cùng report, đổi trạng thái thì phán quyết PHẢI y hệt. Khi làm Mức 2 test này
  sẽ ĐỎ, buộc người sửa đọc sổ và đổi có ý thức thay vì đổi lặng lẽ.
- `test_nhan_vong_doi_hien_tu_nguon_chung` (root) — ghim biến nhãn THẬT SỰ tới
  template. Thiếu biến thì nhãn ra rỗng mà trang vẫn 200; test status không bắt được.
- 3 test còn lại: lưu đúng khi có, rỗng vẫn chạy, đi kèm kết quả cho UI.

Nghiệm thu trên **DB danh bạ THẬT** (chỉ đọc, không ghi — lệ "không nghiệm thu
ghi/xóa trên hệ thật"): `/niche/kenh` 200, chip hiện đủ 4 nấc đang dùng
(Incubating/Testing/Traction/Monetized); pane `K-ZZZ-HISTORY-CLUB` ra đúng chip
`uom_mam`; 19/19 option mang đủ `data-loai` + `data-tt`, OUTLAND tự điền
`narrator`/`monetized`.

**CHƯA làm (Mức 2)** — vẫn chờ user chốt 2 câu hỏi nghiệp vụ ở mục trên. Engine
chưa đọc `trang_thai` một dòng nào; báo cáo 8 phase chưa đổi.

### 29/08/2026 (tiếp) — SỰ CỐ 500 TRÊN MÁY THẬT + bản vá

**Triệu chứng:** ngay sau Mức 1, `192.168.1.250:9000/app/data-analytics/niche/kenh`
trả `Internal Server Error` — trong khi suite 118 pass và render thử trên DB thật
đều 200.

**Nguyên nhân (đo, không đoán):** tiến trình uvicorn data-analytics đang chạy khởi
động **26/08** (`Get-Process StartTime`), còn code sửa **29/08**. Jinja
`auto_reload=True` nạp template mới TỪ ĐĨA ngay lập tức, nhưng biến globals
`nhan_tt_kenh` chỉ tồn tại trong code Python MỚI → template mới gọi
`nhan_tt_kenh.get(...)` trên biến undefined → `UndefinedError` → 500 cả trang.
Đây chính là bẫy đã ghi memory *"sửa template trên hệ đang chạy"*, lần này ở dạng
biến-globals thay vì đổi tên trường.

**Vì sao mọi phép kiểm trước đó không bắt được:** chúng đều chạy trong tiến trình
Python MỚI (pytest / script kiểm), nơi code và template luôn cùng đời. Khoảng lệch
code-cũ × template-mới chỉ tồn tại trên tiến trình đang chạy.

**Bản vá (không chỉ chữa triệu chứng):**
- `dashboard.html`: gom 3 chỗ gọi nhãn về macro `nhan_vong_doi(ma)` dùng
  `nhan_tt_kenh | default({}, true)` → thiếu biến thì **lùi về mã thô, trang vẫn
  sống**. `nen_channels.html` vá cùng kiểu.
- Đây là hành vi BẮT BUỘC chứ không phải phòng xa: mọi lần deploy đều có khoảnh
  khắc template mới gặp code cũ.
- Restart service data-analytics (dừng theo **PID** từ `logs/pids`, tuyệt đối không
  Stop-Process theo tên — sự cố 21/08). Nghiệm thu sau restart: `/niche/kenh`,
  pane `K-ZZZ-HISTORY-CLUB`, pane `K-OUTLAND` đều 200, chip hiện đúng
  Incubating/Traction/Monetized.

**BÀI HỌC TEST (quan trọng hơn bản vá):** test ghim đầu tiên tôi viết là **TEST GIẢ
— nó xanh cả khi đã gỡ fallback**. Lý do: `apps/data-analytics/conftest.py:30` trỏ
`DANH_BA_DB` vào file KHÔNG TỒN TẠI → `ds_kenh` rỗng → nhánh chip không bao giờ
render → không có gì để vỡ. Đã sửa: helper `_danh_ba_co_kenh()` dựng danh bạ tạm
CÓ kênh (nhớ `danh_ba._cache.clear()` vì `_nap` cache theo mtime).
**Kỷ luật rút ra: test chống-hồi-quy phải được chứng minh là ĐỎ khi gỡ bản vá.**
Đã làm đúng vậy — gỡ `| default({}, true)` → test đỏ; khôi phục → xanh.

---

## MỨC 2 — CHẾ ĐỘ CHỈ-SỐ cho kênh chưa bật kiếm tiền (29/08/2026)

**Owner chốt (thay bảng đề xuất Mức 2 ở trên):**

> "Đối với kênh chưa bật kiếm tiền: CHỈ cần quan tâm tới mức tăng trưởng view - AVD -
> CTR. Không cần đưa ra so sánh gợi ý nào cả. Bởi kênh nhỏ các chỉ số đang chưa được
> chính xác."

Hai câu hỏi làm rõ, Owner chọn:
1. **Đầu ra** = chỉ số trần + cảnh báo sụt sâu (giữ van bắt bệnh nặng thật).
2. **Phạm vi** = `uom_mam`/`sandbox` **HOẶC** report thiếu cột tiền. Owner **giữ nguyên
   vế thứ hai sau khi biết** 10/20 report thật không có cột tiền (đo trước khi hỏi lại).

### Luật đã code

`che_do_chi_so(so, trang_thai_kenh)` → True khi vòng đời `uom_mam`/`sandbox` HOẶC
`not _da_monetize(so)`. Rẽ nhánh **SỚM** trong `chan_doan_toan_bo`, trước khi chấm trục
— để không đường nào rò phán quyết ra ngoài. Trả `che_do='chi_so'` với `chi_so_kenh`
(trung vị views/avd/ctr) + `videos` (số trần, xếp view giảm dần) + `xu_huong` (theo
tháng đăng = "mức tăng trưởng") + `canh_bao_sut_sau`.

**KHÔNG có ở chế độ này:** phán quyết · thẻ điểm 4 trục · khung 9 mục · tổng quan danh
mục · **và không gọi LLM** (diễn giải chính là "gợi ý" Owner đã cắt — đỡ luôn tiền token).

### Phát hiện khi đo thật: BỎ VIEW khỏi cảnh báo sụt sâu

Bản đầu cảnh báo cả 3 chỉ số → **22/46 video Space bị cảnh báo**, quá nhiều. Đo trên 2
report thật:

| | views < 0.35× trung vị | avd | ctr |
|---|---|---|---|
| Space (46 video) | 8 | 13 | 1 |
| Wheel (108 video) | **41** | 19 | 2 |

View của kênh YouTube phân phối **lệch cực mạnh** (vài video trúng gánh phần lớn view,
đuôi dài rất ít view) nên "view thấp hơn trung vị nhiều lần" là **hình dạng bình thường**,
không phải bệnh. → `CHI_SO_CANH_BAO = ("avd", "ctr")`; views vẫn nằm trong bảng số vì đó
là chỉ số Owner yêu cầu theo dõi, chỉ không dùng để báo động. Sau sửa: 14/46 và 21/109.
Có test ghim để không ai thêm lại `views` mà chưa đọc số đo.

### Nghiệm thu report THẬT

| Report | Trạng thái | Kết quả |
|---|---|---|
| Space.xlsx (46 video) | sandbox | `chi_so` · views 511,5 · avd 6,11 · ctr 2,82% · 14 cảnh báo |
| Wheel.xlsx (109 video) | uom_mam | `chi_so` · 21 cảnh báo |
| Outland.xlsx | monetized | `toan_bo` — 4 trục + phán quyết **như cũ** |

UI kiểm bằng **Chrome headless** trên dữ liệu thật: 3 thẻ chỉ số, 62 hàng bảng, khối
"chưa đủ dữ liệu để nói xu hướng" hiện đúng khi chưa đủ 3 tháng, **không lỗi JS**.

### Bất biến giữ + bẫy đã tránh

- Kênh `hoat_dong`/`monetized` + report có cột tiền → nhánh cũ **không đổi một byte**
  (test `test_vong_doi_da_kiem_tien_giu_phan_quyet` ghim).
- JS dựng bằng **DOM API** (`createElement`/`textContent`), KHÔNG nối chuỗi vào
  innerHTML — tiêu đề video là dữ liệu người dùng; đúng quy ước chống XSS ghi ở
  `_bang_phan_quyet.html:193`. (Bản nháp đầu dùng `esc()` — hàm KHÔNG TỒN TẠI trong
  dự án, sẽ lỗi runtime; bắt được nhờ grep trước khi chạy.)
- Hàm `veCheDoChiSo` + CSS đặt trong `_bang_phan_quyet.html` = template CON DÙNG CHUNG
  của cả trang chẩn đoán lẫn trang lịch sử → **không drift** (đúng lệ đã lập 20/07).
- Template lịch sử: nhánh `che_do == 'chi_so'` đặt TRƯỚC nhánh cũ, vì `toan_bo.bao_cao_kenh`
  không tồn tại ở chế độ này và `|tojson` trên Undefined là TypeError (đã kiểm chứng).
- 4 chỗ gọi `chan_doan_toan_bo` đều truyền `trang_thai_kenh` → xem lại đúng chế độ lúc chạy.

### Test cũ phải cập nhật (đổi hành vi có chủ đích)

Report mẫu trong test không có cột tiền → rơi vào chế độ chỉ-số, làm 33 test đỏ. Sửa
bằng cách **thêm cột RPM** vào report mẫu (mô phỏng kênh đã monetize) — giữ nguyên từng
giá trị cũ nên assert khác không đổi nghĩa. Kéo theo: mục C2 "phễu tiền" giờ có kết quả
→ 9 mục kỳ vọng `{A1,B3}` thành `{A1,B3,C2}`, số lời gọi LLM 2→3.

Test `test_trang_thai_kenh_KHONG_doi_ket_qua_chan_doan` (lưới chặn Mức 1) đã **làm đúng
việc**: nó đỏ khi Mức 2 đổi cách đọc. Thay bằng 3 test cho luật mới.

**Test: data-analytics 120 → 127 pass · root 235 pass.**

### Còn lại

- Owner **kiểm mắt** trang chẩn đoán với report của kênh sandbox/uom_mam.
- Ba nấc còn lại của bảng Mức 2 (`shadow_ban` ưu tiên trục độ phủ; `monetized` thiếu cột
  RPM = cảnh báo thật) **CHƯA làm** — chờ Owner chốt.
- Câu hỏi "cảnh báo khi số liệu mâu thuẫn trạng thái khai báo" vẫn treo.
