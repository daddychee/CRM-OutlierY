# finance-hub-spec.md — Spec thi công Finance Hub

> Spec **đủ để code**, cho phần Owner đã chốt (đợt A + D1–D4). Quyết định và lý do
> nằm ở `docs/finance-hub.md`; giao diện ở `docs/mockup-de/finance-hub-v2.html`
> (chốt) và `finance-hub-v3.html` (D1–D4). Mã khối dùng chung ba nơi.
>
> Chốt 26/08/2026. Đợt B, C spec sau — chưa code thì chưa spec chi tiết.

## 0. Hiện trạng — phần ĐÃ CÓ, không viết lại

| Thành phần | Nơi | Giữ nguyên |
|---|---|---|
| Sổ thu chi chỉ-thêm JSONL theo năm | `src/tai_chinh.py` `_ghi_dong`, `doc_so` | ✔ chỉ thêm trường |
| Bút toán đảo (`dao_but_toan`) | `tai_chinh.py` | ✔ nguyên vẹn |
| Mục tiêu (`them_muc_tieu`, `doc_muc_tieu`) | `tai_chinh.py` + `muc-tieu.json` | ✔ B4 mở rộng sau |
| Danh mục khoản CSV | `rules/danh_muc_thu_chi.csv` | ✔ 7 mã hiện có |
| Tổng hợp tháng / danh mục / mục tiêu / P&L kênh | `tong_thang`, `tong_hop_danh_muc`, `tong_hop_muc_tieu`, `pnl_theo_kenh` | ✔ thêm chiều, không đổi chữ ký |
| Route + trang 4 tab | `src/main.py` `/finance*`, `templates/finance.html` | ✔ thay UI theo mockup |
| Cổng quyền `yeu_cau_finance` | `main.py` (cờ `finance` từ gateway) | ✔ xem mục 10 |
| Chấm công | `src/cham_cong.py` (`bang_cong_thang`, `chot_ky`) | ✔ **chỉ đọc** |
| Xếp loại KPI | `src/kpi_danh_gia.py` (`moi_nhat_theo_nguoi`) | ✔ **chỉ đọc** |
| Danh bạ kênh/ngách | `nen/common/danh_ba` | ✔ **chỉ đọc** |

**Sổ tiền đang rỗng** → thêm trường không cần migration. Đây là lý do đợt A đi trước.

## 1. Tệp dữ liệu sau đợt A + D

```
data/to-chuc/db/
  so-thu-chi/2026.jsonl          ĐÃ CÓ — thêm trường (mục 2)
  muc-tieu.json                  ĐÃ CÓ
  ty-gia/2026.jsonl              MỚI  A2 — chỉ-thêm, một dòng/ngày/cặp tiền
  dich-vu-tra-phi.json           MỚI  D2 — ghi nguyên tử tmp+os.replace
  bang-luong/2026-08.json        MỚI  D1 — bản duyệt, chỉ-thêm theo kỳ
  chung-tu/2026/<id bút toán>/   MỚI  A3 — kho tệp
apps/to-chuc/rules/
  danh_muc_thu_chi.csv           ĐÃ CÓ
  danh_muc_vi.csv                MỚI  A1
  ngay_nghi_le.csv               MỚI  D1
```

Mọi tệp mới khai trong `apps.json` `du_lieu`/`du_lieu_nen` (Luật 6). Sổ tiền, bảng
lương, chứng từ = quý **VÀNG, giữ vĩnh viễn** (luật Owner 16/08).

## 2. A1 + A2 + A3 — bút toán sau đợt A

