# -*- coding: utf-8 -*-
"""Di trú nhân sự V2 → iam.db (KE_HOACH_THAY_THE bước 2b): hồ sơ ho_so.json +
tài khoản users.txt + bảng tick phan_quyen.json — MỘT script, MẶC ĐỊNH CHỈ LIỆT KÊ
(bài học gan_tang_nguon hệ cũ: liệt kê trước, --chay mới ghi).

Chạy:  python -m nen.iam.di_tru_v2 "C:\\OutlierY\\apps\\AI AGENT\\agent-app" [--chay] [--don-seed]

Luật chuyển đổi (đối chiếu schema V2 → V3):
- trang_thai: dang_lam→hoat_dong · da_nghi→nghi · cho_duyet giữ · tu_choi → BỎ QUA
  (V3 không có trạng thái này — cảnh báo để xử lý tay).
- bo_phan "IT" → "Kinh doanh" (quyết định 04/08 hệ cũ: IT là VỊ TRÍ thuộc Kinh doanh;
  users.txt của lamtn cũng đã ghi Kinh doanh — hai nguồn về một mối).
- chuc_danh (V2) → vi_tri (V3); cap_bac số "2/3/4" → staff/leader/manager, hồ sơ
  thiếu thì suy từ level tài khoản nối (4→manager 3→leader 2→staff 1→intern;
  level 5 để trống — Owner đứng trên thang cấp bậc).
- Tài khoản: INSERT thẳng GIỮ NGUYÊN hash bcrypt (khuôn nhap_users_txt — không ai
  phải đổi mật khẩu); tên đã có trong iam.db (Bot…) → bỏ qua.
- Tick quyen_override: hd:radary:xoa → radary/toan_quyen (V3 đổi tên hành động);
  hd:seo:* GIỮ slug 'seo' chờ app SEO Optimize vào V3 — nếu V3 chốt slug khác thì
  UPDATE app_slug các dòng này. ly_do bắt buộc → tự sinh "Di trú V2 (khóa gốc)".

SEED ĐỤNG MÃ: hồ sơ đích cùng mã NS nhưng KHÁC họ tên (bản thử nghiệm dựng lúc
khởi tạo V3) + tài khoản nối vào hồ sơ đó mà không có trong users.txt → chỉ xóa
khi --don-seed; không có cờ thì DỪNG, không ghi gì (kể cả có --chay).

Idempotent: chạy lại bỏ qua mọi bản ghi đã có. Cuối luôn in đối chiếu số trước/sau.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from nen.iam import iam

TRANG_THAI_MAP = {"dang_lam": "hoat_dong", "da_nghi": "nghi", "cho_duyet": "cho_duyet"}
BO_PHAN_MAP = {"IT": "Kinh doanh"}
CAP_BAC_SO = {"1": "intern", "2": "staff", "3": "leader", "4": "manager"}
LEVEL_CAP_BAC = {1: "intern", 2: "staff", 3: "leader", 4: "manager"}  # 5 → ""
TICK_DOI_TEN = {("radary", "xoa"): "toan_quyen"}
AI_GAN = "(di tru V2)"


def _doc_users_txt(duong: Path) -> list[dict]:
    ds = []
    for dong in duong.read_text(encoding="utf-8").splitlines():
        dong = dong.strip()
        if not dong or dong.startswith("#"):
            continue
        phan = dong.split(":")
        if len(phan) < 4:
            continue
        ds.append({"ten": phan[0], "mk_bcrypt": phan[1],
                   "bo_phan": BO_PHAN_MAP.get(phan[2], phan[2]),
                   "level": int(phan[3]),
                   "phai_doi": len(phan) > 4 and phan[4].strip() == "1"})
    return ds


def _doc_nguon(thu_muc: Path) -> tuple[list[dict], dict, dict]:
    users = _doc_users_txt(thu_muc / "users.txt")
    ho_so = json.loads((thu_muc / "nhan-su" / "ho_so.json").read_text(encoding="utf-8"))
    duong_tick = thu_muc / "kho-tai-lieu" / "phan_quyen.json"
    tick = json.loads(duong_tick.read_text(encoding="utf-8")) if duong_tick.exists() else {}
    return users, ho_so, tick


def _cap_bac(hs: dict, level_tk: int | None) -> str:
    if hs.get("cap_bac") in CAP_BAC_SO:
        return CAP_BAC_SO[hs["cap_bac"]]
    if level_tk is not None:
        return LEVEL_CAP_BAC.get(level_tk, "")
    return ""


def di_tru(thu_muc: Path, chay: bool = False, don_seed: bool = False) -> dict:
    """Trả report dict; chay=False thì CHỈ lập kế hoạch, không ghi một byte."""
    users, ho_so, tick = _doc_nguon(thu_muc)
    conn = iam.ket_noi()          # tự chạy migration 005 (cột sdt/email/planner_id)
    try:
        return _di_tru(conn, users, ho_so, tick, chay, don_seed)
    finally:
        conn.close()


def _di_tru(conn, users: list[dict], ho_so: dict, tick: dict,
            chay: bool, don_seed: bool) -> dict:
    level_theo_ten = {u["ten"]: u["level"] for u in users}
    ma_theo_ten = {hs["ten_dang_nhap"]: ma for ma, hs in ho_so.items()
                   if hs.get("ten_dang_nhap")}
    rp = {"nguoi_moi": [], "nguoi_bo_qua": [], "tk_moi": [], "tk_bo_qua": [],
          "tick_moi": [], "tick_bo_qua": [], "seed_nguoi": [], "seed_tk": [],
          "canh_bao": [], "da_ghi": False}

    # --- kế hoạch NGƯỜI ---
    ke_hoach_nguoi = []
    for ma, hs in sorted(ho_so.items()):
        trang_thai = TRANG_THAI_MAP.get(hs.get("trang_thai", ""))
        if trang_thai is None:
            rp["canh_bao"].append(
                f"{ma}: trạng thái '{hs.get('trang_thai')}' không có ở V3 — BỎ QUA, xử lý tay")
            continue
        bo_phan = BO_PHAN_MAP.get(hs.get("bo_phan", ""), hs.get("bo_phan", ""))
        if bo_phan != hs.get("bo_phan"):
            rp["canh_bao"].append(f"{ma}: bộ phận '{hs.get('bo_phan')}' → '{bo_phan}'")
        ten_tk = hs.get("ten_dang_nhap", "")
        ke_hoach_nguoi.append({
            "ma": ma, "ho_ten": hs.get("ho_ten", ""), "bo_phan": bo_phan,
            "vi_tri": hs.get("chuc_danh", ""), "trang_thai": trang_thai,
            "ghi_chu": hs.get("ghi_chu", ""), "ngay_vao": hs.get("ngay_vao", ""),
            "cap_bac": _cap_bac(hs, level_theo_ten.get(ten_tk)),
            "sdt": hs.get("sdt", ""), "email": hs.get("email", ""),
            "planner_id": hs.get("planner_id", ""), "ten_tk": ten_tk})

    # --- dò SEED đụng mã ---
    for kh in ke_hoach_nguoi:
        cu = conn.execute("SELECT * FROM nguoi WHERE ma=?", (kh["ma"],)).fetchone()
        if cu and cu["ho_ten"] != kh["ho_ten"]:
            rp["seed_nguoi"].append(f"{kh['ma']} (đích: {cu['ho_ten']} ≠ V2: {kh['ho_ten']})")
    ma_seed = [s.split(" ")[0] for s in rp["seed_nguoi"]]
    if ma_seed:
        cho = ",".join("?" for _ in ma_seed)
        for r in conn.execute(
                f"SELECT ten, nguoi_ma FROM tai_khoan WHERE nguoi_ma IN ({cho})", ma_seed):
            if r["ten"] not in level_theo_ten:
                rp["seed_tk"].append(f"{r['ten']} (nối {r['nguoi_ma']})")
    if rp["seed_nguoi"] and not don_seed:
        rp["canh_bao"].append(
            "ĐỤNG MÃ với bản ghi seed ở đích — chạy lại kèm --don-seed để xóa seed rồi nạp; "
            "chưa ghi gì.")
        return rp

    # --- phân loại mới/bỏ qua (idempotent) ---
    for kh in ke_hoach_nguoi:
        cu = conn.execute("SELECT ho_ten FROM nguoi WHERE ma=?", (kh["ma"],)).fetchone()
        if cu and kh["ma"] not in ma_seed:
            rp["nguoi_bo_qua"].append(kh["ma"])
        else:
            rp["nguoi_moi"].append(kh)
    for u in users:
        # seed_tk chỉ chứa tài khoản KHÔNG có trong users.txt (theo cách dựng) —
        # nên tên đã có trong đích luôn là bỏ-qua idempotent, không đụng seed.
        if iam.lay_tai_khoan(conn, u["ten"]):
            rp["tk_bo_qua"].append(u["ten"])
        else:
            rp["tk_moi"].append(u)
    for ten, o in sorted(tick.items()):
        for khoa, cho_phep in sorted(o.items()):
            if not khoa.startswith("hd:") or khoa.count(":") != 2:
                rp["canh_bao"].append(f"tick '{khoa}' của {ten} không phải khóa hd: — BỎ QUA")
                continue
            _, slug, hd = khoa.split(":")
            hd = TICK_DOI_TEN.get((slug, hd), hd)
            co = conn.execute(
                "SELECT 1 FROM quyen_override WHERE ten_tai_khoan=? AND app_slug=? "
                "AND hanh_dong=?", (ten, slug, hd)).fetchone()
            muc = {"ten": ten, "slug": slug, "hd": hd, "cho_phep": bool(cho_phep),
                   "khoa_goc": khoa}
            (rp["tick_bo_qua"] if co else rp["tick_moi"]).append(muc)

    if not chay:
        return rp

    # --- THỰC THI (một transaction: xóa seed → người → tài khoản → tick) ---
    with conn:
        for s in rp["seed_tk"]:
            ten = s.split(" ")[0]
            conn.execute("DELETE FROM tai_khoan WHERE ten=?", (ten,))
            conn.execute("DELETE FROM quyen_override WHERE ten_tai_khoan=?", (ten,))
        for ma in ma_seed:
            conn.execute("DELETE FROM nguoi WHERE ma=?", (ma,))
        for kh in rp["nguoi_moi"]:
            conn.execute(
                "INSERT INTO nguoi (ma, ho_ten, bo_phan, vi_tri, trang_thai, tao_luc, "
                "ghi_chu, ngay_sinh, cccd, dia_chi, ngay_vao, cap_bac, sdt, email, "
                "planner_id) VALUES (?,?,?,?,?,?,?,'','','',?,?,?,?,?)",
                (kh["ma"], kh["ho_ten"], kh["bo_phan"], kh["vi_tri"], kh["trang_thai"],
                 iam._gio(), kh["ghi_chu"], kh["ngay_vao"], kh["cap_bac"], kh["sdt"],
                 kh["email"], kh["planner_id"]))
        for u in rp["tk_moi"]:
            conn.execute(
                "INSERT INTO tai_khoan (ten, mk_bcrypt, nguoi_ma, bo_phan, level, "
                "admin_uy_quyen, phai_doi_mk, khoa, tao_luc) VALUES (?,?,?,?,?,0,?,0,?)",
                (u["ten"], u["mk_bcrypt"], ma_theo_ten.get(u["ten"]), u["bo_phan"],
                 u["level"], int(u["phai_doi"]), iam._gio()))
        for t in rp["tick_moi"]:
            conn.execute(
                "INSERT INTO quyen_override (ten_tai_khoan, app_slug, hanh_dong, "
                "cho_phep, ly_do, ai_gan, luc) VALUES (?,?,?,?,?,?,?)",
                (t["ten"], t["slug"], t["hd"], int(t["cho_phep"]),
                 f"Di trú V2 ({t['khoa_goc']})", AI_GAN, iam._gio()))
    iam.ghi_nhat_ky(conn, AI_GAN, "di_tru_v2",
                    f"nguoi +{len(rp['nguoi_moi'])} · tai_khoan +{len(rp['tk_moi'])} · "
                    f"tick +{len(rp['tick_moi'])} · seed -{len(ma_seed)}/-{len(rp['seed_tk'])}")
    rp["da_ghi"] = True
    return rp


def _in(rp: dict) -> None:
    print(f"Người:      +{len(rp['nguoi_moi'])} mới, {len(rp['nguoi_bo_qua'])} đã có")
    print(f"Tài khoản:  +{len(rp['tk_moi'])} mới, {len(rp['tk_bo_qua'])} đã có")
    print(f"Tick quyền: +{len(rp['tick_moi'])} mới, {len(rp['tick_bo_qua'])} đã có")
    for kh in rp["nguoi_moi"]:
        print(f"  {kh['ma']}  {kh['ho_ten']:<28} {kh['bo_phan']:<22} "
              f"{kh['vi_tri']:<20} {kh['trang_thai']} ← {kh['ten_tk'] or '(chưa nối)'}")
    for t in rp["tick_moi"]:
        print(f"  tick {t['ten']:<16} {t['slug']}/{t['hd']} = {t['cho_phep']}")
    if rp["seed_nguoi"]:
        print("SEED đụng mã:", "; ".join(rp["seed_nguoi"]),
              "| tài khoản seed:", "; ".join(rp["seed_tk"]) or "(không)")
    for c in rp["canh_bao"]:
        print("⚠", c)
    print("ĐÃ GHI." if rp["da_ghi"] else "CHƯA GHI (thêm --chay để thực thi).")


if __name__ == "__main__":
    tham_so = [t for t in sys.argv[1:] if not t.startswith("--")]
    if len(tham_so) != 1:
        print('Cách dùng: python -m nen.iam.di_tru_v2 "<thư mục agent-app>" [--chay] [--don-seed]')
        sys.exit(1)
    rp = di_tru(Path(tham_so[0]), chay="--chay" in sys.argv, don_seed="--don-seed" in sys.argv)
    _in(rp)
    if rp["seed_nguoi"] and not rp["da_ghi"] and "--don-seed" not in sys.argv:
        sys.exit(2)
