# Sub-niche Deep-Dive + DNA Niche (tích hợp kiểu Padoma)

> Sau khi CHỌN một sub-niche (từ Execution Plan / sub-niche map, hoặc chỉ định tay bằng seed), tạo 4 tài
> sản cho đúng sub-niche đó: **Keywords · Tags · Content Outlier · DNA Niche**. Ba cái đầu lấy thẳng từ
> dữ liệu niche-report đã có; DNA dùng lại generator đã kiểm chứng của Padoma (`prompt-dna-v4`).

## Ý tưởng lõi — OX thay bước "thẩm định thủ công"

Padoma dựng DNA từ *"video đã được thẩm định thủ công"* (`prompt-dna-v4`: mọi video trong danh sách đều là
mẫu đáng học, không chấm điểm). niche-report **tự động hoá bước thẩm định đó bằng OX v3**: danh sách outlier
`valid & primary` chính là "danh sách video đã thẩm định". Hai bên khớp nhau tự nhiên:

- **OX (metric)** → *chọn* video nào là winner đã được chứng minh.
- **DNA Padoma (phi-metric)** → *giải mã* vì sao nó giữ chân (hook, cấu trúc, giọng, cảm xúc).

OX lọc, DNA giải mã. **Không** để DNA xếp hạng lại theo metric; **không** để OX quyết định craft.

## Luồng chạy

```
1. Chạy pipeline niche-report:  1_scan → 2_keywords → 3_comments   (tags đã được 1_scan lưu sẵn)
2. Chọn sub-niche:              từ sub-niche map (Execution-Plan spec §6) HOẶC seed thủ công
3. Deep-dive (data, tất định):
   python3 9_subniche_deepdive.py WORK --seeds "3i,atlas,interstellar" --name "3I-ATLAS" --top 40
   -> deepdive_<name>.json      = Keywords (3 tầng) + Tags + Content Outlier   [3 asset đầu]
   -> 00-danh-sach-video-<name>.md = URL list ĐÃ THẨM ĐỊNH (OX)               [cầu sang DNA]
4. DNA Niche (Padoma, dựa transcript):
   a. Điều kiện: .env có TRANSCRIPT_API_KEY (transcriptapi.com) + YOUTUBE_API_KEY; đã thêm
      transcriptapi.com vào allowed domains.
   b. Đưa 00-danh-sach-video-<name>.md vào project Padoma làm 00-danh-sach-video.md.
   c. Chạy prompt-dna-v4 VÒNG 1 (mỗi cụm 5 video: lấy transcript qua skill lay-transcript-youtube +
      comment qua lay-comment-youtube → phân tích → dna-temp/cum-XX.md). Lặp đến hết video.
   d. Chạy VÒNG 2 → 12 file DNA trong dna-niche/.
```

## 12 file DNA (đầu ra Vòng 2 của Padoma)

`01-cau-truc-win` · `02-hook-patterns` · `03-storytelling-formats` · `04-cam-xuc-map` ·
`05-sieu-du-lieu` (keywords/thuật ngữ) · `06-diem-nho-vang` · `07-chuyen-tiep-cta` ·
`08-phong-cach-giong-van` · `09-audience-insight` · `10-loi-can-tranh` · `11-content-gaps` ·
`12-feedback-cai-thien`. Phân loại mỗi video **CHUẨN MẪU / THAM KHẢO / LỆCH NICHE** theo *cơ chế nội
dung*, KHÔNG theo views/sub/engagement.

## Ánh xạ hai lớp (theo `HUONG-DI-TOI-UU.md` của Padoma)

Mỗi video có hai lớp do hai "khán giả" phán xử. Bộ 4 asset phân bổ đúng vào hai lớp:

| Lớp | Conventional/Khác biệt | Asset phục vụ | Vai trò |
|---|---|---|---|
| **Khám phá** (thuật toán + người lạ quyết click) | **Conventional** — bám để được phân phối | Keywords · Tags · Content Outlier · DNA 01/02/03/05 (cấu trúc, hook, format, keyword) | "Sàn/ràng buộc" — KHÔNG phá cách ở đây |
| **Trung thành** (người đã xem quyết sub & quay lại) | **Khác biệt** — xây hào | DNA 04 (cảm xúc) · 08 (giọng văn) + "lõi bản sắc" 2–3 dấu hiệu | Chỗ DUY NHẤT để tiêu "ngân sách khác biệt" |

