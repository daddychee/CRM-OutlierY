# KẾ HOẠCH THAY THẾ HỆ CŨ — checklist + đường lùi

> Chạy KHI VÀ CHỈ KHI Owner đã test bản v2 và ra lệnh thay thế. Trước đó bản v2
> chỉ chạy song song ở dải 9xxx, không đụng hệ thật.

## Điều kiện "go" (tick đủ mới làm)
- [ ] test-all.ps1 XANH toàn bộ (nền + mọi app).
- [ ] Owner đã dùng thử bản v2 ≥ 1 tuần trên dữ liệu bản sao, xác nhận đủ tính năng đang dùng hàng ngày.
- [ ] Backup hệ CŨ mới nhất đã chạy xong + kiểm ket-qua (D:\OUTLIERY-backup).
- [ ] Backup bản v2 chạy xong (tools\scripts\backup.ps1).
- [ ] Chọn khung giờ ít người dùng (tối/cuối tuần), báo team trước.
- [ ] Mua domain + trỏ DNS nội bộ (thay cert tự ký bằng Let's Encrypt DNS-01) — hoặc chấp nhận cert tự ký thêm một thời gian (ghi rõ quyết định).

## Trình tự thay thế (làm đúng thứ tự)
1. **Đóng băng hệ cũ**: stop các Task Scheduler của hệ cũ (OUTLIERY chính + app phụ giữ nguyên — chỉ dừng cổng 8000 agent-app).
2. **Migration dữ liệu thật → v2** (mỗi bước có script, chạy trên bản SAO trước khi chạy thật):
   a. users.txt → iam.db: `python -m nen.iam.nhap_users_txt "C:\OutlierY\apps\AI AGENT\agent-app\users.txt"` (giữ nguyên hash — không ai phải đổi mật khẩu).
   b. Hồ sơ nhân sự ho_so.json + bảng tick phan_quyen.json → iam.db (script viết ở bước này — đối chiếu số người trước/sau).
   c. Kho tài liệu + catalog → data/tri-thuc/kho; nạp lại Qdrant bằng nap_lai_kho (đếm point = số chunk kỳ vọng).
   d. bao-cao-goc + bao-cao-lich-su → data/data-analytics; lich-su chat → data/tri-thuc/db; vault (bản mã) → data/vault; API key các app → Két (tab /cai-dat, nhập tay — key không đi qua file trung gian).
3. **Đổi cổng**: gateway v2 chuyển bind 0.0.0.0:8000 (đổi 1 dòng start-all) HOẶC giữ 9443 + thông báo bookmark mới — Owner chọn trước.
4. **Cắm app phụ thật vào gateway v2**: khai 6 app phụ vào apps.json (cổng thật 8123/8001/7860/8760/...), giữ nguyên *_TRUST_PROXY=1 phía app.
5. **Dựng Task Scheduler cho v2**: 5 tác vụ SYSTEM (qdrant-test→qdrant chính, gateway, các app, caddy, backup 23:00) — mẫu theo deploy-windows hệ cũ.
6. **Nghiệm thu sau swap** (30 phút): đăng nhập 3 vai; hỏi–đáp trích nguồn; upload 1 tài liệu; chạy 1 báo cáo DA; mở từng app phụ qua menu; trang sức khỏe toàn xanh; hỏi số liệu 1 câu.

## ĐƯỜNG LÙI (rollback ≤ 5 phút — quyết ngay khi nghiệm thu sau swap fail)
1. stop-all.ps1 của v2 (hạ gateway v2 khỏi cổng).
2. Start lại Task Scheduler hệ cũ (agent-app cổng 8000 lên lại nguyên trạng — hệ cũ KHÔNG bị sửa gì trong toàn bộ quá trình nên lùi là sạch).
3. Dữ liệu phát sinh trong lúc chạy v2 (nếu có) nằm ở data\ của v2 — không mất, xử lý nhập lại sau.
4. Ghi lại lý do fail → sửa → hẹn lần swap sau.

## Sau thay thế 1 tuần
- Theo dõi logs + sức khỏe hàng ngày; backup chạy đêm có ket-qua sạch.
- Hệ cũ giữ nguyên KHÔNG XÓA tối thiểu 30 ngày (đường lùi dài hạn).
