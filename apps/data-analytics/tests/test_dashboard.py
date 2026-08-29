# -*- coding: utf-8 -*-
"""Test trang /niche (dashboard gộp) — danh bạ mock qua monkeypatch, dữ liệu tmp."""
import json

import pytest
from fastapi.testclient import TestClient

from src import dashboard
from src.main import app
from tests.test_niche_bridge import _seed

CLAIMS = {"X-Remote-User": "tester", "X-Remote-Level": "2"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    project = _seed(tmp_path)                      # snapshot giả 2026-08-18, điểm 58
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path))
    map_path = tmp_path / "niche_projects.json"
    map_path.write_text(json.dumps({"N-TEST": {"TT-US": project}}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-TEST", "ten_chuan": "TEST NICHE",
                                  "thi_truong_cua": ["TT-US"]}])
    monkeypatch.setattr(dashboard, "_ds_kenh",
                        lambda ma: [{"ma": "K-A", "ten_chuan": "KENH A",
                                     "ngach_ma": ma, "thi_truong_ma": "TT-US"}])
    monkeypatch.setattr(dashboard, "_ten_thi_truong", lambda: {"TT-US": "US"})
    return TestClient(app)


def test_khong_claims_401(client):
    assert client.get("/niche").status_code == 401


def test_overall_hien_tile_va_kenh(client):
    r = client.get("/niche", headers=CLAIMS)
    assert r.status_code == 200
    body = r.text
    assert "TEST NICHE" in body                              # niche đang chọn
    # (kênh sống hẳn bên Channel Research từ 19/08 — trang Niche không còn KENH A)
    assert "58" in body and "3.071" in body                  # tile số thật từ snapshot
    assert "VÀO CÓ ĐIỀU KIỆN" in body                        # verdict tiếng Việt
    assert "Read report" in body and "New Research" in body  # button tiếng Anh
    assert 'id="nr-llm"' in body and 'id="nr-deepdive"' in body   # 4 tùy chọn pipeline
    # phương án 2 (19/08): chọn pool sẵn có RadarY, hết ô dán tay
    assert 'id="nr-pool-ws"' in body and 'id="nr-pool"' not in body
    assert "hidden" in body and "iraq" in body               # Best & Worst cụm


def test_overall_banner_va_strip(client):
    """Nội dung báo cáo gộp kéo ra overview (user chốt 18/08): banner phán quyết +
    dải tổng quan số pipeline; MỘT thị trường mặc định (không All — ảnh 2)."""
    body = client.get("/niche", headers=CLAIMS).text
    assert "PHÁN QUYẾT" in body and "Vào có điều kiện" in body
    assert "Tổng quan số của pipeline" in body and "3.815" in body and "12.869" in body
    assert ">All<" not in body                     # hết nút All
    assert "chênh 42× trung vị" in body            # số dẫn xuất PY tính
    b2 = client.get("/niche", headers=CLAIMS,
                    params={"ngach": "N-TEST", "tt": "TT-US"})
    assert b2.status_code == 200 and "TEST NICHE" in b2.text


def test_bon_tab_dien_giai_lai_native(client):
    """4 tab user chốt 18/08, bản DIỄN GIẢI LẠI kiểu dashboard — không nhúng iframe
    báo cáo; diễn giải chi tiết nằm trong title (hover mới hiện)."""
    body = client.get("/niche", headers=CLAIMS).text
    assert ">Overview<" in body and ">Audience<" in body
    assert ">Winning Format<" in body and ">Positioning<" in body
    assert "<iframe" not in body                          # hết nhúng nguyên báo cáo
    # Audience: canvas cắt từ báo cáo + dữ liệu gaps thật
    assert "Audience Profile Canvas" in body and "Là ai" in body
    assert "Which legendary place next?" in body and "surprised most" in body
    # Winning Format: khuôn thắng từ analysis.json
    assert "real life in" in body and "BEAUTIFUL" in body and "hidden cultures" in body
    # Positioning: beachhead chọn + phương án cắt từ báo cáo + bets
    assert "BEACHHEAD CHỌN" in body and "Phương án A" in body and "STRONG" in body
    # diễn giải hover: banner không in cứng, chú giải tile trong title
    assert 'title="Pipeline: borderline' in body.replace("  ", " ")
    assert "chênh 42× trung vị" in body


