# Supervisor — Tầng cố vấn đa chiều cho AI Agent nội bộ

> Tài liệu này ghi **phương pháp** (chưa phải spec code từng dòng) cho bước tiến hóa của
> agent: từ **"tra cứu theo tài liệu công ty"** sang **"cố vấn đa chiều"** — khi cần ra
> quyết định, ngoài kiến thức công ty còn đối chiếu **góc nhìn của chuyên gia (MrA, MrsB…)**
> và **nguồn ngoài (ABC)** để có quyết định nhiều chiều, thay vì nhất-nhất theo một tài liệu.
> Chốt qua phiên bàn ngày 24/07/2026. Phiên sau code trong VSCode phải bám tài liệu này.
>
> **Đã chốt 24/07/2026:** (1) gom **3 tầng** Công ty / Chuyên gia / Ngoài; (2) một trường
> **Tên nguồn** — tài liệu công ty = `Official`, nhập tay + gợi ý tên đã dùng về sau;
> (3) nhập liệu + quyền **như cũ** (Manager+ nạp, RBAC giữ nguyên); (4) chế độ đa chiều là
> **nút riêng** trong trang Hỏi–đáp; (5) **prefer**: tài liệu công ty **luôn dựng & render
> trước** (tìm tách theo tầng); (6) công ty trống mà tầng khác có → vẫn hiện tầng khác kèm
> ghi chú "Công ty chưa có tài liệu" (đa chiều đúng lúc + tín hiệu kho-thiếu).
>
> **ĐỔI 07/08/2026 (user chốt):** gộp **Chuyên gia** và **Ngoài** thành **MỘT tầng** — không
> còn phân biệt "chuyên gia" khác "nguồn ngoài" (thực tế luồng nạp EXTRACT §2b/2c cũng chưa
> bao giờ dùng nhãn `ngoai`, mọi thứ đều nạp `chuyen_gia`, nên phân biệt cũ không phản ánh gì
> thật). Còn lại **2 tầng máy**: `noi_bo` / `ngoai`. Bù lại, khi trả lời đa chiều KHÔNG còn
> hiện nhãn tầng chung ("Chuyên gia"/"Nguồn ngoài") mà tách **MỘT KHỐI RIÊNG cho MỖI TÊN
> NGUỒN thật** (vd "🌐 Andrew X", "🌐 Youtube Official") — chi tiết mục 3.2. Dữ liệu cũ đã gộp
> bằng `scripts/gop_chuyen_gia_ngoai.py` (Qdrant trước, catalog sau, có kiểm chứng).
>
> **Nguyên tắc tối cao:** *"Không có góc nhìn nào nếu không có NGUỒN THẬT đứng sau."*
> Mọi quan điểm phải là một **nguồn đã nạp**, **gắn nhãn xuất xứ**, **tách tầng rõ**. Góc
> nhìn không truy được về một nguồn có địa chỉ = model đang bịa = đúng thứ cả hệ thống này
> sinh ra để chống. Đa chiều mà mờ nguồn thì **tệ hơn** nhất-nhất-theo-tài-liệu.

---

## 0. Vì sao làm — và ranh giới không được vượt

Sức mạnh lớn nhất của agent hiện tại: **nó không bao giờ chém — mọi câu truy được về tài
liệu công ty, có trích nguồn** (van chống bịa). Tầng Supervisor **mở rộng** giá trị đó
(nhiều góc nhìn → quyết định tốt hơn) nhưng **không được phá** nó.

Ba thứ dễ mất nếu làm ẩu — phải giữ bằng mọi giá:

1. **Truy nguồn (provenance).** Mỗi câu vẫn phải chỉ ra được nó đến từ đâu.
2. **Không trộn tầng lặng lẽ.** SOP công ty và ý kiến ngoài mà hiển thị lẫn nhau → người
   đọc tưởng ý kiến ngoài là chính sách công ty. Phải tách khối, gắn nhãn.
3. **Mặc định không đổi.** Luồng hỏi–đáp hiện tại (chỉ nội bộ) phải chạy **y hệt như cũ**
   khi chưa bật chế độ đa chiều — như "loại kênh rỗng = an toàn tuyệt đối" ở module chẩn đoán.

---

## 1. Mô hình dữ liệu — TẦNG NGUỒN

Thêm **một** trục metadata mới, trực giao với quyền truy cập đang có.

