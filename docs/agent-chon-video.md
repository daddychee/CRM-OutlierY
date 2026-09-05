# Spec — AI Agent truy cứu thông tin phục vụ CHỌN VIDEO ĐỂ LÀM

> Soạn 28/08/2026. Phạm vi: RadarY (pool đối thủ) + Niche Research (báo cáo 8 phase).
> Trạng thái: SPEC, chưa code. Mọi số minh hoạ lấy từ dữ liệu thật ngày 28/08/2026
> (ws18 Life In Spain, ws20 Life In US).

## 0. Vấn đề spec này giải

Câu hỏi vận hành: *"hôm nay nếu cần lên lịch sản xuất Life In thì nên chọn tập nào?"*

Phiên thử 28/08 cho thấy trả lời câu này bằng **tín hiệu pool đơn thuần là sai hệ
thống**, không phải sai lệch nhỏ:

| Cụm | Trong pool | Ngoài pool (thị trường) | Kết |
|---|---|---|---|
| `pesos de sueldo` | nổ 3/4 video | view giữa **1.083**, kém `mínimo` 34 lần | dương tính giả |
| `isolated country shocking` | nổ 2/4 | **9 kết quả** toàn YouTube, 0 video/90 ngày | dương tính giả |
| `uzbekistan` | không có video nào | Trends 8 tuần cuối `74 → 3` | âm tính giả rồi bẫy ngược |

Ba trong bốn đề xuất từ tầng pool sai hướng khi đối chiếu tầng cầu.

## 1. Hai loại cầu — nguyên tắc trung tâm

Spec này đứng trên một phân biệt do Owner chốt 28/08:

- **CẦU ĐÃ CHỨNG MINH** = video đã nổ. Chắc chắn có khán giả, nhưng *đã có người
  phục vụ*. Vào sau = tranh slot với bản đã xếp hạng.
- **CẦU MỚI** = Trends đang lên, thảo luận mới, chưa/ít video phục vụ. Rủi ro cao
  hơn, nhưng còn chỗ.

**Luật số lớn (bắt buộc):** một cụm KHÔNG được xếp trên chỉ vì con số tuyệt đối lớn
hơn. Số lớn thường là *di sản của người đi đầu*, không phải cơ hội hôm nay.

Bằng chứng: `en cabo verde` có max 6.032.367 view — cao nhất pool Spain — nhưng 8
kênh đã làm, người sau giảm dần 273k → 252k → 56k → 12k → **1.931** (video mới nhất
13 ngày). Sóng đã tàn; con số 6M gây hiểu nhầm.

Vì vậy mọi phép đo phải là **đạo hàm theo thời gian**, không phải mức tuyệt đối.

## 2. Ba tầng tín hiệu — agent BẮT BUỘC khai đã dùng tầng nào

### Tầng A — CUNG (0 quota, đọc SQLite)

Trả lời: *đối thủ đang làm gì, cái gì đang chạy trong pool.*

- `mapping.tu_khoa_nong(kho)` — cụm bị video nổ thiên vị. Tham số thật:
  `NGAY_NONG=60`, `PHAN_VI_NO=90` (nổ = top 10% view/ngày CỦA CHÍNH phiên),
  `TOI_THIEU_MOI_NONG=4`, `TOI_THIEU_NO=2`, cần ≥30 video mới.
- Phân bố view theo tuổi trong cụm (phát hiện sóng tàn — ca Cabo Verde).
- Phân tán kênh (`kenh_day`). Cụm nổ do MỘT kênh tự nhân bản ≠ cụm nổ do nhiều kênh
  độc lập. Ca thật: `scientists can't explain` nổ 3/3 nhưng **cả 3 đều của Uncensored
  World**; `indonesia stunning women` nổ 3/3 bởi **3 kênh khác nhau**.

### Tầng B — CẦU ĐÃ CHỨNG MINH (quota, có cache)

Trả lời: *ngoài 65 kênh theo dõi, chủ đề này chạy thế nào.*

- `tra_cuu_log.youtube`: `so_ket_qua`, `view_giua`, `view_moi_ngay_tong`,
  `phan_bo_tuoi` (0-7 / 8-28 / 29-90).