def test_audience_fallback_khi_thieu_bao_cao_html(client, tmp_path):
    """Snapshot không có báo cáo gộp HTML → canvas/phương án (tầng NGHĨA cắt từ báo
    cáo) vắng nhưng tab VẪN sống bằng artifact thật; không link đọc-trong-báo-cáo."""
    import json as _j
    idx = tmp_path / "TestNiche_US" / "snapshots" / "index.json"
    d = _j.loads(idx.read_text(encoding="utf-8"))
    d[0]["bao_cao"] = []
    idx.write_text(_j.dumps(d), encoding="utf-8")
    body = client.get("/niche", headers=CLAIMS).text
    assert ">Winning Format<" in body and ">Positioning<" in body   # tab vẫn sống
    assert "real life in" in body and "STRONG" in body              # số từ artifact
    assert "Là ai" not in body                                      # canvas vắng
    assert "sinh khi build báo cáo gộp" in body                     # ghi chú thay thế
    assert "đọc trong báo cáo ↗" not in body


def test_dropdown_du_moi_thi_truong_danh_ba(client, monkeypatch):
    """LUẬT MỚI 18/08 (thay lệnh sáng cùng ngày): dropdown = thị trường ngách ĐÃ
    CHỌN (General → Niches), không phải cả danh bạ; mặc định = thị trường ĐÃ GÁN
    đầu tiên; market đã chọn nhưng chưa gán dự án → khối hướng dẫn New report."""
    monkeypatch.setattr(dashboard, "_ten_thi_truong",
                        lambda: {"TT-US": "US", "TT-KOREA": "Korea"})
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-TEST", "ten_chuan": "TEST NICHE",
                                  "thi_truong_cua": ["TT-US", "TT-KOREA"]}])
    body = client.get("/niche", headers=CLAIMS).text
    assert ">Korea<" in body                              # option trong dropdown
    assert "PHÁN QUYẾT" in body                           # mặc định = US (đã gán)
    import unicodedata as _u0
    assert _u0.normalize("NFC", "Chưa gán dự án nghiên cứu") not in _u0.normalize("NFC", body)
    # nút tạo report chỉ L3+ → vế nút kiểm bằng claims L5
    b2 = client.get("/niche", headers={"X-Remote-User": "t5", "X-Remote-Level": "5"},
                    params={"tt": "TT-KOREA"}).text
    # so sánh qua NFC — chuỗi tiếng Việt trong code/test có thể lệch tổ hợp dấu
    import unicodedata as _u
    assert _u.normalize("NFC", "Chưa gán dự án nghiên cứu") in _u.normalize("NFC", b2)
    assert "moNicheModal('TT-KOREA')" in b2


def test_xem_lai_ngay_cu(client):
    r = client.get("/niche", headers=CLAIMS, params={"ngach": "N-TEST", "ngay": "2026-08-18"})
    assert r.status_code == 200 and "snapshot 2026-08-18" in r.text


def test_doc_va_tai_bao_cao(client):
    ok = client.get("/niche/tai/TestNiche_US/2026-08-18/BAO-CAO-8-PHASE.html",
                    headers=CLAIMS, params={"inline": 1})
    assert ok.status_code == 200 and "text/html" in ok.headers["content-type"]
    assert "content-disposition" not in ok.headers or "attachment" not in ok.headers.get("content-disposition", "")
    tai = client.get("/niche/tai/TestNiche_US/2026-08-18/BAO-CAO-8-PHASE.html", headers=CLAIMS)
    assert "attachment" in tai.headers.get("content-disposition", "")
    # file ngoài sổ snapshot → 404 lặng lẽ
    assert client.get("/niche/tai/TestNiche_US/2026-08-18/decision1.json",
                      headers=CLAIMS).status_code == 404


# ---------- pane KÊNH ----------

def _seed_kenh(monkeypatch, co_report=True):
    from src.bao_cao_lich_su import luu_bao_cao
    monkeypatch.setattr(dashboard, "_kenh_theo_ma",
                        lambda ma: {"ma": "K-A", "ten_chuan": "KENH A", "bi_danh": "kenh-alias",
                                    "ngach_ma": "N-TEST", "thi_truong_ma": "TT-US"}
                        if ma == "K-A" else None)
    if co_report:
        luu_bao_cao("tester", {
            "id": "r-cu", "ten_file_goc": "cu.csv", "ten_bao_cao": "Tuần 33",
            "ten_kenh": "Kenh A", "duong_dan_goc": "/khong/co",
            "kenh": {"tang_vo": "retention", "so_video": 14,
                     "metrics_chinh": {"ctr": 0.046, "retention": 0.24, "views": 412680}},
        }, "2026-08-10T00:00:00")
        luu_bao_cao("tester", {
            "id": "r-moi", "ten_file_goc": "moi.csv", "ten_bao_cao": "Tuần 34",
            "ten_kenh": "KENH  A",                 # lệch hoa/khoảng trắng — phải vẫn khớp
            "duong_dan_goc": "/khong/co",
            "kenh": {"tang_vo": "ctr", "so_video": 15,
                     "metrics_chinh": {"ctr": 0.051, "retention": 0.26, "views": 500000}},
        }, "2026-08-17T00:00:00")


