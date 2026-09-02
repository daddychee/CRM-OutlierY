# -*- coding: utf-8 -*-
"""CỬA KIỂM LOGIC data-analytics (02/09/2026) — "mỗi logic một sơ đồ".

Rà 02/09 (Owner: "chạy lại từng app để không bỏ sót") thấy app chỉ có 2 kịch bản
canary, cả hai đọc cờ hạ tầng — engine là nơi RA PHÁN QUYẾT cho người dùng mà
không logic nào được canh.

Nguyên tắc: CHỈ-ĐỌC, 0 quota, KHÔNG gọi LLM (engine thuần Python nên tự nhiên
đạt). Route trả SỐ ĐO THẬT; phán đúng/sai nằm ở kịch bản canary ngoài code.
"""
from __future__ import annotations

import itertools

import pandas as pd

from src import diagnosis_engine as eng

TRANG_THAI = ("✓", "⚠", "✗", "?")


def phan_quyet_huu_han() -> dict:
    """7 phán quyết là tập ĐÓNG. Quét MỌI tổ hợp 4 trục × 4 trạng thái × các
    nhãn bệnh — engine không được sinh giá trị ngoài `PHAN_QUYET` ('cỗ máy đẻ
    luật' là rủi ro thật khi ai đó thêm nhánh return mới)."""
    benh_ds = (None, "khoe", "ctr_hong", "retention_hong", "le_the")
    ngoai, so = [], 0
    thieu_du_lieu_dung = True
    for nd, ti, dm, ct in itertools.product(TRANG_THAI, repeat=4):
        for benh in benh_ds:
            so += 1
            pq = eng.tong_hop_phan_quyet(
                {"trang_thai": nd, "so_lieu": {"benh": benh}},
                {"trang_thai": ti, "so_lieu": {}},
                {"trang_thai": dm, "so_lieu": {}},
                {"trang_thai": ct, "so_lieu": {}})
            if pq["phan_quyet"] not in eng.PHAN_QUYET:
                ngoai.append(f"{nd}{ti}{dm}{ct}/{benh} → {pq['phan_quyet']}")
            # VAN CHỐNG BỊA cao nhất: nội dung '?' (mẫu quá nhỏ) → luôn dừng
            if nd == "?" and pq["phan_quyet"] != "chua_du_du_lieu":
                thieu_du_lieu_dung = False
    return {"so_to_hop": so, "so_ngoai_tap": len(ngoai),
            "vi_du_ngoai": ngoai[:3],
            "thieu_du_lieu_luon_dung": thieu_du_lieu_dung,
            "so_phan_quyet_khai": len(eng.PHAN_QUYET)}


def anh_xa_don_vi() -> dict:
    """Hệ số %→tỷ lệ 0.01: sai là MỌI ngưỡng lệch 100 lần → không luật nào khớp,
    báo cáo trắng mà HTTP vẫn 200. Report EN và VN phải ra CÙNG biến luật."""
    en = pd.DataFrame([{"Content": "v1",
                        "Impressions click-through rate (%)": 4.61,
                        "Average percentage viewed (%)": 42.0,
                        "Views": 1000}])
    # tên cột VN lấy ĐÚNG từ rules/column_mapping.csv — luật ngoài code, không
    # đoán theo trí nhớ (đoán sai một lần rồi: "Tỷ lệ nhấp qua số lần hiển thị")
    vn = pd.DataFrame([{"Nội dung": "v1",
                        "Tỷ lệ nhấp của số lượt hiển thị hình thu nhỏ (%)": 4.61,
                        "Tỷ lệ phần trăm đã xem trung bình (%)": 42.0,
                        "Số lượt xem": 1000}])
    ra_en = eng.ap_anh_xa_cot(en)
    ra_vn = eng.ap_anh_xa_cot(vn)

    def _lay(df, ten):
        return float(df.iloc[0][ten]) if ten in df.columns else None

    ctr_en, ctr_vn = _lay(ra_en, "ctr"), _lay(ra_vn, "ctr")
    ret_en = _lay(ra_en, "retention")
    return {"ctr_en": ctr_en, "ctr_vn": ctr_vn, "retention_en": ret_en,
            # 4.61% → 0.0461 (không phải 4.61)
            "ctr_dung_don_vi": ctr_en is not None and abs(ctr_en - 0.0461) < 1e-6,
            "en_va_vn_cung_bien": ctr_en is not None and ctr_en == ctr_vn,
            "bien_en": sorted(c for c in ra_en.columns if c.islower())[:6]}


def van_mau_nho() -> dict:
    """Van chống bịa cỡ mẫu ĐỘNG max(NGUONG_SAN 100, 10% median kênh): video 40
    view không được chấm — phán quyết trên nhiễu thống kê là bịa có vẻ khoa học."""
    ca = [((99, 500), False), ((100, 500), True),
          ((150, 5000), False),   # dưới 10% × 5000 = 500
          ((600, 5000), True),
          ((None, 500), False),
          ((500, None), True)]    # median thiếu → dùng sàn 100
    sai = []
    for (views, med), mong in ca:
        that = eng.du_mau_ket_luan(views, med)
        if bool(that) != mong:
            sai.append(f"views={views} med={med}: {that} ≠ {mong}")
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3],
            "nguong_san": eng.NGUONG_SAN}


