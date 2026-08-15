"""LÕI VECTOR: Qdrant (đổi chính thức từ RAGFlow, 18/07/2026).

Vỏ gọi qua đúng 2 hàm cùng chữ ký như lõi cũ — upload_document(file_path, metadata)
và search(query, filters) — nên toàn bộ vỏ (nhập liệu, hỏi–đáp, phản biện, chẩn đoán)
không phải sửa.

Best-practice áp từ qdrant/skills (_references/qdrant-skills):
- NAMED VECTORS "dense" + "sparse" định nghĩa sẵn từ đầu → bật hybrid sau này
  không phải đập collection xây lại.
- App trỏ qua ALIAS `kho_tri_thuc` (collection thật: `kho_v1`) → đổi model embedding
  chỉ cần re-embed vào collection mới rồi swap alias.
- PAYLOAD INDEX (keyword) cho department/effective_status tạo TRƯỚC khi nạp dữ liệu
  (Qdrant chỉ xây filterable HNSW cho field đã index trước — tạo sau là bẫy).
- Model e5 BẮT BUỘC tiền tố "passage: " cho tài liệu, "query: " cho câu hỏi —
  thiếu là chất lượng giảm thầm lặng. Distance = COSINE.
- HYBRID (dense + BM25 trộn RRF) MẶC ĐỊNH BẬT (đổi 18/07/2026): kho tiếng Việt
  nhiều mã/thuật ngữ gần nhau → BM25 khớp từ khóa chính xác bổ trợ cho dense.
  Tắt để đo baseline dense-only: HYBRID_SEARCH=false trong .env.
- RERANK (cross-encoder local, MẶC ĐỊNH BẬT): lấy RỘNG RERANK_LAY_RONG chunk (20)
  → cross-encoder chấm lại từng chunk theo câu hỏi → top SO_KET_QUA tinh nhất.
  Model qua RERANK_MODEL trong .env — không đóng cứng, giống writer/critic.
  Tắt: RERANK_SEARCH=false.

MOCK_MODE=true (mặc định): dữ liệu mẫu, không cần Qdrant/model.
CHẠY THẬT: đặt MOCK_MODE=false trong .env + Qdrant chạy ở QDRANT_URL
(docker run -p 6333:6333 qdrant/qdrant). Lần chạy thật đầu tiên sẽ tải
model embedding về máy (e5-large nặng cỡ GB) — chỉ tải một lần.
"""

import copy
import logging
import os
import re
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import models

load_dotenv()

COLLECTION = "kho_v1"
ALIAS = "kho_tri_thuc"
DENSE, SPARSE = "dense", "sparse"
SPARSE_MODEL = "Qdrant/bm25"
# Các trường QUYỀN TRUY XUẤT trong payload (lọc ai được thấy tài liệu) — đồng bộ khi sửa metadata nguy hiểm
QUYEN_FIELDS = ("department", "effective_status", "access_level", "min_level")


def _user_hieu_luc(user: dict | None) -> dict | None:
    """Cấp HIỆU LỰC (04/08/2026 — cần gạt 'truy cập theo cấp' trang Phân quyền):
    thay level thật bằng cấp Owner đặt (1..4) trước khi áp mọi luật xem tài liệu.
    Best-effort: lỗi đọc sổ lệ riêng → dùng level thật, tuyệt đối không chặn tìm."""
    if not user:
        return user
    try:
        from src import phan_quyen  # lazy — vector_client là tầng thấp
        return phan_quyen.hieu_luc(user)
    except Exception:
        return user
SO_KET_QUA = 5

