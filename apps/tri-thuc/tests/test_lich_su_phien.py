"""Test LỆNH 7 (YC4) — cấu trúc PHIÊN: migration idempotent, không mất lượt, D2 giữ."""

import json
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from src.lich_su import (_duong_dan, doc_lich_su, doc_phien, luu_luot, nang_cap_file)


def _tao_file_cu(ten_user, cac_luot):
    p = _duong_dan(ten_user)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cac_luot, ensure_ascii=False), encoding="utf-8")
    return p


LUOT_CU = [
    {"hoi": "hỏi 1", "dap": "đáp 1", "doc_codes": ["KD-1"], "thoi_gian": "T1"},
    {"hoi": "hỏi 2", "dap": "đáp 2", "doc_codes": [], "thoi_gian": "T2"},
    {"hoi": "hỏi 3", "dap": "đáp 3", "doc_codes": ["KD-2"], "thoi_gian": "T3"},
]


def test_migration_goi_1_phien_khong_mat_luot():
    p = _tao_file_cu("cu1", LUOT_CU)
    assert nang_cap_file(p) is True
    cac_phien = doc_phien("cu1")
    assert len(cac_phien) == 1
    assert cac_phien[0]["ten"] == "Lịch sử cũ" and cac_phien[0]["id"] == "lich-su-cu"
    assert cac_phien[0]["luot"] == LUOT_CU                # đủ 3 lượt, nguyên vẹn thứ tự


def test_migration_idempotent_chay_2_lan():
    p = _tao_file_cu("cu2", LUOT_CU)
    assert nang_cap_file(p) is True
    sau_lan_1 = p.read_text(encoding="utf-8")
    assert nang_cap_file(p) is False                      # lần 2: đã dạng mới → không ghi
    assert p.read_text(encoding="utf-8") == sau_lan_1     # byte không đổi, không nhân đôi


def test_doc_lich_su_phang_tuong_thich_cu():
    """File dạng cũ CHƯA migrate vẫn đọc được (nâng trong bộ nhớ) — caller cũ không đổi."""
    _tao_file_cu("cu3", LUOT_CU)
    assert doc_lich_su("cu3") == LUOT_CU


def test_luu_luot_khong_ha_cap_file_da_migrate():
    p = _tao_file_cu("cu4", LUOT_CU)
    nang_cap_file(p)
    luu_luot("cu4", "hỏi 4", "đáp 4", [], "T4")
    tho = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(tho, dict) and "phien" in tho       # vẫn dạng phiên
    assert len(doc_lich_su("cu4")) == 4                   # lượt mới nối vào, không mất gì


def test_file_hong_khong_vo():
    p = _tao_file_cu("hong", [])
    p.write_text("{hỏng json", encoding="utf-8")
    assert doc_phien("hong") == [] and nang_cap_file(p) is False


# ---- (b) lưu lượt theo phien_id + "cuộc trò chuyện mới" thật ----

def test_luu_theo_phien_id():
    luu_luot("p1", "câu A?", "đáp", [], "T1", phien_id="abc-123")
    luu_luot("p1", "câu B?", "đáp", [], "T2", phien_id="abc-123")   # cùng phiên
    luu_luot("p1", "câu C?", "đáp", [], "T3", phien_id="xyz-999")   # PHIÊN MỚI
    cac_phien = doc_phien("p1")
    assert [(p["id"], len(p["luot"])) for p in cac_phien] == [("abc-123", 2), ("xyz-999", 1)]
    assert cac_phien[0]["ten"] == "câu A?"              # tên mặc định = câu ĐẦU của phiên
    assert cac_phien[1]["ten"] == "câu C?"


def test_phien_id_ban_duoc_lam_sach():
    luu_luot("p2", "câu?", "đáp", [], "T1", phien_id="../<hack>/abc")
    assert doc_phien("p2")[0]["id"] == "hackabc"        # chỉ giữ chữ/số/gạch nối


