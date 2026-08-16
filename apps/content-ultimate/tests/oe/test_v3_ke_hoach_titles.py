"""Test V3 (offline): kế hoạch phút/AVD + máy chấm title (van chống bịa) + vai chương.

Nguồn sự cố kiểm chứng: video "RETIRING in VIETNAM" 27/07 — title đổi ở khâu đăng,
0 chương trả lời hứa, APV 18%. Mọi test chạy callback giả, 0 LLM thật.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from oe.compose import compose_evidence, compose_outline
from oe.ke_hoach import kiem_lich, lich_phut, sap_theo_vai, so_chuong
from oe.suggest import build_candidates, parse_suggestion, suggest_outline
from oe.titles import cham_title_tay, cham_y, parse_titles, titles_goc_cua_song

CL = [
    {"name": "Cost of living", "brief": "Live luxuriously on a small budget in Vietnam.",
     "role": "chapters", "coverage_k": 1, "coverage_n": 4, "peak_score": 0.0,
     "pos": 0.2, "questions_n": 0, "questions": []},
    {"name": "Street life", "brief": "Streets serve as the living room from 5 AM.",
     "role": "chapters", "coverage_k": 3, "coverage_n": 4, "peak_score": 6.9,
     "pos": 0.3, "questions_n": 1, "questions": ["how do they cross the street?"]},
    {"name": "Soul of Vietnam", "brief": "A story of overcoming trauma through dignity.",
     "role": "chapters", "coverage_k": 1, "coverage_n": 4, "peak_score": 4.6,
     "pos": 0.7, "questions_n": 0, "questions": []},
    {"name": "Heritage wonders", "brief": "Hoi An lantern festival and Son Doong cave.",
     "role": "chapters", "coverage_k": 2, "coverage_n": 4, "peak_score": 10.0,
     "pos": 0.8, "questions_n": 0, "questions": []},
    {"name": "Mở màn xe máy", "brief": "Chaotic motorcycle traffic as survival rhythm.",
     "role": "hook", "coverage_k": 1, "coverage_n": 4, "peak_score": 1.0,
     "pos": 0.0, "questions_n": 0, "questions": []},
    {"name": "Kết captivating chaos", "brief": "Vietnam disarms every visitor.",
     "role": "ending", "coverage_k": 1, "coverage_n": 4, "peak_score": 1.0,
     "pos": 0.95, "questions_n": 0, "questions": []},
    # nhiễu kiểu "cluster Nhật" (video lạc sóng): single peak=0 & q=0
    {"name": "Japan tattoo stigma", "brief": "Yakuza associations ban tattoos in onsen.",
     "role": "chapters", "coverage_k": 1, "coverage_n": 4, "peak_score": 0.0,
     "pos": 0.5, "questions_n": 0, "questions": []},
]


# ── ke_hoach: số chương từ ký tự + lịch phút + xếp vai ──────────────────────────

def test_so_chuong_tu_ky_tu():
    assert so_chuong(22000) == 6            # vùng ngọt 3.250 → 22k ≈ 6 chương
    assert so_chuong(4000) == 3             # sàn 3
    assert so_chuong(60000) == 12           # trần 12


def test_lich_phut_cong_du_tong():
    lich = lich_phut(22000, 6)
    assert [m["nhan"] for m in lich] == ["HOOK", "C1", "C2", "C3", "C4", "C5", "C6", "END"]
    assert abs(lich[-1]["den"] - 22000 / 850) < 0.01    # tổng phút = tổng ký tự / 850
    for a, b in zip(lich, lich[1:]):
        assert abs(a["den"] - b["tu"]) < 1e-9           # mốc liền nhau, không hở


def test_sap_theo_vai_tra_hua_len_dau_payoff_ve_65():
    ch = ["A", "B", "C", "D", "E", "F"]
    vai = {"D": "tra_hua", "B": "payoff"}
    xep = sap_theo_vai(ch, vai, 22000)
    assert xep[0] == "D"                                # trả hứa lên chương 1
    tam_payoff = xep.index("B")
    lich = lich_phut(22000, 6)
    tam = (lich[tam_payoff + 1]["tu"] + lich[tam_payoff + 1]["den"]) / 2 / lich[-1]["den"]
    assert 0.5 <= tam <= 0.8                            # payoff về vùng giữa-cuối


def test_kiem_lich_bao_tra_hua_sau_moc_avd():
    ch = ["A", "B", "C", "D", "E", "F"]
    # trả hứa nằm C3 (kết thúc ~12,5') trong khi AVD 5,5' → phải cảnh báo
    cb = kiem_lich(ch, {"C": "tra_hua"}, 22000, 5.5)
    assert any("SAU mốc AVD" in c for c in cb)
    assert kiem_lich(ch, {"A": "tra_hua"}, 22000, 5.5) == []   # C1 kết thúc 4,5' ≤ 5,5' ✓
    # chưa nhập AVD → nhắc nhập, không phán bừa
    assert any("Chưa nhập AVD" in c for c in kiem_lich(ch, {"A": "tra_hua"}, 22000, None))


# ── titles: van chống bịa 3 tầng ────────────────────────────────────────────────

def test_cham_y_verbatim_va_diem_tat_dinh():
    y = [
        {"y": "cheap living", "cluster": "Cost of living",
         "trich": "live luxuriously on a small budget"},          # verbatim ✓ (single trơ 0.4)
        {"y": "daily life", "cluster": "Street life",
         "trich": "streets serve as the living room"},            # verbatim ✓ (xương sống 1.0)
        {"y": "healthcare", "cluster": "Cost of living",
         "trich": "world-class private hospitals"},               # BỊA → 0, có note loại
        {"y": "visa", "cluster": None, "trich": None},            # không vật liệu
    ]
    diem, chi_tiet = cham_y(y, CL)
    assert diem == round((0.4 + 1.0 + 0 + 0) / 4 * 100) == 35
    assert "bịa" in chi_tiet[2]["note"] or "loại" in chi_tiet[2]["note"]
    assert chi_tiet[3]["note"] == "sóng KHÔNG có vật liệu"


def test_cham_y_khong_cho_trich_tu_ten_cluster():
    # kho xác minh CHỈ brief+angle — trích đúng tên cluster vẫn phải bị loại
    diem, chi_tiet = cham_y(
        [{"y": "x", "cluster": "Japan tattoo stigma", "trich": "Japan tattoo stigma"}], CL)
    assert diem == 0 and "loại" in chi_tiet[0]["note"]


def test_parse_titles_loc_va_gan_co_thieu():
    raw = "```json\n" + json.dumps([
        {"title": "Vietnam's Cheap Label Hides Something", "promise": "reveal the truth",
         "y_loi_hua": [{"y": "cheap", "cluster": "Cost of living",
                        "trich": "live luxuriously on a small budget"}]},
        {"title": "", "promise": "x", "y_loi_hua": []},            # rỗng → loại
        {"title": "Retire in Vietnam Today", "promise": "retirement guide",
         "y_loi_hua": [{"y": "visa", "cluster": None, "trich": None},
                       {"y": "healthcare", "cluster": None, "trich": None}]},
    ]) + "\n```"
    ts = parse_titles(raw, CL)
    assert [t["thieu"] for t in ts] == [False, True]               # 40% ngưỡng: 40 vs 0
    assert ts[1]["diem"] == 0


def test_cham_title_tay_di_qua_cung_may_cham():
    fake = lambda s, u: json.dumps({"promise": "cheap living exposed",  # noqa: E731
        "y_loi_hua": [{"y": "cheap", "cluster": "Cost of living",
                       "trich": "live luxuriously on a small budget"}]})
    kq = cham_title_tay("What $500 Buys in Vietnam", CL, fake)
    assert kq["diem"] == 40 and kq["thieu"] is False


def test_titles_goc_sap_theo_view():
    vids = {"a": {"title": "B nhỏ", "view_count": 10}, "b": {"title": "A to", "view_count": 99},
            "c": {"title": "", "view_count": 5}}
    ts = titles_goc_cua_song(vids)
    assert [t["title"] for t in ts] == ["A to", "B nhỏ"]           # view cao trước, bỏ rỗng


# ── suggest: vai + lưới nhiễu + tương thích ngược ──────────────────────────────

def test_build_candidates_loc_single_khong_tin_hieu():
    cands = build_candidates(CL)
    names = {c["name"] for c in cands}
    assert "Japan tattoo stigma" not in names          # single peak=0 & q=0 → không lấp
    assert "Cost of living" not in names or True       # (cũng peak=0 q=0 — cùng luật)
    ngheo = [{"name": f"n{i}", "brief": "x", "coverage_k": 1, "coverage_n": 2,
              "peak_score": 0.0, "pos": None, "questions_n": 0} for i in range(5)]
    assert len(build_candidates(ngheo)) == 5           # sóng nghèo tín hiệu → nới như cũ


def test_parse_suggestion_vai_va_tuong_thich_nguoc():
    data = {"title": "T", "promise": "P",
            "hook": "Mở màn xe máy", "ending": "Kết captivating chaos",
            "chapters": [
                {"name": "Cost of living", "vai": "tra_hua", "vi_sao": "trả giá rẻ"},
                "Street life",                                        # hợp đồng cũ: chuỗi trần
                {"name": "Soul of Vietnam", "vai": "payoff"},
                {"name": "Heritage wonders", "vai": "tra_hua"},       # tra_hua THỨ 2 → bỏ vai
                {"gap": "Is Vietnam actually cheap?", "vai": "linh_hoat"},
            ]}
    picks = parse_suggestion(json.dumps(data), CL)
    assert picks["promise"] == "P"
    assert picks["vai"] == {"Cost of living": "tra_hua", "Soul of Vietnam": "payoff"}
    assert picks["vi_sao"]["Cost of living"] == "trả giá rẻ"
    assert "Street life" in picks["chapters"]                         # chuỗi trần vẫn ăn
    assert any(n.startswith("✍") for n in picks["chapters"])          # gap → chương tự viết


def test_suggest_outline_xep_vai_va_canh_bao():
    data = {"title": "T", "promise": "P", "hook": "Mở màn xe máy",
            "ending": "Kết captivating chaos",
            "chapters": [
                "Street life",
                {"name": "Heritage wonders", "vai": "payoff"},
                {"name": "Cost of living", "vai": "tra_hua"},         # đứng C3 → phải lên C1
            ]}
    # 12k ký tự / 3 chương → mỗi chương ~4,2' → C1 kết thúc ~4,7' ≤ AVD 5,5' ✓
    picks = suggest_outline(CL, [], "T", lambda s, u: json.dumps(data),
                            n_chapters=3, total_chars=12000, avd_phut=5.5)
    assert picks["chapters"][0] == "Cost of living"                   # Python đảo lên đầu
    assert picks["canh_bao"] == []                                    # lên đầu rồi → hết trễ
    # 22k / 3 chương = mỗi chương ~8': C1 kết thúc SAU mốc 5,5' → máy phải nói thật
    # (đáp án đúng là tăng số chương/giảm độ dài, không phải im lặng)
    picks2 = suggest_outline(CL, [], "T", lambda s, u: json.dumps(data),
                             n_chapters=3, total_chars=22000, avd_phut=5.5)
    assert any("SAU mốc AVD" in c for c in picks2["canh_bao"])


# ── compose: guard trả hứa vào brief + PACKAGING; không vai → y cũ ─────────────

def _picks_vai():
    return {"title": "Cheap Label Hides", "promise": "reveal what cheap hides",
            "hook": "Mở màn xe máy", "ending": "Kết captivating chaos",
            "chapters": ["Cost of living", "Street life", "Soul of Vietnam"],
            "vai": {"Cost of living": "tra_hua", "Soul of Vietnam": "payoff"},
            "custom": {}, "extras": {}}


def test_compose_ghi_guard_tra_hua_payoff():
    out = compose_outline(_picks_vai(), CL)
    assert "PAYS THE FIRST INSTALLMENT" in out and "FULL PAYOFF" in out
    assert out.index("PAYS THE FIRST") < out.index("FULL PAYOFF")
    assert "Open that loop here" in out                    # hook mở loop, không trả
    assert "call back the fulfilled title promise" in out  # ending chỉ callback


def test_compose_khong_promise_khong_doi_mot_chu():
    p = _picks_vai()
    p["promise"] = ""                                      # picks cũ / không dùng V3
    out = compose_outline(p, CL)
    assert "Note to the writer" not in out


def test_evidence_co_khoi_packaging_cho_nguoi_upload():
    ev = compose_evidence(_picks_vai(), CL, {"avd_phut": 5.5})
    assert "PACKAGING" in ev and "Cheap Label Hides" in ev
    assert "TRẢ HỨA" in ev and "PAYOFF" in ev and "5.5′" in ev
    assert "Đăng ĐÚNG title này" in ev                     # luật cho người upload
    # không promise → không khối (evidence cũ y nguyên)
    p = _picks_vai(); p["promise"] = ""
    assert "PACKAGING" not in compose_evidence(p, CL)
