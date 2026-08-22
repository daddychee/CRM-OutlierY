"""Test so ghi van hanh + tab Quan ly: token, nhat ky job, ban ky bien, thanh vien.

Chay le:  .venv/bin/python -m pytest tests/test_usage.py -q
Khong dot credit: khong goi API that o day (luat C3).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voiceprofile import usage                                   # noqa: E402


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """So ghi tro vao tmp — khong dung admin/ that cua may."""
    monkeypatch.setattr(usage, "ADMIN_DIR", tmp_path / "admin")
    monkeypatch.delenv("CU_USER", raising=False)
    monkeypatch.delenv("CU_JOB", raising=False)
    return tmp_path / "admin"


def test_ghi_token_gan_dung_nguoi_va_dung_job(ledger, monkeypatch):
    monkeypatch.setenv("CU_USER", "namtnghiem")
    monkeypatch.setenv("CU_JOB", "abc123")
    usage.record_usage("glm", "glm-5.2", 100, 250, kind="chapter")
    rows = usage.read_rows(usage.USAGE)
    assert len(rows) == 1
    assert rows[0]["user"] == "namtnghiem" and rows[0]["job"] == "abc123"
    assert rows[0]["in"] == 100 and rows[0]["out"] == 250


def test_khong_co_CU_USER_thi_nac_danh(ledger):
    usage.record_usage("glm", "glm-5.2", 1, 2)
    assert usage.read_rows(usage.USAGE)[0]["user"] == usage.ANON


def test_doc_usage_dang_openai_that_cua_zai(ledger):
    # Hinh dang do bang probe key that 2026-07-15 — giu test bam vao hinh dang THAT.
    real = {"prompt_tokens": 12, "completion_tokens": 14, "total_tokens": 26,
            "prompt_tokens_details": {"cached_tokens": 5},
            "completion_tokens_details": {"reasoning_tokens": 3}}
    usage.record_openai_usage(real, "glm", "glm-5.2", kind="beat")
    r = usage.read_rows(usage.USAGE)[0]
    assert (r["in"], r["out"], r["cached"], r["reasoning"]) == (12, 14, 5, 3)


def test_usage_rong_hoac_rac_khong_gay(ledger):
    usage.record_openai_usage(None, "glm", "m")
    usage.record_openai_usage("khong phai dict", "glm", "m")
    usage.record_openai_usage({"prompt_tokens": None, "completion_tokens": None}, "glm", "m")
    assert len(usage.read_rows(usage.USAGE)) == 1        # chi cai dict rong duoc ghi


def test_so_ghi_hong_khong_bao_gio_giet_job(tmp_path, monkeypatch):
    # Day o cung / khong co quyen ghi: phai NUOT loi, khong nem ra ngoai (luat A6).
    monkeypatch.setattr(usage, "ADMIN_DIR", tmp_path / "khong-the-tao")
    monkeypatch.setattr(usage.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only fs")))
    usage.record_usage("glm", "m", 1, 2)                 # khong duoc nem
    usage.record_job({"kind": "writer"})
    usage.record_access("thanh", "1.2.3.4", "/")


def test_dong_rach_bi_bo_qua_chu_khong_gay_tab(ledger):
    usage.record_usage("glm", "m", 1, 2)
    (ledger / usage.USAGE).open("a", encoding="utf-8").write('{"ts": 1, "in": khong-phai-json\n')
    usage.record_usage("glm", "m", 3, 4)
    rows = usage.read_rows(usage.USAGE)
    assert [r["in"] for r in rows] == [1, 3]            # dong giua bi bo, 2 dong tot con nguyen


def test_read_rows_loc_theo_since(ledger):
    usage.record_usage("glm", "m", 1, 1)
    rows = usage.read_rows(usage.USAGE, since=usage.time.time() + 100)
    assert rows == []


# --- Ban ky bien: khong bao gio de len nhau -----------------------------------------

def test_snapshot_giu_moi_ban_khong_de_len_nhau(tmp_path, monkeypatch):
    from voiceprofile import server as vp

    monkeypatch.setattr(usage, "ADMIN_DIR", tmp_path / "admin")
    script = tmp_path / "A003" / "script.md"
    script.parent.mkdir(parents=True)
    script.write_text("ban 1", encoding="utf-8")
    (script.parent / "script.outline.txt").write_text("Title: Tap 1", encoding="utf-8")

    j1 = {"user": "thanh", "started": 1_800_000_000.0}
    v1 = vp._snapshot(j1, str(script), "done")
    script.write_text("ban 2 — da viet lai", encoding="utf-8")
    j2 = {"user": "namtnghiem", "started": 1_800_000_060.0}
    v2 = vp._snapshot(j2, str(script), "done")

    assert v1 and v2 and v1 != v2
    # Ban cu VAN CON sau khi script.md bi ghi de — day la ca diem cua tinh nang.
    assert Path(v1).read_text(encoding="utf-8") == "ban 1"
    assert Path(v2).read_text(encoding="utf-8") == "ban 2 — da viet lai"
    assert "thanh" in Path(v1).name and "namtnghiem" in Path(v2).name
    assert Path(v1).with_suffix("").with_suffix(".outline.txt").is_file()
    assert script.read_text(encoding="utf-8") == "ban 2 — da viet lai"   # con tro moi nhat


def test_snapshot_danh_dau_trang_thai_va_ten_user_ban(tmp_path, monkeypatch):
    from voiceprofile import server as vp

    monkeypatch.setattr(usage, "ADMIN_DIR", tmp_path / "admin")
    script = tmp_path / "script.md"
    script.write_text("do dang", encoding="utf-8")
    j = {"user": "../../etc/passwd", "started": 1_800_000_000.0}
    v = vp._snapshot(j, str(script), "cancelled")
    assert "cancelled" in Path(v).name
    # Tinh chat an toan THAT: ten user rac khong the day file ra ngoai history/.
    # ("/" bi khu thanh "_" nen ".." con lai chi la ky tu trong ten file, vo hai.)
    assert "/" not in Path(v).name
    assert Path(v).resolve().parent == (script.parent / "history").resolve()


def test_snapshot_file_khong_ton_tai_thi_im_lang(tmp_path, monkeypatch):
    from voiceprofile import server as vp
    monkeypatch.setattr(usage, "ADMIN_DIR", tmp_path / "admin")
    assert vp._snapshot({"user": "x", "started": 0.0}, str(tmp_path / "chua-co.md"), "error") == ""


def test_outline_title_lay_dong_Title(tmp_path):
    from voiceprofile import server as vp
    assert vp._outline_title("Title: Sagittarius A*\nHOOK\n") == "Sagittarius A*"
    assert vp._outline_title("\n\nHOOK gi do\n") == "HOOK gi do"
    assert vp._outline_title("") == ""


# --- Quan ly thanh vien --------------------------------------------------------------

@pytest.fixture
def cu(tmp_path, monkeypatch):
    from contentultimate import server as m

    ht = tmp_path / ".htpasswd"
    ht.write_text("thanh:x\nnamtnghiem:y\n", encoding="utf-8")
    monkeypatch.setattr(m, "_htpasswd_file", lambda: ht)
    monkeypatch.setattr(m, "_env_dict", lambda: {"ADMIN_USERS": "thanh"})
    added, removed = [], []
    monkeypatch.setattr(m, "_htpasswd_add", lambda f, u, p: added.append((u, p)))
    monkeypatch.setattr(m, "_htpasswd_remove", lambda f, u: removed.append(u))
    m._added, m._removed = added, removed
    return m


def test_them_thanh_vien(cu):
    code, out = cu._manage_users({"action": "add", "user": "lan", "password": "matkhau123"}, "thanh")
    assert code == 200 and out["ok"] and cu._added == [("lan", "matkhau123")]


def test_khong_them_trung_ten(cu):
    code, out = cu._manage_users({"action": "add", "user": "namtnghiem", "password": "matkhau123"}, "thanh")
    assert code == 422 and "đã có người dùng" in out["error"] and cu._added == []


def test_mat_khau_ngan_bi_tu_choi(cu):
    code, out = cu._manage_users({"action": "add", "user": "lan", "password": "ngan"}, "thanh")
    assert code == 422 and "8 ký tự" in out["error"] and cu._added == []


def test_ten_dang_nhap_rac_bi_tu_choi(cu):
    for bad in ("a", "co khoang trang", "../etc", "x" * 33, ""):
        code, _ = cu._manage_users({"action": "add", "user": bad, "password": "matkhau123"}, "thanh")
        assert code == 422, bad
    assert cu._added == []


def test_xoa_thanh_vien(cu):
    code, out = cu._manage_users({"action": "remove", "user": "namtnghiem"}, "thanh")
    assert code == 200 and cu._removed == ["namtnghiem"]


def test_khong_the_tu_xoa_minh(cu):
    code, out = cu._manage_users({"action": "remove", "user": "thanh"}, "thanh")
    assert code == 422 and "tự xoá" in out["error"] and cu._removed == []


def test_khong_xoa_duoc_quan_tri_vien_dang_trong_ADMIN_USERS(cu):
    # thanh la admin; ke ca nguoi khac cung khong xoa duoc truoc khi go khoi ADMIN_USERS
    code, out = cu._manage_users({"action": "remove", "user": "thanh"}, "namtnghiem")
    assert code == 422 and "ADMIN_USERS" in out["error"] and cu._removed == []


def test_reset_mat_khau_ghi_de_hash(cu):
    code, out = cu._manage_users({"action": "reset", "user": "namtnghiem", "password": "matkhaumoi1"}, "thanh")
    assert code == 200 and cu._added == [("namtnghiem", "matkhaumoi1")]


def test_reset_nguoi_khong_ton_tai(cu):
    code, out = cu._manage_users({"action": "reset", "user": "khongcoai", "password": "matkhau123"}, "thanh")
    assert code == 422 and cu._added == []


def test_chua_cau_hinh_htpasswd_thi_bao_tu_te(cu, monkeypatch):
    monkeypatch.setattr(cu, "_htpasswd_file", lambda: None)
    code, out = cu._manage_users({"action": "add", "user": "lan", "password": "matkhau123"}, "thanh")
    assert code == 422 and "HTPASSWD_FILE" in out["error"]


# --- Dau hieu bat thuong (KHONG phai ket luan) ---------------------------------------

def test_canh_bao_khi_nhieu_IP_trong_24h(cu):
    users = [{"user": "namtnghiem", "ips_24h": ["1.1.1.1", "2.2.2.2", "3.3.3.3"]},
             {"user": "thanh", "ips_24h": ["9.9.9.9"]}]
    alerts = cu._alerts(users)
    assert len(alerts) == 1 and "namtnghiem" in alerts[0] and "3 IP" in alerts[0]
    # Phai noi ro day chi la DAU HIEU, khong ket luan bi lo (tranh bao dong gia).
    assert "có thể" in alerts[0]


def test_khong_canh_bao_khi_it_IP(cu):
    assert cu._alerts([{"user": "thanh", "ips_24h": ["1.1.1.1", "2.2.2.2"]}]) == []


# --- Whitelist doc file (luat C2) ----------------------------------------------------

def test_history_file_chi_cho_doc_ban_da_ghi_so(ledger, monkeypatch):
    from contentultimate import server as m
    monkeypatch.setattr(m, "vp_usage", usage)
    usage.record_job({"kind": "writer", "version": "/opt/x/history/20260715-thanh.md"})
    ok = m._history_files()
    assert "/opt/x/history/20260715-thanh.md" in ok
    assert "/opt/x/history/20260715-thanh.outline.txt" in ok   # outline di kem
    assert "/opt/content-ultimate/.env" not in ok              # khong bao gio
    assert "/opt/content-ultimate/cookies.txt" not in ok


# --- "Toi dang la ai" (bai hoc 2026-07-15) -------------------------------------------

class _FakeHeaders(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)


class _FakeH:
    """Handler gia — chi can .headers cho _whoami_bar/_forbidden_page."""
    def __init__(self, user=None):
        self.headers = _FakeHeaders({"X-Remote-User": user} if user else {})


def test_dai_whoami_hien_dung_ten_va_nhan_quan_tri(cu, monkeypatch):
    monkeypatch.setattr(cu, "_env_dict", lambda: {"ADMIN_USERS": "thanh"})
    admin = cu._whoami_bar(_FakeH("thanh"))
    assert "thanh" in admin and "quản trị viên" in admin
    # Nguoi thuong: KHONG duoc gan nhan quan tri (nham la hieu sai quyen cua minh)
    thuong = cu._whoami_bar(_FakeH("Ngoc"))
    assert "Ngoc" in thuong and "quản trị viên" not in thuong
    assert "/logout" in thuong and "Thoát" in thuong


def test_chay_local_khong_nginx_thi_khong_bia_danh_tinh(cu):
    # Khong co X-Remote-User => khong co danh tinh THAT => khong hien gi (luat A1)
    assert cu._whoami_bar(_FakeH(None)) == ""


def test_ten_user_rac_bi_escape_trong_dai(cu, monkeypatch):
    monkeypatch.setattr(cu, "_env_dict", lambda: {"ADMIN_USERS": "thanh"})
    bar = cu._whoami_bar(_FakeH('<script>alert(1)</script>'))
    assert "<script>" not in bar and "&lt;script&gt;" in bar


def test_trang_403_noi_ro_ban_la_ai_va_ai_moi_la_admin(cu, monkeypatch):
    monkeypatch.setattr(cu, "_env_dict", lambda: {"ADMIN_USERS": "thanh"})
    html = cu._forbidden_page(_FakeH("Ngoc")).decode("utf-8")
    # Chinh su TRONG KHONG cua trang 403 cu lam user tuong tool hong/khong co auth.
    assert "Ngoc" in html                      # ban dang la ai
    assert "thanh" in html                     # ai moi la admin
    assert "/logout" in html                   # loi ra


def test_run_cli_ghi_ly_do_loi_vao_job_22_08(monkeypatch):
    """Buoc CLI that bai PHAI de lai ly do trong job (so nhat ky doc tu day).

    Do that 22/08 tren history.jsonl: 4/8 luot writer hong co error=None, vi
    _run_cli chi ghi vao LOG TIEN TRINH (song trong RAM, mat khi restart).
    Hong ma khong truy duoc nguyen nhan la mat luon duong chan doan.
    """
    import subprocess, threading
    import voiceprofile.server as vs

    class ProcGia:
        def __init__(self):
            NL = chr(10)
            self.stdout = iter(["dang chay" + NL,
                                "Traceback (most recent call last):" + NL,
                                "RuntimeError: het han muc API" + NL])
        def wait(self): return 1

    monkeypatch.setattr(vs.subprocess, "Popen", lambda *a, **k: ProcGia())
    job = {"cancelled": threading.Event(), "log": [], "proc": None,
           "user": "u", "job_id": "j"}
    ok = vs._run_cli(job, ["write"], "WRITE", True)
    assert ok is False
    assert job.get("error"), "job phai mang ly do loi"
    assert "WRITE" in job["error"] and "het han muc API" in job["error"]


def test_so_tac_gia_duong_dan_tuong_doi_va_cuu_di_san_22_08(tmp_path, monkeypatch):
    """So dang ky phai song sot khi DOI MAY (di tru 22/08).

    Benh that: index.json luu duong dan TUYET DOI; sau VPS -> o C -> o D thi 10/14 entry tro vao cho khong con, app chi thay 4
    ho so du FILE VAN NAM NGUYEN trong kho. Luat moi: kho hien tai la NGUON SU
    THAT — tim theo duoi duong dan trong kho truoc, ke ca khi duong cu con song
    (A011-A013 tro he cu o o C, da tat va se xoa ~22/09).
    """
    import importlib
    kho = tmp_path / "kho"
    (kho / "uploads" / "A009_LeoKim").mkdir(parents=True)
    (kho / "uploads" / "A009_LeoKim" / "profile.json").write_text("{}", encoding="utf-8")
    dich = kho / "uploads" / "A009_LeoKim" / "profile.json"
    monkeypatch.setenv("CU_DATA_DIR", str(kho))
    import voiceprofile.library as lib
    lib = importlib.reload(lib)

    # (a) ban ghi di san POSIX cua VPS — tren Windows khong tinh la 'absolute'
    assert lib.duong_that("/opt/content-ultimate/uploads/A009_LeoKim/profile.json") == dich
    # (b) ban ghi di san Windows cua he cu
    assert lib.duong_that("C:\\OutlierY\\apps\\content-ultimate\\uploads\\A009_LeoKim\\profile.json") == dich
    # (c) duong tuong doi trong so
    assert lib.duong_that("uploads/A009_LeoKim/profile.json") == dich
    # (d) ghi vao so thi luu TUONG DOI
    assert lib.duong_luu(dich) == "uploads/A009_LeoKim/profile.json"
    # (e) khong tim thay o dau -> tra nguyen, list_authors tu loc
    assert not lib.duong_that("/tmp/vfy2/Beta/out/profile.json").is_file()