# Dữ liệu mẫu cho chế độ mock — cùng cấu trúc chunk mà search() trả về.
# tang_nguon="noi_bo" trên CẢ 4 mục (07/08): khớp thật — mọi tài liệu nội bộ đều có trường
# này (Supervisor Bước 1); THIẾU trường ở mock (bug đã gặp) làm hỏi–đáp mặc định lọc
# tang_nguon=noi_bo (vá cùng ngày) tưởng nhầm "kho rỗng" trong mọi test dùng mock.
_MOCK_CHUNKS = [
    {
        "content": "Bước 1: Kiểm tra video đã đạt chuẩn duyệt của Editor. Bước 2: Đăng lên kênh "
                   "theo khung giờ 19h-21h. Bước 3: Điền tiêu đề, mô tả, thẻ tag theo mẫu SEO.",
        "document_id": "doc-mock-kd-0042",
        "document_keyword": "KD-2026-0042_Quy-trinh-dang-video-YouTube_v2.docx",
        "similarity": 0.91,
        "document_metadata": {
            "department": "Kinh doanh",
            "doc_type": "Quy trình",
            "effective_status": "Còn hiệu lực",
            "version": "v2",
            "access_level": "Công khai nội bộ",
            "doc_code": "KD-2026-0042",
            "min_level": 2,
            "tang_nguon": "noi_bo",
        },
    },
    {
        "content": "Editor xuất video bản final định dạng MP4 1080p, đặt tên theo khuôn "
                   "[Mã kênh]_[Ngày]_[Tên video], chuyển vào thư mục bàn giao cho Kinh doanh.",
        "document_id": "doc-mock-vh-0007",
        "document_keyword": "VH-2026-0007_Huong-dan-xuat-video_v1.pdf",
        "similarity": 0.84,
        "document_metadata": {
            "department": "Vận hành - Sản xuất",
            "doc_type": "Hướng dẫn",
            "effective_status": "Còn hiệu lực",
            "version": "v1",
            "access_level": "Giới hạn theo bộ phận",
            "doc_code": "VH-2026-0007",
            "min_level": 2,
            "tang_nguon": "noi_bo",
        },
    },
    {
        "content": "Khung giờ đăng video 12h-14h (bản cũ — đã thay bằng khung 19h-21h ở v2).",
        "document_id": "doc-mock-kd-0011",
        "document_keyword": "KD-2025-0011_Quy-trinh-dang-video-YouTube_v1.docx",
        "similarity": 0.78,
        "document_metadata": {
            "department": "Kinh doanh",
            "doc_type": "Quy trình",
            "effective_status": "Hết hiệu lực",
            "version": "v1",
            "access_level": "Công khai nội bộ",
            "doc_code": "KD-2025-0011",
            "min_level": 1,
            "tang_nguon": "noi_bo",
        },
    },
    {
        "content": "Chiến lược giá bán và chiết khấu nội bộ Q3: khung giá, mức giảm tối đa, "
                   "thẩm quyền duyệt theo cấp quản lý.",
        "document_id": "doc-mock-kd-0099",
        "document_keyword": "KD-2026-0099_Chien-luoc-gia_v1.docx",
        "similarity": 0.88,  # >= NGUONG_BI_CHAN — ca "bị chặn THẬT SỰ liên quan" trong test
        "document_metadata": {
            "department": "Kinh doanh",
            "doc_type": "Chiến lược",
            "effective_status": "Còn hiệu lực",
            "version": "v1",
            "access_level": "Mật",
            "doc_code": "KD-2026-0099",
            "min_level": 4,  # tài liệu Mật cấp Manager — để test lọc quyền
            "tang_nguon": "noi_bo",
        },
    },
]


def _doc_file(path: Path) -> str:
    """Trích chữ từ PDF/docx/Excel/csv/txt/md/html. File scan không có lớp chữ → chuỗi rỗng."""
    duoi = path.suffix.lower()
    if duoi == ".pdf":
        from pypdf import PdfReader

        return "\n".join((trang.extract_text() or "") for trang in PdfReader(str(path)).pages)
    if duoi in (".html", ".htm"):
        # 02/08/2026: "file thường quy" của user là trang HTML in ra PDF ảnh (0 chữ,
        # OCR local rụng dấu tiếng Việt) — nạp thẳng bản .html gốc là chuẩn nhất:
        # gỡ script/style rồi lấy text, không cần thư viện ngoài.
        import html as html_mod
        import re as re_mod

        tho = path.read_text(encoding="utf-8", errors="ignore")
        tho = re_mod.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", tho)
        tho = re_mod.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)[^>]*>", "\n", tho)
        tho = re_mod.sub(r"(?s)<[^>]+>", " ", tho)
        tho = html_mod.unescape(tho)
        return re_mod.sub(r"[ \t]{2,}", " ", tho)
    if duoi == ".docx":
        import docx

        return "\n".join(d.text for d in docx.Document(str(path)).paragraphs)
    if duoi in (".xlsx", ".xls"):
        import pandas as pd

        cac_sheet = pd.read_excel(path, sheet_name=None)
        return "\n\n".join(f"{ten}\n{bang.to_string(index=False)}"
                           for ten, bang in cac_sheet.items())
    if duoi == ".csv":
        import pandas as pd

        return pd.read_csv(path).to_string(index=False)
    return path.read_text(encoding="utf-8", errors="ignore")  # txt/md và file chữ khác