```jsonc
{
  "id": "BT-260826-a1b2",
  "ngay": "2026-08-26",
  "loai": "thu | chi | dao",
  "danh_muc": "CHI-PROXY",
  "so_tien": 86.0,               // NGUYÊN TỆ, > 0 (âm chỉ dành cho dòng đảo)
  "tien_te": "USD",              // A2 — mặc định VND
  "ty_gia": 25920,               // A2 — VND cho 1 đơn vị nguyên tệ, CHỐT tại ngày ghi
  "nguon_ty_gia": "vcb_transfer",// vcb_transfer | vcb_sell | er_api | tay
  "vi": "payoneer",              // A1 — mã trong danh_muc_vi.csv
  "muc_tieu": "Nuôi kênh SPACE Q3",
  "kenh_ma": "K-COSMIC-DEPTH",   // "" = chung hệ
  "trang_thai_thu": "",          // B5 — "" | uoc_tinh | da_chot | da_ve_vi
  "chung_tu": "INV-2026-08-13",
  "tep_dinh_kem": ["hoa-don.jpg"],   // A3 — tên tệp trong chung-tu/<năm>/<id>/
  "nguoi_ghi": "lanne",
  "ghi_chu": "proxy 911 gói tháng",
  "tham_chieu": "",              // id gốc, chỉ dòng đảo
  "nguon": "tay",                // tay | thue_bao | quota | luong | adsense
  "tao_luc": "2026-08-26T10:11:00"
}
```

**`quy_vnd` KHÔNG lưu** — luôn tính `so_tien × ty_gia` để không có hai con số cãi nhau.
`ngach_ma` KHÔNG lưu — suy từ `kenh_ma` qua danh bạ, một nguồn sự thật.

### A1 — ví

`rules/danh_muc_vi.csv`: `ma,ten,loai,tien_te,ghi_chu`
(`loai` ∈ vi_dien_tu · ngan_hang · quy · phai_thu).

- `them_but_toan` thêm tham số `vi` — **bắt buộc**, giá trị lạ → `ValueError`.
- `so_du_vi() -> {ma: {nguyen_te, quy_vnd, but_toan_cuoi}}` — thu cộng, chi trừ,
  dòng đảo mang dấu sẵn.
- Ví `loai == "phai_thu"` **không** vào tổng khả dụng (AdSense chưa chi trả chưa là tiền).

### A2 — hai đồng tiền

Đồng vận hành: **VND**. Bút toán giữ nguyên tệ, quy đổi ở tầng đọc.

Nguồn tỷ giá (đo thật 26/08/2026, cả hai chạy được từ máy này):

| Nguồn | Đường | Trả về | Vai |
|---|---|---|---|
| Vietcombank | `https://www.vietcombank.com.vn/api/exchangerates?date=now` | USD `cash` 25.890 · `transfer` 25.920 · `sell` 26.300 | **chính** |
| ExchangeRate-API mở | `https://open.er-api.com/v6/latest/USD` | `rates.VND` 26.059,9 — không cần khóa, ngày một lần | dự phòng |

**Mặc định dùng `transfer` của VCB** — đó là giá ngân hàng MUA chuyển khoản, tức số
VND thực nhận khi bán USD từ Payoneer. Dùng `sell` sẽ thổi doanh thu lên ~1,5%.
Chi bằng USD sẵn có trong ví cũng theo `transfer` (giá trị thị trường của số USD đó).

- `ty_gia_ngay(ngay, tien_te="USD") -> {gia, nguon, lay_luc}` — đọc sổ
  `ty-gia/<năm>.jsonl` trước; chưa có thì gọi VCB, lỗi thì gọi er-api, lỗi nữa thì
  lấy **dòng gần nhất** kèm cờ `cu=True`.
- **Không bao giờ bịa**: mọi đường thất bại → trả `None`, form bắt nhập tay, nhãn ghi
  rõ nguồn. Tỷ giá đã chốt trên bút toán **không** cập nhật lại về sau.
- Timeout 8 giây, `LLM_RETRY`-style không retry ngầm (bài học 19/07 + 06/08).

### A3 — chứng từ

