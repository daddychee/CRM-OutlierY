# DISCOVERY + MAPPING — sổ chủ đề (soạn 21/08/2026)

> Sổ mạch "cầu × cung": RadarY thu tín hiệu **CẦU** (người ta đang tìm gì) và ghép với
> kho **CUNG** sẵn có (ai đang làm gì) để chỉ ra khoảng trống thật.
> Nguồn gốc: user gửi `CONTENT-ULTIMATE-V3.md` (Discovery Module + S0 Opportunity Score)
> → phản biện + đo thật → **giữ Discovery, bỏ Opportunity Score**, và **đổi nhà: đặt ở
> RadarY chứ không phải Content Ultimate**.

---

## 0. Vì sao đặt ở RadarY (đổi so với đề xuất ban đầu)

Ban đầu định đặt Discovery trong Content Ultimate. Ba số đo thật ngày 21/08 làm đổi ý:

| Dữ kiện | Số |
|---|---|
| Video có title + ngày đăng trong `data/radary/radary.db` | **31.917** |
| Chuỗi view theo thời gian (`ticks`) | **989.775** |
| Kênh · workspace (ngách/pool) | 803 · 21 |
| Quét toàn bộ 31.917 title để đối chiếu 1 từ khóa | **0,21 giây · 0 quota** |

- Vế **cung** đã nằm ở RadarY. Đẩy vài chục từ khóa sang đó rẻ hơn kéo kho video đi.
- RadarY **có scheduler**; Content Ultimate không (chỉ chạy khi user bấm) → chỉ RadarY
  tích lũy được **lịch sử cầu theo thời gian** (velocity thật, không phải ảnh chụp).
- Người cần đọc bản đồ thị trường là **Kinh doanh**, không riêng người viết kịch bản.
- Content Ultimate vẫn dùng được qua `GET /api/mapping` — đúng chiều phụ thuộc: tool
  viết ĐỌC từ đài quan sát, không phải ngược lại.

---

## 1. Ba van chống bịa (quan trọng nhất của module này)

1. **KHÔNG có "search volume".** Autocomplete chỉ nói *có người gõ cụm này*, không nói
   bao nhiêu người. Google không công bố số. Mọi con số volume suy ra từ autocomplete
   đều là bịa → trục cầu chỉ dùng **tín hiệu đếm được**: cụm xuất hiện ở bao nhiêu biến
   thể seed (`do_phu`), hạng trung bình trong danh sách gợi ý (`hang_tb`), số bài HN.
2. **KHÔNG điểm tổng, KHÔNG ngưỡng cứng.** Chia 4 ô bằng **trung vị của chính phiên
   quét** (cầu/cung cao-thấp so với các từ khóa cùng đợt), không phải hằng số kiểu
   "≥ 7.0 là Green". Ngưỡng cứng không có căn cứ đã bị bác ở proposal V3 bản 1.
3. **Cung thấp có HAI nghĩa trái ngược.** `tuvalu` 14 video · view trung vị 781 (ít người
   làm vì ít người xem) vs `why do people…` 4 video · 2 kênh (chưa ai làm). Chỉ khi ghép
   với cầu mới phân biệt được — đó là lý do tồn tại của Mapping.

---

## 2. Nguồn tín hiệu CẦU — đã kiểm thật 21/08

| Nguồn | Kiểm từ máy công ty | Dùng thế nào |
|---|---|---|
| **YouTube autocomplete** `suggestqueries.google.com/complete/search?client=firefox&ds=yt&q=` | **200 OK**, không key. Seed rộng `"life in"` → 10 gợi ý; seed hẹp `"life in tuvalu"` → 1 | Nguồn CHÍNH. Bắt buộc seed **rộng** + biến thể a–z |
| **HN Algolia** `hn.algolia.com/api/v1/search` | **200 OK**, không key | Phụ — lệch tệp (dân công nghệ), chỉ tham khảo |
| **trendspyg** | có thật, **1.6.0 phát hành 19/08/2026**; `pytrends` bản cuối 04/2023 (chết) | Tuỳ chọn — thư viện mới 2 ngày tuổi, để sau MVP |
| **Reddit `.json`** không auth | **403 Blocked** | **BỎ khỏi MVP** |

Nhiễu đã thấy khi đo: seed `"life in"` trả về `life incremental roblox`, `life in prison
roblox` → phải lọc theo ngách/thị trường của workspace.

---

## 3. Dữ liệu — 2 bảng mới, không đụng bảng cũ

