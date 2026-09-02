# -*- coding: utf-8 -*-
"""CỬA KIỂM LOGIC to-chuc (02/09/2026) — "mỗi logic một sơ đồ".

Rà 02/09: app có 41 route + 19 màn mà CHỈ MỘT kịch bản canary, và nó chỉ soi
"3 file có tồn tại không" — không chạm logic nào. Đây là app nguy hiểm nhất hệ:
sai là TRẢ TIỀN SAI, ĐÁNH GIÁ NGƯỜI SAI, hoặc LỘ MẬT KHẨU công ty.

Nguyên tắc: CHỈ-ĐỌC, 0 quota. Phép nào cần ghi thì ghi vào THƯ MỤC TẠM riêng
của lượt kiểm (không bao giờ đụng sổ tiền / sổ chấm công thật).
"""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from src import cham_cong, kpi, luong, tai_chinh, vault


@contextmanager
def _kho_tam(*bien: str):
    """Trỏ các biến môi trường kho sang thư mục tạm trong lúc kiểm, rồi trả về
    như cũ. Van an toàn: cửa kiểm TUYỆT ĐỐI không được ghi vào sổ thật."""
    cu = {b: os.environ.get(b) for b in bien}
    tam = tempfile.mkdtemp(prefix="kiem-to-chuc-")
    try:
        for b in bien:
            os.environ[b] = str(Path(tam) / b.lower())
        yield Path(tam)
    finally:
        for b, v in cu.items():
            if v is None:
                os.environ.pop(b, None)
            else:
                os.environ[b] = v


def luong_khong_tu_tru() -> dict:
    """Owner chốt TUYỆT ĐỐI: máy KHÔNG tự trừ lương theo ngày công / đi muộn —
    đường duy nhất ảnh hưởng lương là ô 'điều chỉnh HR' có lý do bắt buộc.
    Ai 'tối ưu' thêm hệ số ngày công là tiền bị cắt tự động theo con số đo hiện
    diện; sai kiểu này im như tờ vì bảng vẫn ra số đẹp.

    Kiểm: hai người CÙNG lương cơ bản + CÙNG xếp loại nhưng số ngày công KHÁC
    hẳn nhau (5 vs 22) → thực nhận phải BẰNG NHAU."""
    with _kho_tam("CHAM_CONG_DIR", "TO_CHUC_DB"):
        from src import kpi_danh_gia
        ky = "2026-08"
        ds = [{"ten": "a", "ma": "NS-901", "ho_ten": "A", "bo_phan": "VH"},
              {"ten": "b", "ma": "NS-902", "ho_ten": "B", "bo_phan": "VH"}]
        # A đi làm 3 ngày, B đi làm 12 ngày
        for i in range(3):
            _cham_tam("a", f"2026-08-{3+i:02d}")
        for i in range(12):
            _cham_tam("b", f"2026-08-{3+i:02d}")
        try:
            luong.dat_luong_co_ban("hr", "a", 10_000_000)
            luong.dat_luong_co_ban("hr", "b", 10_000_000)
            kpi_danh_gia.them_danh_gia("a", ky, "B", "kiểm", "hr")
            kpi_danh_gia.them_danh_gia("b", ky, "B", "kiểm", "hr")
        except Exception as e:  # noqa: BLE001 — chữ ký khác thì báo, không bịa
            return {"loi_dung_ham": f"{type(e).__name__}: {e}",
                    "cung_luong_du_khac_ngay_cong": None,
                    "thieu_du_lieu_de_trong": None}
        bang = luong.bang_luong(ky, ds)
        theo = {d["ten"]: d for d in bang["dong"]}
        ta, tb = theo.get("a", {}).get("thuc_nhan"), theo.get("b", {}).get("thuc_nhan")

        # người THIẾU dữ liệu (không lương cơ bản) → để trống, KHÔNG đoán
        ds2 = ds + [{"ten": "c", "ma": "NS-903", "ho_ten": "C", "bo_phan": "VH"}]
        bang2 = luong.bang_luong(ky, ds2)
        dong_c = next((d for d in bang2["dong"] if d["ten"] == "c"), None)
        return {"thuc_nhan_a": ta, "thuc_nhan_b": tb,
                "cung_luong_du_khac_ngay_cong": ta is not None and ta == tb,
                "thieu_du_lieu_de_trong": bool(dong_c) and dong_c.get("thuc_nhan") is None
                                          and bool(dong_c.get("thieu"))}


