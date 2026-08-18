# Protocol Đồng Kiểm — vòng Builder / Auditor

> Mục tiêu: không có kết quả OX/keyword/pattern nào được coi là "đã verify" cho đến khi **hai vai độc lập** — Builder (Dựng) và Auditor (Phản biện) — đồng thuận theo tiêu chí khách quan, hoặc các bất đồng còn lại được ghi nhận công khai. Một mô hình (vd tôi) đóng cả hai vai *tuần tự nhưng cách ly thông tin*, lặp cho đến khi hội tụ.

Đây là protocol để chạy bằng tay/trong-phiên, không cần hạ tầng thêm. Nó **giả định kết quả được sinh theo `outlier_method_v2.md`**.

---

## 1. Vì sao hai vai, không phải "tự rà lại"

Một mô hình tự đọc lại bài của mình có thiên kiến xác nhận: nó bênh vực lập luận đã viết. Tách vai phá thiên kiến đó bằng ba ràng buộc:

1. **Cách ly thông tin:** Auditor **không** được thấy chain-of-thought của Builder — chỉ thấy (a) dữ liệu thô, (b) rule v2, (c) *output* của Builder (các con số + tuyên bố). Auditor phải **tự tính lại từ đầu**, không đọc cách Builder tính.
2. **Lập trường mặc định đối nghịch:** nhiệm vụ của Auditor là **bác bỏ** từng tuyên bố, không phải gật đầu. Mặc định mỗi claim là "chưa được chứng minh" cho tới khi Auditor tự tái lập được.
3. **Trọng tài là sự thật, không phải uy tín:** khi hai bên lệch về một con số, **code/công thức v2 là trọng tài** — chạy lại phép tính quyết định, không tranh luận. Chỉ các phán đoán định tính mới cần con người.

---

## 2. Vai BUILDER — đầu ra phải là *claims kiểm chứng được*

Builder không nộp một báo cáo mơ hồ. Builder nộp một **danh sách claim**, mỗi claim là một câu **falsifiable** (có thể bị chứng minh sai bằng dữ liệu). Ba loại:

- **Claim số (C-NUM):** `Video X có OX_v2 = 6.2 (CI 90%: 5.1–7.4), n_base=11, valid=TRUE, confidence=high`.
- **Claim nhãn (C-LAB):** `Video Y KHÔNG valid vì coverage kênh = 0.55 < 0.7 (pruned)`.
- **Claim pattern (C-PAT):** `Chủ đề T là pattern: 4 outlier / 4 kênh, Σ excess = 1.2M view, lift từ khoá "K" = 2.3 (p=0.01)`.

Mỗi claim ghi kèm: dữ liệu đầu vào đã dùng, tham số v2 áp dụng, và một câu **"điều kiện sai"** — *"claim này sai nếu …"*. Không có điều kiện sai ⇒ không phải claim hợp lệ, Auditor trả về ngay.

---

## 3. Vai AUDITOR — tái lập độc lập + phân loại

Với **mỗi** claim, Auditor tự tính lại từ dữ liệu thô và rule v2 (không tham chiếu phép tính của Builder), rồi gán một trong ba nhãn:

| Nhãn | Điều kiện | Hành động |
|---|---|---|
| **CONFIRM** | Auditor tái lập ra cùng kết quả trong dung sai (§4) | Khoá claim |
| **REFUTE** | Auditor ra kết quả khác ngoài dung sai, hoặc tìm được vi phạm rule | Trả về Builder kèm bằng chứng |
| **UNCERTAIN** | Dữ liệu không đủ để khẳng định/bác (vd n_base quá nhỏ, fresh, pruned) | Hạ xuống "low-confidence", không lên kết luận |

Auditor **bắt buộc** chạy **Checklist Regression §6** cho mỗi claim — đây là các lỗi của v1; nhiệm vụ là đảm bảo v2 không tái phạm.

Auditor cũng được quyền nêu **claim mới** mà Builder bỏ sót (vd "Video Z lẽ ra là outlier high nhưng bị floor loại oan") — đưa vào vòng sau.

---

## 4. Tiêu chí hội tụ (khách quan, để tránh đồng thuận giả & loop vô tận)