- Chi phí thật đo được: ~403-405 units/cụm (2 lời gọi `search.list` × 100 + phụ).

### Tầng C — CẦU MỚI (quota, có cache)

Trả lời: *nhu cầu đang hình thành ở đâu.*

- `trends_cache`: `diem` (52-54 tuần), `xu_huong`, `rising`, `top`.
- Google News / Wikipedia (0 key, ~1-2s).
- Reddit: **đã thử, 403 từ IP này** — không dùng, đừng đề xuất lại.

**LUẬT CỨNG 1 — cấm kết luận từ một tầng.** Tầng A chỉ được sinh *ứng viên*, không
được sinh *khuyến nghị sản xuất*. Trả lời chỉ có tầng A phải tự dán nhãn: "mới đo
cung, chưa kiểm cầu — chưa đủ cơ sở lên lịch".

## 3. Bốn van chống bịa cho tín hiệu Trends

Trends là nguồn dễ đọc sai nhất. Bốn van rút từ ca thật 28/08:

### Van 1 — ĐỘ TRỄ

Điểm cuối của `uzbekistan` là **09/08**, đọc ngày 28/08 = **trễ 19 ngày**. Agent PHẢI
đọc `diem[-1].ngay` và khai độ trễ. Trễ > 14 ngày → hạ xuống "tham khảo", không được
làm căn cứ chính.

### Van 2 — ĐUÔI, KHÔNG PHẢI TRUNG BÌNH QUÝ

So trung bình quý đầu với quý cuối cho `uzbekistan` ra "×7 tăng". Nhìn 8 điểm cuối:
`74, 34, 9, 7, 6, 4, 4, 3` — **đang rơi tự do sau khi đã nổ**.

Agent PHẢI đọc 6-8 điểm cuối và xét hướng của ĐUÔI. Đây chính là cái bẫy "lệch theo
số lớn" mà spec này tồn tại để chặn.

### Van 3 — KIỂM `rising` XEM TĂNG VÌ CÁI GÌ

Trends chỉ nói cụm chữ đó được tìm nhiều hơn — không nói vì lý do gì.

- `ecuador` +252% → `rising` = "ecuador vs curaçao" 70.650, "mexico vs ecuador odds"
  → **bóng đá**, không phải du lịch/đời sống.
- `nomad women` +247% → `rising` = "goal zero nomad 10 solar panel" 40.850 → **pin
  mặt trời**.

Agent PHẢI đọc `rising`/`top` và loại nếu ngữ cảnh lệch khỏi ngách. Không đọc được
ngữ cảnh → ghi "tăng nhưng chưa rõ vì sao", KHÔNG dùng làm căn cứ.

### Van 4 — GIÁ TRỊ TUYỆT ĐỐI, KHÔNG CHỈ HƯỚNG

Trends chuẩn hoá 0-100 theo chính cụm đó, nên "tăng gấp 7" của cụm nền 3 điểm khác
hẳn "tăng 20%" của cụm nền 70 điểm. So thật: `uzbekistan` tb 9,9 · `stunning women`
tb 23,1 · `indonesia` tb 51,8 · `kyrgyzstan` tb 58,2 · `vietnam` tb 73,9.

Agent PHẢI báo cả mức nền lẫn hướng.

## 3b. CẤU TRÚC 4 LỚP (chốt 28/08 — thay 3 tầng song song của bản đầu)

Ba tầng song song đòi agent tự cân → tự đặt ngưỡng tuỳ hứng (PB-2). Thay bằng
**chuỗi lọc tuần tự**, mỗi lớp trả lời một câu và có quyền loại:

```
L1 SÀN NGÁCH  → "công thức nào đang ăn?"      (loại cụm nổ bởi MỘT kênh)
L2 ĐỘ TƯƠI    → "sóng đang lên hay đã tàn?"   (đạo hàm, không mức tuyệt đối)
L3 CHỖ TRỐNG  → "còn chỗ không? mình làm chưa?"
L4 KIỂM CHÉO  → "có tín hiệu nào PHẢN ĐỐI?"   (chỉ được phủ định)
```

