# Quy ước sắp xếp tài liệu — Kho tri thức AI Agent

*Chuẩn tổ chức tài liệu cho kho của Agent. Đơn giản, dễ vận hành, chi phí bằng không.*
*Áp dụng cho cả người tra cứu lẫn AI đọc.*

---

## Nguyên tắc 1 — Cây thư mục NÔNG, phân theo "AI DÙNG" chứ không theo "loại file"

Không gom theo định dạng (PDF/Word/Excel riêng) — cách đó chết khi tài liệu nhiều lên.
Phân theo **bộ phận + mục đích**, giữ **tối đa 3 tầng** thư mục.

```
Kho-tai-lieu/
├── 00_Chung/              (toàn công ty: nội quy, giá trị, mẫu biểu)
├── 01_Nhan-su/
├── 02_Kinh-doanh/
├── 03_YouTube-Noi-dung/   (gắn với Claude Tool)
├── 04_Playbook/           (kế hoạch giải pháp đã đúc kết — QUAN TRỌNG)
└── 99_Luu-tru/            (tài liệu cũ, hết hiệu lực nhưng cần giữ)
```

> **Vì sao tách `04_Playbook`:** đây là "giải pháp đã đúc kết". Khi Agent chẩn đoán
> ra vấn đề X, nó vào đúng ngăn này lấy kế hoạch, không lục lẫn với tài liệu tham khảo.
> Số thứ tự đầu tên ngăn (00, 01, 99...) để thư mục luôn sắp đúng thứ tự mong muốn.

## Nguyên tắc 2 — Đặt tên file theo khuôn CỐ ĐỊNH

```
[Ngày]_[BộPhận]_[ChủĐề]_[PhiênBản].ext
Ví dụ: 2026-07-18_NhanSu_QuyTrinh-Tuyen-Dung_v2.pdf
```

- **Ngày dạng `YYYY-MM-DD`** đặt đầu → máy tự sắp đúng thứ tự thời gian.
- **Không dấu, không khoảng trắng** → dùng gạch `-`, tránh lỗi khi tool xử lý.
- **Luôn có số phiên bản** (`v1`, `v2`...) → biết đâu là bản mới nhất.

## Nguyên tắc 3 — Thẻ mô tả (metadata) ở ĐẦU mỗi tài liệu quan trọng

Không cần phần mềm. Chỉ cần 3–4 dòng ở đầu file (hoặc trong một ô đầu bảng Excel):

```
Chủ đề: Quy trình tuyển dụng nhân sự
Áp dụng cho: Phòng Nhân sự
Hiệu lực: Còn hiệu lực (cập nhật 2026-07-18)
Phụ trách: <tên/bộ phận>
```

> Giúp Agent hiểu ngữ cảnh và giúp bạn biết tài liệu nào lỗi thời → chuyển `99_Luu-tru`.

## Nguyên tắc 4 — Một file mục lục `_MucLuc.md` ở thư mục gốc

Liệt kê có những ngăn nào, mỗi ngăn chứa gì. Vừa cho người, vừa là bản đồ cho Agent.

## Nguyên tắc 5 — Định dạng file nên dùng

Nguyên tắc gốc: **AI đọc CHỮ THẬT (text) rất tốt, đọc HÌNH ẢNH của chữ thì kém.**

| Loại tài liệu | Định dạng nên dùng | Ghi chú |
|---|---|---|
| Văn bản (quy trình, chính sách, hướng dẫn) | **`.md`** (tốt nhất) hoặc **`.docx`** | Chữ thật → Agent đọc chính xác 100% |
| Số liệu / bảng | **`.xlsx`** hoặc **`.csv`** | Đúng cho tính năng chẩn đoán số liệu. Đừng chụp ảnh bảng. |
| PDF | **Chỉ khi là PDF "chữ thật"** | PDF xuất từ Word: OK. PDF scan/chụp ảnh: cần OCR trước. |

**Bẫy lớn nhất — PDF scan:** PDF chụp ảnh/scan thực chất KHÔNG có chữ bên trong,
Agent gần như mù. Mẹo kiểm tra: mở file, **bôi đen một dòng chữ bằng chuột**. Bôi
được → chữ thật, dùng ngay. Chỉ kéo được cả khối như kéo ảnh → là scan, cần OCR.

**Nên tránh làm định dạng lưu trữ chính:** ảnh chụp văn bản (`.jpg`/`.png`), file
scan chưa OCR, định dạng lạ/độc quyền. Slide (`.pptx`) đọc được phần chữ nhưng hay
mất ngữ cảnh — nếu nội dung quan trọng thì rút thành tài liệu chữ riêng.

