"""Module TỔNG HỢP CÓ NEO — nâng cấp extract (supervisor.md §2c): từ "kiểm chữ" lên "kiểm ý".

Trích nguyên văn (trich_doan.py) giải quyết XUẤT XỨ nhưng sản phẩm là câu nói rời — không
khái quát được vấn đề chung, và chunk lời-thoại-vụn khó khớp câu hỏi khái quát của team.
Module này cho LLM VIẾT BÀI PHÂN TÍCH thật (khái quát + đào sâu) nhưng giữ van chống bịa
bằng BA VAN thay một van verbatim:

  (1) NEO BẮT BUỘC : mỗi luận điểm phải trỏ về >=1 đoạn bằng chứng nguyên văn (mã E1..En).
                     Không neo / neo sai mã → parser LOẠI thẳng, chưa cần tới LLM thứ hai.
  (2) KIỂM NEO     : LLM độc lập kiểm từng luận điểm — bằng chứng có ĐỠ được không:
                     do_duoc / suy_rong (hợp lý, giữ kèm ghi chú) / khong_do (mặc định bỏ
                     tick ở màn duyệt). Critic không phán → chua_kiem (nói thật, không đoán).
  (3) NGƯỜI DUYỆT  : từng luận điểm hiện CẠNH bằng chứng + phán quyết critic, người sửa/bỏ
                     rồi mới ghi kho — pattern Duyệt Q&A, người vẫn là van cuối.

Bản phân tích vào kho là TÀI LIỆU CON hậu tố -PT (đúng cơ chế -QA): kế thừa TOÀN BỘ quyền +
tầng nguồn của tài liệu trích gốc, doc_code bất biến, ghi nguyên tử; chạy lại là GHI ĐÈ toàn
file (snapshot mới nhất, không nối). Nội dung file CHỈ chứa phân tích + dòng dẫn chứng trỏ về
mã gốc — KHÔNG chép lại bằng chứng (tránh đúp chunk khi search).

Chỉ hàm thuần + test (writer/verifier tiêm vào để mock). Import app helpers TẠI CHỖ như
qa_bo_sung.py để tránh vòng import.
"""

import logging
import os
import re
import unicodedata
from pathlib import Path

HAU_TO_PT = "-PT"

# Parser KHOAN DUNG số dấu <> (bài học GLM viết '<<<LYDO>>' thiếu 1 dấu — trich_doan.py 24/07)
_MAU_CHU_DE = re.compile(r"<+\s*CHUDE\s*>+(.*?)<+\s*HET\s*>+", re.DOTALL | re.IGNORECASE)
_MAU_BOI_CANH = re.compile(r"<+\s*BOICANH\s*>+(.*?)<+\s*HET\s*>+", re.DOTALL | re.IGNORECASE)
_MAU_AP_DUNG = re.compile(r"<+\s*APDUNG\s*>+(.*?)<+\s*HET\s*>+", re.DOTALL | re.IGNORECASE)
_MAU_TU_KHOA = re.compile(r"<+\s*TUKHOA\s*>+(.*?)<+\s*HET\s*>+", re.DOTALL | re.IGNORECASE)
_MAU_THUATNGU = re.compile(r"<+\s*THUATNGU\s*>+(.*?)<+\s*HET\s*>+", re.DOTALL | re.IGNORECASE)
_MAU_BAI_HOC = re.compile(
    r"<+\s*BAIHOC\s*>+(.*?)<+\s*NEO\s*>+(.*?)<+\s*HET\s*>+",
    re.DOTALL | re.IGNORECASE)
# Tương thích ngược: model cũ/khác có thể vẫn viết khối LUANDIEM — parse như bài học không tiêu đề
_MAU_LUAN_DIEM = re.compile(
    r"<+\s*LUANDIEM\s*>+(.*?)<+\s*NEO\s*>+(.*?)<+\s*HET\s*>+",
    re.DOTALL | re.IGNORECASE)
DAI_TOI_THIEU_LD = 15   # bài học quá ngắn không phải phân tích → bỏ