- `POST /finance/but-toan` nhận `tep` (nhiều tệp), lưu `chung-tu/<năm>/<id>/<tên đã dọn>`.
- Cho phép: jpg, jpeg, png, webp, pdf. Trần 10 MB/tệp, 5 tệp/bút toán.
- Tên tệp dọn theo khuôn đã có ở nhập liệu (bỏ ký tự lạ, giữ dấu tiếng Việt).
- `dao_but_toan` **kế thừa** `tep_dinh_kem` của dòng gốc (không sao chép tệp, dùng
  chung đường dẫn) — dấu vết không đứt.
- Route tải: `GET /finance/chung-tu/{id}/{ten}` — kiểm cờ `finance`, không thấy → 404 lặng lẽ.

### A4 — lọc và xuất

- `GET /finance?tab=ledger&...` nhận: `thang`, `tu`, `den`, `loai`, `vi`, `kenh`,
  `muc_tieu`, `danh_muc`, `q` (tìm trong ghi chú + chứng từ). Lọc **ở server**.
- `GET /finance/xuat.csv` — utf-8-sig cho Excel, cột như bảng đang xem, kèm cột quy VND.
- `GET /finance/xuat.beancount` — mỗi bút toán một transaction:

```
2026-08-26 * "proxy 911 gói tháng"
  chung-tu: "INV-2026-08-13"
  kenh: "K-COSMIC-DEPTH"
  muc-tieu: "Nuôi kênh SPACE Q3"
  Chi:Proxy       86.00 USD @ 25920 VND
  Vi:Payoneer    -86.00 USD @ 25920 VND
```

Bút toán đảo xuất thành transaction số âm có `tham-chieu`. Không cố dựng cây tài
khoản đầy đủ — mục tiêu là mở được bằng Fava, không phải đạt chuẩn kế toán kép.

## 3. D1 — bảng lương từ chấm công (Owner chốt vòng 3: 26/08)

### 3.1 Chấm công đo cái gì

Owner chốt: **chỉ đo giờ CÓ MẶT — mở CRM là tính**. Trong phiên làm gì không đo,
không quan tâm.

- **Ngày công** = ngày có ít nhất một lần mở CRM → `cham_cong.bang_cong_thang()`
  `so_ngay` **đã đếm đúng như vậy**, không phải sửa.
- `tong_giay` (thời lượng trong phiên) **không dùng** cho lương và không hiện trên
  bảng lương. Giữ trong code, đừng gỡ — nhịp tim và beacon vẫn chạy vô hại.
- **Đi muộn** = `vao` trễ hơn giờ chuẩn → chỉ **CẢNH BÁO**, xem D6.

### 3.2 Ngày công (nghỉ Chủ nhật)

```
ngày làm việc của tháng = số ngày trong tháng − số Chủ nhật − ngày lễ trong rules
```

Đo thử: 07/2026 = 27 · **08/2026 = 26** · 09/2026 = 26 · 10/2026 = 27 · 02/2026 = 24.
Con số đổi theo tháng → đơn giá ngày công cũng đổi. Lương cơ bản vẫn cố định theo
tháng (chuẩn VN), không nhân theo số ngày.

`rules/ngay_nghi_le.csv`: `ngay,ten,ghi_chu` — Owner tự thêm Tết, 30/4, 1/5, 2/9,
Giỗ tổ. Lễ rơi vào Chủ nhật **không trừ hai lần**.

### 3.3 Công thức — máy KHÔNG tự trừ gì

```
cong_chot(P)     = so_ngay trong kỳ (chấm công đã chốt)
he_so(P)         = rules/he_so_xep_loai.csv theo xếp loại A/B/C (mặc định 1,10 / 1,00 / 0,90)
de_nghi_chi(P)   = luong_co_ban(P) × he_so(P)  +  dieu_chinh_hr(P)
don_gia_ngay(P)  = de_nghi_chi(P) / cong_chot(P)      ← đầu vào của D3
```

**Khác bản trước:** bỏ hệ số `cong_chot / ngay_lam_viec` khỏi công thức. Owner chốt
**không trừ lương theo chấm công** — máy không được tự cắt tiền của ai vì một con số
đo hiện diện trên hệ công cụ.

