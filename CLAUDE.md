# CLAUDE.md — OUTLIERY PLATFORM v2 (bản đồ gốc)

> Repo này là bản XÂY LẠI hệ OUTLIERY theo kiến trúc tầng nền, chạy SONG SONG hệ
> thật (C:\OutlierY, cổng 8000) — dải cổng 9xxx, dữ liệu test riêng. Khi Owner
> nghiệm thu xong mới thay thế hệ cũ.
>
> **ĐỌC TRƯỚC KHI CODE: [docs/kien_truc_nen.md](docs/kien_truc_nen.md)** — hiến pháp
> kiến trúc (3 tầng, 6 luật tổ chức, hợp đồng app, IAM, bất biến kế thừa).
> Theo Luật 3 (CLAUDE.md phân tầng): file này CHỈ là bản đồ + trạng thái;
> mốc/bài học của app nào ghi vào `apps/<app>/CLAUDE.md` của app đó.

## Luật an toàn tuyệt đối (giai đoạn song song)

1. KHÔNG sửa file trong `C:\OutlierY`; không restart tác vụ nền hệ thật.
2. Qdrant test = :6343 (tools\qdrant, storage data\qdrant) — kho thật :6333 cấm đụng.
3. Dữ liệu test lấy BẢN SAO từ `D:\OUTLIERY-backup` (chỉ đọc backup).
4. Cổng mới phải ghi `docs/PORTS.md` trước khi code; chỉ dải 9xxx.

## Bản đồ

- `nen\` — tầng nền: gateway, iam, ket_cau_hinh, rules (luật cả hệ: danh_muc.csv,
  apps.json), common (danh_ba.py…). Tên `nen` vì `platform` trùng stdlib Python.
- `apps\` — app nghiệp vụ tự đủ: tri-thuc, data-analytics, to-chuc, app-mau.
- `data\` — TÁCH KHỎI CODE, gitignore, backup theo SO_DIA_BA_DU_LIEU.md.
- `docs\` — hiến pháp, PORTS, sổ địa bạ. `runbook\` — tài liệu vận hành cho người.
- `tools\` — qdrant test, scripts start-all/stop-all.ps1.

## Trạng thái (cập nhật mỗi mốc)

- 16/08/2026 — **PHASE 0 XONG**: cây thư mục + git + hiến pháp + PORTS + sổ địa bạ
  dữ liệu + danh bạ thực thể (`nen/rules/danh_muc.csv` seed 4 dòng + `nen/common/
  danh_ba.py`, 13 test pass) + venv + Qdrant test :6343 đã chạy thử readyz-200 song
  song kho thật :6333 + scripts start/stop kiểm chứng. Bài học: package tầng nền
  đặt tên `nen` — `platform` trùng module chuẩn Python (bắt trước khi nổ).
- KẾ TIẾP — PHASE 1 Gateway :9000: đăng nhập/session, proxy theo hợp đồng app,
  claims, app-mau :9190, /suc-khoe + tự restart, Caddy TLS tự ký :9443.