# 06/08 user chê bản đầu "vài câu cô đọng không đầu cuối, không 5W1H, không context" →
# đầu ra đổi thành TÀI LIỆU LESSON LEARNED tự đứng được; tầng tổng hợp được đọc CẢ văn bản
# gốc làm ngữ cảnh (van chống bịa giữ nguyên: bài học vẫn phải neo vào bằng chứng nguyên văn).
SYSTEM_TONG_HOP = (
    "Bạn là người viết TÀI LIỆU BÀI HỌC KINH NGHIỆM (lesson learned) cho kho tri thức nội bộ "
    "của công ty — dạng BÀI GIẢNG có hệ thống, đủ sâu để người đọc CHƯA XEM NGUỒN vẫn học "
    "được trọn vẹn (không phải bản tóm tắt vài dòng). Đầu vào gồm: (1) VĂN BẢN GỐC của nguồn "
    "(nếu có) — dùng để hiểu ngữ cảnh và viết trôi chảy; (2) DANH SÁCH BẰNG CHỨNG — các đoạn "
    "nguyên văn đáng giá đã trích, đánh mã [E1], [E2]…\n"
    "NGƯỜI ĐỌC CHƯA XEM NGUỒN — tài liệu phải TỰ ĐỨNG ĐƯỢC: có đầu có cuối, đủ bối cảnh, đọc "
    "xong trả lời được Ai / Cái gì / Khi nào / Ở đâu / Tại sao / Làm thế nào.\n"
    "CẤU TRÚC BẮT BUỘC:\n"
    "1) <<<CHUDE>>> MỘT DÒNG chủ đề của tài liệu.\n"
    "2) <<<BOICANH>>> một đoạn 3-6 câu: nguồn là ai/kênh gì, nói về vấn đề gì, trong tình huống "
    "nào, dành cho ai, vì sao đáng nghe. CHỈ dùng thông tin có trong văn bản/bằng chứng.\n"
    "3) TÁM ĐẾN MƯỜI LĂM khối <<<BAIHOC>>> (viết ĐỦ theo lượng bằng chứng có — bằng chứng "
    "nhiều thì viết nhiều khối, KHÔNG dồn nhiều ý khác nhau vào một khối cho đủ số, cũng KHÔNG "
    "cố kéo dài nếu bằng chứng mỏng): dòng ĐẦU TIÊN là TÊN bài học (ngắn như tiêu đề mục, "
    "KHÔNG tự đánh số — số thứ tự do hệ thống thêm sau); các câu sau viết LIỀN MẠCH thành đoạn "
    "văn ĐỦ SÂU: vấn đề gì → nguyên lý/vì sao → cách làm cụ thể → ví dụ/số liệu cụ thể (NẾU "
    "bằng chứng có nêu số) → khi nào/điều kiện áp dụng. Mỗi khối kèm <<<NEO>>> liệt kê mã bằng "
    "chứng đỡ nó (vd: E1, E3). Bài học KHÔNG có bằng chứng đỡ thì KHÔNG ĐƯỢC VIẾT.\n"
    "4) <<<APDUNG>>> 3-8 gạch đầu dòng hành động cụ thể người đọc làm được ngay, RÚT TỪ các "
    "bài học ở trên — không thêm ý mới.\n"
    "5) <<<TUKHOA>>> MỘT DÒNG 3-6 từ khóa NGẮN (mỗi từ 1-4 chữ, kiểu nhãn tra cứu: "
    "'thumbnail, CTR, kênh nhỏ') cách nhau dấu phẩy — KHÔNG viết thành câu.\n"
    "6) <<<THUATNGU>>> TÙY CHỌN — chỉ viết khi nguồn có thuật ngữ/khái niệm riêng đáng giải "
    "nghĩa: mỗi dòng MỘT thuật ngữ, định dạng 'Thuật ngữ | Nghĩa ngắn 1 câu'. Không có thuật "
    "ngữ đặc biệt nào thì để trống khối này (viết <<<THUATNGU>>>\\n<<<HET>>>, không có dòng nào "
    "ở giữa) — KHÔNG bịa thuật ngữ cho có.\n"
    "CẤM: bịa số liệu, thêm dữ kiện ngoài nguồn, viết gạch ý rời rạc không giải thích, chép "
    "nguyên văn bằng chứng thay vì viết lại có phân tích, dồn nhiều ý khác nhau vào một khối "
    "BÀI HỌC cho gọn.\n"
    "ĐỊNH DẠNG (đúng các khối, không viết gì ngoài):\n"
    "<<<CHUDE>>>\n<một dòng>\n<<<HET>>>\n"
    "<<<BOICANH>>>\n<đoạn bối cảnh>\n<<<HET>>>\n"
    "<<<BAIHOC>>>\n<tên bài học>\n<nội dung liền mạch>\n<<<NEO>>>\nE1, E3\n<<<HET>>>\n"
    "(lặp lại khối BAIHOC cho từng bài học — 8 đến 15 khối)\n"
    "<<<APDUNG>>>\n- <hành động>\n<<<HET>>>\n"
    "<<<TUKHOA>>>\n<từ khóa, từ khóa>\n<<<HET>>>\n"
    "<<<THUATNGU>>>\n<Thuật ngữ 1 | Nghĩa>\n<Thuật ngữ 2 | Nghĩa>\n<<<HET>>>"
)