### 1.1 Trường `tang_nguon`

| Giá trị | Nghĩa | Độ tin (để hiển thị) |
|---|---|---|
| `noi_bo` | Nội bộ chính thức — SOP, quy trình công ty (mặc định) | Cao nhất — "chuẩn công ty" |
| `ngoai` | MỌI thứ không phải công ty — người cụ thể (chuyên gia) hay nguồn/kênh (nghiên cứu, blog, kênh YouTube…) đều vào đây, KHÔNG phân biệt nữa (đổi 07/08) | Tham khảo — ghi rõ **TÊN CHÍNH XÁC** qua `nguon_ten` |

- **Mặc định `noi_bo`.** Mọi tài liệu cũ + mọi lần nhập không chọn gì → `noi_bo`. Kho hiện
  tại **không đổi một byte** hành vi. (Đây là van an toàn: tầng nguồn RỖNG/không dùng =
  byte-identical như trước, giống pattern loại kênh.)
- **Trực giao với RBAC.** `tang_nguon` chỉ là **nhãn phân tầng**, KHÔNG phải quyền. Quyền
  xem vẫn do `department` / `access_level` / `min_level` / `effective_status` quyết định như
  cũ — tái dùng `client._duoc_xem`, **không viết luật quyền mới**. Một tài liệu tầng `ngoai`
  vẫn có thể là "Công khai nội bộ" hoặc "Giới hạn theo bộ phận".
- **Không phân biệt chuyên gia/nguồn ngoài (07/08).** `nguon_ten` mới là thứ mang thông tin —
  "Andrew X" (một người) và "Youtube Official" (một kênh/tổ chức) đều là giá trị hợp lệ như
  nhau của `nguon_ten` trong CÙNG tầng `ngoai`; hệ thống không cần biết đó là người hay tổ
  chức, chỉ cần TÊN ĐÚNG để trích dẫn.

### 1.2 Trường `nguon_ten` (đi kèm)

- Với `ngoai`: **tên chính xác của người hoặc nguồn** — có thể là một người ("Andrew X"), một
  kênh/tổ chức ("Youtube Official"), hay một ấn phẩm ("Blog ABC", "Nghiên cứu XYZ 2024") — hệ
  thống không phân biệt loại, chỉ cần đúng tên vì đây là thứ hiện làm nhãn khối khi trả lời đa
  chiều (mục 3.2). Với `noi_bo`: mặc định **`Official`** (nhãn tài liệu công ty).
- Đây là chuỗi để **hiển thị + trích dẫn**; gom danh sách tên đã có kiểu tag gợi ý (tái
  dùng cơ chế `tu_khoa` sẵn có — không bắt gõ lại, không bắt buộc).

### 1.3 Nơi lưu (nhất quán 2 kho — bài học quản-lý-tài-liệu-UI)

- **Catalog:** thêm 2 cột `Tầng nguồn`, `Tên nguồn` vào `CATALOG_HEADER` (nâng cấp catalog
  cũ idempotent như `_nang_cap_catalog`, dòng cũ → `noi_bo` + rỗng).
- **Qdrant payload:** thêm `tang_nguon` (+ `nguon_ten`) vào payload; **payload index** cho
  `tang_nguon` để lọc/gom server-side. `tang_nguon` là **trường quyền-mở-rộng**: khi đổi
  qua UI phải đồng bộ Qdrant TRƯỚC, catalog SAU, có kiểm chứng — dùng đúng đường
  `cap_nhat_payload_doc_code` đã có.
- **doc_code vẫn BẤT BIẾN.**

---

## 2. Nạp liệu — kho chuyên gia / nguồn ngoài

Không có cơ chế nạp mới. **Tái dùng nguyên luồng nhập liệu hiện tại**, chỉ thêm 2 ô:

- Dropdown **Tầng nguồn** (3 giá trị cố định — validation 2 lớp như các dropdown khác:
  trình duyệt khóa + backend chặn 422 giá trị ngoài danh sách).
- Ô **Tên nguồn** (bắt buộc khi tầng ≠ `noi_bo`; ẩn/tùy chọn khi `noi_bo`).

Cắt đoạn / embedding / RBAC / catalog: **giữ nguyên**. Một tài liệu chuyên gia đi qua đúng
pipeline như một SOP — chỉ khác cái nhãn tầng.

