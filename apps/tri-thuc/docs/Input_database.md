# Input Database — Đặc tả Module Nhập Liệu (mang sang VSCode để code)

*Chốt ngày 18/07/2026. Kiến trúc: **Lõi có sẵn + Vỏ riêng**. Không phát minh lại bánh xe.*

---

## 1. Quyết định lõi: chọn RAGFlow

Sau khi so sánh 3 công cụ RAG mã nguồn mở phổ biến làm lõi lưu trữ + tìm kiếm, **chọn RAGFlow**.

| Lõi | Metadata tùy ý qua API | Lọc tìm kiếm theo metadata qua API | Chạy headless (engine ẩn) | Đọc tài liệu khó/bảng | Giấy phép | Kết luận |
|---|---|---|---|---|---|---|
| **RAGFlow** | ✅ Có (`meta_fields`) | ✅ Có (`metadata_condition`) | ✅ Thiết kế cho việc này | ✅ Tốt nhất | Apache 2.0, không bẫy | **CHỌN** |
| Onyx | ✅ Có | ⚠️ Không rõ ràng (dùng "document sets") | ✅ Được | Khá | MIT core, **RBAC/SSO trả phí** | Nhì — nếu cần phân quyền chặt (tốn phí) |
| AnythingLLM | ❌ Chỉ vài trường cố định | ❌ Chỉ lọc theo workspace | ⚠️ Monolithic, sống bên trong | Khá | MIT, không bẫy | Ba — vụng cho kiến trúc metadata |

**Vì sao RAGFlow:** là lõi **duy nhất** vừa cho gắn metadata tùy ý (department, doc_type,
effective_status...) vừa cho **lọc tìm kiếm theo metadata** qua API công khai → khớp 1-1 với
dropdown 5 bộ phận + lọc hiệu lực + trích nguồn của mình. Đọc tài liệu khó tốt nhất (quan
trọng cho chẩn đoán số liệu). Apache 2.0, miễn phí cho công ty, không bẫy giấy phép.