SYSTEM_KIEM_NEO = (
    "Bạn là THẨM PHÁN độc lập, đa nghi. Với TỪNG luận điểm được đưa, kiểm tra: các đoạn bằng "
    "chứng nguyên văn đi kèm có THẬT SỰ ĐỠ ĐƯỢC luận điểm đó không?\n"
    "Ba mức phán quyết:\n"
    "- DO_DUOC : bằng chứng đỡ trực tiếp luận điểm.\n"
    "- SUY_RONG: luận điểm suy rộng từ bằng chứng nhưng hợp lý, không bóp méo ý nguồn.\n"
    "- KHONG_DO: bằng chứng KHÔNG đỡ được — luận điểm thêm dữ kiện lạ, đảo ý, hoặc lạc đề.\n"
    "Nghiêm khắc: nghi ngờ thì hạ mức, không nương tay.\n"
    "TRẢ LỜI mỗi luận điểm ĐÚNG MỘT DÒNG, định dạng:\n"
    "L1 | DO_DUOC | <một câu vì sao>\n"
    "L2 | KHONG_DO | <một câu vì sao>\n"
    "Không viết gì khác ngoài các dòng đó."
)


def ma_pt(doc_code_goc: str) -> str:
    """Mã bản phân tích = mã gốc + '-PT' (YT-abc → YT-abc-PT)."""
    return f"{doc_code_goc}{HAU_TO_PT}"


def la_ma_pt(doc_code: str) -> bool:
    return doc_code.endswith(HAU_TO_PT)


def ma_goc_tu_pt(ma: str) -> str:
    return ma[: -len(HAU_TO_PT)] if la_ma_pt(ma) else ma


def _khoi_bang_chung(cac_doan: list[dict]) -> str:
    """Dựng danh sách bằng chứng [E1]..[En] cho đề bài LLM (kèm bản dịch nếu có — giúp model
    viết tiếng Việt sát nghĩa; dịch là nhãn phụ, không phải nguồn sự thật)."""
    khoi = []
    for i, d in enumerate(cac_doan, 1):
        phan = f"[E{i}] {d['trich']}"
        if d.get("dich"):
            phan += f"\n(Dịch tham khảo: {d['dich']})"
        khoi.append(phan)
    return "\n\n".join(khoi)


def _mot_khoi(mau, tho: str) -> str:
    m = mau.search(tho)
    return m.group(1).strip() if m else ""


def tong_hop_co_neo(cac_doan: list[dict], writer, nguon: str = "",
                    van_ban_goc: str = "") -> dict:
    """VAN 1 — LLM viết TÀI LIỆU LESSON LEARNED, parser chỉ giữ bài học CÓ NEO HỢP LỆ.

    van_ban_goc (transcript/bài gốc) là NGỮ CẢNH để viết có đầu có cuối + bối cảnh 5W1H —
    KHÔNG thay bằng chứng: bài học vẫn phải neo vào E1..En, không neo/neo sai mã → LOẠI
    (đếm vào so_loai_khong_neo cho màn duyệt minh bạch). boi_canh là phần MÔ TẢ NGUỒN,
    ap_dung là phần RÚT từ các bài học — hai phần này không neo từng câu, người duyệt là van.
    Trả {chu_de, boi_canh, ap_dung, tu_khoa, thuat_ngu, luan_diem:[{tieu_de, noi_dung, neo}],
    so_loai_khong_neo}. cac_doan rỗng → kết quả rỗng, KHÔNG gọi model."""
    if not cac_doan:
        return {"chu_de": "", "boi_canh": "", "ap_dung": "", "tu_khoa": "", "thuat_ngu": "",
                "luan_diem": [], "so_loai_khong_neo": 0}
    de_bai = (f"Nguồn: {nguon}\n\n" if nguon else "")
    if van_ban_goc.strip():
        de_bai += f"VĂN BẢN GỐC (ngữ cảnh):\n{van_ban_goc.strip()}\n\n"
    de_bai += f"DANH SÁCH BẰNG CHỨNG:\n\n{_khoi_bang_chung(cac_doan)}"
    tho = writer.generate(SYSTEM_TONG_HOP, de_bai)

    chu_de = " ".join(_mot_khoi(_MAU_CHU_DE, tho).split())
    boi_canh = _mot_khoi(_MAU_BOI_CANH, tho)
    ap_dung = _mot_khoi(_MAU_AP_DUNG, tho)
    # Từ khóa ĐỀ XUẤT (06/08 — máy đề xuất, người sửa ở màn duyệt): nhãn ngắn để tra cứu,
    # KHÔNG phải câu; lọc mẩu quá dài phòng model viết thành câu
    tu_khoa = ", ".join(t.strip() for t in _mot_khoi(_MAU_TU_KHOA, tho).split(",")
                        if t.strip() and len(t.strip()) <= 40)
    # Bảng thuật ngữ ĐỀ XUẤT (08/08 — TÙY CHỌN, máy có thể để trống): người duyệt xem/sửa ở
    # màn duyệt, render thành bảng ở _noi_dung_ban_pt — giữ nguyên dạng text thô "Từ | Nghĩa"
    thuat_ngu = _mot_khoi(_MAU_THUATNGU, tho)

    luan_diem, loai = [], 0
    # Khối BAIHOC (dòng đầu = tiêu đề) + khối LUANDIEM cũ (không tiêu đề) — parse cả hai
    tho_sach = _MAU_BOI_CANH.sub("", _MAU_AP_DUNG.sub("", _MAU_THUATNGU.sub("", tho)))
    khoi = [(True, thân, neo) for thân, neo in _MAU_BAI_HOC.findall(tho_sach)] + \
           [(False, thân, neo) for thân, neo in _MAU_LUAN_DIEM.findall(tho_sach)]
    for co_tieu_de, than, neo_tho in khoi:
        than = than.strip()
        neo = sorted({int(k) for k in re.findall(r"[Ee]\s*(\d+)", neo_tho)
                      if 1 <= int(k) <= len(cac_doan)})
        tieu_de, noi_dung = "", than
        if co_tieu_de and "\n" in than:
            dau, phan_con = than.split("\n", 1)
            tieu_de, noi_dung = dau.strip(), phan_con.strip()
        if len(noi_dung) < DAI_TOI_THIEU_LD:
            continue
        if not neo:
            loai += 1
            continue
        luan_diem.append({"tieu_de": tieu_de, "noi_dung": noi_dung, "neo": neo})
    return {"chu_de": chu_de, "boi_canh": boi_canh, "ap_dung": ap_dung, "tu_khoa": tu_khoa,
            "thuat_ngu": thuat_ngu, "luan_diem": luan_diem, "so_loai_khong_neo": loai}