> **Phân biệt với Q&A bổ sung (đã có):** Q&A bổ sung *gắn vào một tài liệu gốc cụ thể* (mã
> `-QA`, kế thừa quyền gốc). Tầng nguồn là *phân loại xuất xứ của cả một tài liệu độc lập*.
> Hai cơ chế khác nhau, không đụng nhau.

---

## 2b. Nạp nguồn DÀI có kiểm soát — module EXTRACT (YouTube & nguồn ngoài)

Nguồn ngoài/chuyên gia thường **rất dài** (transcript YouTube, bài viết, report). **Không nạp
thô cả khối** — chèn một khâu CURATION có LLM hỗ trợ, đúng pattern "Duyệt" của Q&A (LLM đề
xuất → người chốt → mới vào kho).

**NGUYÊN TẮC SỐNG CÒN — EXTRACT = TRÍCH NGUYÊN VĂN, KHÔNG VIẾT LẠI:** LLM chỉ được ĐÁNH DẤU
đoạn đáng giá (trích Y NGUYÊN chữ + một dòng "vì sao"), **KHÔNG tóm tắt/diễn giải**. Vì nếu
lưu bản LLM viết lại thì cái vào kho là "lời của LLM", không phải lời nguồn → **mất xuất xứ,
thủng van chống bịa**. VAN TẠI KHÂU EXTRACT: mỗi đoạn LLM đề xuất phải là **SUBSTRING THẬT**
của văn bản gốc (kiểm verbatim, chuẩn hóa khoảng trắng) — đoạn nào LLM bịa/paraphrase → **BỎ**.

**Flow (giống 3 bước Q&A):**
1. **LẤY** nội dung dài. YouTube: `yt-dlp` liệt kê video của kênh (ID/tiêu đề/ngày, KHÔNG tải
   video) → `youtube-transcript-api` lấy transcript (lời nói = nội dung).
2. **LLM ĐỀ XUẤT** (`de_xuat_trich`): trả về các đoạn NGUYÊN VĂN đáng giá + mốc thời gian +
   một dòng "vì sao đáng giá". Đoạn không verbatim → loại (van chống bịa tại nguồn).
3. **NGƯỜI CHỐT** (khâu whitelist): tick chọn đoạn giữ, sửa nhẹ (cắt câu thừa) — không bắt viết lại.
4. **DUYỆT → nạp** vào tầng `ngoai`, `nguon_ten=<tên nguồn>`, doc_code ỔN ĐỊNH
   (vd `YT-DANNY-<videoid>`) để chạy lại là GHI ĐÈ không nhân bản, kèm mốc thời gian/URL từng
   đoạn (truy nguồn về đúng phút của đúng video).

**YouTube cụ thể:** kênh whitelist ĐÃ KIỂM CHỨNG (vd `@danny_why` → tầng `ngoai`,
`nguon_ten="Danny Why"`). **Pháp lý/ToS:** transcript là nội dung của creator — dùng NỘI BỘ
tham khảo + trích link nguồn là mức chấp nhận được; nếu thành nguồn CỐT LÕI thì xin phép
creator (quyết định nghiệp vụ của user). Auto-caption có lỗi → cần bước làm sạch; video không
phụ đề → STT (`faster-whisper`) nặng, để sau.

**Module TỔNG QUÁT:** mọi nguồn dài (PDF/bài viết/report) đều dùng chung khâu "LLM đề xuất đoạn
NGUYÊN VĂN → người chốt → nạp". YouTube chỉ là một đầu vào.

**Trạng thái (user chốt 24/07):** LÀM **TRƯỚC Bước 3**. Đợt đầu = LÕI `de_xuat_trich` (thuần,
test mock, van verbatim). Acquisition (`yt-dlp`/transcript) + UI chốt + nạp kho = đợt sau.

---

## 2c. TỔNG HỢP CÓ NEO — bài phân tích từ nguồn (nâng cấp extract, chốt 06/08/2026)

**Vì sao cần.** Van verbatim (§2b) giải quyết XUẤT XỨ nhưng sản phẩm bị khóa ở mức "câu nói
rời": không khái quát được vấn đề chung, và RAG cũng khó khớp (câu hỏi của team là câu khái
quát, chunk trong kho là lời thoại vụn). Thực tế user vẫn phải tự dùng LLM viết tài liệu phân
tích từ nguồn — tức là nhu cầu thật nằm ở BÀI PHÂN TÍCH, không phải trích đoạn.

