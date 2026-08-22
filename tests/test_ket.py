# -*- coding: utf-8 -*-
"""Test két cấu hình (P3) — ghim: 2 ngăn config/secret, mã hóa thật, LLM theo vai."""
import pytest

from nen.ket_cau_hinh import ket


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    c = ket.ket_noi()
    yield c
    c.close()


def test_cau_hinh_set_get(conn):
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    assert ket.lay_cau_hinh(conn, "llm.writer.model") == "glm-4.5-air"
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-5")   # ghi đè
    assert ket.lay_cau_hinh(conn, "llm.writer.model") == "glm-5"
    assert ket.lay_cau_hinh(conn, "khong.co", "mac-dinh") == "mac-dinh"


def test_bi_mat_ma_hoa_that_trong_db(conn):
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-bi-mat-tuyet-doi-9999")
    # DB không được chứa plaintext ở BẤT KỲ đâu
    for r in conn.execute("SELECT gia_tri_ma FROM bi_mat").fetchall():
        assert "bi-mat-tuyet-doi" not in r["gia_tri_ma"]
    # nhưng giải mã ra đúng
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-bi-mat-tuyet-doi-9999"
    assert ket.lay_bi_mat(conn, "khong.co") is None


def test_liet_ke_khong_lo_secret(conn):
    """LUẬT lộ-có-chủ-đích (Owner phê lần 4): dau DAU_DAI(10) + duoi 4 để nhận
    diện — nhưng KHÔNG BAO GIỜ trả bản mã hay TOÀN BỘ plaintext trong một trường."""
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-9999-abcdefgh-xyza")
    ds = ket.liet_ke(conn)
    assert ds["bi_mat"][0]["dau"] == "sk-9999-ab" and ds["bi_mat"][0]["duoi"] == "xyza"
    assert "gia_tri_ma" not in ds["bi_mat"][0]
    assert not any("sk-9999-abcdefgh-xyza" in str(v)
                   for v in ds["bi_mat"][0].values())


def test_cau_hinh_llm_gop_du_va_mac_dinh_an_toan(conn):
    ket.dat_cau_hinh(conn, "llm.writer.provider", "openai_compatible")
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_cau_hinh(conn, "llm.writer.base_url", "https://api.z.ai/api/paas/v4")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-test-1234")
    ch = ket.cau_hinh_llm(conn, "ai-agent", "writer")
    assert ch["model"] == "glm-4.5-air"
    assert ch["api_key"] == "sk-test-1234"
    assert ch["timeout"] == 60 and ch["retry"] == 0   # luật nền: bài học hệ cũ
    # vai chưa khai → rỗng, không bịa
    assert ket.cau_hinh_llm(conn, "ai-agent", "vai-la")["provider"] == ""


def test_khoa_fernet_tu_sinh_va_tai_dung(conn, tmp_path):
    ket.dat_bi_mat(conn, "k", "gia-tri-1")
    assert (tmp_path / "ket.key").exists()
    # mở kết nối mới (cùng key file) vẫn giải mã được
    c2 = ket.ket_noi()
    assert ket.lay_bi_mat(c2, "k") == "gia-tri-1"
    c2.close()


# ---------- API keys theo LOẠI (trang API Keys — DE.md mục 12.3, K1-K8) ----------

def test_api_key_them_liet_ke_chi_duoi(conn):
    kid = ket.them_api_key(conn, "llm", "sk-llm-bi-mat-9k2f", nha="glm",
                           model="glm-4.5-air")
    kid2 = ket.them_api_key(conn, "youtube", "AIza-yt-7f2a")
    assert (kid, kid2) == ("api-001", "api-002")     # id tự sinh tăng dần
    ds = ket.liet_ke_api_keys(conn)
    assert [k["id"] for k in ds] == ["api-001", "api-002"]
    assert ds[0]["nha"] == "glm" and ds[0]["duoi"] == "9k2f"
    assert ds[1]["loai"] == "youtube" and ds[1]["ngay"]
    assert not any("bi-mat" in str(v) for k in ds for v in k.values())  # không plaintext
    with pytest.raises(ValueError):
        ket.them_api_key(conn, "llm", "sk-x")        # llm thiếu nhà
    with pytest.raises(ValueError):
        ket.them_api_key(conn, "loai-la", "sk-x")


