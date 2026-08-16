# KIẾN TRÚC NỀN — OUTLIERY PLATFORM v2 (HIẾN PHÁP)

> Văn kiện gốc của bản xây lại `D:\AI AGENT OUTLIERY`. Mọi phiên code (người hay AI)
> phải bám tài liệu này. Chốt qua chuỗi phiên bàn 16/08/2026 với Owner.
> Nguồn gốc: hệ OUTLIERY hiện tại (C:\OutlierY, cổng 8000) chạy tốt từng app nhưng
> thiếu TẦNG NỀN — 7 vấn đề Owner nêu: scale 30-50 người, HTTPS, kết nối app,
> backup/dữ liệu/log, nâng cấp độc lập, API/LLM chồng chéo, user/quyền rối.
> Bản v2 xây tầng nền + di trú nghiệp vụ; KHI NGHIỆM THU XONG mới thay thế hệ cũ.

---

## 1. Kiến trúc 3 tầng

```
        🧠 TẦNG TRÍ TUỆ (AI)
        Hỏi–đáp RAG · Chẩn đoán · Đa chiều · Briefing
        — nhìn xuống toàn hệ qua CONNECTOR chỉ-đọc + kho tri thức —
┌────────────────────────────────────────────────────────────┐
│  TẦNG NGHIỆP VỤ — apps độc lập, tự đủ, thay được            │
│  ai-agent · data-analytics · to-chuc · (app phụ giữ nguyên: │
│  RadarY · PlannerY · Content · SpeakY · SEO · Niche)        │
└────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────┐
│  TẦNG NỀN (Platform Core)                                    │
│  ① GATEWAY  : HTTPS, đăng nhập, session, proxy, /suc-khoe   │
│  ② IAM      : người–tài khoản–vai–quyền — MỘT sổ (iam.db)   │
│  ③ KÉT      : config + secret (API key, model LLM) — MỘT chỗ│
│  ④ DANH BẠ  : thực thể kênh/ngách — MỘT tên cho một vật     │
│  ⑤ CHUẨN    : data tách code, log chuẩn, backup manifest    │
└────────────────────────────────────────────────────────────┘
```

Nguyên tắc phân tầng: **app nghiệp vụ chỉ làm nghiệp vụ** — không app nào tự giữ sổ
user, tự giữ key, tự quyết đường dữ liệu. Mọi thứ "của chung" sống ở tầng nền.

## 2. Đối chiếu chuẩn mở — kế thừa từ đâu (chốt 16/08/2026)

| Mảnh | Kế thừa từ |
|---|---|
| App tự đủ + manifest tự khai | Odoo addons (`__manifest__.py`), Nextcloud (`appinfo/info.xml`), Frappe (`hooks.py`) |
| IAM một sổ, app chỉ nhận claims | Odoo `res.users`/groups, Keycloak (identity ≠ account ≠ role) |
| Nhật ký thay đổi quyền | Keycloak admin events, Frappe Version log |
| Két config/secret tách khỏi code | HashiCorp Vault, 12-factor (factor III) |
| Gateway + health endpoint | chuẩn reverse-proxy + Kubernetes liveness |
| Dữ liệu chia năm/tháng | Hive-style partitioning (data lake) |
| **DB riêng từng app** (lệch Odoo có chủ đích) | Self-contained Systems (scs-architecture.org) — hợp hiện trạng đã per-app + yêu cầu nâng cấp độc lập; NGOẠI LỆ: IAM là MỘT sổ chung |

