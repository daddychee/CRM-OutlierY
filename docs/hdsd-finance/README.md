# Hướng dẫn sử dụng — Finance Hub

> Khu quản lý tiền của OUTLIERY: sổ thu chi, ví, ngân sách, lương, thuê bao,
> lãi lỗ theo kênh và ngách. Vào bằng đường `/finance` trên cổng chính.
>
> Ảnh trong tài liệu chụp từ **chính giao diện đang chạy** với dữ liệu mẫu, không
> phải bản vẽ. Số trong ảnh là số giả để minh họa.

## Ai vào được

| Vai | Vào Finance | Tab Lương | Duyệt chi lương · Chốt kỳ |
|---|---|---|---|
| Owner | ✔ | ✔ | ✔ |
| Kế toán (L2 trở lên) | ✔ | ✔ | ✖ |
| Hành chính Nhân sự (L3 trở lên) | ✔ | ✔ · xuất và gửi phiếu | ✖ |
| Còn lại | ✖ | ✖ | ✖ |

Không có quyền thì gõ thẳng đường dẫn cũng không vào được — cổng chặn ở máy chủ.

## Mười một tab, mỗi tab một việc

| Tab | Việc | Hướng dẫn |
|---|---|---|
| Tổng quan | Nhìn một phát biết tiền còn bao nhiêu, sắp phải làm gì | [01-tong-quan.md](01-tong-quan.md) |
| Sổ thu chi | Ghi từng đồng vào ra, đính kèm chứng từ | [02-so-thu-chi.md](02-so-thu-chi.md) |
| Ví & chốt kỳ | Tiền nằm ở đâu, cuối kỳ đối chiếu rồi chốt | [03-vi-va-chot-ky.md](03-vi-va-chot-ky.md) |
| Ngân sách | Đặt hạn mức tháng cho từng mục tiêu | [04-ngan-sach.md](04-ngan-sach.md) |
| Kênh | Kênh nào lãi thật sau khi gánh chi phí chung | [05-kenh.md](05-kenh.md) |
| Ngách | Ngách nào ngốn người, ngách nào ngốn tiền | [06-ngach.md](06-ngach.md) |
| Lương | Bảng lương từ chấm công, phiếu lương cho từng người | [07-luong.md](07-luong.md) |
| Thuê bao | Dịch vụ trả phí, ngày gia hạn, cắt cái gì thì tiết kiệm | [08-thue-bao.md](08-thue-bao.md) |
| Tài sản | Kiểm kê vật lý & số, bàn giao, mật khẩu ở Vault | [11-tai-san.md](11-tai-san.md) |
| Tự động | Đối soát AdSense, tiền API, luật gợi ý | [09-tu-dong.md](09-tu-dong.md) |
| Danh mục | Bảng mã khoản thu chi | [10-danh-muc.md](10-danh-muc.md) |

## Bốn nguyên tắc chi phối toàn bộ khu này

Hiểu bốn điều này thì dùng chỗ nào cũng đoán được hệ sẽ hành xử ra sao.

**1. Sổ chỉ ghi thêm, không sửa, không xóa.** Một dòng đã vào sổ thì nằm đó vĩnh
viễn. Ghi sai thì bấm **Đảo** — hệ sinh một dòng mới mang số âm, trỏ về dòng gốc.
Nhìn sổ vẫn thấy cả cái sai lẫn cái sửa, nên sáu tháng sau vẫn kể lại được chuyện
gì đã xảy ra.

**2. Không biết thì nói không biết.** Chỗ nào thiếu dữ liệu, hệ hiện dấu gạch
ngang kèm lý do chứ không điền số 0 hay số ước chừng. Ví dụ: chưa chấm xếp loại
thì ô lương để trống; chưa khai đơn giá API thì không cộng vào tổng; PlannerY
không đọc được thì cả khối báo thiếu nguồn.

**3. Máy đề nghị, người chốt.** Không có bút toán nào tự chui vào sổ. Đối soát
AdSense, tiền API, thuê bao đến hạn — tất cả chỉ dựng bản nháp; phải có người bấm
duyệt mới thành tiền trong sổ.

**4. Luật nằm ngoài code.** Danh mục khoản, danh sách ví, hệ số xếp loại, ngày
lễ, luật gợi ý, đơn giá API đều nằm trong tệp CSV/JSON sửa được bằng Excel. Thêm
một loại chi phí mới hay đổi hệ số lương **không cần lập trình viên**.

## Tệp luật sửa bằng Excel

| Tệp | Nội dung |
|---|---|
| `apps/to-chuc/rules/danh_muc_thu_chi.csv` | Mã khoản thu chi |
| `apps/to-chuc/rules/danh_muc_vi.csv` | Danh sách ví tiền |
| `apps/to-chuc/rules/he_so_xep_loai.csv` | Hệ số lương theo xếp loại A/B/C |
| `apps/to-chuc/rules/gio_lam_viec.csv` | Giờ vào chuẩn, dung sai, ngưỡng nhắc đi muộn |
| `apps/to-chuc/rules/ngay_nghi_le.csv` | Ngày lễ — **cần điền cho 2026–2027** |
| `apps/to-chuc/rules/luat_goi_y.csv` | Luật gợi ý phân loại bút toán |

Riêng danh mục nhóm tài sản nằm trong code (`src/tai_san.py`, hằng `NHOM`) vì nó
gắn với luật "nhóm phải khớp loại" — thêm nhóm mới cần sửa một dòng.

Sửa xong lưu lại là hệ đọc ngay ở lần tải trang kế tiếp, không cần khởi động lại.

## Bốn việc cần làm trước khi dùng thật

1. **Điền ngày lễ** vào `ngay_nghi_le.csv` — thiếu thì số ngày làm việc trong
   tháng bị tính dư, kéo theo đơn giá ngày công sai.
2. **Sửa danh sách ví** cho khớp ví thật của công ty (đang tạm: Payoneer,
   Vietcombank, Tiền mặt, AdSense chờ chi trả).
3. **Đặt lương cơ bản** cho từng người ở tab Lương — chưa có thì bảng để trống.
4. **Khai đơn giá API** ở tab Tự động để tiền API quy được ra tiền.

## Lịch hằng tháng

| Ngày | Việc | Ở đâu |
|---|---|---|
| 10–12 | Google chốt tiền → nạp CSV, đối soát doanh thu | tab Tự động |
| sau đối soát | Đối chiếu số dư ví → chốt kỳ | tab Ví & chốt kỳ |
| 15 | Duyệt bảng lương kỳ trước → sinh bút toán lương | tab Lương |

Lịch này hiện ngay đầu tab Tổng quan kèm trạng thái từng mốc. Trễ hạn thì hệ
nhắc, **không tự chạy**.

---

## Bản PDF

`HDSD-Finance-Hub.pdf` — gộp cả 11 tài liệu và 12 ảnh thành một tệp 25 trang,
ảnh nhúng sẵn nên gửi đi đâu cũng xem được, không cần kèm thư mục.

Tạo lại sau khi sửa tài liệu: chạy `scratchpad/gop_pdf.py` để gộp Markdown thành
HTML, rồi Chrome in ra PDF (`--headless --print-to-pdf`). Máy này không có
pandoc, và WeasyPrint thiếu GTK nên không dùng được.
