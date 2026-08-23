# -*- coding: utf-8 -*-
"""Khuôn văn: cách mở đầu · cách chuyển đoạn · cách kết · từ đặc trưng (24/08).

Owner chốt: Python đo trên corpus thật, LLM chỉ đặt tên khuôn. Mọi câu mẫu ở đây là
văn thật, kiểm được — cùng luật với signature moves.
"""
from voiceprofile import khuon_van as KV

BAI = [
    "Why does a river run black? Nobody asked that question until the fish began to "
    "vanish. The mill had been there for sixty years.\n\n"
    "But the water told a different story. Downstream, the color faded to brown. "
    "Farmers noticed first.\n\n"
    "And that is how the town learned what it had been drinking.",

    "Why do birds leave a valley they were born in? The answer took forty years to "
    "find. It began with one ornithologist and a notebook.\n\n"
    "But the notebook went missing in 1974. Nobody looked for it. The valley emptied "
    "anyway.\n\n"
    "And that is how a species disappears without anyone writing it down.",

    "Why is the desert getting louder? Engineers measured it for a decade. The sound "
    "comes from the sand itself.\n\n"
    "But sand does not sing on its own. Something has to move it, and something did.\n\n"
    "And that is how a silence turns into a warning.",
]


def test_bat_khuon_mo_dau():
    r = KV.khuon(BAI)
    assert r["mo_dau"]["so_mau"] == 3
    assert all(c.startswith("Why") for c in r["mo_dau"]["cau"])
    assert r["mo_dau"]["ti_le_cau_hoi"] == 100.0        # ca ba bai mo bang cau hoi


def test_bat_cach_chuyen_doan():
    r = KV.khuon(BAI)
    tu = [x["tu"] for x in r["chuyen_doan"]["hay_dung"]]
    assert "but" in tu and "and" in tu


def test_bat_cach_ket():
    r = KV.khuon(BAI)
    assert len(r["ket"]["cau"]) == 3
    assert all("that is how" in c.lower() for c in r["ket"]["cau"])


def test_moi_cau_mau_deu_la_van_that():
    """Van chong bia: cau mau phai trich NGUYEN VAN tu corpus."""
    gop = "\n".join(BAI)
    r = KV.khuon(BAI)
    for c in r["mo_dau"]["cau"] + r["ket"]["cau"]:
        assert c in gop, f"cau mau khong co that trong corpus: {c!r}"


def test_tu_dac_trung_bo_hu_tu_va_cum_pho_thong():
    """distinctive_ngrams hien cho ra 'one of', 'the world', 'the most' — vo dung."""
    r = KV.khuon(BAI)
    tu = [x["cum"] for x in r["tu_dac_trung"]]
    assert not any(c in tu for c in ("one of", "the most", "of the", "and the"))


def test_corpus_rong_khong_vo():
    r = KV.khuon([])
    assert r["mo_dau"]["so_mau"] == 0 and r["ket"]["cau"] == []
    assert r["chuyen_doan"]["hay_dung"] == [] and r["tu_dac_trung"] == []


def test_khong_khai_khuon_khi_qua_it_mau():
    """Ba bai tro len moi noi duoc 'hay mo bang cau hoi'; mot bai thi khong."""
    r = KV.khuon(BAI[:1])
    assert r["mo_dau"]["du_mau"] is False
    assert KV.khuon(BAI)["mo_dau"]["du_mau"] is True


def test_bo_qua_tieu_de_file_khi_lay_cau_mo():
    """Do that 24/08: A014 cho ra 'Real Life in Sweden .' — do la tieu de file."""
    r = KV.khuon(["Real Life in Sweden\n\nWhy does a river run black? Nobody asked that "
                  "question until the fish began to vanish."])
    assert r["mo_dau"]["cau"][0].startswith("Why")


def test_chuyen_doan_khong_dem_mao_tu():
    """Do that: khong loc thi 'the' chiem 17-21% va bang xep hang thanh vo nghia."""
    van = ("Mot cau mo bai that dai de lam doan dau tien o day.\n\n"
           "The mill had been there for sixty years already.\n\n"
           "But the water told a different story downstream.\n\n"
           "The farmers noticed the color before anyone else did.\n\n"
           "But nobody wrote any of it down at the time.")
    tu = [x["tu"] for x in KV.khuon([van, van, van])["chuyen_doan"]["hay_dung"]]
    assert "the" not in tu and "but" in tu


