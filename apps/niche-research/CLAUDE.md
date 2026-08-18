# CLAUDE.md — Niche Research

YouTube **niche intelligence** tool: từ danh sách kênh đối thủ + YouTube API key → một workbook Excel
trả lời 3 câu hỏi: *bản đồ thị trường là gì · có nên vào không (Go/No-Go) · đánh sub-niche nào trước
(beachhead)* — kèm bản SUMMARY hướng dẫn hành động bằng tiếng Việt.

Thiết kế gốc: `NICHE-TOOL-ARCHITECTURE.md`. **Nguyên tắc vàng (§0): Python làm mọi thứ ĐO ĐƯỢC,
LLM làm mọi thứ PHẢI HIỂU — không bao giờ đảo vai.** Hai bên chỉ nói chuyện qua file JSON có schema
(`contracts/`). LLM không bao giờ tính lại số; Python không bao giờ "đoán chủ đề".

## Lệnh chạy

```bash
python3 orchestrator.py run <competitors.txt>              # pipeline tất định đầy đủ
python3 orchestrator.py run <file> --llm                   # + các tầng LLM (namer/auditor/plan/summary)
python3 orchestrator.py run <file> --deepdive [ANCHOR]     # + S14/S15 tải transcript (TỐN CREDIT transcriptapi.com)
python3 orchestrator.py run <file> --skip-comments --force
python3 orchestrator.py status <project>                   # checklist done/stale/missing (read-only)
python3 orchestrator.py resume <project>                   # "Refresh": chạy tiếp phần thiếu, replay args đã lưu
python3 orchestrator.py llm <project> --agent summary      # chạy lẻ 1 agent LLM (namer|auditor|plan|dna|summary)
```

GUI: `python3 niche_research_gui.py` hoặc double-click `Start.command` (Mac) / `Start.bat` (Win).
Nút **▶ START** = `run`; nút **🔄 Refresh** = `resume` (tự nhớ project gần nhất qua `.last_project.json`
ở gốc tool). Không có test suite — verify bằng cách seed `videos.json` giả vào `niche-data/` rồi chạy
từng script (xem "Cách test" dưới).

`competitors.txt`: file text trộn lẫn API key YouTube (`AIza...`) và kênh (`/channel/UC...`, `@handle`,
`UC...` thô) — key YouTube nằm TRONG file này, KHÔNG nằm trong `.env`.

## Layout project (mỗi niche 1 folder, tự chứa)

```
<project>/
├─ competitors.txt          # input của user (key + kênh)
├─ Report/                  #   <name>_report.xlsx (deliverable) + SUMMARY.md
├─ Transcripts/             # transcript đặt tên THEO TIÊU ĐỀ video + index.json
└─ niche-data/              # MỌI file trung gian: videos.json, analysis.json, decision*.json,
                            #   bets*.json, summary.json, run.log, .state.json (args cho resume)
```

Project cũ kiểu phẳng (mọi thứ ở gốc) được `migrate_layout()` tự dọn vào layout này ở lần run kế —
KHÔNG scan lại. `.state.json` + `run.log` nằm trong `niche-data/`.

## DAG (orchestrator.py)

