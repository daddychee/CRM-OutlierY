# App TRI THỨC (:9101) — hỏi–đáp RAG + kho tài liệu + nguồn ngoài

Bản di trú mạch tri thức từ hệ cũ (`C:\OutlierY\apps\AI AGENT\agent-app`) sang
OUTLIERY Platform v2. Nghiệp vụ giữ nguyên; chỉ đổi 4 mối nối theo
`docs/kien_truc_nen.md` (auth→claims, LLM→két, data→`data/ai-agent/`, +/health).

## App làm gì

- **Nhập tài liệu** (`/`, `POST /upload`): kéo-thả + dropdown bắt buộc → đổi tên
  chuẩn → kho 8 ngăn → nạp Qdrant → sổ `_catalog.csv` chỉ-ghi-thêm.
- **Hỏi–đáp RAG** (`/hoi-dap`, `/hoi`, `/hoi-dap/stream*`): TÌM (lọc quyền
  server-side) → TRẢ LỜI trích nguồn (van chống bịa) → PHẢN BIỆN → CHỐT; stream SSE;
  đa chiều theo tầng nguồn (nút 🧭); góc nhìn ngoài.
- **Kho tài liệu** (`/kho-tai-lieu*`): xem theo RBAC; Owner sửa metadata/nội dung/
  quyền, gỡ mềm, xóa cứng 2 lớp — Qdrant trước, catalog sau.
- **Kho thiếu + Q&A bổ sung** (`/kho-thieu*`): bảng câu kho chưa trả lời được,
  gom nhóm chủ đề, Owner duyệt Q&A bổ sung tri thức.
- **Nguồn ngoài** (`/nguon*`, `/nguon-ngoai`): video YouTube → trích verbatim →
  bài học kinh nghiệm có neo (3 van chống bịa) → duyệt vào kho, chạy nền + lịch sử.
- **Lịch sử hội thoại** (`/lich-su*`): phiên per-user, lọc D2 theo quyền, Owner giám sát.
- **Giám sát** (`/giam-sat`, chỉ Owner): cây phiên hỏi của từng người + lỗ hổng kho.

## Chạy

```powershell
# từ ROOT (D:\AI AGENT OUTLIERY) — PYTHONPATH tự đúng nhờ --app-dir
.venv\Scripts\python.exe -m uvicorn src.main:app --app-dir "apps/ai-agent" --port 9101
```

- Nhận claims từ gateway :9000 (X-Remote-User/Level/Role/Dept — Dept URL-encoded).
  Gọi thẳng :9101 không có claims → 401 (đúng thiết kế; vào qua cổng).
- Dữ liệu: `data/ai-agent/kho/kho-tai-lieu/` (file gốc + catalog + sổ vận hành),
  `data/ai-agent/db/lich-su/` (hội thoại per-user). Qdrant TEST `:6343`.
- Cấu hình LLM writer/critic nạp từ KÉT qua gateway lúc khởi động; gateway chết →
  env/mock, app vẫn sống.

## Test

```powershell
cd "D:\AI AGENT OUTLIERY\apps\ai-agent"
D:\AI AGENT OUTLIERY\.venv\Scripts\python.exe -m pytest -q
```

Toàn bộ chạy MOCK (không Qdrant thật, không gọi model thật, dữ liệu vào tmp).

## Tài liệu

- `docs/supervisor.md` — spec tầng cố vấn đa chiều (tầng nguồn, extract, 3 van).
- `docs/file_arrangement.md` — quy tắc đặt tên/xếp tài liệu.
- `docs/Input_database.md` — spec nhập liệu (phần API/lõi thời RAGFlow đã lỗi thời;
  khung metadata 5 bộ phận vẫn đúng).
