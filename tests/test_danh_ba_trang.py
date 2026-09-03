# -*- coding: utf-8 -*-
"""Test trang Niches + Channels (Đ1 khối đế): gate Manager+/Owner, luồng
niche-trước-kênh, khai tử gõ lại mã, audit có vết, export CSV."""
import re

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


# 03/09: ma la DAY SO (N-001, K-014) chu khong con lay theo ten -> test khong the
# ghim "N-LIFE-IN" nua. Ba helper duoi tao thuc the roi TRA VE MA that.
def _ma_moi(resp, tien_to):
    m = re.findall(rf"{tien_to}-\d{{3,}}", resp.text)
    assert m, f"khong thay ma {tien_to}-<so> trong response"
    return m[-1]


def _tao_ngach(c, ten, **kw):
    r = c.post("/general/niches/create", data={"ten_chuan": ten, **kw})
    return _ma_moi(r, "N")


def _tao_tt(c, ten, ngon_ngu=""):
    r = c.post("/general/markets/create", data={"ten": ten, "ngon_ngu": ngon_ngu})
    return _ma_moi(r, "TT")


def _tao_kenh(c, ten, **kw):
    r = c.post("/general/channels/create", data={"ten_chuan": ten, **kw})
    return _ma_moi(r, "K")

def test_gate_l2_khong_vao_l4_vao(he):
    assert _login("nhanvien", "mk-nv-6").get("/general/niches").status_code == 403
    assert _login("quanly", "mk-ql-6").get("/general/niches").status_code == 200
    assert _login("quanly", "mk-ql-6").get("/general/channels").status_code == 200


def test_niche_truoc_kenh_va_luong_tao(he):
    c = _login("quanly", "mk-ql-6")
    ng = _tao_ngach(c, "Life In", trang_thai="khai_thac")
    tt = _tao_tt(c, "US", "English")
    kenh = _tao_kenh(c, "Outland", ngach_ma=ng, thi_truong_ma=tt,
                     channel_id="UCabc", loai_kenh="compilation", trang_thai="sandbox")
    assert kenh.startswith("K-")
    # tên vẫn hiện trên trang (mã là số, tên mới là thứ người đọc)
    assert "Outland" in c.get("/general/channels").text
    # tạo kênh vào ngách KHÔNG tồn tại → lỗi hiện trên trang, không 500
    truoc = len(re.findall(r"K-\d{3,}", c.get("/general/channels").text))
    r = c.post("/general/channels/create",
               data={"ten_chuan": "Mồ côi", "ngach_ma": "N-KHONG-CO"})
    assert r.status_code == 200
    sau = len(re.findall(r"K-\d{3,}", c.get("/general/channels").text))
    assert sau == truoc, "ngach khong ton tai thi KHONG duoc cap ma kenh"


def test_doi_vong_doi_va_audit_co_vet(he):
    c = _login("quanly", "mk-ql-6")
    ng = _tao_ngach(c, "Space")
    kenh = _tao_kenh(c, "Astro", ngach_ma=ng)
    r = c.post("/general/channels/trang-thai",
               data={"ma": kenh, "trang_thai": "hoat_dong"})
    assert "hoat_dong" in r.text
    conn = iam.ket_noi()
    nk = "".join(str(dict(d)) for d in iam.doc_nhat_ky(conn, 50))
    conn.close()
    assert kenh in nk and "danh_ba" in nk             # mọi thao tác có vết


def test_khai_tu_chi_owner_va_phai_go_lai_ma(he):
    ql = _login("quanly", "mk-ql-6")
    ng = _tao_ngach(ql, "OLD")
    kenh = _tao_kenh(ql, "Time Vault", ngach_ma=ng)
    assert ql.post("/general/channels/khai-tu",
                   data={"ma": kenh, "go_lai": kenh}
                   ).status_code == 403               # Manager không được khai tử
    ow = _login("owner-t", "mk-test")
    r = ow.post("/general/channels/khai-tu", data={"ma": kenh, "go_lai": "go-sai"})
    assert "Retype" in r.text                          # gõ sai mã → chặn
    r = ow.post("/general/channels/khai-tu", data={"ma": kenh, "go_lai": kenh})
    assert "Retired" in r.text
    assert "khai_tu" in ow.get(f"/general/channels?ma={kenh}").text


