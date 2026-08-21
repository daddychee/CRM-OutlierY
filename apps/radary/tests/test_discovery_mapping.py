# -*- coding: utf-8 -*-
"""DISCOVERY + MAPPING (21/08/2026) — vế CẦU và bản đồ cầu × cung.

Không gọi mạng thật: mọi lời gọi HTTP đi qua tham số `doc` (hàm tải giả).
Không dùng DB thật: dựng SQLite tạm trong bộ nhớ theo đúng SCHEMA của app.
"""
from __future__ import annotations

import json
import sqlite3
import time

import pytest

from radary import db, discovery, mapping

# ---------------------------------------------------------------- vế CẦU


def _doc_gia(bang: dict):
    """Hàm tải giả khớp CHÍNH XÁC tham số q (q nằm cuối URL).

    Bẫy đã dính khi viết test: so bằng `in` thì 'q=life+in' khớp luôn cả URL của
    'life in a' → mọi biến thể trả cùng một kết quả, do_phu tính sai.
    """
    from urllib.parse import quote_plus

    def doc(url: str) -> str:
        for k, v in bang.items():
            if url.endswith("q=" + quote_plus(k)):
                return json.dumps([k, v, [], {}])
        return json.dumps(["", [], [], {}])
    return doc


def test_bo_dem_chan_dung_tran():
    """Rate-limit là van an toàn: IP dùng chung với harvest + transcript."""
    nhip = []
    d = discovery.BoDem(tran=3, nghi=1.0, dong_ho=lambda: 100.0, ngu=nhip.append)
    assert [d.xin_phep() for _ in range(5)] == [True, True, True, False, False]
    assert d.da_goi == 3
    assert nhip, "phải có giãn nhịp giữa các lời gọi"


def test_bien_the_seed_luon_hoi_seed_tran_truoc():
    bt = discovery.bien_the_seed("life in")
    assert bt[0] == "life in"
    assert "life in a" in bt and "why life in" in bt
    assert len(bt) == 1 + 26 + len(discovery.TU_HOI)


def test_mo_rong_dem_do_phu_va_hang():
    """do_phu = số biến thể seed mà cụm lọt ra — tín hiệu ĐẾM ĐƯỢC thay cho volume."""
    doc = _doc_gia({
        "life in": ["life in vietnam", "life in japan"],
        "life in a": ["life in vietnam", "life in australia"],
    })
    ra = discovery.mo_rong("life in", discovery.BoDem(tran=2, nghi=0), doc,
                           chu_cai=True, tu_hoi=False)
    assert ra["life in vietnam"]["do_phu"] == 2      # lọt ra từ cả hai hướng gõ
    assert ra["life in japan"]["do_phu"] == 1
    assert ra["life in vietnam"]["hang_tot_nhat"] == 1


def test_goi_y_loi_mang_khong_giet_ca_phien():
    def doc_no(url):
        raise OSError("mạng chết")
    assert discovery.goi_y_youtube("x", doc_no) == []


def test_loc_nhieu_bo_cum_lac_de():
    """Đo thật 21/08: seed 'life in' trả về 'life in prison roblox'."""
    cums = {"life in vietnam": {}, "life in prison roblox": {}, "cooking pasta": {}}
    ra = discovery.loc_nhieu(cums, "life in", chan=("roblox",))
    assert set(ra) == {"life in vietnam"}


def test_quet_sap_theo_do_phu():
    # cụm phải CHỨA seed, nếu không loc_nhieu loại đúng (cụm lạc đề)
    doc = _doc_gia({"seed": ["seed b", "seed a"], "seed a": ["seed a"]})
    ra = discovery.quet("seed", dem=discovery.BoDem(tran=2, nghi=0), doc=doc, tu_hoi=False)
    assert [m["cum"] for m in ra][0] == "seed a"     # do_phu=2, đứng đầu
    assert ra[0]["nguon"] == "autocomplete"


def test_quet_loai_het_cum_lac_de_thi_tra_rong():
    """Không có gì hợp lệ thì trả rỗng, không bịa ra cụm cho đủ bảng."""
    doc = _doc_gia({"seed": ["cooking pasta", "guitar lesson"]})
    assert discovery.quet("seed", dem=discovery.BoDem(tran=1, nghi=0), doc=doc,
                          tu_hoi=False) == []


# ---------------------------------------------------------------- vế CUNG


def _kho(*titles):
    return [{"id": i, "title": t, "title_l": t.lower(), "kenh": f"kenh{i}",
             "kenh_yt": f"UC{i}", "yt_id": f"v{i}", "pub_ts": 1000.0 + i,
             "vph": 10.0, "views": 100 * (i + 1)}
            for i, t in enumerate(titles)]


def test_khop_theo_ranh_gioi_tu_khong_nuot_tu_khac():
    """Bài học SEO 18/08: 'Life' nuốt 'Life In'. LIKE %life in% sẽ khớp
    'life incremental' — sai hẳn bản chất."""
    kho = _kho("Life in Vietnam", "Life incremental roblox", "MY LIFE IN JAPAN")
    r = mapping.do_cung(kho, "life in")
    assert r["so_video"] == 2                        # bỏ 'life incremental'
    assert r["so_kenh"] == 2


def test_do_cung_tra_trung_vi_va_vi_du():
    kho = _kho("abandoned mall", "abandoned city", "abandoned hotel")
    r = mapping.do_cung(kho, "abandoned")
    assert r["so_video"] == 3
    assert r["view_trung_vi"] == 200
    assert r["vi_du"][0]["views"] == 300             # ví dụ xếp theo view giảm dần