**Triết lý — KHÔNG gỡ van chống bịa, NÂNG nó một tầng: từ "kiểm chữ" lên "kiểm ý".**
Trích nguyên văn không còn là sản phẩm cuối — nó xuống làm **tầng bằng chứng**. Sản phẩm
cuối là **bài phân tích** do LLM viết (khái quát + đào sâu), với luật sắt: **mỗi luận điểm
phải trỏ về ≥1 đoạn bằng chứng nguyên văn**. LLM được quyền khái quát, không được quyền vô
căn cứ — vẫn đúng nguyên tắc tối cao "không góc nhìn nào nếu không có nguồn thật đứng sau";
chỉ là "đứng sau" giờ nghĩa là *có bằng chứng đỡ*, không còn là *y nguyên từng chữ*.

**BA VAN thay một van:**
1. **NEO BẮT BUỘC (parser):** LLM tổng hợp phải gắn mã neo `[E1][E3]` vào từng luận điểm.
   Không neo / neo sai mã → parser loại thẳng, chưa cần tới LLM thứ hai.
2. **KIỂM NEO (critic máy):** LLM độc lập kiểm từng luận điểm — bằng chứng có ĐỠ được không:
   `do_duoc` / `suy_rong` (suy rộng hợp lý — giữ, kèm ghi chú) / `khong_do` (mặc định bỏ
   tick ở màn duyệt, người có thể tick lại có chủ đích). Critic không phán → `chua_kiem`
   (nói thật, không đoán). Nên trỏ vai critic sang model mạnh qua `CRITICS=` sẵn có.
3. **NGƯỜI DUYỆT (van cuối):** màn duyệt hiện từng luận điểm CẠNH bằng chứng + phán quyết
   critic; người sửa/bỏ/tick rồi mới ghi kho — đúng pattern Duyệt Q&A. Ý người sửa tay lúc
   duyệt là trách nhiệm của người, miễn kiểm neo.

**Đường ống 5 bước:** TRÍCH (van verbatim §2b giữ nguyên, giờ là kho bằng chứng E1..En —
trích rộng tay hơn, thừa không sao) → TỔNG HỢP CÓ NEO (bài tiếng Việt: 1 dòng chủ đề +
các luận điểm gắn neo) → KIỂM NEO → DUYỆT SONG SONG → NẠP KHO.

**Flow MỘT CỬA (user chốt 06/08 — "flow 2 bước quá rắc rối"):** trên UI, toàn bộ phần MÁY
chạy liền một mạch từ link: transcript → trích → tổng hợp → kiểm neo; người duyệt **MỘT lần
duy nhất** ở cuối — thấy luận điểm cạnh dẫn chứng + phán quyết critic để tự đánh giá, bấm
Duyệt là nạp CẢ HAI tài liệu (trích bằng chứng + bản phân tích -PT) một lượt. Bước
tick-từng-đoạn-trích bỏ khỏi luồng chính (toàn bộ đoạn qua van verbatim đều vào kho làm tầng
bằng chứng, hiện trong khối xổ ra để soi); route trích-thủ-công cũ giữ lại cho ca đặc biệt.
MỘT Ô NHẬP: link/mã đã nạp → máy tự nhận, phân tích lại từ bằng chứng trong kho (không tải
lại phụ đề, quyền -PT kế thừa gốc, khu chọn quyền tự ẩn).

**CHẠY NỀN + LỊCH SỬ (user chốt 06/08 lần 3, sau sự cố chờ 30 phút):** phần máy 5–12 phút
không được là một request đồng bộ — bấm là nhận `task_id` ngay (khuôn `_TAC_VU` của Data
Analytics), frontend poll; **nháp ghi RA ĐĨA** (`kho-tai-lieu/nhap-phan-tich/*.json`, nguyên
tử) nên sống qua đóng tab lẫn restart và thành **🕘 Lịch sử trên GUI**: nháp đang chạy / chờ
duyệt / lỗi (mở duyệt tiếp, xóa được) + nguồn đã vào kho (xem lại nội dung trích & bản -PT
tại chỗ qua `/nguon/xem/<mã>` — chỉ phục vụ tầng ≠ noi_bo + vẫn kiểm `_duoc_xem`). Lịch sử
dùng CHUNG cho Manager+ (nguồn ngoài là việc chung, khác chẩn đoán per-user). Duyệt xong nháp
tự rời lịch sử. Cùng đợt: vá bẫy **SDK tự retry lặng lẽ** (LLM_RETRY mặc định 0 — em ruột bẫy
LLM_TIMEOUT 19/07) và nâng LLM_TIMEOUT 60→240 (đo thật bước trích 178,5s trên transcript 11k ký tự).

