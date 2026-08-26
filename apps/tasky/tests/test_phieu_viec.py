# -*- coding: utf-8 -*-
"""§16 — phiếu việc (từ 26/08 nằm ở mục TASK, không còn trên trang Goal).

Owner 25/08: "Ô Goal vẫn chưa hiển thị rõ hết text — Goal phải rất rõ ràng";
"Nút thêm việc phải ở trên cùng… box thêm việc không nên là box cứng mà chỉ là
nút bấm, khi nhấn thì box mềm hiện ra".
"""
import pytest
from fastapi.testclient import TestClient

from src import main, muc_tieu as mt, tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4",
         "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}
_c = TestClient(main.app)

TEN_DAI = "Định hướng kinh doanh tháng 9/2026 cho toàn khối vận hành và nội dung"


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}], ""))


def test_the_goal_hien_du_ten_khong_cat_bang_ellipsis(_so):
    """Thẻ Goal (trang Goal) phải hiện đủ tên, không cắt bằng '…'."""
    mt.tao(MGR, TEN_DAI, "kq")
    r = _c.get("/muc-tieu", headers=H_MGR)
    the = r.text.split('<article class="g-the')[1].split("</article>")[0]
    assert TEN_DAI in the
    css = r.text.split(".g-the .ten{")[1].split("}")[0]
    assert "text-overflow:ellipsis" not in css


def test_them_viec_la_nut_mo_ra_khong_phai_box_cung(_so):
    m = mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    assert '<details class="them-viec">' in r.text     # đóng sẵn, bấm mới bung
    assert '<div class="them-viec">' not in r.text


def test_nut_them_viec_nam_TREN_danh_sach_viec(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_muc_tieu(ma, MGR, "Rà 10 video", "x", m["id"])
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    assert r.text.index('<details class="them-viec"') < r.text.index("Rà 10 video")


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


# ---------- lõi: mô tả + tài liệu đính kèm ----------

OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}
NGOAI = {"ten": "ducm", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Minh Đức"}


def _viec(ma):
    return tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat")


def test_nguoi_giao_bo_sung_mo_ta_sau_khi_da_giao(ma):
    v = _viec(ma)
    tuan.sua_viec(ma, v["id"], MGR, mo_ta="Ưu tiên 3 video kênh Life In US")
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["mo_ta"].startswith("Ưu tiên 3")


def test_nguoi_lam_khong_sua_de_bai(ma):
    v = _viec(ma)
    with pytest.raises(PermissionError):
        tuan.sua_viec(ma, v["id"], NV, tieu_de="Việc khác hẳn")


def test_viec_tu_them_thi_chinh_chu_sua_duoc(ma):
    v = tuan.them_viec_tu(ma, NV, "Tự học dựng", "hoc")
    tuan.sua_viec(ma, v["id"], NV, mo_ta="Xem 2 khóa")
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["mo_ta"] == "Xem 2 khóa"


def test_ca_hai_ben_dinh_duoc_tai_lieu_nguoi_ngoai_thi_khong(ma):
    v = _viec(ma)
    tuan.them_tai_lieu(ma, v["id"], MGR, "https://nas/ke-hoach.xlsx", "Kế hoạch")
    tuan.them_tai_lieu(ma, v["id"], NV, "https://drive/ban-dung", "Bản dựng")
    assert len(tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]) == 2
    with pytest.raises(PermissionError):
        tuan.them_tai_lieu(ma, v["id"], NGOAI, "https://x/y")


def test_chan_duong_dan_chay_duoc_script(ma):
    v = _viec(ma)
    for xau in ("javascript:alert(1)", "data:text/html,<script>", "chỗ nào đó"):
        with pytest.raises(ValueError):
            tuan.them_tai_lieu(ma, v["id"], MGR, xau)


def test_go_tai_lieu_chi_nguoi_dinh_hoac_nguoi_giao(ma):
    v = _viec(ma)
    tl = tuan.them_tai_lieu(ma, v["id"], NV, "https://drive/ban-dung")
    with pytest.raises(PermissionError):
        tuan.xoa_tai_lieu(ma, v["id"], NGOAI, tl["id"])
    tuan.xoa_tai_lieu(ma, v["id"], MGR, tl["id"])          # người giao gỡ được
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"] == []


def test_viec_cu_khong_co_truong_moi_van_chay(ma):
    """Sổ tuần đã có trên máy công ty không mang 2 khóa này — không được vỡ."""
    v = _viec(ma)
    so = tuan.doc_tuan(ma)
    x = tuan._tim(so, v["id"])
    x.pop("mo_ta"), x.pop("tai_lieu")
    tuan._ghi_tuan(so)
    tuan.them_tai_lieu(ma, v["id"], MGR, "https://a/b")
    tuan.sua_viec(ma, v["id"], MGR, mo_ta="bù sau")
    assert len(tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]) == 1


