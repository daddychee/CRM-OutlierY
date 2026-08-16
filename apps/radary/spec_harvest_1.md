# SPEC — Module HARVEST (Radary)

*Trạng thái: ĐÓNG BĂNG v1 (user duyệt 23/07/2026 sau 2 vòng phản biện — quyết định ghi ở §10). Đổi hành vi → sửa spec trước.*
*Nguồn logic: `radary_methodology.md`. Ngày: 2026-07-23.*

---

## 1. Harvest là gì (một câu)

Một module **độc lập, read-only, advisory** trong Radary: nhận đầu vào là một list kênh (từ vài kênh đến vài trăm), **phân rã** nó thành các nhóm ngách mạch lạc và **mở rộng** (snowball) thành pool đầy đủ, rồi **xuất REPORT** để user tự tay thêm/bớt/xóa vào pool thật. Harvest KHÔNG bao giờ ghi vào DB pool sống.

## 2. Nguyên tắc bất biến (kế thừa CLAUDE.md)

- **NP3 — Read-only tuyệt đối với dữ liệu sống.** Harvest chỉ ĐỌC. Không tạo workspace, không thêm/xóa kênh, không đụng tick/event/packaging. Mọi thay đổi pool do USER thực hiện qua luồng Radary đã có, sau khi đọc report.
- **NP5 — Máy đề xuất, người quyết.** Harvest trưng kết quả + lý do ("giống vì X" / "có thể sai vì Y"). Không tự động hóa quyết định "kênh này vào pool".
- **NP2 — Đơn giản.** Một engine, hai đầu vào. Không tách module con.
- **Quota là công dân hạng nhất.** Job nền, resumable, tôn trọng `RADAR_BUDGET`, ước tính quota TRƯỚC khi chạy, `PAUSE — chạy lại để tiếp` khi cạn.
- **BYO key theo niche/org** như phần còn lại của Radary. Xoay key khi 403 → dự phòng (kế thừa cơ chế `scan.API`).

## 3. Đầu vào & tự nhận diện chế độ

User dán một list (link kênh `@handle` hoặc `/channel/UC...`, hoặc link video → lấy kênh). Engine tự đếm số kênh hợp lệ và chọn chế độ (user ghi đè được):

- **≤ 5 kênh → chế độ SEED.** Bỏ qua phân rã, snowball thẳng từ toàn bộ list.
- **> 5 kênh → chế độ POOL.** Phân rã trước → user chọn nhóm → snowball nhóm được chọn.

Lý do ngưỡng: dưới 5 kênh không đủ dữ liệu để phân cụm đáng tin (bài học methodology §2).

## 4. Pipeline nghiệp vụ

```
INPUT list kênh
   │
   ├─[chế độ SEED, ≤5 kênh]──────────────┐
   │                                      │
   └─[chế độ POOL, >5 kênh]               │
        │                                 │
     [GĐ1: PHÂN RÃ] ──> cây workspace     │
        │  (report trung gian)            │
     user CHỌN nhóm để mở rộng            │
        │                                 │
        └──────────────> [GĐ2: SNOWBALL] <┘
                              │
                        [GĐ3: REPORT cuối]
                              │
                    user tự thêm/bớt/xóa vào pool thật
```

### GĐ1 — PHÂN RÃ (chỉ chế độ POOL)

Tách list hỗn tạp thành cây, **2 tầng cứng** (methodology §2):
- **Tầng 1 — Ngôn ngữ** (function-word detection: EN/ES/PT/...). Ranh giới tuyệt đối.
- **Tầng 2 — Định dạng độ dài**: long-form documentary / sleep-ambient (med≥40ph) / short-form-clip / mixed.

Không dùng comment ở giai đoạn này (rẻ — chỉ vân tay + độ dài).

**Output GĐ1 = report cây phân rã**: mỗi nhóm lá kèm mô tả tự sinh (ngôn ngữ, dải độ dài, số kênh, dải subs, top từ khóa chủ đề, kênh đại diện) + cờ cảnh báo (nhóm <3 kênh: "quá nhỏ, cân nhắc gộp").

**User cắt cây**: chọn nhóm nào là workspace đáng theo, nhóm nào bỏ. Máy trưng, người cắt (NP5).

### GĐ2 — SNOWBALL (khi user yêu cầu, cho nhóm đã chọn)

