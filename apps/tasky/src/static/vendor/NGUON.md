# Vendor — nguồn gốc và lý do

| File | Bản | Nguồn | Giấy phép |
|---|---|---|---|
| `frappe-charts.min.umd.js` | 1.6.2 | `cdn.jsdelivr.net/npm/frappe-charts@1.6.2/dist/frappe-charts.min.umd.js` | MIT |

**Vì sao vendor chứ không CDN:** app phục vụ LAN nội bộ, máy nhân viên không ra
Internet là chuyện thường; CDN chết thì dashboard trắng. Chép về `src/static` là
xong, không thêm build step nào.

**Vì sao chọn Frappe Charts** (Owner chốt 25/08 sau khi so hai bản dashboard thật —
`mockup/UI-v7a-dashboard-svg.html` vs `UI-v7b-dashboard-frappe.html`): SVG thuần,
zero-dependency, ~68KB, dùng qua thẻ script.

**Cái giá đã biết, đừng quên:** thư viện vẽ bằng giá trị màu truyền vào JS, KHÔNG
đọc CSS var — nên đổi theme sáng/tối phải **đọc token rồi vẽ lại** (xem `ve_bieu_do()`
trong `bao_cao.html`). Quên gọi lại là biểu đồ giữ màu theme cũ.

**Nâng cấp bản mới:** tải đúng đường trên với số bản mới, thay file, chạy
`pytest tests/test_dashboard.py` — có test ghim rằng file tồn tại và route phục vụ được.