# ---------- giao diện phiếu ----------

def test_phieu_hien_mo_ta_va_tai_lieu_da_dinh(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat", muc_tieu_id=m["id"])
    tuan.sua_viec(ma, v["id"], MGR, mo_ta="Ưu tiên kênh Life In US")
    tuan.them_tai_lieu(ma, v["id"], MGR, "https://nas.vn/ke-hoach.xlsx", "Kế hoạch T9")
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    assert "Ưu tiên kênh Life In US" in r.text
    assert 'href="https://nas.vn/ke-hoach.xlsx"' in r.text and "Kế hoạch T9" in r.text
    assert 'action="/tasky/viec/tai-lieu"' in r.text


def test_dinh_tai_lieu_bang_form_va_bao_loi_khi_dan_bay(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat", muc_tieu_id=m["id"])
    ve = "/task?goal=" + m["id"]
    r = _c.post("/tasky/viec/tai-lieu", headers=H_MGR, follow_redirects=False,
                data={"id": v["id"], "dia_chi": "https://a.vn/x", "ten": "Brief",
                      "tuan_xem": ma, "ve": ve})
    assert r.status_code == 303 and "loi=" not in r.headers["location"]
    r = _c.post("/tasky/viec/tai-lieu", headers=H_MGR, follow_redirects=False,
                data={"id": v["id"], "dia_chi": "javascript:alert(1)",
                      "tuan_xem": ma, "ve": ve})
    assert "loi=" in r.headers["location"]           # nói thẳng, không nuốt lặng lẽ
    assert len(tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]) == 1


def test_go_viec_bang_form_thuan(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_muc_tieu(ma, MGR, "Việc gõ nhầm", "x", m["id"])
    r = _c.post("/tasky/viec/xoa", headers=H_MGR, follow_redirects=False,
                data={"id": v["id"], "tuan_xem": ma, "ve": "/task"})
    assert r.status_code == 303
    assert tuan.doc_tuan(ma)["viec"] == []


def test_viec_dang_lam_thi_khong_go_trang_bao_loi(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    H_NV = {**H_MGR, "X-Remote-User": "hant", "X-Remote-Level": "2",
            "X-Remote-Actions": "vao"}
    r = _c.post("/tasky/viec/xoa", headers=H_NV, follow_redirects=False,
                data={"id": v["id"], "tuan_xem": ma, "ve": "/tasky"})
    assert "loi=" in r.headers["location"]
    assert len(tuan.doc_tuan(ma)["viec"]) == 1        # công của người ta còn nguyên


def test_them_viec_kem_mo_ta_va_tai_lieu_ngay_luc_tao(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    r = _c.post("/api-tasky/muc-tieu/che-viec", headers=H_MGR,
                data={"muc_tieu_id": m["id"], "tieu_de": "Rà 10 video",
                      "loai_viec": "nghien_cuu", "nguoi": "hant", "tuan_xem": ma,
                      "mo_ta": "3 kênh đối thủ", "tai_lieu": "https://a.vn/list"})
    assert r.status_code == 200
    v = tuan.doc_tuan(ma)["viec"][0]
    assert v["mo_ta"] == "3 kênh đối thủ" and len(v["tai_lieu"]) == 1


def test_tai_lieu_dan_bay_khong_lam_hong_viec_vua_tao(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    r = _c.post("/api-tasky/muc-tieu/che-viec", headers=H_MGR,
                data={"muc_tieu_id": m["id"], "tieu_de": "Rà 10 video",
                      "loai_viec": "nghien_cuu", "tuan_xem": ma,
                      "tai_lieu": "chỗ nào đó"})
    assert r.status_code == 200 and "canh_bao" in r.json()
    assert tuan.doc_tuan(ma)["viec"][0]["tieu_de"] == "Rà 10 video"


def test_bao_loi_dinh_tai_lieu_hien_len_trang_khong_nuot(_so):
    m = mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/task?goal=%s&loi=Ch%%E1%%BB%%89+nh%%E1%%BA%%ADn+link+http" % m["id"],
               headers=H_MGR)
    assert "Chỉ nhận link http" in r.text


def test_nguoi_lam_thay_de_bai_va_tai_lieu_o_man_viec_cua_minh(ma, _so):
    """Đề bài giao cho họ mà họ không thấy thì mô tả vô nghĩa."""
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat")
    tuan.sua_viec(ma, v["id"], MGR, mo_ta="Ưu tiên kênh Life In US")
    tuan.them_tai_lieu(ma, v["id"], MGR, "https://nas.vn/brief.docx", "Brief")
    H_NV = {**H_MGR, "X-Remote-User": "hant", "X-Remote-Level": "2",
            "X-Remote-Actions": "vao"}
    r = _c.get("/tasky", headers=H_NV)
    assert "Ưu tiên kênh Life In US" in r.text
    assert 'href="https://nas.vn/brief.docx"' in r.text
    assert 'action="/tasky/viec/tai-lieu"' in r.text     # tự đính thêm được


def test_nguoi_lam_khong_go_duoc_tai_lieu_cua_leader(ma, _so):
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat")
    tl = tuan.them_tai_lieu(ma, v["id"], MGR, "https://nas.vn/brief.docx", "Brief")
    H_NV = {**H_MGR, "X-Remote-User": "hant", "X-Remote-Level": "2",
            "X-Remote-Actions": "vao"}
    assert 'value="%s"' % tl["id"] not in _c.get("/tasky", headers=H_NV).text
    r = _c.post("/tasky/viec/tai-lieu/xoa", headers=H_NV, follow_redirects=False,
                data={"id": v["id"], "id_tl": tl["id"], "tuan_xem": ma, "ve": "/tasky"})
    assert "loi=" in r.headers["location"]               # chốt thật ở server
    assert len(tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]) == 1


def test_board_bon_cot_theo_khau(ma, _so):
    """Từ 26/08 mục Task là BOARD: mặc định nhóm theo trạng thái (khâu nào ùn)."""
    m = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat", muc_tieu_id=m["id"])
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    for ten in ("Chưa nhận", "Đang làm", "Báo xong", "Đã nghiệm thu"):
        assert ten in r.text
    assert "Cần bạn xử lý" not in r.text


def test_nut_go_viec_nam_DUOI_CUNG_phieu(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_muc_tieu(ma, MGR, "Việc gõ nhầm", "x", m["id"])
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    phieu = r.text.split('class="phieu-noi"')[1].split("</details>")[0]
    assert phieu.index("Lưu mô tả") < phieu.index("Đính") < phieu.index("Gỡ việc này")


def test_o_sua_tai_cho_khong_bi_luat_o_nhap_chung_de(_so):
    """Ô sửa-tại-chỗ phải trông như CHỮ THƯỜNG — luật ô nhập chung không được đè
    (đã dính một lần: khung + nền hiện lên quanh tên Goal)."""
    mt.tao(MGR, "Goal A", "kq")
    css = _c.get("/task", headers=H_MGR).text
    luat = css.split(".noi-dung input:not([type=checkbox])")[1].split("{")[0]
    assert ":not(.o-tai-cho)" in luat


def test_moi_viec_la_mot_the_roi(ma, _so):
    """Owner 25/08: việc trong Task phải tách rời, không dính liền thành một khối."""
    m = mt.tao(MGR, "Goal A", "kq")
    for t in ("Việc 1", "Việc 2"):
        tuan.them_viec_muc_tieu(ma, MGR, t, "x", m["id"])
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    assert r.text.count('<li class="the-viec"') == 2
    css = r.text.split("ul.vs li.the-viec{")[1].split("}")[0]
    assert "border:" in css and "border-radius" in css


# ---------- §16b: mỗi tab báo cáo một vai, không lặp khối ----------

H_OWNER = {"X-Remote-User": "bot", "X-Remote-Level": "5",
           "X-Remote-Dept": "Ban%20qu%E1%BA%A3n%20tr%E1%BB%8B",
           "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan,"
                               "bao_cao_cong_ty,bao_cao_nhan_su",
           "X-Remote-Apps": "tasky"}


def _khoi(pham_vi):
    import re
    r = _c.get("/bao-cao-tuan?pham_vi=" + pham_vi, headers=H_OWNER)
    return re.findall(r"<h3>([^<]*)</h3>", r.text)


def test_moi_khoi_bao_cao_chi_o_MOT_tab(_so):
    """Owner 25/08: 'Từng người', 'Goal', 'Kho quy trình' lặp ở cả ba tab."""
    cty, bp, ns = _khoi("cong-ty"), _khoi("bo-phan"), _khoi("nhan-su")
    assert "Theo bộ phận" in cty and "Nhiệm vụ tôi giao" in cty
    assert "Từng người" not in cty          # bóc từng người là việc của Manager
    assert "Kho quy trình đang hình thành" not in cty
    assert "Goal toàn công ty" not in cty and "Goal của bộ phận" not in cty
    assert "Từng người" in bp and "Goal của bộ phận" in bp
    assert "Từng người" in ns and "Goal của bộ phận" not in ns


def test_bo_bang_tung_nguoi_KHONG_cat_quyen_xem_bo_phan_khac(ma, _so):
    """Bỏ khối trùng là việc BỐ CỤC — không được đụng luật 04/08."""
    tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat")
    r = _c.get("/bao-cao-tuan?pham_vi=bo-phan&bo=Vận hành", headers=H_OWNER)
    assert "Thu Hà" in r.text


# ---------- §16c: sửa tên việc — cái thấy = cái lưu ----------

def test_ten_viec_gon_khoang_trang_khi_luu(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "Chuẩn bị  báo cáo   quý 2", "x")
    assert v["tieu_de"] == "Chuẩn bị báo cáo quý 2"
    tuan.sua_viec(ma, v["id"], MGR, tieu_de="Chuẩn bị  báo cáo  quý 3")
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["tieu_de"] == "Chuẩn bị báo cáo quý 3"


def test_doi_ten_viec_bang_form_thi_dong_ngoai_doi_theo(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Tên cũ", "x", muc_tieu_id=m["id"])
    _c.post("/tasky/viec/sua", headers=H_MGR, follow_redirects=False,
            data={"id": v["id"], "tieu_de": "Tên mới hẳn", "mo_ta": "",
                  "tuan_xem": ma, "ve": "/task?goal=" + m["id"]})
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    dong = r.text.split('class="tieu-de"')[1].split("</div>")[0]
    assert "Tên mới hẳn" in dong and "Tên cũ" not in r.text


def test_vien_the_dung_token_do_duoc_ca_hai_theme(_so):
    """Owner 25/08: bản tối mất hết đường line của box. Viền chung --line chỉ đạt
    1.31:1 trên nền thẻ; token riêng --tk-vien khai cặp tối/sáng."""
    mt.tao(MGR, "Goal A", "kq")
    html = _c.get("/task", headers=H_MGR).text
    assert "--tk-vien:#52678a" in html and "--tk-vien:#c4c4c4" in html
    css = html.split("ul.vs li.the-viec{")[1].split("}")[0]
    assert "var(--tk-vien)" in css


# ---------- §16d: chip trạng thái trên thẻ việc ----------

from datetime import date, timedelta                      # noqa: E402


def _han_sau(n):
    return (date.today() + timedelta(days=n)).isoformat()


def test_chip_trang_thai_theo_tien_do(ma):
    v = tuan.them_viec_muc_tieu(ma, MGR, "V", "x", "mt-1")
    assert tuan.the_trang_thai(v)[0]["chu"] == "Chưa giao"
    v2 = tuan.them_viec_giao(ma, MGR, NV, "V2", "x")
    assert tuan.the_trang_thai(v2)[0]["chu"] == "Chưa ai nhận"
    tuan.nhan_viec(ma, v2["id"], NV)
    v2 = tuan._tim(tuan.doc_tuan(ma), v2["id"])
    assert tuan.the_trang_thai(v2)[0]["chu"] == "Đã nhận"
    tuan.bao_xong(ma, v2["id"], NV)
    v2 = tuan._tim(tuan.doc_tuan(ma), v2["id"])
    assert tuan.the_trang_thai(v2)[0]["chu"] == "Chờ nghiệm thu"


def test_chip_han_chi_hien_khi_that_su_gap(ma):
    xa = tuan.them_viec_giao(ma, MGR, NV, "Xa", "x", han=_han_sau(9))
    gan = tuan.them_viec_giao(ma, MGR, NV, "Gần", "x", han=_han_sau(1))
    qua = tuan.them_viec_giao(ma, MGR, NV, "Quá", "x", han=_han_sau(-3))
    assert [c["chu"] for c in tuan.the_trang_thai(xa)] == ["Chưa ai nhận"]
    assert "Gần đến hạn" in [c["chu"] for c in tuan.the_trang_thai(gan)]
    assert "Quá deadline" in [c["chu"] for c in tuan.the_trang_thai(qua)]


def test_viec_da_nghiem_thu_khong_bi_doa_qua_han(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "Xong rồi", "x", han=_han_sau(-5))
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    tuan.xac_nhan_viec(ma, v["id"], MGR)
    v = tuan._tim(tuan.doc_tuan(ma), v["id"])
    assert [c["chu"] for c in tuan.the_trang_thai(v)] == ["Đã nghiệm thu"]


def test_the_viec_hien_giao_cho_ai_va_chip_trang_thai(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "x",
                        muc_tieu_id=m["id"], han=_han_sau(-2))
    r = _c.get("/task?goal=" + m["id"], headers=H_MGR)
    the = r.text.split('<li class="the-viec"')[1].split("</li>")[0]
    # Kiểu Trello (26/08): người làm là AVATAR tròn có tooltip tên, không phải
    # một dòng chữ dài — nhưng vẫn phải là TÊN NGƯỜI, không phải tài khoản.
    assert 'title="Giao cho Thu Hà"' in the and ">TH</span>" in the
    assert "Chưa ai nhận" in the and "Quá deadline" in the
    assert the.index("Dựng 6 video") < the.index("Giao cho Thu Hà")
