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
