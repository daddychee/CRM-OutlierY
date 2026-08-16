"""Job theo NGUOI (2026-07-16) — nhieu nguoi bam Viet cung luc khong de nhau.

Truoc day JOB la MOT dict global: nguoi bam sau `_reset()` xoa sach log/trang thai cua
nguoi truoc (C2 tung ghi "chua per-user"). Bo test nay khoa hanh vi moi:
  - moi user mot o; 2 user chay song song khong dam vao nhau;
  - cung user khong duoc chay 2 job cung luc (409);
  - 2 user KHAC nhau khong duoc ghi CUNG mot file (409 guard);
  - Huy chi cham job cua chinh minh;
  - chay local khong danh tinh (khong nginx) van hoat dong nhu ban cu.

Chay le:  .venv/bin/python -m pytest tests/test_jobs.py -q  (khong dot credit — luat C3)
"""
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voiceprofile import server as vp  # noqa: E402


@pytest.fixture(autouse=True)
def _sach_jobs():
    vp.JOBS.clear()
    yield
    vp.JOBS.clear()


def test_hai_user_chay_song_song_khong_de_nhau():
    """Loi goc: thanh dang viet, namtnghiem bam Viet -> log cua thanh bi xoa sach."""
    j1, e1 = vp._try_start("thanh", "writer", 0, script_path="/tmp/a/script.md")
    j2, e2 = vp._try_start("namtnghiem", "writer", 0, script_path="/tmp/b/script.md")
    assert j1 and j2 and e1 is None and e2 is None

    vp._log(j1, "chuong 1 cua thanh")
    vp._log(j2, "chuong 1 cua nam")
    assert j1["log"] == ["chuong 1 cua thanh"]          # khong lan sang nhau
    assert j2["log"] == ["chuong 1 cua nam"]
    assert j1["job_id"] != j2["job_id"]
    assert vp.JOBS[vp._job_key("thanh")] is j1


def test_cung_user_khong_chay_2_job_cung_luc():
    j1, _ = vp._try_start("thanh", "writer", 0, script_path="/tmp/a/s.md")
    j2, err = vp._try_start("thanh", "writer", 0, script_path="/tmp/khac/s.md")
    assert j1 and j2 is None
    assert "đang có job chạy" in err
    # job xong -> duoc chay tiep, o cu bi thay the
    with vp._LOCK:
        j1["running"] = False
    j3, err3 = vp._try_start("thanh", "extractor", 4, out="/tmp/o")
    assert j3 and err3 is None and vp.JOBS[vp._job_key("thanh")] is j3


def test_hai_user_khong_duoc_ghi_CUNG_file():
    """2 job cung script_path pha checkpoint {out}.progress.json + ban ky bien cua nhau."""
    j1, _ = vp._try_start("thanh", "writer", 0, script_path="/tmp/x/script.md")
    j2, err = vp._try_start("namtnghiem", "writer", 0, script_path="/tmp/x/script.md")
    assert j1 and j2 is None
    assert "thanh" in err and "đúng file này" in err
    # file khac -> di binh thuong
    j3, err3 = vp._try_start("namtnghiem", "writer", 0, script_path="/tmp/y/script.md")
    assert j3 and err3 is None


def test_hai_user_khong_extract_vao_CUNG_thu_muc():
    j1, _ = vp._try_start("Content", "extractor", 4, out="/tmp/A003")
    j2, err = vp._try_start("Ngoc", "extractor", 4, out="/tmp/A003")
    assert j1 and j2 is None and "Content" in err


def test_huy_chi_cham_job_cua_minh():
    j1, _ = vp._try_start("thanh", "writer", 0, script_path="/tmp/a/s.md")
    j2, _ = vp._try_start("namtnghiem", "writer", 0, script_path="/tmp/b/s.md")
    assert vp.cancel_job("thanh") is True
    assert j1["cancelled"].is_set()
    assert not j2["cancelled"].is_set()                 # job nguoi khac khong bi dung
    assert vp.cancel_job("Ngoc") is False               # khong co job -> False


def test_local_khong_danh_tinh_van_nhu_ban_cu():
    """Khong nginx -> user rong -> mot khoa chung: mot nguoi mot may, hanh vi cu."""
    j1, _ = vp._try_start("", "writer", 0, script_path="/tmp/a/s.md")
    j2, err = vp._try_start(None, "writer", 0, script_path="/tmp/b/s.md")
    assert j1 and j2 is None and "đang có job chạy" in err
    assert vp._job_key("") == vp._job_key(None) == vp.ANON_KEY


def test_public_khong_lo_proc_va_serialize_duoc():
    import json
    job, _ = vp._try_start("thanh", "writer", 0, script_path="/tmp/a/s.md")
    pub = vp._public(job)
    assert "proc" not in pub and "cancelled" not in pub
    json.dumps(pub)                                     # /api/status phai JSON-hoa duoc
    # hinh dang giu nguyen ban cu — frontend khong doi
    for k in ("running", "kind", "step", "step_i", "step_total", "log", "done",
              "error", "script_path", "user", "job_id", "started"):
        assert k in pub, k


def test_others_liet_ke_dong_nghiep_dang_chay():
    vp._try_start("thanh", "writer", 0, script_path="/tmp/a/script.md")
    vp._try_start("namtnghiem", "extractor", 4, out="/tmp/o")
    with vp._LOCK:
        others = vp._others_locked(vp._job_key("thanh"))
    assert [o["user"] for o in others] == ["namtnghiem"]
    assert others[0]["kind"] == "extractor"


def test_log_song_song_an_toan_thread():
    """2 thread ghi log 2 job cung luc — khong mat dong, khong lan o."""
    j1, _ = vp._try_start("a", "writer", 0, script_path="/tmp/1.md")
    j2, _ = vp._try_start("b", "writer", 0, script_path="/tmp/2.md")

    def pump(job, tag):
        for i in range(200):
            vp._log(job, f"{tag}-{i}")
    t1 = threading.Thread(target=pump, args=(j1, "a"))
    t2 = threading.Thread(target=pump, args=(j2, "b"))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert len(j1["log"]) == 200 and len(j2["log"]) == 200
    assert all(x.startswith("a-") for x in j1["log"])
    assert all(x.startswith("b-") for x in j2["log"])