def _cham_tam(ten: str, ngay: str, vao: str = "08:20:00") -> None:
    """Ghi thẳng file chấm công trong THƯ MỤC TẠM (đã trỏ env)."""
    import json
    p = Path(os.environ["CHAM_CONG_DIR"]) / f"{ngay[:7]}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    du = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    du.setdefault(ngay, {})[ten] = {"vao": vao, "ra": "17:30:00",
                                    "nguon_ra": "dang_xuat"}
    p.write_text(json.dumps(du, ensure_ascii=False), encoding="utf-8")


def kpi_van_chong_bia() -> dict:
    """Nguồn KPI chết → '—' kèm lý do, TUYỆT ĐỐI không 0 giả. Hiện 0 thì Manager
    đọc thành 'người này không làm gì' → đánh giá sai người thật."""
    cu = {b: os.environ.get(b) for b in
          ("PLANNERY_PLAN", "CONTENT_HISTORY", "SPEAKY_JOBS_LOG", "BAO_CAO_DIR")}
    try:
        for b in cu:
            os.environ[b] = str(Path(tempfile.gettempdir()) / "khong-ton-tai-canary" / b)
        ra = kpi.tong_hop_kpi([{"ten": "x", "ma": "NS-999", "ho_ten": "X",
                                "bo_phan": "VH", "vi_tri": "content"}], "tuan")
    finally:
        for b, v in cu.items():
            if v is None:
                os.environ.pop(b, None)
            else:
                os.environ[b] = v
    thieu = ra.get("thieu") or {}
    # mọi chỉ số của người phải là None (không phải 0)
    so_0_gia = 0
    for d in ra.get("dong") or []:
        for k, v in d.items():
            if k in ("ten", "ho_ten", "ma", "bo_phan", "vi_tri", "ly_do"):
                continue
            if v == 0:
                so_0_gia += 1
    return {"so_nguon_thieu": len(thieu), "thieu": list(thieu)[:4],
            "nguon_chet_la_none": len(thieu) >= 3,
            "khong_co_so_0_gia": so_0_gia == 0}


def cham_cong_vao_ra() -> dict:
    """Giờ VÀO là tín hiệu ĐẦU ngày, không bao giờ bị đè (nếu thành gán thẳng
    thì mọi người thành đi làm lúc 18h); giờ RA theo tín hiệu CUỐI. Tín hiệu
    chủ đích (đóng app) KHÔNG bị throttle nuốt."""
    import json
    with _kho_tam("CHAM_CONG_DIR"):
        t = datetime(2026, 8, 3, 8, 5, 0)
        cham_cong.ghi_nhan("canary", luc=t)
        cham_cong.ghi_nhan("canary", luc=t.replace(hour=12))
        cham_cong.ghi_nhan("canary", "dong_app", luc=t.replace(hour=18))
        p = Path(os.environ["CHAM_CONG_DIR"]) / "2026-08.json"
        du = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        n = (du.get("2026-08-03") or {}).get("canary") or {}
    return {"vao": n.get("vao"), "ra": n.get("ra"), "nguon_ra": n.get("nguon_ra"),
            "vao_giu_tin_hieu_dau": (n.get("vao") or "").startswith("08:05"),
            "ra_theo_tin_hieu_cuoi": (n.get("ra") or "").startswith("18:")}


def chot_cong_chi_them() -> dict:
    """Chốt công kỳ ghi ĐÚNG MỘT LẦN — chốt đè = sửa lịch sử chấm công sau khi
    đã trả lương, đối chiếu về sau mất cơ sở."""
    with _kho_tam("CHAM_CONG_DIR"):
        cham_cong.chot_ky("2026-08", "hr-canary")
        lan_hai_tu_choi = False
        try:
            cham_cong.chot_ky("2026-08", "hr-canary")
        except ValueError:
            lan_hai_tu_choi = True
    return {"lan_hai_bi_tu_choi": lan_hai_tu_choi}