def test_route_stream_gan_dung_phien(tmp_path, monkeypatch):
    import src.main as app_module
    from src.main import app
    from claims_v2 import client_claims  # V2: claims thay users.txt + đăng nhập

    def stream_gia(*a, **k):
        yield {"type": "token", "data": "đáp"}
        yield {"type": "done", "data": {"critic_count": 0, "bi_chan_quyen": False}}

    monkeypatch.setattr(app_module.qa, "hoi_stream", stream_gia)
    c = client_claims(app, "nv", "Kinh doanh", 2)
    c.post("/hoi-dap/stream", data={"question": "câu 1?", "history": "[]",
                                    "phien_id": "phien-a"})
    c.post("/hoi-dap/stream", data={"question": "câu 2?", "history": "[]",
                                    "phien_id": "phien-b"})
    assert [(p["id"], len(p["luot"])) for p in doc_phien("nv")] == [("phien-a", 1),
                                                                    ("phien-b", 1)]


# ---- (c) trang 2 tầng + đổi tên phiên + D2 giữ nguyên từng lượt ----

from src.main import app
from src.lich_su import doi_ten_phien
from claims_v2 import client_claims, client_khach

# V2: claims từ gateway thay users.txt — bảng bộ phận×level giữ nguyên ý cũ.
HO_SO2 = {"sep": ("Kinh doanh", 5), "nv": ("Kinh doanh", 2)}


def _users2(tmp_path, monkeypatch):
    """V2: không còn USERS_FILE — giữ chữ ký để call-site cũ nguyên vẹn (no-op)."""


def _login(ten):
    return client_claims(app, ten, *HO_SO2[ten])


def test_tang_1_list_phien_va_tang_2_chi_tiet(tmp_path, monkeypatch):
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu 1?", "đáp 1", [], "2026-07-19T10:00:00", phien_id="ph-a")
    luu_luot("nv", "câu 2?", "đáp 2", [], "2026-07-19T11:00:00", phien_id="ph-a")
    luu_luot("nv", "câu khác?", "đáp 3", [], "2026-07-19T12:00:00", phien_id="ph-b")
    c = _login("nv")
    r = c.get("/lich-su")
    assert r.status_code == 200
    assert "câu 1?" in r.text and "câu khác?" in r.text      # 2 phiên trong list
    assert "/hoi-dap?phien=ph-a" in r.text                    # bấm thẳng cuộc = mở chat
    r2 = c.get("/lich-su/phien/ph-a")
    assert r2.status_code == 200 and "đáp 1" in r2.text and "đáp 2" in r2.text
    assert "đáp 3" not in r2.text                             # phiên khác không lẫn


def test_d2_van_an_luot_vuot_quyen_trong_phien(tmp_path, monkeypatch):
    """Lượt trích tài liệu Mật min4 (KD-2026-0099 kho mock) — nv level 2 xem chi tiết
    phiên của MÌNH phải bị ẩn lượt đó, lượt thường vẫn hiện (D2 giữ nguyên từng lượt)."""
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu thường?", "đáp thường", ["KD-2026-0042"], "T1", phien_id="ph-x")
    luu_luot("nv", "câu mật?", "đáp mật", ["KD-2026-0099"], "T2", phien_id="ph-x")
    r = _login("nv").get("/lich-su/phien/ph-x")
    assert "đáp thường" in r.text
    assert "đáp mật" not in r.text                            # ẩn lặng lẽ như D2 cũ


def test_doi_ten_phien(tmp_path, monkeypatch):
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu 1?", "đáp", [], "T1", phien_id="ph-a")
    c = _login("nv")
    assert c.post("/lich-su/doi-ten", data={"phien_id": "ph-a",
                                            "ten_moi": "Chủ đề nghỉ phép"}).status_code == 200
    assert "Chủ đề nghỉ phép" in c.get("/lich-su").text
    assert doi_ten_phien("nv", "khong-co", "x") is False


def test_owner_giam_sat_2_tang_nguyen_ban(tmp_path, monkeypatch):
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu mật?", "đáp mật", ["KD-2026-0099"], "T1", phien_id="ph-x")
    c = _login("sep")
    r = c.get("/lich-su/nv")
    assert r.status_code == 200 and "/lich-su/nv/phien/ph-x" in r.text
    r2 = c.get("/lich-su/nv/phien/ph-x")
    assert "đáp mật" in r2.text                               # Owner thấy nguyên bản
    assert _login("nv").get("/lich-su/sep").status_code == 403  # thường xem người khác → 403


# ---- (d) highlight phiên đã-có-lời-giải trên trang list ----

