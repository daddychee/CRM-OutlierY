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
| AI Agent (→ V3: ai-agent/data-analytics/to-chuc) | báo cáo theo kênh, KPI, vault, writer/critic key .env | mục 6 + két đã có `llm.<vai>` |

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
- **ai-agent**: chưa đụng (loai_kenh_ctx giữ); nút 📊 cầu nối vào chat thuộc đợt
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

## 12. PHẢN HỒI OWNER TRÊN MOCKUP (16/08 — đã áp vào UI, chờ duyệt vòng 2)

1. **Hồ sơ nhân viên LƯU TRỮ ĐẦY ĐỦ** (People / HR Hub ô H1b): Tên · Ngày sinh ·
   CCCD · Địa chỉ thường trú · Ngày vào làm · Bộ phận · Vị trí · Cấp bậc + **kho
   TÀI LIỆU GỐC đính kèm hồ sơ** (scan CCCD 2 mặt, Sơ yếu lý lịch, khác). Tác động
   schema Đ1: bảng `nguoi` thêm `ngay_sinh, cccd, dia_chi, ngay_vao, cap_bac`;
   kho file `data/nen/ho-so-tai-lieu/<ma NS>/` khai `du_lieu_nen` (vàng, vĩnh
   viễn). **NHẠY CẢM**: CCCD + tài liệu chỉ Owner + giỏ nhan_su xem, mọi lượt XEM
   ghi nhật ký (khuôn audit vault).
