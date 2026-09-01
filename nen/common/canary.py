# -*- coding: utf-8 -*-
"""CANARY LOGIC (P1-M2, 01/09/2026) — Owner chốt: mọi logic phải được GỌI TÊN
trong từng app và kiểm đều đặn tự động hoặc có nút hard-test bất cứ lúc.

Canary = gọi tính năng THẬT của app (loopback) với input mẫu, so KẾT QUẢ với
kỳ vọng — bắt ca "HTTP 200 nhưng kết quả rỗng" (họ bài học nút chia chương
Content 30/08) mà health/liveness đều mù.

Kịch bản khai NGOÀI code — nen/rules/canary/<slug>.json:
  {"kich_ban": [{ma, ten, method, duong, body?, cho: [[đường_json, toán_tử,
  giá_trị], ...]}]}
Đường_json: "a.b.0.c"; segment "ten=xxx" tìm phần tử list có trường ten khớp
(thứ tự đổi không vỡ). Toán tử: == != >= <= len>= chua.
Thêm một phép đo logic mới = thêm MỘT DÒNG JSON, không sửa code.

Kết quả lưu BỀN data/canary/<slug>.json (ghi nguyên tử) — UI đọc sau restart;
cảnh báo phát lúc CHUYỂN dung→sai/loi và hồi phục (edge, khuôn giam_sat).
Input kịch bản phải CHỈ-ĐỌC/dry-run — không được ghi dữ liệu thật.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
_cache_luat: dict = {}


def _duong_luat_dir() -> Path:
    return Path(os.environ.get("CANARY_LUAT_DIR", ROOT / "nen" / "rules" / "canary"))


def _duong_data_dir() -> Path:
    return Path(os.environ.get("CANARY_DATA_DIR", ROOT / "data" / "canary"))


def _cong_cua(slug: str) -> int | None:
    from nen.common.hop_dong import tim_app
    app = tim_app(slug)
    return app["cong"] if app else None


def cac_slug() -> list[str]:
    d = _duong_luat_dir()
    if not d.is_dir():
        return []
    return sorted(f.stem for f in d.glob("*.json"))


def doc_kich_ban(slug: str) -> list[dict]:
    duong = _duong_luat_dir() / f"{slug}.json"
    if not duong.exists():
        return []
    khoa = (str(duong), duong.stat().st_mtime)
    if khoa in _cache_luat:
        return _cache_luat[khoa]
    du_lieu = json.loads(duong.read_text(encoding="utf-8-sig"))
    ket = [k for k in du_lieu.get("kich_ban", [])
           if all(k.get(t) for t in ("ma", "ten", "method", "duong", "cho"))]
    _cache_luat.clear()
    _cache_luat[khoa] = ket
    return ket


def _lay(d, duong: str):
    """Resolver đường_json: 'a.b.0.c' + 'ten=xxx' tìm trong list theo trường ten."""
    hien_tai = d
    for phan in duong.split("."):
        if hien_tai is None:
            return None
        if isinstance(hien_tai, list):
            if phan.startswith("ten="):
                hien_tai = next((x for x in hien_tai
                                 if isinstance(x, dict) and x.get("ten") == phan[4:]), None)
                continue
            try:
                hien_tai = hien_tai[int(phan)]
                continue
            except (ValueError, IndexError):
                return None
        if isinstance(hien_tai, dict):
            hien_tai = hien_tai.get(phan)
        else:
            return None
    return hien_tai


def _kiem(gia_tri, toan_tu: str, muc_tieu) -> bool:
    try:
        if toan_tu == "==":
            return gia_tri == muc_tieu
        if toan_tu == "!=":
            return gia_tri != muc_tieu
        if toan_tu == ">=":
            return gia_tri is not None and gia_tri >= muc_tieu
        if toan_tu == "<=":
            return gia_tri is not None and gia_tri <= muc_tieu
        if toan_tu == "len>=":
            return gia_tri is not None and len(gia_tri) >= muc_tieu
        if toan_tu == "chua":
            return gia_tri is not None and str(muc_tieu) in str(gia_tri)
    except TypeError:
        return False
    return False


async def _chay_mot(client: httpx.AsyncClient, cong: int, kb: dict) -> dict:
    """Một kịch bản → {ma, ten, ket_qua: dung|sai|loi, chi_tiet, ms}.
    'loi' = không gọi/đọc được (hạ tầng); 'sai' = gọi được mà KẾT QUẢ lệch kỳ
    vọng — chính là "sai logic" Owner đặt hàng."""
    ket = {"ma": kb["ma"], "ten": kb["ten"], "ket_qua": "dung", "chi_tiet": ""}
    t0 = time.perf_counter()
    try:
        r = await client.request(
            kb["method"], f"http://127.0.0.1:{cong}{kb['duong']}",
            json=kb.get("body"), headers={"X-Remote-User": "giam-sat"})
        ket["ms"] = round((time.perf_counter() - t0) * 1000)
        if r.status_code >= 400:
            ket.update(ket_qua="loi", chi_tiet=f"HTTP {r.status_code} tại {kb['duong']}")
            return ket
        body = r.json()
    except httpx.HTTPError as e:
        ket.update(ket_qua="loi", ms=round((time.perf_counter() - t0) * 1000),
                   chi_tiet=f"{type(e).__name__}: {e}")
        return ket
    except ValueError:
        ket.update(ket_qua="loi", chi_tiet="phản hồi không phải JSON")
        return ket
    for duong_json, toan_tu, muc_tieu in kb["cho"]:
        thuc_te = _lay(body, duong_json)
        if not _kiem(thuc_te, toan_tu, muc_tieu):
            gon = thuc_te if not isinstance(thuc_te, (list, dict)) else (
                f"len={len(thuc_te)}")
            ket.update(ket_qua="sai",
                       chi_tiet=f"kỳ vọng {duong_json} {toan_tu} {muc_tieu!r} "
                                f"↔ thực tế {gon!r}")
            return ket
    return ket


def doc_ket_qua(slug: str) -> dict | None:
    duong = _duong_data_dir() / f"{slug}.json"
    if not duong.exists():
        return None
    try:
        return json.loads(duong.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


async def chay_app(slug: str) -> dict:
    """Chạy toàn bộ kịch bản của một app + lưu bền. Kịch bản nổ không giết lượt."""
    cong = _cong_cua(slug)
    ds = doc_kich_ban(slug)
    ket = {"app": slug, "luc": datetime.now().isoformat(timespec="seconds"),
           "kich_ban": []}
    if cong is None:
        ket["kich_ban"] = [{"ma": k["ma"], "ten": k["ten"], "ket_qua": "loi",
                            "chi_tiet": "app không có trong hợp đồng"} for k in ds]
    else:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for kb in ds:
                ket["kich_ban"].append(await _chay_mot(client, cong, kb))
    d = _duong_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{slug}.json.tmp"
    tmp.write_text(json.dumps(ket, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(d / f"{slug}.json")
    return ket


def so_canary(slug: str, cu: dict | None, moi: dict) -> list[str]:
    """Edge-trigger THUẦN: dung→sai/loi báo một lần, hồi phục báo lại; lần đầu im."""
    if not cu:
        return []
    cu_theo_ma = {k["ma"]: k for k in cu.get("kich_ban", [])}
    bao = []
    for k in moi.get("kich_ban", []):
        truoc = cu_theo_ma.get(k["ma"], {}).get("ket_qua")
        if truoc == "dung" and k["ket_qua"] in ("sai", "loi"):
            bao.append(f"🟠 Canary {slug} — \"{k['ten']}\" {k['ket_qua'].upper()}: "
                       f"{k.get('chi_tiet', '')}")
        if truoc in ("sai", "loi") and k["ket_qua"] == "dung":
            bao.append(f"🟢 Canary {slug} — \"{k['ten']}\" đã hồi phục")
    return bao


async def chay_tat_ca() -> list[str]:
    """Chạy canary mọi app có kịch bản; trả cảnh báo edge (vòng giám sát phát)."""
    bao: list[str] = []
    for slug in cac_slug():
        cu = doc_ket_qua(slug)
        moi = await chay_app(slug)
        bao.extend(so_canary(slug, cu, moi))
    return bao
