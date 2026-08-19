# BẢNG CỔNG — OUTLIERY PLATFORM v2 (giai đoạn test song song)

## Dải cổng bản v2 (9xxx + 6343/6344)

| Cổng | Dịch vụ | Ghi chú |
|---|---|---|
| 9000 | Gateway (HTTP) | Cửa vào duy nhất — **MỞ LAN cho team 19/08**: `http://192.168.1.250:9000` (bind 0.0.0.0, firewall rule OUTLIERY-V3-9000 Private/Domain; app phụ vẫn loopback, proxy cắt x-remote-* từ ngoài) |
| 9443 | Caddy TLS → gateway | Cert tự ký giai đoạn test; domain thật khi thay thế |
| 9101 | apps/ai-agent | Hỏi–đáp RAG + kho tài liệu + nguồn ngoài |
| 9102 | apps/data-analytics | Chẩn đoán số liệu |
| 9103 | apps/to-chuc | KPI + chấm công + NAS |
| 9111 | apps/radary | RadarY (đưa vào 16/08 — mạch APPS.md) |
| 9112 | apps/content-ultimate | Content Ultimate (đưa vào 16/08 — mạch APPS.md) |
| 9113 | apps/niche-research | Niche Research (Owner chen lên app #3 — 18/08) |
| 9114 | apps/video-review | Video Review — feedback video kiểu Frame.io (app V3 mới 18/08) |
| 9115 | apps/seo-optimize | SEO Optimize (đưa vào 19/08 — APPS.md app 4/6) |
| 9116 | apps/plannery | PlannerY — điều phối sản xuất (đưa vào 19/08 — APPS.md app 5/6) |
| 9190 | apps/app-mau | App mẫu chứng minh hợp đồng app |
| 6343 | Qdrant test (HTTP) | storage: data\qdrant — TÁCH HẲN kho thật |
| 6344 | Qdrant test (gRPC) | phải khai tường minh kẻo rơi về 6334 đụng hệ thật |

## Cổng hệ THẬT đang chạy — CẤM ĐỤNG

8000 (OUTLIERY cổng chính) · 8123 / 8001 / 7860 / 8760 (app phụ) ·
6333 / 6334 (Qdrant thật) · 8199 / 8761 (dải bản-sao-cô-lập hệ cũ hay dùng).

Quy tắc: dịch vụ v2 mới = lấy cổng 91xx kế tiếp, ghi vào bảng này TRƯỚC khi code.
Mọi dịch vụ bind 127.0.0.1 trừ gateway/Caddy (LAN khi nghiệm thu).
