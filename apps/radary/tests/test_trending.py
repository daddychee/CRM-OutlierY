# -*- coding: utf-8 -*-
"""TRENDING (23/08/2026) — đo thị trường từ nguồn NGOÀI pool.

Không gọi mạng thật: mọi lời gọi HTTP đi qua tham số `doc` (hàm tải giả).
Phương pháp luận: `trending_methodology.md`.
"""
from __future__ import annotations

import json
import time

import pytest

from radary import trending as tr


@pytest.fixture
def dat_lai_hang(monkeypatch):
    """Hàng đợi + sổ lỗi là biến TOÀN CỤC tiến trình (đúng ý đồ: GDELT là tài
    nguyên CHUNG của cả app, không phải của từng pool).

    Khoá luôn luồng nền: chạy thật thì luồng phải tự vét hàng, nhưng trong test
    thì nó vét mất trước khi ta kịp kiểm hàng — và test có luồng là test bấp bênh.
    Ở đây gọi tay `_vs_mot_luot()` để biết CHÍNH XÁC lượt nào chạy lúc nào."""
    tr._vs_hang.clear(); tr._vs_loi.clear(); tr._vs_dang[0] = None
    monkeypatch.setattr(tr, "_vs_bat_luong", lambda: None)
    yield
    tr._vs_hang.clear(); tr._vs_loi.clear(); tr._vs_dang[0] = None


@pytest.fixture(autouse=True)
def _dat_lai_nhip_gdelt():
    """Nhịp gọi + cờ nghỉ-sau-429 là biến TOÀN CỤC của tiến trình (đúng ý đồ: một
    app một nhịp). Trong test thì nó rò từ ca này sang ca kia — một ca dính 429 là
    mọi ca sau đó bị từ chối oan. Đặt lại trước mỗi ca."""
    tr._chan_toi[0] = 0.0
    tr._lan_goi_gdelt[0] = 0.0
    yield


# --------------------------------------------------------------- kho giả lập
def _kho(bo: list[tuple[str, int, float]], bay_gio: float):
    """(tiêu đề, views, tuổi ngày) -> bản ghi kho đã chuẩn hoá."""
    return tr.chuan_hoa_kho(
        [{"title": t, "views": v, "pub_ts": bay_gio - n * 86400} for t, v, n in bo],
        bay_gio)


BAY_GIO = 1_800_000_000.0


def test_chuan_hoa_kho_bo_ban_ghi_thieu_so_chu_khong_coi_la_0():
    """Thiếu view/ngày đăng là KHÔNG BIẾT, không phải bằng không — van chống bịa."""
    kho = tr.chuan_hoa_kho([
        {"title": "Life in Guyana", "views": 1000, "pub_ts": BAY_GIO - 10 * 86400},
        {"title": "Life in Chad", "views": None, "pub_ts": BAY_GIO - 10 * 86400},
        {"title": "Life in Fiji", "views": 500, "pub_ts": 0},
        {"title": "", "views": 900, "pub_ts": BAY_GIO},
    ], BAY_GIO)
    assert [r["title"] for r in kho] == ["Life in Guyana"]
    assert kho[0]["vpd"] == pytest.approx(100.0)


# ============================== LUẬT 2 — ngưỡng lấy từ phân vị của CHÍNH pool
def test_nguong_lay_tu_phan_vi_cua_chinh_pool_khong_phai_hang_so():
    """Đo thật 23/08: ngưỡng cố định "<=10 video" ôm 36% thực thể ở LIFE IN nhưng
    60% ở TRAVEL DOC — cùng một con số nói ngược nhau giữa hai pool. Nên ngưỡng
    phải trôi theo pool."""
    # pool A: thực thể thường có NHIỀU video
    a = [{"cum": f"a{i}", "n": n, "vpd": 10.0} for i, n in enumerate([8, 12, 14, 20, 40])]
    # pool B: thực thể thường có ÍT video
    b = [{"cum": f"b{i}", "n": n, "vpd": 10.0} for i, n in enumerate([2, 3, 5, 8, 15])]
    nga = tr.nguong_pool(a, tv_pool=10.0)
    ngb = tr.nguong_pool(b, tv_pool=10.0)
    assert nga["video_tv"] == 14 and ngb["video_tv"] == 5
    # CÙNG một thực thể 10 video: pool A coi là ít, pool B coi là nhiều
    h = {"cum": "x", "n": 10, "vpd": 100.0}
    assert tr.xep_o(h, nga) == tr.O_THIEU_CUNG
    assert tr.xep_o(h, ngb) == tr.O_DA_KHAI_THAC


