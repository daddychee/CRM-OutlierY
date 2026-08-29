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
import re
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# Trạng thái việc — tập HỮU HẠN, code không được sinh giá trị ngoài tập này.
CHO_NHAN, DANG_LAM, BAO_XONG, XAC_NHAN = "cho_nhan", "dang_lam", "bao_xong", "xac_nhan"
TU_CHOI, HUY, DOI = "tu_choi", "huy", "doi"
# Yêu cầu phối hợp LIÊN BỘ PHẬN đang chờ bên kia đồng ý (Owner chốt 24/08). Khác
# CHO_NHAN ở chỗ người gửi KHÔNG có quyền trên người nhận — đây là lời mời, không
# phải lệnh; bên kia từ chối là hết chuyện.
CHO_PHOI_HOP = "cho_phoi_hop"
# Việc Manager chẻ ra từ mục tiêu mà CHƯA chọn người (§12) — nó tồn tại trong cây,
# đếm vào tổng việc của mục tiêu, nhưng chưa thuộc về ai nên không vào tỉ lệ của ai.
CHUA_GIAO = "chua_giao"
TRANG_THAI = (CHUA_GIAO, CHO_NHAN, CHO_PHOI_HOP, DANG_LAM, BAO_XONG, XAC_NHAN,
              TU_CHOI, HUY, DOI)
# Trạng thái ĐƯỢC TÍNH vào mẫu số tỉ lệ hoàn thành (xem docstring).
TRONG_MAU_SO = (CHO_NHAN, CHO_PHOI_HOP, DANG_LAM, BAO_XONG, XAC_NHAN, DOI)
LEADER_LEVEL = 3
OWNER_LEVEL = 5
DOI_LA_KET = 2          # dời từ 2 lần trở lên → cờ "việc kẹt"
GAN_HAN_NGAY = 2        # còn ≤ 2 ngày mới gọi là "gần đến hạn" (§16)

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


def tuan_lien_ke(ma: str, buoc: int = 1) -> str:
    """Tuần trước/sau: cộng ngày rồi HỎI LẠI lịch ISO — không tự cộng số tuần, vì
    năm ISO có năm 52 tuần có năm 53 ('2026-W52' + 1 = '2026-W53', +2 = '2027-W01')."""
    tu, _ = khoang_tuan(ma)
    return ma_tuan(date.fromisoformat(tu) + timedelta(days=7 * buoc))


def tuan_ke_tiep(ma: str) -> str:
    return tuan_lien_ke(ma, 1)


def _gio() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- đọc / ghi ----------

def doc_json(duong: Path, mac_dinh: dict) -> dict:
    """Đọc JSON khoan dung: chưa có file / file hỏng → mặc định, không nổ."""
    if not duong.is_file():
        return dict(mac_dinh)
    try:
        d = json.loads(duong.read_text(encoding="utf-8"))
    except ValueError:
        return dict(mac_dinh)
    return d if isinstance(d, dict) else dict(mac_dinh)