def test_highlight_phien_co_cau_gio_da_giai(tmp_path, monkeypatch):
    """Phiên A: câu kho-thiếu lúc hỏi 0 nguồn — giờ kho mock có KD-2026-0042 (mã MỚI
    ngoài baseline) → 💡. Phiên B: câu chưa-nêu nhưng baseline ĐÃ chứa 0042 (kho
    chưa thêm gì) → không sáng. Phiên C: trả lời được bình thường → không sáng."""
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "lịch nghỉ phép?", "Tài liệu chưa nêu cụ thể điều này.",
             [], "2026-07-19T10:00:00", phien_id="ph-sang")
    luu_luot("nv", "câu chưa nêu khác?", "Tài liệu chưa nêu cụ thể.",
             ["KD-2026-0042"], "2026-07-19T11:00:00", phien_id="ph-thuong")
    luu_luot("nv", "đăng video?", "Đăng khung 19h-21h [KD-2026-0042].",
             ["KD-2026-0042"], "2026-07-19T12:00:00", phien_id="ph-ok")
    r = _login("nv").get("/lich-su")
    assert r.status_code == 200
    # nhãn CHÍNH có 💡 (main); sidebar recents chỉ có badge "mới" + tooltip → không tính
    assert r.text.count("💡 New documents can now answer a question you asked") == 1  # đúng 1 phiên sáng
    # scope vùng nội dung chính (sidebar recents cũng link ph-sang — bỏ qua);
    # nhãn 💡 nằm trong khối .phien.sang của ph-sang, giữa link đó và link kế
    noi_dung = r.text.split('class="noi-dung"', 1)[1]
    khoi_sang = noi_dung.split("/hoi-dap?phien=ph-sang")[1].split("/hoi-dap?phien=")[0]
    assert "New documents can now answer a question you asked" in khoi_sang


# ---- Ý 3: mở cuộc trò chuyện cũ và HỎI TIẾP trong đó ----

def _nap_tu_trang(html: str):
    """Rút JSON NAP nhúng trong trang chat (tojson escape unicode → parse lại)."""
    import json as _json
    tho = html.split("const NAP = ")[1].split(";\n")[0]
    return _json.loads(tho)


def test_mo_cuoc_cu_nap_dung_luot_va_loc_d2(tmp_path, monkeypatch):
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu 1?", "đáp 1", ["KD-2026-0042"], "T1", phien_id="ph-a")
    luu_luot("nv", "câu mật?", "đáp mật", ["KD-2026-0099"], "T2", phien_id="ph-a")  # D2 ẩn
    luu_luot("nv", "câu 3?", "đáp 3", [], "T3", phien_id="ph-a")
    luu_luot("nv", "cuộc khác?", "đáp khác", [], "T4", phien_id="ph-b")

    r = _login("nv").get("/hoi-dap?phien=ph-a")
    assert r.status_code == 200
    nap = _nap_tu_trang(r.text)
    assert nap["phien_id"] == "ph-a"
    assert [l["hoi"] for l in nap["luot"]] == ["câu 1?", "câu 3?"]   # lượt Mật bị ẩn D2
    assert "đáp mật" not in r.text                                   # không rò qua JSON
    # phiên khác không lẫn vào NAP (tên nó hiện trong SIDEBAR là hợp lệ — Ý1)
    assert all(l["hoi"] != "cuộc khác?" for l in nap["luot"])


def test_hoi_tiep_gan_dung_phien_cu_va_truyen_ngu_canh(tmp_path, monkeypatch):
    """Lượt mới vào ĐÚNG phiên cũ (không phiên mới); history của cuộc đó tới pipeline."""
    import json as _json

    import src.main as app_module

    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu 1?", "đáp 1", [], "T1", phien_id="ph-a")

    nhan_duoc = {}

    def stream_gia(cau_hoi, lich_su=None, user=None):
        nhan_duoc["lich_su"] = lich_su
        yield {"type": "token", "data": "đáp tiếp"}
        yield {"type": "done", "data": {"critic_count": 0, "bi_chan_quyen": False}}

    monkeypatch.setattr(app_module.qa, "hoi_stream", stream_gia)
    c = _login("nv")
    history = _json.dumps([{"hoi": "câu 1?", "dap": "đáp 1"}])
    c.post("/hoi-dap/stream", data={"question": "thế còn X?", "history": history,
                                    "phien_id": "ph-a"})

    cac_phien = doc_phien("nv")
    assert [(p["id"], len(p["luot"])) for p in cac_phien] == [("ph-a", 2)]  # KHÔNG phiên mới
    assert cac_phien[0]["luot"][1]["hoi"] == "thế còn X?"
    assert nhan_duoc["lich_su"] == [{"hoi": "câu 1?", "dap": "đáp 1"}]  # ngữ cảnh cuộc đó


