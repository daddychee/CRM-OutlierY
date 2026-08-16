# DE.md — sổ chủ đề KHỐI ĐẾ (tầng nền) · ĐỀ XUẤT TÁI THIẾT — chờ Owner duyệt

> Vai trò file: sổ chủ đề mạch KHỐI ĐẾ — đề xuất chức năng, quyết định đã chốt,
> trạng thái, bẫy. Hiến pháp kiến trúc vẫn là [kien_truc_nen.md](kien_truc_nen.md)
> (đế ở đây = 5 mảnh nền: Gateway · IAM · Két · Chuẩn dữ liệu · **Danh bạ**).
> Soạn 16/08/2026 từ khảo sát: đế v2 hiện trạng + bản đồ kênh/niche/API-key
> TOÀN BỘ 9 app hệ cũ (mục 0b).

## 0b. Kiểm kê hiện diện — 9 app, không sót app nào

| App | Đơn vị nó chạm | Hiện diện trong đế (đề xuất) |
|---|---|---|
| RadarY | niche (workspace), pool đối thủ, bảng api_keys Fernet + llm_config | ngách N-xxx (Đ4), kho khóa YT (mục 3b) |
| SEO Optimize | market/niche/kênh nhà (23, có UCxxx)/format/tập; 19 khóa YT + GLM/OpenAI trong .env | kênh K-xxx + thị trường + kho khóa (Đ4) |
| PlannerY | dự án=niche, kênh `ch_xxx`, người `ns_<mã NS>` | ngách + kênh qua `lien_ket_app` (Đ4) |
| Niche Research | dự án=ngách (thư mục) | ngách N-xxx (Đ4) |
| Content Ultimate | author giọng văn, run; video đối thủ | không vào danh bạ; LLM key từ két (Đ4) |
| **SpeakY** | voice profile đặt tên tay theo ngách/kênh (`Lifein-Drew`, `OLD_BENJAMIN` vs `OLD___Benjamin` — đã trùng lặp); jobs_log theo người | kênh ↔ voice profile qua `lien_ket_app` (app_slug=speaky) — mỗi kênh khai giọng chuẩn, hết đặt tên tự do |
| **VOX** (mới, chưa vào một cửa) | video pipeline Veo 3.1; ngôn ngữ EN/ES; LLM OpenAI-compatible | thị trường/ngôn ngữ đọc từ đế + LLM key từ két; khai hợp đồng app khi nhúng — Owner chốt thời điểm |
| **flowkit** (mới, dịch vụ :8100) | cầu Google Flow/Veo cho VOX; db riêng | dịch vụ hạ tầng — vào hợp đồng app (health) khi nhúng; khóa Flow vào két |
| AI Agent (→ V3: tri-thuc/data-analytics/to-chuc) | báo cáo theo kênh, KPI, vault, writer/critic key .env | mục 6 + két đã có `llm.<vai>` |

## 0. Vì sao phải tái thiết (bằng chứng đo được 16/08)

- Danh bạ — mảnh ④ của hiến pháp — thực tế chỉ là **CSV 4 dòng seed**: không UI,
  không API ghi, không audit, không backup danh phận, không validate; 3/4 dòng
  còn ghi chú "Owner kiểm lại". Dòng `K-OUTLAND` **gộp nhầm 2 kênh YouTube thật**
  (Outland EN `UCSoRLy…` + Outland KR `UC3MUra…`).
- Hệ cũ: cùng một kênh thật mang 4–6 danh tính (RadarY id máy / SEO slug file +
  mã gõ tay / PlannerY `ch_xxx` + tên / Data Analytics **tên file Excel** —
  `ten_kenh` trong 8 báo cáo **rỗng 100%**, tính năng so sánh kỳ bị chặn cứng).
  ~5 ngách thật có **8 cách viết tên**. 25/30 kênh đối thủ SEO trùng RadarY mà
  hai app không biết nhau. Giới hạn kênh/niche/thị trường nằm rải trong sổ riêng
  từng app (RADARY_SSO_MAP, users.json SEO) — ngoài tầm bảng phân quyền OUTLIERY.