def _ghi_json(duong: Path, du_lieu: dict) -> None:
    """Ghi nguyên tử: tmp + os.replace — mất điện giữa chừng không để lại file cụt."""
    duong.parent.mkdir(parents=True, exist_ok=True)
    tam = duong.with_name(duong.name + ".tmp")
    tam.write_text(json.dumps(du_lieu, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, duong)


def cac_tuan_gan(so_tuan: int = 26) -> list[str]:
    """Mã các tuần đã có sổ, mới nhất trước — dùng cho thứ sống XUYÊN TUẦN
    (mục tiêu, kho quy trình)."""
    thu_muc = _goc() / "tuan"
    if not thu_muc.is_dir():
        return []
    return [p.stem for p in sorted(thu_muc.glob("*.json"), reverse=True)[:so_tuan]]


def doc_tuan(ma: str) -> dict:
    """Sổ một tuần. Chưa có file / file hỏng → sổ RỖNG hợp lệ (đọc khoan dung,
    không dựng ngoại lệ cho ca 'tuần chưa ai khai gì')."""
    tu, den = khoang_tuan(ma)
    trong = {"tuan": ma, "tu": tu, "den": den, "viec": [], "dong": {}}
    d = doc_json(_duong_tuan(ma), trong)
    if not isinstance(d.get("viec"), list):
        return trong
    d.setdefault("dong", {})
    return d


def _ghi_tuan(so: dict) -> None:
    _ghi_json(_duong_tuan(so["tuan"]), so)


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
    if nguoi_giao["ten"] == nguoi_nhan["ten"]:
        return True          # tự nhận việc về mình — Manager cũng là người làm việc
    if nguoi_giao["level"] <= nguoi_nhan["level"]:
        return False
    if nguoi_giao["level"] >= OWNER_LEVEL:
        return True
    return bool(nguoi_giao.get("bo_phan")) and \
        nguoi_giao.get("bo_phan") == nguoi_nhan.get("bo_phan")


def duoc_yeu_cau_phoi_hop(nguoi_gui: dict, nguoi_nhan: dict) -> bool:
    """Phối hợp NGANG giữa hai bộ phận (Owner chốt 24/08): cả hai phải là quản lý
    (L3+), phải KHÁC BỘ PHẬN, và chênh nhau tối đa 1 bậc.

    Khác bộ phận thì không ai chỉ huy ai (lệ 04/08: toàn quyền chỉ ở bộ phận chủ
    quản) — nên đây là YÊU CẦU, bên kia có quyền từ chối. Cùng bộ phận thì đã có
    đường giao việc thường, không đi cửa này."""
    if nguoi_gui["level"] < LEADER_LEVEL or nguoi_nhan["level"] < LEADER_LEVEL:
        return False
    if not nguoi_gui.get("bo_phan") or not nguoi_nhan.get("bo_phan"):
        return False
    if nguoi_gui["bo_phan"] == nguoi_nhan["bo_phan"]:
        return False
    return abs(nguoi_gui["level"] - nguoi_nhan["level"]) <= 1


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
    if viec.get("nguon") == "phoi_hop":
        return False      # việc phối hợp: BÊN YÊU CẦU nghiệm thu, bên làm không tự
                          # ký cho mình (Owner chốt 24/08)
    return viec["nguoi"] == user["ten"] and user["level"] >= LEADER_LEVEL


# ---------- thao tác ----------

def _han_hop_le(han: str) -> str:
    """Hạn chót dạng YYYY-MM-DD, rỗng = không đặt hạn. Sai định dạng → nói thẳng,
    KHÔNG âm thầm bỏ qua (người giao tưởng đã đặt hạn mà thật ra không)."""
    han = (han or "").strip()
    if not han:
        return ""
    try:
        return date.fromisoformat(han).isoformat()
    except ValueError:
        raise ValueError("Hạn chót phải dạng ngày (YYYY-MM-DD).")


def tinh_han(viec: dict, hom_nay: date | None = None) -> dict:
    """Nhãn hạn cho UI + mức cấp thiết. Việc đã ngã ngũ (xác nhận/hủy/từ chối/dời)
    thì KHÔNG còn hạn để lo — không dọa người ta bằng việc đã xong."""
    if not viec.get("han") or viec["trang_thai"] not in (CHO_NHAN, CHO_PHOI_HOP,
                                                         DANG_LAM, BAO_XONG):
        return {"chu": "", "muc": "", "con": None}
    hom_nay = hom_nay or date.today()
    try:
        con = (date.fromisoformat(viec["han"]) - hom_nay).days
    except ValueError:
        return {"chu": "", "muc": "", "con": None}
    if con < 0:
        return {"chu": f"Quá hạn {-con} ngày", "muc": "cap", "con": con}
    if con == 0:
        return {"chu": "Hạn hôm nay", "muc": "cap", "con": 0}
    if con == 1:
        return {"chu": "Hạn ngày mai", "muc": "luu_y", "con": 1}
    ngay = date.fromisoformat(viec["han"])
    return {"chu": f"Hạn {ngay.day:02d}/{ngay.month:02d}",
            "muc": "luu_y" if con <= 3 else "", "con": con}


def the_trang_thai(viec: dict, hom_nay: date | None = None) -> list[dict]:
    """Chip trạng thái cho thẻ việc (Owner 25/08) — LÕI quyết, template chỉ vẽ.

    Tối đa HAI chip vì đó là hai câu hỏi khác nhau: việc đang ở đâu (ai cầm) và
    hạn có gấp không. Chip hạn chỉ hiện khi thật sự gấp — còn 5 ngày mà đã tô màu
    thì lần nào cũng đỏ, người ta thôi nhìn.
    """
    tt = viec["trang_thai"]
    tien_do = {
        CHUA_GIAO: ("Chưa giao", "luu_y"),
        CHO_NHAN: ("Chưa ai nhận", "luu_y"),
        CHO_PHOI_HOP: ("Chờ bộ phận khác nhận", "luu_y"),
        DANG_LAM: ("Đã nhận", "tin"),
        BAO_XONG: ("Chờ nghiệm thu", "tin"),
        XAC_NHAN: ("Đã nghiệm thu", "ok"),
        TU_CHOI: ("Bị từ chối", "cap"),
        HUY: ("Đã hủy", ""),
        DOI: ("Đã dời sang tuần sau", ""),
    }.get(tt)
    ra = [{"chu": tien_do[0], "muc": tien_do[1]}] if tien_do else []

    h = tinh_han(viec, hom_nay)          # rỗng khi việc đã ngã ngũ
    if h["con"] is not None:
        if h["con"] < 0:
            ra.append({"chu": "Quá deadline", "muc": "cap"})
        elif h["con"] <= GAN_HAN_NGAY:
            ra.append({"chu": "Gần đến hạn", "muc": "luu_y"})
    return ra


def sap_xep(ds: list[dict], hom_nay: date | None = None) -> list[dict]:
    """Gấp và quá hạn nổi lên đầu — thứ cần làm trước phải nằm trên đầu màn hình.
    Trong cùng mức thì việc có hạn gần đứng trước, rồi tới việc tạo sớm hơn."""
    def khoa(v):
        h = tinh_han(v, hom_nay)
        return (0 if v.get("gap") else 1,
                0 if h["muc"] == "cap" else 1,
                h["con"] if h["con"] is not None else 9999,
                v.get("luc_tao", ""))
    return sorted(ds, key=khoa)


def _gon_khoang_trang(chu: str) -> str:
    """Gộp mọi khoảng trắng liên tiếp thành MỘT dấu cách.

    HTML tự gộp khoảng trắng khi hiển thị, còn ô nhập thì giữ nguyên văn — hai
    dấu cách trong tên việc làm người dùng tưởng "sửa rồi mà ngoài không đổi"
    (Owner 25/08). Lưu đúng thứ người ta nhìn thấy thì hết mơ hồ."""
    return " ".join((chu or "").split())


def _viec_moi(tieu_de: str, loai_viec: str, nguoi: str) -> dict:
    tieu_de = _gon_khoang_trang(tieu_de)
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
            "tu_yeu_cau": "",           # id việc phối hợp mà việc này được chẻ ra
            "han": "", "gap": False,    # hạn chót (ISO) + dấu GẤP (Owner chốt 24/08)
            "muc_tieu_id": "",          # việc này phục vụ mục tiêu nào (§12)
            "cung_viec": "",            # cùng một việc giao cho nhiều người (§14)
            "trao_doi": [],             # cuộc trao đổi trong việc (§15) — CHỈ THÊM
            "mo_ta": "",                # đề bài chi tiết, người giao viết (§16)
            "tai_lieu": [],             # link/đường NAS đính kèm (§16)
            "luc_tao": _gio(), "luc_nhan": None, "luc_bao_xong": None,
            "luc_xac_nhan": None, "nguoi_xac_nhan": None, "tu_xac_nhan": False}


def them_viec_giao(ma: str, nguoi_giao: dict, nguoi_nhan: dict,
                   tieu_de: str, loai_viec: str, tu_yeu_cau: str = "",
                   han: str = "", gap: bool = False, muc_tieu_id: str = "") -> dict:
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
                  "trang_thai": CHO_NHAN, "tu_yeu_cau": tu_yeu_cau or "",
                  "han": _han_hop_le(han), "gap": bool(gap),
                  "muc_tieu_id": muc_tieu_id or ""})
        so["viec"].append(v)
        _ghi_tuan(so)
    ghi_nhat_ky("giao_viec", nguoi_giao["ten"],
                {"tuan": ma, "viec": v["id"], "cho": nguoi_nhan["ten"],
                 "tieu_de": v["tieu_de"]})
    return v