def test_generate_la_mot_loai_chon_nha_khong_phai_2_loai_rieng(conn):
    """Owner chốt 17/08: VEO + Seedream là HAI NHÀ của MỘT loại 'generate' (khuôn
    y hệt llm) — không còn là 2 loại cố định riêng trong LOAI_API."""
    assert "generate" in ket.LOAI_API
    assert "veo" not in ket.LOAI_API and "seedream" not in ket.LOAI_API
    assert ket.NHA_GEN == ("veo", "seedream")

    kid = ket.them_api_key(conn, "generate", "flow-key-abcd", nha="veo",
                           model="veo-3.1")
    ds = ket.liet_ke_api_keys(conn)
    assert ds[0]["loai"] == "generate" and ds[0]["nha"] == "veo"
    assert ds[0]["id"] == kid

    ket.them_api_key(conn, "generate", "seed-key-wxyz", nha="seedream")
    ds = ket.liet_ke_api_keys(conn)
    assert {k["nha"] for k in ds} == {"veo", "seedream"}

    with pytest.raises(ValueError):                    # generate thiếu/sai nhà
        ket.them_api_key(conn, "generate", "flow-key-2")
    with pytest.raises(ValueError):
        ket.them_api_key(conn, "generate", "flow-key-3", nha="glm")   # nhà LLM lạc chỗ

    # loại KHÔNG có khái niệm nhà vẫn bị bỏ nha dù người gọi lỡ truyền vào
    kid_yt = ket.them_api_key(conn, "youtube", "AIza-du-nha", nha="glm")
    kid_tr = ket.them_api_key(conn, "transcript", "tr-du-nha", nha="veo")
    ds = ket.liet_ke_api_keys(conn)
    assert next(k for k in ds if k["id"] == kid_yt)["nha"] == ""
    assert next(k for k in ds if k["id"] == kid_tr)["nha"] == ""


def test_api_key_thu_hoi_go_khoi_cap_phat(conn):
    k1 = ket.them_api_key(conn, "youtube", "AIza-mot-1111")
    k2 = ket.them_api_key(conn, "youtube", "AIza-hai-2222")
    ket.luu_cap_phat_viec(conn, "radary", "harvest", [k1, k2], "xoay_vong")
    ra = ket.thu_hoi_api_key(conn, k1)
    assert ra["duoi"] == "1111"
    assert ket.lay_bi_mat(conn, f"api.{k1}.key") is None       # bí mật đã xóa
    assert ket.lay_cau_hinh(conn, f"api.{k1}.loai") == ""      # metadata đã xóa
    muc = ket.doc_cap_phat(conn)["radary"]["harvest"]
    assert muc["khoa"] == [k2]                                  # gỡ khỏi cấp phát
    assert muc["che_do"] == "mot_khoa"                          # còn 1 khóa → chuẩn hóa
    assert ket.thu_hoi_api_key(conn, "api-999") is None


def test_cap_phat_nhieu_khoa_va_che_do(conn):
    k1 = ket.them_api_key(conn, "youtube", "AIza-a-aaaa")
    k2 = ket.them_api_key(conn, "youtube", "AIza-b-bbbb")
    muc = ket.luu_cap_phat_viec(conn, "radary", "harvest", [k1])
    assert muc["che_do"] == "mot_khoa"                          # ≤1 khóa ép một-khóa
    muc = ket.luu_cap_phat_viec(conn, "radary", "harvest", [k1, k2], "du_phong")
    assert muc["che_do"] == "du_phong" and muc["ngay"]
    muc = ket.luu_cap_phat_viec(conn, "radary", "harvest", [k1, k2, "api-chet"])
    assert muc["khoa"] == [k1, k2]                              # id chết tự rơi
    assert muc["che_do"] == "du_phong"                          # giữ chế độ đã chọn


def test_cau_hinh_llm_fallback_cu_byte_identical(conn):
    """HỒI QUY (đường đọc ai-agent/DA qua loopback): két CHỈ có llm.writer.* cũ
    → cau_hinh_llm trả y hệt trước — hệ đang chạy không gãy một nhịp."""
    ket.dat_cau_hinh(conn, "llm.writer.provider", "openai_compatible")
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_cau_hinh(conn, "llm.writer.base_url", "https://api.z.ai/api/paas/v4")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-cu-1234")
    assert ket.cau_hinh_llm(conn, "ai-agent", "writer") == {
        "vai": "writer", "provider": "openai_compatible", "model": "glm-4.5-air",
        "base_url": "https://api.z.ai/api/paas/v4", "api_key": "sk-cu-1234",
        "timeout": 60, "retry": 0}
    # fallback cũ là sổ chung KHÔNG theo app: app khác chưa cấp phát cũng đọc
    # đúng sổ đó (ngữ nghĩa di sản), KHÔNG lẫn sang cấp phát app nào
    assert ket.cau_hinh_llm(conn, "data-analytics", "writer")["api_key"] == "sk-cu-1234"


