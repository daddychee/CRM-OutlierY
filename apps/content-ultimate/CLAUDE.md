# CLAUDE.md — Content Ultimate **V2 (bản độc lập)**

> **⚠ ĐÂY LÀ FORK V2** (user chốt 2026-07-26): `git clone` từ `../Content Ultimate/`
> tại commit `8ca8667`, branch `v2`, dữ liệu (runs/, .env, venv) TÁCH HẲN bản gốc.
> Bản gốc vẫn là bản team đang dùng thật — **không sửa chéo**. Khi V2 ổn định sẽ
> merge bằng git về gốc (vì là clone nên merge = `git merge`, không diff tay).
> Đã lắp trong fork này (2026-07-26/27, test 243 xanh + verify GLM thật end-to-end):
> - **B1** `parse_outline` 2 pass: có dòng CHAPTER đầu dòng → chỉ nhận mốc đầu dòng
>   (văn guard V2 nhắc "Chapter 2's reveal"/"the ENDING" hết xé outline); meta line
>   `Question:`/`Misconception:` vào `_META_LINE` + `estimate_ideas` loại meta (hết ý ma).
> - **B6** khối Writer V2 trong `generator.py` — **gate theo meta-line**: outline không
>   có `Misconception:`/`Question:` thì prompt Y HỆT bản cũ. Hook THE FALSE BELIEF
>   (3 luật); chương OPENING Question-first + PACING + LOOP DISCIPLINE + BREAK STANDS;
>   vòng nở/cắt/hook-cut THỪA KẾ khối (bài học rò payoff). Nguồn sự thật văn bản khối:
>   `_v2_section_block` — sửa chữ phải đối chiếu CONTENT-ULTIMATE-V2-MASTER.md §12.
> - **`oe/m_mine.py`** CLI đào M (pattern = config nới được, 3 nguồn) — `python -m oe.m_mine <run>`.
> - **SOP-V2.md** — quy trình 6 bước cho team (lắp outline V2 dán tay qua tab Writing).
> - **B3 + board V2 (2026-07-27):** tab ⚡ M (V2) đổ từ `GET /oe/api/m-mine`; ô M nằm
>   TRONG khối HOOK (user chốt "hook và M phải là 1"); nút Q per chương (modal: câu hỏi
>   khớp cluster → GAPS ❤ → tự dán, KHÔNG có nút sinh — Q phải nguyên văn); compose ghi
>   `Misconception:` dưới HOOK + `Question:` dưới CHAPTER (picks.misconception/questions).
>   Nút **⚡ Chia outline (PY)** (`suggest.py_split`) chia tất định coverage→peak, thứ tự
>   pos, tự đắp ý con cho chương giãn ≥8× từ cụm chưa dùng gần pos (hằng số gương
>   matInfo board — đổi bên nào phải đổi bên kia). Hướng dẫn team: `SOP-V2.md`.
> Chưa làm: B4 linter (hook-contradiction, hook-no-m) · B5 auto-draft ghi guard vào
> brief. Deploy VPS: chưa — user sẽ quyết vị trí/port.

**Tên tool là "Content Ultimate"** — dùng tên này ở mọi điểm chạm người dùng cấp bộ công cụ
(trang chủ, README, Start.command). Hai khối bên trong giữ tên riêng đã có: **Outline
Board** (Outline Extractor) và **Author Extract**. Tên package Python nội bộ:
`contentultimate` (server hợp nhất), `oe` (outline), `voiceprofile` (giọng văn) — không
đổi trừ khi được yêu cầu.

Repo này là **bản gộp** của 2 tool gốc (`../Author Extract/`, `../Outline Extract/` —
giữ nguyên làm bản lưu, không sửa tiếp bên đó). Tài liệu gốc theo về đây:
[`BUILD-BRIEF-cho-Claude-Code.md`](./BUILD-BRIEF-cho-Claude-Code.md) (kiến trúc 8 module
của Author Extract), [`METHODOLOGY.md`](./METHODOLOGY.md) (phương pháp S1→S5 của Outline),
[`DEVLOG.md`](./DEVLOG.md) (nhật ký quyết định). File này chỉ nói **cách làm việc**.

---

## Bối cảnh nhanh

Bộ công cụ viết **kịch bản YouTube**: tìm "NÓI GÌ" bằng bằng chứng đo được từ video cùng
sóng, rồi viết "BẰNG GIỌNG AI" theo hồ sơ giọng văn tác giả. Nguyên tắc xuyên suốt:
**Python đo — LLM hiểu/sinh, không bao giờ đảo vai.**

Ba khối, một server (`contentultimate/server.py`, entry `content-ultimate`, port 8770):

- **Khối 1 — Outline Board** (`src/oe/`, route `/outline` + `/oe/api/*`): dán URL N video
  cùng sóng → pipeline S1→S4b đo bằng chứng (heatmap peak, beat, cluster embedding,
  tín hiệu comment) → board tick chọn → tự xuất `runs/<run>/outline.txt` (template khóa
  cứng) + `outline_evidence.md`. Board có (thêm 2026-07-14): **2 checkbox Pick/Gộp** ·
  **gộp tay** (chọn ≥2 cluster → ✦ Generate → LLM gộp giữ sắc thái, cụm gộp lên ĐẦU list,
  KHÔNG tự vào outline, gộp-chồng được) · **phân vùng** cluster theo `role` (🎬HOOK/📄BODY/
  🏁ENDING, nút ⧉ toggle) · mỗi mục outline có dòng **`Angle:`** (góc gốc tại peak) + nút
  **CTA** (modal chọn/✨sinh CTA theo nội dung chương) → `CTA:` line · nút **🍪 Cookies**.
- **Khối 2 — Author Extract** (`src/voiceprofile/`, route `/author`): bản thảo tác giả →
  `profile.json` + `clonekit.md` + `dataset.jsonl`, đăng ký `library/index.json` (mã `A001_Tên`).
  **Test lab độ dài** (`lengthlab.py`, CLI `lab`) đo `length_lab` cho profile — xem A6.
- **Khối 3 — Writing** (route `/write` — TÁCH khỏi /author 2026-07-16 theo yêu cầu user):
  outline (nạp từ dropdown qua `/api/outlines`, hoặc dán tay) × tác giả từ library × độ dài ×
  LLM → `script.md` theo chương (chống trôi giọng, checkpoint/resume) → `validate` đo %.
  Mỗi lần viết còn lưu **bản ký biến** `history/<ngày-giờ>-<user>.md` (không đè bản cũ — C2b).
  **/author và /write là CÙNG một `board.html`** — server tiêm `window.CU_MODE` để ẩn tab kia
  (`_vp_board`, luật C1: không tách đôi file). Chạy standalone (voiceprofile.server) → đủ 2 tab.
- **PHÂN QUYỀN 2 vai (2026-07-16):** `roles.json` (ngoài git), thiếu tên = creator.
  | Vai | Được gì |
  |---|---|
  | **Creator** (mặc định) | 3 công cụ: /outline · /author · /write |
  | **Leader** | Creator + 👥 Quản lý (/manage: nhật ký, token, bảo mật) |
  | **Admin** (ADMIN_USERS) | đứng TRÊN vai — thêm ⚙ Cài đặt (API key, thành viên, GÁN QUYỀN) |
  Cổng: `_can_manage` (admin/leader) cho /manage + GET /api/users + /api/activity +
  /api/history-file; **POST /api/users (thêm/xoá/reset/GÁN QUYỀN) chỉ admin**. Đổi quyền hiệu
  lực NGAY (đọc roles.json mỗi request). Thẻ trang chủ + dải whoami hiện theo vai. Local không
  ADMIN_USERS → mọi cổng mở (máy cá nhân). Đã verify ma trận 3 vai bằng user thật trên VPS.
- **Vận hành, 2 trang:** **👥 Quản lý** (`/manage`, leader+) = nhật ký · token · bảo mật.
  **⚙ Cài đặt** (`/settings`, admin) = 2 tab: "API key & Cookies" + "Thành viên & quyền"
  (khóa mời, tạo tài khoản, đổi mật khẩu/xoá, dropdown Creator/Leader).
  *Lịch sử đổi chỗ để khỏi lẫn:* khóa mời Cài đặt→Quản lý (07-15) rồi CẢ khối thành viên
  Quản lý→Cài đặt (07-16, user chốt cùng phân quyền). `fmtT` phải ở lại SETTINGS_HTML
  (khối Cookies dùng chung).
- **Bề rộng trang cho màn 16:9** (user chốt 2026-07-17 — "đừng co cụm giữa màn hình"):
  Cài đặt **1.200px + lưới `grid2` 2 cột** (key‖cookies · mời‖tạo tài khoản) · Quản lý 1.280 ·
  Trang chủ 1.100 với **3 thẻ/hàng** · Author/Writing 1.200 · board Outline giữ 1.460.
  Màn <960px tự gập 1 cột. Trang form (invite/403/logout) cố ý giữ hẹp.
- **Trang `/write` mang danh tính riêng "Content Writing"** (user chốt 2026-07-17): JS trong
  `CU_MODE==='write'` đổi title/brand/sub; `/author` chỉ còn "Extractor". Selector phải scope
  `header .eyebrow` — class trùng với nhãn "Log" phía dưới.
