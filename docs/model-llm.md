# model-llm.md — sổ chủ đề CẤU HÌNH MODEL LLM TOÀN HỆ

> Mọi việc liên quan "đổi model", "app gọi model nào", "thêm nhà LLM" đọc file
> này TRƯỚC. Nguồn sự thật là CODE + KÉT; sổ này ghi luật, số đo thật và bẫy.

## 1. Nguồn sự thật: KÉT, không phải .env

Model + khóa của cả hệ nằm ở **két cấu hình** (`data/nen/ket.db`, quản trên
`General > API Keys`). `.env` của từng app chỉ còn dùng khi chạy NGOÀI cổng
OUTLIERY (`*_TRUST_PROXY` tắt) — trong V3 coi như di sản.

Hai ngăn: `cau_hinh` (không mật: nhà, model, base_url) và `bi_mat` (khóa API,
mã hóa Fernet). Chi tiết cơ chế: `nen/ket_cau_hinh/ket.py`, sổ khối đế `DE.md` mục 3b.

**Thứ tự resolve model (một luật duy nhất, hai route cùng theo):**

1. `cap_phat[app][viec].model` — model đặt RIÊNG cho một việc, thắng tuyệt đối.
2. rỗng thì lấy `api.<khóa đầu>.model` — model khai ở chính cây khóa ("theo khóa").
3. rỗng nữa thì rơi về mặc định hardcode trong app (xem mục 4).

Hai route phục vụ hai kiểu app:

| Route | Ai gọi | Lấy lúc nào |
|---|---|---|
| `/api/cau-hinh/api-khoa/{app}` | radary · content-ultimate · niche-research · seo-optimize | **mỗi lần chạy** (đổi model là ăn ngay, không cần restart app) |
| `/api/cau-hinh/llm/{vai}?app=` | ai-agent · data-analytics | **lúc khởi động** (`nap_cau_hinh_llm`) → đổi model xong **phải restart app** |

Cả hai chỉ phục vụ loopback; key trả plaintext cho app DÙNG, tuyệt đối không log.

**Bẫy đã vá 23/08/2026:** route `api-khoa` từng trả `model` rỗng thẳng, KHÔNG
làm bước 2 → Owner đổi model trên UI mà niche/seo/radary vẫn chạy hằng số trong
code, im lặng. Giờ hai route cùng luật; test ghim trong `tests/test_radary.py`
(`test_loopback_api_khoa_tra_cap_phat_va_chan_ngoai`).

## 2. Công tắc suy luận theo ĐỜI model GLM — KHÔNG được thay thế mù

GLM 5.x là model reasoning: mặc định nó sinh một chuỗi suy luận TRƯỚC câu trả
lời, ăn vào `max_tokens` → JSON bị cắt, câu trả lời cụt. Mỗi đời tắt/hạ một kiểu
KHÁC HẲN NHAU. Đo thật 23/08/2026 trên key công ty (api-020, endpoint z.ai):

| Model | `thinking:{type:"disabled"}` | `reasoning_effort` |
|---|---|---|
| `glm-5.2` và cũ hơn | tắt hẳn — reasoning 0 token, 1.0s | **vô hiệu** — reasoning vẫn 178-205 token |
| `glm-5.3` | **400** `1210 This model always engages in thinking` | **bắt buộc** — `low` kéo reasoning 279 → 11 token |

Ghi chú quan trọng khi làm việc với 5.3:

- Có mặt field `thinking` là 400, kể cả khi gửi kèm `reasoning_effort` → phải BỎ
  HẲN field, không phải đổi giá trị.
- `thinking:{type:"low"}` cũng 400 — `low/high/max` là giá trị của
  `reasoning_effort` (chuẩn OpenAI), không phải của `thinking.type`.
- `reasoning_effort:"minimal"` (OpenAI có) → 400. z.ai chỉ nhận **low · high · max**.
- Model chưa mở cho gói của tài khoản thì trả **429 `1302 Rate limit reached`**
  chứ không phải 404/403 — đừng đọc nhầm thành nghẽn nhịp. Cách phân biệt: gọi
  model khác ngay sau đó, nếu model kia OK thì là chuyện quyền model.

Ba app tự dựng payload nên mỗi app có một hàm nhận diện đời model (Luật 4 của
`kien_truc_nen.md`: không import chéo app). Thêm model mới bị 1210 thì thêm tiền
tố vào đúng một hằng, không sửa logic:

| App | Hằng | Chỗ dùng |
|---|---|---|
| seo-optimize | `LUON_THINKING` — `seo/llm.py` | `_openai_compat`, nhánh `no_think` |
| content-ultimate | `LUON_THINKING` — `src/oe/llm.py` | `LLM.complete` |
| niche-research | `_GLM_ALWAYS_THINKING` — `scripts/llm_provider.py` | chỗ dựng `extra_body` |

Mức suy luận đổi được qua env `LLM_REASONING_EFFORT` / `GLM_REASONING_EFFORT`
(mặc định `low`).