def test_post_redirect_get_giu_vi_tri(he):
    """Owner 18/08 'đổi trạng thái kênh bị chuyển URL': mọi POST danh bạ 303 về
    GET sạch GIỮ VỊ TRÍ (?ma= chi tiết đang mở + bộ lọc) + bao/loi — hết kẹt URL
    đường POST, F5 hết re-submit; nhánh LỖI cũng redirect."""
    c = TestClient(gateway_app, follow_redirects=False)
    c.post("/login", data={"ten": "quanly", "mat_khau": "mk-ql-6"})
    rn = c.post("/general/niches/create", data={"ten_chuan": "Space"})
    ng = re.search(r"N-\d{3,}", rn.headers.get("location", "") + rn.text).group()
    r = c.post("/general/channels/create",
               data={"ten_chuan": "Astro", "ngach_ma": ng})
    assert r.status_code == 303
    kenh = re.search(r"K-\d{3,}", r.headers["location"]).group()
    assert f"ma={kenh}" in r.headers["location"]       # mở luôn kênh vừa tạo

    r = c.post("/general/channels/trang-thai",
               data={"ma": kenh, "trang_thai": "hoat_dong",
                     "ve_ma": kenh, "ve_ngach": ng})
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.startswith("/general/channels?")
    assert f"ma={kenh}" in loc and f"ngach={ng}" in loc and "bao=" in loc
    trang = c.get(loc).text
    assert ">Traction</span>" in trang                 # đổi THẬT + chi tiết vẫn mở

    # nhánh lỗi cũng redirect kèm loi + giữ vị trí (không kẹt URL POST)
    r = c.post("/general/channels/trang-thai",
               data={"ma": kenh, "trang_thai": "trang-thai-la", "ve_ma": kenh})
    assert r.status_code == 303
    assert "loi=" in r.headers["location"] and f"ma={kenh}" in r.headers["location"]
    # niches cùng khuôn: trạng thái lạ → 303 kèm loi (không render trực tiếp)
    r = c.post("/general/niches/create",
               data={"ten_chuan": "Space 2", "trang_thai": "trang-thai-la"})
    assert r.status_code == 303 and "loi=" in r.headers["location"]


def test_lien_ket_app_chi_owner(he):
    ql = _login("quanly", "mk-ql-6")
    ng = _tao_ngach(ql, "Life In")
    kenh = _tao_kenh(ql, "Outland", ngach_ma=ng)
    assert ql.post("/general/channels/link",
                   data={"ma": kenh, "app_slug": "seo-optimize",
                         "khoa": "outland-o-01"}).status_code == 403
    ow = _login("owner-t", "mk-test")
    ow.post("/general/channels/link",
            data={"ma": kenh, "app_slug": "seo-optimize", "khoa": "outland-o-01"})
    assert "outland-o-01" in ow.get(f"/general/channels?ma={kenh}").text


def test_export_csv(he):
    c = _login("quanly", "mk-ql-6")
    ng = _tao_ngach(c, "Life In")
    r = c.get("/general/channels/export")
    assert r.status_code == 200 and ng in r.text
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
    n_life = _tao_ngach(c, "Life In")
    n_space = _tao_ngach(c, "Space")
    tt_us = _tao_tt(c, "US", "English")
    kenh = {}
    for ten in ("Outland", "Life Decoded"):
        kenh[ten] = _tao_kenh(c, ten, ngach_ma=n_life, thi_truong_ma=tt_us,
                              trang_thai="sandbox")
    kenh["Space Archive"] = _tao_kenh(c, "Space Archive", ngach_ma=n_space,
                                      trang_thai="uom_mam")

    b = c.get("/general/niches").text
    assert b.count(f'href="/general/channels?ngach={n_life}"') == 2   # 2 chip kênh
    assert b.count(f'href="/general/channels?ngach={n_space}"') == 1
    # Markets đếm ĐÚNG số kênh gắn thị trường đó (Space Archive không gắn US)
    dong_us = [d for d in b.split("<tr>") if tt_us in d][0]
    assert "<td>2</td>" in dong_us

    def _bang(html):      # chỉ xét BẢNG (dropdown "Clone of" trong modal liệt kê mọi kênh)
        return html.split('id="bang-kenh"', 1)[1].split("</table>", 1)[0]
    b = _bang(c.get(f"/general/channels?ngach={n_life}").text)         # lọc theo niche
    assert kenh["Outland"] in b and kenh["Space Archive"] not in b
    b = _bang(c.get("/general/channels?trang_thai=uom_mam").text)      # lọc vòng đời
    assert kenh["Space Archive"] in b and kenh["Outland"] not in b
    # dữ liệu cho lọc CLIENT-side (market + search) có sẵn trên từng dòng
    b = c.get("/general/channels").text
    assert f'data-market="{tt_us}"' in b and 'id="q-kenh"' in b
    assert 'id="loc-tt-market"' in b


