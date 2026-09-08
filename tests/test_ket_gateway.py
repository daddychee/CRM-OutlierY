# -*- coding: utf-8 -*-
"""Test két nối gateway (P3): /general/ai-models chỉ Owner (giỏ tuyệt đối — Admin ủy quyền
cũng KHÔNG vào được), API loopback, key write-only."""
import asyncio

import bcrypt
import httpx
import pytest
from fastapi.testclient import TestClient

from nen.gateway.main import app as gateway_app
from nen.iam import iam
from nen.ket_cau_hinh import ket

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def he(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))   # quota log về tmp
    # SỔ GỌI đọc biến RIÊNG — thiếu dòng này thì test ghi vào sổ THẬT (đã dính
    # 03/09: 28 dòng rác lọt vào số liệu quota Owner đang xem). conftest ROOT
    # cũng chặn, đây là lớp hai để fixture tự đứng được.
    monkeypatch.setenv("SO_GOI_DIR", str(tmp_path / "so-goi"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-test", "MatKhau123", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "admin", "MatKhau123", "Kinh doanh", 4,
                      phai_doi_mk=False)
    iam.sua_tai_khoan(conn, ow, "admin", admin_uy_quyen=True)
    conn.close()


@pytest.fixture()
def client(he):
    return TestClient(gateway_app, follow_redirects=False)


def _login(client, ten, mk):
    return client.post("/login", data={"ten": ten, "mat_khau": mk})


def test_cai_dat_admin_uy_quyen_van_403(client):
    _login(client, "admin", "MatKhau123")
    assert client.get("/general/api-keys").status_code == 403   # giỏ Owner tuyệt đối


def test_ai_models_nghi_huu_redirect(client):
    """Trang 'AI Models' tự chế nghỉ hưu (Owner lệnh 16/08 — vi phạm quy trình
    duyệt mockup): GET redirect sang /general/api-keys; POST llm cũ GIỮ làm
    backend fallback."""
    _login(client, "owner-test", "MatKhau123")
    r = client.get("/general/ai-models")
    assert r.status_code == 303
    assert r.headers["location"] == "/general/api-keys"


def test_owner_luu_vai_llm_va_key_write_only(client):
    """Backend fallback llm.<vai>.* cũ vẫn chạy; trang API Keys MIGRATE mục cũ
    thành khóa (idempotent) và chỉ hiện ĐUÔI — không bao giờ render lại key."""
    _login(client, "owner-test", "MatKhau123")
    assert client.get("/general/api-keys").status_code == 200
    r = client.post("/general/ai-models/llm", data={
        "vai": "writer", "provider": "openai_compatible", "model": "glm-4.5-air",
        "base_url": "https://api.z.ai/api/paas/v4", "api_key": "sk-that-9999"})
    assert r.status_code == 303
    trang = client.get("/general/api-keys").text     # migration chạy lúc mở trang
    assert "glm-4.5-air" in trang
    assert "sk-that-99···9999" in trang   # dau(10)···duoi (Owner phê lần 4)
    assert "sk-that-9999" not in trang    # KHÔNG bao giờ hiện lại key trọn
    conn = ket.ket_noi()
    assert len(ket.liet_ke_api_keys(conn)) == 1      # mục cũ → 1 khóa LLM
    assert ket.doc_cap_phat(conn)["ai-agent"]["writer"]["khoa"] == ["api-001"]
    conn.close()
    client.get("/general/api-keys")                  # mở lại — idempotent
    conn = ket.ket_noi()
    assert len(ket.liet_ke_api_keys(conn)) == 1
    conn.close()
    # backend cũ: sửa model, bỏ trống key → key cũ GIỮ NGUYÊN (đường fallback)
    client.post("/general/ai-models/llm", data={"vai": "writer", "model": "glm-5",
                                      "provider": "", "base_url": "", "api_key": ""})
    conn = ket.ket_noi()
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-that-9999"
    assert ket.lay_cau_hinh(conn, "llm.writer.model") == "glm-5"
    conn.close()


def test_trang_api_keys_them_thu_hoi_cap_phat(client):
    """Vòng đời qua UI: thêm khóa (write-only) → cấp phát cho việc trong hợp
    đồng → thu hồi (gõ lại đuôi) gỡ khỏi cấp phát; MỌI bước có vết audit
    (trả nợ 'két không vết' — DE.md 3b)."""
    _login(client, "owner-test", "MatKhau123")
    r = client.post("/general/api-keys/add", data={
        "loai_chon": "llm:glm", "khoa": "sk-ui-kiemthu-2468", "model": "glm-4.5-air"})
    assert r.status_code == 303 and "bao=" in r.headers["location"]
    trang = client.get("/general/api-keys").text
    assert "sk-ui-kiem···2468" in trang and "sk-ui-kiemthu-2468" not in trang

    r = client.post("/general/api-keys/cap-phat", data={     # cấp cho việc hợp đồng
        "app_slug": "ai-agent", "viec": "writer", "them": "api-001"})
    assert r.status_code == 303
    conn = ket.ket_noi()
    assert ket.doc_cap_phat(conn)["ai-agent"]["writer"]["khoa"] == ["api-001"]
    conn.close()
    r = client.post("/general/api-keys/cap-phat", data={     # việc ngoài hợp đồng
        "app_slug": "ai-agent", "viec": "viec-bia", "them": "api-001"})
    assert "loi=" in r.headers["location"]

    r = client.post("/general/api-keys/revoke", data={"id": "api-001",
                                                      "go_lai": "sai"})
    assert "loi=" in r.headers["location"]                   # gõ sai đuôi → chặn
    r = client.post("/general/api-keys/revoke", data={"id": "api-001",
                                                      "go_lai": "2468"})
    assert "bao=" in r.headers["location"]
    conn = ket.ket_noi()
    assert ket.liet_ke_api_keys(conn) == []
    assert ket.doc_cap_phat(conn)["ai-agent"]["writer"]["khoa"] == []
    conn.close()
    conn = iam.ket_noi()
    hd = [d["hanh_dong"] for d in iam.doc_nhat_ky(conn, 20)]
    conn.close()
    assert "api_key_them" in hd and "api_cap_phat" in hd and "api_key_thu_hoi" in hd
    nk = iam.ket_noi()
    assert not any("sk-ui-kiemthu-2468" in d["chi_tiet"]
                   for d in iam.doc_nhat_ky(nk, 20))
    nk.close()                                               # audit không chứa key


def test_assigned_keys_show_more_server_side(client):
    """Owner phê lần 3 (18/08): Show more đổi sang SERVER-SIDE — server cắt danh
    sách trước khi gửi HTML (JS ẩn/hiện cũ không tác dụng trên trình duyệt thật,
    không tái hiện được). >5 khóa: mặc định đúng 5 dòng + LINK GET 'Show more (N)';
    ?mo_rong=<ma> render đủ + link 'Show less'; ≤5 khóa: không link nào."""
    _login(client, "owner-test", "MatKhau123")
    conn = ket.ket_noi()
    ids = [ket.them_api_key(conn, "youtube", f"AIzaKhoaThu{i:02d}xxxxx")
           for i in range(7)]                     # 7 khóa > 5 để chạm ngưỡng
    ket.luu_cap_phat_viec(conn, "radary", "harvest", ids, "xoay_vong")
    conn.close()

    # MẶC ĐỊNH (collapsed): server chỉ gửi 5 dòng — không phải gửi đủ rồi JS ẩn
    trang = client.get("/general/api-keys?tab=app&app=radary").text
    assert 'class="khoa-list"' in trang
    assert trang.count('class="khoa-dong"') == 5
    assert "AIzaKhoaTh···" in trang                    # dau(10)···duoi, không ••••duoi
    assert "••••" not in trang
    assert ">Show more (2)</a>" in trang
    # Jinja escape & thành &amp; trong thuộc tính — trình duyệt đọc lại thành &
    assert 'href="/general/api-keys?tab=app&amp;app=radary&amp;mo_rong=harvest"' in trang
    assert "Show less" not in trang
    assert ".khoa-list{display:flex;flex-direction:column;gap:4px}" in trang
    assert "querySelectorAll('.khoa-list')" not in trang   # JS show-more cũ đã gỡ hẳn

    # MỞ RỘNG qua query param: đủ 7 dòng + Show less (bỏ ma khỏi mo_rong)
    trang = client.get("/general/api-keys?tab=app&app=radary&mo_rong=harvest").text
    assert trang.count('class="khoa-dong"') == 7
    assert "Show more" not in trang
    assert ">Show less</a>" in trang
    assert 'href="/general/api-keys?tab=app&amp;app=radary"' in trang

    # Form hành động không phụ thuộc mo_rong: gỡ khóa ✕ lúc ĐANG collapsed vẫn ăn
    r = client.post("/general/api-keys/cap-phat", data={
        "app_slug": "radary", "viec": "harvest", "go": ids[0]})
    assert r.status_code == 303
    conn = ket.ket_noi()
    assert ket.doc_cap_phat(conn)["radary"]["harvest"]["khoa"] == ids[1:]
    # ≤5 khóa: không còn link nào cả (hành vi cũ giữ nguyên)
    ket.luu_cap_phat_viec(conn, "radary", "harvest", ids[:4], "xoay_vong")
    conn.close()
    trang = client.get("/general/api-keys?tab=app&app=radary").text
    assert trang.count('class="khoa-dong"') == 4
    assert "Show more" not in trang and "Show less" not in trang
    # dropdown "+ key" phải NÓI RÕ đây là kho khóa DỰ PHÒNG (Owner 18/08):
    # option nhãn đầu disabled + đúng số khóa chưa gán (7 tạo - 4 đang gán = 3)
    assert "— spare keys (3) —" in trang
    assert '<option value="" disabled selected>' in trang


def test_tab1_moi_khoi_5_dong_show_more_server_side(client):
    """LUẬT TRANG API (Owner 18/08 — docs/UI.md): MỌI danh sách mặc định 5 dòng
    + Show more/less server-side. Tab 1: 20 khóa YouTube → collapsed đúng 5 dòng
    + link 'Show more (15)' (mã mo_rong theo KHỐI LOẠI 'loai:youtube'); expanded
    đủ 20 + Show less; khối ≤5 không link. Badge khóa chưa dùng là 'spare'
    (Owner gọi là key dự phòng — 'idle' không truyền đạt ý)."""
    _login(client, "owner-test", "MatKhau123")
    conn = ket.ket_noi()
    for i in range(20):
        ket.them_api_key(conn, "youtube", f"AIzaTabMot{i:02d}xxxxxx")
    conn.close()

    trang = client.get("/general/api-keys").text
    assert trang.count("data-thu-hoi=") == 5           # server chỉ gửi 5 dòng khóa
    assert ">Show more (15)</a>" in trang
    # Owner 18/08: Show more/less phải TRÔNG NHƯ NÚT — class nut-mo (anchor chữ
    # trần không ai nhận ra bấm được), style khai trong trang
    assert 'class="nut-mo" href="/general/api-keys?tab=api&amp;mo_rong=loai:youtube"' in trang
    assert "a.nut-mo{" in trang
    assert trang.count("Show more") == 1               # khối llm/generate/transcript ≤5: không link
    assert "Show less" not in trang
    assert ">spare</span>" in trang and ">idle<" not in trang

    trang = client.get("/general/api-keys?tab=api&mo_rong=loai:youtube").text
    assert trang.count("data-thu-hoi=") == 20          # expanded đủ 20
    assert "Show more" not in trang
    assert ">Show less</a>" in trang
    assert 'href="/general/api-keys?tab=api"' in trang


def test_tab1_moi_khoi_cung_luoi_6_cot(client):
    """Owner chốt 24/08/2026: mọi khối khóa tab 1 dùng CHUNG lưới 6 cột cố định
    (khối không có Model vẫn giữ ô trống) → các bảng thẳng một trục; cột Usage +
    Added đã bỏ. Ghim bằng SỐ Ô mỗi hàng, không ghim mặt chữ CSS."""
    import re
    _login(client, "owner-test", "MatKhau123")
    conn = ket.ket_noi()
    ket.them_api_key(conn, "youtube", "AIzaLuoiOK000000000000")      # khối KHÔNG có Model
    ket.them_api_key(conn, "llm", "sk-luoi-glm-0000000", nha="glm")  # khối CÓ Model
    ket.them_api_key(conn, "transcript", "sk-luoi-tran-000000")
    conn.close()

    trang = client.get("/general/api-keys").text
    khoi = trang.split('<table class="gon luoi-khoa">')[1:]
    assert len(khoi) >= 4                                    # youtube/llm/generate/transcript/serp…
    for kh in khoi:
        than = kh.split("</table>")[0]
        assert "table-layout:fixed" in trang and than.count("<col ") == 6
        for hang in re.findall(r"<tr>(.*?)</tr>", than, re.S):
            if "colspan" in hang:                            # hàng gộp (No key yet / Show more)
                assert 'colspan="6"' in hang
                continue
            assert hang.count("<td") in (0, 6)               # 0 = hàng <th>; còn lại đúng 6 ô
    assert ">Usage</th>" not in trang and ">Added</th>" not in trang
    assert 'class="usage"' not in trang


def test_tab2_luoi_7_cot_va_nut_save_dinh_mep_phai(client):
    """Owner chốt 24/08: tab 2 cùng luật lưới — 7 cột cố định, mọi hàng đúng 7 ô.
    Nút Save phải dính MÉP PHẢI ô hành động ở mọi hàng: form.dong của base là
    inline-flex (co theo nội dung) nên justify-content vô hiệu — đo thật bằng
    Chrome cho save_x lệch 120px giữa hàng có/không dropdown; luật display:flex +
    width:100% là thứ chữa, ghim ở đây để đừng ai gỡ."""
    import re
    _login(client, "owner-test", "MatKhau123")
    trang = client.get("/general/api-keys?tab=app&app=radary").text
    than = trang.split('<table class="gon luoi-app">')[1].split("</table>")[0]
    assert than.count("<col ") == 7
    for hang in re.findall(r"<tr>(.*?)</tr>", than, re.S):
        assert hang.count("<td") in (0, 7)
    assert "table.luoi-app td form.dong{display:flex;width:100%" in trang
    assert "justify-content:flex-end" in trang


def test_tab3_quota_log_5_dong_show_more_server_side(client):
    """Cùng LUẬT cho bảng Quota log (mã 'log'): 7 dòng log → collapsed 5 +
    Show more (2); expanded đủ + Show less; URL giữ nguyên bộ lọc."""
    # Ghi vào SỔ GỌI — sổ mà trang thật sự đọc. Trước 03/09 test ghi vào
    # quota_log (khuôn P4) và vẫn xanh, trong khi trang thật TRẮNG suốt vì
    # data/logs/quota/ chưa app nào ghi: test xanh mà tính năng chết.
    from nen.common import so_goi
    _login(client, "owner-test", "MatKhau123")
    for i in range(7):
        so_goi.ghi("radary", "youtube", duoi="9999", viec=f"viec-log-{i}")

    trang = client.get("/general/api-keys?tab=log").text
    assert trang.count("viec-log-") == 5
    assert ">Show more (2)</a>" in trang
    assert 'href="/general/api-keys?tab=log&amp;mo_rong=log"' in trang

    trang = client.get("/general/api-keys?tab=log&mo_rong=log").text
    assert trang.count("viec-log-") == 7
    assert ">Show less</a>" in trang

    # bộ lọc sống sót trong link Show more (không mất ngày/app đang lọc)
    trang = client.get("/general/api-keys?tab=log&loc_app=radary").text
    assert "tab=log&amp;loc_app=radary&amp;mo_rong=log" in trang


def test_redirect_giu_vi_tri_va_modal_revoke(client):
    """Owner phê lần 4 ('ấn vào quay về đầu trang'): (a) mọi POST đọc ve_tab/
    ve_app/ve_mo_rong từ form → redirect về ĐÚNG chỗ đang đứng, nhánh lỗi cũng
    vậy; form cũ không mang field → hành vi cũ. (b) Revoke đổi sang MODAL xác
    nhận dùng chung — ô inline 'tail' bé xíu bị bỏ hẳn."""
    _login(client, "owner-test", "MatKhau123")
    conn = ket.ket_noi()
    kid = ket.them_api_key(conn, "llm", "sk-llm-redirect-9012", nha="glm")
    conn.close()

    # (a) redirect giữ vị trí — cap-phat từ tab app đang mở rộng writer
    r = client.post("/general/api-keys/cap-phat", data={
        "app_slug": "ai-agent", "viec": "writer", "them": kid,
        "ve_tab": "app", "ve_app": "ai-agent", "ve_mo_rong": "writer"})
    loc = r.headers["location"]
    assert "tab=app" in loc and "app=ai-agent" in loc and "mo_rong=writer" in loc
    r = client.post("/general/api-keys/model", data={
        "id": kid, "model": "glm-5", "ve_tab": "api"})
    assert r.headers["location"].startswith("/general/api-keys?tab=api")
    # nhánh LỖI giữ nguyên vị trí (gõ sai đuôi trong modal)
    r = client.post("/general/api-keys/revoke", data={
        "id": kid, "go_lai": "sai!", "ve_tab": "api"})
    loc = r.headers["location"]
    assert "tab=api" in loc and "loi=" in loc
    # form CŨ không mang ve_* (trang mở trước khi vá) — cap-phat lùi về tab app
    r = client.post("/general/api-keys/cap-phat", data={
        "app_slug": "ai-agent", "viec": "writer", "go": kid})
    assert "tab=app" in r.headers["location"] and "app=ai-agent" in r.headers["location"]

    # (b) modal revoke: nút mỗi dòng type=button mở modal, KHÔNG còn ô inline
    trang = client.get("/general/api-keys").text
    assert f'data-thu-hoi="{kid}"' in trang
    assert 'id="md-revoke"' in trang and 'id="rv-go-lai"' in trang
    assert trang.count('name="go_lai"') == 1          # DUY NHẤT trong modal
    # chip giãn hết cột — hết khoảng chết giữa chip khóa và nút ✕ (lỗi 2a)
    assert ".khoa-dong .chip-o{flex:1;text-align:left}" in trang


def test_model_chi_hien_cho_llm_generate(client):
    """Owner phê lần 4 ('tự bịa đúng không?'): ô model CHỈ có ở loại llm/generate
    — task transcript KHÔNG có ô model (loại này không có khái niệm model).
    Từ 22/08 ô model là DROPDOWN (Owner: 'cho phép chọn model khi cấu hình per
    app') — hết gõ tay nên cũng hết cần autocomplete=off; danh sách gợi ý theo
    nhà của khóa đầu + lựa chọn '— theo khóa —' để bỏ override."""
    _login(client, "owner-test", "MatKhau123")
    conn = ket.ket_noi()
    ket.them_api_key(conn, "transcript", "tr-abcdefgh-9999")
    kid = ket.them_api_key(conn, "llm", "sk-llm-abcdef-8888", nha="glm")
    # gán khóa cho việc: gợi ý model đi theo NHÀ của khóa đầu, chưa gán thì
    # dropdown chỉ có "— theo khóa —" (chưa biết nhà nào thì không bịa gợi ý)
    ket.luu_cap_phat_viec(conn, "content-ultimate", "viet_kich_ban", [kid])
    conn.close()

    # tab 2: content-ultimate có cả task llm + transcript + youtube trong hợp
    # đồng → số ô model đúng bằng SỐ VIỆC LLM (transcript/youtube không có ô).
    # 08/09: ghim theo HÀNH VI thay số cứng 2 — hợp đồng nở 4→9 việc (08/09,
    # Luật 1 "chỗ nào dùng API phải khai") làm con số cũ tự vỡ dù trang vẫn đúng.
    from nen.common.hop_dong import tim_app as _tim_app
    so_llm = sum(1 for v in _tim_app("content-ultimate")["viec_api"]
                 if v["loai"] == "llm")
    trang = client.get("/general/api-keys?tab=app&app=content-ultimate").text
    assert trang.count('name="model"') == so_llm
    assert '<input name="model"' not in trang            # chọn, không gõ tay
    assert f'value="{ket.MODEL_THEO_KHOA}"' in trang     # bỏ override được
    for m in ket.MODEL_GOI_Y["glm"]:                     # gợi ý theo nhà của khóa
        assert f'<option value="{m}"' in trang

    # tab 1: bảng YouTube Transcript (đứng CUỐI danh sách loại) không còn form
    # đổi model — form model chỉ nằm trong các khối llm/generate phía trên
    trang = client.get("/general/api-keys").text
    assert 'action="/general/api-keys/model"' in trang
    khoi_transcript = trang.split("YouTube Transcript", 1)[1]
    assert 'action="/general/api-keys/model"' not in khoi_transcript


def test_api_keys_va_permissions_khong_cache(client):
    """Owner nghi cache trình duyệt khi thấy UI cũ ở 2 trang sửa liên tục —
    no-store cho mọi đường render (GET lẫn POST-lỗi trực tiếp của Permissions)."""
    _login(client, "owner-test", "MatKhau123")
    assert client.get("/general/api-keys").headers["cache-control"] == "no-store"
    assert client.get("/general/permissions").headers["cache-control"] == "no-store"
    r = client.post("/general/permissions/grant", data={           # nhánh lỗi render trực tiếp
        "ten": "owner-test", "app_slug": "*", "hanh_dong": "vault", "gia_tri": "cho"})
    assert r.headers["cache-control"] == "no-store"


def test_tab1_generate_nhom_theo_nha_va_modal_2_option(client):
    """Owner chốt 17/08: VEO + Seedream lên MỘT khối 'Generate Video/Image API'
    nhóm theo nhà (giống LLM) — không còn 2 khối cố định riêng; modal Add API
    key có 2 option generate:veo/generate:seedream; nhãn Transcript đổi tên."""
    _login(client, "owner-test", "MatKhau123")
    conn = ket.ket_noi()
    ket.them_api_key(conn, "generate", "flow-that-1234", nha="veo", model="veo-3.1")
    ket.them_api_key(conn, "generate", "seed-that-5678", nha="seedream")
    conn.close()

    trang = client.get("/general/api-keys").text
    assert "Generate Video/Image API" in trang          # đúng 4 khối: youtube/llm/generate/transcript
    assert "VEO (Google Flow)" in trang and "Seedream" in trang   # nhóm theo nhà, khuôn LLM
    assert "flow-that-···1234" in trang and "seed-that-···5678" in trang
    assert "YouTube Transcript" in trang
    assert "VEO (Google Flow) (Google Flow)" not in trang          # không lặp nhãn cũ

    assert 'value="generate:veo">Generate — VEO<' in trang
    assert 'value="generate:seedream">Generate — Seedream<' in trang
    assert 'value="transcript">YouTube Transcript<' in trang
    assert 'value="veo">VEO<' not in trang and 'value="seedream">Seedream<' not in trang

    r = client.post("/general/api-keys/add", data={
        "loai_chon": "generate:veo", "khoa": "flow-them-qua-ui"})
    assert r.status_code == 303 and "bao=" in r.headers["location"]
    conn = ket.ket_noi()
    ds = ket.liet_ke_api_keys(conn)
    conn.close()
    muc = next(k for k in ds if k["dau"] == "flow-them-" and k["duoi"] == "a-ui")
    assert muc["loai"] == "generate" and muc["nha"] == "veo"     # partition(":") sinh generic ăn luôn


def test_api_loopback_tra_du_va_chan_khong_loopback(he):
    conn = ket.ket_noi()
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-noi-bo-1234")
    conn.close()

    async def goi(client_addr):
        transport = httpx.ASGITransport(app=gateway_app, client=client_addr)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://t") as c:
            return await c.get("/api/cau-hinh/llm/writer")

    r = asyncio.run(goi(("127.0.0.1", 50000)))     # app phụ loopback
    assert r.status_code == 200
    assert r.json()["api_key"] == "sk-noi-bo-1234"
    assert r.json()["timeout"] == 60 and r.json()["retry"] == 0

    r2 = asyncio.run(goi(("192.168.1.50", 50000)))  # máy LAN gọi thẳng → chặn
    assert r2.status_code == 403


def test_api_loopback_theo_app_khong_muon_nham(he):
    """Bug 18/08 (Owner phê lần 3): loopback nhận query ?app= — data-analytics
    xin việc dien_giai ra ĐÚNG khóa của mình, không mượn khóa Writer ai-agent;
    thiếu ?app= → mặc định ai-agent (tương thích ngược, không phá caller cũ)."""
    conn = ket.ket_noi()
    k_ai = ket.them_api_key(conn, "llm", "sk-ai-agent-1111", nha="glm")
    k_da = ket.them_api_key(conn, "llm", "sk-data-analytics-2222", nha="claude")
    ket.luu_cap_phat_viec(conn, "ai-agent", "writer", [k_ai])
    ket.luu_cap_phat_viec(conn, "data-analytics", "dien_giai", [k_da])
    conn.close()

    async def goi(url):
        transport = httpx.ASGITransport(app=gateway_app,
                                        client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://t") as c:
            return await c.get(url)

    r = asyncio.run(goi("/api/cau-hinh/llm/dien_giai?app=data-analytics"))
    assert r.json()["api_key"] == "sk-data-analytics-2222"
    r = asyncio.run(goi("/api/cau-hinh/llm/writer?app=ai-agent"))
    assert r.json()["api_key"] == "sk-ai-agent-1111"
    r = asyncio.run(goi("/api/cau-hinh/llm/writer"))     # thiếu app → mặc định ai-agent
    assert r.json()["api_key"] == "sk-ai-agent-1111"
    # DA xin vai trùng tên 'writer' CHƯA cấp cho DA → KHÔNG với sang ai-agent
    r = asyncio.run(goi("/api/cau-hinh/llm/writer?app=data-analytics"))
    assert r.json()["api_key"] == ""
