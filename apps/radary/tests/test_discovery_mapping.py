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
    assert "writeHash({ q, qws: String(ws) })" in js   # kèm pool sinh ra từ khoá
    # Ghim Ý NGHĨA, không ghim mặt chữ: phải SO pool của từ khoá với pool đang mở
    # trước khi tự mở lại, và đổi pool thì bỏ từ khoá cũ. (Bản đầu ghim nguyên câu
    # lệnh nên vỡ ngay khi đổi cách viết — cùng lớp lỗi self-test ghim hằng số.)
    assert "wsCuaQ" in js and "=== String(ws)" in js
    assert "writeHash({ q: '', qws: '' })" in js


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


def test_du_mau_doi_xung_hai_chieu():
    """22/08 (thay test 'ky truoc it thi cam' cu): mot BEN >= 3 la du noi.

    Cum MOI NOI 1 -> 9 la tin hieu len that (cua so 7 ngay ma doi ky truoc du mau
    thi moi thu moi deu "it mau" — user: bong bong 7 ngay trong). Cum CHET 6 -> 0
    van bao giam (bai hoc 21/08). Ca hai ky deu < 3 thi van noi thang khong doan.
    """
    from radary import tra_cuu
    now = time.time()
    r = tra_cuu.xu_huong_cum(_kho_theo_ngay([("x y", 45, 1), ("x y", 5, 9)], now), ["x y"], bay_gio=now)[0]
    assert r["chieu"] == "lên" and r["phan_tram"] == 800 and r["du_mau"]
    r2 = tra_cuu.xu_huong_cum(_kho_theo_ngay([("c d", 45, 6)], now), ["c d"], bay_gio=now)[0]
    assert r2["chieu"] == "xuống" and r2["phan_tram"] == -100
    r3 = tra_cuu.xu_huong_cum(_kho_theo_ngay([("e f", 45, 2), ("e f", 5, 2)], now), ["e f"], bay_gio=now)[0]
    assert r3["phan_tram"] is None and r3["du_mau"] is False


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
    # lich su la DROPDOWN (duyet mockup v2) — triet ly "moi phien rieng" giu o title
    assert "Mỗi từ khoá là một phiên riêng" in js
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


# ------------- NHỊP POOL: bucket chưa chốt (user 22/08) -------------------------


def test_bucket_dang_chay_va_chua_chot_duoc_danh_dau():
    """User 22/08: 'pool theo ngày tăng nhưng theo giờ luôn giảm'. HAI nguyên nhân,
    cả hai đều làm đường tụt giả:
      dang_chay — bucket hiện tại mới qua một phần thời gian
      chua_chot — video cũ chỉ quét 1 lần/24h nên phần views của chúng chỉ được phân
                  bổ vào một bucket SAU khi có lần quét kế tiếp; mọi bucket trong 24h
                  gần nhất còn thiếu và sẽ tự đầy lên.
    Đo thật ws20: bucket đã chốt 118-135k, bucket 22/08 00:00 mới 53.831."""
    from pathlib import Path
    goc = Path(__file__).resolve().parents[1]
    api_src = goc.joinpath("radary", "api.py").read_text(encoding="utf-8")
    js = goc.joinpath("web", "app.js").read_text(encoding="utf-8")
    assert "'chua_chot': het > moc_chot" in api_src
    # mốc chốt phải lấy từ LỊCH JOB thật (allages), không đoán "24h qua": ngưỡng cứng
    # loại nhầm cả bucket đã đầy (đo thật: 21/08 18h = 122.852 đã được điền bù)
    assert "due_all = (db.get_jobs(c, ws) or {}).get('allages')" in api_src
    assert "moc_chot = (due_all - cad)" in api_src
    # UI phải LOẠI các điểm chưa chốt khỏi đường, không chỉ điểm cuối
    assert "ptsVe = soChuaChot ? pts.slice(0, pts.length - soChuaChot) : pts" in js
    assert "chưa chốt — không vẽ lên đường" in js


def test_tu_khoa_khong_ro_ri_sang_pool_khac(tmp_path):
    """Từ khoá tra ở pool nào phải NẰM YÊN ở pool đó.

    Bug 22/08: đổi pool thì `ws` trong hash bị ghi thành pool MỚI trong khi `q` của
    pool cũ còn nguyên, nên phép kiểm "từ khoá này có thuộc pool đang mở không" luôn
    đúng -> tự tra lại -> ghi thẳng vào lịch sử pool mới (UZBEKISTAN ws1 10:05 ->
    ws20 10:06; áfrica ws18 10:35 -> ws20 10:43). Chặn hai tầng.
    """
    from pathlib import Path as _P
    goc = _P(__file__).resolve().parents[1]
    api_src = (goc / 'radary' / 'api.py').read_text(encoding='utf-8')
    js = (goc / 'web' / 'app.js').read_text(encoding='utf-8')

    # Tầng SERVER: "xem lại" mà chưa có bản lưu thì KHÔNG được tính mới rồi lưu.
    than = api_src.split("def tra_cuu_pool(")[1].split("def _ghi_bo_qua_khoa")[0]
    # tach dung nhanh xem_lai (22/08 them buoc va khoi A tuoi truoc do — bo qua no)
    nhanh = than.split("if xem_lai:")[1].split("a = tra_cuu.xu_huong_pool")[0]
    assert "if not cu:" in nhanh and "'khong_co_ban_luu': True" in nhanh
    assert "db.tra_cuu_luu" not in nhanh          # nhánh xem lại tuyệt đối không ghi

    # Tầng UI: so với pool SINH RA từ khoá (qws), không phải pool đang mở (ws).
    assert "const wsCuaQ = String(h0.qws || nho.qws || '')" in js
    assert "if (a.khong_co_ban_luu)" in js


