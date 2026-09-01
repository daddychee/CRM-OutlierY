# -*- coding: utf-8 -*-
"""P1-M3 (01/09/2026) — ĐO ĐƯỜNG TRUYỀN + ring buffer + API tổng hợp command center.

Đường truyền: luật ngoài code nen/rules/duong_truyen.json — kieu 'tcp' (bắt tay
TCP đo ms, KHÔNG tải nội dung, 0 quota) hoặc 'doc' (đọc thử file/thư mục đo ms
— NAS 'còn mount nhưng đơ' lộ ở latency trước khi ai kêu). Vòng giám sát đo mỗi
tick, ring buffer 60 điểm; API /general/api/giam-sat/tong-hop gom một cục cho UI.
"""
import asyncio
import json
import socket
import threading

import pytest

from nen.common import duong_truyen, giam_sat


@pytest.fixture()
def san(tmp_path, monkeypatch):
    # server TCP thật trên cổng ephemeral
    sv = socket.socket()
    sv.bind(("127.0.0.1", 0))
    sv.listen(5)
    cong = sv.getsockname()[1]
    t = threading.Thread(target=lambda: [sv.accept() for _ in range(9)],
                         daemon=True)
    t.start()
    f = tmp_path / "nas" / "x.bin"
    f.parent.mkdir()
    f.write_bytes(b"x" * 8192)
    luat = tmp_path / "duong_truyen.json"
    luat.write_text(json.dumps({"tuyen": [
        {"ma": "tcp-song", "ten": "TCP sống", "kieu": "tcp",
         "dich": f"127.0.0.1:{cong}"},
        {"ma": "tcp-chet", "ten": "TCP chết", "kieu": "tcp", "dich": "127.0.0.1:1"},
        {"ma": "nas", "ten": "NAS thử", "kieu": "doc", "dich": str(f.parent)},
        {"ma": "nas-mat", "ten": "NAS mất", "kieu": "doc",
         "dich": str(tmp_path / "khong-co")},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("DUONG_TRUYEN_LUAT", str(luat))
    yield
    sv.close()


def test_do_cac_tuyen(san):
    kq = {t["ma"]: t for t in asyncio.run(duong_truyen.do_tat_ca())}
    assert kq["tcp-song"]["ok"] is True and kq["tcp-song"]["ms"] >= 0
    assert kq["tcp-chet"]["ok"] is False and kq["tcp-chet"]["ms"] is None
    assert kq["nas"]["ok"] is True and kq["nas"]["ms"] >= 0
    assert kq["nas-mat"]["ok"] is False


def test_tuyen_chet_khong_giet_luot_do(san):
    ds = asyncio.run(duong_truyen.do_tat_ca())
    assert len(ds) == 4  # tuyến chết vẫn có mặt trong kết quả


# ---------- ring buffer trong giám sát ----------

def test_ring_buffer_luu_va_cat_lich_su():
    giam_sat.xoa_lich_su()
    for i in range(70):
        giam_sat.luu_tick({"ts": 1000 + i * 60, "req": i, "loi": 0,
                           "duong_truyen": []})
    ls = giam_sat.lay_lich_su(60)
    assert len(ls) == 60 and ls[-1]["req"] == 69 and ls[0]["req"] == 10


# ---------- API tổng hợp ----------

def test_api_tong_hop_gom_du_khoi(san, tmp_path, monkeypatch):
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
    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: [])
    client = TestClient(gw.app, follow_redirects=False)
    client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})
    r = client.get("/general/api/giam-sat/tong-hop")
    assert r.status_code == 200
    b = r.json()
    for khoa in ("dich_vu", "dem", "nhip", "canary", "duong_truyen",
                 "lich_su", "su_co"):
        assert khoa in b, khoa
    # trang command center render + gate — NẰM TRONG KHUNG GENERAL (Owner 01/09:
    # "hiển thị như các tab trong khối general"), không phải trang trần
    r = client.get("/general/command-center")
    assert r.status_code == 200 and "COMMAND CENTER" in r.text
    assert "Audit Log" in r.text and 'nav class="muc"' in r.text  # nav tab General của nen_base
    # theme TRÙNG cả hệ (Owner 01/09): đọc + ghi khóa outliery_theme, nghe
    # storage event (tab khác đổi là đổi theo), có nút gạt
    assert "outliery_theme" in r.text
    assert '"storage"' in r.text or "'storage'" in r.text
    assert "nutTheme" in r.text
    khach = TestClient(gw.app, follow_redirects=False)
    assert khach.get("/general/command-center").status_code in (303, 401, 403)


def test_tong_hop_noi_that_voi_ket(san, tmp_path, monkeypatch):
    """Owner 01/09: màn Quota phải ĐỒNG NHẤT với tab API Keys — khối `ket` đọc
    thật từ két: khóa (CHE đuôi, không bao giờ key trần) + cấp phát app·việc +
    cấu hình LLM per app/việc."""
    import bcrypt
    from fastapi.testclient import TestClient

    from nen.iam import iam
    from nen.ket_cau_hinh import ket
    _goc = bcrypt.gensalt
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _goc(4))
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "owner-test", "mk-test", "Ban quản trị", 5,
                      phai_doi_mk=False)
    conn.close()
    kc = ket.ket_noi()
    kid_yt = ket.them_api_key(kc, "youtube", "AIzaThuNghiem1234WXYZ")
    ket.luu_cap_phat_viec(kc, "seo-optimize", "trich_kenh", [kid_yt])
    kid_llm = ket.them_api_key(kc, "llm", "sk-thunghiem-5678ABCD",
                               nha=ket.NHA_LLM[0], model="glm-4.5-air")
    ket.luu_cap_phat_viec(kc, "data-analytics", "writer", [kid_llm])
    kc.commit()
    kc.close()

    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: [])
    client = TestClient(gw.app, follow_redirects=False)
    client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})
    b = client.get("/general/api/giam-sat/tong-hop").json()
    tho = str(b)
    assert "AIzaThuNghiem1234WXYZ" not in tho and "sk-thunghiem" not in tho
    khoa = {k["id"]: k for k in b["ket"]["khoa"]}
    assert khoa[kid_yt]["loai"] == "youtube" and khoa[kid_yt]["duoi"] == "WXYZ"
    assert "seo-optimize · trich_kenh" in khoa[kid_yt]["cap_cho"]
    llm = {(d["app"], d["viec"]): d for d in b["ket"]["llm"]}
    assert llm[("data-analytics", "writer")]["model"] == "glm-4.5-air"
    assert llm[("data-analytics", "writer")]["provider"]