Vì sao tuần tự: loại sớm thì rẻ (L1-L3 đều 0 quota, tới L4 chỉ còn 2-3 ứng viên
thay vì tra 10-14 cụm ~2.025 units) · mỗi lớp có tiêu chí riêng nên không cần cân
điểm · thứ tự phản ánh độ tin cậy (L1 đo trên pool thật của ngách, L4 là nguồn
ngoài dễ nhiễu).

### L4 CHỈ ĐƯỢC PHỦ ĐỊNH (Owner chốt 28/08)

Trends/News **không bao giờ là lý do để CHỌN** một tập, chỉ để LOẠI. Bất đối xứng
này có cơ sở: một cụm tăng có thể vì trăm lý do không liên quan (`ecuador` +252%
= bóng đá; `nomad women` +247% = pin mặt trời; `uzbekistan` +649% nhưng đuôi
74→3), còn một cụm rơi thì thường là rơi thật.

### Cầu mới đọc từ CHÍNH POOL, không từ autocomplete

Đã kiểm 28/08: `discovery.mo_rong("life in")` trả 137 cụm, toàn **nước giàu**
(Japan, America, England, Finland, London, Dubai). Pool đang thắng bằng **nước
nghèo/lạ**. Đo trên 252 video ws20 trong 60 ngày:

| Nhóm | n | Trung vị | Đỉnh |
|---|---|---|---|
| Nước giàu | 121 | **20**/ngày | 2.875 |
| Nước nghèo/lạ | 131 | **84**/ngày | 33.572 |

Nghèo/lạ thắng 4,2 lần ở trung vị, 12 lần ở đỉnh. **Nếu agent nghe autocomplete
để chọn tập, nó sẽ chọn sai** — autocomplete đo *người tìm chủ động*, ngách này
sống bằng *người bị đề xuất động vào*. `life in tuvalu` không ai gõ nhưng video
Tuvalu đạt 293k.

Điều này **bác một phần PB-1**: autocomplete không phải lời giải cho ngách
browse-driven; nó chỉ dùng được cho ngách search-driven. Cầu mới ở đây đọc bằng
đạo hàm bậc hai trên chính pool (xem L2).

### L2 — LUẬT ĐÃ SỬA sau khi chạy thật (bản v1 SAI, đừng dùng lại)

Bản v1 dùng **hằng số 15 ngày** chia mới/cũ và không kiểm phân tán kênh trong
nhóm. Chạy thật ws20 cho **5/6 cụm "đang lên" là GIẢ**. Ba luật bắt buộc:

1. **Mốc tuổi = TRUNG VỊ CỦA CHÍNH PHIÊN**, không hằng số. Đo ws20: trung vị
   28,3 ngày — hằng số 15 rơi đúng p25, nên "nhóm mới" chỉ là 1/4 trẻ nhất.
   (Cùng bài học `burstiness_cv` 21/08: ngưỡng tự đặt phải đo trên đối chứng.)
2. **Mỗi kênh MỘT SUẤT** (video tốt nhất) khi lấy trung vị — một kênh spam
   không được lái tỷ lệ.
3. **`cu = 0` là MẪU NHỎ, không phải tăng vô hạn.** Cần ≥3 kênh độc lập mỗi
   nhóm mới kết luận.

Kết quả đảo ngược sau sửa (ws20):

| Cụm | v1 | v2 |
|---|---|---|
| `islands on the` | 12,5× lên | **0,37 TÀN** |
| `ring on fire` | 47,6× lên | mẫu nhỏ (cu=0) |
| `nomads islands on` | 21,4× lên | mẫu nhỏ (cu=0) |
| `ancient customs` | 3,9× lên | mẫu nhỏ |
| `indonesia stunning women` | 2,2× lên | mẫu nhỏ (cu=0) |
| `world strangest` | 6,3× lên | **5,4× lên** (4 kênh) |
| `bhutan` | ổn định | 4,3× lên → L4 phủ định (3 kq) |

Kiểm chéo thô `islands on the`: nhóm mới 12 video nhưng **9/12 dưới 200/d**, chỉ
2 video đỉnh kéo lên; nhóm cũ đều đặn 700-830/d → cụm thật sự tàn.

