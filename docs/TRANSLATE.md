# TRANSLATE.md — sổ chủ đề CHUYỂN NGỮ (đọc TRƯỚC khi dịch bất kỳ chuỗi nào)

> Vai trò file: quy ước + trạng thái + quy trình của mạch dịch tiếng Anh,
> tách khỏi CLAUDE.md lớn. Task UI nói chung: xem [UI.md](UI.md).

## Phạm vi Owner đã chốt (UI_FLOW.md mục 8)

- **Dịch sang EN**: toàn bộ VỎ hiển thị — sidebar, tab, menu, nút, nhãn form,
  placeholder, tooltip, thông báo trạng thái trên trang, chuỗi JS hiển thị.
- **GIỮ tiếng Việt**: nội dung agent trả lời + tài liệu trong kho; comment trong
  code (phong cách repo); dữ liệu.

## LUẬT VÀNG — thứ TUYỆT ĐỐI KHÔNG DỊCH (dịch là vỡ logic)

1. **Khóa dữ liệu catalog** — dict key đọc từ CSV/payload: `d['Mã tài liệu']`,
   `'Tiêu đề'`, `'Hiệu lực'`, `'Bộ phận'`… (bảng ánh xạ EN→key đã có sẵn trong
   template, vd `KT_NHAN` của kho_tai_lieu.html — nhãn hiển thị EN, key giữ VN).
2. **Giá trị dữ liệu khớp backend**: option value dropdown ('Còn hiệu lực',
   'Hết hiệu lực'…), tên bộ phận ('Vận hành - Sản xuất', 'Kinh doanh'), giá trị
   so sánh trong Jinja/JS (`d['Hiệu lực'] == 'Hết hiệu lực'`).
3. **Hàm chuẩn hóa tiếng Việt** (`boDau`, `boDauTk`… — `đ→d`, NFD) — là LOGIC
   tìm kiếm, không phải nhãn.
4. **5 khối script chat đóng băng trong hoi_dap.html** — chỉ đụng trong đợt riêng
   Owner đã duyệt (chưa làm, xem Việc treo).
5. Chuỗi do SERVER Python phát (flash message, `ten_nhom` vault, lỗi route…) —
   để đợt dịch server, KHÔNG dịch lỏi từng chỗ trong template đợt khác.

## Quy trình bắt buộc mỗi đợt dịch

1. Dịch template → **grep chuỗi VN cũ trong `tests/` của app đó** và sửa assertion
   CÙNG LƯỢT (bài học: 2 test đỏ vì sót "💡 Đã có tài liệu mới…" + "Vault chưa
   được khởi tạo").
2. Chạy suite TỪNG APP từ thư mục app (root pytest chỉ chạy tầng nền) + suite root.
3. Commit theo đợt, message ghi rõ phần còn sót (checkpoint sớm — tránh mất việc).

Lệnh kiểm kê chuỗi VN còn lại (loại comment; kết quả còn lẫn khóa dữ liệu — phải
soi mắt từng dòng theo LUẬT VÀNG ở trên, đừng dịch máy móc):

```bash
grep -nP '[ăâđêôơưàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵĂÂĐÊÔƠƯ]' <file> \
  | grep -vE '^[0-9]+:\s*(<!--|//|/\*|\*|\{#)'
```

## Trạng thái (cập nhật mỗi đợt)

- ✅ Đợt 2 (16/08): vỏ điều hướng EN + khu General + login gateway — `dbff341`→`9140710`.
- ✅ Đợt 3 (16/08): tên app hợp đồng EN (Knowledge/Organization/Sample App) — `07a8bed`.
- ✅ Đợt 4 (16/08): 14 template nội dung 3 app (Library/Gap/External source/lịch sử/
  giám sát/KPI/NAS/Vault/chẩn đoán + bảng phán quyết) + test theo — `16d36a3` + `b7a5cfa`.
  Đã rà vét: chuỗi VN còn lại trong template đều thuộc LUẬT VÀNG (giữ nguyên).
- ⬜ Đợt 5 — chuỗi VN trong **5 khối script chat đóng băng** (hoi_dap.html): phá đóng
  băng CÓ CHỦ ĐÍCH (Owner đã cho phép), nghiệm thu chat kỹ qua origin LAN thật,
  cập nhật luật đóng băng byte sau khi xong.
- ⬜ Đợt 6 — chuỗi SERVER phát: flash message các route, `ten_nhom` vault (to-chuc),
  thông báo lỗi… (quét cả 3 app + gateway; sửa Python là phải quét test kỹ hơn template).
- Bỏ qua có chủ đích: `kiem_stream.html` (công cụ tạm), nội dung agent/tài liệu (giữ VN).
