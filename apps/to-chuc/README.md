# App TỔ CHỨC (to-chuc, :9103)

Mạch TỔ CHỨC của OUTLIERY v2, di trú từ `C:\OutlierY\apps\AI AGENT\agent-app`:

| Mảnh | Route | Quyền (gate trong app) |
|---|---|---|
| **KPI** (4 nguồn chỉ-đọc) + bảng chấm công ngày | `GET /kpi?ky=tuan\|thang&ngay_cc=` | Manager+ (level ≥ 4) |
| **Chấm công** (điểm hứng lay_user + nhịp tim + beacon) | `POST /api/nhip`, `POST /api/nhip-thoat` | mọi người có claims |
| **NAS công ty** (chỉ đường + file .bat gắn ổ) | `GET /nas`, `GET /nas/cai-dat/{so}` | mọi người có claims |
| **Vault** tài khoản số (AES-256-GCM + 10 safekey + audit) | `GET /vault`, `POST /vault/tao\|mo\|khoa\|khoi-phuc-master\|muc\|xoa-muc\|xem` | CHỈ Owner (level = 5) |

Gateway đã kiểm quyền "vao" app; app KHÔNG tự giữ user — nhận claims
`X-Remote-User/Level/Role/Dept` (Dept được proxy quote → app unquote).

## Chạy

```
# từ ROOT (D:\AI AGENT OUTLIERY)
python -m uvicorn src.main:app --app-dir "apps/to-chuc" --port 9103
# test (từ thư mục app)
cd apps\to-chuc && ..\..\.venv\Scripts\python.exe -m pytest -q
```

## Dữ liệu (Luật 6) + env

| Env | Mặc định | Nghĩa |
|---|---|---|
| `CHAM_CONG_DIR` | `data/to-chuc/db/cham-cong` | `YYYY-MM.json` {ngày: {user: vao/ra/nguon_ra}}, ghi nguyên tử |
| `VAULT_DIR` | `data/vault` | `vault.enc` (bản mã) + `safekey_login.json` (hash) + `audit.csv` chỉ-ghi-thêm |
| `PLANNERY_PLAN` | `data/to-chuc/nguon/plannery-plan.json` (không tồn tại) | nguồn KPI — CHỈ ĐỌC |
| `CONTENT_HISTORY` | `data/to-chuc/nguon/content-history.jsonl` (không tồn tại) | nguồn KPI — CHỈ ĐỌC |
| `SPEAKY_JOBS_LOG` | `data/to-chuc/nguon/speaky-jobs_log.csv` (không tồn tại) | nguồn KPI — CHỈ ĐỌC |
| `BAO_CAO_DIR` | `data/data-analytics/db/bao-cao-lich-su` | lịch sử báo cáo của app data-analytics — CHỈ ĐỌC |
| `NAS_DUONG_DAN` | (trống → /nas 404) | nhiều share ngăn `;` |
| `NAS_RIENG_MANAGER` / `NAS_WEB` / `NAS_DONG_BO` | (trống/false) | ổ chỉ Manager+ thấy / web UI NAS / cờ "đang chạy trên server" (bật mới tra dung lượng + nhật ký xóa) |
| `VAULT_TU_KHOA` | 600 | giây tự khóa vault |
| `IAM_DB` | `data/nen/iam.db` | sổ IAM — app đọc CHỈ-ĐỌC lấy danh sách người cho bảng KPI |

**VAN CHỐNG BỊA SỐ LIỆU** (bất biến kế thừa): nguồn KPI không đọc được → `None` →
UI hiện `—` kèm lý do, tuyệt đối không 0 giả. IAM không đọc được → nói thẳng trên
trang. Chấm công là "hiện diện trên hệ công cụ", không phải máy chấm vân tay.

## Việc treo (thuộc gateway/IAM, KHÔNG thuộc app này)

- **/khoi-phuc** (đặt lại mật khẩu ĐĂNG NHẬP Owner bằng safekey, đường công khai):
  đổi sổ user nên thuộc IAM/gateway. Hàm `vault.dat_lai_mat_khau_owner` vẫn nằm
  trong `src/vault.py` (import `src.auth` tại chỗ — không route nào gọi ở app này);
  gateway nối lại khi làm trang quên-mật-khẩu.
- **nas_sync** (đồng bộ tài khoản Windows theo mật khẩu OUTLIERY): cần mật khẩu
  thật lúc đăng nhập → thuộc gateway. Trang NAS hiện chạy nhánh "chưa bật đồng bộ"
  (copy đường dẫn + map ổ tay + .bat tự hỏi mật khẩu); template giữ nguyên nhánh
  tài khoản chờ nối.
- **Điểm hứng chấm công TOÀN HỆ**: hệ cũ hứng ở cổng 8000 cho mọi app; v2 app này
  chỉ hứng request của chính nó + nhịp tim/beacon từ base.html. Muốn "mở app nào
  cũng tính có mặt" như cũ → gateway ghi nhận (gọi /api/nhip hoặc ghi thẳng).
- **Tín hiệu `dang_xuat`**: nút Đăng xuất ở gateway — gateway nên bắn tín hiệu
  chấm công khi xóa phiên (hệ cũ ghi "Đăng xuất" là nguồn giờ ra chuẩn nhất).
- **KPI nối PlannerY**: IAM v2 chưa có trường `khau`/`planner_id` của hồ sơ hệ cũ
  → người VH chỉ nối được qua HỌ TÊN trùng tên trong plan.json (UI ghi chú rõ).
