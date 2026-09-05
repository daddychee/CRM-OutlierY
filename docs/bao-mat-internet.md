# Sổ chủ đề — ĐƯA OUTLIERY RA INTERNET

> Mở sổ 05/09/2026. Mạch việc dài nhiều phiên: rà soát bảo mật → siết → HTTPS →
> mở cho nhân sự dùng từ xa. Nguồn sự thật vẫn là CODE; sổ này ghi phát hiện,
> quyết định và tiến độ. CLAUDE.md chỉ giữ mốc trỏ về đây.

## 0. Bối cảnh & mục tiêu

Owner muốn (a) nhân sự dùng CRM từ xa qua Internet với tên miền riêng, và
(b) về lâu dài BÁN sản phẩm này cho công ty khác.

**Đã chốt trong phiên 05/09:** tách làm HAI ĐÍCH, không gộp.
- **Đích A** — đưa hệ hiện tại ra Internet cho chính công ty. Khả thi, việc tính
  bằng TUẦN.
- **Đích B** — thành sản phẩm bán được (đa khách hàng). Việc tính bằng THÁNG,
  phải chọn kiến trúc trước: mỗi khách một bản cài, hay một bản tách tenant.
  CHƯA quyết — đừng viết code cho Đích B trước khi chốt.

Trong lúc làm Đích A: dùng VPN để có ngay nhu cầu từ xa mà không phơi hệ chưa siết.

## 1. Quy mô hệ (đo 05/09, để ước lượng công)

| Khối | File .py | Dòng |
|---|---|---|
| nen (gateway/iam/common/két) | 32 | 6.999 |
| ai-agent | 59 | 10.754 |
| to-chuc (vault/KPI/chấm công/NAS) | 29 | 7.621 |
| radary | 59 | 17.914 |
| seo-optimize | 109 | 37.973 |
| niche-research | 32 | 7.430 |
| content-ultimate | 142 | 25.720 |
| data-analytics | 27 | 7.088 |
| video-review | 30 | 5.218 |
| plannery | 13 | 3.335 |
| **Tổng** | **532** | **~130.000** |

## 2. Hạ tầng hiện trạng (đo thật 05/09)

- **Cổng**: chỉ `0.0.0.0:9000` mở ra mạng. 7 app phụ + Qdrant (6343) đều
  `127.0.0.1` — kiến trúc một cửa ĐÚNG như thiết kế, đây là nền tốt.
- **Caddy ĐÃ CÓ** tại `tools/caddy/` (caddy.exe + Caddyfile), đang chạy TLS tự ký
  `https://localhost:9443` + miền test `outliery.test`. Khi ra Internet: đổi sang
  tên miền thật + Let's Encrypt, KHÔNG phải dựng lại từ đầu.
- **Chưa có TPM, chưa có camera** trên máy chủ → Windows Hello / WebAuthn nền tảng
  KHÔNG dùng được. Muốn yếu tố thứ 2 phần cứng thì phải mua khóa USB.
- **Sao lưu** `D:\OUTLIERY-backup` — CÙNG MÁY, chưa có bản ngoài.
- **SESSION_SECRET** đã đặt giá trị thật (64 hex).
- Firewall: profile mạng Private; rule mở 9000 (Domain+Private), 8000 (Private).

## 3. Phát hiện — TẦNG NỀN (đã rà + tự kiểm chứng 05/09)

Xếp theo mức nguy hiểm KHI RA INTERNET.

### N1. NGHIÊM TRỌNG — Không có CSRF token ở bất kỳ route ghi nào
Toàn `nen/` không có dòng CSRF nào; phòng thủ duy nhất là `samesite="lax"`
(`nen/gateway/main.py:162`). Route ghi nhạy cảm đều là POST form thuần:
tạo/sửa/xóa tài khoản (`main.py:734`, `:756`), đặt cấp truy cập (`:1315`),
bật admin ủy quyền (`:1333`), thêm/thu hồi API key (`:1496`, `:1520`),
đổi mật khẩu (`:223`, `:252`).
**Làm nặng thêm:** `/nen{duong:path}` (`main.py:2437`) trả **307 giữ nguyên
method+body** cho POST → bàn đạp chuyển tiếp. ĐÃ KIỂM CHỨNG bằng mắt.

### N2. NGHIÊM TRỌNG — Không giới hạn đăng nhập sai
`main.py:140-163` + `iam.py:115-122`. Không đếm lần sai, không khóa tạm, không
delay, không CAPTCHA. Cộng với N8 (mật khẩu tối thiểu 6 ký tự) = tài khoản bị dò.
**Kèm rủi ro DoS**: `/login` chạy sync trong threadpool (có chủ đích, vì bcrypt
CPU-bound) → bắn vài trăm request/giây làm cạn threadpool, cả cổng đứng.

### N3. NGHIÊM TRỌNG — Cookie phiên: thiếu `secure`, TTL 30 ngày, không thu hồi được
`main.py:161-162` + `PHIEN_TTL` (`main.py:37`). Có httponly ✓ samesite=lax ✓,
THIẾU `secure=True`. Không có bảng phiên → **đổi mật khẩu KHÔNG giết phiên cũ**
(`user_hien_tai` `main.py:71-90` chỉ kiểm tài khoản còn tồn tại + cờ khóa).
Cookie bị cắp dùng được 30 ngày; cách duy nhất cắt là khóa hẳn tài khoản.