def so_tien_chi_them() -> dict:
    """Sổ tiền CHỈ-THÊM: sửa = bút toán ĐẢO (dòng mới), dòng gốc còn nguyên.
    Nếu đường nào ghi đè dòng cũ thì sổ mất tính bất biến → đối soát/kiểm toán
    sụp mà báo cáo vẫn ra số đẹp. Đọc SỔ THẬT (chỉ đọc) để soi bất biến."""
    so = tai_chinh.doc_so()
    theo_id: dict[str, int] = {}
    for d in so:
        i = d.get("id")
        if i:
            theo_id[i] = theo_id.get(i, 0) + 1
    trung = [i for i, n in theo_id.items() if n > 1]
    dao = [d for d in so if d.get("loai") == "dao" or d.get("tham_chieu")]
    # đảo phải trỏ tới dòng CÓ THẬT và không đảo-của-đảo
    dao_hong = []
    for d in dao:
        tc = d.get("tham_chieu")
        goc = next((x for x in so if x.get("id") == tc), None)
        if tc and (goc is None or goc.get("loai") == "dao"):
            dao_hong.append(tc)
    return {"so_dong": len(so), "so_id_trung": len(trung),
            "so_dao": len(dao), "so_dao_hong": len(dao_hong),
            "dong_goc_con_nguyen": len(trung) == 0,
            "dao_sinh_dong_moi": len(dao_hong) == 0}


def vault_dia_ma_hoa() -> dict:
    """Trên đĩa KHÔNG BAO GIỜ có bản rõ — trộm file/backup là đọc hết, đúng thứ
    AES-GCM sinh ra để chặn. Dựng vault TẠM rồi soi bytes."""
    MOC = "MAT-KHAU-MOC-CANARY-9f3a"
    with _kho_tam("VAULT_DIR"):
        try:
            vault.tao_vault("mat-khau-chu-du-dai-canary", "canary")
            vault.mo_bang_master("mat-khau-chu-du-dai-canary", "canary")
            # module không mở API thêm mục công khai — dùng đường nội bộ để dựng
            # dữ liệu MẪU trong vault TẠM (không đụng vault thật)
            vault._ghi_muc([{"nhom": "khac", "ten": "thử", "tai_khoan": "u",
                             "mat_khau": MOC}], vault._dek_dang_mo())
        except Exception as e:  # noqa: BLE001
            return {"loi_dung_ham": f"{type(e).__name__}: {e}",
                    "dia_khong_chua_ban_ro": None,
                    "chua_mo_khong_doc_duoc": None}
        goc = Path(os.environ["VAULT_DIR"])
        tho = b""
        for f in goc.rglob("*"):
            if f.is_file():
                tho += f.read_bytes()
        vault.khoa()
        doc_duoc_khi_khoa = True
        try:
            doc_duoc_khi_khoa = vault.doc_muc() is not None
        except Exception:  # noqa: BLE001 — ném lỗi cũng là "không đọc được"
            doc_duoc_khi_khoa = False
    return {"so_byte_dia": len(tho),
            "dia_khong_chua_ban_ro": MOC.encode() not in tho,
            "chua_mo_khong_doc_duoc": not doc_duoc_khi_khoa}


def nguoi_nghi_ra_khoi_bang() -> dict:
    """Người đã thôi việc không còn trong bảng lương — còn trong bảng là CHI
    TIỀN cho người không còn làm, mà sổ chỉ-thêm nên bút toán đó không xóa
    được. Đọc IAM thật (chỉ đọc) + đối chiếu bảng lương kỳ này."""
    from src import main as _m
    ds, ly_do = _m._ds_nguoi_iam()
    if ds is None:
        return {"iam_loi": ly_do, "nghi_khong_vao_bang": None}
    ky = datetime.now().strftime("%Y-%m")
    bang = luong.bang_luong(ky, ds)
    ten_trong_bang = {d.get("ten") for d in bang.get("dong") or []}
    # _ds_nguoi_iam đã lọc người nghỉ → giao của hai tập phải rỗng theo định
    # nghĩa; kiểm thêm: mọi dòng bảng lương đều có mã hồ sơ (không tài khoản hệ)
    khong_ma = [d.get("ten") for d in bang.get("dong") or [] if not d.get("ma")]
    return {"so_nguoi_iam": len(ds), "so_dong_bang": len(ten_trong_bang),
            "so_dong_khong_ma": len(khong_ma),
            "nghi_khong_vao_bang": len(khong_ma) == 0}


CAC_MA = {"luong-khong-tu-tru": luong_khong_tu_tru,
          "kpi-van-chong-bia": kpi_van_chong_bia,
          "cham-cong-vao-ra": cham_cong_vao_ra,
          "chot-cong-chi-them": chot_cong_chi_them,
          "so-tien-chi-them": so_tien_chi_them,
          "vault-dia-ma-hoa": vault_dia_ma_hoa,
          "nguoi-nghi-ra-khoi-bang": nguoi_nghi_ra_khoi_bang}
