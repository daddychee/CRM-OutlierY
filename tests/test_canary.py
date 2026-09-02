# -*- coding: utf-8 -*-
"""P1-M2 CANARY LOGIC (01/09/2026) — trọng tâm Owner chốt: "mọi logic phải được
GỌI TÊN trong từng app và kiểm đều đặn tự động hoặc có nút hard-test bất cứ lúc".

Canary = gọi tính năng THẬT với input mẫu, so KẾT QUẢ với kỳ vọng — bắt ca
"HTTP 200 nhưng kết quả rỗng" (họ bài học nút chia chương Content 30/08) mà
mọi health khác đều mù. Kịch bản khai NGOÀI code: nen/rules/canary/<slug>.json,
mỗi kịch bản một MÃ TÊN LOGIC; kỳ vọng = [đường_json, toán_tử, giá_trị].
Kết quả lưu bền data/canary/<slug>.json; cảnh báo lúc CHUYỂN dung→sai (edge).
"""
import asyncio
import json
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import Response as FResponse

from nen.common import canary

# ---------- resolver + toán tử (hàm thuần) ----------

def test_lay_duong_json_long_va_tim_theo_ten():
    d = {"trang_thai": "ok",
         "mo_dun": [{"ten": "kho", "trang_thai": "ok", "so": 157},
                    {"ten": "llm", "trang_thai": "canh_bao"}]}
    assert canary._lay(d, "trang_thai") == "ok"
    assert canary._lay(d, "mo_dun.0.ten") == "kho"
    # tìm phần tử list theo trường ten — thứ tự module đổi không vỡ kịch bản
    assert canary._lay(d, "mo_dun.ten=llm.trang_thai") == "canh_bao"
    assert canary._lay(d, "khong.co") is None


def test_kiem_cac_toan_tu():
    assert canary._kiem("ok", "==", "ok")
    assert canary._kiem("canh_bao", "!=", "loi")
    assert canary._kiem(157, ">=", 100)
    assert canary._kiem([1, 2, 3], "len>=", 2)
    assert not canary._kiem([], "len>=", 1)
    assert canary._kiem("157 point / 19 tài liệu", "chua", "point")


# ---------- chạy kịch bản với app stub thật ----------

TRANG_THAI = {"chuong": 2}   # stub đổi được giữa các test


@pytest.fixture(scope="module")
def stub():
    app = FastAPI()

    @app.get("/api/suc-khoe")
    async def sk():
        return {"trang_thai": "ok",
                "mo_dun": [{"ten": "kho", "trang_thai": "ok"}]}

    @app.post("/api/py-split")
    async def split():
        # mô phỏng đúng bệnh: HTTP 200 nhưng số chương tùy TRANG_THAI
        return {"chuong": [{"i": i} for i in range(TRANG_THAI["chuong"])]}

    @app.get("/api/no")
    async def no():
        return FResponse("chet", status_code=500)

    sv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0,
                                       log_level="warning"))
    t = threading.Thread(target=sv.run, daemon=True)
    t.start()
    for _ in range(50):
        if sv.started:
            break
        time.sleep(0.1)
    yield sv.servers[0].sockets[0].getsockname()[1]
    sv.should_exit = True
    t.join(timeout=5)