**API chính của RAGFlow sẽ dùng** (docs: https://ragflow.io/docs/http_api_reference):
- Nạp tài liệu: `POST /api/v1/datasets/{dataset_id}/documents`
- Gắn/sửa metadata: `POST /api/v1/datasets/{dataset_id}/metadata/update`
- Lấy danh sách giá trị metadata (để tự đổ vào dropdown): `GET /api/v1/datasets/{dataset_id}/metadata/summary`
- Tìm + lọc: `POST /api/v1/retrieval` (nhận `metadata_condition` với toán tử is/contains/in/>/<; trả về chunk + `document_metadata` để trích nguồn)

---

## 2. Kiến trúc Lõi + Vỏ — ghép lại được gì

```
        VỎ RIÊNG (code trong VSCode)                  LÕI RAGFlow (Docker, trên PC LAN)
   ┌─────────────────────────────────────┐        ┌──────────────────────────────────────┐
   │ 1. Module NHẬP LIỆU                  │        │  Nhận file + metadata                │
   │    - Web kéo-thả                     │──API──►│  Đọc/OCR tài liệu khó, bảng biểu     │
   │    - Dropdown 5 bộ phận (bắt buộc)   │        │  Cắt nhỏ + đánh chỉ mục (vector)     │
   │    - Kiểm định dạng, cảnh báo scan   │        │  LƯU TRỮ — không rời PC LAN           │
   │ 2. Vòng PHẢN BIỆN                    │◄─API──►│  Tìm + LỌC theo metadata → trả về    │
   │    (gọi Claude API để suy luận)      │        │  đoạn tài liệu + nguồn để trích dẫn   │
   │ 3. CHẨN ĐOÁN số liệu                 │──API──►│  Tra Playbook liên quan trong kho    │
   └─────────────────────────────────────┘        └──────────────────────────────────────┘
        (phần TẠO GIÁ TRỊ RIÊNG)                        (phần KHÔNG PHÁT MINH LẠI)
```

- **Lõi lo:** lưu trữ, đọc/OCR, cắt nhỏ, đánh chỉ mục vector, tìm kiếm ngữ nghĩa, lọc metadata.
  Chạy local → tài liệu không rời công ty. Tiết kiệm hàng tháng công sức.
- **Vỏ lo:** giao diện nhập liệu + dropdown bắt buộc, vòng phản biện, chẩn đoán số liệu.
  Đây là phần không công cụ nào có sẵn — đáng để dồn sức code (~1/3 khối lượng; lõi gánh 2/3).
- **Kết quả:** Agent giữ bí mật (local) + thông minh (Claude API) + đáng tin (lọc metadata +
  trích nguồn + phản biện).

---

## 3. Module Nhập Liệu — luồng vận hành

1. Người dùng mở trang web LAN → **kéo-thả** một/nhiều file.
2. **Kiểm định dạng trước khi nhận** — cảnh báo nếu là PDF scan chưa OCR / ảnh (theo Nguyên tắc 5
   của `file_arrangement.md`). AI đọc chữ thật tốt, đọc ảnh của chữ thì kém.
3. Với mỗi file: điền metadata (dropdown bắt buộc + vài ô gõ tay) — **không để AI đoán**.
4. Bấm **Lưu** → module: (a) tự đổi tên file theo khuôn chuẩn, (b) đẩy file + metadata vào lõi
   RAGFlow qua API, (c) chép file vào đúng ngăn thư mục theo Bộ phận, (d) ghi 1 dòng vào **sổ
   danh mục chung** `_catalog.csv`, (e) chèn **thẻ mô tả** vào đầu file.

**3 quy tắc an toàn bắt buộc:**
- Kiểm định dạng, cảnh báo scan/ảnh trước khi nhận.
- **Không ghi đè** — trùng tên thì tự thêm hậu tố, không bao giờ mất file.
- **Sổ danh mục chỉ ghi thêm, không sửa dòng cũ** — giữ lịch sử.

---

## 4. Khung metadata (dựa chuẩn Dublin Core, customize 5 bộ phận)

### Người nhập GÕ TAY
| Trường | Ý nghĩa / vì sao cần |
|---|---|
| **Tiêu đề** | Tên rõ nghĩa; là thứ Agent hiển thị khi trích nguồn. |
| **Chủ đề / Từ khóa** | Vài từ khóa; giúp Agent tìm đúng cả khi người hỏi dùng từ khác. |
| **Phụ trách** | Ai chịu trách nhiệm nội dung; để biết hỏi ai khi cần cập nhật. |

### DROPDOWN (giá trị cố định — để dữ liệu sạch, nhất quán)
| Trường | Giá trị | Vì sao cần |
|---|---|---|
| **Bộ phận** | Ban quản trị / Hành chính Nhân sự / IT / Vận hành - Sản xuất / Kinh doanh | Quyết định ngăn thư mục + nền phân quyền. |
| **Loại tài liệu** | Quy trình / Chính sách / Hướng dẫn / Biểu mẫu / Playbook / Báo cáo / Chiến lược / Khác | Cho Agent lọc trước khi tìm → chính xác hơn. |
| **Hiệu lực** | Còn hiệu lực / Hết hiệu lực / Bản nháp | **Trường hay quên & hối tiếc nhất** — ngăn Agent trích tài liệu đã bỏ. |
| **Phiên bản** | v1 / v2 / v3… | Biết đâu là bản mới nhất. |
| **Mức truy cập** | Công khai nội bộ / Giới hạn theo bộ phận / Mật | Nền cho phân quyền (Giai đoạn 4). |

### MÁY TỰ ĐIỀN
| Trường | Ý nghĩa |
|---|---|
| **Ngày nhập** | Hôm nay; lọc theo thời gian. |
| **Mã tài liệu** | ID cố định (vd `KD-2026-0042`), **tách khỏi tên file** → chống trùng, không mất dấu dù đổi tên. |
| **Định dạng** / **Tên file gốc** | Truy vết + cảnh báo scan. |

> **Bộ phận trong dropdown = tên ngăn thư mục**, khớp 1-1:
> Ban quản trị → `01_Ban-quan-tri` · Hành chính Nhân sự → `02_Hanh-chinh-Nhan-su` ·
> IT → `03_IT` · Vận hành - Sản xuất → `04_Van-hanh-San-xuat` · Kinh doanh → `05_Kinh-doanh`
> (Kinh doanh là bộ phận chủ đạo dùng tool). Thêm `00_Chung`, `06_Playbook`, `99_Luu-tru`.

---

## 5. Cấu trúc công ty (nền cho dropdown Bộ phận)

1. **Ban quản trị** — quyết định chiến lược, tài chính.
2. **Hành chính Nhân sự** — tuyển dụng, quản lý nhân sự.
3. **IT** — bảo mật, quản lý farming email.
4. **Vận hành - Sản xuất** — Content Writer, Editor; sản xuất video.
5. **Kinh doanh** — đăng video lên YouTube, kiếm tiền Adsense. **Bộ phận chủ đạo dùng tool.**

---

## 6. Bẫy cần tránh (đúc kết từ cộng đồng RAG)

- Đừng nhồi tài liệu bẩn / PDF scan chưa OCR vào kho (rác vào → rác ra).
- Đừng bỏ qua metadata (đang làm đúng).
- Đừng quên trường **Hiệu lực** → Agent trích tài liệu hết hạn.
- Đừng để kho phình to với tài liệu cũ trùng lặp — dọn định kỳ.
- Tách **Mã tài liệu** khỏi tên file.
- **Thiết kế xong khung metadata + quy tắc TRƯỚC khi code** (đang làm đúng — bước quan trọng nhất).

---

## 7. Việc trước khi cam kết + lưu ý cấu hình PC

- **RAGFlow nặng để cài:** cần **Docker** + PC **RAM kha khá** (khuyến nghị ≥16GB). Con PC văn
  phòng cũ trong kế hoạch LAN cần kiểm tra, có thể phải **nâng RAM**. Nếu quá yếu → tính lõi nhẹ hơn.
- **Thử nửa buổi (spike) trước khi xây tiếp:** gọi thử 3 API RAGFlow —
  (1) nạp 1 tài liệu kèm metadata `Bộ phận` → (2) `metadata/update` → (3) `retrieval` với
  `metadata_condition` lọc đúng bộ phận đó. Chạy thông vòng tròn này rồi mới code module đầy đủ.

---

## Nguồn tham khảo
- RAGFlow HTTP API: https://ragflow.io/docs/http_api_reference | Set metadata: https://ragflow.io/docs/set_metadata
- RAGFlow LICENSE (Apache 2.0): https://github.com/infiniflow/ragflow/blob/main/LICENSE
- Onyx dev API: https://docs.onyx.app/developers/overview | EE (tính năng trả phí): https://docs.onyx.app/deployment/miscellaneous/enterprise_edition
- AnythingLLM API: https://docs.anythingllm.com/features/api
- Dublin Core (15 trường): https://www.dublincore.org/specifications/dublin-core/usageguide/elements/
- Metadata cho RAG (Unstructured): https://unstructured.io/insights/how-to-use-metadata-in-rag-for-better-contextual-results
- 7 lỗi RAG thường gặp (kapa.ai): https://www.kapa.ai/blog/rag-gone-wrong-the-7-most-common-mistakes-and-how-to-avoid-them