- **Gói UX board Outline (user duyệt 5 lỗi 2026-07-21, code 2026-07-22):** ① board theo
  user + pipeline theo run (chi tiết ở C2); ② cột phải `position:sticky` + `max-height:100vh` — list cluster trái dài gấp nhiều lần,
  không giới hạn cao thì slot kéo-thả trôi khỏi màn hình. **Sửa 2026-07-23: CHỈ `.panel`
  slot cuộn nội bộ (`flex:1;min-height:0;overflow-y:auto`), khối outline.txt + Copy GHIM
  ĐÁY luôn hiện (`flex:none`, pre cao ≤32vh)** — bản đầu cho cả cột cuộn làm khung txt
  chui xuống dưới thanh cuộn vô hình, user tưởng mất tính năng copy. Sửa TRỰC TIẾP nội
  dung txt chưa từng tồn tại (bản lưu cũ cũng chỉ pre+Copy); user bảo TẠM CHƯA làm —
  nếu làm phải thiết kế "sửa tay thì khoá ghép từ picks" (file bị ghép đè sau mỗi thao tác); ③ bảng cluster có badge vị trí
  pick (`pickBadge`: → HOOK / → C3 / → ENDING / ↳ ý con · tên chương); ④ cụm gộp lưu
  `merged_sources` (tên cụm GỐC, gộp-chồng kế thừa — `s4c_consolidate`); board hiện
  "Gộp từ: A · B · C" ở chip title + hàng detail + oitem; cụm gộp TRƯỚC 07-22 không có
  tên nguồn (hiện "(cụm gộp cũ)") — không truy hồi được, đừng cố; ⑤ nav 2 board — bản đầu ẩn link
  trang đang mở, user chốt lại NGAY trong ngày (2026-07-22): **hiện ĐỦ 4 tab ở mọi trang,
  đúng thứ tự "Trang chủ · Outline Board · Writing · Author Extract"** (bỏ số ①② vì thứ tự
  user chọn không theo số), tab đang mở tô nền accent (`.newbtn.here` / `navHere()`);
  standalone vẫn ẩn /write //author vì voiceprofile.server không có route đó.
  **Vị trí: thanh `.topnav` RIÊNG dòng đầu, canh TRÁI, `padding-right:260px`** (chốt lần 2
  cùng ngày sau screenshot bị đè): dải whoami là `position:fixed` góc phải MỌI trang —
  đặt nav phía phải header là chui gầm dải; đừng dời nav về header lại.
  **Chốt lần 3 (mockup user cùng ngày): board Outline nhập luôn 🍪 Cookies +
  ＋Video Outlier vào cụm topnav** — 6 nút liền nhau canh trái, header dưới chỉ còn
  tiêu đề · số liệu wave · ô 📁 run · trạng thái lưu. /author //write không có 2 nút
  đó nên topnav của chúng vẫn 4 tab.
- **Thư viện hiện "✍ người viết"** (user yêu cầu 2026-07-22): `created_by` = thành viên
  team chạy extract, chảy CU_USER (cli) / X-Remote-User (detect-corpus) → `library/index.json`
  → `/api/library` → dropdown "Tác giả (thư viện)" + dòng ghi chú (màu theo palette,
  var(--accent)). Người extract SAU CÙNG đứng tên; entry cũ đã backfill từ
  `admin/history.jsonl` trên VPS (A007/A008=ngocth; A001–A004 có trước sổ per-user —
  không có bằng chứng thì ĐỂ TRỐNG, không bịa).

**Hai hợp đồng dữ liệu nối 3 khối (đổi format là gãy dây chuyền):**
`outline.txt` (`Title:` / `HOOK` / `CHAPTER n — <tên>` / `ENDING`, xem METHODOLOGY §S5)
và `library/index.json`.

> **Cạm bẫy đã trả giá — thêm dòng vào `outline.txt` là việc NGUY HIỂM.** `parse_outline`
> săn từ khoá mốc (`hook|chapter N|end|intro|outro…`) ở **bất kỳ đâu** trong text (cố ý, để
> chịu được outline viết liền một khối). Nên mọi dòng VĂN XUÔI thêm vào outline đều có thể bị
> hiểu là mốc phần: CTA đời thường *"Watch till the end!"* / *"Comment below your intro song"*
> xé outline thành các phần **MA** ⇒ sai số phần ⇒ sai phân bổ độ dài ⇒ kịch bản vượt ký tự
> (lỗi thật 2026-07-15, do chính dòng `CTA:`/`Angle:` thêm hôm 07-14). Đã chặn bằng
> `_mask_meta` (che dòng `Angle:`/`CTA:` khi TÌM mốc; brief vẫn cắt từ text GỐC nên nội dung
> còn nguyên). **Che phải dùng ký tự KHÔNG PHẢI khoảng trắng** — `_SECTION_MARK` có `\s*`
> trước từ khoá nên nó nuốt trọn khoảng trắng vừa che vào mốc kế tiếp, kéo luôn dòng
> `Angle:`/`CTA:` ra khỏi brief. Thêm loại dòng metadata mới ⇒ phải thêm vào `_META_LINE`.

- **Lệnh thiết yếu:**
  - Cài: `python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev,llm,embed]"`
    (extra `embed` = fastembed cho S4; nặng, lần đầu lâu).
  - Test: `.venv/bin/python -m pytest -q` (bộ voiceprofile + bộ oe trong `tests/oe/`, phải
    xanh trước khi báo xong việc). **Luôn dùng `.venv/bin/python` của CHÍNH repo này** —
    `python3` trần trên máy user trỏ vào venv của folder backup `../Author Extract/` ⇒ test
    xanh trên code SAI (dính 2026-07-15, xem C3).
  - Giao diện: `Start.command` hoặc `.venv/bin/content-ultimate` (`--no-browser` cho
    headless; `--run` chọn run board Outline, mặc định run mới nhất có data).
  - Pipeline outline không GUI: `python3 run_all.py videos.txt --run <tên>`.
  - CLI giọng văn: `.venv/bin/voiceprofile` — 6 lệnh `build`/`rhetoric`/`dataset`/
    `clonekit`/`write`/`validate`.
  - **`.env` = KHO KEY** (không phải công tắc): key nhiều provider cùng lúc
    (`ANTHROPIC_API_KEY`/`GLM_API_KEY`) + key Outline (`TRANSCRIPT_API_KEY`,
    `YOUTUBE_API_KEY`, `GLM_BASE_URL`, `LLM_PROVIDER` cho `oe.llm`) + `ADMIN_USERS`.
    Trên VPS admin KHÔNG soạn .env tay (trừ `ADMIN_USERS`): nhập key qua tab
    **⚙ Cài đặt** (`/settings`, ghi vào .env qua `merge_env`). Chọn LLM là việc của
    dropdown UI / `--provider --model`, KHÔNG phải của `.env`.
  - `videos.txt` chứa API key YouTube thật (convention trộn key + URL) — không commit.
- **Bản đồ code:** xem docstring đầu mỗi module. Điểm cần nhớ:
  - `contentultimate/server.py` — kế thừa handler `voiceprofile.server`, mount thêm
    route oe + `/api/outlines` + `/api/outline-load` + **`/manage` & `/api/users`,
    `/api/activity`, `/api/history-file`** (tab Quản lý — xem C2b). Trang chủ HOME inline.
  - `voiceprofile/` — nguyên trạng Author Extract (cli, quant, rhetoric, generator,
    validate, library, llm đa provider, server + board.html, gui Tkinter dự phòng)
    + `usage.py` (sổ ghi token/job/truy cập dùng chung — `oe/llm.py` cũng ghi vào đây)
    + `lengthlab.py` (test lab — **ĐÃ THỬ, RA RÁC, mặc định TẮT**; xem luật A5 trước khi bật; CLI `lab`;
    ghi khối `length_lab` vào `profile.json`, `generator` đọc qua `_chars_per_idea`).
  - `oe/` — Outline Extract (s1→s5, common, llm GLM riêng, board.html) + `s4c_consolidate.py`
    (`merge_clusters` — gộp tay), `cta.py` (`generate_cta` — sinh CTA theo chapter), `suggest.py`
    (✨ gợi ý cả outline). `common.ROOT` = gốc repo; `runs/` ở gốc repo. **Server THẬT của board là
    `contentultimate/server.py`** (route `/oe/api/*`, tái dùng `oe.s5_server._board_data/_save/
    _merge` + `oe.cta`) — thêm route board phải sửa Ở ĐÓ, không chỉ `oe/s5_server.py`.
    `_board_data` gọi `_ensure_angle` (backfill `angle` + tính lại `role` từ beats mỗi lần mở).
  - Trùng lặp có chủ đích chưa hợp nhất: 2 `llm.py` (voiceprofile đa provider ↔ oe GLM),
    2 `board.html` — chỉ hợp nhất khi thực sự đụng tới (Luật C1).

---

## Quyết định thiết kế đã chốt (đừng lật lại nếu không có lý do)

Nhật ký đầy đủ ở [`DEVLOG.md`](./DEVLOG.md). Bất biến của Writer (Khối 3):

- **Mục tiêu là ĐỘ HAY của văn, điểm % chỉ tham khảo** (memory `goal-is-quality-not-score`).
  Không tối ưu theo điểm.
