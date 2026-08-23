# -*- coding: utf-8 -*-
"""C5 (24/08) — ba tang do con thieu: lap truong, dien ngon, cu phap."""
from voiceprofile import dien_ngon as DN

# Cung mot chu de, ba lap truong khac han: giang giai / ke chuyen / noi thang voi nguoi doc
GIANG = ("The current runs north along the shelf. It carries nutrients from the deep "
         "water toward the surface. The plankton bloom follows it each spring, and the "
         "fish follow the plankton.")
KE = ("I first saw the current from the deck of a trawler in March. I did not know then "
      "what it carried. We had been at sea for nine days and I was tired of looking at water.")
NOI_THANG = ("You have seen this current on a map. You just did not know what it does. "
             "Do you know why the fish arrive in March? Watch what happens next.")


def test_do_dung_ngoi_cua_ba_lap_truong():
    g, k, n = DN.dac_trung(GIANG), DN.dac_trung(KE), DN.dac_trung(NOI_THANG)
    assert n["ngoi_thu_hai"] > g["ngoi_thu_hai"]
    assert k["ngoi_thu_nhat_it"] > g["ngoi_thu_nhat_it"]
    assert g["ngoi_thu_hai"] == 0.0


def test_bat_cau_hoi_va_lien_tu_mo_cau():
    f = DN.dac_trung("But the tide turned. And then it turned again. Why does that matter? "
                     "So we waited.")
    assert f["cau_hoi"] > 0
    assert f["lien_tu_mo_cau"] >= 0.7      # But / And / So mo dau 3 trong 4 cau


def test_dem_cau_moi_doan():
    van = "One. Two. Three.\n\nFour. Five.\n\nSix."
    assert abs(DN.dac_trung(van)["cau_moi_doan"] - 2.0) < 0.01


def test_bat_the_bi_dong_bang_proxy():
    chu_dong = "The storm destroyed the pier. Workers rebuilt it that summer."
    bi_dong = "The pier was destroyed by the storm. It was rebuilt that summer."
    assert DN.dac_trung(bi_dong)["bi_dong"] > DN.dac_trung(chu_dong)["bi_dong"]


def test_van_rong_khong_vo():
    f = DN.dac_trung("")
    assert all(isinstance(v, float) for v in f.values())


# --- Van an toan: KHONG duoc lan vao thang cham giong -----------------------------
def test_khong_lot_vao_quant_features_hay_target():
    """Bai hoc punct_freq_total (23/08): moi chieu them vao thang cham deu pha loang no.
    Tang C5 la CHAN DOAN — no phai nam o khoa rieng."""
    from voiceprofile.corpus import Corpus
    from voiceprofile.profile import build_profile
    works = [GIANG + " " + KE + " " + NOI_THANG] * 4
    p = build_profile("A", "en", "en", Corpus(name="A", works=works, train=works, heldout=[]))
    ten_quant = {f["name"] for f in p["quant_features"]}
    assert not (set(DN.TEN_CHIEU) & ten_quant), "chieu dien ngon lot vao quant_features"
    assert not (set(DN.TEN_CHIEU) & set(p["reproduction_targets"])), "lot vao target cham"
    assert "discourse_features" in p


def test_profile_khai_do_duoc_theo_so_diem_do():
    from voiceprofile.corpus import Corpus
    from voiceprofile.profile import build_profile
    ngan = ["He waited. Nobody came."]
    p = build_profile("A", "en", "en", Corpus(name="A", works=ngan, train=ngan, heldout=[]))
    df = p["discourse_features"]
    assert df["do_duoc"] is False and df["chieu"]["cau_hoi"]["sd"] is None
    assert isinstance(df["chieu"]["cau_hoi"]["target"], float)   # gia tri van do duoc


def test_file_khong_co_dong_trong_thi_khong_khai_do_dai_doan():
    """Do that 24/08: A007/A012 ra 786 cau/doan — do la do dai FILE, khong phai doan."""
    mot_khoi = "One. Two. Three. Four. Five. Six. Seven. Eight."
    hs = DN.ho_so([mot_khoi, mot_khoi, mot_khoi])
    assert hs["canh_bao"], "phai bao khi corpus khong co ranh gioi doan"
    assert hs["chieu"]["cau_moi_doan"]["do_duoc"] is False
    assert not any("Đoạn dài" in c for c in DN.mo_ta(hs))


def test_corpus_co_ranh_doan_thi_khai_binh_thuong():
    van = "One. Two.\n\nThree. Four.\n\nFive. Six."
    hs = DN.ho_so([van, van, van])
    assert not hs["canh_bao"]
    assert any("Đoạn dài" in c for c in DN.mo_ta(hs))


def test_do_cau_moi_doan_tren_VAN_GOC_khong_phai_don_vi_da_cat():
    """Bug 24/08: chunk_by_words noi cac cau bang dau cach nen XOA SACH ranh gioi doan;
    do 'so cau moi doan' tren chunk do thi ho so nao du lon de phai cat chunk cung bi
    bao "file khong co mot dong trong nao" — canh bao oan cho phan lon kho."""
    goc = "Mot. Hai.\n\nBa. Bon.\n\nNam. Sau.\n\nBay. Tam."
    da_cat = ["Mot. Hai. Ba. Bon.", "Nam. Sau. Bay. Tam."]      # ranh gioi doan da mat
    hs = DN.ho_so(da_cat, van_goc=[goc])
    assert not hs["canh_bao"], "van goc CO ranh gioi doan thi khong duoc bao thieu"
    assert abs(hs["chieu"]["cau_moi_doan"]["target"] - 2.0) < 0.01


def test_van_bao_khi_van_goc_that_su_mot_khoi():
    mot_khoi = "Mot. Hai. Ba. Bon. Nam. Sau. Bay. Tam."
    hs = DN.ho_so([mot_khoi], van_goc=[mot_khoi])
    assert hs["canh_bao"]


def test_khong_truyen_van_goc_thi_giu_hanh_vi_cu():
    mot_khoi = "Mot. Hai. Ba. Bon."
    assert DN.ho_so([mot_khoi])["canh_bao"]