def test_ba_khoi_thanh_ngang_dung_chung_mot_luoi():
    """Cột nhãn / thanh / số của ba khối thanh ngang phải thẳng hàng.

    Trước đây mỗi khối tự khai flex: Trends dùng 44% + 82px, "Biến thể người ta gõ"
    dùng 46% + 92px -> nhìn là thấy lệch (user báo 22/08). Nay cả ba đi qua HangThanh
    nên chỉ còn MỘT nơi khai bề rộng cột.
    """
    from pathlib import Path as _P
    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')
    assert "const COT_NHAN = '46%', COT_SO = '92px'" in js
    # Không khối nào được tự khai lại bề rộng cột nhãn/số của hàng thanh
    for cu in ('flex:0 0 44%', 'flex:0 0 46%', 'flex:0 0 82px', 'flex:0 0 92px'):
        assert cu not in js, f'còn khai lưới riêng: {cu}'
    assert js.count('<${HangThanh}') >= 2      # Trends + biến thể cùng dùng


def test_the_kenh_kem_video_cua_kenh_do():
    """Kênh đẩy mạnh chủ đề phải kèm LUÔN video của chính kênh đó nói về từ khoá.

    User 22/08: "hiện luôn video nói về từ khóa trong kênh đó, cần UI dễ nhìn thay vì
    liệt kê". Video đã nằm sẵn trong dữ liệu pool nên đính vào là 0 quota.
    """
    import time
    from pathlib import Path as _P
    from radary import tra_cuu

    now = time.time()
    kho = [{'yt_id': f'v{i}', 'title': f'Life in Tajikistan {i}',
            'title_l': f'life in tajikistan {i}',
            'kenh': 'A' if i % 2 else 'B', 'kenh_yt': 'UCA' if i % 2 else 'UCB',
            'views': 1000 * (i + 1), 'pub_ts': now - 86400 * 10 * (i + 1), 'vph': 1.0}
           for i in range(6)]
    r = tra_cuu.xu_huong_pool(kho, 'tajikistan', bay_gio=now)
    for k in r['top_kenh']:
        assert k['video'], 'kênh nào cũng phải kèm video'
        assert len(k['video']) <= tra_cuu.SO_VIDEO_MOI_KENH
        views = [v['views'] for v in k['video']]
        assert views == sorted(views, reverse=True)          # video khoẻ nhất trước
        assert k['view_tb'] == round(k['views'] / k['so_video'])
        assert set(k['video'][0]) >= {'yt_id', 'title', 'views', 'pub_ts'}

    # UI: thẻ, không phải liệt kê phẳng; và chịu được bản lưu CŨ chưa có trường video
    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')
    assert 'function TheKenh(' in js and '<${TheKenh}' in js
    assert 'Bản lưu cũ chưa kèm video' in js


def _kho_nong(now):
    """Kho tổng hợp: 1 cụm nóng thật, 1 cụm phổ biến mà nguội, họ cụm trùng."""
    kho = []
    # 40 video nền nguội: view/ngày ~ 10 (tuổi 10 ngày, 100 view)
    for i in range(40):
        kho.append({'yt_id': f'nen{i}', 'title': f'Life in Nowhere part {i}',
                    'title_l': f'life in nowhere part {i}',
                    'kenh': 'K', 'kenh_yt': 'UCK', 'views': 100, 'vph': 0,
                    'pub_ts': now - 86400 * 10})
    # cụm NÓNG "hidden villages": 4 video mới, 3 video nổ (view/ngày rất cao)
    for i, v in enumerate((90000, 80000, 70000, 120)):
        kho.append({'yt_id': f'hot{i}', 'title': f'Hidden Villages of Georgia {i}',
                    'title_l': f'hidden villages of georgia {i}',
                    'kenh': 'K2', 'kenh_yt': 'UCK2', 'views': v, 'vph': 0,
                    'pub_ts': now - 86400 * 9})
    return kho


