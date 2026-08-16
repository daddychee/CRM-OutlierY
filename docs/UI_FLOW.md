# UI_FLOW.md — HỢP ĐỒNG GIAO DIỆN & LUỒNG (chốt với Owner 16/08/2026)

> Luật: **UI và flow của v2 = chép đúng V1 (C:\OutlierY\apps\AI AGENT\agent-app),
> không thêm không bớt.** File này là hợp đồng — code giao diện khác file này là SAI.
> Muốn đổi bất cứ mục nào phải hỏi Owner trước, chốt xong cập nhật file này rồi mới code.
> (Ra đời sau sự cố 16/08: trang chủ bị tự chế thành "bảng chọn app" khác hẳn V1.)

## 1. Luồng vào hệ

1. Vào `https://<địa chỉ>:9443` → trang **đăng nhập** (nền OUTLIERY như V1).
2. Đăng nhập xong → chuyển thẳng **trang Hỏi–đáp** (`/app/tri-thuc/hoi-dap`) —
   đúng hành vi V1 (`RedirectResponse("/hoi-dap")` sau login).
3. Tài khoản có mật khẩu tạm → bị ép **đổi mật khẩu** trước khi vào (YC6 V1).
4. **KHÔNG có trang "bảng chọn app"** — đã xóa hẳn (chốt Owner). Mọi điều hướng
   qua sidebar.

## 2. Sidebar trái (chép đúng V1, từng mục, từng nhãn)

| Khu | Mục (nhãn đúng chữ V1) | Đích trong v2 | Ai thấy |
|---|---|---|---|
| Tab **Home** | Hỏi–đáp (nút "New") | /app/tri-thuc/hoi-dap | mọi người |
| — nhãn "Công cụ" | Data Analytics | /app/data-analytics/chan-doan | theo quyền vào app |
| | NAS công ty | /app/to-chuc/nas | mọi người, **ẨN khi chưa cấu hình NAS_DUONG_DAN** (luật V1) |
| | ~~RadarY · Content · SpeakY · PlannerY · Niche · SEO~~ | **ẨN HẲN** khi chưa di trú (chốt Owner) — chuyển app nào sang thì mục đó tự hiện | |
| — ô tìm + nhãn "Gần đây" | các cuộc trò chuyện (phien) + "Xem tất cả lịch sử →" | /app/tri-thuc/hoi-dap?phien=… · /app/tri-thuc/lich-su | mọi người |
| Tab **Monitoring** — nhãn "Quản trị (Manager+)" | Datafeed | /app/tri-thuc/ (trang nhập liệu) | Manager+ |
| | Kho tài liệu | /app/tri-thuc/kho-tai-lieu | Manager+ |
| | Kho cần bổ sung | /app/tri-thuc/kho-thieu | Manager+ |
| | Nguồn ngoài | /app/tri-thuc/nguon-ngoai | Manager+ |
| — nhãn "Nhân sự" | Nhân sự | /quan-tri (hồ sơ NS nằm trong IAM gateway) | Owner + HR L3+ |
| **Management** (popup ghim đáy, kiểu menu Claude) | Hoạt động team | /app/tri-thuc/giam-sat | chỉ Owner |
| | User | /quan-tri | chỉ Owner (+ Admin ủy quyền theo giỏ quyền IAM) |
| | Vault | /app/to-chuc/vault | chỉ Owner |
| | Phân quyền | /quan-tri (khu phân quyền) | chỉ Owner |
| | Setting | /cai-dat (két cấu hình LLM) | chỉ Owner |
| | **Sức khỏe hệ** (dòng MỚI duy nhất của v2, chốt Owner 16/08) | /suc-khoe | chỉ Owner |
| Đáy sidebar | Đổi mật khẩu · Đăng xuất | /doi-mat-khau · /logout | mọi người |

Ghi chú kỹ thuật: link NỘI BỘ app tri-thuc trong template được proxy tự viết lại
theo `tien_to` — giữ nguyên dạng V1 (`/hoi-dap`, `/kho-tai-lieu`…). Link CHÉO APP
và link GATEWAY (Data Analytics, NAS, Vault, Nhân sự, User, Phân quyền, Setting,
Sức khỏe, Đổi mật khẩu, Đăng xuất) phải ghi ĐƯỜNG TUYỆT ĐỐI như bảng trên —
tien_to của tri-thuc không viết lại hộ.

## 3. Topbar + hành vi chung (giữ nguyên V1)

- Topbar chữ **OUTLIERY** (wordmark Space Grotesk) + nút gạt ☀/🌙 (khóa
  localStorage `outliery_theme`, data-theme trên `<html>` — KHÔNG media query).
- ☰ mở sidebar ở màn hẹp; **Shift+click** mục sidebar mở cửa sổ rời.
- Brand "Breakout Signal": VOID/PANEL/RADAR BLUE/SLATE/MIST, Inter UI; light
  accent #2C6FC4. Token `--th-*` như V1.
- Khối `<script>` của `hoi_dap.html` **đóng băng byte** theo V1 — cấm sửa.

## 4. Những thứ KHÔNG có trong hợp đồng này

- Trang chủ dạng thẻ app (launcher) — ĐÃ XÓA.
- Tên thư mục kỹ thuật (`tri-thuc`, `to-chuc`, `app-mau`) — KHÔNG được xuất hiện
  trên màn hình người dùng; nhãn hiển thị lấy theo bảng mục 2.
- `app-mau` — khuôn cho dev, không bao giờ hiện trên UI.
