# -*- coding: utf-8 -*-
"""BA LUAT API cua Owner tren DATA-ANALYTICS (chot 08/09) — test TRUOC, code sau.

Ra 08/09 (so 15.29): Luat 1 dat ~90% (app da doc khoa THEO VIEC san — khuon dung);
Luat 2 va 3 = 0% (khong dropdown chon nha/model, khong nut thinking, va lop LLM
goi z.ai KHONG kem tham so thinking nen glm-5 tu bat thinking — dot token ngam).

Test khong goi API that, khong can gateway song.
"""
import pathlib
import sys

GOC = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

APPS_JSON = pathlib.Path(r"D:\AI AGENT OUTLIERY\nen\rules\apps.json")


def _doc(p: str) -> str:
    return (GOC / p).read_text(encoding="utf-8")


# ══ LUAT 1 — KHAI BAO (da gan dat; ghim de khong thoai lui) ═════════════════════
def test_luat1_so_chi_phi_ghi_MA_VIEC_hop_dong():
    """Ra 08/09: so ghi `vai` (writer/critic — ten NOI BO) thay vi ma viec hop
    dong (dien_giai/phan_bien) nen doi soat tien theo viec phai dich mot nac."""
    src = _doc("src/llm/base.py") + _doc("src/llm/factory.py")
    assert "ma_viec" in src or "MA_VIEC" in src, \
        "so goi phai ghi MA VIEC hop dong, khong chi ghi vai noi bo"


def test_luat1_van_doc_khoa_theo_tung_viec():
    """Khuon DUNG cua app nay (khong duoc thoai lui ve gop phang nhu CU cu):
    hoi gateway theo TUNG viec trong hop dong."""
    src = _doc("src/dien_giai.py")
    assert "ANH_XA_VAI" in src and "/api/cau-hinh/llm/" in src
    assert '"dien_giai"' in src and '"phan_bien"' in src


# ══ LUAT 2 — USER CHON API ══════════════════════════════════════════════════════
def test_luat2_trang_chan_doan_co_o_chon_nha_model():
    """Ra 08/09: 0 dropdown LLM trong moi template — nha/model chi Owner dat o Ket."""
    # LUU Y: chan_doan.html la template CHET (18/08 doi mat tien sang chon_module);
    # form Diagnose THAT nam trong dashboard.html — ghim dung file dang chay.
    html = _doc("src/templates/dashboard.html")
    assert 'id="da_llm"' in html, "thieu o chon nha/model tren form chan doan that"
    assert "/api/llm-lua-chon" in html, "dropdown phai nap tu server"


def test_luat2_route_nhan_lua_chon_nha_model():
    """Lua chon tren UI phai di toi tang goi LLM (khong chi trang tri)."""
    src = _doc("src/main.py") + _doc("src/dien_giai.py")
    assert "provider" in src and "model" in src
    assert "chon_llm" in src, "thieu duong nhan lua chon nha/model tu UI"


def test_luat2_api_liet_ke_nha_model_cho_dropdown():
    """UI phai lay danh sach nha/model tu server (nhu /api/providers ben CU),
    khong hardcode trong HTML."""
    src = _doc("src/main.py")
    assert "/api/llm-lua-chon" in src, "thieu route liet ke lua chon LLM"


# ══ LUAT 3 — MODEL + NUT THINKING ═══════════════════════════════════════════════
def test_luat3_trang_chan_doan_co_nut_thinking():
    html = _doc("src/templates/dashboard.html")
    assert 'id="da_llm_think"' in html, "thieu nut bat/tat thinking canh o chon model"
    assert "chon_llm" in html and "thinking" in html, "form phai gui 2 lua chon"


def test_luat3_lop_llm_nhan_muc_thinking():
    """Ra 08/09: openai_compatible.generate() goi z.ai KHONG kem thinking ->
    glm-5 TU BAT thinking (do 02/09: 88% output token la suy nghi ngam)."""
    from src.llm.openai_compatible import OpenAICompatibleProvider
    import inspect
    sig = inspect.signature(OpenAICompatibleProvider.__init__)
    assert "thinking" in sig.parameters, "provider phai nhan muc thinking"
    src = inspect.getsource(OpenAICompatibleProvider)
    assert "reasoning_effort" in src or "extra_body" in src, \
        "phai gui thinking/reasoning_effort xuong API"


def test_luat3_ba_muc_va_mac_dinh_TAT():
    """Cung thang muc voi Content Ultimate: tat | thap | nha; mac dinh TAT
    (Owner chot 02/09 sau 3 su co thinking dot token)."""
    from src.llm import factory
    assert hasattr(factory, "THINKING_MAC_DINH")
    assert factory.THINKING_MAC_DINH == "tat"
    assert set(getattr(factory, "THINKING_MUC", ())) == {"tat", "thap", "nha"}


def test_luat3_thinking_di_toi_payload_dung_muc(monkeypatch):
    """Ghim HANH VI: 'tat' -> body co thinking disabled; 'thap' -> reasoning_effort
    low; 'nha' -> khong dong gi (de nha cung cap tu quyet)."""
    from src.llm.openai_compatible import OpenAICompatibleProvider

    goi = {}

    class _Comp:
        def create(self, **kw):
            goi.clear(); goi.update(kw)
            class _M:
                content = "OK"
            class _C:
                message = _M()
            return type("R", (), {"choices": [_C()],
                                  "usage": type("U", (), {"prompt_tokens": 1,
                                                          "completion_tokens": 1})()})()

    def _lam(muc):
        p = OpenAICompatibleProvider(model="glm-5", api_key="x",
                                     base_url="https://api.z.ai/api/paas/v4",
                                     mock=False, thinking=muc)
        p.client = type("Cl", (), {"chat": type("Ch", (), {"completions": _Comp()})()})()
        p.vai = "dien_giai"
        p.generate("s", "u")
        return dict(goi)

    tat = _lam("tat")
    assert "disabled" in str(tat), f"muc 'tat' phai gui thinking disabled: {tat}"
    thap = _lam("thap")
    assert "low" in str(thap), f"muc 'thap' phai gui reasoning_effort low: {thap}"
    nha = _lam("nha")
    assert "thinking" not in str(nha) and "reasoning_effort" not in str(nha), \
        f"muc 'nha' khong duoc dong gi: {nha}"
