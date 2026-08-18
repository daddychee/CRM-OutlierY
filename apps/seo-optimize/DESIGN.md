# DESIGN.md — SEO OPTIMIZE OUTLIERY

> Công cụ nội bộ, dùng cả ngày, dữ liệu dày. Đọc lâu không mỏi mắt quan trọng hơn gây ấn tượng.

---

## ⚠ Đọc trước: file này KHÔNG phải nguồn sự thật

Nguồn sự thật là **`seo/board.html`** (giá trị đang chạy) và **`CLAUDE.md`** (lý do đằng sau
từng quyết định, kèm mọi bẫy đã cắn). File này là **bản xuất ra** theo khuôn `DESIGN.md` của
skill `web-design`, để đưa cho công cụ/người khác đọc nhanh.

Dự án này đã dính lỗi *"hai nguồn sự thật cho cùng một thứ"* ba lần (`siblings` · `#profSel` ·
textarea-vs-danh-sách) và lần nào cũng lệch. Nên file này có **hàng rào**:

```bash
python -m seo.designcheck      # đối chiếu MỌI con số ở đây với board.html
```

Chạy nó sau mỗi lần đụng `:root` hoặc bố cục, cùng hạng với `boardcheck` / `contrastcheck`.
Lệch là nó báo hỏng. **Đừng sửa tay file này cho khớp — sửa board trước, rồi cập nhật ở đây.**

---

## 1. Visual Theme & Atmosphere

**Style**: 极简克制 / Tối giản tiết chế (minimal restrained)
**Keywords**: dense · measured · calm · token-driven · low-glare · two-theme · offline
**Tone**: điềm đạm, đo được, không trang trí — **NOT** playful, NOT "bold minimalism",
NOT oversized-typography.
**Feel**: như bảng điều khiển trong phòng máy — sáng vừa đủ để nhìn cả ca trực, không cái gì
nhấp nháy để giành sự chú ý.

**Interaction Tier**: **L1** (tinh tế nhưng tĩnh)
**Dependencies**: **CSS thuần**. Không GSAP, không Lenis, không thư viện nào.
Tool chạy `http.server` trên `127.0.0.1` và **phải chạy được offline** → cấm mọi CDN, kể cả
webfont. Đó cũng là lý do dùng font hệ thống, không `@import` Google Fonts.

**Vì sao L1, không L2/L3**: cảnh `Dashboard` trong skill `web-design` đặt baseline L1 và nói
thẳng *"不要用 scroll reveal（信息需要立即可见）"*. Người dùng mở tool này vài chục lần mỗi
ngày để tra số — hiệu ứng cuộn làm chậm việc đọc chứ không làm đẹp.

---

## 2. Color Palette & Roles

Hai bảng, mỗi bảng khai **đúng một lần**. JS đặt `data-theme` trên `<html>`;
**không dùng `@media prefers-color-scheme`** — khai hai chỗ là chắc chắn sẽ lệch nhau.

