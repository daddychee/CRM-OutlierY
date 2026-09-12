# -*- coding: utf-8 -*-
"""Cầu CHẠY pipeline ngách qua service niche-research (:9113) + snapshot khi xong.

Tính năng 2 user chốt 18/08: "báo cáo mới sinh ra được cập nhật trên dashboard".
Luồng: nút Run → POST resume tới service (key YouTube service tự lấy từ KÉT) →
dashboard poll /niche/chay/<project>/trang-thai → thấy chạy xong thì bridge tự
ĐÓNG BĂNG snapshot (gọi scripts/snapshot.py của niche-research như CLI độc lập —
`ponytail:` chuyển thành endpoint /api/snapshot khi niche server được restart kèm
code mới) → trả done=true → JS reload trang, số mới hiện.

Mọi lời gọi HTTP có timeout (bài học SDK-600s hệ cũ); service chết → lỗi rõ.
"""
from __future__ import annotations

import json
import os
import re
from nen.common import token_noi_bo
import subprocess
import sys
import threading
from pathlib import Path

import requests

_APP_DIR = Path(__file__).resolve().parents[1]
_ROOT = _APP_DIR.parents[1]
_SNAPSHOT_PY = _ROOT / "apps" / "niche-research" / "scripts" / "snapshot.py"
_BUILD_BC_PY = _ROOT / "apps" / "niche-research" / "scripts" / "19_build_bao_cao.py"
_WRITER_PY = _ROOT / "apps" / "niche-research" / "scripts" / "20_bao_cao_writer.py"
# giây — trần CẢ writer (4 lượt LLM); quá thì ghi nhật ký, build tiếp. ĐO 11/09 với
# claude-opus-5 qua mwapi: 119+181+36+40 = 376s (300 cũ cắt writer mọi lần) — mwapi
# mất ~127s mới ra chữ đầu mỗi lượt; 900 ≈ 4 lượt × (180s chờ + ~45s viết).
_WRITER_TIMEOUT = 900

# chống snapshot đúp khi nhiều tab cùng poll thấy "vừa xong"
_snapshot_lock = threading.Lock()
_da_snapshot: set[str] = set()      # project đã snapshot cho lần-xong hiện tại
_dang_dong_goi: set[str] = set()    # project đang đóng gói nền (19/08)


def _api() -> str:
    return os.environ.get("NICHE_API", "http://127.0.0.1:9113").rstrip("/")


def _headers(user: dict) -> dict:
    """Chuyển claims của user hiện tại sang service (loopback, cùng khuôn gateway)."""
    return {"X-Remote-User": user.get("ten", ""),
            "X-Remote-Level": str(user.get("level", 0)),
            "X-Remote-Role": user.get("vai", "")}


def kiem_khoa(llm: bool = False, deepdive: bool = False) -> dict:
    """Bước 'check API' TRƯỚC Researching (user chốt 19/08): đọc cấp phát KÉT của
    niche-research qua gateway loopback — đúng nguồn service sẽ dùng lúc chạy
    (khoa_v3), CHỈ trả boolean từng việc, tuyệt đối không lộ key ra response."""
    goc = os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000").rstrip("/")
    # GOP 08/09: 3 viec ngach nay khai duoi slug APP CHU (data-analytics)
    r = requests.get(f"{goc}/api/cau-hinh/api-khoa/data-analytics", timeout=5,
                     headers=token_noi_bo.header())
    r.raise_for_status()
    cap = r.json() or {}

    def _co(viec: str) -> bool:
        return any(k.get("key") for k in (cap.get(viec) or {}).get("khoa", []))

    kq = {"youtube": _co("quet_kenh")}
    if llm:
        kq["llm"] = _co("phan_tich")
    if deepdive:
        kq["transcript"] = _co("lay_transcript")
    return {"ok": all(kq.values()), "chi_tiet": kq,
            "thieu": [v for v, ok in kq.items() if not ok]}


def chay_lai(project: str, user: dict) -> dict:
    """Resume/chạy lại project đã có pool — service tự lo key từ KÉT."""
    r = requests.post(f"{_api()}/api/resume/{project}", headers=_headers(user), timeout=15)
    r.raise_for_status()
    with _snapshot_lock:
        _da_snapshot.discard(project)      # lần chạy mới → cho phép snapshot mới
    return r.json()


