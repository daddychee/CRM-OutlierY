# PHÂN CÔNG — trục B của mô hình quyền

> Sổ chủ đề. Owner chốt 24/08/2026: **mọi luật quyền của mọi app đều đi qua khối nền.**
> Nguồn sự thật vẫn là code (`nen/iam/iam.py`, `nen/rules/phan_quyen.json`); sổ này ghi
> *vì sao* và *hợp đồng* để app sau làm theo mà không phải đọc lại toàn bộ lịch sử.

## 1. Vì sao có trục B

Trước 24/08 khối nền chỉ trả lời **một nửa** câu hỏi quyền:

| | Trục A — NĂNG LỰC | Trục B — PHÂN CÔNG |
|---|---|---|
| Trả lời | *được làm LOẠI việc gì* | *trên ĐỐI TƯỢNG nào* |
| Ví dụ | sinh metadata, xóa kênh, xem nhật ký | kênh CF-01, thị trường Spanish, dự án X |
| Ai đặt | Owner (General › Permissions) | **Manager**, ngay trong app |
| Nhịp đổi | vài lần/năm | vài lần/tuần |
| Trước 24/08 | ✅ `phan_quyen.json` + `quyen_override` | ❌ mỗi app tự giữ một mẩu |

Nửa còn lại nằm rải trong từng app: SEO giữ `profile.created_by` + `users.json`, RadarY giữ
bảng `members`, PlannerY giữ phân công trong `plan.json`, Niche giữ `users/invites`. Hệ quả:
cấp quyền ở nền xong **vẫn phải vào từng app gán lại**, và khi hai bên lệch nhau thì hỏng **câm**.

**Sự cố phát hiện ra điều này (24/08).** Manager giao kênh CF-01 cho nhân sự mới → `400
"Không có tài khoản 'nhungpn'"`. Vì `/api/set-channel-owner` kiểm tên bằng `users.json` — sổ
di sản V2 **đông băng từ 19/08** (khi ta cố ý gỡ `users.sync_sso`). Đo thêm bằng dữ liệu thật:

- người **mới** không có trong sổ → bị từ chối, dù họ đăng nhập và dùng app cả ngày;
- người **cũ** đã đổi bộ phận / đã khóa thì **vẫn nhận** được kênh;
- **11/26 kênh** đang đứng tên người không vào được app (`thanhtran` bộ phận khác: 7 kênh;
  `huyenkn` tài khoản khóa: 4 kênh) → không ai dưới Manager sửa được, và không có dòng nào báo;
- cấp ô tick `sua` cho người đó **không cứu được** — vì thứ chặn là trục B, không phải trục A.

## 2. Mô hình chốt

```
làm được  =  CÓ NĂNG LỰC (trục A)   VÀ   ĐỐI TƯỢNG THUỘC PHÂN CÔNG (trục B)
```

- Vai **bỏ qua trục B** là quyết định của **app** (app biết vai mình đang cầm). SEO:
  Manager/Owner ghi mọi kênh; `leader`/`seo` đi qua trục B.
- **Nền trả đúng thứ đã ghi, không diễn giải theo vai.** Gộp hai thứ vào một hàm thì đến lúc
  đổi luật vai là phạm vi đổi theo mà không ai để ý — đúng bẫy đã dính ở
  `seo/roles.overview_channels` hồi V2.
- **Giao việc = Manager trở lên. Leader KHÔNG** (Owner chốt 24/08, thu hồi nới 02/08 của V2):
  giao việc là quyết định quản lý — ai làm gì, ai chịu trách nhiệm — nên nó đi cùng người chịu
  trách nhiệm nhân sự, không đi cùng người phụ trách thị trường.

## 3. Hợp đồng cho app (làm theo là xong)

**Bảng** `phan_cong (app_slug, loai, ma, ten_tai_khoan, ghi_chu, ai_gan, luc)` — migration 007.
Nền **cố ý không biết** "kênh" là gì: chỉ giữ cặp *người ↔ mã đối tượng*. `loai` do app khai,
`ma` là khóa của app, `ma='*'` = toàn bộ loại đó (giao cả cụm thay vì bấm từng cái).

**Luật**: khai một hành động trong `nen/rules/phan_quyen.json`:

```jsonc
"phan_cong": { "nhan": "Giao việc (…)", "mo_ta": "…", "min_level": 4, "bo_phan": [...] }
```

> Tên khóa phải tránh substring `them/tao/sua/xoa/toan_quyen/quan_tri` — `iam.vai_cho_app`
> dò substring, dính là hành động mới tự đẩy vai (bẫy `nas_cap_cao` 30/07).