def _chuan_phan_quyet(s: str) -> str:
    """Chuẩn hóa chuỗi phán quyết để so khớp khoan dung: bỏ dấu tiếng Việt (đ→d riêng — U+0111
    không phân rã qua NFD, bẫy đã gặp 05/08), upper, mọi ký tự không chữ-số → '_'."""
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()


def _tim_phan_quyet(chuoi: str) -> str | None:
    """Tìm phán quyết trong 1 mẩu chữ (đã chuẩn hóa): KHONG_DO xét TRƯỚC vì chứa 'DO'."""
    ch = _chuan_phan_quyet(chuoi)
    for token, ket_qua in (("KHONG_DO", "khong_do"), ("SUY_RONG", "suy_rong"),
                           ("DO_DUOC", "do_duoc")):
        if token in ch:
            return ket_qua
    return None


def kiem_neo(luan_diem: list[dict], cac_doan: list[dict], verifier) -> list[dict]:
    """VAN 2 — critic độc lập phán từng luận điểm dựa trên ĐÚNG các bằng chứng nó neo.

    Trả list CÙNG ĐỘ DÀI luan_diem: [{ket_qua: do_duoc|suy_rong|khong_do|chua_kiem, ghi_chu}].
    Critic bỏ sót luận điểm nào → chua_kiem (nói thật với người duyệt, KHÔNG tự đoán đạt)."""
    if not luan_diem:
        return []
    phan = []
    for i, ld in enumerate(luan_diem, 1):
        bc = "\n".join(f"[E{k}] {cac_doan[k - 1]['trich']}" for k in ld["neo"])
        ten = (ld.get("tieu_de") or "").strip()
        noi_dung = (f"{ten}: {ld['noi_dung']}" if ten else ld["noi_dung"])
        phan.append(f"Luận điểm L{i}:\n{noi_dung}\nBằng chứng được neo:\n{bc}")
    tho = verifier.generate(SYSTEM_KIEM_NEO, "\n\n---\n\n".join(phan))

    ket = [{"ket_qua": "chua_kiem",
            "ghi_chu": "Critic không trả phán quyết — tự kiểm bằng dẫn chứng bên cạnh."}
           for _ in luan_diem]
    for dong in tho.splitlines():
        m = re.match(r"\s*L\s*(\d+)\s*[|:\-–—]\s*(.*)", dong)
        if not m or not 1 <= int(m.group(1)) <= len(luan_diem):
            continue
        pq = _tim_phan_quyet(m.group(2))
        if pq is None:
            continue
        # ghi chú = phần sau dấu | thứ hai nếu có; không có thì cả phần còn lại của dòng
        manh = [p.strip() for p in m.group(2).split("|")]
        ghi_chu = manh[-1] if len(manh) >= 2 else m.group(2).strip()
        ket[int(m.group(1)) - 1] = {"ket_qua": pq, "ghi_chu": ghi_chu}
    return ket


def phan_tich_co_neo(cac_doan: list[dict], writer, verifier, nguon: str = "",
                     van_ban_goc: str = "") -> dict:
    """Chạy trọn 2 van máy: tổng hợp lesson-learned có neo → kiểm neo. Trả nháp cho màn duyệt
    (van 3 = người): {chu_de, boi_canh, ap_dung,
    luan_diem:[{tieu_de, noi_dung, neo, ket_qua, ghi_chu}], so_loai_khong_neo}."""
    nhap = tong_hop_co_neo(cac_doan, writer, nguon, van_ban_goc=van_ban_goc)
    for ld, pq in zip(nhap["luan_diem"], kiem_neo(nhap["luan_diem"], cac_doan, verifier)):
        ld.update(pq)
    return nhap