def chay_moi(project: str, competitors_text: str, user: dict, *,
             skip_comments: bool = False, force: bool = False,
             deepdive: bool = False, llm: bool = False) -> dict:
    """Chạy project với pool (mới/cộng dồn) — upload competitors.txt cho service,
    service tự lo key từ KÉT (thiếu key → service 503 rõ). 4 cờ = TOÀN BỘ tùy chọn
    /api/run của service (kiểm 18/08 theo yêu cầu user: pipeline không cần nhập
    liệu dữ liệu nào khác ngoài pool — niche/thị trường lấy từ danh bạ)."""
    data = {"name": project, "skip_comments": str(skip_comments).lower(),
            "force": str(force).lower(), "deepdive": str(deepdive).lower(),
            "llm": str(llm).lower()}
    r = requests.post(f"{_api()}/api/run", data=data,
                      files={"competitors": ("competitors.txt", competitors_text.encode("utf-8"))},
                      headers=_headers(user), timeout=30)
    r.raise_for_status()
    with _snapshot_lock:
        _da_snapshot.discard(project)
    return r.json()


def trang_thai(project: str, user: dict) -> dict:
    """Trạng thái từ service; vừa chạy xong + có report → đóng gói NỀN đúng một lần.

    Đóng gói (writer 4 lượt LLM + builder + snapshot) mất tới 6,5 phút — đo thật
    OldNewbie_US 12/09 (10:29:26 → 10:35:53). Trước đây nó chạy ĐỒNG BỘ ngay trong
    lời gọi này, lại nằm TRONG _snapshot_lock, nên mọi lượt poll 3 giây một lần của
    dashboard đều kẹt ở khóa suốt từng ấy phút: màn hình đứng im ở "Researching…
    2023s" (đúng giây pipeline kết thúc), người dùng không phân biệt được máy đang
    viết diễn giải hay đã chết. Giờ đẩy sang thread nền và NÓI RA là đang đóng gói
    để UI hiện tiến độ. Trả {running, has_report, dang_dong_goi}."""
    r = requests.get(f"{_api()}/api/status/{project}", headers=_headers(user), timeout=10)
    r.raise_for_status()
    st = r.json()
    if not st.get("running") and st.get("has_report"):
        # giữ khóa ĐÚNG lúc ghi sổ "đã nhận việc", không giữ suốt lúc đóng gói
        with _snapshot_lock:
            moi = project not in _da_snapshot
            if moi:
                _da_snapshot.add(project)
        # ĐĨA mới là nguồn sự thật, không phải registry bộ nhớ: _da_snapshot mất
        # sạch sau mỗi lần restart app, nên lượt poll ĐẦU sau restart từng châm
        # ngòi writer chạy lại (4 lượt LLM tiền thật) rồi ghi đè báo cáo tốt bằng
        # bản mới — đo thật 12/09: restart 10:57:58, poll 10:58:24 chạy writer
        # trong khi báo cáo đã đóng gói xong từ 10:35:53. Cùng vết 11/09; dashboard
        # hỏi can_dong_goi từ 19/08, riêng đường poll này thì chưa.
        if moi and can_dong_goi(project):
            dong_goi_nen(project)
    return {"running": bool(st.get("running")), "has_report": bool(st.get("has_report")),
            "dang_dong_goi": dang_dong_goi(project),
            "buoc": tinh_trang(project).get("buoc")}   # để UI nói được đang ở bước nào


def _thu_muc(project: str) -> Path:
    return Path(os.environ.get("NICHE_PROJECTS_DIR")
                or _ROOT / "data" / "niche-research" / "projects") / project


