# Phòng thủ API bên thứ 3 — spec + hiện trạng

> Sổ chủ đề, mở 05/09/2026 theo chốt của Owner: "nếu bắt buộc dùng API bên thứ 3
> thì xây lớp phòng thủ cho CRM ra sao". Nguồn sự thật là CODE — đổi luật phải
> cập nhật cả sổ này. Module van: `nen/common/phong_thu.py`; điểm nối:
> `apps/<app>/src/llm/` (ai-agent + data-analytics).

## Triết lý

API bên thứ 3 mang đúng 3 loại rủi ro → 3 nhóm phòng thủ, cộng 2 lớp nền:

1. **Lộ dữ liệu** (gửi ra ngoài) → lớp Cửa-ra-dữ-liệu.
2. **Phụ thuộc sẵn sàng** (nhà cung cấp chết/chậm/đổi giá) → lớp Chịu-lỗi.
3. **Tin nhầm đầu ra** (bịa, prompt injection) → lớp Không-tin-đầu-ra.
4. Nền: **Key + mạng** và **Sổ sách + cảnh báo**.

Quy tắc fail của van (`nen/common/phong_thu.py`): vi phạm CHỦ ĐÍCH → raise
`LoiPhongThu`, lỗi NỔI với thông điệp rõ (cùng họ LLM_RETRY=0); lỗi NỘI BỘ của
chính van (sổ hỏng, env rác) → bỏ qua van đó, KHÔNG giết call thật; app chạy
độc lập không có `nen` (bản đóng gói lite) → van tự tắt, hành vi cũ không đổi.

## Lớp 1 — Cửa ra dữ liệu

- [x] Kho tài liệu không rời máy, chỉ gửi vài chunk liên quan (kiến trúc gốc 18/07).
- [x] Nội dung vault không bao giờ vào prompt (vault chưa vào V3; luật ghi sẵn).
- [x] **Helper `che_pii(text, bang_ten)`** (05/09): che email + SĐT VN, kèm bảng
      {tên thật → mã NS-xxx} thì che cả tên. **LUẬT**: tính năng mới nào cho LLM
      đọc dữ liệu NHÂN SỰ (KPI, chấm công, hồ sơ) PHẢI gọi `che_pii` trước khi
      ghép prompt — hiện chưa mạch nào gửi dữ liệu nhân sự ra LLM, helper nằm chờ.
- Phân loại dữ liệu 2 nấc: **cấm tuyệt đối rời máy** = vault, iam.db/hash mật
  khẩu, SĐT/email/lương hồ sơ, chấm công; **được trích đoạn** = chunk tài liệu,
  số liệu báo cáo (đã che PII nếu dính nhân sự).

## Lớp 2 — Key + mạng

- [x] Key trong KÉT, UI write-only 4 số cuối, ghi .env nguyên tử (lệ từ V2).
- [x] Mỗi mục đích một key, pool YouTube xoay vòng khi 403.
- [x] **Van `kiem_host`** (05/09): BASE_URL của provider phải là **https** + host
      nằm trong allowlist (`HOST_MAC_DINH`: api.anthropic.com, api.openai.com,
      api.z.ai, open.bigmodel.cn, api.deepseek.com, api.x.ai; thêm host qua .env
      `LLM_HOST_CHO_PHEP=a.com,b.com`). Loopback được miễn (mock/dev). Chặn NGAY
      lúc dựng client — .env bị sửa/gõ nhầm trỏ prompt + key sang server lạ là
      chết từ cửa, không đợi tới lúc gọi.
- [x] **Van `kiem_secret`** (05/09): giá trị secret trong env (tên khớp
      API_KEY/SECRET/TOKEN/PASSWORD/MAT_KHAU, dài ≥12) xuất hiện NGUYÊN VĂN trong
      prompt → chặn call. Bắt cả bug code ghép nhầm lẫn tài liệu chứa key thật.
- [x] Script audit `tools/scripts/soi-egress.ps1` (CHỈ ĐỌC): chụp kết nối TCP ra
      ngoài theo tiến trình, tô đỏ đích lạ ngoài LAN/allowlist — Owner chạy tay
      định kỳ.
- [ ] **VIỆC TREO CỦA USER**: rotate 2 key YouTube đã lộ trong lịch sử GitHub
      repo niche-research cũ (nợ từ 18/08).
- [ ] Firewall outbound default-deny theo tiến trình: Windows Firewall không lọc
      được theo DOMAIN (IP anycast của API đổi liên tục) — muốn làm thật cần
      forward proxy riêng. Ghi nhận là phương án NÂNG CAO, chưa làm; van
      `kiem_host` trong code là tuyến thay thế hiện tại.

## Lớp 3 — Chịu lỗi (API chết không kéo CRM chết)

