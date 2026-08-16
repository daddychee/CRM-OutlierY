"""Test lab do do dai — hieu chinh so ky tu/brief cho tung tac gia.

Chay le:  .venv/bin/python -m pytest tests/test_lengthlab.py -q
Khong dot credit: LLM gia (luat C3).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from voiceprofile.generator import (CHAPTER_MIN_QUALITY, CHAPTER_WARN_CHARS,  # noqa: E402
                                    depth_plan, idea_budget)
from voiceprofile.lengthlab import (LAB_CONFIGS, build_lab_brief,  # noqa: E402
                                    chars_per_brief_of, config_for_target, fit_constants,
                                    guide_table, pick_lab_material, render_guide, run_lab,
                                    sweet_spot_briefs)

# Nguon lieu gia — thay cho cluster that trong runs/ (test khong duoc phu thuoc du lieu may)
MAT = {"run": "test-run", "title": "A Real Topic",
       "briefs": [f"Real cluster brief number {i} with enough words to be developed." for i in range(3)],
       "addons": [f"Attached fact number {i}." for i in range(4)]}

PROFILE = {"author": "Ventures", "exemplars": ["A long sweeping sentence."],
           "signature_moves": [], "reproduction_targets": {}}


def _fake_llm(a: int, b: int, noise=lambda i: 0):
    """LLM gia: viet dung a ky tu/brief + b ky tu/add-on (+ nhieu neu muon)."""
    state = {"i": 0}

    def f(system, user):
        state["i"] += 1
        nb = sum(1 for x in MAT["briefs"] if x[:40] in user)
        na = sum(1 for x in MAT["addons"] if x[:20] in user)
        return "x" * max(1, nb * a + na * b + noise(state["i"]))
    return f


# --- Khop hang so ---------------------------------------------------------------------

def test_khop_dung_hang_so_khi_khong_nhieu():
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=_fake_llm(1408, 98), samples=3, model="glm:glm-5.2")
    assert lab["chars_per_brief"] == 1408
    assert lab["chars_per_addon"] == 98


def test_khop_chiu_duoc_nhieu():
    # Nhieu +-10% quanh gia tri that -> hang so khop van sat
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=_fake_llm(1408, 98, noise=lambda i: (i % 5 - 2) * 140),
                  samples=5, model="glm:glm-5.2")
    assert 1250 <= lab["chars_per_brief"] <= 1570      # +-10%


def test_khop_bo_qua_o_KHONG_add_on():
    """Do that 2026-07-15: cong thuc khop <1 ky tu o cac o CO add-on nhung truot 20% o
    cac o khong add-on (brief ngheo -> LLM tu don chu). Khop chi duoc dung o co add-on."""
    rows = {(2, 0): [9999], (3, 0): [9999],        # rac co y — phai bi bo qua
            (2, 4): [2 * 1408 + 4 * 98], (3, 4): [3 * 1408 + 4 * 98]}
    fit = fit_constants(rows)
    assert fit["chars_per_brief"] == 1408 and fit["chars_per_addon"] == 98


def test_du_lieu_rac_thi_tra_rong_chu_khong_bia_hang_so():
    assert fit_constants({}) == {}
    assert fit_constants({(2, 4): []}) == {}
    assert fit_constants({(2, 4): [10]}) == {}                 # 1 diem, 2 an -> khong khop
    assert fit_constants({(2, 4): [1], (3, 4): [0]}) == {}     # a <= 0 -> tu choi


# --- Guide: bang tra Tac gia - Chapter - Brief - Add on --------------------------------

def test_bang_tra_dung_dinh_dang_user_chot():
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=_fake_llm(1408, 98), samples=3, model="glm:glm-5.2")
    assert len(lab["table"]) == len(LAB_CONFIGS)
    for r in lab["table"]:
        assert set(("author", "chapter", "brief", "addon")) <= set(r)
        assert r["author"] == "Ventures"
        assert r["model"] == "glm:glm-5.2"
    # sap theo do dai chuong tang dan -> user do bang
    assert [r["chapter"] for r in lab["table"]] == sorted(r["chapter"] for r in lab["table"])


def test_bang_tra_ghi_do_dao_dong_de_user_biet_o_nao_dang_tin():
    # o (2,4) on dinh, o (2,0) dao dong manh -> spread_pct phai phan anh
    rows = {(2, 4): [3200, 3210, 3205], (2, 0): [2800, 4300, 3500]}
    t = {(r["brief"], r["addon"]): r for r in guide_table(rows, "V", "m")}
    assert t[(2, 4)]["spread_pct"] < 2
    assert t[(2, 0)]["spread_pct"] > 40


def test_chon_cau_hinh_cho_muc_tieu():
    rows = {(2, 0): [3531], (2, 4): [3207], (3, 0): [3914], (3, 4): [4615]}
    tbl = guide_table(rows, "V", "m")
    assert config_for_target(tbl, 3200)["brief"] == 2       # 3207 gan 3200 nhat
    assert config_for_target(tbl, 3200)["addon"] == 4
    assert config_for_target(tbl, 4600)["brief"] == 3
    assert config_for_target(tbl, 9000)["chapter"] == 4615  # xa nhat van tra o dai nhat
    assert config_for_target([], 3000) is None


def test_hoa_nhau_thi_uu_tien_o_ON_DINH_hon():
    # 2 o cach muc tieu bang nhau -> chon cai dao dong nho hon (do that: brief giau
    # -> LLM bam theo -> +-3%; brief ngheo -> ung tac -> +-22%)
    rows = {(2, 0): [2800, 3200], (3, 4): [2990, 3010]}
    tbl = guide_table(rows, "V", "m")
    assert config_for_target(tbl, 3000)["brief"] == 3


# --- Vung ngot: guide THAT SU cua lab -------------------------------------------------

def test_vung_ngot_suy_ra_tu_hang_so_va_KHAC_nhau_theo_tac_gia():
    """So '2-3 brief' khong phai truc giac — no suy ra tu hang so cua chinh tac gia do."""
    v = sweet_spot_briefs(1408, CHAPTER_MIN_QUALITY, CHAPTER_WARN_CHARS)   # Ventures
    lw = sweet_spot_briefs(1720, CHAPTER_MIN_QUALITY, CHAPTER_WARN_CHARS)  # Lewis
    gon = sweet_spot_briefs(900, CHAPTER_MIN_QUALITY, CHAPTER_WARN_CHARS)  # tac gia viet gon
    assert v == [2]                    # 2x1408=2816 OK; 3x1408=4224 vuot tran 4000
    assert lw == [2]                   # 2x1720=3440 OK; 3x1720=5160 vuot xa
    assert gon == [3, 4]               # viet gon -> chua duoc nhieu brief hon
    assert v != gon                    # dung mot hang so chung la sai cho it nhat mot ben


# --- Noi vao Writer -------------------------------------------------------------------

def test_profile_chua_chay_lab_van_chay_binh_thuong():
    """Khong duoc pha profile cu."""
    assert chars_per_brief_of({}, 1250) == 1250
    assert chars_per_brief_of({"length_lab": {}}, 1250) == 1250
    assert chars_per_brief_of({"length_lab": {"chars_per_brief": 0}}, 1250) == 1250
    assert chars_per_brief_of({"length_lab": {"chars_per_brief": "rac"}}, 1250) == 1250
    assert chars_per_brief_of({"length_lab": {"chars_per_brief": 1720}}, 1250) == 1720


def test_hang_so_rieng_doi_ke_hoach_do_sau():
    """Cung outline, 2 tac gia -> 2 ke hoach khac nhau. Do la ca diem cua lab."""
    v = depth_plan(4, 3500, chars_per_idea=1408)
    lw = depth_plan(4, 3500, chars_per_idea=1720)
    assert v["est_chars"] != lw["est_chars"]
    assert lw["est_chars"] > v["est_chars"]           # Lewis viet dai hon -> uoc cao hon
    assert idea_budget(3500, chars_per_idea=1720) <= idea_budget(3500, chars_per_idea=1408)


def test_bo_trong_hang_so_thi_dung_mac_dinh_chung():
    assert depth_plan(4, 3500) == depth_plan(4, 3500, chars_per_idea=0)


# --- Vo chac chan ---------------------------------------------------------------------

def test_build_lab_brief_ghep_dung_so_luong():
    assert build_lab_brief(MAT, 2, 0).count(".") >= 2
    b = build_lab_brief(MAT, 3, 4)
    assert all(x[:30] in b for x in MAT["briefs"])
    assert all(x[:20] in b for x in MAT["addons"])


def test_mau_hong_khong_giet_ca_lab():
    calls = {"n": 0}

    def flaky(system, user):
        calls["n"] += 1
        if calls["n"] % 3 == 0:
            raise RuntimeError("mang loi")
        return "x" * 3000
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=flaky, samples=3, model="m")
    assert lab["table"]                       # van ra bang, khong nem loi


def test_nut_dung_thi_khong_ghi_gi_vao_profile():
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=_fake_llm(1408, 98), samples=3, model="m",
                  should_stop=lambda: True)
    assert lab == {}


def test_render_guide_doc_duoc():
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=_fake_llm(1408, 98), samples=3, model="glm:glm-5.2")
    out = "\n".join(render_guide(lab))
    assert "Ventures" in out and "Chapter" in out and "Brief" in out and "Add-on" in out
    assert "1408" in out
    assert render_guide({}) == ["(chua chay lab)"]


# --- Noi vao Extractor (buoc 5) -------------------------------------------------------

def test_extractor_chay_lab_thanh_buoc_5_khi_duoc_tick(monkeypatch, tmp_path):
    """Lab la buoc CUOI: cac buoc re hon xong truoc; lab hong thi profile van dung duoc."""
    from voiceprofile import server as vp

    ran = []
    monkeypatch.setattr(vp, "_run_cli", lambda job, args, label, abort: ran.append(args) or True)
    monkeypatch.setattr(vp, "_snapshot", lambda job, p, s: "")
    monkeypatch.setattr(vp.usage, "record_job", lambda row: None)

    job, err = vp._try_start("thanh", "extractor", 2, out=str(tmp_path / "o"))
    assert job and err is None
    vp._run_extractor(job=job, corpus=str(tmp_path), name="V", out=str(tmp_path / "o"),
                      do_rhetoric=False, do_clonekit=False, do_dataset=False,
                      provider="glm:glm-5.2", do_lab=True, lab_samples=8)
    vp.JOBS.clear()
    cmds = [a[0] for a in ran]
    assert cmds == ["build", "lab"]                 # lab chay SAU build
    lab_args = next(a for a in ran if a[0] == "lab")
    assert "--samples" in lab_args and lab_args[lab_args.index("--samples") + 1] == "8"
    assert "--provider" in lab_args                 # phai truyen provider xuong


def test_extractor_khong_tick_lab_thi_khong_chay():
    from voiceprofile import server as vp
    import inspect
    # do_lab mac dinh False -> profile cu / luong cu khong tu dung ton them tien (luat A6)
    sig = inspect.signature(vp._run_extractor)
    assert sig.parameters["do_lab"].default is False
    assert sig.parameters["lab_samples"].default == 5
    assert "job" in sig.parameters               # job theo nguoi (2026-07-16)


# --- Cong chan so vo ly (lab THAT tra ve so rac 2026-07-15) ---------------------------

def test_tu_choi_hang_so_vo_ly_add_on_dai_hon_brief():
    """Lab that tren fixture hu cau tra ve '211 ky tu/brief · 501 ky tu/add-on'. Mot
    add-on la MOT CAU — khong the dai gap 2.4 lan mot brief khai trien day du. Neu khong
    chan, so rac chui vao profile va Writer dung ngay -> te hon ca hang so cung."""
    rac = {(2, 4): [2427], (3, 4): [2638]}          # so DO THAT tu lab hong
    assert fit_constants(rac) == {}


def test_tu_choi_brief_ngan_phi_ly():
    assert fit_constants({(2, 4): [900], (3, 4): [1100]}) == {}      # a=200 -> qua ngan


def test_van_nhan_hang_so_hop_ly():
    ok = {(2, 4): [2 * 1408 + 4 * 98], (3, 4): [3 * 1408 + 4 * 98]}
    assert fit_constants(ok)["chars_per_brief"] == 1408


def test_lab_hong_thi_bao_ro_va_KHONG_dat_hang_so():
    """Tha KHONG CO hang so (Writer roi ve mac dinh) con hon co hang so SAI."""
    # LLM gia viet gan nhu nhau bat ke cau hinh -> khop ra so rac
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=lambda s, u: "x" * 2500, samples=3, model="m")
    assert "chars_per_brief" not in lab           # KHONG duoc dat hang so rac
    assert lab.get("unreliable")                  # phai noi ro vi sao
    assert lab["table"]                           # bang tra van giu de user doc
    assert chars_per_brief_of({"length_lab": lab}, 1250) == 1250   # Writer roi ve mac dinh


# --- Nguon lieu = CLUSTER THAT (thay fixture hu cau, 2026-07-15) ----------------------

def _mk_run(root, name, n, role="chapters", beats=3, brief=None):
    """Run gia — cluster brief NHIEU NHIP giong that ("Introduce X. Explain Y. Reveal Z.")."""
    d = root / name
    d.mkdir(parents=True)
    body = brief if brief is not None else " ".join(
        f"Beat {j} of the story told with enough words to be developed fully." 
        for j in range(beats))
    (d / "clusters.json").write_text(json.dumps([
        {"name": f"{name} cluster {i}", "brief": body, "role": role,
         "coverage_k": n - i} for i in range(n)]), encoding="utf-8")
    return d


def test_lay_brief_tu_cluster_that_khong_phai_fixture(tmp_path):
    """Fixture hu cau da that bai that: chu de model khong biet -> viet ~2500 bat ke cau
    hinh -> khop ra so rac. Noi dung production luon la cluster that."""
    _mk_run(tmp_path, "run-a", 8)
    m = pick_lab_material(tmp_path)
    assert m["run"] == "run-a"
    assert len(m["briefs"]) == 3 and len(m["addons"]) == 4


def test_brief_la_cac_NHIP_cua_MOT_cluster_khong_phai_3_cluster_khac_nhau(tmp_path):
    """Mo hinh user chot: 01 cluster chinh -> 2-3 brief (chinh la cac nhip cua no).
    Do cung la cach do da cho hang so hop ly (1408); lay 3 cluster roi lam 3 brief thi sai."""
    _mk_run(tmp_path, "r", 8)
    m = pick_lab_material(tmp_path)
    assert all(b.startswith("Beat ") for b in m["briefs"])       # cac nhip
    assert len({b for b in m["briefs"]}) == 3                    # 3 nhip KHAC nhau
    # add-on = MOT cau (su kien ngan), khong phai ca mach ke nhieu nhip
    assert all(a.count(".") <= 1 for a in m["addons"])


def test_chon_run_NHIEU_cluster_nhat_va_TAT_DINH(tmp_path):
    _mk_run(tmp_path, "run-nho", 8)
    _mk_run(tmp_path, "run-to", 20)
    assert pick_lab_material(tmp_path)["run"] == "run-to"
    # tat dinh: goi lai ra dung cai cu -> hang so so sanh duoc giua cac tac gia
    assert pick_lab_material(tmp_path) == pick_lab_material(tmp_path)


def test_bo_qua_cluster_khong_phai_chapter_va_brief_qua_ngan(tmp_path):
    _mk_run(tmp_path, "toan-hook", 20, role="hook")
    _mk_run(tmp_path, "brief-ngan", 20, brief="Ngan.")
    assert pick_lab_material(tmp_path) == {}


def test_cluster_khong_du_NHIP_thi_tu_choi(tmp_path):
    """Mo hinh user: MOT cluster chinh cung cap 2-3 brief = cac NHIP cua no. Cluster chi
    co 1 nhip thi khong do duoc."""
    _mk_run(tmp_path, "mot-nhip", 20,
            brief="One single beat but written with a great many words to be long enough.")
    assert pick_lab_material(tmp_path) == {}


def test_chua_co_run_thi_lab_TU_CHOI_chay_chu_khong_bia(tmp_path):
    """Tha khong chay con hon do bang thuoc do sai."""
    assert pick_lab_material(tmp_path) == {}
    logs = []
    assert run_lab(PROFILE, lambda s, u: "x" * 3000, material={}, on_progress=logs.append) == {}
    assert any("chua co run nao" in x for x in logs)


def test_run_hong_khong_lam_gay_viec_chon(tmp_path):
    (tmp_path / "hong").mkdir()
    (tmp_path / "hong" / "clusters.json").write_text("{khong-phai-json", encoding="utf-8")
    _mk_run(tmp_path, "tot", 8)
    assert pick_lab_material(tmp_path)["run"] == "tot"


def test_ghi_source_run_de_truy_nguoc():
    """Hang so gan voi (tac gia x model x DO QUEN THUOC cua chu de) — phai biet no do
    tren cai gi, vi doi nguon lieu la so co the doi (do that: lech 77%)."""
    lab = run_lab(PROFILE, material=MAT, llm_text_fn=_fake_llm(1408, 98), samples=3, model="m")
    assert lab["source_run"] == "test-run"
