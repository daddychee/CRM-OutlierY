# CLAUDE.md — app data-analytics (v2, :9102)

> App CHẨN ĐOÁN SỐ LIỆU kênh YouTube — di trú từ agent-app hệ cũ 16/08/2026
> (commit 7c6a515), nghiệp vụ GIỮ NGUYÊN: engine 4 trục + 7 phán quyết + báo cáo
> 9 mục + cache diễn giải + lịch sử dùng chung + chạy nền.
> Phương pháp luận (ĐỌC trước khi sửa engine): [docs/analytic_methodology.md](docs/analytic_methodology.md)

## Chạy & test
- Chạy (từ ROOT): `python -m uvicorn src.main:app --app-dir "apps/data-analytics" --port 9102`
- Test (TỪ THƯ MỤC APP): `cd apps/data-analytics` → `..\..\.venv\Scripts\python.exe -m pytest -q` (64 test)
- Dữ liệu: `data/data-analytics/db/bao-cao-lich-su` (bản ghi) + `kho/bao-cao-goc` (file gốc).

## 4 mối nối khác hệ cũ (còn lại giữ nguyên)
1. Auth = claims gateway (X-Remote-User/Level/Role/Dept — Dept phải unquote); gateway đã gate quyền vào app.
2. Diễn giải LLM = `src/dien_giai.py` (trích từ qa_pipeline, giữ vòng phản biện).
   `ponytail:` diễn giải CHƯA tra playbook kho công ty (rag thuộc app tri-thuc) —
   nâng cấp: gọi API search tri-thuc qua cầu nối, KHÔNG import chéo.
3. Config LLM nạp từ KÉT qua gateway lúc startup (không còn key trong app).
4. `/chan-doan/kenh-goi-y`: DANH BẠ thực thể (nen/rules/danh_muc.csv) đứng trước tên đã dùng.

## Bất biến KHÔNG được phá (kế thừa nguyên hệ cũ)
Luật ngoài code (rules/*.csv — user sửa Excel) · engine chỉ chấm số, LLM chỉ diễn
giải · KHÔNG gọi LLM 80 lần (bấm video nào diễn giải video đó, cache theo
bao_cao_id×chi_muc) · LLM chết không giết bài chẩn đoán · van chống bịa
chua_du_du_lieu · xem lại lịch sử không gọi API.

## Trạng thái
- 16/08/2026: di trú xong, 64 test xanh, E2E thật qua gateway (80 video, tầng vỡ
  retention). Registry tác vụ nền còn trong RAM (`ponytail:` đủ 1 worker, mất khi
  restart — nâng SQLite nếu đa worker).
