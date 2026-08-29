"""Cỗ máy chẩn đoán số liệu TỔNG QUÁT — luật nằm NGOÀI code (rules/diagnosis_rules.csv).

Nguyên tắc chống bịa: engine CHỈ kết luận từ luật đã khớp trong bảng luật do user soạn.
LLM không được suy diễn chẩn đoán — chỉ diễn giải luật đã khớp (qa_pipeline lo, kèm phản biện).

Muốn thêm lĩnh vực/luật mới: thêm dòng vào CSV, KHÔNG sửa file này.
Biến dùng được trong cột `dieu_kien`: tên BIẾN LUẬT (vd `ctr`, `retention`) và `<tên>_baseline`
(trung vị của chính dữ liệu người dùng — bền với outlier).

★ TẦNG PHIÊN DỊCH (rules/column_mapping.csv):
Report YouTube Studio thật dùng tên cột tiếng Anh dài ("Impressions click-through rate (%)")
và đơn vị PHẦN TRĂM (4.61 chứ không phải 0.0461). Bảng ánh xạ đổi tên cột report → biến luật
+ nhân HỆ SỐ quy đổi đơn vị (%→tỷ lệ 0-1). Thêm report dạng mới = thêm dòng ánh xạ, không sửa code.
Đây là ranh giới minh bạch: mọi biến luật đều truy được về đúng cột report + hệ số nào.
"""

import logging
import re
import unicodedata
from pathlib import Path

import pandas as pd

_RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
DUONG_DAN_LUAT = _RULES_DIR / "diagnosis_rules.csv"
DUONG_DAN_ANH_XA = _RULES_DIR / "column_mapping.csv"
DUONG_DAN_PROFILE = _RULES_DIR / "content_type_profiles.csv"  # profile loại kênh (luật NGOÀI code)
DUONG_DAN_TU_KHOA_NHOM = _RULES_DIR / "tu_khoa_nhom_nghia.csv"  # §12.4(b): gộp từ đồng nghĩa (NGOÀI code)

# Thứ tự phễu top-down — báo TẦNG VỠ SỚM NHẤT trước
FUNNEL = ["impressions", "ctr", "views", "retention", "watchtime", "engagement", "revenue"]

MIN_DONG_BASELINE = 5  # dưới ngưỡng này baseline kém tin cậy → cảnh báo
MIN_DONG_NHOM = 5      # nhóm (độ dài/tuổi) ít hơn ngần này video → median không đáng tin, để None

# Nhãn dòng tổng của report YouTube Studio (cột đầu = "Total")
NHAN_TONG = "total"
# Report YouTube Studio xuất tiếng Anh HOẶC tiếng Việt — nhận diện cả hai (tên đã _chuan_hoa_ten).
# NFC hóa để literal khớp tên cột bất kể Excel lưu dạng tổ hợp/dựng sẵn.
_nfc_t = lambda *xs: tuple(unicodedata.normalize("NFC", x) for x in xs)
NHAN_TONG_SET = _nfc_t("total", "tổng", "tong")                 # nhãn dòng TỔNG kênh (EN + VN)
CONTENT_ALIASES = _nfc_t("content", "nội_dung", "noi_dung")     # cột ĐỊNH DANH (video id / dòng Tổng)
TITLE_ALIASES = _nfc_t("video_title", "tiêu_đề_video", "tieu_de_video")  # cột TIÊU ĐỀ video

# ═══ NỀN THỐNG KÊ (Giai đoạn 1 — methodology mục 4 & 8) — chỉ hàm tiện ích, CHƯA đổi
#     hành vi chẩn đoán. Các giai đoạn sau (baseline 3 lớp, 4 trục chấm điểm) gọi vào đây. ═══

# Ngưỡng cắt NHÓM ĐỘ DÀI (phút) — methodology B1 "độ dài vs hiệu quả"
DO_DAI_NGAN_PHUT = 8    # < 8' = ngắn
DO_DAI_DAI_PHUT = 15    # 8–15' = vừa; > 15' = dài

# Ngưỡng cắt NHÓM TUỔI video (ngày) — methodology mục 4 (baseline theo tuổi) & mục 7
TUOI_MOI_NGAY = 7       # < 7 ngày = mới (thuật toán còn đang thử đẩy)
TUOI_DANG_CHAY_NGAY = 30  # 7–30 = đang chạy; > 30 = đuôi dài

NHAN_KHONG_RO = "khong_ro"  # thiếu nguyên liệu để phân nhóm → không đoán

# Van chống bịa cho SỐ LIỆU (methodology mục 8): ngưỡng cỡ mẫu ĐỘNG — video chưa đủ
# view thì KHÔNG kết luận retention/CTR (mẫu quá nhỏ → vô nghĩa), xếp "chưa đủ dữ liệu".
NGUONG_SAN = 100        # sàn cứng tối thiểu
TY_LE_MEDIAN = 0.1      # hoặc 10% median view kênh — lấy giá trị LỚN HƠN (ngưỡng tự lớn theo kênh)

# ═══ Giai đoạn 3 — bốn trục chấm điểm (methodology mục 5). Ngưỡng so với baseline
#     (tỷ lệ) đặt tập trung ở đây cho dễ chỉnh. Bốn trạng thái: ✓ đạt / ⚠ cảnh báo /
#     ✗ hỏng / ? chưa đủ dữ liệu. ═══
NGUONG_LECH_NGAY = 3    # ngày nhập tay lệch quá ngần này với dữ liệu theo ngày → cảnh báo
TY_LE_TRUC_THAP = 0.7      # < 70% baseline = thấp
TY_LE_TRUC_RAT_THAP = 0.5  # < 50% baseline = rất thấp
TY_LE_TRUC_CAO = 1.15      # >= 115% baseline = cao
TY_LE_TRU_COT = 2.0        # views >= 2× median kênh = video trụ cột (gánh view)
TIEN_VARS = ("revenue", "ad_revenue", "rpm", "cpm")  # 4 chỉ số TIỀN — kênh không có cái nào = chưa monetize


def _da_monetize(so: pd.DataFrame) -> bool:
    """Kênh đã bật kiếm tiền chưa — MỘT nguồn dùng chung (§12.4 bước 2: trước đây `rpm_theo_format`
    tự kiểm tra inline, nay trích ra để chỗ khác (vd tu_khoa theo RPM) gọi lại thay vì tự chế bản
    khác dễ lệch nghĩa). Kênh có ít nhất một cột trong TIEN_VARS còn giá trị thật → đã monetize."""
    return any(c in so.columns and so[c].notna().any() for c in TIEN_VARS)
# Dấu hiệu tên cột TIỀN của YouTube (đa ngôn ngữ) — để CẢNH BÁO khi có cột tiền mà chưa ánh xạ được
# biến nào (lưới an toàn chống lỗi âm thầm kết luận 'chưa monetize'). CHỈ tín hiệu mạnh, KHÔNG trùng
# cột affiliate/hoa hồng (tránh báo nhầm kênh thật sự chưa monetize như Space có 'Tổng doanh số').
_TIN_HIEU_TIEN = re.compile(
    r"\brpm\b|\bcpm\b|estimated revenue|doanh thu ước tính|doanh thu mỗi nghìn|"
    r"ad revenue|doanh thu từ quảng cáo|quảng cáo trên youtube",
    re.IGNORECASE)
NGUONG_KHAN_GIA_THAP = 0.15  # tỷ lệ người xem quay lại < 15% = kênh đang ĐỐT (hút người lạ rồi mất)

# ═══ CHẾ ĐỘ CHỈ-SỐ cho kênh CHƯA BẬT KIẾM TIỀN (Owner chốt 29/08/2026) ═══
# "Kênh chưa monetize: CHỈ quan tâm mức tăng trưởng view / AVD / CTR. Không đưa ra so
# sánh gợi ý nào cả — kênh nhỏ các chỉ số đang chưa chính xác."
# Nghĩa là ở chế độ này engine KHÔNG phán quyết, KHÔNG chấm 4 trục, KHÔNG khuyến nghị:
# chỉ TRÌNH BÀY số + xu hướng, cộng một van duy nhất là cảnh báo video sụt SÂU BẤT THƯỜNG
# so với chính kênh (Owner giữ lại để không bỏ lọt ca hỏng nặng thật).
# Vào chế độ khi: vòng đời uom_mam/sandbox HOẶC report thiếu hẳn cột tiền.
TRANG_THAI_CHUA_TIEN = ("uom_mam", "sandbox")
# Sụt sâu = dưới ngần này lần trung vị KÊNH. Đặt THẤP hơn hẳn TY_LE_TRUC_RAT_THAP (0.5) vì
# đây không phải chấm điểm — chỉ bắt ca dị thường rõ rệt trên kênh mà số vốn đã nhiễu.
TY_LE_SUT_SAU = 0.35
CHI_SO_CHUA_TIEN = ("views", "avd", "ctr")   # đúng 3 chỉ số Owner nêu

# CẢNH BÁO sụt sâu KHÔNG xét views — ĐO THẬT 29/08 trên 2 report thật: kênh Wheel có
# 41/108 video dưới 0.35× trung vị view, Space 8/46. View của kênh YouTube vốn phân phối
# lệch cực mạnh (vài video trúng gánh phần lớn view, đuôi dài ít view) nên "view thấp hơn
# trung vị nhiều lần" là HÌNH DẠNG BÌNH THƯỜNG, không phải bệnh — báo động theo view chỉ
# tạo nhiễu. AVD/CTR là chỉ số CHẤT LƯỢNG mỗi lượt xem, không bị hiệu ứng đó (đo cùng lúc:
# AVD 13/46 và 19/107, CTR 1/46 và 2/90 — mức cảnh báo hợp lý).
CHI_SO_CANH_BAO = ("avd", "ctr")


def che_do_chi_so(so: pd.DataFrame, trang_thai_kenh: str | None) -> bool:
    """Kênh này có chạy CHẾ ĐỘ CHỈ-SỐ (không phán quyết) không?

    True khi vòng đời là uom_mam/sandbox HOẶC report không có cột tiền nào. Hai vế
    ĐỘC LẬP có chủ đích: trạng thái khai tay có thể lạc hậu, còn report thiếu cột tiền
    là bằng chứng trực tiếp — thoả một trong hai là đủ (Owner chốt 29/08)."""
    if (trang_thai_kenh or "").strip() in TRANG_THAI_CHUA_TIEN:
        return True
    return not _da_monetize(so)

# ═══ Giai đoạn 4 — TẬP PHÁN QUYẾT HỮU HẠN (methodology mục 5: 4 trục vào, 1 trong 7 ra) ═══
# ĐÂY là cơ chế chống "cỗ máy đẻ luật": engine KHÔNG được sinh phán quyết ngoài tập này.
# Số phán quyết ít + mỗi cái neo vào MỘT hành động cụ thể.
PHAN_QUYET = [
    "nhan_ban",          # 4 trục đạt → công thức thắng, làm thêm
    "giu",               # ổn, không nổi bật, giữ nguyên
    "sua_bao_bi",        # CTR hỏng, Retention ổn → sửa thumbnail/tiêu đề
    "sua_noi_dung",      # Retention hỏng (giật tít / lê thê) → sửa nội dung
    "doi_ngach_vi_tien", # nội dung giỏi kéo view nhưng RPM đáy → đừng nhân bản cho doanh thu
    "bo",                # phần lớn trục hỏng → khai tử, thôi đổ công suất
    "chua_du_du_lieu",   # mẫu quá nhỏ → van chống bịa, không đoán
]


def doc_bang_luat(path=DUONG_DAN_LUAT) -> list[dict]:
    return pd.read_csv(path).fillna("").to_dict("records")


def doc_anh_xa(path=DUONG_DAN_ANH_XA) -> list[dict]:
    """Đọc bảng ánh xạ cột. Trả [] nếu chưa có file (giữ tương thích ngược)."""
    if not Path(path).exists():
        return []
    return pd.read_csv(path).fillna("").to_dict("records")


# ═══ TẦNG LOẠI KÊNH (content type) — đọc số theo bối cảnh nội dung, luật NGOÀI code ═══
# Baseline TỰ KÊNH vẫn là xương sống (không bao giờ bỏ — không bịa). Loại kênh chỉ THÊM
# lên trên: (1) chủ yếu đổi cách DIỄN GIẢI (LLM + câu chẩn đoán, xem app/qa_pipeline);
# (2) hạn chế đổi VÀI ngưỡng tuyệt đối CÓ CĂN CỨ (kieu 'noi_nguong' nới ngưỡng retention,
# 'ky_vong_thap' coi RPM thấp là quy luật). Mọi kieu KHÁC chỉ để diễn giải/hiển thị, KHÔNG
# đụng ngưỡng. Loại kênh rỗng/không tìm thấy → None → engine chạy như chưa có tính năng.

def doc_content_profile(loai_kenh: str | None, path=DUONG_DAN_PROFILE) -> dict | None:
    """Đọc profile 1 loại kênh từ file ngoài code. Trả {loai_kenh, ten_hien_thi, dieu_chinh:[...]}
    hoặc None nếu rỗng/không có/không tìm thấy (mặc định AN TOÀN: không giả định loại kênh).
    Mỗi điều chỉnh: {chi_so, kieu, he_so(float|None), do_tin_cay, nguon}."""
    key = (loai_kenh or "").strip()
    if not key or not Path(path).exists():
        return None
    rows = pd.read_csv(path).fillna("").to_dict("records")
    dong = [r for r in rows if str(r.get("loai_kenh", "")).strip() == key]
    if not dong:
        return None
    dieu_chinh = []
    for r in dong:
        hs = str(r.get("he_so", "")).strip()
        dieu_chinh.append({
            "chi_so": str(r.get("chi_so", "")).strip(),
            "kieu": str(r.get("kieu", "")).strip(),
            "he_so": float(hs) if hs else None,
            "do_tin_cay": str(r.get("do_tin_cay", "")).strip(),
            "nguon": str(r.get("nguon", "")).strip(),
        })
    return {"loai_kenh": key,
            "ten_hien_thi": str(dong[0].get("ten_hien_thi", "")).strip() or key,
            "dieu_chinh": dieu_chinh}


def _tai_nhom_nghia(path=DUONG_DAN_TU_KHOA_NHOM) -> dict:
    """§12.4(b): bảng gộp từ đồng nghĩa/cùng chủ đề NGOÀI CODE cho khối từ khóa Winning Format
    (cột tu,nhom_nghia — dòng '#' đầu là comment giới hạn, bị bỏ qua). Trả {} nếu rỗng/không có
    → AN TOÀN TUYỆT ĐỐI: mọi từ đếm riêng như cũ (byte-identical với trước §12.4(b))."""
    if not Path(path).exists():
        return {}
    rows = pd.read_csv(path, comment="#").fillna("").to_dict("records")
    return {str(r.get("tu", "")).strip().lower(): str(r.get("nhom_nghia", "")).strip()
            for r in rows
            if str(r.get("tu", "")).strip() and str(r.get("nhom_nghia", "")).strip()}


def _dieu_chinh(profile: dict | None, chi_so: str, kieu: str) -> dict | None:
    """Tìm điều chỉnh khớp (chi_so, kieu) trong profile — hoặc None. Chỉ 2 kieu engine hành động:
    ('retention','noi_nguong') nới ngưỡng retention; ('rpm','ky_vong_thap') RPM thấp là quy luật."""
    if not profile:
        return None
    return next((d for d in profile["dieu_chinh"]
                 if d["chi_so"] == chi_so and d["kieu"] == kieu), None)


def _chuan_hoa_ten(c: str) -> str:
    # NFC để khớp tên cột tiếng Việt bất kể Excel lưu dạng tổ hợp (NFD) hay dựng sẵn (NFC).
    return unicodedata.normalize("NFC", str(c).strip().lower().replace(" ", "_"))


