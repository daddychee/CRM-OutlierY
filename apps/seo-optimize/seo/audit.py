"""Nhật ký AI LÀM GÌ — chỉ có nghĩa khi mỗi người một tài khoản (`users.py`).

**Vì sao đáng có:** tool này xoá được kênh/format/tập và tiêu được quota + tiền LLM. Với một
mật khẩu dùng chung thì câu *"ai vừa xoá kênh Hidden Globe"* là câu KHÔNG TRẢ LỜI ĐƯỢC — nên
cũng chẳng ai buồn hỏi. Có tài khoản riêng rồi thì nó trả lời được, và chi phí gần bằng 0.

**Chỉ ghi việc GHI, không ghi việc ĐỌC.** Poll `/api/status` 1 giây/lần và mọi lần mở tab đều
là GET; ghi hết thì file phình nhanh và thứ đáng đọc chìm nghỉm giữa hàng vạn dòng vô nghĩa.

**KHÔNG BAO GIỜ ghi nội dung body.** Body của `/api/generate` mang cả kịch bản; của `/api/login`
mang mật khẩu. Chỉ ghi *ai · lúc nào · từ đâu · gọi cái gì · kết quả ra sao* + vài field định
danh đã chọn lọc (slug/tên) để tra cứu được.

Ghi JSONL nối đuôi, tự cắt khi quá to. Không LLM, không quota, thuần stdlib.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from . import common

MAX_BYTES = 2_000_000          # ~2 MB thì xoay vòng; giữ đúng 1 file cũ
KEEP_KEYS = ("slug", "name", "niche", "run", "episode", "kind", "token", "old")
# `old` vốn là "tên thị trường CŨ" của `/api/save-market`. Nhưng `/api/change-password` cũng
# gửi `old` — và đó là **MẬT KHẨU HIỆN TẠI**. Trùng tên khoá ⇒ mật khẩu trần đi thẳng vào
# `logs/`, đúng thứ file này hứa không bao giờ làm. Bắt được bằng bài đo, không phải bằng đọc
# code: nhìn `KEEP_KEYS` thì "old" trông vô hại.
# Hai lớp chặn, giữ đủ cả hai — một lớp là dựa vào việc nhớ cập nhật danh sách:
#   · theo ĐƯỜNG: endpoint nào đụng mật khẩu thì chỉ giữ `name`
#   · theo TÊN KHOÁ: khoá nào nghe như mật khẩu thì bỏ, dù đi qua đường nào
SECRET_PATHS = ("/api/change-password", "/api/user-passwd", "/api/login", "/api/reset-approve",
                "/api/admin-keys")   # 03/08: body mang API key — không field nào được lọt nhật ký
_SECRETISH = ("pass", "pw", "secret", "token", "key", "old", "new")

_LOCK = threading.Lock()


def _dir():
    """Tính LÚC GỌI, không đóng băng theo `common.ROOT` lúc import — self-test đổi ROOT sang
    thư mục tạm mà module vẫn ghi vào chỗ thật thì đúng bẫy đã cắn với `.trash/`."""
    return common.ROOT / "logs"


def path():
    return _dir() / "audit.jsonl"


def _rotate(p) -> None:
    try:
        if p.exists() and p.stat().st_size > MAX_BYTES:
            old = p.with_suffix(".1.jsonl")
            if old.exists():
                old.unlink()
            p.rename(old)
    except OSError:
        pass                                             # xoay vòng hỏng KHÔNG được chặn việc ghi


def fields(body: dict, path: str = "") -> dict:
    """Chỉ vài field ĐỊNH DANH, không bao giờ nội dung.

    Body của `/api/generate` mang cả kịch bản; body của `/api/login` và
    `/api/change-password` mang mật khẩu. Danh sách CHO PHÉP (không phải danh sách cấm)
    là mặc định đúng ở đây: thêm endpoint mới mà quên nghĩ tới thì nó lọt ra ngoài chứ
    không lọt vào — trừ đúng một lỗ đã cắn: khoá `old` trùng tên giữa "tên thị trường
    cũ" và "mật khẩu hiện tại". Nên có thêm lớp lọc theo TÊN KHOÁ.
    """
    if not isinstance(body, dict):
        return {}
    p = (path or "").split("?", 1)[0]
    keys = ("name",) if p in SECRET_PATHS else KEEP_KEYS
    out = {}
    for k in keys:
        if k.lower() in _SECRETISH and p in SECRET_PATHS:
            continue
        v = body.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            out[k] = str(v)[:120]
    return out

def log(user: str, ip: str, action: str, ok: bool = True, **extra) -> None:
    """Ghi một dòng. **Nuốt mọi lỗi**: không ghi được nhật ký thì cũng không được làm hỏng
    thao tác user vừa làm — nhật ký là thứ phụ, dữ liệu mới là thứ chính."""
    try:
        rec = {"t": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
               "user": user or "(chưa đăng nhập)", "ip": ip or "", "do": action, "ok": bool(ok)}
        rec.update({k: v for k, v in extra.items() if v not in (None, "", [], {})})
        p = path()
        with _LOCK:                                      # nhiều thread cùng ghi → dòng lẫn vào nhau
            p.parent.mkdir(parents=True, exist_ok=True)
            _rotate(p)
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:                                    # noqa: BLE001
        pass


def tail(n: int = 200) -> list[dict]:
    """N dòng mới nhất (mới → cũ). Dòng hỏng thì BỎ QUA, không làm chết cả bảng."""
    p = path()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for ln in reversed(lines[-max(n, 1) * 2:]):
        try:
            out.append(json.loads(ln))
        except Exception:                                # noqa: BLE001
            continue
        if len(out) >= n:
            break
    return out


# ĐÃ GỠ `clear()` (2026-08-02) — ĐỪNG VIẾT LẠI. User chốt: *"không ai trong role được phép
# xoá lịch sử hoạt động của từng tài khoản"*. Nhật ký mà người trong hệ thống xoá được thì
# mất phần lớn giá trị — chỗ đáng tra nhất chính là lúc có ai đó muốn xoá nó đi. File tự
# xoay vòng ở `MAX_BYTES` nên không phình vô hạn; cần dọn thật thì xoá file trên đĩa, tức
# phải sờ được vào máy — cùng mức tin cậy với `python -m seo.users`.


if __name__ == "__main__":                               # self-test offline, thư mục tạm
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        old = common.ROOT
        common.ROOT = Path(td)
        try:
            assert tail() == [], "chưa có file thì trả rỗng, không nổ"
            log("thanh", "192.168.1.5", "delete-profile", slug="hidden-globe-hg-02")
            log("binh", "192.168.1.9", "generate", run="gen-abc", episode="tap-1")
            log("binh", "192.168.1.9", "delete-format", ok=False, error="không thấy")
            t = tail()
            assert len(t) == 3 and t[0]["do"] == "delete-format", t
            assert t[0]["ok"] is False and t[2]["user"] == "thanh"
            assert t[2]["slug"] == "hidden-globe-hg-02", t[2]

            # KHÔNG được lọt nội dung nhạy cảm vào nhật ký
            f = fields({"password": "bimat", "script": "x" * 9999, "srt": "y" * 500,
                        "slug": "kenh-a", "text": "cả bài metadata"})
            assert f == {"slug": "kenh-a"}, f
            raw = path().read_text(encoding="utf-8")
            log("ai-do", "1.2.3.4", "login", **fields({"password": "sieu-bi-mat"}))
            assert "sieu-bi-mat" not in path().read_text(encoding="utf-8")

            # Nhiều thread cùng ghi: không dòng nào vỡ
            ts = [threading.Thread(target=log, args=(f"u{i}", "ip", "test")) for i in range(60)]
            [x.start() for x in ts]; [x.join() for x in ts]
            good = sum(1 for ln in path().read_text(encoding="utf-8").splitlines()
                       if ln.strip() and json.loads(ln))
            assert good == 64, good

            # Dòng rác giữa file không được làm chết `tail`
            with path().open("a", encoding="utf-8") as fh:
                fh.write("{day khong phai json}\n")
            assert len(tail(500)) == 64

            # ── KHOÁ `old` TRÙNG TÊN: "tên thị trường cũ" vs "MẬT KHẨU hiện tại" ──────
            # Lỗi ĐÃ TỪNG SỐNG trong `KEEP_KEYS` mà self-test cũ vẫn in "khong lot mat khau" —
            # một bộ kiểm báo xanh cho lỗi đang chạy thì chính nó là lời nói dối. Ca này tồn
            # tại để chuyện đó không lặp lại.
            mk = fields({"name": "US", "old": "USA"}, "/api/save-market")
            assert mk.get("old") == "USA", f"thị trường vẫn phải ghi được tên cũ: {mk}"
            # LIỆT KÊ TAY, **tuyệt đối không lặp qua `SECRET_PATHS`**: lặp qua chính danh
            # sách đang kiểm thì bỏ một đường ra khỏi danh sách là bài kiểm cũng thôi kiểm
            # đường đó — test không bao giờ đỏ được. (Tôi viết đúng như vậy lần đầu và nó
            # báo XANH cho lỗi vừa trồng lại.)
            for p in ("/api/change-password", "/api/user-passwd", "/api/login",
                      "/api/reset-approve"):
                got = fields({"name": "binh", "old": "matkhau-that-cua-toi",
                              "new": "matkhau-moi", "password": "abc123456"}, p)
                assert got == {"name": "binh"}, f"{p} lọt mật khẩu: {got}"
            # Không truyền `path` thì vẫn phải an toàn với khoá nghe như mật khẩu
            assert "password" not in fields({"password": "x", "name": "a"})

            # Ghi hỏng thì im lặng, KHÔNG ném ra ngoài (nhật ký không được phá thao tác chính)
            common.ROOT = Path(td) / "khong-ton-tai" / "a" / "b"
            log("x", "y", "z")                            # không được raise

            print("audit.py self-test OK - chi ghi field da chon loc, khong lot mat khau/kich ban "
                  "(ke ca khoa `old` trung ten voi mat khau cu), ", end="")
            print(
                  "nhieu thread khong vo dong, dong rac khong lam chet tail, ghi hong khong nem loi")
        finally:
            common.ROOT = old
