SEO OPTIMIZE OUTLIERY — Chạy trên Windows
==========================================

Yêu cầu: Python 3.10+ (tải tại https://www.python.org/downloads/ — khi cài NHỚ tick
"Add python.exe to PATH"). Không cần thư viện ngoài (chỉ dùng stdlib).

Bước 1 — Cấu hình key
  - Copy file  .env.example  thành  .env  (cùng thư mục này).
  - Mở .env bằng Notepad, điền:
        LLM_PROVIDER=glm
        GLM_API_KEY=<key z.ai của bạn>
        GLM_MODEL=glm-5.2
        GLM_BASE_URL=https://api.z.ai/api/paas/v4
        YOUTUBE_API_KEYS=<key1>,<key2>
    (Hoặc để mỗi YouTube key 1 dòng trong file  api.txt)

Bước 2 — Chạy
  - Double-click  Start.bat
  - Trình duyệt tự mở  http://127.0.0.1:8760/
  - Ctrl+C trong cửa sổ đen để dừng.

Ghi chú
  - Nếu Start.bat báo 'python' không nhận diện: cài lại Python và tick "Add to PATH",
    hoặc chạy trong CMD:  py -m seo.server
  - .env và api.txt KHÔNG được chia sẻ (chứa key thật).
  - Kết quả (Title/Tag/Description) luôn theo ngôn ngữ nội dung (thường tiếng Anh); giao diện tiếng Việt.