def test_phien_la_khong_vo_nap_null(tmp_path, monkeypatch):
    _users2(tmp_path, monkeypatch)
    r = _login("nv").get("/hoi-dap?phien=khong-ton-tai")
    assert r.status_code == 200 and _nap_tu_trang(r.text) is None   # mở như cuộc mới


def test_bam_thang_vao_cuoc_mo_chat(tmp_path, monkeypatch):
    # Chốt lại theo user: thẻ cuộc CHÍNH CHỦ trỏ thẳng /hoi-dap?phien=... (không
    # còn nút Tiếp tục); giám sát người khác vẫn trỏ trang chỉ-đọc.
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu 1?", "đáp 1", [], "T1", phien_id="ph-a")
    c = _login("nv")
    trang = c.get("/lich-su").text
    assert "/hoi-dap?phien=ph-a" in trang                     # bấm cuộc = mở chat
    assert "tiep-tuc" not in trang                            # nút thừa đã gỡ
    assert "Continue this chat" in c.get("/lich-su/phien/ph-a").text
    r = _login("sep").get("/lich-su/nv")
    assert "/lich-su/nv/phien/ph-a" in r.text                 # giám sát: chỉ-đọc
    assert "/hoi-dap?phien=" not in r.text


# ---- Ý 1: sidebar cuộc trò chuyện trên trang chat ----

def test_sidebar_hien_cuoc_va_danh_dau_active(tmp_path, monkeypatch):
    _users2(tmp_path, monkeypatch)
    luu_luot("nv", "câu 1?", "đáp 1", [], "2026-07-20T10:00:00", phien_id="ph-a")
    luu_luot("nv", "câu 2?", "đáp 2", [], "2026-07-20T11:00:00", phien_id="ph-b")
    c = _login("nv")

    trang = c.get("/hoi-dap").text
    assert 'id="thanh-ben"' in trang
    assert "/hoi-dap?phien=ph-a" in trang and "/hoi-dap?phien=ph-b" in trang
    assert 'class="rec-item active"' not in trang       # chưa mở cuộc nào (CSS có chữ tb-active — so theo attribute)

    trang2 = c.get("/hoi-dap?phien=ph-a").text
    # class đứng TRƯỚC href trong thẻ → href của cuộc active nằm ngay SAU dấu active
    active = trang2.split('class="rec-item active"')[1].split('href="')[1].split('"')[0]
    assert active == "/hoi-dap?phien=ph-a"                 # đúng cuộc đang mở được đánh dấu


def test_sidebar_khach_rong_khong_vo():
    from src.main import app

    trang = client_khach(app).get("/hoi-dap").text  # V2: claims thiếu bộ phận ≈ khách
    assert 'id="thanh-ben"' in trang and "No chats yet" in trang


def test_sidebar_cat_gioi_han_nhung_lich_su_day_du_khong_cat(tmp_path, monkeypatch):
    """Hiệu năng: sidebar (base.html qua context processor + /hoi-dap) chỉ tính
    SO_PHIEN_SIDEBAR phiên gần nhất theo thời gian — khỏi tốn Qdrant cho phiên cũ
    không hiện; trang Lịch sử đầy đủ (/lich-su) vẫn liệt kê hết, không cắt."""
    from src.main import SO_PHIEN_SIDEBAR

    _users2(tmp_path, monkeypatch)
    tong = SO_PHIEN_SIDEBAR + 3
    for i in range(tong):
        luu_luot("nv", f"câu {i}?", "đáp", [], f"2026-07-20T{i:02d}:00:00",
                 phien_id=f"ph-{i}")

    c = _login("nv")
    sidebar = c.get("/hoi-dap").text
    for i in range(tong - SO_PHIEN_SIDEBAR, tong):          # N phiên MỚI NHẤT còn đủ
        assert f"/hoi-dap?phien=ph-{i}" in sidebar
    assert "/hoi-dap?phien=ph-0" not in sidebar             # phiên CŨ NHẤT bị cắt khỏi sidebar

    day_du = c.get("/lich-su").text
    assert "/hoi-dap?phien=ph-0" in day_du                  # trang đầy đủ vẫn còn phiên cũ nhất
