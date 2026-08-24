# Tasky — FLOW v1 (bản chờ duyệt, 24/08/2026)

> App độc lập `apps/tasky`, cổng **9117**, vào qua gateway :9000 như 10 app còn lại.
> Vòng duyệt: **FLOW (bản này) → duyệt → UI mockup → duyệt → code.** Chưa code gì.
> Bản đã duyệt là MỐC — sửa thì ra `FLOW-v2.md`, không ghi đè (lệ mockup 18/08).

## 0. Bốn mục tiêu phải trả lời được

| Mã | Mục tiêu Owner nêu | Flow nào trả lời |
|---|---|---|
| a | Nhân sự hoạch định rõ mục tiêu tuần | §2 bước 1-2 (leader giao → nhân sự nhận) |
| b | Chẻ nhỏ mục tiêu thành công việc cụ thể | §2 bước 3 (cây tầng 3 + trọng số) |
| c | Report cho CHÍNH nhân sự: đạt bao nhiêu %, chưa xong việc gì, về đâu | §5 + §6 |
| d | Lấy làm báo cáo với lãnh đạo | §7 |

## 1. Vai và quyền (khai trong `nen/rules/phan_quyen.json`, đi qua `iam.co_quyen`)

| Hành động | Mặc định | Làm được gì |
|---|---|---|
| `vao` | L1 (mọi nhân sự) | Xem + khai tuần CỦA MÌNH |
| `giao_muc_tieu` | L3+ (Leader) | Đặt mục tiêu tuần + phân công người, **trong bộ phận mình** |
| `xac_nhan_ket_qua` | L3+ (Leader) | Xác nhận việc đã xong + đóng tuần cho người trong bộ phận mình |
| `bao_cao_bo_phan` | L4+ (Manager) | Xem báo cáo MỌI bộ phận (lệ 04/08: Manager xem ngang nhau) |
| `mo_lai_tuan` | L5 (Owner) | Mở lại một tuần đã đóng để sửa (ghi vết ai mở, lúc nào) |

Tên hành động đã tránh 5 từ khóa `xoa/toan_quyen/sua/tao/them` để `iam.vai_cho_app()`
không suy nhầm X-Remote-Role sang app khác (bẫy `nas_toan_quyen` 18/08).

## 2. Nhịp một tuần (state machine)

```
        ┌──────────┐  leader đặt mục tiêu + phân công
        │  NHÁP    │  nhân sự chẻ việc, sửa/xóa tự do
        └────┬─────┘
             │ nhân sự bấm "Chốt kế hoạch"  (trần: hết Thứ Ba, sau đó hệ TỰ chốt)
             ▼            → ĐÓNG BĂNG MẪU SỐ (điểm kế hoạch lưu thành số, không tính lại)
        ┌──────────┐
        │ĐANG CHẠY │  tick trạng thái việc; việc thêm sau mốc này = PHÁT SINH (tính riêng)
        └────┬─────┘
             │ nhân sự bấm "Gửi kết quả tuần"
             ▼
        ┌──────────────┐
        │CHỜ XÁC NHẬN  │  leader soát: việc nào thật xong, việc chưa xong đi đâu
        └────┬─────────┘
             │ leader bấm "Xác nhận & đóng tuần"
             ▼
        ┌──────────┐   → số vào báo cáo lãnh đạo
        │ ĐÃ ĐÓNG  │   → việc chọn "dời" tự sinh sang file tuần sau (so_lan_doi +1)
        └──────────┘   → khóa sửa; chỉ Owner mở lại được
```

**Nhịp thực tế trong tuần**

| Khi nào | Ai | Làm gì |
|---|---|---|
| T2 sáng | Leader | Đặt 2-5 mục tiêu tuần của bộ phận, mỗi mục tiêu giao cho 1+ người kèm *kết quả kỳ vọng* |
| T2–T3 | Nhân sự | Chẻ mục tiêu thành việc cụ thể, gắn trọng số → **Chốt kế hoạch** |
| T2–CN | Nhân sự | Tick `đang làm` / `xong`; việc mới phát sinh vẫn khai được (đánh dấu phát sinh) |
| CN hoặc T2 sau | Nhân sự | **Gửi kết quả tuần** |
| T2 sau | Leader | Xác nhận từng việc + chọn hướng cho việc chưa xong → **Đóng tuần** |

## 3. Cây dữ liệu (map tree 3 tầng)

```
Mục tiêu tuần  (bộ phận · leader đặt · có kết quả kỳ vọng)
└── Giao cho người X  (kết quả X phải ra)
    ├── Việc 1   trọng số nhỏ 1đ / vừa 2đ / lớn 3đ
    ├── Việc 2   ...
    └── Việc 3   (phát sinh — thêm sau khi chốt)
```

Lưu tại `data/tasky/db/tuan/YYYY-Www.json` (mỗi tuần MỘT file, ghi nguyên tử
tmp + `os.replace`, khai `du_lieu` trong `nen/rules/apps.json` để backup 19:00 nhận).
Vết thao tác (chốt / gửi / xác nhận / đóng / hủy / dời / mở lại) ghi
`data/tasky/db/nhat-ky.jsonl` **chỉ-thêm** — sửa ý vẫn còn dấu ai làm gì lúc nào.

Trường mỗi việc: `id · muc_tieu_id · nguoi · tieu_de · trong_so · trang_thai ·
phat_sinh · goc_id · so_lan_doi · ly_do_huy · xac_nhan{boi,luc} · luc_tao · luc_xong`.

