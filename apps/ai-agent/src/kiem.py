"""CỬA KIỂM LOGIC ai-agent (02/09/2026) — Owner chốt "16 logic = 16 sơ đồ".

Mỗi logic nghiệp vụ một mã kiểm; canary tầng nền GET /api/kiem/{ma} mỗi 30'
(+ nút hard-test) rồi so kỳ vọng khai ở nen/rules/canary/ai-agent.json.

Nguyên tắc: CHỈ-ĐỌC, 0 quota — không gọi LLM, chỉ chạy hàm thuần + đọc
catalog. Route trả SỐ ĐO THẬT; phán đúng/sai nằm ở kịch bản canary.
"""
from __future__ import annotations

# ── ma trận RBAC: user × chunk, luật _duoc_xem là NGUỒN SỰ THẬT DUY NHẤT ──
_USERS = [
    {"ten": "owner", "bo_phan": "Kinh doanh", "level": 5},
    {"ten": "manager-kd", "bo_phan": "Kinh doanh", "level": 4},
    {"ten": "leader-kd", "bo_phan": "Kinh doanh", "level": 3},
    {"ten": "nv-kd", "bo_phan": "Kinh doanh", "level": 2},
    {"ten": "nv-vh", "bo_phan": "Vận hành - Sản xuất", "level": 2},
]
_CHUNKS = [
    {"ten": "công khai", "md": {"access_level": "Công khai nội bộ",
                                "department": "Kinh doanh", "min_level": 1}},
    {"ten": "KD lv2", "md": {"access_level": "Nội bộ",
                             "department": "Kinh doanh", "min_level": 2}},
    {"ten": "KD lv4", "md": {"access_level": "Nội bộ",
                             "department": "Kinh doanh", "min_level": 4}},
    {"ten": "thiếu min_level", "md": {"access_level": "Nội bộ",
                                      "department": "Kinh doanh"}},
]


def _mong_doi(u: dict, md: dict) -> bool:
    """Kỳ vọng ĐỘC LẬP với code luật — viết lại luật đã chốt bằng lời:
    Owner (5) thấy tất; công khai nội bộ ai cũng thấy; min_level thiếu → ẩn;
    Manager+ (4) bỏ rào bộ phận nhưng vẫn kiểm min_level; dưới 4 phải đúng
    bộ phận VÀ đủ level."""
    if u["level"] >= 5:
        return True
    if md.get("access_level") == "Công khai nội bộ":
        return True
    ml = md.get("min_level")
    if not isinstance(ml, int):
        return False
    if u["level"] >= 4:
        return ml <= u["level"]
    return md.get("department") == u["bo_phan"] and ml <= u["level"]


def rbac_ma_tran() -> dict:
    """RBAC một nguồn sự thật: chạy _duoc_xem THẬT trên ma trận user × chunk,
    so với luật viết bằng lời — lệch một ô là rò quyền."""
    from src.vector_client import QdrantClientWrapper as VectorClient
    sai = []
    for u in _USERS:
        for c in _CHUNKS:
            that = VectorClient._duoc_xem(c["md"], u)
            if that != _mong_doi(u, c["md"]):
                sai.append(f'{u["ten"]} × {c["ten"]}: {that}')
    thieu = next(c for c in _CHUNKS if c["ten"] == "thiếu min_level")
    nv = next(u for u in _USERS if u["ten"] == "nv-kd")
    ow = next(u for u in _USERS if u["ten"] == "owner")
    return {"so_ca": len(_USERS) * len(_CHUNKS), "so_sai": len(sai),
            "chi_tiet_sai": sai[:5],
            "thieu_min_level_an": not VectorClient._duoc_xem(thieu["md"], nv),
            "owner_thay_tat": all(VectorClient._duoc_xem(c["md"], ow)
                                  for c in _CHUNKS)}


