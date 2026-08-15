# Yêu cầu code — Nâng logic phân tích module chẩn đoán

> Dán từng GIAI ĐOẠN vào Claude Code. KHÔNG làm cả 5 giai đoạn một lần — mỗi giai đoạn là
> 1 commit riêng, có test riêng, chạy kiểm chứng trên report thật rồi mới sang giai đoạn sau.
> Nền tảng phương pháp: đọc `analytic_methodology.md` ở thư mục gốc `AI AGENT/` trước khi code.
>
> **Bối cảnh code hiện tại** (đã đọc `src/diagnosis_engine.py`): engine chấm luật bằng `_khop`
> (eval biểu thức) trên MỘT hàng số liệu + baseline MỘT lớp (`_tinh_baseline` = median toàn kênh,
> bỏ dòng Total). Có `chan_doan_video`, `chan_doan_kenh`, `liet_ke_video`, tầng phiên dịch
> `ap_anh_xa_cot` qua `rules/column_mapping.csv`. Engine hiện là "máy dò triệu chứng": trả
> `matched` + `tang_vo`. Nhiệm vụ chung: nâng thành "máy ra phán quyết" mà KHÔNG phá 20 luật cũ.
>
> **Nguyên tắc bất biến (giữ nguyên tinh thần dự án):**
> - Luật vẫn nằm NGOÀI code (CSV). Không hard-code luật vào .py.
> - Van chống bịa: thiếu dữ liệu → nói "chưa đủ dữ liệu", KHÔNG đoán.
> - Tách UI khỏi logic: mọi thứ dưới đây là logic thuần trong engine, không đụng template.
> - Mỗi hàm mới có test. Chạy `pytest` xanh trước khi commit.

---

## GIAI ĐOẠN 1 — Nền thống kê: lọc mẫu nhỏ + phân nhóm (làm TRƯỚC, mọi thứ sau gọi nó)

**Mục tiêu:** dựng hai hàm tiện ích mà các giai đoạn sau đều dùng. Chưa đổi hành vi chẩn đoán.

**Việc 1.1 — Cột phái sinh cần có sẵn trước khi phân nhóm.**
Trong `ap_anh_xa_cot` (hoặc một hàm hậu xử lý ngay sau nó), bổ sung tính các cột phái sinh nếu
nguyên liệu có mặt, đặt tên biến luật rõ ràng:
- `duration_min` = `duration_sec` / 60 (report có cột Duration tính bằng giây).
- `tuoi_video_ngay` = số ngày từ `Video publish time` đến ngày chạy report. Ngày chạy: lấy
  max ngày trong Chart/Totals nếu có, KHÔNG có thì cho truyền vào tham số `ngay_chay` (mặc định
  None → bỏ qua cột tuổi, không lỗi). Parse `Video publish time` dạng "Mar 25, 2026".
- `returning_ratio` = `returning_viewers` / (`new_viewers` + `returning_viewers`) khi mẫu số > 0.
Cột nào thiếu nguyên liệu thì BỎ QUA (không tạo, không lỗi) — giữ đúng phong cách hiện tại.

**Việc 1.2 — Hàm phân nhóm.**
```
def phan_nhom_do_dai(df) -> pd.Series   # nhãn: "ngắn"(<8ph) / "vừa"(8-15ph) / "dài"(>15ph)
def phan_nhom_tuoi(df) -> pd.Series     # nhãn: "mới"(<7 ngày) / "đang chạy"(7-30) / "đuôi dài"(>30)
```
Các ngưỡng cắt nhóm để trong hằng số đầu file (dễ sửa), KHÔNG rải rác. Nhóm không tính được
(thiếu cột) → trả nhãn "khong_ro" cho hàng đó.

**Việc 1.3 — Ngưỡng cỡ mẫu (van chống bịa cho số liệu).**
Thêm hằng số `MIN_VIEW_KET_LUAN` NHƯNG tính ĐỘNG: một video chỉ được kết luận về retention/CTR
nếu `views >= max(NGUONG_SAN, TY_LE_MEDIAN * median_views_kenh)`. Đặt `NGUONG_SAN=100`,
`TY_LE_MEDIAN=0.1` làm mặc định (đưa lên đầu file để chỉnh). Viết:
```
def du_mau_ket_luan(views, median_views_kenh) -> bool
```
Video KHÔNG đủ mẫu: các giai đoạn sau sẽ gán trạng thái "chưa đủ dữ liệu" thay vì chấm luật.

