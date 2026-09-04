# -*- coding: utf-8 -*-
"""Test màn Overview: ba trạm + việc kế tiếp. Không bịa trạng thái cho quá khứ."""
import pytest

from src import tong_quan


def _tap(duyet=(), full=None, xong=False):
    return {"ma": "LI106", "duyet": list(duyet), "full": full, "xong_duyet": xong}


def test_khong_kich_ban_thi_ghi_viet_ngoai_tool():
    ma, chu, thanh = tong_quan._trang_thai_writing("LI106", None)
    assert (ma, chu, thanh) == ("ngoai_tool", "viết ngoài tool", "trong")


def test_kich_ban_da_chot_hien_ban():
    ma, chu, _ = tong_quan._trang_thai_writing("LI106", {"chot_luc": "2026-09-04", "ban": "v2"})
    assert ma == "da_chot" and chu == "Đã chốt v2"


def test_editing_dem_ban_cho_duyet():
    t = _tap(duyet=[{"trang_thai": "dang_duyet"}, {"trang_thai": "da_duyet"}])
    ma, chu, _ = tong_quan._trang_thai_editing(t)
    assert ma == "dang" and chu == "2 bản · 1 chờ duyệt"


def test_editing_xong_khi_moi_ban_da_duyet():
    t = _tap(duyet=[{"trang_thai": "da_duyet"}], xong=True)
    assert tong_quan._trang_thai_editing(t)[0] == "xong"


def test_publish_chua_dang_thi_gach_ngang_khong_doan():
    assert tong_quan._trang_thai_publish(_tap(), None)[1] == "—"


def test_publish_da_dang_chua_hau_kiem():
    ma, chu, _ = tong_quan._trang_thai_publish(_tap(full={"ma": "x"}), None)
    assert ma == "da_dang" and "chưa hậu kiểm" in chu


def test_loc_tap_dang_san_xuat():
    """Tập hậu kiểm xong = việc đã đóng, không chiếm chỗ Overview."""
    xong = {"tram": {"publish": {"ma": "hau_kiem_xong"}}}
    dang = {"tram": {"publish": {"ma": "da_dang"}}}
    assert not tong_quan.dang_san_xuat(xong) and tong_quan.dang_san_xuat(dang)


@pytest.mark.parametrize("w,e,p,mong", [
    ("cho_duyet", "chua_co", "chua_dang", "→ leader: duyệt kịch bản"),
    ("da_chot", "dang", "chua_dang", "→ leader: duyệt bản dựng đang chờ"),
    ("da_chot", "chua_co", "chua_dang", "→ editor: gen voice rồi nộp RenderY"),
    ("ngoai_tool", "xong", "da_dang", "→ đủ dữ liệu thì chạy hậu kiểm"),
    ("ngoai_tool", "xong", "hau_kiem_xong", "→ content + editor: áp kết luận vào tập sau"),
])
def test_viec_ke_theo_ba_tram(w, e, p, mong):
    assert tong_quan._viec_ke((w, "", ""), (e, "", ""), (p, "", "")) == mong


# ---------- route ----------

from urllib.parse import quote  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402


def _h(ten="an", level=2, actions=""):
    return {"X-Remote-User": ten, "X-Remote-Level": str(level),
            "X-Remote-Dept": quote("Vận hành Sản xuất"), "X-Remote-Actions": actions}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_trang_chu_la_khoi_bon_the(client):
    """Trang chủ dạng khối như Content Ultimate — 4 thẻ ứng 4 tab."""
    r = client.get("/", headers=_h())
    assert r.status_code == 200
    for duong in ["/tong-quan", "/kich-ban", "/danh-sach", "/publish"]:
        assert f'href="{duong}"' in r.text


def test_trang_publish_liet_ke_tap_da_dang(client):
    r = client.get("/publish", headers=_h())
    assert r.status_code == 200 and "Tập đã đăng" in r.text


def test_overview_can_claims(client):
    assert client.get("/tong-quan").status_code == 401


def test_overview_render_vo_reviewy(client):
    r = client.get("/tong-quan", headers=_h())
    assert r.status_code == 200
    chu = r.text
    assert "REVIEW" in chu and "Writing Review" in chu and "Editing Review" in chu
    assert "Tập đang sản xuất" in chu


def test_popup_tra_ve_than_khong_vo(client):
    """Popup bàn giao = /tap/<ma>?popup=1 — CHỈ thân, không kéo theo topnav."""
    kho = __import__("src.kho_video", fromlist=["x"])
    goc = kho.nas_dir() / "xuat"
    goc.mkdir(parents=True, exist_ok=True)
    f = goc / "LI900.mp4"
    f.write_bytes(b"x" * 64)
    rel = f.relative_to(kho.nas_dir().resolve()).as_posix()
    client.post("/api-vr/nas-lien-ket", data={"duong": rel, "ten": "ban dung"},
                headers=_h())
    r = client.get("/tap/LI900?popup=1", headers=_h())
    assert r.status_code == 200
    assert "hai-khoi" in r.text and "topnav" not in r.text


def test_dem_cho_review_chi_dem_ban_chua_ai_xem(client):
    """Con số trên tab Editing = Awaiting review (chưa AI KHÁC người đăng bình
    luận), KHÔNG phải mọi bản chưa Approved — bản đang review dở không phải
    việc đang chờ ai nhặt (đo thật 04/09: 6 chứ không phải 31)."""
    from src.main import _dem_topnav
    kho = __import__("src.kho_video", fromlist=["x"])
    goc = kho.nas_dir() / "xuat"
    goc.mkdir(parents=True, exist_ok=True)
    f = goc / "LI901.mp4"
    f.write_bytes(b"y" * 64)
    rel = f.relative_to(kho.nas_dir().resolve()).as_posix()
    r = client.post("/api-vr/nas-lien-ket", data={"duong": rel, "ten": "ban dung"},
                    headers=_h(ten="hieu"))
    ma = r.json()["ma"]
    truoc = _dem_topnav()["so_cho"]
    # người KHÁC bình luận -> hết là 'đang chờ ai nhặt'
    client.post("/api-vr/binh-luan",
                json={"video_ma": ma, "noi_dung": "sua hook", "ts_giay": 1.0},
                headers=_h(ten="lan"))
    assert _dem_topnav()["so_cho"] == truoc - 1
