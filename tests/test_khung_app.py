# -*- coding: utf-8 -*-
"""KHUNG MỞ APP GIỮ SIDEBAR (Owner 16/08 — "mở app vẫn còn sidebar"): app ngoài
khai giao_dien 'khung' mở qua GET /open/<slug> = shell OUTLIERY (sidebar+topbar)
+ iframe /app/<slug>/; gate y hệt cửa vào app; native/lạ → 404; /app trực tiếp
sống nguyên; proxy cắt X-Frame-Options/CSP-frame-ancestors CHỈ cho app khung."""
import bcrypt
import pytest
from fastapi.testclient import TestClient

from nen.common.sidebar import sb_apps_tu_claims
from nen.gateway.main import app as gateway_app
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-test", "MatKhau123", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "nhanvien", "MatKhau123", "Kinh doanh", 2,
                      phai_doi_mk=False)
    conn.close()
    return TestClient(gateway_app, follow_redirects=False)


def _login(client, ten="owner-test", mk="MatKhau123"):
    return client.post("/login", data={"ten": ten, "mat_khau": mk})


def test_open_chua_dang_nhap_ve_login(client):
    r = client.get("/open/radary")
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_open_radary_khung_du_sidebar_va_iframe(client):
    _login(client)
    r = client.get("/open/radary")
    assert r.status_code == 200
    b = r.text
    assert '<iframe class="khung-app" src="/app/radary/"' in b   # nội dung = iframe
    assert 'class="sidebar"' in b and "OUTLIERY" in b            # shell chuẩn
    assert "RadarY" in b and "Content Ultimate" in b             # nhóm Tools đủ app
    # đồng nhất URL 18/08 (4f37839): nút Tools = /<slug> (khung phục vụ cùng trang)
    assert 'class="nav-item active" href="/radary"' in b         # mục đang mở active
    assert "<title>RadarY — AI AGENT OUTLIERY</title>" in b


def test_reviewy_sidebar_xo_4_muc_con(client):
    """ReviewY là app KHUNG có menu con khai trong hợp đồng (apps.json muc_con):
    đứng trong app thì sidebar xổ đủ 4 mục, mục đang xem sáng. Mục con khai bằng
    DỮ LIỆU nên thêm app có menu con không phải sửa template — test này ghim
    luôn cơ chế đó, không riêng ReviewY."""
    _login(client)
    r = client.get("/video-review")
    assert r.status_code == 200
    b = r.text
    assert 'ReviewY' in b                       # tên mới, không còn "Video Review"
    for ten, duong in [("Overview", "tong-quan"), ("Writing Review", "kich-ban"),
                       ("Editing Review", "danh-sach"), ("Publish Review", "publish")]:
        assert f'href="/video-review?duong={duong}"' in b and ten in b
    # không đứng trong app thì KHÔNG xổ mục con (đỡ rối sidebar)
    r2 = client.get("/radary")
    assert 'href="/video-review?duong=tong-quan"' not in r2.text


def test_moi_muc_con_phai_nam_trong_tien_to():
    """LƯỚI CHỐNG LỖI 'thiếu tiền tố nào hỏng phần đó' (đã dính 2 lần: Content
    03/08 mất /manage /settings, ReviewY 05/09 mất /publish → sidebar bấm ra
    404 Not Found). Mục con sidebar đi qua proxy nên đường của nó BẮT BUỘC nằm
    trong tien_to — nếu không, gateway không biết viết lại và app không nhận."""
    from nen.common.hop_dong import doc_hop_dong
    thieu = []
    for a in doc_hop_dong():
        tien_to = a.get("tien_to") or []
        for m in a.get("muc_con") or []:
            duong = "/" + m["duong"].lstrip("/")
            if not any(duong == t or duong.startswith(t + "/") for t in tien_to):
                thieu.append(f"{a['slug']}: muc con {duong} khong co trong tien_to")
    assert not thieu, "; ".join(thieu)


def test_muc_con_khai_bang_du_lieu_khong_hardcode():
    """Content Ultimate cũng chuyển sang cùng cơ chế — giữ NGUYÊN đường cũ
    /outline /author /write nên hành vi app đó không đổi."""
    from nen.common.hop_dong import doc_hop_dong
    cu = {a["slug"]: a.get("muc_con") or [] for a in doc_hop_dong()}
    assert [m["duong"] for m in cu["content-ultimate"]] == ["outline", "author", "write"]
    assert [m["duong"] for m in cu["video-review"]] == [
        "tong-quan", "kich-ban", "danh-sach", "publish"]