> **Lưu ý chế độ một-model (sửa lỗi A5):** khi MỘT model đóng cả hai vai, "tái lập số độc lập" gần như vô nghĩa — cùng một công thức tất định cho ra cùng kết quả, luôn CONFIRM. Vì vậy ở chế độ một-model, **trọng lượng kiểm chứng dồn vào leg ĐỊNH TÍNH + Checklist Regression §6**, còn leg số chỉ là chạy lại công thức một lần (trọng-tài-bằng-code), KHÔNG được coi là bằng chứng độc lập. Leg số chỉ thực sự độc lập khi dùng **hai model thật khác nhau** — đó là chế độ khuyến nghị cho đảm bảo mạnh.

- **Claim số:** ở chế độ hai-model, CONFIRM khi hai phép tính lệch ≤ **5%** *và* cùng bracket sau khi xét CI; ở chế độ một-model, chỉ là kiểm tính-đúng công thức, không tính là độc lập.
- **Claim nhãn / pattern:** CONFIRM khi hai bên trùng nhãn (valid/invalid, pattern/không). Lệch ⇒ REFUTE.
- **Điều kiện DỪNG vòng lặp** (đạt một trong ba):
  1. **Hội tụ sạch:** mọi claim *material* ở trạng thái CONFIRM (UNCERTAIN được phép tồn tại nhưng phải bị hạ tin cậy và ghi nhãn).
  2. **Trần số vòng:** đạt `MAX_ROUNDS = 3`. Khi đó **xuất bản kèm phụ lục "Bất đồng còn lại"** — liệt kê mọi REFUTE/UNCERTAIN chưa giải quyết. **Không bao giờ** im lặng bỏ qua bất đồng.
  3. **Bế tắc định tính:** bất đồng không phải do số mà do phán đoán (vd "đây có phải pattern đáng làm không") → escalate cho **con người** quyết, ghi rõ hai lập luận.
- **Chống đồng thuận giả:** nếu một vòng cho ra **0 REFUTE và 0 UNCERTAIN ngay lần đầu**, coi là đáng ngờ (Auditor có thể đã lười/đồng thuận). Bắt buộc Auditor nộp **bằng chứng tái lập** cho ít nhất 3 claim khó nhất (OX cao nhất, pattern lớn nhất, claim gần ranh bracket) trước khi được phép kết thúc.

---

## 5. Vòng lặp đầy đủ

```
Round n:
  1. BUILDER  → sinh/chỉnh danh sách claim (theo rule v2)
  2. AUDITOR  → (cách ly) tái lập từng claim + chạy Checklist Regression §6
              → gán CONFIRM / REFUTE / UNCERTAIN + bằng chứng
  3. RECONCILE:
       - CONFIRM   → khoá
       - REFUTE    → Builder sửa (đổi số / loại claim / bổ sung dữ liệu) ⇒ Round n+1
       - UNCERTAIN → hạ tin cậy, gắn nhãn, giữ trong báo cáo
       - claim mới của Auditor → vào Round n+1
  4. Kiểm DỪNG (§4). Chưa đạt ⇒ Round n+1 (đến MAX_ROUNDS).
OUTPUT: báo cáo final = {claim CONFIRMED} + {phụ lục bất đồng/uncertain}
```

Mỗi vòng ghi **nhật ký**: claim nào đổi nhãn, vì sao. Nhật ký này là bằng chứng "đã đồng kiểm", đính kèm report cuối.

---

## 6. Checklist Regression — Auditor PHẢI test (ánh xạ 11 lỗi của v1)

Đây là phần xương sống: mỗi mục là một lỗi v1, kèm phép test cụ thể Auditor chạy để chắc v2 không tái phạm.

