# Tasky (:9117) — kế hoạch tuần của nhân sự

Leader giao **việc** tuần cho nhân sự → nhân sự **nhận việc** rồi tự viết
**checklist** cách mình sẽ triển khai → làm xong tick → quản lý xem **khối lượng**
và **tỉ lệ hoàn thành**. Không mục tiêu tầng trên, không trọng số, không điểm số.

Đặc tả đầy đủ: **FLOW-v3.md** (bản đang theo; v1/v2 giữ làm mốc lịch sử).
Bản dựng hình giao diện: `mockup/UI-v2.html` (Owner duyệt 24/08) — chỉ để duyệt,
app thật `extends base.html` của hệ, không lấy CSS từ mockup.

## Chạy

```powershell
# từ ROOT repo
python -m uvicorn src.main:app --app-dir "apps/tasky" --port 9117
```

Vào qua cổng OUTLIERY: `http://<IP>:9000/tasky`. Gọi thẳng :9117 không có claims
sẽ 401 — app không giữ sổ user, danh tính do gateway tiêm.

## Test

```powershell
cd apps/tasky
pytest
```

## Env

| Biến | Mặc định | Việc |
|---|---|---|
| `TASKY_DIR` | `data/tasky/db` | Gốc dữ liệu: `tuan/YYYY-Www.json` + `nhat-ky.jsonl` |

## Quyền (khai ở `nen/rules/phan_quyen.json`)

| Hành động | Mặc định | Việc |
|---|---|---|
| `vao` | L1 | Vào app, xem việc **của mình** |
| `giao_viec` | L3+ | Giao việc — app kiểm thêm ở server: level người giao > level người nhận **và** cùng bộ phận (Owner giao mọi bộ phận) |
| `xac_nhan_ket_qua` | L3+ | Xác nhận việc báo xong + đóng tuần |
| `bao_cao_bo_phan` | L3+ | Báo cáo bộ phận mình |
| `bao_cao_cong_ty` | L4+ | Báo cáo mọi bộ phận (giữ lệ 04/08) |
| `bao_cao_nhan_su` | L3+ HCNS | HR xem toàn công ty để chấm công + xếp loại KPI |

Tên hành động **tránh 5 từ khóa** `xoa/toan_quyen/sua/tao/them` — `iam.vai_cho_app()`
dò substring các từ đó để suy X-Remote-Role gửi sang app khác (bẫy `nas_toan_quyen`
18/08). Thêm hành động mới phải chạy `pytest tests/test_iam.py` ở ROOT.

## Tiến độ

- [x] **B1** Khung app + claims + đăng ký 4 chỗ (PORTS.md · apps.json · phan_quyen.json · start-all.ps1)
- [x] **B2** Lõi `src/tuan.py`: sổ tuần + luật giao/nhận/từ chối/tick/xác nhận/dời/hủy/đóng tuần + thống kê (32 test)
- [x] **B3** Màn *Việc của tôi* + API `/api-tasky/*` (nhận · từ chối có lý do · viết/tick checklist · báo xong · tự thêm việc)
- [ ] B4 Màn *Giao việc* + xác nhận + đóng tuần
- [ ] B5 Màn *Báo cáo* (4 phạm vi)
- [ ] B6 Kho quy trình — mới đếm/thống kê, chưa gợi ý

## Việc treo

- Icon sidebar: `_icon_app.html` của mỗi app có bản riêng (Luật 4). Slug `tasky`
  chưa có nhánh nên đang là ô vuông mặc định — thêm nhánh vào các bản khi làm B3.
- Chưa nối app nào (Luật 4 + FLOW-v3 §9.5). Chiều nối tương lai: **Tasky → PlannerY**,
  task đã chừa sẵn trường `nguon_ngoai`.