def yeu_cau_phoi_hop(ma: str, nguoi_gui: dict, nguoi_nhan: dict,
                     tieu_de: str, loai_viec: str,
                     han: str = "", gap: bool = False, muc_tieu_id: str = "") -> dict:
    """Gửi YÊU CẦU phối hợp sang bộ phận khác — trạng thái CHỜ PHỐI HỢP.

    Bên nhận toàn quyền: nhận rồi tự làm, hoặc chẻ việc con giao cho người của họ
    (đường giao việc thường, `tu_yeu_cau` giữ liên kết ngược). Từ chối cũng được —
    người gửi không có quyền trên họ."""
    if not duoc_yeu_cau_phoi_hop(nguoi_gui, nguoi_nhan):
        raise PermissionError(
            "Chỉ gửi được cho quản lý bộ phận KHÁC, chênh nhau tối đa 1 bậc.")
    if not (loai_viec or "").strip():
        raise ValueError("Phải chọn loại việc.")
    with _khoa:
        so = doc_tuan(ma)
        v = _viec_moi(tieu_de, loai_viec, nguoi_nhan["ten"])
        v.update({"nguoi_giao": nguoi_gui["ten"], "nguon": "phoi_hop",
                  "trang_thai": CHO_PHOI_HOP,
                  "bo_phan_gui": nguoi_gui.get("bo_phan", ""),
                  "han": _han_hop_le(han), "gap": bool(gap),
                  "muc_tieu_id": muc_tieu_id or ""})
        so["viec"].append(v)
        _ghi_tuan(so)
    ghi_nhat_ky("yeu_cau_phoi_hop", nguoi_gui["ten"],
                {"tuan": ma, "viec": v["id"], "cho": nguoi_nhan["ten"],
                 "bo_phan_nhan": nguoi_nhan.get("bo_phan", ""), "tieu_de": v["tieu_de"]})
    return v


def yeu_cau_da_gui(ma: str, user: dict) -> list[dict]:
    """Yêu cầu phối hợp CHÍNH user này gửi đi — để theo dõi, không tính vào tỉ lệ
    của họ (Owner chốt: ai làm mới được tính công)."""
    return [v for v in doc_tuan(ma)["viec"]
            if v["nguon"] == "phoi_hop" and v.get("nguoi_giao") == user["ten"]]


def viec_con(ma: str, id_yeu_cau: str) -> list[dict]:
    """Việc bên nhận đã chẻ ra giao cho người bộ phận mình từ một yêu cầu."""
    return [v for v in doc_tuan(ma)["viec"] if v.get("tu_yeu_cau") == id_yeu_cau]


def them_viec_muc_tieu(ma: str, user: dict, tieu_de: str, loai_viec: str,
                       muc_tieu_id: str, han: str = "", gap: bool = False) -> dict:
    """Manager chẻ một việc từ mục tiêu, CHƯA chọn người — cây hiện ngay, giao sau."""
    if not muc_tieu_id:
        raise ValueError("Việc này phải thuộc một mục tiêu.")
    if not (loai_viec or "").strip():
        raise ValueError("Phải chọn loại việc.")
    with _khoa:
        so = doc_tuan(ma)
        v = _viec_moi(tieu_de, loai_viec, "")
        v.update({"nguoi_giao": user["ten"], "nguon": "giao", "trang_thai": CHUA_GIAO,
                  "muc_tieu_id": muc_tieu_id, "han": _han_hop_le(han), "gap": bool(gap)})
        so["viec"].append(v)
        _ghi_tuan(so)
    ghi_nhat_ky("che_viec", user["ten"],
                {"tuan": ma, "viec": v["id"], "muc_tieu": muc_tieu_id,
                 "tieu_de": v["tieu_de"]})
    return v


def gan_nguoi(ma: str, id_viec: str, nguoi_giao: dict, nguoi_nhan: dict) -> dict:
    """Giao một việc đang CHƯA GIAO cho ai đó — vẫn qua đúng luật giao việc (§9.2)."""
    if not duoc_giao_cho(nguoi_giao, nguoi_nhan):
        raise PermissionError("Chỉ giao được cho người cấp dưới trong bộ phận mình.")
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if v["trang_thai"] != CHUA_GIAO:
            raise ValueError("Việc này đã có người rồi.")
        v.update({"nguoi": nguoi_nhan["ten"], "nguoi_giao": nguoi_giao["ten"],
                  "trang_thai": CHO_NHAN, "luc_tao": _gio()})
        _ghi_tuan(so)
    ghi_nhat_ky("giao_viec", nguoi_giao["ten"],
                {"tuan": ma, "viec": id_viec, "cho": nguoi_nhan["ten"],
                 "tieu_de": v["tieu_de"]})
    return v


def gan_lai_nguoi(ma: str, id_viec: str, nguoi_giao: dict,
                  nguoi_nhan: dict | None) -> dict:
    """Giao LẠI một việc cho người khác, hoặc gỡ người (nguoi_nhan=None).

    Chỉ làm được khi việc CHƯA AI BẮT TAY VÀO: chưa giao / chờ nhận / bị từ chối.
    Việc đang làm dở hoặc đã báo xong thì phải Trả lại (hoặc Hủy kèm lý do) trước —
    giao thẳng cho người khác là xóa trắng công người đang làm mà họ không biết.
    """
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if v["trang_thai"] not in (CHUA_GIAO, CHO_NHAN, TU_CHOI):
            raise ValueError("Việc đang làm dở thì Trả lại hoặc Hủy trước, "
                             "rồi mới giao cho người khác.")
        if not (v.get("nguoi_giao") == nguoi_giao["ten"]
                or nguoi_giao["level"] >= OWNER_LEVEL):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới giao lại.")
        if nguoi_nhan is None:
            v.update({"nguoi": "", "trang_thai": CHUA_GIAO, "ly_do": ""})
        else:
            if not duoc_giao_cho(nguoi_giao, nguoi_nhan):
                raise PermissionError(
                    "Chỉ giao được cho người cấp dưới trong bộ phận mình.")
            v.update({"nguoi": nguoi_nhan["ten"], "trang_thai": CHO_NHAN,
                      "ly_do": "", "luc_nhan": None})
        _ghi_tuan(so)
    ghi_nhat_ky("gan_lai_nguoi", nguoi_giao["ten"],
                {"tuan": ma, "viec": id_viec,
                 "cho": nguoi_nhan["ten"] if nguoi_nhan else ""})
    return v