def test_tu_khoa_nong_do_bang_hieu_suat_khong_phai_tan_suat():
    """Cụm 4 video nổ phải THẮNG cụm 40 video nguội — đúng bệnh user chỉ ra 22/08:

    chọn ứng viên theo tần suất tích luỹ thì 'life in nowhere' (40 video) đè chết
    'hidden villages' (4 video, 3 nổ, max 90k view/ngày); đo thật ws20 sót 98% cụm
    lift cao, có cụm max 1,53 triệu view.
    """
    import time
    from radary import mapping

    now = time.time()
    r = mapping.tu_khoa_nong(_kho_nong(now), bay_gio=now)
    assert r['co_du_lieu']
    cums = [m['cum'] for m in r['cum']]
    # dai dien cua ho co the la bat ky n-gram nao cua title nong — ghim theo TU,
    # khong ghim mat chu ca cum
    assert any(('villages' in c) or ('georgia' in c) for c in cums), cums
    # cụm nguội 40 video KHÔNG được vào danh sách nóng (tỉ lệ nổ ~0)
    assert not any('nowhere' in c for c in cums), cums
    top = r['cum'][0]
    assert top['so_no'] >= mapping.TOI_THIEU_NO and top['ti_le_no'] >= 2 * r['nen']
    assert top['vi_du']['views'] == 90000          # ví dụ = video nổ to nhất, để bấm xem


def test_tu_khoa_nong_gop_ho_cum_va_van_chong_bia():
    import time
    from radary import mapping

    now = time.time()
    r = mapping.tu_khoa_nong(_kho_nong(now), bay_gio=now)
    # GỘP HỌ: 'hidden villages' đẻ nhiều n-gram con ('hidden', 'villages of georgia'…)
    # cùng (so_moi, so_no, video ví dụ) — chỉ được giữ MỘT dòng đại diện
    ho = [m for m in r['cum'] if 'hidden' in m['cum'] or 'villages' in m['cum']
          or 'georgia' in m['cum']]
    assert len(ho) == 1, [m['cum'] for m in ho]
    # VAN CHỐNG BỊA: phiên < 30 video mới → nói thẳng, không kết luận
    it = mapping.tu_khoa_nong(_kho_nong(now)[:10], bay_gio=now)
    assert not it['co_du_lieu'] and 'chưa đủ mẫu' in it['ly_do']


def test_route_tu_khoa_nong_va_tab_ui():
    """Route + ngân sách soi ngoài + tab Đang nóng — ghim theo ý nghĩa."""
    from pathlib import Path as _P

    goc = _P(__file__).resolve().parents[1]
    api_src = (goc / 'radary' / 'api.py').read_text(encoding='utf-8')
    js = (goc / 'web' / 'app.js').read_text(encoding='utf-8')

    than = api_src.split("def tu_khoa_nong_api(")[1].split("\ndef tu_khoa_noi(")[0]
    # danh sách ai xem cũng được, nhưng TIÊU QUOTA (soi nền) phải leader+
    assert "duoc_soi = auth.ROLE_RANK.get(w['member_role'], -1) >= auth.ROLE_RANK['leader']" in than
    # ngân sách: chỉ soi cụm CHƯA có bản lưu, trần theo ngày, chạy NỀN sau response
    assert "NGAN_SACH_NONG - da_soi_hom_nay" in than
    assert "nhiem_vu_nen.add_task(_soi_nen_nong" in than
    # probe nền tắt trends (trình duyệt ~17s/cụm) và nuốt lỗi từng cụm
    assert "trends=False" in api_src.split("def _soi_nen_nong(")[1].split("\n@app")[0]

    # Hot Topic nam trong OVERVIEW (duyet mockup v2), tai NGAY khi mo tab —
    # khong con chip "Dang nong" trong Keyword
    assert ">Hot Topic" in js and "tu-khoa-nong" in js and "đang soi…" in js
    assert "Đang nóng" not in js
    # cot cuoi bang Hot Topic ten External, khop ten khoi C
    assert "<th>External</th>" in js


def test_bong_bong_tach_mau_theo_loai():
    """Bong bóng TĂNG tách màu theo loại (user 22/08): đối tượng xanh, mẫu câu tím —
    mở tab Tất cả là nhìn ra cặp kết hợp cùng đang lên. Giảm giữ một màu đỏ."""
    from pathlib import Path as _P
    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')
    than = js.split('function BanDoCum(')[1].split('\nfunction ')[0]
    assert "r.loai === 'mau_cau' ? '#7e57c2' : '#2e7d32'" in than
    assert "xuong ? '#c62828'" in than               # giảm không tách loại
    assert 'CẶP KẾT HỢP' in than                     # chú giải nói rõ cách dùng


