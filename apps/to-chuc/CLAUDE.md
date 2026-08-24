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