Cho mỗi nhóm user chọn, mở rộng đến hội tụ (methodology §3):
1. Dựng **centroid ĐÓNG BĂNG** từ kênh của nhóm đó (chống trôi ngữ nghĩa).
2. Mỗi vòng: rút n-gram từ title THẬT của pool nhóm → search sâu (`type=channel` + `type=video` long) → loại kênh đã gặp → **lọc Tầng 1 bằng centroid gốc** → **chấm Tầng 2 (khán giả, LUÔN BẬT)**.
3. Dừng khi vòng đẻ ≤1 kênh mới đạt chuẩn.

**Cửa sinh ứng viên**: chỉ Cửa 3 (search sâu title thật) là động cơ. Cửa 1 (featured) thử vì rẻ nhưng biết trước thường rỗng. Cửa 2/4 (author) KHÔNG khám phá — chỉ dùng chấm điểm (methodology §3).

### GĐ3 — REPORT cuối

Report chính user nhận, cho mỗi nhóm đã snowball:
- Pool đề xuất xếp hạng (luật kép ≥2 trục), mỗi kênh: tên + link + channelId + 4 trục điểm (voc/long/core/broad) + provenance (vòng nào tìm ra) + "giống vì X" + "có thể sai vì Y" (TC7) + subs.
- Bằng chứng hội tụ (đà kênh mới qua các vòng).
- Mô tả workspace tự sinh (để user dán khi tự tạo workspace).
- Quota đã tiêu.

## 5. Chấm điểm (từ methodology §1, §6)

- **Tầng 1 (nội dung — quyết định IN/OUT):** `voc≥15` VÀ `long_ratio≥0.6` VÀ `subs≥ngưỡng` (mặc định 5K, user chỉnh). Centroid đóng băng.
- **Tầng 2 (khán giả — LUÔN BẬT, chỉ xếp hạng, KHÔNG loại):** co-occurrence author chuẩn hoá theo tỷ lệ, mẫu lớn (trộn relevance+time, nhiều trang), báo cỡ mẫu N kèm điểm. Kênh mẫu mỏng (<30 author) gắn cờ ⚠, không bị phạt.
- **Luật kép:** vào hạng A khi mạnh ≥2 trục.
- **Lưu ý ngách tương tác thấp:** Tầng 2 có thể im lặng (core=0 hàng loạt) — báo rõ, KHÔNG coi là kênh xấu (methodology §5.2).

## 6. Ràng buộc vận hành (job nền)

- Chạy nền như `niche_report`, checkpoint sau mỗi kênh đo / mỗi vòng.
- **Ước tính quota TRƯỚC**: hiện lên "list này ~X kênh, snowball ~Y vòng, ước ~Z units — tiếp tục?". Vì comment LUÔN BẬT nên cảnh báo rõ chi phí cao (methodology §8: comment sâu ~gấp 10× vân tay).
- Tôn trọng `RADAR_BUDGET`, resumable, `PAUSE — chạy lại để tiếp`.
- Xoay key 403 → dự phòng. Mọi trường response YouTube dùng `.get()` phòng thủ (bài học sự cố `duration` thiếu ở livestream).

## 7. Phân quyền (mô hình 3 bậc)

- ~~Chạy Harvest + xem report: `editor`+. `viewer` chỉ xem report đã sinh.~~ **User siết 23/07/2026:** vai `editor` đổi tên thành `leader`; toàn bộ Harvest (kể cả XEM) = `leader` trở lên — viewer 403.
- Harvest KHÔNG có nút ghi pool → không cần quyền ghi. User áp dụng report qua luồng pool sẵn có (chịu phân quyền pool ở đó).

## 8. Ranh giới rõ ràng — Harvest KHÔNG làm gì

- KHÔNG tạo workspace tự động.
- KHÔNG thêm/xóa kênh vào pool sống.
- KHÔNG tự quyết "gỡ kênh".
- KHÔNG sinh khuyến nghị "nên đánh chủ đề này" (NP5).
- KHÔNG đo thể loại (documentary/faceless/narrator) — user đã bỏ; API mù trục này.

## 9. Câu hỏi mở cho vòng phản biện

1. Ngưỡng SEED/POOL = 5 kênh — hợp lý chưa?
2. Report lưu bao lâu? (draft có TTL hay giữ vĩnh viễn như report ngách?)
3. Có cho user "gộp 2 nhóm phân rã thành 1 pool để snowball chung" không, hay mỗi nhóm riêng?
4. Snowball nhiều nhóm cùng lúc (song song) hay tuần tự (tiết kiệm quota, dễ theo dõi)?

## 10. VÒNG PHẢN BIỆN 1 — quyết định của user (23/07/2026, qua mockup UI + thảo luận)