def test_nguong_khong_du_mau_thi_noi_thang():
    ng = tr.nguong_pool([], tv_pool=10.0)
    assert ng["du_mau"] is False and ng["ly_do"]


def test_bon_o_va_o_chua_du_dau_vet():
    ng = tr.nguong_pool([{"cum": f"c{i}", "n": n, "vpd": v}
                         for i, (n, v) in enumerate([(4, 10), (10, 10), (14, 10),
                                                     (30, 10), (60, 40)])],
                        tv_pool=10.0)
    O = tr.xep_o
    assert O({"n": 10, "vpd": 10 * ng["boi_p75"] + 1}, ng) == tr.O_THIEU_CUNG
    assert O({"n": 10, "vpd": 1.0}, ng) == tr.O_DA_THU
    assert O({"n": 99, "vpd": 10 * ng["boi_p75"] + 1}, ng) == tr.O_DA_KHAI_THAC
    assert O({"n": 99, "vpd": 1.0}, ng) == tr.O_BAO_HOA
    # dưới ngưỡng mẫu -> KHÔNG kết luận, dù hiệu suất trông rất đẹp
    assert O({"n": 2, "vpd": 9999.0}, ng) == tr.O_CHUA_DU


def test_ho_so_pool_duoi_hai_video_thi_khong_ket_luan():
    kho = _kho([("Life in Guyana today", 1000, 10)], BAY_GIO)
    assert tr.ho_so_pool(kho, "guyana", BAY_GIO) is None


def test_ho_so_pool_dem_dung_va_khong_khop_tu_con():
    kho = _kho([("Life in Guyana", 1000, 10), ("Guyana coast", 2000, 10),
                ("Guyanacaster fake", 9999, 10)], BAY_GIO)
    h = tr.ho_so_pool(kho, "guyana", BAY_GIO)
    assert h["n"] == 2                       # ranh giới từ: "guyanacaster" KHÔNG tính
    assert h["vpd"] == pytest.approx(150.0)
    assert len(h["nhip"]) == 12 and sum(h["nhip"]) == 2


# ============================== LUẬT 3 — không loại ứng viên nào theo ngưỡng
def test_khop_tu_dien_giu_moi_ung_vien_khong_cat_theo_nguong():
    """Mỗi từ khoá là một ý tưởng riêng (Owner 23/08) — bốn ô chỉ là thứ tự đọc."""
    trends = [{"cum": "guyana", "con_mo": True}, {"cum": "senegal", "con_mo": False},
              {"cum": "japan earthquake", "con_mo": True}]
    ra = tr.khop_tu_dien(trends, ["guyana", "senegal", "japan"])
    assert set(ra) == {"guyana", "senegal", "japan"}


def test_khop_uu_tien_ban_ghi_con_mo_cua_so():
    trends = [{"cum": "guyana oil", "con_mo": False, "luong": "50K+"},
              {"cum": "guyana", "con_mo": True, "luong": "100+"}]
    ra = tr.khop_tu_dien(trends, ["guyana"])
    assert ra["guyana"]["con_mo"] is True


def test_doc_trending_csv_doc_thang_cua_so_va_nguyen_nhan():
    """Cột Ended rỗng = cửa sổ CÒN MỞ; Trend breakdown = nguyên nhân — đọc thẳng
    khỏi dữ liệu, không phải tự suy."""
    ra = tr.doc_trending_csv([
        {"Trends": "peru", "Search volume": "20K+", "Started": "August 21, 2026",
         "Ended": "nan", "Trend breakdown": "peru,picchu,machu picchu"},
        {"Trends": "oman", "Search volume": "50K+", "Started": "August 20, 2026",
         "Ended": "August 22, 2026", "Trend breakdown": "oman,trump oman,trump iran"},
        {"Trends": "", "Search volume": "1M+", "Started": "", "Ended": "", "Trend breakdown": ""},
    ])
    assert len(ra) == 2                                  # dòng rỗng bị bỏ
    assert ra[0]["con_mo"] is True and ra[1]["con_mo"] is False
    assert ra[0]["breakdown"] == ["picchu", "machu picchu"]   # bỏ phần tử đầu = chính cụm


