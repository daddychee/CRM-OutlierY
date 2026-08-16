# BẢNG CỔNG — OUTLIERY PLATFORM v2 (giai đoạn test song song)

## Dải cổng bản v2 (9xxx + 6343/6344)

| Cổng | Dịch vụ | Ghi chú |
|---|---|---|
| 9000 | Gateway (HTTP) | Cửa vào duy nhất giai đoạn dev |
| 9443 | Caddy TLS → gateway | Cert tự ký giai đoạn test; domain thật khi thay thế |
| 9101 | apps/ai-agent | Hỏi–đáp RAG + kho tài liệu + nguồn ngoài |
| 9102 | apps/data-analytics | Chẩn đoán số liệu |
| 9103 | apps/to-chuc | KPI + chấm công + NAS |
| 9111 | apps/radary | RadarY (đưa vào 16/08 — mạch APPS.md) |
| 9190 | apps/app-mau | App mẫu chứng minh hợp đồng app |
| 6343 | Qdrant test (HTTP) | storage: data\qdrant — TÁCH HẲN kho thật |
| 6344 | Qdrant test (gRPC) | phải khai tường minh kẻo rơi về 6334 đụng hệ thật |

## Cổng hệ THẬT đang chạy — CẤM ĐỤNG

8000 (OUTLIERY cổng chính) · 8123 / 8001 / 7860 / 8760 (app phụ) ·
6333 / 6334 (Qdrant thật) · 8199 / 8761 (dải bản-sao-cô-lập hệ cũ hay dùng).

Quy tắc: dịch vụ v2 mới = lấy cổng 91xx kế tiếp, ghi vào bảng này TRƯỚC khi code.
Mọi dịch vụ bind 127.0.0.1 trừ gateway/Caddy (LAN khi nghiệm thu).
