"""Sổ "câu kho chưa trả lời được" — Ý 1 Đợt 3.

Khi agent trả KHONG_CO_TAI_LIEU vì kho thiếu THẬT (bi_chan_quyen=False) và user
đăng nhập thật → ghi 1 dòng vào kho-tai-lieu/cau_kho_thieu.csv. Câu bị CHẶN QUYỀN
không ghi — tài liệu đã có, ghi vào đây sẽ báo nhầm "cần soạn tài liệu".

Context = tối đa 3 câu hỏi trước trong phiên (mạch hỏi, mới nhất đứng đầu, nối
" ← ") — giúp quản lý hiểu ngữ cảnh, và để dành cải thiện search sau này.
"""

import csv
import json
import os
import re
import uuid
from pathlib import Path

KHO_THIEU_HEADER = ["Thời gian", "Câu hỏi", "Bộ phận người hỏi", "Context (mạch hỏi)"]
CO_TAY_HEADER = ["Thời gian", "Câu hỏi", "Bộ phận người hỏi", "Context (mạch hỏi)",
                 "Nguồn lúc hỏi"]


def _duong_dan() -> Path:
    return Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / "cau_kho_thieu.csv"


def ghi_cau_kho_thieu(cau_hoi: str, bo_phan: str, lich_su: list[dict],
                      thoi_gian_iso: str) -> None:
    """Ghi thêm 1 câu kho-thiếu-thật (append, utf-8-sig — khuôn ghi_csv_chi_them của app)."""
    from src.main import ghi_csv_chi_them  # import tại chỗ — tránh vòng import với app

    # Context: tối đa 3 câu hỏi TRƯỚC trong phiên, câu gần nhất đứng đầu
    context = " ← ".join(l["hoi"] for l in reversed(lich_su[-3:]))
    duong_dan = _duong_dan()
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    ghi_csv_chi_them(duong_dan, KHO_THIEU_HEADER,
                     [thoi_gian_iso, cau_hoi, bo_phan, context])


def ghi_co_tay(cau_hoi: str, bo_phan: str, context: str, nguon: str,
               thoi_gian_iso: str) -> None:
    """Cờ tay "Câu này chưa có lời giải" — người dùng XÁC NHẬN kho thiếu, tín hiệu
    mạnh nhất trong 3 nguồn (không phụ thuộc máy đoán cụm từ hay ngưỡng cosine)."""
    from src.main import ghi_csv_chi_them  # import tại chỗ — tránh vòng import với app

    duong_dan = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / "co_tay_kho_thieu.csv"
    duong_dan.parent.mkdir(parents=True, exist_ok=True)
    ghi_csv_chi_them(duong_dan, CO_TAY_HEADER,
                     [thoi_gian_iso, cau_hoi, bo_phan, context, nguon])


def _doc_csv(duong_dan: Path) -> list[list[str]]:
    if not duong_dan.is_file():
        return []
    return list(csv.reader(duong_dan.open(encoding="utf-8-sig")))[1:]  # bỏ header


def doc_tat_ca_nguon() -> list[dict]:
    """Ghép 3 nguồn: sổ tự động cau_kho_thieu.csv + CỜ TAY co_tay_kho_thieu.csv
    (người dùng xác nhận — mạnh nhất) + câu 👎 trong phan_hoi.csv có "Bị chặn
    quyền" == Không (chủ động chê + không phải do chặn quyền).

    CHỐNG ĐẾM ĐÚP: log tự động là bộ đếm CHÍNH — dòng cờ tay / 👎 có câu (chuẩn
    hóa) trùng câu đã trong log bị loại khỏi phép đếm (một lượt vừa-log-vừa-báo
    chỉ đếm 1), nhưng câu có cờ tay vẫn được ĐÁNH DẤU co_tay=True để bảng ưu tiên.
    Cờ tay / 👎 câu riêng (log không bắt được) vẫn giữ nguyên dòng."""
    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    co_tay = [d for d in _doc_csv(kho / "co_tay_kho_thieu.csv") if len(d) >= 4]
    cau_co_tay = {_chuan_hoa(d[1]) for d in co_tay}

    muc = []
    for dong in _doc_csv(kho / "cau_kho_thieu.csv"):
        if len(dong) >= 4:
            muc.append({"thoi_gian": dong[0], "cau_hoi": dong[1],
                        "bo_phan": dong[2], "context": dong[3]})
    da_log = {_chuan_hoa(m["cau_hoi"]) for m in muc}
    for dong in co_tay:  # cờ tay câu CHƯA có trong log tự động → thêm dòng riêng
        if _chuan_hoa(dong[1]) not in da_log:
            muc.append({"thoi_gian": dong[0], "cau_hoi": dong[1],
                        "bo_phan": dong[2], "context": dong[3]})
    da_log |= cau_co_tay  # 👎 trùng cờ tay cũng là đếm đúp → loại
    for dong in _doc_csv(kho / "phan_hoi.csv"):
        # cột: [Thời gian, Câu hỏi, Câu trả lời, Đánh giá, Nguồn, Bị chặn quyền]
        # dòng cũ trước Rule 2 thiếu cột cuối → coi như "Không" (giữ vào thống kê)
        if (len(dong) >= 4 and dong[3] == "Tệ" and (len(dong) < 6 or dong[5] != "Có")
                and _chuan_hoa(dong[1]) not in da_log):
            muc.append({"thoi_gian": dong[0], "cau_hoi": dong[1],
                        "bo_phan": "", "context": ""})
    for m in muc:  # đánh dấu nhóm có người xác nhận — gop_va_dem gom cờ này lên nhóm
        m["co_tay"] = _chuan_hoa(m["cau_hoi"]) in cau_co_tay
    return muc