def test_kenh_pane_tile_va_benchmark(client, monkeypatch):
    _seed_kenh(monkeypatch)
    r = client.get("/niche/kenh/K-A", headers=CLAIMS)
    assert r.status_code == 200
    body = r.text
    assert "KENH A" in body and "Tuần 34" in body            # bản mới nhất mặc định
    assert "500.000" in body and "5.1%" in body               # tile từ metrics_chinh
    assert "Full analysis" in body
    assert "3.071" in body and "128.885" in body              # dải so-ngách từ snapshot niche
    # REPORT LIST cuối kênh (user 18/08): đủ cả bản cũ + link Full analysis từng bản
    assert ">Reports<" in body and "Tuần 33" in body
    assert "/bao-cao-lich-su/r-cu" in body and "/bao-cao-lich-su/r-moi" in body
    assert "đang xem" in body                                 # đánh dấu bản đang mở
    assert "chỉ hiện số tóm tắt" in body                      # file gốc không có → lý do, không vỡ
    assert "— 💰" in body or "chưa bật kiếm tiền" in body     # tile doanh thu van chống bịa


def test_kenh_pane_xem_report_cu(client, monkeypatch):
    _seed_kenh(monkeypatch)
    r = client.get("/niche/kenh/K-A", headers=CLAIMS, params={"id": "r-cu"})
    assert r.status_code == 200 and "Tuần 33" in r.text and "412.680" in r.text


def test_kenh_chua_co_report(client, monkeypatch):
    _seed_kenh(monkeypatch, co_report=False)
    r = client.get("/niche/kenh/K-A", headers=CLAIMS)
    assert r.status_code == 200 and "Chưa có report nào gắn tên kênh" in r.text


def test_kenh_khong_ton_tai_404(client, monkeypatch):
    _seed_kenh(monkeypatch, co_report=False)
    assert client.get("/niche/kenh/K-XYZ", headers=CLAIMS).status_code == 404


# ---------- PA2: một mặt tiền ----------

def test_chan_doan_trang_chon_2_khoi(client):
    # User chốt 18/08 (khuôn Content Ultimate): /chan-doan (đích alias gateway
    # /data-analytics) = trang CHỌN 2 KHỐI Niche Research · Channel Research.
    r = client.get("/chan-doan", headers=CLAIMS)
    assert r.status_code == 200
    assert "Niche Research" in r.text and "Channel Research" in r.text
    assert 'href="/niche"' in r.text and 'href="/niche/kenh"' in r.text


def test_channel_research_home(client):
    # Khối ②: danh sách kênh danh bạ theo niche, bấm vào là trang chẩn đoán.
    r = client.get("/niche/kenh", headers=CLAIMS)
    assert r.status_code == 200
    assert "Channel Research" in r.text and "KENH A" in r.text
    assert 'href="/niche/kenh/K-A"' in r.text


def test_modal_theo_module_khong_dinh_nhau(client):
    """User bắt 19/08: modal New Research dính cả nhánh Channel (và ngược lại) —
    mỗi module chỉ render ĐÚNG nhánh form của mình, hết tab chuyển trong modal."""
    ben_niche = client.get("/niche", headers=CLAIMS).text
    assert 'id="nr-niche"' in ben_niche and 'id="nr-kenh"' not in ben_niche
    assert ">New Research<" in ben_niche
    ben_kenh = client.get("/niche/kenh", headers=CLAIMS).text
    assert 'id="nr-kenh"' in ben_kenh and 'id="nr-niche"' not in ben_kenh
    assert ">New channel report<" in ben_kenh
    # form kênh vẫn đủ: select từ danh bạ + file + Diagnose
    assert 'id="nrk-kenh"' in ben_kenh and "KENH A" in ben_kenh
    assert 'id="nrk-file"' in ben_kenh and "Diagnose" in ben_kenh


def test_dieu_huong_tren_dau_khong_con_rail(client):
    # User chốt 18/08 (ảnh 1): thanh trên chỉ TÊN MODULE + dropdown niche + dropdown
    # thị trường + ngày — hết crumb/New report/General; kênh sống bên Channel Research.
    body = client.get("/niche", headers=CLAIMS).text
    assert 'class="nd-top"' in body and "nd-rail" not in body
    assert '<b class="nd-mod">Niche Research</b>' in body
    assert "nd-crumb" not in body                              # hết crumb
    assert 'aria-label="Market"' in body                       # dropdown thị trường
    assert 'href="/niche/kenh/K-A"' not in body                # hết tab kênh ở đây