def giao_nhieu_nguoi(ma: str, nguoi_giao: dict, ds_nhan: list[dict], tieu_de: str,
                     loai_viec: str, **kw) -> list[dict]:
    """Cùng một việc, nhiều người làm (Owner chốt 25/08).

    MỖI NGƯỜI MỘT BẢN VIỆC — ai cũng tự viết checklist, tự bấm nhận, tự được nghiệm
    thu, nên mọi luật và tỉ lệ hiện có giữ nguyên. Các bản dùng chung `cung_viec` để
    UI gom lại thành một dòng "Việc X — 3 người".
    """
    if not ds_nhan:
        raise ValueError("Phải chọn ít nhất một người.")
    chung = "cv-" + uuid.uuid4().hex[:8] if len(ds_nhan) > 1 else ""
    ra = []
    for n in ds_nhan:
        v = them_viec_giao(ma, nguoi_giao, n, tieu_de, loai_viec, **kw)
        if chung:
            with _khoa:
                so = doc_tuan(ma)
                _tim(so, v["id"])["cung_viec"] = chung
                _ghi_tuan(so)
            v["cung_viec"] = chung
        ra.append(v)
    return ra


def them_viec_tu(ma: str, user: dict, tieu_de: str, loai_viec: str = "",
                 han: str = "", gap: bool = False) -> dict:
    """Việc nhân sự tự nhận — không qua luật giao, vào thẳng ĐANG LÀM."""
    with _khoa:
        so = doc_tuan(ma)
        v = _viec_moi(tieu_de, loai_viec, user["ten"])
        v.update({"luc_nhan": v["luc_tao"], "han": _han_hop_le(han), "gap": bool(gap)})
        so["viec"].append(v)
        _ghi_tuan(so)
    ghi_nhat_ky("tu_them_viec", user["ten"],
                {"tuan": ma, "viec": v["id"], "tieu_de": v["tieu_de"]})
    return v


def danh_dau(ma: str, id_viec: str, user: dict,
             gap: bool | None = None, han: str | None = None) -> dict:
    """Đổi dấu GẤP / hạn chót sau khi việc đã tồn tại.

    Ai đổi được: người giao việc đó (hoặc Owner) — vì gấp/hạn là cam kết với người
    cần kết quả. Việc nhân sự TỰ THÊM thì chính chủ tự đặt (việc của họ)."""
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        tu_minh = v["nguon"] == "tu_them" and v["nguoi"] == user["ten"]
        if not (tu_minh or duoc_xac_nhan(v, user)):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới đổi hạn / dấu gấp.")
        if gap is not None:
            v["gap"] = bool(gap)
        if han is not None:
            v["han"] = _han_hop_le(han)
        _ghi_tuan(so)
    ghi_nhat_ky("danh_dau", user["ten"],
                {"tuan": ma, "viec": id_viec, "gap": v["gap"], "han": v["han"]})
    return v


def nhan_viec(ma: str, id_viec: str, user: dict) -> dict:
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        _kiem_chinh_chu(v, user)
        if v["trang_thai"] not in (CHO_NHAN, CHO_PHOI_HOP):
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
        if v["trang_thai"] not in (CHO_NHAN, CHO_PHOI_HOP):
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
        if v["trang_thai"] in (CHO_NHAN, CHO_PHOI_HOP):
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


def chuyen_vao_goal(ma: str, id_viec: str, user: dict, muc_tieu_id: str) -> dict:
    """Gắn một việc đang lẻ vào Goal (Owner 25/08: dùng để gom việc bản cũ vào một
    Goal rồi xóa cả cụm). Quyền như xác nhận việc đó."""
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not duoc_xac_nhan(v, user):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới chuyển được.")
        v["muc_tieu_id"] = muc_tieu_id or ""
        _ghi_tuan(so)
    ghi_nhat_ky("chuyen_vao_goal", user["ten"],
                {"tuan": ma, "viec": id_viec, "muc_tieu": muc_tieu_id})
    return v


def _duoc_sua_de_bai(viec: dict, user: dict) -> bool:
    """Ai sửa được ĐỀ BÀI (tên việc, mô tả): người giao (hoặc Owner). Việc nhân sự
    tự thêm thì chính chủ — cùng luật với `danh_dau`, không đẻ luật mới."""
    tu_minh = viec.get("nguon") == "tu_them" and viec["nguoi"] == user["ten"]
    return tu_minh or duoc_xac_nhan(viec, user)


def sua_viec(ma: str, id_viec: str, user: dict, tieu_de: str | None = None,
             mo_ta: str | None = None, loai_viec: str | None = None) -> dict:
    """Sửa đề bài sau khi việc đã tạo — gõ nhầm tên, hoặc bổ sung mô tả sau.

    Người LÀM không sửa đề bài; họ ghi lưu ý bằng trao đổi (chỉ-thêm, có dấu vết ai
    nói gì lúc nào) — nếu cho cả hai bên sửa chung một ô thì đè nhau, mất chứng cứ.
    """
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not _duoc_sua_de_bai(v, user):
            raise PermissionError("Chỉ người giao việc (hoặc Owner) mới sửa đề bài.")
        if tieu_de is not None and tieu_de.strip():
            v["tieu_de"] = _gon_khoang_trang(tieu_de)[:200]
        if loai_viec is not None and loai_viec.strip():
            v["loai_viec"] = loai_viec.strip()[:60]
        if mo_ta is not None:
            v["mo_ta"] = mo_ta.strip()[:4000]
        _ghi_tuan(so)
    ghi_nhat_ky("sua_viec", user["ten"], {"tuan": ma, "viec": id_viec})
    return v


def _dia_chi_hop_le(dia_chi: str) -> str:
    """Nhận link web hoặc đường NAS. Chặn `javascript:`/`data:` — chuỗi này sẽ đi
    thẳng vào thuộc tính href, nhận bừa là mở cửa cho script chạy trong phiên người
    khác."""
    dc = (dia_chi or "").strip()
    if not dc:
        raise ValueError("Chưa có đường dẫn tài liệu.")
    if (dc.lower().startswith(("http://", "https://"))
            or dc.startswith("\\")            # \máy	hư-mục
            or re.match(r"^[A-Za-z]:[\\/]", dc)):   # G:\… trên máy đã map ổ
        return dc[:500]
    raise ValueError("Chỉ nhận link http(s) hoặc đường NAS trong công ty.")


def them_tai_lieu(ma: str, id_viec: str, user: dict, dia_chi: str,
                  ten: str = "") -> dict:
    """Đính tài liệu vào việc — LƯU ĐƯỜNG DẪN, không chép file.

    Tài liệu công ty đã nằm ở NAS và kho tri thức, mỗi nơi có luật quyền riêng; chép
    bản thứ hai vào Tasky là đẻ thêm một kho phải canh quyền và canh bản mới nhất.
    """
    dc = _dia_chi_hop_le(dia_chi)
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not duoc_doc_trao_doi(v, user):
            raise PermissionError("Bạn không có phần trong việc này.")
        tl = {"id": "tl-" + uuid.uuid4().hex[:6], "dia_chi": dc,
              "ten": (ten or "").strip()[:120] or dc,
              "ai": user["ten"], "luc": _gio()}
        v.setdefault("tai_lieu", []).append(tl)
        _ghi_tuan(so)
    ghi_nhat_ky("them_tai_lieu", user["ten"],
                {"tuan": ma, "viec": id_viec, "dia_chi": dc})
    return tl