- Bảng quyền đế chỉ có 2 chiều (app × hành_động) — không diễn đạt được
  "người này chỉ xem kênh kia".

## 1. BỐN QUYẾT ĐỊNH OWNER ĐÃ CHỐT (16/08/2026)

1. **Phạm vi danh bạ**: KÊNH NHÀ + NGÁCH + THỊ TRƯỜNG. Kênh đối thủ KHÔNG vào
   đế — là nghiệp vụ theo dõi của RadarY/SEO, sẽ gắn về ngách chuẩn (mã N-xxx)
   ở giai đoạn thay thế app phụ.
2. **Kênh đa ngữ**: mỗi kênh YouTube thật (mỗi UCxxx) = MỘT mã K-xxx riêng;
   trường `kenh_goc` nối bản dịch về kênh gốc (khớp khái niệm clones PlannerY).
   → seed K-OUTLAND phải tách 2.
3. **Nhập liệu ban đầu: NHẬP TAY TỪ ĐẦU** (như nhân sự GĐ4) — xóa seed, nhập
   từng đơn vị qua form. Máy chỉ cung cấp BẢNG THAM KHẢO chỉ-đọc (mục 7) để gõ
   nhanh, không import tự động.
4. **Quyền sửa danh bạ**: Owner + **Manager bộ phận chủ quản** được TẠO kênh/ngách
   + sửa vận hành (vòng đời, phụ trách, tên hiển thị, alias); **đổi MÃ + xóa/khai
   tử = chỉ Owner** (xác nhận 2 lớp gõ lại mã). Mọi thao tác ghi nhật ký.

## 2. LUẬT PHÂN CÔNG — chống chồng chéo (bất biến mới của đế)

| Tầng | Giữ gì | Cấm gì |
|---|---|---|
| **ĐẾ** | DANH TÍNH (mã bất biến K-xxx/N-xxx/TT-xxx, tên chuẩn, alias, UCxxx), PHÂN LOẠI (ngách, thị trường, loại kênh), VÒNG ĐỜI, PHỤ TRÁCH (mã NS-xxx), QUYỀN phạm vi thực thể, LIÊN KẾT khóa từng app, VẾT (audit) | không giữ dữ liệu nghiệp vụ (video, số liệu, script, lịch) |
| **APP** | nghiệp vụ của nó, mọi bản ghi gắn **MÃ đế** (không gắn tên) | CẤM tự đẻ sổ kênh/ngách; CẤM ô nhập tên kênh tự do — mọi ô kênh/ngách là DROPDOWN đọc từ đế (khớp bất biến "metadata dropdown cố định" của hiến pháp) |

Mã thực thể **bất biến như doc_code**. Tên hiển thị đổi được — mã không bao giờ.

## 3. MÔ HÌNH DỮ LIỆU — `data/nen/danh_ba.db` (SQLite, migrations riêng)

Chuyển hộ khẩu từ `nen/rules/danh_muc.csv` (luật) sang **DỮ LIỆU vận hành** đúng
Luật 1 hiến pháp: CRUD qua UI + audit; giữ **cửa Excel** bằng nút Xuất/Nhập CSV.
Khai `du_lieu_nen` trong apps.json (sqlite-snapshot, vàng, vĩnh viễn) — hết cảnh
danh bạ vô danh phận backup.