### N4. CAO — Thiếu SESSION_SECRET thì tự sinh, chết lặng lẽ
`main.py:35` `os.environ.get(...) or secrets.token_hex(32)`. Máy hiện tại CÓ đặt
nên an toàn, nhưng ra Internet thường thêm worker → mỗi worker một khóa khác →
cookie worker A ký, worker B từ chối, đăng nhập chập chờn không giải thích được.
Phải fail-fast: thiếu secret thì KHÔNG khởi động.

### N5. CAO — 11 chỗ kiểm loopback là FAIL-OPEN
Khuôn `if request.client and request.client.host not in (...)` — khi
`request.client is None` thì vế trái sai → **cho qua**. ĐÃ KIỂM CHỨNG bằng Python.
Đếm được **11 chỗ** trong `nen/gateway/main.py`.
Nguy hiểm nhất: `/api/cau-hinh/api-khoa/{app_slug}` (`main.py:2183`) trả
**API key PLAINTEXT** của cả công ty, và KHÔNG có xác thực nào khác ngoài kiểm IP.
Sửa: `if not request.client or request.client.host not in (...)` — 1 dòng/chỗ.

### N6. CAO — Host header do client kiểm soát, không allowlist
`proxy.py:128` gán `X-Forwarded-Host` = header `host` của client. App phía sau
(SEO Optimize so Origin vs X-Forwarded-Host) tin giá trị này → host header
poisoning. Cần allowlist Host ở Caddy/gateway.
**Tin tốt đã kiểm:** `_HEADER_CAM` (`proxy.py:51-56`) chặn ĐỦ cả 7 header
`X-Remote-*` mà app thật sự đọc → không giả mạo danh tính được từ trình duyệt.

### N7. TRUNG BÌNH — Route công khai rò thông tin nhẹ
`/health` (`main.py:122`) lộ phiên bản; `/login` (`main.py:133`) lộ `che_do_mo`
= hệ đã có tài khoản hay chưa. Các redirect `/suc-khoe`, `/quan-tri`, `/cai-dat`…
lộ cấu trúc URL nội bộ. Không route dữ liệu nào hở.

### N8. TRUNG BÌNH — Mật khẩu tối thiểu 6 ký tự
`iam.py:180` + `iam.py:214`. Nghịch lý: `nas_sync.py:103-113` ĐÃ CÓ chuẩn mạnh
hơn (≥8, HOA+thường+số, không chứa tên) nhưng chỉ dùng báo trạng thái NAS, không
chặn IAM. → Nâng IAM lên dùng chính hàm đã có.

### N9. THẤP — Email tài khoản dịch vụ hardcode
`tools/scripts/start-all.ps1:132-133` (ENVATO_EMAIL/VECTEEZY_EMAIL), file được
track git. Không phải mật khẩu, nhưng hỗ trợ phishing.

### ĐÃ KIỂM VÀ ĐẠT (không cần rà lại) — tầng nền
- **SQL injection: KHÔNG CÓ.** Mọi giá trị tham số hóa; 5 chỗ f-string trong SQL
  đều là định danh từ whitelist nội bộ (`danh_ba.py:217,309`, `iam.py:257,425`,
  `sqlite_migrate.py:27`).
- **Path traversal: KHÔNG CÓ.** `main.py:1088` `Path(ten).name != ten` + chặn `.`
  đầu — agent đã chạy thử 5 payload trên Windows.
- **SSRF: KHÔNG CÓ.** Mọi lời gọi ra đều tới host hardcode loopback.
- **Subprocess: AN TOÀN.** `nas_sync.py:161` script PowerShell hằng số, mật khẩu
  qua BIẾN MÔI TRƯỜNG không qua argv, tên qua regex + blacklist, timeout 120s,
  không `shell=True`.
- **Nâng quyền IAM: PHÒNG THỦ TỐT.** `co_quyen` fail-closed; claims dựng
  server-side từ DB mỗi request; 3 luật sắt chống tự sửa/đụng Owner.
- **Bí mật: ĐÚNG CHUẨN.** API key mã hóa Fernet, DB không có plaintext, log không
  ghi key. Trần đã biết (`ket.py:9-11`): khóa Fernet nằm cùng máy.

## 4. Phát hiện — APP ai-agent + to-chuc (đã rà + tự kiểm chứng 05/09)

**Giả định gốc của cả 2 app:** "app bind 127.0.0.1 nên chỉ gateway tới được, header
giả đã bị vứt" (`to-chuc/main.py:127-131`, `ai-agent/main.py:123-128`). Toàn bộ mô
hình bảo mật đứng trên MỘT giả định này. Ra Internet nó thành điểm gãy chí mạng.

### A1. NGHIÊM TRỌNG — App không tự kiểm loopback, danh tính hoàn toàn là header
`to-chuc/main.py:125-144`, `ai-agent/main.py:123-138`: `lay_user()` đọc thẳng
`X-Remote-User/Level/Role/Dept`, KHÔNG kiểm IP nguồn.
Đối chiếu: route `/api/kiem` LẠI CÓ kiểm loopback (`to-chuc/main.py:213`,
`ai-agent/main.py:383`) → cơ chế tồn tại nhưng không áp cho route nghiệp vụ.
Khai thác: cổng 9103 lộ ra (đổi bind, port-forward nhầm, hoặc SSRF từ app khác) →
`curl -H "X-Remote-User: bot" -H "X-Remote-Level: 5" http://target:9103/vault`
= thành Owner tức khắc. Đọc vault, lương, hồ sơ nhân sự, tài chính. Không cần mật khẩu.
**Sửa: mỗi app kiểm `request.client.host` loopback, HOẶC shared-secret gateway↔app.**