def test_cau_hinh_llm_resolve_tu_cap_phat_moi(conn):
    kid = ket.them_api_key(conn, "llm", "sk-moi-8888", nha="glm",
                           model="glm-4.5-air")
    ket.luu_cap_phat_viec(conn, "ai-agent", "writer", [kid], model="glm-5")
    ch = ket.cau_hinh_llm(conn, "ai-agent", "writer")
    assert ch["provider"] == "openai_compatible"                # suy từ nhà GLM
    assert ch["base_url"] == "https://api.z.ai/api/paas/v4"
    assert ch["model"] == "glm-5"                               # model CỦA VIỆC thắng
    assert ch["api_key"] == "sk-moi-8888"
    # việc CÓ cấp phát nhưng 0 khóa = TẮT tường minh — fallback không hồi sinh
    ket.dat_bi_mat(conn, "llm.critic.api_key", "sk-critic-cu")
    ket.dat_cau_hinh(conn, "llm.critic.provider", "openai_compatible")
    ket.luu_cap_phat_viec(conn, "ai-agent", "critic", [])
    assert ket.cau_hinh_llm(conn, "ai-agent", "critic")["provider"] == ""


def test_cau_hinh_llm_theo_app_khong_muon_nham_khoa(conn):
    """HỒI QUY QUAN TRỌNG NHẤT (bug Owner phê lần 3, 18/08): bản cũ hardcode
    'ai-agent' → data-analytics xin cấu hình bị trả nhầm khóa Writer của
    ai-agent. Giờ 2 app 2 cấp phát khác nhau PHẢI ra 2 khóa KHÁC NHAU."""
    k_ai = ket.them_api_key(conn, "llm", "sk-cua-ai-agent-1111", nha="glm",
                            model="glm-4.5-air")
    k_da = ket.them_api_key(conn, "llm", "sk-cua-data-analytics-2222", nha="claude",
                            model="claude-haiku-4-5")
    ket.luu_cap_phat_viec(conn, "ai-agent", "writer", [k_ai])
    ket.luu_cap_phat_viec(conn, "data-analytics", "dien_giai", [k_da])

    ch_ai = ket.cau_hinh_llm(conn, "ai-agent", "writer")
    ch_da = ket.cau_hinh_llm(conn, "data-analytics", "dien_giai")
    assert ch_ai["api_key"] == "sk-cua-ai-agent-1111"
    assert ch_da["api_key"] == "sk-cua-data-analytics-2222"
    assert ch_ai["api_key"] != ch_da["api_key"]                 # hết mượn nhầm
    assert ch_da["provider"] == "anthropic"                     # đúng nhà của khóa DA

    # data-analytics xin việc TRÙNG TÊN với ai-agent nhưng CHƯA cấp phát cho DA
    # → KHÔNG với sang cấp phát ai-agent; rơi về fallback sổ chung (ở đây rỗng)
    assert ket.cau_hinh_llm(conn, "data-analytics", "writer")["api_key"] == ""


def _bi_mat_theo_khoa(conn, khoa):
    return next(r for r in ket.liet_ke(conn)["bi_mat"] if r["khoa"] == khoa)