```
thi_truong (ma TT-xx PK, ten, ngon_ngu, ghi_chu)              -- vd TT-US/English
ngach      (ma N-xxx PK, ten_chuan, trang_thai, ghi_chu)      -- trang_thai: khai_thac|thu|nghi
kenh       (ma K-xxx PK bất biến, ten_chuan, channel_id UNIQUE khi có (UCxxx),
            ngach_ma FK, thi_truong_ma FK, loai_kenh,          -- khóa content_type_profiles
            trang_thai,                                        -- vòng đời mục 4
            kenh_goc_ma FK NULL,                               -- bản dịch → kênh gốc
            phu_trach NULL,                                    -- mã NS-xxx (không phải username)
            bo_phan_chu_quan, tao_luc, ghi_chu)
bi_danh    (thuc_the_ma FK, bi_danh, UNIQUE(bi_danh) TOÀN CỤC) -- alias đụng nhau = chặn từ cửa
lien_ket_app (thuc_the_ma FK, app_slug, khoa,                  -- thay 5 cột cứng CSV
            PRIMARY KEY(thuc_the_ma, app_slug))                -- + hết hardcode CAC_COT_KHOA
```

- Audit: mọi ghi qua gateway → `iam.ghi_nhat_ky` (cùng sổ với quyền — một chỗ tra).
- `danh_ba.py` v2: GIỮ nguyên 5 hàm đọc (đổi backend + **cache theo mtime** như
  hop_dong/iam đã vá) → cầu nối P6 không sửa chữ ký; THÊM hàm ghi (chỉ gateway
  gọi). App phụ tương lai đọc qua HTTP `/api/danh-ba/*`.
- Khớp tên (router cầu nối): sửa 2 nợ — khớp theo **ranh giới từ** + ưu tiên tên
  dài nhất (hết "Life" nuốt "Life In"); phục vụ cả `ngach` (đang là mã chết).

## 3b. MẢNH TÀI NGUYÊN API NGOÀI — YouTube · LLM · Veo/Flow (mở rộng KÉT)

**Hiện trạng phân tán (đo 16/08):** SEO giữ `YOUTUBE_API_KEYS` = 19 khóa trong
MỘT biến .env + `GLM_API_KEY`/`OPENAI_API_KEY`; RadarY có bảng `api_keys` riêng
(Fernet, cờ `harvest/backup/workspace_id` — đã tự chế xoay khóa) + `llm_config`
per-org; agent-app giữ WRITER/CRITIC/ANTHROPIC key trong .env; VOX/flowkit thêm
LLM + Google Flow key mới. Bốn kho khóa, bốn kiểu mã hóa, không audit chung.

**Đề xuất — két (mảnh ③) thành MỘT kho tài nguyên ngoài:**
- Keyspace phân vùng trong két sẵn có (Fernet, write-only, đuôi 4 ký tự):
  `llm.<vai>.*` (đã có — V3 dùng) · `yt.<nhom>.keys` (kho khóa YouTube theo NHÓM,
  mỗi nhóm một bó khóa xoay được — thay 19-khóa-một-biến của SEO và bảng riêng
  của RadarY) · `dich_vu.<ten>.*` (Flow/Veo, dịch vụ khác về sau).
- **Phân bổ theo app**: bảng nhỏ `cap_phat(app_slug, keyspace)` — app chỉ đọc
  được nhóm khóa được cấp; app phụ nhận qua env lúc khởi động từ két (giai đoạn
  thay thế), app V3 đọc API loopback như LLM hiện nay.
- **Audit + đếm dùng**: đổi khóa ghi `nhat_ky_quyen` (két hiện KHÔNG vết — nợ đã
  đo); lượt gọi YouTube/LLM ghi log JSON-lines theo chuẩn P4 (`data/logs/`) để
  thấy khóa nào sắp cạn quota — nguồn sự thật cho việc xoay khóa, thay vì mỗi
  app tự đoán.
- **UI**: trang mới `/general/api-keys` (mục 5) — nhập/xóa khóa theo nhóm, cấp
  phát cho app, xem đuôi + lượt dùng gần nhất. LLM theo vai vẫn ở AI Models
  (mỗi trang một việc).

## 4. VÒNG ĐỜI KÊNH (đề xuất mặc định — Owner chỉnh trực tiếp khi duyệt)

`uom_mam` (lập xong hồ sơ, chưa đăng) → `sandbox` (nuôi/ngâm) → `hoat_dong`
(đăng đều, chưa bật tiền) → `monetized` → `ngu_dong` (tạm dừng) → `khai_tu`.
Đổi trạng thái = 1 click có vết; `khai_tu` chỉ Owner (gỡ mềm — không xóa dòng).