Ba điều bắt buộc rút từ đối chiếu:
1. **Migration có phiên bản**: mỗi app có `migrations\` + bảng `schema_version` trong DB.
2. **DB sống backup qua LỆNH snapshot** (SQLite backup API / `VACUUM INTO`; Qdrant qua
   snapshot API) — TUYỆT ĐỐI không copy trần file DB đang mở.
3. **Config ≠ Secret**: hai ngăn tách bạch trong két (UI có thể chung một trang).

## 3. Bảng cổng (chi tiết: docs/PORTS.md)

Gateway :9000 (HTTP) / :9443 (Caddy TLS) · app-mau :9190 · ai-agent :9101 ·
data-analytics :9102 · to-chuc :9103 · Qdrant test :6343 (gRPC :6344).
**Cấm đụng dải hệ thật: 8000, 8123, 8001, 7860, 8760, 6333, 6334.**

## 4. Luật an toàn song song hệ cũ (giai đoạn test)

1. KHÔNG sửa bất kỳ file nào trong `C:\OutlierY`; không restart tác vụ nền hệ thật.
2. Qdrant test riêng (:6343, storage trong `data\qdrant`) — không chung collection thật.
3. Dữ liệu test = BẢN SAO từ `D:\OUTLIERY-backup` (chỉ đọc backup, không đọc-ghi dữ liệu sống).
4. Chỉ dùng dải cổng 9xxx + 6343/6344.

## 5. LUẬT TỔ CHỨC FILE/FOLDER (6 luật)

**Luật 1 — 4 loại file, mỗi loại một chỗ:**
- CODE → `apps\<app>\src` | TÀI LIỆU dự án → `apps\<app>\docs` (cấp hệ: `docs\` gốc)
- LUẬT ngoài code → `apps\<app>\rules` (riêng app) / `nen\rules` (cả hệ)
- DỮ LIỆU vận hành → `data\<app>\` — tuyệt đối không nằm trong folder code.

**Luật 2 — Mỗi app là một ngôi nhà TỰ ĐỦ** (mở folder app là đủ ngữ cảnh code tiếp):
```
apps\<app>\
├── CLAUDE.md   ← nhật ký + bài học CỦA RIÊNG app
├── README.md   ← app làm gì, chạy thế nào (cho người)
├── docs\  ├── rules\  ├── src\  ├── templates\  ├── tests\  └── migrations\
```

**Luật 3 — CLAUDE.md phân tầng:** gốc = hiến pháp + bản đồ trỏ; mốc/bài học của app
nào ghi vào CLAUDE.md app đó. Hết thời nhật ký 112KB một cục.

**Luật 4 — Phụ thuộc MỘT CHIỀU:** app chỉ import từ `nen\common`; CẤM import chéo
app khác. Muốn dữ liệu của nhau → connector chỉ-đọc qua API. Kỹ thuật: mọi dịch vụ
chạy working-dir = root + PYTHONPATH = root (script start lo) → `from nen.common
import ...` chạy đồng nhất.

> ⚠️ BẪY TÊN PACKAGE (dính 16/08, bắt trước khi nổ): thư mục tầng nền tên `nen`,
> KHÔNG phải `platform` — `platform` trùng module chuẩn Python, đặt trùng là che
> stdlib làm vỡ thư viện khác. Package Python cấm đặt tên trùng stdlib, cấm dấu `-`.

**Luật 5 — Dữ liệu tích lũy đặt theo NĂM/THÁNG + khuôn tên file:**
`data\<app>\kho\<năm>\<tháng>\YYYY-MM-DD_<kenh_id>_<ten>.ext`
UI chỉ hiện gần đây + tìm kiếm; kho đĩa có quy luật là nguồn đầy đủ (tra bằng Explorer).

**Luật 6 — DATABASE là tài sản ưu tiên số 1** (code là công cụ — dựng lại được từ git;
data mất là mất vĩnh viễn):
```
data\<app>\
├── db\    ← DB sống (SQLite/JSON-store) + schema_version — backup BẮT BUỘC qua lệnh
├── kho\   ← file tích lũy năm/tháng — copy trần được
└── xuat\  ← file sinh cho người tải — mất tái sinh được, không cần backup
```
App bắt buộc khai mục `du_lieu` trong hợp đồng app; store không khai = không được
backup → mọi dữ liệu phải có danh phận từ khi sinh ra. Sổ người đọc:
`docs\SO_DIA_BA_DU_LIEU.md`.

## 6. Hợp đồng app (`nen\rules\apps.json`)

Mỗi app tự khai (khuôn manifest Odoo/Nextcloud):
```json
{
  "slug": "data-analytics",
  "ten": "Data Analytics",
  "cong": 9102,
  "tien_to": ["/chan-doan"],
  "health": "/health",
  "phien_ban": "2.0.0",
  "quyen": {"vao": "...", "hanh_dong": {}},
  "du_lieu": [
    {"ten": "bao-cao-goc", "loai": "kho-file", "duong": "data/data-analytics/kho",
     "muc_quy": "vang", "backup": "copy", "giu": "vinh-vien"},
    {"ten": "lich-su", "loai": "sqlite", "duong": "data/data-analytics/db/lichsu.db",
     "muc_quy": "vang", "backup": "sqlite-snapshot", "giu": "vinh-vien"}
  ]
}
```

## 7. IAM — mô hình (Phase 2)

- 3 khối: NGƯỜI (hồ sơ NS) → TÀI KHOẢN → QUYỀN (ma trận vai tổ chức → hành động per app).
- `iam.db` (SQLite WAL) là MỘT nguồn sự thật; app chỉ nhận claims mỗi request
  (`X-Remote-User/Role`), không giữ sổ vai riêng.
- **Vai ADMIN ỦY QUYỀN** — 2 giỏ: Owner tuyệt đối (vault, két, bảng phân quyền, xóa
  cứng) / Ủy quyền được (tài khoản thường ngày, duyệt hồ sơ, nạp tài liệu, duyệt Q&A,
  giám sát). 3 luật sắt: không tự nâng quyền · không đụng Owner · mọi thao tác có vết
  (`nhat_ky_quyen`).
- Chuyển thể TOÀN BỘ luật hiện hành: thang 5 level × bộ phận × vị trí; Manager không
  ngang Owner; nấc quan_tri; vai seo PlannerY... Test hồi quy: ma trận quyền TRÙNG hệ cũ.

## 8. Bất biến kế thừa từ hệ cũ — KHÔNG ĐƯỢC PHÁ

Van chống bịa (tài liệu không nêu → nói thẳng; số liệu nguồn chết → "—") · trích nguồn
từng câu · metadata dropdown cố định · luật ngoài code (CSV user sửa bằng Excel) ·
doc_code bất biến · RBAC lọc server-side, từ chối tài liệu lặng lẽ · Qdrant trước
catalog sau · mỗi hàm có test · việc nặng không chạy trong request (chạy nền) · mọi
lời gọi API ngoài có timeout, retry mặc định 0 · ghi file nguyên tử (tmp + os.replace)
· JS không dùng API secure-context-only thiếu fallback (tới khi HTTPS phủ) ·
text-thuần cho ruột hệ (JSON/CSV/MD/SQLite); Excel/PDF là CỬA XUẤT sinh từ ruột.

## 9. Bảng ánh xạ file cũ → chỗ mới (thi hành khi di trú từng app)

| File hiện tại (C:\OutlierY\apps\AI AGENT) | Về đâu |
|---|---|
| analytic_methodology.md, yeu_cau_code_nang_logic_phan_tich.md | `apps\data-analytics\docs\` |
| supervisor.md, file_arrangement.md, Input_database.md (lỗi thời 1 phần) | `apps\ai-agent\docs\` |
| App_Rule.md, User_Management.md | `nen\iam\docs\` |
| Lo-trinh…, danh_gia_chien_luoc.md, OUTLIERY-tich-hop-tong-quan.docx | `docs\` gốc |
| HUONG_DAN_*.md, OUTLIERY-Runbook*.docx, VPS.txt | `runbook\` |
| AI Agent API.txt (KEY) | KHÔNG copy file — nội dung nhập KÉT (Phase 3) |
| CLAUDE.md 112KB | tách theo Luật 3 |
| V1_implementation.md, V1_update.md | `apps\ai-agent\docs\luu-tru\` |
| Claude Tool, awesome-public-datasets, Report Sampling, design-system | không thuộc platform — giữ chỗ cũ |

## 10. Lộ trình 8 phase (chi tiết từng việc: xem phiên bàn 16/08 + cập nhật tại đây)

- **P0** Khung & luật chơi: cây thư mục, git, hiến pháp, PORTS, venv, Qdrant test,
  **danh mục thực thể (0.6)**, luật tổ chức (0.7), **sổ địa bạ dữ liệu (0.8)**.
- **P1** Gateway: đăng nhập/session, proxy theo hợp đồng app, claims, app-mau,
  /suc-khoe + tự restart, Caddy TLS tự ký.
- **P2** IAM: iam.db + co_quyen() trung tâm + vai Admin ủy quyền + trang quản trị
  hợp nhất + migration users.txt→iam.db + nhật ký quyền.
- **P3** Két: config ≠ secret, vai LLM (writer/critic/…) → model, API loopback,
  UI Owner, timeout/retry một chỗ.
- **P4** Chuẩn dữ liệu: DATA_DIR, log chuẩn JSON-lines, backup manifest phân loại
  (snapshot vs copy), diễn tập restore.
- **P5** Di trú nghiệp vụ: ai-agent (RAG), data-analytics (+dropdown kênh từ danh bạ,
  kho năm/tháng), to-chuc (KPI/chấm công/NAS), vault; ~589 test theo sang; kèm docs +
  rules + CLAUDE.md từng app theo bảng ánh xạ mục 9.
- **P6** Cầu nối: connector `bao_cao_kenh` + nút 📊 + router (danh bạ đã có từ P0).
- **P7** Nghiệm thu tổng: load test 50 phiên, bản sao PlannerY sau gateway, runbook
  3 quyển, kế hoạch thay thế + rollback 5 phút.

## 11. Backlog sau thay thế (KHÔNG làm trong bản này)

LLM gateway đo chi phí per-app · tách nhỏ tiếp ai-agent · connector RadarY/PlannerY/
SEO đầy đủ + briefing tuần · tầng "AI suy luận chung" · bộ nút xuất Excel/PDF cho các
bảng báo cáo (ưu tiên theo chỉ định Owner) · viết lại app phụ (không bao giờ).
