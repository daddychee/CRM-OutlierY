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
   c. Kho tài liệu + catalog → data/ai-agent/kho; nạp lại Qdrant bằng nap_lai_kho (đếm point = số chunk kỳ vọng).
   d. bao-cao-goc + bao-cao-lich-su → data/data-analytics; lich-su chat → data/ai-agent/db; vault (bản mã) → data/vault; API key các app → Két (tab /cai-dat, nhập tay — key không đi qua file trung gian).
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

## NHẬT KÝ THỰC HIỆN — CUTOVER 22/08/2026 (chạy sớm hơn mốc 00:00 23/08 theo lệnh Owner "chạy luôn")

Owner chốt: bỏ SpeakY (không đưa vào V3) · cutover · phương án điện B1 (bật 9:00 / tắt 20:00).

1. **Backup 3 lớp trước khi đụng** (18:05–18:15): OUTLIERY-Backup V2 chạy tay Result 0;
   backup V3 chạy sạch 38 mục ok / 6 thieu-nguon (vault, cham-cong-chot, kpi, so-thu-chi,
   muc-tieu, ho-so-tai-lieu — tính năng chưa có trong V3, không phải lỗi); bản đóng băng
   `D:\OUTLIERY-backup\CUTOVER-20260823\` (agent-app, plannery, seo, content, niche,
   radary-data, speaky — ~590MB). Bug tìm ra: backup.ps1 thiếu Set-Location root
   (ModuleNotFoundError khi gọi từ ngoài) — đã vá, commit ee45e01.
2. **Tác vụ V3** : `OUTLIERY-V3` (SYSTEM, at-startup + lặp 30 phút — start-all idempotent
   kiêm tự hồi phục app chết; đã nghiệm thu chạy dưới SYSTEM, Result 0, 13 cổng sống),
   `OUTLIERY-V3-Backup` (hằng ngày 19:00).
3. **Đóng băng V2** : 8 tác vụ Stop + Disable (OUTLIERY, PlannerY, SEOOptimize,
   ContentUltimate, NicheResearch, Qdrant, SpeakY, OUTLIERY-Backup; RadarY đã tắt trước
   đó trong ngày — hết đốt đôi quota). Cổng 8000/8123/8760/8770/8780/7860/6333 xác nhận tắt.
4. **Đồng bộ lần cuối V2→V3** (đo diff từng vùng trước khi chép):
   - plan.json: KHÔNG chép — delta 908→909 của V2 là bản ghi rỗng (diff nội dung = 0),
     V3 _rev 945 là nguồn đầy đủ.
   - Chấm công 2026-08: GỘP (min vào / max ra từng người-ngày) — +14 ngày từ V2, 33 bản
     ghi bổ sung; bản V3 trước gộp lưu trong CUTOVER-20260823.
   - SEO Optimize: +17 episodes, 1 episode bản V2 mới hơn đè (bản V3 cũ lưu
     v3-seo-bi-de), +22 runs. Cache LLM bỏ qua.
   - Data Analytics: +8 bao-cao-goc → kho\bao-cao-goc, +2 file lịch sử (thanh,
     kh-ch-56827845). Lịch sử chat: +15 file → data\ai-agent\db\lich-su.
   - KHÔNG cần đồng bộ: kho tài liệu (catalog 19=19), users (iam.db 20 tài khoản phủ đủ
     18 của users.txt), hồ sơ nhân sự (không đổi sau di trú 19/08), niche (30/07),
     content history (07/08 < snapshot), RadarY (V3 là nguồn chuẩn từ 19/08).
5. **Redirect bookmark cũ**: Caddy thêm site :8000 → 301 `http://192.168.1.250:9000{uri}`
   (nghiệm thu sống); giữ 2–4 tuần rồi gỡ khi log hết truy cập.
6. **Phương án điện B1**: hibernate đã bật, wake timers đã bật; tác vụ `OUTLIERY-TatMay`
   20:00 (script tat-may.ps1 — ghi log + cảnh báo nếu backup cũ) + `OUTLIERY-BatMay`
   9:00 (WakeToRun, chạy start-all). Hiệu lực từ 23/08 — đêm 22/08 máy vẫn bật theo dõi.
   Lần thức-từ-hibernate THẬT đầu tiên: 9:00 sáng 24/08 — PHẢI kiểm sáng đó; nếu máy
   không tự dậy → bật BIOS RTC alarm 9:00 làm đường chính, wake timer làm dự phòng.

### Việc treo sau cutover
- [ ] **Vault chưa có trong V3** — dữ liệu két (bản mã) an toàn trong freeze + mirror;
      cần gấp thì Enable lại tác vụ OUTLIERY (V2) tạm để mở vault, xong Disable lại.
- [ ] Kiểm sáng 24/08: máy tự dậy 9:00? (xem logs\tat-may.log + giờ boot).
- [ ] Nghiệm thu 1 vòng restart máy thật (OUTLIERY-V3 at-startup đã test bằng Start-Task,
      chưa test boot lạnh thật).
- [ ] Sau 2–4 tuần: gỡ khối :8000 trong Caddyfile khi hết truy cập.
- [ ] **Sau 30 ngày (~22/09) mới xóa C:\OutlierY**; TRƯỚC khi xóa: chuyển
      `C:\OutlierY\tools\ffmpeg` sang D:\ + sửa VR_FFPROBE trong start-all.ps1
      (video-review đang trỏ vào đó); nén dữ liệu vận hành thành V2-ARCHIVE.
- [ ] VPS Vultr 45.32.107.108 KHÔNG dùng cho phương án này (B1 đủ) — cất mật khẩu
      trong VPS.txt vào vault + đổi mật khẩu root (đang nằm plaintext).