# ─────────────── đọc bằng chứng từ tài liệu trích đã có trong kho ───────────────

_MAU_DICH = re.compile(r"\(🇻🇳 Dịch tham khảo:\s*(.*?)\)\s*$", re.DOTALL)


def _dong_catalog(doc_code: str, kho: Path):
    """Tìm dòng catalog + đường dẫn file của 1 tài liệu. Không thấy → ValueError."""
    from src.main import DEPT_FOLDER, doc_catalog

    row = next((r for r in doc_catalog(kho) if r["Mã tài liệu"] == doc_code), None)
    if row is None:
        raise ValueError(f"Không thấy tài liệu {doc_code} trong catalog")
    ngan = (row.get("Ngăn") or "").strip() or DEPT_FOLDER.get(row.get("Bộ phận"), "00_Chung")
    ten = (row.get("Tên file mới") or "").strip()
    return row, ngan, (kho / ngan / ten if ten else None)


def _duong_dan_kem(doc_code: str, duoi: str, kho: Path) -> Path | None:
    """Đường dẫn file PHỤ LỤC đính kèm (<mã>_bang-chung.md / <mã>_transcript.txt) — cùng
    ngăn với tài liệu chính, KHÔNG vào catalog/Qdrant. Không thấy tài liệu → None."""
    try:
        _, ngan, _ = _dong_catalog(doc_code, kho)
    except ValueError:
        return None
    return kho / ngan / f"{doc_code}_{duoi}"


def doc_transcript_goc(doc_code: str, kho: Path | None = None) -> str:
    """Đọc VĂN BẢN GỐC (transcript) lưu kèm tài liệu trích — file bạn đồng hành
    <mã>_transcript.txt cùng ngăn (nap_doan_video ghi, KHÔNG vào catalog/Qdrant, chỉ làm
    ngữ cảnh khi phân tích lại). Không có (tài liệu nạp trước 06/08) → chuỗi rỗng."""
    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    try:
        _, ngan, _ = _dong_catalog(doc_code, kho)
    except ValueError:
        return ""
    f = kho / ngan / f"{doc_code}_transcript.txt"
    try:
        return f.read_text(encoding="utf-8") if f.is_file() else ""
    except OSError:
        return ""


def doc_doan_tu_file_goc(doc_code: str, kho: Path | None = None) -> list[dict]:
    """Đọc lại các đoạn bằng chứng [{trich, dich}] của một tài liệu. ƯU TIÊN phụ lục
    <mã>_bang-chung.md (kiến trúc 1-tài-liệu 06/08: file chính là BÀI HỌC, bằng chứng nằm
    phụ lục); không có phụ lục → đọc chính file (tài liệu TRÍCH đời cũ, cùng định dạng:
    đoạn nguyên văn + dòng '🇻🇳 Dịch tham khảo' tùy chọn, dòng '#' đầu là header — bỏ).
    Không file nào → ValueError."""
    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    _, _, file_goc = _dong_catalog(doc_code, kho)
    bc = _duong_dan_kem(doc_code, "bang-chung.md", kho)
    if bc is not None and bc.is_file():
        file_goc = bc
    if file_goc is None or not file_goc.is_file():
        raise ValueError(f"File của tài liệu {doc_code} không còn trên đĩa")
    ket = []
    for khoi in file_goc.read_text(encoding="utf-8").split("\n\n"):
        khoi = khoi.strip()
        if not khoi or khoi.startswith("#"):
            continue
        m = _MAU_DICH.search(khoi)
        trich = khoi[: m.start()].strip() if m else khoi
        if trich:
            ket.append({"trich": trich, "dich": m.group(1).strip() if m else ""})
    return ket


# ─────────────── nạp bản phân tích -PT vào kho (kế thừa quyền gốc như -QA) ───────────────