`dieu_chinh_hr` là **ô HR nhập tay**: số tiền (âm hoặc dương) + **lý do bắt buộc**.
Đây là đường duy nhất để công vắng, đi muộn, thưởng nóng, phạt ảnh hưởng tới lương —
và nó luôn có tên người quyết đứng sau. Bảng hiện đủ ba cột nguồn để HR nhìn mà
quyết: ngày công · đi muộn · xếp loại.

`luong_co_ban` lấy từ hồ sơ IAM (trường mới `luong_co_ban`). Chưa có → dòng đó "—",
không đoán, không tính vào tổng.

### 3.4 Van chống bịa

- Công **chưa chốt** kỳ đó → bảng ở trạng thái *chưa chốt công*, nút duyệt khóa.
- Người **chưa có xếp loại** → `he_so` trống → `de_nghi_chi` = "—" kèm lý do. Duyệt
  được phần còn lại; người thiếu ghi bù bằng bút toán sau.
- Nguồn chấm công chết → "—" kèm lý do, không 0 giả.

### 3.5 Duyệt và ghi sổ

`POST /finance/luong/duyet` → ghi `bang-luong/<kỳ>.json` (chỉ-thêm: `nguoi_duyet`,
`luc`, toàn bộ dòng kèm `dieu_chinh_hr` và lý do) **rồi** sinh một bút toán
`CHI-LUONG` cho mỗi người (`nguon: "luong"`). Duyệt hai lần cùng kỳ → chặn.

**Ranh giới cần Owner xác nhận** (spec tạm để như sau): HR **lập và xuất** bảng lương
+ phiếu lương; **duyệt chi tiền** vẫn là Owner, vì bước đó sinh bút toán vào sổ tiền.

## 3b. D5 — phiếu lương kèm báo cáo hiệu suất (HR xuất và gửi)

Owner chốt: *"Xuất ra phiếu lương kèm báo cáo hiệu suất cụ thể của nhân sự và HR là
người xuất và gửi."*

Một phiếu / người / kỳ, gồm:

| Khối | Nội dung | Nguồn |
|---|---|---|
| Định danh | mã NS, họ tên, bộ phận, vị trí, kỳ | IAM |
| Công | ngày công / ngày làm việc của tháng, ngày vắng | `cham_cong` |
| Đi muộn | số buổi, tổng phút — **ghi chú rõ: không trừ lương** | D6 |
| Hiệu suất | xếp loại + nhận xét người chấm; các chỉ tiêu có số (video đúng lịch, kịch bản hoàn thành, báo cáo) | `kpi_danh_gia` + `kpi.py` 4 nguồn |
| Ngách đã tham gia | ngách + ngày công từng ngách | D3 |
| Lương | cơ bản · hệ số · điều chỉnh HR (kèm lý do) · **thực nhận** | D1 |

- `GET /finance/luong/phieu/{ky}/{ma_ns}` → **trang HTML in được** (khổ A4, CSS
  `@media print`), Ctrl+P ra PDF.
  **Không dùng WeasyPrint** — máy Windows này thiếu GTK, 3 test `test_remake_dep`
  fail vì đúng lý do đó từ 29/07. Đừng rước lại.
- `GET /finance/luong/phieu.zip?ky=` → gói toàn kỳ cho HR tải một lần.
- **Gửi**: giai đoạn này HR tải rồi tự gửi (Google Workspace đã có). Gửi thẳng bằng
  SMTP là việc sau, và cần Owner cấp tài khoản gửi — chưa làm thì đừng vẽ nút.
- Chỉ xuất phiếu của kỳ **đã duyệt**. Kỳ chưa duyệt → nút khóa, không có phiếu nháp
  trôi ra ngoài.

## 3c. D6 — cảnh báo đi muộn (không dính tới lương)

`rules/gio_lam_viec.csv`: `bo_phan,gio_vao,dung_sai_phut` — mặc định `*,08:30,10`.
**Owner cần xác nhận giờ vào chuẩn.**