**BÀI HỌC GHIM: thước đo sai nguy hiểm hơn thiếu thước đo.** v1 cho 6 ứng viên
tự tin, v2 cho 1. Không nghi con số `1.432` trùng nhau thì đã đề xuất 3 cụm tàn.

### L3 — kênh mình NẰM TRONG pool (Owner chốt 28/08)

Kênh của mình tính vào pool như một nguồn volume thị trường bình thường. L3
**không loại theo "của ai"**, chỉ dùng để cảnh báo trùng bài đã làm.

## 4. Ma trận quyết định (thay cho điểm tổng)

**KHÔNG có điểm tổng, KHÔNG xếp hạng một chiều** — theo lệ A3 đã chốt ở Content
Ultimate (score tổng ẩn vẫn bị cấm). Thay bằng ô hai trục:

|  | Cầu mới ĐANG LÊN | Cầu mới PHẲNG/GIẢM |
|---|---|---|
| **Cung pool THƯA** | ⭐ Cơ hội — ưu tiên | Ngách chết hoặc quá sớm |
| **Cung pool DÀY** | Cạnh tranh nhưng còn ăn | ⛔ Sóng tàn (ca Cabo Verde) |

Agent xuất mỗi ứng viên kèm: ô nào, số của cả 3 tầng, và **"kết luận này sai trong
trường hợp nào"** (lệ đã có trong `ASK_SYSTEM` của RadarY).

## 5. Bộ tool

Đặt trong app **ai-agent** (có sẵn RAG + phản biện + van chống bịa + lịch sử). Gọi ra
qua API loopback theo khuôn `radary_bridge.py` — forward claims SSO của **chính người
hỏi**, không dùng identity hệ thống (bẫy SEO Optimize 04/08).

| # | Tool | Tầng | Quota | Ghi chú |
|---|---|---|---|---|
| 1 | `resolve_pool(ten)` | — | 0 | "life in" → 4 ws. **Bắt buộc chạy đầu** |
| 2 | `kiem_do_tuoi(ws)` | — | 0 | loại pool chết/rỗng |
| 3 | `tu_khoa_nong(ws)` | A | 0 | engine 22/08 |
| 4 | `soi_cum(ws, cum)` | A | 0 | phân bố tuổi + phân tán kênh |
| 5 | `doc_cache_tra_cuu(ws, cum)` | B | 0 | **đọc trước khi tra mới** |
| 6 | `doc_cache_trends(cum, geo)` | C | 0 | nt |
| 7 | `tra_cuu_ngoai(ws, cum)` | B | ~405 | **cần user duyệt** |
| 8 | `lay_trends(cum, geo)` | C | SERP | **cần user duyệt** |
| 9 | `bao_cao_ngach(project, muc)` | C | 0 | Niche `demand`, `crackability` |
| 10 | `kenh_cua_minh(ngach)` | — | 0 | **CHƯA CÓ — xem §7** |

**LUẬT CỨNG 2 — cache-first.** Tool 5/6 luôn chạy trước 7/8. Phiên 28/08 lấy được
toàn bộ tín hiệu cầu với **0 quota mới** nhờ cache có sẵn.

**LUẬT CỨNG 3 — không tự tiêu quota.** Tool 7/8 chỉ chạy khi user duyệt. Agent đề
nghị: "cụm X chưa có trong cache, tra tốn ~405 units, có tra không?" Lý do: RadarY có
trần 30 lượt LLM/người/ngày và ngân sách 5 cụm/ngày/pool.

## 6. Luồng chuẩn

```
1. resolve_pool          → nhiều pool thì HỎI LẠI, không tự chọn
2. kiem_do_tuoi          → loại pool chết (ws1 event cuối 20/08) / rỗng (ws19)
3. tu_khoa_nong          → 10-14 cụm ứng viên               [tầng A]
4. soi_cum từng cụm      → loại sóng tàn + cụm một-kênh     [tầng A]
5. doc_cache_* mọi cụm   → tín hiệu cầu miễn phí            [tầng B+C]
6. → thiếu cache ở cụm đầu bảng: XIN DUYỆT tra thêm
7. 4 van Trends          → loại tăng-giả (bóng đá, pin, đuôi rơi)
8. Ma trận 2 trục        → ứng viên + "sai khi nào"
```