def test_dau_khoa_luu_dung_10_ky_tu(conn):
    """Hiển thị khóa 'dau···duoi' — dat_bi_mat lưu DAU_DAI(10) ký tự đầu (Owner
    phê lần 4: 3 ký tự vô dụng với 19 khóa Google cùng 'AIz') ngang hàng đuôi 4;
    liet_ke() + liet_ke_api_keys() đều trả 'dau', không trả TOÀN BỘ plaintext."""
    assert ket.DAU_DAI == 10
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-9999-abcdefgh-xyza")
    r = _bi_mat_theo_khoa(conn, "llm.writer.api_key")
    assert r["dau"] == "sk-9999-ab" and r["duoi"] == "xyza"
    assert not any("sk-9999-abcdefgh-xyza" in str(v) for v in r.values())

    kid = ket.them_api_key(conn, "youtube", "AIzaSyABCDEF1234567890")
    muc = next(k for k in ket.liet_ke_api_keys(conn) if k["id"] == kid)
    assert muc["dau"] == "AIzaSyABCD" and muc["duoi"] == "7890"
    assert not any("AIzaSyABCDEF1234567890" in str(v) for v in muc.values())

    # ghi đè cùng khóa (ON CONFLICT) → dau/duoi cập nhật theo giá trị mới
    ket.dat_bi_mat(conn, "llm.writer.api_key", "zz-khac-han-hoan-toan-0000")
    r2 = _bi_mat_theo_khoa(conn, "llm.writer.api_key")
    assert r2["dau"] == "zz-khac-ha" and r2["duoi"] == "0000"


def test_backfill_dau_khoa_idempotent(conn):
    """Backfill phủ CẢ HAI đời cũ: dau rỗng (trước migration 002) VÀ dau 3 ký tự
    (trước khi nâng DAU_DAI 3→10) → tính lại từ bản mã; KHÔNG đụng gia_tri_ma/
    sua_luc; gọi lần 2 không đổi gì (idempotent)."""
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-that-abcdef-1234")
    ket.dat_bi_mat(conn, "llm.critic.api_key", "sk-critic-ghijkl-5678")
    # mô phỏng 2 đời cũ: dòng dau rỗng + dòng dau 3 ký tự (bản 17/08)
    with conn:
        conn.execute("UPDATE bi_mat SET dau='' WHERE khoa='llm.writer.api_key'")
        conn.execute("UPDATE bi_mat SET dau='sk-' WHERE khoa='llm.critic.api_key'")
    truoc = dict(conn.execute(
        "SELECT gia_tri_ma, sua_luc FROM bi_mat WHERE khoa='llm.writer.api_key'"
    ).fetchone())

    so = ket.backfill_dau_khoa(conn)
    assert so == 2                                  # cả dòng rỗng lẫn dòng 3 ký tự
    r = conn.execute(
        "SELECT dau, gia_tri_ma, sua_luc FROM bi_mat WHERE khoa='llm.writer.api_key'"
    ).fetchone()
    assert r["dau"] == "sk-that-ab"
    assert r["gia_tri_ma"] == truoc["gia_tri_ma"]   # không ghi lại bản mã
    assert r["sua_luc"] == truoc["sua_luc"]         # không đụng mốc sửa
    assert _bi_mat_theo_khoa(conn, "llm.critic.api_key")["dau"] == "sk-critic-"

    assert ket.backfill_dau_khoa(conn) == 0         # lần 2: không còn gì để nâng
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-that-abcdef-1234"

    # khóa NGẮN hơn DAU_DAI: dau = trọn khóa, backfill KHÔNG đếm lại mãi
    ket.dat_bi_mat(conn, "khoa.ngan", "abc123")
    assert _bi_mat_theo_khoa(conn, "khoa.ngan")["dau"] == "abc123"
    assert ket.backfill_dau_khoa(conn) == 0


def test_them_api_key_chan_trung_gia_tri(conn):
    """Owner 18/08 (check trùng key): cùng MỘT khóa dán 2 lần → ValueError chỉ
    ra bản đã có (id + dau···duoi) thay vì lặng lẽ đẻ bản sao — so bằng SHA-256
    (Fernet không so được bản mã); khóa KHÁC giá trị vào bình thường; khóa đã
    THU HỒI dán lại được (bản cũ đã xóa hẳn)."""
    kid = ket.them_api_key(conn, "youtube", "AIza-trung-lap-1111")
    with pytest.raises(ValueError) as e:
        ket.them_api_key(conn, "youtube", "AIza-trung-lap-1111")
    assert kid in str(e.value) and "AIza-trung···1111" in str(e.value)
    with pytest.raises(ValueError):                        # trùng cả khi khác LOẠI
        ket.them_api_key(conn, "transcript", "AIza-trung-lap-1111")
    assert len(ket.liet_ke_api_keys(conn)) == 1            # không đẻ bản sao
    ket.them_api_key(conn, "youtube", "AIza-khac-han-2222")
    assert len(ket.liet_ke_api_keys(conn)) == 2
    ket.thu_hoi_api_key(conn, kid)
    kid2 = ket.them_api_key(conn, "youtube", "AIza-trung-lap-1111")   # dán lại OK
    assert kid2 != kid