def xoa_tai_lieu(ma: str, id_viec: str, user: dict, id_tl: str) -> None:
    """Gỡ một tài liệu: người đã đính, người giao việc, hoặc Owner."""
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        ds = v.get("tai_lieu") or []
        tl = next((x for x in ds if x["id"] == id_tl), None)
        if tl is None:
            raise ValueError("Không thấy tài liệu này.")
        if not (tl["ai"] == user["ten"] or duoc_xac_nhan(v, user)):
            raise PermissionError("Chỉ người đính (hoặc người giao việc) mới gỡ được.")
        v["tai_lieu"] = [x for x in ds if x["id"] != id_tl]
        _ghi_tuan(so)
    ghi_nhat_ky("xoa_tai_lieu", user["ten"],
                {"tuan": ma, "viec": id_viec, "ban_goc": tl})


def duoc_doc_trao_doi(viec: dict, user: dict) -> bool:
    """Ai đọc/viết được cuộc trao đổi trong một việc: NGƯỜI LÀM, NGƯỜI GIAO, Owner.

    Giữ đúng luật 1 (§9.1): đồng nghiệp ngang cấp không xem việc của nhau, nên cũng
    không đọc được trao đổi trong đó.
    """
    return (user["level"] >= OWNER_LEVEL
            or viec["nguoi"] == user["ten"]
            or viec.get("nguoi_giao") == user["ten"])


def them_trao_doi(ma: str, id_viec: str, user: dict, chu: str) -> dict:
    """Nhắn một câu vào việc. CHỈ THÊM — không sửa, không xóa: trao đổi là chứng cứ
    của quá trình, sửa được thì mất tác dụng đối chiếu (cùng lệ nhật ký của hệ)."""
    chu = (chu or "").strip()
    if not chu:
        raise ValueError("Chưa nhập nội dung.")
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        if not duoc_doc_trao_doi(v, user):
            raise PermissionError("Bạn không có phần trong việc này.")
        v.setdefault("trao_doi", []).append(
            {"id": "td-" + uuid.uuid4().hex[:6], "ai": user["ten"],
             "ten": user.get("ho_ten") or user["ten"],
             "luc": _gio(), "chu": chu[:1000]})
        _ghi_tuan(so)
    ghi_nhat_ky("trao_doi", user["ten"], {"tuan": ma, "viec": id_viec})
    return v["trao_doi"][-1]


def doc_trao_doi(ma: str, id_viec: str, user: dict) -> list[dict]:
    v = _tim(doc_tuan(ma), id_viec)
    if not duoc_doc_trao_doi(v, user):
        raise PermissionError("Bạn không có phần trong việc này.")
    return v.get("trao_doi") or []


def duoc_xoa(viec: dict, user: dict) -> tuple[bool, str, str]:
    """Xóa HẲN một việc. Trả (được?, lý do, loại lỗi) — loại là "quyen" hoặc
    "trang_thai" để chỗ gọi ném đúng ngoại lệ, KHÔNG dò chuỗi tiếng Việt.

    Luật (theo lệ gỡ-mềm-trước của hệ):
    - Việc CHƯA AI LÀM (chưa giao / chờ nhận / chờ phối hợp) hoặc đã đóng vô hại
      (bị từ chối / đã hủy) → người giao, chính chủ, hoặc Owner xóa được. Gõ nhầm
      thì xóa cho sạch, không để lại rác.
    - Việc ĐANG LÀM / ĐÃ BÁO XONG → KHÔNG xóa; dùng Hủy kèm lý do. Người ta đã bỏ
      công, xóa trắng là xóa cả dấu vết công đó.
    - Việc ĐÃ NGHIỆM THU hoặc ĐÃ DỜI → chỉ Owner, vì xóa sẽ đổi số của báo cáo tuần
      đã chốt (hoặc bỏ mồ côi việc đã sinh ở tuần sau).
    """
    la_chu = viec["nguoi"] == user["ten"]
    la_nguoi_giao = viec.get("nguoi_giao") == user["ten"]
    la_owner = user["level"] >= OWNER_LEVEL
    tt = viec["trang_thai"]

    # Owner là chủ hệ — dọn được mọi việc ở mọi trạng thái (cần cho việc dọn Goal
    # test / tạo nhầm). Nhật ký vẫn giữ nguyên bản nên không mất trắng.
    if la_owner:
        return True, "", ""

    if tt in (XAC_NHAN, DOI):
        if not la_owner:
            return (False, "Việc đã nghiệm thu / đã dời nằm trong số báo cáo — "
                    "chỉ Owner mới xóa được.", "quyen")
        return True, "", ""
    if tt in (DANG_LAM, BAO_XONG):
        # Việc TỰ THÊM là việc của chính mình, chưa ai nghiệm thu → chủ nó xóa được;
        # việc người khác giao thì phải Hủy kèm lý do (giữ dấu vết công đã bỏ ra).
        if viec.get("nguon") == "tu_them" and (la_chu or la_owner):
            return True, "", ""
        return (False, "Việc đang làm thì dùng Hủy kèm lý do, không xóa trắng.",
                "trang_thai")
    if la_owner or la_nguoi_giao or la_chu:
        return True, "", ""
    return False, "Chỉ người giao việc (hoặc Owner) mới xóa được.", "quyen"


def xoa_viec(ma: str, id_viec: str, user: dict) -> dict:
    """Xóa hẳn khỏi sổ tuần. Nhật ký giữ NGUYÊN BẢN việc bị xóa — sai thì còn đường
    dựng lại bằng tay, không mất trắng."""
    with _khoa:
        so = doc_tuan(ma)
        v = _tim(so, id_viec)
        duoc, vi_sao, loai = duoc_xoa(v, user)
        if not duoc:
            raise (PermissionError(vi_sao) if loai == "quyen" else ValueError(vi_sao))
        so["viec"] = [x for x in so["viec"] if x["id"] != id_viec]
        _ghi_tuan(so)
    ghi_nhat_ky("xoa_viec", user["ten"], {"tuan": ma, "viec": id_viec, "ban_goc": v})
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
                    if v["nguoi"] == nguoi
                    and v["trang_thai"] in (CHO_NHAN, CHO_PHOI_HOP, DANG_LAM, BAO_XONG)]
        if con_treo:
            raise ValueError(
                f"Còn {len(con_treo)} việc chưa xử lý — xác nhận, dời hoặc hủy trước khi đóng tuần.")
        so["dong"][nguoi] = {"luc": _gio(), "boi": user["ten"]}
        _ghi_tuan(so)
    ghi_nhat_ky("dong_tuan", user["ten"], {"tuan": ma, "cua": nguoi})
    return so["dong"][nguoi]