def test_doc_trending_csv_chiu_duoc_o_khong_phai_chuoi():
    """Sự cố 23/08 lượt quét thật: AttributeError 'float' object has no attribute
    'strip'. Test cũ chỉ cho ăn CHUỖI (đúng khi đọc file .csv), còn đường LẤY TRỰC
    TIẾP trả về số cho 'Search volume' và NaN cho ô trống. Ô trống KHÔNG phải 0 và
    NaN KHÔNG phải chuỗi 'nan' — phải quy về rỗng trước khi đọc."""
    nan = float("nan")
    ra = tr.doc_trending_csv([
        {"Trends": "guyana", "Search volume": 200000.0, "Started": "August 21, 2026",
         "Ended": nan, "Trend breakdown": nan},
        {"Trends": "oman", "Search volume": 50000, "Started": nan,
         "Ended": "August 22, 2026", "Trend breakdown": "oman,trump oman"},
        {"Trends": nan, "Search volume": 1000.0, "Started": nan, "Ended": nan,
         "Trend breakdown": nan},
    ])
    assert len(ra) == 2                                   # dòng tên NaN bị bỏ như dòng rỗng
    assert ra[0]["con_mo"] is True                        # NaN = cửa sổ còn mở
    assert ra[1]["con_mo"] is False
    assert ra[0]["luong"] == "200000" and ra[1]["luong"] == "50000"   # không ra "200000.0"
    assert ra[0]["breakdown"] == [] and ra[0]["bat_dau"] == "August 21, 2026"
    assert ra[1]["bat_dau"] == ""                         # NaN -> rỗng, không phải "nan"

# ============================== bước xác minh loại — lỗi đã trả giá 23/08
def _doc_wiki(bang: dict):
    """Wikipedia pageterms giả."""
    def _doc(url: str) -> str:
        pages = {}
        for i, (ten, mo) in enumerate(bang.items()):
            pages[str(i)] = {"title": ten.title(),
                             "terms": ({"description": [mo]} if mo else {})}
        return json.dumps({"query": {"pages": pages}})
    return _doc


def test_xac_minh_loai_go_danh_tu_chung():
    """Bỏ bước này thì từ điển pool lọt đầy DANH TỪ CHUNG và mọi trend chứa một từ
    thường đều khớp — đã dính thật khi dựng thử 23/08 (fire, car, dream, price)."""
    mo_ta = tr.xac_minh_loai(["guyana", "fire", "car"], doc=_doc_wiki({
        "guyana": "country in South America",
        "fire": "rapid oxidation of a material",
        "car": "motorized road vehicle"}))
    giu, bo = tr.loc_thuc_the(["guyana", "fire", "car"], mo_ta)
    assert giu == ["guyana"]
    assert [t for t, _ in bo] == ["fire", "car"]
    assert all(m for _, m in bo)              # kèm lý do, không loại im lặng


def test_xac_minh_loai_khong_tra_duoc_thi_khong_bia_khoa():
    mo_ta = tr.xac_minh_loai(["guyana"], doc=lambda u: "khong-phai-json")
    assert mo_ta == {}
    giu, bo = tr.loc_thuc_the(["guyana"], mo_ta)
    assert giu == [] and bo == [("guyana", "")]


# ============================== GDELT — lấp lỗ hổng "vì sao nóng"
def _doc_gdelt(payload):
    return lambda url: payload if isinstance(payload, str) else json.dumps(payload)


def test_vi_sao_nong_lay_duoc_dinh_va_bai_bao():
    d = tr.vi_sao_nong("guyana", doc=_doc_gdelt({"timeline": [{"data": [
        {"date": "20260820T000000Z", "value": 3, "toparts": []},
        {"date": "20260823T000000Z", "value": 41, "toparts": [
            {"title": "Guyana oil discovery", "domain": "reuters.com", "url": "http://x"}]},
    ]}]}))
    assert d["co_du_lieu"] and d["dinh_ngay"] == "20260823"
    # ĐƠN VỊ: timelinevolinfo trả PHẦN TRĂM tổng tin, không phải số bài. Gọi nó là
    # "tin" là ghi nhãn sai — đã in nhầm "0.6547 tin" khi nghiệm thu 23/08.
    assert d["dinh_phan_tram"] == 41 and d["don_vi"] == "phần trăm tổng tin"
    assert d["bai"][0]["nguon"] == "reuters.com"
    assert len(d["diem"]) == 2 and "phan_tram" in d["diem"][0]


