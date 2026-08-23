# -*- coding: utf-8 -*-
"""Mô tả giọng: ba khối A+B+C (24/08, Owner chốt sau vòng phản hồi thứ hai).

Vòng 1 chỉ có 5 trường mô tả chung; Owner: "vẫn chưa đủ chi tiết". Thiếu thật sự là
NGUYÊN LIỆU — hồ sơ sẵn có signature moves kèm trích dẫn đã kiểm chứng và cả tập đoạn
văn thật mà bản mô tả không hề dùng. Vòng 2: ba khối theo ba người đọc, và mọi ví dụ
kỹ thuật đều bị Python đối chiếu với kho câu đã đưa cho model.
"""
from voiceprofile import mo_ta_giong as MT

_CAU_THAT = ("Imagine a river that runs completely black. Not dark blue. "
             "Not murky brown. Black.")
_MO_BAI = "Why does a river run black in the middle of a national park?"
_KET_BAI = "And that is how a town learns what it has been drinking all along."

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
    "signature_moves": [{"move": "Anaphoric negation then a blunt one-word correction",
                         "evidence": [_CAU_THAT]}],
}
_KV = {
    "mo_dau": {"du_mau": True, "so_mau": 6, "cau": [_MO_BAI], "ti_le_cau_hoi": 50.0,
               "ti_le_co_so": 33.0, "tu_moi_cau": 12.0},
    "chuyen_doan": {"du_mau": True, "so_doan": 40,
                    "hay_dung": [{"tu": "but", "so_lan": 8, "phan_tram": 20,
                                  "vi_du": "But the water told a different story."}]},
    "ket": {"du_mau": True, "so_mau": 6, "cau": [_KET_BAI]},
    "tu_dac_trung": [{"cum": "parts per billion", "so_lan": 9, "so_van_ban": 4}],
}

_TRA_VE_DU = {
    "dinh_danh": "Người kể đứng cạnh người xem, giải thích bằng chi tiết vật lý.",
    "ky_thuat": [{"ten": "Phủ định dồn rồi chặn bằng một từ", "vi_du": _CAU_THAT}],
    "dung_cho": "Tư liệu môi trường, kể chuyện điều tra có mốc thời gian.",
    "khong_hop": "Quảng cáo giật gân: chỉ 3% câu là câu hỏi trực tiếp.",
    "mood": "Trầm, tỉnh táo.", "atmosphere": "Không gian rộng, ánh sáng lạnh.",
    "cach_mo": "Mở bằng câu hỏi về một hiện tượng vật lý.",
    "cach_chuyen": "Nối đoạn bằng 'But' (20% số đoạn).",
    "cach_ket": "Kết bằng một câu tổng kết mang giọng kể.",
    "tu_nen_dung": "Cụm đo lường cụ thể: 'parts per billion'.",
    "chi_lenh": ["Giữ 14.3 từ mỗi câu", "Gọi 'you' 8.6 lần mỗi 1.000 từ",
                 "26% số câu dưới 8 từ"],
}


def _sinh(tra_ve=None, kv=_KV):
    return MT.sinh_mo_ta(_PROFILE, lambda p, s: (tra_ve or _TRA_VE_DU), kv=kv)


# --- Nguyên liệu đưa cho model -----------------------------------------------------
def test_du_lieu_gom_ca_moves_va_khuon_van():
    d = MT.du_lieu_neo(_PROFILE, _KV)
    assert d["so_do"]["tu_moi_cau"] == 14.3           # làm tròn cho người đọc
    assert d["so_do"]["phan_tram_cau_ngan"] == 26     # tỉ lệ -> phần trăm
    assert d["moves"] and d["moves"][0]["evidence"] == [_CAU_THAT]
    assert d["khuon"]["mo_dau"]["cau"] == [_MO_BAI]


def test_prompt_mang_du_ba_khoi_va_cam_bia():
    p = MT.build_prompt(MT.du_lieu_neo(_PROFILE, _KV), "Test Author")
    for muc in ("dinh_danh", "ky_thuat", "dung_cho", "cach_mo", "cach_ket", "chi_lenh"):
        assert muc in p, f"prompt thieu muc {muc}"
    assert "14.3" in p and "8.6" in p
    assert "OPENING SENTENCES" in p and "CLOSING SENTENCES" in p
    assert "never invent" in p.lower()
    assert "DIGITS" in p and "never spell one out" in p


def test_prompt_khong_co_khuon_thi_khong_bia_muc():
    p = MT.build_prompt(MT.du_lieu_neo(_PROFILE, None), "X")
    assert "OPENING SENTENCES" not in p


