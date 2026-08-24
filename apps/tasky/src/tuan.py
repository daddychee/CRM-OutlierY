# -*- coding: utf-8 -*-
"""LÕI TASKY — sổ việc theo tuần + toàn bộ luật nghiệp vụ (FLOW-v3.md).

Mỗi tuần MỘT file `TASKY_DIR/tuan/YYYY-Www.json`, ghi nguyên tử (tmp + os.replace)
dưới một khóa tiến trình. Mọi thao tác đổi trạng thái đều để lại vết CHỈ-THÊM trong
`TASKY_DIR/nhat-ky.jsonl` — đổi ý vẫn còn dấu ai làm gì lúc nào.

BA LUẬT KHÔNG ĐƯỢC NỚI (Owner chốt 24/08):
1. **Giao việc**: level người giao > level người nhận VÀ cùng bộ phận (Owner L5 giao
   mọi bộ phận). Kiểm Ở ĐÂY bằng level+bộ phận thật, KHÔNG tin dropdown của client.
2. **Nhận việc là bắt buộc**: chưa bấm Nhận thì chưa viết được checklist — leader
   nhờ đó biết chắc việc đã đến tay người ta.
3. **Van chống bịa**: chưa có việc nào → tỉ lệ là None (UI hiện "—"), TUYỆT ĐỐI
   không trả 0.0 giả vờ là "làm việc kém".

Việc bị TỪ CHỐI hoặc HỦY không vào mẫu số tỉ lệ (không phải việc nhân sự không làm),
nhưng vẫn đếm riêng để leader nhìn thấy — giao sai người là tín hiệu quản trị.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# Trạng thái việc — tập HỮU HẠN, code không được sinh giá trị ngoài tập này.
CHO_NHAN, DANG_LAM, BAO_XONG, XAC_NHAN = "cho_nhan", "dang_lam", "bao_xong", "xac_nhan"
TU_CHOI, HUY, DOI = "tu_choi", "huy", "doi"
TRANG_THAI = (CHO_NHAN, DANG_LAM, BAO_XONG, XAC_NHAN, TU_CHOI, HUY, DOI)
# Trạng thái ĐƯỢC TÍNH vào mẫu số tỉ lệ hoàn thành (xem docstring).
TRONG_MAU_SO = (CHO_NHAN, DANG_LAM, BAO_XONG, XAC_NHAN, DOI)
OWNER_LEVEL = 5
DOI_LA_KET = 2          # dời từ 2 lần trở lên → cờ "việc kẹt"

_khoa = threading.Lock()


# ---------- đường dẫn + tuần ----------

def _goc() -> Path:
    return Path(os.getenv("TASKY_DIR", "data/tasky/db"))


def _duong_tuan(ma: str) -> Path:
    return _goc() / "tuan" / f"{ma}.json"


def ma_tuan(ngay: date | None = None) -> str:
    """'2026-W35' theo lịch ISO (tuần bắt đầu Thứ Hai — chuẩn VN)."""
    y, w, _ = (ngay or date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def khoang_tuan(ma: str) -> tuple[str, str]:
    """'2026-W35' → ('2026-08-24', '2026-08-30'). Mã sai → ValueError."""
    try:
        y, w = ma.split("-W")
        dau = date.fromisocalendar(int(y), int(w), 1)
    except (ValueError, AttributeError):
        raise ValueError(f"Mã tuần phải dạng YYYY-Www, nhận '{ma}'.")
    return dau.isoformat(), date.fromisocalendar(int(y), int(w), 7).isoformat()


def tuan_ke_tiep(ma: str) -> str:
    """'2026-W52' → '2027-W01' (cộng 7 ngày rồi hỏi lại lịch ISO — không tự cộng
    số tuần, vì năm ISO có năm 52 tuần có năm 53)."""
    tu, _ = khoang_tuan(ma)
    return ma_tuan(date.fromisoformat(tu) + timedelta(days=7))


def _gio() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- đọc / ghi ----------

def doc_tuan(ma: str) -> dict:
    """Sổ một tuần. Chưa có file / file hỏng → sổ RỖNG hợp lệ (đọc khoan dung,
    không dựng ngoại lệ cho ca 'tuần chưa ai khai gì')."""
    tu, den = khoang_tuan(ma)
    trong = {"tuan": ma, "tu": tu, "den": den, "viec": [], "dong": {}}
    p = _duong_tuan(ma)
    if not p.is_file():
        return trong
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return trong
    if not isinstance(d, dict) or not isinstance(d.get("viec"), list):
        return trong
    d.setdefault("dong", {})
    return d


def _ghi_tuan(so: dict) -> None:
    p = _duong_tuan(so["tuan"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(so, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


def ghi_nhat_ky(hanh_dong: str, ai: str, chi_tiet: dict) -> None:
    """Vết CHỈ-THÊM. Nhật ký hỏng KHÔNG được chặn nghiệp vụ."""
    try:
        p = _goc() / "nhat-ky.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        ban = {"luc": _gio(), "hanh_dong": hanh_dong, "ai": ai, **chi_tiet}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ban, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _tim(so: dict, id_viec: str) -> dict:
    for v in so["viec"]:
        if v["id"] == id_viec:
            return v
    raise ValueError("Không tìm thấy việc này.")


# ---------- luật quyền (§9.2) ----------

def duoc_giao_cho(nguoi_giao: dict, nguoi_nhan: dict) -> bool:
    """Level cao giao level thấp, cùng bộ phận. Owner (L5) giao mọi bộ phận.
    Ngang cấp KHÔNG giao được nhau — luật nghiêm ngặt lớn hơn."""
    if nguoi_giao["level"] <= nguoi_nhan["level"]:
        return False
    if nguoi_giao["level"] >= OWNER_LEVEL:
        return True
    return bool(nguoi_giao.get("bo_phan")) and \
        nguoi_giao.get("bo_phan") == nguoi_nhan.get("bo_phan")


def _kiem_chinh_chu(viec: dict, user: dict) -> None:
    if viec["nguoi"] != user["ten"]:
        raise PermissionError("Đây không phải việc của bạn.")


def duoc_xac_nhan(viec: dict, user: dict) -> bool:
    """Người GIAO việc đó xác nhận. Owner xác nhận được tất. Việc tự thêm hoặc việc
    của chính leader → tự xác nhận (báo cáo sẽ dán nhãn 'tự xác nhận')."""
    if user["level"] >= OWNER_LEVEL:
        return True
    if viec.get("nguoi_giao") and viec["nguoi_giao"] == user["ten"]:
        return True
    return viec["nguoi"] == user["ten"] and user["level"] >= 3


# ---------- thao tác ----------

def _viec_moi(tieu_de: str, loai_viec: str, nguoi: str) -> dict:
    tieu_de = (tieu_de or "").strip()
    if not tieu_de:
        raise ValueError("Việc phải có tên.")
    return {"id": "v-" + uuid.uuid4().hex[:8],
            "tieu_de": tieu_de[:200],
            "loai_viec": (loai_viec or "").strip()[:60],
            "nguoi": nguoi,
            "nguoi_giao": None, "nguon": "tu_them", "trang_thai": DANG_LAM,
            "ly_do": "", "checklist": [],
            "so_lan_doi": 0, "goc_id": None,
            "nguon_ngoai": None,        # chừa cho chiều Tasky → PlannerY (§9.5)
            "luc_tao": _gio(), "luc_nhan": None, "luc_bao_xong": None,
            "luc_xac_nhan": None, "nguoi_xac_nhan": None, "tu_xac_nhan": False}


def them_viec_giao(ma: str, nguoi_giao: dict, nguoi_nhan: dict,
                   tieu_de: str, loai_viec: str) -> dict:
    """Leader giao việc → trạng thái CHỜ NHẬN. Loại việc bắt buộc: đây là khóa gom
    checklist thành quy trình sau này (§5), thiếu thì không cứu được bằng migration."""
    if not duoc_giao_cho(nguoi_giao, nguoi_nhan):
        raise PermissionError(
            "Chỉ giao được cho người cấp dưới trong bộ phận mình.")
    if not (loai_viec or "").strip():
        raise ValueError("Phải chọn loại việc.")
    with _khoa:
        so = doc_tuan(ma)
        v = _viec_moi(tieu_de, loai_viec, nguoi_nhan["ten"])
        v.update({"nguoi_giao": nguoi_giao["ten"], "nguon": "giao",
                  "trang_thai": CHO_NHAN})
        so["viec"].append(v)
        _ghi_tuan(so)
    ghi_nhat_ky("giao_viec", nguoi_giao["ten"],
                {"tuan": ma, "viec": v["id"], "cho": nguoi_nhan["ten"],
                 "tieu_de": v["tieu_de"]})
    return v


def them_viec_tu(ma: str, user: dict, tieu_de: str, loai_viec: str = "") -> dict:
    """Việc nhân sự tự nhận — không qua luật giao, vào thẳng ĐANG LÀM."""
    with _khoa:
        so = doc_tuan(ma)
        v = _viec_moi(tieu_de, loai_viec, user["ten"])
        v["luc_nhan"] = v["luc_tao"]
        so["viec"].append(v)
        _ghi_tuan(so)
    ghi_nhat_ky("tu_them_viec", user["ten"],
                {"tuan": ma, "viec": v["id"], "tieu_de": v["tieu_de"]})
    return v


def nhan_viec(ma: str, id_viec: str, user: dict) -> dict:
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        _kiem_chinh_chu(v, user)
        if v["trang_thai"] != CHO_NHAN:
            raise ValueError("Việc này không ở trạng thái chờ nhận.")
        v.update({"trang_thai": DANG_LAM, "luc_nhan": _gio()})
        _ghi_tuan(so)
    ghi_nhat_ky("nhan_viec", user["ten"], {"tuan": ma, "viec": id_viec})
    return v


def tu_choi_viec(ma: str, id_viec: str, user: dict, ly_do: str) -> dict:
    """Từ chối BẮT BUỘC ghi lý do. Việc trả về leader (giao lại / sửa / hủy)."""
    ly_do = (ly_do or "").strip()
    if not ly_do:
        raise ValueError("Phải ghi lý do từ chối.")
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        _kiem_chinh_chu(v, user)
        if v["trang_thai"] != CHO_NHAN:
            raise ValueError("Chỉ từ chối được việc chưa nhận.")
        v.update({"trang_thai": TU_CHOI, "ly_do": ly_do[:500]})
        _ghi_tuan(so)
    ghi_nhat_ky("tu_choi_viec", user["ten"],
                {"tuan": ma, "viec": id_viec, "ly_do": ly_do[:500]})
    return v


def them_buoc(ma: str, id_viec: str, user: dict, noi_dung: str) -> dict:
    """Viết một bước checklist. CHƯA NHẬN VIỆC thì chưa viết được (luật 2)."""
    noi_dung = (noi_dung or "").strip()
    if not noi_dung:
        raise ValueError("Bước phải có nội dung.")
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        _kiem_chinh_chu(v, user)
        if v["trang_thai"] == CHO_NHAN:
            raise ValueError("Nhận việc trước rồi mới viết cách triển khai.")
        if v["trang_thai"] in (TU_CHOI, HUY):
            raise ValueError("Việc đã đóng, không thêm bước được.")
        b = {"id": "b-" + uuid.uuid4().hex[:6], "noi_dung": noi_dung[:300],
             "xong": False, "luc_xong": None}
        v["checklist"].append(b)
        _ghi_tuan(so)
    return b


def tick_buoc(ma: str, id_viec: str, id_buoc: str, user: dict, xong: bool = True) -> dict:
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        _kiem_chinh_chu(v, user)
        for b in v["checklist"]:
            if b["id"] == id_buoc:
                b["xong"] = bool(xong)
                b["luc_xong"] = _gio() if xong else None
                _ghi_tuan(so)
                return b
    raise ValueError("Không tìm thấy bước này.")


def bao_xong(ma: str, id_viec: str, user: dict) -> dict:
    """Nhân sự báo xong → chờ leader xác nhận (nấc 2 của FLOW-v3 §4)."""
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        _kiem_chinh_chu(v, user)
        if v["trang_thai"] not in (DANG_LAM, BAO_XONG):
            raise ValueError("Việc chưa nhận hoặc đã đóng.")
        v.update({"trang_thai": BAO_XONG, "luc_bao_xong": _gio()})
        _ghi_tuan(so)
    ghi_nhat_ky("bao_xong", user["ten"], {"tuan": ma, "viec": id_viec})
    return v


def xac_nhan_viec(ma: str, id_viec: str, user: dict) -> dict:
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not duoc_xac_nhan(v, user):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới xác nhận được.")
        if v["trang_thai"] != BAO_XONG:
            raise ValueError("Chỉ xác nhận được việc đã báo xong.")
        v.update({"trang_thai": XAC_NHAN, "luc_xac_nhan": _gio(),
                  "nguoi_xac_nhan": user["ten"],
                  "tu_xac_nhan": v["nguoi"] == user["ten"]})
        _ghi_tuan(so)
    ghi_nhat_ky("xac_nhan", user["ten"], {"tuan": ma, "viec": id_viec})
    return v


def tra_lai_viec(ma: str, id_viec: str, user: dict, ly_do: str = "") -> dict:
    """Leader trả lại việc báo xong mà chưa đạt → về ĐANG LÀM."""
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not duoc_xac_nhan(v, user):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới trả lại được.")
        if v["trang_thai"] != BAO_XONG:
            raise ValueError("Chỉ trả lại được việc đang chờ xác nhận.")
        v.update({"trang_thai": DANG_LAM, "luc_bao_xong": None,
                  "ly_do": (ly_do or "").strip()[:500]})
        _ghi_tuan(so)
    ghi_nhat_ky("tra_lai", user["ten"], {"tuan": ma, "viec": id_viec})
    return v


def huy_viec(ma: str, id_viec: str, user: dict, ly_do: str) -> dict:
    """Hủy BẮT BUỘC ghi lý do; việc giữ nguyên trong sổ, không xóa."""
    ly_do = (ly_do or "").strip()
    if not ly_do:
        raise ValueError("Phải ghi lý do hủy.")
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not duoc_xac_nhan(v, user):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới hủy được.")
        v.update({"trang_thai": HUY, "ly_do": ly_do[:500]})
        _ghi_tuan(so)
    ghi_nhat_ky("huy_viec", user["ten"],
                {"tuan": ma, "viec": id_viec, "ly_do": ly_do[:500]})
    return v


def doi_sang_tuan_sau(ma: str, id_viec: str, user: dict,
                      ly_do: str = "", nguoi_moi: dict | None = None) -> dict:
    """Đóng tuần: việc chưa xong → dời. Tuần này ghi DOI (vẫn tính là chưa hoàn
    thành — đó là sự thật), tuần sau sinh việc MỚI giữ goc_id + so_lan_doi + 1.
    Đổi người = dời kèm người mới, vẫn phải qua luật giao việc."""
    ma_sau = tuan_ke_tiep(ma)
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not duoc_xac_nhan(v, user):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới dời được.")
        if v["trang_thai"] in (XAC_NHAN, HUY, TU_CHOI, DOI):
            raise ValueError("Việc này không còn để dời.")
        nhan = nguoi_moi or {"ten": v["nguoi"], "level": 0, "bo_phan": None}
        if nguoi_moi and not duoc_giao_cho(user, nguoi_moi):
            raise PermissionError("Chỉ đổi sang người cấp dưới trong bộ phận mình.")
        v.update({"trang_thai": DOI, "ly_do": (ly_do or "").strip()[:500]})
        _ghi_tuan(so)

        sau = doc_tuan(ma_sau)
        moi = _viec_moi(v["tieu_de"], v["loai_viec"], nhan["ten"])
        moi.update({"nguoi_giao": v.get("nguoi_giao") or user["ten"],
                    "nguon": v["nguon"],
                    "trang_thai": CHO_NHAN if v["nguon"] == "giao" else DANG_LAM,
                    "goc_id": v.get("goc_id") or v["id"],
                    "so_lan_doi": v["so_lan_doi"] + 1,
                    # checklist chép sang để không phải viết lại từ đầu, bỏ tick cũ
                    "checklist": [{"id": "b-" + uuid.uuid4().hex[:6],
                                   "noi_dung": b["noi_dung"], "xong": False,
                                   "luc_xong": None}
                                  for b in v["checklist"] if not b["xong"]]})
        sau["viec"].append(moi)
        _ghi_tuan(sau)
    ghi_nhat_ky("doi_tuan", user["ten"],
                {"tuan": ma, "viec": id_viec, "sang": ma_sau, "viec_moi": moi["id"],
                 "lan_doi": moi["so_lan_doi"], "ly_do": (ly_do or "")[:500]})
    return moi


def dong_tuan(ma: str, nguoi: str, user: dict) -> dict:
    """Leader chốt: tuần này của một người coi như đã soát xong."""
    with _khoa:
        so = doc_tuan(ma)
        con_treo = [v for v in so["viec"]
                    if v["nguoi"] == nguoi and v["trang_thai"] in (CHO_NHAN, DANG_LAM, BAO_XONG)]
        if con_treo:
            raise ValueError(
                f"Còn {len(con_treo)} việc chưa xử lý — xác nhận, dời hoặc hủy trước khi đóng tuần.")
        so["dong"][nguoi] = {"luc": _gio(), "boi": user["ten"]}
        _ghi_tuan(so)
    ghi_nhat_ky("dong_tuan", user["ten"], {"tuan": ma, "cua": nguoi})
    return so["dong"][nguoi]


# ---------- đọc theo phạm vi + thống kê ----------

def viec_cua(ma: str, ten: str) -> list[dict]:
    return [v for v in doc_tuan(ma)["viec"] if v["nguoi"] == ten]


def cho_xac_nhan(ma: str, user: dict) -> list[dict]:
    """Việc đang chờ CHÍNH user này xác nhận (dùng cho màn Giao việc)."""
    return [v for v in doc_tuan(ma)["viec"]
            if v["trang_thai"] == BAO_XONG and duoc_xac_nhan(v, user)]


def thong_ke_nguoi(ma: str, ten: str) -> dict:
    """Số của MỘT người trong tuần.

    ti_le = None khi không có việc nào trong mẫu số — van chống bịa, UI hiện "—".
    Việc bị từ chối / bị hủy đếm riêng, KHÔNG vào mẫu số.
    """
    ds = viec_cua(ma, ten)
    mau_so = [v for v in ds if v["trang_thai"] in TRONG_MAU_SO]
    xong = [v for v in mau_so if v["trang_thai"] == XAC_NHAN]
    buoc = [b for v in ds for b in v["checklist"]]
    return {
        "nguoi": ten,
        "so_viec": len(mau_so),
        "giao": sum(1 for v in mau_so if v["nguon"] == "giao"),
        "tu_them": sum(1 for v in mau_so if v["nguon"] == "tu_them"),
        "xong": len(xong),
        "cho_xac_nhan": sum(1 for v in mau_so if v["trang_thai"] == BAO_XONG),
        "chua_nhan": sum(1 for v in mau_so if v["trang_thai"] == CHO_NHAN),
        "bi_tu_choi": sum(1 for v in ds if v["trang_thai"] == TU_CHOI),
        "bi_huy": sum(1 for v in ds if v["trang_thai"] == HUY),
        "ket": sum(1 for v in mau_so if v["so_lan_doi"] >= DOI_LA_KET),
        "buoc_tong": len(buoc),
        "buoc_xong": sum(1 for b in buoc if b["xong"]),
        "tu_xac_nhan": any(v["tu_xac_nhan"] for v in xong),
        "ti_le": round(100 * len(xong) / len(mau_so)) if mau_so else None,
        "da_dong": ten in doc_tuan(ma)["dong"],
    }


def bang_bao_cao(ma: str, ds_nguoi: list[dict]) -> list[dict]:
    """Bảng báo cáo cho danh sách người ĐÃ LỌC PHẠM VI (route lo quyền — lõi không
    tự đoán ai được xem ai)."""
    ra = []
    for n in ds_nguoi:
        t = thong_ke_nguoi(ma, n["ten"])
        t.update({"ho_ten": n.get("ho_ten", ""), "bo_phan": n.get("bo_phan", "")})
        ra.append(t)
    return ra
