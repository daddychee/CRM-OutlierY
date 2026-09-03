# -*- coding: utf-8 -*-
"""B5 giám sát (31/08/2026) — VÒNG GIÁM SÁT NỀN + CẢNH BÁO NGAY.

Tab Applications chỉ đo khi có người mở trang; "báo ngay khi sai logic" cần
một vòng nền trong gateway: mỗi chu kỳ đo dịch vụ + heartbeat, phát cảnh báo
lúc CHUYỂN trạng thái (edge-trigger — tự nhiên chống spam), ghi sổ sự cố bền
qua nhat_ky, đẩy ntfy nếu Owner đặt topic (không topic → chỉ ghi sổ, không nổ).

Luật chuyển trạng thái (nen/common/giam_sat.py::so_sanh — HÀM THUẦN):
- app chết 2 CHU KỲ LIÊN TIẾP mới báo (chống flap 1 nhịp mạng), hồi phục báo lại;
- module deep health chuyển sang 'loi' báo MỘT lần, về ok/canh_bao báo hồi phục;
- heartbeat chuyển sang trễ báo một lần, có nhịp lại báo hồi phục.
"""
import json

from nen.common import canh_bao, giam_sat


def _app(ten, song=True, muc=None, mo_dun=None):
    return {"ten": ten, "song": song, "muc": muc, "mo_dun": mo_dun or []}


def _nhip(ma, ten, tre):
    return {"ma": ma, "ten": ten, "chu_ky_phut": 90, "nhip_cuoi": "x", "tre": tre}


def test_chet_2_chu_ky_moi_bao_va_hoi_phuc():
    tt = {}
    # chu kỳ 1: chết lần đầu — CHƯA báo (chống flap)
    tt, bao = giam_sat.so_sanh(tt, [_app("RadarY", song=False)], [])
    assert bao == []
    # chu kỳ 2: vẫn chết → báo đúng 1 dòng
    tt, bao = giam_sat.so_sanh(tt, [_app("RadarY", song=False)], [])
    assert len(bao) == 1 and "RadarY" in bao[0] and "không trả lời" in bao[0]
    # chu kỳ 3: vẫn chết → KHÔNG lặp lại
    tt, bao = giam_sat.so_sanh(tt, [_app("RadarY", song=False)], [])
    assert bao == []
    # sống lại → báo hồi phục
    tt, bao = giam_sat.so_sanh(tt, [_app("RadarY", song=True)], [])
    assert len(bao) == 1 and "hồi phục" in bao[0]


def test_chet_1_nhip_roi_song_lai_khong_bao_gi():
    tt = {}
    tt, bao = giam_sat.so_sanh(tt, [_app("X", song=False)], [])
    tt, bao2 = giam_sat.so_sanh(tt, [_app("X", song=True)], [])
    assert bao == [] and bao2 == []


def test_module_loi_bao_mot_lan_kem_ten_module():
    tt = {}
    ok = _app("AI Agent", muc="ok")
    loi = _app("AI Agent", muc="loi", mo_dun=[
        {"ten": "kho-vector", "trang_thai": "loi", "chi_tiet": "kho RỖNG"}])
    tt, _ = giam_sat.so_sanh(tt, [ok], [])
    tt, bao = giam_sat.so_sanh(tt, [loi], [])
    assert len(bao) == 1 and "kho-vector" in bao[0]
    tt, bao = giam_sat.so_sanh(tt, [loi], [])
    assert bao == []  # vẫn lỗi → không lặp
    tt, bao = giam_sat.so_sanh(tt, [ok], [])
    assert len(bao) == 1 and "hồi phục" in bao[0]


def test_nhip_tre_bao_mot_lan_roi_hoi_phuc():
    tt = {}
    tt, _ = giam_sat.so_sanh(tt, [], [_nhip("backup-dem", "Backup 19:00", False)])
    tt, bao = giam_sat.so_sanh(tt, [], [_nhip("backup-dem", "Backup 19:00", True)])
    assert len(bao) == 1 and "Backup 19:00" in bao[0] and "trễ" in bao[0]
    tt, bao = giam_sat.so_sanh(tt, [], [_nhip("backup-dem", "Backup 19:00", True)])
    assert bao == []
    tt, bao = giam_sat.so_sanh(tt, [], [_nhip("backup-dem", "Backup 19:00", False)])
    assert len(bao) == 1 and "hồi phục" in bao[0]