def test_ban_do_cua_so_do_7_28_90_toan_thoi_gian():
    """22/08 — user chốt bộ mẫu cửa sổ 7/28/90/toàn thời gian (thay thanh trượt):

    xu hướng + cạnh tranh cùng đo trong cửa sổ; toàn thời gian = cạnh tranh trọn đời
    (xu hướng giữ 30 ngày); lifetime không còn pha loãng cửa sổ ngắn.
    """
    import time
    from pathlib import Path as _P
    from radary import tra_cuu

    now = time.time()
    kho = []
    for i in range(5):      # 5 video cũ 3 năm — chỉ được tính ở "toàn thời gian"
        kho.append({'yt_id': f'cu{i}', 'title': f'Life in Georgia old {i}',
                    'title_l': f'life in georgia old {i}', 'kenh': 'K', 'kenh_yt': 'U',
                    'views': 100, 'vph': 0, 'pub_ts': now - 86400 * 1100})
    for i in range(4):      # 4 video 20 ngày tuổi
        kho.append({'yt_id': f'moi{i}', 'title': f'Life in Georgia new {i}',
                    'title_l': f'life in georgia new {i}', 'kenh': 'K', 'kenh_yt': 'U',
                    'views': 100, 'vph': 0, 'pub_ts': now - 86400 * 20})

    r7 = tra_cuu.xu_huong_cum(kho, ['georgia'], bay_gio=now, cua_so=7)[0]
    r28 = tra_cuu.xu_huong_cum(kho, ['georgia'], bay_gio=now, cua_so=28)[0]
    r0 = tra_cuu.xu_huong_cum(kho, ['georgia'], bay_gio=now, cua_so=0)[0]
    assert r7['video_cua_so'] == 0          # video 20 ngày tuổi ngoài cửa sổ 7 ngày
    assert r28['video_cua_so'] == 4         # lọt cửa sổ 28 — 5 video cũ KHÔNG pha loãng
    assert r0['video_cua_so'] == 9          # toàn thời gian = trọn đời
    assert r0['tong_video'] == 9

    api_src = (_P(__file__).resolve().parents[1] / 'radary' / 'api.py').read_text(encoding='utf-8')
    than = api_src.split('def tu_khoa_noi(')[1].split('def _ghi_bo_qua_khoa')[0]
    assert 'cua_so' in than and 'tra_cuu.CUA_SO_HOP_LE' in than
    # MAC DINH 7 ngay (user chot 22/08) — ca server lan client phai khop
    assert 'cua_so: int = 7' in than and 'cua_so = 7' in than
    assert 'lui_thang' not in than          # máy thời gian đã gỡ theo lệnh user

    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')
    assert '<option value="7">7 ngày</option>' in js
    assert '<option value="0">Toàn thời gian</option>' in js
    assert 'cua_so=${cs}' in js and 'type="range"' not in js
    assert 'useState(7);       // cửa sổ đo mặc định 7 ngày' in js
    assert 'r.video_cua_so ?? r.tong_video' in js    # trục đọc cửa sổ


def test_ban_do_khong_bien_mat_trong_im_lang():
    """22/08 — pool SPACE mở tab Đối tượng không thấy bong bóng, user tưởng "pool
    nhiều video quá nên không quét được". Sự thật: quét tốt (48 cụm), nhưng bộ dò
    đối-tượng (từ sau giới từ — khuôn của ngách Life-in-X) chỉ bắt được 4 cụm đủ mẫu
    ở ngách SPACE (title kiểu "Mars Is Hiding..." — đối tượng làm chủ ngữ). Biểu đồ
    dưới 2 cụm phải NÓI LÝ DO, không return null lặng lẽ."""
    from pathlib import Path as _P
    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')
    than = js.split('function BanDoCum(')[1].split('\nfunction ')[0]
    assert 'return null' not in than.split('d.length < 2')[1].split('const w')[0]
    assert 'Không đủ cụm để vẽ bản đồ' in than
    assert 'Không phải pool chưa quét' in than


def test_ung_vien_trich_tu_vung_do_theo_cua_so():
    """22/08 — user: "không có lý do gì mà không tổng hợp được từ khoá của hàng
    nghìn video". Ứng viên phải trích từ VÙNG ĐANG ĐO (kỳ này + kỳ trước), không
    phải top tần suất toàn lịch sử — cụm mới nhú tuần này phải hiện ở cửa sổ 7."""
    from pathlib import Path as _P
    api_src = (_P(__file__).resolve().parents[1] / 'radary' / 'api.py').read_text(encoding='utf-8')
    than = api_src.split('def tu_khoa_noi(')[1].split('def _ghi_bo_qua_khoa')[0]
    assert 'kho_uv = kho if cua_so == 0 else' in than
    assert '2 * cua_so * 86400' in than              # vùng đo = kỳ này + kỳ trước
    assert 'goi_y_seed(kho_uv' in than and 'doi_tuong(kho_uv' in than
    assert 'xu_huong_cum(kho, cums' in than          # ĐO vẫn trên trọn kho (tổng trọn đời)