Trả lời 4 câu §9: (1) **giữ ngưỡng 5** · (2) **không TTL — job hiện hành duy nhất, báo cáo full user tự tải về là bản lưu** · (3) **CÓ gộp** — checkbox "gộp các nhóm đã chọn thành 1 pool" trước khi snowball · (4) **tuần tự** (hàng đợi; VPS 1GB + dễ theo dõi).

Các quyết định thêm từ thảo luận:

- **Kho key Harvest TÁCH RIÊNG hoàn toàn** khỏi key quét radar: mục "Key Harvest" trong tab quản trị, ô dán NHIỀU key một lần (mỗi dòng 1 key, bỏ trùng 409, có nút kiểm). Harvest chỉ tiêu key kho này — không bao giờ đụng key niche production (1 phiên harvest ~31K units = 10 ngày quota radar). Key cộng quota phải từ dự án Google Cloud khác nhau (luật cũ).
- **BỎ cổng duyệt quota trước khi chạy** (sửa §6 — user đổi vì đã có kho key lớn riêng): bấm Chạy là chạy nền ngay. Chỉ còn 2 cảnh báo: (a) kho key Harvest trống → chặn + chỉ đường sang quản trị; (b) toàn bộ key 403 giữa chừng → job PAUSE tại checkpoint + banner "hết quota — thêm key hoặc chờ 14:00". Ước tính quota vẫn tính ngầm để hiện tiến độ ("đã tiêu X/~Y"), không còn là cổng chặn.
- **"Đo khán giả" (comment):** mặc định BẬT, ô tắt được từng job ngay màn nhập (dung hòa spec cũ "LUÔN BẬT" với methodology §5.2 — trục có điều kiện, đắt ~10×).
- **1 job hiện hành duy nhất — bỏ màn danh sách job**: tab Harvest rảnh → màn nhập; đang chạy/xong → tiến độ/cây/report. Chạy job mới khi job cũ chưa xong → hỏi xác nhận.
- **UI chỉ hiện ý chính; báo cáo FULL tải file** (md, mọi kênh + điểm số + N mẫu + bằng chứng hội tụ + đối chứng âm) bằng nút riêng trong tab Harvest — bản tải về là bản lưu của user.
- **Chặn vòng lặp:** ngoài luật hội tụ ≤1 kênh mới/vòng, thêm trần cứng 6 vòng + trần quota/job (tham số config).
- **Phạm vi v1 = Phân rã + Snowball.** Audit pool đang chạy (công cụ 3 methodology) để v2 — tái dùng phần chấm điểm.
- **Đổi tên tab toàn app (không riêng Harvest):** Board · Alert · Report (Báo cáo) · Tuning (Cài đặt) · Setting (Quản trị) · New Niche (+Niche mới) · Harvest — chỉ đổi nhãn hiển thị, khóa nội bộ URL hash giữ nguyên để link cũ không gãy. (User đề xuất "Boarding"/"Scan"; chốt lại Board/New Niche sau góp ý tránh hiểu lệch.)
- **Bảo mật trước khi chạy:** 6-7 key trong `radary_methodology.md` §9 đã lộ qua chat — user cần tái tạo/xóa trong Google Cloud Console trước khi đưa vào kho key Harvest.

**Vòng phản biện 2 (23/07/2026, trên mockup v2):**
- **Dải tiến trình theo giai đoạn** thay chip trạng thái: Đọc kênh → Phân loại → Chọn workspace → Snowball (vòng x/≤6) → Report; chạy đến đâu XANH đến đó, SEED mờ 2 bước giữa. Kèm quota đã tiêu (ước ngầm).
- **Bước 2 đổi tên "Phân loại Workspace"** + tính năng mới: bấm vào từng workspace mở danh sách kênh, **✕ loại kênh không phù hợp khỏi bản nháp** TRƯỚC khi snowball — centroid dựng từ phần còn lại (curation làm sạch seed, vẫn read-only với pool sống).
- UI bỏ chữ "Màn", chỉ đánh số bước 1·2·3; bỏ chip ghi chú "không hỏi duyệt quota" (hành vi giữ nguyên, chỉ bỏ dòng chữ).

## Phụ lục — Case vàng để nghiệm thu (từ phiên nghiên cứu)
- SEED mode: 3 kênh "Life in Country" → hội tụ 17→8→4→0, pool ~18 kênh ≥5K.
- POOL mode: 86 kênh "Space" → phân rã EN73/ES8/PT5, EN tách 4 nhóm định dạng.
- Đối chứng ÂM: kênh triệu-sub trùng từ khóa nhưng long-form thấp (NASA/Yes Theory) phải rơi khỏi pool documentary.