# ---------- kênh cảnh báo ----------

def test_khong_topic_thi_khong_goi_mang(monkeypatch):
    monkeypatch.delenv("GIAM_SAT_NTFY_TOPIC", raising=False)
    goi = []
    monkeypatch.setattr(canh_bao, "_post", lambda *a: goi.append(a))
    assert canh_bao.gui("tiêu đề", "nội dung") is False
    assert goi == []


def test_co_topic_thi_gui_dung_khuon(monkeypatch):
    monkeypatch.setenv("GIAM_SAT_NTFY_TOPIC", "outliery-giam-sat-thu")
    goi = []
    monkeypatch.setattr(canh_bao, "_post", lambda url, body: goi.append((url, body)))
    assert canh_bao.gui("🔴 RadarY không trả lời", "chi tiết") is True
    url, body = goi[0]
    d = json.loads(body)
    # chuẩn ntfy JSON publish: POST về gốc, topic nằm TRONG body (khuôn radary)
    assert d["topic"] == "outliery-giam-sat-thu"
    assert d["title"] and "chi tiết" in d["message"]


def test_ntfy_loi_mang_khong_no(monkeypatch):
    """Kênh cảnh báo chết không được giết vòng giám sát — nuốt lỗi, trả False."""
    monkeypatch.setenv("GIAM_SAT_NTFY_TOPIC", "t")
    def _no(*a):
        raise OSError("mạng đứt")
    monkeypatch.setattr(canh_bao, "_post", _no)
    assert canh_bao.gui("x", "y") is False


# ---------- phát cảnh báo = sổ bền + ntfy ----------

def test_phat_ghi_nhat_ky_va_goi_ntfy(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGS_DIR", str(tmp_path))
    goi = []
    monkeypatch.setattr(canh_bao, "gui", lambda t, n="": goi.append(t) or True)
    giam_sat.phat(["🔴 X không trả lời"])
    assert goi == ["🔴 X không trả lời"]
    logs = list(tmp_path.rglob("*.log"))
    assert logs and "không trả lời" in logs[0].read_text(encoding="utf-8")


def test_health_timeout_noi_THAT_ly_do_khong_bia_ten_module():
    """Sự cố 03/09 (Owner báo): sổ sự cố đầy cặp "AI Agent — module lỗi:
    suc-khoe: không đọc được" / "đã hồi phục", lặp đều mỗi ~10 phút.

    Bệnh THẬT là health chậm quá trần 10s — ai-agent bật rerank, đo được
    15,4–22,9s mỗi lần canary search (embedding 0,09s + Qdrant 0,06s; rerank
    chiếm 99%). Cứ 10 phút cache canary hết hạn là một lượt vượt trần.

    Nhưng cảnh báo lại nói "module suc-khoe không đọc được" — một module KHÔNG
    HỀ TỒN TẠI, do gateway chỉ đặt muc='loi' rồi để so_sanh dựng chuỗi mặc định.
    Người đọc đi tìm nhầm chỗ. Giờ gateway ghi rõ loại lỗi vào mo_dun.

    Ghim: khi có mo_dun thật thì cảnh báo dùng nó, không rơi về chuỗi bịa."""
    tt = {}
    ok = _app("AI Agent", muc="ok")
    het_gio = _app("AI Agent", muc="loi", mo_dun=[
        {"ten": "health", "trang_thai": "loi", "chi_tiet": "quá 10s không trả lời"}])
    tt, _ = giam_sat.so_sanh(tt, [ok], [])
    tt, bao = giam_sat.so_sanh(tt, [het_gio], [])
    assert len(bao) == 1
    assert "quá 10s không trả lời" in bao[0], bao[0]
    assert "không đọc được" not in bao[0], (
        "vẫn rơi về chuỗi bịa — người đọc sẽ đi tìm module `suc-khoe` không tồn tại")