```
di_muon(P, ngày) = vao > gio_vao + dung_sai_phut
di_muon_thang(P) = {so_buoi, tong_phut, chi_tiet: [{ngay, vao, tre_phut}]}
```

- Hiện ở HR Hub và trên phiếu lương, **không** vào công thức lương.
- Ngày không có `vao` → **không** tính đi muộn (vắng khác muộn, đừng gộp).
- Ngưỡng nhắc: quá `N` buổi/tháng thì HR thấy cờ vàng (mặc định 5, để trong rules).
- Câu chữ trên UI phải nói thẳng: *"đo bằng lần mở CRM đầu ngày — làm việc ngoài hệ
  không được ghi nhận"*. Van trung thực của chấm công vẫn nguyên.

## 4. D2 — dịch vụ trả phí (gộp C1)

`dich-vu-tra-phi.json` — danh sách:

```jsonc
{
  "id": "DV-a1b2",
  "ten": "Proxy 911", "nha_cung_cap": "911proxy.com",
  "nhom": "proxy",                 // proxy | api | cong_cu | email | khac
  "phi": 86, "tien_te": "USD",
  "chu_ky": "thang",               // thang | quy | nam | mot_lan
  "ngay_gia_han": "2026-09-13",
  "tu_dong_gia_han": true,
  "trang_thai": "dang_dung",       // dang_dung | sap_bo | da_huy
  "danh_muc": "CHI-PROXY",         // mã khoản dùng khi ghi bút toán
  "vi": "payoneer",
  "kenh_ma": "K-COSMIC-DEPTH",     // "" = chung hệ
  "vault_id": "3f9a1c22",          // CHỈ id trỏ sang Vault — không tài khoản, không mật khẩu
  "ghi_chu": "", "tao_luc": "...", "sua_luc": "..."
}
```

- **Không có trường mật khẩu, và không được thêm.** Vault giữ bí mật; Finance giữ lịch.
  Cột "Đăng nhập" trên UI chỉ render đường dẫn `/vault#<vault_id>` khi người xem là Owner.
- `den_han(trong_bao_nhieu_ngay=14)` → hàng chờ trên Tổng quan. Quá hạn mà chưa ghi →
  đánh dấu đỏ, **không tự ghi bút toán**.
- Ghi từ hàng chờ: mở form bút toán điền sẵn (`nguon: "thue_bao"`, tham chiếu `id`),
  người bấm Lưu mới vào sổ. Ghi xong đẩy `ngay_gia_han` lên chu kỳ kế tiếp.
- `trang_thai = "sap_bo"` là **quyết định cắt chi**: hiện trên Tổng quan kèm số tiền
  tiết kiệm/tháng. App **không** tự hủy dịch vụ — hủy là việc tay ở trang nhà cung cấp.
- `chi_phi_thue_bao_thang()` quy mọi chu kỳ về tháng (năm ÷ 12, quý ÷ 3) cho B3.

## 5. D3 — chi phí sản xuất theo ngách

Nguồn (chỉ đọc, Luật 4): `data/plannery/plan.json` — `projects[].ngach_ma`,
`projects[].channels[].kenh_ma`, `assignments[] = {person_id, project_id}`,
`people[].id = "ns_<mã NS>"`.

```
ngay_cong(P, N) = cong_chot(P) × tỷ_trọng(P → N)

tỷ_trọng mặc định  = 1 / (số ngách P được phân công)
tỷ_trọng nâng cấp  = số video của P trong ngách N / tổng video của P trong kỳ
                     (dùng NGAY khi PlannerY có video gắn tên — dữ liệu chính xác
                      hơn thắng, Owner đã đồng ý không hỏi lại)

chi_phi_nhan_cong(N) = Σ ngay_cong(P, N) × don_gia_ngay(P)     ← don_gia_ngay từ D1
chi_phi_san_xuat(N)  = chi_phi_nhan_cong(N) + chi tiền mặt của các kênh thuộc N
```