def _noi_dung_ban_pt(tieu_de_goc: str, doc_code_goc: str, nguon_ten: str,
                     chu_de: str, luan_diem: list[dict],
                     boi_canh: str = "", ap_dung: str = "", thuat_ngu: str = "",
                     noi_dan_chung: str = "") -> str:
    """Nội dung file bài học — TÀI LIỆU LESSON LEARNED tự đứng được, dạng BÀI GIẢNG có hệ
    thống (08/08, theo mẫu user gửi): Mục lục (CODE tự dựng từ tiêu đề bài học — KHÔNG nhờ
    LLM viết, tránh mục lục lệch nội dung thật) → Bối cảnh → Phần 1..N mỗi bài học (kèm dẫn
    chứng) → Áp dụng → Bảng thuật ngữ (nếu có). noi_dan_chung = nơi bằng chứng nằm (mặc định
    mã tài liệu trích — kiến trúc 2-tài-liệu cũ; kiến trúc 1-tài-liệu truyền 'phụ lục kèm
    tài liệu'). KHÔNG chép lại bằng chứng vào đây — tránh đúp chunk khi search."""
    noi_bc = noi_dan_chung or doc_code_goc
    ten_bai_hoc = [(ld.get("tieu_de") or "").strip() or f"Bài học {i}"
                   for i, ld in enumerate(luan_diem, 1)]

    muc_luc = (["- Bối cảnh"] if boi_canh.strip() else [])
    muc_luc += [f"- Phần {i} — {ten}" for i, ten in enumerate(ten_bai_hoc, 1)]
    if ap_dung.strip():
        muc_luc.append("- Áp dụng ngay")
    if thuat_ngu.strip():
        muc_luc.append("- Bảng thuật ngữ")

    phan = [f"# Bài học kinh nghiệm: {chu_de or tieu_de_goc}\n"
            f"# Nguồn: {nguon_ten} — tổng hợp có kiểm neo; mã E# trỏ về đoạn nguyên văn "
            f"trong {noi_bc}."]
    if len(muc_luc) > 1:   # chỉ 1 mục (vd chỉ có bài học, không bối cảnh/áp dụng) thì bỏ mục lục
        phan.append("## Mục lục\n\n" + "\n".join(muc_luc))
    if boi_canh.strip():
        phan.append(f"## Bối cảnh\n\n{boi_canh.strip()}")
    for i, (ld, ten) in enumerate(zip(luan_diem, ten_bai_hoc), 1):
        phan.append(f"## Phần {i} — {ten}\n\n{ld['noi_dung']}\n"
                    f"(Dẫn chứng: {', '.join('E%d' % k for k in ld['neo'])} — {noi_bc})")
    if ap_dung.strip():
        phan.append(f"## Áp dụng ngay\n\n{ap_dung.strip()}")
    if thuat_ngu.strip():
        dong_bang = ["| Thuật ngữ | Nghĩa |", "|---|---|"]
        for dong in thuat_ngu.strip().splitlines():
            thuat, _, nghia = dong.partition("|")
            thuat, nghia = thuat.strip(), nghia.strip()
            if thuat:
                dong_bang.append(f"| {thuat} | {nghia} |")
        if len(dong_bang) > 2:
            phan.append("## Bảng thuật ngữ\n\n" + "\n".join(dong_bang))
    return "\n\n".join(phan)


def nap_ban_phan_tich(doc_code_goc: str, chu_de: str, luan_diem: list[dict], client,
                      import_date: str, kho: Path | None = None,
                      boi_canh: str = "", ap_dung: str = "", tu_khoa: str = "",
                      thuat_ngu: str = "") -> dict:
    """VAN 3 đã qua (người duyệt xong) → ghi kho. Kế thừa TOÀN BỘ quyền + tầng nguồn của tài
    liệu trích gốc (đọc lại catalog MỖI LẦN — gốc đổi quyền thì -PT theo, như -QA). Lần đầu
    tạo file + upload + 1 dòng catalog; lần sau GHI ĐÈ TOÀN FILE + cap_nhat_noi_dung (xóa
    chunk cũ nạp lại — chống mồ côi), KHÔNG thêm dòng catalog. Luận điểm rỗng → ValueError."""
    from src.main import doc_catalog, duong_dan_khong_trung, ghi_catalog

    luan_diem = [ld for ld in luan_diem
                 if (ld.get("noi_dung") or "").strip() and ld.get("neo")]
    if not luan_diem:
        raise ValueError("Không có luận điểm nào để ghi — bản phân tích rỗng")

    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    row, ngan, _ = _dong_catalog(doc_code_goc, kho)
    ma = ma_pt(doc_code_goc)
    tieu_de_goc = row.get("Tiêu đề") or doc_code_goc
    nguon_ten = row.get("Tên nguồn") or "Official"
    noi_dung = _noi_dung_ban_pt(tieu_de_goc, doc_code_goc, nguon_ten, chu_de, luan_diem,
                                boi_canh=boi_canh, ap_dung=ap_dung, thuat_ngu=thuat_ngu)

    cat = doc_catalog(kho)
    pt_row = next((r for r in cat if r["Mã tài liệu"] == ma), None)
    lan_dau = pt_row is None
    if lan_dau:
        file_pt = duong_dan_khong_trung(kho / ngan, f"{ma}_Phan-tich.md")
    else:
        ten = (pt_row.get("Tên file mới") or f"{ma}_Phan-tich.md").strip()
        file_pt = kho / ngan / ten
    file_pt.parent.mkdir(parents=True, exist_ok=True)
    tam = file_pt.with_name(file_pt.name + ".tmp")
    tam.write_text(noi_dung, encoding="utf-8")
    os.replace(tam, file_pt)

    ml = str(row.get("Level tối thiểu") or "").strip()
    metadata = {
        # 06/08 user chốt vai từng trường + "bỏ hết chữ Bài học kinh nghiệm ở tiêu đề":
        # title là CHỦ ĐỀ thuần, KHÔNG theo tiêu đề gốc (cùng tên gốc nhìn như tài liệu
        # trùng — user báo) và KHÔNG tiền tố lặp (chip badge trong bảng đã nói vai).
        # keywords là TỪ KHÓA THẬT, không đổ câu dài.
        "title": chu_de.strip() or tieu_de_goc,
        "keywords": tu_khoa.strip() or chu_de,
        "owner": row.get("Phụ trách") or "",
        "version": "v1",
        "department": row.get("Bộ phận") or "",
        "doc_type": "Khác",
        "effective_status": row.get("Hiệu lực") or "",
        "access_level": row.get("Mức truy cập") or "",
        "min_level": int(ml) if ml.isdigit() else None,
        "doc_code": ma,
        "import_date": import_date[:10],
        "original_filename": file_pt.name,
        "tang_nguon": row.get("Tầng nguồn") or "noi_bo",
        "nguon_ten": nguon_ten,
    }
    if lan_dau:
        doc_id = client.upload_document(str(file_pt), metadata)
        ghi_catalog(kho, [
            ma, metadata["import_date"], metadata["title"], metadata["department"],
            metadata["doc_type"], metadata["effective_status"], "v1",
            metadata["access_level"],
            metadata["min_level"] if metadata["min_level"] is not None else "",
            metadata["keywords"], metadata["owner"], file_pt.name, ngan,
            "false", doc_id, "", metadata["tang_nguon"], metadata["nguon_ten"]])
    else:
        client.cap_nhat_noi_dung(str(file_pt), metadata)
    return {"ok": True, "ma_pt": ma, "file": file_pt.name, "lan_dau": lan_dau,
            "so_luan_diem": len(luan_diem), "so_chunk": client.dem_chunk_doc_code(ma)}