## 7. Giới hạn đã biết

1. **`kenh_cua_minh` chưa có.** Cột `favorite` trong `channels` trống → agent không
   biết bạn đã làm tập nào, có thể đề xuất trùng bài cũ. **Chặn thật: cần Owner đánh
   dấu kênh mình trước khi agent dùng được cho sản xuất.**
2. **Trends geo ES thiếu.** Cache ES chỉ có `casa`, `áfrica` → nhánh Spain chưa kết
   luận được, phải tra thêm (tốn quota).
3. **Reddit 403** từ IP này.
4. **Trends trễ tới 19 ngày** → không bắt được sóng trong tuần.
5. **`view_giua` bị một video lạc bóp méo** khi `so_ket_qua` nhỏ: `women who own` có
   view giữa 2.699.558 nhưng **chỉ 1 kết quả**. Agent phải bỏ qua cụm có
   `so_ket_qua < 20`.

## 8. Nghiệm thu — PHÁT BIỂU THEO LUẬT (sửa PB-3)

Bản đầu liệt kê theo TÊN CỤM → agent có thể học thuộc "loại uzbekistan" mà vẫn vô
dụng ngày mai (đúng bệnh `designcheck` 03/08 ghim hằng số hiện hành). Mỗi ca dưới
đây phát biểu theo LUẬT, kèm ví dụ chỉ để minh hoạ.

| # | Luật phải thi hành | Ví dụ 28/08 |
|---|---|---|
| N1 | Tên ngách khớp nhiều pool → HỎI LẠI, không tự chọn | "life in" → 4 ws |
| N2 | Pool có `event` cuối > 3 ngày hoặc 0 kênh → loại khỏi phân tích | ws1, ws19 |
| N3 | Cụm mà mọi video nổ thuộc CÙNG một kênh → không được xếp ứng viên | `scientists can't explain` |
| N4 | L2 phải chia mới/cũ bằng TRUNG VỊ TUỔI PHIÊN, không hằng số | ws20 = 28,3d |
| N5 | Mỗi kênh một suất khi lấy trung vị L2 | — |
| N6 | Nhóm mới hoặc cũ < 3 kênh độc lập → "mẫu nhỏ", KHÔNG kết luận | `ring on fire` cu=0 |
| N7 | Cụm có trung vị mới/cũ < 0,6 → TÀN, loại dù video đỉnh lớn | `islands on the` 0,37 |
| N8 | Cụm `so_ket_qua < 20` ở tầng B → phủ định, dù view giữa cao | `bhutan` 3 kq |
| N9 | Trends: đọc 6-8 điểm ĐUÔI, không trung bình quý | `uzbekistan` 74→3 |
| N10 | Trends: `rising` lệch ngữ cảnh ngách → không dùng làm căn cứ | ecuador = bóng đá |
| N11 | Trends: `rising` rỗng → "không kiểm được ngữ cảnh", không dùng một mình | `uzbekistan` |
| N12 | Trends `diem[-1]` trễ > 14 ngày → hạ xuống tham khảo | trễ 19 ngày |
| N13 | Tầng C chỉ được PHỦ ĐỊNH, không được dùng để chọn | — |
| N14 | Trả lời chỉ có tầng A phải tự dán nhãn "chưa đủ cơ sở lên lịch" | — |
| N15 | Mọi khuyến nghị kèm số cả 3 tầng + "sai trong trường hợp nào" | — |
| N16 | Không tiêu quota khi chưa xin duyệt | — |
| N17 | Cụm KHÔNG chứa thực thể/danh từ riêng của ngách → loại (cụm hư từ) | `they are`, `will do to` |
| N18 | Tách SHORTS khỏi long-form TRƯỚC mọi phép đo; ngưỡng theo pool | Space US 1.043 Shorts |

### N17 — cụm hư từ (phát hiện khi đối chứng Space US 28/08)

`they are` đạt tỷ lệ L2 **354×** và qua sạch mọi van số học, nhưng gom: "LLMs Are
Great. Until They Disengage You" (AI) + "How do submarines know where they are?"
(tàu ngầm, Veritasium 2M) + "Men Have 10% Larger Brains" (sinh học). Không phải
một công thức — chỉ là hư từ tiếng Anh.