> **04/08/2026 — ĐỔI SANG BẢNG "BREAKOUT SIGNAL" của OUTLIERY** (user chốt "UI đúng format
> AI Agent" khi app vào một cửa 8000). Trị số chép từ token thật của agent-app/base.html:
> tối VOID #090C12 · PANEL #121826 · RADAR BLUE #4C8FE0 · SLATE #8B96A8 · MIST #E8EDF4;
> sáng trắng trung tính + accent đậm xuống #2C6FC4. Màu 3 TRỤ CỘT + ok/danger là màu NGHĨA
> nghiệp vụ — giữ, không rebrand. Mực phụ/alpha tinh chỉnh theo `seo.contrastcheck`
> (mọi cặp ≥ 4.5:1). Font UI: Inter (wordmark Space Grotesk), tải từ /static cổng 8000.
> Theme: MỘT khóa localStorage chung `outliery_theme`; "Tự động" = theo HĐH (hết theo giờ).

```css
:root,:root[data-theme="dark"]{
  /* Nền — BA mặt phẳng, không hơn */
  --bg:#090C12;          /* nền trang (VOID) */
  --panel:#121826;       /* .board, .panel — mặt chứa nội dung (PANEL) */
  --raised:#182233;      /* .pcard/.fcard/.card/.fold — nổi lên trên panel */
  /* Cạnh */
  --border:#31425E;      /* nét của ĐIỀU KHIỂN: chip · nút · ô nhập · tab (~40 chỗ) */
  --border-soft:#243149; /* vạch ngăn nhẹ (= line của agent-app) */
  --edge:#405674;        /* CHỈ .niche — cạnh của tầng KHÔNG có nền riêng */
  /* Chữ */
  --text:#E8EDF4;        /* thân bài, tiêu đề (MIST) */
  --muted:#8B96A8;       /* mô tả, nhãn phụ (SLATE) */
  --faint:#9AA5B5;       /* chú thích, số đếm — màu CĂNG NHẤT, đụng gì cũng phải đo lại */
  /* Nhấn + ngữ nghĩa */
  --accent:#4C8FE0;  --accent-ink:#071018;  --accent-soft:rgba(76,143,224,.05);
  --link:#6BA4E8;  --ok:#A2C494;  --danger:#D97C6C;  --danger-soft:rgba(217,124,108,.14);
  --scrim:rgba(6,8,12,.78);         /* màn phủ sau overlay */
  /* BA TRỤ CỘT (chỉ có nghĩa trong Generator) */
  --pil-title:#D9B36C;  --pil-tag:#8BBDD0;  --pil-des:#C2B3E3;
  --pil-title-soft:rgba(217,179,108,.08);
  --pil-tag-soft:rgba(139,189,208,.08);
  --pil-des-soft:rgba(194,179,227,.08);
  --dur:.16s;                        /* mọi transition hover */
}
:root[data-theme="light"]{
  --bg:#F5F5F5; --panel:#FAFAFA; --raised:#FFFFFF;
  --border:#D9D9D9; --border-soft:#E6E6E6; --edge:#C4C9D2;
  --text:#16181C; --muted:#565B63; --faint:#5C6169;
  --accent:#2C6FC4; --accent-ink:#FFFFFF; --accent-soft:rgba(44,111,196,.04);
  --link:#1E5AA8; --ok:#38582D; --danger:#A8402F; --danger-soft:rgba(168,64,47,.10);
  --scrim:rgba(20,22,28,.55);        /* nhạt hơn dark: scrim 76% gần đen trên nền sáng nặng tay */
  --pil-title:#6B4A0D; --pil-tag:#255668; --pil-des:#5A428D;
  --pil-title-soft:rgba(107,74,13,.11);
  --pil-tag-soft:rgba(37,86,104,.11);
  --pil-des-soft:rgba(90,66,141,.11);
}
```

### Luật màu

1. **Mọi màu qua biến CSS.** Hex ngoài hai khối `:root` chỉ được phép nằm trong chú thích.
   `designcheck` chốt điều này.
2. **CAO HƠN KHÔNG PHẢI TỐT HƠN.** AA đòi 4.5:1, nhưng chữ thân bài vượt ~14:1 trên nền tối bị
   **halation** (nhoè viền, mỏi mắt khi đọc lâu). Bản trước đặt 16.25:1 và user kêu *"nhìn rất
   đau mắt"*. Đích hiện tại: **12.15:1** (dark) / **11.96:1** (light) — vẫn hơn gấp đôi chuẩn.
   `contrastcheck` cảnh báo khi vượt `GLARE_HI = 14`.
3. **Nền `rgba` phủ lên nền đặc phải đo RIÊNG.** Ma trận thuần chỉ đo chữ trên 3 mặt phẳng, nên
   nó **mù** với `.card.picked` / `.mini.on` / `.chip.warn`. Đo thật: `faint` trong thẻ đã chọn
   = **3.99** trong khi ma trận báo 5.31. Alpha **0.08 là trần** (0.09 đã tụt 4.44).
4. **HAI TẦNG NGHĨA MÀU, đừng trộn:**
   - **Tầng KHỐI — màu = TRỤ CỘT.** Mỗi khối chỉ khai một biến `--pil`; vạch trái · `h3` ·
     nút `↻` · `.card.picked` · `.score .val` · tab kết quả đều đọc lại `var(--pil)`.
     Description lấy **tím** vì phải khác cả 4 màu đã có nghĩa.
   - **Tầng CHIP — màu = NGHĨA, DẠNG = LOẠI.** Chỉ 3 màu: xanh (tag/liên kết) · lục (đạt) ·
     đỏ (thiếu). Số đo (`.chip.num`, tabular) và cấu trúc (`.chip.struct`, mono + viền gạch)
     dùng màu trung tính, phân biệt bằng **dạng**.
5. **Ngoài Generator không có trụ cột nào** → vàng ở tab KÊNH/FORMAT/TẬP vẫn là accent/thương
   hiệu. Không mâu thuẫn.
6. **Không bao giờ hiện số tiền nếu `.env` chưa đặt giá.** Hiện hướng dẫn bật, không "ước lượng
   giúp".

---

## 3. Typography Rules

**Font Stack** — font hệ thống, **không `@import`** (offline):

```css
--disp: "Avenir Next","Segoe UI",system-ui,sans-serif;
--mono: ui-monospace,"SF Mono",Menlo,Consolas,monospace;
```

### Thang khoảng cách & mốc căn lề

Thang **8px**: `--s1:4 · --s2:8 · --s3:12 · --s4:16 · --s5:24 · --s6:32 · --s7:48`.
Mọi `gap`/`padding` phải lấy từ đây. Trước đó là 14·16·18·22·30 — sáu giá trị không theo
thang nào, mắt không bắt được nhịp.

**HAI mốc lề, đừng gộp:**

| Token | Là gì |
|---|---|
| `--card-x` **22px** | padding ngang của **mọi** thẻ/panel |
| `--text-x` **23px** | `1px viền + --card-x` — chữ **ngoài** thẻ thụt đúng ngần này thì mới thẳng hàng với chữ **trong** thẻ |

Đo bằng trình duyệt (script CDP, xem `CLAUDE.md`), không đọc CSS suông: mép trái là tổng của
padding cha + viền + margin, chỉ lúc chạy mới biết. Bộ kiểm so **theo TẦNG** và **theo CỘT** —
thụt một mức cho khối lồng là chủ ý của cây phân cấp, và so mốc cột trái với cột phải của
Generator là vô nghĩa.

| Vai trò | Token | Size | Weight | Ghi chú |
|---|---|---|---|---|
| Tên sản phẩm (`h1.brand`) | — | 26px | 700 | `letter-spacing:-.015em`, trong banner |
| Nhãn mục (`.grp-head h3`) | `--lbl` | 12px | 700 | UPPERCASE, `letter-spacing:.12em` |
| Số KPI (`.score .val`) | `--t-xl` | 22px | 700 | `tabular-nums` |
| Thân bài | `--t-md` | **15px** | 400 | |
| Phụ / nút nhỏ | `--t-sm` | 13px | | |
| Chú thích, chip | `--t-xs` | 12px | | **SÀN TUYỆT ĐỐI** |

**Luật chữ:**
- **KHÔNG BAO GIỜ dùng < 12px ở bất kỳ đâu**, kể cả inline style trong JS.
- Thân bài **15px, không phải 13–14px** như cảnh Dashboard của skill đề nghị. Cố ý: user đã
  phản hồi *"khó nhìn"* và cả thang chữ được đặt lại vì việc đó. Không thu nhỏ ngược.
- **Monospace CHỈ cho nội dung thật** (tag · description · pattern · công thức title). Nhãn,
  chip, số đếm dùng `--disp`.
- **Không trang trí chữ**: không gradient, không glow, không `text-shadow`. Bảng quyết định của
  skill `web-design` cho phong cách 极简克制 là **"--" ở mọi ô** — board đang đúng, giữ nguyên.
- **Không dùng emoji làm icon ở chỗ chữ bắt buộc phải đọc được.** Ký hiệu hiện dùng
  (`◐ ☀ ☾ ✓ ✕ ↻ ⭳`) đã đo trên máy đích bằng dấu vân pixel canvas: 8/8 có glyph thật.
  Đã cắn với `🖥` — ra ô vuông, nút trông như hỏng.

---

## 4. Component Stylings

| Thành phần | Nền | Cạnh | Hover | Ghi chú |
|---|---|---|---|---|
| `header.hero` | gradient `--raised`→`--panel` | `--edge` 1px | — | dải 3 màu 4px vẽ bằng **lớp nền** |
| `.gsearch` / `.gres` | `--panel` / `--raised` | `--border` / `--edge` | `.gitem` → `--accent-soft` | bảng kết quả tràn RA NGOÀI banner |
| `.pillars` / `.pil` | `--panel` | `--border`, ngăn cách 1px | — | 3 ngăn chia đều, `flex:1` |
| `.board`, `.panel` | `--panel` | `--border` | — | mặt chứa |
| `.niche` | **không có** | `--edge` 1px | — | xem §6 |
| `.pcard` / `.fcard` | `--raised` | `--border` | **đổi viền** | **cấm nhấc lên** |
| `.card` (kết quả) | `--raised` | `--border` → `--pil` khi chọn | đổi viền | tint `--pil-soft` .08 |
| `.tab` (rail trái) | trong suốt | — | `--panel` + chữ `--text` | đang mở: vạch accent 3px trái |
| `.chip` | tuỳ loại | `--border-soft` | — | `white-space:nowrap`, trừ `.chip.struct` |
| `.btn-primary` | `--accent` đặc | — | `brightness(1.12)` | chữ `--accent-ink` |
| `.mini` | trong suốt | `--border` | chữ → `--accent` | |
| `.runtab .rrow` | — | gạch đứt | nền → `--raised` | bảng cuộn ngang riêng |
| `.overlay` | `--scrim` | — | — | |

**Luật thành phần:**
- **Banner đầu trang phải NÓI THẬT, không phải khẩu hiệu.** Dòng cũ `Title ×3 · Tag ×3 ·
  Description ×1 · pick → metadata.txt` đã gỡ vì nó **sai ở chế độ nhiều kênh** (mỗi kênh
  nhận đúng MỘT bộ chốt sẵn, không có ×3 để pick). Thay bằng 3 ngăn mang đúng luật của từng
  trụ cột. Dải 4 màu ở mép trên dùng `--pil-*` nên banner kiêm luôn **bảng chú giải hệ màu**
  của Generator — trước đó hệ màu chỉ nằm trong `CLAUDE.md`, màn hình không chỗ nào nói ra.
  Nền là gradient giữa **hai bề mặt CÓ SẴN**, không chế màu mới ⇒ mọi chữ trong banner vẫn
  nằm trong ma trận `contrastcheck` đã đo, không phát sinh điểm mù kiểu nền `rgba`.
- **`overflow:hidden` trên khối cha CẮT MẤT mọi thứ bung ra ngoài nó** — dropdown, tooltip,
  popover. Đã cắn 2026-08-01: banner đặt `overflow:hidden` để bo góc cắt gọn dải màu, rồi thêm
  ô tìm kiếm thì **bảng kết quả biến mất sạch và không bấm được** (`elementFromPoint` tại chỗ
  ô kết quả trả về `.ctxbar` nằm dưới). Triệu chứng ĐÁNH LỪA: bảng vẫn "đóng lại" sau khi bấm
  (do listener click-ra-ngoài), trông y như đã chọn xong. Cách chữa đúng là **bỏ `overflow`,
  vẽ dải bằng LỚP NỀN** — nền tự tôn trọng `border-radius`, không cần cắt gì.
- **Thẻ dữ liệu hover đổi VIỀN, không nhấc lên.** `transform:translateY` = **0 chỗ** trong toàn
  bộ board. Lift phá mật độ thông tin (luật của cảnh Dashboard).
- **Mọi thứ bấm được phải có CẢ hover VÀ focus.** Đã đo bằng chuột thật + phím Tab thật.
  Bẫy: luật hover phải đổi sang giá trị **KHÁC** giá trị thường — từng viết
  `:hover h3{color:var(--accent)}` cho h3 vốn đã là accent, đọc CSS thấy "có hover" mà thực tế
  không đổi một pixel.
- **Phần tử `<div>` có `onclick` phải có `tabindex="0"`** + được listener `keydown` chung biến
  Enter/Space thành `.click()`. Nếu không, bàn phím **không cách nào** xổ thẻ ra để chạm nút
  bên trong.
- **Vùng bấm ≥ 24×24** (WCAG 2.2 AA). Đích nội bộ: 32px cho nút độc lập. Chip link inline 27px
  được chấp nhận — nâng lên 32 là bơm phồng mọi chip trong thẻ vốn đang dày.
- **Phần tử ẩn/hiện bằng `[hidden]` mà có `display:` riêng BẮT BUỘC có `.x[hidden]{display:none}`**
  — bẫy đã cắn 2 lần (`.grp` · `.niche-body`).

---

## 5. Layout Principles

```
body → .app (max-width 1500px) → header · .ctxbar · .shell
                                              ├── .sidenav  (rail 190px, sticky)
                                              └── .panes    (minmax(0,1fr))
```

- **Rail điều hướng bên TRÁI, dọc, 190px, `sticky top:16px`.** Chiều ngang là thứ khan hiếm
  (Generator là lưới 2 cột, bảng lịch sử phải cuộn ngang); chiều dọc thì thừa.
- **190px chứ không 240–280px** như skill đề nghị: rail hiện tại đã ăn **212px** (190 + gap 22)
  của lưới Generator, buộc phải dời ngưỡng gãy cột 1160 → 1372. Rộng thêm nữa là đẩy ngưỡng
  vượt quá mọi màn hình thường dùng.
- **Lưới thẻ: `repeat(auto-fit, minmax(min(320px,100%), 430px))` + `justify-content:start`.**
  `auto-fill` + `1fr` chia đủ cột kể cả khi chỉ có 1–2 thẻ ⇒ thẻ bó lại 320px và bỏ trống
  1.100px bên phải. `min(320px,100%)` chống tràn ở khung hẹp.
- **Cắt chữ dài bằng CSS, KHÔNG `slice()` trong JS** — `slice` cắt giữa từ.
- **Nội dung rộng (bảng, công thức mono) cuộn trong hộp riêng.** Trang không bao giờ cuộn ngang.

---

## 6. Depth & Elevation

Cây lồng nhau có **BỐN** tầng nhưng chỉ có **BA** ô tô nền → bắt buộc một giá trị bị lặp, và bản
lặp rơi trúng `body` ⇒ khối niche đọc ra như **lỗ thủng xuyên qua bảng**.

Không đẻ được mặt phẳng thứ tư: dark thì `--raised` là **trần** (mọi nền `rgba` composite lên
nó), light thì `--bg` là **sàn** (`faint` chỉ còn 6.72). Nên tầng thứ tư đổi sang **kênh khác**:

| Bước | dark | light |
|---|---|---|
| `body → panel` | 1.093 | 1.085 |
| `panel → raised` | 1.137 | 1.083 |
| **`edge` trên `panel`** | **1.99** | **1.95** |

**Mực PHỤ phải đủ đậm — nhợt nhạt cũng là một lỗi** (user 2026-08-01: *"màu chữ trông nhợt nhạt quá"*).
Đếm trên board thật: `--text` chỉ chiếm **18%** chữ trên màn, 82% còn lại là `muted`/`faint`/`accent`/`ok`
— và ở theme sáng chúng từng chỉ **5.02–5.43**, sát sàn AA. Đã nâng lên **6.57–7.40** (light) và
**7.61–9.01** (dark), giữ nguyên hue+saturation, chỉ chỉnh độ sáng.
`--text` ở dark **giữ nguyên 12.15** — nâng nữa là chạm lại ngưỡng loá.

`.niche` **bỏ hẳn nền**, phân tầng bằng **viền `--edge`** — mạnh **~18×** mọi bước nền còn lại.
Cộng bo góc + padding + gap 20px + vạch accent ở tiêu đề.

**Hệ quả bắt buộc nhớ:** con trực tiếp của `.niche-body` mà dùng `--panel` thì thành
panel-trên-panel = **CR 1.000** — chỉ dời lỗ thủng xuống một tầng. `.niche .fold` phải lên
`raised`.

**Không dùng `box-shadow` để tạo tầng** — bóng trên nền tối gần như vô hình, và trên nền sáng
nó thêm một lớp xám không kiểm soát được bằng ma trận tương phản.

---

## 7. Animation & Interaction

**Tier L1. Toàn bộ bằng CSS.**

```css
--dur:.16s;                                   /* trong dải 150–300ms của checklist */
@media (prefers-reduced-motion:reduce){:root{--dur:0s}}
```

| Cái gì | Chi tiết |
|---|---|
| Hover | `color · background-color · border-color` trong `.16s ease-out` |
| Vào (đổi tab) | `panein .18s ease-out` — `opacity 0→1` + `translateY 4px→0` |
| Focus | `outline: 2px solid var(--accent); outline-offset: 2px` |
| Nút chính | `filter: brightness(1.12)` |

**Luật hiệu ứng:**
- **CHỈ chuyển 3 thuộc tính màu, KHÔNG `all`.** `all` sẽ animate cả `width`/`height` — đúng
  anti-pattern *layout thrashing*.
- **Hiệu ứng vào chỉ chạy khi ĐỔI TAB, không khi vẽ lại.** `renderLib`/`renderFmts`/`renderEps`
  chạy sau **mọi** lần lưu/xoá/extract; gắn hiệu ứng ở đó thì sửa một field cũng thấy cả trang
  nháy. Đã đo bằng sự kiện `animationstart` thật: đổi tab **1** lần · vẽ lại **0** lần.
- **Không scroll-reveal, không parallax, không pin, không con trỏ tuỳ biến, không 3D.**
- **`prefers-reduced-motion: reduce` phải tắt HẲN**, không chỉ rút ngắn. Đã đo: 0 lần chạy.
- Sau khi hiệu ứng xong `transform` phải về `none` — transform còn sót sẽ phá `position:sticky`
  của đầu bảng.

---

## 8. Do's and Don'ts

### ✅ Do

- Đo trước khi sửa, đo lại sau khi sửa. Chạy `boardcheck` · `contrastcheck` · `designcheck`
  sau **mọi** lần đụng `:root` hoặc bố cục.
- Kiểm bằng **trình duyệt thật có tương tác** (`scratchpad/cdp.py`). Kiểm tĩnh không chứng minh
  được một nút có làm gì.
- Thêm màu/tầng mới thì thêm **token**, và cập nhật `contrastcheck` (`INK`/`BG`/`TINTS`).
- Đổi một ngưỡng breakpoint thì tìm **mọi** ngưỡng đi kèm (`.cols` và `.side` phải khớp nhau).
- Nói ra khi tool bỏ bớt/lọc/cắt dữ liệu — kèm số lượng và lý do.

### ❌ Don't

- **Đừng làm đậm `--border` để tạo tầng.** Nó là nét của ~40 điều khiển; làm đậm là làm đậm
  hàng trăm nét 1px mỗi màn hình — đúng thứ gây mỏi mắt. Dùng `--edge`.
- **Đừng viết luật hover gán đúng giá trị mà phần tử đã có.** Đọc CSS sẽ thấy "đã có hover",
  thực tế không đổi gì.
- **Đừng dùng `@media prefers-color-scheme`** — JS đặt `data-theme`, mỗi bảng màu khai một lần.
- **Đừng thêm webfont / CDN / thư viện.** Tool phải chạy offline.
- **Đừng dùng `font-size` < 12px.**
- **Đừng đóng dấu ✓ cho thứ chưa đối chiếu được.** *"Không có gì để đối chiếu"* ≠ *"đã đối
  chiếu và khớp"*.
- **Đừng để bộ kiểm báo xanh cho lỗi đang chạy.** Bộ kiểm nào cũng phải có self-test trồng lỗi
  giả và bắt buộc nó báo hỏng.

---

## 9. Responsive Behavior

| Ngưỡng | Đổi gì |
|---|---|
| **> 1372px** | Generator 2 cột (`1fr` + `380px`), cột phải `sticky` |
| **≤ 1372px** | Generator xếp **1 cột**, cột phải hết `sticky` — hai dòng này phải khớp nhau |
| **≤ 1120px** | Banner: bỏ dòng phụ của 3 trụ cột, dải co về đúng bề chữ |
| **≤ 1040px** | Bảng **Tài khoản** xếp dọc mỗi ô một dòng, ẩn hàng tiêu đề cột |
| **≤ 900px** | Rail thành **hàng ngang cuộn được**, vạch chọn chuyển xuống chân tab |

**1120px là số ĐO ĐƯỢC, không phải số tròn chọn bừa:** dòng phụ (`ghép từ title đối thủ` …)
còn vừa khít ở 1120 và bắt đầu bị `text-overflow` cắt ở 1060. Không mượn ngưỡng 1372 có sẵn
vì 1280 và 1366 là hai bề rộng laptop phổ biến nhất — cắt ở 1372 là xoá dòng phụ trên gần
như mọi máy xách tay. Dưới ngưỡng phải bỏ luôn `flex:1` của dải: bỏ chữ mà vẫn giãn kín thì
ba ngăn thành ba ô rỗng.

**Đã đo, không viewport nào cuộn ngang:**

| | 375 | 768 | 1024 | 1440 |
|---|---|---|---|---|
| `scrollWidth` | 360 | 753 | 1009 | 1425 |

Tool này chỉ chạy trên desktop (`127.0.0.1`, mở bằng `Start.bat`) — 375px không phải trường hợp
dùng thật, nhưng "trang không bao giờ cuộn ngang" vẫn là luật cứng.

---

## Đã cân nhắc và CỐ Ý không làm

| Khuyến nghị (nguồn) | Vì sao bỏ |
|---|---|
| Pattern *"Operations **Landing**"* — hero, CTA dùng thử (ui-ux-pro-max) | Tool nội bộ không có trang bán hàng |
| Style *"Exaggerated Minimalism"*, `clamp(3rem,10vw,12rem)` weight 900 | Dành cho fashion/agency; đặt vào bảng dữ liệu dày là hỏng |
| Palette xanh/hổ phách, nền `#F8FAFC` | Gần trắng tinh — đúng thứ đã bỏ vì chói |
| Fira Code/Fira Sans qua Google Fonts | CDN |
| GSAP + ScrollTrigger (L2/L3) | CDN, và cảnh Dashboard **cấm** scroll-reveal |
| Skeleton loading | Pipeline đã hiện tiến trình bằng CHỮ — thông tin hơn hẳn khung xám |
| Số KPI chạy số (number roll) | Trang trí thuần cho tool tra cứu |
| Section label thêm `border-bottom` accent | Board đã dùng vạch accent cho cấp **nhóm**; dùng lại ở cấp **section** là hai cấp một ký hiệu → **làm yếu** phân cấp |
| Rail 240–280px | Đã đo: rail 190px đã ăn 212px của lưới 2 cột |
| Thân bài 13–14px | User đã phản hồi "khó nhìn"; thang chữ đặt lại vì việc đó |
| Skip-link | Rail 4 mục, tới nội dung ~8 Tab — xa mức "100 tabs" mà checklist nhắm tới |
