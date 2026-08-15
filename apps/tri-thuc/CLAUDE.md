# CLAUDE.md — app tri-thuc (nhật ký + bài học CỦA RIÊNG app)

> Theo Luật 3: mốc/bài học của app này ghi ở đây; hiến pháp xem `docs/kien_truc_nen.md` gốc.

## App là gì

Mạch TRI THỨC di trú từ agent-app hệ cũ: nhập tài liệu → Qdrant + catalog; hỏi–đáp
RAG stream + vòng phản biện; kho tài liệu CRUD Owner; kho-thiếu + Q&A bổ sung;
nguồn ngoài YouTube (bài học kinh nghiệm có neo); lịch sử phiên; giám sát Owner.
Cổng :9101. Chạy/test: xem README.md.

## Bất biến KHÔNG ĐƯỢC PHÁ (kế thừa hệ cũ, mục 8 hiến pháp)

- Van chống bịa: tài liệu không nêu → nói thẳng; kho rỗng → không gọi model.
- RBAC lọc server-side (`vector_client._duoc_xem` là MỘT nguồn sự thật quyền);
  từ chối tài liệu 404/ẩn LẶNG LẼ (Rule 2 — không lộ tài liệu tồn tại).
- doc_code bất biến; Qdrant TRƯỚC catalog SAU (+ kiểm chứng payload khi đổi quyền).
- Luật ngoài code (`rules/*.csv`); metadata dropdown cố định, backend kiểm lại.
- Việc nặng chạy NỀN (BackgroundTasks + registry + nháp ra đĩa); mọi lời gọi API
  ngoài có timeout (LLM_TIMEOUT), retry mặc định 0; ghi file nguyên tử.
- **hoi_dap.html có KHỐI `<script>` ĐÓNG BĂNG BYTE** — tuyệt đối không sửa một byte
  bên trong các thẻ `<script>` của file này (luật hệ cũ, JS phải chạy HTTP LAN).

## Mốc

- 16/08/2026 — **DI TRÚ P5 LẦN ĐẦU**: copy 11 module + llm/ + 12 template + static
  từ agent-app (CHỈ ĐỌC nguồn); `src/main.py` trích ~40 route mạch tri thức từ
  app.py cũ (bỏ login/NAS/chấm công/quản user/phân quyền/cài đặt/proxy/vault/
  nhân sự/chẩn đoán); mối nối đổi theo mẫu data-analytics:
  1. auth → claims X-Remote-User/Level/Role/Dept (Dept URL-encoded, unquote);
     gate = ngưỡng level thường quy (upload/quản lý/nguồn ngoài ≥4, owner =5) —
     lệ riêng tick từng người thuộc IAM tầng nền, app không giữ sổ.
  2. LLM → `src/cau_hinh_llm.py` nạp từ két qua gateway lúc startup rồi dựng lại
     qa.writer/qa.critics; gateway chết → env/mock.
  3. Data → KHO_TAI_LIEU=data/tri-thuc/kho/kho-tai-lieu, LICH_SU_DIR=
     data/tri-thuc/db/lich-su (setdefault TRƯỚC import module — Luật 6);
     QDRANT_URL mặc định :6343 (kho thật :6333 cấm đụng).
  4. +/health; /giam-sat dựng cây từ `lich_su.danh_sach_nguoi_dung()` (quét
     LICH_SU_DIR) vì app không còn users.txt — bộ phận/level từng người thuộc IAM.
  Lazy import `from src.app import ...` trong 4 module (kho_thieu, nap_youtube,
  qa_bo_sung, tong_hop_neo) đổi thành `from src.main import ...` — thay đổi DUY
  NHẤT trong module copy.