### A2. NGHIÊM TRỌNG — RBAC tài liệu FAIL-OPEN khi bộ phận rỗng
`ai-agent/src/vector_client.py:538`:
`ap_quyen = bool(user and user.get("bo_phan")) and user.get("level",0) < 5`
Cùng lỗi: `ai-agent/main.py:1183`, `:1760`, `:1785`.
Bộ phận rỗng → KHÔNG lọc quyền gì cả (di sản "chế độ mở" thời chưa có auth).
Cột cho phép rỗng (`nen/iam/migrations/001_khoi_tao.sql:16` DEFAULT ''), và
`iam.tao_tai_khoan` (`iam.py:171-198`) KHÔNG kiểm bộ phận rỗng. Gateway chỉ gửi
header khi giá trị truthy (`proxy.py:136`).
→ Một Intern level 1 bộ phận rỗng đọc được TOÀN BỘ kho mọi bộ phận, gồm tài liệu
Mật, qua hỏi–đáp + `/kho-tai-lieu` + `/tai-ban-goc`.
**ĐÃ KIỂM DỮ LIỆU THẬT 05/09: 20 tài khoản, 0 tài khoản bộ phận rỗng → CHƯA bị
khai thác. Nhưng là mìn: Owner tạo 1 tài khoản bỏ trống ô bộ phận là nổ.**
Lỗ này ĐỘC LẬP với A1 — khai thác được cả khi gateway chạy đúng.
**Sửa: fail-closed (không bộ phận = không thấy gì) + cấm tạo tài khoản bộ phận rỗng.**

### A3. NGHIÊM TRỌNG — Vault: trạng thái mở là TOÀN CỤC, không gắn với người mở
`to-chuc/src/vault.py:152-165` — `_DEK`/`_HET_HAN` là biến module-level.
`_dek_dang_mo()` chỉ hỏi "vault có đang mở không", KHÔNG hỏi AI mở.
ĐÃ KIỂM: không có biến `_AI_MO` nào trong file.
Hệ cho phép nhiều Owner (`iam.py:191`). → Owner A mở vault, trong 600 giây Owner B
(hoặc ai chiếm được phiên của bất kỳ Owner nào) lặp `POST /vault/xem` đọc sạch mọi
mật khẩu MÀ KHÔNG CẦN biết mật khẩu chủ. Audit ghi tên kẻ đó — nhưng là ghi nhận
SAU KHI MẤT.
**→ Cửa thứ hai (mật khẩu chủ) trên thực tế bị vô hiệu cho mọi Owner không phải
người mở. Sửa: gắn DEK theo danh tính người mở.**

### A4. CAO — Vault: không giới hạn số lần thử mật khẩu chủ / safekey
`vault.py:180-191` (`mo_bang_master`) chỉ ghi audit rồi `return False`.
`vault.py:277-285` (`_kiem_safekey`) duyệt toàn sổ, chạy scrypt CHO TỪNG bản ghi →
10 lần scrypt/request = đòn bẩy DoS ~1.5 giây CPU mỗi request.
scrypt maxmem 128MB × nhiều request song song = DoS cạn RAM (`vault.py:70`).

### A5. CAO — `/upload` không giới hạn dung lượng, đọc trọn vào RAM
`ai-agent/main.py:1879` `tmp_path.write_bytes(await file.read())`. Không trần dung
lượng, không kiểm đuôi/MIME. Manager+ upload file 8GB → app 9101 chết vì hết RAM,
kéo sập hỏi–đáp toàn công ty.
**Chuẩn ĐÃ CÓ SẴN trong repo:** `to-chuc/src/tai_chinh.py:309-323` (`kiem_tep`) —
trần 10MB/tệp, tối đa 5 tệp, whitelist đuôi. Bê sang là xong.

### A6. CAO — SSRF ở đường nạp nguồn ngoài
`ai-agent/main.py:646-667`, `:798-820` → `src/nap_youtube.py`. URL người dùng nhập
không whitelist tên miền, không chặn IP nội bộ.
Kết hợp A1 → SSRF thành đường vào thẳng: gọi `127.0.0.1:9103` kèm header giả.
**Van ĐÃ CÓ SẴN:** `ai-agent/src/llm/base.py:11-20` → `nen/common/phong_thu.kiem_host`
(bắt buộc https + allowlist) đang áp cho đường gọi LLM. Áp nốt cho nạp nguồn ngoài.

### A7. CAO — Phiếu lương: có cờ finance là đọc lương mọi người
`to-chuc/main.py:790-800` `/finance/luong/phieu/{ky}/{ten}` và `:802-822`
`phieu.zip` — chỉ gate `yeu_cau_finance`, KHÔNG kiểm `ten` có phải chính người đó.
Kế toán cấp thấp mở được lương Owner; `phieu.zip` tải TOÀN BỘ bảng lương một lần.
**CẦN OWNER XÁC NHẬN đây có đúng ý đồ nghiệp vụ không** (kế toán vốn cần xem lương).