Ràng buộc:
- Chỉ tính người có lương **đã duyệt** trong kỳ. Chưa duyệt → ô ghi *lương chưa duyệt*.
- Người không có phân công nào → ngày công vào hàng **"chưa phân công"**, không rải đều.
- PlannerY chết → cả khối báo "không đọc được phân công", không suy từ trí nhớ.
- Tổng cột nhân công **phải bằng** tổng bảng lương đã duyệt — có test ghim đẳng thức này.

Kết quả thành một quy tắc phân bổ mới của B1: `"theo ngày công"`.

## 6. D4 — lịch tài chính

`rules/lich_tai_chinh.csv`: `ma,ngay_trong_thang,ten,phu_thuoc`

| Mã | Ngày | Việc | Khóa bởi |
|---|---|---|---|
| `doi_soat` | 10–12 | Nạp CSV chi trả AdSense của tháng trước | — |
| `chot_ky` | sau đối soát | Đối chiếu số dư ví → chốt kỳ | `doi_soat` xong |
| `tra_luong` | 15 | Duyệt bảng lương kỳ trước → bút toán CHI-LUONG | công đã chốt |

- Kỳ kế toán **vẫn là tháng dương lịch** — chỉ lịch việc theo mốc này.
- `trang_thai_moc(thang) -> [{ma, han, trang_thai, khoa_vi}]`; `trang_thai` ∈
  cho_den_han · den_han · tre_han · xong.
- Trễ hạn thì **nhắc**, không tự chạy. Không mốc nào tự sinh bút toán.

## 7. Route

| Method | Đường | Quyền | Việc |
|---|---|---|---|
| GET | `/finance` | cờ `finance` | 8 tab theo mockup v3 |
| POST | `/finance/but-toan` | cờ `finance` | ghi bút toán (kèm tệp) |
| POST | `/finance/dao` | cờ `finance` | bút toán đảo |
| POST | `/finance/muc-tieu` | cờ `finance` | thêm mục tiêu |
| GET | `/finance/chung-tu/{id}/{ten}` | cờ `finance` | tải chứng từ |
| GET | `/finance/xuat.csv` · `/finance/xuat.beancount` | cờ `finance` | xuất |
| GET/POST | `/finance/dich-vu` · `/finance/dich-vu/{id}` | cờ `finance` | D2 |
| GET | `/finance/luong` | **xem mục 10** | D1 bảng đề nghị |
| POST | `/finance/luong/duyet` | **chỉ Owner** | duyệt + sinh bút toán |
| POST | `/finance/ty-gia/lay` | cờ `finance` | gọi VCB, ghi sổ tỷ giá |
| POST | `/finance/chot-ky` | **chỉ Owner** | C5 (đợt sau) |

## 8. Test bắt buộc (mỗi mục ít nhất một test)

1. Bút toán thiếu `vi` hoặc ví lạ → 422/`ValueError`.
2. Ví `phai_thu` không vào tổng khả dụng.
3. Tỷ giá: mọi nguồn chết → `None`, **không** sinh số; tỷ giá đã chốt không đổi khi
   sổ tỷ giá thay đổi về sau.
4. Bút toán đảo kế thừa `tep_dinh_kem`.
5. Xuất `.beancount` parse được (`beancount.loader` nếu có, không thì so khuôn dòng).
6. Ngày làm việc: 08/2026 = 26; lễ trùng Chủ nhật không trừ hai lần.
7. Lương: công chưa chốt → khóa duyệt; người thiếu xếp loại → "—" và không vào tổng;
   duyệt hai lần cùng kỳ → chặn.
8. **Tổng nhân công D3 = tổng bảng lương đã duyệt** (đẳng thức ghim).
9. Người không phân công → ngày công vào "chưa phân công", không rải cho ngách.
10. PlannerY chết → khối D3 báo thiếu nguồn, không dựng số.
11. D2: ghi từ hàng chờ đẩy `ngay_gia_han` đúng chu kỳ; `sap_bo` vào bảng tiết kiệm.
12. Không route nào của Finance trả về trường mật khẩu của Vault (test quét khóa).