**Ba đường dây** (khuôn `api-khoa` — app bind loopback nên chỉ app gọi được):

| Đường | Dùng để |
|---|---|
| `GET /api/quyen/tai-khoan/{app}` | ai **vào được** app — app dựng ô chọn, **hết giữ sổ người** |
| `GET /api/quyen/pham-vi/{app}?ten=` | người này được giao đối tượng nào |
| `GET /api/quyen/phan-cong/{app}` | toàn bộ phân công + **mồ côi** (giao cho người nay không vào được) |
| `POST /api/quyen/phan-cong` | **ghi** — app chuyển tiếp NGUYÊN cookie người bấm |

Đường GHI xác thực bằng **cookie**, không bằng loopback: `Cookie` không nằm trong
`proxy._HEADER_CAM` nên app vẫn nhận được cookie OUTLIERY của người dùng. Hệ quả đáng giá —
**app không cầm thứ gì để tự xưng danh**, nên app có lỗi cũng không tự phong quyền cho ai được.

**Phía app**, một file adapter (~110 dòng, xem `apps/seo-optimize/seo/phan_cong_v3.py`):

- cache 15s cho bản tươi; nền chết thì **dùng bản gần nhất tới 5 phút** rồi DỪNG với lý do đọc
  được — không rơi về sổ cũ (chống hai-nguồn-lệch-nhau, cùng luật với khóa API);
- **nhớ cả lần hỏng 5s**: `_me()` được gọi hàng chục lần mỗi lượt render, không nhớ thì nền chết
  = treo trang (đo thật: 3 test timeout);
- fail-closed **nhưng nói ra**: thiếu dữ liệu phân công thì chặn kèm câu *"chưa xác định được…"*,
  tuyệt đối không đổ oan *"bạn không phải chủ kênh"* — câu sai đó đẩy người ta đi xin nhầm thứ.

## 4. Sáu luật sắt

1. App **không giữ sổ người**. Sổ cũ hạ xuống chỉ-đọc rồi xóa.
2. Phân công chỉ trỏ tới tài khoản **vào được app** — **nền kiểm**, không phải app kiểm.
3. Người rời app thì phân công cũ **nổi lên** (`phan_cong_mo_coi`), không tự xóa: xóa hộ là
   quyết định nghiệp vụ của Manager, không phải của cái sổ.
4. Ai được giao việc là **một hành động khai trong luật**, không phải hằng số trong code app.
5. Mọi thay đổi ghi `nhat_ky_quyen`.
6. Nền chết → app **không** rơi về sổ cũ; chỉ dùng bản gần nhất trong hạn, hết hạn thì dừng.

## 5. Trạng thái

| | |
|---|---|
| Nền (bảng + iam + luật + 4 route) | ✅ `a46328a` — 16 test |
| SEO Optimize (adapter + roles + server + board) | ✅ `e9808b9` (repo con) — 10 test, suite 23 pass |
| Gieo dữ liệu ban đầu | ⏳ `tools/scripts/gieo_phan_cong_seo.py` — **đã chạy thử, chờ Owner cho ghi** |
| Restart gateway + app | ⏳ chờ Owner (không `--reload` nên team đang chạy chưa bị ảnh hưởng) |
| RadarY / PlannerY / Niche / Content | ⏳ đợt sau, cùng hợp đồng mục 3 |

**Gieo dữ liệu**: chuyển trạng thái đang chạy (`created_by`) sang sổ mới để **không ai mất
quyền lúc đổi** — 15 kênh gieo được, 11 kênh vào diện *CẦN GIAO LẠI* (người tạo không dùng
được app nữa; máy **không đoán hộ**, Manager quyết). Script mặc định chỉ liệt kê, `--chay`
mới ghi và tự backup `iam.db` trước.

**Thứ tự bắt buộc**: gieo **trước**, restart **sau**. Restart mà chưa gieo thì 26 kênh thành
"chưa giao ai" và 15 người mất quyền sửa cho tới khi gieo xong.

## 6. Việc còn lại của mạch này

- Nhân bản hợp đồng sang RadarY / PlannerY / Niche / Content; dọn sổ riêng từng app.
- Khối **chỉ-đọc** "Phân công đang có" gom cả hệ ở General › Permissions (Owner soi một chỗ:
  ai cầm gì, ai được giao mà không vào được app, đối tượng nào chưa ai làm).
- Cân nhắc `vai_pham_vi` (xem/làm) nếu có app cần hai mức — nay cố ý chưa có, thêm là migration mới.
