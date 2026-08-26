# RUNBOOK SỰ CỐ — OUTLIERY Platform v2

> Dành cho người VẬN HÀNH (không cần biết code). Làm đúng thứ tự từng bước.
> Nguyên tắc: bình tĩnh — dữ liệu có backup, code có git, không thao tác nào ở đây
> làm mất dữ liệu.

## 0. Nhìn tổng quan nhanh nhất
Mở trình duyệt: `https://localhost:9443/suc-khoe` (đăng nhập nếu được hỏi).
Bảng xanh = sống, đỏ = app đó không phản hồi.

## 1. "Cả hệ không vào được"
1. Mở PowerShell → chạy:
   `powershell -File "D:\AI AGENT OUTLIERY\tools\scripts\start-all.ps1"`
   (Script tự bỏ qua dịch vụ đang chạy, chỉ bật cái đang chết.)
2. Đợi 10 giây, mở lại `https://localhost:9443`. Trình duyệt cảnh báo chứng chỉ
   (giai đoạn test dùng cert tự ký) → bấm Nâng cao → Tiếp tục.
3. Vẫn chết → xem mục 5 (thu thập thông tin rồi báo).

## 2. "Một app đỏ trên trang Sức khỏe"
1. Chạy lại start-all.ps1 như trên (nó bật lại app chết).
2. Vẫn đỏ → tắt sạch rồi bật lại:
   `powershell -File "D:\AI AGENT OUTLIERY\tools\scripts\stop-all.ps1"`
   rồi chạy start-all.ps1.

## 3. "Hỏi–đáp không trích được tài liệu / kho rỗng"
- Kho vector (Qdrant test) chạy ở cổng 6343. Kiểm:
  mở `http://127.0.0.1:6343/readyz` — phải hiện "all shards are ready".
- Chết → start-all.ps1 (Qdrant nằm trong danh sách tự bật).
- Sống mà vẫn không trích được → kho có thể rỗng: cần nạp lại tài liệu
  (xem 02-so-tay-admin.md mục Nạp tài liệu).

## 4. Khôi phục dữ liệu từ backup
- Backup nằm ở thư mục `E:\OUTLIERY-V3-backup` (ổ KHÁC với ổ D chứa bản gốc — đổi 26/08/2026) (chạy `tools\scripts\backup.ps1`
  để tạo bản mới bất cứ lúc nào; sổ kết quả: `ket-qua.jsonl` trong đó).
- Khôi phục một database SQLite: chép file `<tên>.snapshot.db` trong backup đè
  lên file gốc trong `D:\AI AGENT OUTLIERY\data\...` (TẮT hệ trước bằng
  stop-all.ps1, chép xong bật lại).
- Khôi phục kho file (báo cáo, tài liệu): chép nguyên thư mục tương ứng từ backup
  về `data\`.
- ĐÃ DIỄN TẬP: quy trình này có test tự động chứng minh chạy được
  (tests/test_sao_luu.py). Mỗi quý làm tay một lần cho quen.

## 5. Khi phải báo người giữ code — thu thập sẵn
1. Chụp màn hình trang Sức khỏe hệ.
2. Chép nguyên văn thông báo lỗi (nếu có).
3. Ghi: ai đang làm gì, mấy giờ, trên máy nào.
4. KHÔNG tự sửa file trong `D:\AI AGENT OUTLIERY\nen` hay `apps`.