def test_vi_sao_nong_rut_ten_mien_tu_url_khi_gdelt_khong_tra_domain():
    """Đo thật 23/08: `toparts` của timelinevolinfo không kèm khoá 'domain' nên
    nguồn ra None hết. Rút từ chính URL thay vì để trống."""
    d = tr.vi_sao_nong("guyana", doc=_doc_gdelt({"timeline": [{"data": [
        {"date": "20260823T000000Z", "value": 5, "toparts": [
            {"title": "X", "url": "https://www.reuters.com/world/abc"}]}]}]}))
    assert d["bai"][0]["nguon"] == "reuters.com"


def test_vi_sao_nong_bi_chan_nhip_thi_noi_ro_chu_khong_tra_rong():
    """GDELT trả HTML khi bị chặn nhịp. Trả rỗng là để người (hay AI) đọc nhầm
    thành 'không có tin gì' — đúng thứ report_cum.py cấm."""
    d = tr.vi_sao_nong("guyana", doc=_doc_gdelt("<html>rate limited</html>"))
    assert d["co_du_lieu"] is False and "chặn nhịp" in d["ly_do"]


def test_vi_sao_nong_khong_co_tin_thi_ghi_ly_do_kem_ten_va_so_ngay():
    d = tr.vi_sao_nong("guyana", ngay=30, doc=_doc_gdelt({"timeline": []}))
    assert d["co_du_lieu"] is False and "guyana" in d["ly_do"] and "30" in d["ly_do"]


def test_gdelt_gian_cach_du_de_khong_bi_chan():
    """1 lời gọi/5 giây là hạn mức GDELT công bố. Hằng số này là lời nhắc TUYỆT ĐỐI
    không quét cả từ điển qua đường này — chỉ hỏi cho ứng viên người dùng bấm."""
    assert tr.GDELT_GIAN_CACH >= 5.0


def test_khop_phoi_ra_DO_CHAC_de_bat_noi_nham_thuc_the():
    """Nối nhầm là lỗi thật đã đo 23/08: `dream` khớp từ trend "atlanta dream"
    (đội bóng rổ), `jordan` khớp từ "jordan spieth" (gôn thủ). Không loại (luật 3)
    mà PHƠI RA: độ chắc = thực thể chiếm bao nhiêu phần của cụm trend."""
    trends = [{"cum": "guyana", "con_mo": True},
              {"cum": "atlanta dream", "con_mo": True},
              {"cum": "jordan spieth comments pga tour", "con_mo": True}]
    ra = tr.khop_tu_dien(trends, ["guyana", "dream", "jordan"])
    assert ra["guyana"]["do_chac"] == 1.0
    assert ra["dream"]["do_chac"] < 0.6 and ra["dream"]["khop_voi"] == "atlanta dream"
    assert ra["jordan"]["do_chac"] < 0.3
    assert set(ra) == {"guyana", "dream", "jordan"}     # KHÔNG cái nào bị loại


def test_gdelt_429_noi_ro_la_bi_chan_nhip_chu_khong_gop_vao_loi_chung():
    """Đo thật 23/08: ba lời gọi liên tiếp là 429 hết. Gộp nó vào "lỗi HTTP" chung
    thì người đi sửa nhầm chỗ — đúng họ sự cố 29/07 (Z.ai hết tiền bị báo nhầm
    thành không lấy được phụ đề)."""
    import urllib.error as ue

    def _doc(url):
        raise ue.HTTPError(url, 429, "Too Many Requests", {}, None)

    d = tr.vi_sao_nong("guyana", doc=_doc)
    assert d["co_du_lieu"] is False and d.get("bi_chan_nhip") is True
    assert "chặn nhịp" in d["ly_do"]


def test_gdelt_loi_khac_429_thi_ghi_dung_ma_HTTP():
    import urllib.error as ue

    def _doc(url):
        raise ue.HTTPError(url, 503, "Service Unavailable", {}, None)

    d = tr.vi_sao_nong("guyana", doc=_doc)
    assert d["co_du_lieu"] is False and not d.get("bi_chan_nhip") and "503" in d["ly_do"]


