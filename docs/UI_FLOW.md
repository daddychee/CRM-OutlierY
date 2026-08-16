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

## 5. KHU QUẢN TRỊ NỀN (chốt Owner 16/08/2026 — khối đế có giao diện riêng)

Nguyên tắc: **mỗi trang MỘT việc, mỗi việc MỘT đường dẫn** — chấm dứt kiểu
/quan-tri gánh 4 chức năng. Trang /quan-tri, /cai-dat, /suc-khoe cũ NGHỈ HƯU
(redirect sang đường mới, giữ 1 nhịp chuyển tiếp rồi xóa).

| Trang | Đường | Việc | Ai vào |
|---|---|---|---|
| Tổng quan đế | /nen | dịch vụ sống/chết + đế đã nạp gì: tài khoản theo bộ phận×level, key LLM có/chưa, số thực thể danh bạ, backup gần nhất | Owner |
| Tài khoản | /nen/tai-khoan | thêm/xóa/sửa tài khoản IAM | Owner (+giỏ ủy quyền quan_tai_khoan) |
| Nhân sự | /nen/nhan-su | hồ sơ + duyệt hồ sơ | **Owner + Hành chính Nhân sự L3+** (đúng V1) (+giỏ duyet_ho_so) |
| Phân quyền | /nen/phan-quyen | bảng TICK app × tính năng, ô tick lẻ đè mặc định + bật/tắt Admin ủy quyền | chỉ Owner (giỏ owner tuyệt đối) |
| Cấu hình LLM | /nen/cau-hinh | két: provider/model/key theo vai | chỉ Owner |
| Dữ liệu & backup | /nen/du-lieu | sổ địa bạ sống từ apps.json + tuổi backup + backup tay | Owner |
| Nhật ký | /nen/nhat-ky | vết quyền + đăng nhập | Owner |
| Ứng dụng | /nen/ung-dung | hợp đồng app: cổng, health, phiên bản, tiền tố | Owner |

Sidebar KHÔNG đổi hình dạng — chỉ đổi đích: Nhân sự → /nen/nhan-su · User →
/nen/tai-khoan · Phân quyền → /nen/phan-quyen · Setting → /nen/cau-hinh ·
Sức khỏe hệ → /nen (tổng quan đế nuốt trang suc-khoe cũ).

## 6. PHÂN QUYỀN — luật đối chiếu V1 (chốt 16/08/2026)

- Nhân sự: Owner + HR (Hành chính Nhân sự) L3+ — V2 từng khóa mất HR, là LỖI.
- User / Phân quyền / Setting / Giám sát / Vault: chỉ Owner.
- Datafeed / Kho tài liệu / Kho cần bổ sung / Nguồn ngoài: Manager+ (L4).
- Data Analytics: Kinh doanh L2+ hoặc L4+ mọi bộ phận.
- **Giỏ ỦY QUYỀN giữ nhưng mặc định TẮT** (Owner chốt): không bật cho ai thì
  hành vi = V1 đúng 100%; bật từng người ở trang Phân quyền, mọi thao tác có
  vết nhat_ky_quyen. Giỏ Owner tuyệt đối (vault, két, bảng phân quyền, xóa cứng
  tài liệu) KHÔNG ủy quyền được — không tick nào đè.

## 7. MIỀN (chốt Owner 16/08/2026 — 2 giai đoạn)

- **Giai đoạn test (làm ngay):** 2 miền qua Caddy — `outliery.test` (cổng chính:
  đăng nhập + chat + app, đường /app/... như nay) và `quantri.outliery.test`
  (khu nền mục 5; cùng handler với /nen — vào bằng IP vẫn chạy). Máy test thêm
  2 dòng hosts. Cookie đăng nhập đặt Domain miền cha → một đăng nhập chạy mọi
  miền con. HTTPS Caddy tls internal.
