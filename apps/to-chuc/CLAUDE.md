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
- **tt_nas luôn 'tat'**: nhánh tài khoản NAS trong nas.html là nhánh chờ nas_sync
  về gateway — đừng xóa nhánh đó, cũng đừng tin nó đang chạy.