- **Độ dài kiểm soát bằng PHÂN TẦNG ĐỘ SÂU** (chốt 2026-07-09 bản gốc "ngân sách ý", **sửa
  2026-07-14 sau khi user báo tool CẮT Ý trong outline của họ**). Nguyên lý gốc vẫn đúng: LLM
  không đếm được ký tự nhưng đếm Ý rất tốt (thí nghiệm Norway: 3 ý → 3.735 ký tự, giữa vùng
  ngọt); và **không bao giờ NÉN văn**. Sai lầm đã sửa: bản cũ coi **độ sâu là hằng số** (mọi ý
  ~1.250 ký tự) nên chỉ còn 2 cần gạt — bỏ ý hoặc nén văn — mà nén bị cấm ⇒ buộc **vứt ý của
  user**. Công thức đúng: **độ dài = Σ(độ sâu từng ý)**, mỗi ý nhận một MỨC khai triển:
  **FULL** (~1.250) · **MENTION** (`CHARS_PER_MENTION`≈110, một câu lồng vào mạch).
  **Ý yếu nhất vẫn xuất hiện ở mức MENTION — KHÔNG BAO GIỜ bỏ ý của user.**
  *"Nhắc lướt" ≠ "nén văn"*: mention là một thể văn cố ý; nén là ép khai triển đầy đủ thành
  đoạn đặc nghẹt (vẫn cấm, cho các ý FULL).
  - Tầng 1 (`outline_scope_report`, `/api/outline-check`): `depth_plan(n_ý, target)` → báo
    **KẾ HOẠCH** (`scope_plans`, board hiện với ▸): "8 ý → 4 FULL + 4 nhắc lướt ≈ 5.400". Chỉ
    **cảnh báo** (`scope_warnings`) khi *ngay cả mức tối thiểu* vượt ×1.15 → user quyết nâng
    mục tiêu hay tự bớt ý (luật A3 — tool KHÔNG âm thầm cắt).
  - Tầng 2 (`build_section_prompt`): `DEPTH PLAN` — k ý FULL (Python tính, kiểm soát độ dài) +
    **"EVERY OTHER idea MUST STILL APPEAR, one sentence each / NEVER drop an idea"**.
    KHÔNG nhắc con số ký tự. (Câu cũ *"leave the rest out entirely"* đã bỏ — chính nó vứt ý.)
  - Tầng 3 (`build_scope_cut_prompt`): vượt trần ×1.15 → MỘT vòng **HẠ TẦNG** (FULL → một câu),
    *không xoá ý* (Python đo, tối đa 1 lượt LLM phụ/phần). KHÁC Module 6 auto-revise theo
    điểm — vẫn không tối ưu điểm %. **Tầng 2 và Tầng 3 phải gọi CHUNG `depth_plan`** — trước
    2026-07-15 Tầng 3 gọi thẳng `idea_budget` nên đòi lại đúng cái k gây vượt ⇒ cắt xong vẫn vượt.
  - **Trần Tầng 3 = MỤC TIÊU CỦA CHÍNH CHƯƠNG** (sàn `CHAPTER_MIN_QUALITY`), **không phải**
    hằng số chung. `CHAPTER_WARN_CHARS`=4.000 là ngưỡng **chất lượng giọng** (dài hơn → trôi
    giọng) — dùng nó làm cam kết **độ dài** là nhầm vai, và đó là **nguyên nhân chính** user báo
    "over ký tự quá nhiều" (2026-07-15): chương mục tiêu 3.000 phải viết tới 4.600 (+53%) mới bị
    đụng ⇒ đo thật 3.323 (+11%) và 4.092 (+36%) **đều lọt** ⇒ 6 chương = 21.300/18.000 (**+18%
    âm thầm**). Sàn 2.500 để chương mục tiêu ngắn không bị cắt thành văn cụt (ca đó đã có cảnh
    báo cấu trúc riêng).
  - **`depth_plan` chọn k sao cho ước lượng GẦN target nhất** — nhắc lướt **ăn vào** ngân sách,
    không cộng thêm. Bản đầu (2026-07-14) lấy thẳng `k = idea_budget(target)` rồi cộng mention
    lên trên ⇒ **vượt có hệ thống**, càng nhiều ý của user càng nặng: đo thật target 3.500 +
    10 ý = 4.520 (+29%), 12 ý = +35% — đúng cái user báo "over ký tự quá nhiều" (2026-07-15).
    Sau khi sửa: 3.500 + 10 ý = 3.380 (−3%). Sàn `min_k` (2 với chapter, 1 với end) giữ chất
    lượng; khi cả sàn vẫn vượt thì **Tầng 1 cảnh báo để user quyết** — tuyệt đối không tự cắt ý (A3).
  - **Sức chứa 1 chương**: `idea_budget` trần **4 FULL**, nhưng 4 FULL cần ≥4.375 ký tự trong khi
    `CHAPTER_WARN_CHARS`=4.000 ⇒ **thực tế tối đa 3 FULL**/chương; MENTION chỉ bị chặn bởi ngân
    sách → ~10 ý/chương là mức dùng thật. **Sức chứa THẬT phụ thuộc tác giả** — `depth_plan`/
    `idea_budget` nhận `chars_per_idea` từ `length_lab` của profile (luật A5).
  - **Nhắc lướt nhiều = bỏ ý trá hình.** `depth_plan` làm kế hoạch "vừa khuôn" bằng cách hạ thêm ý
    xuống nhắc lướt: 10 ý/chương 3.000 → **8 ý (80%) chỉ một câu**, và cảnh báo IM LẶNG (est 3.380
    < ngưỡng 3.450). "Không bỏ sót" trên giấy nhưng chương đọc ra là **danh sách**. Đây là lý do
    chế độ **1 cluster chính (2-3 brief) + add-on** được chốt: nó ép mật độ ý về mức mà "viết hay"
    và "không bỏ sót" cùng tồn tại được. **Ba mục tiêu của user (hay · đúng ký tự · không sót)
    MÂU THUẪN nhau từ ý thứ 3 trở đi** — chương 3.000 chỉ cõng công bằng được ~2 ý. Bắt buộc bỏ
    một trong ba; **A3 nói USER chọn, không phải tool tự chọn** (hiện tool luôn tự chọn "nhắc lướt").
- **HOOK cũng có trần độ dài** (`HOOK_CHARS_MAX`, vòng cắt riêng `build_hook_cut_prompt` — KHÔNG
  dùng `build_scope_cut_prompt` vì hook là tầng platform, không phải giọng tác giả). Trước
  2026-07-15 hook bị **loại khỏi** chốt Tầng 3 (`if sec.kind in ("chapter","end")`) nên viết dài
  bao nhiêu cũng không ai chặn.
- **Brief của HOOK là NGUYÊN LIỆU, không phải bảng kiểm.** Từ 2026-07-14 brief hook kéo theo dòng
  `Angle:`/`CTA:` (compose.py) — gọi chúng là *"Points to hit"* là bắt LLM phủ kín ⇒ hook phình,
  phá quy ước 250-500. Prompt phải nói rõ: lấy **một** mạch mạnh nhất, **cố ý bỏ** phần còn lại.

> **Đã thử và bác bỏ (Pillar, test lab, …) — xem LUẬT A5.**
- **Hook = tầng platform thuần, TÁCH khỏi giọng tác giả** → **xem LUẬT A4** (luật cứng,
  user đã nhắc 2 lần). Chapter/End mới giữ giọng tác giả.
- **Sinh theo chương, chương là ĐƠN VỊ BẢO TOÀN**; neo giọng (exemplar+moves ở system)
  + nối mạch (đuôi 60 từ chương trước). Vùng ngọt ~2.500-4.000 ký tự/chương (trần là
  ngưỡng kích hoạt Tầng 3 ở trên).
- **Phân bổ:** Hook ~375 ký tự, End clamp 7%/500-1200, Body chia đều.
- **Checkpoint/resume:** `{out}.progress.json` khóa theo hash outline; `write --continue`.
- Bất biến của Board (Khối 1): **tool trình bằng chứng, USER pick** — không score tổng,
  không auto-sort "độ tốt", không "khuyên chọn" (xem Luật A3).
- **Board 2026-07-14 (giữ nguyên hành vi nếu không có lý do):**
  - **Gộp tay** (`s4c_consolidate.merge_clusters` + `_merge` server): user chọn ≥2 → LLM gộp
    GIỮ MỌI sắc thái (prompt ép nêu đủ các góc, thà dài hơn mất ý); Python union bằng chứng
    (coverage/peak/pos/videos/gids), `merged_from` cộng dồn. Cụm gộp lên ĐẦU list, **KHÔNG tự
    vào outline** (user đọc rồi tự pick — luật A3), gộp-chồng được.
  - **`angle`** (S4 `s4_cluster`): summary của beat peak MẠNH NHẤT trong cụm = góc gốc tại điểm
    tua-lại nhiều nhất. Vào `outline.txt` dòng `Angle:` (chỉ khi ≠ brief) → Author Extract bám
    đúng góc, KHÔNG tự sinh. brief tổng hợp có thể làm mượt; angle giữ bản sắc.
  - **CTA per-chapter** (`cta.py` + `/oe/api/cta`): user quyết chapter nào có CTA → modal to chọn
    từ kho (theo loại) HOẶC ✨ sinh theo brief/angle chapter (LLM). Vào `outline.txt` dòng `CTA:`.
    Kho CTA tuân luật content: không sub/like ở hook, không câu "hết video", advertiser-friendly.
  - **`role`** (hook/body/ending) = beat type + chốt vị trí, NHƯNG **chốt vị trí chỉ khi biết pos**;
    `pos=None` (video thiếu duration) → tin beat type, không demote (nếu không dồn hết về body).
    Board phân vùng theo role; server tính lại role từ beats mỗi lần mở (`_ensure_angle`).