2. **UI thật KHÔNG chứa ghi chú giải thích** (kiểu "— toàn dropdown, không ô gõ
   tên…"): đã quét sạch mọi chú thích khỏi 6 trang mockup; thành LUẬT cho UI đế
   khi code — giải thích để trong sổ/hướng dẫn, không để trên màn hình.
3. **API Keys đổi cấu trúc** (Owner chốt): hiển thị THEO API (YouTube Data v3 /
   Flow-Veo / LLM) → từng KHÓA một dòng → **cấu hình khóa cho từng app** (kèm
   trần lượt/ngày tùy chọn) → tab **QUOTA LOG** (thời gian · API · khóa · app ·
   việc · lượt · quota tiêu · còn lại; đọc từ log JSON-lines chuẩn P4, lọc + xuất
   CSV). Bỏ khái niệm "nhóm khóa" làm trục chính — nhóm chỉ còn là nhãn lọc.

## 13. PHẢN HỒI OWNER VÒNG 3 (16/08 — đã áp vào mockup, chờ duyệt)

1. **NICHE CÓ TRƯỚC KÊNH**: Niches đứng đầu điều hướng; bảng niche hiện CHIP các
   kênh thuộc nó; niche nối app **Niche Research** qua `lien_ket_app`. Kênh chỉ
   tạo được khi đã có niche (form bắt chọn từ dropdown).
2. **Gộp C1+C4**: form tạo kênh thành MODAL mở từ nút "+ New channel" (một khối
   một việc, không còn form đứng thường trực). Kênh gắn mật thiết **Data
   Analytics**: bảng kênh thêm cột số báo cáo + ngày mới nhất; chi tiết kênh có
   khối báo cáo + đường sang Data Analytics.
3. **API-FIRST, đa loại API**: thứ tự tab = ① Add API → ② Cấu hình theo app →
   ③ Quota log. Loại API: YouTube Data v3 · **LLM (Claude/GLM/Gemini/ChatGPT/
   Deepseek — được CHỌN MODEL từng khóa)** · VEO · Seedream. Cấu hình theo app =
   mỗi VIỆC trong app chọn API (+model) nào — thay khái niệm vai LLM cũ của két
   (AI Models sẽ gộp về đây khi code — hết 2 trang một chuyện).
4. **Permissions về đúng 2 khái niệm**: P1 đổi nhãn "Nhân sự"; P2 = LUẬT THƯỜNG
   QUY (bộ phận nào xem bộ phận đó — bảng mặc định theo bộ phận); P3 = NGOẠI LỆ
   của từng nhân sự (vào thêm app / khu chức năng / phạm vi kênh-ngách / chặn
   bớt, mỗi ngoại lệ kèm lý do + ngày + người gán). Bỏ ma trận P2-P5 cũ.
5. **HR Hub**: hồ sơ chi tiết H1b chỉ mở khi DOUBLE-CLICK dòng nhân sự.
6. **Finance Hub**: thêm trục **MỤC TIÊU** — mọi bút toán bắt buộc gắn mục tiêu
   (tab Mục tiêu: ngân sách/đã chi/đã thu/tiến độ); Categories hiện TỔNG tháng +
   lũy kế từng mã. Khi code: **tham khảo lõi mở kế toán** (beancount/hledger
   plain-text ledger — khớp triết lý text-thuần + chỉ-thêm; quyết ở Đ2b) thay vì
   tự viết engine sổ.

7. **K5 chỉnh vòng 4 (Owner 16/08)**: "việc trong app" phải sinh từ **TÍNH NĂNG
   THẬT của app** — app khai danh sách việc-cần-API trong HỢP ĐỒNG APP (apps.json
   thêm ô `viec_api: [{ten, loai_api, nhieu_khoa}]`), trang cấu hình dựng bảng từ
   đó, không bịa việc chung chung. **Một việc nhận được NHIỀU khóa cùng loại**
   (pool gán cho việc, chế độ "xoay vòng" khi cạn quota — ca điển hình: RadarY
   harvest cần nhiều khóa YouTube v3; SEO extract 19 khóa cùng bản chất). Chế độ
   khác: "một khóa", "dự phòng khi lỗi". Mockup K5-K7 đã thể hiện 3 app mẫu
   (radary / ai-agent / vox). **Finance Hub: Owner giữ nguyên bản hiện tại, sẽ
   tự điều chỉnh sau** — không sửa thêm cho tới khi có phản hồi mới.

**Hai luật toàn cục Owner chốt:** (a) MỌI bảng/bản ghi hiển thị **ngày nhập
thông tin**; (b) **số tiền là DỮ LIỆU BẢO QUẢN LÂU DÀI** — sổ thu chi vào
`du_lieu_nen` mức quý VÀNG, giữ VĨNH VIỄN, chỉ-thêm (sửa = bút toán đảo), backup
sqlite-snapshot như iam.db.

## Trạng thái

- 16/08/2026 — Sổ lập, đề xuất hoàn chỉnh, 4 quyết định Owner đã chốt (mục 1).
- 16/08/2026 — Owner bổ sung: kiểm đủ 9 app (mục 0b), mảnh API keys (mục 3b),
  khu chức năng HR/Kế toán (mục 10), quy trình UI-trước (mục 11).
- 16/08/2026 — Chốt Kế toán = bộ phận riêng kiêm nhiệm (mục 10) + phản hồi vòng 1
  trên mockup đã áp (mục 12). **Đang ở bước: Owner duyệt mockup vòng 2
  (`docs/mockup-de/` — 6 trang) → chốt → Đ1 code.**
- 16/08/2026 — **Đ1.1 + Đ1.2/Đ1.3 CODE XONG** (`9720213` + commit trang):
  danh_ba.db 5 bảng (niche TRƯỚC kênh) + danh_ba.py v2 (API đọc giữ chữ ký, ghi
  + sinh mã + alias unique + liên kết app + khai tử mềm + xuất CSV, cache chịu
  WAL) + 2 trang /general/niches /general/channels (gate Manager+ tạo/sửa ·
  Owner liên kết/khai tử gõ-lại-mã · audit nhat_ky_quyen từng thao tác) —
  suite 89 + 64 pass, nghiệm thu sống HTTPS. UI đang theo style khu nền
  (form <details> thay modal mockup — làm đẹp đợt UI riêng).
  **SẴN SÀNG cho Owner nhập danh bạ thật** (thứ tự: Markets → Niches → Channels;
  bảng tham khảo mục 7). CÒN Đ1: API Keys (mục 3b + mockup K1-K8) + hồ sơ nhân
  sự mở rộng (mục 12.1) + cột thuc_the cho quyen_override.
- 16/08/2026 — **Đ2.1 + Đ2.3 XONG** (`00c8135`): router cầu nối khớp ranh giới
  từ + cụm-con nhường tên dài (Life/Life In/Outland-vs-Space có test ghim); cổng
  DA đọc từ hợp đồng app; KPI to-chuc phát planner_id dẫn xuất `ns_<mã NS>` —
  nối PlannerY theo ID. Root 90 + to-chuc 32 pass.
- **Đ2.2 KẾ TIẾP — data-analytics nối danh bạ (checklist thi công):**
  (a) `/chan-doan/kenh-goi-y` trả `[{ma, ten}]` TỪ DANH BẠ (danh_sach_ten_kenh
  nghỉ hưu khỏi gợi ý, giữ làm hiển thị bản ghi cũ); (b) form upload: ô kênh
  thành DROPDOWN bắt buộc (gửi `kenh_ma`), server tra `danh_ba.tra_thuc_the` —
  giá trị lạ từ chối 422; bản ghi lưu `kenh_ma` + `ten_kenh`=tên chuẩn;
  `loai_kenh` TỰ ĐIỀN từ đế khi kênh đã khai (form chỉ dùng khi đế trống);
  (c) `so_sanh_ky` (diagnosis_engine ~1503-1557) so `kenh_ma` khi cả 2 bản ghi
  có, fallback so ten_chuan-hóa cho bản ghi cũ; (d) màn GÁN TAY: trang
  bao-cao-lich-su hiện dropdown gán kênh cho bản ghi thiếu `kenh_ma`, POST
  `/bao-cao-lich-su/gan-kenh` điền Ô RỖNG của dòng đã có (ghi nguyên tử, khuôn
  cột Bản đẹp hệ cũ), gate DA chung; (e) test: từ chối kênh lạ · lưu kenh_ma ·
  loai_kenh tự điền · so kỳ theo mã chạy được với 2 báo cáo cùng kênh · gán tay.
  Lưu ý: conftest DA đã trỏ DANH_BA_DB tmp — test seed kênh qua API danh_ba.
- 16/08/2026 — **Đ1b HR HUB + Đ2b FINANCE HUB XONG** (Owner đòi đúng — 2 hub bị
  xếp sau danh bạ, nay đã trả): /hr (People·Attendance+chốt công chỉ-thêm·KPI
  Review xếp loại A/B/C append·Leaves) + /finance (Ledger JSONL chỉ-thêm + bút
  toán đảo·Goals ngân sách/đã chi·Categories 7 mã + tổng tháng/lũy kế·Channel
  P&L theo kenh_ma từ danh bạ). Giỏ nhan_su/ke_toan vào gio_uy_quyen (tick được
  ở Permissions, tick thắng mặc định cả 2 chiều); gateway phát cờ hr/finance
  (HCNS L3+ · Kế toán L2+ · Owner); sidebar user-menu + URL đẹp /hr /finance;
  4 store mới khai du_lieu (sổ tiền VÀNG vĩnh viễn). 4 suite 92+307/3+64+53
  pass; nghiệm thu sống: Owner 200 đủ tab, L2 không giỏ 403. Việc treo hub:
  Approvals + H1b hồ sơ chi tiết (đợi mục 12.1), export CSV, lọc ledger sâu,
  lương (nối chốt công + xếp loại).
- 16/08/2026 — **HR HUB MỘT CỬA XONG** (`43974f3`, Owner hỏi "Tại sao ko đưa
  Account và People vào luôn HR?"): gộp People + Accounts vào /hr. People nâng
  chỉ-xem → CRUD (`iam.sua_nguoi` trả nợ "hồ sơ chỉ tạo được": None = giữ
  nguyên trường, trạng thái ∈ cho_duyet/hoat_dong/nghi, KHÔNG có xóa hồ sơ —
  nghỉ việc = gỡ mềm 'nghi', mã NS bất biến, ghi nhật ký). Tab Accounts CHỈ
  render khi gateway phát cờ `accounts` (giỏ quan_tai_khoan — gõ ?tab=accounts
  tay vẫn bị ép về People, 0 chuỗi route lộ ra). KIẾN TRÚC: form hub POST
  thẳng route `/general/people|accounts/*` sẵn có kèm field ẩn `ve=hr`
  (whitelist) → 303 về /hr?bao/loi — quyền kiểm MỘT chỗ ở gateway, to-chuc
  không ghi IAM (Luật 4). GET /general/people|accounts nghỉ hưu thành redirect
  (khuôn /quan-tri), nav General gọn 2 mục. 4 suite root 98(+6) / to-chuc
  57(+4) / ai-agent 307+3skip / DA 64; nghiệm thu sống sau restart ĐỦ BỘ (bẫy
  nen/common): Owner đủ tab + form ve=hr, HR-không-accounts ẩn sạch tab, L2
  403. GIỚI HẠN ĐÃ BIẾT: người được tick `quan_tai_khoan` mà KHÔNG phải
  HR/Kế toán/Owner sẽ có cờ accounts nhưng thiếu cờ hr → không vào được hub
  (persona chưa tồn tại — mặc định giỏ chỉ Owner; khi ủy quyền thật thì cấp
  kèm giỏ nhan_su hoặc nới yeu_cau_hr nhận cờ accounts, quyết lúc đó).
  Trường bỏ trống trong form sửa = giữ nguyên (không xóa giá trị về rỗng —
  chấp nhận, form điền sẵn giá trị cũ). Link /general/people trong sidebar
  `sb_ns` của 3 app + hoi_dap.html ĐỂ NGUYÊN — sống qua redirect.
- 16/08/2026 — **HỒ SƠ NHÂN SỰ ĐẦY ĐỦ + TÀI LIỆU GỐC XONG** (`7db4e53`, Owner
  phê đúng: People chỉ 3 trường trần, không kế thừa V2 — mục 12.1 đáng lẽ phải
  đi CÙNG hub, lỗi xếp nhịp lần 2). Migration `003` (002 đã bị chiếm) thêm 5
  cột `nguoi`: ngay_sinh/cccd/dia_chi/ngay_vao/cap_bac (DEFAULT '' — hồ sơ cũ
  hiện '—', đã kiểm DB thật tự áp). `nen/rules/chuc_danh.csv` KẾ THỪA V2
  (7 vị trí; Kế toán/Thủ quỹ mang `Hành chính Nhân sự;Kế toán` cover kiêm
  nhiệm lẫn chuyên trách). IAM: `DEPARTMENTS` 5 (MỘT nguồn danh mục, lần đầu
  có hằng) + `CAP_BAC` slug intern/staff/leader/manager + kiểm CẶP bộ
  phận×vị trí Ở SERVER trên giá trị SAU GỘP (bài học 01/08 hệ cũ) +
  grandfather bản ghi cũ; nhật ký sua_nguoi chỉ ghi TÊN CỘT (CCCD/địa chỉ
  không lọt audit log). CCCD NHẠY CẢM: to-chuc pop ngay cửa đọc, chỉ giữ
  `cccd_che` (8 số + ****) — xem đủ qua `GET /general/people/cccd/{ma}`, MỖI
  lượt một dòng vết `xem_cccd` (khuôn vault). Tài liệu gốc (CCCD 2 mặt/SYLL/
  khác): upload whitelist pdf-jpg-jpeg-png trần 10MB, slug chống traversal,
  chống ghi đè hậu tố -2 ("thay" = nộp bản mới, bản cũ giữ), ghi nguyên tử,
  vết nộp + vết xem MỖI lượt; kho `data/nen/ho-so-tai-lieu/<mã>/` khai
  du_lieu_nen (VÀNG vĩnh viễn — backup đêm tự gom). UI People theo mockup
  H1b: double-click dòng mở chi tiết (JS thuần — an toàn LAN HTTP), Vị trí
  lọc theo Bộ phận, ô CCCD trống + placeholder bản che (rỗng = giữ nguyên →
  không thể lỡ ghi bản che vào DB), bảng có ngày nhập, không ghi chú màn
  hình. 4 suite 101(+3)/58(+1)/307+3skip/64; nghiệm thu sống: van CẶP trả
  đúng thông điệp, traversal 404, migration áp DB thật. GHI CHÚ: người nộp
  tài liệu tra ở Audit Log (chưa có cột riêng); không xóa được CCCD về rỗng
  qua form (chấp nhận). KẾ TIẾP mạch nhân sự (nợ V2 còn lại): luồng PHÊ
  DUYỆT (H2 — HR tạo trạng thái chờ → Owner duyệt + cấp tài khoản ngay màn
  duyệt, từ chối kèm lý do) + vòng đời hồ sơ↔tài khoản khi xóa/đổi.
- 16/08/2026 — **GỘP PEOPLE + ACCOUNTS = MỘT TAB "ACCOUNTS" + XÓA DỮ LIỆU NẠP
  MỚI** (`868708c`, Owner chốt: "People và account hiện đang trùng nhau. Gộp
  chức năng làm 1, để tên là account. Xóa hết dữ liệu cũ, nạp mới từ đầu").
  MỖI DÒNG = MỘT CON NGƯỜI (nguoi LEFT JOIN tai_khoan qua nguoi_ma; chưa cấp
  tài khoản → Username "—"; tài khoản mồ côi hiện dòng riêng không giấu).
  Form duy nhất "New person" → `POST /general/accounts/create-full`: hồ sơ đủ
  8 trường + khối tài khoản TÙY CHỌN (chỉ render khi cờ accounts); kèm
  username → gate quan_tai_khoan 403 TRƯỚC khi tạo gì; chống mồ côi (bài học
  V2 GĐ2): kiểm username trước → tạo hồ sơ → tạo tài khoản nối nguoi_ma (bộ
  phận LẤY TỪ HỒ SƠ) → lỗi thì XÓA hồ sơ vừa tạo + vết `rollback_tao_nguoi`
  (đã kiểm sống: mk ngắn → kho về 0 sạch). `POST /general/accounts/grant`
  cấp tài khoản cho hồ sơ có sẵn — mỗi hồ sơ TỐI ĐA MỘT tài khoản. Xóa tài
  khoản = thu hồi đăng nhập, hồ sơ giữ (lệ V2). Hai lớp quyền giữ nguyên
  trong MỘT tab: giỏ nhan_su thấy/sửa hồ sơ, khối Account (grant/reset/level/
  khóa/xóa) chỉ render + chỉ server nhận với quan_tai_khoan. tab=people +
  GET /general/people cũ đáp về tab gộp. 4 suite 103(+2)/58/307+3skip/64.
  DỮ LIỆU: đã xóa 20 tài khoản seed V2 + 1 hồ sơ, GIỮ DUY NHẤT `owner`
  (chống tự khóa), audit giữ nguyên làm sử liệu (vết `don_du_lieu`) — hệ
  SẠCH chờ Owner/HR nhập người thật từ đầu qua New person. VIỆC TREO: sửa
  bộ phận HỒ SƠ chưa tự chảy sang bộ phận TÀI KHOẢN (V2 có đồng bộ users.txt
  — cần Owner chốt chiều đồng bộ); rollback DELETE nguoi nằm ở gateway, cố ý
  KHÔNG thêm xoa_nguoi public vào iam (giữ luật không xóa hồ sơ).
- 16/08/2026 — **API KEYS CODE LẠI ĐÚNG MOCKUP K1-K8 — GỠ "AI MODELS" TỰ CHẾ**
  (`c661483`, Owner phê đúng VI PHẠM QUY TRÌNH: tên + cấu trúc "AI Models" tự
  đặt trong đợt đổi URL EN, chưa qua duyệt, trái chốt mục 12.3 "hiển thị THEO
  API"). Trang `/general/api-keys` (gate ket_cau_hinh chỉ Owner) 3 tab đúng
  mockup: Add API (4 khối YouTube v3 / LLM 5 nhà / VEO / Seedream — khóa
  write-only đuôi ••••4, thu hồi gõ-lại-đuôi, model lưu ngay) → Per-app
  config (`viec_api` khai trong HỢP ĐỒNG apps.json: ai-agent writer/critic/
  extract + DA dien_giai; một việc nhiều khóa, chế độ mot_khoa/xoay_vong/
  du_phong) → Quota log (chuẩn P4 JSONL `data/logs/quota/`, helper
  `nen/common/quota_log.py`, lọc + export CSV, rỗng thật không bịa 0).
  TRẢ NỢ AUDIT KÉT: mọi thêm/thu hồi/cấp phát ghi nhat_ky_quyen CHỈ ĐUÔI.
  TƯƠNG THÍCH: `ket.cau_hinh_llm` GIỮ CHỮ KÝ (ai-agent + DA đọc loopback
  `/api/cau-hinh/llm/{vai}` → đổ env lúc khởi động — hai app không đổi một
  byte); ưu tiên cấp phát ai-agent việc cùng tên → fallback `llm.<vai>.*` cũ
  (test hồi quy bằng tuyệt đối); cấp phát 0 khóa = TẮT tường minh. Migration
  `di_tru_llm_cu` idempotent chạy lúc Owner mở trang, giữ override provider/
  base_url per-khóa; KÉT THẬT ĐANG RỖNG (V3 chưa nhập khóa nào — app chạy
  mock .env) → no-op, loopback writer trước/sau bằng nhau đã kiểm sống.
  Cấp phát lưu `api.cap_phat` trong cau_hinh két (ăn sẵn backup sqlite).
  /general/ai-models + /cai-dat → 303 api-keys, nhãn AI Models sạch khỏi
  mọi template. 4 suite 114(+11)/307+3skip/64/58. NGHIỆM THU CÒN CHỜ OWNER
  (tôi không còn phiên Owner — mật khẩu Bot đã đổi, đúng thiết kế): mở
  /general/api-keys, dán khóa GLM thật vào khối LLM, cấp cho việc writer ở
  tab 2, restart ai-agent → chat chạy thật; Ctrl+U không thấy khóa. VIỆC
  TREO: engine xoay khóa thật ở app tiêu thụ (Đ4); các app nối
  `quota_log.ghi` dần; trạng thái "nghi cạn" (K1) cần quota log có dữ liệu.

## 14. PERMISSIONS THIẾT KẾ LẠI (16/08 — mockup v2 CHỜ OWNER DUYỆT, chưa code)

Owner phê trang Permissions "không bám sát thảo luận": (1) tài khoản đã mang
Bộ phận × Cấp bậc = quyền MẶC ĐỊNH có sẵn — trang không được bắt cấu hình lại;
(2) thứ cần đi sâu là NGOẠI LỆ; (3) từng app có HỆ QUYỀN RIÊNG phải tôn trọng
— mảng từng hỏng nhiều nhất V2. Đã khảo sát trọn hệ quyền V2 (App_Rule.md +
apps_registry + phan_quyen.py + vai nội bộ 6 app + 13 vụ hỏng). Mockup
`permissions.html` viết lại P1–P5:

- **P1** chọn nhân sự + dòng ưu tiên `Ô TICK LẺ > CẤP TRUY CẬP > thường quy`.
- **P2 MẶC ĐỊNH CHỈ ĐỌC**: bảng per app — Vào được? / Vai trong app / Vì sao
  (suy từ bộ phận × level); đổi mặc định = đổi ở Accounts (một nguồn sự thật).
  In rõ luật tuyệt đối: tầng QUẢN TRỊ app (tài khoản · key · cấu hình) độc
  quyền Owner — Manager không bao giờ ngang Owner.
- **P3 CẤP TRUY CẬP (acting)**: truy cập như cấp 1–4, chức danh thật không
  đổi, Owner thật không bao giờ bị hạ (chống tự khóa).
- **P4 NGOẠI LỆ THEO APP (trọng tâm)**: mỗi app một khối <details> (khuôn V2
  Owner đã duyệt) — từng HÀNH ĐỘNG THẬT khai trong hợp đồng, kèm cột "tính
  năng mở khóa" (khuôn nhan_hd/mo_ta_hd V2), Mặc định / Hiệu lực / Đặt
  (kế thừa·cho·chặn), ô lệch viền xanh, badge "N lệ riêng"; nấc **Quản trị**
  mặc định chỉ Owner nhưng tick cấp lẻ được; chỉ lưu ô khác mặc định, tick về
  mặc định tự xóa, hàng Owner khóa ở server.
- **P5 SỔ NGOẠI LỆ TOÀN HỆ**: mọi override đang tồn — người/app/hành động/
  cho-chặn/**lý do bắt buộc**/ngày · người gán/nút gỡ.

**Hợp đồng app mở rộng** (áp khi code, sẵn chỗ cho app V2 port sang):
`hanh_dong: {ma: {nhan, mo_ta, bo_phan, min_level}}` (fail-closed khi không
khai) + `quan_tri` (mặc định chỉ Owner, phát vai cao nhất) + `vai_xoa` (vai
phát khi có toàn-quyền-vận-hành — chống thăng quyền lặng lẽ) + thang vai
CHUẨN HÓA DANH PHÁP một kiểu: `viewer < (vai đặc thù) < leader < manager <
admin` — chữ "owner" chỉ còn MỘT nghĩa là Owner của OUTLIERY (V2 lệch:
radary/seo gọi owner, content/niche/planner gọi admin). Vai dịch từ hành
động kiểu dừng-tại-hit-đầu, tiêm X-Remote-Role MỖI request.

**13 luật ghim từ vụ hỏng V2** (rút gọn — chi tiết ở khảo sát 16/08):
(1) dịch vai "gần đúng" = thăng quyền lặng lẽ — đối chiếu TỪNG NẤC;
(2) OUTLIERY là nguồn sự thật duy nhất — đồng bộ vai MỖI request, mọi nhánh,
sổ riêng app không được thắng (bẫy PlannerY users.json còn nguyên ở V2);
(3) cấm map theo TÊN đăng nhập — nối bằng mã (nguoi_ma/planner_id);
(4) vai không-gán-phạm-vi là ca chưa từng chạy — test user "trắng";
(5) ghép SSO phải rà MỌI chỗ đọc cookie; (6) endpoint nhạy cảm phải SAU cổng
— đo 401/200 thật; (7) NAS chỉ-thêm L1-2; (8) Manager XEM ngang, TOÀN QUYỀN
chỉ bộ phận chủ quản; (9) DEFAULT = vai THẤP NHẤT, fail-closed đo bằng chi
phí token/quota; (10) danh mục cũ grandfather khi đọc, cấm gán mới, phản
biện khi lệnh phá chỗ đứng Owner; (11) test hồi quy dựng từ BẢN GHI CŨ thiếu
trường; (12) self-test ghim LUẬT không ghim hằng số; (13) chẩn quyền phải
soi DB vai THẬT của app, không dừng ở bảng OUTLIERY. Cộng chuẩn nghiệm thu
sống V2: sau restart đo từng app từng vai (manager /keys 403…) + test ghim
"sổ ngoại lệ RỖNG = hành vi thường quy byte-identical".

**Trạng thái: CHỜ OWNER DUYỆT MOCKUP** — duyệt xong mới code (sửa
phan_quyen.json schema + co_quyen + trang /general/permissions + hợp đồng).
- 16/08/2026 — **PERMISSIONS V2 THI CÔNG XONG** (`5e897c1` — Owner xem thiết kế
  mục 14 rồi đòi thấy trong UI). Trang /general/permissions chạy đúng P1-P5;
  luật phan_quyen.json schema hành-động-thật per app (nhan/mo_ta hiện trên
  trang); vai dịch từ hành động, danh pháp chuẩn "admin" (test quét không còn
  vai "owner"); migration iam 004 (acting + ly_do/ai_gan/luc trên override,
  đặt cho/chặn BẮT BUỘC lý do, L5 không hạ được); X-Remote-Actions tiêm mỗi
  request (proxy chặn giả mạo), app gate CHỈ TIN CỜ fail-closed — kiểm sống
  L2-có-cờ 200 / L5-không-cờ 403; test hồi quy sổ-rỗng byte-identical.
  4 suite 120(+6)/308+3skip/64/58. NGHIỆM THU CÒN CHỜ OWNER (không còn phiên
  Bot): vòng hồi quy 3 vai chưa tick gì phải y trước; tick giam_sat cho L2 →
  vào được NGAY lượt sau, gỡ ở P5 → 403; acting L2→L4; soi Audit đủ vết kèm
  lý do. VIỆC TREO: gate sửa/xóa kho ai-agent còn level-based (chuyển nốt
  sang cờ quan_tri); app đã khai hành động muốn hiện vai "manager" cần khai
  toan_quyen (hiện Manager hiển thị viewer trên app như ai-agent — nhãn thôi,
  cờ hành động vẫn đúng).
