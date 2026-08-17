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
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-9999xyza")
    ds = ket.liet_ke(conn)
    assert ds["bi_mat"][0]["duoi"] == "xyza"
    assert "gia_tri_ma" not in ds["bi_mat"][0]
    assert not any("sk-9999" in str(v) for v in ds["bi_mat"][0].values())


def test_cau_hinh_llm_gop_du_va_mac_dinh_an_toan(conn):
    ket.dat_cau_hinh(conn, "llm.writer.provider", "openai_compatible")
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_cau_hinh(conn, "llm.writer.base_url", "https://api.z.ai/api/paas/v4")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-test-1234")
    ch = ket.cau_hinh_llm(conn, "writer")
    assert ch["model"] == "glm-4.5-air"
    assert ch["api_key"] == "sk-test-1234"
    assert ch["timeout"] == 60 and ch["retry"] == 0   # luật nền: bài học hệ cũ
    # vai chưa khai → rỗng, không bịa
    assert ket.cau_hinh_llm(conn, "vai-la")["provider"] == ""


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
    assert ket.cau_hinh_llm(conn, "writer") == {
        "vai": "writer", "provider": "openai_compatible", "model": "glm-4.5-air",
        "base_url": "https://api.z.ai/api/paas/v4", "api_key": "sk-cu-1234",
        "timeout": 60, "retry": 0}


def test_cau_hinh_llm_resolve_tu_cap_phat_moi(conn):
    kid = ket.them_api_key(conn, "llm", "sk-moi-8888", nha="glm",
                           model="glm-4.5-air")
    ket.luu_cap_phat_viec(conn, "ai-agent", "writer", [kid], model="glm-5")
    ch = ket.cau_hinh_llm(conn, "writer")
    assert ch["provider"] == "openai_compatible"                # suy từ nhà GLM
    assert ch["base_url"] == "https://api.z.ai/api/paas/v4"
    assert ch["model"] == "glm-5"                               # model CỦA VIỆC thắng
    assert ch["api_key"] == "sk-moi-8888"
    # việc CÓ cấp phát nhưng 0 khóa = TẮT tường minh — fallback không hồi sinh
    ket.dat_bi_mat(conn, "llm.critic.api_key", "sk-critic-cu")
    ket.dat_cau_hinh(conn, "llm.critic.provider", "openai_compatible")
    ket.luu_cap_phat_viec(conn, "ai-agent", "critic", [])
    assert ket.cau_hinh_llm(conn, "critic")["provider"] == ""


def _bi_mat_theo_khoa(conn, khoa):
    return next(r for r in ket.liet_ke(conn)["bi_mat"] if r["khoa"] == khoa)


def test_dau_khoa_luu_dung_3_ky_tu(conn):
    """Owner chốt 17/08: hiển thị khóa 'dau···duoi' — dat_bi_mat lưu 3 ký tự đầu
    ngang hàng đuôi 4; liet_ke() + liet_ke_api_keys() đều trả 'dau', không trả
    plaintext ở bất cứ trường nào."""
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-9999xyza")
    r = _bi_mat_theo_khoa(conn, "llm.writer.api_key")
    assert r["dau"] == "sk-" and r["duoi"] == "xyza"
    assert not any("sk-9999xyza" in str(v) for v in r.values())

    kid = ket.them_api_key(conn, "youtube", "AIzaSyABCDEF1234567890")
    muc = next(k for k in ket.liet_ke_api_keys(conn) if k["id"] == kid)
    assert muc["dau"] == "AIz" and muc["duoi"] == "7890"
    assert not any("AIzaSyABCDEF1234567890" in str(v) for v in muc.values())

    # ghi đè cùng khóa (ON CONFLICT) → dau/duoi cập nhật theo giá trị mới
    ket.dat_bi_mat(conn, "llm.writer.api_key", "zz-khac-han-0000")
    r2 = _bi_mat_theo_khoa(conn, "llm.writer.api_key")
    assert r2["dau"] == "zz-" and r2["duoi"] == "0000"


def test_backfill_dau_khoa_idempotent(conn):
    """Khóa nạp TRƯỚC migration 002 (dau rỗng) → backfill tính đúng từ bản mã;
    KHÔNG đụng gia_tri_ma/sua_luc; gọi lần 2 không đổi gì (idempotent)."""
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-that-1234")
    # mô phỏng dòng cũ trước migration: xóa dau về rỗng như DEFAULT của cột mới
    with conn:
        conn.execute("UPDATE bi_mat SET dau='' WHERE khoa='llm.writer.api_key'")
    truoc = dict(conn.execute(
        "SELECT gia_tri_ma, sua_luc FROM bi_mat WHERE khoa='llm.writer.api_key'"
    ).fetchone())

    so = ket.backfill_dau_khoa(conn)
    assert so == 1
    r = conn.execute(
        "SELECT dau, gia_tri_ma, sua_luc FROM bi_mat WHERE khoa='llm.writer.api_key'"
    ).fetchone()
    assert r["dau"] == "sk-"
    assert r["gia_tri_ma"] == truoc["gia_tri_ma"]   # không ghi lại bản mã
    assert r["sua_luc"] == truoc["sua_luc"]         # không đụng mốc sửa

    assert ket.backfill_dau_khoa(conn) == 0         # lần 2: không còn dòng dau='' → idempotent
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-that-1234"  # giải mã vẫn đúng


def test_di_tru_llm_cu_idempotent_giu_base_url(conn):
    ket.dat_cau_hinh(conn, "llm.writer.provider", "openai_compatible")
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_cau_hinh(conn, "llm.writer.base_url", "http://may-la.noi-bo:9999/v1")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-di-tru-4321")
    truoc = ket.cau_hinh_llm(conn, "writer")
    ra = ket.di_tru_llm_cu(conn)
    assert [m["vai"] for m in ra] == ["writer"] and ra[0]["duoi"] == "4321"
    assert ket.di_tru_llm_cu(conn) == []                        # idempotent
    assert len(ket.liet_ke_api_keys(conn)) == 1                 # không nhân đôi
    # resolve SAU migration ra đúng giá trị CŨ kể cả base_url lạ (override per-khóa)
    assert ket.cau_hinh_llm(conn, "writer") == truoc
    # mục cũ GIỮ nguyên làm fallback
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-di-tru-4321"