> Tài liệu đang là ảnh/scan → gom một chỗ, OCR khi bắt đầu Giai đoạn 1 (Claude lo).

## Nguyên tắc 6 — "Sạch định dạng" vs "Sạch cấu trúc" (hai nghĩa khác nhau)

Chữ "file sạch" có HAI nghĩa, đừng lẫn:

**(1) Sạch ĐỊNH DẠNG = file có CHỮ THẬT (không phải ảnh của chữ).** Một file `.docx`/`.md`
gõ bằng máy, hay PDF xuất từ Word → sạch định dạng, nạp vào Agent tốt. PDF scan/ảnh chụp
→ bẩn định dạng, cần OCR (xem Nguyên tắc 5).

**(2) Sạch CẤU TRÚC = chữ GỌN GÀNG, dễ cắt đúng chỗ.** Một file có chữ thật NHƯNG bên trong
đầy **bảng biểu dày, nhiều cột, hộp văn bản chồng chéo, hình chèn giữa chữ** thì lúc máy bóc
chữ ra sẽ RỐI — chữ dính cục, nhảy thứ tự, cắt thành đoạn vô nghĩa. File đó "sạch định dạng"
nhưng "bẩn cấu trúc" → Agent tìm kém. (Cắt sai chỗ làm rớt chất lượng 30-40%.)

**File LÝ TƯỞNG để nạp = vừa sạch định dạng vừa sạch cấu trúc:**

| Mức | Loại | Xử lý |
|---|---|---|
| ✅ Sạch (nạp tốt) | Word/PDF-máy dạng **văn xuôi / danh sách** (quy trình, chính sách, hướng dẫn, ghi chú). Có tiêu đề, gạch đầu dòng càng tốt. | Nạp thẳng. |
| ⚠️ Kém sạch | Chữ thật nhưng **nhiều bảng dày / nhiều cột / layout phức tạp** (brochure, báo cáo nhiều bảng). | Rút nội dung quan trọng thành dạng chữ trước khi nạp. |
| ❌ Bẩn | PDF scan / ảnh chụp / chụp màn hình. | OCR hoặc gõ lại trước. |

> **Lưu ý phân vai:** file NHIỀU BẢNG SỐ LIỆU (báo cáo YouTube, tài chính) KHÔNG thuộc kho
> hỏi–đáp — chúng dành cho **module chẩn đoán số liệu** (đọc bằng cách khác). Kho hỏi–đáp
> ưu tiên tài liệu dạng văn xuôi.

**Mẹo kiểm nhanh "sạch cấu trúc" (giống mẹo bôi-đen PDF):** mở file, **copy một đoạn chữ dán
vào Notepad/ô trống**. Ra gọn gàng theo dòng, đọc được → sạch, nạp tốt. Ra lộn xộn, dính cục,
mất thứ tự → cấu trúc phức tạp, nên chỉnh lại trước khi nạp.

## Nguyên tắc 7 — Chữ viết tắt phải định nghĩa đủ LẦN ĐẦU

Trong MỖI tài liệu, lần ĐẦU TIÊN dùng một chữ viết tắt phải viết ĐỦ TÊN rồi mở
ngoặc chữ tắt — ví dụ **"Google AdSense (GA)"** hoặc **"Gemini Assistant (GA)"**,
từ đó về sau trong tài liệu dùng chữ tắt thoải mái.

**Lý do:** cùng một chữ tắt có thể mang nghĩa khác nhau ở các tài liệu/bộ phận
khác nhau — kho đã gặp thật: "GA" vừa là Google AdSense (tài liệu kiếm tiền) vừa
là Gemini Assistant (tài liệu MMO), kho tự mâu thuẫn chính nó, cả người lẫn máy
đều nhầm. Viết đủ tên lần đầu giúp cả người đọc lẫn AI Agent hiểu đúng ngữ cảnh
từng tài liệu, tránh trả lời nhầm nghĩa khi người dùng hỏi bằng chữ tắt.

---

## Phương pháp & chi phí

- **Không cần** phần mềm DMS / SharePoint. Chỉ dùng **thư mục thường trên PC LAN**
  tổ chức theo 4 nguyên tắc trên. Chi phí bằng 0, và Agent đọc thẳng được vì không có
  tầng phần mềm chắn giữa.

## Cách làm — đừng cầu toàn

Không sắp xếp hoàn hảo cả kho ngay lần đầu. Bắt đầu với **vài chục tài liệu hay dùng
nhất** (nhóm cho Giai đoạn 1), làm chuẩn nhóm đó trước, rồi mở rộng dần. Cố làm sạch
cả kho một lúc là cách chắc chắn nhất để bỏ cuộc giữa chừng.