def test_nhan_en_va_khong_ghi_chu_man_hinh(he):
    """Chuẩn UI hệ: nhãn EN, nhãn vòng đời/trạng thái dịch sang EN, không câu
    giải thích tiếng Việt trên màn hình (luật Owner mục 12.2)."""
    c = _login("quanly", "mk-ql-6")
    ng = _tao_ngach(c, "Life In", trang_thai="khai_thac")
    kenh = _tao_kenh(c, "Outland", ngach_ma=ng, trang_thai="sandbox")
    b = c.get("/general/niches").text
    # nhãn EN hiện ra; mã máy chỉ còn trong value/data-* (không phải chữ người đọc)
    assert ">Exploiting</span>" in b and ">khai_thac<" not in b
    b = c.get(f"/general/channels?ma={kenh}").text
    assert "Testing" in b and "Export CSV" in b
    assert "chưa gán" not in b and "gõ lại" not in b        # hết chuỗi VN cũ trên màn
    # khối khai tử vẫn CHỈ Owner (quyền không đổi) — nhãn EN + gõ-lại-mã giữ nguyên
    assert "Retire channel" not in b
    ow = _login("owner-t", "mk-test").get(f"/general/channels?ma={kenh}").text
    assert "Retire channel" in ow and f'placeholder="retype {kenh}"' in ow


def test_niche_thi_truong_user_chon_khong_mac_dinh(he):
    """Owner chốt 18/08: thị trường THUỘC TỪNG NGÁCH do user tick — ngách tạo
    không tick gì = 'none chosen', tick rồi sửa là thay cả tập."""
    c = _login("quanly", "mk-ql-6")
    tt_us = _tao_tt(c, "US", "English")
    tt_kr = _tao_tt(c, "Korea", "Korean")
    # tạo KHÔNG tick → 0 thị trường (không còn mặc định cả danh mục)
    r = c.post("/general/niches/create", data={"ten_chuan": "Space"})
    assert "none chosen" in r.text
    # tạo CÓ tick 2 thị trường
    r = c.post("/general/niches/create", data={
        "ten_chuan": "Life In", "thi_truong": [tt_us, tt_kr]})
    ng = _ma_moi(r, "N")
    assert "US" in r.text and "Korea" in r.text
    from nen.common import danh_ba
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == ng)
    assert sorted(n["thi_truong_cua"]) == sorted([tt_kr, tt_us])
    # update thay cả tập: chỉ còn Korea
    c.post("/general/niches/update", data={
        "ma": ng, "ten_chuan": "Life In", "trang_thai": "duy_tri",
        "thi_truong": [tt_kr]})
    n = next(t for t in danh_ba.liet_ke("ngach") if t["ma"] == ng)
    assert n["thi_truong_cua"] == [tt_kr]
    # mã thị trường lạ → lỗi hiện trên trang, không 500
    r = c.post("/general/niches/update", data={
        "ma": ng, "ten_chuan": "Life In", "trang_thai": "duy_tri",
        "thi_truong": ["TT-LA"]})
    assert r.status_code == 200 and "không tồn tại" in r.text