def test_phan_loai_tu_loai_danh_tu_la_doi_tuong():
    """22/08 — user chốt luật đơn giản: DANH TỪ = đối tượng, còn lại = mẫu câu.

    Hai tầng: ngoài từ điển EN = tên riêng = đối tượng (cứu tajikistan bị tagger
    đoán JJ vì đuôi -an); trong từ điển → phiếu POS trên CHỮ THƯỜNG (trung hoà
    ALL-CAPS). Ca gốc user chỉ ra: 'replace' (sau "to" nguyên mẫu) hết là đối tượng.
    """
    import pytest
    from radary import mapping

    if not mapping._nap_nltk():
        pytest.skip('máy này thiếu nltk/data — nhánh fallback giới-từ đã có test riêng')

    kho = mapping.tai_kho.__wrapped__ if False else None      # không cần DB — kho tay
    kho = ([{'title': 'Scientists Want To Replace The ISS', 'title_l': 'scientists want to replace the iss'}] * 4
           + [{'title': 'LIFE IN TAJIKISTAN! EXTREMELY BEAUTIFUL WOMEN', 'title_l': 'life in tajikistan! extremely beautiful women'}] * 4
           + [{'title': 'Journey Of The Universe In Deep Space', 'title_l': 'journey of the universe in deep space'}] * 4)
    phieu = mapping.bang_pos(kho, 'en')
    assert phieu is not None
    assert not mapping.la_doi_tuong('replace', phieu)      # động từ — ca user báo
    assert not mapping.la_doi_tuong('extremely', phieu)    # trạng từ, dù title ALL-CAPS
    assert not mapping.la_doi_tuong('beautiful', phieu)    # tính từ
    assert not mapping.la_doi_tuong('deep', phieu)
    assert mapping.la_doi_tuong('tajikistan', phieu)       # tên riêng ngoài từ điển
    assert mapping.la_doi_tuong('universe', phieu)         # danh từ thường
    assert mapping.loai_cum('deep space', phieu) == 'doi_tuong'    # cụm danh từ
    assert mapping.loai_cum('want to', phieu) == 'mau_cau'

    # doi_tuong() nhánh EN dùng luật mới: replace không bao giờ lọt nữa
    for v in kho:
        v.setdefault('kenh', 'K'); v.setdefault('kenh_yt', 'U')
        v.setdefault('yt_id', 'x'); v.setdefault('pub_ts', 0)
        v.setdefault('views', 0); v.setdefault('vph', 0)
    dt = {d['cum'] for d in mapping.doi_tuong(kho, so_muc=30, ngon_ngu='en')}
    assert 'replace' not in dt and 'tajikistan' in dt

    # ngôn ngữ khác → None → nơi gọi về luật sau-giới-từ cũ (van an toàn)
    assert mapping.bang_pos(kho, 'es') is None
    # tên ĐẦY ĐỦ từ đế phải hiểu như mã — 'English' từng làm cả hệ lặng lẽ về luật cũ
    assert mapping.bang_pos(kho, 'English') is not None
    assert mapping.bang_pos(kho, 'Spanish') is None


def test_serp_hai_loi_goi_va_canh_bao_quota():
    """22/08 — Owner chốt SERP: 2 lời gọi/cụm, có cảnh báo quota.

    Ràng buộc là quota free (~100/tháng) nên MỘT lời gọi google phải vắt ba khối
    (câu hỏi thật / liên quan / web). Hết quota khóa này thì xoay khóa kế; hết
    sạch thì NÓI THẲNG, không trả khối rỗng như thể không có dữ liệu.
    """
    from pathlib import Path as _P
    from radary import serp

    goc = _P(__file__).resolve().parents[1]

    # xoay khóa: khóa 1 hết → tự sang khóa 2, đếm đúng số lượt đã tiêu
    goi = []
    def gia(nha, khoa, *a, **kw):
        goi.append(khoa)
        if khoa == 'k1':
            raise serp.HetQuota('HTTP 429')
        return {'co_du_lieu': True}
    bo = serp.BoKhoa([{'id': 'api-1', 'key': 'k1', 'nha': 'serpapi'},
                      {'id': 'api-2', 'key': 'k2', 'nha': 'serper'}])
    assert bo.chay(gia, 'cum thu')['co_du_lieu']
    assert goi == ['k1', 'k2'] and bo.het == ['api-1'] and bo.da_tieu == 1

    # hết sạch khóa → ném lỗi có chữ, KHÔNG trả rỗng im lặng
    bo2 = serp.BoKhoa([{'id': 'api-1', 'key': 'k1', 'nha': 'serpapi'}])
    try:
        bo2.chay(gia, 'cum thu')
        raise AssertionError('phải ném khi hết mọi khóa')
    except RuntimeError as e:
        assert 'hết hạn mức' in str(e) and 'api-1' in str(e)

    # không có khóa nào → con_khoa False (nơi gọi bỏ qua êm, không giết trang)
    assert not serp.BoKhoa([]).con_khoa()

    # MỘT lời gọi google trả ba khối
    src = (goc / 'radary' / 'serp.py').read_text(encoding='utf-8')
    than = src.split('def google(')[1].split('# ---- XOAY VONG')[0]
    for khoi in ('cau_hoi', 'lien_quan', 'web'):
        assert khoi in than, khoi

    # UI: cảnh báo thiếu khóa + hết hạn mức, và card câu hỏi thật
    js = (goc / 'web' / 'app.js').read_text(encoding='utf-8')
    assert 'Chưa cấp khóa SERP' in js and 'Hạn mức SERP' in js
    assert 'Câu hỏi thật người ta hỏi' in js
    assert 'Vùng quan tâm nhất' in js