- **HỆ NGUYÊN LIỆU trên board (2026-07-16 — user duyệt mockup rồi mới code):** Python thuần
  trong `oe/board.html`, không tốn LLM, **chỉ báo — không chặn, không tự sửa (A3)**.
  - Vì sao: đo 8 run thật — run tốt GIÃN (khung chương ÷ brief) **5,3-7,9×**, run hỏng
    **10-22×**. Brief mỏng bị bắt viết dài → LLM độn chữ ("văn dài và chán") và **tự chèn nội
    dung user chưa duyệt** — phá hợp đồng bằng chứng. Áp cho MỌI thể loại (Tanzania vs
    Norway/Cape Verde: cùng thể loại, kết cục ngược nhau đúng theo nguyên liệu).
  - **Ô "Độ dài kịch bản"** (`lenInput` → `picks.total_chars`): board trước đây KHÔNG biết tổng
    độ dài (nó nằm bên Writer) nên không thể tính nguyên liệu. Writer đọc lại qua
    `/api/outlines[].total_chars` làm mặc định ô ký tự — 2 nơi không lệch nhau.
  - **Badge 3 mức mỗi chương** (`matInfo`): khung = (tổng − hook 375 − end clamp7%) ÷ số chương;
    cần ≈ khung÷6; màu theo KHOẢNG TRỐNG thật trong dữ liệu (8-10× không có ca nào):
    `✓ <8×` · `⚠ 8-10× cân nhắc` · `● >10×`. Chương đói → **nút ＋ (ý con) phát sáng** — cơ chế
    thêm add-on ĐÃ CÓ SẴN từ trước (extras: kéo cluster vào/gõ tay/kéo chương khác vào để gộp),
    user chưa từng dùng vì không có gì báo khi nào cần. Hằng số là số ĐO chỉnh được, không phải
    chân lý. Nhắc lại quyết định đã chốt: KHÔNG có nút "Hạ mục tiêu" (tổng ghim thương mại).
- **Cảnh báo transcript thô khi nạp corpus** (Extractor, 2026-07-16): `/api/detect-corpus` trả
  `transcript_warnings` (từ `corpus.transcript_warnings()`) → board in ⚠ vào ex_log, cả luồng
  chọn-folder lẫn upload. **Chỉ báo** — user tự dọn folder; KHÔNG có ô tick tự loại file
  (user chốt: bản đầu chỉ cảnh báo).
- **Dropdown LLM = đúng 4 lựa chọn** (yêu cầu team 2026-07-08, `MODEL_CHOICES` trong
  `voiceprofile/llm.py`): Claude Sonnet (`claude-sonnet-5`), Claude Opus
  (`claude-opus-4-8`), GLM 5.0 (**id thật trên z.ai là `glm-5`** — đo endpoint /models),
  GLM 5.2 (`glm-5.2`); lọc theo key có trong .env. Không thêm provider/model vào
  dropdown khi chưa được yêu cầu. Giá trị dropdown `provider:model` → server tách
  thành `--provider --model` (`_provider_args`).
- **Tab ⚙ Cài đặt chỉ quản trị viên thấy** (yêu cầu 2026-07-08): admin = user trong
  `ADMIN_USERS` (.env), nhận diện qua header `X-Remote-User` do nginx basic auth truyền
  (app sau proxy nên header không giả được từ ngoài); `ADMIN_USERS` trống = chế độ máy
  cá nhân, ai cũng là admin. Key sửa qua app bị giới hạn trong catalog `SETTING_KEYS`.
- Trạng thái module chưa build (Author Extract): Module 4 (không cần vì EN→EN),
  6-vòng-tự-sửa, 7 (Quality Oracle), 8 (Experiment Log) — đừng build trước khi được yêu cầu.
  Nợ kỹ thuật Outline: GAPS lọc heuristic còn lẫn câu đùa (fix đúng = 1 lượt LLM phán).
- **CHẶN IP YouTube trên VPS (2026-07-14, thường gặp):** IP datacenter Vultr bị YouTube gắn cờ
  ("Sign in to confirm you're not a bot"). yt-dlp KHÔNG fail hẳn mà lấy được title/view/comment
  nhưng THIẾU player response → `duration=None` + heatmap thiếu → `pos=None` → vùng/cột-vị-trí
  sai. `heatmap.py` tự kèm `--cookies cookies.txt` nếu có, NHƯNG cookies từ IP máy chủ **hết hạn
  nhanh**. Cách chữa (vận hành, không phải code): nút **🍪 Cookies** trên board → dán cookies.txt
  mới (tiện ích "Get cookies.txt LOCALLY", cửa sổ ẩn danh) → chạy lại pipeline. S1 tự **cảnh báo**
  khi duration/heatmap thiếu hàng loạt. Bền hơn: proxy residential/PO-token (chưa làm).

---

## PHẦN A — LUẬT CỨNG (không ngoại lệ, kể cả với việc vặt)

Vi phạm là hỏng kiến trúc hoặc làm bẩn dữ liệu, không phải chuyện style.

### A1. Python đo — LLM hiểu/sinh, không bao giờ đảo vai

**Số liệu là thứ đo được, không phải thứ nghe hợp lý.**

- Mọi con số (đỉnh heatmap, đếm signal, đặc trưng giọng, điểm %) do **Python** tính —
  xác định, tái lập được. LLM chỉ: chia beat, đặt tên cluster, đề xuất moves, viết văn.
  Không bao giờ để LLM "ước lượng" một con số rồi trình bày như đã đo. Áp dụng cho cả
  chính bạn (Claude): muốn biết giá trị trên corpus/run, viết code đo, đừng đoán.
- Mọi nhãn/claim của LLM phải kèm trích dẫn mà Python verify tồn tại thật trong nguồn
  (Module 3b của voiceprofile; verify quote của oe). LLM không tự viết timestamp.
- Các stage oe nói chuyện qua file JSON trung gian (`videos.json → peaks.json →
  beats.json → clusters.json → evidence.json`) — hợp đồng giữa stage, đổi schema phải
  nói rõ.
- **Kiểm chứng mù, không tự chấm:** không dùng văn bản hệ thống sinh ra để chứng minh
  hồ sơ giọng của nó đúng.
- **Self-profile là chế độ mặc định** của Extractor (không có baseline ngành): đặc trưng
  ổn định qua ĐOẠN ~4.000 từ + bền trên held-out, target ±1 SD; có `--baseline-dir` thì
  contrast mode z-score. Chỉ cảnh báo khi corpus < 5 đoạn.
- **Bản quyền:** không tái bản nguyên văn tác giả; dataset nguyên văn chỉ dùng cá nhân/
  nghiên cứu; output gắn nhãn "lấy cảm hứng từ giọng văn [tác giả]".

### A2. Ranh giới dữ liệu & thư mục

**Repo chỉ chứa code. Dữ liệu runtime của user nằm ngoài git.**

- Ngoài git (theo `.gitignore`): `.env` (kho key), `videos.txt` (key thật), `runs/`
  (data sóng), `library/` (sổ đăng ký tác giả), corpus + output do user chọn đường dẫn.
- `sample_data/`, `corpus/baseline_authors/`, `tests/oe/fixture_*` là fixture dùng chung
  — không nhét nội dung tác giả cụ thể, không sửa trừ khi được yêu cầu.
- Không hard-code tên/đường dẫn một tác giả cụ thể vào `src/` hay `tests/`.

### A3. Tool trình bằng chứng — USER pick (Khối 1)

**Board KHÔNG tự chọn outline hộ user. Quyết định thiết kế, không phải thiếu sót.**

- Không gộp cột thành điểm tổng ẩn; không sort sẵn theo "độ tốt"; không "khuyên chọn".
  Auto-pick lúc mở board chỉ là điền sẵn khung sóng (coverage≥2) — user toàn quyền sửa.
- Yêu cầu ngả sang "tool tự pick / xếp hạng / chấm một con số tổng" → dừng, hỏi user.
- Mỗi dòng bằng chứng click xem được đoạn thật (`&t=<giây>s`); số đếm embedding-match
  là **ước lượng dưới**, trình bày đúng như vậy.

### A4. Hook thuộc NỀN TẢNG, không thuộc tác giả

**User đã phải nhắc 2 lần (2026-07-03 và 2026-07-15). Không được hỏi lại, không được
"cải tiến" theo hướng khác.**

- **Hook KHÔNG dùng giọng tác giả.** Không exemplar, không signature move, không câu dài
  văn chương. Hook là **tầng platform thuần**: nhiệm vụ của nó là YouTube — chặn cú lướt,
  mở curiosity loop. `build_hook_prompt` phải giữ system riêng, **không** đụng
  `build_voice_block`. Chapter/End mới là chỗ của giọng tác giả.
- **Adapt theo nền tảng nghĩa là adapt CẢ ĐỘ DÀI:** 250-500 ký tự (~15-25 giây). Con số này
  là một phần của hợp đồng nền tảng, **không phải gợi ý**. Prompt nói 250-500 mà không có
  chốt Python đo lại = không có luật (hook từng bị loại khỏi chốt Tầng 3 → phình 2.400 ký tự
  vẫn lọt, 2026-07-15). Vòng cắt của hook phải là `build_hook_cut_prompt` — KHÔNG bao giờ
  dùng `build_scope_cut_prompt` (cái đó là giọng tác giả + hạ tầng ý).
- **Hook mở MỘT vòng tò mò — không phải bảng kiểm.** Brief của hook (kể cả `Angle:`/`CTA:`
  kéo theo) là **nguyên liệu để chọn**, không phải danh sách phải phủ kín. Bắt hook nói hết
  mọi ý = hook phình và hết là hook.
- Hook **không scale theo tổng độ dài**: kịch bản 10.000 hay 30.000 ký tự thì hook vẫn
  `HOOK_CHARS`. Đừng "cân đối" nó theo tỷ lệ.

### A5. Độ sâu giao bằng Ý — KHÔNG bằng số câu, KHÔNG bằng số ký tự

**Chốt 2026-07-16 sau 4 lý thuyết bị chính dữ liệu bác bỏ (~110 chương thật, ~2,1M token).
Prompt `build_section_prompt` đang chạy là thứ TỐT NHẤT đã đo. Đừng "cải tiến" nó nếu
không có số liệu bác bỏ được bảng dưới.**