def test_cum_khong_co_video_tra_ve_khong_vo():
    r = mapping.do_cung(_kho("abc"), "why do people")
    assert r == {"so_video": 0, "so_kenh": 0, "view_trung_vi": 0,
                 "vph_trung_vi": 0.0, "moi_nhat": 0, "vi_du": []}


# ---------------------------------------------------------------- bản đồ


def _cums(*cap):
    return [{"cum": c, "seed": "s", "do_phu": d, "hang_tb": 1.0} for c, d in cap]


def test_ban_do_chia_du_4_o():
    kho = _kho(*(["life in x"] * 10), "jupiter core", "why nobody talks")
    bd = mapping.ban_do(kho, _cums(("life in", 9), ("why do people", 8),
                                   ("jupiter", 2), ("tuvalu", 1), ("abandoned", 5)))
    assert bd["du_mau"] is True
    o = {m["cum"]: m["o"] for m in bd["muc"]}
    assert o["life in"] == mapping.O_DO_LUA             # cầu cao · cung cao
    assert o["why do people"] == mapping.O_KHOANG_TRONG  # cầu cao · cung 0
    assert o["tuvalu"] == mapping.O_HOANG               # cầu thấp · cung thấp


def test_mau_nho_thi_KHONG_chia_o():
    """Không đủ mẫu thì nói thẳng, không đoán — cùng luật với engine chẩn đoán."""
    bd = mapping.ban_do(_kho("abc"), _cums(("a", 1), ("b", 2)))
    assert bd["du_mau"] is False
    assert all(m["o"] is None for m in bd["muc"])
    assert "cần ít nhất" in bd["ly_do_thieu_mau"]


def test_nguong_la_TRUNG_VI_cua_phien_khong_phai_hang_so():
    """Ngưỡng cứng không căn cứ đã bị bác ở proposal V3 bản 1 — ghim lại ở đây."""
    bd = mapping.ban_do(_kho("x"), _cums(("a", 100), ("b", 100), ("c", 100),
                                         ("d", 100), ("e", 100)))
    assert bd["nguong"]["cau_do_phu"] == 100
    assert not any(isinstance(v, str) for v in bd["nguong"].values())


def test_cung_thap_hai_nghia_phan_biet_duoc_nho_cau():
    """Lý do tồn tại của module: 'tuvalu' (ít xem) vs 'why do people' (chưa ai làm)
    nhìn vế cung thì giống hệt nhau."""
    bd = mapping.ban_do(_kho("a b", "c d", "e f"),
                        _cums(("tuvalu", 1), ("why do people", 9),
                              ("m", 5), ("n", 5), ("o", 5)))
    o = {m["cum"]: m["o"] for m in bd["muc"]}
    assert o["tuvalu"] != o["why do people"]


# ---------------------------------------------------------------- lưu trữ


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    c.execute("INSERT INTO orgs(id, name, created_ts) VALUES(1,'o',0)")
    c.execute("INSERT INTO workspaces(id, org_id, name, created_ts) VALUES(1,1,'w',0)")
    c.commit()
    yield c
    c.close()


def test_luu_idempotent_khong_de_trung_cum(conn):
    muc = _cums(("life in vietnam", 3), ("abandoned", 2))
    db.kw_luu(conn, 1, muc, ngay="2026-08-21")
    db.kw_luu(conn, 1, muc, ngay="2026-08-21")          # quét lại cùng ngày
    assert conn.execute("SELECT COUNT(*) FROM keywords").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM keyword_stats").fetchone()[0] == 2


def test_luu_giu_chuoi_theo_ngay(conn):
    db.kw_luu(conn, 1, _cums(("x", 3)), ngay="2026-08-20")
    db.kw_luu(conn, 1, _cums(("x", 7)), ngay="2026-08-21")
    chuoi = db.kw_lich_su(conn, 1, "x")
    assert [r["do_phu"] for r in chuoi] == [7, 3]       # mới nhất trước
    assert db.kw_danh_sach(conn, 1)[0]["do_phu"] == 7   # danh sách lấy lần gần nhất


def test_bo_qua_la_go_MEM_giu_lich_su(conn):
    db.kw_luu(conn, 1, _cums(("nhieu", 5)), ngay="2026-08-21")
    assert db.kw_bo_qua(conn, 1, "nhieu") == 1
    assert db.kw_danh_sach(conn, 1) == []                       # khuất khỏi bản đồ
    assert len(db.kw_danh_sach(conn, 1, gom_bo_qua=True)) == 1   # vẫn còn dòng
    assert db.kw_lich_su(conn, 1, "nhieu")                      # lịch sử nguyên vẹn
    db.kw_bo_qua(conn, 1, "nhieu", bo=False)
    assert len(db.kw_danh_sach(conn, 1)) == 1                   # bật lại được


def test_cum_rong_bi_bo_qua_khi_luu(conn):
    kq = db.kw_luu(conn, 1, [{"cum": "  "}, {"cum": "ok"}], ngay="2026-08-21")
    assert kq["moi"] == 1


# ---------------------------------------------------------------- route API