**Nghiệm thu GĐ1:** viết test cho 3 hàm trên bằng dữ liệu nhỏ tự tạo (không cần report thật):
phân nhóm đúng nhãn, `du_mau_ket_luan` chặn đúng video ít view, cột phái sinh tính đúng khi đủ
nguyên liệu và bỏ qua khi thiếu. `pytest` xanh. Commit: "GĐ1 nền thống kê: cột phái sinh + phân
nhóm độ dài/tuổi + ngưỡng cỡ mẫu động".

---

## GIAI ĐOẠN 2 — Baseline 3 lớp (thay 1 lớp hiện tại) + nguyên tắc lùi

**Mục tiêu:** thay `_tinh_baseline` một-lớp bằng baseline nhiều lớp có fallback.

**Việc 2.1 — Hàm baseline 3 lớp.**
```
def tinh_baseline_3_lop(df_video_so, nhom_do_dai, nhom_tuoi) -> dict
```
Trả cấu trúc:
```
{
  "toan_kenh": {<bien>: median, ...},
  "theo_do_dai": {"ngắn": {...}, "vừa": {...}, "dài": {...}},
  "theo_tuoi":   {"mới": {...}, "đang chạy": {...}, "đuôi dài": {...}},
}
```
Mỗi ô là median các video thuộc nhóm đó. Nhóm dưới `MIN_DONG_NHOM` (đặt =5) video thì ô đó
để `None` — KHÔNG tính median không đáng tin.

**Việc 2.2 — Hàm chọn baseline với nguyên tắc lùi.**
```
def chon_baseline(bien, nhan_do_dai, nhan_tuoi, muc_dich, baseline_3_lop) -> tuple[float|None, str]
```
Trả `(gia_tri_baseline, nguon_baseline_da_dung)`. `muc_dich` ∈ {"format","tang_truong","chien_luoc"}
quyết định thử lớp nào TRƯỚC (format→theo_do_dai, tang_truong→theo_tuoi, chien_luoc→toan_kenh).
Nếu lớp ưu tiên là None (thiếu mẫu) → LÙI xuống toan_kenh và ghi nguồn đã dùng (vd "lùi: toàn kênh").
`nguon_baseline_da_dung` PHẢI trả về để tầng trên khai báo minh bạch cho user.

**Việc 2.3 — Giữ tương thích ngược.**
`chan_doan`, `chan_doan_video`, `chan_doan_kenh` cũ vẫn phải chạy (20 luật cũ dùng `<bien>_baseline`
= median toàn kênh). Cách an toàn: baseline toàn-kênh trong cấu trúc mới CHÍNH LÀ cái cũ → map
`<bien>_baseline` = `baseline_3_lop["toan_kenh"][bien]` khi chấm luật cũ. KHÔNG được làm 20 luật cũ đổi kết quả.

**Nghiệm thu GĐ2:** test baseline 3 lớp trên dữ liệu tự tạo (nhóm đủ mẫu ra median đúng, nhóm
thiếu mẫu ra None + lùi đúng lớp). Test hồi quy: chạy `chan_doan_video` trên report thật, so
`matched`/`tang_vo` GIỐNG trước GĐ2 (20 luật cũ không đổi). Commit: "GĐ2 baseline 3 lớp + nguyên
tắc lùi, giữ tương thích 20 luật cũ".

---

## GIAI ĐOẠN 3 — Bốn trục chấm điểm (mỗi trục 1 hàm, trả trạng thái)

**Mục tiêu:** viết 4 hàm chấm độc lập, mỗi hàm nhận 1 video + baseline_3_lop, trả trạng thái
chuẩn hóa. CHƯA tổng hợp (GĐ4 lo). Trạng thái chuẩn: `"✓"` / `"⚠"` / `"✗"` / `"?"` (chưa đủ dữ liệu).