1. **Lỗi tuổi (#1):** Lấy 1 video già (>2 năm) OX cao và 1 video mới (<30 ngày). Kiểm: OX có được tính qua `shape(age)` không? Nếu bỏ hiệu chỉnh tuổi mà OX video già tụt mạnh ⇒ v2 đang sai, REFUTE.
2. **Tăng trưởng kênh (#2):** Với kênh `trend=up`, kiểm baseline có dùng cửa sổ `RECENT_WINDOW_MONTHS` không, hay vẫn quét toàn đời. Nếu video cũ lọt vào baseline ⇒ REFUTE.
3. **Tự thổi baseline (#3):** Tính lại `scale_channel` *có* và *không* leave-one-out + trim đỉnh. Nếu video đang xét vẫn nằm trong baseline của nó ⇒ REFUTE.
4. **Keyword không base-rate (#4):** Mọi claim keyword phải là **lift có p-value**, không phải tần suất thô. Thấy "từ phổ biến" không kèm lift ⇒ REFUTE.
5. **Shorts/format (#5):** Kiểm `SHORT_MAX_SEC=180` và bucket Short/Mid/Long. Video 90s bị xếp Long ⇒ REFUTE.
6. **Floor cứng (#6):** Kiểm `MIN_ABS_VIEWS` có = `max(2000, P25)` của niche không, hay vẫn 10.000 cứng. Floor không in ra report ⇒ REFUTE.
7. **Bracket sắc nét (#7):** Mọi C-NUM phải có CI + n_base. Bracket thăng hạng khi CI vắt ranh giới ⇒ REFUTE.
8. **VPD thiên lệch (#8):** Không claim nào được dựa trên `views/day` thô để so video khác tuổi. Thấy VPD thô làm tín hiệu ⇒ REFUTE.
9. **Pattern bỏ reach (#9):** Mọi C-PAT phải có `Σ excess view` đạt ngưỡng, không chỉ đếm số hit. Pattern toàn kênh nhỏ, excess dưới ngưỡng ⇒ REFUTE.
10. **Overclaim "validated" (#10):** Báo cáo có gắn nhãn "validated" cho các mốc 2/5/10× (vốn là quy ước vidIQ) không? Có ⇒ REFUTE; phải ghi là heuristic.
11. **Survivorship (#11):** Kênh `coverage<0.7` có cờ `pruned` và OX được mô tả là "ước lượng thận trọng" không? Thiếu ⇒ REFUTE.

**Test phân phối (bao trùm):** OX của toàn niche có xấp xỉ log-normal không? Nếu đa đỉnh/lệch mạnh ⇒ baseline có thể lẫn format/thời kỳ ⇒ REFUTE toàn cục, quay lại v2 §1–§4.

---

## 7. Định nghĩa "đã verify"

Một kết quả chỉ được dán nhãn **VERIFIED** khi:
- Đi qua ≥ 1 vòng Builder/Auditor với cách ly thông tin;
- Ở trạng thái **CONFIRM** theo dung sai §4;
- Vượt toàn bộ Checklist Regression §6 liên quan;
- Mọi UNCERTAIN/REFUTE còn lại đã được ghi vào phụ lục bất đồng (minh bạch, không giấu).

Kết quả không đạt đủ ⇒ dán **TENTATIVE** hoặc **DISPUTED**, kèm lý do. Người dùng cuối luôn thấy nhãn này cạnh mỗi claim.

---

## 8. Vì sao loop này không tự lừa mình

- **Cách ly** ngăn Auditor mượn lập luận Builder ⇒ tái lập là độc lập thật.
- **Trọng tài bằng code** ngăn "ai hùng biện hơn thì thắng" ở các tranh chấp số.
- **Trần vòng + phụ lục bắt buộc** ngăn loop vô tận *và* ngăn việc che bất đồng để tỏ ra đã hội tụ.
- **Cảnh báo đồng thuận-quá-nhanh** (§4) ngăn Auditor lười gật đầu.
- **Checklist Regression** đảm bảo mỗi vòng đều chủ động truy đúng những chỗ v1 từng sai, thay vì rà chung chung.

> Giới hạn cần thành thật: cùng một mô hình đóng hai vai vẫn chia sẻ điểm mù chung (vd cả hai cùng hiểu sai một công thức). Cách ly + trọng tài-bằng-code giảm thiểu, không xoá bỏ. Khi cần đảm bảo mạnh hơn, dùng **hai model thật khác nhau** cho hai vai, hoặc đưa các phán đoán định tính ra cho con người — đó là lý do §4 luôn chừa đường escalate.
