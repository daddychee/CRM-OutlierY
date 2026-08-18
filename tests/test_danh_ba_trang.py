# -*- coding: utf-8 -*-
"""Test trang Niches + Channels (Đ1 khối đế): gate Manager+/Owner, luồng
niche-trước-kênh, khai tử gõ lại mã, audit có vết, export CSV."""
import bcrypt
import pytest
from fastapi.testclient import TestClient

from nen.gateway.main import app as gateway_app
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def he(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setenv("DANH_BA_DB", str(tmp_path / "danh_ba.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-t", "mk-test", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "quanly", "mk-ql-6", "Kinh doanh", 4,
                      phai_doi_mk=False)
    iam.tao_tai_khoan(conn, ow, "nhanvien", "mk-nv-6", "Kinh doanh", 2,
                      phai_doi_mk=False)
    conn.close()


def _login(ten, mk):
    # follow_redirects=True: từ 18/08 mọi POST danh bạ là POST-REDIRECT-GET
    # (Owner 'đổi trạng thái kênh bị chuyển URL') — client luồng đi theo redirect
    # để assert trang đích như cũ; ý nghĩa test (luồng + quyền) GIỮ NGUYÊN.
    c = TestClient(gateway_app, follow_redirects=True)
    c.post("/login", data={"ten": ten, "mat_khau": mk})
    return c


def test_gate_l2_khong_vao_l4_vao(he):
    assert _login("nhanvien", "mk-nv-6").get("/general/niches").status_code == 403
    assert _login("quanly", "mk-ql-6").get("/general/niches").status_code == 200
    assert _login("quanly", "mk-ql-6").get("/general/channels").status_code == 200


def test_niche_truoc_kenh_va_luong_tao(he):
    c = _login("quanly", "mk-ql-6")
    r = c.post("/general/niches/create", data={"ten_chuan": "Life In",
                                               "trang_thai": "khai_thac"})
    assert "N-LIFE-IN" in r.text
    r = c.post("/general/markets/create", data={"ten": "US", "ngon_ngu": "English"})
    assert "TT-US" in r.text
    r = c.post("/general/channels/create", data={
        "ten_chuan": "Outland", "ngach_ma": "N-LIFE-IN", "thi_truong_ma": "TT-US",
        "channel_id": "UCabc", "loai_kenh": "compilation", "trang_thai": "sandbox"})
    assert "K-OUTLAND" in r.text
    # tạo kênh vào ngách KHÔNG tồn tại → lỗi hiện trên trang, không 500
    r = c.post("/general/channels/create",
               data={"ten_chuan": "Mồ côi", "ngach_ma": "N-KHONG-CO"})
    assert r.status_code == 200 and "K-MO-COI" not in r.text


def test_doi_vong_doi_va_audit_co_vet(he):
    c = _login("quanly", "mk-ql-6")
    c.post("/general/niches/create", data={"ten_chuan": "Space"})
    c.post("/general/channels/create",
           data={"ten_chuan": "Astro", "ngach_ma": "N-SPACE"})
    r = c.post("/general/channels/trang-thai",
               data={"ma": "K-ASTRO", "trang_thai": "hoat_dong"})
    assert "hoat_dong" in r.text
    conn = iam.ket_noi()
    nk = "".join(str(dict(d)) for d in iam.doc_nhat_ky(conn, 50))
    conn.close()
    assert "K-ASTRO" in nk and "danh_ba" in nk        # mọi thao tác có vết


def test_khai_tu_chi_owner_va_phai_go_lai_ma(he):
    ql = _login("quanly", "mk-ql-6")
    ql.post("/general/niches/create", data={"ten_chuan": "OLD"})
    ql.post("/general/channels/create",
            data={"ten_chuan": "Time Vault", "ngach_ma": "N-OLD"})
    assert ql.post("/general/channels/khai-tu",
                   data={"ma": "K-TIME-VAULT", "go_lai": "K-TIME-VAULT"}
                   ).status_code == 403               # Manager không được khai tử
    ow = _login("owner-t", "mk-test")
    r = ow.post("/general/channels/khai-tu",
                data={"ma": "K-TIME-VAULT", "go_lai": "go-sai"})
    assert "Retype" in r.text                          # gõ sai mã → chặn
    r = ow.post("/general/channels/khai-tu",
                data={"ma": "K-TIME-VAULT", "go_lai": "K-TIME-VAULT"})
    assert "Retired" in r.text
    assert "khai_tu" in ow.get("/general/channels?ma=K-TIME-VAULT").text


def test_post_redirect_get_giu_vi_tri(he):
    """Owner 18/08 'đổi trạng thái kênh bị chuyển URL': mọi POST danh bạ 303 về
    GET sạch GIỮ VỊ TRÍ (?ma= chi tiết đang mở + bộ lọc) + bao/loi — hết kẹt URL
    đường POST, F5 hết re-submit; nhánh LỖI cũng redirect."""
    c = TestClient(gateway_app, follow_redirects=False)
    c.post("/login", data={"ten": "quanly", "mat_khau": "mk-ql-6"})
    c.post("/general/niches/create", data={"ten_chuan": "Space"})
    r = c.post("/general/channels/create",
               data={"ten_chuan": "Astro", "ngach_ma": "N-SPACE"})
    assert r.status_code == 303
    assert "ma=K-ASTRO" in r.headers["location"]       # mở luôn kênh vừa tạo

    r = c.post("/general/channels/trang-thai",
               data={"ma": "K-ASTRO", "trang_thai": "hoat_dong",
                     "ve_ma": "K-ASTRO", "ve_ngach": "N-SPACE"})
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.startswith("/general/channels?")
    assert "ma=K-ASTRO" in loc and "ngach=N-SPACE" in loc and "bao=" in loc
    trang = c.get(loc).text
    assert ">Active</span>" in trang                   # đổi THẬT + chi tiết vẫn mở

    # nhánh lỗi cũng redirect kèm loi + giữ vị trí (không kẹt URL POST)
    r = c.post("/general/channels/trang-thai",
               data={"ma": "K-ASTRO", "trang_thai": "trang-thai-la",
                     "ve_ma": "K-ASTRO"})
    assert r.status_code == 303
    assert "loi=" in r.headers["location"] and "ma=K-ASTRO" in r.headers["location"]
    # niches cùng khuôn: trạng thái lạ → 303 kèm loi (không render trực tiếp)
    r = c.post("/general/niches/create",
               data={"ten_chuan": "Space 2", "trang_thai": "trang-thai-la"})
    assert r.status_code == 303 and "loi=" in r.headers["location"]


def test_lien_ket_app_chi_owner(he):
    ql = _login("quanly", "mk-ql-6")
    ql.post("/general/niches/create", data={"ten_chuan": "Life In"})
    ql.post("/general/channels/create",
            data={"ten_chuan": "Outland", "ngach_ma": "N-LIFE-IN"})
    assert ql.post("/general/channels/link",
                   data={"ma": "K-OUTLAND", "app_slug": "seo-optimize",
                         "khoa": "outland-o-01"}).status_code == 403
    ow = _login("owner-t", "mk-test")
    r = ow.post("/general/channels/link",
                data={"ma": "K-OUTLAND", "app_slug": "seo-optimize",
                      "khoa": "outland-o-01"})
    assert "outland-o-01" in ow.get("/general/channels?ma=K-OUTLAND").text


def test_export_csv(he):
    c = _login("quanly", "mk-ql-6")
    c.post("/general/niches/create", data={"ten_chuan": "Life In"})
    r = c.get("/general/channels/export")
    assert r.status_code == 200 and "N-LIFE-IN" in r.text
    assert "text/csv" in r.headers["content-type"]


# ---------- UI A1: bám mockup đã duyệt (modal · lọc · chip kênh) ----------

def test_modal_thay_form_details(he):
    """Mockup N1/C1: "+ New" mở MODAL (không còn <details> khai form)."""
    c = _login("quanly", "mk-ql-6")
    for duong, md in (("/general/niches", "md-niche"), ("/general/channels", "md-kenh")):
        b = c.get(duong).text
        assert f'class="modal-bg" id="{md}"' in b          # modal có mặt
        assert f'data-mo="{md}"' in b                      # nút + New mở nó
        assert "<summary" not in b                         # form <details> đã đi
        assert "modal-bg" in b and 'class="dong-x"' in b   # nút ✕
    b = c.get("/general/niches").text
    assert 'class="modal-bg" id="md-market"' in b          # market cũng dùng modal


def test_bo_loc_va_chip_kenh_trong_niche(he):
    """Lọc niche/lifecycle SERVER-side lọc đúng; chip kênh của niche đủ số;
    bảng Markets đếm đúng số kênh."""
    c = _login("quanly", "mk-ql-6")
    c.post("/general/niches/create", data={"ten_chuan": "Life In"})
    c.post("/general/niches/create", data={"ten_chuan": "Space"})
    c.post("/general/markets/create", data={"ten": "US", "ngon_ngu": "English"})
    for ten in ("Outland", "Life Decoded"):
        c.post("/general/channels/create", data={
            "ten_chuan": ten, "ngach_ma": "N-LIFE-IN", "thi_truong_ma": "TT-US",
            "trang_thai": "sandbox"})
    c.post("/general/channels/create", data={
        "ten_chuan": "Space Archive", "ngach_ma": "N-SPACE", "trang_thai": "uom_mam"})

    b = c.get("/general/niches").text
    assert b.count('href="/general/channels?ngach=N-LIFE-IN"') == 2   # 2 chip kênh
    assert b.count('href="/general/channels?ngach=N-SPACE"') == 1
    # Markets đếm ĐÚNG số kênh gắn thị trường đó (Space Archive không gắn TT-US)
    dong_us = [d for d in b.split("<tr>") if "TT-US" in d][0]
    assert "<td>2</td>" in dong_us

    def _bang(html):      # chỉ xét BẢNG (dropdown "Clone of" trong modal liệt kê mọi kênh)
        return html.split('id="bang-kenh"', 1)[1].split("</table>", 1)[0]
    b = _bang(c.get("/general/channels?ngach=N-LIFE-IN").text)         # lọc theo niche
    assert "K-OUTLAND" in b and "K-SPACE-ARCHIVE" not in b
    b = _bang(c.get("/general/channels?trang_thai=uom_mam").text)      # lọc vòng đời
    assert "K-SPACE-ARCHIVE" in b and "K-OUTLAND" not in b
    # dữ liệu cho lọc CLIENT-side (market + search) có sẵn trên từng dòng
    b = c.get("/general/channels").text
    assert 'data-market="TT-US"' in b and 'id="q-kenh"' in b
    assert 'id="loc-tt-market"' in b


def test_nhan_en_va_khong_ghi_chu_man_hinh(he):
    """Chuẩn UI hệ: nhãn EN, nhãn vòng đời/trạng thái dịch sang EN, không câu
    giải thích tiếng Việt trên màn hình (luật Owner mục 12.2)."""
    c = _login("quanly", "mk-ql-6")
    c.post("/general/niches/create", data={"ten_chuan": "Life In", "trang_thai": "khai_thac"})
    c.post("/general/channels/create", data={"ten_chuan": "Outland",
                                             "ngach_ma": "N-LIFE-IN", "trang_thai": "sandbox"})
    b = c.get("/general/niches").text
    # nhãn EN hiện ra; mã máy chỉ còn trong value/data-* (không phải chữ người đọc)
    assert ">Exploiting</span>" in b and ">khai_thac<" not in b
    b = c.get("/general/channels?ma=K-OUTLAND").text
    assert "Sandbox" in b and "Export CSV" in b
    assert "chưa gán" not in b and "gõ lại" not in b        # hết chuỗi VN cũ trên màn
    # khối khai tử vẫn CHỈ Owner (quyền không đổi) — nhãn EN + gõ-lại-mã giữ nguyên
    assert "Retire channel" not in b
    ow = _login("owner-t", "mk-test").get("/general/channels?ma=K-OUTLAND").text
    assert "Retire channel" in ow and 'placeholder="retype K-OUTLAND"' in ow


def test_niche_thi_truong_user_chon_khong_mac_dinh(he):
    """Owner chốt 18/08: thị trường THUỘC TỪNG NGÁCH do user tick — ngách tạo
    không tick gì = 'none chosen', tick rồi sửa là thay cả tập."""
    c = _login("quanly", "mk-ql-6")
    c.post("/general/markets/create", data={"ten": "US", "ngon_ngu": "English"})
    c.post("/general/markets/create", data={"ten": "Korea", "ngon_ngu": "Korean"})
    # tạo KHÔNG tick → 0 thị trường (không còn mặc định cả danh mục)
    r = c.post("/general/niches/create", data={"ten_chuan": "Space"})
    assert "none chosen" in r.text
    # tạo CÓ tick 2 thị trường
    r = c.post("/general/niches/create", data={
        "ten_chuan": "Life In", "thi_truong": ["TT-US", "TT-KOREA"]})
    assert r.text.count("N-LIFE-IN") >= 1 and "US" in r.text and "Korea" in r.text
    from nen.common import danh_ba
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == "N-LIFE-IN")
    assert sorted(n["thi_truong_cua"]) == ["TT-KOREA", "TT-US"]
    # update thay cả tập: chỉ còn Korea
    c.post("/general/niches/update", data={
        "ma": "N-LIFE-IN", "ten_chuan": "Life In", "trang_thai": "thu",
        "thi_truong": ["TT-KOREA"]})
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == "N-LIFE-IN")
    assert n["thi_truong_cua"] == ["TT-KOREA"]
    # mã thị trường lạ → lỗi hiện trên trang, không 500
    r = c.post("/general/niches/update", data={
        "ma": "N-LIFE-IN", "ten_chuan": "Life In", "trang_thai": "thu",
        "thi_truong": ["TT-LA"]})
    assert r.status_code == 200 and "không tồn tại" in r.text
