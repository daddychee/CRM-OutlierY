# METHODOLOGY — SEO Optimize

> Tool sinh **metadata YouTube** (Title ×3 · Tag ×3 · Description ×1) cho mạng lưới kênh riêng,
> theo pipeline harvest đối thủ + marketing-hybrid + LLM, xuất `metadata.txt` để dùng khi đăng.
> Đọc kèm 3 file spec pillar: [title-definition.md](title-definition.md) · [tag-definition.md](tag-definition.md) · [description-definition.md](description-definition.md).
> Cập nhật: 2026-07-04.

Vị trí trong hệ tool (sibling với Outline Extract):
`Outlier Discovery → Niche Research → Content Verdict → Outline Extractor → Author Extract → RoughCut → [SEO Optimize]`

---

## §0. Nguyên tắc nền (kế thừa Outline Extract)

- **Python đo — LLM hiểu, không đảo vai.** Python: gọi API, đếm tần suất, weighting, đo độ dài, validate, compose file. LLM: relevance gate, phân vai tag, chọn primary, sinh Title/Description/chapter-title, giả định desire. Hai bên nói chuyện qua **JSON trung gian** (hợp đồng giữa stage).
- **LLM không bịa số/link.** Mọi tag do LLM giữ phải tồn tại thật trong pool; link/CTA nhập tay, LLM không sáng tác.
- **Idempotent/resumable.** API tốn quota/tiền → skip khi output mới hơn input, cache trên đĩa, không tải lại thứ đã có.
- **GUI web-local:** Python `http.server` bind `127.0.0.1`, HTML/JS tĩnh không CDN (offline). Key trong `.env` (gitignore, kèm `.example`).
- **Khác biệt có chủ đích với Outline Extract (A2):** tool này **CÓ điểm xếp hạng** option (user yêu cầu). Điểm = **độ khớp pattern marketing + guardrail, KHÔNG phải dự đoán CTR** — phải gắn nhãn đúng, không tạo tự tin ảo. Trọng tài cuối vẫn là A/B trên kênh.
- **Ngôn ngữ:** UI/log tiếng Việt; **deliverable (Title/Tag/Description/chapter) theo ngôn ngữ nội dung** (thường English), KHÔNG dịch sang tiếng Việt (`llm.OUTPUT_LANG_RULE` ép trong mọi prompt sinh nội dung).

---

## §1. Hai module

### Module 4 — 1 tập → N kênh (`episode.py`)

Cùng 1 tập đăng nhiều kênh → mỗi kênh 1 bộ metadata **khác nhau đủ để né trùng**, vẫn đúng
phong cách kênh. Title + Description khác hẳn; Tag được chồng lấn (đòn bẩy yếu nhất).
Chi phí phẳng theo số kênh: harvest/brief/tag-annotate dùng chung, title 1 call/nhóm-format,
description 1 call ra N bản → **N kênh ≈ 4 call**. Xuất 1 file gộp chia section theo kênh.

### Module 3 — Niche Format Profile

Dán URL đối thủ trong niche → lọc **outlier** (`views ≥ 2× median` mỗi kênh) → format chung của niche
phủ cả 3 trụ cột + luật riêng. Nhiều format/niche. Áp dụng theo luật **kênh đè niche** (§3).
Python đo mọi con số; LLM chỉ rút pattern/skeleton (2 call) và **phải dẫn example là title có thật**.

### Module 1 — Profile Description Library (kiểu Author Extract)
Input: **URL kênh** (channel / @handle / hoặc 1 video của kênh) → Python **tự fetch** video của kênh
(resolve channelId → uploads playlist, phân trang) → gộp cụm skeleton → Profile ổn định (ít over-fit).
**Rule pool:** kênh nhiều video chỉ lấy **30–50 video MỚI NHẤT** (limit chốt cứng `[5,50]` trong
`channel_video_ids`) — đủ để suy skeleton, không tốn quota/thời gian fetch cả kênh.
Lưu: `profiles/<slug>.json`, đặt tên `[Tên kênh] + [Mã số]` (vd `Cosmic Lens · CL-01`).