def test_reddit_qua_apify_chi_chay_khi_bam():
    """22/08 — Owner: "tôi muốn Reddit đủ nghĩa vì Apify cũng có free user".

    Reddit chặn IP máy chủ nên đi qua Apify (scraper thuê). Vì TỐN TIỀN nên
    KHÔNG gọi tự động mỗi lần tra cứu — phải là nút bấm, đúng khuôn "Hỏi lại
    (102 units)" của khối B; và chỉ leader+ được bấm.
    """
    from pathlib import Path as _P
    from radary import reddit

    goc = _P(__file__).resolve().parents[1]

    # actor chọn theo ĐO THẬT: rẻ gấp 4 và là cái duy nhất trả upvote
    assert reddit.ACTOR == 'clearpath~reddit-search-scraper'
    src = (goc / 'radary' / 'reddit.py').read_text(encoding='utf-8')
    assert 'KHONG tra upvote' in src          # ghi lại vì sao loại actor kia

    # dịch dữ liệu: giữ đúng thứ SERP không có — upvote, bình luận, subreddit
    than = src.split('def tim(')[1].split('def du_credit')[0]
    for truong in ('upvote', 'binh_luan', 'sub', 'ngay', 'link'):
        assert f'"{truong}"' in than, truong
    assert 'bai.sort(key=lambda b: -b["upvote"])' in than       # bài mạnh nhất trước

    # route: leader+, và không có khóa thì nói thẳng
    api_src = (goc / 'radary' / 'api.py').read_text(encoding='utf-8')
    r = api_src.split('def tra_cuu_reddit(')[1].split('\nclass DoThiTruongIn')[0]
    assert "auth.ws_for_user(c, ws, u['id'], 'leader')" in r
    assert 'Chưa cấp khóa Apify' in r and 'hết credit tháng' in r
    assert 'db.tra_cuu_luu' in r                                # lưu để mở lại 0 đồng

    # UI: nút bấm + báo giá trước khi bấm, KHÔNG tự gọi
    js = (goc / 'web' / 'app.js').read_text(encoding='utf-8')
    assert '>\n                Hỏi Reddit</button>' in js or 'Hỏi Reddit</button>' in js
    assert 'tốn ~0,016 USD mỗi lần' in js
    assert 'tra-cuu/reddit' in js


def test_serp_ep_so_va_bo_sung_trends_cho_ban_nen():
    """22/08 — user báo hai ô Trends/News trống trên bản lưu của Hot Topic.

    (1) Bản do probe NỀN tạo cố ý tắt Trends (nền 5 cụm/ngày × 3 lượt ≈ 450
        lượt/tháng, vượt xa gói free 100) → phải nói rõ lý do + cho bổ sung khi
        NGƯỜI mở xem thật, giữ nguyên tắc "quota chỉ tiêu khi người quyết định".
    (2) SERP trả LẪN số và chuỗi ("100" / "<1%" / "Breakout") → sort theo giá trị
        nổ `bad operand type for unary -: str`. Ép số an toàn, đọc không được
        thì 0 (không đoán bừa).
    """
    from pathlib import Path as _P
    from radary import serp

    assert serp._so(100) == 100 and serp._so("100") == 100
    assert serp._so("<1%") == 1 and serp._so("Breakout") == 0 and serp._so(None) == 0

    goc = _P(__file__).resolve().parents[1]
    api_src = (goc / 'radary' / 'api.py').read_text(encoding='utf-8')
    r = api_src.split('def tra_cuu_trends(')[1].split('\nclass RedditIn')[0]
    assert "auth.ws_for_user(c, ws, u['id'], 'leader')" in r      # tiêu quota → leader+
    assert 'db.tra_cuu_luu' in r                                  # ghi lại, lần sau 0 lượt
    assert 'tu_nen' in api_src and 'quét nền tạo' in api_src  # lý do rõ, không 'đã tắt'      # lý do rõ, không "đã tắt"

    js = (goc / 'web' / 'app.js').read_text(encoding='utf-8')
    assert 'Lấy Google Trends' in js and '(3 lượt SERP)' in js
    assert 'tra-cuu/trends' in js


