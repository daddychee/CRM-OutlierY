# HƯỚNG DẪN TEAM — Content Ultimate V2 (bản 2026-07-27)

## V2 là gì, một câu

Kịch bản giữ chân người xem bằng công thức **V = (M + (Q→E)) × (A + B)**:
**hook bẻ gãy MỘT niềm tin sai (M)** ngay câu đầu, và **mỗi chương mở bằng một câu
hỏi thật của khán giả (Q)** rồi mới trả lời (E). Đã chứng minh trên 2 bài thật
(Jupiter · Moscow), duyệt từng chương.

**Nguyên tắc an toàn:** không chọn M, không chọn Q → tool chạy **y hệt bản cũ**.
Không ai bị ép đổi cách làm; dùng đến đâu bật đến đấy.

---

## Có gì mới trên board Outline (5 thứ)

| Nút / chỗ | Làm gì |
|---|---|
| **⚡ Chia outline (PY)** (cạnh ✨) | Chia hook/chương/ending **tự động bằng số đo** — 0 LLM, bấm là ra ngay, bấm lại ra y hệt. Chương xếp theo trình tự sóng đang kể (pos). **Chương nào mỏng nguyên liệu sẽ tự được đắp thêm ý con** từ cụm gần đó — hết badge đói ngay từ lúc chia. |
| **Tab ⚡ M (V2)** (cạnh GAPS) | Python quét beat + comment tìm **niềm tin sai** ứng viên: *M thuần* (video tự đính chính — mạnh nhất) · *M mềm* (twist "Despite…") · *Cộng hưởng* (khán giả tự nói niềm tin vỡ, theo ❤) · *Top ❤* (kho quote). Bấm **chọn** một dòng là xong. |
| **Ô ⚡ M trong khối HOOK** | M nằm **trong** khối HOOK (nó là linh hồn của hook): trên là niềm tin sẽ bị bẻ, dưới là cluster nguyên liệu để bẻ. Sửa tay được; xoá trống = hook viết kiểu cũ. |
| **Nút Q** (cạnh CTA, mỗi chương) | Chọn **câu hỏi khán giả NGUYÊN VĂN** cho chương: nguồn ưu tiên là câu hỏi khớp đúng cluster đó, rồi GAPS theo ❤, hoặc tự dán. Chương sẽ mở bằng câu hỏi này rồi mới trả lời. |
| **Badge nguyên liệu + nút ＋** (như cũ, quan trọng hơn với V2) | `giãn >8×` = brief mỏng, LLM sẽ độn chữ/bịa số. Cách chữa ĐÚNG là **thêm ý** (nút ＋: kéo cluster vào hoặc gõ số thật từ transcript), không phải tăng chương. |

Ngoài board: Writer (tab Writing) tự nhận các dòng mới trong outline — hook bẻ M ở
câu 1 không lộ payoff, chương mở bằng Q, vòng nở/cắt giữ đúng luật. Terminal có thêm
`.venv/bin/python -m oe.m_mine <run>` (bản CLI của tab M).

---

## Quy trình chuẩn 7 bước

1. **Pipeline như cũ** — dán link video cùng sóng, chờ chạy xong.
2. **Bấm ⚡ Chia outline (PY)** — có ngay khung hook/chương/ending xếp theo sóng,
   chương mỏng đã được đắp ý. Đọc lại, kéo thả chỉnh theo ý mình (đây là GỢI Ý,
   người quyết là bạn).
3. **Mở tab ⚡ M (V2), chọn MỘT M** — ưu tiên bảng *M thuần*; sóng không có thì
   *M mềm* + một câu *Cộng hưởng* ❤ cao là đủ (bài Moscow làm đúng thế).
4. **Bấm Q ở từng chương nên có** — chọn câu hỏi mà chương đó trả lời TRỌN VẸN.
   Chương thuần dữ kiện không có câu hỏi thật thì ĐỂ TRỐNG, đừng bịa.
5. **Soát badge nguyên liệu** — chương nào còn `⚠/●` thì bấm ＋ nạp thêm fact thật
   (số liệu lấy từ transcript trong `runs/<run>/transcripts/`).
6. **Đặt Title + độ dài** (quy ước 21.000 ký tự ≈ 6 chương — phần dư cho hook/ending).
7. **Sang tab Writing** — chọn outline từ dropdown, chọn giọng, WRITE. Duyệt từng
   phần theo checklist dưới.

## Checklist duyệt (bắt đúng các lỗi máy hay mắc)

- Câu 1 của hook có **bẻ thẳng** niềm tin không (không warm-up)? Hook có **lộ đáp án**
  của video không? (Lộ = vứt.)
- Chương có mở bằng câu hỏi rồi **giữ đáp án đến cuối chương** không?
- Có câu nào **khẳng định lại** niềm tin hook đã bẻ không?
- **Mọi con số / so sánh định lượng truy được về transcript không?** — lỗi phổ biến
  nhất của model (5 ca bịa trong 2 bài thí nghiệm, đều bắt ở bước này).

## Phân mảng (tạm thời)

| Mảng | Dùng V2? |
|---|---|
| Toplist / du lịch / kể chuyện thường (A008…) | ✅ Dùng ngay — nhịp văn khớp tự nhiên |
| Khoa học giọng văn chương dài hơi (Sagan…) | ⚠ Hook + cấu trúc dùng ngay; nhịp câu chưa đạt giọng gốc (đang chờ thí nghiệm exemplar dày) |

Chi tiết phương pháp & số đo: `METHODOLOGY-V2.md` · `CONTENT-ULTIMATE-V2-MASTER.md`.