**Nạp kho — tài liệu con hậu tố `-PT`** (đúng cơ chế `-QA` đã chạy): kế thừa TOÀN BỘ quyền +
tầng nguồn + tên nguồn của tài liệu trích gốc, doc_code bất biến, ghi nguyên tử; chạy lại là
GHI ĐÈ toàn file (bản phân tích là snapshot mới nhất, không nối). Nội dung file CHỈ chứa phân
tích + dòng "(Dẫn chứng: E1, E3 — <mã gốc>)" trỏ về tài liệu trích — KHÔNG chép lại bằng
chứng, tránh đúp chunk khi search. Khi trả lời, agent phân biệt được "Phân tích tổng hợp từ
nguồn X (đã kiểm neo)" với "Lời gốc của X" qua hậu tố mã + tiêu đề.

**Code:** lõi `src/tong_hop_neo.py` (thuần, test mock — tổng hợp, kiểm neo, đọc đoạn từ tài
liệu trích, nạp `-PT`); route `/nguon/phan-tich/de-xuat` + `/nguon/phan-tich/duyet` (cùng
gate trang Nguồn ngoài); UI bước 2 ngay trong trang Nguồn ngoài.

---

## 3. Truy xuất & trả lời — BẢN TƯ VẤN ĐA CHIỀU

### 3.1 Kích hoạt CÓ CHỦ Ý (không tự động trộn)

- **Mặc định giữ nguyên:** hỏi–đáp thường vẫn trả lời **chỉ tầng `noi_bo`**, y như hiện tại.
- **Chế độ đa chiều là một hành động RIÊNG** (nút/công tắc "🧭 Hỏi đa chiều" hoặc "Cố vấn").
  Người dùng chủ động chọn → không bao giờ vô tình nhận ý kiến ngoài như chính sách công ty.
  (Đây là cách hiện thực nguyên tắc "không trộn tầng lặng lẽ".)

### 3.2 Luồng khi bật đa chiều — TÌM RIÊNG công ty vs phần còn lại, TÁCH KHỐI THEO TÊN NGUỒN (đổi 07/08)

1. **TÌM RIÊNG 2 suất** (lọc quyền theo user, tái dùng `search` — **không bỏ RBAC**): một suất
   `noi_bo`, một suất `ngoai` (gộp — không còn suất `chuyen_gia` riêng). *Vì sao tách 2 suất:*
   tìm một phát chung rồi lấy top-k thì nguồn ngoài điểm cao có thể **ĐÈ** tài liệu công ty ra
   khỏi kết quả — tách suất thì công ty luôn có chỗ riêng. (Embedding chạy local nên rẻ.)
2. **PREFER — công ty luôn đầu tiên:** khối `noi_bo` (Official) **luôn dựng và render TRƯỚC**
   khi có bất kỳ chunk liên quan nào. Suất `ngoai` chỉ hiện khi điểm cao nhất **vượt ngưỡng
   liên quan** (`NGUONG_DA_CHIEU`) — chống nhiễu.
3. **TÁCH KHỐI THEO TÊN NGUỒN THẬT (đổi 07/08):** suất `ngoai` sau khi qua ngưỡng được **gom
   theo `nguon_ten`** — mỗi tên một khối riêng, KHÔNG còn nhãn chung "Chuyên gia"/"Nguồn
   ngoài". Hai chunk cùng đến từ "Andrew X" → một khối; một chunk khác của "Youtube Official"
   → khối riêng kế bên. Đây là code (`_nhom_theo_nguon`), không nhờ LLM tự đặt tên khối.
4. **Van chống bịa theo KHỐI:** khối/tên nguồn nào **không có chunk** → **không xuất hiện**,
   KHÔNG sinh quan điểm rỗng (không có tài liệu của Andrew X về chủ đề → không có khối
   "Andrew X").
5. **Công ty trống nhưng có khối khác** (chốt 24/07): **vẫn hiện** các khối còn lại, kèm dòng
   đầu **"⚠️ Công ty chưa có tài liệu về việc này"** — vừa đa chiều đúng lúc cần, vừa là **tín
   hiệu kho-thiếu** để bổ sung tài liệu công ty sau (nối cơ chế kho-thiếu đã có).