### A8. CAO — Prompt injection từ transcript nguồn ngoài
`ai-agent/src/qa_pipeline.py`, `tong_hop_neo.py`, `trich_doan.py`. Transcript do
người lạ trên Internet viết được ghép thẳng vào prompt. Van chống bịa là ràng buộc
NỘI DUNG, không phải ranh giới CHỈ THỊ. Delimiter (`<<<LYDO>>>`…) có thể bị giả mạo
ngay trong nguồn — CLAUDE.md đã ghi parser phải "khoan dung số dấu <>" → càng dễ giả.
Giảm nhẹ nhờ Owner duyệt, nhưng duyệt bằng mắt không bắt được chỉ thị giấu trong
transcript dài. Sửa: delimiter ngẫu nhiên mỗi request + tách rõ DỮ LIỆU/MỆNH LỆNH.

### A9. TRUNG BÌNH — `doc_code` không sanitize, an toàn gián tiếp
`ai-agent/main.py:1179-1211`, `:1774-1796`, `:1750-1772`. Không khai thác được HÔM
NAY vì `doc_code` phải khớp một dòng `_catalog.csv` trước khi dùng. Rủi ro là HỒI QUY:
thêm route mới dùng `doc_code` mà quên bước tra catalog là thành traversal ngay.
Sửa rẻ: thêm regex khuôn `^[A-Z]+-\d{4}-[0-9A-F]{6}(-QA|-PT)?$` làm lưới thứ hai.

### A10. TRUNG BÌNH — Thông báo lỗi rò đường dẫn nội bộ
`ai-agent/main.py:1912`, `:636`, `:960`, `:1000`, `:1037`, `:1063`;
`to-chuc/main.py:466,479,563,584,606,628,743,756` — `f"...: {e}"` có thể chứa đường
dẫn tuyệt đối `D:\AI AGENT OUTLIERY\...`, tên collection, chi tiết stack.
Cần kiểm thêm: `llm/openai_compatible.py:62` ghi `str(e)` vào sổ — nếu nhà cung cấp
echo lại request thì có nguy cơ KEY lọt vào log.

### ĐÃ KIỂM VÀ ĐẠT — 2 app này
- **Vault mã hóa: ĐÚNG CHUẨN.** Template không render mật khẩu (`vault.html:146-151`,
  nút Edit cố ý loại `mat_khau` khỏi tojson); audit chỉ ghi TÊN mục; đường lộ bản rõ
  DUY NHẤT là `POST /vault/xem` và nó CÓ audit. Đây là thiết kế đúng.
- **Không có route nào chỉ ẩn nút mà quên kiểm server** (đã đối chiếu `/kho-tai-lieu`,
  `/vault/xem`, `/nas/cai-dat`).
- **Gate cờ header fail-closed** (`ai-agent/main.py:140-194`, `to-chuc/main.py:146-162`).
- **Path traversal: không khai thác được.** Chuẩn tốt nhất repo:
  `tai_chinh.py:336-344` `resolve().relative_to()`.
- **Command injection: KHÔNG CÓ.** (chi tiết ở mục 3 tầng nền)
- **RBAC Qdrant (khi có bộ phận): TỐT.** `_duoc_xem` (`vector_client.py:441-463`) và
  filter server-side (`:549-570`) khớp từng chữ có chủ đích; `Range(lte)` cố tình
  không khớp point thiếu `min_level` → tài liệu chưa gán quyền TỰ ẨN (fail-safe).
  Từ chối lặng lẽ 404 không lộ sự tồn tại.

**Nhận định quan trọng:** phần lớn biện pháp phòng thủ ĐÃ CÓ SẴN trong repo nhưng
chưa áp đều — `resolve().relative_to()` ở tài chính, `kiem_tep` giới hạn upload,
`kiem_host` chặn egress, kiểm loopback ở `/api/kiem`. Việc cần làm chủ yếu là MỞ
RỘNG CHUẨN ĐÃ CÓ ra chỗ còn thiếu, không phải phát minh mới. → giảm rủi ro và giảm công.

## 4b. PATH TRAVERSAL — 2 LỖ KHAI THÁC ĐƯỢC THẬT (tái hiện 05/09)

Khác A9 (an toàn gián tiếp), hai lỗ dưới đây TÔI ĐÃ TỰ TÁI HIỆN bằng code thật.

### T1. NGHIÊM TRỌNG — Ghi file ra ngoài kho qua `video_id` lấy từ URL
`nap_youtube.py:20-30` `video_id_tu_url` trả THẲNG phần cuối URL, không lọc.
→ `main.py:690` (`/nguon/youtube/duyet`) → `nap_youtube.py:158-171`:
`doc_code = f"YT-{video_id}"` → `file_path = kho/ngan/f"{doc_code}_YouTube.md"`
→ `os.replace(tam, file_path)`.
Đường thứ 2: `main.py:944` (`/nguon/tron-goi/duyet`) → `tong_hop_neo.py:478`, `:442`.
**`/nguon/tron-goi/duyet` KHÔNG kiểm url có phải YouTube** (kiểm đó chỉ có ở
`/de-xuat`, `main.py:810`) → URL tùy ý đi thẳng vào tên file.

TÁI HIỆN 05/09 (chạy thật):
  video_id_tu_url("https://youtube.com/watch?v=../../../../evil")
    -> '../../../../evil'
  duong ghi -> kho/03_KinhDoanh/YT-../../../../evil_YouTube.md   ← THOÁT KHỎI KHO

