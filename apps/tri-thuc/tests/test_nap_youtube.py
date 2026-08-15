"""Test phần THUẦN của acquisition YouTube (src/nap_youtube.py): tách video id từ URL +
ghép transcript → text sạch. lay_transcript (I/O mạng) KHÔNG test ở đây."""

import src.nap_youtube as ny
from src.nap_youtube import ghep_transcript, trich_tu_video, video_id_tu_url


class FakeWriter:
    def __init__(self, tho):
        self.tho = tho

    def generate(self, system_prompt, user_prompt):
        return self.tho


def test_http_client_cookies_chua_dat_tra_none(monkeypatch):
    monkeypatch.delenv("YOUTUBE_COOKIES", raising=False)
    from src.nap_youtube import _http_client_cookies
    assert _http_client_cookies() is None                         # không đặt → ẩn danh như cũ


def test_luu_xoa_trang_thai_cookies(monkeypatch):
    """Vòng đời qua UI: lưu (đếm dòng) → _http_client_cookies đọc được → trạng thái → gỡ.
    Đường dẫn mặc định nằm trong KHO_TAI_LIEU (conftest đã trỏ kho tạm — không đụng kho thật)."""
    monkeypatch.delenv("YOUTUBE_COOKIES", raising=False)
    from src.nap_youtube import (_http_client_cookies, luu_cookies,
                                 trang_thai_cookies, xoa_cookies)
    assert trang_thai_cookies() == {"co": False, "so_dong": 0}
    so = luu_cookies("# Netscape HTTP Cookie File\n"
                     ".youtube.com\tTRUE\t/\tTRUE\t9999999999\tPREF\tf1=1\n"
                     ".youtube.com\tTRUE\t/\tTRUE\t9999999999\tSID\tabc\n")
    assert so == 2
    assert trang_thai_cookies() == {"co": True, "so_dong": 2}
    s = _http_client_cookies()
    assert s is not None and s.cookies.get("SID") == "abc"        # transcript sẽ đi kèm phiên
    xoa_cookies()
    assert trang_thai_cookies()["co"] is False
    assert _http_client_cookies() is None                          # gỡ xong → ẩn danh lại


def test_luu_cookies_dan_nham_file_bao_loi():
    import pytest

    from src.nap_youtube import luu_cookies
    with pytest.raises(ValueError):
        luu_cookies("nội dung linh tinh không phải cookies")       # không dòng youtube.com → chặn


def test_http_client_cookies_file_khong_ton_tai_tra_none(monkeypatch):
    monkeypatch.setenv("YOUTUBE_COOKIES", "/khong/co/that/cookies.txt")
    from src.nap_youtube import _http_client_cookies
    assert _http_client_cookies() is None                         # đường dẫn sai → None, không vỡ


def test_http_client_cookies_nap_tu_file_netscape(tmp_path, monkeypatch):
    f = tmp_path / "cookies.txt"
    f.write_text("# Netscape HTTP Cookie File\n"
                 ".youtube.com\tTRUE\t/\tTRUE\t9999999999\tPREF\tf1=50000000\n", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_COOKIES", str(f))
    from src.nap_youtube import _http_client_cookies
    s = _http_client_cookies()
    assert s is not None and s.cookies.get("PREF") == "f1=50000000"  # cookie nạp vào session


def test_video_id_tu_url_cac_dang():
    assert video_id_tu_url("https://www.youtube.com/watch?v=abc123XYZ_0") == "abc123XYZ_0"
    assert video_id_tu_url("https://www.youtube.com/watch?v=abc123XYZ_0&t=42s") == "abc123XYZ_0"
    assert video_id_tu_url("https://youtu.be/abc123XYZ_0") == "abc123XYZ_0"
    assert video_id_tu_url("https://www.youtube.com/shorts/abc123XYZ_0") == "abc123XYZ_0"
    assert video_id_tu_url("abc123XYZ_0") == "abc123XYZ_0"        # id trần → giữ nguyên


def test_ghep_transcript_lam_sach():
    segs = [{"text": "Bước một là", "start": 0.0, "duration": 2.0},
            {"text": "[Âm nhạc]", "start": 2.0, "duration": 1.0},
            {"text": "chọn   ngách\nnhỏ", "start": 3.0, "duration": 2.0}]
    out = ghep_transcript(segs)
    assert out == "Bước một là chọn ngách nhỏ"   # bỏ [Âm nhạc], gộp khoảng trắng/xuống dòng


def test_ghep_transcript_rong():
    assert ghep_transcript([]) == ""


def test_trich_tu_video_noi_acquisition_va_extract(monkeypatch):
    """URL → id → (giả lập) transcript → ghép → de_xuat_trich. Giả lập mạng (monkeypatch),
    writer giả trả 1 đoạn NGUYÊN VĂN có trong transcript → van verbatim giữ lại."""
    monkeypatch.setattr(ny, "lay_transcript", lambda vid, ngon_ngu=("vi", "en"): [
        {"text": "chọn một ngách thật nhỏ để dễ lên top", "start": 0, "duration": 3}])
    tho = "<<<TRICH>>>\nchọn một ngách thật nhỏ để dễ lên top\n<<<LYDO>>>\nchiến lược ngách\n<<<HET>>>"
    kq = trich_tu_video("https://youtu.be/XyZ_9", FakeWriter(tho))
    assert kq["video_id"] == "XyZ_9"
    assert kq["cac_doan"] == [{"trich": "chọn một ngách thật nhỏ để dễ lên top",
                               "dich": "", "ly_do": "chiến lược ngách"}]   # gốc tiếng Việt → dich rỗng


def test_noi_dung_tai_lieu_kem_dich_gan_nhan():
    """Nội dung file = lời gốc + dòng '🇻🇳 Dịch tham khảo' GẮN NHÃN khi có dich; không có dich
    thì chỉ lời gốc (van chống bịa: lời gốc là nguồn sự thật, dịch là nhãn phụ)."""
    from src.nap_youtube import _noi_dung_tai_lieu
    noi_dung = _noi_dung_tai_lieu("Danny Why", "https://youtu.be/XyZ_9", [
        {"trich": "Clicks are emotional", "dich": "Cú click mang tính cảm xúc", "ly_do": "x"},
        {"trich": "chọn ngách thật nhỏ", "dich": "", "ly_do": "y"}])
    assert "Clicks are emotional" in noi_dung                       # lời gốc verbatim
    assert "🇻🇳 Dịch tham khảo: Cú click mang tính cảm xúc" in noi_dung  # dịch gắn nhãn
    assert "chọn ngách thật nhỏ" in noi_dung and noi_dung.count("Dịch tham khảo") == 1  # đoạn VN không thêm dịch