def _ws(goi, mock_de):
    r = goi("POST", "/api/workspaces", vai="leader",
            json={"name": "US", "ngach": "N-LIFE-IN", "market": "TT-US"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_mapping_chua_quet_thi_noi_thang(org_moi, goi, mock_de):
    """Chưa có dữ liệu thì nói rõ, không trả bảng rỗng khó hiểu."""
    ws = _ws(goi, mock_de)
    r = goi("GET", f"/api/workspaces/{ws}/mapping", vai="viewer")
    assert r.status_code == 200
    d = r.json()
    assert d["chua_quet"] is True and d["muc"] == []
    assert "Chưa quét" in d["ly_do_thieu_mau"]


def test_viewer_XEM_duoc_mapping_nhung_KHONG_quet_duoc(org_moi, goi, mock_de):
    """Xem là đọc (viewer); quét là tiêu tài nguyên + đụng IP chung (leader+)."""
    ws = _ws(goi, mock_de)
    assert goi("GET", f"/api/workspaces/{ws}/mapping", vai="viewer").status_code == 200
    r = goi("POST", f"/api/workspaces/{ws}/discovery/scan", vai="viewer",
            json={"seed": "life in"})
    assert r.status_code == 403


def test_scan_thieu_seed_thi_422(org_moi, goi, mock_de):
    ws = _ws(goi, mock_de)
    r = goi("POST", f"/api/workspaces/{ws}/discovery/scan", vai="leader", json={"seed": "  "})
    assert r.status_code == 422


def test_bo_qua_cum_khong_co_thi_404(org_moi, goi, mock_de):
    ws = _ws(goi, mock_de)
    r = goi("POST", f"/api/workspaces/{ws}/keywords/bo-qua", vai="leader",
            json={"cum": "khong ton tai"})
    assert r.status_code == 404


def test_mapping_doc_duoc_sau_khi_co_keyword(org_moi, goi, mock_de):
    """Ghi thẳng vào DB (không gọi mạng) rồi đọc qua API — kiểm đường dữ liệu."""
    from radary import db
    ws = _ws(goi, mock_de)
    c = db.connect()
    db.kw_luu(c, ws, [{"cum": f"cum {i}", "do_phu": i} for i in range(1, 7)], ngay="2026-08-21")
    c.close()
    d = goi("GET", f"/api/workspaces/{ws}/mapping", vai="viewer").json()
    assert d["du_mau"] is True and len(d["muc"]) == 6
    assert set(d["nhan_o"]) == {"khoang_trong", "do_lua", "bao_hoa", "hoang"}
    assert d["nguong"]["cau_do_phu"] is not None


def test_tu_la_KHONG_duoc_dung_de_xep_hang():
    """Ghim bài học 21/08: chỉ số 'từ chưa có trong pool' ban đầu được dùng làm
    'độ hợp ngách' để dìm cụm lạc đề — nhưng đo thật cho thấy nó dìm luôn
    'life in rio' / 'life in kiev' (hợp ngách, pool chưa có = ĐÚNG khoảng trống).
    Máy không phân biệt được 'lạc đề' với 'mới lạ' → chỉ là cột thông tin."""
    kho = _kho("life in japan", "life in japan again", "life in korea", "life in korea 2")
    cums = [{"cum": c, "seed": "life in", "do_phu": d, "hang_tb": 1.0}
            for c, d in [("life in japan", 1), ("life in rio", 9), ("life in korea", 2),
                         ("life in kiev", 8), ("life in peru", 7)]]
    bd = mapping.ban_do(kho, cums)
    theo_cau = [m["cum"] for m in bd["muc"]]
    assert theo_cau[0] == "life in rio", "phải xếp theo CẦU, không theo mức mới lạ"
    la = {m["cum"]: m["tu_la"] for m in bd["muc"]}
    assert la["life in rio"] == 1.0      # 'rio' chưa có trong pool = mới lạ tối đa
    assert la["life in japan"] == 0.0    # 'japan' pool làm rồi


def test_tu_la_bo_tu_seed_ra_khoi_phep_tinh():
    von = {"japan"}
    assert mapping.tu_la_voi_pool("life in japan", von, seed="life in") == 0.0
    assert mapping.tu_la_voi_pool("life in", von, seed="life in") is None


# ------------------------------------------------- phân loại theo THỊ TRƯỜNG (21/08)


def _tt(**kw):
    d = {"so_ket_qua": 20, "ti_le_moi": 60, "tuoi_giua_ngay": 54,
         "kenh_nho_lot_top": 11, "view_giua_moi": 30000}
    d.update(kw)
    return d


def test_cum_chet_khong_con_la_khoang_trong():
    """Ca thật `life in rio`: pool 0 video nên bản đồ cũ gọi là 'khoảng trống', nhưng
    thị trường 0% video mới, tuổi trung vị 1.106 ngày = CỤM CHẾT."""
    m = {"so_video": 0, "tt": _tt(ti_le_moi=0, tuoi_giua_ngay=1106, view_giua_moi=None)}
    assert mapping.phan_loai_quyet_dinh(m) == "nguoi"


def test_cum_song_co_cua_thi_dang_danh():
    assert mapping.phan_loai_quyet_dinh({"so_video": 0, "tt": _tt()}) == "dang_danh"


def test_cum_song_nhung_toan_kenh_lon_thi_kho():
    assert mapping.phan_loai_quyet_dinh({"so_video": 0, "tt": _tt(kenh_nho_lot_top=1)}) == "kho"


def test_pool_da_lam_thi_khong_goi_la_khoang_trong():
    assert mapping.phan_loai_quyet_dinh({"so_video": 30, "tt": _tt()}) == "dang_lam"


def test_chua_do_thi_truong_thi_KHONG_doan():
    assert mapping.phan_loai_quyet_dinh({"so_video": 0}) == "chua_do"
    assert mapping.phan_loai_quyet_dinh({"so_video": 0, "tt": {"so_ket_qua": 0}}) == "chua_do"


def test_thi_truong_tra_duoi_muc_minh_thi_khong_dang_vao():
    """Ca thật `life in the countryside`: sống 60% + 11/20 kênh nhỏ nhưng chỉ 4k
    view/video mới, trong khi pool đang ở 30k → vào cũng không hơn cái mình đang có."""
    m = {"so_video": 0, "tt": _tt(view_giua_moi=4000)}
    assert mapping.phan_loai_quyet_dinh(m, pool_view_moi=30000) == "kho"
    assert mapping.phan_loai_quyet_dinh(m, pool_view_moi=None) == "dang_danh"   # không có baseline thì không phán


def test_tab_mapping_nam_trong_whitelist_cua_UI():
    """Bug 21/08: bấm tab Mapping xong bị đá về Board — vì guard 'tab không hợp lệ'
    trong app.js giữ một whitelist CỨNG mà tab mới không được thêm vào.
    Ghim cả 3 chỗ phải khai khi thêm tab, để lần sau không sót chỗ nào."""
    from pathlib import Path
    js = Path(__file__).resolve().parents[1].joinpath("web", "app.js").read_text(encoding="utf-8")
    assert "['board', 'alerts', 'mapping', 'reports', 'settings'].includes(tab)" in js, \
        "thiếu trong whitelist guard -> tab tự nhảy về board"
    assert "['mapping', 'Mapping']" in js, "thiếu trong TABS -> không có nút"
    assert "tab === 'mapping'" in js, "thiếu trong dispatch -> bấm vào ra trang trắng"


# --------------------------------- THỊ TRƯỜNG / NGÔN NGỮ (user: chỉ làm Mỹ, 21/08)


def test_loai_title_tieng_viet_khoi_seed_cua_thi_truong_my():
    """Sự cố thật: pool gốc lẫn kênh Việt → seed 'cuộc sống thực' → quét + đo cả thị
    trường Việt, trong khi công ty chỉ làm Mỹ."""
    kho = _kho(*(["Life in Alaska"] * 4), *(["Cuộc sống thực ở Mỹ"] * 9))
    en = [g["seed"] for g in mapping.goi_y_seed(kho, ngon_ngu="English")]
    assert "life in" in en
    assert not any(mapping.la_tieng_viet(s) for s in en)
    # thị trường Việt thì ngược lại
    vi = [g["seed"] for g in mapping.goi_y_seed(kho, ngon_ngu="Vietnamese")]
    assert any(mapping.la_tieng_viet(s) for s in vi)


def test_khong_khai_ngon_ngu_thi_khong_loc():
    kho = _kho(*(["Cuộc sống thực ở Mỹ"] * 5))
    assert mapping.goi_y_seed(kho, ngon_ngu=None), "không rõ ngôn ngữ thì nhận hết, không đoán"


def test_vung_ngon_ngu_khong_doan_khi_thieu_khai_bao():
    """Không khai được thị trường → trả rỗng, KHÔNG mặc định 'US'."""
    assert mapping.vung_ngon_ngu("", None) == {}
    assert mapping.vung_ngon_ngu("TT-KHONG-CO", "Tiếng gì đó") == {}
    assert mapping.vung_ngon_ngu("TT-US", "English") == {
        "hl": "en", "relevanceLanguage": "en", "gl": "us", "regionCode": "US"}


def test_vung_di_vao_loi_goi_autocomplete():
    """hl/gl phải có mặt trong URL — thiếu là autocomplete trả theo IP máy chủ (VN)."""
    thay = {}

    def doc(url):
        thay["url"] = url
        return json.dumps(["x", [], [], {}])
    discovery.goi_y_youtube("life in", doc, {"hl": "en", "gl": "us"})
    assert "hl=en" in thay["url"] and "gl=us" in thay["url"]
    discovery.goi_y_youtube("life in", doc, None)
    assert "hl=" not in thay["url"] and "gl=" not in thay["url"]


def test_vung_di_vao_loi_goi_search_youtube():
    goi = []

    class _Api:
        used = 0

        def get(self, ep, params, cost=1):
            goi.append((ep, params))
            return {}
    from radary import thi_truong
    thi_truong.do_mot_cum(_Api(), "life in alaska", vung={"regionCode": "US", "relevanceLanguage": "en"})
    ep, params = goi[0]
    assert ep == "search" and params["regionCode"] == "US" and params["relevanceLanguage"] == "en"


def test_chiu_duoc_ten_ngon_ngu_sai_trong_de():
    """Đế thật (đo 21/08) do người nhập nên có lỗi: TT-US khai ngôn ngữ 'US',
    TT-SPAIN khai 'Spainish'. Code phải chịu được, không rơi về 'không rõ'."""
    assert mapping.vung_ngon_ngu("TT-US", "US")["relevanceLanguage"] == "en"
    assert mapping.vung_ngon_ngu("TT-SPAIN", "Spainish")["relevanceLanguage"] == "es"
    assert mapping.hop_ngon_ngu("Cuộc sống thực ở Mỹ", "US") is False
    assert mapping.hop_ngon_ngu("Life in Alaska", "US") is True


# ============ TRA CỨU MỘT TỪ KHOÁ (bản 2, user chốt 21/08) ============


def _kho_lua(thang_video, bay_gio):
    """Dựng kho có video theo từng tháng đăng để kiểm xu hướng theo lứa."""
    kho, i = [], 0
    for thang_truoc, n in thang_video:
        for _ in range(n):
            i += 1
            pub = bay_gio - thang_truoc * 30 * 86400
            kho.append({"id": i, "title": "Life in Alaska ep", "title_l": "life in alaska ep",
                        "kenh": "K", "kenh_yt": "UC1", "yt_id": f"v{i}", "pub_ts": pub,
                        "vph": 5.0, "views": 1000 * thang_truoc})
    return kho


def test_xu_huong_theo_lua_dang():
    from radary import tra_cuu
    now = time.time()
    r = tra_cuu.xu_huong_pool(_kho_lua([(3, 4), (2, 6), (1, 9)], now), "life in alaska",
                              bay_gio=now)
    assert r["co_du_lieu"] and r["so_video"] == 19
    assert len(r["lua"]) == 3
    assert [l["so_video"] for l in r["lua"]] == [4, 6, 9]     # theo thứ tự tháng tăng dần


def test_lua_it_mau_thi_khong_lay_trung_vi():
    """Dưới 2 video/tháng thì không kết luận view/ngày — mẫu quá nhỏ."""
    from radary import tra_cuu
    now = time.time()
    r = tra_cuu.xu_huong_pool(_kho_lua([(2, 1)], now), "life in alaska", bay_gio=now)
    assert r["lua"][0]["du_mau"] is False and r["lua"][0]["view_moi_ngay"] is None


def test_video_qua_moi_khong_tinh_view_moi_ngay():
    """Video dưới 7 ngày tuổi chưa ổn định — không đưa vào trung vị."""
    from radary import tra_cuu
    now = time.time()
    assert tra_cuu._view_moi_ngay({"pub_ts": now - 3 * 86400, "views": 999}, now) is None
    assert tra_cuu._view_moi_ngay({"pub_ts": now - 30 * 86400, "views": 300}, now) == 10


def test_pool_khong_co_video_thi_noi_thang():
    from radary import tra_cuu
    r = tra_cuu.xu_huong_pool(_kho("chuyện khác"), "life in alaska")
    assert r["co_du_lieu"] is False and "chưa có video" in r["ly_do"]


def test_trends_loi_thi_khong_giet_ca_tra_cuu(monkeypatch):
    """Google Trends là thư viện non (1.6.0, phát hành 19/08) — hỏng thì mất Trends,
    không được mất luôn khối YouTube."""
    from radary import tra_cuu
    import builtins
    that = builtins.__import__

    def gia(name, *a, **k):
        if name == "trendspyg":
            raise ImportError("khong co")
        return that(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", gia)
    r = tra_cuu.google_trends("life in alaska")
    assert r["co_du_lieu"] is False and "trendspyg" in r["ly_do"]


def test_ngoai_youtube_gioi_han_90_ngay_va_theo_vung():
    from radary import tra_cuu
    goi = []

    class _Api:
        used = 0

        def get(self, ep, params, cost=1):
            goi.append((ep, params))
            return {}
    tra_cuu.ngoai_youtube(_Api(), "life in alaska", {"regionCode": "US", "relevanceLanguage": "en"})
    ep, p = goi[0]
    assert ep == "search" and p["order"] == "viewCount"
    assert "publishedAfter" in p and p["regionCode"] == "US"


def test_ngoai_youtube_khong_co_ket_qua_thi_noi_thang():
    from radary import tra_cuu

    class _Api:
        used = 0

        def get(self, ep, params, cost=1):
            return {"items": []}
    r = tra_cuu.ngoai_youtube(_Api(), "cụm không ai làm")
    assert r["co_du_lieu"] is False and "90 ngày" in r["ly_do"]


def test_loc_video_khac_ngon_ngu_va_shorts():
    """Ảnh user 21/08: pool US mà kết quả có video Indonesia + Shorts. YouTube CÓ trả
    defaultAudioLanguage nên lọc được chính xác, không phải đoán từ title."""
    from radary import tra_cuu

    class _Api:
        used = 0

        def get(self, ep, params, cost=1):
            if ep == "search":
                return {"items": [{"id": {"videoId": f"v{i}"}} for i in range(4)]}
            if ep == "videos":
                return {"items": [
                    {"id": "v0", "snippet": {"title": "Life in Alaska", "channelTitle": "A",
                                             "channelId": "UCa", "publishedAt": "2026-07-01T00:00:00Z",
                                             "defaultAudioLanguage": "en"},
                     "statistics": {"viewCount": "1000"}, "contentDetails": {"duration": "PT20M"}},
                    {"id": "v1", "snippet": {"title": "KISAH PENJARA", "channelTitle": "B",
                                             "channelId": "UCb", "publishedAt": "2026-07-01T00:00:00Z",
                                             "defaultAudioLanguage": "id"},
                     "statistics": {"viewCount": "9999999"}, "contentDetails": {"duration": "PT30M"}},
                    {"id": "v2", "snippet": {"title": "funny #shorts", "channelTitle": "C",
                                             "channelId": "UCc", "publishedAt": "2026-07-01T00:00:00Z",
                                             "defaultAudioLanguage": "en"},
                     "statistics": {"viewCount": "8888888"}, "contentDetails": {"duration": "PT45S"}},
                    {"id": "v3", "snippet": {"title": "Alaska cabin tour", "channelTitle": "D",
                                             "channelId": "UCd", "publishedAt": "2026-07-01T00:00:00Z"},
                     "statistics": {"viewCount": "500"}, "contentDetails": {"duration": "PT15M"}},
                ]}
            return {"items": []}
    r = tra_cuu.ngoai_youtube(_Api(), "life in alaska",
                              {"regionCode": "US", "relevanceLanguage": "en"})
    assert r["so_ket_qua"] == 2                       # giữ v0 và v3
    assert r["da_bo"] == {"khac_ngon_ngu": 1, "shorts": 1}
    assert {v["yt_id"] for v in r["top_video"]} == {"v0", "v3"}


def test_khong_khai_thi_truong_thi_khong_loc_ngon_ngu():
    """Pool chưa gắn thị trường → không có căn cứ loại, giữ hết (không loại oan)."""
    from radary import tra_cuu

    class _Api:
        used = 0

        def get(self, ep, params, cost=1):
            if ep == "search":
                return {"items": [{"id": {"videoId": "v1"}}]}
            if ep == "videos":
                return {"items": [{"id": "v1", "snippet": {
                    "title": "x", "channelTitle": "B", "channelId": "UCb",
                    "publishedAt": "2026-07-01T00:00:00Z", "defaultAudioLanguage": "id"},
                    "statistics": {"viewCount": "10"}, "contentDetails": {"duration": "PT20M"}}]}
            return {"items": []}
    r = tra_cuu.ngoai_youtube(_Api(), "x", None)
    assert r["so_ket_qua"] == 1 and r["da_bo"]["khac_ngon_ngu"] == 0


def test_trends_rate_limit_co_thong_diep_rieng(monkeypatch):
    """RateLimitError phải ra câu người đọc hiểu, không phải tên lớp lỗi trần."""
    from radary import tra_cuu
    import builtins
    that = builtins.__import__

    class RateLimitError(Exception):
        pass

    def gia(name, *a, **k):
        if name == "trendspyg":
            class M:
                @staticmethod
                def download_google_trends_explore(*x, **y):
                    raise RateLimitError("429")
            return M
        return that(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", gia)
    r = tra_cuu.google_trends("x")
    assert r["co_du_lieu"] is False and r.get("rate_limit") is True
    assert "chặn tạm" in r["ly_do"] and "nguồn khác vẫn chạy" in r["ly_do"]


def test_cache_trends_theo_ngay(conn):
    """Hỏi lại cùng từ khoá trong ngày phải đọc cache — Google chặn theo IP."""
    assert db.trends_doc(conn, "life in alaska", "US", ngay="2026-08-21") is None
    db.trends_ghi(conn, "Life In Alaska", "US", {"co_du_lieu": True, "diem": [1]}, ngay="2026-08-21")
    d = db.trends_doc(conn, "life in alaska", "US", ngay="2026-08-21")   # không phân biệt hoa thường
    assert d and d["co_du_lieu"] is True
    assert db.trends_doc(conn, "life in alaska", "US", ngay="2026-08-22") is None


# ---------------------------- LỊCH SỬ TRA CỨU (user 21/08) ----------------------


def test_luu_va_doc_lai_tra_cuu(conn):
    """User: 'sau mỗi lần tra từ khoá mới thì không quay lại xem từ khoá cũ được'."""
    db.tra_cuu_luu(conn, 1, "life in alaska", a={"so_video": 2}, b={"youtube": {"x": 1}})
    d = db.tra_cuu_doc(conn, 1, "life in alaska")
    assert d["a"]["so_video"] == 2 and d["b"]["youtube"]["x"] == 1 and d["ts"] > 0


def test_tra_lai_khoi_A_KHONG_xoa_ket_qua_ngoai(conn):
    """Khối B tốn 102 units nên tra lại khối A (0 quota) không được xoá nó."""
    db.tra_cuu_luu(conn, 1, "x", a={"v": 1}, b={"tot": True})
    db.tra_cuu_luu(conn, 1, "x", a={"v": 2})              # chỉ cập nhật A
    d = db.tra_cuu_doc(conn, 1, "x")
    assert d["a"]["v"] == 2 and d["b"]["tot"] is True


def test_danh_sach_moi_nhat_truoc_va_bao_co_ngoai_chua(conn):
    db.tra_cuu_luu(conn, 1, "cu", a={})
    time.sleep(0.01)
    db.tra_cuu_luu(conn, 1, "moi", a={}, b={"co": 1})
    ds = db.tra_cuu_danh_sach(conn, 1)
    assert [x["cum"] for x in ds] == ["moi", "cu"]
    assert ds[0]["co_ngoai"] is True and ds[1]["co_ngoai"] is False


def test_moi_cum_mot_dong_khong_de_trung(conn):
    for _ in range(3):
        db.tra_cuu_luu(conn, 1, "life in alaska", a={})
    assert conn.execute("SELECT COUNT(*) FROM tra_cuu_log").fetchone()[0] == 1


def test_lich_su_tach_theo_pool(conn):
    """Pool US và Spain không được thấy lịch sử của nhau."""
    conn.execute("INSERT INTO workspaces(id, org_id, name, created_ts) VALUES(2,1,'w2',0)")
    db.tra_cuu_luu(conn, 1, "life in", a={})
    db.tra_cuu_luu(conn, 2, "la vida en", a={})
    assert [x["cum"] for x in db.tra_cuu_danh_sach(conn, 1)] == ["life in"]
    assert [x["cum"] for x in db.tra_cuu_danh_sach(conn, 2)] == ["la vida en"]


def test_cum_rong_khong_ghi(conn):
    db.tra_cuu_luu(conn, 1, "   ", a={})
    assert conn.execute("SELECT COUNT(*) FROM tra_cuu_log").fetchone()[0] == 0


def test_trends_bat_cookie_disk():
    """Ghim: cookies='disk' phải được truyền — đây là thứ giảm rate limit về sau."""
    from pathlib import Path
    src = Path(__file__).resolve().parents[1].joinpath("radary", "tra_cuu.py").read_text(encoding="utf-8")
    assert 'cookies="disk"' in src
    assert "TRENDSPYG_COOKIES" in src


def test_chi_so_LUONG_la_view_that_khong_phai_totalResults():
    """User 21/08: 'chưa đưa ra được quantity của từ khoá'. Không ai có search volume
    của YouTube — pageInfo.totalResults đo thật trả 1.000.000 cho MỌI truy vấn (số
    giả). Số thật duy nhất là VIEW thị trường đang trả."""
    from radary import tra_cuu

    class _Api:
        used = 0

        def get(self, ep, params, cost=1):
            if ep == "search":
                return {"pageInfo": {"totalResults": 1000000},
                        "items": [{"id": {"videoId": f"v{i}"}} for i in range(2)]}
            if ep == "videos":
                return {"items": [
                    {"id": f"v{i}", "snippet": {"title": "t", "channelTitle": "K",
                                                "channelId": "UC", "publishedAt": "2026-07-01T00:00:00Z",
                                                "defaultAudioLanguage": "en"},
                     "statistics": {"viewCount": str(v)}, "contentDetails": {"duration": "PT20M"}}
                    for i, v in enumerate([300000, 100000])]}
            return {"items": []}
    r = tra_cuu.ngoai_youtube(_Api(), "life in alaska", {"relevanceLanguage": "en"})
    assert r["tong_view_90n"] == 400000
    assert r["view_moi_thang"] == round(400000 / 3)
    assert "totalResults" not in json.dumps(r)      # tuyệt đối không dùng số giả đó


def test_route_lich_su_doc_lap_va_hash_giu_tu_khoa():
    """User 21/08: 'kết quả mất sau mỗi lần F5'. Hai điều kiện để F5 không mất:
    (1) có route lịch sử ĐỘC LẬP để tải ngay khi mở tab (trước đó lịch sử chỉ về kèm
        kết quả tra cứu nên F5 xong là trắng);
    (2) từ khoá đang xem nằm trong URL hash, và chỉ tự mở lại khi ĐÚNG pool."""
    from pathlib import Path
    goc = Path(__file__).resolve().parents[1]
    api_src = goc.joinpath("radary", "api.py").read_text(encoding="utf-8")
    js = goc.joinpath("web", "app.js").read_text(encoding="utf-8")
    assert "'/api/workspaces/{ws}/tra-cuu/lich-su'" in api_src
    assert "/tra-cuu/lich-su`).then(r => setLichSu" in js
    assert "writeHash({ q })" in js
    # Ghim Ý NGHĨA, không ghim mặt chữ: phải SO pool của từ khoá với pool đang mở
    # trước khi tự mở lại, và đổi pool thì bỏ từ khoá cũ. (Bản đầu ghim nguyên câu
    # lệnh nên vỡ ngay khi đổi cách viết — cùng lớp lỗi self-test ghim hằng số.)
    assert "wsCuaQ" in js and "=== String(ws)" in js
    assert "writeHash({ q: '' })" in js


# ------------------- TỪ KHOÁ ĐANG NỔI trong pool (user 21/08) -------------------


def _kho_theo_ngay(cap, bay_gio):
    """cap = [(cụm, số ngày trước, số video)] -> kho giả."""
    kho, i = [], 0
    for cum, ngay_truoc, n in cap:
        for _ in range(n):
            i += 1
            kho.append({"id": i, "title": f"{cum} something", "title_l": f"{cum} something",
                        "kenh": "K", "kenh_yt": "UC1", "yt_id": f"v{i}",
                        "pub_ts": bay_gio - ngay_truoc * 86400, "vph": 1.0, "views": 10000})
    return kho


def test_bat_cum_dang_len():
    """Đo thật pool US: 'living in' 19 -> 79 video = +316%."""
    from radary import tra_cuu
    now = time.time()
    kho = _kho_theo_ngay([("living in", 45, 19), ("living in", 10, 79)], now)
    r = tra_cuu.xu_huong_cum(kho, ["living in"], bay_gio=now)[0]
    assert r["video_30n_truoc"] == 19 and r["video_30n"] == 79
    assert r["phan_tram"] == 316 and r["chieu"] == "lên"


def test_bat_cum_dang_chet_du_ky_nay_bang_khong():
    """Ca thật '15 mind' 6 -> 0. Ban đầu đòi CẢ HAI kỳ đủ mẫu nên mất đúng tín hiệu
    giảm mạnh nhất — nay chỉ cần kỳ TRƯỚC đủ mẫu (nó là mẫu số)."""
    from radary import tra_cuu
    now = time.time()
    r = tra_cuu.xu_huong_cum(_kho_theo_ngay([("15 mind", 45, 6)], now), ["15 mind"], bay_gio=now)[0]
    assert r["phan_tram"] == -100 and r["chieu"] == "xuống"


def test_ky_truoc_qua_it_thi_noi_thang_khong_doan():
    from radary import tra_cuu
    now = time.time()
    r = tra_cuu.xu_huong_cum(_kho_theo_ngay([("x y", 45, 1), ("x y", 5, 9)], now), ["x y"], bay_gio=now)[0]
    assert r["phan_tram"] is None and r["chieu"] is None and r["du_mau"] is False


def test_xep_cum_dang_len_truoc_it_mau_xuong_cuoi():
    from radary import tra_cuu
    now = time.time()
    kho = _kho_theo_ngay([("len nhanh", 45, 5), ("len nhanh", 5, 40),
                          ("giam", 45, 10), ("giam", 5, 3),
                          ("it mau", 45, 1), ("it mau", 5, 1)], now)
    ra = tra_cuu.xu_huong_cum(kho, ["len nhanh", "giam", "it mau"], bay_gio=now)
    assert [r["cum"] for r in ra] == ["len nhanh", "giam", "it mau"]


def test_co_chuoi_mat_do_theo_thang_de_ve_sparkline():
    from radary import tra_cuu
    now = time.time()
    kho = _kho_theo_ngay([("a b", 200, 4), ("a b", 100, 6), ("a b", 10, 8)], now)
    r = tra_cuu.xu_huong_cum(kho, ["a b"], bay_gio=now)[0]
    assert len(r["chuoi"]) >= 3 and all("ngay" in p and "gia_tri" in p for p in r["chuoi"])


def test_quet_ngram_MOI_VI_TRI_ra_nhieu_cum_hon_han():
    """User 21/08: 'từ khoá trong pool có rất nhiều, tại sao chỉ có mỗi vài cụm'.
    Gốc: goi_y_seed chỉ lấy n-gram MỞ ĐẦU title nên bỏ sót chủ đề nằm giữa câu."""
    kho = _kho(*(["Real Life in Vietnam Travel Documentary"] * 5),
               *(["Amazing Facts About Beautiful Women"] * 5))
    dau = {g["seed"] for g in mapping.goi_y_seed(kho, 50, toi_thieu_video=3)}
    moi = {g["seed"] for g in mapping.goi_y_seed(kho, 50, toi_thieu_video=3, moi_vi_tri=True)}
    assert "travel documentary" not in dau      # nằm cuối title -> chế độ cũ bỏ sót
    assert "travel documentary" in moi
    assert len(moi) > len(dau)


def test_bo_ngram_toan_tu_chuc_nang_va_ngram_mo_dau_bang_tu_chuc_nang():
    kho = _kho(*(["The Most Beautiful Land of Fire"] * 5))
    ra = {g["seed"] for g in mapping.goi_y_seed(kho, 50, toi_thieu_video=3, moi_vi_tri=True)}
    assert not any(c.split()[0] in mapping._TU_TRO for c in ra), "n-gram mở đầu bằng từ chức năng phải bị bỏ"
    assert "land of" in ra, "n-gram KẾT THÚC bằng từ chức năng vẫn giữ (mẫu mở đầu chủ đề)"


def test_moi_video_dem_mot_lan_cho_mot_cum():
    """Title lặp cụm 2 lần không được tính thành 2 video."""
    kho = _kho("life in alaska and life in norway")
    ra = {g["seed"]: g["so_video"] for g in mapping.goi_y_seed(kho, 50, toi_thieu_video=1, moi_vi_tri=True)}
    assert ra.get("life in") == 1


def test_nho_tab_qua_localStorage_vi_iframe_mat_hash():
    """User 21/08: 'đang ở mapping nhưng ấn F5 luôn bị trả về board'.
    Gốc: RadarY chạy TRONG IFRAME khi vào qua cổng 9000 — history.replaceState chỉ đổi
    URL của iframe, F5 trang cha thì iframe tải lại src gốc và mất sạch hash."""
    from pathlib import Path
    js = Path(__file__).resolve().parents[1].joinpath("web", "app.js").read_text(encoding="utf-8")
    assert "localStorage.setItem(NHO_KEY" in js and "nhoGhi(patch)" in js
    # khởi tạo phải đọc hash TRƯỚC rồi mới tới localStorage (link chia sẻ vẫn thắng)
    assert "h0.tab || nho0.tab || 'board'" in js
    assert "h0.ws ? Number(h0.ws) : (nho0.ws ? Number(nho0.ws) : null)" in js
    assert "h0.q || nho.q || ''" in js


def test_khong_tong_hop_so_giua_cac_PHIEN():
    """User 21/08: bảng 'so lượng giữa các từ khoá đã tra' KHÔNG có giá trị — mỗi từ
    khoá là MỘT PHIÊN, đo ở thời điểm khác nhau (cửa sổ 90 ngày trượt theo ngày đo) và
    phạm vi khác nhau (địa danh vs mẫu câu). Lịch sử chỉ để XEM LẠI từng phiên."""
    from pathlib import Path
    goc = Path(__file__).resolve().parents[1]
    api_src = goc.joinpath("radary", "api.py").read_text(encoding="utf-8")
    js = goc.joinpath("web", "app.js").read_text(encoding="utf-8")
    assert "@app.get('/api/workspaces/{ws}/tra-cuu/so-sanh')" not in api_src
    assert "soSanh" not in js
    assert "mỗi từ khoá là một phiên" in js.lower() or "mỗi từ khoá là một phiên" in js
    assert "/tra-cuu/lich-su" in api_src, "lịch sử vẫn phải còn để xem lại"


def test_bing_la_nguon_goi_y_thu_hai():
    """Bing (DuckDuckGo dùng chung hạ tầng) trả cụm mà YouTube autocomplete không có —
    đo thật 'life in alaska': 'during winter', 'anchorage alaska', 'alaska today'."""
    def doc(url):
        assert "bing.com" in url and "mkt=en-US" in url
        return json.dumps(["life in alaska", ["life in alaska during winter",
                                              "life in anchorage alaska"], [], {}])
    r = discovery.goi_y_bing("life in alaska", doc, {"hl": "en", "gl": "us"})
    assert r == ["life in alaska during winter", "life in anchorage alaska"]


def test_bing_loi_mang_khong_giet_phien():
    def doc_no(url):
        raise OSError("chet")
    assert discovery.goi_y_bing("x", doc_no) == []