def van_kho_rong() -> dict:
    """Van chống bịa lớp 1: kho trả 0 chunk → câu cố định, KHÔNG gọi model.
    Đếm lời gọi bằng client giả — 0 quota, 0 tiền."""
    from src import qa_pipeline
    dem = {"n": 0}

    class _RagRong:
        def search(self, *a, **k):
            return []

        def search_co_bi_chan(self, *a, **k):
            return False

    class _ModelDem:
        def generate(self, *a, **k):
            dem["n"] += 1
            return "KHÔNG ĐƯỢC GỌI"

    qa = qa_pipeline.QAPipeline(rag=_RagRong(), writer=_ModelDem(), critics=[])
    kq = qa.hoi("câu hỏi bất kỳ không có trong kho")
    return {"tra_loi_co_dinh": kq["answer"] == qa_pipeline.KHONG_CO_TAI_LIEU,
            "so_nguon": len(kq.get("sources") or []),
            "so_lan_goi_model": dem["n"]}


def viet_lai_cau() -> dict:
    """Viết lại câu hỏi đa lượt: câu NGẮN phụ thuộc ngữ cảnh mới đáng tốn lượt
    model; câu dài tự đứng thì không — sai chiều nào cũng tốn tiền hoặc lạc đề."""
    from src.qa_pipeline import QAPipeline
    ca = [("Thường kéo dài bao lâu?", True),
          ("Cái đó làm sao?", True),
          ("Quy trình đăng video YouTube của công ty gồm những bước nào",
           False)]
    sai = [c for c, mong in ca
           if QAPipeline._can_viet_lai_cau_hoi(c) != mong]
    return {"so_ca": len(ca), "so_sai": len(sai), "ca_sai": sai}


def mac_dinh_noi_bo() -> dict:
    """Hỏi–đáp THƯỜNG phải lọc tang_nguon=noi_bo + effective_status — lỗ hổng
    vá 07/08: thiếu là tài liệu tầng ngoài lẫn vào mọi câu trả lời không nhãn."""
    from src import qa_pipeline
    bat = {}

    class _RagBat:
        def search(self, cau, filters=None, **k):
            bat["filters"] = filters or {}
            return []

        def search_co_bi_chan(self, *a, **k):
            return False

    qa = qa_pipeline.QAPipeline(rag=_RagBat(), writer=None, critics=[])
    qa.hoi("câu bất kỳ")
    f = bat.get("filters", {})
    return {"filters": f,
            "co_loc_noi_bo": f.get("tang_nguon") == "noi_bo",
            "co_loc_hieu_luc": f.get("effective_status") == "Còn hiệu lực"}


def qa_ke_thua_quyen() -> dict:
    """Tài liệu Q&A (-QA) kế thừa TOÀN BỘ quyền gốc — đọc catalog thật, so 4
    cột quyền từng cặp gốc↔-QA. Lệch một cột là rò quyền."""
    from src.main import doc_catalog
    COT = ["Bộ phận", "Mức truy cập", "Level tối thiểu", "Hiệu lực"]
    dong = doc_catalog()
    theo_ma = {d.get("Mã tài liệu"): d for d in dong if d.get("Mã tài liệu")}
    lech, so_qa = [], 0
    for ma, d in theo_ma.items():
        if not ma.endswith("-QA"):
            continue
        so_qa += 1
        goc = theo_ma.get(ma[:-3])
        if goc is None:
            lech.append(f"{ma}: không thấy tài liệu gốc")
            continue
        for c in COT:
            if (d.get(c) or "") != (goc.get(c) or ""):
                lech.append(f"{ma}·{c}: {d.get(c)!r} ≠ {goc.get(c)!r}")
    return {"so_qa": so_qa, "so_lech": len(lech), "chi_tiet": lech[:5]}


CAC_MA = {"rbac-ma-tran": rbac_ma_tran, "van-kho-rong": van_kho_rong,
          "viet-lai-cau": viet_lai_cau, "mac-dinh-noi-bo": mac_dinh_noi_bo,
          "qa-ke-thua-quyen": qa_ke_thua_quyen}
