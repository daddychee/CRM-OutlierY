# -*- coding: utf-8 -*-
"""Bao cao qua trinh extract (24/08) — Owner yeu cau: chay xong phai co bao cao.

Bao cao tra loi bon cau hoi ma truoc day phai mo profile.json ra doc tay:
  1. May da doc gi (file nao vao, file nao bi loai, bao nhieu diem do)?
  2. Do duoc gi, va CHIEU NAO TIN DUOC (giu vi on dinh / giu vi bat buoc / chua do duoc)?
  3. Giong nay khac cac giong khac trong kho o cho nao (Delta)?
  4. Cai gi thuc su di vao prompt luc viet?
"""
from voiceprofile import bao_cao
from voiceprofile.corpus import Corpus
from voiceprofile.profile import build_profile

VAN = ("The road bent north past the mill. Nobody used it after the trucks went south. "
       "Grass came back within two winters, and the fence posts went the year after. "
       "You would not know there had been a road at all.\n\n"
       "Then the county paved it again. Nobody could say why. The mill had been gone "
       "for thirty years by then and the trucks were never coming back.\n\n")


def _profile(n=6):
    works = [VAN * 3] * n
    return build_profile("Test Author", "en", "en",
                         Corpus(name="T", works=works, train=works, heldout=works[:1]))


def test_bao_cao_co_du_bon_phan():
    md = bao_cao.bao_cao_extract(_profile())
    for muc in ("Corpus", "Chỉ số giọng", "Lập trường", "đi vào prompt"):
        assert muc in md, f"thieu muc: {muc}"
    assert "Test Author" in md


def test_bao_cao_noi_RO_vi_sao_mot_chieu_duoc_giu():
    md = bao_cao.bao_cao_extract(_profile())
    assert "ổn định" in md and "bắt buộc" in md


def test_ho_so_corpus_mong_thi_bao_cao_canh_bao_len_dau():
    md = bao_cao.bao_cao_extract(_profile(n=1))
    assert "⚠" in md
    dau = md.split("## ")[0] + md.split("## ")[1]
    assert "điểm đo" in dau, "canh bao corpus mong phai o phan dau bao cao"


def test_bao_cao_khong_vo_voi_ho_so_thieu_truong():
    for hs in ({}, {"author": "X"}, {"author": "X", "quant_features": []}):
        md = bao_cao.bao_cao_extract(hs)
        assert isinstance(md, str) and md.strip()


def test_bao_cao_hien_dung_khoi_di_vao_prompt():
    p = _profile()
    md = bao_cao.bao_cao_extract(p)
    from voiceprofile.generator import build_nhip_block
    kh = build_nhip_block(p).strip()
    if kh:
        assert kh.splitlines()[1] in md, "khoi trong bao cao phai la khoi THAT di vao prompt"


def test_bao_cao_kho_gom_moi_ho_so_va_canh_bao_trung():
    from voiceprofile import delta as D
    kho_van = {"A": [VAN * 3], "A_ban_sao": [VAN * 3],
               "B": ["You already knew that. You just did not say it. So here is the part "
                     "you missed, and you missed it because nobody told you to look."]}
    bang = D.xay_bang(kho_van)
    md = bao_cao.bao_cao_kho([{"ma": "A", "ten": "A", "profile": _profile()},
                              {"ma": "A_ban_sao", "ten": "A2", "profile": _profile()},
                              {"ma": "B", "ten": "B", "profile": _profile(n=1)}], bang)
    assert "A_ban_sao" in md and ("trùng" in md or "bản sao" in md)


# --- Tom tat ho so cho UI (24/08, Owner yeu cau) -----------------------------------
def test_tom_tat_ho_so_du_bon_nhom_so():
    """UI can: mức độ · số từ · độ giãn câu · mức độ giống tác giả."""
    from voiceprofile import server as vp
    r = vp._tom_tat_tu_profile(_profile(), ma="A999", bang_delta=None)
    assert r["muc_do"] in ("du", "mong", "chua_do_duoc")
    assert r["tu"] > 0 and r["diem_do"] >= 1
    assert r["nhip"]["do_gian"] is not None      # do gian cau = do lech chuan do dai cau
    assert "tu_moi_cau" in r["nhip"] and "ti_le_cut" in r["nhip"]
    assert "giong" in r


