# CLAUDE.md — app to-chuc (KPI + chấm công + NAS + Vault)

> Nhật ký + bài học CỦA RIÊNG app này (Luật 3). Kiến trúc chung: `docs/kien_truc_nen.md`.

## App làm gì

Mạch TỔ CHỨC di trú từ agent-app hệ cũ: **/kpi** (Manager+, bảng KPI 4 nguồn chỉ-đọc
+ chấm công ngày) · **/api/nhip, /api/nhip-thoat** (tín hiệu hiện diện) · **/nas** +
**/nas/cai-dat/{so}** (chỉ đường ổ NAS, mọi người) · **/vault*** (két tài khoản số,
CHỈ Owner). Chi tiết env + việc treo: README.md.

## Mốc

- 16/08/2026 — **DI TRÚ P5 (to-chuc) XONG**: copy nguyên `cham_cong.py` + `vault.py`;
  `kpi.py` chuyển thể (bỏ import chéo `src.bao_cao_lich_su` — Luật 4 — thay bằng đọc
  file BAO_CAO_DIR của data-analytics, THÊM ca nguồn chết → None + `thieu["bao_cao"]`);
  route trích từ app.py cũ (NAS + nhịp + vault), trang /kpi MỚI thay khối KPI của
  /nhan-su (hồ sơ đã về IAM); danh sách người cho KPI đọc CHỈ-ĐỌC `nen/iam` khoan
  dung (IAM chết → nói thẳng, không bảng rỗng giả). Claims 4 header, Dept unquote.
  Mặc định 4 nguồn KPI KHÔNG trỏ C:\OutlierY hệ thật — nguồn chết → "—".
- 18/08/2026 — **ĐƯA NAS TRỌN VÀO V2**: mạch `nas_sync` (tài khoản Windows đồng bộ
  theo mật khẩu OUTLIERY, từng để "việc treo" hôm 16/08) đã nối xong. Module sống ở
  `nen/common/nas_sync.py` (mảnh tầng nền, KHÔNG import IAM — nhận `nhom` làm THAM
  SỐ); GATEWAY gọi `dong_bo_nen()` ở 3 chỗ biết mật khẩu thật: đăng nhập đúng
  (`/login`), tự đổi mật khẩu (`/profile/mat-khau`, `/doi-mat-khau`). App này CHỈ ĐỌC
  `nas_sync.bat()`/`trang_thai()` để vẽ khung "Your account" — bỏ hẳn `_nas_dong_bo_bat()`
  cục bộ. Nhóm Windows (ToanQuyen/ChiThem) tính qua hành động `nas_cap_cao`
  (`nen/rules/phan_quyen.json` apps.to-chuc, mặc định level>=3) — MỘT CỬA
  `iam.co_quyen()` nên ô tick lẻ + cấp truy cập (acting) tự ăn theo, không cần code
  riêng như `phan_quyen.py` hệ cũ. Sổ trạng thái chuyển sang `data/nen/nas-dong-bo.json`
  (khai trong apps.json `du_lieu_nen`, Luật 6).
  **BẪY ĐẶT TÊN (dính thật, test bắt được)**: đặt tên hành động ĐẦU TIÊN là
  `nas_toan_quyen` — `iam.vai_cho_app()` dò SUBSTRING `"xoa"`/`"toan_quyen"` để tự
  suy X-Remote-Role gửi sang app (đúng dùng cho hành động NGHIỆP VỤ của app, ví dụ
  xóa dự án), nên tên chứa "toan_quyen" bị NUỐT NHẦM vào luật đó — bất kỳ ai đủ
  `nas_cap_cao` (level>=3) đều bị đẩy vai `admin` sang MỌI app khác dùng chung khóa
  đó. Đổi tên thành `nas_cap_cao` (không chứa `xoa`/`toan_quyen`/`sua`/`tao`/`them`)
  là sửa dứt điểm. BÀI HỌC: đặt tên hành động IAM mới PHẢI tránh 5 từ khóa đó trừ
  khi CỐ Ý muốn nó ảnh hưởng vai app — `test_iam.py` có test cách ly app-này-không-
  lây-app-kia, chạy `pytest tests/test_iam.py` ở ROOT sau khi thêm hành động mới.
  **VIỆC TREO** (ghi trong `nen/common/nas_sync.py` đầu file): Owner cấp/reset mật
  khẩu người KHÁC (trang /nen/tai-khoan) chưa gọi `dong_bo_nen`; đổi level/khóa tài
  khoản chưa nối `doi_nhom_nen`/`vo_hieu_nen` — người bị đổi cấp/khóa giữ quyền NAS
  cũ tới lần đăng nhập/đổi mật khẩu kế tiếp.

