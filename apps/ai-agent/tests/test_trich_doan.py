"""Test LÕI module extract (src/trich_doan.py): LLM đề xuất đoạn NGUYÊN VĂN, VAN VERBATIM
loại đoạn LLM bịa/viết lại. Writer giả (không gọi API thật)."""

from src.trich_doan import SYSTEM_TRICH, de_xuat_trich


class FakeWriter:
    def __init__(self, tho):
        self.tho = tho
        self.calls = []

    def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.tho


VAN_BAN = ("Bước một là chọn một ngách thật nhỏ để dễ lên top tìm kiếm. "
           "Sau đó đăng video đều đặn mỗi tuần, đừng ngắt quãng. "
           "Đừng chạy theo trend nếu bạn chưa hiểu rõ ngách của mình.")


def _khoi(trich, ly_do):
    return f"<<<TRICH>>>\n{trich}\n<<<LYDO>>>\n{ly_do}\n<<<HET>>>\n"


def test_giu_doan_verbatim_bo_doan_bia():
    tho = (_khoi("chọn một ngách thật nhỏ để dễ lên top tìm kiếm", "chiến lược ngách")
           + _khoi("hãy mua ngay khóa học triệu view của tôi hôm nay", "câu LLM bịa — không có trong nguồn"))
    kq = de_xuat_trich(VAN_BAN, FakeWriter(tho))
    trichs = [d["trich"] for d in kq]
    assert any("ngách thật nhỏ" in t for t in trichs)       # đoạn NGUYÊN VĂN → giữ
    assert not any("mua ngay khóa học" in t for t in trichs)  # đoạn LLM bịa → BỎ (van verbatim)
    assert kq[0]["ly_do"] == "chiến lược ngách"              # lý do (nhận xét LLM) tách riêng
    assert kq[0]["dich"] == ""                               # không có khối DICH → dich rỗng


def _khoi_dich(trich, dich, ly_do):
    return f"<<<TRICH>>>\n{trich}\n<<<DICH>>>\n{dich}\n<<<LYDO>>>\n{ly_do}\n<<<HET>>>\n"


def test_khoi_dich_duoc_parse_kem_doan_gia():
    """Khối <<<DICH>>> → dich đi kèm đoạn; van verbatim VẪN chỉ kiểm lời gốc (dich không bị kiểm)."""
    tho = _khoi_dich("chọn một ngách thật nhỏ để dễ lên top tìm kiếm",
                     "pick a very small niche to rank easily", "chiến lược ngách")
    kq = de_xuat_trich(VAN_BAN, FakeWriter(tho))
    assert len(kq) == 1
    assert "ngách thật nhỏ" in kq[0]["trich"]                # lời gốc verbatim giữ
    assert kq[0]["dich"] == "pick a very small niche to rank easily"  # bản dịch (nhãn phụ) giữ nguyên
    assert kq[0]["ly_do"] == "chiến lược ngách"


def test_dich_bia_khong_lam_hong_van_verbatim():
    """Đoạn trích PHẢI verbatim; dich bịa/khác gốc KHÔNG cứu được đoạn trích sai."""
    tho = _khoi_dich("Nên chọn ngách nhỏ để nhanh lên top", "bản dịch bất kỳ", "paraphrase")
    assert de_xuat_trich(VAN_BAN, FakeWriter(tho)) == []     # trich không verbatim → loại cả đoạn


def test_doan_viet_lai_bi_loai():
    # LLM PARAPHRASE (đổi chữ) thay vì chép nguyên văn → không phải substring → loại
    tho = _khoi("Nên chọn ngách nhỏ để nhanh lên top", "diễn giải lại, không nguyên văn")
    assert de_xuat_trich(VAN_BAN, FakeWriter(tho)) == []


def test_doan_qua_ngan_bi_loai():
    tho = _khoi("mỗi tuần", "quá ngắn, thiếu ngữ cảnh")     # verbatim nhưng < DAI_TOI_THIEU
    assert de_xuat_trich(VAN_BAN, FakeWriter(tho)) == []


def test_ton_trong_so_doan():
    tho = (_khoi("chọn một ngách thật nhỏ để dễ lên top tìm kiếm", "a")
           + _khoi("đăng video đều đặn mỗi tuần, đừng ngắt quãng", "b")
           + _khoi("đừng chạy theo trend nếu bạn chưa hiểu rõ ngách của mình", "c"))
    assert len(de_xuat_trich(VAN_BAN, FakeWriter(tho), so_doan=2)) == 2  # cắt đúng top-N


def test_van_ban_rong_khong_goi_writer():
    w = FakeWriter("")
    assert de_xuat_trich("   ", w) == []
    assert w.calls == []                                     # rỗng → KHÔNG gọi LLM


def test_delimiter_lech_van_parse_duoc():
    """Regex khoan dung: GLM thật hay viết lệch số dấu </> (vd '<<<LYDO>>' thiếu 1 dấu).
    Đoạn verbatim vẫn phải parse + giữ (bug kiểm chứng video Danny 24/07)."""
    tho = ("<<<TRICH>>>\nchọn một ngách thật nhỏ để dễ lên top tìm kiếm\n"
           "<<<LYDO>>\nchiến lược ngách\n<<HET>>")   # LYDO 2 dấu >, HET 2 dấu <>
    kq = de_xuat_trich(VAN_BAN, FakeWriter(tho))
    assert len(kq) == 1 and "ngách thật nhỏ" in kq[0]["trich"]


def test_prompt_buoc_nguyen_van():
    w = FakeWriter("")
    de_xuat_trich(VAN_BAN, w)
    sys = w.calls[0][0]
    assert sys == SYSTEM_TRICH
    assert "NGUYÊN VĂN" in sys and "KHÔNG viết lại" in sys and "KHÔNG tóm tắt" in sys