def mo_lai_tuan(ma: str, nguoi: str, user: dict) -> None:
    """THU LẠI việc đóng tuần (Owner yêu cầu 24/08) — đóng nhầm thì mở lại được,
    không phải chờ ai.

    Quyền: đúng người đóng được tuần đó mới mở lại được (leader quản người đó, hoặc
    Owner). Sổ giữ vết CẢ hai chiều trong nhat-ky.jsonl — mở lại là chuyện bình
    thường, nhưng phải biết ai mở và lúc nào."""
    with _khoa:
        so = doc_tuan(ma)
        if nguoi not in so.get("dong", {}):
            raise ValueError("Tuần của người này chưa đóng.")
        if user["level"] < OWNER_LEVEL:
            cua_ho = [v for v in so["viec"] if v["nguoi"] == nguoi]
            if cua_ho and not any(duoc_xac_nhan(v, user) for v in cua_ho):
                raise PermissionError("Bạn không quản người này — không mở lại được.")
        cu = so["dong"].pop(nguoi)
        _ghi_tuan(so)
    ghi_nhat_ky("mo_lai_tuan", user["ten"],
                {"tuan": ma, "cua": nguoi, "dong_boi": cu.get("boi", ""),
                 "dong_luc": cu.get("luc", "")})


# ---------- đọc theo phạm vi + thống kê ----------

def viec_cua(ma: str, ten: str) -> list[dict]:
    return [v for v in doc_tuan(ma)["viec"] if v["nguoi"] == ten]


def cho_xac_nhan(ma: str, user: dict) -> list[dict]:
    """Việc đang chờ CHÍNH user này xác nhận (dùng cho màn Giao việc)."""
    return [v for v in doc_tuan(ma)["viec"]
            if v["trang_thai"] == BAO_XONG and duoc_xac_nhan(v, user)]


def cac_loai_viec(so_tuan: int = 12) -> list[str]:
    """Danh sách loại việc ĐÃ DÙNG (mới nhất trước) để gợi ý khi khai việc — danh
    mục tự lớn dần, gõ tên mới là thành loại mới (khuôn tag từ khóa của AI Agent).
    Quét vài tuần gần nhất là đủ; kho rỗng → [] chứ không bịa danh mục mẫu."""
    ra: list[str] = []
    for ma in cac_tuan_gan(so_tuan):
        for v in doc_tuan(ma)["viec"]:
            loai = (v.get("loai_viec") or "").strip()
            if loai and loai not in ra:
                ra.append(loai)
    return ra


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
        "chua_nhan": sum(1 for v in mau_so
                         if v["trang_thai"] in (CHO_NHAN, CHO_PHOI_HOP)),
        "phoi_hop": sum(1 for v in mau_so if v["nguon"] == "phoi_hop"),
        "gap": sum(1 for v in mau_so if v.get("gap")
                   and v["trang_thai"] != XAC_NHAN),
        "qua_han": sum(1 for v in mau_so if tinh_han(v)["chu"].startswith("Quá hạn")),
        "bi_tu_choi": sum(1 for v in ds if v["trang_thai"] == TU_CHOI),
        "bi_huy": sum(1 for v in ds if v["trang_thai"] == HUY),
        "ket": sum(1 for v in mau_so if v["so_lan_doi"] >= DOI_LA_KET),
        "buoc_tong": len(buoc),
        "buoc_xong": sum(1 for b in buoc if b["xong"]),
        "tu_xac_nhan": any(v["tu_xac_nhan"] for v in xong),
        "ti_le": round(100 * len(xong) / len(mau_so)) if mau_so else None,
        "da_dong": ten in doc_tuan(ma)["dong"],
    }


def nhom_viec(ds_viec: list[dict]) -> dict:
    """Chia việc của một mục tiêu thành BA nhóm theo mức cần hành động (Owner chốt
    25/08: 10 việc đổ một mạch thì dễ miss).

    - `can_xu_ly`: việc của MANAGER — chưa phân công, chưa ai nhận, quá hạn, chờ nghiệm thu
    - `dang_chay`: có người đang làm, chỉ cần liếc
    - `xong`: đã nghiệm thu (UI thu gọn)
    """
    can, chay, xong = [], [], []
    for v in ds_viec:
        tt = v["trang_thai"]
        if tt == XAC_NHAN:
            xong.append(v)
        elif tt in (CHUA_GIAO, CHO_NHAN, CHO_PHOI_HOP, BAO_XONG, TU_CHOI):
            # TỪ CHỐI nằm ở đây để leader ĐỌC ĐƯỢC LÝ DO rồi giao lại — trước đó nó
            # rơi ra ngoài cả ba nhóm nên biến mất khỏi màn hình (Owner báo 25/08)
            can.append(v)
        elif tt == DANG_LAM:
            (can if tinh_han(v)["muc"] == "cap" else chay).append(v)
    return {"can_xu_ly": can, "dang_chay": chay, "xong": xong}


# ---- BOARD KANBAN (§17 bước 2, Owner chốt 26/08) ----------------------------
# Cột của board = một TRỤC. Kéo thẻ sang cột khác nghĩa là gì thì do trục quyết,
# và mỗi nghĩa đều là một hàm ĐÃ CÓ ở dưới — board không đẻ luật mới.
TRUC = ("trang_thai", "goal", "nguoi")

COT_TRANG_THAI = (
    ("chua_nhan", "Chưa nhận", (CHUA_GIAO, CHO_NHAN, CHO_PHOI_HOP, TU_CHOI)),
    ("dang_lam", "Đang làm", (DANG_LAM,)),
    ("bao_xong", "Báo xong", (BAO_XONG,)),
    ("xac_nhan", "Đã nghiệm thu", (XAC_NHAN,)),
)