### Module 2 — Generator
Input:
- **Nguồn đối thủ:** video CHÍNH đối thủ + list video PHỤ cùng nội dung (URL) → harvest tag thật + title/description (bằng chứng desire).
- **Nội dung của bạn:** Kịch bản (text) + SRT (chapters).
- Chọn 1 Profile Description.

Output (pickable, có điểm):
- **Description ×1** (theo Profile + kịch bản + chapters SRT)
- **Tag ×3** (pool tag đối thủ, weighted, gate theo nội dung)
- **Title ×3** (marketing-hybrid: kịch bản + bằng chứng desire đối thủ)

Pick 1 Des + 1 Tag + 1 Title → **[Xuất]** nhập tay link/CTA → `metadata.txt`. **[Restart]** → chọn Profile khác → pick lại.

---

## §2. Pipeline (stage · Python/LLM · output JSON)

| Stage | Việc | P/L | Output |
|---|---|---|---|
| **H1 harvest** | `videos.list` lấy tag+title+description video chính+phụ (real, batch) | P | `harvest.json` |
| **H2 pool** | chuẩn hóa tag, dedup mặt chữ, view+position weighting | P | `tagpool.json` |
| **G-tag** | relevance gate + phân vai + chọn primary (theo nội dung) → 3 bộ | P+L | `tags.json` |
| **G-title** | map desire (kịch bản+bằng chứng) → sinh 3 title (FAB/PAS) + score | P+L | `titles.json` |
| **G-des** | fill Profile skeleton từ kịch bản + chapters(SRT) | P+L | `description.json` |
| **compose** | ghép pick + Channel → `metadata.txt` | P | `metadata.txt` |

Profile extract (Module 1) là pipeline riêng: `videos.list` description nhiều video kênh → block extraction (P regex + L phân loại) → cluster skeleton → `profiles/<slug>.json`.

---

## §3. Schema JSON (hợp đồng giữa stage)

