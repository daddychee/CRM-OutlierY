# -*- coding: utf-8 -*-
"""Bo KIEM CHUNG KICH BAN DAU RA (21/08/2026): soi ho so + cham 3 nhom tach bach.

Moi fixture o day la van ban TU DUNG — khong dung corpus/kich ban that cua tac gia
(luat A2: khong hard-code du lieu mot tac gia cu the vao tests).
"""
from __future__ import annotations

import pytest

from voiceprofile import deai
from voiceprofile.soi_ho_so import soi_profile

# --- fixture van ban -------------------------------------------------------------
VAN_NGUOI = (
    "The river had been there long before the road. Farmers followed it north each "
    "spring, and the town grew where the water slowed. Nobody planned that. It simply "
    "happened, the way most towns happen, one decision at a time until the decisions "
    "look like a plan. By the time the railway arrived the pattern was already set."
)
VAN_VUN = ("It was cold. Very cold. The men waited. Nobody spoke. The ice held. "
           "Then it broke. They ran. Some fell. The rest kept going. It was over.")
VAN_MAC_MAY = (
    "In today's world, the river plays a crucial role in the region. Let's dive into "
    "the rich tapestry of its history — a testament to human resilience — and delve "
    "into what it means. In conclusion, it is worth noting that the river stands as a "
    "symbol of life."
)


def _profile(exemplars, targets=None, slm=18.0):
    """Ho so toi thieu du cho ca 3 nhom cham."""
    return {
        "author": "Test Author",
        "exemplars": exemplars,
        "quant_features": [{"name": "sentence_len_mean", "value": slm, "baseline": None}],
        "reproduction_targets": targets or {},
    }


# --- NHOM A: dau vet may ---------------------------------------------------------
def test_bat_cum_sao_va_em_dash():
    r = deai.cham_dau_vet_may(VAN_MAC_MAY)
    nhan = {h["nhan"] for h in r["hits"]}
    assert r["so_hit"] >= 5, "bo luat phai bat duoc cac cum LLM kinh dien"
    assert "cum sao" in nhan
    assert r["em_dash_so_luong"] == 2
    assert r["muc"] == "nang"


def test_van_nguoi_khong_bi_bao_dong():
    r = deai.cham_dau_vet_may(VAN_NGUOI)
    assert r["so_hit"] == 0
    assert r["muc"] == "dat"


def test_bat_ky_tu_vo_hinh():
    r = deai.cham_dau_vet_may("Hello​world and﻿ more text here now.")
    assert r["ky_tu_an"] == 2
    assert r["muc"] == "nang"          # ky tu an luon la muc nang


def test_luat_nam_NGOAI_code(tmp_path):
    """Them mot dong CSV lam doi ket qua — KHONG sua .py (bat bien so 1 cua spec)."""
    csv = tmp_path / "luat.csv"
    csv.write_text("mau_regex,nhan,trong_so,goi_y_sua,ghi_chu\n"
                   '"\\bthe river\\b",cum rieng,3,doi cach goi,\n',
                   encoding="utf-8")
    luat = deai.doc_luat(csv)
    assert len(luat) == 1
    assert deai.cham_dau_vet_may(VAN_NGUOI, luat)["so_hit"] == 1


def test_dong_csv_hong_khong_giet_ca_bo_luat(tmp_path):
    csv = tmp_path / "luat.csv"
    csv.write_text("mau_regex,nhan,trong_so,goi_y_sua,ghi_chu\n"
                   '"[unclosed",loi,1,,\n'
                   '"\\briver\\b",ok,1,,\n', encoding="utf-8")
    assert len(deai.doc_luat(csv)) == 1


def test_thieu_file_luat_van_chay(tmp_path):
    assert deai.doc_luat(tmp_path / "khong-co.csv") == []