def test_khoi_A_luon_tuoi_va_doi_chieu_cum_rut_gon():
    """22/08 — user: "in pool không có video nào về kyrgyzstan, tôi không tin nổi".

    Đúng là bug: bản lưu do PROBE NỀN của Hot Topic tạo chỉ có khối B, cột `a`
    rỗng '{}' → xem lại thấy khối A trắng dù pool có 12 video thật. Khối A đọc
    SQLite <1s và 0 quota nên cache nó vừa vô ích vừa đẻ bản thiếu — luôn tính
    tươi, cache CHỈ dành cho khối B (nơi tốn units/tiền).

    Kèm đối chiếu cụm rút gọn: cụm DÀI đo cạnh tranh trong công thức ngách,
    cụm NGẮN đo chủ đề (đo thật: kyrgyzstan 12 video/10 kênh vs life in
    kyrgyzstan 7/7 — khớp ranh giới từ nên "Real Life in KYRGYZSTAN" rơi ra).
    """
    from pathlib import Path as _P
    from radary import tra_cuu

    assert tra_cuu.cum_rut_gon('life in kyrgyzstan') == 'kyrgyzstan'
    assert tra_cuu.cum_rut_gon('real life in tajikistan') == 'tajikistan'
    assert tra_cuu.cum_rut_gon('kyrgyzstan') == ''          # đã ngắn thì không đối chiếu
    assert tra_cuu.cum_rut_gon('stunning women') == ''      # không phải cụm khung

    api_src = (_P(__file__).resolve().parents[1] / 'radary' / 'api.py').read_text(encoding='utf-8')
    than = api_src.split('def tra_cuu_pool(')[1].split('def _ghi_bo_qua_khoa')[0]
    # xem lại mà khối A rỗng → tính tươi + vá luôn bản lưu
    assert "not (cu.get('a') or {}).get('co_du_lieu')" in than
    assert 'db.tra_cuu_luu(c, ws, q, a=a_tuoi)' in than
    assert "a['doi_chieu']" in than and 'cum_rut_gon' in than

    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')
    assert 'Cụm rút gọn' in js and 'cụm NGẮN đo CHỦ ĐỀ' in js


def test_trends_tach_nhom_nguoi_khoi_truy_van_chu_de():
    """22/08 — user hỏi "lọt từ khoá Việt Nam có phải do sai thị trường không".

    KHÔNG sai: tham số gửi đi đúng geo=US, status Success. Đó là bản chất
    Google Trends — "rising related queries" là truy vấn tăng mạnh trong nhóm
    NGƯỜI cùng tìm chủ đề, không phải truy vấn VỀ chủ đề; chủ đề ít người tìm
    thì nhóm nhỏ nên 'openai news today', 'lidl near me' lọt vào (RELATED_TOPICS
    còn nhiễu hơn: National Health Service, GitHub).

    Không vứt dữ liệu — gắn nhãn đúng bản chất, tách hai nhóm.
    """
    from radary import serp

    class GiaNha:
        def __call__(self, nha, khoa, engine, tham_so):
            return {'related_queries': {
                'rising': [{'query': 'victory peak kyrgyzstan', 'extracted_value': 11750},
                           {'query': 'u23 việt nam vs u23 kyrgyzstan', 'extracted_value': 7550},
                           {'query': 'kyrgyz republic', 'extracted_value': 300},
                           {'query': 'openai news today', 'extracted_value': 15450},
                           {'query': 'lidl near me', 'extracted_value': 14600}],
                'top': [{'query': 'kazakhstan', 'extracted_value': 100}]}}

    goc = serp._goi
    serp._goi = GiaNha()
    try:
        d = serp.truy_van_lien_quan('serpapi', 'k', 'kyrgyzstan', geo='US')
    finally:
        serp._goi = goc

    lq = [m['cum'] for m in d['rising']]
    nn = [m['cum'] for m in d['nhom_nguoi']]
    assert 'victory peak kyrgyzstan' in lq
    assert 'u23 việt nam vs u23 kyrgyzstan' in lq        # sự kiện THẬT, giữ đúng nhóm
    assert 'kyrgyz republic' in lq                       # biến thể rút gọn cũng bắt được
    assert set(nn) == {'openai news today', 'lidl near me'}
    assert d['top'][0]['cum'] == 'kazakhstan'            # cột phổ biến vốn sạch, không đụng


def test_bang_cum_mac_dinh_5_dong():
    """22/08 — user: bảng cụm chỉ cần hiện 5 từ khoá + nút show more/less.

    Cùng luật với bảng Hot Topic ở Overview: trang phải quét được trong một màn
    hình, 50+ dòng đẩy phần dưới xuống quá sâu. Bản đồ bong bóng vẫn vẽ TẤT CẢ
    (nó là hình, không tốn chiều dọc theo số dòng).
    """
    from pathlib import Path as _P
    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')
    assert 'moBang ? ds : ds.slice(0, 5)' in js
    assert 'Xem tất cả ${n} cụm' in js and '▴ Thu gọn' in js
    assert 'setMoBang(false)' in js                 # đổi pool là thu lại


