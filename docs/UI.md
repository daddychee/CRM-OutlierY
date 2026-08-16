# UI.md — sổ chủ đề GIAO DIỆN (đọc TRƯỚC khi làm bất kỳ task UI nào)

> Vai trò file: một chỗ duy nhất chứa nguyên tắc + lịch sử + bẫy của mạch UI,
> để AI không phải đọc cả CLAUDE.md lớn. CLAUDE.md gốc chỉ giữ mốc một dòng
> trỏ về đây. Task chuyển ngữ có sổ riêng: [TRANSLATE.md](TRANSLATE.md).

## Thứ tự đọc khi nhận task UI

1. **[UI_FLOW.md](UI_FLOW.md) = HỢP ĐỒNG giao diện** (Owner chốt từng mục) —
   UI v2 chép đúng V1, muốn khác một mục phải hỏi Owner TRƯỚC. Đây là luật cao nhất.
2. File này — nguyên tắc kỹ thuật + bẫy đã trả giá.
3. Nếu task dính chuyển ngữ → đọc thêm [TRANSLATE.md](TRANSLATE.md).

## Nguyên tắc kỹ thuật bất biến

- **5 khối `<script>` trong `hoi_dap.html` (tri-thuc) ĐÓNG BĂNG BYTE** — không sửa
  một byte bên trong, kể cả khoảng trắng. Ngoại lệ DUY NHẤT: đợt dịch chuỗi chat
  Owner đã cho phép phá đóng băng CÓ CHỦ ĐÍCH (xem TRANSLATE.md — chưa làm).
- **JS phải chạy HTTP LAN** (không secure context): cấm `crypto.randomUUID`,
  `navigator.clipboard`… trần — phải có fallback (sự cố chat tê liệt 01/08 hệ cũ).
- **Theme**: MỘT khóa `outliery_theme` + `data-theme` trên `<html>` toàn hệ;
  KHÔNG dùng `@media prefers-color-scheme`; màu mới phải khai cặp token
  `:root{}` + `:root[data-theme="light"]{}`, không viết hex trần.
- **Brand "Breakout Signal"**: VOID #090C12 / PANEL #121826 / RADAR BLUE #4C8FE0 /
  SLATE #8B96A8 / MIST #E8EDF4; light accent đậm #2C6FC4; Inter UI + Space Grotesk
  chỉ wordmark. Màu trạng thái (ok/danger/warn) là màu NGHĨA, không rebrand.
- **Sidebar do GATEWAY quyết** qua claims `X-Remote-Apps` — app không tự đoán quyền;
  khuôn chung `nen/common/sidebar.py`.
- Route giữ nguyên khi đổi nhãn (chỉ đổi chữ hiển thị); giữ nguyên ID phần tử mà JS
  đóng băng đang bám (vd 4 ID `sb-mgmt*`).

## Lịch sử các đợt UI (chi tiết nằm trong commit message)

| Đợt | Nội dung | Commit chốt |
|---|---|---|
| Chốt UI=V1 | "/" → Hỏi–đáp, xóa launcher, app chưa di trú ẩn, claims sidebar | `d64a00e` |
| Khu nền | 8 trang /nen mỗi trang một việc + phân quyền V1 + 2 miền Caddy | `a88c384`, `a84fd1d` |
| Đợt 2 | Vỏ điều hướng EN + user menu kiểu Claude + tab Database + /profile | `dbff341`→`9140710` |
| Đợt 3 | 5 điểm Owner: logo=Home, topbar ngày, bỏ nút theme cũ, icon DB/Gap | `07a8bed` |
| Đợt 4 | Dịch nhãn EN 14 trang nội dung 3 app (xem TRANSLATE.md) | `16d36a3`, `b7a5cfa` |

## Bẫy đã trả giá (đừng dính lại)

- Comment CSS chứa nguyên văn chữ `<script>` → regex tách khối script nuốt cả
  sidebar (dính 2 lần). Tách khối phải loại `<script>` nằm trong `<style>`.
- Template trộn EOL (index.html CRLF, hoi_dap.html LF) — script sửa hàng loạt
  phải dò EOL từng file; so byte khối đóng băng phải quy đồng newline.
- Nhãn UI nằm trong assertion test — đổi nhãn phải quét cả `tests/` (xem quy
  trình trong TRANSLATE.md).
- Test ghim hằng số (schema_version, hex màu) tự vỡ khi đổi giá trị → ghim LUẬT
  (đếm file migration, đọc accent hiện hành), không ghim mặt chữ.
- Fixture dùng app-mau ĐANG CHẠY SẴN :9190 — sửa code app-mau phải restart tiến
  trình sống rồi mới tin kết quả test.
- Comment Jinja/CSS không được chứa cú pháp `{%...%}` — Jinja đọc thành lệnh thật.

## Việc treo UI

- Dịch chuỗi VN trong 5 khối script chat đóng băng (đợt riêng — TRANSLATE.md).
- Nhãn/thông báo do SERVER phát còn tiếng Việt (flash, `ten_nhom` vault…) —
  thuộc đợt dịch server (TRANSLATE.md).
- Caddy root CA cho máy nhân viên khi mở LAN; DNS zone lúc thay thế (UI_FLOW.md mục 7).
