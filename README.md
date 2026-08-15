# OUTLIERY PLATFORM v2

Bản xây lại hệ OUTLIERY theo kiến trúc tầng nền — chạy SONG SONG hệ thật (cổng 8000)
ở dải cổng riêng 9xxx, dữ liệu test riêng, không đụng `C:\OutlierY`.

- **Hiến pháp kiến trúc (đọc trước khi code):** [docs/kien_truc_nen.md](docs/kien_truc_nen.md)
- Bảng cổng: [docs/PORTS.md](docs/PORTS.md)
- Sổ địa bạ dữ liệu: [docs/SO_DIA_BA_DU_LIEU.md](docs/SO_DIA_BA_DU_LIEU.md)

## Chạy (giai đoạn dev)

```powershell
# lần đầu: tạo venv + cài gói
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# bật/tắt các dịch vụ nền (Qdrant test :6343, sau này gateway :9000...)
powershell -File tools\scripts\start-all.ps1
powershell -File tools\scripts\stop-all.ps1

# test
& .\.venv\Scripts\python.exe -m pytest
```

## Cấu trúc

`nen\` tầng nền (gateway, iam, két, rules, common — tên `nen` vì `platform` trùng
module chuẩn Python) · `apps\` app nghiệp vụ
(mỗi app một nhà tự đủ) · `data\` TÁCH KHỎI CODE (gitignore, backup lo) · `docs\`
tài liệu cấp hệ · `runbook\` tài liệu vận hành cho người · `tools\` binary + scripts.