def baseline_nguon() -> dict:
    """Baseline 3 lớp PHẢI khai nguồn đang so + lùi đúng khi nhóm thiếu mẫu.
    Không khai thì LLM viết 'so với kênh' trong khi số là nhóm độ dài — người
    đọc tin nhầm căn cứ."""
    bl3 = {"toan_kenh": {"ctr": 0.05},
           "theo_do_dai": {"dài": {"ctr": 0.08}, "ngắn": None},
           "theo_tuoi": {"mới": {"ctr": 0.06}}}
    ca = [
        # (biến, nhóm dài, nhóm tuổi, mục đích) → (giá trị mong, chuỗi nguồn phải chứa)
        (("ctr", "dài", "mới", "format"), (0.08, "độ dài")),
        (("ctr", "ngắn", "mới", "format"), (0.05, "toàn kênh")),   # nhóm None → lùi
        (("ctr", "dài", "mới", "chien_luoc"), (0.05, "toàn kênh")),
    ]
    sai, luon_khai = [], True
    for args, (gt_mong, chua) in ca:
        gt, nguon = eng.chon_baseline(*args, bl3)
        if not nguon:
            luon_khai = False
        if gt != gt_mong or chua.lower() not in (nguon or "").lower():
            sai.append(f"{args} → {gt} / {nguon!r}")
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3],
            "luon_khai_nguon": luon_khai}


def che_do_chi_so() -> dict:
    """Kênh chưa monetize → chế độ CHỈ-SỐ: TUYỆT ĐỐI không phán quyết, không gọi
    LLM (Owner chốt: kênh nhỏ số chưa chính xác, KHÔNG khuyến nghị). Rò một phán
    quyết là đưa lời khuyên trên dữ liệu vô nghĩa."""
    df = pd.DataFrame([
        {"content": f"v{i}", "video_title": f"Video {i}", "views": 500 + i,
         "ctr": 0.04, "retention": 0.4, "watchtime": 100.0, "duration": 600}
        for i in range(8)])
    kq = eng.chan_doan_toan_bo(df, trang_thai_kenh="uom_mam")
    videos = kq.get("videos") or []
    ro_ri = sum(1 for v in videos if v.get("phan_quyet"))
    return {"che_do": kq.get("che_do"), "so_video": len(videos),
            "so_phan_quyet_ro_ri": ro_ri,
            "co_bao_cao_kenh": bool(kq.get("bao_cao_kenh"))}


def so_sanh_ky() -> dict:
    """Bẫy CỬA SỔ TRƯỢT: 2 report 28 ngày xuất cách nhau 1 tuần chồng 21 ngày —
    so ngây thơ ra 'tăng trưởng +300%' hoàn toàn ảo mà không dấu hiệu nào là sai.
    Đây là loại sai lặng lẽ nguy hiểm nhất: người ra quyết định trên số ảo."""
    def bc(id_, ten, dau, cuoi, views=1000):
        return {"id": id_, "ten_kenh": ten, "ky_bat_dau": dau,
                "ky_ket_thuc": cuoi,
                "kenh": {"metrics_chinh": {"views": views}}}

    ca = [
        ("thiếu tên kênh",
         bc("a", "", "2026-01-01", "2026-01-28"), bc("b", "K", "2026-02-01", "2026-02-28")),
        ("khác kênh",
         bc("a", "K1", "2026-01-01", "2026-01-28"), bc("b", "K2", "2026-02-01", "2026-02-28")),
        ("thiếu kỳ",
         bc("a", "K", None, None), bc("b", "K", "2026-02-01", "2026-02-28")),
        ("CHỒNG LẤN 21 ngày",
         bc("a", "K", "2026-01-01", "2026-01-28"), bc("b", "K", "2026-01-08", "2026-02-04")),
    ]
    sai, bat_chong_lan = [], False
    for ten, a, b in ca:
        ra = eng.so_sanh_ky(a, b)
        if not ra.get("loi"):
            sai.append(f"{ten}: KHÔNG chặn")
        elif "chồng" in ten.lower() and "chồng" in ra["loi"].lower():
            bat_chong_lan = True
    # ca hợp lệ: 2 kỳ RỜI, cùng kênh, cùng độ dài → phải ra số
    hop_le = eng.so_sanh_ky(
        bc("a", "K", "2026-01-01", "2026-01-28", 1000),
        bc("b", "K", "2026-02-01", "2026-02-28", 1500))
    if hop_le.get("loi"):
        sai.append(f"ca hợp lệ bị chặn oan: {hop_le['loi'][:60]}")
    return {"so_ca": len(ca) + 1, "so_sai": len(sai), "chi_tiet": sai[:3],
            "bat_duoc_chong_lan": bat_chong_lan,
            "ca_hop_le_ra_so": not hop_le.get("loi")}


CAC_MA = {"phan-quyet-huu-han": phan_quyet_huu_han,
          "anh-xa-don-vi": anh_xa_don_vi,
          "van-mau-nho": van_mau_nho,
          "baseline-nguon": baseline_nguon,
          "che-do-chi-so": che_do_chi_so,
          "so-sanh-ky": so_sanh_ky}
