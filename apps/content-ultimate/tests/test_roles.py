"""Phan quyen 2 vai (user chot 2026-07-16): Creator dung 3 tool · Leader them trang
Quan ly · Admin (ADMIN_USERS) dung tren vai — them Cai dat (key, thanh vien, GAN QUYEN).

Chay le:  .venv/bin/python -m pytest tests/test_roles.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from contentultimate import server as m  # noqa: E402


class _H(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)


class FakeH:
    def __init__(self, user=None):
        self.headers = _H({"X-Remote-User": user} if user else {})


@pytest.fixture
def env(tmp_path, monkeypatch):
    ht = tmp_path / ".htpasswd"
    ht.write_text("thanh:x\nNgoc:y\nContent:z\n", encoding="utf-8")
    monkeypatch.setattr(m, "_htpasswd_file", lambda: ht)
    monkeypatch.setattr(m, "_env_dict", lambda: {"ADMIN_USERS": "thanh"})
    monkeypatch.setattr(m, "ROLES_PATH", tmp_path / "roles.json")
    monkeypatch.setattr(m, "_htpasswd_add", lambda f, u, p: None)
    monkeypatch.setattr(m, "_htpasswd_remove", lambda f, u: None)
    return m


# --- gan quyen ------------------------------------------------------------------------

def test_gan_leader_va_ha_ve_creator(env):
    code, out = env._manage_users({"action": "role", "user": "Ngoc", "role": "leader"}, "thanh")
    assert code == 200 and "Leader" in out["msg"]
    assert env._role_of("Ngoc") == "leader"
    # ha ve creator -> XOA khoi roles.json (creator = mac dinh, khong ghi thua)
    code, _ = env._manage_users({"action": "role", "user": "Ngoc", "role": "creator"}, "thanh")
    assert code == 200 and env._load_roles() == {}


def test_quyen_rac_bi_tu_choi(env):
    for bad in ("admin", "boss", "", "LEADER2"):
        code, out = env._manage_users({"action": "role", "user": "Ngoc", "role": bad}, "thanh")
        assert code == 422 and "creator hoặc leader" in out["error"], bad


def test_khong_gan_cho_nguoi_khong_ton_tai_va_admin(env):
    code, _ = env._manage_users({"action": "role", "user": "ai-do", "role": "leader"}, "thanh")
    assert code == 422
    code, out = env._manage_users({"action": "role", "user": "thanh", "role": "leader"}, "thanh")
    assert code == 422 and "đứng trên vai trò" in out["error"]


def test_xoa_thanh_vien_don_luon_quyen(env):
    env._manage_users({"action": "role", "user": "Ngoc", "role": "leader"}, "thanh")
    assert env._load_roles() == {"Ngoc": "leader"}
    env._manage_users({"action": "remove", "user": "Ngoc"}, "thanh")
    assert env._load_roles() == {}                    # khong de "quyen ma" cua nguoi da xoa


# --- cong _can_manage -------------------------------------------------------------------

def test_ma_tran_quyen(env):
    env._manage_users({"action": "role", "user": "Ngoc", "role": "leader"}, "thanh")
    assert env._can_manage(FakeH("thanh")) is True        # admin
    assert env._can_manage(FakeH("Ngoc")) is True         # leader
    assert env._can_manage(FakeH("Content")) is False     # creator
    assert env._can_manage(FakeH(None)) is False          # khong danh tinh (sau nginx)


def test_local_khong_ADMIN_USERS_thi_mo_het_nhu_cu(env, monkeypatch):
    monkeypatch.setattr(env, "_env_dict", lambda: {})
    assert env._can_manage(FakeH(None)) is True           # che do may ca nhan


def test_roles_json_rach_khong_khoa_ca_team(env, monkeypatch, tmp_path):
    bad = tmp_path / "roles.json"
    bad.write_text("{khong-phai-json", encoding="utf-8")
    monkeypatch.setattr(env, "ROLES_PATH", bad)
    assert env._load_roles() == {}                        # rach -> creator het, khong crash
    assert env._role_of("Ngoc") == "creator"


def test_users_payload_co_role(env, monkeypatch, tmp_path):
    monkeypatch.setattr(env.vp_usage, "read_rows", lambda *a, **k: [])
    monkeypatch.setattr(env, "_load_invites", lambda: [])
    env._save_roles({"Ngoc": "leader"})
    d = env._users_payload()
    by = {u["user"]: u for u in d["users"]}
    assert by["Ngoc"]["role"] == "leader"
    assert by["Content"]["role"] == "creator"             # khong co trong roles -> mac dinh
    assert by["thanh"]["admin"] is True


def test_js_nhung_trong_python_khong_bi_nuot_escape():
    """Loi that 2026-07-17: ghi \\n MOT gach cheo vao chuoi HTML trong server.py —
    Python parse thanh XUONG DONG THAT truoc khi phuc vu -> chuoi JS bi ngat giua chung
    -> SyntaxError dong 268 -> toan bo JS trang Cai dat chet (user chup man hinh bao).
    node --check tren VAN BAN FILE khong bat duoc (o tang file \\n van hop le) —
    PHAI kiem tren HANG SO RUNTIME sau khi Python parse."""
    bs = chr(92)
    # hai chuoi prompt phai con nguyen escape \n o RUNTIME (khong phai xuong dong that)
    assert ('?' + bs + 'n' + bs + 'n' + 'Mật khẩu của họ') in m.SETTINGS_HTML
    assert ('ký tự).' + bs + 'n' + bs + 'n' + 'Tự đưa cho họ') in m.SETTINGS_HTML
    # tong quat: khong dong nao trong <script> ket thuc bang chuoi confirm/prompt mo dang do
    import re
    for html in (m.SETTINGS_HTML, m.MANAGE_HTML, m.HOME, m.INVITE_HTML):
        for js in re.findall(r"<script>(.*?)</script>", html, re.S):
            for ln in js.splitlines():
                if "confirm('" in ln or "prompt('" in ln:
                    assert ln.rstrip().endswith((")", ");", "return;", "{")) or "'" not in ln.split("confirm('")[-1] or ln.count("'") % 2 == 0, ln[:80]