def can_dong_goi(project: str) -> bool:
    """Run đã xong nhưng CHƯA đóng gói (writer+builder+snapshot)?

    Sự cố 19/08 (user: 'chạy Space/Spain mà tool không hiện gì'): chuỗi đóng gói
    chỉ chạy khi tab dashboard còn mở để poll — đóng tab là báo cáo nằm trên đĩa
    mà dashboard (đọc theo snapshot) không thấy, cũng không báo vỡ ở đâu. Hàm này
    cho trang tự phát hiện: có file Report mà chưa snapshot / snapshot cũ hơn."""
    d = _thu_muc(project)
    rp = d / "Report"
    if not rp.is_dir():
        return False
    files = [f for f in rp.glob("*") if f.is_file() and not f.name.startswith("~$")]
    if not files:
        return False
    moi_nhat = max(f.stat().st_mtime for f in files)
    idx = d / "snapshots" / "index.json"
    if not idx.is_file():
        return True
    try:
        so = json.loads(idx.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    if not so:
        return True
    thu_muc_snap = d / "snapshots" / so[-1]["id"]
    if not thu_muc_snap.is_dir():
        return True
    # So với NỘI DUNG snapshot, KHÔNG phải mtime THƯ MỤC (sự cố 11/09): snapshot cùng
    # ngày ghi đè file trong thư mục CÓ SẴN, mà ghi đè file thì mtime thư mục đứng yên
    # (đo thật OldNewbie_US: thư mục 19:11:14 trong khi file bên trong 21:10:07) → trang
    # tưởng chưa đóng gói, MỖI lần mở dashboard lại chạy writer (4 lời gọi LLM) rồi ghi
    # đè báo cáo tốt bằng bản kém hơn. snapshot.py dùng shutil.copy2 nên file trong
    # snapshot giữ nguyên mtime nguồn → chép xong hai mốc bằng nhau.
    trong = [f.stat().st_mtime for f in thu_muc_snap.glob("*") if f.is_file()]
    moc_snap = max(trong) if trong else thu_muc_snap.stat().st_mtime
    return moi_nhat > moc_snap + 1


def dong_goi_nen(project: str) -> None:
    """Đóng gói NỀN (thread) — trang không chờ; chống chạy trùng bằng _dang_dong_goi."""
    with _snapshot_lock:
        if project in _dang_dong_goi:
            return
        _dang_dong_goi.add(project)

    def _chay():
        try:
            _snapshot(project)
        finally:
            with _snapshot_lock:
                _dang_dong_goi.discard(project)

    threading.Thread(target=_chay, daemon=True).start()


def dang_dong_goi(project: str) -> bool:
    with _snapshot_lock:
        return project in _dang_dong_goi


# Dòng bước orchestrator in ra: ">>> [3/20] 12:39:43  S4  comments -> viewer
# questions". Giờ là TUỲ CHỌN — nhật ký đời cũ không có, vẫn phải bóc được bước.
_MAU_BUOC = re.compile(r"^>>> \[(\d+)/(\d+)\]\s*(?:(\d\d:\d\d:\d\d)\s+)?(.*)$")


def _buoc_hien_tai(dong: list[str]) -> dict | None:
    """Bước đang chạy = dòng '>>> [n/total] …' CUỐI CÙNG của nhật ký.

    Owner 12/09 hỏi giữa lần chạy "tiến trình có đang chạy không?" mà màn hình chỉ
    có số giây — phải vào tận máy soi tiến trình mới biết đang ở bước 3/20 quét
    bình luận. Nhật ký vốn đã ghi sẵn bước, chỉ là chưa ai bóc ra cho trang."""
    for d in reversed(dong):
        m = _MAU_BUOC.match(d.strip())
        if m:
            return {"so": int(m.group(1)), "tong": int(m.group(2)),
                    "luc": m.group(3), "ten": m.group(4).strip()}
    return None


def tinh_trang(project: str, so_dong: int = 12) -> dict:
    """Trạng thái run ĐỌC TỪ ĐĨA (không cần service): đuôi stdout.log + mốc thời
    gian — để trang nói được 'vỡ ở đâu' thay vì im lặng (user 19/08)."""
    d = _thu_muc(project)
    log = d / "niche-data" / "stdout.log"
    if not log.is_file():
        return {"co_log": False}
    try:
        dong = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"co_log": False}
    duoi = [x for x in dong if x.strip()][-so_dong:]
    xong = any("Pipeline done" in x for x in dong[-40:])
    loi = [x for x in dong[-80:]
           if ("Traceback" in x or "ERROR" in x or "LOI" in x or "Error:" in x)]
    from datetime import datetime as _dt
    # BƯỚC đọc từ run.log: orchestrator ghi THẲNG vào đó, còn stdout.log đi qua
    # đường ống của service nên bị ĐỆM và trễ — đo thật 12/09 giữa lần chạy
    # Cooking_DEU: stdout.log dừng ở [13/20] trong khi run.log đã [14/20]. Một
    # bước LLM dài cả chục phút nên lấy nhầm nguồn là hiện bước cũ suốt từng ấy
    # phút. Thiếu run.log (dự án đời cũ) thì lùi về stdout.log như trước.
    dong_buoc = dong
    rl = d / "niche-data" / "run.log"
    if rl.is_file():
        try:
            dong_buoc = rl.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    return {"co_log": True, "xong": xong, "duoi": duoi, "loi": loi[-3:],
            "buoc": _buoc_hien_tai(dong_buoc),
            "luc": _dt.fromtimestamp(log.stat().st_mtime).strftime("%d/%m %H:%M")}