def ap_anh_xa_cot(df: pd.DataFrame, anh_xa: list[dict] | None = None) -> pd.DataFrame:
    """Đổi tên cột report thật → biến luật + nhân hệ số quy đổi đơn vị.

    - Khớp tên cột KHÔNG phân biệt hoa/thường + khoảng trắng.
    - Cột report không có trong bảng ánh xạ → GIỮ NGUYÊN (không mất dữ liệu).
    - Hệ số rỗng/không đọc được → bỏ qua cột đó (vd cột dạng h:mm:ss).
    - Biến luật đã có sẵn đúng tên trong report thì vẫn dùng được (ánh xạ không bắt buộc).
    """
    if anh_xa is None:
        anh_xa = doc_anh_xa()

    # map: tên cột report (đã chuẩn hóa) -> (bien_luat, he_so)
    quy_tac = {}
    for r in anh_xa:
        cot = _chuan_hoa_ten(r.get("cot_report", ""))
        bien = str(r.get("bien_luat", "")).strip()
        hs = r.get("he_so", "")
        if not cot or not bien:
            continue
        try:
            hs = float(hs)
        except (ValueError, TypeError):
            continue  # hệ số rỗng → cột không map số (bỏ qua)
        quy_tac[cot] = (bien, hs)

    out = pd.DataFrame(index=df.index)
    cot_chuan = {c: _chuan_hoa_ten(c) for c in df.columns}
    for c in df.columns:
        key = cot_chuan[c]
        if key in quy_tac:
            bien, hs = quy_tac[key]
            out[bien] = pd.to_numeric(df[c], errors="coerce") * hs
        else:
            # Cột TEXT định danh/tiêu đề (EN hoặc VN) → chuẩn hóa về tên chuẩn để downstream
            # (hiển thị tiêu đề, tách Total) đọc thống nhất không cần biết ngôn ngữ report.
            if key in CONTENT_ALIASES:
                key = "content"
            elif key in TITLE_ALIASES:
                key = "video_title"
            # giữ nguyên cột (tên chuẩn hóa) nếu chưa có sẵn từ ánh xạ
            if key not in out.columns:
                out[key] = df[c]
    return out


# ═══ Giai đoạn 1 nền thống kê — hàm tiện ích cho các giai đoạn sau (baseline 3 lớp,
#     4 trục chấm điểm). CHƯA đổi hành vi chẩn đoán; chỉ được gọi khi giai đoạn sau viết. ═══

def them_cot_phai_sinh(df_map: pd.DataFrame, ngay_chay=None) -> pd.DataFrame:
    """Hậu xử lý SAU ap_anh_xa_cot: thêm cột phái sinh. Cùng phong cách ap_anh_xa_cot —
    thiếu nguyên liệu thì BỎ QUA cột, KHÔNG raise (van chống bịa cho số liệu).

    - duration_min = duration_sec / 60.
    - tuoi_video_ngay = số ngày từ 'Video publish time' (dạng 'Mar 25, 2026') đến
      ngay_chay; ngay_chay=None → BỎ QUA cột tuổi (không lỗi).
    - returning_ratio = returning / (new + returning), CHỈ khi mẫu số > 0.
    """
    out = df_map.copy()

    if "duration_sec" in out.columns:
        out["duration_min"] = pd.to_numeric(out["duration_sec"], errors="coerce") / 60

    if ngay_chay is not None and "video_publish_time" in out.columns:
        ngay_dang = pd.to_datetime(out["video_publish_time"], format="%b %d, %Y",
                                   errors="coerce")
        out["tuoi_video_ngay"] = (pd.Timestamp(ngay_chay).normalize()
                                  - ngay_dang.dt.normalize()).dt.days

    if "new_viewers" in out.columns and "returning_viewers" in out.columns:
        new = pd.to_numeric(out["new_viewers"], errors="coerce")
        ret = pd.to_numeric(out["returning_viewers"], errors="coerce")
        tong = new + ret
        out["returning_ratio"] = ret / tong.where(tong > 0)  # mẫu ≤ 0/NaN → NaN, khỏi chia 0
    return out


def phan_nhom_do_dai(df: pd.DataFrame) -> pd.Series:
    """Nhãn nhóm ĐỘ DÀI mỗi hàng (methodology B1): 'ngắn' <8', 'vừa' 8–15', 'dài' >15'.
    Thiếu độ dài → 'khong_ro'. Dùng duration_min (từ them_cot_phai_sinh) hoặc duration_sec."""
    if "duration_min" in df.columns:
        phut = pd.to_numeric(df["duration_min"], errors="coerce")
    elif "duration_sec" in df.columns:
        phut = pd.to_numeric(df["duration_sec"], errors="coerce") / 60
    else:
        return pd.Series([NHAN_KHONG_RO] * len(df), index=df.index)

    def nhan(x):
        if pd.isna(x):
            return NHAN_KHONG_RO
        if x < DO_DAI_NGAN_PHUT:
            return "ngắn"
        return "vừa" if x <= DO_DAI_DAI_PHUT else "dài"
    return phut.map(nhan)


def phan_nhom_tuoi(df: pd.DataFrame) -> pd.Series:
    """Nhãn nhóm TUỔI mỗi hàng (methodology mục 4): 'mới' <7 ngày, 'đang chạy' 7–30,
    'đuôi dài' >30. Thiếu tuoi_video_ngay (vd không có ngay_chay) → 'khong_ro'."""
    if "tuoi_video_ngay" not in df.columns:
        return pd.Series([NHAN_KHONG_RO] * len(df), index=df.index)
    tuoi = pd.to_numeric(df["tuoi_video_ngay"], errors="coerce")

    def nhan(x):
        if pd.isna(x):
            return NHAN_KHONG_RO
        if x < TUOI_MOI_NGAY:
            return "mới"
        return "đang chạy" if x <= TUOI_DANG_CHAY_NGAY else "đuôi dài"
    return tuoi.map(nhan)


def du_mau_ket_luan(views, median_views_kenh) -> bool:
    """Van chống bịa cho SỐ LIỆU (methodology mục 8): video ĐỦ view để KẾT LUẬN
    retention/CTR chưa? True chỉ khi views >= max(NGUONG_SAN, TY_LE_MEDIAN*median_kênh).
    Ngưỡng ĐỘNG (tự lớn theo kênh, không cứng lỗi thời). views thiếu → False; median
    thiếu → dùng sàn cứng NGUONG_SAN. Giai đoạn sau: chưa đủ view → 'chưa đủ dữ liệu'."""
    try:
        v = float(views)
    except (TypeError, ValueError):
        return False
    if pd.isna(v):
        return False
    try:
        med = float(median_views_kenh)
        if pd.isna(med):
            med = 0.0
    except (TypeError, ValueError):
        med = 0.0
    return v >= max(NGUONG_SAN, TY_LE_MEDIAN * med)


def doc_bao_cao(path) -> pd.DataFrame:
    """Đọc báo cáo Excel/CSV; chuẩn hóa tên cột (thường, gạch dưới).

    KHÔNG áp ánh xạ ở đây — để hàm chẩn đoán chủ động áp, giữ raw cho phần tách dòng Total.
    """
    path = str(path)
    if path.lower().endswith((".xlsx", ".xls")):
        # Report YouTube Studio xuất .xlsx nhiều sheet; "Table data" là bảng theo video
        xl = pd.ExcelFile(path)
        ten_sheet = next((s for s in xl.sheet_names if "table" in s.lower()), xl.sheet_names[0])
        df = xl.parse(ten_sheet)
    else:
        df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def doc_chart_data(path):
    """Đọc Chart data (dữ liệu theo NGÀY mỗi video: Date/Content/publish/Engaged views).
    xlsx → sheet 'Chart data'; csv rời (Table data) KHÔNG kèm chart → None. Không lỗi nếu vắng."""
    path = str(path)
    try:
        if path.lower().endswith((".xlsx", ".xls")):
            xl = pd.ExcelFile(path)
            ten = next((s for s in xl.sheet_names if "chart" in s.lower()), None)
            if ten is None:
                return None
            df = xl.parse(ten)
        else:
            return None
        df.columns = [str(c).strip() for c in df.columns]
        return df if len(df) else None
    except Exception:
        return None


def _cot_content(df: pd.DataFrame):
    """Cột định danh (EN 'Content' / VN 'Nội dung') — None nếu không có."""
    return next((c for c in df.columns if _chuan_hoa_ten(c) in CONTENT_ALIASES), None)


def _la_report_youtube(df: pd.DataFrame) -> bool:
    """Report YouTube Studio: có cột định danh (Content/Nội dung) + 1 dòng TỔNG (Total/Tổng)."""
    col = _cot_content(df)
    if col is None:
        return False
    return df[col].astype(str).str.strip().str.lower().isin(NHAN_TONG_SET).any()


def tach_total_va_video(df: pd.DataFrame):
    """Tách report YouTube Studio thành (dòng_total, df_các_video).

    Nếu không phải report YouTube (không có dòng Total) → (None, df nguyên).
    """
    if not _la_report_youtube(df):
        return None, df
    col = _cot_content(df)
    la_total = df[col].astype(str).str.strip().str.lower().isin(NHAN_TONG_SET)
    dong_total = df[la_total].iloc[0] if la_total.any() else None
    df_video = df[~la_total].reset_index(drop=True)
    return dong_total, df_video


def _sach(d: dict) -> dict:
    """numpy → float thuần (để trả JSON được), bỏ ô trống/không phải số."""
    out = {}
    for k, v in d.items():
        try:
            if pd.notna(v):
                out[k] = float(v)
        except (ValueError, TypeError):
            continue
    return out


def _khop(dieu_kien: str, bien: dict) -> bool:
    """Chấm 1 biểu thức luật. Thiếu chỉ số trong báo cáo → luật không áp (không lỗi).

    eval bị khóa builtins, chỉ thấy các biến số liệu; file luật do chính user soạn
    trên máy user nên đây là ranh giới tin cậy chấp nhận được.
    """
    expr = dieu_kien
    for tu, thay in ((r"\bAND\b", " and "), (r"\bOR\b", " or "), (r"\bNOT\b", " not ")):
        expr = re.sub(tu, thay, expr, flags=re.IGNORECASE)
    try:
        return bool(eval(expr, {"__builtins__": {}}, dict(bien)))
    except Exception:
        return False


def _cham_luat(hien_tai: dict, baselines: dict, bang_luat: list[dict]) -> tuple:
    """Chấm toàn bộ luật với 1 hàng số liệu + baseline. Trả (matched, tang_vo)."""
    bien = dict(hien_tai)
    bien.update({f"{k}_baseline": v for k, v in baselines.items()})

    matched = [r for r in bang_luat if _khop(str(r["dieu_kien"]), bien)]
    matched.sort(key=lambda r: FUNNEL.index(r["tang_pheu"]) if r["tang_pheu"] in FUNNEL
                 else len(FUNNEL))
    tang_vo = next((r["tang_pheu"] for r in matched if r["tang_pheu"] in FUNNEL), None)
    return matched, tang_vo


def _tinh_baseline(so: pd.DataFrame) -> dict:
    """Baseline = trung vị mỗi cột số (bền với outlier). Cần >= 2 hàng."""
    return _sach(so.median().to_dict()) if len(so) >= 2 else {}


# ═══ Giai đoạn 2 — BASELINE BA LỚP (analytic_methodology.md mục 4) ═══
# Ba điểm neo cho ba mục đích: theo NHÓM ĐỘ DÀI (đánh giá format), theo NHÓM TUỔI
# (đánh giá tăng trưởng), TOÀN KÊNH (chiến lược). Nguyên tắc lùi: nhóm thiếu mẫu thì
# median không đáng tin → để None, tầng trên tự lùi về toàn kênh + KHAI BÁO nguồn.
# LƯU Ý tương thích ngược: 20 luật YT cũ VẪN nhìn baseline = median TOÀN KÊNH (nhánh
# toan_kenh), engine chấm luật không đổi — baseline 3 lớp chỉ để giai đoạn sau dùng.

def _median_nhom(so: pd.DataFrame, mask) -> dict | None:
    """Median của các video trong 1 nhóm — None nếu nhóm < MIN_DONG_NHOM (mẫu quá nhỏ)."""
    con = so[mask]
    if len(con) < MIN_DONG_NHOM:
        return None
    return _sach(con.median().to_dict())


def tinh_baseline_3_lop(so: pd.DataFrame, nhan_do_dai, nhan_tuoi) -> dict:
    """Baseline 3 lớp từ bảng số video (đã bỏ Total, đã ánh xạ) + 2 nhãn nhóm (Giai đoạn 1).
    Trả dict: {toan_kenh: {biến→median}, theo_do_dai: {ngắn/vừa/dài → dict|None},
    theo_tuoi: {mới/đang chạy/đuôi dài → dict|None}}. Nhóm thiếu mẫu → None (không median)."""
    return {
        "toan_kenh": _tinh_baseline(so),                     # = baseline cũ, giữ nguyên
        "theo_do_dai": {g: _median_nhom(so, nhan_do_dai == g)
                        for g in ("ngắn", "vừa", "dài")},
        "theo_tuoi": {g: _median_nhom(so, nhan_tuoi == g)
                      for g in ("mới", "đang chạy", "đuôi dài")},
    }


def chon_baseline(ten_bien: str, nhan_do_dai_video: str, nhan_tuoi_video: str,
                  muc_dich: str, bl3: dict) -> tuple:
    """Chọn baseline theo MỤC ĐÍCH, có nguyên tắc lùi. Trả (giá_trị, chuỗi_nguồn).
    Chuỗi nguồn BẮT BUỘC trả ra để tầng trên khai báo minh bạch (van chống bịa):
    user biết con số đang so với baseline nào.

    - format      → lớp theo_do_dai của đúng nhãn nhóm độ dài video.
    - tang_truong → lớp theo_tuoi của đúng nhãn nhóm tuổi video.
    - chien_luoc  → dùng thẳng toàn kênh.
    Lùi: ô lớp ưu tiên là None (nhóm thiếu mẫu) → lùi về toàn kênh, ghi rõ lý do."""
    toan = bl3.get("toan_kenh") or {}
    if muc_dich == "chien_luoc":
        return toan.get(ten_bien), "toàn kênh"
    if muc_dich == "format":
        lop = (bl3.get("theo_do_dai") or {}).get(nhan_do_dai_video)
        nhan, ly_do = nhan_do_dai_video, "nhóm độ dài"
    elif muc_dich == "tang_truong":
        lop = (bl3.get("theo_tuoi") or {}).get(nhan_tuoi_video)
        nhan, ly_do = nhan_tuoi_video, "nhóm tuổi"
    else:
        raise ValueError(f"muc_dich '{muc_dich}' không hợp lệ "
                         "(format | tang_truong | chien_luoc)")
    if lop is None:                                          # nhóm thiếu mẫu → lùi
        return toan.get(ten_bien), f"lùi về toàn kênh do {ly_do} thiếu mẫu"
    if ten_bien in lop:
        return lop[ten_bien], f"{ly_do} '{nhan}'"
    return toan.get(ten_bien), "toàn kênh"                   # nhóm đủ mẫu nhưng biến vắng


# ═══ Giai đoạn 3 — ĐỐI CHIẾU NGÀY CHẠY + BỐN TRỤC CHẤM ĐIỂM (methodology mục 5) ═══
# Bốn trục chấm ĐỘC LẬP, mỗi trục trả {trang_thai, ly_do, so_lieu}. CHƯA tổng hợp
# thành phán quyết (Giai đoạn 4). Trạng thái: ✓ đạt / ⚠ cảnh báo / ✗ hỏng / ? chưa đủ.