## 5. KHU GENERAL SAU TÁI THIẾT — 10 trang, mỗi trang MỘT việc

| Trang | Trạng thái | Chức năng đề xuất |
|---|---|---|
| Overview | sửa | số thực thể thành LINK; cảnh báo kênh thiếu phụ trách / ngách không kênh |
| **Channels** `/general/channels` | **MỚI** | bảng kênh (lọc ngách/thị trường/trạng thái/phụ trách) · form tạo-sửa toàn dropdown (ngách, thị trường, loại kênh, phụ trách lấy từ People) · đổi vòng đời 1 click · khối liên kết app (khóa từng app, chỉ Owner sửa) · alias · Xuất/Nhập CSV · gate mục 1-Q4 |
| **Niches** `/general/niches` | **MỚI** | ngách (CRUD + trạng thái) + khối THỊ TRƯỜNG (bảng nhỏ cùng trang — cùng là trục phân loại) |
| Accounts | giữ | như hiện tại |
| People | sửa | thêm SỬA/XÓA hồ sơ + đổi `trang_thai` (đang chỉ tạo được); phát `planner_id` dẫn xuất `ns_<mã>` trong API danh sách người → **fix nhánh KPI planner_id chết** ở to-chuc |
| Permissions | sửa | thêm chiều THỰC THỂ: `quyen_override` thêm cột `thuc_the` (mặc định `*`; migration Đ1 chừa sẵn, UI Đ3) — về sau thay RADARY_SSO_MAP + scopes SEO; thêm hàng HÀNH ĐỘNG CON per-app (trả nợ "gate tinh còn trong app") |
| AI Models | sửa | thêm XÓA vai; két ghi audit khi đổi key (đang không vết) |
| **API Keys** `/general/api-keys` | **MỚI** | kho khóa YouTube theo nhóm (xoay được) + khóa dịch vụ (Flow/Veo…) · cấp phát cho app · đuôi 4 ký tự + lượt dùng gần nhất · chỉ Owner (giỏ tuyệt đối, như két) — chi tiết mục 3b |
| Data & Backup | sửa | thêm nút CHẠY backup tay; danh_ba.db tự vào manifest |
| Audit Log | sửa | lọc theo người/hành động (đang cứng 200 dòng) |
| Applications | sửa | hợp đồng app thêm ô khai thực thể tiêu thụ (`thuc_the: {kenh: "..."}`) — nguồn sinh `lien_ket_app`, hết sửa Python khi thêm app; cầu nối đọc CỔNG từ hợp đồng (bỏ hardcode 9102); ghi nhận VOX + flowkit chờ khai hợp đồng khi nhúng một cửa |

## 6. APP TIÊU THỤ — đổi gì ở V3 ngay (Đ2)

- **data-analytics**: ô kênh datalist tự do → **dropdown bắt buộc chọn từ đế**
  (server tra mã, từ chối giá trị lạ); bản ghi lưu `kenh_ma` (K-xxx), `ten_kenh`
  chỉ còn hiển thị; `so_sanh_ky` so theo `kenh_ma` (hết chặn oan vì lệch chính
  tả); `loai_kenh` TỰ ĐIỀN từ đế (hết trục phân loại lặp); màn GÁN TAY 1 lần cho
  8 báo cáo cũ (Owner/người chạy gán kênh — không tự đoán); `danh_sach_ten_kenh()`
  nghỉ hưu (chỉ còn fallback hiển thị bản ghi chưa gán).
- **to-chuc/KPI**: nối PlannerY bằng `planner_id` dẫn xuất từ mã NS (đang so họ
  tên); về sau video-đến-hạn theo kênh đọc `kenh_ma`.
- **tri-thuc**: chưa đụng (loai_kenh_ctx giữ); nút 📊 cầu nối vào chat thuộc đợt
  phá đóng băng hoi_dap (ghi việc treo — endpoint P6 hiện KHÔNG có cửa người dùng).