- 26/08/2026 — **FINANCE HUB: nghiên cứu lõi mã nguồn mở → 18 tính năng, Owner chốt
  spec + giao diện**. Sổ riêng: `docs/finance-hub.md` (quyết định, cái đã bác bỏ,
  schema bút toán sau đợt A, thứ tự thi công). Chốt chính: **KHÔNG thay engine bằng
  beancount/hledger** (engine một-người, dòng lệnh, không RBAC) — mượn 6 khái niệm
  + xuất `.beancount` để dùng Fava làm phòng báo cáo. Mockup: v2 `docs/mockup-de/
  finance-hub-v2.html` (đã chốt), v3 `finance-hub-v3.html` (thêm D1–D4 Owner bổ sung
  26/08: bảng lương từ chấm công · tài khoản trả phí không kèm mật khẩu · chi phí
  ngách theo ngày công · lịch chốt 10–12 và trả lương 15), v4 `finance-hub-v4.html`
  (Dashboard 6 biểu đồ + D5 phiếu lương + D6 cảnh báo đi muộn) — **chờ duyệt**.
  **Owner chốt vòng 3 (26/08):** chấm công chỉ đo GIỜ CÓ MẶT (mở CRM), trong phiên
  không đo — `tong_giay` nghỉ hưu khỏi bảng lương, `so_ngay` là số dùng; **đi muộn
  chỉ CẢNH BÁO, máy không tự trừ lương**, đường duy nhất ảnh hưởng lương là ô "điều
  chỉnh HR" có lý do bắt buộc; quyền Finance mở cho **cả giỏ `nhan_su`** (HR) lẫn
  `ke_toan` — bỏ ý định tách giỏ `finance_luong` (cơ cấu 2 người); HR xuất + gửi
  phiếu lương kèm báo cáo hiệu suất, phiếu là **trang HTML in được** (KHÔNG WeasyPrint
  — máy này thiếu GTK, 3 test `test_remake_dep` fail từ 29/07); dashboard dùng
  **frappe-charts vendor** như Tasky, nhớ bẫy "thư viện không đọc CSS var, đổi theme
  phải vẽ lại". Spec thi công: `docs/finance-hub-spec.md`.
  **Mã ô mockup = mã tính năng trong sổ** (A1…D4), một hệ mã cho cả UI lẫn spec.
  BA ĐIỂM CHẠM APP KHÁC (Luật 4 — đọc, không ghi): `cham_cong.bang_cong_thang` +
  `chot_ky` cho bảng lương; `data/plannery/plan.json` `projects[].ngach_ma` +
  `assignments[]` cho chi phí ngách (person_id `ns_<mã NS>` khớp IAM); `quota_log`
  cho tiền API. **Vault chỉ cho `vault_id`** — metadata gia hạn ở sổ Finance riêng,
  mật khẩu không rời két. LƯU Ý: sổ tiền đang RỖNG (0 bút toán) nên đổi cấu trúc
  bản ghi bây giờ là miễn phí — đợt A phải xong trước khi mở cho kế toán ghi thật.

- 26/08/2026 — **FINANCE HUB CODE XONG ĐỢT A + D** (8 commit, mỗi bước pytest xanh
  trước khi commit; 116 test app / 232 test root). Trang `/finance` giờ 9 tab:
  Tổng quan (dashboard + lịch tài chính) · Sổ thu chi · Ví · Mục tiêu · Kênh ·
  Ngách · Lương · Thuê bao · Danh mục. **Đã restart app trên CRM 26/08.**
  MODULE MỚI: `src/luong.py` (D1 bảng lương + D6 đi muộn) · `src/chi_phi_ngach.py`
  (D3) · `src/lich_tai_chinh.py` (D4) · `src/templates/phieu_luong.html` (D5).
  RULES MỚI (luật ngoài code): `danh_muc_vi.csv` · `he_so_xep_loai.csv` ·
  `gio_lam_viec.csv` · `ngay_nghi_le.csv` (**Owner cần điền lễ 2026-2027**).
  BA CHỖ SUÝT VI PHẠM SỔ CHỈ-THÊM, đã sửa trước khi chạy: gắn tên tệp chứng từ
  SAU khi ghi bút toán · gắn nhãn `nguon` sau khi ghi · validate tệp bằng cách
  ghi thử vào kho. Cả ba đều thành "chốt dữ liệu TRƯỚC, ghi sổ SAU".
  BẪY MỚI: test từng ghi ra `apps/to-chuc/nhan-su/ty-gia` THẬT vì conftest chưa
  cách ly `TY_GIA_DIR` — đã dọn + cách ly thêm 4 env (TY_GIA_DIR, CHUNG_TU_DIR,
  DICH_VU_PATH, LUONG_DIR). Thêm store mới thì PHẢI thêm env vào conftest.
  Chi tiết + spec: `docs/finance-hub.md` + `docs/finance-hub-spec.md`.

