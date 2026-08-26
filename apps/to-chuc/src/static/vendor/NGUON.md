# Vendor — nguồn gốc và lý do

| File | Bản | Nguồn | Giấy phép |
|---|---|---|---|
| `frappe-charts.min.umd.js` | 1.6.2 | `cdn.jsdelivr.net/npm/frappe-charts@1.6.2/dist/frappe-charts.min.umd.js` | MIT |

**Vì sao vendor chứ không CDN:** app phục vụ LAN nội bộ, máy nhân viên không ra
Internet là chuyện thường; CDN chết thì dashboard trắng. Bản này chép từ
`apps/tasky/src/static/vendor/` — mỗi app tự đứng (Luật 4), không app nào phục vụ
tệp tĩnh cho app khác.

**Cái giá đã biết, đừng quên:** thư viện vẽ bằng giá trị màu TRUYỀN VÀO JS, KHÔNG
đọc CSS var — đổi theme sáng/tối phải **đọc token rồi vẽ lại** (xem `veBieuDo()`
trong `finance.html`). Quên gọi lại là biểu đồ giữ màu theme cũ.

**Nâng cấp:** tải đúng đường trên với số bản mới, thay file, chạy
`pytest tests/test_finance.py` — có test ghim route phục vụ được tệp này.