# --- Van chống bịa: ví dụ kỹ thuật phải là văn THẬT --------------------------------
def test_loai_ky_thuat_co_vi_du_BIA():
    xau = {**_TRA_VE_DU, "ky_thuat": [
        {"ten": "Kỹ thuật có thật", "vi_du": _CAU_THAT},
        {"ten": "Kỹ thuật bịa", "vi_du": "The mountain wept for the village below it."}]}
    ten = [k["ten"] for k in _sinh(xau)["mo_ta"]["ky_thuat"]]
    assert ten == ["Kỹ thuật có thật"]


def test_loai_trich_qua_ngan():
    xau = {**_TRA_VE_DU, "ky_thuat": [{"ten": "Ngắn quá", "vi_du": "Black."}]}
    assert "ky_thuat" not in _sinh(xau)["mo_ta"]


def test_vi_du_lay_tu_khuon_van_cung_duoc_chap_nhan():
    ok = {**_TRA_VE_DU, "ky_thuat": [{"ten": "Mở bằng câu hỏi", "vi_du": _MO_BAI}]}
    assert _sinh(ok)["mo_ta"]["ky_thuat"][0]["ten"] == "Mở bằng câu hỏi"


# --- Chuẩn hoá ---------------------------------------------------------------------
def test_bo_phan_rong_thay_vi_de_chu_lung_lo():
    r = MT.chuan_hoa({"dinh_danh": "  ", "dung_cho": "Tư liệu.", "mood": None,
                      "atmosphere": "", "khong_hop": "x"})
    assert "dinh_danh" not in r and "mood" not in r and "atmosphere" not in r
    assert r["dung_cho"] == "Tư liệu."


def test_chi_giu_ba_chi_lenh():
    assert MT.chuan_hoa({"chi_lenh": ["a", "b", "c", "d", "e"]})["chi_lenh"] == ["a", "b", "c"]


def test_cat_o_ranh_gioi_cau_khong_cat_giua_tu():
    """Phòng ngừa: bản sinh thật chưa chạm trần, nhưng chạm thì phải cắt cho gọn."""
    cau = "Tư liệu thiên nhiên và môi trường, kể chuyện theo mốc thời gian. "
    r = MT.chuan_hoa({"dung_cho": cau * 20})
    assert len(r["dung_cho"]) <= MT.TRAN_KY_TU
    assert r["dung_cho"].endswith((".", "…")) and not r["dung_cho"].endswith(" ")


def test_khong_cat_khi_van_trong_tran():
    v = "Giọng kể điềm tĩnh, câu ngắn."
    assert MT.chuan_hoa({"mood": v})["mood"] == v


# --- Van an toàn chung -------------------------------------------------------------
def test_ho_so_chua_do_duoc_thi_KHONG_goi_llm():
    mong = {**_PROFILE, "corpus_stats": {"n_works": 1, "n_tokens": 900, "n_stability_units": 1}}
    goi = []
    r = MT.sinh_mo_ta(mong, llm_json=lambda p, s: goi.append(p) or {})
    assert goi == [] and r["ly_do"] and not r.get("mo_ta")


def test_llm_hong_thi_khong_lam_hong_extract():
    def no(_p, _s):
        raise RuntimeError("API 500")
    r = MT.sinh_mo_ta(_PROFILE, llm_json=no)
    assert not r.get("mo_ta") and "API 500" in r["ly_do"]


def test_so_do_neo_di_kem_de_doi_chieu():
    assert _sinh()["mo_ta"]["so_do_neo"]["tu_moi_cau"] == 14.3


def test_bao_cao_md_ra_dung_ba_khoi():
    d = MT.dong_markdown(_sinh()["mo_ta"])
    assert [x for x in d if x.startswith("### ")] == [
        "### Nhận ra giọng", "### Giao việc", "### Viết theo giọng"]
    assert any("Phủ định dồn" in x for x in d)


def test_khong_tick_thi_khong_chay_buoc_mo_ta():
    """Luật A6: luồng cũ KHÔNG được tự tiêu thêm một lượt LLM."""
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


def test_prompt_cam_in_ten_truong_ky_thuat_vao_van_tieng_viet():
    """Bản chạy thật đầu tiên của khối C: 'phan_tram_cau_hoi chỉ 2', 'Da_dang_tu_vung
    0.47' — tên trường trong code lọt vào câu văn cho người đọc."""
    p = MT.build_prompt(MT.du_lieu_neo(_PROFILE, _KV), "X")
    assert "NEVER print a field name" in p
