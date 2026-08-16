# Content Ultimate

Bộ công cụ viết **kịch bản YouTube** gộp từ 2 tool: **Outline Board** (tìm "nói gì" bằng
bằng chứng đo được từ video cùng sóng) và **Author Extract** (tái tạo giọng văn tác giả
để viết "bằng giọng ai"). Một giao diện web, chạy local (sẽ deploy VPS cho team).

## Chạy

Double-click **`Start.command`** (lần đầu tự cài, hơi lâu vì fastembed) — trình duyệt mở
trang chủ 2 khối:

1. **Outline Board** (`/outline`) — dán URL các video cùng chủ đề/sóng trend → pipeline
   S1→S4b đo bằng chứng (heatmap Most Replayed, beat, cluster, tín hiệu comment) →
   bảng cluster tick/kéo thả → tự xuất `runs/<run>/outline.txt` + `outline_evidence.md`.
2. **Author Extract** (`/author`) — tab **① Extractor**: folder bản thảo tác giả →
   `profile.json` (hồ sơ giọng) + clonekit + dataset, tự vào thư viện. Tab **② Writer**:
   nạp outline từ board (dropdown "Outline từ board") hoặc dán tay → chọn tác giả + độ
   dài + LLM → `script.md` sinh theo chương, xong tự đo % giống giọng (tham khảo).

Chạy tay: `.venv/bin/content-ultimate [--port 8770] [--run <tên>] [--no-browser]`.

## Cài đặt thủ công

```bash
python3.13 -m venv .venv
.venv/bin/pip install -e ".[dev,llm,embed]"
```

- **`.env`** — kho API key (điền nhiều provider cùng lúc: `ANTHROPIC_API_KEY`,
  `GLM_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`; riêng Outline: `TRANSCRIPT_API_KEY`).
  Chọn LLM nào là ở dropdown trên giao diện.
- **`videos.txt`** — key YouTube Data API (trộn key + URL, xem `videos.txt.example`).
- Cần `yt-dlp` trên hệ thống (`brew install yt-dlp`) cho khối Outline.

## Chọn LLM

Dropdown ở Extractor/Writer có đúng 4 lựa chọn (hiện theo key đã nhập): **Claude
Sonnet · Claude Opus · GLM 5.0 · GLM 5.2**. Muốn thêm lựa chọn Claude thì nhập
`ANTHROPIC_API_KEY` ở tab Cài đặt (hoặc `.env` khi chạy máy cá nhân).

## Deploy VPS cho team

Xem [`deploy/SETUP-VPS.md`](./deploy/SETUP-VPS.md) — Ubuntu + systemd + nginx (HTTPS,
đăng nhập basic auth do quản trị viên cấp tài khoản). Trên web, quản trị viên nhập API
key trong tab **⚙ Cài đặt** (chỉ quản trị viên nhìn thấy — đặt `ADMIN_USERS` trong
`.env` trên server); thành viên team upload bản thảo qua nút **Upload…** thay cho
Browse. Job nặng chạy 1-cái-một — người bấm sau sẽ thấy thông báo "đang chạy".

## Lệnh nâng cao

```bash
python3 run_all.py videos.txt --run <tên>   # pipeline outline không GUI
.venv/bin/voiceprofile --help               # CLI 6 lệnh: build/rhetoric/dataset/clonekit/write/validate
.venv/bin/pytest -q                         # toàn bộ test (voiceprofile + oe)
```

## Tài liệu

- [`CLAUDE.md`](./CLAUDE.md) — nguyên tắc làm việc trong repo (đọc trước khi sửa code).
- [`BUILD-BRIEF-cho-Claude-Code.md`](./BUILD-BRIEF-cho-Claude-Code.md) — kiến trúc 8 module Author Extract.
- [`METHODOLOGY.md`](./METHODOLOGY.md) — phương pháp S1→S5 của Outline Board.
- [`DEVLOG.md`](./DEVLOG.md) — nhật ký quyết định thiết kế.

Repo gộp từ `../Author Extract/` + `../Outline Extract/` (2 folder gốc giữ làm bản lưu).
Output gắn nhãn "lấy cảm hứng từ giọng văn [tác giả]" — không gán cho tác giả thật.
