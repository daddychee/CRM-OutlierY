"""Neo giong day va dung nhip (C3b — Dot 2, 22/08/2026).

Van an toan quan trong nhat: KHONG lam day bang transcript tho. Bai hoc 16/07
(CLAUDE.md) ghi ro user da BAC BO viec dung lai ho so tu corpus transcript vi
van ra "coc loc". Module nay chi THEM mau van THAT (co dau cau) vao prompt luc
viet, khong ghi de profile.json, khong doi mot target nao.
"""
from voiceprofile import chon_neo


VAN_NGUOI = (
    "The market opens before dawn, when the air still carries the cold of the river. "
    "Vendors set out their crates in the half dark. Nobody hurries. A woman arranges "
    "tomatoes into a pyramid that will collapse twice before the sun is properly up, "
    "and she will build it again both times without complaint, because this is simply "
    "what the morning asks of her. By seven the street is loud. By nine it is over.\n\n"
    "Further along, the bread stalls. Flour dusts everything within arm's reach. "
    "The baker talks while he works, and he works fast. He has done this for thirty "
    "years. His hands know the dough better than he does, which is a thing he says "
    "himself, laughing, as though it were a small betrayal.\n\n"
    "What surprises visitors is the quiet underneath all that noise. People argue "
    "about prices, then stand together drinking coffee. The argument was not the "
    "point. The coffee was.\n\n"
    "Winter changes the rhythm entirely. Stalls close by two. The river fog does not "
    "lift some days, and the whole street works inside a soft grey box, calling to "
    "each other across it. You learn to recognise people by voice before face.\n\n"
    "By March the light returns and everything shifts again, earlier openings, longer "
    "afternoons, the same tomatoes stacked into the same doomed pyramid.\n\n"
    "None of this appears in the guidebooks, which is probably for the best. A market "
    "that knows it is being watched stops behaving like a market.\n"
)

TRANSCRIPT_THO = (
    "imagine a country where the winters last half the year and the people are calm "
    "about it they wake up early they go to work they come home and nobody complains "
    "about the cold because complaining does not make the cold go away this is just "
    "how life works there and once you see it you understand something about the "
    "place that no statistic will tell you about how people build a life around a "
    "climate instead of fighting it every single day of their lives forever "
) * 6


def test_chon_neo_khop_nhip_corpus_hon_mau_lech():
    """Muc dich cua module: neo phai KHOP NHIP corpus, khong chi day hon.

    Do that 22/08: 3 mau cu cua A013 co 33,3% cau dai trong khi corpus that chi
    9,3% — model bi chi vao mot cai dich khong phai nhip cua tac gia.
    """
    r = chon_neo.chon([VAN_NGUOI], muc_tieu_tu=200)
    assert r["neo"], r["ly_do"]
    # mot tap mau LECH co chu dich: chi lay cau dai nhat
    cau = sorted(chon_neo._cau(VAN_NGUOI), key=lambda c: -len(c.split()))[:3]
    lech_mau = chon_neo._lech(chon_neo.nhip(" ".join(cau)), r["nhip_corpus"])
    lech_neo = chon_neo._lech(r["nhip_neo"], r["nhip_corpus"])
    assert lech_neo < lech_mau


def test_khong_lam_day_bang_transcript_tho():
    """Corpus toan transcript chua don dau cau -> TU CHOI, noi ro ly do.

    Lam day bang van khong dau cau la day model viet khong dau cau. Giu neo cu
    con hon lam hong them.
    """
    r = chon_neo.chon([TRANSCRIPT_THO])
    assert r["neo"] == []
    assert "dau cau" in r["ly_do"]


def test_bo_file_tho_giu_file_lanh_trong_cung_corpus():
    """Corpus tron: do GOP che su that, phai loc theo TUNG FILE.

    Ca that A003: do gop ra 9,3 dau ket/1000 (qua nguong) nhung 2/5 file la
    transcript tho 0,1 — loc gop thi 2 file do lot vao neo.
    """
    r = chon_neo.chon([VAN_NGUOI, TRANSCRIPT_THO, VAN_NGUOI])
    assert r["neo"]
    assert r["file_bo_qua"] == 1
    gop = "\n\n".join(r["neo"])
    assert "imagine a country where the winters" not in gop


def test_khong_lay_hai_khoi_trung_noi_dung():
    """Mau trung nhau lam neo thuc te mong hon so tu (benh A011 do 21/08)."""
    r = chon_neo.chon([VAN_NGUOI, VAN_NGUOI], muc_tieu_tu=5000)
    for i, a in enumerate(r["neo"]):
        for b in r["neo"][i + 1:]:
            sa, sb = chon_neo._shingle(a), chon_neo._shingle(b)
            assert len(sa & sb) / len(sa) < chon_neo.TRUNG_LAP


def test_khong_co_corpus_thi_noi_thang_khong_doan():
    for duong in (None, ""):
        r = chon_neo.neo_day(duong)
        assert r["neo"] == [] and r["ly_do"]
    r = chon_neo.neo_day("/khong/co/thu/muc/nay")
    assert r["neo"] == [] and r["ly_do"]


def test_build_voice_block_tran_theo_tong_tu_khong_dem_mau():
    """Tran neo tinh theo TONG TU (C3b), nhung ho so 3 mau van y nguyen hanh vi cu."""
    from voiceprofile.generator import build_voice_block, TRAN_TU_NEO

    ba_mau = {"author": "X", "exemplars": ["mot hai ba bon nam sau bay tam."] * 3}
    khoi = build_voice_block(ba_mau)
    assert khoi.count("[1]") == 1 and "[3]" in khoi          # ca 3 mau vao het

    day = {"author": "X", "exemplars": ["cau nay dai vua phai de dem tu. " * 40] * 20}
    khoi2 = build_voice_block(day)
    so_tu = sum(len(str(e).split()) for e in day["exemplars"]
                if f"[{day['exemplars'].index(e) + 1}]" in khoi2)
    assert len(khoi2.split()) > len(khoi.split())            # day hon that
    assert len(khoi2.split()) < TRAN_TU_NEO * 1.3            # nhung co tran
