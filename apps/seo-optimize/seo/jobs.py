"""Nhiều lần sinh CHẠY SONG SONG — thay cho một `PIPELINE` toàn cục.

**Bản cũ hỏng thế nào khi có 2 người:** `server.PIPELINE` là MỘT dict cho cả server. Hệ quả đo
được: người thứ hai bấm Sinh nhận `409 "đang chạy"`, và tệ hơn — `/api/status` đọc chung dict đó
nên board của người B hiện **thanh tiến trình và số token của người A**, rồi khi A xong thì B thấy
"xong" và đi mở kết quả của A. Board không nói dối vì nó cố tình, mà vì server chỉ có một chỗ để
nói.

**Chốt thiết kế:** mỗi lần sinh là một `job` riêng, khoá theo `run` id (vốn đã duy nhất từ lúc sửa
bug `runs/gen/`). `pipeline.generate` và `episode.generate` nhận một dict rồi tự `update()` vào đó —
nên chỉ cần đưa dict CỦA JOB thay vì dict toàn cục, **hai module đó không phải sửa một dòng nào**.

**XẾP HÀNG, KHÔNG ĐUỔI VỀ (2026-08-02).** Bản trước quá trần thì `start()` raise → 409. Đo với
7 người bấm cùng lúc: **4/7 bị từ chối**, tức quá nửa nhóm phải tự canh giờ bấm lại — mà họ
không nhìn thấy ai đang chạy nên chỉ còn cách bấm mò. Nay quá trần thì **vào hàng đợi**: vẫn
đúng 3 job chạy cùng lúc (lý do bên dưới), nhưng những người sau được xếp chỗ theo THỨ TỰ BẤM và
board nói rõ *"trước bạn còn N người"*. Không ai phải bấm lại.

**`QUEUE_MAX` là trần thứ hai, đừng bỏ.** Hàng đợi vô hạn thì 50 cú bấm nhầm thành 50 thread nằm
chờ, và người cuối đợi cả tiếng mà vẫn tưởng sắp tới lượt. Đầy hàng thì mới từ chối, và nói rõ
đang có mấy cái chạy / mấy cái chờ.

**Vẫn có trần `MAX_RUNNING`** — không phải để chặn người dùng, mà vì mỗi job gọi LLM song song
(`llm.MAX_PARALLEL = 4`) và ăn quota YouTube. Bỏ trần là 5 người bấm cùng lúc thành 20 request LLM
đồng thời → 429, và quota YouTube bốc hơi trong một phút. Quá trần thì **nói rõ đang có mấy job
chạy**, đừng chỉ báo "đang bận".

Không LLM, không quota, thuần stdlib.
"""
from __future__ import annotations

import threading
import time

MAX_RUNNING = 3          # trần job CHẠY cùng lúc
QUEUE_MAX = 12           # trần job NẰM CHỜ — quá thì mới từ chối
QUEUE_WAIT = 1800        # chờ quá 30 phút thì bỏ cuộc, đừng để thread nằm mãi
KEEP = 40                # số job giữ lại trong bộ nhớ để board còn poll được sau khi xong
DONE_TTL = 3600          # job đã xong quá 1h thì dọn — kết quả vẫn nằm trong runs/, không mất gì

_LOCK = threading.RLock()
_CV = threading.Condition(_LOCK)     # đánh thức người đang xếp hàng khi có chỗ trống
_JOBS: dict[str, dict] = {}


def _queued_l() -> list[str]:
    """Danh sách đang chờ, THEO THỨ TỰ BẤM. Chỉ gọi khi đang giữ khoá."""
    return [r for r, j in sorted(_JOBS.items(), key=lambda kv: kv[1].get("queued_at") or 0)
            if j.get("queued")]


def _renumber_l() -> None:
    """Cập nhật `ahead` cho mọi người đang chờ — board đọc thẳng field này."""
    for i, r in enumerate(_queued_l()):
        _JOBS[r]["ahead"] = i
        _JOBS[r]["step"] = ("đang xếp hàng — tới lượt bạn ngay khi có chỗ" if i == 0
                            else f"đang xếp hàng — trước bạn còn {i} người")


def _blank(run: str) -> dict:
    return {"running": False, "queued": False, "ahead": 0, "step": "", "done": False,
            "error": None, "run": run, "usage": None, "result": None,
            "started": 0.0, "ended": 0.0, "queued_at": 0.0}