6. **SOẠN** một câu trả lời dạng **bản tư vấn tách khối**, mỗi dòng vẫn **trích nguồn**:

   ```
   📌 Theo tài liệu công ty:
      … [KD-2026-xxxx]
   🌐 Andrew X:
      … [KD-2026-49B0D6]
   🌐 Youtube Official:
      … [NG-ABC-003]
   ⚖️ Đồng thuận / Mâu thuẫn:
      Công ty và Andrew X cùng khuyên X; Youtube Official ngược lại ở điểm Y vì …
   ```

7. **Prompt writer (SYSTEM mới, van chống bịa giữ nguyên):** chỉ dùng chunk được cung cấp;
   **viết đúng theo nhãn khối đã cho sẵn** (không tự đặt/đổi tên, không thêm nhãn chung chung);
   **cấm** bịa quan điểm cho khối không có dữ liệu; khối "Đồng thuận/Mâu thuẫn" chỉ nêu khi
   các khối **thật sự** nói về cùng vấn đề.

### 3.3 Tận dụng vòng phản biện đã có

Vòng **writer ↔ critic** hiện tại *đã là* một cỗ máy đa góc nhìn (đang dùng để bắt lỗi).
Mở rộng vai critic: ngoài "có bịa/lạc đề không", thêm tiêu chí **"có gán sai ý cho sai
khối/sai nguồn không?"** và **"có bịa quan điểm cho khối không có dữ liệu không?"**. Bộ cơ
đã có — chỉ thêm tiêu chí, không xây mới.

---

## 4. Tầng "AI suy luận chung" — TÙY CHỌN, rủi ro cao nhất, để SAU

Có thể cho model dùng **kiến thức chung của chính nó** (best-practice ngành) như một chiều
tham khảo. Nhưng đây là tầng **nguy hiểm nhất** vì không có nguồn:

- Chỉ bật khi người dùng chủ động chọn.
- **Dán nhãn to:** *"🤖 AI suy luận chung — KHÔNG phải nguồn công ty, có thể sai hoặc lỗi
  thời."*
- **TUYỆT ĐỐI không** trộn vào phần trích dẫn; luôn nằm khối riêng, dưới cùng.
- **Không** đưa vào các cơ chế ngầm (kho-thiếu, feedback) vì nó không phải "kho thiếu".

→ **Không làm ở đợt đầu.** Ghi ở đây để nhớ ranh giới, làm sau khi 2 tầng có-nguồn đã chạy tốt.

---

## 5. RBAC × Tầng nguồn — cách hai trục ghép

- **Không luật quyền mới.** Người dùng thấy chunk của một tầng **chỉ khi** RBAC hiện tại cho
  phép (`_duoc_xem`). Tầng nguồn không nới cũng không siết quyền.
- Hệ quả: bản tư vấn đa chiều **tự lọc theo quyền** — nhân viên bộ phận khác không thấy khối
  chuyên gia/nguồn nếu tài liệu đó ngoài quyền họ. Từ chối vẫn **lặng lẽ** (không lộ tài liệu
  tồn tại), nhất quán Rule 2.

---

## 6. Nhịp triển khai — BƯỚC TỐI THIỂU TRƯỚC

Làm nhỏ, đo thật trên vài câu, rồi mới mở rộng. Mỗi bước một commit, test xanh, kiểm dữ liệu thật.

- **Bước 1 — Nền dữ liệu (rủi ro thấp) — XONG (24/07, agent-app 111):** thêm `tang_nguon`
  (3 giá trị) + `nguon_ten` vào catalog + payload + index + dropdown nhập liệu; `noi_bo` →
  `nguon_ten` mặc định `Official`. Mặc định `noi_bo` → **hành vi cũ không đổi** (test hồi quy).
- **Bước 2 — Kho nguồn khác thử (CHƯA LÀM, đổi tên 07/08 — không còn nhãn `chuyen_gia`
  riêng):** nạp **một** kho nhỏ (ghi chú/playbook người giỏi), gắn tầng `ngoai` + tên.
