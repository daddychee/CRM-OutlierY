"""Test s5_server per-run (2026-07-22) — pipeline theo run + khoá song song + merged_sources.

Bối cảnh: trước đây PIPELINE là 1 dict global và board dùng 1 run dir global → 2 người
làm cùng lúc, người sau ĐÈ trạng thái/board của người trước. Bộ test này khoá hành vi mới:
mỗi run một trạng thái, tối đa MAX_PIPE run song song, S1* giữ YT_LOCK, S4* giữ EMBED_LOCK.
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from oe import common, s5_server as s5
from oe.s4c_consolidate import merge_clusters


def _wait(cond, timeout=5.0):
    t0 = time.time()
    while not cond():
        if time.time() - t0 > timeout:
            raise AssertionError("hết giờ chờ điều kiện")
        time.sleep(0.01)


class _LlmHong:
    """LLM luôn lỗi → merge_clusters đi nhánh fallback (nối thô), không gọi mạng."""
    def complete(self, *a, **k):
        raise RuntimeError("offline")


# ── merged_sources (#4) ─────────────────────────────────────────────────────

def _cum(name, brief="b", **kw):
    return {"name": name, "brief": brief, "videos": [], "member_gids": [],
            "questions": [], "coverage_n": 3, **kw}


def test_merge_luu_ten_cum_nguon():
    m = merge_clusters(_LlmHong(), [_cum("A"), _cum("B"), _cum("C")])
    assert m["merged_from"] == 3
    assert m["merged_sources"] == ["A", "B", "C"]


def test_merge_chong_ke_thua_nguon_goc():
    """Gộp một cụm-đã-gộp với cụm mới → danh sách nguồn là các cụm GỐC, không lấy tên trung gian."""
    da_gop = _cum("AB", merged_from=2, merged_sources=["A", "B"])
    m = merge_clusters(_LlmHong(), [da_gop, _cum("C"), _cum("A")])  # A trùng → khử
    assert m["merged_from"] == 4                    # đếm cộng dồn như cũ (2+1+1)
    assert m["merged_sources"] == ["A", "B", "C"]   # tên gốc, khử trùng, giữ thứ tự


# ── PIPELINES per-run + cap ─────────────────────────────────────────────────

def test_moi_run_mot_trang_thai_va_status_of_doc_dia(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "RUNS", tmp_path)
    monkeypatch.setattr(s5, "PIPELINES", {})
    # run đang chạy trong process
    s5.PIPELINES["run-a"] = dict(s5._blank("run-a"), running=True, step="S1")
    a = s5.status_of("run-a")
    assert a["running"] and a["run"] == "run-a"
    # run của process cũ (chỉ còn .pipeline.json trên đĩa) → đọc lại, running ép False
    st = dict(s5._blank("run-b"), running=True, completed=["S1 metadata + heatmap"])
    common.run_dir("run-b", create=True)
    s5._persist("run-b", st)
    b = s5.status_of("run-b")
    assert b["running"] is False and b["completed"] == ["S1 metadata + heatmap"]
    # run chưa từng chạy → trạng thái trắng, không nổ
    assert s5.status_of("run-c")["done"] is False


def test_start_pipeline_chan_trung_run_va_qua_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "RUNS", tmp_path)
    monkeypatch.setattr(s5, "PIPELINES", {})
    monkeypatch.setattr(s5, "MAX_PIPE", 1)
    tha = threading.Event()

    def _gia_lap(run_name, urls_text, *, resume=False):
        tha.wait(5)
        s5.PIPELINES[run_name]["running"] = False

    monkeypatch.setattr(s5, "_run_pipeline", _gia_lap)
    ok, err = s5.start_pipeline("run-a")
    assert ok
    ok2, err2 = s5.start_pipeline("run-a")              # double-click cùng run
    assert not ok2 and "đang chạy" in err2
    ok3, err3 = s5.start_pipeline("run-b")              # vượt cap
    assert not ok3 and "tối đa 1" in err3
    tha.set()
    _wait(lambda: not s5.PIPELINES["run-a"]["running"])
    ok4, _ = s5.start_pipeline("run-b")                 # slot trống → chạy được
    assert ok4
    tha.set()
    _wait(lambda: not s5.PIPELINES["run-b"]["running"])


def test_khoa_yt_va_embed_giu_dung_buoc(tmp_path, monkeypatch):
    """Chạy _run_pipeline thật với subprocess giả: bước S1* phải giữ YT_LOCK,
    S4* phải giữ EMBED_LOCK, các bước giữa không giữ khoá nào."""
    monkeypatch.setattr(common, "RUNS", tmp_path)
    monkeypatch.setattr(s5, "PIPELINES", {})
    giu = {}

    class _KQ:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def _fake_run(cmd, **kw):
        mod = cmd[2]                                    # [py, -m, module, ...]
        giu[mod] = (s5.YT_LOCK.locked(), s5.EMBED_LOCK.locked())
        return _KQ()

    monkeypatch.setattr(s5.subprocess, "run", _fake_run)
    s5._run_pipeline("run-x", "https://youtu.be/abc")
    st = s5.PIPELINES["run-x"]
    assert st["done"] and not st["error"]
    assert giu["oe.s1_ingest"] == (True, False)
    assert giu["oe.s1b_transcripts"] == (True, False)
    assert giu["oe.s2_peaks"] == (False, False)
    assert giu["oe.s4_cluster"] == (False, True)
    assert giu["oe.s4b_signals"] == (False, True)
    # khoá phải được NHẢ sau khi xong (nếu quên release, pipeline sau treo vĩnh viễn)
    assert not s5.YT_LOCK.locked() and not s5.EMBED_LOCK.locked()


def test_khoa_duoc_nha_khi_buoc_do(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "RUNS", tmp_path)
    monkeypatch.setattr(s5, "PIPELINES", {})

    class _KQ:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(s5.subprocess, "run", lambda *a, **k: _KQ())
    s5._run_pipeline("run-do", "https://youtu.be/abc")
    st = s5.PIPELINES["run-do"]
    assert st["error"] and not st["running"]
    assert not s5.YT_LOCK.locked() and not s5.EMBED_LOCK.locked()


def test_board_data_kem_run_va_danh_sach(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "RUNS", tmp_path)
    rd = common.run_dir("run-moi", create=True)
    common.write_json(rd / "clusters.json", [])
    d = s5._board_data(rd)
    assert d["run"] == "run-moi"
    assert d["runs"] == ["run-moi"]