```sql
CREATE TABLE keywords (
  id INTEGER PRIMARY KEY,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
  cum TEXT NOT NULL,                  -- cụm từ khoá đã chuẩn hoá (lowercase, gọn khoảng trắng)
  seed TEXT DEFAULT '',               -- seed sinh ra nó
  nguon TEXT DEFAULT 'autocomplete',  -- autocomplete | hn | trends | tay
  tao_ts REAL NOT NULL,
  bo_qua INTEGER NOT NULL DEFAULT 0,  -- user gạt khỏi bản đồ (nhiễu) — gỡ mềm
  UNIQUE (workspace_id, cum));

CREATE TABLE keyword_stats (          -- append-only theo ngày, khuôn pool_stats/channel_stats
  keyword_id INTEGER NOT NULL REFERENCES keywords(id),
  ngay TEXT NOT NULL,                 -- YYYY-MM-DD giờ VN
  do_phu INTEGER NOT NULL DEFAULT 0,  -- xuất hiện ở bao nhiêu biến thể seed
  hang_tb REAL NOT NULL DEFAULT 0,    -- hạng trung bình trong danh sách gợi ý (1 = đầu)
  hn_bai INTEGER NOT NULL DEFAULT 0,
  hn_diem INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (keyword_id, ngay));
```

Giữ vĩnh viễn (như `pool_stats`) — chuỗi theo ngày chính là thứ Content Ultimate không
làm được, và là cơ sở để về sau nói "cụm này đang lên hay đang xuống".

---

## 4. Đo CUNG — đọc DB, 0 quota

Cho mỗi cụm, quét `videos` (31.917 dòng, 0,21s):

| Số | Cách tính | Ghi chú |
|---|---|---|
| `so_video` · `so_kenh` | đếm title khớp | khớp theo **ranh giới từ**, không phải `LIKE %x%` — bài học SEO 18/08: "Life" nuốt "Life In" |
| `view_trung_vi` | max(views) mỗi video từ `ticks`, lấy trung vị | trung vị bền outlier hơn trung bình |
| `moi_nhat` | `max(pub_ts)` | cụm chết từ 2 năm trước ≠ cụm đang nóng |
| `vph_trung_vi` | `last_vph` trung vị | velocity thật |

---

## 5. Ghép thành bản đồ

- Trục **cầu** = `do_phu` (chính) + hạng trung bình (phụ), so với **trung vị phiên quét**.
- Trục **cung** = `so_video`, so với **trung vị phiên quét**.
- 4 ô:

| Ô | Nghĩa | Ví dụ đo thật 21/08 |
|---|---|---|
| cầu cao · cung thấp | **KHOẢNG TRỐNG** — ưu tiên | `why do people…` 4 video · 2 kênh |
| cầu cao · cung cao | **ĐỎ LỬA** — phải hơn hẳn mới thắng | |
| cầu thấp · cung cao | **BÃO HOÀ** — tránh | `life in` 2.300 video · 118 kênh · view trung vị 2.867 |
| cầu thấp · cung thấp | **HOANG** — thường có lý do | `tuvalu` 14 video · view trung vị 781 |

Bấm một ô → danh sách video thật đang chiếm chỗ (kênh, view, ngày đăng, link) —
**trình bằng chứng, người chọn** (luật A3), không "khuyên nên làm gì".

---

## 6. Quyền

Theo `apps_registry` hiện hành của RadarY: **mọi bộ phận L1 xem** · **L3+ (leader)** chạy
quét và gạt nhiễu · quản trị vẫn chỉ Owner. Không đẻ luật quyền mới.

---

## 7. Nhịp thi công — mỗi bước một commit xanh

| # | Việc | Cổng nghiệm thu |
|---|---|---|
| **M1** | `radary/discovery.py` — expand seed → cụm (autocomplete + HN), thuần hàm | test với HTTP giả; chạy thật 1 seed ra ≥ 10 cụm |
| **M2** | 2 bảng + `db.keywords_*` | tạo/đọc/ghi idempotent, không đụng bảng cũ |
| **M3** | `radary/mapping.py` — đo cung + ghép 4 ô | chạy trên DB thật: `life in` ra bão hoà, `why do people` ra khoảng trống |
| **M4** | API `POST /api/workspaces/{ws}/discovery/scan` · `GET /api/workspaces/{ws}/mapping` | quyền đúng 3 vai; không có ws → 404 |
| **M5** | Tab **Mapping** trong `web/app.js` | 4 ô bấm ra video thật |
| **M6** | Job theo lịch (scheduler sẵn có) | rate-limit; log lời gọi |

**Rate-limit bắt buộc từ M1:** autocomplete dùng CHUNG IP với harvest của RadarY và với
`youtube-transcript-api` của Content Ultimate. App đã từng dính "Sign in to confirm you're
not a bot" trên VPS. Mặc định ≤ 1 lời gọi/giây, tổng ≤ 60/phiên quét.

---

## 8. Không làm (YAGNI)

Reddit (403) · trendspyg trong MVP · embedding cluster (dùng token overlap trước) ·
điểm tổng/ngưỡng cứng · tự động đưa cụm vào outline (user tick).
