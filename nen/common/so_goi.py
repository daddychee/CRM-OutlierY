# -*- coding: utf-8 -*-
"""SỔ GỌI API (01/09/2026) — usage THẬT cho Command Center.

Mọi call ra dịch vụ ngoài ghi MỘT DÒNG JSON-lines:
  {luc, app, dich_vu, duoi, viec, model, units, ms, ok, ma_loi}
- dich_vu: "youtube" / "llm" / tên khác — mở, không enum cứng.
- duoi: 4 ký tự cuối của key (app không cần biết id két; Command Center join
  với két theo đuôi — két đã lưu đuôi 4).
- Đường ghi: app repo cha gọi thẳng ghi(); app tự đủ (radary/seo/content…)
  POST /api/so-goi loopback (khuôn heartbeat — không session, bọc try phía
  app: sổ chết không được làm hỏng việc thật).

File data/logs/so-goi/YYYY/MM/YYYY-MM-DD.log (khuôn nhat_ky, append 1 dòng
nguyên tử mức OS). Sống/chết của key = CALL THẬT gần nhất — không probe đốt
quota, không bịa số.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Xoay khóa 403 ĐẠT khi cứu được ≥ ngưỡng này. Không đòi 100%: ngày cạn quota
# thì ca cuối không còn key nào để xoay là bình thường — chỉ khi ĐA SỐ không
# cứu được mới là cơ chế hỏng thật.
TI_LE_XOAY_DAT = 0.8

# Dịch vụ được trả kèm TỪNG LẦN CALL để UI vẽ mỗi call một cột. Chỉ dịch vụ
# THƯA (Owner chốt 02/09: LLM + serp) — YouTube 29.704 call/ngày vừa không vẽ
# nổi vừa đã có biểu đồ units cộng dồn riêng. Thêm dịch vụ mới vào đây là UI tự
# vẽ, không phải sửa code UI.
VE_TUNG_CALL = ("llm", "serp")
TOI_DA_CALL = 600


def _goc() -> Path:
    return Path(os.environ.get("SO_GOI_DIR", ROOT / "data" / "logs" / "so-goi"))


def _duong_gia() -> Path:
    return Path(os.environ.get("GIA_LLM", ROOT / "nen" / "rules" / "gia_llm.csv"))


_gia_cache: dict = {}


def bang_gia() -> dict[str, tuple[float, float]]:
    """{model: (usd_vao_1M, usd_ra_1M)} từ rules/gia_llm.csv — LUẬT NGOÀI CODE.

    Đổi giá hay thêm model mới = sửa file CSV, không đụng code. Cache theo mtime
    + size (bài học 03/09: mtime trên Windows thô, sửa rồi đọc lại ngay là trúng
    khoá cũ). File hỏng/thiếu → bảng rỗng, mọi usd = None; KHÔNG bịa giá.
    """
    p = _duong_gia()
    try:
        st = p.stat()
    except OSError:
        return {}
    khoa = (str(p), st.st_mtime, st.st_size)
    if _gia_cache.get("khoa") == khoa:
        return _gia_cache["ban"]
    ban: dict[str, tuple[float, float]] = {}
    try:
        import csv
        with open(p, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                m = (r.get("model") or "").strip()
                if not m:
                    continue
                try:
                    ban[m] = (float(r["gia_vao_usd_1m"]), float(r["gia_ra_usd_1m"]))
                except (KeyError, TypeError, ValueError):
                    continue      # dòng hỏng bỏ qua, không giết cả bảng
    except OSError:
        return {}
    _gia_cache.update(khoa=khoa, ban=ban)
    return ban


def tinh_usd(model: str, token_vao: int, token_ra: int) -> float | None:
    """Chi phí USD của MỘT call. Model chưa khai giá → None (không đoán)."""
    gia = bang_gia().get((model or "").strip())
    if not gia:
        return None
    return token_vao / 1e6 * gia[0] + token_ra / 1e6 * gia[1]


def _ty_gia_usd() -> float | None:
    """Tỉ giá USD gần nhất từ sổ của app to-chuc (nhan-su/ty-gia/<năm>.jsonl).

    Nền KHÔNG import chéo app (Luật 4) → đọc thẳng file theo cùng quy ước
    đường dẫn. Chưa có sổ → None, UI chỉ hiện USD (không quy đổi bừa).
    """
    d = Path(os.environ.get("TY_GIA_DIR", ROOT / "nhan-su" / "ty-gia"))
    gia = None
    try:
        for nam in sorted(d.glob("*.jsonl"), reverse=True)[:2]:
            for ln in nam.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if r.get("tien_te") == "USD" and r.get("gia"):
                    gia = float(r["gia"])       # dòng sau đè dòng trước = mới nhất
            if gia:
                return gia
    except (OSError, TypeError, ValueError):
        return None
    return gia


def ghi(app: str, dich_vu: str, duoi: str = "", viec: str = "", model: str = "",
        units: float = 0, ms: float | None = None, ok: bool = True,
        ma_loi: str = "", token_vao: int | None = None,
        token_ra: int | None = None) -> None:
    """Ghi MỘT dòng sổ. token_vao/token_ra chỉ có nghĩa với dịch vụ LLM.

    CHI PHÍ TÍNH NGAY LÚC GHI, không tính lại lúc đọc (Owner chốt 03/09): giá
    nhà cung cấp và tỉ giá đều đổi theo thời gian, tính lại sau là hoá đơn tháng
    trước tự nhảy số. Chốt `usd` + `ty_gia` vào dòng sổ = con số bất biến, đối
    chiếu hoá đơn được. Model chưa có trong bảng giá → usd = None (KHÔNG đoán
    giá; UI hiện "—" kèm lời nhắc thêm dòng vào rules/gia_llm.csv).
    """
    gio = datetime.now()
    duong = _goc() / f"{gio:%Y}" / f"{gio:%m}"
    duong.mkdir(parents=True, exist_ok=True)
    ban = {"luc": gio.isoformat(timespec="seconds"), "app": app,
           "dich_vu": dich_vu, "duoi": duoi, "viec": viec,
           "model": model, "units": units,
           "ms": round(ms) if ms is not None else None,
           "ok": ok, "ma_loi": ma_loi}
    # Dòng KHÔNG có token giữ nguyên hình dạng cũ — sổ cũ đọc được, mọi chỗ
    # đang parse không phải sửa (7 app đang ghi sổ, chỉ vài app có token).
    if token_vao is not None or token_ra is not None:
        tv, tr = int(token_vao or 0), int(token_ra or 0)
        ban["token_vao"], ban["token_ra"] = tv, tr
        usd = tinh_usd(model, tv, tr)
        if usd is not None:
            ban["usd"] = round(usd, 6)
            tg = _ty_gia_usd()
            if tg:
                ban["ty_gia"] = tg
    with open(duong / f"{gio:%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(ban, ensure_ascii=False) + "\n")


def _dong_hom_nay() -> list[dict]:
    gio = datetime.now()
    f = _goc() / f"{gio:%Y}" / f"{gio:%m}" / f"{gio:%Y-%m-%d}.log"
    if not f.exists():
        return []
    try:
        tho = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    ket = []
    for ln in tho:
        try:
            ket.append(json.loads(ln))
        except ValueError:
            continue
    return ket


TRAN_DOC = 2000       # trần dòng trả cho trang log — xem mục "vì sao" trong doc()


def doc(ngay: str = "", api: str = "", khoa_duoi: str = "",
        app: str = "", tran: int = TRAN_DOC) -> list[dict]:
    """Đọc sổ MỘT ngày (mặc định hôm nay) + lọc, mới nhất trước — TRẢ THEO KHUÔN
    quota_log CŨ (api/khoa_duoi/luot/quota_tieu) để trang API Keys và Export CSV
    không phải sửa.

    Vì sao có hàm dịch schema này: hệ từng có HAI sổ song song. quota_log (khuôn
    P4) chưa app nào ghi — data/logs/quota/ rỗng vĩnh viễn — nên tab Quota log và
    cột "lượt gọi hôm nay" luôn trắng, trong khi so_goi đã ghi thật (02/09: 29.446
    youtube + 132 llm + 58 serp). Dịch ở ĐÂY thay vì sửa template/export để chỗ
    đọc chỉ có một khuôn, và ngày nào bỏ hẳn quota_log thì xóa đúng hàm này.
    """
    ngay = (ngay or "").strip() or date.today().isoformat()
    f = _goc() / ngay[:4] / ngay[5:7] / f"{ngay}.log"
    if not f.is_file():
        return []
    try:
        tho = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    # TRẦN: sổ thật một ngày lên tới ~31k dòng (radary quét YouTube liên tục) —
    # trả hết thì trang log dựng 31k hàng HTML và nghẹt. Đọc từ CUỐI file ngược
    # lên: mới nhất trước là thứ người ta cần khi soi lỗi, và cắt sớm thì không
    # phải parse cả file. Lọc hẹp (một API / một khóa) gần như không chạm trần.
    if tran and tran > 0:
        tho = tho[::-1]
    ra = []
    for ln in tho:
        try:
            d = json.loads(ln)
        except ValueError:
            continue          # sổ là append thô — một dòng hỏng không vỡ trang
        if api and d.get("dich_vu") != api:
            continue
        if khoa_duoi and d.get("duoi") != khoa_duoi:
            continue
        if app and d.get("app") != app:
            continue
        # `viec` rỗng thì lấy model làm nhãn (LLM ghi model, chưa ghi viec) —
        # cùng lệ với tom_tat_hom_nay để hai bảng không nói khác nhau.
        ra.append({"luc": d.get("luc", ""), "api": d.get("dich_vu", ""),
                   "khoa_duoi": d.get("duoi", ""), "app": d.get("app", ""),
                   "viec": d.get("viec") or d.get("model", ""),
                   "luot": 1, "quota_tieu": int(d.get("units") or 0),
                   "ok": bool(d.get("ok", True)), "ma_loi": d.get("ma_loi", "")})
        if tran and len(ra) >= tran:
            break
    return ra if (tran and tran > 0) else ra[::-1]


def chi_phi_theo_app(tu_ngay: str = "", den_ngay: str = "") -> dict:
    """CHI PHÍ LLM theo APP trong khoảng ngày (mặc định: hôm nay).

    Owner 03/09: "hiện số token đã tiêu tốn của từng API, để tính chi phí sử
    dụng cho từng app". Trả:
      {app: {calls, calls_co_token, token_vao, token_ra, usd, vnd,
             theo_model: {model: {...}}, thieu_gia: [model…]}}

    BA VAN CHỐNG BỊA SỐ TIỀN:
    1. Chỉ cộng dòng CÓ token. Call chưa ghi token không thành "0 token" — 0 giả
       làm hoá đơn trông rẻ hơn thật. `calls_co_token / calls` cho biết đang phủ
       bao nhiêu phần.
    2. `usd` chốt LÚC GHI, không tính lại lúc đọc — giá và tỉ giá đều đổi theo
       thời gian, tính lại là hoá đơn tháng trước tự nhảy số.
    3. Model chưa khai giá → vào `thieu_gia`, KHÔNG đoán giá. UI phải nói rõ
       "chưa tính được phần này" thay vì cộng thiếu trong im lặng.
    """
    tu = (tu_ngay or "").strip() or date.today().isoformat()
    den = (den_ngay or "").strip() or tu
    ket: dict = {}
    goc = _goc()
    if not goc.is_dir():
        return ket
    for f in sorted(goc.glob("*/*/*.log")):
        ngay = f.stem
        if not (tu <= ngay <= den):
            continue
        try:
            tho = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln in tho:
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            if d.get("dich_vu") != "llm":
                continue
            a = ket.setdefault(d.get("app") or "?", {
                "calls": 0, "calls_co_token": 0, "token_vao": 0, "token_ra": 0,
                "usd": 0.0, "vnd": 0.0, "theo_model": {}, "thieu_gia": []})
            a["calls"] += 1
            co_tk = d.get("token_vao") is not None or d.get("token_ra") is not None
            if not co_tk:
                continue
            tv, tr = int(d.get("token_vao") or 0), int(d.get("token_ra") or 0)
            usd = d.get("usd")
            a["calls_co_token"] += 1
            a["token_vao"] += tv
            a["token_ra"] += tr
            m = d.get("model") or "?"
            mm = a["theo_model"].setdefault(m, {
                "calls": 0, "token_vao": 0, "token_ra": 0, "usd": 0.0})
            mm["calls"] += 1
            mm["token_vao"] += tv
            mm["token_ra"] += tr
            if usd is None:
                if m not in a["thieu_gia"]:
                    a["thieu_gia"].append(m)
                continue
            a["usd"] += float(usd)
            mm["usd"] += float(usd)
            # VNĐ theo tỉ giá CHỐT LÚC GỌI (mỗi dòng mang tỉ giá của chính nó),
            # nên tổng tháng không đổi khi tỉ giá hôm nay đổi.
            if d.get("ty_gia"):
                a["vnd"] += float(usd) * float(d["ty_gia"])
    for a in ket.values():
        a["usd"] = round(a["usd"], 6)
        a["vnd"] = round(a["vnd"])
        for mm in a["theo_model"].values():
            mm["usd"] = round(mm["usd"], 6)
    return ket


def luot_hom_nay() -> dict[str, int]:
    """Tổng SỐ CALL hôm nay theo đuôi khóa — cột 'lượt gọi hôm nay' tab Add API.
    Khác quota_log cũ ở chỗ đếm call thật; khóa chưa gọi lần nào không có mặt
    (trang tự hiện '—', KHÔNG bịa số 0 trông như đã đo)."""
    tong: dict[str, int] = {}
    for d in _dong_hom_nay():
        duoi = d.get("duoi") or ""
        if duoi:
            tong[duoi] = tong.get(duoi, 0) + 1
    return tong


def kiem_vet(app: str) -> dict:
    """VẾT cho hệ kiểm logic (02/09): bằng chứng từ sổ gọi HÔM NAY của MỘT app.
    - theo_viec: {viec: {calls, loi, ms_max, luc_cuoi}} — logic 'quét có chạy'.
    - xoay_khoa: sau lỗi 403, call kế CÙNG dịch vụ trong ≤5s phải OK với key
      KHÁC. so_403=0 → xoay_ok=None (không có gì để phán, không bịa ĐÚNG)."""
    dong = [d for d in _dong_hom_nay() if d.get("app") == app]
    theo_viec: dict = {}
    for d in dong:
        v = theo_viec.setdefault(d.get("viec") or d.get("dich_vu") or "?", {
            "calls": 0, "loi": 0, "ms_max": 0, "luc_cuoi": ""})
        v["calls"] += 1
        if not d.get("ok", True):
            v["loi"] += 1
        if d.get("ms"):
            v["ms_max"] = max(v["ms_max"], d["ms"])
        v["luc_cuoi"] = (d.get("luc") or "")[11:16]
    # ĐO TỈ LỆ, không để MỘT ca lật kết quả (lỗi thật tự bắt 02/09: hệ có 990
    # sự kiện 403, xoay khóa chạy đúng, nhưng một ca cuối ngày không cứu được
    # làm phép kiểm báo SAI — xóa mất 989 ca đúng). Ngày cuối quota cạn thì ca
    # không-cứu-được là BÌNH THƯỜNG; chỉ khi ĐA SỐ không cứu mới là hỏng thật.
    so_403 = so_cuu = 0
    vd_cuu = vd_hong = ""
    for i, d in enumerate(dong):
        if d.get("ok", True) or "403" not in str(d.get("ma_loi", "")):
            continue
        so_403 += 1
        cuu = None
        try:
            t0 = datetime.fromisoformat(d.get("luc", ""))
        except ValueError:
            t0 = None
        for sau in dong[i + 1:]:
            if sau.get("dich_vu") != d.get("dich_vu"):
                continue
            if t0 is not None:
                try:
                    if (datetime.fromisoformat(sau["luc"]) - t0).total_seconds() > 5:
                        break
                except (KeyError, ValueError):
                    pass
            if sau.get("ok", True) and sau.get("duoi") != d.get("duoi"):
                cuu = sau
            break
        if cuu is not None:
            so_cuu += 1
            vd_cuu = (f"403 key ••{d.get('duoi', '?')} → ≤5s key "
                      f"••{cuu.get('duoi', '?')} OK")
        else:
            vd_hong = f"403 key ••{d.get('duoi', '?')} — call kế không cứu"
    if so_403 == 0:
        xoay_ok: bool | None = None
        chi_tiet = "0 sự kiện 403 hôm nay — CHƯA được kiểm chứng (không phải khỏe)"
    else:
        ti_le = so_cuu / so_403
        xoay_ok = ti_le >= TI_LE_XOAY_DAT
        chi_tiet = (f"cứu {so_cuu}/{so_403} ({ti_le:.0%}) — "
                    + (vd_cuu if xoay_ok else vd_hong))
    return {"theo_viec": theo_viec,
            "xoay_khoa": {"so_403": so_403, "so_cuu_duoc": so_cuu,
                          "xoay_ok": xoay_ok, "chi_tiet": chi_tiet}}


def tom_tat_hom_nay() -> dict:
    """Tổng hợp file HÔM NAY: per dịch vụ {calls, loi, tong_units,
    theo_duoi{duoi: {units, calls, loi, ok_cuoi, ma_loi, luc_cuoi}},
    theo_viec{app · viec: {calls, loi, ms_max}}}. Dòng hỏng bỏ qua."""
    gio = datetime.now()
    f = _goc() / f"{gio:%Y}" / f"{gio:%m}" / f"{gio:%Y-%m-%d}.log"
    ket: dict = {}
    if not f.exists():
        return ket
    try:
        dong_tho = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ket
    for ln in dong_tho:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        dv = ket.setdefault(d.get("dich_vu", "?"), {
            "calls": 0, "loi": 0, "tong_units": 0, "theo_duoi": {},
            "theo_viec": {}, "theo_gio": {}, "theo_gio_calls": {},
            "theo_gio_loi": {}, "token_vao": 0, "token_ra": 0, "usd": 0.0,
            "calls_co_token": 0, "model_chua_gia": []})
        dv["calls"] += 1
        if not d.get("ok", True):
            dv["loi"] += 1
        dv["tong_units"] += d.get("units", 0) or 0
        # TOKEN + CHI PHÍ (03/09): chỉ cộng dòng THẬT SỰ có token — call chưa ghi
        # token không được coi là "0 token", vì 0 giả làm chi phí trông rẻ hơn
        # thật. `calls_co_token` cho UI nói rõ đang phủ bao nhiêu phần.
        if d.get("token_vao") is not None or d.get("token_ra") is not None:
            dv["token_vao"] += int(d.get("token_vao") or 0)
            dv["token_ra"] += int(d.get("token_ra") or 0)
            dv["calls_co_token"] += 1
            if d.get("usd") is not None:
                dv["usd"] += float(d.get("usd") or 0)
            elif d.get("model") and d["model"] not in dv["model_chua_gia"]:
                # model có token mà không tính được tiền → nêu ĐÍCH DANH để Owner
                # thêm một dòng vào rules/gia_llm.csv, không im lặng tính thiếu.
                dv["model_chua_gia"].append(d["model"])
        gio_call = (d.get("luc") or "")[11:13]
        if gio_call:
            dv["theo_gio"][gio_call] = dv["theo_gio"].get(gio_call, 0) + (d.get("units", 0) or 0)
            # theo_gio chỉ cộng UNITS — dịch vụ không tính units (LLM: đo thật
            # 02/09 là 132 call / units toàn 0 vì chưa ghi token; transcript,
            # stock…) sẽ ra đường phẳng 0, tưởng "không dùng" trong khi đang
            # chạy. Đếm thêm CALLS + LỖI theo giờ để mọi dịch vụ đều vẽ được
            # nhịp bằng thước của chính nó.
            dv["theo_gio_calls"][gio_call] = dv["theo_gio_calls"].get(gio_call, 0) + 1
            if not d.get("ok", True):
                dv["theo_gio_loi"][gio_call] = dv["theo_gio_loi"].get(gio_call, 0) + 1
        duoi = d.get("duoi") or ""
        if duoi:
            k = dv["theo_duoi"].setdefault(duoi, {
                "units": 0, "calls": 0, "loi": 0, "ok_cuoi": True,
                "ma_loi": "", "luc_cuoi": ""})
            k["units"] += d.get("units", 0) or 0
            k["calls"] += 1
            if not d.get("ok", True):
                k["loi"] += 1
            k["ok_cuoi"] = bool(d.get("ok", True))
            k["ma_loi"] = d.get("ma_loi", "") if not d.get("ok", True) else ""
            k["luc_cuoi"] = (d.get("luc") or "")[11:16]
        if d.get("app"):
            khoa_v = f"{d['app']} · {d.get('viec') or d.get('model') or d.get('dich_vu')}"
            v = dv["theo_viec"].setdefault(khoa_v, {"calls": 0, "loi": 0, "ms_max": 0})
            v["calls"] += 1
            if not d.get("ok", True):
                v["loi"] += 1
            if d.get("ms"):
                v["ms_max"] = max(v["ms_max"], d["ms"])
        # TỪNG LẦN CALL (Owner 02/09, "chỉ dùng cho LLM và serp"): hai dịch vụ
        # này thưa — đo thật hôm chốt là 132 và 58 call/ngày, vẽ mỗi call một
        # cột thì rộng 7,5px và 17px, đọc được. YouTube 29.704 call thì KHÔNG
        # (0,03px/cột) và cũng không cần: nó đã có biểu đồ units cộng dồn riêng.
        # Trần TOI_DA_CALL để một ngày bất thường không bơm cả vạn dòng qua mạng.
        if d.get("dich_vu") in VE_TUNG_CALL:
            ds = dv.setdefault("moi_call", [])
            if len(ds) < TOI_DA_CALL:
                ds.append({"luc": (d.get("luc") or "")[11:19],
                           "ms": d.get("ms"), "ok": bool(d.get("ok", True)),
                           "ma_loi": d.get("ma_loi", ""),
                           "nhan": d.get("viec") or d.get("model") or "",
                           "duoi": d.get("duoi") or "", "app": d.get("app") or ""})
            else:
                dv["moi_call_cat"] = dv.get("moi_call_cat", 0) + 1
    return ket
