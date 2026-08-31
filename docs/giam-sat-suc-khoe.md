# Sổ chủ đề — GIÁM SÁT SỨC KHỎE HỆ (tab Applications thành trạm điều hành)

> Mở sổ 31/08/2026. Mục tiêu Owner đặt: tab App contracts không chỉ báo app
> sống/chết mà check sức khỏe TỪNG MODULE trong từng app + báo ngay khi tính
> năng chạy sai logic. Đã khảo sát open source trước khi code (kết luận: Uptime
> Kuma / Gatus / Healthchecks / GlitchTip chỉ lo tầng probe/alert; tầng "module
> nào đang hỏng" bắt buộc app tự khai — nên MƯỢN 3 pattern (deep health,
> dead-man's switch, condition assertion) và tự xây phần vỏ trong nền V3).
> Kỷ luật mạch này: TEST TRƯỚC (đỏ) → code cho xanh → cả suite → commit riêng.

## Kiến trúc chốt

- **Hợp đồng sức khỏe 2 tầng** trong apps.json:
  - `health` (bắt buộc, có sẵn) = liveness — sống/chết, gateway ping 3s.
  - `suc_khoe` (TÙY CHỌN, mới) = endpoint sức khỏe SÂU theo khuôn
    `nen/common/suc_khoe.py`: `{app, phien_ban, trang_thai, mo_dun:[{ten,
    trang_thai: ok|canh_bao|loi, chi_tiet}]}`. App không khai → hành vi cũ
    y nguyên (không luật mới).
- **Van chống bịa cho giám sát**: check nổ exception là DỮ LIỆU ('loi' + lý
  do), endpoint sức khỏe không bao giờ 500; khai `suc_khoe` mà không trả lời
  được → gateway ghi 'loi' (khai là phải giữ lời); MOCK → 'canh_bao' nói thẳng.
- **Trạm đo lỗi ở proxy** (`nen/common/dem_loi.py` + móc trong
  `nen/common/proxy.py`): mọi request app đi qua chuyen_tiep → 5xx của app /
  cổng chết (502) / timeout (504, trước đây nổ thô thành 500 không vết) đều
  ghi nhận theo CỔNG, cửa sổ trượt 5 phút; vết bền JSON-lines qua nhat_ky
  (app=gateway, hanh_dong=loi_app, trần 60 dòng/cửa sổ chống bão). Bộ đếm
  trong RAM (1 worker, restart về 0 — giới hạn đã biết, khuôn _TAC_VU).
- Tab `/general/applications`: cột **Modules** (xổ chi tiết từng module) +
  cột **Errors 5′** (N lỗi / M request + lỗi gần nhất giờ·status·đường dẫn).
  Template guard `is defined` — bài học Jinja auto-reload 19/08.

## Nhật ký

- **31/08/2026 — B1+B2+B3 xong, test-first từng bước** (repo cha 73a690a B1 ·
  a1063b7 B2 · f049422 B3; plannery repo lồng 4aeab76). Baseline trước khi làm:
  237 pass / 1 fail (test_content_ultimate ghim hợp đồng — của mạch OUTLINE
  30-31/08, không đụng). Sau: root 253 pass / 1 fail đó; app ai-agent 312 pass.
  - B1: khuôn suc_khoe + app-mau làm mẫu `/api/suc-khoe` + gateway _do_dich_vu
    đọc tầng sâu + cột Modules. Điều tra health lệch: content-ultimate /
    niche-research / seo-optimize khai `/api/health` ĐỀU SỐNG THẬT (agent grep
    không thấy vì layout khác — probe runtime mới là sự thật); plannery +
    rendery mượn `/api/me` (endpoint auth) làm health → plannery đã có /health
    thật (commit ở repo lồng) + apps.json đổi; RENDERY CÒN NỢ (code ở
    F:/RenderY repo riêng, app có job dựng nền — không sửa/restart bừa).
  - B2: dem_loi + móc proxy + cột Errors 5′ (7 test: cửa sổ trượt, vết bền,
    trần chống bão, 5xx/502/504 qua proxy thật, tab render).
  - B3 exemplar ai-agent: `/api/suc-khoe` module kho-vector = lưới sự cố 31/07
    (kho Qdrant RỖNG 3 ngày, hỏi–đáp chết lặng lẽ) trồi lên hợp đồng — catalog
    có tài liệu + kho 0 point → loi kèm chỉ đường nap_lai_kho.py; không gọi
    LLM trong health.
  - Phiên song song: mạch két API-keys (main.py/ket.py/nen_api_keys.html) đang
    treo uncommitted → commit bằng phẫu thuật index (dựng nội dung index =
    HEAD + đúng vùng sửa của mạch này, hash-object + update-index), không quét
    hunk của mạch két. Bẫy gặp: anchor nhiều dòng chết vì CRLF — anchor 1 dòng.
  - DEPLOY CHỜ TAY OWNER: classifier chặn Stop-Process — cần dừng 3 tiến trình
    theo cổng (9000 gateway, 9116 plannery, 9101 ai-agent) rồi
    `schtasks /run /tn OUTLIERY-V3` (start-all tự bỏ qua app còn sống). Máy
    reboot 9:00 hằng ngày cũng tự ăn bản mới nếu không restart tay.

## Việc còn (theo thứ tự đề xuất đã duyệt hướng)

- [ ] **Nghiệm thu sống sau restart**: tab Applications hiện Modules ai-agent
      (kho thật :6343 → ok "N point / M tài liệu"); plannery Status xanh với
      /health mới; thử 1 request lỗi xem cột Errors 5′.
- [ ] **B3 lan dần**: khai `suc_khoe` cho radary (giờ quét cuối + quota),
      to-chuc (chấm công hôm nay), rendery/thumby (ffmpeg + đĩa), plannery
      (plan.json đọc được + _rev)… mỗi app một commit, test trong app.
- [ ] **Rendery /health thật** (repo F:/RenderY/autoedit — sửa + restart lúc
      không có job dựng; apps.json đang tạm giữ /api/me).
- [ ] **B4 heartbeat việc nền** (pattern Healthchecks): sổ việc-phải-chạy-đúng-
      hạn (backup 19:00, quét RadarY, BatMay 9:00) + POST /api/nhip-viec/<ma>;
      quá hạn → đỏ trên tab.
- [ ] **B5 cảnh báo ngay**: lift ntfy_send của radary lên nen/common + luật
      (chết ≥2 ping liên tiếp / module loi / heartbeat trễ) + gộp chống spam.
- [ ] **B6 canary tính năng thật** (pattern Gatus conditions): 15'/lần gọi vài
      đường end-to-end với kỳ vọng cụ thể (search có chunk, SSO đúng vai).
- [ ] Gatus binary đứng NGOÀI gateway làm lưới cuối (gateway chết thì ai báo?)
      — cân nhắc sau khi B5 chạy.
