# -*- coding: utf-8 -*-
"""B3 giám sát lan sang data-analytics (31/08/2026) — /api/suc-khoe.

- llm-dien-giai: DA nạp cấu hình LLM từ KÉT qua gateway mỗi lần Analyze; két
  trống vai writer → diễn giải trả MẪU lặng lẽ (cùng họ bệnh ai-agent 31/08).
  Health hỏi két 1 lần (timeout 3s): trống → canh_bao chỉ đường điền két.
- bao-cao: BAO_CAO_DIR đọc được + đếm báo cáo.
"""
from fastapi.testclient import TestClient

from src import main

tc = TestClient(main.app)


def _mo_dun():
    r = tc.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "data-analytics"
    return {m["ten"]: m for m in b["mo_dun"]}


def test_gateway_chet_la_canh_bao_khong_500():
    # conftest trỏ GATEWAY_URL cổng chết — chính là ca này
    md = _mo_dun()
    assert md["llm-dien-giai"]["trang_thai"] == "canh_bao"


def test_ket_trong_vai_writer_canh_bao_chi_duong(monkeypatch):
    monkeypatch.setattr(main, "_hoi_ket_writer", lambda: {"provider": ""})
    md = _mo_dun()
    assert md["llm-dien-giai"]["trang_thai"] == "canh_bao"
    assert "két" in md["llm-dien-giai"]["chi_tiet"]


def test_ket_co_writer_la_ok_kem_model(monkeypatch):
    monkeypatch.setattr(main, "_hoi_ket_writer",
                        lambda: {"provider": "openai_compatible",
                                 "model": "glm-4.5-air"})
    md = _mo_dun()
    assert md["llm-dien-giai"]["trang_thai"] == "ok"
    assert "glm-4.5-air" in md["llm-dien-giai"]["chi_tiet"]


def test_health_hoi_ket_DUNG_TEN_VIEC_nhu_duong_nap_that(monkeypatch):
    """LỖI THẬT 02/09 — BÁO ĐỘNG GIẢ suốt từ 18/08.

    Két tra theo APP × VIỆC-TRONG-HỢP-ĐỒNG. Đường nạp thật xin việc `dien_giai`
    và LUÔN lấy được khóa (đo trên hệ đang chạy: openai_compatible/glm-5), nhưng
    health lại hỏi vai "writer" — tên đã bị bỏ từ 18/08 — nên vĩnh viễn nhận
    provider rỗng và kêu "két chưa có vai writer" trong khi tính năng vẫn sống.

    Ba test trên đều monkeypatch `_hoi_ket_writer` nên KHÔNG chạm cái URL sai —
    vì thế lỗi sống sót. Test này bắt đúng chỗ đó: soi URL health gọi ra, và
    ghim nó phải nằm trong ANH_XA_VAI của chính đường nạp (một nguồn sự thật)."""
    from src import dien_giai

    goi = {}

    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None, headers=None):
            goi["url"], goi["params"] = url, params
            class _R:
                @staticmethod
                def json(): return {"provider": "openai_compatible", "model": "x"}
            return _R()

    monkeypatch.setattr("httpx.Client", lambda *a, **k: _C())
    main._hoi_ket_writer()

    viec = goi["url"].rsplit("/", 1)[-1]
    assert viec in dien_giai.ANH_XA_VAI, (
        f"health hỏi két việc {viec!r} — KHÔNG có trong hợp đồng "
        f"{sorted(dien_giai.ANH_XA_VAI)}; két sẽ trả provider rỗng và health "
        "báo động giả dù tính năng vẫn sống")
    assert goi["params"] == {"app": "data-analytics"}


def test_bao_cao_dir_doc_duoc(tmp_path, monkeypatch):
    (tmp_path / "b1.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BAO_CAO_DIR", str(tmp_path))
    md = _mo_dun()
    assert md["bao-cao"]["trang_thai"] == "ok"
    assert "1" in md["bao-cao"]["chi_tiet"]


def test_ket_dien_SAU_khi_app_chay_thi_analyze_tu_nap_lai(monkeypatch):
    """Cùng bẫy ai-agent 02/09, ở app này còn KÍN HƠN.

    Két chỉ đọc một lần lúc khởi động, mà `_lay_writer` lại cache `_writer`
    vĩnh viễn sau lần Analyze đầu → Owner điền khóa sau khi app đã chạy thì
    diễn giải MẪU đóng băng luôn, không lần restart thì không thoát.

    Ghim: writer đang mock → lần gọi sau tự hỏi lại két và dựng writer thật;
    writer đã thật thì KHÔNG hỏi lại (giữ cache, không bắn GET mỗi lượt).
    Và nhánh này PHẢI có chặn nhịp: đo thật, một lần hỏi két khi gateway không
    với tới tốn 2,5s — không chặn thì gateway chết là mỗi lượt Analyze cõng
    thêm 2,5s, nhân với từng video."""
    from types import SimpleNamespace

    from src import dien_giai

    goi = []
    monkeypatch.setattr(dien_giai, "_writer", SimpleNamespace(mock=True))
    monkeypatch.setattr(dien_giai, "_critics", [])
    monkeypatch.setattr(dien_giai, "_NAP_LAI", {"ts": 0.0})
    monkeypatch.setattr(dien_giai, "nap_cau_hinh_llm", lambda: goi.append(1))
    monkeypatch.setattr(dien_giai, "get_provider",
                        lambda vai: SimpleNamespace(mock=False, model="glm-5"))
    monkeypatch.setattr(dien_giai, "get_critics",
                        lambda: [SimpleNamespace(mock=False)])

    w, _ = dien_giai._lay_writer()
    assert w.mock is False and len(goi) == 1

    # đã thật rồi → không hỏi két nữa
    dien_giai._lay_writer()
    assert len(goi) == 1


def test_hoi_lai_ket_co_chan_nhip_khong_moi_lan_analyze(monkeypatch):
    """Két vẫn trống thì nhánh hỏi-lại phải BỊ CHẶN NHỊP. Đo thật: một lần hỏi
    khi gateway không với tới tốn 2,5s (timeout httpx) — mỗi lượt Analyze cõng
    thêm 2,5s là kiểu chậm không ai truy ra nguyên nhân."""
    from types import SimpleNamespace

    from src import dien_giai

    goi = []
    monkeypatch.setattr(dien_giai, "_writer", SimpleNamespace(mock=True))
    monkeypatch.setattr(dien_giai, "_critics", [])
    monkeypatch.setattr(dien_giai, "_NAP_LAI", {"ts": 0.0})
    monkeypatch.setattr(dien_giai, "nap_cau_hinh_llm", lambda: goi.append(1))
    monkeypatch.setattr(dien_giai, "get_provider",
                        lambda vai: SimpleNamespace(mock=True))   # két vẫn trống
    monkeypatch.setattr(dien_giai, "get_critics", lambda: [])
    for _ in range(4):
        dien_giai._lay_writer()
    assert len(goi) == 1, f"hỏi két {len(goi)} lần — thiếu chặn nhịp"