Nội dung file do người gửi kiểm soát (`cac_doan` → `_noi_dung_tai_lieu`).
Dùng đường dẫn CỐ ĐỊNH + `os.replace`, KHÔNG qua `duong_dan_khong_trung`
→ **ghi đè im lặng** bất kỳ file .md/.txt nào tên khớp.
Ghi trúng `src/static` (được mount), `rules/*.csv` (luật ngoài code) hay `.env`
= NGHIÊM TRỌNG. Cần quyền `nguon_ngoai` (Manager+).
**Sửa:** `re.fullmatch(r"[0-9A-Za-z_-]{5,20}", vid)` ngay trong `video_id_tu_url`,
+ kiểm url YouTube ở `/nguon/tron-goi/duyet` cho khớp `/de-xuat`.

### T2. CAO — Đọc file JSON bất kỳ trên đĩa qua `ky` (bảng lương)
`luong.py:144-145` `_duong` = `Path(getenv("LUONG_DIR")) / ten_tep` — KHÔNG resolve,
KHÔNG kiểm biên. `luong.py:268-270` `doc_bang_luong(ky)` ghép `f"bang-luong/{ky}.json"`.
Route KHÔNG áp `_thang_hop_le`: `main.py:790-800` `/finance/luong/phieu/{ky}/{ten}`,
`:802-807` `/finance/luong/phieu.zip?ky=`. (Hàm `_thang_hop_le` CÓ TỒN TẠI ở
`main.py:374-378` nhưng không được gọi ở các đường này.)

TÁI HIỆN 05/09: `%2f` bị Starlette chặn, nhưng **`%5c` (dấu \) KHÔNG bị chặn**:
  ky = unquote("..%5c..%5c..%5csecret") -> '..\..\..\secret'
  duong -> secret.json                                   ← THOÁT THƯ MỤC LƯƠNG

Nội dung file render ra trang phiếu / gói zip. Giới hạn: phải là JSON.
Ghi: `main.py:769` (`ky: str = Form(...)`) → `luong.py:297` — khó hơn (bị chắn bởi
`cham_cong.doc_chot(ky)` phải trả dict) nhưng vẫn dựng được cặp đường để ghi đè .json.
**BÀI HỌC WINDOWS: chặn `..` mà chỉ nghĩ tới `/` là chưa đủ — `%5c` lọt.**
**Sửa:** validate NGAY TRONG `luong.doc_bang_luong` + `cham_cong._duong` để hàm lõi
tự bảo vệ (bịt luôn T3), đừng chỉ vá ở route.

### T3. THẤP — `cham_cong._duong(thang)` không tự bảo vệ
`cham_cong.py:37-38`, `:141-150`. Mọi caller HTTP hiện ĐỀU đã lọc (`main.py:394`
`_thang_hop_le`; `chot_ky` tự regex `cham_cong.py:161-162`). Nợ kỹ thuật: hàm lõi
dựa vào kỷ luật caller. Lối vào duy nhất còn hở là gián tiếp qua T2.