def _chuan_hoa(cau: str) -> str:
    """Gộp câu giống/gần giống: bỏ dấu câu, lowercase, ép khoảng trắng."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", cau.lower())).strip()


def gop_va_dem(muc: list[dict]) -> list[dict]:
    """Gom theo câu chuẩn hóa → đếm tần suất; câu hay hỏi nhất lên đầu."""
    nhom: dict[str, dict] = {}
    for m in muc:
        khoa = _chuan_hoa(m["cau_hoi"])
        if not khoa:
            continue
        g = nhom.setdefault(khoa, {"cau_hoi": m["cau_hoi"], "so_lan": 0, "co_tay": False,
                                   "bo_phan": set(), "contexts": [], "gan_nhat": ""})
        g["so_lan"] += 1
        g["co_tay"] = g["co_tay"] or bool(m.get("co_tay"))
        if m["bo_phan"]:
            g["bo_phan"].add(m["bo_phan"])
        if m["context"] and m["context"] not in g["contexts"] and len(g["contexts"]) < 3:
            g["contexts"].append(m["context"])  # vài context mẫu là đủ hiểu mạch
        g["gan_nhat"] = max(g["gan_nhat"], m["thoi_gian"])

    ket_qua = [{**g, "bo_phan": " · ".join(sorted(g["bo_phan"])) or "—"}
               for g in nhom.values()]
    ket_qua.sort(key=lambda g: g["gan_nhat"], reverse=True)   # phụ: mới nhất trước
    ket_qua.sort(key=lambda g: g["so_lan"], reverse=True)     # nhì: tần suất giảm dần
    ket_qua.sort(key=lambda g: g["co_tay"], reverse=True)     # nhất: người xác nhận lên đầu
    return ket_qua


def cau_da_gom(cac_nhom_chu_de: list[dict]) -> set[str]:
    """Tập câu (đã _chuan_hoa) thuộc nhóm CHƯA giải quyết — bảng chờ ẩn các câu này
    (đã gom vào nhóm thì không hiện lại như câu lẻ). Nhóm ĐÃ giải KHÔNG tính: câu
    của nó vốn đã có tài liệu nên tự rơi khỏi bảng chờ, không cần xử lý riêng."""
    return {_chuan_hoa(c["cau"]) for nh in cac_nhom_chu_de
            if not nh.get("da_giai_quyet") for c in nh.get("cac_cau", [])}


def loc_bang_cho(cac_nhom_chu_de: list[dict]) -> list[dict]:
    """Bảng chờ = gộp+đếm 3 nguồn, ĐÃ ẩn câu đã gom vào nhóm chưa giải quyết VÀ câu
    Manager+ đã xóa vì không phù hợp. So bằng _chuan_hoa cho khớp cách gộp câu hiện có."""
    an = cau_da_gom(cac_nhom_chu_de) | khoa_cau_da_xoa()
    return [n for n in gop_va_dem(doc_tat_ca_nguon())
            if _chuan_hoa(n["cau_hoi"]) not in an]


# ===== XÓA CÂU KHÔNG PHÙ HỢP (yêu cầu user 31/07/2026) =====
# Ba nguồn log là CSV chỉ-ghi-thêm (không sửa lịch sử) → "xóa" = ghi câu vào sổ loại
# trừ cau_kho_thieu_da_xoa.json, bảng chờ lọc ra. Muốn khôi phục: xóa dòng trong file.

def _duong_dan_da_xoa() -> Path:
    return Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / "cau_kho_thieu_da_xoa.json"


def doc_cau_da_xoa() -> list[dict]:
    p = _duong_dan_da_xoa()
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []  # file hỏng → coi như chưa xóa câu nào, không sập trang


def khoa_cau_da_xoa() -> set[str]:
    return {d.get("khoa", "") for d in doc_cau_da_xoa()}


def xoa_cau_cho(cau_hoi: str, ai: str, thoi_gian_iso: str) -> None:
    """Manager+ xóa 1 câu không phù hợp khỏi bảng chờ (ghi nguyên tử, có vết ai/lúc nào).
    Khóa = câu chuẩn hóa — trùng cách gộp câu, nên xóa 1 lần là ẩn mọi biến thể giống nhau;
    đã xóa rồi thì ghi lại vô hại (không nhân đôi)."""
    khoa = _chuan_hoa(cau_hoi)
    if not khoa:
        return
    cac = doc_cau_da_xoa()
    if khoa in {d.get("khoa") for d in cac}:
        return
    cac.append({"khoa": khoa, "cau_hoi": cau_hoi, "ai": ai, "thoi_gian": thoi_gian_iso})
    p = _duong_dan_da_xoa()
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(cac, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


# ================= YC7 — NHÓM CHỦ ĐỀ kho-thiếu (Manager+ gom câu, nối trang nhập) =====

def _duong_dan_nhom() -> Path:
    return Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / "nhom_kho_thieu.json"


def doc_nhom() -> list[dict]:
    p = _duong_dan_nhom()
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []  # file hỏng → coi như chưa có nhóm, không sập trang


def ghi_nhom(cac_nhom: list[dict]) -> None:
    """Ghi NGUYÊN TỬ (file tạm + os.replace) như users.txt/lich-su."""
    p = _duong_dan_nhom()
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(cac_nhom, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


def xoa_nhom(nhom_id: str) -> None:
    """Xóa 1 nhóm chủ đề theo id (ghi nguyên tử). Không thấy id → ghi lại y nguyên,
    vô hại. Xóa xong: câu của nhóm không còn 'đã gom' → tự hiện lại ở bảng chờ
    (bảng tính động từ log mỗi lần load, không lưu trạng thái riêng)."""
    ghi_nhom([nh for nh in doc_nhom() if nh.get("id") != nhom_id])


def tao_nhom(ten_chu_de: str, cac_cau: list[str], rag, thoi_gian_iso: str) -> dict:
    """Gom các câu kho-thiếu thành 1 nhóm chủ đề. Chụp BASELINE doc_codes của từng
    câu tại thời điểm tạo (search không lọc quyền — góc nhìn quản lý kho): sau này
    "đã giải quyết" = search ra doc_code MỚI ngoài baseline — cùng luật với
    phien_co_cau_da_giai, KHÔNG dùng "khác rỗng" (kho thật luôn trả top-k, bug A).
    CHỈ tầng noi_bo (07/08): kho-thiếu là tín hiệu THIẾU TÀI LIỆU CÔNG TY — thêm một
    video/bài viết nguồn ngoài không được coi là "đã giải quyết" khoảng trống đó."""
    def _baseline(cau: str) -> list[str]:
        chunks = rag.search(cau, {"effective_status": "Còn hiệu lực",
                                  "tang_nguon": "noi_bo"}, user=None)
        return sorted({c["document_metadata"].get("doc_code", "") for c in chunks})

    nhom = {"id": uuid.uuid4().hex[:8],
            "ten_chu_de": ten_chu_de.strip(),
            "cac_cau": [{"cau": c, "doc_codes_goc": _baseline(c)} for c in cac_cau],
            "da_giai_quyet": False,
            "thoi_gian": thoi_gian_iso}
    cac = doc_nhom()
    cac.append(nhom)
    ghi_nhom(cac)
    return nhom


def _cau_da_giai(cau: dict, rag) -> bool:
    """1 câu trong nhóm coi là ĐÃ GIẢI khi search giờ ra doc_code MỚI ngoài baseline.
    CHỈ tầng noi_bo (07/08) — cùng lý do ở tao_nhom."""
    chunks = rag.search(cau["cau"], {"effective_status": "Còn hiệu lực",
                                     "tang_nguon": "noi_bo"}, user=None)
    goc = set(cau.get("doc_codes_goc") or [])
    return any(c["document_metadata"].get("doc_code") not in goc for c in chunks)


def cap_nhat_nhom_da_giai(rag) -> list[dict]:
    """Tính lại trạng thái khi mở trang /kho-thieu (TỰ ĐỘNG, không đánh dấu tay —
    user chốt): nhóm đang chờ mà MỌI câu đã giải → chuyển da_giai_quyet=True và
    lưu lại (chuyển mục, không ẩn — xem lại được lịch sử bổ sung kho).
    Chỉ search LOCAL, không LLM; nhóm đã giải rồi không kiểm lại."""
    cac = doc_nhom()
    doi = False
    for nh in cac:
        if (not nh.get("da_giai_quyet") and nh.get("cac_cau")
                and all(_cau_da_giai(c, rag) for c in nh["cac_cau"])):
            nh["da_giai_quyet"] = True
            doi = True
    if doi:
        ghi_nhom(cac)
    return sorted(cac, key=lambda n: n.get("thoi_gian", ""), reverse=True)