Trạng thái việc: `chua_lam → dang_lam → xong_tu_khai → xong_xac_nhan`
(nhánh cuối tuần: `doi_tuan_sau` · `huy` kèm lý do).

## 4. Luật tính % hiệu suất (Owner chốt: theo trọng số, 2 nấc xác nhận)

```
% kế hoạch = (điểm việc XONG-ĐÃ-XÁC-NHẬN) ÷ (điểm kế hoạch ĐÓNG BĂNG lúc chốt)
```

- **Mẫu số đóng băng thành SỐ lúc chốt**, không tính lại từ cây hiện tại → sửa trọng
  số hay xóa việc giữa tuần không làm số đẹp lên.
- Việc **phát sinh** không vào mẫu số; báo cáo hiện tách: `78% kế hoạch · +4đ phát sinh`.
- Hai số song song: **% tự khai** (nhân sự tick) và **% đã xác nhận** (leader).
  Báo cáo lãnh đạo dùng số **đã xác nhận**; báo cáo cá nhân thấy cả hai.
- **Van chống bịa** (luật xuyên hệ): chưa chốt kế hoạch → % hiện `—` kèm lý do
  *"chưa chốt kế hoạch tuần"*, TUYỆT ĐỐI không hiện 0% hay số tạm giả.
  Tuần chưa đóng → bảng lãnh đạo ghi rõ *"chưa đóng — số tự khai"*.

## 5. Việc chưa xong đi đâu (mục c)

Lúc đóng tuần, **mỗi việc chưa xong buộc chọn một hướng**:

| Hướng | Hệ làm gì |
|---|---|
| Dời sang tuần sau | Sinh việc mới ở file tuần sau, giữ `goc_id`, `so_lan_doi +1`, vẫn treo dưới mục tiêu cũ |
| Hủy | Buộc ghi lý do; việc giữ nguyên trong sổ (không xóa) để còn vết |
| Đổi người | Dời sang tuần sau nhưng gán người khác (leader quyết) |

`so_lan_doi >= 2` → tự lên cờ **VIỆC KẸT** ở cả báo cáo cá nhân và bảng lãnh đạo.
Mục tiêu còn việc dời → tự mang sang tuần sau ở trạng thái *tiếp tục*, không phải khai lại.

## 6. Báo cáo cá nhân (mục c) — nhân sự tự thấy

Một trang, đọc trong 10 giây:
- Thẻ lớn: `% hiệu suất tuần qua` + so sánh tuần trước (↑/↓ bao nhiêu điểm %)
- `Điểm kế hoạch: X · xong-xác-nhận: Y · phát sinh xong: Z`
- Danh sách **việc chưa giải quyết** kèm hướng đã chọn (dời / hủy / đổi người)
- Khối **việc kẹt** (dời ≥2 lần) — đọc thẳng câu "việc này về đâu"
- Nhận xét của leader (nếu có) khi đóng tuần

## 7. Báo cáo lãnh đạo (mục d)

Bảng `bộ phận × người`: `% xác nhận · điểm KH · phát sinh · việc kẹt · trạng thái tuần`,
kèm khối **mục tiêu tuần không đạt** của từng bộ phận. Xuất được bản in/HTML một trang.
Manager thấy mọi bộ phận (chỉ xem); Leader thấy bộ phận mình; Owner thấy tất.

## 8. Ca biên đã tính trước

| Ca | Xử lý |
|---|---|
| Nhân sự nghỉ cả tuần | Tự đánh dấu *tuần nghỉ* → % không tính, báo cáo ghi "nghỉ", không phải 0% |
| Không chốt kế hoạch tới hết T3 | Hệ **tự chốt** bản đang có, ghi cờ `tu_dong` (thấy rõ trong báo cáo) |
| Leader vừa giao vừa tự làm | Tự tick được, nhưng việc của chính leader do **cấp trên** xác nhận; nếu không có cấp trên trong app → ghi nhãn *"tự xác nhận"* |
| Tuần đã đóng cần sửa | Chỉ Owner mở lại, có vết trong nhật ký |
| Người thuộc bộ phận khác leader | Leader chỉ giao/xác nhận trong bộ phận mình (gate ở server, không chỉ ẩn nút) |

## 9. Ranh giới — Tasky KHÔNG làm

- Không tự suy "đã xong" từ dữ liệu app khác. Số máy đo (PlannerY / Content / DA)
  nằm ở **KPI của app to-chuc**; vòng 2 sẽ cho hai số **đứng cạnh nhau**, không thay nhau.
- Không quản dự án dài hạn, không Gantt, không comment thread — review video đã có
  Video Review, lịch sản xuất đã có PlannerY.
- Không nhập tay số liệu hiệu suất kênh.

## 10. Ba điểm còn mở — cần Owner chốt khi duyệt flow

1. **Trần chốt kế hoạch**: đề xuất hết Thứ Ba 23:59, sau đó hệ tự chốt. Đổi thành T2 hay T4?
2. **Leader tự xác nhận việc của chính mình**: cho phép kèm nhãn *"tự xác nhận"*, hay bắt buộc Manager cấp trên?
3. **Việc lẻ không thuộc mục tiêu nào**: cho khai (mục "Việc khác", vẫn tính điểm) hay bắt mọi việc phải treo dưới một mục tiêu?