- **Module EXTRACT (§2b) — XONG (24/07, agent-app 112→117 + 224c048):** lõi `de_xuat_trich`
  (van verbatim) → acquisition transcript (bỏ yt-dlp, per-video) → route Owner đề-xuất/duyệt →
  trang Nguồn ngoài. Sau nghiệm thu video thật thêm: cookies YouTube chống chặn IP, tách lỗi
  phụ-đề vs lỗi-model, khối `<<<DICH>>>` bản dịch gắn nhãn (không kiểm verbatim, không thay
  lời gốc). Parser phải KHOAN DUNG delimiter lệch — GLM thật viết thiếu dấu `>`.
- **Bước 3 — Trả lời đa chiều — XONG CODE (29/07, agent-app b1c2357):** nút "🧭 Đa chiều" gọi
  đường RIÊNG `/hoi-dap/stream-da-chieu`; tìm tách theo tầng; prefer công ty; ngưỡng
  `NGUONG_DA_CHIEU`; tầng rỗng bỏ khối; công ty trống → cảnh báo deterministic + ghi kho-thiếu
  (trừ khi bị chặn quyền — Rule 2); critic thêm tiêu chí sai-tầng. **CÒN nghiệm thu thật mục 7**
  (kho Qdrant máy công ty đang rỗng — phải restore snapshot trước).
- **Module TỔNG HỢP CÓ NEO (§2c) — chốt + code 06/08/2026:** bài phân tích khái quát từ đoạn
  trích, ba van (neo bắt buộc / kiểm neo / người duyệt), tài liệu con `-PT` kế thừa quyền gốc.
- **GỘP chuyên gia + ngoài thành MỘT tầng (§1.1, §3.2) — chốt + code 07/08/2026:** dropdown
  còn 2 giá trị `noi_bo`/`ngoai`; trả lời đa chiều tách khối theo `nguon_ten` thật thay vì
  nhãn tầng chung; dữ liệu cũ (7 tài liệu) gộp bằng `scripts/gop_chuyen_gia_ngoai.py`.
- **Sau (chưa gấp):** tầng "AI suy luận chung" (mục 4); đo ngưỡng liên quan riêng cho `ngoai`
  nếu nhiễu; thống kê nguồn nào hay được đối chiếu; Bước 2 (kho chuyên gia thử) vẫn CHƯA LÀM —
  giờ chỉ còn nghĩa là "nạp một kho nhỏ, gắn `ngoai` + tên", không còn nhãn `chuyen_gia` riêng.

---

## 7. Nghiệm thu (định nghĩa "đúng")

1. Chưa bật đa chiều → hỏi–đáp trả lời **giống hệt** trước (chỉ `noi_bo`). *(hồi quy)*
2. Bật đa chiều, chủ đề có cả công ty lẫn nhiều nguồn khác nhau → bản tư vấn **tách nhiều
   khối**, mỗi khối mở đầu ĐÚNG TÊN nguồn thật, **mỗi ý trích đúng nguồn của đúng khối**.
3. Chủ đề chỉ có tài liệu nội bộ → **chỉ hiện khối nội bộ**, KHÔNG bịa khối nguồn khác.
4. Nhân viên bộ phận khác hỏi → **không thấy** khối nguồn khác ngoài quyền họ
   (RBAC giữ nguyên, từ chối lặng lẽ).
5. Đổi `tang_nguon` một tài liệu qua UI → payload Qdrant + catalog **đồng bộ, kiểm chứng
   được** bằng thử thật.

---

## 8. KHÔNG làm (YAGNI — ranh giới để khỏi phình)

- Không tự động trộn tầng vào câu trả lời mặc định.
- Không sinh quan điểm cho tầng không có dữ liệu (không có nguồn = không có khối).
- Không thêm luật quyền mới — tái dùng `_duoc_xem`.
- Không nạp dữ liệu công cộng dạng số (kiểu awesome-public-datasets) vào kho — đó là **con
  số, không phải quan điểm**, không phục vụ mục tiêu này.
- Không làm tầng "AI suy luận chung" ở đợt đầu.

---

## Bất biến kế thừa (nhắc lại — không được phá)

Van chống bịa · trích nguồn từng dòng · doc_code bất biến · luật/giá trị ngoài code (dropdown
cố định) · tách UI khỏi logic · mỗi hàm có test · RBAC bộ phận × level · Qdrant trước catalog
sau khi đổi trường quyền-mở-rộng · từ chối lặng lẽ (không lộ tài liệu ngoài quyền).