def n_running() -> int:
    with _LOCK:
        return sum(1 for j in _JOBS.values() if j.get("running"))


def n_queued() -> int:
    with _LOCK:
        return len(_queued_l())


def running_runs() -> list[str]:
    with _LOCK:
        return [r for r, j in _JOBS.items() if j.get("running")]


def _prune() -> None:
    """Dọn job đã xong quá hạn, và cắt bớt nếu quá nhiều. KHÔNG bao giờ đụng job đang chạy."""
    now = time.time()
    with _LOCK:
        for r in [r for r, j in _JOBS.items()
                  if not j.get("running") and not j.get("queued")
                  and j.get("ended") and now - j["ended"] > DONE_TTL]:
            _JOBS.pop(r, None)
        if len(_JOBS) > KEEP:
            done = sorted(((r, j) for r, j in _JOBS.items()
                           if not j.get("running") and not j.get("queued")),
                          key=lambda kv: kv[1].get("ended") or 0)
            for r, _ in done[:len(_JOBS) - KEEP]:
                _JOBS.pop(r, None)


def start(run: str) -> dict:
    """Nhận một lần sinh và trả dict của nó (để đưa thẳng cho `pipeline.generate`).

    **Luôn nhận, trừ khi hàng đợi đã đầy.** Job vào trạng thái `queued`; thread của nó gọi
    `acquire()` để đợi tới lượt. Ghi nhận ĐỒNG BỘ (trước khi spawn thread) để poll đầu tiên
    không bắt nhầm trạng thái của lần trước.
    """
    _prune()
    with _CV:
        old = _JOBS.get(run)
        # Bấm lại đúng run đang chạy/đang chờ: đừng đẻ job thứ hai ghi cùng một thư mục runs/.
        if old and (old.get("running") or old.get("queued")):
            raise RuntimeError(f"Lần sinh '{run}' đang chạy hoặc đang xếp hàng rồi")
        if len(_queued_l()) >= QUEUE_MAX:
            raise RuntimeError(
                f"Hàng đợi đã đầy ({QUEUE_MAX} lần sinh đang chờ, "
                f"{n_running()} đang chạy) — đợi vài phút rồi bấm lại.")
        j = _blank(run)
        j.update(queued=True, queued_at=time.time(), step="đang xếp hàng…")
        _JOBS[run] = j
        _renumber_l()
        _CV.notify_all()
        return j


def acquire(run: str, timeout: float = QUEUE_WAIT) -> bool:
    """Chặn cho tới lượt của `run`. Trả False nếu bỏ cuộc (hết giờ / job bị dọn mất).

    **FIFO theo lúc BẤM**, không phải theo thread nào tỉnh trước: `notify_all` đánh thức tất cả,
    ai cũng tự kiểm "mình có phải người đầu hàng không". Thiếu luật này thì thứ tự do bộ lập lịch
    của HĐH quyết, và người bấm trước có thể bị chen mãi.
    """
    end = time.time() + max(1.0, timeout)
    with _CV:
        while True:
            j = _JOBS.get(run)
            if j is None:                                  # bị dọn mất → thôi
                return False
            q = _queued_l()
            if q and q[0] == run and n_running() < MAX_RUNNING:
                j.update(queued=False, running=True, ahead=0, step="bắt đầu…",
                         started=time.time())
                _renumber_l()
                return True
            left = end - time.time()
            if left <= 0:
                j.update(queued=False, running=False, done=False, ahead=0,
                         ended=time.time(),
                         error=f"Đợi quá lâu trong hàng ({int(timeout / 60)} phút) — "
                               f"CHƯA sinh gì cả, không tốn token. Bấm lại khi server đỡ bận.")
                _renumber_l()
                _CV.notify_all()
                return False
            _CV.wait(min(left, 1.0))


def update(run: str, **kw) -> None:
    with _CV:
        j = _JOBS.get(run)
        if j is not None:
            j.update(kw)


def finish(run: str, error: str | None = None, **kw) -> None:
    """Xong (hoặc hỏng) → NHẢ CHỖ và đánh thức người kế tiếp trong hàng.

    `notify_all` là bắt buộc: thiếu nó thì chỗ trống ra mà không ai biết, cả hàng nằm chờ tới lúc
    `_CV.wait(1.0)` hết giờ — vẫn chạy, nhưng mỗi lượt trễ thêm cả giây vô cớ.
    """
    with _CV:
        j = _JOBS.get(run)
        if j is None:
            return
        j.update(running=False, queued=False, ahead=0, done=error is None, error=error,
                 ended=time.time(), **kw)
        if error is None:
            j["step"] = kw.get("step", "xong")
        _renumber_l()
        _CV.notify_all()