- [x] `LLM_TIMEOUT` (mặc định 60s) + `LLM_RETRY=0` — lỗi nổi ngay (bài học 19/07 + 06/08).
- [x] Van an toàn kiểu `_kho_ok`: dịch vụ ngoài chết → tính năng phụ thuộc tắt
      mềm, app vẫn lên (bài học Docker sập 02/08).
- [x] Việc chậm chạy NỀN (BackgroundTasks/_TAC_VU), không khóa event loop.
- [x] Fallback nhà cung cấp: đổi model/nhà qua két + .env không sửa code
      (docs/model-llm.md; 429 theo model → đổi model là fix nhanh).
- **LUẬT**: phần lõi CRM (nhân sự, chấm công, phân quyền, vault) KHÔNG được phụ
  thuộc bất kỳ API ngoài nào — API chỉ phục vụ tầng diễn giải/suy luận.

## Lớp 4 — Không tin đầu ra

- [x] Van chống bịa + vòng phản biện + kiểm verbatim (xương sống từ GĐ1).
- [x] Đầu ra LLM không tự động ghi/xóa dữ liệu — luôn có người duyệt (Q&A/bài học).
- **LUẬT prompt injection**: nội dung tầng `ngoai`/`chuyen_gia` (transcript, tài
  liệu ngoài) chỉ được làm DỮ LIỆU để phân tích, không bao giờ nối vào phần CHỈ
  THỊ của prompt.

## Lớp 5 — Sổ sách + cảnh báo

- [x] Sổ gọi tập trung `nen/common/so_goi.py`: 1 dòng/call, token + USD chốt
      lúc ghi, chi phí theo app (Command Center, 01-03/09).
- [x] **Vá 05/09: đường STREAM ghi sổ** — trước đó `generate_stream` (đường tiêu
      CHÍNH của hỏi–đáp) không ghi dòng nào → trần/ngày và Command Center mù
      đường tiêu lớn nhất. Giờ stream ghi call + ms + ok/lỗi; token stream chưa
      đo (OpenAI cần `stream_options include_usage`, GLM chưa chắc hỗ trợ —
      `ponytail:` trần USD chưa thấy phần stream, trần CALL thấy đủ).
- [x] **Van `kiem_tran`** (05/09): trần LLM/ngày qua .env — `LLM_TRAN_USD_NGAY`
      (chỉ cộng dòng có usd) + `LLM_TRAN_CALL_NGAY` (đếm mọi call llm, kể cả
      stream/lỗi — thước tin cậy hơn). 0/bỏ trống = TẮT (mặc định — không đổi
      hành vi hệ đang chạy; Owner bật bằng 1 dòng .env, gợi ý 5 USD + 500 call).
      Vượt trần → chặn call với thông điệp nói rõ cách nâng.
- [x] Secret không lọt log: sổ gọi chỉ ghi đuôi 4 ký tự key; `ma_loi` cắt 120 ký tự.

## Lớp 6 — Chọn nhà cung cấp

- Dữ liệu càng nhạy càng dồn về provider có cam kết KHÔNG train trên input +
  retention rõ (Anthropic API mặc định không train trên dữ liệu khách; Z.ai phải
  đọc điều khoản trước khi cho đọc dữ liệu nhóm nhân sự).
- **LUẬT**: mạch chạm dữ liệu người → chỉ đi qua provider đã duyệt trong sổ này.

## Điểm nối hiện tại (05/09)

Van chạy tại MỘT điểm-ra `src/llm/` (base.py gọi `phong_thu`), phủ:

| App | Đường LLM | Van host | Van secret+trần | Ghi sổ stream |
|---|---|---|---|---|
| ai-agent | src/llm (writer/critics/đa chiều/extract) | ✓ | ✓ | ✓ |
| data-analytics | src/llm (bản sao, APP_SO_GOI riêng) | ✓ | ✓ | ✓ |
| content-ultimate / seo-optimize / niche-research | client LLM riêng của app | CHƯA | CHƯA | app tự ghi so_goi qua loopback |

- [ ] Nối dần van vào 3 app tự đủ (mỗi app một đợt, đúng khuôn 6 bước APPS.md).

## Cấu hình .env (mẫu ở .env.example)

```
# LLM_TRAN_USD_NGAY=5        # trần USD LLM/ngày cả hệ (0/trống = tắt)
# LLM_TRAN_CALL_NGAY=500     # trần số call LLM/ngày (0/trống = tắt)
# LLM_HOST_CHO_PHEP=         # thêm host ngoài allowlist mặc định, ngăn bởi ','
```

Test: `tests/test_phong_thu.py` (unit 4 van) + `apps/ai-agent/tests/
test_phong_thu_llm.py` (nối dây provider) + stream-ghi-sổ trong
`apps/ai-agent/tests/test_so_goi_llm.py`.