def _cat_doan(text: str, muc_tieu: int = 500, chong_lan: int = 50) -> list[str]:
    """Cắt tài liệu ở RANH GIỚI CÂU/ĐOẠN, không bao giờ giữa câu (skill: cắt giữa câu
    làm rớt chất lượng 30-40%). Mỗi chunk ~400-600 từ, chồng lấn ~50 từ giữ mạch."""
    cac_cau = [c.strip() for c in re.split(r"(?<=[.!?…])\s+|\n{2,}", text) if c.strip()]
    chunks, hien_tai, so_tu = [], [], 0
    for cau in cac_cau:
        tu = len(cau.split())
        if hien_tai and so_tu + tu > muc_tieu:
            chunks.append(" ".join(hien_tai))
            giu, dem = [], 0  # giữ các câu cuối làm phần chồng lấn
            for c in reversed(hien_tai):
                giu.insert(0, c)
                dem += len(c.split())
                if dem >= chong_lan:
                    break
            hien_tai, so_tu = giu, dem
        hien_tai.append(cau)
        so_tu += tu
    if hien_tai:
        chunks.append(" ".join(hien_tai))
    return chunks


class QdrantClientWrapper:
    def __init__(self, url: str | None = None, mock: bool | None = None,
                 hybrid: bool | None = None):
        if mock is None:
            mock = os.getenv("MOCK_MODE", "true").strip().lower() == "true"
        self.mock = mock
        if hybrid is None:
            # Mặc định BẬT trong CODE (không chỉ .env — .env bị gitignore, không theo
            # repo sang máy khác): hybrid là hành vi chuẩn của app ở mọi nơi
            hybrid = os.getenv("HYBRID_SEARCH", "true").strip().lower() == "true"
        self.hybrid = hybrid
        # Rerank: mặc định BẬT; tắt qua RERANK_SEARCH=false để quay lại hành vi cũ
        self.rerank_search = os.getenv("RERANK_SEARCH", "true").strip().lower() == "true"
        self.rerank_lay_rong = int(os.getenv("RERANK_LAY_RONG", "20"))
        # Ngưỡng cosine dense cho cờ bị-chặn-quyền (đo thật 19/07, scripts/do_nguong_bi_chan.py):
        # bị-chặn-thật 0.826-0.862 vs lọt-top-k-tình-cờ 0.776-0.803 → 0.81 dưới sàn nhóm thật.
        # ponytail: khe chỉ ~0.024 trên kho 22 chunk — đo lại khi kho đổi; kho lên hàng trăm
        # chunk nên chuyển sang cross-encoder rerank chấm liên quan (thang phân cực mạnh hơn).
        self.nguong_bi_chan = float(os.getenv("NGUONG_BI_CHAN", "0.81"))
        self._mock_upload_count = 0
        self._mock_chunks: dict[str, set] = {}    # mock: doc_code → set index chunk (mô phỏng Qdrant)
        self._mock_payload: dict[str, dict] = {}  # mock: doc_code → payload quyền (mô phỏng set_payload)
        if mock:
            return

        from fastembed import SparseTextEmbedding, TextEmbedding  # nặng — chỉ nạp khi thật
        from qdrant_client import QdrantClient

        # 127.0.0.1 CHỨ KHÔNG "localhost" (01/08/2026): Qdrant native chỉ nghe IPv4;
        # "localhost" làm Windows thử IPv6 ::1 trước → +2s MỖI kết nối, sidebar phiên
        # gọi Qdrant ~11 lần/trang render → trang 22-45s (đo thật). Docker cũ nghe cả
        # hai stack nên bệnh chỉ phát khi chuyển native.
        self.client = QdrantClient(url=url or os.getenv("QDRANT_URL", "http://127.0.0.1:6333"))
        # e5-large, KHÔNG phải -small: fastembed chỉ đóng gói bản -large;
        # bản -small làm TextEmbedding ném ValueError ngay lúc khởi động
        self.dense_model = TextEmbedding(
            os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large"))
        self.sparse_model = SparseTextEmbedding(SPARSE_MODEL)
        # Đo số chiều từ chính model → đổi EMBEDDING_MODEL trong .env không phải sửa code
        self.dense_dim = len(next(iter(self.dense_model.embed(["đo độ dài vector"]))))
        if self.rerank_search:
            from fastembed.rerank.cross_encoder import TextCrossEncoder  # nạp lazy như trên

            # Model rerank mặc định jina-reranker-v2 (đa ngôn ngữ, tiếng Việt tốt) —
            # LƯU Ý giấy phép CC-BY-NC (PHI thương mại). Cần giấy phép thương mại (MIT):
            # đổi .env RERANK_MODEL=BAAI/bge-reranker-base — KHÔNG sửa code.
            self.reranker = TextCrossEncoder(
                os.getenv("RERANK_MODEL", "jinaai/jina-reranker-v2-base-multilingual"))
        # VAN AN TOÀN (01/08/2026 — sự cố Docker sập 14:57): Qdrant chết KHÔNG được
        # giết cả app lúc khởi động (cổng 8000 gánh cả login + proxy 6 app + chấm
        # công, chúng không cần kho vector). Init hỏng → app vẫn lên, cờ _kho_ok
        # tắt; mỗi lượt dùng kho sẽ TỰ THỬ NỐI LẠI (_dam_bao_kho) — Qdrant sống
        # dậy là kho tự hồi, không cần restart app.
        try:
            self._khoi_tao_collection()
            self._kho_ok = True
        except Exception as e:
            self._kho_ok = False
            logging.warning("Kho vector (Qdrant) chưa sẵn sàng lúc khởi động — app vẫn chạy, "
                            "khối tri thức sẽ tự thử nối lại: %s", e)

    def _dam_bao_kho(self):
        """Gọi đầu mỗi thao tác kho thật: init trước đó hỏng → thử lại NGAY BÂY GIỜ
        (Qdrant có thể đã sống dậy). Vẫn hỏng → ném lỗi rõ nghĩa cho tầng trên."""
        if self._kho_ok:
            return
        try:
            self._khoi_tao_collection()
            self._kho_ok = True
            logging.info("Kho vector (Qdrant) đã nối lại được — khối tri thức hoạt động bình thường.")
        except Exception as e:
            raise ConnectionError(
                "Kho tri thức (Qdrant) đang mất kết nối — các phần khác của app vẫn "
                "hoạt động; kiểm tra dịch vụ Qdrant cổng 6333.") from e

    def _khoi_tao_collection(self):
        """Tạo collection + payload index + alias lúc khởi động nếu chưa có."""
        if not self.client.collection_exists(COLLECTION):
            self.client.create_collection(
                collection_name=COLLECTION,
                vectors_config={DENSE: models.VectorParams(
                    size=self.dense_dim, distance=models.Distance.COSINE)},
                sparse_vectors_config={SPARSE: models.SparseVectorParams(
                    modifier=models.Modifier.IDF)},  # IDF cho BM25
            )
        # Index TRƯỚC khi nạp dữ liệu → Qdrant xây filterable HNSW cho các trường lọc.
        # Gọi MỖI lần khởi động (idempotent) để collection CŨ cũng nhận index mới
        # (min_level thêm ở Mảnh B phân quyền)
        for truong, kieu in (("department", models.PayloadSchemaType.KEYWORD),
                             ("effective_status", models.PayloadSchemaType.KEYWORD),
                             ("min_level", models.PayloadSchemaType.INTEGER),
                             ("tang_nguon", models.PayloadSchemaType.KEYWORD)):  # Supervisor — gom theo tầng
            self.client.create_payload_index(COLLECTION, field_name=truong,
                                             field_schema=kieu)
        if ALIAS not in [a.alias_name for a in self.client.get_aliases().aliases]:
            self.client.update_collection_aliases(change_aliases_operations=[
                models.CreateAliasOperation(create_alias=models.CreateAlias(
                    collection_name=COLLECTION, alias_name=ALIAS))])

    def upload_document(self, file_path: str, metadata: dict) -> str:
        """Trích chữ → cắt đoạn → embed (dense + sparse) → nạp theo lô. Trả về document_id."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Không thấy file: {file_path}")
        if self.mock:
            self._mock_upload_count += 1
            # Mô phỏng upsert THEO INDEX (đúng ngữ nghĩa Qdrant): thêm index 0..n-1, KHÔNG xóa index
            # cũ cao hơn → để LỘ chunk mồ côi nếu không xóa trước. Test orphan dựa vào hành vi này.
            doc_id = metadata.get("doc_code") or path.stem
            try:
                n = len(_cat_doan(_doc_file(path)))
            except Exception:
                n = 0
            if n:
                self._mock_chunks.setdefault(doc_id, set()).update(range(n))
            self._mock_payload[doc_id] = {k: metadata.get(k) for k in QUYEN_FIELDS}  # payload quyền
            return f"doc-mock-{self._mock_upload_count:04d}"
        self._dam_bao_kho()

        doc_id = metadata.get("doc_code") or path.stem
        chunks = _cat_doan(_doc_file(path))
        if not chunks:
            # PDF scan/ảnh: không có chữ để nạp — file vẫn nằm trong kho 8 ngăn,
            # cảnh báo scan ở /upload đã dặn user OCR rồi nạp lại
            return doc_id

        dense_vecs = list(self.dense_model.embed([f"passage: {c}" for c in chunks]))
        sparse_vecs = list(self.sparse_model.embed(chunks))
        points = [
            models.PointStruct(
                # ID định danh từ doc_code + số thứ tự chunk (Qdrant cần UUID/số) →
                # nạp lại bản sửa cùng doc_code là GHI ĐÈ, không nhân bản
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}#{i}")),
                vector={
                    DENSE: dense_vecs[i].tolist(),
                    SPARSE: models.SparseVector(
                        indices=sparse_vecs[i].indices.tolist(),
                        values=sparse_vecs[i].values.tolist()),
                },
                payload={**metadata, "content": chunks[i], "chunk_index": i,
                         "file_name": path.name},
            )
            for i in range(len(chunks))
        ]
        self.client.upload_points(ALIAS, points=points, batch_size=64, max_retries=3)
        return doc_id

    def _filter_doc_code(self, doc_code: str):
        return models.Filter(must=[models.FieldCondition(
            key="doc_code", match=models.MatchValue(value=doc_code))])

    def xoa_chunk_doc_code(self, doc_code: str) -> None:
        """XÓA SẠCH mọi chunk của doc_code theo FILTER (KHÔNG theo index) — bản mới ít chunk hơn
        bản cũ thì các chunk thừa cũ KHÔNG còn sót lại như rác (chống chunk mồ côi). Mock: pop store."""
        if self.mock:
            self._mock_chunks.pop(doc_code, None)
            return
        self.client.delete(ALIAS, points_selector=models.FilterSelector(
            filter=self._filter_doc_code(doc_code)))

    def dem_chunk_doc_code(self, doc_code: str) -> int:
        """Đếm chunk hiện có của doc_code trong Qdrant — kiểm chứng sau đồng bộ (lớp an toàn cuối)."""
        if self.mock:
            return len(self._mock_chunks.get(doc_code, ()))
        return self.client.count(ALIAS, count_filter=self._filter_doc_code(doc_code),
                                 exact=True).count

    def dem_point_kho(self) -> int | None:
        """Tổng point trong kho — LƯỚI CẢNH BÁO (31/07/2026): phát hiện ca 'catalog có tài
        liệu nhưng Qdrant rỗng' (kho chết lặng lẽ 29-31/07 không ai nhận ra: container tạo
        lại/volume mới → hỏi-đáp không trích được gì mà không báo lỗi). None = KHÔNG kết nối
        được Qdrant (Docker chưa chạy…) — người gọi tự phân biệt 'rỗng' với 'không nối được'.
        Mock trả None (không có kho thật để cảnh báo)."""
        if self.mock:
            return None
        try:
            return self.client.count(ALIAS, exact=True).count
        except Exception:
            return None

    def cap_nhat_noi_dung(self, file_path: str, metadata: dict) -> dict:
        """CẬP NHẬT NỘI DUNG tài liệu (thao tác NẶNG, chạm truy xuất). Trình tự CHỐNG CHUNK MỒ CÔI:
        (1) XÓA SẠCH chunk cũ theo doc_code TRƯỚC (không theo index); (2) nạp chunk mới (TÁI DÙNG
        pipeline upload_document — không viết lại); (3) đếm lại kiểm chứng. Payload chunk mới giữ
        đúng quyền truy xuất trong `metadata` (do người gọi lấy từ catalog — cập nhật nội dung KHÔNG
        đổi quyền). VAN AN TOÀN: file mới không có chữ (scan chưa OCR) → RAISE TRƯỚC khi xóa để KHÔNG
        mất nội dung cũ. Trả {so_cu, so_moi, du_kien}."""
        doc_code = metadata.get("doc_code") or Path(file_path).stem
        du_kien = len(_cat_doan(_doc_file(Path(file_path))))
        if du_kien == 0:
            raise ValueError("File mới không có nội dung text để nạp (PDF scan chưa OCR?) — "
                             "chưa cập nhật để không xóa mất nội dung cũ.")
        so_cu = self.dem_chunk_doc_code(doc_code)
        self.xoa_chunk_doc_code(doc_code)            # BƯỚC 4: xóa sạch chunk cũ theo doc_code TRƯỚC
        self.upload_document(file_path, metadata)    # rồi nạp mới (cùng UUID5 doc_code#i, không mồ côi)
        so_moi = self.dem_chunk_doc_code(doc_code)   # BƯỚC 6: đếm lại xác nhận khớp, không dư
        if so_moi != du_kien:
            logging.warning("Cập nhật nội dung %s: chunk sau nạp (%d) KHÁC kỳ vọng (%d) — Owner kiểm tra!",
                            doc_code, so_moi, du_kien)
        return {"so_cu": so_cu, "so_moi": so_moi, "du_kien": du_kien}

    def cap_nhat_payload_doc_code(self, doc_code: str, payload_moi: dict) -> None:
        """CẬP NHẬT PAYLOAD QUYỀN cho MỌI chunk của doc_code theo FILTER doc_code (set_payload, KHÔNG
        xóa-nạp lại nội dung — nội dung không đổi, chỉ đổi trường quyền). payload_moi: các trường trong
        QUYEN_FIELDS cần đặt lại (department/effective_status/access_level/min_level). wait=True để bền
        trước khi trả (kiểm chứng đọc lại mới đáng tin). Mock: cập nhật store payload."""
        if self.mock:
            self._mock_payload.setdefault(doc_code, {}).update(payload_moi)
            return
        self.client.set_payload(ALIAS, payload=payload_moi, wait=True,
                                points=models.FilterSelector(filter=self._filter_doc_code(doc_code)))

    def doc_payload_mau(self, doc_code: str) -> dict | None:
        """Đọc payload của MỘT chunk của doc_code (kiểm chứng sau đồng bộ — biến 'hy vọng đồng bộ đúng'
        thành 'chứng minh đồng bộ đúng'). None nếu không còn chunk nào. Chỉ trả các trường QUYỀN."""
        if self.mock:
            pl = self._mock_payload.get(doc_code)
            return {k: pl.get(k) for k in QUYEN_FIELDS} if pl else None
        diem, _ = self.client.scroll(ALIAS, limit=1, with_payload=True,
                                     scroll_filter=self._filter_doc_code(doc_code))
        if not diem:
            return None
        pl = diem[0].payload or {}
        return {k: pl.get(k) for k in QUYEN_FIELDS}

    @staticmethod
    def _duoc_xem(md: dict, user: dict) -> bool:
        """LUẬT XEM (Mảnh B, chốt với user): thấy tài liệu KHI công khai nội bộ
        (mọi bộ phận, mọi level) HOẶC (đúng bộ phận user VÀ min_level <= level user).
        min_level THIẾU → ẨN với user thật (an toàn, không lọt tài liệu chưa gán).

        OWNER TOÀN QUYỀN (user chốt 30/07/2026): level 5 thấy MỌI tài liệu.
        MANAGER+ (user chốt 31/07/2026 "truy cập được tất cả tài liệu"): level >= 4
        bỏ rào BỘ PHẬN — thấy tài liệu mọi bộ phận, chỉ còn kiểm min_level (tài liệu
        gắn min_level 5 vẫn của riêng Owner; kho hiện chưa có tài liệu nào như vậy
        nên Manager thấy tất).
        04/08/2026: cấp HIỆU LỰC (cần gạt 'truy cập theo cấp' trang Phân quyền)
        thắng chức danh thật — Owner thật không bao giờ bị hạ."""
        user = _user_hieu_luc(user)
        if user.get("level", 0) >= 5:
            return True
        if md.get("access_level") == "Công khai nội bộ":
            return True
        ml = md.get("min_level")
        if not isinstance(ml, int):
            return False
        if user.get("level", 0) >= 4:
            return ml <= user["level"]
        return md.get("department") == user["bo_phan"] and ml <= user["level"]

    def metadata_theo_doc_code(self, cac_ma: list[str]) -> dict[str, dict]:
        """Tra metadata (department/access_level/min_level...) theo doc_code — MỘT lần
        cho cả lô (D2 lọc lịch sử dùng). Mã không còn trong kho → vắng mặt trong kết quả
        (caller coi như không được xem — ẩn an toàn)."""
        can_tra = set(cac_ma)
        if not can_tra:
            return {}
        if self.mock:
            return {c["document_metadata"]["doc_code"]: dict(c["document_metadata"])
                    for c in _MOCK_CHUNKS
                    if c["document_metadata"]["doc_code"] in can_tra}
        diem, _ = self.client.scroll(
            ALIAS, limit=5000, with_payload=True,
            scroll_filter=models.Filter(must=[models.FieldCondition(
                key="doc_code", match=models.MatchAny(any=sorted(can_tra)))]),
        )
        ket_qua: dict[str, dict] = {}
        for p in diem:
            pl = p.payload or {}
            ma = pl.get("doc_code")
            if ma and ma not in ket_qua:
                ket_qua[ma] = pl
        return ket_qua

    def search_co_bi_chan(self, query: str, filters: dict | None = None,
                          user: dict | None = None) -> bool:
        """RULE 2 (đã sửa bug): kiểm 'có tài liệu BỊ CHẶN QUYỀN khớp câu hỏi không' —
        đúng cả khi kết quả có-quyền KHÔNG rỗng (bug cũ: chỉ kiểm khi rỗng nên bỏ sót
        ca 'thấy MMO được phép nhưng sót AdSense level 4 bị chặn').

        Cơ chế: truy vấn BỎ filter quyền (giữ filter nghiệp vụ), soi từng chunk bằng
        CHÍNH luật _duoc_xem, và chunk bị chặn CHỈ TÍNH khi cosine dense với câu hỏi
        >= NGUONG_BI_CHAN — vector search luôn trả đủ k hàng xóm nên kho nhỏ thì tài
        liệu bị chặn lọt top-k của gần như MỌI câu (dương tính giả, đo 19/07). Chấm
        bằng cosine dense THUẦN chứ không phải điểm RRF của search(): RRF là điểm
        theo hạng (1/(k+rank)), lọt top tình cờ vẫn điểm cao → không tách được.

        CHỈ để ghi ngầm vào feedback/log; user vẫn thấy "chưa có tài liệu", KHÔNG lộ
        tài liệu tồn tại. True = kho CÓ tài liệu liên quan nhưng bị chặn."""
        user = _user_hieu_luc(user)   # 04/08: cần gạt truy-cập-theo-cấp áp trước luật
        if not (user and user.get("bo_phan")):
            return False  # chế độ mở / chưa đăng nhập: không có filter quyền → không thể bị chặn
        if user.get("level", 0) >= 5:
            return False  # Owner toàn quyền — không tồn tại "bị chặn", khỏi tốn một lượt query
        if self.mock:  # mock: "similarity" của chunk mẫu đóng vai cosine
            return any(not self._duoc_xem(c["document_metadata"], user)
                       and c.get("similarity", 0.0) >= self.nguong_bi_chan
                       for c in self.search(query, filters, user=None))
        self._dam_bao_kho()
        muc_must = [models.FieldCondition(key=k, match=models.MatchValue(value=v))
                    for k, v in (filters or {}).items()]
        dense_q = next(iter(self.dense_model.embed([f"query: {query}"]))).tolist()
        kq = self.client.query_points(
            ALIAS, query=dense_q, using=DENSE,
            query_filter=models.Filter(must=muc_must) if muc_must else None,
            limit=SO_KET_QUA, with_payload=True)
        return any(not self._duoc_xem(dict(p.payload or {}), user)
                   and p.score >= self.nguong_bi_chan
                   for p in kq.points)

    def search(self, query: str, filters: dict | None = None,
               user: dict | None = None) -> list[dict]:
        """Tìm chunk liên quan, lọc metadata + LỌC QUYỀN server-side (lặng lẽ).

        user = {"bo_phan", "level"}: chỉ áp lọc quyền khi bo_phan không None —
        tức đăng nhập THẬT. Chế độ mở (user None / bo_phan None) thấy tất cả.
        Owner (level 5) KHÔNG bị áp filter quyền — toàn quyền xem mọi bộ phận
        (user chốt 30/07/2026, cùng luật với _duoc_xem); filter nghiệp vụ
        (hiệu lực...) vẫn áp bình thường.
        04/08/2026: cấp HIỆU LỰC (cần gạt trang Phân quyền) thay level thật cả ở
        filter server-side lẫn luật xem client-side.
        """
        user = _user_hieu_luc(user)
        ap_quyen = bool(user and user.get("bo_phan")) and user.get("level", 0) < 5

        if self.mock:
            hits = _MOCK_CHUNKS
            for key, value in (filters or {}).items():
                hits = [c for c in hits if c["document_metadata"].get(key) == value]
            if ap_quyen:  # mock lọc cùng luật để test được logic quyền
                hits = [c for c in hits if self._duoc_xem(c["document_metadata"], user)]
            return copy.deepcopy(hits)

        self._dam_bao_kho()
        muc_must = []
        if filters:
            muc_must += [models.FieldCondition(key=k, match=models.MatchValue(value=v))
                         for k, v in filters.items()]
        if ap_quyen:
            # Luật xem dịch sang Qdrant: should = HOẶC (công khai | đúng bộ phận + đủ level).
            # Range(lte) KHÔNG khớp point thiếu min_level → tài liệu chưa gán level
            # tự ẨN với user thật (backfill bằng scripts/gan_level.py).
            # MANAGER+ (31/07/2026): bỏ điều kiện bộ phận, chỉ còn min_level — PHẢI khớp
            # từng chữ với _duoc_xem kẻo search và các trang lệch luật nhau.
            nhanh_gioi_han = [models.FieldCondition(key="min_level",
                                                    range=models.Range(lte=user["level"]))]
            if user["level"] < 4:
                nhanh_gioi_han.insert(0, models.FieldCondition(
                    key="department", match=models.MatchValue(value=user["bo_phan"])))
            muc_must.append(models.Filter(should=[
                models.FieldCondition(key="access_level",
                                      match=models.MatchValue(value="Công khai nội bộ")),
                models.Filter(must=nhanh_gioi_han),
            ]))
        dieu_kien = models.Filter(must=muc_must) if muc_must else None

        # Rerank bật → lấy RỘNG hơn để cross-encoder có nguyên liệu chấm lại
        gioi_han = self.rerank_lay_rong if self.rerank_search else SO_KET_QUA

        # [PERF] tách riêng 2 chặng bên trong search: embedding (local) vs query Qdrant
        t0 = time.perf_counter()
        dense_q = next(iter(self.dense_model.embed([f"query: {query}"]))).tolist()
        if self.hybrid:
            sq = next(iter(self.sparse_model.embed([query])))
            t_embed = time.perf_counter() - t0
            t1 = time.perf_counter()
            ket_qua = self.client.query_points(
                ALIAS,
                prefetch=[
                    models.Prefetch(query=dense_q, using=DENSE,
                                    filter=dieu_kien,
                                    limit=max(gioi_han, SO_KET_QUA * 4)),
                    models.Prefetch(
                        query=models.SparseVector(indices=sq.indices.tolist(),
                                                  values=sq.values.tolist()),
                        using=SPARSE, filter=dieu_kien,
                        limit=max(gioi_han, SO_KET_QUA * 4)),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=gioi_han, with_payload=True,
            )
        else:
            t_embed = time.perf_counter() - t0
            t1 = time.perf_counter()
            ket_qua = self.client.query_points(
                ALIAS, query=dense_q, using=DENSE,
                query_filter=dieu_kien, limit=gioi_han, with_payload=True,
            )
        print(f"[PERF]   └ trong search: embedding {t_embed:.2f}s"
              f" | Qdrant query {time.perf_counter() - t1:.2f}s", flush=True)

        chunks = []
        for p in ket_qua.points:
            payload = dict(p.payload or {})
            content = payload.pop("content", "")
            chunks.append({
                "content": content,
                "document_id": payload.get("doc_code") or str(p.id),
                "document_keyword": payload.get("file_name")
                                    or payload.get("original_filename", ""),
                "similarity": p.score,  # điểm gốc hybrid/dense — giữ nguyên để đối chiếu
                "document_metadata": payload,
            })

        # RERANK: cross-encoder chấm lại từng chunk theo câu hỏi → top SO_KET_QUA tinh nhất
        if self.rerank_search and len(chunks) > 1:
            t2 = time.perf_counter()
            diem = list(self.reranker.rerank(query, [c["content"] for c in chunks]))
            for c, d in zip(chunks, diem):
                c["rerank_score"] = float(d)  # thêm khóa mới để debug/đo — không đè similarity
            chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
            chunks = chunks[:SO_KET_QUA]
            print(f"[PERF]   └ rerank: {time.perf_counter() - t2:.2f}s", flush=True)
        return chunks