def doi_chieu_ngay_chay(ngay_user, df_theo_ngay=None) -> tuple:
    """Ngày user nhập = ngay_chay CHÍNH THỨC (để tính tuoi_video_ngay). Đối chiếu với
    ngày MỚI NHẤT trong Chart/Totals nếu có: lệch > NGUONG_LECH_NGAY → kèm chuỗi cảnh
    báo (KHÔNG tự sửa ngày user — chỉ kiểm chéo chống nhập sai). Không có Chart/Totals
    → bỏ qua, không lỗi. Trả (ngay_chay: Timestamp, canh_bao: str|None)."""
    ngay = pd.Timestamp(ngay_user).normalize()
    if df_theo_ngay is None or len(df_theo_ngay) == 0:
        return ngay, None
    cot_ngay = next((c for c in df_theo_ngay.columns if _chuan_hoa_ten(c) == "date"), None)
    if cot_ngay is None:
        return ngay, None
    ngay_data = pd.to_datetime(df_theo_ngay[cot_ngay], errors="coerce").max()
    if pd.isna(ngay_data):
        return ngay, None
    lech = abs((ngay - ngay_data.normalize()).days)
    if lech > NGUONG_LECH_NGAY:
        return ngay, (f"Ngày nhập tay ({ngay.date()}) lệch {lech} ngày với ngày mới nhất "
                      f"trong dữ liệu theo ngày ({ngay_data.date()}) — kiểm tra lại.")
    return ngay, None


def _trang(trang_thai: str, ly_do: str, so_lieu: dict) -> dict:
    return {"trang_thai": trang_thai, "ly_do": ly_do, "so_lieu": so_lieu}


def cham_truc_noi_dung(video: dict, bl3: dict, nhan_do_dai: str, nhan_tuoi: str,
                       profile: dict | None = None) -> dict:
    """Trục NỘI DUNG = CTR × Retention × AVD. Retention QUYẾT trạng thái chính; AVD giữ
    hai vai (session đủ push? / nên dài hay ngắn hơn?) nhưng CHỐNG ĐẾM TRÙNG: AVD chỉ
    nâng/hạ ĐÚNG MỘT bậc khi MÂU THUẪN hướng với Retention, KHÔNG tạo phiếu hỏng riêng
    khi trùng hướng. Mẫu quá nhỏ (du_mau_ket_luan False) → '?' ngay, không chấm.
    profile loại kênh (nếu có + căn cứ): NỚI ngưỡng báo động retention theo he_so — baseline
    vẫn TỰ KÊNH, chỉ nới độ nhạy báo động cho loại kênh mà retention thô vốn thấp (vd trẻ em)."""
    toan = bl3.get("toan_kenh") or {}
    views = video.get("views")
    if not du_mau_ket_luan(views, toan.get("views")):
        return _trang("?", "Chưa đủ view để kết luận retention/CTR (mẫu quá nhỏ)",
                      {"views": views})

    ctr, ret = video.get("ctr"), video.get("retention")
    ctr_bl, _ = chon_baseline("ctr", nhan_do_dai, nhan_tuoi, "format", bl3)
    ret_bl, ng_ret = chon_baseline("retention", nhan_do_dai, nhan_tuoi, "format", bl3)
    so_lieu = {"ctr": ctr, "retention": ret, "nguon_baseline": ng_ret}
    if None in (ctr, ret, ctr_bl, ret_bl) or ctr_bl == 0 or ret_bl == 0:
        return _trang("?", "Thiếu CTR/Retention hoặc baseline để chấm nội dung", so_lieu)

    # NỚI ngưỡng retention theo loại kênh (chỉ khi profile có căn cứ). he_so > 1 → chia ngưỡng
    # xuống → video phải thấp HƠN NỮA mới bị coi là thấp/rất thấp. CTR không đụng.
    dc_ret = _dieu_chinh(profile, "retention", "noi_nguong")
    f_ret = dc_ret["he_so"] if dc_ret and dc_ret.get("he_so") else 1.0

    ctr_thap = ctr < ctr_bl * TY_LE_TRUC_THAP
    ctr_cao = ctr >= ctr_bl * TY_LE_TRUC_CAO
    ret_on = ret >= ret_bl * TY_LE_TRUC_THAP / f_ret
    ret_rat_thap = ret < ret_bl * TY_LE_TRUC_RAT_THAP / f_ret

    # benh = phân loại bệnh nội dung (tín hiệu MÁY ĐỌC cho tầng tổng hợp GĐ4, không đổi
    # trạng thái/ly_do): giat_tit & le_the = Retention hỏng; bao_bi_yeu = CTR hỏng; khoe = đạt.
    if ret_rat_thap:
        trang_thai, ly_do, benh = "✗", "Retention rất thấp — nội dung lê thê / cấu trúc dàn trải", "le_the"
    elif ctr_cao and not ret_on:
        trang_thai, ly_do, benh = "✗", "CTR cao nhưng giữ chân thấp — giật tít, nội dung không đúng bao bì", "giat_tit"
    elif ctr_thap and ret_on:
        trang_thai, ly_do, benh = "⚠", "CTR thấp nhưng giữ chân ổn — bao bì (thumbnail/tiêu đề) yếu", "bao_bi_yeu"
    elif ret_on and not ctr_thap:
        trang_thai, ly_do, benh = "✓", "Bao bì và giữ chân đều ổn", "khoe"
    else:
        trang_thai, ly_do, benh = "⚠", "Giữ chân dưới chuẩn nhẹ — cần theo dõi", "theo_doi"
    so_lieu["benh"] = benh
    if dc_ret:   # minh bạch: ghi rõ đã nới ngưỡng theo loại kênh + nguồn/độ tin cậy
        so_lieu["dieu_chinh"] = {"chi_so": "retention", "kieu": "noi_nguong", "he_so": f_ret,
                                 "loai_kenh": profile["ten_hien_thi"],
                                 "do_tin_cay": dc_ret["do_tin_cay"], "nguon": dc_ret["nguon"]}
        ly_do += (f" — (ngưỡng retention đã NỚI ×{f_ret:g} theo loại kênh "
                  f"{profile['ten_hien_thi']}, độ tin cậy: {dc_ret['do_tin_cay']})")

    # AVD hai vai — CHỐNG ĐẾM TRÙNG. AVD = video['avd'] hoặc suy từ Retention × duration_min.
    avd = video.get("avd")
    if avd is None and video.get("duration_min") is not None and ret is not None:
        avd = ret * video["duration_min"]
    avd_bl = toan.get("avd")
    if avd is not None and avd_bl:
        so_lieu["avd"] = avd
        so_lieu["avd_du_day"] = avd >= avd_bl          # vai 1: session đủ để YouTube đẩy?
        ret_tot = ret >= ret_bl
        avd_thap = avd < avd_bl
        if ret_tot and avd_thap:                        # MÂU THUẪN: giữ chân tốt, session ngắn
            ly_do += (" — gợi ý: nên làm DÀI HƠN (Retention tốt nhưng AVD thấp, "
                      "đang bỏ session time trên bàn)")
            if trang_thai == "✓":
                trang_thai = "⚠"                        # hạ ĐÚNG một bậc
        elif (not ret_tot) and (not avd_thap):          # MÂU THUẪN: giữ chân thấp, session dài
            ly_do += " — gợi ý: nên CẮT NGẮN (AVD cao nhưng Retention thấp, video lê thê)"
            if trang_thai == "✗":
                trang_thai = "⚠"                        # nâng ĐÚNG một bậc (session vẫn ổn)
        # else: AVD trùng hướng Retention → KHÔNG đổi trạng thái, KHÔNG thêm phiếu hỏng
    return _trang(trang_thai, ly_do, so_lieu)


def cham_truc_tien(video: dict, bl3: dict, profile: dict | None = None) -> dict:
    """Trục TIỀN: RPM so baseline toàn kênh (cao/thường/đáy) + rò rỉ phễu tiền
    (doanh thu/view) + đòn bẩy bỏ trống (endscreen/card CTR = 0 → 'tiền để trên bàn').
    Cột nào thiếu thì bỏ qua phần đó, không lỗi.
    profile loại kênh (nếu có + căn cứ 'ky_vong_thap', vd trẻ em theo COPPA): RPM đáy KHÔNG
    coi là bất thường (là quy luật của loại kênh) → không '⚠', không đẩy 'đổi ngách vì tiền'."""
    toan = bl3.get("toan_kenh") or {}
    # KÊNH CHƯA BẬT KIẾM TIỀN: baseline toàn kênh không có BẤT KỲ chỉ số tiền nào (report không
    # có cột revenue/rpm/cpm/ad_revenue) → KHÁC HẲN 'thiếu dữ liệu tạm thời' (còn ít nhất 1 cột
    # tiền nhưng video này trống). Giữ ký hiệu '?' để không vỡ tầng tổng hợp, NHƯNG gắn nhãn
    # máy-đọc 'chua_monetize' + lý do rõ để UI/tổng hợp không hiểu nhầm là cần đi tìm thêm số liệu.
    if not any(k in toan for k in TIEN_VARS):
        return _trang("?", "Kênh chưa bật kiếm tiền — chưa đánh giá được trục doanh thu, "
                      "tập trung vào lượt xem và giữ chân trước.", {"nhan": "chua_monetize"})
    rpm, rpm_bl = video.get("rpm"), toan.get("rpm")
    so_lieu = {"rpm": rpm}
    if rpm is None or rpm_bl in (None, 0):
        # Có cột tiền ở kênh nhưng video này trống RPM → THIẾU DỮ LIỆU thật (khác chua_monetize)
        so_lieu["nhan"] = "thieu_du_lieu"
        trang_thai, ly_do = "?", "Thiếu RPM hoặc baseline RPM để chấm trục tiền"
    elif rpm >= rpm_bl * TY_LE_TRUC_CAO:
        trang_thai, ly_do = "✓", "RPM cao hơn mặt bằng kênh — video sinh lời tốt"
    elif rpm < rpm_bl * TY_LE_TRUC_THAP:
        dc_rpm = _dieu_chinh(profile, "rpm", "ky_vong_thap")
        if dc_rpm:   # RPM thấp là QUY LUẬT của loại kênh (có căn cứ) → không báo bất thường
            trang_thai, ly_do = "✓", (f"RPM thấp là quy luật của loại kênh {profile['ten_hien_thi']} "
                                      f"— không coi là bất thường")
            so_lieu["dieu_chinh"] = {"chi_so": "rpm", "kieu": "ky_vong_thap",
                                     "loai_kenh": profile["ten_hien_thi"],
                                     "do_tin_cay": dc_rpm["do_tin_cay"], "nguon": dc_rpm["nguon"]}
        else:
            trang_thai, ly_do = "⚠", "RPM đáy so mặt bằng kênh — lượt xem rẻ tiền"
    else:
        trang_thai, ly_do = "✓", "RPM quanh mặt bằng kênh"

    views, rev = video.get("views"), video.get("revenue")
    rev_bl, views_bl = toan.get("revenue"), toan.get("views")
    if None not in (views, rev, rev_bl, views_bl) and views > 0 and views_bl > 0:
        rpv, rpv_bl = rev / views, rev_bl / views_bl
        so_lieu["revenue_per_view"] = rpv
        if rpv_bl > 0 and rpv < rpv_bl * TY_LE_TRUC_THAP:
            ly_do += " — rò rỉ phễu tiền: doanh thu/view dưới chuẩn kênh"

    for ten, nhan in (("endscreen_ctr", "end screen"), ("card_ctr", "card")):
        v = video.get(ten)
        if v is not None and v <= 0:
            ly_do += f" — tiền để trên bàn: chưa dùng {nhan} (CTR = 0)"
            so_lieu[ten] = v
    return _trang(trang_thai, ly_do, so_lieu)


def cham_truc_danh_muc(video: dict, bl3: dict) -> dict:
    """Trục DANH MỤC: video là trụ cột (gánh view) hay vãng lai? Vị trí theo view so
    median kênh + returning_ratio so baseline (kéo khán giả quay lại hay toàn người lạ)."""
    toan = bl3.get("toan_kenh") or {}
    views, med = video.get("views"), toan.get("views")
    rr, rr_bl = video.get("returning_ratio"), toan.get("returning_ratio")
    so_lieu = {"views": views, "returning_ratio": rr}
    if views is None or med in (None, 0):
        return _trang("?", "Thiếu views hoặc baseline để chấm danh mục", so_lieu)

    if views >= med * TY_LE_TRU_COT:
        trang_thai, ly_do = "✓", "Video TRỤ CỘT — gánh view của kênh"
    elif views < med * TY_LE_TRUC_THAP:
        trang_thai, ly_do = "⚠", "Video ĐUÔI — ít view so mặt bằng kênh"
    else:
        trang_thai, ly_do = "✓", "Video quanh mặt bằng view của kênh"

    if rr is not None and rr_bl is not None:
        if rr >= rr_bl:
            ly_do += " — kéo được khán giả quay lại (tích lũy tài sản kênh)"
        else:
            ly_do += " — chủ yếu người xem mới (view vãng lai, ít tích lũy)"
            if trang_thai == "✓" and views < med * TY_LE_TRU_COT:
                trang_thai = "⚠"
    return _trang(trang_thai, ly_do, so_lieu)


def cham_truc_cong_thuc(video: dict, bl3: dict, nhan_do_dai: str, nhan_tuoi: str) -> dict:
    """Trục CÔNG THỨC: format độ dài này có thuộc nhóm THẮNG của kênh không? So median
    nhóm độ dài (retention/watchtime/rpm) với toàn kênh. Nhóm thiếu mẫu → '?' (không đoán)."""
    toan = bl3.get("toan_kenh") or {}
    nhom = (bl3.get("theo_do_dai") or {}).get(nhan_do_dai)
    so_lieu = {"nhom_do_dai": nhan_do_dai, "nhom_tuoi": nhan_tuoi}
    if nhom is None:
        return _trang("?", f"Nhóm độ dài '{nhan_do_dai}' thiếu mẫu — chưa kết luận công thức",
                      so_lieu)

    thang = tong = 0
    for bien in ("retention", "watchtime", "rpm"):
        g, k = nhom.get(bien), toan.get(bien)
        if g is not None and k not in (None, 0):
            tong += 1
            so_lieu[f"{bien}_nhom_vs_kenh"] = round(g / k, 2)
            thang += g >= k
    if tong == 0:
        return _trang("?", "Thiếu số liệu so sánh nhóm vs kênh", so_lieu)
    if thang >= 2:
        return _trang("✓", f"Format độ dài '{nhan_do_dai}' thuộc nhóm THẮNG — nên lặp lại", so_lieu)
    if thang == 0:
        return _trang("⚠", f"Format độ dài '{nhan_do_dai}' dưới mặt bằng kênh — cân nhắc đổi", so_lieu)
    return _trang("✓", f"Format độ dài '{nhan_do_dai}' quanh mặt bằng kênh", so_lieu)


def chan_doan(df: pd.DataFrame, bang_luat: list[dict] | None = None,
              anh_xa: list[dict] | None = None) -> dict:
    """Chẩn đoán DÒNG CUỐI (tương thích ngược: dữ liệu time-series/mock cũ).

    Nếu là report YouTube Studio → tự chuyển sang chẩn đoán VIDEO ĐẦU TIÊN so baseline kênh.
    Áp ánh xạ cột trước để hiểu report thật; nếu df đã dùng tên biến luật thì ánh xạ vô hại.
    """
    if bang_luat is None:
        bang_luat = doc_bang_luat()

    dong_total, _ = tach_total_va_video(df)
    if dong_total is not None:
        # Report YouTube thật → mặc định chẩn đoán video đầu bảng (thường mới/đáng chú ý nhất)
        return chan_doan_video(df, 0, bang_luat=bang_luat, anh_xa=anh_xa)

    # Đường cũ: dữ liệu không phải report YouTube (mock/time-series) — dòng cuối = mới nhất
    df2 = ap_anh_xa_cot(df, anh_xa)
    so = df2.select_dtypes("number")
    if so.empty:
        raise ValueError("Báo cáo không có cột số liệu nào")

    hien_tai = _sach(so.iloc[-1].to_dict())
    baselines = _tinh_baseline(so)
    canh_bao = None
    if len(so) < MIN_DONG_BASELINE:
        canh_bao = (f"Chưa đủ dữ liệu baseline (có {len(so)} dòng, nên có ≥ "
                    f"{MIN_DONG_BASELINE}) — kết quả chỉ mang tính tham khảo.")

    matched, tang_vo = _cham_luat(hien_tai, baselines, bang_luat)
    return {
        "che_do": "dong_cuoi",
        "tang_vo": tang_vo,
        "matched": matched,
        "metrics": hien_tai,
        "baselines": baselines,
        "canh_bao_baseline": canh_bao,
    }