Mỗi hàm trả dict: `{"trang_thai": "...", "ly_do": "câu ngắn", "so_lieu": {...dùng để giải thích}}`.

**Việc 3.1 — Trục CTR × Retention × AVD** (`cham_truc_noi_dung`):
- Nếu `du_mau_ket_luan` = False → trả `"?"` ngay, không chấm.
- CTR so baseline format; Retention so baseline format; AVD 2 vai:
  (a) `avd_du_day` = AVD so baseline AVD toàn kênh (đủ để YouTube đẩy không).
  (b) `goi_y_do_dai`: nếu Retention CAO (≥ baseline) NHƯNG AVD THẤP → "nên làm dài hơn";
      nếu Retention THẤP NHƯNG AVD cao (video dài lê thê) → "nên cắt ngắn".
- **CHỐNG ĐẾM TRÙNG:** khi tổng điểm trục này, Retention và `avd_du_day` KHÔNG được cộng như 2
  bằng chứng độc lập. Quy tắc: Retention quyết trạng thái CHÍNH của trục; AVD chỉ nâng/hạ 1 bậc
  hoặc thêm gợi ý độ dài, KHÔNG tự tạo 1 phiếu ✗ riêng khi đã trùng hướng với Retention.
- `ly_do` phải nêu rõ bệnh: "bao bì yếu" (CTR thấp+Ret ổn) / "giật tít" (CTR cao+Ret thấp) /
  "nội dung lê thê" (Ret rất thấp) / "khỏe" — dùng lại tinh thần luật YT-01/02/04/09 cũ.

**Việc 3.2 — Trục Tiền** (`cham_truc_tien`):
- RPM so baseline toàn kênh. Trạng thái theo RPM: cao/thường/đáy.
- Tính tỷ lệ phễu tiền nếu đủ cột: `monetized_playbacks / views`, `revenue / views`. Cờ rò rỉ
  nếu tỷ lệ thấp bất thường so baseline.
- Cờ "đòn bẩy bỏ trống": `endscreen_ctr` hoặc `card_ctr` = 0 hoặc rất thấp → ghi vào `ly_do`
  ("tiền để trên bàn: chưa dùng end screen").

**Việc 3.3 — Trục Danh mục** (`cham_truc_danh_muc`): chấm ở cấp VIDEO trong bối cảnh kênh:
- Video có nằm trong nhóm "gánh kênh" (top theo view) hay "đuôi"?
- `returning_ratio` của video so baseline — video này kéo khán giả quay lại hay chỉ người lạ?

**Việc 3.4 — Trục Công thức** (`cham_truc_cong_thuc`):
- Video thuộc nhóm độ dài/thời điểm đăng nào, và nhóm đó có phải nhóm THẮNG của kênh không
  (so hiệu quả trung bình nhóm với toàn kênh).

**Nghiệm thu GĐ3:** test mỗi trục trên report thật, in ra trạng thái 4 trục cho vài video đã
biết tính chất (video 66% view; video giật-tít CTR cao ret thấp; video ít view phải ra "?").
KIỂM BẰNG MẮT kết quả có đúng trực giác không. Commit từng trục hoặc gộp: "GĐ3 bốn trục chấm điểm".

---

## GIAI ĐOẠN 4 — Tầng tổng hợp: 4 trạng thái → 1 phán quyết hữu hạn

**Mục tiêu:** hàm đọc 4 trạng thái trục → 1 phán quyết trong tập HỮU HẠN.

```
PHAN_QUYET = ["nhan_ban", "giu", "sua_bao_bi", "sua_noi_dung", "doi_ngach_vi_tien", "bo", "chua_du_du_lieu"]

def tong_hop_phan_quyet(truc_noi_dung, truc_tien, truc_danh_muc, truc_cong_thuc) -> dict
```
Trả `{"phan_quyet": <1 trong tập trên>, "giai_thich": "câu analyst", "the_diem": {4 trục}, "baseline_da_dung": {...}}`.

