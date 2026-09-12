# -*- coding: utf-8 -*-
"""ĐÓNG GÓI KHÔNG ĐƯỢC CHẶN POLL (sự cố 12/09).

Pipeline OldNewbie_US xong lúc 10:29:26, writer viết tầng NGHĨA mất tới 10:35:53
— 6,5 phút. Suốt thời gian đó màn hình Owner ĐỨNG HÌNH ở "Researching… 2023s"
(2023s quy ra đúng 10:29:23, tức giây pipeline kết thúc): trang_thai() gọi
_snapshot() ĐỒNG BỘ bên trong _snapshot_lock, nên mọi lượt poll 3 giây một lần
đều kẹt ở khóa và không lượt nào trả lời được. Owner hỏi "gần 30' rồi không biết
có hỏng gì không" — đúng loại bệnh hệ-im-lặng-khi-đang-làm-việc đã vá hai lần
trong ngày (writer câm, van phòng thủ câm).

HAI LUẬT test ghim:
1. Poll PHẢI trả lời ngay, không chờ đóng gói — dong_goi_nen() đã có sẵn từ 19/08.
2. Trạng thái PHẢI nói ra là đang đóng gói, để UI hiện được tiến độ thay vì để
   người dùng nhìn một con số bất động.
"""
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from src import niche_run
from src.main import app

CLAIMS_L3 = {"X-Remote-User": "leader", "X-Remote-Level": "3"}


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


@pytest.fixture()
def client(tmp_path, monkeypatch):
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"N-TEST": {"TT-US": "Proj_US"}}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    niche_run._da_snapshot.clear()      # registry module-level — dọn giữa các test
    niche_run._dang_dong_goi.clear()
    return TestClient(app)


def _vua_xong(monkeypatch, can: bool = True):
    """Service báo run vừa xong; `can` = ĐĨA nói còn phải đóng gói hay không."""
    monkeypatch.setattr(niche_run.requests, "get",
                        lambda url, **kw: _Resp({"running": False, "has_report": True}))
    monkeypatch.setattr(niche_run, "can_dong_goi", lambda p: can)


def _cho_nen_xong(project: str = "Proj_US", giay: float = 3.0) -> None:
    het = time.perf_counter() + giay
    while niche_run.dang_dong_goi(project) and time.perf_counter() < het:
        time.sleep(0.02)


def test_poll_tra_loi_ngay_trong_luc_dong_goi(client, monkeypatch):
    """Writer thật mất 6,5 phút — poll phải trả lời trong tích tắc, không chờ nó."""
    _vua_xong(monkeypatch)
    dung = threading.Event()
    monkeypatch.setattr(niche_run, "_snapshot", lambda p: dung.wait(3) or True)
    try:
        t0 = time.perf_counter()
        r = client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3).json()
        cho = time.perf_counter() - t0
        assert cho < 1.0, (
            f"poll bị chặn {cho:.1f}s vì đóng gói chạy ĐỒNG BỘ trong _snapshot_lock "
            "— đây chính là 6,5 phút UI đứng hình hôm 12/09")
        assert r["running"] is False and r["has_report"] is True
        assert r.get("dang_dong_goi") is True, (
            "trạng thái không nói đang đóng gói → UI chẳng có gì để hiện ngoài "
            "con số giây đứng yên, người dùng không phân biệt được đang viết hay đã chết")
    finally:
        dung.set()
        _cho_nen_xong()


def test_khong_dong_goi_lai_khi_dia_noi_da_xong(client, monkeypatch):
    """Registry _da_snapshot nằm trong BỘ NHỚ — restart app là mất sạch, nên lượt
    poll ĐẦU TIÊN sau restart tưởng chưa đóng gói bao giờ và chạy lại writer (4 lượt
    LLM tiền thật) rồi GHI ĐÈ báo cáo tốt bằng bản mới. Đo thật 12/09: restart lúc
    10:57:58, lượt poll 10:58:24 châm ngòi writer trong khi can_dong_goi() = False
    và báo cáo đã đóng gói xong từ 10:35:53. Cùng vết 11/09 (vòng đóng gói lặp đốt
    token) — dashboard đã hỏi can_dong_goi từ 19/08, riêng đường poll này thì chưa.

    Nguồn sự thật phải là ĐĨA (can_dong_goi), không phải registry bộ nhớ."""
    _vua_xong(monkeypatch, can=False)      # đĩa: đã đóng gói xong rồi
    goi = []
    monkeypatch.setattr(niche_run, "_snapshot", lambda p: goi.append(p) or True)
    r = client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3).json()
    _cho_nen_xong()
    assert goi == [], ("đĩa đã nói đóng gói xong mà vẫn chạy lại writer — 4 lượt LLM "
                       "tiền thật + ghi đè báo cáo tốt bằng bản kém hơn (vết 11/09)")
    assert r["dang_dong_goi"] is False


def test_dong_goi_xong_thi_het_co_va_chi_chay_mot_lan(client, monkeypatch):
    _vua_xong(monkeypatch)
    goi = []
    monkeypatch.setattr(niche_run, "_snapshot", lambda p: goi.append(p) or True)
    client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3)
    _cho_nen_xong()
    r = client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3).json()
    # hết cờ = JS được phép reload; và đóng gói vẫn đúng MỘT lần dù poll nhiều lượt
    assert r.get("dang_dong_goi") is False
    assert goi == ["Proj_US"]