## 9. Thứ tự commit

1. `A1` ví — CSV + trường `vi` + `so_du_vi` + tab Ví.
2. `A2` tiền tệ — trường + sổ tỷ giá + nguồn VCB/er-api + quy đổi ở tầng đọc.
3. `A3` chứng từ — kho tệp + tải + kế thừa khi đảo.
4. `A4` lọc + xuất CSV + xuất beancount.
5. `D2` dịch vụ trả phí (gộp C1) — sổ tự đầy từ đây.
6. `D1` bảng lương — ngày công, hệ số, duyệt, bút toán.
7. `D3` chi phí ngách — cần đơn giá của D1.
8. `D4` lịch tài chính + khóa phụ thuộc.

Mỗi bước: `pytest` xanh trước khi commit; UI bám mockup đã chốt, không tự chế thêm.

## 10. Quyền (Owner chốt vòng 3: 26/08)

Owner chốt: **quyền xem và sửa Finance thuộc HR và nhân sự bộ phận Tài chính** — bộ
phận này mới có 2 người, cơ cấu phình to thì tính lại.

| Ai | Vào Finance | Tab Lương | Duyệt chi lương | Vault |
|---|---|---|---|---|
| Owner | ✔ | ✔ | ✔ | ✔ |
| Giỏ `ke_toan` (Kế toán L2+) | ✔ | ✔ | ✖ | ✖ |
| Giỏ `nhan_su` (HR L3+) | ✔ | ✔ **+ xuất/gửi phiếu** | ✖ | ✖ |
| Còn lại | ✖ | ✖ | ✖ | ✖ |

Thi công: `_gio_chuc_nang` ở gateway phát cờ `finance` **thêm vế `nhan_su`** — HR có
giỏ nhân sự thì cũng có cờ Finance. **Không** đẻ giỏ mới `finance_luong` (đề xuất
tách ba mức của vòng trước **bỏ** — cơ cấu 2 người không cần).

Giữ nguyên: kiểm quyền **ở server** chứ không ẩn nút · Manager không bao giờ ngang
Owner (luật 04–05/08) · tab không có quyền thì gõ `?tab=luong` tay cũng bị ép về tab
đầu · đường sang Vault chỉ render cho Owner.

**Còn treo:** nhân viên xem phiếu lương của chính mình — Owner chưa nói. Hiện HR gửi
phiếu, nên chưa cần route `/toi/luong`. Làm khi Owner yêu cầu, đừng làm nửa vời.

## 11. Dashboard (Owner đồng ý vòng 3)

Thư viện: **frappe-charts 1.6.2** (MIT, SVG thuần, ~68KB) — vendor riêng vào
`apps/to-chuc/src/static/vendor/` kèm `NGUON.md` như Tasky đã làm. Không CDN: máy
nhân viên trong LAN thường không ra Internet.

**Bẫy đã ghi ở Tasky, đừng dẫm lại:** thư viện vẽ bằng màu **truyền vào JS**, không
đọc CSS var → đổi theme sáng/tối phải đọc token rồi **vẽ lại** (khuôn `ve()` +
`mau()` trong `apps/tasky/src/templates/bao_cao.html`). Quên gọi lại là biểu đồ giữ
màu theme cũ.

| Biểu đồ | Dạng | Nguồn |
|---|---|---|
| Dòng tiền 12 tháng | cột thu/chi + đường ròng | `tong_thang` từng tháng |
| Số dư ví theo tháng | đường | `so_du_vi` cộng dồn |
| Cơ cấu chi tháng này | cột ngang | `tong_hop_danh_muc` |
| Lãi/lỗ theo kênh sau phân bổ | cột, top 10 | B1 |
| Chi phí theo ngách | cột chồng nhân công ‖ tiền mặt | D3 |
| Thuê bao theo nhóm | cột ngang | D2 |

Chưa có dữ liệu → ghi "chưa có dữ liệu", **không vẽ trục rỗng** trông như đã đo.