def cot_theo_trang_thai(ds_viec: list[dict]) -> list[dict]:
    """Bốn cột theo khâu. Việc ĐÃ DỜI sang tuần sau không hiện — bản mới ở tuần sau
    mới là bản đang sống (cùng lệ với báo cáo)."""
    ra = []
    for ma_cot, ten, cac_tt in COT_TRANG_THAI:
        ra.append({"ma": ma_cot, "ten": ten,
                   "viec": [v for v in ds_viec if v["trang_thai"] in cac_tt]})
    return ra


def cot_theo_goal(ds_viec: list[dict], ds_mt: list[dict]) -> list[dict]:
    """Mỗi Goal một cột (kiểu Trello). Chỉ dựng cột cho Goal CÓ TRONG danh sách
    truyền vào — tức đã lọc quyền ở tầng gọi."""
    theo = {}
    for v in ds_viec:
        theo.setdefault(v.get("muc_tieu_id") or "", []).append(v)
    ra = [{"ma": m["id"], "ten": m["tieu_de"], "viec": theo.get(m["id"], [])}
          for m in ds_mt]
    if theo.get(""):        # việc cũ chưa gắn Goal nào — không giấu đi
        ra.append({"ma": "", "ten": "Chưa thuộc Goal nào", "viec": theo[""]})
    return ra


def cot_theo_nguoi(ds_viec: list[dict], ten_hien: dict | None = None) -> list[dict]:
    """Mỗi người một cột — nhìn ra ai đang ôm bao nhiêu việc. Cột 'Chưa giao' đứng
    đầu vì đó là việc cần hành động ngay."""
    ten_hien = ten_hien or {}
    theo = {}
    for v in ds_viec:
        theo.setdefault(v.get("nguoi") or "", []).append(v)
    ra = [{"ma": "", "ten": "Chưa giao", "viec": theo.pop("", [])}] if theo.get("") else []
    for ten in sorted(theo, key=lambda t: ten_hien.get(t, t).lower()):
        ra.append({"ma": ten, "ten": ten_hien.get(ten, ten), "viec": theo[ten]})
    return ra


def dung_cot(ds_viec: list[dict], truc: str, ds_mt: list[dict] | None = None,
             ten_hien: dict | None = None) -> list[dict]:
    """Dựng cột theo trục. Trục lạ → về trạng thái (mặc định an toàn)."""
    if truc == "goal":
        return cot_theo_goal(ds_viec, ds_mt or [])
    if truc == "nguoi":
        return cot_theo_nguoi(ds_viec, ten_hien)
    return cot_theo_trang_thai(ds_viec)


# Bộ lọc "việc cần xử lý" — thông báo bấm vào là mở ĐÚNG danh sách này, thay vì
# ném người dùng sang trang báo cáo rồi để họ tự mò (Owner 29/08).
LOC_VIEC = ("qua_han", "cho_xac_nhan", "chua_nhan", "gap", "bi_tu_choi", "viec_ket")


def loc_viec(ds_viec: list[dict], loc: str, user: dict | None = None,
             hom_nay: date | None = None) -> list[dict]:
    """Lọc theo tình huống cần hành động. Luật ở đây, UI chỉ truyền tên bộ lọc."""
    song = [v for v in ds_viec
            if v["trang_thai"] in (CHO_NHAN, CHO_PHOI_HOP, DANG_LAM, BAO_XONG)]
    if loc == "qua_han":
        return [v for v in song if tinh_han(v, hom_nay)["chu"].startswith("Quá hạn")]
    if loc == "cho_xac_nhan":
        return [v for v in ds_viec if v["trang_thai"] == BAO_XONG
                and (user is None or duoc_xac_nhan(v, user))]
    if loc == "chua_nhan":
        return [v for v in ds_viec if v["trang_thai"] in (CHUA_GIAO, CHO_NHAN, CHO_PHOI_HOP)]
    if loc == "gap":
        return [v for v in song if v.get("gap")]
    if loc == "bi_tu_choi":
        return [v for v in ds_viec if v["trang_thai"] == TU_CHOI]
    if loc == "viec_ket":
        return [v for v in song if v["so_lan_doi"] >= DOI_LA_KET]
    return ds_viec


def keo_duoc(viec: dict, truc: str, cot_dich: str, user: dict) -> tuple[bool, str]:
    """Kéo thẻ sang cột `cot_dich` có hợp lệ không — HỎI TRƯỚC KHI KÉO để UI khóa
    sẵn, nhưng server VẪN kiểm lại lúc thả (chốt thật ở server).

    Không nới một ly quyền nào: mỗi nước đi ứng đúng một hàm hiện có, luật của hàm
    đó là luật cuối cùng."""
    tt = viec["trang_thai"]
    if truc == "trang_thai":
        if cot_dich == "dang_lam":              # = nhận việc
            return (viec["nguoi"] == user["ten"] and tt in (CHO_NHAN, CHO_PHOI_HOP),
                    "Chỉ người được giao mới nhận việc này.")
        if cot_dich == "bao_xong":              # = báo xong
            return (viec["nguoi"] == user["ten"] and tt == DANG_LAM,
                    "Chỉ người đang làm mới báo xong.")
        if cot_dich == "xac_nhan":              # = nghiệm thu
            return (tt == BAO_XONG and duoc_xac_nhan(viec, user),
                    "Chỉ người giao việc (hoặc Owner) mới nghiệm thu.")
        if cot_dich == "chua_nhan":             # = trả lại việc
            return (tt in (BAO_XONG, DANG_LAM) and duoc_xac_nhan(viec, user),
                    "Chỉ người giao việc mới trả lại.")
        return False, "Không đổi được sang cột này."
    if truc == "goal":
        return (duoc_xac_nhan(viec, user) or viec.get("nguoi_giao") == user["ten"],
                "Chỉ người giao việc (hoặc Owner) mới chuyển việc sang Goal khác.")
    if truc == "nguoi":
        if tt not in (CHUA_GIAO, CHO_NHAN, TU_CHOI):
            return False, ("Việc đang làm dở thì Trả lại hoặc Hủy trước, "
                           "rồi mới giao cho người khác.")
        return (viec.get("nguoi_giao") == user["ten"] or user["level"] >= OWNER_LEVEL,
                "Chỉ người giao việc (hoặc Owner) mới giao lại.")
    return False, "Trục không hợp lệ."