def test_trang_thai_running_mo_coi_sau_khi_app_khoi_dong_lai(tmp_path, monkeypatch):
    """Sự cố 23/08 ngay sau restart: kv còn state='running' của lượt quét đã chết
    theo tiến trình cũ. Luồng nằm TRONG tiến trình nên khởi động lại là mất — kv
    thì không biết điều đó, UI cứ quay mãi. Đọc trạng thái phải đối chiếu luồng
    thật, mồ côi thì nói thẳng là đứt chứ không báo đang chạy."""
    import radary.trending as _tr
    from radary import db as _db
    conn = _db.connect(str(tmp_path / "t.db")) if _db.connect.__code__.co_argcount else _db.connect()
    _db.kv_set(conn, 7, _tr.KHOA_TT, {"state": "running", "buoc": "đọc pool"})
    _tr._luong.pop(7, None)                       # không có luồng nào sống cho ws 7
    tt = _tr.trang_thai(conn, 7)
    assert tt["state"] == "error"
    assert "đứt" in tt["ly_do"]


# ============================== hai viec Owner chot 23/08

def test_bon_buoc_chay_khai_o_MOT_cho_va_danh_so():
    """Owner: 'phải note lại các giai đoạn chạy, chạy từng bước nào'. Nhãn bước
    trước đây rải rác trong _chay dưới dạng chuỗi rời — UI chỉ hiện được chữ, không
    biết đang ở bước mấy trên mấy. Gom về MỘT danh sách khai báo, _chay chỉ gọi
    theo chỉ số, kv ghi kèm số thứ tự để UI vẽ được tiến trình."""
    import inspect
    assert len(tr.BUOC) >= 4
    ma = inspect.getsource(tr._chay)
    for i in range(len(tr.BUOC)):
        assert f"_buoc(conn, ws, {i}" in ma, f"_chay không khai bước {i}"
    # không còn nhãn bước viết tay lẫn vào
    assert 'state="running", buoc=' not in ma


def test_buoc_ghi_kem_so_thu_tu(tmp_path):
    from radary import db as _db
    conn = _db.connect()
    tr._buoc(conn, 9, 2, geo="US")
    tt = _db.kv_get(conn, 9, tr.KHOA_TT, None)
    assert tt["buoc_so"] == 3 and tt["buoc_tong"] == len(tr.BUOC)
    assert "US" in tt["buoc"]            # nhãn có chỗ điền geo thì phải điền thật


def test_ho_so_pool_kem_video_de_dan_chung():
    """Owner: hiện link + thumbnail như bảng Topic hot bên Mapping. Muốn vậy hồ sơ
    phải mang theo yt_id — con số 'n video' tự nó không kiểm chứng được."""
    kho = tr.chuan_hoa_kho([
        {"title": "Life in Guyana", "pub_ts": time.time() - 10 * 86400, "views": 500_000,
         "yt_id": "aaa", "kenh": "K1"},
        {"title": "Guyana today", "pub_ts": time.time() - 20 * 86400, "views": 100_000,
         "yt_id": "bbb", "kenh": "K2"},
        {"title": "Guyana rừng", "pub_ts": time.time() - 5 * 86400, "views": 10_000,
         "yt_id": "ccc", "kenh": "K3"},
        {"title": "Life in Peru", "pub_ts": time.time() - 5 * 86400, "views": 900_000,
         "yt_id": "ddd", "kenh": "K4"},
    ])
    h = tr.ho_so_pool(kho, "guyana", so_video=2)
    assert h["n"] == 3
    # aaa 50k/ngày > bbb 5k/ngày > ccc 2k/ngày — xếp theo NHỊP chạy, không theo
    # view thô (ccc mới 5 ngày nhưng chạy chậm hơn bbb đã 20 ngày).
    assert [v["yt_id"] for v in h["video"]] == ["aaa", "bbb"]
    assert h["video"][0]["kenh"] == "K1" and h["video"][0]["tuoi"] == 10
    assert all("ddd" != v["yt_id"] for v in h["video"])           # video khác cụm không lọt