def chan_doan_video(df: pd.DataFrame, chi_muc: int = 0, bang_luat: list[dict] | None = None,
                    anh_xa: list[dict] | None = None) -> dict:
    """Chẩn đoán 1 VIDEO (theo chỉ mục trong bảng video, đã bỏ dòng Total) so baseline kênh.

    baseline = trung vị TẤT CẢ video của kênh (bỏ dòng Total — Total không phải 1 video để so).
    """
    if bang_luat is None:
        bang_luat = doc_bang_luat()

    _, df_video = tach_total_va_video(df)
    df_map = ap_anh_xa_cot(df_video, anh_xa)
    so = df_map.select_dtypes("number")
    if so.empty:
        raise ValueError("Báo cáo không có cột số liệu nào (sau khi ánh xạ cột)")
    if not (0 <= chi_muc < len(so)):
        raise IndexError(f"Chỉ mục video {chi_muc} ngoài phạm vi (có {len(so)} video)")

    hien_tai = _sach(so.iloc[chi_muc].to_dict())
    nhom_do_dai, nhom_tuoi = phan_nhom_do_dai(df_map), phan_nhom_tuoi(df_map)
    bl3 = tinh_baseline_3_lop(so, nhom_do_dai, nhom_tuoi)
    # 08/08 (analytic_methodology.md §12.1): so ĐÚNG NHÓM ĐỘ DÀI thay vì baseline toàn kênh
    # phẳng — dùng lại chon_baseline() đã viết cho GĐ3 (bốn trục), nguyên tắc lùi y hệt mục 4.
    # Không đổi bộ 20 luật/ngưỡng — chỉ đổi baseline nào được đưa vào chấm.
    nhan_do_dai_video, nhan_tuoi_video = nhom_do_dai.iloc[chi_muc], nhom_tuoi.iloc[chi_muc]
    baselines, nguon_baseline = {}, {}
    for bien in bl3["toan_kenh"]:
        gia_tri, nguon = chon_baseline(bien, nhan_do_dai_video, nhan_tuoi_video, "format", bl3)
        if gia_tri is not None:
            baselines[bien] = gia_tri
            nguon_baseline[bien] = nguon
    canh_bao = None
    if len(so) < MIN_DONG_BASELINE:
        canh_bao = (f"Kênh mới có {len(so)} video — baseline chưa đủ tin cậy "
                    f"(nên có ≥ {MIN_DONG_BASELINE}). Kết quả chỉ mang tính tham khảo.")

    # Van chống bịa (methodology §8, "luật nền của toàn engine") — trước bản vá này, đường
    # 20-luật/LLM ("Analyze" video) là đường DUY NHẤT trong file không gọi du_mau_ket_luan,
    # nên video vài chục view và video hàng chục nghìn view có thể khớp CÙNG một luật (tỷ lệ
    # retention/CTR không tự phản ánh quy mô) → LLM viết ra cùng một "hành động cần làm". Đường
    # 4-trục (cham_truc_noi_dung) đã đúng từ trước; giờ gate y hệt ở đây trước khi chấm luật.
    du_du_lieu = du_mau_ket_luan(hien_tai.get("views"), bl3["toan_kenh"].get("views"))
    if du_du_lieu:
        matched, tang_vo = _cham_luat(hien_tai, baselines, bang_luat)
    else:
        matched, tang_vo = [], None

    # Nhãn video để hiển thị (nếu có cột tiêu đề)
    tieu_de = None
    for ten in ("video_title", "content"):
        if ten in df_map.columns:
            val = df_map.iloc[chi_muc][ten]
            if pd.notna(val):
                tieu_de = str(val)
                break

    return {
        "che_do": "video",
        "chi_muc": chi_muc,
        "video_title": tieu_de,
        "so_video": len(so),
        "tang_vo": tang_vo,
        "matched": matched,
        "du_du_lieu": du_du_lieu,   # False → views quá thấp để kết luận, matched luôn [] (§8)
        "metrics": hien_tai,
        "baselines": baselines,
        "nguon_baseline": nguon_baseline,   # 08/08: minh bạch baseline mỗi biến đang so nhóm nào
        "baseline_3_lop": bl3,   # Giai đoạn 2: cho giai đoạn sau (4 trục) dùng; 20 luật cũ không đụng
        "canh_bao_baseline": canh_bao,
    }


def liet_ke_video(df: pd.DataFrame) -> list[dict]:
    """Danh sách video để user chọn chẩn đoán: [{chi_muc, tieu_de, views}]."""
    _, df_video = tach_total_va_video(df)
    df_map = ap_anh_xa_cot(df_video, anh_xa=None)
    ra = []
    for i in range(len(df_map)):
        tieu_de = None
        for ten in ("video_title", "content"):
            if ten in df_map.columns and pd.notna(df_map.iloc[i][ten]):
                tieu_de = str(df_map.iloc[i][ten])
                break
        views = df_map.iloc[i]["views"] if "views" in df_map.columns else None
        ra.append({"chi_muc": i, "tieu_de": tieu_de,
                   "views": float(views) if pd.notna(views) else None})
    return ra


def chan_doan_kenh(df: pd.DataFrame, bang_luat: list[dict] | None = None,
                   anh_xa: list[dict] | None = None) -> dict:
    """Chẩn đoán CẢ KÊNH: dòng Total so với baseline = trung vị các video của chính kênh.

    Đây là 'sức khỏe tổng': tổng kênh đang lệch gì so với mặt bằng video của kênh.
    (Xu hướng theo NGÀY dùng Chart/Totals data — mốc sau; mốc này so Total vs mặt bằng video.)
    """
    if bang_luat is None:
        bang_luat = doc_bang_luat()

    dong_total, df_video = tach_total_va_video(df)
    if dong_total is None:
        raise ValueError("Báo cáo không có dòng Total — không phải report YouTube Studio tổng kênh")

    df_total_map = ap_anh_xa_cot(dong_total.to_frame().T, anh_xa)
    df_video_map = ap_anh_xa_cot(df_video, anh_xa)

    so_video = df_video_map.select_dtypes("number")
    hien_tai = _sach(df_total_map.select_dtypes("number").iloc[0].to_dict())
    # Baseline 3 lớp (Giai đoạn 2). Total chấm với nhánh toan_kenh = baseline cũ → không đổi kết quả.
    bl3 = tinh_baseline_3_lop(so_video, phan_nhom_do_dai(df_video_map),
                              phan_nhom_tuoi(df_video_map))
    baselines = bl3["toan_kenh"]
    canh_bao = None
    if len(df_video_map) < MIN_DONG_BASELINE:
        canh_bao = (f"Kênh mới có {len(df_video_map)} video — baseline chưa đủ tin cậy.")

    matched, tang_vo = _cham_luat(hien_tai, baselines, bang_luat)
    return {
        "che_do": "kenh",
        "so_video": len(df_video_map),
        "tang_vo": tang_vo,
        "matched": matched,
        "metrics": hien_tai,
        "baselines": baselines,
        "baseline_3_lop": bl3,   # Giai đoạn 2: cho giai đoạn sau; 20 luật cũ không đụng
        "canh_bao_baseline": canh_bao,
    }


# ═══ Giai đoạn 4 — TỔNG HỢP 4 TRỤC → 1 PHÁN QUYẾT + CHẨN ĐOÁN TOÀN BỘ CẤP KÊNH ═══

def tong_hop_phan_quyet(noi_dung: dict, tien: dict, danh_muc: dict, cong_thuc: dict) -> dict:
    """Đọc 4 trạng thái trục (GĐ3) → kết luận ĐÚNG MỘT phán quyết trong PHAN_QUYET.
    KHÔNG gọi LLM. Bảng quyết định theo THỨ TỰ ƯU TIÊN (không phải bảng CSV vì đây là
    ladder ưu tiên có điều kiện chéo trục + đếm đa số — CSV sẽ thành hộp đen khó đọc hơn;
    tập phán quyết hữu hạn PHAN_QUYET mới là cái giữ 'luật ngoài code' đúng tinh thần)."""
    tt_nd = noi_dung["trang_thai"]
    tt_ti, tt_dm, tt_ct = tien["trang_thai"], danh_muc["trang_thai"], cong_thuc["trang_thai"]
    benh = noi_dung.get("so_lieu", {}).get("benh")
    the_diem = {"noi_dung": tt_nd, "tien": tt_ti, "danh_muc": tt_dm, "cong_thuc": tt_ct}
    baseline_da_dung = {
        "noi_dung": noi_dung.get("so_lieu", {}).get("nguon_baseline"),
        "cong_thuc": f"nhóm độ dài '{cong_thuc.get('so_lieu', {}).get('nhom_do_dai')}'",
    }
    # tien '⚠' CHÍNH LÀ RPM đáy (trục tiền chỉ trả ⚠ cho đúng ca RPM đáy — xem cham_truc_tien)
    tien_rpm_day = tt_ti == "⚠"
    # KÊNH CHƯA MONETIZE: trục Tiền '?' kèm nhãn 'chua_monetize' → trục Tiền TẠM KHÔNG có tiếng
    # nói (chưa có tiền để xét), coi như trung lập — không kéo xuống phán quyết tiêu cực về tiền.
    tien_chua_monetize = (tt_ti == "?"
                          and tien.get("so_lieu", {}).get("nhan") == "chua_monetize")
    # 'không đạt' của 3 trục ngoài nội dung = ✗ hoặc ⚠ ('?' là chưa biết, KHÔNG tính là hỏng)
    so_khong_dat_khac = sum(1 for t in (tt_ti, tt_dm, tt_ct) if t in ("✗", "⚠"))

    def ra(pq, ket_luan):
        gt = (f"Nội dung {tt_nd}, tiền {tt_ti}, danh mục {tt_dm}, công thức {tt_ct} — {ket_luan}")
        return {"phan_quyet": pq, "giai_thich": gt,
                "the_diem": the_diem, "baseline_da_dung": baseline_da_dung}

    # 1) VAN CHỐNG BỊA cao nhất: mẫu quá nhỏ (nội dung '?') → không đoán, dừng ngay.
    if tt_nd == "?":
        return ra("chua_du_du_lieu",
                  "chưa đủ view để kết luận, không phán quyết khi mẫu quá nhỏ.")
    # 2) Cả 4 trục đạt → công thức thắng, NÊN LÀM THÊM. Kênh CHƯA MONETIZE → trục Tiền tạm trung
    #    lập (không có tiền để xét), xét nhân bản trên 3 trục còn lại — Tiền coi như 'không cản'.
    if tt_nd == "✓" and tt_dm == "✓" and tt_ct == "✓" and (tt_ti == "✓" or tien_chua_monetize):
        return ra("nhan_ban",
                  ("nội dung/danh mục/công thức đều đạt, kênh chưa bật kiếm tiền nên tạm chưa xét "
                   "doanh thu — vẫn là công thức thắng, nên nhân bản format này." if tien_chua_monetize
                   else "cả bốn góc đều đạt, đây là công thức thắng — nên nhân bản format này."))
    # 3) Nội dung GIỎI (bao bì + giữ chân đều tốt) nhưng RPM đáy → ĐỔI NGÁCH VÌ TIỀN.
    #    Ví dụ then chốt của phương pháp (methodology dòng 135). Dùng benh='khoe' làm cổng
    #    'nội dung đạt' để vẫn bắt được cả khi AVD hạ trạng thái xuống ⚠ (chỉ là gợi ý độ dài).
    #    CHƯA MONETIZE thì KHÔNG vào đây: chưa có tiền thì không có cơ sở nói 'rẻ tiền'
    #    (tien_rpm_day chỉ True khi tien '⚠', mà chua_monetize là '?' → đã loại; guard cho rõ ý).
    if benh == "khoe" and tien_rpm_day and not tien_chua_monetize:
        return ra("doi_ngach_vi_tien",
                  "bao bì và giữ chân tốt nhưng RPM đáy — video giỏi kéo view nhưng rẻ tiền, "
                  "đừng nhân bản format này cho mục tiêu doanh thu.")
    # 4) CTR hỏng nhưng Retention còn ổn → chỉ cần SỬA BAO BÌ (thumbnail/tiêu đề).
    if benh == "bao_bi_yeu":
        return ra("sua_bao_bi",
                  "giữ chân ổn nhưng CTR yếu — sửa thumbnail/tiêu đề, nội dung không cần đụng.")
    # 5) Retention hỏng (giật tít hoặc lê thê) → SỬA NỘI DUNG (gốc bệnh nằm ở nội dung).
    if benh in ("giat_tit", "le_the"):
        return ra("sua_noi_dung",
                  "giữ chân hỏng (giật tít / lê thê) — bệnh ở nội dung, sửa cấu trúc/lời hứa.")
    # 6) Nội dung chỉ tàm tạm (⚠, KHÔNG phải 'khoe') VÀ phần lớn trục còn lại cũng hỏng → BỎ.
    if tt_nd == "⚠" and benh != "khoe" and so_khong_dat_khac >= 2:
        return ra("bo",
                  "nội dung tàm tạm và phần lớn các góc còn lại đều hỏng — khai tử, thôi đổ công suất.")
    # 7) Còn lại: có điểm chưa tối ưu nhưng chưa tới mức phải sửa/bỏ → GIỮ.
    return ra("giu", "ổn nhưng chưa nổi bật, chưa có góc nào hỏng đủ nặng — giữ nguyên, theo dõi.")


def _tong_quan_danh_muc(so: pd.DataFrame, nhan_do_dai: pd.Series, bl3: dict) -> dict:
    """Bức tranh DANH MỤC cấp kênh (tầng 2 methodology) — Studio không cho sẵn:
    tập trung view (top1/top3 trên tổng), new/returning trung bình, nhóm độ dài thắng nhất."""
    views = pd.to_numeric(so.get("views"), errors="coerce").dropna() if "views" in so else pd.Series(dtype=float)
    tong = float(views.sum())
    vsort = views.sort_values(ascending=False)
    top1 = float(vsort.iloc[0]) / tong if tong > 0 and len(vsort) >= 1 else None
    top3 = float(vsort.iloc[:3].sum()) / tong if tong > 0 and len(vsort) >= 1 else None

    rr = pd.to_numeric(so.get("returning_ratio"), errors="coerce").dropna() if "returning_ratio" in so else pd.Series(dtype=float)
    returning_tb = float(rr.mean()) if len(rr) else None
    new_tb = 1 - returning_tb if returning_tb is not None else None

    # Nhóm độ dài thắng nhất: nhóm có nhiều chỉ số (retention/watchtime/rpm) vượt median kênh nhất.
    toan = bl3.get("toan_kenh") or {}
    diem_nhom, nhom_thang = {}, None
    for g, med_nhom in (bl3.get("theo_do_dai") or {}).items():
        if not med_nhom:
            continue
        diem = sum(1 for b in ("retention", "watchtime", "rpm")
                   if med_nhom.get(b) is not None and toan.get(b) not in (None, 0)
                   and med_nhom[b] >= toan[b])
        diem_nhom[g] = diem
    if diem_nhom:
        nhom_thang = max(diem_nhom, key=diem_nhom.get)

    return {
        "so_video": int(len(so)),
        "tap_trung_top1": top1,        # 1 video gánh bao nhiêu % view kênh
        "tap_trung_top3": top3,
        "returning_ratio_tb": returning_tb,
        "new_ratio_tb": new_tb,
        "nhom_do_dai_thang": nhom_thang,
        "diem_nhom_do_dai": diem_nhom,
    }