| Stage | Script | Ghi | Loại |
|---|---|---|---|
| S1 scan (resumable) | `1_scan.py` | videos.json, channels.json | PY |
| S3 keywords+LIFT | `2_keywords.py` | analysis.json | PY |
| S4 comments→gaps (resumable, optional) | `3_comments.py` | gaps.json | PY |
| S5 crackability (hard-gate) | `5_crackability.py` | crackability.json | PY |
| S6 monetization (HEURISTIC) | `6_monetization.py` | monetization.json | PY |
| S7 demand & trend | `7_demand.py` | demand.json | PY |
| S8 DECISION 1 Go/No-Go | `8_decision1.py` | decision1.json | PY |
| S9 sub-niche clustering | `9_subniche.py` | subniche.json | PY |
| S9b đặt tên cụm | `run_agent.py namer` | subniche.json (labels) + `_s9b_namer.done` | LLM |
| S10 DECISION 2 beachhead | `10_decision2.py` | decision2.json | PY |
| S11 candidate bets | `11_synthesize_bets.py` | bets.json | PY |
| S12 Auditor (phản biện bets) | `run_agent.py auditor` | bets_audited.json | LLM |
| S13 Execution Plan | `run_agent.py plan` | execution_plan.json | LLM |
| S19 FINAL SUMMARY (3 lượt) | `run_agent.py summary` | summary.json + Report/SUMMARY.md | LLM |
| S18 build report | `18_build_report.py` | Report/*.xlsx | PY |
| S14/S15 deep-dive (chỉ khi `--deepdive`) | `14_deepdive.py`, `15_fetch_transcripts.py` | deepdive_*.json, Transcripts/ | PY |
| S16/17 DNA (cần transcript) | `run_agent.py dna` | dna.json | LLM |

Quy ước điều phối:
- **Idempotent kiểu Make**: stage bị skip khi mọi output mới hơn mọi input (`up_to_date`). `--force` ép chạy lại.
- **Resumable**: S1/S4/S15 checkpoint mỗi page/video, in `PAUSE`/`DONE`; orchestrator loop tới khi `DONE`.
  Hết quota YouTube → PAUSE, KHÔNG đánh dấu done (thêm key hoặc chờ rồi resume).
- **Mọi tầng LLM là optional** — lỗi (key sai, quota, mạng) chỉ skip stage đó, pipeline vẫn ra report.
- S9b mutate `subniche.json` tại chỗ nên dùng **file marker `_s9b_namer.done`** làm output (nếu không sẽ
  "up-to-date" vĩnh viễn).
- Schema gate best-effort sau mỗi stage (`contracts/*.schema.json`; đủ mạnh khi cài `jsonschema`).
- Mỗi script PY chạy độc lập được: `python3 scripts/N_xxx.py <niche-data-dir>` (S1/S4/S15 nhận thêm
  đường dẫn competitors.txt trước workdir).

## LLM (`scripts/llm_provider.py` + `scripts/run_agent.py`)

- **MỘT provider xuyên suốt** qua `LLM_PROVIDER` trong `.env` (quyết định của user — ưu tiên chỉn chu,
  không đa model). `AUDITOR_LLM_PROVIDER` là opt-in nâng cao, mặc định bỏ trống.
- Provider hỗ trợ: `anthropic` | `glm` | `openai` | `grok` | `custom` (mọi endpoint OpenAI-compatible).
- `.env` cấu trúc **2 block A/B** (Anthropic / GLM) — bật block nào thì bỏ `#` block đó, comment block kia.
  Dòng `LLM_PROVIDER` xuất hiện ĐẦU TIÊN thắng (do `os.environ.setdefault`).
- **GLM = Z.AI**: base `https://api.z.ai/api/paas/v4`, model `glm-5.2`. GLM 5.x là model REASONING —
  mặc định tool gửi `thinking: {type: disabled}` (bật lại bằng `GLM_THINKING=enabled`). Nếu không tắt,
  reasoning ăn hết max_tokens → stream rỗng. Key bigmodel.cn (nội địa TQ) cần override `GLM_BASE_URL`.
- **Mọi call đều STREAMING** (SSE) — timeout 180s áp per-chunk, không phải cả lần sinh; có fallback
  non-streaming khi đứt mạng giữa chừng. Output dài (auditor/summary/dna: 16000 tokens) bắt buộc streaming.
- `extract_json()` là parser **tự vá**: chịu được ```json fence, văn xuôi bao quanh, trailing comma,
  thiếu dấu phẩy, JSON bị CẮT (cứu prefix hợp lệ). Đừng thay bằng `json.loads` trần.
- Agent spec = file `agents/*.md` — **chính nó là system prompt** (single source of truth, đừng lặp
  hướng dẫn trong code).
- **S19 summary = vòng lặp 3 lượt CÙNG 1 model** (soạn → tự phản biện gay gắt → hoàn thiện). User đã
  chốt: giữ nguyên 3 lượt, KHÔNG thêm knob giảm lượt. Tiết kiệm token bằng `cache_prefix`
  (method+evidence gửi 1 lần, lượt 2–3 tái dùng cache ~10% giá) — đừng gửi lại evidence trong user msg.
  Lượt 3 trả **markdown THÔ** (không bọc JSON) để không bao giờ "unbalanced JSON" khi bị cắt.
  Evidence pack đọc TOÀN BỘ artifact (yêu cầu tường minh của user) nhưng cap từng list để giữ token.
- Output SUMMARY: tiếng Việt, 10 mục §0–§9, mọi nhận định trỏ về 1 con số + file nguồn. Persona =
  chuyên gia 35 năm về quy luật phối ngẫu; **§1 WINNING FORMAT 6 tiểu mục bắt buộc** (thời lượng ·
  chủ đề/sub-format · tiêu đề · thumbnail-SUY-LUẬN-có-nhãn · tags · nhịp đăng); văn phong
  SỐ→NGHĨA→LÀM. Evidence pack có sẵn `title_features` (winners vs normals) / `format_mix` mở rộng /
  `lift_tags` / `cadence` / `browse_share_weighted` — Python đo, LLM chỉ diễn giải.

## `.env` (gốc tool — KHÔNG commit/đóng gói file này, chỉ đóng gói `.env.example`)

`TRANSCRIPT_API_KEY` (transcriptapi.com, cho S15 — 1 credit/video, lỗi 402 nghĩa là chưa có paid plan,
xem https://transcriptapi.com/billing) · `LLM_PROVIDER` + key/model của block đang bật · tùy chọn
`GLM_THINKING`, `MAX_COMMENTS`. Đọc qua `_common.get_env()` (env thật ưu tiên hơn .env; có cache).

## Phương pháp & các bẫy đã trả giá (đừng lặp lại)

- **SHORTS GATE (mặc định BẬT)**: Short (≤180s) bị chặn HOÀN TOÀN — `compute_outliers` xoá in-place
  (`videos[:]`) ngay đầu hàm nên MỌI stage sạch Short; S1 không lưu Short từ scan; S6 tự lọc riêng
  (script duy nhất không gọi compute). Tắt bằng `SHORTS_GATE=off` trong .env.
- **OX v3** (`_common.compute_outliers`): OX = views / (channel_scale × shape(age)); baseline recent
  (≤18 mo) + matured (≥45 d), leave-one-out, trim top decile, tách format Short/Mid/Long, floor
  per-channel-per-format. Săn outlier trong `valid=TRUE, scope=primary`.
- **`x["age"]`/`fmt`/`valid` CHỈ tồn tại sau khi gọi `compute_outliers(videos, now)`** — script nào đọc
  các field này mà quên gọi sẽ lỗi câm (đã dính: competition pillar = 0 vì age=None).
- **Xếp hạng theo Σexcess (reach tuyệt đối), KHÔNG theo OX thô** — OX cao trên kênh tí hon là artifact.
- **Lift** = over-index trong outlier vs normal (two-proportion z + Benjamini-Hochberg FDR q=0.10),
  không phải frequency. Lift là LIÊN HỆ, không nhân quả (R-3).
- Khớp term với title phải dùng **word-boundary regex**, không substring ("space" ≠ "spacex").
- Trend trong `7_demand.py` dùng **views/day** (không phải raw views) để khử cohort-bias — trước đó raw
  views tạo trend DECLINING giả.
- Crackability: newcomer = kênh **nhỏ VÀ trẻ** (AND); cần `channels.json` có `publishedAt` (scan mới có).
- RPM/monetization là **HEURISTIC** — mọi diễn giải phải gắn nhãn ước lượng. Residuals bất biến:
  R-1 (recent-window), R-A (subs hiện tại ≠ subs lúc đăng), R-3 (lift ≠ nhân quả) — report phải in ra,
  kết quả là "đặt cược có thông tin để A/B test", không phải chân lý.
- `18_build_report.py`: mọi giá trị ghi ô Excel đi qua `_xl()` (flatten list/dict → chuỗi) — LLM hay trả
  list làm `openpyxl` crash. Dùng `b.get(key, [])` cho analysis cũ thiếu key.
- Log GUI stream theo dòng (`PYTHONUNBUFFERED=1`) — script chạy lâu PHẢI in tiến độ định kỳ, không GUI
  trông như treo.
- `TIME_BUDGET` trong S1/S4/S15 (mặc định 9999) — hạ ~30 nếu chạy trong sandbox giết shell sớm.

## Cách test (không có pytest)

Seed `videos.json` + `channels.json` giả vào `<tmp>/niche-data/` (nhiều kênh, mỗi kênh 1 video x12–15
làm outlier, tuổi 50–700 ngày) rồi chạy lần lượt `2_keywords.py` → `5..11` → `18_build_report.py` với
argv = đường dẫn niche-data. Test LLM bằng monkeypatch `requests.post` (Anthropic trả
`{"content":[{"type":"text","text":...}]}`, OpenAI-compat trả SSE `data: {...}` + `data: [DONE]`).
Test GUI headless: import module, `tk.Tk(); root.withdraw(); App(root)`.

## Đóng gói cho máy khác

Zip toàn bộ tool NHƯNG loại: `.env` (key thật), `.last_project.json` (path máy cũ), `__pycache__`,
`*.bak`, `.DS_Store`. `orchestrator.check_deps()` tự cài `requests`/`openpyxl` lần chạy đầu.
Người nhận: giải nén → tạo `.env` từ `.env.example` + điền key → `Start.bat`/`Start.command`.