Ở Life In lỗi này **vô hình** vì mọi cụm đều mang danh từ riêng (`indonesia`,
`bhutan`). Space US có nhiều kênh phổ thông nên hư từ nổi lên.

Lời giải có sẵn trong `mapping.py`, chưa nối vào: `la_doi_tuong()`, `loai_cum()`,
`hook_hop_le()`, `canonical_thuc_the()`. Agent phải gọi các hàm này thay vì tự
phán đoán bằng LLM.

### N18 — Shorts làm lệch mọi phép đo view/ngày

Đo 28/08 (60 ngày, trung vị view/ngày):

| Pool | Shorts ≤3 phút | Long-form |
|---|---|---|
| **Space US (ws22)** | n=1.043 · **451**/d | n=3.401 · 124/d |
| Life In US (ws20) | n=34 · 6/d | n=1.125 · 53/d |

Space US có 1.043 Shorts, trung vị **cao gấp 3,6 lần** long-form → mọi cụm chứa
Shorts đều bị kéo lệch lên. Ca thật: `moon earth` ra 4,65× nhưng video đỉnh đều
là Shorts của Science Of Interest (132.128/d, 109.527/d) trong khi long-form cùng
cụm chỉ 81-1.284/d.

Shorts là **định dạng sản xuất khác hẳn** — không dùng để lên lịch video dài.
Agent phải tách hai rổ và khai đang đo rổ nào.

**Đây là lỗi không thể phát hiện nếu chỉ chạy một pool** — đúng giá trị của đối
chứng mà PB-3 đòi hỏi.

**Đối chứng bắt buộc:** mọi thay đổi luật phải chạy trên **≥2 pool khác ngách**
(đã làm: Life In US ws20 + Space US ws22 — xem §10) để phân biệt luật đúng với
luật khớp riêng một tập dữ liệu.

## 9. Chốt PB-7 — đọc qua API, KHÔNG import chéo

Bản đầu mâu thuẫn: §5 nói khuôn `radary_bridge` (API loopback) nhưng tool 3/4 mô
tả gọi thẳng `mapping.*`. **Chốt: đi qua API**, theo lệ V3.

Lý do không import trực tiếp:
- Lệ V3 "cầu nối API, không import chéo" (đã áp cho `radary_bridge`, `niche_bridge`).
- `mapping.tai_kho` nạp toàn bộ pool (ws20 = 3.735 video) trong tiến trình agent —
  bài học 31/07 "database is locked": đọc nặng khi scan đang ghi tranh khóa SQLite.
- RadarY tự kiểm quyền theo vai SSO của chính nó; import thẳng thì bỏ qua tầng đó.

**Hệ quả:** RadarY cần bổ sung route trả sẵn kết quả L1/L2 (hiện
`/discovery/tu-khoa-nong` có L1 nhưng chưa có đạo hàm L2). Đây là việc code
RadarY, không phải việc của agent.

---

# PHẢN BIỆN SPEC NÀY (tự phản biện, 28/08)

Theo lệ vòng phân tích – phản biện của dự án. Dưới đây là các lỗ hổng của chính spec
trên. Xếp theo mức nghiêm trọng.

## PB-1 (NẶNG NHẤT) — Spec vẫn KHÔNG bắt được "cầu mới" đúng nghĩa

Đây là mâu thuẫn nội tại: yêu cầu của Owner là "dự đoán mang tính cập nhật", nhưng
mọi nguồn tầng C trong spec đều **trễ**:

- Trends: điểm cuối theo tuần, đo được **trễ 19 ngày**.
- `tra_cuu_ngoai`: đếm video **đã đăng** — tức là cung, không phải cầu.
- Wikipedia: pageview trễ 1-2 ngày, chỉ có cho thực thể có bài.

Nghĩa là spec đặt tên tầng C là "cầu mới" nhưng thực chất đo **cầu của 2-3 tuần
trước**. Với chu kỳ sản xuất video (viết + voice + dựng), tổng độ trễ có thể lên
4-5 tuần từ lúc tín hiệu hình thành tới lúc video lên sóng.