def get(run: str) -> dict | None:
    with _CV:
        j = _JOBS.get(run)
        return dict(j) if j else None


def snapshot(run: str = "") -> dict:
    """Trạng thái cho `/api/status`.

    Hỏi ĐÚNG một job (`?run=`) thì trả job đó. **Không hỏi run nào thì KHÔNG được đoán bừa**
    một job đang chạy trả về — đó chính là lỗi cũ: board của người này nhận tiến trình của
    người kia. Trả trạng thái RỖNG kèm `n_running` để board biết mà nói cho đúng.
    """
    if run:
        j = get(run)
        if j:
            return {**j, "n_running": n_running(), "n_queued": n_queued(), "found": True}
        return {**_blank(run), "n_running": n_running(), "n_queued": n_queued(),
                "found": False}
    return {**_blank(""), "n_running": n_running(), "n_queued": n_queued(),
            "running_runs": running_runs(), "found": False, "no_run": True}


def _reset_for_test() -> None:
    with _CV:
        _JOBS.clear()
        _CV.notify_all()


if __name__ == "__main__":                       # self-test offline
    _reset_for_test()

    def _run(r):
        """start + acquire — đúng thứ tự mà server làm."""
        j = start(r)
        assert acquire(r, timeout=5), r
        return j

    # ── Hai job SONG SONG, trạng thái KHÔNG lẫn vào nhau (đây là cả lý do module tồn tại) ──
    a = _run("run-a")
    b = _run("run-b")
    assert n_running() == 2
    update("run-a", step="harvest…")
    update("run-b", step="tags…")
    assert snapshot("run-a")["step"] == "harvest…", snapshot("run-a")
    assert snapshot("run-b")["step"] == "tags…", snapshot("run-b")
    # dict trả cho pipeline.generate phải là CHÍNH dict của job → generate tự update là thấy ngay
    a["step"] = "titles…"
    assert snapshot("run-a")["step"] == "titles…"
    assert snapshot("run-b")["step"] == "tags…", "job kia KHÔNG được đổi theo"

    # ── Xong một cái, cái kia vẫn chạy ──
    finish("run-a")
    assert snapshot("run-a")["done"] and not snapshot("run-a")["running"]
    assert snapshot("run-b")["running"] and not snapshot("run-b")["done"]
    assert n_running() == 1

    # ── Lỗi của job này không dính sang job kia ──
    finish("run-b", error="hong roi")
    assert snapshot("run-b")["error"] == "hong roi"
    assert snapshot("run-a")["error"] is None, "lỗi không được lây"

    # ── Không hỏi run nào thì KHÔNG đoán bừa (bug cũ: trả job của người khác) ──
    _reset_for_test()
    _run("cua-nguoi-khac")
    s_ = snapshot()
    assert s_["no_run"] and not s_["running"] and s_["n_running"] == 1, s_
    assert s_["run"] == "", "phải trả rỗng, không được trả run của người khác"

    # ── Hỏi run KHÔNG tồn tại: nói rõ không thấy, đừng giả vờ đang chạy ──
    s_ = snapshot("khong-co")
    assert s_["found"] is False and not s_["running"] and not s_["done"], s_

    # ── QUÁ TRẦN THÌ XẾP HÀNG, KHÔNG ĐUỔI VỀ (đổi hành vi 2026-08-02) ──────────────────────
    _reset_for_test()
    for i in range(MAX_RUNNING):
        _run(f"r{i}")
    j4 = start("nguoi-thu-4")                      # KHÔNG raise nữa
    assert j4["queued"] and not j4["running"], j4
    s_ = snapshot("nguoi-thu-4")
    assert s_["ahead"] == 0 and "xếp hàng" in s_["step"], s_
    j5 = start("nguoi-thu-5")
    assert snapshot("nguoi-thu-5")["ahead"] == 1, snapshot("nguoi-thu-5")
    assert "còn 1 người" in snapshot("nguoi-thu-5")["step"], snapshot("nguoi-thu-5")["step"]
    assert n_running() == MAX_RUNNING and n_queued() == 2

    # người thứ 4 phải TỰ VÀO khi có chỗ — và đúng thứ tự bấm, không phải ai tỉnh trước
    got = []
    t4 = threading.Thread(target=lambda: got.append(("4", acquire("nguoi-thu-4", 5))))
    t5 = threading.Thread(target=lambda: got.append(("5", acquire("nguoi-thu-5", 5))))
    t5.start(); time.sleep(0.15)                   # người 5 chờ TRƯỚC, nhưng bấm SAU
    t4.start(); time.sleep(0.15)
    finish("r0")
    t4.join(6)
    assert got and got[0] == ("4", True), f"phải tới lượt người bấm TRƯỚC: {got}"
    assert not t5.is_alive() or n_running() == MAX_RUNNING
    finish("r1"); t5.join(6)
    assert ("5", True) in got, got

    # ── Hàng đợi có TRẦN, và nói rõ vì sao ──
    _reset_for_test()
    for i in range(MAX_RUNNING):
        _run(f"c{i}")
    for i in range(QUEUE_MAX):
        start(f"q{i}")
    try:
        start("giot-nuoc-tran-ly")
        raise AssertionError("hàng đầy thì phải từ chối")
    except RuntimeError as e:
        assert str(QUEUE_MAX) in str(e) and "đang chạy" in str(e), f"phải nói rõ: {e}"

    # ── Bấm lại đúng run ĐANG chạy / ĐANG chờ: chặn, kẻo 2 thread ghi cùng runs/<id>/ ──
    for r in ("c0", "q0"):
        try:
            start(r)
            raise AssertionError(f"phải chặn job trùng id: {r}")
        except RuntimeError as e:
            assert "đang chạy hoặc đang xếp hàng" in str(e), e

    # ── Chờ quá lâu thì bỏ cuộc, và nói rõ CHƯA tốn gì ──
    _reset_for_test()
    for i in range(MAX_RUNNING):
        _run(f"k{i}")
    start("cho-mai")
    assert acquire("cho-mai", timeout=1) is False
    s_ = snapshot("cho-mai")
    assert not s_["running"] and not s_["queued"] and "CHƯA sinh gì cả" in (s_["error"] or "")

    # ── Dọn job cũ nhưng TUYỆT ĐỐI không đụng job đang chạy / đang chờ ──
    _reset_for_test()
    _run("dang-chay")
    start("dang-cho")
    for i in range(KEEP + 10):
        _JOBS[f"xong{i}"] = _blank(f"xong{i}")
        _JOBS[f"xong{i}"].update(done=True, ended=time.time() - DONE_TTL - 10)
    _prune()
    assert _JOBS.get("dang-chay", {}).get("running"), "job đang chạy bị dọn mất"
    assert _JOBS.get("dang-cho", {}).get("queued"), "job đang XẾP HÀNG bị dọn mất"
    assert all(not r.startswith("xong") for r in _JOBS), "job xong quá hạn phải được dọn"

    # ── Nhiều thread cùng vào: không mất job, không vượt trần, không kẹt ──
    _reset_for_test()
    errs, ran = [], []
    peak = [0]

    def _w(i):
        try:
            start(f"t{i}")
            if acquire(f"t{i}", timeout=10):
                with _CV:
                    peak[0] = max(peak[0], n_running())
                ran.append(i)
                time.sleep(0.02)
                finish(f"t{i}")
        except RuntimeError:
            pass                                   # hàng đầy là kết quả HỢP LỆ, không phải lỗi
        except Exception as e:                     # noqa: BLE001
            errs.append(e)

    ts = [threading.Thread(target=_w, args=(i,)) for i in range(40)]
    [t.start() for t in ts]
    [t.join(20) for t in ts]
    assert not errs, errs
    assert peak[0] <= MAX_RUNNING, f"vượt trần: {peak[0]}"
    assert len(ran) >= MAX_RUNNING, len(ran)
    assert n_running() == 0, n_running()
    print(f"jobs.py self-test OK - qua tran thi XEP HANG (FIFO theo luc bam, {len(ran)}/40 chay "
          f"het, cao diem {peak[0]}<={MAX_RUNNING}), hang co tran va noi ro ly do, cho qua lau "
          "thi bao CHUA ton gi, 2 job song song khong lan trang thai, prune khong dung job "
          "dang chay/dang cho")