```jsonc
// harvest.json
{ "main": {"id","title","description","tags":[...],"views"},
  "sub": [ {"id","title","description","tags":[...],"views"}, ... ] }

// tagpool.json  (mỗi tag = 1 record đã weighting)
[ {"tag","canonical","n_videos","sum_view_w","best_pos","word_len"} ... ]

// tags.json  (3 bộ)
{ "sets": [ {"name","score","chars","ratio":{"broad","longtail"},
             "coverage":"6/8","tags":[...]} , ... ] }  // 3 phần tử

// titles.json  (3 title)
{ "items": [ {"text","score","chars","desire","technique","proof":bool,
              "awareness","evidence"} , ... ] }         // 3 phần tử

// description.json
{ "score","chars","profile","text","chapters":[{"t","label"}],
  "sigs":{"kw_in_125":bool,"hashtags":int} }

// profiles/<slug>.json
{ "channel","channel_id","code","n_videos","skeleton":["HOOK","SUMMARY","CHAPTERS","CTA","HASHTAG"],
  "block_rules":{...}, "deviation_vs_standard":[...],
  // ── user tự khai (library.USER_FIELDS) — re-extract KHÔNG ghi đè ──
  "niche":"Space / Science", "lang":"English", "links":"<Link/CTA cố định>",
  "note":"", "updated":"<iso>",
  "format":"<slug Format đối thủ kênh này học theo — GẮN SẴN, không chọn lúc generate>" }

// formats/<slug>.json  (Module 3 — BỘ SƯU TẬP đối thủ của 1 niche)
{ "name":"Documentary dài", "niche":"Space / Science",
  "competitors":[ { "channel_id","url","title","handle","added_at",
                    "package":{ "keywords":[<tag KÊNH>], "description","description_chars",
                                "sections":[{"type","title","playlists":[...]}], "n_sections",
                                "trailer","subs","views","video_count","topics":[...],"country" },
                    "cadence":{"median_days","n"}, "n_videos","n_outliers","enough_sample",
                    "outliers":[{"id","title","desc","tags":[...],"views","published_at"}] } ],
  "package":{ "n_channels","keywords_common":[...],"keywords_all":[...],"keywords_per_channel",
              "about_chars":{...},"sections":{...},"with_trailer","subs":{...},"cadence_days",
              "guide":{"about_pattern","keywords_guide","homepage_guide","cadence_note","checklist":[...]} },
  "community_raw":"<user dán tay — API không có endpoint>", "community":{...},
  "sources":{"channels":[...],"n_channels":N,"loose_videos":N,"unknown_lines":[...]},
  "n_videos":N, "n_outliers":N, "outlier_rule":"<mô tả luật + số kênh đủ mẫu>",
  "title":{ "patterns":[{"pattern","example","example_verified":bool,"desire","technique","support"}],
            "chars":{"avg","range"}, "words":{"avg"}, "anchors":[...], "note" },
  "description":{ "skeleton":[...], "blocks":[{"block","chars","desc"}],
                  "chars":{"avg","range"}, "hashtag":{...}, "special_chars":[...], "note" },
  "tags":{ "base":[...], "ratio":{"broad","longtail"}, "avg_count", "range",
           "videos_with_tag", "pool_size" },
  "rules":{ "must":[...], "avoid":[...] },        // LLM đề xuất → user sửa; extract lại KHÔNG ghi đè
  "evidence":[{"id","title","views","channel"}],  // outlier đã học — bằng chứng, cấm bịa
  "created","updated" }

// brief kịch bản (digest.build — nén 1 lần, 3 stage dùng chung; lưu trong result.json._brief)
{ "topic", "entities":[...], "beats":[...], "desires":[...], "keywords":[...], "promise" }

// usage (llm.usage_snapshot — đọc field `usage` API trả về, KHÔNG ước lượng)
{ "calls","in","out","total","cache_hits","saved_in","saved_out","cost","saved_cost" }

// runs/<run>/result.json — chế độ 1 TẬP → N KÊNH (episode.py)
{ "mode":"episode", "keyword","n_videos","created","main_url","_main_title","usage",
  "channels":[ { "slug","channel","code","lang","niche","links","format","skeleton_source",
                 "title":{"text","score","chars","desire","technique","rule_hits":[...]},
                 "tags":{"name","tags":[...],"score","chars"},
                 "description":{"text","score","chars","chapters":[...],"sigs":{...}},
                 "warnings":[<cảnh báo trùng với kênh khác>] } ],
  "_pool":[...], "_comp_titles":[...], "_brief":{...} }

// runs/<run>/result.json  (thêm phần gắn run vào KÊNH + Format niche)
{ "titles":[{...,"rule_hits":[...]}], "tags":[...], "description":{...}, "keyword","n_videos",
  "profile":"<slug kênh>", "format":"<slug format>", "skeleton_source":"kênh|niche|standard",
  "created":"<iso>", "main_url":"<url video đối thủ>",
  "picked_title":"<title đã chọn lúc xuất>", "exported_at":"<iso>",
  "_pool":[...], "_comp_titles":[...], "_main_title":"..." }   // _* để Sinh lại từng phần
```

**Format gắn vào kênh** (`episode.format_for`): `profile.format` → chọn tay cho run → suy theo niche.
Mỗi kênh của mình học package + pattern tiêu đề của MỘT kênh đối thủ, khai báo 1 lần từ trước.

**Kênh đè niche** (`niche_format.resolve`): `skeleton` lấy của Profile kênh nếu có → không thì của
Format niche → không nữa thì standard. `base_tags` của niche chèn **cuối** order tag (chỉ lọt khi
còn ngân sách 500 ký tự). `rules.avoid` → `check_rules` sinh `rule_hits` = **cảnh báo**, không hard-gate.

**Niche** không có store riêng: là 1 field text trên profile, **user tự nhập** (không để LLM đoán →
tránh chẻ nhỏ/trùng lặp niche). Board gom nhóm khi render; niche rỗng → "Chưa phân loại" xếp cuối.

Đổi schema = đổi hợp đồng → nói rõ, không đổi âm thầm.

---

## §4. Scoring (điểm khớp pattern — có nhãn)

- **Title:** cộng điểm các tiêu chí §5 title-definition (desire thật · driver rõ · awareness-fit · proof-backed · feed guardrail · evidence). Hard-gate (>100 ký tự / policy) = loại, không cho điểm.
- **Tag:** relevance + view/position weight + specificity (§4 tag-definition). 3 bộ khác nhau ở tỉ lệ broad/long-tail.
- Điểm hiển thị badge + nhãn "pattern". **Không** gọi là CTR/chất lượng. Sort best-first (user yêu cầu ranking).