def nhom_cho_leader(ma: str, user: dict, ds_nguoi: list[dict]) -> dict:
    """Việc của QUÂN mình, gom theo mức cần hành động — cùng ngôn ngữ với màn Goal.

    "Cần bạn xử lý" ở đây là việc của LEADER: chờ mình xác nhận, quá hạn, chưa ai
    nhận, việc kẹt. Việc nhân sự đang làm đúng hạn thì chỉ cần liếc."""
    trong = {n["ten"] for n in ds_nguoi}
    ds = [v for v in doc_tuan(ma)["viec"] if v["nguoi"] in trong]
    n = nhom_viec(sap_xep(ds))
    # việc chưa ai nhận / chờ xác nhận đã nằm ở can_xu_ly nhờ nhom_viec
    return {**n, "canh_bao": [c for c in (
        {"muc_do": "cap", "chu": f"{len([v for v in ds if tinh_han(v)['chu'].startswith('Quá hạn')])} quá hạn"},
        {"muc_do": "luu_y", "chu": f"{len([v for v in ds if v['trang_thai'] == BAO_XONG])} chờ bạn xác nhận"},
        {"muc_do": "luu_y", "chu": f"{len([v for v in ds if v['trang_thai'] == CHO_NHAN])} chưa nhận"},
        {"muc_do": "cap", "chu": f"{len([v for v in ds if v['so_lan_doi'] >= DOI_LA_KET and v['trang_thai'] in (CHO_NHAN, DANG_LAM, BAO_XONG)])} việc kẹt"},
    ) if not c["chu"].startswith("0 ")]}


def chua_giao(ma: str, muc_tieu_id: str = "") -> list[dict]:
    """Việc đã chẻ mà chưa có người — Manager cần thấy để giao."""
    return [v for v in doc_tuan(ma)["viec"]
            if v["trang_thai"] == CHUA_GIAO
            and (not muc_tieu_id or v.get("muc_tieu_id") == muc_tieu_id)]


def con_treo(ma: str, user: dict) -> list[dict]:
    """Việc CHƯA ngã ngũ mà user này có quyền xử lý — leader phải dời/hủy hết mới
    đóng được tuần cho người đó."""
    return [v for v in doc_tuan(ma)["viec"]
            if v["trang_thai"] in (CHO_NHAN, CHO_PHOI_HOP, DANG_LAM)
            and duoc_xac_nhan(v, user)]


def kho_quy_trinh(so_tuan: int = 26, du_de_rut: int = 3) -> list[dict]:
    """NỀN cho §5 — mỗi loại việc đã tích được bao nhiêu checklist của việc ĐÃ HOÀN
    THÀNH, và bước nào lặp nhiều nhất.

    Vòng này CHỈ ĐẾM và bày ra, KHÔNG đề xuất gì: dưới `du_de_rut` lần thì nói thẳng
    "chưa đủ tiền lệ". Chuẩn hóa bước để gom = thường hóa + gộp khoảng trắng (đủ để
    đếm; gộp bước gần giống là việc của vòng sau, làm khi có dữ liệu thật).
    """
    gom: dict[str, dict] = {}
    for ma in cac_tuan_gan(so_tuan):
        for v in doc_tuan(ma)["viec"]:
            loai = (v.get("loai_viec") or "").strip()
            if not loai or v["trang_thai"] != XAC_NHAN or not v["checklist"]:
                continue
            m = gom.setdefault(loai, {"loai": loai, "so_checklist": 0, "buoc": {}})
            m["so_checklist"] += 1
            for khoa in {" ".join((b["noi_dung"] or "").lower().split())
                         for b in v["checklist"] if b.get("noi_dung")}:
                o = m["buoc"].setdefault(khoa, {"lan": 0, "mau": ""})
                o["lan"] += 1
                o["mau"] = o["mau"] or next(
                    b["noi_dung"] for b in v["checklist"]
                    if " ".join((b["noi_dung"] or "").lower().split()) == khoa)
    ra = []
    for m in gom.values():
        hay_nhat = max(m["buoc"].values(), key=lambda o: o["lan"], default=None)
        ra.append({"loai": m["loai"], "so_checklist": m["so_checklist"],
                   "du_de_rut": m["so_checklist"] >= du_de_rut,
                   "con_thieu": max(0, du_de_rut - m["so_checklist"]),
                   "buoc_hay_nhat": hay_nhat["mau"] if hay_nhat else "",
                   "lan_lap": hay_nhat["lan"] if hay_nhat else 0})
    return sorted(ra, key=lambda m: (-m["so_checklist"], m["loai"]))


def tong_hop(bang: list[dict]) -> dict:
    """Số cấp công ty/bộ phận từ bảng báo cáo. Không ai có việc → ti_le None."""
    co_viec = [d for d in bang if d["so_viec"]]
    tong_viec = sum(d["so_viec"] for d in co_viec)
    tong_xong = sum(d["xong"] for d in co_viec)
    return {"so_nguoi": len(bang), "co_viec": len(co_viec),
            "chua_co_viec": len(bang) - len(co_viec),
            "tong_viec": tong_viec, "tong_xong": tong_xong,
            "tong_buoc": sum(d["buoc_tong"] for d in bang),
            "tong_ket": sum(d["ket"] for d in bang),
            "da_dong": sum(1 for d in bang if d["da_dong"]),
            "ti_le": round(100 * tong_xong / tong_viec) if tong_viec else None}


def tong_hop_quan(ma: str, ds_nguoi: list[dict], user: dict) -> dict:
    """Số của QUÂN mình trong tuần — cho hàng ô tổng hợp ở màn Việc của tôi.

    Quản lý mở màn đó thấy 4 ô toàn 0 vì họ không có việc cá nhân (Owner báo
    29/08). Bốn số này nói về người mình quản, và mỗi số đều mở được ra danh
    sách việc tương ứng (?can=) — không phải con số cụt.
    """
    trong = {n["ten"] for n in ds_nguoi}
    ds = [v for v in doc_tuan(ma)["viec"] if v["nguoi"] in trong]
    mau_so = [v for v in ds if v["trang_thai"] in TRONG_MAU_SO]
    xong = [v for v in mau_so if v["trang_thai"] == XAC_NHAN]
    return {
        "so_nguoi": len(ds_nguoi),
        "so_viec": len(mau_so),
        "xong": len(xong),
        # van chống bịa: không có việc nào thì KHÔNG có tỉ lệ, UI hiện "—"
        "ti_le": round(100 * len(xong) / len(mau_so)) if mau_so else None,
        "qua_han": len(loc_viec(ds, "qua_han")),
        "cho_xac_nhan": len(loc_viec(ds, "cho_xac_nhan", user)),
        "chua_nhan": len(loc_viec(ds, "chua_nhan")),
        "gap": len(loc_viec(ds, "gap")),
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