- **Bảng đo quyết định** (Ventures × GLM · nội dung Kellogg thật · 5 mẫu/biến thể · mục tiêu
  3.000 · toàn văn ở `THI-NGHIEM-do-dai.md` trên máy user — **ngoài git** theo luật A2, các con
  số dưới đây là bản ghi chính thức):

  | Cách giao độ sâu | Ký tự (tb) | Dao động | Số câu viết ra |
  |---|---|---|---|
  | **Ý** — `"AT MOST k ý FULL + mỗi ý còn lại MỘT CÂU"` (**hiện tại**) | 3.289 (+10%) | **±7%** | 9·9·11·12·13 |
  | Số câu — `"viết ĐÚNG 13 câu"` | 3.581 | ±20% | 14·14·14·14·14 |
  | Chủ đạo 5 câu + mỗi phụ 2 câu | 3.197 | **±46%** | 15·14·**5**·14·13 |

- **NGHỊCH LÝ CỐT LÕI — đọc kỹ:** ép số câu thì LLM khoá số câu **hoàn hảo** (14×5 lần) nhưng
  **kéo dãn từng câu** (196→300 ký tự) để nhét vừa nội dung ⇒ **ký tự lỏng ra (±20%)** và
  **user chấm: "câu văn quá dài, mất mạch cao trào lên xuống"**. Khoá cái vỏ thì méo cái ruột.
  Ngược lại, giao bằng **Ý** không hề nhắc câu (9→13 câu tuỳ ý) nhưng **ký tự chặt nhất (±7%)**
  và giữ được nhịp. **Thứ ta cần kiểm soát là KÝ TỰ (trần 4.000), không phải câu.**
- **Chia mệnh lệnh thành nhiều số càng tệ**: biến thể "chủ đạo 5 + mỗi phụ 2" ra **±46%**, có mẫu
  chỉ 1.399 ký tự/5 câu. Càng nhiều ràng buộc số đếm, LLM càng dễ gãy.
- **Mệnh đề `"EVERY OTHER idea MUST STILL APPEAR: … ONE clear sentence"` là thứ đang giữ độ dài.**
  Bỏ nó ra thì cùng nội dung nở từ 3.289 → 5.812 (**+77%**). Đừng bao giờ gỡ mệnh đề này.
  *(Bài học phương pháp: mọi con số "hệ hiện tại dao động ±27%" trước 07-16 là **SAI** — chúng
  đo trên một bản prompt tự chế đã làm rơi mệnh đề này. **Chuẩn đối chiếu phải gọi thẳng
  `build_section_prompt`**, không được chép tay lại.)*
- **"MỘT CÂU" cho mức nhắc lướt thì VẪN ĐÚNG** — đó là một **thể văn ngắn có chủ đích**, đo được
  98-108 ký tự trên 2 nội dung khác hẳn nhau. Cấm là cấm dùng **số câu để định cỡ văn khai
  triển**, không phải cấm mức nhắc-lướt-một-câu.
- **`CHARS_PER_IDEA=1250` là số KHỚP TỪ n=1** (Norway) đem áp cho mọi tác giả/model/chủ đề.
  Nó **không phải hằng số của "một ý"** — đo lại: 997 (chủ đề hư cấu) → 1.846 (cluster thật).
  Đổi theo **hình dạng prompt** VÀ **độ quen thuộc của chủ đề với model**. Nó chỉ là con số để
  **Python ước lượng**; đừng bao giờ nói ký tự cho LLM.
#### GỐC RỄ THẬT của "câu văn phẳng và quá dài" (tìm ra + vá 2026-07-16)

**Cả ngày 07-15/16 tôi đo độ dài CHƯƠNG và xoay cách giao độ sâu. Lỗi không nằm ở đó — nó
nằm ở KHỐI 2 (hồ sơ giọng), từ trước khi Writer chạy. Mọi lý thuyết đều xây trên một hồ sơ
đã hỏng.**

Chuỗi nhân quả, đo trên corpus thật của user:

```
Corpus Ventures 5 file — 2 file là transcript YouTube THÔ (0,1 dấu câu/1000 ký tự)
  → split_sentences trả về ĐÚNG 1 "câu" = cả file (14.799 ký tự)
  → _sliding_paragraphs PHUN nguyên cục ra làm exemplar
     (bug: `out.append` chạy TRƯỚC khi kiểm `max_words=120` ⇒ giới hạn vô hiệu)
  → sentence_len_mean = 1085 (hư cấu; file sạch cho 13.4)
  → select_exemplars đi tìm đoạn KHỚP 1085 → chọn đúng 2 cục thô đó làm "giọng tác giả"
  → LLM được xem cục 14.799 ký tự không dấu chấm và bảo "đây là giọng"
  → LLM viết 191-307 ký tự/câu, đều đều, không lên xuống
  → user: "câu văn phẳng và quá dài"
```

**Lỗi tự khuếch đại**: thống kê hỏng → chọn exemplar khớp thống kê hỏng → càng củng cố.

- **Ventures THẬT viết 78-92 ký tự/câu** — nhất quán trên 3 file sạch (86.000 ký tự:
  Russia 78 · Serbia 92 · Uzbekistan 85). Tool sản xuất **191-307** = **gấp 2,5-4 lần**.
- **Nhịp thật có lên xuống**: `44 → 136 → 150 → 42 → 23`. LLM viết đều 225-300 mọi câu ⇒ phẳng.
  Đó chính là "mạch cao trào" user nói mất.
- **Đã vá 3 chỗ (đều là BỚT, không thêm cơ chế):**
  1. `_sliding_paragraphs` kiểm `max_words` TRƯỚC khi phun; cửa sổ vượt trần bị BỎ.
     *(Test `test_exemplar_distance_not_dominated_by_large_scale_feature` từng **dựa vào chính
     bug này** — fixture `author_like * 3` nối thiếu khoảng trắng ⇒ 1 câu 42 từ > max_words=40.
     Vá bug làm test đỏ; đã sửa fixture.)*
  2. `corpus.transcript_warnings()` + `punctuation_density()` — **BÁO** file transcript thô
     (ngưỡng `MIN_ENDERS_PER_1K=4`; sạch 11-13 vs thô 0,1 — hai cụm cách xa nhau).
     Tool báo, **user quyết** (A3) — không tự bỏ file của user.
  3. `YOUTUBE_RULES["chapter"]` **bỏ** khẳng định *"long, clause-rich sentences… the author's
     LONG sentences ARE the voice"* — nó áp phong cách đó cho MỌI tác giả. Nhịp câu phải đến từ
     **exemplar thật (show, đừng tell)**; luật nền tảng chỉ nói về CẤU TRÚC (loop, nhịp chương).
- **Hồ sơ dựng lại từ 3 file sạch**: `sentence_len_mean` 1085 → **13.4 từ/câu**; exemplar
  14.799 ký tự/1 câu → **570 ký tự/6 câu (94 ký tự/câu)**.
- **⚠⚠ ĐỪNG DỰNG LẠI PROFILE TỪ CORPUS TRANSCRIPT — đã thử, USER BÁC BỎ.**
  Dựng lại hồ sơ Ventures từ 3 file "sạch" cho `sentence_len_mean` 1085 → **13.4 từ/câu** và
  exemplar 14.799 ký tự/1 câu → **570 ký tự/6 câu**. Số liệu đẹp. **Nhưng user đọc và loại:
  "hồ sơ cũ ok hơn, câu văn không bị cộc lốc, không bị phẳng, liền mạch, logic."**
  Đo có kiểm soát (cùng nội dung, chỉ đổi hồ sơ): CŨ **219** ký tự/câu · MỚI **102** → cộc lốc.
  **Lý do sâu:** corpus là **transcript LỜI NÓI**, kể cả file có dấu chấm. 63-92 ký tự/câu đó là
  **nhịp NÓI**, và dấu chấm do người/máy gõ lại đặt — không phải thiết kế tu từ của tác giả.
  **Không thể học nhịp VĂN VIẾT từ bản ghi LỜI NÓI.** Hồ sơ hỏng cả hai đường: để thô → 1085
  (hư cấu); chấm câu lại → 63 (nhịp nói). Cả hai đều không phải nhịp văn.
  **Sự thật khó chịu: bug 14.799 ký tự đang VÔ TÌNH GIÚP** — nó ép LLM viết câu dài có mệnh đề
  phụ, nối ý = thứ user gọi là "liền mạch, logic". Vá bug thì đúng kỹ thuật nhưng **hỏng đầu ra**.
  ⇒ **Giữ nguyên profile Ventures đang chạy.** Hai bug fix (`max_words`, `transcript_warnings`)
  vẫn đúng và vẫn giữ trong code — nhưng **chỉ an toàn cho corpus VĂN VIẾT thật**. Corpus
  transcript thì đừng dựng lại.
- **"Giống tác giả" ≠ "đọc hay".** Hồ sơ MỚI bám tác giả thật sát hơn (CV nhịp câu 0.61 vs
  0.64 của tác giả; hồ sơ CŨ chỉ 0.44) — **vẫn bị loại**. Đo độ giống không thay được người đọc.
- **BÀI HỌC PHƯƠNG PHÁP (đắt nhất):** luật B1 nói *"data ngoài kiểm soát (format transcript…)
  phải kiểm bằng chạy thử"*. Transcript **là** data ngoài kiểm soát và **không ai kiểm** — nên
  cả một ngày thí nghiệm về độ dài chương đều xây trên hồ sơ hỏng. **Nghi ngờ dữ liệu đầu vào
  TRƯỚC khi nghi ngờ cơ chế.** Nhưng cũng: **dữ liệu hỏng không có nghĩa sửa nó là đúng** —
  phải để USER chấm đầu ra, vì đây là bài toán chất lượng văn, không phải bài toán số.

