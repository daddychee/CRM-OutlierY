# Outlier Method v3 — bản đã đồng kiểm (CONVERGED)

> Trạng thái: **VERIFIED ở mức thiết kế** qua 3 vòng Builder/Auditor (xem `dong_kiem_log.md`).
> "VERIFIED" = nhất quán nội bộ, không còn REFUTE chưa xử lý, mọi giới hạn không thể xoá được ghi rõ ở §R.
> KHÔNG đồng nghĩa "đã chứng minh bằng dữ liệu thật" — việc đó cần một scan thật và lý tưởng là hai model độc lập (xem §R-0).
> Bản này thay thế v2. Khác biệt so với v2 nằm ở các mục đánh dấu **[R2]/[R3]** và ở §R (Residuals).

---

## 0. Công thức lõi (giữ từ v2)

```
OX_v3 = view thực tế ÷ view KỲ VỌNG ở-cùng-độ-tuổi, cửa sổ gần đây, leave-one-out
expected = scale_channel × shape(age)
```

Ràng buộc dữ liệu: API chỉ cho **view tích lũy hiện tại + tuổi**, không cho đường cong theo thời gian. Mọi hiệu chỉnh tuổi là **cross-sectional**, kéo theo giới hạn định danh APC ở §R-1.

---

## 1. Đường cong trưởng thành — phiên bản đã giới hạn cohort **[R2, vá A1]**

**Vấn đề Auditor nêu (A1):** pool video mọi tuổi để dựng `shape(age)` trộn lẫn hiệu ứng **tuổi / cohort / period** — không tách được từ một snapshot. Đây là bài toán age–period–cohort, vô định nếu không có giả định.

**Cách v3 thu hẹp (không tuyên xoá):**
1. **Khai báo giả định công khai (APC-A):** *trong* `RECENT_WINDOW_MONTHS`, hiệu ứng period & cohort đủ nhỏ để bỏ qua so với hiệu ứng tuổi. Mọi kết quả OX phụ thuộc giả định này — nó được in trên đầu report.
2. **Ước lượng `shape(age)` CHỈ từ video trong cửa sổ gần đây**, không từ toàn lịch sử. Các video trong cửa sổ cùng một thời kỳ ⇒ cohort gần nhau ⇒ thành phần cohort gần như triệt tiêu. Đổi lại bucket tuổi-lớn ít mẫu hơn (xem A3-residual §R-2).
3. **Phạm vi chấm điểm có giới hạn:** chỉ video **trong cửa sổ ∧ đã trưởng thành** nhận `OX` chính thức (`scope=primary`). Video cũ hơn cửa sổ nhận `OX_legacy` với cờ `scope=legacy, confidence=low` — không dùng cho pattern/đề xuất.
4. **Diagnostic period (D-PERIOD):** so `shape(age)` ước lượng trong-cửa-sổ với `shape(age)` ước lượng trên toàn lịch sử. Lệch > 25% ở bất kỳ bucket nào ⇒ cờ `period_effect=true`, cảnh báo giả định APC-A đang yếu ở niche này.

Kết quả: claim không còn là "đã hiệu chỉnh tuổi" mà là **"OX hợp lệ cho video trong cửa sổ trưởng thành, dưới giả định APC-A có diagnostic kiểm tra"**. Đây là claim Auditor CONFIRM được vì nó đúng phạm vi.

---

## 2. Cửa sổ gần đây + fallback kênh đăng thưa **[R2, vá A6]**

`scale_channel` & baseline tính từ video trong `RECENT_WINDOW_MONTHS` (mặc định 18) ∧ đã trưởng thành (≥ `MATURITY_DAYS`).

**Fallback khi giao hai điều kiện cạn (< `MIN_BASE_VIDEOS`):**
1. Nới cửa sổ theo bậc: 18 → 24 → 36 tháng.
2. Vẫn thiếu ⇒ mượn `shape(age)` cấp niche, lấy scale = **trimmed median toàn-thời của kênh**, gắn cờ `scale_borrowed=true, confidence=low`.
3. Vẫn không đủ video bất kỳ ⇒ kênh `unscored`, loại khỏi pattern.

Cờ quỹ đạo `trend=up/down` khi median 6 tháng gần nhất lệch > ±40% so với 6 tháng trước.

---

## 3. Leave-one-out + trim đỉnh (giữ từ v2)