def test_nhan_vong_doi_hien_tu_nguon_chung(he):
    """29/08: nhãn vòng đời chuyển từ khai CỨNG trong template sang
    danh_ba.NHAN_TRANG_THAI_KENH (dùng chung với Data Analytics). Ghim rằng biến
    THẬT SỰ tới template — thiếu thì nhãn ra rỗng mà trang vẫn 200, test status
    không bắt được."""
    from nen.common import danh_ba
    c = _login("quanly", "mk-ql-6")
    n2 = _tao_ngach(c, "Space 2")
    _tao_kenh(c, "Astro", ngach_ma=n2, trang_thai="sandbox")
    r = c.get("/general/channels")
    assert r.status_code == 200
    assert danh_ba.NHAN_TRANG_THAI_KENH["sandbox"] in r.text      # 'Testing' hiện thật
    # bộ lọc liệt kê đủ mọi nấc (kể cả nấc ẩn Retired) bằng nhãn, không phải mã thô
    for ma in danh_ba.TRANG_THAI_KENH_HOP_LE:
        assert danh_ba.NHAN_TRANG_THAI_KENH[ma] in r.text


def test_doi_ten_ngach_thi_TEN_MOI_dung_truoc_ma_cu(he):
    """Owner 03/09: tao ngach 'What If' roi doi ten 'SCI-FI' -> tuong "ten khong
    doi duoc" vi bang hien MA in dam o cot DAU (N-WHAT-IF), ten that nam cot sau.
    Ma phai giu (noi sang RadarY/Niche Research) nhung khong duoc gia lam ten."""
    c = _login("quanly", "mk-ql-6")
    ma = _tao_ngach(c, "What If")
    r = c.post("/general/niches/update",
               data={"ma": ma, "ten_chuan": "SCI-FI", "trang_thai": "khai_thac"})
    assert r.status_code == 200
    assert ma in r.text, "ma phai GIU nguyen"
    assert "SCI-FI" in r.text, "ten moi phai hien"
    # ten dung TRUOC ma trong cung mot hang -> mat doc ten truoc
    hang = [d for d in r.text.split("<tr") if "SCI-FI" in d and ma in d][0]
    assert hang.index("SCI-FI") < hang.index(ma), "ten phai dung TRUOC ma"
    # tieu de bang: cot Name truoc cot Code
    assert r.text.index("<th>Name</th>") < r.text.index("<th>Code</th>")


def test_ma_moi_la_DAY_SO_khong_lay_theo_ten(he):
    """Owner 03/09: 'dat code thi dat la mot day so, tranh gay hieu nham'.
    Ma sinh tu ten (What If -> N-WHAT-IF) TRONG NHU TEN, nen doi ten ma ma dung
    yen thi tuong hong. Ma so thi khong ai nham no voi ten."""
    c = _login("quanly", "mk-ql-6")
    r = c.post("/general/niches/create", data={"ten_chuan": "What If"})
    assert "WHAT-IF" not in r.text, "ma KHONG duoc lay theo ten nua"
    import re as _re
    ma = _re.search(r"N-\d{3,}", r.text)
    assert ma, f"phai sinh ma dang N-<so>: {r.text[:300]}"
    # doi ten: ma GIU nguyen (van la khoa noi sang RadarY/Niche Research)
    r2 = c.post("/general/niches/update",
                data={"ma": ma.group(), "ten_chuan": "SCI-FI", "trang_thai": "khai_thac"})
    assert ma.group() in r2.text and "SCI-FI" in r2.text


def test_ma_so_khong_trung_va_khong_dung_lai_so_da_xoa(he):
    """So chay tang theo max hien co, khong dem lai tu dau — xoa roi tao moi thi
    KHONG duoc cap lai so cu (ma cu con nam trong audit/lien ket app)."""
    from nen.common import danh_ba
    conn = danh_ba.ket_noi() if hasattr(danh_ba, "ket_noi") else None
    c = _login("quanly", "mk-ql-6")
    mas = []
    import re as _re
    for ten in ("Alpha", "Beta", "Gamma"):
        r = c.post("/general/niches/create", data={"ten_chuan": ten})
        m = _re.search(r"N-\d{3,}", r.text)
        assert m, ten
        mas.append(m.group())
    assert len(set(mas)) == 3, f"ma phai khac nhau: {mas}"
    so = [int(x.split("-")[1]) for x in mas]
    assert so == sorted(so), f"so phai tang dan: {so}"