### KHUÔN ĐÚNG ĐÃ CÓ SẴN TRONG REPO — nhân bản ra chỗ thiếu
`to-chuc/src/tai_chinh.py:336-344` `duong_chung_tu`:
`p.resolve().relative_to(goc.resolve())` trong try/except → thoát biên trả None.
Đây là chuẩn tốt nhất trong cả 2 app. Cùng file: `_ten_tep_sach` (`:301-306`) xử lý
cả `\` lẫn `/`, lọc ký tự cấm Windows + ADS + NUL; `thu_muc_chung_tu` (`:292-298`)
regex hóa id. **Việc cần làm: tách thành helper dùng chung, áp cho mọi chỗ dựng
đường dẫn từ dữ liệu ngoài.**

### Upload — bổ sung
- **B1 (TRUNG BÌNH)**: `/upload` không trần dung lượng, `await file.read()` nạp trọn
  vào RAM (`ai-agent/main.py:1874`; cùng bệnh `:1313`). Gateway + proxy cũng buffer body.
- **B2 (THẤP)**: `/upload` nhận MỌI đuôi (`main.py:1838-1888`). Tái hiện: `shell.aspx`
  → lưu thành `..._v1.aspx`. **Giảm nhẹ thật:** kho KHÔNG mount tĩnh, tải về là
  `Content-Disposition: attachment`, `/kho-tai-lieu/xem` render bằng `textContent`
  (`kho_tai_lieu.html:400`) → không XSS. NHƯNG kết hợp T1 (ghi được vào `src/static`)
  thì thành nghiêm trọng.
  Whitelist ĐÃ CÓ: `_KHO_DUOI_CHO_PHEP` (`main.py:1284`) — hiện chỉ áp cho
  `/cap-nhat-noi-dung`, chưa áp cho `/upload`.

## 4c. Phát hiện — 7 APP PHỤ (rà + tự kiểm chứng 05/09)

### PHÁT HIỆN CÓ HỆ THỐNG: hệ chia làm HAI NỬA
Đo bằng script 05/09 (grep TRUST_PROXY ở cửa danh tính từng app):

| App | Tự kiểm loopback? |
|---|---|
| radary, niche-research, seo-optimize, content-ultimate, plannery | **CÓ** (app cũ ghép SSO) |
| ai-agent, to-chuc, data-analytics, video-review | **KHÔNG** (app viết mới trong V3) |

→ App CŨ được ghép SSO thì làm ĐÚNG (kiểm cả `*_TRUST_PROXY` lẫn loopback).
App V3 VIẾT MỚI thì tin header vô điều kiện. Đây là chia đôi CÓ HỆ THỐNG, không
phải lỗi lẻ — nghĩa là sửa được bằng MỘT khuôn chung áp cho 4 app, không phải
đi vá từng ca.

### G1. NGHIÊM TRỌNG — video-review: fail-open tuyệt đối
`apps/video-review/src/main.py:76-90` `lay_user()` chỉ cần header CÓ MẶT (`:82`);
quyền lấy thẳng từ `X-Remote-Actions` (`:96-101`).
Nghịch lý: CHÍNH FILE NÀY có khuôn loopback ở `:161-162` cho `/api/kiem`.
Khai thác: `curl -H "X-Remote-Level: 5" -H "X-Remote-Actions: duyet,xoa"` →
**xóa vĩnh viễn file gốc trên NAS công ty** (NAS không có Recycle Bin).
Kèm: `:363-368` `/media/{ma}` dùng `duong.read_bytes()` — đọc trọn file 2-10GB
vào RAM, vài request song song là OOM chết tiến trình.
LƯU Ý PHẠM VI: đường upload từng khúc ĐÃ BỊ GỠ khỏi code
(`apps/video-review/CLAUDE.md:98-100`) — không còn route upload nào.

### G2. NGHIÊM TRỌNG — content-ultimate: ghi file ra ĐƯỜNG DẪN TÙY Ý
`voiceprofile/server.py:896-911` `POST /api/write` nhận `b["script_path"]` NGUYÊN VĂN
→ `:327-330` `Path(script_path).parent.mkdir(parents=True)` + `write_text()`.
KHÔNG resolve, KHÔNG kiểm thư mục cha. ĐÃ ĐỌC XÁC NHẬN 05/09.
Tương tự `POST /api/build` (`:838-866` → `:192`) với `b["out"]`.
→ Ghi đè mã nguồn app khác trong V3, thả file vào thư mục khởi động = **RCE gián tiếp**.
Cộng: TOÀN BỘ `voiceprofile/server.py` KHÔNG CÓ MỘT GATE QUYỀN NÀO (`:764-797` do_GET,
`:799-920` do_POST — 15 route gồm `/api/build`, `/api/write`, `/api/open`).
`/api/open` (`:914-918`) chạy `subprocess.Popen(["open", p])` với p từ client.
Và `_is_admin` fail-open: `contentultimate/server.py:152-153` `if not admins: return True`.

### G3. NGHIÊM TRỌNG — niche-research: path traversal đọc file tùy ý
`server.py:1061` `log_path = PROJECTS / name / DATA_DIR / "stdout.log"` — `name` THÔ
từ URL. Là route DUY NHẤT không qua `_proj()` (`:1123-1127` vốn có lọc regex).
Route KHÔNG có gate nào (`:1058-1059`).
Cộng **C2 (CAO)**: khóa YouTube bị ghi vào `competitors.txt` (`:331-336`
`_bom_khoa_youtube`) mà route tải phục vụ CẢ gốc dự án (`:1111` `for base in [d/"Report", d]`)
→ `GET /api/download/{project}/competitors.txt` = **toàn bộ khóa YouTube công ty**.
Tên project lấy miễn phí từ `/api/projects` (`:381`, cũng không gate).
Cộng **C3 (CAO)**: 13 route không gate, gồm `POST /api/upload` (`:746`) và
`/api/dashboard` (`:853`). Nút Upload chỉ ẩn ở UI (`web/app.js:301`).

### G4. NGHIÊM TRỌNG — plannery: `/api/state` không gate, rò toàn bộ nhân sự
`apps/plannery/server.py:671-677` — trả thẳng `plan.json`, KHÔNG gọi `identity()`.
ĐÃ ĐỌC XÁC NHẬN: `/api/me` (`:678`) và `POST /api/plan` (`:879`) đều CÓ gọi, riêng
route này sót. Dữ liệu: họ tên thật, `standard_rate`, `last_week_rate`, `leaves`.
Cộng **F3 (TRUNG BÌNH)**: vai `seo` xóa được video + đổi khối lượng kênh cũ
(`:278` loại `videos`/`video_minutes` khỏi phép so) — rộng hơn lệ Owner đã chốt
("chỉ thêm kênh/video mới, không đụng cấu hình kênh cũ").

### G5. NGHIÊM TRỌNG — data-analytics: không kiểm loopback (HAI bản sao) + lan truyền
`src/main.py:64-77` và `src/dashboard.py:35-43` đều chỉ đọc header;
`:80` `yeu_cau_data_analytics = lay_user` (ủy thác 100% cho gateway).
**LAN TRUYỀN — điểm đáng lo nhất:** `radary_bridge.py:20-23` và `niche_run.py:40-44`
TỰ DỰNG LẠI `X-Remote-*` từ claims CHƯA XÁC THỰC rồi gửi sang RadarY/niche-research
→ **một app thủng là cả cụm thủng**, kể cả app đích có kiểm loopback đúng.
Cộng: `/api/agent/*` không token (`agent_api.py:27,52,70`); `/registry` trả toàn bộ
mục lục = bản đồ trinh sát. IDOR `/bao-cao-goc/{id}` (`main.py:644-653`) tải Excel
gốc của người khác; `nguoi` nhận TỪ FORM client (`:508,545`) → ghi cache vào file
người khác, đốt quota LLM của họ.
**E5 (TRUNG BÌNH):** quyền thực tế là **L1 TOÀN CÔNG TY**, không phải "Kinh doanh L2"
như đã chốt — `nen/rules/phan_quyen.json` khai `"vao": {"min_level": 1}` không rào
bộ phận, và app KHÔNG đọc `X-Remote-Actions`.

### G6. TRUNG BÌNH — Dịch vai bằng SO KHỚP CHUỖI CON
`nen/iam/iam.py:602-608`: `if ("xoa" in ma or "toan_quyen" in ma)` → `vai_xoa`;
`any(t in ma for t in ("sua","tao","them"))` → leader.
Hiện chưa bị lợi dụng (đã liệt kê toàn bộ action trong `nen/rules/phan_quyen.json`),
nhưng thêm một action tên `xem_lich_su_xoa` là **thăng quyền lặng lẽ**.
Kèm: video-review KHÔNG khai `vai_xoa` → action `xoa` (L4) rơi vào mặc định `"admin"`,
cao hơn khuôn các app khác (`manager`).
ĐỐI CHIẾU LÀM ĐÚNG: `plannery/server.py:206-216` `_vai_tu_actions` dùng SO KHỚP TẬP
HỢP CHÍNH XÁC → không dính bẫy này.

### HAI APP CHẮC NHẤT — dùng làm KHUÔN MẪU khi sửa các app khác

**seo-optimize (:9115) — chắc nhất.** Không có lỗ nghiêm trọng.
- SSO fail-closed HAI điều kiện: `seo/server.py:880-884` kiểm cả `SEO_TRUST_PROXY`
  (`:304-305`) VÀ `self._ip()` từ **socket thật** (`:859-860`), không đọc X-Forwarded-For.
- **Endpoint LẠ → đòi quyền CAO NHẤT** (`:940-947` `PERM_OF.get(path,"users")`) —
  fail-closed đúng chiều. `DEFAULT="viewer"` (`seo/roles.py:143`).
- 12 cửa quản trị 404 vô điều kiện khi SSO (`:316-319`, `:927-935`).
- SSRF allowlist chủ động (`seo/phong_thu_v3.py:64-82`), traversal `_safe_token`
  (`seo/common.py:217-235`), key chỉ trả đuôi (`seo/admin_keys.py:41-57`).
- Điểm yếu DUY NHẤT (TRUNG BÌNH): CSRF dựa `Sec-Fetch-Site`, **không gửi header thì
  cho qua** (`:1391-1393`) — curl/script bỏ qua được; giảm nhẹ vì vẫn so Origin (`:1409`).

**radary (:9111) — chắc thứ nhì.** SSO fail-closed đúng (`radary/auth.py:106`, loopback
`:64-65`, mặc định viewer `:87`). SQL không injection. Traversal whitelist regex
(`report.py:337-344`). Key chỉ trả masked.
- TRUNG BÌNH: `PATCH /api/orgs/{org}/keys/{kid}` **SÓT** `_sso_quan_tri_dong()`
  (`api.py:342-343`) — 14/15 route anh em đều có. Route quản trị org duy nhất còn mở.
- TRUNG BÌNH: cookie thiếu `secure` mặc định (`auth.py:35-36`, `RADARY_SECURE_COOKIE`
  không được đặt trong `start-all.ps1`).

## 5. Rủi ro NGOÀI code

- **R1. Mật khẩu app = mật khẩu tài khoản Windows máy chủ** (`nen/gateway/main.py:103`
  → `nas_sync.dong_bo_nen`, `nas_sync.py:83` `Set-LocalUser`). Đoán được mật khẩu
  một nhân viên là có tài khoản Windows trên máy chủ. **PHẢI cắt trước khi ra
  Internet.**
- **R2. Sao lưu cùng máy** — ransomware/hỏng ổ là mất cả gốc lẫn bản sao.
- **R3. Không có xác thực hai lớp** ở bất kỳ đâu trong hệ (grep totp/otp = rỗng).
- **R4. Vault**: mở/khóa là trạng thái TOÀN CỤC của tiến trình, tự khóa 600s.

## 7. TIẾN ĐỘ THI CÔNG

### Quyết định của Owner (05/09/2026)
- **Phiếu lương: KẾ TOÁN ĐƯỢC XEM CỦA MỌI NGƯỜI — ĐÚNG Ý ĐỒ, GIỮ NGUYÊN.**
  Mục A7 trong sổ này KHÔNG phải lỗ hổng, là nghiệp vụ. Đừng "sửa" ở đợt sau.
- **KHÔNG làm VPN** — chưa có nhân sự thực sự cần dùng từ xa, cứ thong thả làm cho chắc.
- Owner duyệt flow 7 giai đoạn; làm lần lượt, mỗi GĐ báo cáo rồi mới sang GĐ sau.

### GĐ 1 — KHUÔN XÁC THỰC CHUNG ✅ XONG (05/09)
Backup trước khi làm: `backup/truoc-siet-bao-mat_20260905_103630/` (iam.db + ket.db).

| Commit | Việc | Test |
|---|---|---|
| `017d0b3` | Helper `nen/common/xac_thuc_app.py` + **17 guard fail-open → fail-closed** | 6 + 1 quét cây |
| `60dfbff` (radary) · `6bb6f08` (niche) | 2 guard trong repo con | — |
| `ee9540a` | video-review đòi đủ 2 điều kiện | 149 pass |
| `b143405` | to-chuc (vault + lương) | 184 pass |
| `f456b60` | data-analytics — vá **CẢ HAI** bản sao danh tính | 150 pass |
| `fc26286` | ai-agent | 337 pass |

**Phát hiện thêm khi thi công (test quét ra, báo cáo rà soát chưa thấy):**
- Guard fail-open là **17 chỗ**, không phải 13 — gồm cả `apps/tasky` chưa từng được rà.
- data-analytics có **HAI** bản sao cửa danh tính (`main.py` + `dashboard.py`); ghi chú
  `ponytail:` trong chính file đã dự đoán "gộp về claims.py chung khi có mảnh thứ ba".

**Bài học thi công:** TestClient báo `client.host == "testclient"` nên bản vá làm 46
test video-review đỏ. Cách xử lý ĐÚNG là cho conftest giả lập loopback như hệ thật,
**KHÔNG nới bản vá cho test xanh** — nới là mở lại đúng lỗ vừa bịt. Conftest phải
TÔN TRỌNG test tự khai địa chỉ, nếu không thì chính test bảo vệ bị vô hiệu.

**Token nội bộ (lớp 2 cho 2 route phát API key):** `nen/common/token_noi_bo.py`.
SÁU nơi gọi 2 route này, HIỆN CHƯA nơi nào gửi header `X-Noi-Bo` (tương thích
ngược đang giữ chúng chạy). GĐ6 phải sửa ĐỦ 6 chỗ TRƯỚC khi đặt biến môi trường,
sai thứ tự là cả cụm mất khóa LLM:
  - `apps/ai-agent/src/cau_hinh_llm.py:26`
  - `apps/content-ultimate/src/contentultimate/khoa_v3.py:37`
  - `apps/data-analytics/src/dien_giai.py:82`
  - `apps/data-analytics/src/main.py:114`
  - `apps/data-analytics/src/niche_run.py:52`
  - `apps/niche-research/khoa_v3.py:46`
Kiểm IP một mình không đủ vì **mọi SSRF trong hệ đều phát request TỪ loopback**.
Tương thích ngược có chủ đích: chưa đặt `OUTLIERY_TOKEN_NOI_BO` → bỏ qua lớp 2
(guard loopback đã fail-closed vẫn giữ); **GĐ6 đặt token trong start-all.ps1 rồi
siết thành bắt buộc** — ĐỪNG QUÊN mục này.

### CẦN LÀM KHI RESTART CỤM (chưa làm — Owner chọn thời điểm)
4 app mới cần cờ trong Arguments của tác vụ nền, **thiếu là app trả 401 toàn bộ**:
`AA_TRUST_PROXY=1` (ai-agent) · `TC_TRUST_PROXY=1` (to-chuc) ·
`DA_TRUST_PROXY=1` (data-analytics) · `VR_TRUST_PROXY=1` (video-review).

### GĐ 2 — VÁ LỖ NGHIÊM TRỌNG (đang làm, 05/09)

| Commit | Lỗ | Kết quả |
|---|---|---|
| `daba943` (content-ultimate) | **G2** ghi file tùy ý = RCE gián tiếp | 804 pass, 4 test mới |
| `51d4b06` (plannery) | **G4** `/api/state` rò toàn bộ nhân sự | 57 pass, kiểm sống 401/200 |
| `2f3882d` (niche) | **G3-C1/C2** traversal + rò khóa YouTube | 25 pass, 3 test mới |
| `9cf6ace` | **T1** video_id + **T2/T3** ky/thang — vá ở HÀM LÕI | 347 + 202 pass |
| `11e0816` | **G1** video-review stream /media (hết OOM) | 149 pass |

**BÀI HỌC TEST quan trọng (đã ghi vào chính test):** bản test đầu cho lỗ `ky` XANH
NGAY TỪ ĐẦU — nhưng xanh vì **file không tồn tại**, không phải vì bị chặn; đường
dẫn thật vẫn thoát ra ngoài (soi tận mắt `normpath` mới thấy). **Test xanh ngay từ
đầu là dấu hiệu TEST SAI, không phải code đúng.** Phải đo TRỰC TIẾP cái cần chặn.

**Quyết định kỹ thuật:** `video_id` chặn theo **BỘ KÝ TỰ** `[0-9A-Za-z_-]` (dài
1–40), KHÔNG siết 5–20. Bộ ký tự mới là thứ chặn traversal (`/`, `\`, `.` đều
ngoài bộ); siết thêm độ dài chỉ đổi lấy rủi ro phá dữ liệu thật mà không thêm an
toàn — dữ liệu thật có id ngắn kiểu "abc".

### CÒN LẠI GĐ 2 — CẦN OWNER QUYẾT
**13 route niche-research không có gate quyền** (mục G3-C3). Cơ chế quyền của app
ĐÃ CÓ và làm đúng (`_get_role`, 4 vai admin/manager/leader/seo) — chỉ là 13 route
không gọi nó. Đề xuất mức quyền:
- **Đọc (10 route)** `/api/projects` `/api/status` `/api/docs` `/api/mdtext`
  `/api/report` `/api/dashboard` `/api/watch` `/api/signals` `/api/timeseries`
  `/api/log` `/api/download` → **seo trở lên** (mọi người đã đăng nhập).
- **Ghi (1 route)** `POST /api/upload/{name}` → **leader trở lên** (nút Upload
  hiện chỉ ẩn ở UI `web/app.js:301`, server không kiểm).


## 6. Nhật ký quyết định

- **05/09/2026** — Mở sổ. Chốt tách Đích A / Đích B. Chốt dùng VPN làm giải pháp
  tạm cho nhu cầu từ xa. Chưa sửa một dòng code nào — mới rà soát.