## 7. BẢNG THAM KHẢO NHẬP TAY (chỉ-đọc, để gõ nhanh — máy không tự ghi)

Nguồn khảo sát 16/08: **23 kênh nhà** (SEO profiles — nơi duy nhất có UCxxx thật,
xem `C:\OutlierY\apps\seo-optimize\profiles\*.json`: cột channel/channel_id/code/
niche/lang/created_by) · **7 kênh PlannerY** (LIFE DECODED, Outland, Astro Mind,
Time Vault, INVESTIGATE1, Cosmic Depth, THE HEALTHY ELDER) · **~5-8 ngách** (Life
In · Space · Investigation · OLD · Health/SENIOR HEALTH · Quantum · Storm · Travel
Documentary) · **3 thị trường** (US/English · SPAIN/Spanish · KOREA/Korean).
Khi dựng trang Channels sẽ kèm trang in "danh sách đối chiếu" từ khảo sát này.

## 8. NHỊP TRIỂN KHAI (mỗi đợt một commit xanh, nghiệm thu sống rồi mới sang đợt)

- **Đ1 — Xương**: danh_ba.db + migrations (chừa cột `thuc_the` cho quyen_override)
  + danh_ba.py v2 + 2 trang Channels/Niches + audit + xuất/nhập CSV + xóa seed cũ
  → **Owner nhập tay danh bạ thật** (nghiệm thu = danh bạ sống ≥ 23 kênh + ngách
  + thị trường, thao tác có vết). Kèm trang API Keys + keyspace `yt.<nhom>`/
  `dich_vu.<ten>` + audit két (mục 3b — phần kho khóa; cấp phát cho app phụ để Đ4).
- **Đ2 — Nối app V3**: mục 6 (data-analytics + KPI + cầu nối) + backfill gán tay
  8 báo cáo. Nghiệm thu: so sánh kỳ chạy được với 2 báo cáo cùng kênh.
- **Đ3 — Quyền thực thể**: UI Permissions phạm vi kênh/ngách; test ghim
  "Staff chỉ thấy kênh được giao".
- **Đ4 — Giai đoạn thay thế app phụ** (ngoài phạm vi đợt này): RadarY workspace ↔
  N-xxx, SEO profile ↔ K-xxx qua `lien_ket_app`; gỡ RADARY_SSO_MAP + scopes riêng.

## 9. VÁ NỢ ĐẾ ĐI KÈM (từ khảo sát — làm trong Đ1/Đ2, mục nào lớn tách commit)

két: audit + xóa khóa · People: sửa/xóa hồ sơ + trạng thái · sinh mã NS chống
race + bỏ trần 999 · bo_phan hết text tự do (dropdown từ danh mục) · Audit lọc ·
nút chạy backup · hợp đồng app validate du_lieu · cau_noi bỏ hardcode cổng.

## 10. KHU CHỨC NĂNG NGHIỆP VỤ — HR Hub · Finance Hub (đề xuất theo yêu cầu Owner 16/08)

Bối cảnh Owner nêu: HR hiện chỉ tạo được hồ sơ; tương lai HR cần CHẤM CÔNG +
ĐÁNH GIÁ KPI; Kế toán cần chỗ làm THU CHI. Cần "tính năng to hơn" theo MẢNG
nghiệp vụ, không phải từng trang lẻ.

**Khái niệm — HUB (khu làm việc theo chức năng):** mỗi mảng hỗ trợ có MỘT cửa
gộp mọi việc của mảng đó. Hub KHÔNG phải app mới và KHÔNG giữ dữ liệu riêng —
nó là VỎ điều hướng đặt trong app to-chuc, mở bằng **GIỎ CHỨC NĂNG** cấp từ đế.