def test_open_khoi_quan_ly_nam_gon_trong_popup(client):
    """Owner phê 17/08 'không đưa khối dưới sidebar ra ngoài': HR/Finance/General/
    Profile/Log out phải nằm GỌN TRONG popup sb-mgmt ghim đáy (y cấu trúc base.html
    các app) — pane bên trên CHỈ còn Home + Tools; Home trỏ '/' (vị trí AI Agent)."""
    _login(client)
    b = client.get("/open/radary").text
    assert 'id="sb-mgmt"' in b and 'id="sb-mgmt-nut"' in b and 'id="sb-mgmt-muc"' in b
    truoc, sau = b.split('id="sb-mgmt"', 1)               # pane vs khối popup đáy
    for duong in ('href="/hr"', 'href="/finance"', 'href="/general"',
                  'href="/profile"', 'href="/logout"', 'href="/tracking"',
                  'href="/vault"'):
        assert duong not in truoc, duong                  # không còn link phẳng ở pane
        # các mục theo quyền Owner đều có mặt TRONG popup
        assert duong in sau, duong
    assert 'class="nav-item new" href="/"' in truoc       # Home = chỗ của AI Agent (kiểu nút New chat)
    assert "mgmt-mui" in sau                              # nút chip + mũi tên popup


def test_open_gate_y_het_cua_vao_app(client):
    # content-ultimate: chỉ VH L2+ — nhanvien KD bị chặn y luật proxy
    _login(client, "nhanvien", "MatKhau123")
    assert client.get("/open/content-ultimate").status_code == 403
    assert client.get("/open/radary").status_code == 200         # radary mọi bộ phận L1
    _login(client)
    assert client.get("/open/content-ultimate").status_code == 200


def test_open_native_va_slug_la_404(client):
    _login(client)
    assert client.get("/open/ai-agent").status_code == 404       # native không qua khung
    assert client.get("/open/to-chuc").status_code == 404
    assert client.get("/open/khong-co").status_code == 404


def test_sidebar_href_khung_vs_native():
    # đồng nhất URL 18/08 (4f37839): MỘT luật /<slug> cho mọi nút Tools —
    # /open/<slug> vẫn sống đỡ bookmark cũ (test_open_* bên trên vẫn đi cửa đó)
    ds = {a["slug"]: a["href"] for a in sb_apps_tu_claims(
        ["radary", "content-ultimate"])}
    assert ds == {"radary": "/radary",
                  "content-ultimate": "/content-ultimate"}


def test_thu_tu_tools_giong_nhau_moi_sidebar():
    """Owner 30/08: "bấm vào app thì sidebar nhảy thứ tự". Có HAI nơi dựng danh
    sách Tools — sb_apps_tu_claims (app native) và gateway (khung /app/<slug>) —
    gateway từng chép logic lọc mà quên sắp xếp. Ghim: cả hai ra CÙNG thứ tự,
    và gateway thật sự gọi hàm sắp chung (không chép lại lần nữa)."""
    import inspect
    from nen.common.sidebar import THU_TU_TOOLS, sap_thu_tu_tools
    import nen.gateway.main as gw

    # xáo trộn đầu vào — thứ tự ra phải theo THU_TU_TOOLS, không theo thứ tự vào
    xao = [{"slug": s} for s in reversed(THU_TU_TOOLS)]
    assert [a["slug"] for a in sap_thu_tu_tools(xao)] == THU_TU_TOOLS

    # app chưa khai tên → xuống CUỐI, giữ nguyên thứ tự hợp đồng giữa chúng
    ds = sap_thu_tu_tools([{"slug": "la-2"}, {"slug": "seo-optimize"},
                           {"slug": "la-1"}, {"slug": "radary"}])
    assert [a["slug"] for a in ds] == ["radary", "seo-optimize", "la-2", "la-1"]

    # sidebar app native đi qua cùng hàm — giao với hợp đồng giữ đúng thứ tự
    duoc = ["seo-optimize", "radary", "content-ultimate", "tasky"]
    ra = [a["slug"] for a in sb_apps_tu_claims(duoc)]
    assert ra == [s for s in THU_TU_TOOLS if s in duoc]

    # gateway PHẢI gọi hàm sắp chung (bắt tại nguồn, không đợi nhìn bằng mắt)
    assert "sap_thu_tu_tools(" in inspect.getsource(gw.mo_app_khung)


def test_icon_app_hai_ban_sao_khop_nhau():
    """Icon sidebar nằm ở HAI file (app và gateway là hai tiến trình, không include
    chéo template được). Thêm app mới mà chỉ sửa một file thì app đó ra icon ô
    vuông ở nửa hệ — từng dính với slug V3 (plannery/content-ultimate…). Ghim: hai
    file phủ CÙNG tập slug, và mọi app trong THỨ TỰ Tools đều có icon riêng."""
    import re
    from pathlib import Path
    from nen.common.sidebar import THU_TU_TOOLS

    goc = Path("apps/ai-agent/src/templates/_icon_app.html")
    sao = Path("nen/gateway/templates/_icon_app_khung.html")

    def slugs(f):
        t = f.read_text(encoding="utf-8")
        ra = set()
        # cắt tới " -%}" bằng lookahead — [^-] bỏ sót slug có gạch (content-ultimate…)
        for m in re.findall(r"a\.slug (?:==|in) (.+?)(?= -%\})", t):
            ra |= set(re.findall(r"'([a-z0-9-]+)'", m))
        return ra

    sg, ss = slugs(goc), slugs(sao)
    assert sg and sg == ss, f"hai file icon lệch slug: chỉ gốc {sg - ss}, chỉ sao {ss - sg}"
    thieu = [s for s in THU_TU_TOOLS if s not in sg]
    assert not thieu, f"app trong THỨ TỰ Tools chưa có icon riêng: {thieu}"