- 26/08/2026 (tiếp) — **FINANCE HUB XONG TOÀN BỘ 18 TÍNH NĂNG**, 147 test app.
  Module mới đợt này: `src/don_vi_kinh_te.py` (B2) · `src/tu_dong.py` (B5 đối soát
  AdSense + C3 tiền API từ quota log + C2 luật gợi ý) · `templates/doi_soat.html`;
  thêm vào `tai_chinh.py`: `pnl_phan_bo` (B1) · `muc_dot` (B3) · `ngan_sach_ky` +
  `dat_han_muc` (B4) · `chot_ky_tien` + `doi_chieu_vi` (C5).
  **BÀI HỌC UI ĐẮT NHẤT MẠCH NÀY** (Owner bắt lỗi 3 lần liên tiếp): tôi dựng trang
  từ trí nhớ + khuôn app thay vì mở tệp mockup đặt cạnh chép từng khối, rồi báo
  "xong" dựa trên test xanh. Ba lần sai: (1) chỉ đổi nhãn tab, thân trang vẫn bản
  cũ tiếng Anh; (2) tab Tổng quan thiếu 4/6 khối; (3) tự đặt `max-width:1180px`
  làm trang co lại giữa màn trong khi mockup tràn khung, thanh lọc và form sai kiểu.
  **Từ nay: mỗi thay đổi UI phải chụp lại trang thật bằng Chrome headless
  (`--headless=new --screenshot`, ép `data-theme="dark"` để so đúng cặp) và đối
  chiếu mockup TRƯỚC khi báo.** Test xanh không chứng minh giao diện đúng.
  Bài học thứ hai: phần chưa code thì giữ nguyên vị trí khối kèm nhãn "chưa có
  module" (như mốc đối soát trong Lịch tài chính), ĐỪNG cắt bỏ tab — cắt đi thì
  trang trông như một sản phẩm khác hẳn bản đã duyệt.

## Bài học / bẫy riêng app

- **Điểm hứng chấm công đổi tầng**: hệ cũ hứng MỌI app ở cổng 8000; v2 app chỉ hứng
  request của mình → số giờ sẽ THẤP hơn hệ cũ cho tới khi gateway hứng toàn hệ
  (việc treo README). Đừng đọc số chấm công v2 như "giờ làm cả hệ".
- **kpi_bao_cao đổi hợp đồng có chủ đích**: hệ cũ luôn trả dict (nguồn nhà); v2 trả
  `None` khi BAO_CAO_DIR không tồn tại — nguồn giờ là app khác, chết được. Template
  và test đã theo; ai tái dùng hàm phải xử None.
- **Khuôn tên file bao-cao đôi nơi**: `kpi._ten_file_bao_cao` COPY từ
  `bao_cao_lich_su._ten_file` (data-analytics). Đổi khuôn bên đó phải đổi đây.
- **Trạng thái RAM trong test**: vault giữ DEK + cham_cong giữ throttle `_da_ghi`
  ở module-level → conftest phải `vault.khoa()` + `_da_ghi.clear()` mỗi test, và
  IAM_DB phải trỏ tmp kẻo route /kpi TỰ TẠO iam.db thật (ket_noi chạy migration).
  Từ 18/08 THÊM `nas_sync._da_dong_bo_phien.clear()` + `NAS_SO_DUONG` trỏ tmp (cùng
  họ trạng thái RAM module-level) — conftest đã cập nhật.
- **tt_nas ĐÃ SỐNG (18/08/2026)**: nhánh tài khoản NAS trong nas.html không còn là
  nhánh chờ — đọc thật `nas_sync.trang_thai()`/`bat()` (mốc phía trên). Chỉ 'tat' khi
  NAS_DONG_BO tắt (mặc định máy dev/test) — đúng nghĩa, không phải "chưa mang sang".