@pytest.fixture()
def san(tmp_path, monkeypatch, stub):
    luat = tmp_path / "rules"
    luat.mkdir()
    (luat / "stub-app.json").write_text(json.dumps({"kich_ban": [
        {"ma": "suc-khoe-kho", "ten": "Kho vector khỏe",
         "method": "GET", "duong": "/api/suc-khoe",
         "cho": [["mo_dun.ten=kho.trang_thai", "==", "ok"]]},
        {"ma": "chia-chuong", "ten": "Chia outline ra chương",
         "method": "POST", "duong": "/api/py-split", "body": {"outline": "mẫu"},
         "cho": [["chuong", "len>=", 2]]},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CANARY_LUAT_DIR", str(luat))
    monkeypatch.setenv("CANARY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(canary, "_cong_cua",
                        lambda slug: stub if slug == "stub-app" else None)
    TRANG_THAI["chuong"] = 2
    return tmp_path


def test_chay_app_dung_het_va_luu_ben(san):
    kq = asyncio.run(canary.chay_app("stub-app"))
    assert [k["ket_qua"] for k in kq["kich_ban"]] == ["dung", "dung"]
    # lưu bền — UI đọc lại được sau restart
    luu = json.loads((san / "data" / "stub-app.json").read_text(encoding="utf-8"))
    assert luu["kich_ban"][0]["ma"] == "suc-khoe-kho" and luu["luc"]


def test_ket_qua_rong_la_sai_logic_kem_chi_tiet(san):
    """Đúng bệnh chia chương: HTTP 200 nhưng 0 phần tử → 'sai' + kỳ-vọng↔thực-tế."""
    TRANG_THAI["chuong"] = 0
    kq = asyncio.run(canary.chay_app("stub-app"))
    cc = [k for k in kq["kich_ban"] if k["ma"] == "chia-chuong"][0]
    assert cc["ket_qua"] == "sai"
    assert "len>=" in cc["chi_tiet"] and "0" in cc["chi_tiet"]


def test_endpoint_500_la_loi_khong_giet_luot_chay(san, monkeypatch):
    luat = san / "rules" / "stub-app.json"
    d = json.loads(luat.read_text(encoding="utf-8"))
    d["kich_ban"].append({"ma": "no", "ten": "Nổ", "method": "GET",
                          "duong": "/api/no", "cho": [["x", "==", 1]]})
    luat.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    kq = asyncio.run(canary.chay_app("stub-app"))
    theo_ma = {k["ma"]: k for k in kq["kich_ban"]}
    assert theo_ma["no"]["ket_qua"] == "loi" and "500" in theo_ma["no"]["chi_tiet"]
    assert theo_ma["suc-khoe-kho"]["ket_qua"] == "dung"  # kịch bản khác vẫn chạy


# ---------- route hard-test trên gateway ----------

def test_route_hard_test_chay_ngay_va_doc_ket_qua(san, tmp_path, monkeypatch):
    """Owner bấm là chạy NGAY, không đợi chu kỳ; GET đọc kết quả bền."""
    import bcrypt
    from fastapi.testclient import TestClient

    from nen.iam import iam
    _goc = bcrypt.gensalt
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _goc(4))
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "owner-test", "mk-test", "Ban quản trị", 5,
                      phai_doi_mk=False)
    conn.close()
    from nen.gateway.main import app as gw
    client = TestClient(gw, follow_redirects=False)
    client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})

    r = client.post("/general/api/canary/stub-app/chay")
    assert r.status_code == 200
    assert [k["ket_qua"] for k in r.json()["kich_ban"]] == ["dung", "dung"]
    r = client.get("/general/api/canary")
    assert r.status_code == 200 and "stub-app" in r.json()
    # slug không có kịch bản → 404 lặng lẽ
    assert client.post("/general/api/canary/khong-co/chay").status_code == 404


def test_route_chan_nguoi_chua_dang_nhap(san, tmp_path, monkeypatch):
    import bcrypt
    from fastapi.testclient import TestClient
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    from nen.gateway.main import app as gw
    client = TestClient(gw, follow_redirects=False)
    r = client.post("/general/api/canary/stub-app/chay")
    assert r.status_code in (303, 401, 403)


# ---------- mở rộng "16 logic = 16 sơ đồ" (02/09) ----------
# Kịch bản thêm trường loai/canh/mo_ta/so_do (UI dùng, runner bỏ qua) +
# lay_chang (số đo chặng THẬT từ body) + chua_kiem (logic gọi tên nhưng chưa
# có đường kiểm — hiện CHƯA trung thực, không bịa) + noi="nen" (route ở gateway
# — kiểm VẾT đọc sổ gọi nền). kiem[i] trong kết quả ↔ cho[i] trong kịch bản.