Khi tính `scale_channel` cho video X: loại X (LOO) và cắt top decile (`TRIM_TOP_FRAC=0.10`). Một cụm hit không tự nâng baseline che lấp chính nó.

---

## 4. Floor PER-CHANNEL, hết lệch theo size **[R2, vá A7]**

**Vấn đề Auditor nêu (A7):** floor theo P25 *niche* vẫn bị vài kênh khổng lồ kéo lên, loại oan outlier kênh nhỏ.

**v3:**
- `MIN_ABS_VIEWS(kênh) = max(2.000, P25 view-trưởng-thành CỦA CHÍNH KÊNH ĐÓ)` — floor riêng từng kênh, không còn nhiễm chéo theo size.
- `MIN_BASE_VIEWS = 0.2 × median baseline của kênh` (cũng nội bộ kênh).
- Kênh có quá ít video để tính P25 ổn định ⇒ floor lùi về hằng 2.000 + cờ `floor_fallback=true, confidence≤medium`.
- Mọi floor đã tính được **in ra report**.

---

## 5. Bất định OX — phương pháp theo cỡ mẫu **[R2, vá A3]**

**Vấn đề Auditor nêu (A3):** bootstrap median ở n≈8 không tin cậy (phân phối rời rạc).

**v3 — chọn theo `n_base`:**
- `n_base ≥ 20`: bootstrap CI 90% (đáng tin ở cỡ này).
- `12 ≤ n_base < 20`: CI hạng phân-phối-tự-do (rank-based) thay bootstrap.
- `n_base < 12`: **không** báo CI giả; thay bằng **jackknife sensitivity** — bỏ lần lượt từng điểm baseline, ghi khoảng dao động OX; kèm cờ `confidence=low`.
- Bracket (2/5/10×) **không thăng hạng** nếu CI/khoảng jackknife vắt ranh giới ⇒ ghi `tentative`.

---

## 6. Keyword bằng LIFT + hiệu chỉnh đa kiểm định **[R2, vá A2]**

```
lift(word) = P(word | outlier) ÷ P(word | non-outlier)
```
- Cổng: ≥ `MIN_KW_COUNT`=5 lần trong nhóm outlier ∧ ≥ `MIN_KW_CHANNELS`=3 kênh.
- Kiểm định Fisher exact cho mỗi từ, **sau đó hiệu chỉnh Benjamini–Hochberg (FDR q=0.10)** trên toàn bộ từ test — chỉ giữ từ qua FDR. Điều này chặn dương-tính-giả do test hàng trăm từ ở p<0,05.
- **Caveat bắt buộc in report:** OX cao có thể do thumbnail / traffic ngoài / mùa vụ / thuật toán. Lift cho biết từ *đi kèm* breakout, không chứng minh *gây ra*. Đây là tín hiệu để A/B test, không phải kết luận.

---

## 7. Pattern: ngưỡng reach DERIVE từ dữ liệu, bỏ magic 10× **[R2, vá A4]**

**Vấn đề Auditor nêu (A4):** `10 × median niche` là magic number, mâu thuẫn §10 chống magic number.

**v3 — một cụm là pattern khi thoả CẢ ba:**
1. ≥ `PATTERN_MIN_CHANNELS`=3 outlier `scope=primary, confidence≥medium` thuộc ≥3 kênh;
2. Tổng view-vượt-trội của cụm `Σ(view − expected)` **vượt P90 của phân phối view-vượt-trội của một-video-đơn trong niche** — tức cụm phải mạnh hơn video đơn lẻ tốt nhất bình thường. Ngưỡng này **suy từ phân phối thực**, không phải hằng số áp đặt;
3. (tunable) `PATTERN_EXCESS_PCTL` mặc định = 90, được khai báo là **lựa chọn heuristic** (xem §R-3) — không gắn nhãn "validated".

Xếp hạng pattern theo `Σ(view vượt trội)`; report luôn để cột view tuyệt đối cạnh OX.

---

## 8. Survivorship & coverage (giữ từ v2)

`coverage = scanned / videoCount`. `<0.7` ⇒ cờ `pruned=true`, OX là ước lượng **thận trọng** (thực tế có thể cao hơn). Trim đỉnh §3 giảm nhẹ tác động. Report ghi rõ: OX phản ánh catalog hiện còn public.

---

## 9. Khung validation trung thực (giữ từ v2, mở rộng)

