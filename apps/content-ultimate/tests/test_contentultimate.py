"""Test lớp nối Content Ultimate: catalog model cho dropdown + merge .env của tab Cài đặt.

Chạy lẻ:  .venv/bin/python tests/test_contentultimate.py   (hoặc qua pytest -q)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from contentultimate.server import merge_env                    # noqa: E402
from voiceprofile.llm import MODEL_CHOICES, available_model_choices  # noqa: E402


def test_model_choices_theo_key():
    # chỉ GLM có key -> đúng 2 lựa chọn GLM, thứ tự như catalog
    ids = [m["id"] for m in available_model_choices({"GLM_API_KEY": "x"})]
    assert ids == ["glm:glm-5", "glm:glm-5.2"]
    # đủ 2 key -> đủ 4 lựa chọn (yêu cầu team: Sonnet/Opus/GLM 5.0/GLM 5.2)
    both = available_model_choices({"GLM_API_KEY": "x", "ANTHROPIC_API_KEY": "y"})
    assert [m["label"] for m in both] == ["Claude Sonnet", "Claude Opus", "GLM 5.0", "GLM 5.2"]
    # không key nào -> rỗng
    assert available_model_choices({}) == []
    # id thật của "GLM 5.0" trên z.ai là glm-5 (đo endpoint /models 2026-07-08)
    assert {m["model"] for m in MODEL_CHOICES if m["provider"] == "glm"} == {"glm-5", "glm-5.2"}


def test_merge_env_update_them_va_tat():
    text = "# ghi chú giữ nguyên\nGLM_API_KEY=old\n#ANTHROPIC_API_KEY=\nOTHER=keep\n"
    out = merge_env(text, {"GLM_API_KEY": "new", "ANTHROPIC_API_KEY": "sk-abc",
                           "YOUTUBE_API_KEY": "AIza1"})
    assert "GLM_API_KEY=new" in out
    assert "ANTHROPIC_API_KEY=sk-abc" in out          # dòng comment được kích hoạt lại
    assert "YOUTUBE_API_KEY=AIza1" in out             # key chưa có thì thêm cuối file
    assert "# ghi chú giữ nguyên" in out and "OTHER=keep" in out

    # value rỗng -> comment dòng lại (tắt key, không mất dấu vết)
    out2 = merge_env(out, {"GLM_API_KEY": ""})
    assert "GLM_API_KEY=new" not in out2 and "# GLM_API_KEY=" in out2


def test_merge_env_khu_dong_trung_key():
    # parser .env last-wins -> dòng active trùng key phía sau phải bị vô hiệu hoá
    out = merge_env("A_KEY=1\nA_KEY=2\n", {"A_KEY": "3"})
    lines = out.splitlines()
    assert lines[0] == "A_KEY=3" and lines[1].startswith("#")


def test_merge_env_chan_injection_xuong_dong():
    # bảo mật 2026-07-09: value chứa \n không được chèn biến .env khác
    out = merge_env("", {"ADMIN_USERS": "thanh\nHTPASSWD_FILE=/etc/passwd"})
    assert "ADMIN_USERS=thanh" in out
    assert "HTPASSWD_FILE" not in out           # phần sau \n bị cắt, không thành biến mới
    assert "\r" not in out


def test_khoa_moi_vong_doi(tmp_path, monkeypatch):
    import contentultimate.server as cu

    monkeypatch.setattr(cu, "INVITES_PATH", tmp_path / "invites.json")
    ht = tmp_path / ".htpasswd"
    ht.write_text("thanh:$2y$fakehash\n", encoding="utf-8")
    added = []
    fake_add = lambda f, u, p: added.append((u, p))  # noqa: E731 — không gọi htpasswd thật

    inv = cu._create_invite()
    # sai token / tên xấu / mật khẩu ngắn / tên đã tồn tại -> từ chối, khóa CHƯA bị đốt
    assert cu._accept_invite("sai-token", "lan", "12345678", htfile=ht, add_user=fake_add)[0] is False
    assert cu._accept_invite(inv["token"], "lan xinh", "12345678", htfile=ht, add_user=fake_add)[0] is False
    assert cu._accept_invite(inv["token"], "lan", "ngan", htfile=ht, add_user=fake_add)[0] is False
    assert cu._accept_invite(inv["token"], "thanh", "12345678", htfile=ht, add_user=fake_add)[0] is False
    assert added == []
    # hợp lệ -> tạo tài khoản, khóa thành đã-dùng, dùng lại phải bị chặn
    ok, msg = cu._accept_invite(inv["token"], "lan", "matkhau123", htfile=ht, add_user=fake_add)
    assert ok and added == [("lan", "matkhau123")]
    assert cu._load_invites()[0]["used_by"] == "lan"
    assert cu._accept_invite(inv["token"], "mai", "matkhau123", htfile=ht, add_user=fake_add)[0] is False
    # khóa hết hạn -> từ chối
    inv2 = cu._create_invite()
    lst = cu._load_invites()
    next(i for i in lst if i["token"] == inv2["token"])["expires"] = 1.0
    cu._save_invites(lst)
    assert cu._accept_invite(inv2["token"], "mai", "matkhau123", htfile=ht, add_user=fake_add)[0] is False


def test_luu_cookies(tmp_path, monkeypatch):
    import contentultimate.server as cu

    monkeypatch.setattr(cu, "COOKIES_PATH", tmp_path / "cookies.txt")
    # rác (copy từ DevTools, không tab / không youtube.com) -> từ chối, không ghi file
    assert cu._save_cookies("SIDCC=abc; VISITOR=xyz")[0] is False
    assert cu._save_cookies("linkedin.com\tTRUE\t/\tFALSE\t0\ta\tb")[0] is False
    assert not (tmp_path / "cookies.txt").exists()
    # đúng định dạng nhưng CHƯA đăng nhập (chỉ cookie khách) -> lưu kèm cảnh báo
    ok, msg = cu._save_cookies("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tVISITOR_INFO1_LIVE\tx")
    assert ok and (tmp_path / "cookies.txt").exists() and "thiếu cookie đăng nhập" in msg
    # có cookie đăng nhập -> lưu sạch, không cảnh báo
    ok, msg = cu._save_cookies("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tLOGIN_INFO\tx")
    assert ok and msg == "đã lưu"
    assert cu._cookies_status()["exists"] and cu._cookies_status()["n_lines"] == 1
    # nội dung rỗng KHÔNG được xóa file (bug thật 2026-07-09: Lưu-ô-trống nuốt cookies)
    assert cu._save_cookies("")[0] is False
    assert (tmp_path / "cookies.txt").exists()


def test_luu_cookies_atomic_ghi_de_file_khong_ghi_duoc(tmp_path, monkeypatch):
    # bug thật 2026-07-10: cookies.txt cũ read-only (mô phỏng root-owned) → ghi atomic
    # qua os.replace vẫn thành công vì chỉ cần quyền ghi THƯ MỤC.
    import contentultimate.server as cu

    ck = tmp_path / "cookies.txt"
    monkeypatch.setattr(cu, "COOKIES_PATH", ck)
    ck.write_text("# cũ\n.youtube.com\tTRUE\t/\tTRUE\t0\tOLD\tx", encoding="utf-8")
    ck.chmod(0o400)                                  # file chỉ đọc, nhưng thư mục ghi được
    ok, _ = cu._save_cookies(
        "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tLOGIN_INFO\tnew")
    assert ok and "LOGIN_INFO" in ck.read_text(encoding="utf-8")


def test_duong_dan_tai_ve_an_toan(tmp_path, monkeypatch):
    import voiceprofile.server as vs

    monkeypatch.setattr(vs, "_REPO_ROOT", tmp_path)
    (tmp_path / "runs").mkdir()
    f = tmp_path / "runs" / "script.md"
    f.write_text("x", encoding="utf-8")
    assert vs._safe_download_path(str(f)) == f.resolve()          # file .md trong root: OK
    assert vs._safe_download_path("/etc/passwd") is None          # ngoài root
    assert vs._safe_download_path(str(tmp_path / "runs" / ".." / ".." / "etc" / "passwd")) is None
    py = tmp_path / "x.py"
    py.write_text("x", encoding="utf-8")
    assert vs._safe_download_path(str(py)) is None                # đuôi không cho phép
    assert vs._safe_download_path(str(tmp_path / "khong-ton-tai.md")) is None
    assert vs._safe_download_path("") is None


def test_download_chan_credential(tmp_path, monkeypatch):
    # bảo mật 2026-07-09: /api/download KHÔNG được trả cookies.txt / videos.txt / .env
    import voiceprofile.server as vs

    monkeypatch.setattr(vs, "_REPO_ROOT", tmp_path)
    (tmp_path / "runs").mkdir()
    for name in ("cookies.txt", "videos.txt", ".env", "library.json"):
        (tmp_path / name).write_text("SECRET", encoding="utf-8")
    (tmp_path / "runs" / "script.md").write_text("ok", encoding="utf-8")
    (tmp_path / "runs" / "dataset.jsonl").write_text("{}", encoding="utf-8")
    # deliverable .md/.jsonl trong tool: cho tải
    assert vs._safe_download_path(str(tmp_path / "runs" / "script.md"))
    assert vs._safe_download_path(str(tmp_path / "runs" / "dataset.jsonl"))
    # credential: chặn hết
    assert vs._safe_download_path(str(tmp_path / "cookies.txt")) is None
    assert vs._safe_download_path(str(tmp_path / "videos.txt")) is None
    assert vs._safe_download_path(str(tmp_path / ".env")) is None
    assert vs._safe_download_path(str(tmp_path / "library.json")) is None
    assert vs._safe_download_path("/etc/passwd") is None


def test_chan_brute_force_theo_ip():
    import contentultimate.server as cu

    cu._ACCEPT_FAILS.clear()
    assert all(cu._accept_guard("1.2.3.4", limit=3) for _ in range(3))
    assert cu._accept_guard("1.2.3.4", limit=3) is False   # lần 4 trong cửa sổ -> chặn
    assert cu._accept_guard("5.6.7.8", limit=3) is True    # IP khác không bị vạ lây
    cu._ACCEPT_FAILS.clear()


if __name__ == "__main__":
    test_model_choices_theo_key()
    test_merge_env_update_them_va_tat()
    test_merge_env_khu_dong_trung_key()
    print("OK — 3 test contentultimate")