# ─────────────── KIẾN TRÚC 1 TÀI LIỆU (user chốt 06/08: "chỉ cần bài học kinh nghiệm") ───────────────

def _ghi_kem(file_chinh: Path, doc_code: str, duoi: str, noi_dung: str) -> None:
    """Ghi file phụ lục nguyên tử cạnh file chính."""
    f = file_chinh.parent / f"{doc_code}_{duoi}"
    tam = f.with_name(f.name + ".tmp")
    tam.write_text(noi_dung, encoding="utf-8")
    os.replace(tam, f)


def nap_bai_hoc(doc_code: str, url: str, nguon_ten: str, chu_de: str, luan_diem: list[dict],
                client, import_date: str, nguoi_nhap: str = "", tu_khoa: str = "",
                boi_canh: str = "", ap_dung: str = "", thuat_ngu: str = "",
                cac_doan: list[dict] | None = None,
                van_ban: str = "", department: str = "", access_level: str = "",
                min_level: int | None = None, kho: Path | None = None) -> dict:
    """MỘT tài liệu duy nhất cho mỗi nguồn = BÀI HỌC KINH NGHIỆM (user chốt 06/08 — kho không
    còn cặp trích + phân tích). Bằng chứng KHÔNG mất: đoạn trích → phụ lục <mã>_bang-chung.md,
    transcript → <mã>_transcript.txt — cạnh file chính, KHÔNG vào catalog/Qdrant, xem được
    qua nút Dẫn chứng, và là nguồn cho 'phân tích lại'.

    Create-or-overwrite theo doc_code: lần đầu cần department/access_level/min_level (người
    chọn ở form); lần sau lấy quyền từ dòng catalog hiện có (form ẩn khu quyền). LƯỚI GIỮ
    BẰNG CHỨNG: ghi đè một tài liệu TRÍCH đời cũ (file chính đang là đoạn nguyên văn, chưa có
    phụ lục) → file cũ tự chuyển thành phụ lục bằng chứng TRƯỚC khi ghi đè, không mất lời gốc."""
    from src.main import DEPT_FOLDER, doc_catalog, duong_dan_khong_trung, ghi_catalog

    luan_diem = [ld for ld in luan_diem
                 if (ld.get("noi_dung") or "").strip() and ld.get("neo")]
    if not luan_diem:
        raise ValueError("Không có bài học nào để ghi — tài liệu rỗng")

    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    row = next((r for r in doc_catalog(kho) if r["Mã tài liệu"] == doc_code), None)
    lan_dau = row is None
    if lan_dau:
        if not department or not access_level or min_level is None:
            raise ValueError("Tài liệu mới cần chọn bộ phận / mức truy cập / level")
        ngan = DEPT_FOLDER.get(department, "00_Chung")
        (kho / ngan).mkdir(parents=True, exist_ok=True)
        file_chinh = duong_dan_khong_trung(kho / ngan, f"{doc_code}_Bai-hoc.md")
    else:
        ngan = (row.get("Ngăn") or "").strip() or DEPT_FOLDER.get(row.get("Bộ phận"), "00_Chung")
        ten = (row.get("Tên file mới") or f"{doc_code}_Bai-hoc.md").strip()
        file_chinh = kho / ngan / ten
        department = row.get("Bộ phận") or department
        access_level = row.get("Mức truy cập") or access_level
        ml = str(row.get("Level tối thiểu") or "").strip()
        min_level = int(ml) if ml.isdigit() else min_level
        nguon_ten = nguon_ten or row.get("Tên nguồn") or ""
        # LƯỚI GIỮ BẰNG CHỨNG: file chính đời cũ là bản TRÍCH (không phải bài học) và chưa
        # có phụ lục → chuyển nó thành phụ lục trước khi ghi đè
        bc = file_chinh.parent / f"{doc_code}_bang-chung.md"
        if file_chinh.is_file() and not bc.is_file():
            dong_dau = file_chinh.read_text(encoding="utf-8").split("\n", 1)[0]
            if not dong_dau.startswith("# Bài học kinh nghiệm"):
                os.replace(file_chinh, bc)

    noi_dung = _noi_dung_ban_pt(nguon_ten or doc_code, doc_code, nguon_ten, chu_de,
                                luan_diem, boi_canh=boi_canh, ap_dung=ap_dung,
                                thuat_ngu=thuat_ngu,
                                noi_dan_chung="phụ lục bằng chứng kèm tài liệu")
    file_chinh.parent.mkdir(parents=True, exist_ok=True)
    tam = file_chinh.with_name(file_chinh.name + ".tmp")
    tam.write_text(noi_dung, encoding="utf-8")
    os.replace(tam, file_chinh)

    if cac_doan:   # phụ lục bằng chứng — cùng định dạng tài liệu trích cũ (parse lại được)
        from src.nap_youtube import _noi_dung_tai_lieu
        _ghi_kem(file_chinh, doc_code, "bang-chung.md",
                 _noi_dung_tai_lieu(nguon_ten, url, cac_doan))
    if van_ban.strip():
        _ghi_kem(file_chinh, doc_code, "transcript.txt", van_ban)

    metadata = {
        # 06/08 user chốt "bỏ hết chữ Bài học kinh nghiệm ở tiêu đề" — title là CHỦ ĐỀ
        # thuần (chip "↳ Bài học kinh nghiệm" trong bảng đã nói vai, khỏi lặp trong chữ).
        "title": chu_de.strip() or nguon_ten or doc_code,
        "keywords": tu_khoa.strip(),
        "owner": (nguoi_nhap or "").strip() or (row.get("Phụ trách") if row else "") or "",
        "version": "v1", "department": department, "doc_type": "Khác",
        "effective_status": (row.get("Hiệu lực") if row else "") or "Còn hiệu lực",
        "access_level": access_level,
        "min_level": int(min_level) if min_level is not None else None,
        "doc_code": doc_code, "import_date": import_date[:10],
        "original_filename": file_chinh.name,
        "tang_nguon": (row.get("Tầng nguồn") if row else "") or "ngoai",
        "nguon_ten": nguon_ten or "",
    }
    client.cap_nhat_noi_dung(str(file_chinh), metadata)   # create-or-update, chống mồ côi
    if lan_dau:
        ghi_catalog(kho, [
            doc_code, metadata["import_date"], metadata["title"], metadata["department"],
            metadata["doc_type"], metadata["effective_status"], "v1",
            metadata["access_level"],
            metadata["min_level"] if metadata["min_level"] is not None else "",
            metadata["keywords"], metadata["owner"], file_chinh.name, ngan,
            "false", doc_code, "", metadata["tang_nguon"], metadata["nguon_ten"]])
    else:   # ghi đè: catalog phản ánh chủ đề/từ khóa/người duyệt mới (Qdrant đã cập ở trên)
        from src.main import cap_nhat_metadata_an_toan
        cap_nhat_metadata_an_toan(doc_code, {"title": metadata["title"],
                                             "keywords": metadata["keywords"],
                                             "owner": metadata["owner"]}, kho)

    # TÀI LIỆU LIÊN QUAN — bản rẻ (07/08): vector similarity thuần, tính lại mỗi lần nạp/
    # duyệt lại (chủ đề có thể đổi). Lỗi không chặn ghi bài học — chỉ mất phần liên quan.
    try:
        from src.tai_lieu_lien_quan import tinh_va_luu_lien_quan
        tinh_va_luu_lien_quan(doc_code, metadata["title"], metadata["keywords"], client, kho)
    except Exception as e:
        logging.warning("Không tính được tài liệu liên quan cho %s: %s", doc_code, e)
    return {"ok": True, "doc_code": doc_code, "file": file_chinh.name, "lan_dau": lan_dau,
            "so_luan_diem": len(luan_diem), "so_chunk": client.dem_chunk_doc_code(doc_code)}