Nguyên tắc vàng Padoma: *tiêu ngân sách khác biệt ở nơi thuật toán KHÔNG nhìn*. Vì vậy Keywords/Tags/
Content-Outlier và DNA lớp khám phá là **sàn bất biến** (làm giống winner để được phân phối); chỉ giọng/
cảm xúc/motif ở lớp trung thành mới là chỗ khác biệt. Đừng để khác biệt rỉ sang packaging (giết phân phối);
đừng để DNA lớp khám phá bị coi là "kinh thánh" (nó chỉ là ràng buộc — Padoma §6.2).

## 3 asset data — chi tiết (từ `9_subniche_deepdive.py`)

- **Keywords — 3 tầng (kiểu `05-sieu-du-lieu`):** *từ chung sub-niche* (★ nếu ≥40% outlier) · *winner-
  distinctive* (từ khoá over-index theo lift, thật sự xuất hiện trong outlier của sub-niche) · *đột phá*
  (lift cao nhưng hiếm — hiếm mà ở winner). Lưu ý: "từ khoá cửa-sổ-hook" thật sự (30s/6 phút đầu) chỉ có
  được ở bước DNA (cần transcript); ở đây `winner-distinctive` là proxy metric gần nhất.
- **Tags:** tổng hợp `snippet.tags` (1_scan đã lưu) của outlier trong sub-niche: tags phổ biến + tags ở
  nhóm outlier mạnh nhất. Nếu scan cũ chưa có tags → cần scan lại (1_scan hiện đã lưu tags mặc định).
- **Content Outlier:** outlier `valid & primary` trong sub-niche, xếp theo excess; cột `content_class` để
  trống — nhãn CHUẨN MẪU/THAM KHẢO/LỆCH do bước DNA (pass nội dung) điền, không phải OX.

## DNA render THẲNG vào report (một tài liệu tổng hợp)

Ngoài 12 file `.md`, DNA giờ render thành **sheet trong workbook** để report là MỘT tài liệu vận hành
niche. `4_build_report.py` đọc `WORK/dna.json` (nếu có) và thêm 6 sheet:
`DNA — Tổng quan` · `DNA — Hook patterns` [khám phá] · `DNA — Cấu trúc & Cảm xúc` ·
`DNA — Giọng & Kho câu` [trung thành] · `DNA — Từ khoá hook & Thuật ngữ` · `DNA — Lỗi cần tránh`.

**Luồng thật (cần 2 key):**
```bash
python3 9_subniche_deepdive.py  WORK --seeds "..." --name "<X>"      # -> 00-danh-sach-video-<X>.md
python3 10_fetch_transcripts.py WORK/00-danh-sach-video-<X>.md WORK/transcripts 40   # TRANSCRIPT_API_KEY
#   -> pass DNA (prompt-dna-v4, 2 vòng, phi-metric, phân loại CHUẨN MẪU/THAM KHẢO/LỆCH) trên transcripts
#      => viết WORK/dna.json
python3 4_build_report.py WORK  WORK/<niche>_report.xlsx             # render DNA sheets vào workbook
```

**Schema `dna.json`** (mỗi khoá = 1 phần; renderer có header cố định):
```json
{"niche":"...", "source":"...", "layers_note":"...",
 "hook_patterns":[{"name","type","formula","fit","example"}],
 "structures":[{"name","arc","fit"}],
 "emotions":[{"emotion","clusters","exemplars"}],
 "voice":[{"aspect","detail"}],
 "strong_lines":[{"line","video","klass","emotion","why"}],
 "hook_keywords":[{"group","terms"}],
 "terms":[{"term","meaning","example"}],
 "avoid":[{"mistake","evidence","consequence","severity"}]}
```
DNA vẫn là bước SEMANTIC (đọc transcript, phi-metric) — nên do 2-model hoặc người xác nhận nhãn
CHUẨN MẪU/THAM KHẢO/LỆCH, không để OX quyết craft.

## Trung thực

- OX chọn winner dưới giả định APC-A (xem `outlier_method.md` R-1). DNA giải mã craft nhưng "vì sao giữ
  chân" là suy luận định tính, cần A/B test.
- Tags phản ánh cái creator *khai báo*, không đảm bảo là lý do được phân phối.
- `winner-distinctive` ≠ hook-window thật cho đến khi có transcript (bước DNA).
- Nhãn CHUẨN MẪU/THAM KHẢO/LỆCH là phán đoán nội dung — nên do 2-model hoặc người xác nhận, đúng tinh thần
  `synthesis_critique_loop.md`.
