# SỔ ĐỊA BẠ DỮ LIỆU — OUTLIERY

> "Code là công cụ — xóa đi dựng lại được từ git. Database là TÀI SẢN — mất là mất
> vĩnh viễn." Sổ này trả lời: công ty đang có dữ liệu gì, nằm đâu, quý cỡ nào,
> backup kiểu gì, khôi phục thế nào. Bản máy đọc: `nen\rules\apps.json`
> (mục `du_lieu` từng app). Đổi nơi chứa dữ liệu = PHẢI cập nhật cả hai.

## Mức quý

- 🥇 **vàng** — mất là mất vĩnh viễn (tài liệu, lịch sử, hồ sơ, báo cáo, vault)
- 🥈 **bạc** — mất thì đau nhưng gom lại được (log job, cache phân tích)
- 🔄 **tái-sinh** — sinh lại được từ nguồn khác (thumbnail, bản đẹp, index)

## Luật backup theo loại store

| Loại | Cách backup | Cấm |
|---|---|---|
| SQLite đang chạy | `VACUUM INTO` / SQLite backup API → file snapshot | copy trần file .db đang mở |
| Qdrant | snapshot qua API (đã có tiền lệ hệ cũ) | copy trần thư mục storage đang chạy |
| JSON/CSV store | copy được (ghi nguyên tử tmp+replace nên file luôn lành) | — |
| Kho file năm/tháng | copy 2 tầng (gương + theo-ngày) như hệ cũ | — |
| `xuat\` | không backup (tái sinh được) | — |

## KIỂM KÊ TÀI SẢN HIỆN TẠI (hệ cũ C:\OutlierY — chụp 16/08/2026)

| App | Store | Mức quý | Ghi chú di trú |
|---|---|---|---|
| AI Agent | kho-tai-lieu\ + _catalog.csv | 🥇 | → data\tri-thuc\kho + db |
| AI Agent | Qdrant collection kho_v1 (alias kho_tri_thuc) | 🥈 (dựng lại được từ kho bằng nap_lai_kho.py — nhưng coi như 🥇 vì tốn công) | → Qdrant test :6343 |
| AI Agent | users.txt + ho_so.json + phan_quyen.json | 🥇 | → iam.db (P2) |
| AI Agent | lich-su\*.json (hội thoại per-user) | 🥇 | → data\tri-thuc\db |
| AI Agent | nhan-su\ (hồ sơ, chấm công) | 🥇 | → iam.db + data\to-chuc |
| AI Agent | bao-cao-goc\ + bao-cao-lich-su\ | 🥇 | → data\data-analytics (kho năm/tháng + db) |
| AI Agent | phan_hoi.csv, nhom_kho_thieu.json, nhap-phan-tich\ | 🥇 | → data\tri-thuc |
| AI Agent | vault\ (bản mã AES) | 🥇 | → data\vault (chỉ bản mã, như cũ) |
| RadarY | radary.db + data\niche\*\analysis.json | 🥇 | giữ nguyên app phụ |
| RadarY | thumbs\ | 🔄 | loại khỏi backup theo-ngày (đã đúng) |
| PlannerY | plan.json (+backups\ 40 bản tự giữ) | 🥇 | giữ nguyên |
| Content | picks/outline/history.jsonl + admin\ | 🥇 | giữ nguyên |
| SEO Optimize | profiles\ niches\ episodes\ users.json audit | 🥇 | giữ nguyên |
| SpeakY | jobs_log.csv + profiles | 🥈 | giữ nguyên |
| SpeakY | audio out | 🔄 | — |
| Niche Research | projects\<ngách>\ (signals, snapshots, report) | 🥇 | giữ nguyên |

## Trạng thái bản v2 (cập nhật khi mỗi phase xong)

- P0 (16/08/2026): `data\` mới chỉ có `qdrant\` (trống). Dữ liệu test sẽ là BẢN SAO
  từ `D:\OUTLIERY-backup` — chỉ đọc backup, không đụng dữ liệu sống hệ cũ.
- Ổ đĩa: bản test nằm cùng ổ D với OUTLIERY-backup — CHẤP NHẬN cho test; khi thay
  thế thật phải chốt lại: dữ liệu sống và backup KHÔNG chung ổ.