Spec **chưa giải** vấn đề này, chỉ ghi vào §7 như một giới hạn. Đó là né, không phải
giải.

**Đã kiểm sau khi viết phản biện:** `radary/discovery.py` tồn tại **chính xác vì lý
do này**. Docstring của nó ghi: *"RadarY giữ về CUNG (31.917 video) nhưng chưa bao
giờ hỏi về CẦU"*. Đây là nguồn tươi nhất hệ đang có — autocomplete phản ánh người ta
gõ gì **hôm nay**, không trễ tuần như Trends.

Nên tầng C của spec bị soạn thiếu. Bổ sung bắt buộc:

- `discovery.mo_rong(seed, BoDem(tran=9))` — 0 quota, ~9s, đã được `/tra-cuu/ngoai`
  gọi sẵn (biến `bien_the` trong `api.py`). Trả `do_phu` (cụm xuất hiện ở bao nhiêu
  biến thể seed) + `hang_tot_nhat`.
- `discovery.goi_y_bing` — nguồn thứ hai, ra cụm YouTube không gợi ý.

**Van chống bịa kèm theo (chép từ docstring module, KHÔNG được phá):** autocomplete
chỉ nói *"CÓ NGƯỜI GÕ cụm này"*, KHÔNG nói bao nhiêu người. Mọi "search volume" suy
ra từ đây đều là bịa. Agent chỉ được dùng `do_phu` và `hang`, tuyệt đối không quy đổi
ra lượng tìm kiếm.

**Ràng buộc vận hành:** autocomplete dùng CHUNG IP với harvest RadarY và
youtube-transcript-api của Content Ultimate; app từng dính "Sign in to confirm you're
not a bot". Trần cứng ≤1 lời gọi/giây, 60 lời gọi/phiên. Agent gọi tự do sẽ **làm
hỏng cả harvest lẫn Content Ultimate** — phải chia sẻ `BoDem`, không tự đặt trần
riêng.

**Kết luận PB-1: spec bản đầu chưa đạt yêu cầu "cập nhật" của Owner.** Đã có lời giải
trong hệ, phải đưa vào tầng C trước khi code. Thứ tự tầng C sau sửa: autocomplete
(tươi nhất, 0 quota) → News → Trends (trễ, làm nền) → Wikipedia.

## PB-2 — Ma trận 2 trục lảng tránh chỗ khó

§4 nói "không điểm tổng" và viện lệ A3. Nhưng A3 cấm điểm tổng vì nó *giấu cách tính*
— không cấm việc phải quyết định. Ma trận 2 ô đẩy toàn bộ việc phân định về cho
người đọc, mà người đọc chính là người đã hỏi "chọn tập nào".

Nguy hiểm hơn: ranh giới "THƯA/DÀY" và "LÊN/PHẲNG" **không được định nghĩa số**. Agent
sẽ tự đặt ngưỡng mỗi lần một khác → cùng dữ liệu, hai lần hỏi ra hai ô khác nhau.
Đây là lỗi lặp lại bài học `burstiness_cv` (21/08): ngưỡng tự đặt không đo trên nhóm
đối chứng thì vô giá trị.

**Cần:** hoặc định nghĩa ngưỡng bằng phân vị của chính phiên (như `PHAN_VI_NO=90` đã
làm), hoặc thừa nhận thẳng rằng agent chỉ xếp ứng viên, người quyết.

## PB-3 — Bộ nghiệm thu §8 là bộ test QUÁ KHỚP

Cả 10 mục đều rút từ **đúng một phiên dữ liệu 28/08**. Agent qua hết 10 mục vẫn có
thể vô dụng ngày mai, vì nó có thể chỉ học thuộc "loại uzbekistan, loại cabo verde".

Đây đúng là bệnh mà `designcheck` đã dính (03/08): self-test ghim hằng số hiện hành
thì tự vỡ hoặc tự đúng một cách vô nghĩa.