def test_loai_tieu_de_dai_va_chu_thich_google_docs():
    """Hai loai rac gap that trong kho: tieu de khong co dau ket cau, va chu thich [a]."""
    van = ("15 Facts About the Perfect Country That Has a Dark Side Nobody Warns You\n\n"
           "Would you trade 7 years of your life for the air you breathe? Nobody asks.\n\n"
           "The answer came from a study nobody wanted to publish at the time.\n\n"
           "[a]Hiển thị nút Like và Subscriber")
    r = KV.khuon([van, van, van])
    assert r["mo_dau"]["cau"][0].startswith("Would you trade")
    assert not r["ket"]["cau"][0].startswith("[")


# --- Chuong ben trong mot tac pham (Owner 24/08) -----------------------------------
# Owner: "1 tac pham gan 100k tu hoan toan da co the xac dinh van phong, va tac pham
# tieu bieu nhat chinh la giong ghim vao dau khan gia."
# Dung: file Investigate Lewis co 90.373 tu voi CHAPTER ONE... — do theo FILE thi ca
# quyen sach chi cho MOT cau mo bai. Don vi dung phai la LAN MO BAI quan sat duoc.
SACH = ("CHAPTER ONE\nA Secret Origin Story\n\n"
        "The letter arrived on a Tuesday in late autumn. Nobody opened it for a week.\n\n"
        "He read it twice and then put it in a drawer where it stayed for years.\n\n"
        "CHAPTER TWO\nThe Quiet Years\n\n"
        "Money moved through the office in ways nobody could explain afterwards.\n\n"
        "By spring the firm had doubled and nobody asked a single question.\n\n"
        "CHAPTER THREE\nWhat the Auditors Missed\n\n"
        "Nobody checks a number that has always been right before this moment.\n\n"
        "The auditors signed the report and went home for the weekend as usual.\n\n")


def test_mot_tac_pham_co_chuong_van_cho_nhieu_mau():
    r = KV.khuon([SACH])
    assert r["mo_dau"]["so_mau"] == 3, "ba chuong phai cho ba cau mo bai"
    assert r["mo_dau"]["du_mau"] is True
    assert r["ket"]["so_mau"] == 3


def test_tieu_de_chuong_khong_bi_nham_la_cau_mo():
    r = KV.khuon([SACH])
    assert not any(c.startswith("CHAPTER") for c in r["mo_dau"]["cau"])
    assert r["mo_dau"]["cau"][0].startswith("The letter arrived")


def test_khong_co_chuong_thi_van_do_theo_tac_pham():
    van = ("Mot bai khong co chuong nao ca, chi la van xuoi lien mach thoi.\n\n"
           "Doan thu hai cua bai viet nay cung khong co tieu de chuong nao het.")
    r = KV.khuon([van])
    assert r["mo_dau"]["so_mau"] == 1 and r["mo_dau"]["du_mau"] is False


def test_chi_nhan_chuong_khi_co_it_nhat_ba_cai():
    """Mot dong 'CHAPTER ONE' le loi khong bien ca file thanh nhieu chuong."""
    van = "CHAPTER ONE\n\n" + ("Cau van binh thuong trong mot bai viet dai. " * 6)
    assert KV.khuon([van])["mo_dau"]["so_mau"] == 1


def test_bo_don_vi_khong_co_cau_van_nao():
    """Do that 24/08: A002 cho ra "My Witness Statement" — tieu de muc luc — lam mau
    mo bai. Tha it mau con hon mau rac: mau rac di thang vao prompt roi thanh
    "cach mo bai cua tac gia"."""
    muc_luc = "CHAPTER ONE\nMy Witness Statement\n\nWhat Lies Ahead\n\nA Vision\n\n"
    that = ("CHAPTER TWO\n\nThe letter arrived on a Tuesday in late autumn here.\n\n"
            "Nobody opened it for a week after that had happened at all.\n\n")
    r = KV.khuon([muc_luc + that + that.replace("TWO", "THREE")])
    assert all("Witness Statement" not in c for c in r["mo_dau"]["cau"])
    assert r["mo_dau"]["cau"][0].startswith("The letter arrived")