def test_danh_gia_du_moi_cho_khong_dung_som(san):
    """Mỗi phần tử cho = một trạm trên sơ đồ logic → phải đánh giá HẾT,
    không dừng ở kỳ vọng đầu vỡ; kiem[i] ↔ cho[i] theo thứ tự."""
    luat = san / "rules" / "stub-app.json"
    d = json.loads(luat.read_text(encoding="utf-8"))
    d["kich_ban"] = [{"ma": "nhieu-kiem", "ten": "Nhiều kiểm", "method": "GET",
                      "duong": "/api/suc-khoe",
                      "cho": [["trang_thai", "==", "hong"],      # vỡ
                              ["mo_dun", "len>=", 1],            # đạt
                              ["trang_thai", "==", "cung-hong"]]}]  # vỡ
    luat.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    kq = asyncio.run(canary.chay_app("stub-app"))
    k = kq["kich_ban"][0]
    assert k["ket_qua"] == "sai"
    assert [x["dat"] for x in k["kiem"]] == [False, True, False]
    assert "hong" in k["chi_tiet"]  # chi_tiet vẫn nêu kỳ vọng đầu vỡ


def test_lay_chang_so_do_that(san):
    """lay_chang trích SỐ ĐO TỪNG CHẶNG từ body — panel sơ đồ hiện số thật."""
    luat = san / "rules" / "stub-app.json"
    d = json.loads(luat.read_text(encoding="utf-8"))
    d["kich_ban"] = [{"ma": "co-chang", "ten": "Có chặng", "method": "POST",
                      "duong": "/api/py-split", "body": {},
                      "cho": [["chuong", "len>=", 1]],
                      "lay_chang": [["số chương", "chuong.0.i"]]}]
    luat.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    kq = asyncio.run(canary.chay_app("stub-app"))
    assert kq["kich_ban"][0]["chang"] == [{"nhan": "số chương", "so": 0}]


def test_chua_kiem_hien_trung_thuc_khong_goi(san):
    """Logic chưa có đường kiểm: khai chua_kiem=true (không method/duong/cho)
    → vẫn được GỌI TÊN, kết quả 'chua' — không bịa, không gọi HTTP."""
    luat = san / "rules" / "stub-app.json"
    d = json.loads(luat.read_text(encoding="utf-8"))
    d["kich_ban"] = [{"ma": "serp-tach", "ten": "SERP tách rising",
                      "chua_kiem": True, "loai": "vet",
                      "ghi_chua": "cần route đọc tra_cuu_log"}]
    luat.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert len(canary.doc_kich_ban("stub-app")) == 1   # reader không loại
    kq = asyncio.run(canary.chay_app("stub-app"))
    k = kq["kich_ban"][0]
    assert k["ket_qua"] == "chua" and "tra_cuu_log" in k["chi_tiet"]


def test_noi_nen_goi_cong_gateway(san, stub, monkeypatch):
    """noi='nen' → kịch bản gọi cổng NỀN (CONG_NEN) thay cổng app — dùng cho
    kiểm VẾT đọc sổ gọi nằm ở gateway."""
    monkeypatch.setenv("CONG_NEN", str(stub))          # giả gateway = stub
    monkeypatch.setattr(canary, "_cong_cua", lambda slug: None)  # app KHÔNG có cổng
    luat = san / "rules" / "stub-app.json"
    d = {"kich_ban": [{"ma": "vet-nen", "ten": "Vết ở nền", "method": "GET",
                       "duong": "/api/suc-khoe", "noi": "nen",
                       "cho": [["trang_thai", "==", "ok"]]}]}
    luat.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    kq = asyncio.run(canary.chay_app("stub-app"))
    assert kq["kich_ban"][0]["ket_qua"] == "dung"


def test_edge_canh_bao_khi_chuyen_dung_sang_sai():
    """so_canary là HÀM THUẦN: chỉ báo lúc CHUYỂN (dung→sai/loi, và hồi phục)."""
    cu = {"kich_ban": [{"ma": "a", "ten": "Logic A", "ket_qua": "dung"}]}
    moi_sai = {"kich_ban": [{"ma": "a", "ten": "Logic A", "ket_qua": "sai",
                             "chi_tiet": "0 chương"}]}
    bao = canary.so_canary("app-x", cu, moi_sai)
    assert len(bao) == 1 and "Logic A" in bao[0] and "app-x" in bao[0]
    assert canary.so_canary("app-x", moi_sai, moi_sai) == []   # vẫn sai → im
    bao = canary.so_canary("app-x", moi_sai, cu)
    assert len(bao) == 1 and "hồi phục" in bao[0]
    assert canary.so_canary("app-x", None, cu) == []           # lần đầu → im