def test_backfill_hash_va_luu_cap_phat_dedup(conn):
    """(a) Dòng trước migration 003 (hash rỗng) được backfill điền hash cùng
    lượt decrypt — idempotent, không đụng gia_tri_ma/sua_luc; sau backfill khóa
    trùng giá trị MỚI bị bắt. (b) luu_cap_phat_viec DEDUP giữ thứ tự — cùng
    khóa không bao giờ nằm 2 lần trong MỘT việc."""
    ket.them_api_key(conn, "youtube", "AIza-hash-cu-3333")
    with conn:                                  # mô phỏng dòng đời trước 003
        conn.execute("UPDATE bi_mat SET hash='' WHERE khoa LIKE 'api.%'")
    # hash rỗng → khóa trùng CHƯA bị bắt (không có gì để so)
    kid_trung = ket.them_api_key(conn, "transcript", "AIza-hash-cu-3333")
    ket.thu_hoi_api_key(conn, kid_trung)        # dọn bản trùng thử
    with conn:
        conn.execute("UPDATE bi_mat SET hash='' WHERE khoa LIKE 'api.%'")
    assert ket.backfill_dau_khoa(conn) == 1     # điền hash (dau vốn đã đủ 10)
    assert ket.backfill_dau_khoa(conn) == 0     # idempotent
    with pytest.raises(ValueError):             # sau backfill: trùng bị bắt
        ket.them_api_key(conn, "youtube", "AIza-hash-cu-3333")

    k1 = ket.them_api_key(conn, "youtube", "AIza-dedup-a-4444")
    k2 = ket.them_api_key(conn, "youtube", "AIza-dedup-b-5555")
    muc = ket.luu_cap_phat_viec(conn, "radary", "harvest",
                                [k1, k2, k1, k1], "xoay_vong")
    assert muc["khoa"] == [k1, k2]              # dedup giữ thứ tự


def test_di_tru_llm_cu_idempotent_giu_base_url(conn):
    ket.dat_cau_hinh(conn, "llm.writer.provider", "openai_compatible")
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_cau_hinh(conn, "llm.writer.base_url", "http://may-la.noi-bo:9999/v1")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-di-tru-4321")
    truoc = ket.cau_hinh_llm(conn, "ai-agent", "writer")
    ra = ket.di_tru_llm_cu(conn)
    assert [m["vai"] for m in ra] == ["writer"] and ra[0]["duoi"] == "4321"
    assert ket.di_tru_llm_cu(conn) == []                        # idempotent
    assert len(ket.liet_ke_api_keys(conn)) == 1                 # không nhân đôi
    # resolve SAU migration ra đúng giá trị CŨ kể cả base_url lạ (override per-khóa)
    assert ket.cau_hinh_llm(conn, "ai-agent", "writer") == truoc
    # mục cũ GIỮ nguyên làm fallback
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-di-tru-4321"


def test_loai_serp_mot_khoa_cho_moi_engine(conn):
    """22/08 — Owner mở khối SERP trong General để nối Google Trends ổn định
    (trendspyg đang hỏng 57%) + Reddit qua site:reddit.com.

    MỘT khoá dùng cho MỌI engine của nhà đó (google / google_trends /
    google_news / youtube) — quota trừ chung, không cần khoá riêng từng engine.
    Dùng khuôn NHÀ như llm/generate vì còn đang so ba nhà.
    """
    assert "serp" in ket.LOAI_API
    assert ket.TEN_LOAI_API["serp"] == "Search Results API (SERP)"
    assert set(ket.NHA_SERP) == {"serpapi", "serper", "searchapi"}
    assert set(ket.NHA_SERP_INFO) == set(ket.NHA_SERP)     # nhà nào cũng có nhãn

    kid = ket.them_api_key(conn, "serp", "khoa-thu-serp-22-08", nha="serpapi")
    assert kid.startswith("api-")
    assert ket.lay_cau_hinh(conn, f"api.{kid}.nha") == "serpapi"
    assert ket.lay_cau_hinh(conn, f"api.{kid}.loai") == "serp"
    with pytest.raises(ValueError, match="Nhà SERP"):
        ket.them_api_key(conn, "serp", "khoa-khac", nha="bing-lung-tung")
