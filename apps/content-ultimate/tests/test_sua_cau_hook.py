"""Vong sua cau + mo-dun hook (Dot 3, 23/08/2026).

Bang chung nen: luat "moi doan toi da mot em-dash" bi vi pham 26-59% => model
KHONG tuan luat dem duoc. Doi thu model NHIN THAY thi an. Nen chan bang MAY sau
khi sinh, va cham hook bang MAY thay vi dan bang loi.
"""
from voiceprofile import hook, sua_cau


# ---------------------------------------------------------------- sua cau

def _luat():
    from voiceprofile import deai
    return deai.doc_luat()


def test_bat_dung_cau_mang_dong_tac_may():
    t = ("The country sits at the heart of the region. It is landlocked, no sea, "
         "no coastline. Here is what is surprising. Nobody expected it.")
    vi = sua_cau.cau_vi_pham(t, _luat())
    cum = " | ".join(c for _, c, _ in vi)
    assert "Here is what is surprising" in cum
    # cau thuong khong bi bat oan
    assert "The country sits at the heart" not in cum


def test_van_tu_choi_khi_roi_con_so():
    """Van quan trong nhat: dot 22/08 viet lai ca chuong lam roi 'hon hai nghin tan
    vang', roi ten Ulugh Beg, va de ra mot loi sai that. Sua cau phai giu du kien."""
    goc = "It produces 2000 tons of gold each year, more than most nations."
    ok, ly_do = sua_cau.nhan_duoc(goc, "It produces vast amounts of gold each year.")
    assert not ok and "con so" in ly_do


def test_van_tu_choi_khi_roi_ten_rieng():
    goc = "The observatory of Ulugh Beg still stands in Samarkand."
    ok, ly_do = sua_cau.nhan_duoc(goc, "The old observatory still stands there.")
    assert not ok and "ten rieng" in ly_do


def test_van_tu_choi_khi_lech_do_dai_qua_nguong():
    goc = "It is landlocked, and that shapes everything about how the country trades."
    ok, ly_do = sua_cau.nhan_duoc(goc, "It is landlocked.")
    assert not ok and "do dai" in ly_do


def test_van_nhan_ban_sua_giu_du_lieu():
    goc = "Uzbekistan holds 2000 tons of gold, a fortune buried under the Kyzyl Kum."
    moi = "Uzbekistan holds 2000 tons of gold buried beneath the Kyzyl Kum desert."
    ok, ly_do = sua_cau.nhan_duoc(goc, moi)
    assert ok, ly_do


def test_sua_giu_nguyen_van_khi_llm_hong():
    """Khong bao gio tra ban hong: LLM loi -> giu nguyen van goc."""
    def llm_hong(system, user, max_tokens=None):
        raise RuntimeError("het han muc")

    t = "Here is what is surprising. The country has no sea."
    moi, bao = sua_cau.sua(t, llm_hong, _luat())
    assert moi == t and bao.get("loi")


def test_sua_bo_qua_cau_khong_qua_van():
    """Ban sua lam roi con so -> giu NGUYEN cau goc, cac cau khac van duoc sua.

    CA HAI cau deu phai MANG dong tac may thi moi duoc gui di sua — cau thuong
    khong bi bat (do la thiet ke dung: chi dung vao cho co benh).
    """
    goc = "Here is what is surprising. Then there is the uranium, all 2000 tons of it."

    def llm(system, user, max_tokens=None):
        ra = []
        for dong in user.splitlines():
            n = dong.split(".")[0].strip()
            if "surprising" in dong:
                ra.append(n + ". The country has no sea at all.")
            else:
                ra.append(n + ". Uranium sits beside it in vast quantity.")
        return chr(10).join(ra)

    moi, bao = sua_cau.sua(goc, llm, _luat())
    assert "2000 tons of it" in moi                # cau bi tu choi giu nguyen
    assert bao["tu_choi"]
    assert bao["so_cau_sua"] == 1                  # cau con lai van duoc sua


# ---------------------------------------------------------------- hook

def test_hook_cham_bon_luat():
    """Ca that 22/08: ban cu mo bang nghich ly (tot), ban moi goi ten chu de o tu
    dau tien (dong vong lap truoc khi mo)."""
    tot = ("35 years ago, this country did not exist on any map. An empire had "
           "swallowed it whole and erased the name. Then the empire fell apart in "
           "a single winter, and what was underneath had been waiting there the "
           "entire time, older than the empire itself and far stranger.")
    xau = ("Uzbekistan. That is the name most people cannot find on a map. It sits "
           "at the heart of Central Asia, a country of desert and mountain, and it "
           "has been there for a very long time indeed, quietly minding itself.")
    d_tot = hook.cham(tot, title="Uzbekistan")
    d_xau = hook.cham(xau, title="Uzbekistan")
    assert d_tot["diem"] > d_xau["diem"]
    assert "cau dau khong goi ten chu de" in d_xau["truot"]


def test_hook_cam_cau_dan_bao_hieu():
    t = ("A country vanished for seventy years. Here is what is surprising about "
         "how it came back, and why nobody outside the region noticed it happen.")
    assert "khong co cau dan bao hieu" in hook.cham(t, title="Uzbekistan")["truot"]


def test_hook_chon_ban_dat_nhieu_luat_nhat():
    a = "Uzbekistan is a country in Central Asia. It has deserts and mountains here."
    b = ("35 years ago this place did not exist on any map, and no one outside the "
         "region could tell you why that changed or what was hiding underneath it.")
    chon, diem = hook.chon([a, b], title="Uzbekistan")
    assert chon == b
    assert len(diem) == 2


def test_hook_hoa_diem_thi_lay_ban_ngan_hon():
    a = "A country vanished for seventy years. " * 3
    b = "A country vanished for seventy years."
    chon, _ = hook.chon([a, b], title="Uzbekistan")
    assert chon == b


def test_hook_danh_sach_rong_khong_vo():
    assert hook.chon([], title="X") == ("", [])
    assert hook.chon(["", "   "], title="X") == ("", [])


def test_khoi_luat_hook_khong_dung_em_dash():
    """Bai hoc 22/08: model bat chuoc HINH THUC cua chinh ban huong dan."""
    assert "—" not in hook.khoi_luat()