# ═══ 08/08 — TƯƠNG QUAN + XU HƯỚNG THEO THÁNG (analytic_methodology.md §12.2, §12.3) ═══
# Thuần thống kê Python (pandas .corr(), groupby theo tháng) — KHÔNG gọi model. Mở rộng phần
# MÁY TÍNH để tầng diễn giải có số liệu giàu hơn (nối các cột lại với nhau — mục 1), không
# phá ranh giới "máy tính, LLM chỉ diễn giải" của mục 5. Cả hai đều áp van chống bịa mẫu nhỏ
# (mục 8): dưới ngưỡng thì BỎ QUA, không suy diễn từ vài điểm.

CAP_TUONG_QUAN = [("duration_min", "retention"), ("duration_min", "avd"), ("ctr", "retention")]
NGUONG_MAU_TUONG_QUAN = 8   # dưới ngưỡng này, hệ số tương quan không đáng tin


def tinh_tuong_quan(so: pd.DataFrame) -> list[dict]:
    """Hệ số tương quan Pearson cho các cặp biến QUAN TRỌNG (CAP_TUONG_QUAN) — chỉ tính khi
    cả hai cột có mặt và đủ mẫu CHUNG (mục 8). Trả [{bien_1, bien_2, he_so, so_mau}], bỏ qua
    cặp thiếu cột/thiếu mẫu. Không kết luận chiều/độ mạnh — đó là việc của tầng diễn giải."""
    ket = []
    for b1, b2 in CAP_TUONG_QUAN:
        if b1 not in so.columns or b2 not in so.columns:
            continue
        cap = so[[b1, b2]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(cap) < NGUONG_MAU_TUONG_QUAN:
            continue
        he_so = cap[b1].corr(cap[b2])
        if pd.isna(he_so):
            continue
        ket.append({"bien_1": b1, "bien_2": b2, "he_so": round(float(he_so), 2),
                   "so_mau": int(len(cap))})
    return ket


NGUONG_MAU_THANG = 3     # ít nhất N video/tháng thì trung vị tháng đó mới đáng tin
SO_THANG_TOI_THIEU = 3   # cần >= N điểm-tháng đủ mẫu mới dám nói "xu hướng"
# 29/08: thêm views/avd/ctr — chế độ chỉ-số cần ĐÚNG 3 biến này để nói "mức tăng
# trưởng"; retention/duration/rpm giữ nguyên cho báo cáo 9 mục đang dùng.
BIEN_XU_HUONG = ("views", "avd", "ctr", "retention", "duration_min", "rpm")


def xu_huong_theo_thang(df_map: pd.DataFrame) -> dict | None:
    """Trung vị mỗi biến trong BIEN_XU_HUONG theo THÁNG ĐĂNG (video_publish_time, KHÁC ngay_chay
    — đó là ngày chạy report, một giá trị cho cả report, không cho biết video nào đăng tháng
    nào). Chỉ trả về biến có >= SO_THANG_TOI_THIEU tháng, mỗi tháng >= NGUONG_MAU_THANG video
    (mục 8 — không suy xu hướng từ 1-2 điểm). Trả {bien: [{thang, trung_vi, so_video}, ...]}
    (thứ tự thời gian tăng dần); None nếu thiếu cột hoặc không biến nào đủ điều kiện."""
    if "video_publish_time" not in df_map.columns:
        return None
    ngay_dang = pd.to_datetime(df_map["video_publish_time"], format="%b %d, %Y", errors="coerce")
    thang = ngay_dang.dt.to_period("M")

    ket = {}
    for bien in BIEN_XU_HUONG:
        if bien not in df_map.columns:
            continue
        gia_tri = pd.to_numeric(df_map[bien], errors="coerce")
        khung = pd.DataFrame({"thang": thang, "gia_tri": gia_tri}).dropna()
        nhom = khung.groupby("thang")["gia_tri"].agg(["median", "count"])
        nhom = nhom[nhom["count"] >= NGUONG_MAU_THANG].sort_index()
        if len(nhom) < SO_THANG_TOI_THIEU:
            continue
        ket[bien] = [{"thang": str(t), "trung_vi": round(float(r["median"]), 4),
                     "so_video": int(r["count"])} for t, r in nhom.iterrows()]
    return ket or None


# ═══ Đợt 0 — KHUNG BÁO CÁO KÊNH 9 MỤC CỐ ĐỊNH (methodology mục 3 + 10) ═══
# Báo cáo kênh LUÔN liệt kê đủ 9 phương pháp (A1..C3), mỗi mục TỰ KHAI 1 trong 3 trạng thái
# (suy từ DỮ LIỆU, không bắt user khai): co_ket_qua (đủ cột + đủ mẫu → kết quả thật, kèm số video
# căn cứ) / chua_co_so_lieu (report THIẾU HẲN cột cần — không có gì để tìm, vd kênh chưa monetize)
# / chua_du_de_phan_tich (CÓ cột nhưng mẫu quá nhỏ HOẶC logic sẽ bổ sung ở đợt sau). Phân biệt 2
# trạng thái sau là BẮT BUỘC. 3 mục đã có logic (A1 Pareto, C2 phễu tiền, C3 đòn bẩy) đổ kết quả
# thật; 6 mục còn lại nền khung cho các đợt bổ sung sau.
TRANG_THAI_9 = ("co_ket_qua", "chua_co_so_lieu", "chua_du_de_phan_tich")
TEN_MUC_9 = [
    ("A1", "Định luật tập trung (Pareto)"),
    ("A2", "Đường cong tuổi thọ video (velocity)"),
    ("A3", "Cấu trúc khán giả (New/Returning cấp kênh)"),
    ("B1", "Độ dài video vs hiệu quả"),
    ("B2", "Thời điểm đăng"),
    ("B3", "Ma trận CTR × Retention (bệnh phổ biến của kênh)"),
    ("C1", "Bản đồ RPM/CPM theo format"),
    ("C2", "Rò rỉ chuyển đổi phễu tiền"),
    ("C3", "Đòn bẩy tăng trưởng bỏ trống (end screen/card)"),
]
_TEN_MUC_9 = dict(TEN_MUC_9)


def _muc9(ma: str, trang_thai: str, noi_dung=None, so_video=None, ghi_chu=None,
          chieu_phu=None, ma_tran=None) -> dict:
    return {"ma": ma, "ten": _TEN_MUC_9[ma], "trang_thai": trang_thai,
            "noi_dung": noi_dung, "so_video": so_video, "ghi_chu": ghi_chu,
            "chieu_phu": chieu_phu,   # chiều con Winning Format (giờ, từ khóa) của B2
            "ma_tran": ma_tran}       # 4 ô ma trận CTR×Retention của B3 (để UI vẽ lưới)


# ═══ Đợt 1 — WINNING FORMAT cấp kênh (methodology mục 3B + 11): độ dài / thứ / giờ / từ khóa ═══
# THỐNG KÊ THUẦN (không LLM). Van chống bịa: chỉ kết luận khi nhóm đủ MIN_DONG_NHOM video, luôn
# kèm số mẫu; thiếu cột → chua_co_so_lieu, đủ cột nhưng mẫu nhỏ → chua_du_de_phan_tich.
_THU_VN = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
# Từ chức năng (VN + EN) loại khi đếm từ khóa tiêu đề — tránh nhiễu 'the/của/and…'.
_STOPWORDS = frozenset(unicodedata.normalize("NFC", w) for w in """
the a an of to in for and or is are on with that this you your my his her it its as at by be
what why how when who which từ và của cho là các những một có được trong để người này đã thì với
khi ra vào lên khỏi nhất như về trên dưới sau trước bằng nếu thì mà nên vẫn còn đang sẽ bị làm
i we they he she it do does did no not - & |
""".split())


def _wf(trang_thai, noi_dung=None, so_video=None, ghi_chu=None) -> dict:
    return {"trang_thai": trang_thai, "noi_dung": noi_dung, "so_video": so_video, "ghi_chu": ghi_chu}


def _cot_publish(df_map: pd.DataFrame):
    """Series datetime từ cột thời gian xuất bản (EN/VN) — None nếu không có / không parse được."""
    col = next((c for c in df_map.columns if _chuan_hoa_ten(c) in _VELO_PUB), None)
    if col is None:
        return None
    s = pd.to_datetime(df_map[col], errors="coerce")   # infer; "Mar 25, 2026" parse được
    return s if s.notna().any() else None


def _phut_giay(giay: float) -> str:
    """Đổi giây → chuỗi 'X phút Y giây' (bỏ giây khi = 0; < 1 phút → 'Y giây'). Dùng hiển thị
    độ dài video CỤ THỂ để user biết chính xác nên làm dài bao nhiêu."""
    tong = int(round(giay))
    p, g = divmod(tong, 60)
    if p == 0:
        return f"{g} giây"
    return f"{p} phút {g} giây" if g else f"{p} phút"


def _khoang_phut_nhom(nhom: str) -> str:
    """Khoảng phút của một nhóm độ dài, LẤY TỪ HẰNG NGƯỠNG (đổi hằng → câu chữ tự đổi theo,
    không viết số cứng): ngắn < DO_DAI_NGAN_PHUT; vừa [NGAN, DAI]; dài > DO_DAI_DAI_PHUT."""
    n, d = DO_DAI_NGAN_PHUT, DO_DAI_DAI_PHUT
    return {"ngắn": f"dưới {n:g} phút", "vừa": f"{n:g}–{d:g} phút",
            "dài": f"trên {d:g} phút"}.get(nhom, nhom)


def _do_dai_giay(so: pd.DataFrame, mask) -> pd.Series | None:
    """Độ dài (GIÂY) các video được mask chọn — ưu tiên duration_sec (chính xác), lùi
    duration_min×60. None nếu không có cột độ dài (van chống bịa: không có thì không hiện)."""
    if "duration_sec" in so.columns:
        s = pd.to_numeric(so.loc[mask, "duration_sec"], errors="coerce")
    elif "duration_min" in so.columns:
        s = pd.to_numeric(so.loc[mask, "duration_min"], errors="coerce") * 60
    else:
        return None
    s = s.dropna()
    return s if len(s) else None


def _wf_do_dai(so: pd.DataFrame, views, ndd) -> dict:
    """Chiều 1: nhóm độ dài (ngắn/vừa/dài) nào cho view trung vị cao nhất — chỉ nhóm ĐỦ mẫu.
    HIỆN MỐC PHÚT cụ thể: mỗi nhóm kèm khoảng phút (từ hằng ngưỡng); nhóm thắng kèm ĐỘ DÀI THẬT
    (trung vị + min–max phút giây từ cột duration) để user biết chính xác nên làm video dài bao nhiêu."""
    if views is None:
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột Lượt xem")
    if not ndd.isin(["ngắn", "vừa", "dài"]).any():
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột Độ dài (Duration)")
    ket = {}
    for g in ("ngắn", "vừa", "dài"):
        mask = (ndd == g) & views.notna()
        cnt = int(mask.sum())
        if cnt >= MIN_DONG_NHOM:
            ket[g] = (cnt, float(views[mask].median()), mask)
    if not ket:
        return _wf("chua_du_de_phan_tich",
                   ghi_chu=f"chưa nhóm độ dài nào đủ {MIN_DONG_NHOM} video để so")
    best = max(ket, key=lambda g: ket[g][1])
    cnt, medv, mask = ket[best]
    nd = (f"Nhóm '{best}' ({_khoang_phut_nhom(best)}) cho nhiều view nhất — "
          f"trung vị {medv:,.0f} view/video")
    if "retention" in so.columns:
        ret = pd.to_numeric(so.loc[mask, "retention"], errors="coerce").median()
        if pd.notna(ret):
            nd += f", retention trung vị {ret*100:.0f}%"
    # ĐỘ DÀI THẬT của nhóm thắng: trung vị + biên min–max (phút giây) từ cột duration
    giay = _do_dai_giay(so, mask)
    if giay is not None:
        nd += (f". Video nhóm thắng dài {_phut_giay(giay.min())}–{_phut_giay(giay.max())}, "
               f"tập trung quanh trung vị {_phut_giay(giay.median())} → nhắm độ dài này")
    # So sánh các nhóm ĐỦ MẪU (mỗi nhóm kèm KHOẢNG PHÚT từ hằng ngưỡng)
    nd += ". So nhóm: " + "; ".join(f"{g} ({_khoang_phut_nhom(g)}) {ket[g][1]:,.0f} view"
                                    for g in ("ngắn", "vừa", "dài") if g in ket)
    return _wf("co_ket_qua", noi_dung=nd, so_video=cnt)


def _wf_thu(views, pub) -> dict:
    """Chiều 2: thứ trong tuần cho view khởi đầu tốt nhất — chỉ thứ ĐỦ mẫu (không may rủi)."""
    if views is None:
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột Lượt xem")
    if pub is None:
        return _wf("chua_co_so_lieu", ghi_chu="report không có/không đọc được cột Thời gian xuất bản")
    thu = pub.dt.dayofweek
    ket = {}
    for d in range(7):
        mask = (thu == d) & views.notna()
        cnt = int(mask.sum())
        if cnt >= MIN_DONG_NHOM:
            ket[d] = (cnt, float(views[mask].median()))
    if not ket:
        return _wf("chua_du_de_phan_tich",
                   ghi_chu=f"chưa thứ nào đủ {MIN_DONG_NHOM} video để kết luận (không suy từ may rủi)")
    best = max(ket, key=lambda d: ket[d][1])
    cnt, medv = ket[best]
    return _wf("co_ket_qua",
               noi_dung=f"Đăng {_THU_VN[best]} cho view khởi đầu tốt nhất — trung vị {medv:,.0f} view",
               so_video=cnt)


def _wf_gio(views, pub) -> dict:
    """Chiều 3: khung giờ đăng — CHỈ khi report thật sự có GIỜ (không bịa khung giờ từ ngày trơ)."""
    if views is None:
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột Lượt xem")
    if pub is None:
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột Thời gian xuất bản")
    gio = pub.dt.hour
    # NaT → NaN; fillna(0) để dòng không parse KHÔNG bị coi là 'có giờ' (NaN != 0 vốn = True).
    if not ((gio.fillna(0) != 0) | (pub.dt.minute.fillna(0) != 0)).any():   # toàn 00:00 = chỉ có NGÀY
        return _wf("chua_co_so_lieu", ghi_chu="report không kèm GIỜ đăng (chỉ có ngày) — không suy khung giờ")
    def khung(h):
        return "sáng" if 5 <= h <= 11 else "chiều" if 12 <= h <= 17 else "tối" if 18 <= h <= 22 else "đêm"
    nhan = gio.map(khung)
    ket = {}
    for k in ("sáng", "chiều", "tối", "đêm"):
        mask = (nhan == k) & views.notna()
        cnt = int(mask.sum())
        if cnt >= MIN_DONG_NHOM:
            ket[k] = (cnt, float(views[mask].median()))
    if not ket:
        return _wf("chua_du_de_phan_tich", ghi_chu=f"chưa khung giờ nào đủ {MIN_DONG_NHOM} video")
    best = max(ket, key=lambda k: ket[k][1])
    cnt, medv = ket[best]
    return _wf("co_ket_qua",
               noi_dung=f"Đăng buổi {best} cho view tốt nhất — trung vị {medv:,.0f} view", so_video=cnt)


def _tach_tu(tieu_de) -> set:
    """Tách tiêu đề thành TẬP từ (đã bỏ dấu câu, chữ thường, bỏ stopword + từ < 3 ký tự + số)."""
    tu = re.findall(r"[0-9A-Za-zÀ-ỹ]+", unicodedata.normalize("NFC", str(tieu_de).lower()))
    return {t for t in tu if len(t) >= 3 and not t.isdigit() and t not in _STOPWORDS}


def _tu_khoa_theo_bien(df_map: pd.DataFrame, gia_tri, cot_tieu_de: str, nguong_dem: int = 2,
                       nhom_nghia: dict | None = None):
    """Chia video theo BIẾN gia_tri (trên/dưới trung vị), đếm từ khóa tiêu đề nổi bật hẳn ở nhóm
    trên trung vị so với phần còn lại (§12.4 bước 1: tổng quát hóa biến chia nhóm — trước đây
    hard-code views). Trả (danh_sách_từ_nổi_bật KHÔNG cắt bớt — sắp theo rate giảm dần, n_thang)
    hoặc None nếu thiếu mẫu; nguong_dem = số video tối thiểu chứa từ ở nhóm thắng (mặc định 2,
    bước 3 dùng NGUONG_DEM_MAU_THUAN chặt hơn vì đó là tuyên bố mạnh hơn 'nổi bật' thường).
    nhom_nghia (§12.4(b)): {từ: tên_nhóm} — từ có trong bảng được ĐẾM GỘP theo tên nhóm thay vì
    đếm riêng; None → tự nạp qua _tai_nhom_nghia() (rỗng nếu chưa soạn file → hành vi cũ)."""
    if gia_tri is None:
        return None
    if nhom_nghia is None:
        nhom_nghia = _tai_nhom_nghia()
    hop_le = gia_tri.notna()
    med = gia_tri[hop_le].median()
    thang = hop_le & (gia_tri > med)
    n_thang = int(thang.sum())
    if n_thang < MIN_DONG_NHOM:
        return None
    tieu = df_map[cot_tieu_de]
    dem_thang, dem_con = {}, {}
    for i in df_map.index:
        if not hop_le.get(i, False):
            continue
        for t in _tach_tu(tieu.get(i)):
            t = nhom_nghia.get(t, t)
            (dem_thang if thang.get(i, False) else dem_con)[t] = \
                (dem_thang if thang.get(i, False) else dem_con).get(t, 0) + 1
    n_con = int((hop_le & ~thang).sum()) or 1
    noi_bat = []
    for t, c in dem_thang.items():
        if c < nguong_dem:                           # xuất hiện đủ nhiều ở nhóm thắng (không fluke)
            continue
        rate_w, rate_r = c / n_thang, dem_con.get(t, 0) / n_con
        if rate_w >= 2 * rate_r:                    # nổi bật hẳn ở nhóm thắng
            noi_bat.append((t, rate_w))
    noi_bat.sort(key=lambda x: -x[1])
    return [t for t, _ in noi_bat], n_thang


NGUONG_DEM_MAU_THUAN = 3   # §12.4 bước 3: tuyên bố "mâu thuẫn" mạnh hơn "nổi bật" thường (nguong_dem=2)


def _tu_mau_thuan(df_map: pd.DataFrame, cot_tieu_de: str, tu_noi_bat_a: list, bien_b,
                  nhom_nghia: dict | None = None) -> list:
    """Trong các từ ĐÃ nổi bật ở biến A (tu_noi_bat_a — danh sách đã hiển thị, không quét lại
    toàn bộ từ vựng nên không phải multiple-testing mới), tìm từ nào CŨNG nổi bật ở nhóm THẤP
    của biến B — lật nhóm thắng/thua bằng cách đảo dấu (-bien_b) rồi tái dùng đúng logic đếm
    của _tu_khoa_theo_bien, đòi NGUONG_DEM_MAU_THUAN (bằng chứng số thật ở phía 'thấp', không
    suy từ việc từ đó vắng mặt trong danh sách nổi bật phía kia — đúng tự phản biện §12.4)."""
    if not tu_noi_bat_a or bien_b is None:
        return []
    ket = _tu_khoa_theo_bien(df_map, -bien_b, cot_tieu_de, nguong_dem=NGUONG_DEM_MAU_THUAN,
                             nhom_nghia=nhom_nghia)
    if not ket:
        return []
    tu_thap_set = {t for t in ket[0]}
    return [t for t in tu_noi_bat_a if t in tu_thap_set]


def _wf_tu_khoa(df_map: pd.DataFrame, views, retention=None, rpm=None) -> dict:
    """Chiều 4: từ khóa tiêu đề nổi bật ở nhóm THẮNG (trên trung vị) — tính RIÊNG theo LƯỢT XEM
    (độ phủ), RETENTION (giữ chân) và RPM (tiền, chỉ khi kênh đã monetize), mỗi biến áp đúng
    ngưỡng MIN_DONG_NHOM của chính nó. Thống kê text trên mẫu nhỏ → khiêm tốn: chỉ vài từ + ghi
    rõ 'gợi ý sơ bộ cần kiểm thêm'. §12.4 bước 3 — ĐỐI XỨNG hai chiều đối chiếu view↔retention
    (không chỉ báo tiêu cực một phía, tránh thiên vị loại insight nói ra):
      - ⚠ canh_bao: từ nổi bật ở view-cao MÀ cũng nổi bật ở retention-thấp — "đi cùng" (không
        khẳng định nhân quả) khả năng câu view rẻ.
      - 💡 co_hoi: từ nổi bật ở retention-cao MÀ cũng nổi bật ở view-thấp — nội dung giữ chân
        tốt nhưng độ phủ thấp, đáng thử đổi tiêu đề.
    CHƯA kiểm soát biến gây nhiễu (độ dài/tuổi video) — ghi rõ trong ghi_chu khi có cờ."""
    cot = next((c for c in ("video_title", "content") if c in df_map.columns), None)
    if cot is None or (views is None and retention is None and rpm is None):
        return _wf("chua_co_so_lieu",
                   ghi_chu="report không có cột Tiêu đề video / Lượt xem / Retention / RPM")
    nhom = _tai_nhom_nghia()   # nạp MỘT lần, dùng chung cho mọi lượt đếm bên dưới (§12.4(b))
    ket_view = _tu_khoa_theo_bien(df_map, views, cot, nhom_nghia=nhom)
    ket_ret = _tu_khoa_theo_bien(df_map, retention, cot, nhom_nghia=nhom)
    ket_rpm = _tu_khoa_theo_bien(df_map, rpm, cot, nhom_nghia=nhom)
    doan, n_video_max = [], 0
    for ket, nhan in ((ket_view, "theo lượt xem"), (ket_ret, "theo retention"), (ket_rpm, "theo RPM")):
        if ket and ket[0]:
            tu, n = ket
            doan.append(f"{nhan}: {', '.join(tu[:4])} (n={n})")
            n_video_max = max(n_video_max, n)
    if not doan:
        return _wf("chua_du_de_phan_tich",
                   ghi_chu="chưa thấy từ khóa nổi bật rõ / mẫu nhóm trên trung vị chưa đủ")
    tu_view_top4 = ket_view[0][:4] if ket_view else []
    tu_ret_top4 = ket_ret[0][:4] if ket_ret else []
    canh_bao = _tu_mau_thuan(df_map, cot, tu_view_top4, retention, nhom_nghia=nhom)
    co_hoi = _tu_mau_thuan(df_map, cot, tu_ret_top4, views, nhom_nghia=nhom)
    ghi_chu = None
    if canh_bao:
        doan.append(f"⚠ đi cùng retention thấp: {', '.join(canh_bao)} — có thể đang câu view rẻ")
    if co_hoi:
        doan.append(f"💡 đi cùng lượt xem thấp: {', '.join(co_hoi)} — giữ chân tốt, thử đổi tiêu đề")
    if canh_bao or co_hoi:
        ghi_chu = ("Cờ ⚠/💡 chỉ là từ ĐI CÙNG số liệu (chưa loại trừ do độ dài/tuổi video khác "
                  "nhau giữa các nhóm) — cần đọc kèm bối cảnh, không phải kết luận nhân quả.")
    return _wf("co_ket_qua",
               noi_dung="Từ khóa nổi bật ở nhóm thắng — " + "; ".join(doan)
                        + " — gợi ý sơ bộ, cần kiểm thêm",
               so_video=n_video_max, ghi_chu=ghi_chu)


def goi_y_winning_format(df_map: pd.DataFrame) -> dict:
    """Winning Format cấp kênh — 4 chiều (do_dai / thu / gio / tu_khoa), mỗi chiều {trang_thai,
    noi_dung, so_video, ghi_chu}. Thống kê thuần, van chống bịa (chỉ kết luận khi đủ mẫu)."""
    so = df_map.select_dtypes("number")
    views = pd.to_numeric(so["views"], errors="coerce") if "views" in so.columns else None
    retention = pd.to_numeric(so["retention"], errors="coerce") if "retention" in so.columns else None
    # RPM chỉ tính khi kênh ĐÃ MONETIZE (dùng chung _da_monetize với rpm_theo_format) — kênh chưa
    # bật kiếm tiền thì bỏ qua lặng lẽ, không hiện 'chưa đủ dữ liệu' gây hiểu nhầm là thiếu số liệu.
    rpm = (pd.to_numeric(so["rpm"], errors="coerce")
           if "rpm" in so.columns and _da_monetize(so) else None)
    ndd = phan_nhom_do_dai(df_map)
    pub = _cot_publish(df_map)
    return {"do_dai": _wf_do_dai(so, views, ndd), "thu": _wf_thu(views, pub),
            "gio": _wf_gio(views, pub), "tu_khoa": _wf_tu_khoa(df_map, views, retention, rpm)}


# ═══ Đợt 2 — 3 MẢNH TỔNG HỢP CẤP KÊNH (methodology mục 3: A3 / B3 / C1). Thống kê thuần, ═══
#     tái dùng phan_nhom_do_dai + du_mau_ket_luan + baseline. Van chống bịa: đủ mẫu mới kết luận.

def phan_tich_khan_gia_kenh(df_map: pd.DataFrame) -> dict:
    """A3 — kênh đang XÂY hay ĐỐT lượt xem? Tỷ lệ người xem QUAY LẠI trên tổng ở cấp kênh
    (returning / (new + returning)). Thiếu cột khán giả → chưa có số liệu; ít video → chưa đủ."""
    so = df_map.select_dtypes("number")
    new = pd.to_numeric(so["new_viewers"], errors="coerce") if "new_viewers" in so.columns else None
    ret = pd.to_numeric(so["returning_viewers"], errors="coerce") if "returning_viewers" in so.columns else None
    rr = pd.to_numeric(so["returning_ratio"], errors="coerce") if "returning_ratio" in so.columns else None
    co_nr = new is not None and ret is not None and (new.notna() & ret.notna()).any()
    co_rr = rr is not None and rr.notna().any()
    if not co_nr and not co_rr:
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột New/Returning viewers")
    if co_nr:                                           # ưu tiên sum new+returning (có trọng số)
        hop = new.notna() & ret.notna()
        n = int(hop.sum())
        tong = float((new[hop] + ret[hop]).sum())
        ty_le = float(ret[hop].sum()) / tong if tong > 0 else None
    else:
        hop = rr.notna()
        n = int(hop.sum())
        ty_le = float(rr[hop].mean())
    if n < MIN_DONG_BASELINE:
        return _wf("chua_du_de_phan_tich", so_video=n,
                   ghi_chu=f"chỉ {n} video có dữ liệu khán giả (cần ≥ {MIN_DONG_BASELINE})")
    if ty_le is None:
        return _wf("chua_co_so_lieu", ghi_chu="không tính được tỷ lệ khán giả quay lại (mẫu số 0)")
    pct = ty_le * 100
    if ty_le < NGUONG_KHAN_GIA_THAP:
        nd = (f"Chỉ {pct:.0f}% người xem quay lại — kênh chủ yếu HÚT NGƯỜI LẠ rồi họ đi mất, chưa "
              f"tích lũy khán giả. Nên làm CHUỖI nội dung nhiều kỳ + cho lý do rõ để theo dõi kênh.")
    else:
        nd = (f"{pct:.0f}% người xem quay lại — kênh đang XÂY được tệp trung thành; tiếp tục nuôi "
              f"chuỗi nội dung để tăng tỷ lệ này (kênh đang thành thương hiệu).")
    return _wf("co_ket_qua", noi_dung=nd, so_video=n)


def ma_tran_ctr_retention(df_map: pd.DataFrame, bl3: dict) -> dict:
    """B3 — ma trận 2×2 CTR (cao/thấp) × Retention (cao/thấp) so baseline TOÀN KÊNH, đếm video
    mỗi ô → BỆNH PHỔ BIẾN NHẤT của kênh. Chỉ đếm video ĐỦ MẪU; video chưa đủ để riêng."""
    so = df_map.select_dtypes("number")
    toan = bl3.get("toan_kenh") or {}
    ctr_bl, ret_bl = toan.get("ctr"), toan.get("retention")
    if ctr_bl in (None, 0) or ret_bl in (None, 0):
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột CTR và/hoặc Retention")
    o = {"khoe": 0, "giat_tit": 0, "bao_bi_yeu": 0, "yeu_toan_dien": 0}
    chua_du = 0
    for i in range(len(so)):
        row = so.iloc[i]
        views, ctr, ret = row.get("views"), row.get("ctr"), row.get("retention")
        if not du_mau_ket_luan(views, toan.get("views")) or pd.isna(ctr) or pd.isna(ret):
            chua_du += 1
            continue
        ctr_cao, ret_cao = ctr >= ctr_bl, ret >= ret_bl
        o["khoe" if (ctr_cao and ret_cao) else "giat_tit" if ctr_cao
          else "bao_bi_yeu" if ret_cao else "yeu_toan_dien"] += 1
    tong = sum(o.values())
    if tong < MIN_DONG_NHOM:
        return _wf("chua_du_de_phan_tich", so_video=tong,
                   ghi_chu=f"chỉ {tong} video đủ mẫu để phân loại (cần ≥ {MIN_DONG_NHOM})")
    dong_nhat = max(o, key=o.get)
    _TEN = {"khoe": "video khỏe", "giat_tit": "giật tít",
            "bao_bi_yeu": "bao bì yếu", "yeu_toan_dien": "yếu toàn diện"}
    _HD = {"khoe": "nhân bản công thức đang thắng",
           "giat_tit": "sửa NỘI DUNG cho khớp lời hứa của thumbnail/tiêu đề",
           "bao_bi_yeu": "làm lại THUMBNAIL và TIÊU ĐỀ (nội dung vốn giữ chân tốt)",
           "yeu_toan_dien": "xem lại CẢ bao bì lẫn nội dung"}
    if dong_nhat == "khoe":
        nd = f"Phần lớn video KHỎE ({o['khoe']}/{tong}) — {_HD['khoe']}"
    else:
        nd = f"Bệnh phổ biến nhất: {_TEN[dong_nhat]} ({o[dong_nhat]}/{tong} video) → {_HD[dong_nhat]}"
    return {"trang_thai": "co_ket_qua", "noi_dung": nd, "so_video": tong, "ghi_chu": None,
            "ma_tran": {**o, "chua_du": chua_du}}


def rpm_theo_format(df_map: pd.DataFrame) -> dict:
    """C1 — bản đồ RPM (USD/1000 view) theo NHÓM ĐỘ DÀI, lộ ra nhóm lãi nhất mỗi nghìn view.
    Phụ thuộc dữ liệu tiền: không có cột RPM/doanh thu (kênh chưa monetize) → chưa có số liệu."""
    so = df_map.select_dtypes("number")
    if not _da_monetize(so):
        return _wf("chua_co_so_lieu", ghi_chu="report không có cột RPM/doanh thu (kênh chưa bật kiếm tiền)")
    if "rpm" not in so.columns or not so["rpm"].notna().any():
        return _wf("chua_du_de_phan_tich",
                   ghi_chu="có cột tiền nhưng thiếu RPM trực tiếp theo video (không tự tính từ 0)")
    rpm = pd.to_numeric(so["rpm"], errors="coerce")
    views = pd.to_numeric(so["views"], errors="coerce") if "views" in so.columns else None
    ndd = phan_nhom_do_dai(df_map)
    ket = {}
    for g in ("ngắn", "vừa", "dài"):
        mask = (ndd == g) & rpm.notna()
        cnt = int(mask.sum())
        if cnt >= MIN_DONG_NHOM:
            mv = float(views[mask].median()) if views is not None else None
            ket[g] = (cnt, float(rpm[mask].median()), mv)
    if not ket:
        return _wf("chua_du_de_phan_tich", ghi_chu=f"chưa nhóm độ dài nào đủ {MIN_DONG_NHOM} video có RPM")
    best = max(ket, key=lambda g: ket[g][1])
    cnt, medrpm, medviews = ket[best]
    nd = (f"Nhóm độ dài '{best}' có RPM cao nhất — trung vị {medrpm:.2f} USD/1000 view"
          + (f" (view trung vị {medviews:,.0f})" if medviews is not None else "")
          + ". Ưu tiên sản xuất theo LỢI NHUẬN, không chỉ theo view — nhóm ít view mà RPM cao có thể lãi hơn.")
    return _wf("co_ket_qua", noi_dung=nd, so_video=cnt)


# ═══ Đợt 3 — ĐƯỜNG CONG TUỔI THỌ VIDEO (velocity, methodology mục 3.A2). Ghép Chart data ═══
#     theo NGÀY với ngày đăng → mỗi video CHÍN (đạt 80% view) sau bao nhiêu ngày rồi NGUỘI.
MIN_VIDEO_VELOCITY = 3   # cần ≥ ngần này video đủ chuỗi ngày để lấy trung vị chín/nguội (Chart data ít video)
_VELO_DATE = _nfc_t("date", "ngày", "ngay")
_VELO_VIEWS = _nfc_t("engaged_views", "views", "lượt_xem_có_chủ_đích", "luot_xem_co_chu_dich",
                     "số_lượt_xem", "so_luot_xem")
_VELO_PUB = _nfc_t("video_publish_time", "thời_gian_xuất_bản_video", "thoi_gian_xuat_ban_video")


def duong_cong_tuoi_tho(df_chart, ngay_hien_tai=None) -> dict:
    """A2 — mỗi video CHÍN (cumulative đạt 80% view lifetime) sau bao nhiêu ngày kể từ đăng,
    rồi NGUỘI (view/ngày tụt < 10% đỉnh) sau bao nhiêu ngày. Trung vị cấp kênh trên các video
    ĐỦ dữ liệu. Van chống bịa: video bị cắt cụt đầu (đăng trước cửa sổ Chart) hoặc chưa nguội
    (view/ngày cuối vẫn cao) → xếp riêng, KHÔNG kết luận. Mốc 'hiện tại' = ngày lớn nhất trong
    dữ liệu (KHÔNG dùng giờ hệ thống) trừ khi truyền ngay_hien_tai."""
    if df_chart is None or len(df_chart) == 0:
        return _wf("chua_co_so_lieu", ghi_chu="report không có Chart data theo ngày")
    cot = {_chuan_hoa_ten(c): c for c in df_chart.columns}
    col_date = next((cot[k] for k in _VELO_DATE if k in cot), None)
    col_content = next((cot[k] for k in CONTENT_ALIASES if k in cot), None)
    col_pub = next((cot[k] for k in _VELO_PUB if k in cot), None)
    col_views = next((cot[k] for k in _VELO_VIEWS if k in cot), None)
    if col_date is None or col_content is None or col_views is None or col_pub is None:
        return _wf("chua_co_so_lieu", ghi_chu="Chart data thiếu cột Ngày/Nội dung/Ngày đăng/Lượt xem")

    chin_ls, nguoi_ls = [], []
    n_ok, n_cut, n_chua_nguoi = 0, 0, 0
    for _, g in df_chart.groupby(col_content):
        p = pd.to_datetime(g[col_pub], errors="coerce").dropna()
        if p.empty:
            continue
        pub = p.iloc[0].normalize()
        gg = pd.DataFrame({
            "age": (pd.to_datetime(g[col_date], errors="coerce").dt.normalize() - pub).dt.days,
            "v": pd.to_numeric(g[col_views], errors="coerce").fillna(0.0),
        }).dropna(subset=["age"])
        gg = gg[gg["age"] >= 0].sort_values("age")
        if gg.empty or gg["v"].sum() <= 0:
            continue
        if int(gg["age"].iloc[0]) > 1:          # cửa sổ Chart bắt đầu SAU khi đăng → cụt đầu
            n_cut += 1
            continue
        total = float(gg["v"].sum())
        peak = float(gg["v"].max())
        nguong = max(1.0, 0.1 * peak)
        if gg["v"].iloc[-1] >= nguong:          # ngày cuối vẫn active → CHƯA thấy nguội
            n_chua_nguoi += 1
            continue
        cum = gg["v"].cumsum()
        chin = int(gg["age"][cum >= 0.8 * total].iloc[0])       # đạt 80% view
        active = gg["age"][gg["v"] >= nguong]
        nguoi = int(active.iloc[-1]) if len(active) else chin    # ngày cuối view/ngày còn đáng kể
        n_ok += 1
        chin_ls.append(chin)
        nguoi_ls.append(nguoi)

    if n_ok < MIN_VIDEO_VELOCITY:
        return _wf("chua_du_de_phan_tich", so_video=n_ok,
                   ghi_chu=(f"chỉ {n_ok} video đủ chuỗi ngày để tính (cần ≥ {MIN_VIDEO_VELOCITY}; "
                            f"{n_cut} cắt cụt đầu, {n_chua_nguoi} chưa nguội) — cần Chart data dài "
                            f"hơn hoặc nhiều video hơn"))
    chin_med = int(pd.Series(chin_ls).median())
    nguoi_med = int(pd.Series(nguoi_ls).median())
    nhip = "đăng RẢI đều" if nguoi_med > 7 else "đăng DỒN theo cụm"
    nd = (f"Video của kênh thường CHÍN sau ~{chin_med} ngày (đạt 80% view) rồi NGUỘI sau ~{nguoi_med} "
          f"ngày. Nên giữ NHỊP đăng khoảng {nguoi_med} ngày/video ({nhip}) để duy trì view kênh.")
    return _wf("co_ket_qua", noi_dung=nd, so_video=n_ok)


def pham_vi_ngay_chart(df_chart) -> tuple[str, str] | None:
    """Issue 2 §2 — kỳ báo cáo [ngày đầu, ngày cuối] ISO 'YYYY-MM-DD', đọc từ cột Ngày của
    Chart data (report .xlsx). Trả None nếu không có Chart data / không có cột ngày đọc được
    (report .csv 'Table data' rời không kèm granularity ngày) — kỳ khi đó phải nhập tay hoặc
    để trống, KHÔNG tự đoán (van chống bịa: thà không có kỳ còn hơn đoán sai làm so_sanh_ky
    tính tăng trưởng ảo)."""
    if df_chart is None or len(df_chart) == 0:
        return None
    cot = {_chuan_hoa_ten(c): c for c in df_chart.columns}
    col_date = next((cot[k] for k in _VELO_DATE if k in cot), None)
    if col_date is None:
        return None
    ngay = pd.to_datetime(df_chart[col_date], errors="coerce").dropna()
    if ngay.empty:
        return None
    return ngay.min().strftime("%Y-%m-%d"), ngay.max().strftime("%Y-%m-%d")


DUNG_SAI_NGAY_KY = 2          # lệch độ dài kỳ tối đa (ngày) vẫn coi là "cùng độ dài" — bù sai số nhập tay
CHI_SO_SO_SANH_KY = ("views", "ctr", "retention", "watchtime", "revenue")


def so_sanh_ky(bao_cao_a: dict, bao_cao_b: dict) -> dict:
    """Issue 2 §3 — so sánh TĂNG TRƯỞNG giữa 2 báo cáo (dict ban_ghi từ bao_cao_lich_su.py) của
    CÙNG một kênh. Van chống bịa (methodology §7 'chiều thời gian, cẩn thận cửa sổ trượt'): chặn
    CỨNG — trả {'loi': lý_do} thay vì tính liều lĩnh — khi: (1) thiếu ten_kenh ở báo cáo nào đó
    (không xác định được có cùng kênh), (2) khác ten_kenh, (3) thiếu kỳ (ky_bat_dau/ky_ket_thuc)
    ở báo cáo nào đó, (4) hai kỳ lệch độ dài quá DUNG_SAI_NGAY_KY, (5) hai kỳ CHỒNG LẤN (báo cáo
    28-ngày xuất cách nhau 1 tuần chồng 21 ngày → so ngây thơ ra tăng trưởng ảo — đúng bẫy §7 nêu).
    Thuần Python, KHÔNG LLM — chỉ trừ số đã lưu sẵn (kenh.metrics_chinh), không đọc lại file gốc.
    Tham số không cần đúng thứ tự cũ/mới — tự xác định qua ky_bat_dau."""
    if bao_cao_a.get("id") and bao_cao_a.get("id") == bao_cao_b.get("id"):
        return {"loi": "Hai báo cáo giống hệt nhau (cùng id) — không có gì để so sánh."}
    ten_a = (bao_cao_a.get("ten_kenh") or "").strip()
    ten_b = (bao_cao_b.get("ten_kenh") or "").strip()
    if not ten_a or not ten_b:
        return {"loi": "Một trong hai báo cáo chưa gắn tên kênh — không xác định được có cùng "
                       "kênh hay không, không so sánh được."}
    if ten_a != ten_b:
        return {"loi": f"Hai báo cáo khác kênh ('{ten_a}' và '{ten_b}') — không so sánh được."}

    dau_a, cuoi_a = bao_cao_a.get("ky_bat_dau"), bao_cao_a.get("ky_ket_thuc")
    dau_b, cuoi_b = bao_cao_b.get("ky_bat_dau"), bao_cao_b.get("ky_ket_thuc")
    if not (dau_a and cuoi_a and dau_b and cuoi_b):
        return {"loi": "Một trong hai báo cáo chưa gắn kỳ (ngày bắt đầu/kết thúc) — không so "
                       "sánh được. Nạp lại report có Chart data hoặc nhập tay kỳ báo cáo."}
    try:
        da_a, ca_a = pd.Timestamp(dau_a), pd.Timestamp(cuoi_a)
        da_b, ca_b = pd.Timestamp(dau_b), pd.Timestamp(cuoi_b)
    except (ValueError, TypeError):
        return {"loi": "Ngày kỳ báo cáo không đọc được — không so sánh được."}
    if da_a > ca_a or da_b > ca_b:
        return {"loi": "Kỳ báo cáo có ngày bắt đầu sau ngày kết thúc — dữ liệu kỳ không hợp lệ."}

    if da_a > da_b:   # tự xác định CŨ/MỚI theo ngày bắt đầu — không tin thứ tự tham số truyền vào
        bao_cao_a, bao_cao_b = bao_cao_b, bao_cao_a
        da_a, ca_a, da_b, ca_b = da_b, ca_b, da_a, ca_a
        dau_a, cuoi_a, dau_b, cuoi_b = dau_b, cuoi_b, dau_a, cuoi_a

    do_dai_a, do_dai_b = (ca_a - da_a).days, (ca_b - da_b).days
    if abs(do_dai_a - do_dai_b) > DUNG_SAI_NGAY_KY:
        return {"loi": f"Hai kỳ khác độ dài đáng kể ({do_dai_a} ngày so với {do_dai_b} ngày) — "
                       "so sánh sẽ lệch, không đáng tin (methodology §7)."}
    if da_b <= ca_a:
        so_ngay_chong = (ca_a - da_b).days + 1
        return {"loi": f"Hai kỳ chồng lấn khoảng {so_ngay_chong} ngày — so sánh kiểu này cho "
                       "TĂNG TRƯỞNG ẢO (bẫy cửa sổ trượt, methodology §7), không so được."}

    m_cu = (bao_cao_a.get("kenh") or {}).get("metrics_chinh") or {}
    m_moi = (bao_cao_b.get("kenh") or {}).get("metrics_chinh") or {}
    chi_so = {}
    for k in CHI_SO_SO_SANH_KY:
        v_cu, v_moi = m_cu.get(k), m_moi.get(k)
        if v_cu is None or v_moi is None:
            continue
        delta = v_moi - v_cu
        chi_so[k] = {"cu": v_cu, "moi": v_moi, "delta": delta,
                     "pct": round(delta / v_cu * 100, 1) if v_cu else None}

    return {"ten_kenh": ten_a,
            "ky_cu": {"tu": dau_a, "den": cuoi_a}, "ky_moi": {"tu": dau_b, "den": cuoi_b},
            "chi_so": chi_so}


def bao_cao_kenh_9_muc(df_map: pd.DataFrame, bl3: dict, tong_quan: dict,
                       df_chart=None) -> list[dict]:
    """Khung 9 mục CỐ ĐỊNH cho báo cáo cả kênh — LUÔN trả đủ 9 mục đúng thứ tự A1..C3, mỗi
    mục tự khai 1 trong 3 trạng thái (suy từ dữ liệu). Mọi kết luận co_ket_qua kèm so_video."""
    so = df_map.select_dtypes("number")
    n = len(so)
    du_mau = n >= MIN_DONG_BASELINE
    toan = bl3.get("toan_kenh") or {}

    def co(*cols):        # có ≥1 cột SỐ (còn dữ liệu) trong danh sách
        return any(c in so.columns and so[c].notna().any() for c in cols)

    ra = []

    def co_ket_qua_hoac_mau_nho(ma, du_cot, ly_do_thieu, tinh_noi_dung):
        """3 mục ĐÃ có logic (A1/C2/C3): thiếu cột → chưa có số liệu; mẫu nhỏ → chưa đủ; else kết quả."""
        if not du_cot:
            ra.append(_muc9(ma, "chua_co_so_lieu", ghi_chu=ly_do_thieu))
        elif not du_mau:
            ra.append(_muc9(ma, "chua_du_de_phan_tich", so_video=n,
                            ghi_chu=f"kênh mới {n} video (cần ≥ {MIN_DONG_BASELINE} để kết luận)"))
        else:
            ra.append(_muc9(ma, "co_ket_qua", noi_dung=tinh_noi_dung(), so_video=n))

    wf = goi_y_winning_format(df_map)   # Đợt 1 — Winning Format: điền B1 (độ dài) + B2 (thứ/giờ/từ khóa)

    def tu_wf(ma, w, chieu_phu=None):
        ra.append(_muc9(ma, w["trang_thai"], noi_dung=w.get("noi_dung"), so_video=w.get("so_video"),
                        ghi_chu=w.get("ghi_chu"), chieu_phu=chieu_phu, ma_tran=w.get("ma_tran")))

    # ── A1 Pareto — CÓ LOGIC (tổng quan danh mục) ──
    def _nd_pareto():
        t1, t3 = tong_quan.get("tap_trung_top1") or 0, tong_quan.get("tap_trung_top3") or 0
        return (f"Top 1 video chiếm {t1*100:.0f}% view, top 3 chiếm {t3*100:.0f}% — "
                + ("phụ thuộc một cú trúng (chưa có mô hình bền vững)" if t1 > 0.6
                   else "phân bố tương đối đều"))
    co_ket_qua_hoac_mau_nho("A1", co("views"), "report không có cột Lượt xem", _nd_pareto)

    # ── A2..C1: 6 mục CHƯA có logic phân tích (nền khung) ──
    tu_wf("A2", duong_cong_tuoi_tho(df_chart))     # Đợt 3: đường cong tuổi thọ (cần Chart data)
    tu_wf("A3", phan_tich_khan_gia_kenh(df_map))   # Đợt 2: kênh đang xây hay đốt lượt xem
    # B1 độ dài + B2 thời điểm đăng: ĐÃ CÓ LOGIC (Winning Format Đợt 1). B2 gộp thứ (chính) +
    # khung giờ + từ khóa tiêu đề làm chiều phụ — mỗi chiều tự khai trạng thái riêng.
    tu_wf("B1", wf["do_dai"])
    tu_wf("B2", wf["thu"], chieu_phu=[
        {"ten": "Khung giờ đăng", **wf["gio"]},
        {"ten": "Từ khóa tiêu đề thắng", **wf["tu_khoa"]},
    ])
    tu_wf("B3", ma_tran_ctr_retention(df_map, bl3))   # Đợt 2: ma trận CTR×Retention → bệnh phổ biến
    tu_wf("C1", rpm_theo_format(df_map))              # Đợt 2: bản đồ RPM theo nhóm độ dài

    # ── C2 Rò rỉ phễu tiền — CÓ LOGIC (cấp kênh) ──
    def _nd_pheu_tien():
        rev, views_bl, rpm = toan.get("revenue"), toan.get("views"), toan.get("rpm")
        if rev and views_bl:
            return f"Doanh thu/view trung vị kênh ≈ {rev / views_bl:.4f} USD (soi mắt xích rò rỉ phễu tiền)"
        if rpm is not None:
            return f"RPM trung vị kênh ≈ {rpm:.2f} USD/1000 view"
        return "Có dữ liệu tiền ở video nhưng thiếu baseline doanh thu/RPM cấp kênh"
    co_ket_qua_hoac_mau_nho("C2", co("revenue", "ad_revenue", "rpm"),
                            "report không có cột doanh thu/RPM (kênh chưa bật kiếm tiền)", _nd_pheu_tien)

    # ── C3 Đòn bẩy end screen/card — CÓ LOGIC (đếm CTR = 0 = tiền/session để trên bàn) ──
    def _nd_don_bay():
        cot = "endscreen_ctr" if "endscreen_ctr" in so.columns else "card_ctr"
        nhan = "end screen" if cot == "endscreen_ctr" else "card"
        gt = pd.to_numeric(so[cot], errors="coerce").fillna(0)
        n_zero = int((gt <= 0).sum())
        return f"{n_zero}/{n} video có {nhan} CTR = 0 → tiền/session để trên bàn (chưa dùng {nhan})"
    co_ket_qua_hoac_mau_nho("C3", co("endscreen_ctr", "card_ctr"),
                            "report không có cột End screen/Card CTR", _nd_don_bay)

    return ra


# LƯỚI AN TOÀN TỔNG QUÁT — mỗi CHỈ SỐ QUAN TRỌNG: (biến engine cần | 'publish', regex dấu hiệu
# tên cột đa ngôn ngữ, tên dễ đọc). Nếu report có cột KHỚP dấu hiệu nhưng biến CHƯA ánh xạ → cảnh báo.
_NHOM_TIN_HIEU = [
    (("ctr",), r"click.?through|tỷ lệ nhấp|\bctr\b", "CTR (tỷ lệ nhấp)"),
    (("retention",), r"percentage viewed|tỷ lệ phần trăm đã xem|\bretention\b", "Tỷ lệ giữ chân (retention)"),
    (("duration_sec", "duration_min"), r"\bduration\b|thời lượng|độ dài video", "Độ dài video"),
    (TIEN_VARS, _TIN_HIEU_TIEN.pattern, "Doanh thu / RPM / CPM"),
    (("new_viewers", "returning_viewers", "returning_ratio"),
     r"new viewers|returning viewers|người xem mới|người xem cũ|người xem quay lại", "Người xem mới / quay lại"),
    ("publish", r"publish time|thời gian xuất bản|published", "Thời gian xuất bản"),
]


def _kiem_anh_xa_thieu(df_raw: pd.DataFrame, df_map: pd.DataFrame) -> list[dict]:
    """LƯỚI AN TOÀN TỔNG QUÁT (không chỉ tiền): report có tên cột mang dấu hiệu MỘT chỉ số quan
    trọng nhưng SAU ánh xạ engine KHÔNG có biến đó → cảnh báo (nhiều khả năng thiếu dòng ánh xạ
    cho ngôn ngữ này trong column_mapping.csv). PHÂN BIỆT: 'chưa ánh xạ' = cột KHÔNG map được (biến
    vắng trong df_map) — KHÁC 'map được nhưng rỗng' (biến CÓ trong df_map, chỉ thiếu dữ liệu thật:
    đó là 'chưa có số liệu' trung thực, KHÔNG cảnh báo). Trả [{ten, cot}] + LOG. Chống lỗi âm thầm
    kết luận sai (vd kênh đã monetize bị báo chưa monetize vì cột tiền tiếng Việt chưa ánh xạ)."""
    ket = []
    for bien, pat, ten in _NHOM_TIN_HIEU:
        anh_xa_duoc = (_cot_publish(df_map) is not None) if bien == "publish" \
            else any(b in df_map.columns for b in bien)   # 'có trong df_map' = ĐÃ ánh xạ (dù rỗng)
        if anh_xa_duoc:
            continue
        cot = next((c for c in df_raw.columns if re.search(pat, str(c), re.IGNORECASE)), None)
        if cot:
            ket.append({"ten": ten, "cot": str(cot)})
    if ket:
        logging.warning("Report có cột NGHI là chỉ số quan trọng nhưng CHƯA ánh xạ được biến — có "
                        "thể thiếu dòng ánh xạ trong rules/column_mapping.csv cho ngôn ngữ này: %s",
                        "; ".join(f"{k['ten']} (vd '{k['cot']}')" for k in ket))
    return ket


def _bang_chi_so(so: pd.DataFrame, df_map: pd.DataFrame, tieu_de_theo_i) -> dict:
    """CHẾ ĐỘ CHỈ-SỐ — trình bày số, KHÔNG phán quyết (Owner chốt 29/08).

    Trả: trung vị kênh 3 chỉ số + xu hướng theo tháng đăng + danh sách video kèm số
    (xếp view giảm dần) + cảnh báo video sụt SÂU so với chính kênh.
    Van chống bịa giữ nguyên: chỉ số nào report không có → None, KHÔNG suy ra 0."""
    ket_chi_so = {}
    for bien in CHI_SO_CHUA_TIEN:
        if bien in so.columns:
            gt = pd.to_numeric(so[bien], errors="coerce").dropna()
            ket_chi_so[bien] = {"trung_vi": round(float(gt.median()), 4),
                                "so_video": int(len(gt))} if len(gt) else None
        else:
            ket_chi_so[bien] = None

    # Cảnh báo SỤT SÂU — van duy nhất còn lại. So với trung vị KÊNH, chỉ báo ca dị
    # thường rõ rệt; KHÔNG xếp hạng, KHÔNG khuyến nghị hành động.
    # Chỉ xét AVD/CTR (xem CHI_SO_CANH_BAO): view lệch phân phối nên không dùng được.
    canh_bao = []
    for bien in CHI_SO_CANH_BAO:
        goc = ket_chi_so.get(bien)
        if not goc or bien not in so.columns:
            continue
        nguong = goc["trung_vi"] * TY_LE_SUT_SAU
        if nguong <= 0:
            continue
        cot = pd.to_numeric(so[bien], errors="coerce")
        for i in range(len(so)):
            v = cot.iloc[i]
            if pd.notna(v) and v < nguong:
                canh_bao.append({"chi_muc": i, "video_title": tieu_de_theo_i(i),
                                 "chi_so": bien, "gia_tri": round(float(v), 4),
                                 "trung_vi_kenh": goc["trung_vi"]})

    ds = []
    for i in range(len(so)):
        v = _sach(so.iloc[i].to_dict())
        ds.append({"chi_muc": i, "video_title": tieu_de_theo_i(i),
                   **{b: v.get(b) for b in CHI_SO_CHUA_TIEN}})
    ds.sort(key=lambda r: (r.get("views") is None, -(r.get("views") or 0)))
    return {"chi_so_kenh": ket_chi_so, "videos": ds, "canh_bao_sut_sau": canh_bao,
            "xu_huong": {b: v for b, v in (xu_huong_theo_thang(df_map) or {}).items()
                         if b in CHI_SO_CHUA_TIEN} or None}


def chan_doan_toan_bo(df: pd.DataFrame, ngay_chay=None, df_chart=None, loai_kenh=None,
                      trang_thai_kenh=None) -> dict:
    """Hàm TRANG UI GỌI: chấm 4 trục + phán quyết cho TỪNG video + bức tranh danh mục
    cấp kênh. KHÔNG gọi LLM (LLM chỉ diễn giải khi user bấm 1 video qua route riêng).
    df_chart: Chart data theo ngày (nếu có) → mục A2 đường cong tuổi thọ.
    loai_kenh: khóa loại kênh tự khai (vd 'tre_em'). Rỗng/không có profile → chạy y như
    không có tính năng (mặc định an toàn: KHÔNG giả định loại kênh). Baseline vẫn TỰ KÊNH.
    trang_thai_kenh: vòng đời khai ở General. uom_mam/sandbox — hoặc report thiếu hẳn cột
    tiền — → CHẾ ĐỘ CHỈ-SỐ: trả che_do='chi_so' (số + xu hướng + cảnh báo sụt sâu), KHÔNG
    phán quyết, KHÔNG chấm 4 trục (Owner chốt 29/08: kênh nhỏ số chưa chính xác nên đừng
    khuyến nghị). Kênh đã monetize + vòng đời khác → nhánh cũ, không đổi một byte."""
    _, df_video = tach_total_va_video(df)
    df_map = them_cot_phai_sinh(ap_anh_xa_cot(df_video), ngay_chay=ngay_chay)
    # AVD ≈ Retention × Duration (không có cột report ánh xạ) — tạo cột để CẢ video lẫn
    # baseline toàn kênh cùng có AVD (trục nội dung mới so được AVD với baseline kênh).
    if "retention" in df_map.columns and "duration_min" in df_map.columns:
        df_map["avd"] = (pd.to_numeric(df_map["retention"], errors="coerce")
                         * pd.to_numeric(df_map["duration_min"], errors="coerce"))
    so = df_map.select_dtypes("number")
    if so.empty:
        raise ValueError("Báo cáo không có cột số liệu nào (sau khi ánh xạ cột)")
    canh_bao_anh_xa = _kiem_anh_xa_thieu(df_video, df_map)   # lưới an toàn: cột có mà chưa ánh xạ
    ndd, ntu = phan_nhom_do_dai(df_map), phan_nhom_tuoi(df_map)
    bl3 = tinh_baseline_3_lop(so, ndd, ntu)   # tính MỘT LẦN, dùng chung mọi video
    profile = doc_content_profile(loai_kenh)  # None nếu rỗng/không có → không điều chỉnh gì

    def _tieu_de(i):
        for ten in ("video_title", "content"):
            if ten in df_map.columns and pd.notna(df_map.iloc[i][ten]):
                return str(df_map.iloc[i][ten])
        return None

    # ── CHẾ ĐỘ CHỈ-SỐ: kênh chưa bật kiếm tiền → TRÌNH BÀY SỐ, không phán quyết ──
    # Owner chốt 29/08: "kênh nhỏ các chỉ số đang chưa chính xác" nên mọi so sánh /
    # gợi ý đều bị cắt; giữ đúng một van là cảnh báo sụt sâu. Rẽ nhánh SỚM, trước khi
    # chấm trục — để không có đường nào rò phán quyết ra ngoài.
    if che_do_chi_so(so, trang_thai_kenh):
        kq = _bang_chi_so(so, df_map, _tieu_de)
        canh_bao = (f"Kênh mới có {len(so)} video — số liệu chưa đủ ổn định."
                    if len(so) < MIN_DONG_BASELINE else None)
        return {
            "che_do": "chi_so",            # UI đọc cờ này để dựng bảng số thay bảng phán quyết
            "so_video": len(so),
            "chi_so_kenh": kq["chi_so_kenh"],
            "videos": kq["videos"],
            "xu_huong": kq["xu_huong"],
            "canh_bao_sut_sau": kq["canh_bao_sut_sau"],
            "canh_bao_baseline": canh_bao,
            "canh_bao_anh_xa": [f"{k['ten']} (cột '{k['cot']}')" for k in canh_bao_anh_xa] or None,
            "trang_thai_kenh": (trang_thai_kenh or "").strip() or None,
            "ly_do_che_do": ("vòng đời kênh chưa bật kiếm tiền"
                             if (trang_thai_kenh or "").strip() in TRANG_THAI_CHUA_TIEN
                             else "report không có cột doanh thu/RPM"),
        }

    videos = []
    for i in range(len(so)):
        v = _sach(so.iloc[i].to_dict())
        nd = cham_truc_noi_dung(v, bl3, ndd.iloc[i], ntu.iloc[i], profile)
        ti = cham_truc_tien(v, bl3, profile)
        dm = cham_truc_danh_muc(v, bl3)
        ct = cham_truc_cong_thuc(v, bl3, ndd.iloc[i], ntu.iloc[i])
        pq = tong_hop_phan_quyet(nd, ti, dm, ct)
        tieu_de = _tieu_de(i)
        videos.append({
            "chi_muc": i, "video_title": tieu_de, "views": v.get("views"),
            "nhom_do_dai": ndd.iloc[i], "nhom_tuoi": ntu.iloc[i],
            "phan_quyet": pq["phan_quyet"], "giai_thich": pq["giai_thich"],
            "the_diem": pq["the_diem"], "baseline_da_dung": pq["baseline_da_dung"],
            "truc": {"noi_dung": nd, "tien": ti, "danh_muc": dm, "cong_thuc": ct},
        })

    canh_bao = None
    if len(so) < MIN_DONG_BASELINE:
        canh_bao = f"Kênh mới có {len(so)} video — baseline chưa đủ tin cậy."
    tong_quan = _tong_quan_danh_muc(so, ndd, bl3)
    # 08/08 (§12.2, §12.3): nối thêm tương quan liên tục + xu hướng theo tháng đăng — số THÔ,
    # đưa vào đề bài diễn giải ở app.py (_dong_tong_quan_bo_sung), LLM chỉ đọc không tự suy.
    tong_quan["tuong_quan"] = tinh_tuong_quan(so)
    tong_quan["xu_huong_thang"] = xu_huong_theo_thang(df_map)
    return {
        "che_do": "toan_bo",
        "so_video": len(so),
        "videos": videos,
        "tong_quan_danh_muc": tong_quan,
        "bao_cao_kenh": bao_cao_kenh_9_muc(df_map, bl3, tong_quan, df_chart),   # khung 9 mục cố định
        "baseline_3_lop": bl3,
        "canh_bao_baseline": canh_bao,
        # Lưới an toàn (A+B): cột chỉ số quan trọng chưa ánh xạ được → hiện banner cho user
        "canh_bao_anh_xa": [f"{k['ten']} (cột '{k['cot']}')" for k in canh_bao_anh_xa] or None,
        # Minh bạch loại kênh: khóa + profile áp dụng (None nếu không chọn loại kênh)
        "loai_kenh": profile["loai_kenh"] if profile else None,
        "profile_loai_kenh": profile,
    }