**Cần:** ca kiểm phải phát biểu theo LUẬT ("cụm có đuôi Trends giảm > 50% trong 8
điểm cuối phải bị loại"), không theo TÊN CỤM. Và cần ít nhất một phiên dữ liệu thứ
hai (pool khác, hoặc ws20 tháng trước) làm đối chứng.

## PB-4 — Chưa chứng minh 3 tầng tốt hơn 1 tầng

Spec khẳng định tầng A một mình gây 3/4 sai. Nhưng "sai" ở đây do **chính tôi phán
định**, dựa trên tầng B — chưa có kết quả thực tế nào xác nhận.

Có thể `pesos de sueldo` view giữa thấp nhưng vẫn là lựa chọn đúng cho một kênh nhỏ
mới (dễ chen hơn `world strangest` với 82 video/tuần). Spec ngầm giả định "view giữa
cao = tốt hơn" mà chưa xét **sức kênh của chính mình** — đúng thứ mà §7 thừa nhận
là chưa có (`kenh_cua_minh`).

**Nghĩa là:** spec loại `pesos de sueldo` có thể là một dương-tính-giả kiểu mới, chỉ
đổi từ thiên vị-pool sang thiên vị-thị-trường. Cách kiểm duy nhất: theo dõi tiếp
5-10 video được đề xuất theo spec này và đo kết quả thật.

## PB-5 — Van 3 (`rising`) không chạy được ở diện rộng

Van 3 đòi agent đọc `rising` để loại tăng-giả. Nhưng:
- `uzbekistan` có `rising: []` — **rỗng**. Van 3 không phán định được gì.
- Với cụm hẹp (`life in tajikistan`), Trends thường trả rỗng (chính comment trong
  `api.py` đã ghi nhận điều này).

Nên van 3 chỉ chạy được ở cụm phổ biến — đúng nhóm cụm mà ta ít cần nó nhất. Ở cụm
ngách (nơi cơ hội thật nằm), van này im lặng. Spec chưa nói agent phải làm gì khi
`rising` rỗng: coi là sạch, hay coi là chưa kiểm được?

**Đề nghị:** `rising` rỗng → tín hiệu Trends của cụm đó xuống hạng "không kiểm được
ngữ cảnh", không được dùng một mình.

## PB-6 — Chi phí thật của một câu hỏi chưa được tính

§5 ghi ~405 units/cụm. Nhưng luồng §6 có 10-14 ứng viên. Nếu chỉ 5 cụm thiếu cache:
**~2.025 units** cho một câu hỏi, cộng lượt LLM của agent.

Spec có luật xin duyệt (LUẬT CỨNG 3) nhưng **không có trần**. Một người hỏi 3 câu
trong ngày có thể đốt hết ngân sách quét của cả pool — mà quét pool mới là thứ nuôi
tầng A. Tức là agent có thể **tự cắn vào nguồn dữ liệu của chính nó**.

**Cần:** trần quota/ngày cho agent, tách khỏi ngân sách quét nền.

## PB-7 — Rủi ro vận hành chưa nêu

- `mapping.tu_khoa_nong` chạy trong tiến trình agent sẽ nạp kho pool (`tai_kho`) —
  ws20 có 3.735 video. Chưa đo thời gian/bộ nhớ. Bài học 31/07 (RadarY "database is
  locked") cảnh báo: đọc nặng trong khi scan đang ghi có thể tranh khóa SQLite.
- Spec chưa nói agent đọc DB **trực tiếp** hay **qua API loopback**. §5 nói theo khuôn
  `radary_bridge` (API), nhưng tool 3/4 mô tả gọi hàm `mapping.*` (import trực tiếp).
  **Mâu thuẫn nội tại** — vi phạm lệ V3 "cầu nối API, không import chéo".

## Tổng kết phản biện

Spec **dùng được làm nền bàn tiếp, chưa dùng được để code**. Ba việc phải xử lý trước:

1. **PB-1** — bổ sung nguồn cầu-mới thật sự tươi (autocomplete là ứng viên tốt nhất),
   nếu không thì spec không đạt yêu cầu gốc của Owner.
2. **PB-7** — chốt agent đọc qua API hay import trực tiếp; hiện đang mâu thuẫn.
3. **PB-3** — viết lại nghiệm thu theo luật, thêm phiên dữ liệu đối chứng thứ hai.

PB-4 chỉ giải được bằng theo dõi kết quả thật sau vài tuần — cần chấp nhận đây là
giả thuyết đang chờ kiểm, không phải chân lý.