---

## §5. GUI & Endpoints

`seo/board.html` (tĩnh) ↔ `seo/server.py` (`127.0.0.1`):
- `GET /` → board.html
- `GET /api/profiles` → thư viện kênh (FULL profile + field user khai)
- `GET /api/runs?profile=<slug>` → lịch sử run của kênh (bỏ `profile=` = tất cả, mới→cũ)
- `GET /api/formats` → Format Profile của các niche (Module 3)
- `POST /api/extract-format` {name, niche, urls, limit} → Module 3 (thread + poll `/api/status`)
- `POST /api/update-format` {slug, name, niche, rules, note} → sửa luật/tên (không đụng số liệu đã đo)
- `POST /api/delete-format` {slug} → xoá format
- `POST /api/extract-profile` {channel_url, channel, limit, niche, lang, links} → Module 1 (thread + poll `/api/status`)
- `POST /api/update-profile` {slug, niche, lang, links, format, sub_url} → sửa field user khai (không chạm phần máy phân tích)
- `POST /api/delete-profile` {slug} → xoá kênh
- `POST /api/generate` {main_url, sub_urls, script, srt, profile, format?, only?, model?} → Module 2;
  thêm `channels:[slug,...]` **> 1 phần tử** → chuyển sang Module 4 (1 tập → N kênh)
- `GET /api/result` → titles/tags/description JSON
- `POST /api/export` {run, text, picked_title} → ghi `metadata.txt` + đánh dấu title đã dùng vào result.json
- `GET /api/status` → tiến độ pipeline (resumable)

**Tab GUI:** `KÊNH` (cây niche → card kênh; detail 3 mục Guide · Thông tin · Lịch sử) · `GENERATOR`
(chạy trong ngữ cảnh kênh đang chọn — Profile, Link/CTA, lịch sử đều theo kênh đó).

---

## §5b. Kỷ luật token LLM

4 call/run: `digest → tags → titles → describe` (chapter đã gộp vào describe).

| Cơ chế | Tác dụng |
|---|---|
| `digest.build` nén kịch bản 1 lần → `content_brief` | hết cảnh gửi kịch bản thô 3 lần |
| `digest.sample` lấy đầu+giữa+cuối | cùng ngân sách nhưng phủ cả video (prefix phẳng mất phần kết) |
| `digest.MIN_CHARS = 2500` | kịch bản ngắn thì KHÔNG nén — nén lỗ vốn |
| `script_opening` ~900 ký tự | Description vẫn giữ giọng văn gốc dù dùng brief |
| `.cache/llm/` cho call temp ≤ 0.3 | chạy lại cùng input = 0 token |
| `result.json._brief` | regen không nén lại, không phụ thuộc cache đĩa |

Đo thật (kịch bản 20k): run đầu −23% · Sinh lại Title −67% · video khác cùng kịch bản −72%.
**Đánh đổi đã biết:** `↻ Sinh lại Tag` input y hệt → cache, kết quả không đổi (0 token).

---

## §6. Giới hạn MVP (có chủ đích)

- Desire Map cho Title: **LLM tự suy** từ kịch bản + bằng chứng đối thủ (chưa có thư viện Desire Map riêng).
- Feedback loop (đo CTR/retention thật để cập nhật) — **chưa làm** ở MVP; thiết kế chừa chỗ.
- Channel constants (link/CTA): **lưu theo từng kênh** (`profiles/<slug>.json` field `links`), tool tự điền lúc generate; vẫn sửa tay được trước khi xuất.
- Chỉ YouTube; không đa nền tảng.
- Thumbnail/CTR: ngoài phạm vi tool này.

---

## §7. Config & chạy

- `.env`: `YOUTUBE_API_KEY`, `LLM_API_KEY`/provider (không commit; kèm `.env.example`).
- Chạy: `python3 -m seo.server` (hoặc `Start.command`) → mở `http://127.0.0.1:<port>/`.
- Verify (B4): stage Python bằng seed giả; stage LLM monkeypatch + chạy thật 1–2 video ngắn; "xong" = generate trên 2–3 video thật → pick → `metadata.txt` xuất đúng.