#### ĐÃ THỬ VÀ BÁC BỎ — đừng làm lại (mỗi cái đều tốn ~20-40 chương thật)

1. **Outline khai báo `Pillar:`/`Angle:`/`+ ý thêm`** (2026-07-15). Chẩn đoán đúng
   (`estimate_ideas` bịa ý: brief 588 ký tự có 3 nhịp bị đếm thành **10 ý**), nhưng đo thật
   **tệ hơn hẳn**: hiện tại `[3323, 4092, 3235]` tb 3.550 (+18%); 3 thiết kế Pillar độc lập ra
   **+65% / +74% / +90%**. Lý do: `"AT MOST k ý"` là **ràng buộc** (LLM tuân theo), còn
   `"PILLAR — khai triển đầy đủ"` + mục `ANGLE` riêng là **lời mời nở ra**. Ý ma cũng **không
   đổi kết quả**: 10 ý đoán → k=2; 4 ý khai báo → cũng k=2.
2. **Test lab đo `chars_per_brief` per-author** (`lengthlab.py`, CLI `lab` — code vẫn còn,
   **mặc định tắt**). Chạy **2 lab đầy đủ = 40 chương**, cả hai đều **RA RÁC**:
   - *Fixture hư cấu*: `211 ký tự/brief · 501 ký tự/add-on` — add-on (MỘT CÂU) không thể dài
     gấp 2,4 lần brief đầy đủ. Trên chủ đề model không biết, nó viết ~2.000-2.650 **bất kể cấu
     hình** ⇒ 4 ô gần bằng nhau ⇒ khớp 2 ẩn ra số vô nghĩa. **Nó đã kịp ghi số rác vào profile
     thật** → phải khôi phục từ backup → từ đó có cổng chặn `_sane`.
   - *Cluster thật (Kellogg)*: sửa được lỗi fixture (3.692 khớp 3.531 đo tay, +5%) nhưng **vẫn
     rác**: 4 ô dao động **±31% / ±30% / ±79% / ±41%**, cổng chặn từ chối.
   - **Lý do gọn nhất:** hai ô sạch nhất cho tín hiệu `+456 ký tự/brief` nhưng nhiễu `±567`.
     **Nhiễu lớn hơn tín hiệu** ⇒ cần vài chục mẫu/ô ⇒ hàng trăm chương/tác giả. Không đáng.
   - Mô hình tuyến tính cũng sai: cùng thao tác "thêm 1 brief" cho `+456` (không add-on) vs
     `+1015` (có add-on) — lệch 2-3 lần ⇒ `a×brief + b×addon` không mô tả đúng thực tế.
   - **Cổng chặn `_sane` phải giữ**: `chars_per_brief ≥ 400`, `chars_per_addon ≤ ½ brief`.
     Không đạt ⇒ KHÔNG đặt hằng số, gắn cờ `unreliable`, Writer rơi về mặc định. **Thà không
     có hằng số còn hơn có hằng số sai** — số rác từ lab chui thẳng vào kế hoạch Writer.
   - Nếu vẫn muốn chạy lab: nguyên liệu **phải là cluster thật trong `runs/`**
     (`pick_lab_material`), cấu trúc **MỘT cluster chính → briefs = các NHỊP của nó**
     (`split_sentences`), addons = **câu đầu của cluster khác**. KHÔNG lấy 3 cluster khác nhau
     làm 3 brief. Chưa có run nào ⇒ lab **từ chối chạy**, không bịa fixture.
   - *Còn đứng:* hằng số **add-on ổn định qua nội dung** (108 vs 98) — một câu vẫn là một câu.
     `picks["extras"]` **rỗng ở mọi run** — user chưa từng dùng add-on, không có dữ liệu thật.

3. **Giao độ sâu bằng SỐ CÂU** (2026-07-16) — `"viết ĐÚNG N câu"` / `"chủ đạo N câu + mỗi phụ
   M câu"`. **User đọc văn và loại thẳng: "câu văn quá dài, mất mạch cao trào lên xuống."**
   Số liệu khớp với cảm nhận đó: LLM giữ đúng số câu bằng cách **kéo dãn câu** (196→300 ký tự).
   Xem bảng ở đầu A5. **Đừng làm lại dưới bất kỳ biến thể nào** (khoảng "8-10 câu", số chính xác,
   chia theo chủ đạo/phụ — đã thử cả ba).

#### Vòng NỞ — Tầng 3 chiều ngược (CÀI 2026-07-17, khép việc 4)

Chương viết ra **hụt** so khung (hồ sơ giọng viết ngắn — đo thật: A008 exemplar 1.164 ký tự
→ hụt đều −34%, trong khi cùng ngày A003 +11%, A007 +6%). Lệch là **bệnh toàn hệ, cả 2
chiều, kể cả tác giả tốt** (A003 dao động −9%..+113%) ⇒ cần bộ điều tốc 2 chiều theo TỪNG
BÀI, không chỉ sửa hồ sơ. Thiết kế chốt sau vòng phản biện 4 phản đề (mỗi phản đề thành
một bộ phận):

```
Sau vòng cắt, chỉ CHAPTER:
  hụt = viết ra < khung × EXPAND_FLOOR(0.8)
  ├─ hụt + giãn brief > EXPAND_STARVING(10×) → KHÔNG nở (nở khi đói = ép LLM bịa nội dung
  │    user chưa duyệt — phá hợp đồng A3); log "thêm add-on trên board"
  ├─ hụt + đủ nguyên liệu → tối đa EXPAND_MAX_ROUNDS(2) lượt:
  │    build_expand_prompt (đòn bẩy TỶ LỆ — lệnh đếm số ý bị LOẠI: mẫu 812 ký tự phá 57% văn)
  │    nhận nếu: dài hơn & kept_ratio ≥ EXPAND_KEPT_MIN(0.7) & ≤ trần cắt 4.600 → đo lại
  └─ cuối bài: ≥ nửa số chương phải nở → cảnh báo "hồ sơ giọng viết NGẮN hệ thống" (gốc rễ
       ở exemplar — sửa hồ sơ thì hết trả phí nở mỗi bài)
```

- Số đo đỡ lưng từng hằng số: `0.8` (tác giả khỏe thấp nhất −9%, Vietnam 47-78% — tách sạch);
  `≥0.7` kept (đo thật 89-100%); `2 lượt` (hụt 53% có lần 1 lượt về −1%, có lần chỉ về −26%
  — đo lại rồi mới quyết lượt 2); `10×` (ngưỡng đỏ board).
- `kept_ratio` = % câu cũ (>40 ký tự, khớp 60 ký tự đầu) sống sót — chống "nở" bằng viết lại.
- Chi phí: chỉ chương hụt trả 1-2 lượt; tác giả khỏe trả 0 (luật C3).

#### Đo được là CÓ tác dụng (chưa code)