# --- NHOM B: nhip ----------------------------------------------------------------
def test_phan_vun_hon_giong_tac_gia():
    p = _profile([VAN_NGUOI])
    r = deai.cham_nhip(VAN_VUN, p, {"do_duoc": True})
    assert r["chuan"] is not None
    assert any("VUN HON" in n for n in r["nhan_xet"])
    assert any("liet ke" in n for n in r["nhan_xet"])


def test_khong_co_ho_so_thi_chi_MO_TA_khong_phan_benh():
    """Khong baseline thi khong ket luan — cung luat voi engine chan doan."""
    r = deai.cham_nhip(VAN_VUN, None, None)
    assert r["chuan"] is None
    assert any("MO TA" in n for n in r["nhan_xet"])
    assert not any("VUN HON" in n for n in r["nhan_xet"])


def test_ho_so_hong_thi_khong_lay_lam_chuan():
    """do_duoc=False -> khong duoc dung exemplar cua no lam chuan nhip."""
    p = _profile([VAN_NGUOI])
    assert deai.cham_nhip(VAN_VUN, p, {"do_duoc": False})["chuan"] is None


def test_khong_co_nguong_cv_tuyet_doi():
    """DA THU VA BAC BO: van NGUOI do duoc cv 0,36-0,60. Cam dung cv de phan benh."""
    r = deai.cham_nhip(VAN_NGUOI, _profile([VAN_NGUOI]), {"do_duoc": True})
    assert "burstiness_cv" in r["chi_so"]              # van bao cao nhu so mo ta
    assert not any("cv" in n.lower() for n in r["nhan_xet"])
    assert not hasattr(deai, "CV_MAY")


# --- NHOM C: giong (co cua chan) -------------------------------------------------
_TARGETS = {"ttr": {"target": 0.55, "sd": 0.05}}


def test_ho_so_hong_thi_KHONG_cham_giong():
    """Van chan chinh cua bo nay: cham bang target dung tren corpus hong = phan bay."""
    r = deai.cham_giong(VAN_NGUOI, _profile([VAN_NGUOI], _TARGETS), {"do_duoc": False})
    assert r["trang_thai"] == "khong_du_co_so"
    assert "dau cau" in r["ly_do"]


def test_ho_so_sach_thi_cham_that():
    r = deai.cham_giong(VAN_NGUOI, _profile([VAN_NGUOI], _TARGETS), {"do_duoc": True})
    assert r["trang_thai"] == "da_cham"
    assert 0 <= r["phan_tram"] <= 100


def test_khong_co_target_thi_noi_thang():
    r = deai.cham_giong(VAN_NGUOI, _profile([VAN_NGUOI]), {"do_duoc": True})
    assert r["trang_thai"] == "khong_du_co_so"


# --- Gop: kiem_chung -------------------------------------------------------------
def test_kiem_chung_tra_du_3_nhom_va_ket_luan():
    r = deai.kiem_chung(VAN_MAC_MAY, _profile([VAN_NGUOI], _TARGETS))
    assert set(r) >= {"dau_vet_may", "nhip", "giong", "ho_so", "ket_luan", "so_tu"}
    assert r["ket_luan"], "phai co it nhat mot cau ket luan doc duoc"


def test_kiem_chung_chay_duoc_khi_khong_co_ho_so():
    r = deai.kiem_chung(VAN_NGUOI, None)
    assert r["ho_so"] is None
    assert r["giong"]["trang_thai"] == "khong_ho_so"


# --- SOI HO SO -------------------------------------------------------------------
def test_bat_corpus_thieu_dau_cau():
    """Dau van tay that: sentence_len_mean = 1085 (transcript chua don dau cau)."""
    r = soi_profile(_profile([VAN_NGUOI], slm=1085.1))
    assert "corpus_thieu_dau_cau" in r["co"]
    assert r["do_duoc"] is False


def test_bat_neo_mong():
    r = soi_profile(_profile([VAN_NGUOI]))          # ~60 tu << 800
    assert "neo_mong" in r["co"]
    assert r["neo_du"] is False
    assert r["do_duoc"] is True                     # neo mong KHONG lam so do sai