def test_ho_so_pool_khong_bia_video_khi_kho_thieu_yt_id():
    """Pool cũ có bản ghi thiếu yt_id — bỏ qua, không dựng link rỗng."""
    kho = tr.chuan_hoa_kho([
        {"title": "Life in Guyana", "pub_ts": time.time() - 10 * 86400, "views": 500_000},
        {"title": "Guyana today", "pub_ts": time.time() - 20 * 86400, "views": 100_000},
    ])
    h = tr.ho_so_pool(kho, "guyana")
    assert h["n"] == 2 and h["video"] == []


# ============================== GDELT cham — do that 23/08: 12-17s moi loi goi

def test_vi_sao_co_cache_hoi_lai_khong_goi_mang():
    """Owner báo 'vì sao nóng chạy lâu quá'. Đo thật: GDELT tốn 12-17s MỖI lời gọi
    và chặn nhịp rất hay. Không rút ngắn được lời gọi đầu, nhưng lần hỏi LẠI thì
    không được trả giá lần nữa — khối lượng tin 30 ngày không đổi trong vài giờ."""
    from radary import db as _db
    conn = _db.connect()
    dem = []

    def _gia(url):
        dem.append(url)
        return json.dumps({"timeline": [{"data": [
            {"date": "20260816T120000Z", "value": 0.65,
             "toparts": [{"title": "Bai 1", "url": "https://x.com/a"}]}]}]})

    a = tr.vi_sao_co_cache(conn, 3, "guyana", doc=_gia)
    b = tr.vi_sao_co_cache(conn, 3, "guyana", doc=_gia)
    assert a["co_du_lieu"] and b["co_du_lieu"]
    assert len(dem) == 1, "lần hỏi lại vẫn gọi mạng"
    assert b["tu_cache"] is True and a.get("tu_cache") is not True
    # cụm khác thì vẫn phải hỏi thật
    tr.vi_sao_co_cache(conn, 3, "niger", doc=_gia)
    assert len(dem) == 2


def test_vi_sao_khong_cache_ket_qua_hong():
    """Lỗi mạng/429 KHÔNG được đóng băng 6 tiếng — chỉ cache câu trả lời có dữ liệu."""
    from radary import db as _db
    conn = _db.connect()
    dem = []

    def _hong(url):
        dem.append(url)
        raise RuntimeError("mang hong")

    for _ in range(2):
        r = tr.vi_sao_co_cache(conn, 4, "guyana", doc=_hong)
        assert r["co_du_lieu"] is False
    assert len(dem) == 2


def test_bi_429_thi_tu_choi_NGAY_thay_vi_bat_cho_them_mot_luot():
    """Dính 429 rồi mà vẫn cho gọi tiếp thì người dùng ngồi thêm 12s nữa để nhận
    đúng lỗi đó — cảm giác 'mãi không xong' đến từ đây. Chặn thì nói ngay, kèm số
    giây còn lại, KHÔNG chạm mạng."""
    import urllib.error as ue
    dem = []

    def _429(url):
        dem.append(url)
        raise ue.HTTPError(url, 429, "Too Many Requests", {}, None)

    r1 = tr.vi_sao_nong("guyana", doc=_429)
    assert r1["bi_chan_nhip"] is True
    r2 = tr.vi_sao_nong("niger", doc=_429)
    assert r2["bi_chan_nhip"] is True
    assert len(dem) == 1, "lời gọi thứ hai vẫn chạm mạng"
    assert r2["cho_giay"] > 0 and str(r2["cho_giay"]) in r2["ly_do"]


# ============================== hang doi "vi sao nong" (Owner chot 23/08)

def _gdelt_gia(dem=None):
    def _f(url):
        if dem is not None:
            dem.append(url)
        return json.dumps({"timeline": [{"data": [
            {"date": "20260816T120000Z", "value": 0.65,
             "toparts": [{"title": "Bai 1", "url": "https://x.com/a"}]}]}]})
    return _f


