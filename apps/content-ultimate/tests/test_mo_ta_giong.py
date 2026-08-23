# -*- coding: utf-8 -*-
"""Mô tả giọng văn + hướng dẫn dùng (24/08, Owner yêu cầu).

Owner: "cần một đoạn mô tả giọng văn, và hướng dẫn sử dụng: dùng để cho nội dung gì,
set up mood gì, atmosphere ra sao."

Đây là chỗ DUY NHẤT trong author extract mà LLM được nói thành lời — nên van phải
chặt hơn mọi chỗ khác: nó chỉ được diễn giải SỐ ĐO Python đã đo và các đoạn văn
THẬT, không được đẻ ra con số mới.
"""
import pytest

from voiceprofile import mo_ta_giong as MT

_PROFILE = {
    "author": "Test Author",
    "corpus_stats": {"n_works": 6, "n_tokens": 25392, "n_stability_units": 6},
    "quant_features": [
        {"name": "sentence_len_mean", "value": 14.29, "keep": True},
        {"name": "sentence_short_ratio", "value": 0.26, "keep": True},
        {"name": "ttr", "value": 0.41, "keep": True},
    ],
    "discourse_features": {"do_duoc": True, "chieu": {
        "ngoi_thu_hai": {"target": 8.6, "sd": 1.2},
        "cau_hoi": {"target": 0.03, "sd": 0.01},
        "lien_tu_mo_cau": {"target": 0.15, "sd": 0.03},
    }},
    "exemplars": ["The road bent north past the mill. Nobody used it after the trucks "
                  "went south. Grass came back within two winters."],
    "signature_moves": [{"move": "Mở bằng một chi tiết vật lý cụ thể"}],
}


def test_du_lieu_gui_cho_llm_chi_gom_so_da_do_va_van_that():
    d = MT.du_lieu_neo(_PROFILE)
    assert d["so_do"]["tu_moi_cau"] == 14.3          # lam tron cho nguoi doc
    assert d["so_do"]["goi_ban_doc_moi_1000_tu"] == 8.6
    assert d["so_do"]["phan_tram_cau_ngan"] == 26     # ti le -> phan tram
    assert d["doan_mau"], "phai co doan van that lam neo"
    assert "Mở bằng một chi tiết" in " ".join(d["moves"])


def test_prompt_cam_bia_so_va_bat_dung_dung_so_da_do():
    p = MT.build_prompt(MT.du_lieu_neo(_PROFILE), "Test Author")
    assert "14.3" in p and "8.6" in p
    for cam in ("do not invent", "only the numbers"):
        assert cam.lower() in p.lower(), f"prompt thieu van: {cam}"


def test_parse_du_nam_phan():
    raw = {"tom_tat": "Giọng kể điềm tĩnh, câu ngắn.",
           "dung_cho": "Tư liệu, kể chuyện địa lý.",
           "mood": "Trầm, tỉnh táo.",
           "atmosphere": "Không gian rộng, ánh sáng lạnh.",
           "khong_hop": "Quảng cáo giật gân."}
    r = MT.chuan_hoa(raw)
    assert set(r) >= {"tom_tat", "dung_cho", "mood", "atmosphere", "khong_hop"}
    assert all(isinstance(v, str) and v.strip() for v in r.values())


def test_bo_phan_rong_thay_vi_de_chu_lung_lo():
    r = MT.chuan_hoa({"tom_tat": "  ", "dung_cho": "Tư liệu.", "mood": None,
                      "atmosphere": "", "khong_hop": "x"})
    assert "tom_tat" not in r and "mood" not in r and "atmosphere" not in r
    assert r["dung_cho"] == "Tư liệu."


def test_ho_so_chua_do_duoc_thi_KHONG_goi_llm():
    """Van chong bia: corpus mong thi so do chua tin duoc — mo ta dua tren no cung vay."""
    mong = {**_PROFILE, "corpus_stats": {"n_works": 1, "n_tokens": 900, "n_stability_units": 1}}
    goi = []
    r = MT.sinh_mo_ta(mong, llm_json=lambda p, s: goi.append(p) or {})
    assert goi == [], "khong duoc goi model khi ho so chua do duoc"
    assert r["ly_do"] and not r.get("mo_ta")


def test_llm_hong_thi_khong_lam_hong_extract():
    def no(_p, _s):
        raise RuntimeError("API 500")
    r = MT.sinh_mo_ta(_PROFILE, llm_json=no)
    assert not r.get("mo_ta") and "API 500" in r["ly_do"]


def test_sinh_mo_ta_tra_ve_phan_da_chuan_hoa():
    r = MT.sinh_mo_ta(_PROFILE, llm_json=lambda p, s: {
        "tom_tat": "Câu ngắn, nhịp đều.", "dung_cho": "Tư liệu địa lý.",
        "mood": "Trầm.", "atmosphere": "Rộng, lạnh.", "khong_hop": "Hài."})
    assert r["mo_ta"]["tom_tat"] == "Câu ngắn, nhịp đều."
    assert r["mo_ta"]["so_do_neo"]["tu_moi_cau"] == 14.3    # so di kem de doi chieu


def test_khong_nhan_chuoi_qua_dai_tu_llm():
    dai = "x" * 5000
    r = MT.chuan_hoa({"tom_tat": dai})
    assert len(r["tom_tat"]) <= MT.TRAN_KY_TU + 1


def test_khong_tick_thi_khong_chay_buoc_mo_ta():
    """Luat A6: luong cu KHONG duoc tu tieu them mot luot LLM."""
    import inspect
    from voiceprofile import server as vp
    assert inspect.signature(vp._run_extractor).parameters["do_mo_ta"].default is False


def test_route_va_ui_co_duong_mo_ta():
    import pathlib
    from voiceprofile import server as vp
    src = open(vp.__file__, encoding="utf-8").read()
    assert '"do_mo_ta": b.get("mo_ta"' in src, "route phai doc co tu body"
    ui = (pathlib.Path(vp.__file__).parent / "board.html").read_text(encoding="utf-8")
    assert 'id="ex_mota"' in ui and "mo_ta:$('ex_mota').checked" in ui


def test_cat_o_ranh_gioi_cau_khong_cat_giua_tu():
    """Phong ngua: ban sinh that chua cham tran, nhung cham thi phai cat cho gon."""
    cau = "Tư liệu thiên nhiên và môi trường, kể chuyện theo mốc thời gian. "
    r = MT.chuan_hoa({"tom_tat": cau * 20})
    assert len(r["tom_tat"]) <= MT.TRAN_KY_TU
    assert r["tom_tat"].endswith(".") or r["tom_tat"].endswith("…")
    assert not r["tom_tat"].endswith(" ")


def test_khong_cat_khi_van_trong_tran():
    v = "Giọng kể điềm tĩnh, câu ngắn."
    assert MT.chuan_hoa({"mood": v})["mood"] == v


def test_prompt_bat_viet_so_bang_CHU_SO():
    """Ban chay that dau tien: model viet 'muoi bon phay nam lan moi nghin tu' — so
    bang chu doc rat vat trong bao cao. Loi o prompt ('as a person says it out loud')."""
    p = MT.build_prompt(MT.du_lieu_neo(_PROFILE), "X")
    assert "DIGITS" in p and "never spell a number out in words" in p