Ba loại tuyên bố, ghi rõ trong report: **(A)** suy từ dữ liệu (median>mean; bỏ view/sub; tách format); **(B)** heuristic vay mượn (mốc 2/5/10/20×; `PATTERN_EXCESS_PCTL`) — *không* gắn nhãn validated; **(C)** cần tái kiểm mỗi niche (mọi ngưỡng số). Tự kiểm: phân phối OX nên ~log-normal; đa đỉnh/lệch mạnh ⇒ baseline lẫn format/thời kỳ ⇒ quay lại §1–§4.

---

## R. RESIDUALS — giới hạn KHÔNG thể xoá (Auditor yêu cầu ghi công khai)

Đây là phần phân biệt v3 với v1: thay vì giấu, ta liệt kê những gì *về bản chất* không giải được, để người dùng đặt cược có ý thức.

- **R-0 — Điểm mù chung của một-model.** Toàn bộ đồng kiểm ở đây do MỘT model đóng cả hai vai. Cách ly thông tin + trọng-tài-bằng-code giảm thiểu, nhưng nếu cả Builder lẫn Auditor cùng hiểu sai một công thức thì lỗi lọt. **Đảm bảo mạnh hơn = hai model thật khác nhau.** Vì vậy nhãn là "VERIFIED ở mức thiết kế", không phải chân lý.
- **R-1 — Bất định APC (từ A1).** Single snapshot không tách được tuổi/cohort/period. v3 thu hẹp bằng giả định APC-A + cửa sổ gần + diagnostic D-PERIOD, *không xoá*. Nếu `period_effect=true`, OX của niche đó kém tin cậy — đây là tính chất của dữ liệu, không phải bug sửa được bằng code.
- **R-2 — shape(age) nhiễu ở bucket tuổi-lớn (từ A1 fix).** Giới hạn shape về cửa sổ gần làm bucket >365 ngày ít mẫu ⇒ kỳ vọng video gần mốc đó nhiễu hơn. Chấp nhận được vì các video đó phần lớn rơi vào `scope=legacy`.
- **R-3 — `PATTERN_EXCESS_PCTL=90` là lựa chọn, không phải chân lý.** Đã derive ngưỡng *từ phân phối* (hết magic 10×), nhưng *chọn percentile nào* (90 vs 85 vs 95) vẫn là phán đoán → khai báo heuristic, để tunable.
- **R-4 — Causation của keyword.** Lift + FDR loại nhiễu thống kê, nhưng không thể quy nhân quả từ dữ liệu quan sát. Chỉ A/B test thật trên kênh của bạn mới khẳng định được.

---

## Bảng tham số v3 (đổi so với v2 in đậm)

| Tham số | Mặc định | Đổi từ v2 |
|---|---|---|
| `RECENT_WINDOW_MONTHS` | 18 (nới 24/36 khi cạn) | + fallback **[R2]** |
| `MATURITY_DAYS` | 45 | giữ |
| `SHORT_MAX_SEC` / `MID_MAX_SEC` | 180 / 1200 | giữ |
| `MIN_BASE_VIDEOS` | 8 (→ thang tin cậy) | giữ |
| `MIN_ABS_VIEWS` | `max(2000, P25 *của kênh*)` | **niche→per-channel [R2]** |
| `MIN_BASE_VIEWS` | `0.2 × median *của kênh*` | **per-channel [R2]** |
| `TRIM_TOP_FRAC` | 0.10 | giữ |
| `MIN_KW_COUNT` / `MIN_KW_CHANNELS` | 5 / 3 | giữ |
| `KW_FDR_Q` | 0.10 | **MỚI [R2]** |
| `CI_METHOD` | bootstrap≥20 / rank 12–19 / jackknife<12 | **MỚI [R2]** |
| `PATTERN_MIN_CHANNELS` | 3 | giữ |
| `PATTERN_EXCESS_PCTL` | 90 (heuristic) | **derive thay 10× [R2/R3]** |

---

## Golden rule v3

Một outlier `primary/high` là giả thuyết; một pattern (§7) là giả thuyết đáng test; không cái nào là kết luận. Mọi con số chỉ hợp lệ *dưới giả định APC-A*, đo trên catalog còn public, và mang nhãn tin cậy của nó. "VERIFIED" nói rằng phương pháp nhất quán và trung thực về giới hạn — quyết định làm video vẫn là một **đặt cược có thông tin**.