def test_hang_doi_khong_bat_nguoi_dung_ngoi_cho(dat_lai_hang):
    """GDELT tốn 12-17s/lời gọi và chặn nhịp gắt. Bấm xong phải được trả lời NGAY
    (đã xếp hàng, đứng thứ mấy), việc chạy nền — thay vì giữ request 12s."""
    from radary import db as _db
    conn = _db.connect()
    dem = []
    r = tr.xin_vi_sao(conn, 11, "guyana", doc=_gdelt_gia(dem))
    assert r["xep_hang"] is True and r["vi_tri"] == 1
    assert dem == [], "đã chạm mạng ngay trong request — đúng cái cần tránh"

    assert tr._vs_mot_luot() is True            # worker làm một lượt
    assert len(dem) == 1
    xong = tr.xin_vi_sao(conn, 11, "guyana")
    assert xong["co_du_lieu"] is True and xong["tu_cache"] is True
    assert tr._vs_mot_luot() is False           # hàng rỗng


def test_hoi_lai_khi_dang_xep_hang_khong_nhan_doi_luot(dat_lai_hang):
    """UI hỏi lại mỗi 3s để xem xong chưa — mỗi lần hỏi mà đẩy thêm một lượt vào
    hàng thì hàng phình vô hạn và GDELT bị gọi lặp cùng một cụm."""
    from radary import db as _db
    conn = _db.connect()
    tr.xin_vi_sao(conn, 12, "guyana", doc=_gdelt_gia())
    for _ in range(4):
        r = tr.xin_vi_sao(conn, 12, "guyana")
        assert r["xep_hang"] is True
    assert len(tr._vs_hang) == 1


def test_xep_hang_theo_thu_tu_va_bao_dung_vi_tri(dat_lai_hang):
    from radary import db as _db
    conn = _db.connect()
    for i, c in enumerate(["guyana", "niger", "haiti"], 1):
        assert tr.xin_vi_sao(conn, 13, c, doc=_gdelt_gia())["vi_tri"] == i
    assert tr.xin_vi_sao(conn, 13, "haiti")["vi_tri"] == 3


def test_loi_tra_ve_mot_lan_va_bam_lai_thi_thu_lai(dat_lai_hang):
    """Lỗi KHÔNG vào cache (van chống bịa), nhưng phải giữ lại đủ lâu để người dùng
    đọc được — nếu quên ngay thì lần hỏi lại kế tiếp trông như chưa từng chạy."""
    from radary import db as _db
    conn = _db.connect()

    def _hong(url):
        raise RuntimeError("mang hong")

    tr.xin_vi_sao(conn, 2, "guyana", doc=_hong)
    tr._vs_mot_luot()
    r = tr.xin_vi_sao(conn, 2, "guyana")
    assert r["co_du_lieu"] is False and not r.get("xep_hang")
    assert tr.xin_vi_sao(conn, 2, "guyana")["co_du_lieu"] is False   # vẫn đọc lại được

    dem = []
    r2 = tr.xin_vi_sao(conn, 2, "guyana", lam_moi=True, doc=_gdelt_gia(dem))
    assert r2["xep_hang"] is True                                     # bấm lại thì thử lại
    tr._vs_mot_luot()
    assert len(dem) == 1
    assert tr.xin_vi_sao(conn, 2, "guyana")["co_du_lieu"] is True


def test_bi_chan_nhip_thi_xep_LAI_hang_chu_khong_bao_hong(dat_lai_hang):
    """Sự cố ngay lượt nghiệm thu đầu: bấm 3 cụm, cả 3 báo lỗi trong 1 giây. Vì
    worker vét cạn hàng trong lúc GDELT đang chặn — mỗi lượt bị từ chối ngay rồi
    ghi thành lỗi. Hàng đợi mà không biết CHỜ thì vô nghĩa: bị chặn nhịp là xếp
    LẠI, để vòng lặp nền chờ hết cữ rồi làm tiếp. Chỉ bỏ cuộc sau vài lần."""
    import urllib.error as ue
    from radary import db as _db
    conn = _db.connect()

    def _429(url):
        raise ue.HTTPError(url, 429, "Too Many Requests", {}, None)

    tr.xin_vi_sao(conn, 15, "guyana", doc=_429)
    tr._vs_mot_luot()
    assert len(tr._vs_hang) == 1, "bị chặn nhịp mà không xếp lại hàng"
    assert (15, "guyana") not in tr._vs_loi, "vội báo hỏng trong khi mới chỉ bị chặn"

    for _ in range(tr.VS_THU_LAI):
        tr._chan_toi[0] = 0.0
        tr._vs_mot_luot()
    assert tr._vs_hang == []
    assert tr._vs_loi[(15, "guyana")]["co_du_lieu"] is False    # hết lượt thì nói thật