**Luật tổng hợp (bảng quyết định, để trong CSV `rules/phan_quyet.csv` nếu làm được — giữ tinh
thần luật-ngoài-code; nếu quá phức tạp cho CSV thì code trong .py NHƯNG comment rõ từng nhánh):**
- Bất kỳ trục CHÍNH nào = "?" và không đủ mẫu → `chua_du_du_lieu` (van chống bịa, KHÔNG đoán).
- 4 trục đều ✓ → `nhan_ban` (đây là công thức thắng, làm thêm).
- Nội dung ✓, Tiền ✗ (RPM đáy) → `doi_ngach_vi_tien` — CHÍNH LÀ ví dụ then chốt: "giỏi kéo view
  rẻ tiền, đừng nhân bản format này cho mục tiêu doanh thu".
- CTR ✗ mà Retention ✓ → `sua_bao_bi`. Retention ✗ → `sua_noi_dung`.
- Phần lớn ✗ → `bo`. Còn lại → `giu`.
`giai_thich` PHẢI là câu tổng hợp cả 4 góc như analyst, KHÔNG chỉ nêu 1 trục.

**Việc 4.2 — Hàm mới cấp kênh** `chan_doan_toan_bo(df, ngay_chay=None)`:
chạy 4 trục + tổng hợp cho MỌI video, trả list thẻ điểm + phán quyết, KÈM tổng quan danh mục
cấp kênh (Pareto top1/top3 %, tỷ lệ new/returning trung bình kênh, nhóm độ dài thắng nhất).
Đây là hàm UI sẽ gọi. KHÔNG gọi LLM ở đây (giữ nguyên nguyên tắc: LLM chỉ diễn giải, gọi riêng
từng video khi user bấm — như route `/chan-doan/video` hiện có).

**Nghiệm thu GĐ4:** test bảng quyết định phủ mọi nhánh phán quyết. Chạy `chan_doan_toan_bo` trên
report thật, in phán quyết 80 video — kiểm mắt: video 66%-view ra phán quyết hợp lý, video ít
view ra `chua_du_du_lieu`, có ít nhất 1 video ra `doi_ngach_vi_tien` nếu tồn tại. Commit: "GĐ4
tầng tổng hợp 4 trục → phán quyết + hàm chẩn đoán toàn bộ cấp kênh".

---

## GIAI ĐOẠN 5 — Chiều thời gian (LÀM SAU, khi có ≥2 report kỳ rời)

**Chưa làm ngay nếu chưa có 2 report kỳ không chồng lấn.** Khi làm:
```
def so_sanh_ky(df_ky_nay, df_ky_truoc) -> dict
```
- CHẶN nếu 2 kỳ chồng lấn hoặc khác độ dài (nhận `khoang_ngay` mỗi kỳ, kiểm tra không giao nhau).
  Chồng lấn → raise/trả cảnh báo rõ "2 kỳ chồng lấn, không so được, hãy xuất kỳ rời nhau".
- So delta các chỉ số CÙNG video giữa 2 kỳ (join theo Content id). Báo video đang lên/xuống.
- Nối vào lịch sử báo cáo Tầng 1 (`bao_cao_lich_su.py`) đã lưu file gốc → chạy lại được trên report cũ.

**Nghiệm thu GĐ5:** test chặn đúng khi kỳ chồng lấn; test delta đúng trên 2 kỳ giả rời nhau.

---

## Lưu ý cho Claude Code khi làm

- ĐỌC `analytic_methodology.md` trước — nó giải thích VÌ SAO mỗi quyết định, tránh làm sai tinh thần.
- Mỗi giai đoạn 1 commit, message có "vì sao", `pytest` xanh trước commit. Đừng gộp 5 giai đoạn.
- Sau mỗi giai đoạn, in kết quả trên REPORT THẬT và để user kiểm mắt — test xanh ≠ chạy đúng.
- KHÔNG phá 20 luật YT cũ (test hồi quy ở GĐ2). KHÔNG hard-code luật vào .py. Giữ luật trong CSV.
- Nếu một mục thấy "luật chồng luật" (thêm luật mà không đổi được quyết định nào) → BỎ, hỏi lại user.