- **Giai đoạn thay thế:** bật vai trò DNS Server của Windows Server, zone
  `outliery.lan` wildcard trỏ IP máy chủ, DHCP phát DNS — máy nhân viên không
  cài gì. Lộ trình sau đó: mỗi app một miền con (chat./data./nas./quantri.) để
  BỎ HẲN tầng viết-lại-đường-dẫn trong proxy; nếu công ty có domain thật thì
  thay outliery.lan bằng domain thật + Let's Encrypt (hết cảnh báo trình duyệt).
- Chưa chuyển máy nhân viên nào sang miền test — hệ thật C:\OutlierY không đụng.

## 8. UI TIẾNG ANH + USER MENU KIỂU CLAUDE (chốt Owner 16/08/2026 — đợt 2)

Thay thế bảng nhãn mục 2 (cấu trúc sidebar giữ, NHÃN đổi tiếng Anh; ROUTE giữ
nguyên — chỉ đổi chữ hiển thị, không đổi đường dẫn):

| Cũ (V1) | Mới (EN) | Ghi chú |
|---|---|---|
| tab Home | Home | |
| nút New | New chat | |
| nhãn Công cụ | Tools | NAS RỜI khỏi đây → vào user menu |
| tab Monitoring | **Database** | Owner chốt 16/08 (đổi từ đề xuất Data Center) |
| Datafeed | **Input** | |
| Kho tài liệu | **Library** | |
| Kho cần bổ sung | **Gap** | |
| Nguồn ngoài | GỘP vào **Input** — 2 tab con Upload / External source, route + logic giữ nguyên | chốt Owner |
| Nhân sự (mục sidebar) | BỎ — People nằm trong General | HR L3+ thấy General |
| Gần đây / Xem tất cả lịch sử | Recents / View all history | |
| popup Management | **USER MENU kiểu Claude**: chip đáy sidebar hiện "Display name — Rank" (mọi người) | |
| — trong menu (mọi người) | Profile · Theme (Light/Dark) · NAS (ẩn khi chưa cấu hình) · Log out | |
| — thêm cho Owner | Tracking (= Hoạt động team cũ) · General (= khu nền 8 trang) · Vault | |
| — thêm cho HR L3+ | General (mở vào CHỈ thấy People — 7 trang kia vẫn chặn server-side) | chốt Owner |
| Hoạt động team | Tracking | giữ nguyên chức năng |
| Khu nền: Tổng quan đế / Tài khoản / Nhân sự / Phân quyền / Cấu hình LLM / Dữ liệu & backup / Nhật ký / Ứng dụng | **General**: Overview / Accounts / People / Permissions / AI Models / Data & Backup / Audit Log / Applications | |
| Đăng nhập / Đăng xuất / Đổi mật khẩu | Sign in / Log out / Change password (nằm trong Profile) | |
| Cấp bậc L1..L5 | Intern / Staff / Leader / Manager / Owner | |
| Nút chung | Send · Save · Create · Delete · Apply · Download · Approve | |

**Profile** (trang mới, mọi người): tự sửa Display name + thông tin cá nhân +
Change password (**bắt gõ mật khẩu hiện tại** — vá thiếu sót v2); Bộ phận + Level
CHỈ ĐỌC (Owner quản — nhân viên tự sửa là tự thăng quyền). Chip đáy sidebar hiện
Display name, chưa điền fallback tên đăng nhập.

**Phạm vi dịch đợt này (chốt Owner)**: toàn bộ VỎ điều hướng (sidebar, tab, menu,
nút, khu nền, login). Chuỗi tiếng Việt NẰM TRONG 5 khối script chat đóng băng
(nút Cuộc trò chuyện mới, thông báo chờ…) để ĐỢT RIÊNG — phá đóng băng có chủ
đích + nghiệm thu chat kỹ. Nội dung agent trả lời + tài liệu vẫn tiếng Việt.

**Theme**: mục trong user menu, dùng ĐÚNG cơ chế chung `outliery_theme` +
data-theme; nhân dịp này các trang khu nền bỏ media query về đúng cơ chế chung.