def test_niche_chua_gan_project(client, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-KHAC", "ten_chuan": "NICHE TRỐNG",
                                  "thi_truong_cua": ["TT-US"]}])
    r = client.get("/niche", headers=CLAIMS, params={"ngach": "N-KHAC"})
    # Từ 18/08 mọi thị trường danh bạ đều có khối riêng — niche chưa gán dự án
    # hiện hướng dẫn New report per-market thay vì một dòng chung.
    assert r.status_code == 200 and "Chưa gán dự án nghiên cứu" in r.text


def test_ngach_chua_chon_thi_truong_hien_huong_dan(client, monkeypatch):
    """Luật 18/08: ngách 0 thị trường (user chưa tick ở General → Niches) →
    hướng dẫn sang General, KHÔNG hiện thông điệp gán-dự-án gây lạc đường."""
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-MOI", "ten_chuan": "NICHE MOI",
                                  "thi_truong_cua": []}])
    r = client.get("/niche", headers=CLAIMS, params={"ngach": "N-MOI"})
    import unicodedata as _u
    body = _u.normalize("NFC", r.text)
    assert r.status_code == 200
    assert _u.normalize("NFC", "chưa chọn thị trường nào") in body
    assert _u.normalize("NFC", "Chưa gán dự án nghiên cứu") not in body


def _danh_ba_co_kenh(tmp_path, monkeypatch):
    """Danh bạ tạm CÓ kênh — conftest mặc định trỏ file không tồn tại (ds_kenh
    rỗng), mà nhánh chip vòng đời chỉ render khi có kênh. Không dựng cái này thì
    test "chip" nào cũng xanh giả."""
    from nen.common import danh_ba
    duong = tmp_path / "danh-ba-co-kenh.db"
    monkeypatch.setenv("DANH_BA_DB", str(duong))
    conn = danh_ba.ket_noi(duong)
    try:
        ng = danh_ba.them_ngach(conn, "Space")
        danh_ba.them_kenh(conn, "Astro", ng, trang_thai="uom_mam")
        conn.commit()
    finally:
        conn.close()
    danh_ba._cache.clear()          # _nap cache theo mtime — ép đọc lại DB mới
    return ng


def test_trang_kenh_song_khi_thieu_bien_nhan_vong_doi(tmp_path, monkeypatch):
    """SỰ CỐ 29/08: template mới + code Python CŨ → 500 cả trang.

    Jinja auto-reload nạp template từ đĩa NGAY, còn tiến trình uvicorn giữ code cũ
    tới lúc restart. Template gọi thẳng `nhan_tt_kenh.get(...)` trong khi biến
    globals chỉ có ở code mới → undefined → Internal Server Error trên máy thật
    (localhost dev không lộ vì ở đó code luôn mới).

    Ghim: thiếu biến thì nhãn LÙI VỀ MÃ THÔ, trang vẫn 200. Mọi lần deploy đều có
    khoảnh khắc này nên đây là hành vi bắt buộc, không phải phòng xa.

    ĐÃ KIỂM test này BẮT ĐƯỢC LỖI THẬT: gỡ `| default({}, true)` trong macro
    `nhan_vong_doi` thì test đỏ (500)."""
    from fastapi.testclient import TestClient

    from src.main import app, templates
    _danh_ba_co_kenh(tmp_path, monkeypatch)
    monkeypatch.setitem(templates.env.globals, "nhan_tt_kenh", None)   # mô phỏng code cũ
    c = TestClient(app, headers={"X-Remote-User": "bot", "X-Remote-Level": "5",
                                 "X-Remote-Role": "owner"},
                   raise_server_exceptions=False)
    r = c.get("/niche/kenh")
    assert r.status_code == 200
    assert "uom_mam" in r.text            # lùi về mã thô, KHÔNG vỡ trang


def test_chip_vong_doi_hien_nhan_dep_khi_du_bien(tmp_path, monkeypatch):
    """Mặt còn lại: đủ biến thì hiện NHÃN người đọc được, không phải mã thô."""
    from fastapi.testclient import TestClient

    from nen.common.danh_ba import NHAN_TRANG_THAI_KENH
    from src.main import app
    _danh_ba_co_kenh(tmp_path, monkeypatch)
    c = TestClient(app, headers={"X-Remote-User": "bot", "X-Remote-Level": "5",
                                 "X-Remote-Role": "owner"})
    r = c.get("/niche/kenh")
    assert r.status_code == 200
    assert NHAN_TRANG_THAI_KENH["uom_mam"] in r.text      # 'Incubating'
    assert 'class="tt-chip tt-uom_mam"' in r.text
