# -*- coding: utf-8 -*-
"""SƠ ĐỒ VẬN HÀNH SỐNG per app (02/09/2026 — Owner đặt hàng).

Sơ đồ khai NGOÀI code nen/rules/so_do/<slug>.json:
  {"nut": [{ma, ten, cot, loai?, suc_khoe?|canary?|tuyen?}], "canh": [[tu, den, nhan?]]}
- cot: 0..n — layout theo cột trái→phải (người dùng → tính năng → lõi → ngoài).
- binding trạng thái (UI tô màu SỐNG): suc_khoe=<tên module> / canary=<mã> /
  tuyen=<mã đường truyền>; không binding → nút trung tính.
Thêm/sửa sơ đồ = sửa JSON, không sửa code. API tổng-hợp trả kèm để màn App vẽ.
"""
import json

import pytest

from nen.common import so_do


@pytest.fixture()
def san(tmp_path, monkeypatch):
    d = tmp_path / "so_do"
    d.mkdir()
    (d / "stub-app.json").write_text(json.dumps({
        "nut": [
            {"ma": "team", "ten": "Team", "cot": 0, "loai": "nguoi"},
            {"ma": "hoi-dap", "ten": "Hỏi–đáp", "cot": 1,
             "canary": "tim-kiem-tra-ket-qua"},
            {"ma": "kho", "ten": "Kho vector", "cot": 2, "loai": "kho",
             "suc_khoe": "kho-vector"},
            {"ma": "zai", "ten": "Z.ai", "cot": 3, "loai": "ngoai",
             "tuyen": "z-ai"},
            {"thieu": "ma va ten"},
        ],
        "canh": [["team", "hoi-dap"], ["hoi-dap", "kho"],
                 ["hoi-dap", "zai", "writer"]],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SO_DO_LUAT_DIR", str(d))
    return d


def test_doc_bo_nut_thieu_truong_va_canh_mo_coi(san):
    sd = so_do.doc("stub-app")
    assert [n["ma"] for n in sd["nut"]] == ["team", "hoi-dap", "kho", "zai"]
    # cạnh trỏ nút không tồn tại → bỏ (sửa JSON tay dễ gõ nhầm, không được vỡ UI)
    (san / "stub-app.json").write_text(json.dumps({
        "nut": [{"ma": "a", "ten": "A", "cot": 0}],
        "canh": [["a", "khong-co"]]}, ensure_ascii=False), encoding="utf-8")
    sd = so_do.doc("stub-app")
    assert sd["canh"] == []


def test_khong_co_file_tra_none(san):
    assert so_do.doc("khong-ton-tai") is None


def test_tat_ca_vao_api_tong_hop(san, tmp_path, monkeypatch):
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
    monkeypatch.setattr(gw, "_apify_credit", lambda: None)
    client = TestClient(gw.app, follow_redirects=False)
    client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})
    b = client.get("/general/api/giam-sat/tong-hop").json()
    assert "so_do" in b
    assert [n["ma"] for n in b["so_do"]["stub-app"]["nut"]][0] == "team"


def test_so_do_ai_agent_that_hop_le():
    """Sơ đồ mẫu ai-agent trong repo: mọi binding phải trỏ thứ CÓ THẬT —
    suc_khoe trỏ module app khai, canary trỏ mã trong kịch bản."""
    sd = so_do.doc("ai-agent")
    assert sd, "thiếu nen/rules/so_do/ai-agent.json"
    from nen.common import canary
    ma_canary = {k["ma"] for k in canary.doc_kich_ban("ai-agent")}
    module_thuc = {"kho-vector", "catalog", "llm-writer", "search-canary"}
    for n in sd["nut"]:
        if n.get("canary"):
            assert n["canary"] in ma_canary, n
        if n.get("suc_khoe"):
            assert n["suc_khoe"] in module_thuc, n


def test_moi_canh_kich_ban_phai_co_that_tren_so_do():
    """HỆ KIỂM 02/09 — trạm trên dây tổng hợp logic gắn `canh`. Nếu `canh` trỏ
    dây KHÔNG có trên sơ đồ thì logic đó biến mất khỏi map lặng lẽ (trạm không
    bao giờ hiện) — ghim để sửa sơ đồ/kịch bản là biết ngay."""
    from nen.common import canary
    hong = []
    for slug in canary.cac_slug():
        sd = so_do.doc(slug)
        if not sd:
            continue
        co_canh = {(c[0], c[1]) for c in sd["canh"]}
        co_nut = {n["ma"] for n in sd["nut"]}
        for k in canary.doc_kich_ban(slug):
            canh = k.get("canh")
            if not canh:
                continue
            assert len(canh) == 2, f"{slug}/{k['ma']}: canh phải là [tu, den]"
            tu, den = canh
            if tu not in co_nut or den not in co_nut:
                hong.append(f"{slug}/{k['ma']}: nút {tu}→{den} không có trên sơ đồ")
            elif (tu, den) not in co_canh:
                hong.append(f"{slug}/{k['ma']}: dây {tu}→{den} không có trên sơ đồ")
    assert not hong, "canh trỏ dây không tồn tại:\n" + "\n".join(hong)


def test_kich_ban_khai_du_truong_he_kiem():
    """Logic có `canh` phải khai đủ loai + mo_ta để UI dựng bảng/panel; logic
    `chua_kiem` phải nêu LÝ DO (ghi_chua) — trung thực, không để trống."""
    from nen.common import canary
    thieu = []
    for slug in canary.cac_slug():
        for k in canary.doc_kich_ban(slug):
            if k.get("canh"):
                if k.get("loai") not in ("goi", "vet", "bat_bien"):
                    thieu.append(f"{slug}/{k['ma']}: loai phải goi|vet|bat_bien")
                if not (k.get("mo_ta") or k.get("ghi_chua")):
                    thieu.append(f"{slug}/{k['ma']}: thiếu mo_ta")
            if k.get("chua_kiem") and not k.get("ghi_chua"):
                thieu.append(f"{slug}/{k['ma']}: chua_kiem phải nêu ghi_chua")
    assert not thieu, "\n".join(thieu)


def test_canh_bao_so_do_phu_qua_it_so_voi_app():
    """LƯỚI CHỐNG SÓT (02/09 — Owner bắt được RadarY khai 14 nút trong khi app
    có 80 route): app nhiều đường mà sơ đồ ít nút gần như chắc chắn SÓT MẠCH.
    Không chặn cứng (app khác nhau mật độ khác nhau) — chỉ ghim mức đã rà, để
    lần sau app phình ra là test đỏ và có người đi rà lại."""
    import re
    from pathlib import Path
    from nen.common import so_do

    # trần route/nút đã RÀ THẬT 02/09 — nới trần phải kèm rà lại sơ đồ
    TRAN = 4.0
    goc = Path(__file__).resolve().parents[1] / "apps"
    if not goc.is_dir():
        return
    qua_it = []
    for d in sorted(goc.iterdir()):
        if not d.is_dir():
            continue
        sd = so_do.doc(d.name)
        if not sd:
            continue
        n = 0
        for f in d.rglob("*.py"):
            if ".venv" in str(f) or "test" in f.name:
                continue
            try:
                s = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            n += len(re.findall(r"@(?:app|router)\.(?:get|post|put|delete|patch)\(", s))
        if n and n / len(sd["nut"]) > TRAN:
            qua_it.append(f"{d.name}: {n} route / {len(sd['nut'])} nút "
                          f"= {n/len(sd['nut']):.1f} (trần {TRAN})")
    assert not qua_it, ("sơ đồ có thể đang SÓT MẠCH — rà lại rồi mới nới trần:\n"
                        + "\n".join(qua_it))


def test_gauge_ban_nguyet_khong_dung_large_arc_flag():
    """LỖI UI 02/09 (Owner báo): gauge "Quota YouTube còn" 67% vẽ thành HAI MẨU
    RỜI ở hai đầu thay vì một cung liền.

    Nền gauge là NỬA vòng tròn (M12 64 A52 52 0 0 1 116 64) nên cung giá trị
    không bao giờ quét quá 180° → large-arc-flag phải LUÔN 0. Bản cũ đặt
    `big = pct>50 ? 1 : 0`, bảo trình duyệt vẽ CUNG LỚN tức phần bù, đi vòng
    ngược phía dưới. Càng gần 100% mẩu càng to nên 93% trông "gần đúng" — chính
    vì thế lỗi sống lâu mà không ai bắt; 67% mới lộ hẳn.

    Ghim: khối gauge không được sinh large-arc-flag theo pct."""
    import re
    from pathlib import Path

    goc = Path(__file__).resolve().parents[1]
    s = (goc / "nen" / "gateway" / "templates"
         / "nen_command_center.html").read_text(encoding="utf-8")
    m = re.search(r"function gauge\(el, pct, mau, cap\)\{.*?\n\}", s, re.S)
    assert m, "không tìm thấy hàm gauge — đổi tên thì sửa test này theo"
    ham = m.group(0)

    # mọi lệnh vẽ cung trong hàm phải có large-arc-flag = 0
    cung = re.findall(r"A52 52 0 ([^ ]+) 1", ham)
    assert cung, "không thấy lệnh vẽ cung nào trong hàm gauge"
    for co in cung:
        assert co == "0", (
            f"large-arc-flag = {co!r} — nền là NỬA vòng tròn nên cung không bao "
            "giờ quá 180°; đặt khác 0 là trình duyệt vẽ cung lớn (phần bù) và "
            "gauge vỡ thành hai mẩu rời khi pct > 50")


def test_gauge_viewbox_khit_chan_cung_khong_thua_trang():
    """Owner báo gauge lệch (OCD) 02/09 — ĐO ra: canh giữa NGANG đã đúng
    (svg_x_giua = 0), lệch nằm ở CHIỀU DỌC.

    Nét cung dày 13 + linecap round nên hình thật tràn ±6,5px quanh đường tâm:
    đỉnh y = 64−52−6,5 = 5,5 · chân y = 64+6,5 = 70,5 · cao 65. Bản cũ để
    height 78 → thừa 14px trắng chết dưới đáy, khối gauge bị đẩy lệch lên trong
    panel. Cắt khít xong đo lại: trên 10 / dưới 10 cân nhau.

    Ba số này phải đi cùng nhau — đổi một mà quên hai kia là lệch lại."""
    import re
    from pathlib import Path

    goc = Path(__file__).resolve().parents[1]
    s = (goc / "nen" / "gateway" / "templates"
         / "nen_command_center.html").read_text(encoding="utf-8")

    m = re.search(r'<svg width="128" height="(\d+)" viewBox="([\d. ]+)"', s)
    assert m, "không tìm thấy thẻ svg của gauge"
    cao, vb = int(m.group(1)), [float(x) for x in m.group(2).split()]

    r, cy, net = 52, 64, 13
    dinh, chan = cy - r - net / 2, cy + net / 2
    assert vb[1] == dinh, f"viewBox bắt đầu {vb[1]} — đỉnh cung thật ở {dinh}"
    assert vb[3] == chan - dinh == cao, (
        f"viewBox cao {vb[3]} / svg cao {cao} — chân cung tới {chan} nên phải "
        f"là {chan - dinh}; lệch là thừa/thiếu trắng dưới đáy")

    # số % kéo lên nằm trong lòng cung — margin âm không được vượt chiều cao svg
    mv = re.search(r"\.gauge \.val\{[^}]*margin-top:(-?\d+)px", s)
    assert mv, "không tìm thấy margin-top của .gauge .val"
    assert -cao < int(mv.group(1)) < 0, (
        f"margin-top {mv.group(1)}px không hợp với svg cao {cao}px — "
        "số % sẽ rơi ra ngoài lòng cung")


def test_cache_bat_duoc_ban_moi_khi_ghi_de_ngay_trong_cung_khoanh_khac(san):
    """Lộ ra 02/09 qua test đỏ CHẬP CHỜN (chạy nhanh thì dính, chậm thì thoát).

    Khóa cache cũ chỉ có mtime, mà mtime trên Windows thô — sửa file rồi đọc lại
    ngay trong cùng khoảnh khắc là trúng khóa cũ, trả BẢN CŨ. Đo bản cũ: hỏng
    45/300 lượt (15%). Ngoài đời nghĩa là Owner sửa JSON sơ đồ rồi F5 thấy y
    nguyên, tưởng file không ăn.

    Ghim: ghi đè liên tiếp thì lần đọc sau luôn ra bản MỚI."""
    import json

    hong = 0
    for _ in range(120):
        (san / "nhip.json").write_text(json.dumps({
            "nut": [{"ma": "a", "ten": "A", "cot": 0},
                    {"ma": "b", "ten": "B", "cot": 1}],
            "canh": [["a", "b"]]}), encoding="utf-8")
        so_do.doc("nhip")
        (san / "nhip.json").write_text(json.dumps({
            "nut": [{"ma": "a", "ten": "A", "cot": 0}],
            "canh": [["a", "khong-co"]]}), encoding="utf-8")
        if so_do.doc("nhip")["canh"] != []:
            hong += 1
    assert hong == 0, (
        f"{hong}/120 lượt đọc trúng bản CŨ — khóa cache không phân biệt được "
        "hai lần ghi sát nhau")