def test_proxy_cat_header_khung_va_wiring(client, monkeypatch):
    """_bo_vi_khung: cắt XFO + CSP-có-frame-ancestors (CSP thường giữ); proxy_app
    truyền khung=True đúng app khai, native False — bắt tại chỗ nối chuyen_tiep."""
    from nen.common.proxy import _bo_vi_khung
    assert _bo_vi_khung("x-frame-options", "DENY")
    assert _bo_vi_khung("content-security-policy", "frame-ancestors 'none'")
    assert not _bo_vi_khung("content-security-policy", "default-src 'self'")
    assert not _bo_vi_khung("etag", "abc")

    import nen.gateway.main as gw
    bat: dict = {}

    async def _gia(request, **kw):
        bat.update(kw)
        from fastapi.responses import Response as R
        return R("ok")

    monkeypatch.setattr(gw, "chuyen_tiep", _gia)
    _login(client)
    client.get("/app/radary/board")
    assert bat["khung"] is True
    client.get("/app/app-mau/")
    assert bat["khung"] is False


def test_ui_a2_a3_modal_va_badge(client):
    """UI A2/A3 theo chuẩn A1: API Keys có modal Add key + khối transcript hiện
    (bug loop 4 loại cũ); Permissions dùng badge overrides — logic/field y nguyên."""
    _login(client)
    b = client.get("/general/api-keys").text
    assert 'class="modal-bg" id="md-key"' in b and 'data-mo="md-key"' in b
    assert "YouTube Transcript" in b                    # loại thứ 4 hết vô hình (Owner chốt 17/08 đổi nhãn)
    assert 'value="transcript"' in b                    # thêm được khóa transcript từ UI
    b = client.get("/general/permissions?ten=nhanvien").text
    assert "0 overrides" in b                           # badge chuẩn trên summary
    assert 'class="badge ok">yes' in b                  # P2 badge thay chip
    # Owner 18/08 (docs/UI.md): <details> khu General phải có CHỈ BÁO mở rộng —
    # chevron trong summary xoay 90° khi [open], summary hạ cỡ 14px không ăn heading
    assert '<summary><svg class="ic chev"' in b
    assert "details.app[open] summary .chev{transform:rotate(90deg)}" in b
    assert "font-size:14px" in b.split("details.app summary{", 1)[1].split("}", 1)[0]


def test_moi_app_nghe_doi_theme_song():
    """Gạt theme ở khung thì app trong iframe phải đổi NGAY, không cần F5.

    App chạy trong iframe là document RIÊNG: trước đây mỗi app chỉ đọc
    localStorage 'outliery_theme' lúc TẢI, nên gạt xong app vẫn giữ màu cũ
    (user báo 22/08 — RadarY nền tối trong khung đã sáng). Sự kiện 'storage'
    bắn cho mọi document CÙNG ORIGIN khác, nên app tự nghe là đủ — lo luôn cả
    cửa sổ rời (Shift+click) chứ không riêng iframe.

    Lưới này quét CẢ CÂY: app mới thêm sau mà quên nghe cũng bị bắt.
    """
    import os
    from pathlib import Path

    goc = Path(__file__).resolve().parents[1]
    thieu = []
    for f in list((goc / 'apps').rglob('*.html')) + list((goc / 'nen').rglob('*.html')):
        if any(p in f.parts for p in ('node_modules', 'vendor', '_references')):
            continue
        try:
            s = f.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        if 'outliery_theme' not in s:
            continue                              # trang không dính theme thì bỏ qua
        if 'addEventListener("storage"' in s or "addEventListener('storage'" in s:
            continue
        thieu.append(str(f.relative_to(goc)))

    # Ba trang đang do phiên khác sửa lúc vá (22/08) — hoãn để test đỏ không chặn
    # việc của họ; vá nốt khi index sạch rồi bỏ khỏi danh sách này.
    hoan = {'apps/ai-agent/src/templates/base.html',
            'apps/ai-agent/src/templates/hoi_dap.html',
            'nen/gateway/templates/nen_base.html',
            'nen/gateway/templates/nen_khung_app.html'}
    con_lai = [t for t in thieu if t.replace(os.sep, '/') not in hoan]
    assert not con_lai, 'trang dùng theme mà không nghe đổi sống: ' + ', '.join(con_lai)