def _ghi_nhat_ky_writer(duong: Path, w: subprocess.CompletedProcess) -> None:
    """Sự cố 11/09: writer chết 401 mà output bị bỏ → khối Nhật ký im lặng. Ghi kết
    quả writer vào CHÍNH stdout.log của lần chạy (tinh_trang đọc file này): hỏng →
    mã thoát + đuôi output (dòng 'LOI…' tinh_trang bắt được); ổn → dòng xác nhận
    kèm các dòng CANH BAO (lượt writer nào thiếu cũng hiện)."""
    ra = [x for x in ((w.stdout or b"") + (w.stderr or b"")).decode(
        "utf-8", "replace").splitlines() if x.strip()]
    if w.returncode == 0:
        dong = [">>> [đóng gói] bao_cao_writer (tầng NGHĨA) — xong"]
        dong += [f"    {x}" for x in ra if "CANH BAO" in x]
    else:
        dong = [f">>> [đóng gói] bao_cao_writer (tầng NGHĨA) THẤT BẠI — mã {w.returncode}"]
        dong += [f"    {x}" for x in ra[-6:]]
    try:
        with open(duong / "niche-data" / "stdout.log", "a", encoding="utf-8") as f:
            f.write("\n".join(dong) + "\n")
    except OSError:
        pass


def _snapshot(project: str) -> bool:
    """Đóng băng lần chạy hiện tại bằng script CLI của niche-research (best-effort).
    TRƯỚC snapshot: build BÁO CÁO GỘP HTML (19_build_bao_cao.py — tầng 1, 19/08)
    để mọi run tự có HTML trong Report/; build hỏng chỉ mất HTML, không chặn snapshot."""
    duong = Path(os.environ.get("NICHE_PROJECTS_DIR")
                 or _ROOT / "data" / "niche-research" / "projects") / project
    try:
        # tầng 2 TRƯỚC (writer LLM sinh bao_cao_nghia.json — 1 lời gọi/run, key KÉT;
        # hỏng chỉ mất tầng NGHĨA, builder giữ slot chờ) rồi tầng 1 render HTML.
        try:
            w = subprocess.run([sys.executable, str(_WRITER_PY), str(duong)],
                               capture_output=True, timeout=_WRITER_TIMEOUT,
                               env={**os.environ, "PYTHONUTF8": "1"})
        except subprocess.TimeoutExpired as tx:
            # quá giờ vẫn phải ghi nhật ký + để builder chạy tiếp (nghiệm thu 11/09)
            w = subprocess.CompletedProcess(
                tx.cmd, -1, tx.output or b"",
                f"LOI: writer quá thời gian {_WRITER_TIMEOUT}s — bị dừng".encode("utf-8"))
        _ghi_nhat_ky_writer(duong, w)
        subprocess.run([sys.executable, str(_BUILD_BC_PY), str(duong)],
                       capture_output=True, timeout=120,
                       env={**os.environ, "PYTHONUTF8": "1"})
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        cp = subprocess.run([sys.executable, str(_SNAPSHOT_PY), str(duong)],
                            capture_output=True, timeout=120,
                            env={**os.environ, "PYTHONUTF8": "1"})
        return cp.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
