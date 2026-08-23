# -*- coding: utf-8 -*-
"""C4 (24/08) — thuoc nhan dang tac gia (Burrows's Delta).

Hai thuoc cu chi noi "khong giong may" (nhom A) va "dung nhip" (nhom B). Ca hai
deu KHONG phan biet noi Derek Muller voi David Attenborough neu hai nguoi tinh co
cung nhip cau. Delta tra loi cau hoi con lai: ban vua viet GIONG AI NHAT trong kho.
"""
import pytest

from voiceprofile import delta as D

# Ba giong khac han nhau ve HU TU (thu Delta thuc su do), khong phai ve chu de.
GIONG_A = [
    "We must ask what the data shows and we must ask it again and again. "
    "We are not certain. We are never certain. But we can measure, and we can "
    "compare, and we can say what the measurement means for us.",
    "We look at the numbers. We ask what they mean. We are careful because we "
    "have been wrong before, and we will be wrong again, and we must say so.",
    "We do not know yet. We suspect. We test what we suspect and we report what "
    "the test says, even when the test says we were wrong about all of it.",
]
GIONG_B = [
    "The bird waits in the shadow of the branch. Below it, the river moves slowly "
    "through the valley, carrying silt from the mountains toward the delta where "
    "the fish gather in their thousands beneath the surface.",
    "The colony sits on the cliff above the water. In the morning the adults leave "
    "for the open sea, and the young remain behind on the rock, waiting through the "
    "long hours until the tide turns again.",
    "The forest floor holds a world beneath the leaves. Insects move through the "
    "soil under the roots of trees that have stood in this valley since long before "
    "the arrival of the first people.",
]
GIONG_C = [
    "So here is the thing. You think you know how it works. You do not. Nobody does. "
    "That is what makes it interesting, and that is why you should keep watching.",
    "Now you might say that is obvious. It is not. You would be surprised how many "
    "people get this wrong, and you would be more surprised by why they get it wrong.",
    "You have seen this before. You just did not notice it. That is the point, and "
    "once you notice it you cannot stop noticing it anywhere you look.",
]
KHO = {"A": GIONG_A, "B": GIONG_B, "C": GIONG_C}


def test_delta_nhan_ra_dung_tac_gia():
    """Van moi cua giong C phai xep hang 1 la C."""
    bang = D.xay_bang(KHO)
    moi = ("You already knew that. You just did not say it out loud. So here is what "
           "you should do now, and you should do it before you forget why it matters.")
    hang = D.xep_hang(moi, bang)
    assert hang[0]["ma"] == "C", f"xep hang sai: {hang}"
    assert hang[0]["delta"] < hang[1]["delta"]


def test_delta_doi_xung_va_khong_am():
    bang = D.xay_bang(KHO)
    d = D.delta_giua("A", "B", bang)
    assert d >= 0 and abs(d - D.delta_giua("B", "A", bang)) < 1e-9


def test_hai_corpus_giong_het_nhau_thi_delta_gan_khong():
    """Ca thuc dung: A003/A008/A011 tro vao CUNG mot corpus — Delta phai lo ra."""
    bang = D.xay_bang({"A": GIONG_A, "A_ban_sao": list(GIONG_A), "B": GIONG_B})
    assert D.delta_giua("A", "A_ban_sao", bang) < 0.05


def test_van_ban_qua_ngan_thi_bao_khong_du_mau():
    bang = D.xay_bang(KHO)
    r = D.xep_hang("We do not know yet.", bang, tra_co=True)
    assert r["du_mau"] is False
    assert r["hang"], "van xep hang, chi la kem tin cay — bao ro chu khong im lang"


def test_can_it_nhat_hai_tac_gia():
    with pytest.raises(ValueError):
        D.xay_bang({"A": GIONG_A})


def test_tu_khong_co_phuong_sai_bi_loai():
    """sd = 0 thi z khong dinh nghia duoc — loai tu do, khong chia cho 0."""
    kho = {"A": ["the cat sat on the mat and the dog sat too"],
           "B": ["the cat sat on the mat and the dog sat too as well indeed"]}
    bang = D.xay_bang(kho, so_tu=50)
    assert all(sd > 0 for sd in bang["sd"].values())
    assert D.delta_giua("A", "B", bang) >= 0


def test_bang_ghi_ra_va_doc_lai_duoc(tmp_path):
    bang = D.xay_bang(KHO)
    p = tmp_path / "bang.json"
    D.ghi_bang(bang, p)
    lai = D.doc_bang(p)
    assert D.xep_hang(GIONG_C[0], lai)[0]["ma"] == "C"


def test_gom_nhom_ban_sao():
    """A003/A008/A011 va A007/A012 la cung corpus — thuoc phai TU chi ra."""
    bang = D.xay_bang({"A": GIONG_A, "A2": list(GIONG_A), "A3": list(GIONG_A),
                       "B": GIONG_B, "C": GIONG_C})
    nhom = D.nhom_ban_sao(bang)
    assert len(nhom) == 1 and nhom[0] == ["A", "A2", "A3"]


def test_khong_gom_nham_hai_giong_that():
    bang = D.xay_bang(KHO)
    assert D.nhom_ban_sao(bang) == []