def test_bat_exemplar_trung_lap():
    doan = VAN_NGUOI
    r = soi_profile(_profile([doan, doan + " One more sentence added at the end here."]))
    assert "exemplar_trung_lap" in r["co"]


def test_ho_so_lanh_thi_sach():
    day = " ".join([VAN_NGUOI] * 20)                # > 800 tu, khong trung
    r = soi_profile({"author": "X", "exemplars": [day],
                     "quant_features": [{"name": "sentence_len_mean", "value": 18.0}],
                     "reproduction_targets": _TARGETS})
    assert r["co"] == []
    assert r["do_duoc"] and r["neo_du"]


def test_chi_lay_3_exemplar_dau_dung_nhu_build_voice_block():
    """Neo do phai khop cai THAT SU vao prompt (generator lay [:3])."""
    r = soi_profile(_profile([VAN_NGUOI, VAN_VUN, VAN_MAC_MAY, "x " * 5000]))
    assert r["chi_so"]["exemplar_so_mau"] == 3
    assert r["chi_so"]["exemplar_tong_tu"] < 1000


@pytest.mark.parametrize("van", [VAN_NGUOI, VAN_VUN, VAN_MAC_MAY, "", "   "])
def test_khong_vo_voi_moi_dau_vao(van):
    deai.kiem_chung(van, None)
    deai.do_nhip(van)


# --- CUA CHAN corpus transcript tho (C2) -----------------------------------------
def test_bat_corpus_transcript_tho(tmp_path):
    """Dau van tay that: van ban dai khong dau ket cau -> canh bao co ten file."""
    from voiceprofile.corpus import transcript_warnings
    (tmp_path / "tho.txt").write_text(("so this is the thing about the river " * 40), encoding="utf-8")
    (tmp_path / "sach.txt").write_text((VAN_NGUOI + " ") * 8, encoding="utf-8")
    canh = transcript_warnings(tmp_path)
    assert len(canh) == 1 and "tho.txt" in canh[0]


def test_route_build_chan_truoc_khi_dung_ho_so():
    """/api/build phai goi transcript_warnings TRUOC khi start job, va co duong
    di tiep khi user tick xac nhan (A3: user quyet, nhung phai biet minh quyet gi)."""
    from voiceprofile import server as vp
    src = open(vp.__file__, encoding="utf-8").read()
    i_chan = src.index("xac_nhan_transcript_tho")
    i_start = src.index('_try_start(self._user(), "extractor"')
    assert i_chan < i_start, "cua chan phai dung TRUOC khi khoi dong extractor"
    assert "corpus_transcript_tho" in src


def test_route_kiem_chung_va_soi_ho_so_ton_tai():
    """Ghim 2 duong API cua bo kiem chung — xoa lang le la test do."""
    import contentultimate.server as srv
    src = open(srv.__file__, encoding="utf-8").read()
    assert '"/api/kiem-chung"' in src and '"/api/soi-ho-so"' in src
    assert hasattr(srv, "_kiem_chung") and hasattr(srv, "_soi_kho_ho_so")


def test_khong_nhan_duong_dan_tu_client():
    """Chi nhan MA tac gia — client khong duoc tro server vao file bat ky."""
    import contentultimate.server as srv
    ma, r = srv._kiem_chung({"code": "../../etc/passwd", "text": "x"})
    assert ma == 400 and "khong tim thay" in r["error"]


def test_bao_loi_khi_khong_co_van_ban():
    import contentultimate.server as srv
    assert srv._kiem_chung({})[0] == 400
    assert srv._kiem_chung({"text": "   "})[0] == 400


def test_chan_van_ban_qua_dai():
    import contentultimate.server as srv
    ma, r = srv._kiem_chung({"text": "a b " * 200_000})
    assert ma == 400 and "qua dai" in r["error"]