**Giỏ chức năng (phan_quyen.json thêm nhóm `gio_chuc_nang`):**
- `nhan_su` — HR Hub: hồ sơ nhân sự (CRUD qua API đế — IAM vẫn là nguồn sự thật,
  hub không bản sao) · duyệt hồ sơ · chấm công (xem + chốt công kỳ) · KPI (xem +
  **đánh giá xếp loại kỳ** A/B/C kèm nhận xét — dữ liệu mới ở to-chuc) · nghỉ phép.
  Mặc định: Owner + Hành chính Nhân sự L3+ (thay luật hardcode `quyen_nhan_su`
  hiện tại — chuyển thành giỏ tick được).
- `ke_toan` — Finance Hub: SỔ THU CHI (append-only, sửa = bút toán đảo có vết) ·
  danh mục khoản thu/chi (luật ngoài code, sửa Excel được) · mỗi bút toán GẮN MÃ
  KÊNH từ danh bạ (tùy chọn) → **báo cáo LÃI/LỖ THEO KÊNH** (điểm ăn tiền: nối
  trục thực thể mục 3 — chi phí proxy/tài khoản/voice và doanh thu AdSense quy
  về từng K-xxx) · tổng hợp tháng · lương (đợt sau — nối chấm công + xếp loại KPI).
  Mặc định theo bộ phận Kế toán (xem chốt dưới) + Owner.

**CHỐT Owner 16/08 — Kế toán là BỘ PHẬN RIÊNG, hiện HCNS KIÊM NHIỆM:** thêm
"Kế toán" vào danh mục bộ phận (danh mục 4→5, các bộ phận cũ không đổi); giỏ
`ke_toan` mặc định cho bộ phận Kế toán (đề xuất từ L2 — Owner chỉnh trên UI);
giai đoạn kiêm nhiệm: người HCNS nhận giỏ qua TICK ở trang Permissions, badge
"kiêm nhiệm" hiện ở mọi nơi liên quan (People, HR Hub, Finance). Khi tuyển kế
toán chuyên trách: tạo hồ sơ bộ phận Kế toán → giỏ tự có, gỡ tick người kiêm
nhiệm — không sửa luật. UI duyệt: `docs/mockup-de/permissions.html` (ô P2, P5).

**Chống chồng chéo (áp luật mục 2):** hồ sơ người = dữ liệu ĐẾ (IAM); chấm công/
KPI/đánh giá/thu chi = dữ liệu NGHIỆP VỤ ở to-chuc, tham chiếu mã NS-xxx + K-xxx;
danh mục khoản = rules CSV. Sidebar: mục "HR" / "Finance" chỉ hiện với người có
giỏ (gateway phát cờ trong X-Remote-Apps như cờ `nas`/`quan-tri` sẵn có).
Trang People trong General GIỮ vai trò quản trị gốc (Owner); HR Hub là cửa LÀM
VIỆC hằng ngày — cùng dữ liệu, hai cửa hai vai, không đúp bảng.

## 11. QUY TRÌNH LÀM UI TRƯỚC (Owner chốt 16/08: "chưa code, tạo trước UI")

Mọi trang mới của mạch đế đi theo nhịp: **mockup tĩnh → Owner chỉnh trên UI →
chốt → mới code logic**. Bộ mockup đợt 1 tại `docs/mockup-de/` (mở thẳng bằng
trình duyệt, dữ liệu mẫu lấy từ khảo sát thật, banner vàng đánh dấu MOCKUP):
`channels.html` · `niches.html` · `api-keys.html` · `hr-hub.html` ·
`finance-hub.html`. Owner ghi chú thẳng lên từng khối (mỗi khối có mã ô vd C1,
C2… để trỏ khi phản hồi).

## Trạng thái

- 16/08/2026 — Sổ lập, đề xuất hoàn chỉnh, 4 quyết định Owner đã chốt (mục 1).
- 16/08/2026 — Owner bổ sung: kiểm đủ 9 app (mục 0b), mảnh API keys (mục 3b),
  khu chức năng HR/Kế toán (mục 10), quy trình UI-trước (mục 11). **Đang ở bước:
  Owner chỉnh mockup `docs/mockup-de/` → chốt → Đ1 code.**