- **Vòng sửa theo TỶ LỆ** *(chiều NỞ đã cài ở trên; chiều CẮT-theo-tỷ-lệ vẫn chưa)*: bản nháp
  3.871 (+29%) → nói `"cắt 29%"` ra **3.248 (+8%), ±11%**.
  So sánh: nói **số ký tự** → +6% nhưng ±25%; nói **số từ** → +23%, gần như không nhúc nhích;
  không sửa → +36%. **Tỷ lệ là đòn bẩy tốt nhất.** Tầng 3 hiện KHÔNG nói tỷ lệ (nó nói "giữ k
  ý trung tâm" = đòn bẩy yếu), chỉ chạy 1 vòng, **không bao giờ đo lại**.
  ⚠ **Chưa đo CHẤT LƯỢNG sau khi cắt** — prompt thí nghiệm có `"shorten by tightening"` mà
  *tightening = nén văn*, thứ bị cấm. Phải chạy `validate` trước/sau khi cắt trước khi tin.

### A6. Tiền thật, API dễ vỡ

- Heatmap Most Replayed **undocumented** → toàn bộ lấy/parse nằm trong MỘT module
  (`oe/heatmap.py`). Lỗi nguồn ngoài chỉ làm trống cột, không được gãy pipeline.
- transcriptapi.com tốn credit, YouTube Data API tốn quota, LLM tốn tiền → mọi stage
  idempotent/resumable: skip khi output mới hơn input, checkpoint theo video/chương,
  PAUSE khi hết quota (không đánh dấu done), không tải lại thứ đã có trên đĩa.
- Không thêm bước gọi LLM/API mới vào pipeline mà không nói rõ chi phí mỗi lần chạy.

---

## PHẦN B — NGUYÊN TẮC HÀNH VI

Thiên về thận trọng hơn tốc độ. Việc vặt (typo, đổi tên biến cục bộ) dùng phán đoán —
nhưng Phần A vẫn áp dụng nguyên vẹn.

### B0. Ponytail đang bật (plugin, từ 2026-07-17)

User đã cài plugin **ponytail** (lười-có-kỷ-luật: YAGNI → tái dùng → stdlib → native → một
dòng). Nó trùng khít bài học đắt nhất của dự án: *mọi lần THÊM cơ chế đều tệ hơn, lần BỚT
thì ăn*. Kết quả `ponytail-audit` 2026-07-17 (đã kiểm bằng grep, chưa cắt — chờ user):
- `delete:` **lengthlab** ~700 dòng (thí nghiệm thất bại có hồ sơ, mặc định tắt — xem A5);
- `delete:` **`voiceprofile/gui.py`** 580 dòng (Tkinter, mồ côi tuyệt đối — chỉ còn entry
  point trong pyproject); `stdlib:` `_esc` → `html.escape`;
- `yagni:` `--baseline-dir` contrast mode chưa ai dùng — nhưng KHOAN cắt (luật C1, chạm quant).
Audit ngây thơ sẽ đòi cắt cả các vết sẹo có hồ sơ (2 llm.py, `_mask_meta`, cổng `_sane`,
banner onerror, tab `:target`…) — **tra CLAUDE.md trước khi nghe audit**.

### B1. Think Before Coding

**Đừng đoán. Đừng giấu chỗ chưa hiểu. Nói rõ đánh đổi.**

- Nêu rõ giả định trước khi code; không chắc thì hỏi.
- Nhiều cách hiểu yêu cầu → trình bày các cách, đừng tự chọn âm thầm.
- Với data ngoài kiểm soát (field yt-dlp, format transcript, .env thật): **kiểm bằng
  chạy thử** trước khi viết logic quanh nó — đừng tin tài liệu/trí nhớ hơn hành vi thật.
- Trước khi thêm code, định vị nó thuộc khối/module nào — không lấn module chưa tới lượt.
- Có cách đơn giản hơn thì nói ra; phản biện khi thấy hợp lý.

### B2. Simplicity First — kỷ luật MVP

**Code tối thiểu giải quyết đúng yêu cầu. Không làm trước phần chưa cần.**

- Giới hạn MVP là **quyết định có chủ đích**, không phải bug để "tiện tay" sửa:
  tokenizer regex, `noun_specificity_proxy` heuristic, GAPS heuristic, trend cột
  optional tắt mặc định. Chỉ nâng cấp khi được yêu cầu rõ.
- Không thêm tham số CLI/config, nguồn signal, cột board mới khi chưa được hỏi.
- Không abstraction cho code dùng một lần; không error-handling cho tình huống không
  thể xảy ra (định nghĩa "không thể" đổi trên server team — xem C2).
- Viết 200 dòng mà rút được còn 50 → viết lại.

### B3. Surgical Changes

**Chỉ động vào phần bắt buộc phải sửa. Chỉ dọn rác do chính mình tạo ra.**

- KHÔNG đổi khi chưa được yêu cầu: format `outline.txt`, schema JSON trung gian của oe,
  `library/index.json`, thứ tự cột board, header front-matter `script.md`.
- Không "cải thiện" code/comment lân cận; giữ style hiện có của từng package
  (voiceprofile và oe có style hơi khác nhau — tôn trọng từng bên).
- Thay đổi của bạn tạo import/biến thừa → xoá; dead code có từ trước → báo, để nguyên.
- Phép thử: mỗi dòng diff truy ngược được về yêu cầu của user.

### B4. Goal-Driven Execution

**Định nghĩa tiêu chí "xong" đo được. Lặp cho tới khi kiểm chứng.**

- "Sửa bug" → test tái hiện trước, rồi làm pass. "Thêm đặc trưng" → test khớp giá trị
  kỳ vọng trên fixture.
- `.venv/bin/pytest -q` phải xanh trước khi báo hoàn thành; đỏ thì nói thẳng là đỏ.
- Stage Python của oe: verify bằng **seed giả** (heatmap có đỉnh đặt sẵn, comment có
  câu hỏi đặt sẵn). Stage LLM: verify offline bằng callback/monkeypatch, rồi chạy thật
  ít nhất 1 lần trên corpus/video nhỏ.
- Thay đổi ở server/board → start server thật, gọi endpoint bằng curl/urllib mà kiểm,
  không chỉ đọc code. **Không tự nhận "đã xong" nếu chưa thực sự chạy** — lỗi
  subprocess/encoding/403 chỉ lộ khi chạy thật.
- Việc nhiều bước → nêu kế hoạch ngắn:
  ```
  1. [Bước] → verify: [cách kiểm]
  2. [Bước] → verify: [cách kiểm]
  ```

---

## PHẦN C — LUẬT VPS & VẬN HÀNH TEAM

Đích deploy: **VPS cho team content dùng chung qua browser.** Bản local Mac đang chạy
là bước đệm; các luật dưới áp dụng cho mọi thay đổi từ giờ.

### C1. Gộp là DI CHUYỂN + NỐI, không viết lại

**Hai nửa đều đang chạy tốt. Không refactor đồng loạt.**

- Giữ ranh giới 3 package: `voiceprofile` / `oe` / `contentultimate` (lớp nối mỏng).
- Trùng lặp (2 `llm.py`, 2 `board.html`) chỉ hợp nhất khi thực sự đụng tới, hợp nhất
  về phía voiceprofile (`llm.py` đa provider, kho key `.env`).
- 2 folder gốc `../Author Extract/`, `../Outline Extract/` là bản lưu — không sửa tiếp.

### C2. VPS = headless + nhiều người + mạng công khai

**Code viết cho máy Mac một người không tự nhiên chạy được cho team.**

> **Lộ trình hạ tầng user chốt 2026-07-22** (kế hoạch, chưa thực hiện — user tự làm):
> ① nâng VPS **phương án B: 2 vCPU / 4GB** (Vultr resize tại chỗ, giữ IP/data; snapshot
> trước khi resize; sau resize chỉ cần restart service là `MAX_PIPE` tự thành 2);
> ② SAU ĐÓ chuyển sang **server nội bộ** (≥4 nhân/8GB khuyến nghị). App đã portable
> (thuần file + systemd + nginx): chuyển = cài môi trường + rsync `runs/ uploads/
> library/ admin/ .env .htpasswd roles.json invites.json cookies.txt` + nginx conf.
> Ba việc phải quyết lúc chuyển: team truy cập kiểu gì (LAN hay Tailscale/VPN),
> HTTPS nội bộ (hết certbot/sslip.io), lịch backup riêng cho data. Lợi ích phụ:
> IP văn phòng/dân cư ít bị YouTube bot-check hơn hẳn IP datacenter.
> Đo 2026-07-21: VPS hiện tại 1 vCPU/951MB — fastembed S4 cần ~300-500MB nên
> KHÔNG chạy nổi 2 pipeline song song trước khi nâng cấp; token KHÔNG phải nút thắt
> (pipeline ~28k token/run, writer ~155k/kịch bản).

- Không osascript / mở browser / lệnh `open` trên server — ĐÃ XỬ LÝ: payload
  `/api/library` trả `can_pick` (false trên Linux) → board ẩn Browse/Save-as/Open và
  hiện nút **Upload…** (`/api/upload-corpus`, chỉ nhận .txt/.md vào `uploads/<tên>/`);
  `--no-browser` cho headless. Tính năng mới nào đụng filesystem phải đi qua đường
  tương tự, grep `osascript` trước khi tuyên bố "chạy được VPS".
- App chỉ bind `127.0.0.1`, ra internet qua reverse proxy (nginx) + HTTPS + auth.
  KHÔNG mở port app trực tiếp, không có chuyện "để auth sau". **Auth đã chốt:** nginx
  basic auth (htpasswd, admin cấp/thu tài khoản trên server) + `X-Remote-User` xuống
  app; toàn bộ quy trình ở [`deploy/SETUP-VPS.md`](./deploy/SETUP-VPS.md) (systemd +
  nginx conf mẫu trong `deploy/`).
- Nhiều người bấm cùng lúc là tình huống THẬT. **Job voiceprofile chạy THEO NGƯỜI từ
  2026-07-16** (`JOBS` keyed theo `X-Remote-User`, hết thời JOB global đè nhau):
  - **mỗi tài khoản 1 job** → số job song song tối đa = số thành viên team; mỗi job là 1
    subprocess chờ mạng là chính nên VPS chịu nhẹ; **nút thắt thật là rate-limit provider**
    (429 nghẽn tốc độ đã retry/backoff trong `voiceprofile/llm.py`, PHÂN BIỆT với 1113 hết
    tiền — hết tiền thì báo ngay, không chờ).
  - `/api/status` trả job **của người hỏi** + `others` (ai khác đang chạy gì) — hình dạng
    payload GIỮ NGUYÊN bản cũ nên frontend cũ không gãy; Huỷ chỉ huỷ job của chính mình.
  - **Guard trùng đích**: 2 người không được viết CÙNG `script_path` / extract CÙNG thư mục
    (409 nêu rõ ai đang giữ) — 2 job cùng file phá checkpoint `{out}.progress.json` + bản ký
    biến của nhau.
  - `usage.new_job_id()` có đuôi ngẫu nhiên — 2 người bấm cùng mili-giây từng sinh **trùng
    job_id** ⇒ token 2 người trộn vào nhau trong sổ (test_jobs bắt được đúng lỗi này).
  - Chạy local không nginx → không danh tính → một khoá chung `ANON_KEY`, hành vi như cũ.
  - **Board Outline THEO USER + pipeline THEO RUN (2026-07-22, fix lỗi UX "người sau đè
    người trước")**: bỏ `RD` global làm nguồn sự thật — mỗi request tự mang run
    (`?run=`/`body.run` do board gửi → `USER_RUNS[user]` persist ở `runs/.user-runs.json`
    → run mặc định). `oe.s5_server.PIPELINE` global → `PIPELINES` dict theo run +
    `start_pipeline()` cap `MAX_PIPE = min(2, cpu_count)` (VPS 1 vCPU hiện tại = 1;
    **sau nâng 2 vCPU chỉ cần restart là thành 2 — không sửa code**). Hai khoá toàn cục
    khi chạy song song: `YT_LOCK` giữ S1/S1b/S1c (1 luồng gọi YouTube — chạy yt-dlp song
    song cùng IP là cách nhanh nhất ăn bot-check) và `EMBED_LOCK` giữ S4/S4b (fastembed
    ~500MB RAM, 1 suất). Board có ô đổi run (`#runSel`); `_board_data` trả `run` + `runs`.
    Test: `tests/oe/test_s5_server.py` + `test_board_theo_user_khong_de_nhau`.
    Còn LẠI ngoài phạm vi: 2 người cùng sửa MỘT run vẫn last-write-wins (mô hình team là
    mỗi người một run — chưa ai xin đồng-sửa).
- Lỗi mạng/API/timeout/input rác của đồng nghiệp là tình huống thật trên server team —
  lớp server phải xử lý và báo lỗi tử tế (không phải "impossible scenario" của B2).
- **JS nhúng trong chuỗi Python (`SETTINGS_HTML`…): backslash phải GẤP ĐÔI, và kiểm cú pháp
  phải ở TẦNG RUNTIME.** Lỗi thật 2026-07-17: ghi `\n` một gạch vào file → Python parse thành
  xuống-dòng thật → chuỗi JS `confirm('…')` bị ngắt giữa chừng → SyntaxError → **toàn bộ JS
  trang chết** (tab không bấm được, bảng không nạp). `node --check` trên văn bản FILE **không
  bắt được** — ở tầng file `\n` vẫn hợp lệ; phải extract script từ **hằng số đã import**
  (`from contentultimate import server; server.SETTINGS_HTML`) rồi mới check. Đã có test khoá
  (`test_js_nhung_trong_python_khong_bi_nuot_escape`). Phòng thủ đi kèm, giữ lại vĩnh viễn:
  (1) `window.onerror` → banner đỏ hiện lỗi ngay trên trang (user chụp là thấy thủ phạm);
  (2) tab Cài đặt chuyển bằng **anchor + CSS `:target`** — JS chết vẫn bấm được tab.
- `.env`, `videos.txt`, `cookies.txt`, corpus tác giả, `library/`, `runs/` không vào
  git, không nằm trong web root, không lộ qua endpoint nào. **Mọi endpoint đọc/tải file
  phải whitelist** (bài học rà soát 2026-07-09): `/api/outline-load` chỉ đọc path trong
  danh sách runs; `/api/download` chỉ trả `.md/.jsonl` deliverable + denylist
  cookies.txt/videos.txt/.env — KHÔNG bao giờ nới đuôi `.txt/.json` (credential nằm ở
  đó). Dữ liệu động nhét `innerHTML` phải `esc()`; `merge_env` cắt value ở `\n`.
  Nhận diện admin CHỈ qua `X-Remote-User` do nginx ghi đè (`location /`), không tin
  header client. Corpus trên VPS dùng chung vẫn theo luật bản quyền A1.

### C2b. Tab Quản lý (`/manage`, 2026-07-15) — theo dõi được tới đâu, KHÔNG tới đâu

**Chỉ admin (`ADMIN_USERS`, hiện `thanh`). Sổ ghi ở `admin/` — ngoài git, 700/600
(chứa tên đăng nhập + IP = dữ liệu cá nhân).**

- **Sổ ghi** (`voiceprofile/usage.py`, append-only JSONL, **không hàm nào được ném lỗi** —
  mất một dòng sổ là chuyện nhỏ, giết job viết 30 phút thì không):
  `usage.jsonl` (1 lần gọi LLM) · `history.jsonl` (1 job) · `access.jsonl` (cặp user+IP mới/giờ).
- **Danh tính xuống subprocess bằng `CU_USER`/`CU_JOB`** (`_run_cli` đặt): lớp LLM chạy trong
  subprocess CLI nên KHÔNG thấy header nginx. `CU_JOB` là thứ nối token của subprocess với
  dòng job của server — bỏ nó là mất cột token.
- **Token ĐO từ response provider, không ước lượng** (luật A1). Đo thật trên z.ai 2026-07-15:
  GLM trả `usage` ở **chunk CUỐI của stream, kể cả khi KHÔNG gửi `stream_options`** → `oe/llm.py`
  chỉ nhặt khi đi ngang, không đụng payload. `voiceprofile/llm.py` không stream → lấy thẳng.
  Ghi usage **trước** khi xét content: lần trả rỗng (reasoning đốt hết max_tokens) VẪN TỐN TIỀN.
- **KHÔNG quy token ra tiền** trong UI: giá provider đổi theo thời điểm ⇒ quy đổi = số bịa (A1).
- **Bản ký biến** (`_snapshot`): mỗi lần viết lưu `history/<ngày-giờ>-<user>.md` + outline kèm;
  `script.md` vẫn là con trỏ bản mới nhất. **Trước 15/07/2026 tool ghi đè ⇒ không có lịch sử quá
  khứ, không dựng lại được.** Đọc/tải bản cũ qua `/api/history-file` (`&dl=1` → Content-Disposition;
  nút Xem · ⤓ Kịch bản · ⤓ Outline mỗi dòng nhật ký) — whitelist **theo sổ `history.jsonl`**,
  KHÔNG theo đuôi file (luật C2). Vì thế `.outline.txt` tải được mà `.env`/`cookies.txt` thì không:
  chúng không có trong sổ. Thêm loại file mới cho tải ⇒ phải thêm vào `_history_files()`.
- **Giới hạn phải nói thật với user, đừng hứa quá:** basic auth **không có phiên** ⇒ không
  "đăng xuất thiết bị lạ", không thu hồi; lộ mật khẩu chỉ chặn được bằng **đổi mật khẩu**
  (người thật cũng phải đổi theo). Nhiều IP **không chứng minh** bị lộ (4G/VPN/ISP đổi IP) —
  `_alerts` là **dấu hiệu để người thật xem**, tool KHÔNG tự khoá ai. Muốn phiên/thu hồi/2FA
  phải đưa auth vào app (mẫu đã chạy thật: `radary/auth.py` cùng VPS) — **việc riêng, chưa làm**.
- **LUÔN hiện "đang đăng nhập là ai" trên MỌI trang — cả 2 board**, không chỉ trang admin
  (`_whoami_bar`; `_forbidden_page` nói rõ bạn là ai + ai mới là admin). **Không phải trang trí —
  nó chặn một hiểu lầm đã xảy ra thật 2026-07-15:** admin tạo tài khoản test (`Ngoc`) → đăng nhập
  bằng nó → browser nhớ mật khẩu, im lặng gửi lại mãi → thấy tool chạy ngon mà **không hề bị hỏi
  mật khẩu** ⇒ tưởng "tool không có bảo mật, người lạ vào được", và không hiểu vì sao `/manage`
  trả 403. Lần vá đầu chỉ gắn dải vào trang chủ/Cài đặt/Quản lý — **user vẫn không thấy vì họ
  sống ở `/outline` và `/author`**. Bài học: danh tính phải có ở nơi người ta LÀM VIỆC.
  Log nginx (`$3` = `$remote_user`) là bằng chứng dứt điểm cho mọi nghi vấn kiểu này —
  đo trước khi tin. Đường vào KHÔNG kèm mật khẩu vẫn 401 sạch ở mọi route (đã đo).
- 2 `board.html` KHÔNG có placeholder `<!--WHOAMI-->`: `Handler._board()` tiêm vào `</style>` +
  `<body>` lúc phục vụ (giữ luật C1 — không sửa file Khối 1/2 khi không cần). Cả 2 file dùng
  chung bộ biến CSS nên dải hiện đúng; không khớp được thì trả nguyên trang (thiếu dải còn hơn
  gãy board). Dải để `z-index:60` — phải nằm trên mọi overlay/modal của board (cao nhất: 58).
- **`/logout` = trả 401 + `WWW-Authenticate`** để browser hỏi lại tài khoản. **KHÔNG phải cơ chế
  bảo mật** (basic auth không có gì để thu hồi), chỉ là lối đổi tài khoản; tuỳ browser có thể vẫn
  nhớ mật khẩu cũ → trang `/logout` nói thẳng cách chắc ăn (đóng browser / cửa sổ ẩn danh).
- Chống tự khoá (như `ADMIN_USERS` 2026-07-09): không tự xoá mình, không xoá người đang trong
  `ADMIN_USERS` (gỡ khỏi danh sách ở tab Cài đặt trước).

### C3. Tiền thật nhân theo số người dùng

**Một người bấm nhầm tốn vài cent; cả team bấm hằng ngày là hóa đơn.**

- Giữ idempotent/resumable ở mọi stage (đã có: skip theo index, checkpoint chương,
  `--continue`, `.pipeline.json`). Thay đổi nào phá tính chất này = bug kiến trúc.
- Dev/test offline bằng callback/seed giả — không đốt credit để verify logic thuần.
- **z.ai dùng 429 cho CẢ HAI việc**: nghẽn tốc độ VÀ **hết tiền** (`code 1113`,
  "Insufficient balance"). Đo thật 2026-07-15. Báo "chờ chút rồi thử lại" khi thực ra hết tiền
  = cả team ngồi chờ vô ích, `oe/llm.py` còn retry 4 lần + backoff (~50s) trước khi báo sai.
  Đã tách: `_explain_429`/`_no_balance` → nói thẳng "HẾT TIỀN, nạp rồi chạy lại".
- **Bẫy môi trường:** `tests/test_llm.py` import `voiceprofile` từ **venv đang active**, không
  ép `sys.path`. Máy user có venv của folder backup `../Author Extract/` ⇒ `python3 -m pytest`
  trần có thể **test nhầm code backup mà vẫn xanh**. Luôn chạy `.venv/bin/python -m pytest`.

---

**Các nguyên tắc này đang phát huy tác dụng nếu:** diff không có thay đổi thừa, không
con số nào bị "ước lượng" thay vì đo, không dữ liệu tác giả/key nào lọt vào git, format
`outline.txt`/`library/index.json` không bị đổi ngoài ý muốn, mọi thay đổi server đều
được chạy thật trước khi báo xong, và hóa đơn API không phình vì chạy lại thứ đã có.