def test_tom_tat_khai_muc_do_theo_diem_do():
    from voiceprofile import server as vp
    assert vp._tom_tat_tu_profile(_profile(n=1), ma="A", bang_delta=None)["muc_do"] == "chua_do_duoc"
    assert vp._tom_tat_tu_profile(_profile(n=6), ma="A", bang_delta=None)["muc_do"] in ("du", "mong")


def test_tom_tat_ho_so_khong_nhan_duong_dan_tu_client():
    """Cung luat voi /api/kiem-chung: client chi gui MA, khong tro server vao file bat ky."""
    from voiceprofile import server as vp
    ma, r = vp._api_ho_so({"ma": "../../etc/passwd"})
    assert ma == 404 and "error" in r


def test_route_ho_so_ton_tai():
    from voiceprofile import server as vp
    src = open(vp.__file__, encoding="utf-8").read()
    assert '"/api/ho-so"' in src, "xoa lang le duong API nay la test do"


def test_con_corpus_thi_khong_canh_bao_neo_mong():
    """Luc viet that, cli thay 3 doan mau bang neo day rut tu corpus — canh bao
    'neo chi 253 tu' o day la sai ngu canh (da sua cung loi trong bao cao .md)."""
    from voiceprofile import server as vp
    p = _profile()
    p["corpus_stats"]["corpus_dir"] = str(__import__("pathlib").Path(__file__).parent)
    r = vp._tom_tat_tu_profile(p, ma="A", bang_delta=None)
    assert r["neo_day"] is True
    assert not any("Neo giọng chỉ" in c for c in r["canh_bao"])


# --- Yeu cau hoan thien ho so (24/08, Owner) ---------------------------------------
# "Phan luu y nay can dua ra yeu cau de hoan thien ho so (neu co)."
# Canh bao MO TA van de; yeu cau noi NGUOI DUNG PHAI LAM GI. Khong phai van de nao
# cung co viec de lam — cai nao khong sua duoc thi khong bia ra viec.
def _tt(profile, **kw):
    from voiceprofile import server as vp
    return vp._tom_tat_tu_profile(profile, ma="A", bang_delta=None, **kw)


def test_corpus_mong_ra_yeu_cau_KEM_SO_TU():
    p = _profile()
    p["corpus_stats"] = {"n_works": 1, "n_tokens": 3726, "n_stability_units": 1}
    yc = _tt(p)["yeu_cau"]
    assert yc, "corpus mong phai co viec de lam"
    assert any("8.274" in x for x in yc), f"phai noi ro can them bao nhieu tu: {yc}"


def test_file_khong_co_dong_trong_ra_yeu_cau_nap_lai():
    p = _profile()
    p["discourse_features"] = {"do_duoc": True, "chieu": {},
                               "canh_bao": ["File corpus không có một dòng trống nào — ..."]}
    yc = _tt(p)["yeu_cau"]
    assert any("dòng trống" in x for x in yc)


def test_transcript_tho_ra_yeu_cau_cham_cau():
    p = _profile()
    p["quant_features"] = [{"name": "sentence_len_mean", "value": 1085.0, "keep": False}]
    yc = _tt(p)["yeu_cau"]
    assert any("chấm câu" in x.lower() for x in yc)


def test_ho_so_sach_thi_KHONG_bia_ra_viec():
    p = _profile(n=8)
    p["corpus_stats"] = {"n_works": 8, "n_tokens": 30000, "n_stability_units": 8}
    assert _tt(p)["yeu_cau"] == []


def test_bao_cao_md_in_muc_yeu_cau():
    from voiceprofile import bao_cao
    p = _profile()
    p["corpus_stats"] = {"n_works": 1, "n_tokens": 3726, "n_stability_units": 1}
    md = bao_cao.bao_cao_extract(p)
    assert "Cần làm để hoàn thiện hồ sơ" in md and "8.274" in md


def test_ui_hien_khoi_yeu_cau_rieng_khoi_luu_y():
    import pathlib
    from voiceprofile import server as vp
    ui = (pathlib.Path(vp.__file__).parent / "board.html").read_text(encoding="utf-8")
    assert 'id="hs_yeucau"' in ui and "Cần làm để hoàn thiện hồ sơ" in ui
    assert "d.yeu_cau" in ui