def test_click_tu_khoa_khong_tu_tieu_quota():
    """22/08 — user: "click vào từ khoá phải hỏi xác nhận để tránh click nhầm và
    lãng phí token".

    Đúng: trước đây traCuu() cho từ khoá CHƯA từng tra thì tự gọi khối B = 102
    units YouTube + 4 lượt SERP; bấm nhầm một bong bóng là mất thật. Nay khối A
    (0 quota, đọc SQLite) vẫn chạy ngay — đó là thứ người ta muốn xem — còn khối
    B thành nút có BÁO GIÁ + XÁC NHẬN HAI BƯỚC, cùng khuôn Reddit/Trends.
    """
    from pathlib import Path as _P
    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')

    than = js.split('const chayTraCuu = async')[1].split('const [xacNhanNgoai')[0]
    assert "api('POST', `/workspaces/${ws}/tra-cuu/ngoai`" not in than   # hết tự gọi
    assert 'KHÔNG tự hỏi thị trường ngoài' in than

    # ADVANCE MAPPING (user 22/08): mot nut, ba o tick — moi o mot loai chi phi
    assert 'Advance Mapping' in js
    assert '102 units YouTube' in js and '4 lượt SERP' in js and '0,016 USD Apify' in js
    assert 'setAdvPool' in js and 'setAdvSerp' in js and 'setAdvReddit' in js
    assert 'ngoai_pool: advPool' in js and 'serp_google: advSerp' in js
    assert 'setXacNhanNgoai(true)' in js and 'hoiNgoaiLanDau' in js
    assert 'setXacNhanNgoai(false)' in js                                # đổi cụm là reset

    # CỬA HỎI TRƯỚC (user nhắc lần 2): click từ khoá KHÔNG chạy ngay, phải xác nhận
    assert 'const [hoiCum, setHoiCum]' in js
    assert 'setHoiCum({ cum: q, lai: !!lai })' in js
    assert 'Không hỏi lại trong phiên này' in js
    assert 'chayTraCuu(cum)' in js          # gõ tay + Enter thì đi thẳng, khỏi hỏi
    # XEM LẠI bản đã lưu (lai=true) cũng đi thẳng — route xem_lai=1 là 0 quota
    # tuyệt đối, hỏi chỉ làm phiền (user báo khi mở từ dropdown lịch sử)
    assert 'if (khongHoiLai || !tu || lai) return chayTraCuu(q, lai)' in js


def test_advance_mapping_tach_duoc_tung_phan():
    """22/08 — Owner chốt tên "Advance Mapping" với ba ô tick.

    Chọn phương án TICK thay vì nút chạy-hết, và bật sẵn cả ba: ai bấm thẳng thì
    y hệt chạy-hết, ai muốn tiết kiệm thì bỏ tick. Lý do: quota SERP free ~100
    lượt/tháng, full mỗi cụm ăn 4 lượt → chỉ 25 cụm/tháng.
    """
    from pathlib import Path as _P
    goc = _P(__file__).resolve().parents[1]
    api_src = (goc / 'radary' / 'api.py').read_text(encoding='utf-8')

    # ba cờ độc lập, mặc định BẬT (bỏ tick nào thì phần đó không chạy, không tốn)
    mo = api_src.split('class TraCuuNgoaiIn')[1].split('@app.post')[0]
    for co in ('ngoai_pool: bool = True', 'trends: bool = True', 'serp_google: bool = True'):
        assert co in mo, co

    than = api_src.split('def _soi_khoi_b(')[1].split('\ndef ')[0]
    assert 'if ngoai_pool:' in than                    # không tick → không gọi YouTube
    assert 'if not serp_google:' in than               # không tick → không tiêu lượt SERP
    assert 'bỏ tick Ngoài Pool' in than                # nói rõ vì sao trống, không im lặng

    js = (goc / 'web' / 'app.js').read_text(encoding='utf-8')
    assert 'if (!advPool && !advSerp && !advReddit) return' in js   # không tick gì thì thôi
    assert "api('POST', `/workspaces/${ws}/tra-cuu/reddit`" in js   # Reddit đi route riêng


def test_advance_mapping_la_popup_rieng():
    """22/08 — user: "không muốn box show more như hiện tại, muốn box popup riêng".

    Ba ô tick trước đây xổ ngay trong dòng nhắc, đẩy hết nội dung bên dưới xuống.
    Nay là hộp nổi giữa màn hình, đóng bằng ✕ / bấm nền / Esc — cùng khuôn với
    popup xác nhận tra cứu đã có. Luồng không đổi: trong pool vẫn chạy ngay.
    """
    from pathlib import Path as _P
    js = (_P(__file__).resolve().parents[1] / 'web' / 'app.js').read_text(encoding='utf-8')

    khoi = js.split('${xacNhanNgoai && A ?')[1].split('${hoiCum ?')[0]
    assert 'position:fixed;inset:0;z-index:50' in khoi        # hộp nổi, không inline
    assert 'setXacNhanNgoai(false)' in khoi                   # bấm nền đóng
    assert 'aria-label="Đóng"' in khoi                        # nút ✕
    for tick in ('advPool', 'advSerp', 'advReddit'):
        assert f'checked=${{{tick}}}' in khoi, tick

    assert "e.key === 'Escape'" in js                         # Esc đóng cả hai popup
    # dòng nhắc inline chỉ còn MỘT nút, không còn nhánh xổ tick
    nhac = js.split('Muốn soi ra ngoài')[1].split('</div>` : \'\'}')[0]
    assert 'checkbox' not in nhac