**ai-agent + data-analytics KHÔNG nằm trong bảng trên**: chúng đi qua adapter đa
nhà `src/llm/openai_compatible.py` (dùng chung cho ChatGPT/DeepSeek/Grok), không
gửi `thinking` nên 5.3 chạy được — nhưng cũng không hạ được mức, mỗi lượt kèm vài
trăm token reasoning. Muốn hạ phải thêm nhánh có điều kiện vào adapter đó.

## 3. Đổi model: bấm ở đâu, restart cái gì

1. `General > API Keys` **tab 1**: ô Model của khóa GLM — đổi ô này là mọi việc
   đang để "theo khóa" đi theo.
2. **tab Per-app config**: ô Model của từng việc (dropdown từ 23/08 — trước là gõ
   tay, sai chính tả id model là hỏng lặng lẽ). Chọn `— theo khóa —` để bỏ model
   riêng, trả việc đó về model của khóa.
3. Restart **ai-agent** + **data-analytics** (2 app nạp lúc khởi động). Các app
   khác lấy mỗi lần chạy, không cần.

Gợi ý model trong dropdown: `MODEL_GOI_Y` trong `nen/ket_cau_hinh/ket.py` — z.ai
ra bản mới thì thêm một dòng ở đó (và restart gateway, task không có `--reload`).

Dừng dịch vụ để restart: **theo CỔNG đang nghe**, không bao giờ theo tên tiến
trình (sự cố giết nhầm cả hệ 21/08). `tools/scripts/start-all.ps1` idempotent —
chỉ bật cái nào đang tắt.

## 4. Mặc định hardcode trong app (lưới cuối, khi két không nói gì)

| App | Chỗ | Giá trị |
|---|---|---|
| content-ultimate | `src/oe/llm.py` · `src/voiceprofile/llm.py` | `glm-5.2` |
| niche-research | `scripts/llm_provider.py` `_GLM_DEFAULT_MODEL` | `glm-5.2` |
| seo-optimize | `seo/llm.py` `_default_model` | `glm-5.2` |
| radary | `radary/llm.py` `DEFAULT_MODEL` | `glm-5.2` |

Giữ ở bản ĐANG CHẠY ỔN, không trỏ bản mới nhất: mặc định là lưới an toàn cho lúc
két im lặng, trỏ vào model chưa chắc gọi được là biến lưới thành bẫy. RadarY từng
để `glm-4-plus` — id đã biến mất khỏi `/models` của z.ai, tức phần diễn giải LLM
của nó hỏng lặng lẽ cho tới 23/08.

RadarY còn giữ bảng `llm_config` RIÊNG trong DB của nó (org-level, tab Quản trị
của app) cho phần diễn giải — chỗ này KHÔNG đọc két, phải đổi riêng.

## 5. Hiện trạng (23/08/2026, sau khi Owner đổi khóa GLM sang glm-5.3)

| App | Việc | Model thật đang nhận |
|---|---|---|
| niche-research | phan_tich | **glm-5.3** (theo khóa) |
| seo-optimize | sinh_metadata | **glm-5.3** (theo khóa) |
| radary | dien_giai | **glm-5.3** (theo khóa) |
| ai-agent | critic | **glm-5.3** (theo khóa) |
| data-analytics | phan_bien | **glm-5.3** (theo khóa) |
| content-ultimate | viet_kich_ban | `glm-5.2` (đặt riêng, đang đè) |
| content-ultimate | phan_tich_outline | `glm-5.2` (đặt riêng, đang đè) |
| ai-agent | extract | `glm-5` (đặt riêng, đang đè) |
| data-analytics | dien_giai | `glm-5` (đặt riêng, đang đè) |
| ai-agent | writer | `glm-4.5-air` — Owner chốt GIỮ (nhanh/rẻ cho việc rút gọn tài liệu) |

Bốn dòng "đang đè" muốn lên 5.3 thì đổi ở tab Per-app config, hoặc chọn
`— theo khóa —`. **ai-agent · writer hiện có 0 khóa được cấp** → theo luật két là
tắt tường minh, app rơi về mock; đây là việc treo riêng, không liên quan model.

Nghiệm thu sống 23/08 (gọi thật, không phải mock): seo `_openai_compat` json_mode
ra JSON đúng với cả 5.2 và 5.3; content-ultimate `LLM.complete` (SSE) ra câu hoàn
chỉnh cả hai; niche `llm_provider.call` (SSE) ra câu hoàn chỉnh cả hai. 5.3 chậm
hơn 5.2 khoảng 1.5-2 lần cho câu ngắn (2.1-2.4s vs 1.0-1.5s).

## 6. Việc treo

- Hạ mức suy luận cho ai-agent + data-analytics (adapter đa nhà) — chưa làm, cân
  nhắc vì adapter dùng chung nhiều nhà.
- ai-agent · writer chưa được cấp khóa → hỏi-đáp đang mock.
- RadarY `llm_config` trong DB app vẫn phải đổi bằng tay ở tab Quản trị của nó;
  cân nhắc cho nó đọc thẳng két như các app khác.
