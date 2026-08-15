"""Test lõi TỔNG HỢP CÓ NEO (src/tong_hop_neo.py — supervisor.md §2c): 3 van
(neo bắt buộc ở parser / kiểm neo critic / nạp -PT kế thừa quyền gốc). Mock Qdrant + mock LLM."""

import csv
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

import pytest

from src import tong_hop_neo as T
from src.main import CATALOG_HEADER, client, doc_catalog


class GiaLLM:
    """LLM giả: trả văn bản cố định, ghi lại lời gọi."""

    def __init__(self, tra_ve: str):
        self.tra_ve = tra_ve
        self.gois = []

    def generate(self, system, prompt):
        self.gois.append((system, prompt))
        return self.tra_ve


DOAN = [{"trich": "People are not clicking. And when people don't click, YouTube stops "
                  "pushing your videos.", "dich": "Người dùng không nhấp chuột."},
        {"trich": "Your thumbnail should not explain everything, it should create a question "
                  "in the viewer's mind.", "dich": ""},
        {"trich": "Small channels actually have an advantage. When you're small, you can "
                  "experiment freely.", "dich": "Kênh nhỏ có lợi thế thử nghiệm."}]


def _setup():
    client._mock_chunks.clear(); client._mock_payload.clear()
    kho = Path(os.environ["KHO_TAI_LIEU"])
    (kho / "01_Ban-quan-tri").mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["YT-abc", "2026-08-06", "Danny Why — YouTube abc", "Ban quản trị",
                    "Khác", "Còn hiệu lực", "v1", "Giới hạn theo bộ phận", "4",
                    "thumbnail; CTR", "Danny Why", "YT-abc_YouTube.md", "01_Ban-quan-tri",
                    "false", "YT-abc", "", "chuyen_gia", "Danny Why"])
    (kho / "01_Ban-quan-tri" / "YT-abc_YouTube.md").write_text(
        "# Nguồn tham khảo: Danny Why\n# Video: https://youtube.com/watch?v=abc\n\n"
        f"{DOAN[0]['trich']}\n(🇻🇳 Dịch tham khảo: {DOAN[0]['dich']})\n\n"
        f"{DOAN[1]['trich']}\n\n"
        f"{DOAN[2]['trich']}\n(🇻🇳 Dịch tham khảo: {DOAN[2]['dich']})",
        encoding="utf-8")
    return kho


# ─────────────── mã -PT xuôi ngược ───────────────

def test_ma_pt_xuoi_nguoc():
    assert T.ma_pt("YT-abc") == "YT-abc-PT"
    assert T.la_ma_pt("YT-abc-PT") and not T.la_ma_pt("YT-abc")
    assert T.ma_goc_tu_pt("YT-abc-PT") == "YT-abc"
    assert T.ma_goc_tu_pt("YT-abc") == "YT-abc"


# ─────────────── VAN 1: parser neo bắt buộc ───────────────

def test_tong_hop_lesson_learned_du_cau_truc():
    """06/08 user chê 'vài câu cô đọng không đầu cuối' → cấu trúc mới: BỐI CẢNH 5W1H +
    BÀI HỌC có tiêu đề viết liền mạch + ÁP DỤNG; văn bản gốc vào đề bài làm ngữ cảnh."""
    tho = ("<<<CHUDE>>>\nVì sao video không tăng trưởng\n<<<HET>>>\n"
           "<<<BOICANH>>>\nDanny Why là kênh dạy YouTube cho kênh nhỏ; video này giải thích "
           "vì sao video không được đẩy và cách sửa bằng thumbnail.\n<<<HET>>>\n"
           "<<<BAIHOC>>>\nClick là cửa ngõ tăng trưởng\nNhiều kênh đổ lỗi thuật toán nhưng "
           "vấn đề thật là người xem không bấm; khi không có click YouTube ngừng đẩy video, "
           "nên phải sửa từ thumbnail trước tiên.\n<<<NEO>>>\nE1\n<<<HET>>>\n"
           "<<<APDUNG>>>\n- Soát lại thumbnail 10 video gần nhất.\n<<<HET>>>")
    llm = GiaLLM(tho)
    kq = T.tong_hop_co_neo(DOAN, llm, van_ban_goc="toàn bộ transcript ở đây")
    assert "VĂN BẢN GỐC" in llm.gois[0][1] and "toàn bộ transcript" in llm.gois[0][1]
    assert kq["boi_canh"].startswith("Danny Why là kênh")
    assert kq["ap_dung"].startswith("- Soát lại thumbnail")
    assert kq["luan_diem"][0]["tieu_de"] == "Click là cửa ngõ tăng trưởng"
    assert kq["luan_diem"][0]["noi_dung"].startswith("Nhiều kênh đổ lỗi")
    assert kq["luan_diem"][0]["neo"] == [1]


def test_tong_hop_giu_neo_hop_le_loai_khong_neo_va_neo_bia():
    # 4 luận điểm: (1) neo E1,E3 hợp lệ; (2) KHÔNG có khối neo có mã → loại + đếm;
    # (3) neo E9 ngoài phạm vi 3 đoạn → như không neo; (4) delimiter LỆCH '<<<NEO>>' vẫn parse
    tho = ("<<<CHUDE>>>\nVì sao video không tăng trưởng\n<<<HET>>>\n"
           "<<<LUANDIEM>>>\nClick là cửa ngõ của mọi tăng trưởng trên YouTube.\n"
           "<<<NEO>>>\nE1, E3\n<<<HET>>>\n"
           "<<<LUANDIEM>>>\nLuận điểm này hoàn toàn không có bằng chứng nào đứng sau.\n"
           "<<<NEO>>>\nkhông có\n<<<HET>>>\n"
           "<<<LUANDIEM>>>\nLuận điểm neo vào bằng chứng không tồn tại trong danh sách.\n"
           "<<<NEO>>>\nE9\n<<<HET>>>\n"
           "<<<LUANDIEM>>\nThumbnail phải gợi tò mò thay vì giải thích hết nội dung video.\n"
           "<<<NEO>>\nE2\n<<<HET>>")
    kq = T.tong_hop_co_neo(DOAN, GiaLLM(tho))
    assert kq["chu_de"] == "Vì sao video không tăng trưởng"
    assert [ld["neo"] for ld in kq["luan_diem"]] == [[1, 3], [2]]
    assert kq["luan_diem"][0]["tieu_de"] == ""     # khối LUANDIEM cũ: tương thích ngược, không tiêu đề
    assert kq["so_loai_khong_neo"] == 2


def test_tong_hop_khong_doan_khong_goi_model():
    llm = GiaLLM("bất kỳ")
    kq = T.tong_hop_co_neo([], llm)
    assert kq["luan_diem"] == [] and llm.gois == []


# ─────────────── 08/08: bài giảng có hệ thống — bảng thuật ngữ TÙY CHỌN ───────────────

def test_tong_hop_parse_thuat_ngu_tuy_chon():
    tho = ("<<<CHUDE>>>\nChủ đề\n<<<HET>>>\n"
           "<<<BAIHOC>>>\nBài học A\nNội dung đủ dài để không bị lọc bỏ.\n<<<NEO>>>\nE1\n<<<HET>>>\n"
           "<<<THUATNGU>>>\nOutlier | Video vượt trung bình kênh\n"
           "Packaging | Tiêu đề + thumbnail\n<<<HET>>>")
    kq = T.tong_hop_co_neo(DOAN, GiaLLM(tho))
    assert "Outlier | Video vượt trung bình kênh" in kq["thuat_ngu"]
    assert "Packaging | Tiêu đề + thumbnail" in kq["thuat_ngu"]
    assert len(kq["luan_diem"]) == 1   # khối THUATNGU không lẫn vào parser BÀI HỌC


def test_tong_hop_thuat_ngu_rong_khi_khong_co_khoi():
    tho = ("<<<CHUDE>>>\nChủ đề\n<<<HET>>>\n"
           "<<<BAIHOC>>>\nBài học A\nNội dung đủ dài để không bị lọc bỏ.\n<<<NEO>>>\nE1\n<<<HET>>>")
    kq = T.tong_hop_co_neo(DOAN, GiaLLM(tho))
    assert kq["thuat_ngu"] == ""


# ─────────────── VAN 2: kiểm neo ───────────────

def test_kiem_neo_parse_pipe_dau_tieng_viet_va_thieu_dong():
    luan_diem = [{"noi_dung": "A", "neo": [1]}, {"noi_dung": "B", "neo": [2]},
                 {"noi_dung": "C", "neo": [3]}]
    # L1 chuẩn pipe; L2 viết CÓ DẤU + tách bằng ':' (parser phải khoan dung);
    # L3 critic BỎ SÓT → chua_kiem (nói thật, không tự đoán đạt)
    tho = ("L1 | DO_DUOC | bằng chứng nói thẳng điều này\n"
           "L2: KHÔNG ĐỠ — luận điểm thêm dữ kiện lạ")
    kq = T.kiem_neo(luan_diem, DOAN, GiaLLM(tho))
    assert [v["ket_qua"] for v in kq] == ["do_duoc", "khong_do", "chua_kiem"]
    assert kq[0]["ghi_chu"] == "bằng chứng nói thẳng điều này"


def test_kiem_neo_khong_do_thang_do_duoc_khi_chua_ca_hai():
    # "KHONG_DO" chứa chuỗi 'DO' — phải xét KHONG_DO trước, không nhận nhầm do_duoc
    assert T._tim_phan_quyet("KHONG_DO") == "khong_do"
    assert T._tim_phan_quyet("Suy rộng") == "suy_rong"
    assert T._tim_phan_quyet("ĐỠ ĐƯỢC") == "do_duoc"
    assert T._tim_phan_quyet("không rõ") is None


def test_phan_tich_co_neo_gop_phan_quyet():
    tho_writer = ("<<<CHUDE>>>\nChủ đề\n<<<HET>>>\n"
                  "<<<LUANDIEM>>>\nLuận điểm một đủ dài để không bị lọc.\n<<<NEO>>>\nE1\n<<<HET>>>")
    kq = T.phan_tich_co_neo(DOAN, GiaLLM(tho_writer), GiaLLM("L1 | SUY_RONG | khái quát hợp lý"))
    assert kq["luan_diem"][0]["ket_qua"] == "suy_rong"
    assert kq["luan_diem"][0]["ghi_chu"] == "khái quát hợp lý"


# ─────────────── đọc bằng chứng từ file tài liệu trích ───────────────

def test_doc_doan_tu_file_goc():
    _setup()
    doan = T.doc_doan_tu_file_goc("YT-abc")
    assert [d["trich"] for d in doan] == [d["trich"] for d in DOAN]
    assert doan[0]["dich"] == DOAN[0]["dich"] and doan[1]["dich"] == ""


def test_doc_doan_goc_khong_ton_tai_raise():
    _setup()
    with pytest.raises(ValueError):
        T.doc_doan_tu_file_goc("YT-khong-co")


# ─────────────── VAN 3 xong → nạp -PT kế thừa quyền, ghi đè không nhân bản ───────────────

LD = [{"noi_dung": "Click là cửa ngõ tăng trưởng.", "neo": [1, 3]},
      {"noi_dung": "Thumbnail gợi tò mò, không giải thích hết.", "neo": [2]}]


def test_nap_ban_phan_tich_lan_dau_ke_thua_quyen():
    kho = _setup()
    kq = T.nap_ban_phan_tich("YT-abc", "Vì sao video không tăng trưởng", LD, client,
                             "2026-08-06T10:00:00",
                             boi_canh="Kênh Danny Why dạy YouTube.",
                             ap_dung="- Soát thumbnail.")
    assert kq["ok"] and kq["lan_dau"] and kq["ma_pt"] == "YT-abc-PT"
    f = kho / "01_Ban-quan-tri" / "YT-abc-PT_Phan-tich.md"
    assert f.is_file()
    noi = f.read_text(encoding="utf-8")
    assert "# Bài học kinh nghiệm:" in noi
    assert "## Bối cảnh" in noi and "Kênh Danny Why dạy YouTube." in noi
    assert "## Áp dụng ngay" in noi and "- Soát thumbnail." in noi
    assert "(Dẫn chứng: E1, E3 — YT-abc)" in noi
    # KHÔNG chép lại bằng chứng vào file -PT (tránh đúp chunk khi search)
    assert DOAN[0]["trich"] not in noi

    pt = [r for r in doc_catalog() if r["Mã tài liệu"] == "YT-abc-PT"]
    assert len(pt) == 1
    goc = next(r for r in doc_catalog() if r["Mã tài liệu"] == "YT-abc")
    for cot in ("Bộ phận", "Mức truy cập", "Level tối thiểu", "Hiệu lực",
                "Tầng nguồn", "Tên nguồn"):
        assert pt[0][cot] == goc[cot], cot
    assert client.dem_chunk_doc_code("YT-abc-PT") >= 1


def test_nap_ban_phan_tich_muc_luc_va_bang_thuat_ngu():
    """08/08: bài giảng có hệ thống — mục lục CODE tự dựng (không nhờ LLM, tránh lệch) +
    heading 'Phần N' thay 'Bài học N' + bảng thuật ngữ TÙY CHỌN render từ text thô."""
    kho = _setup()
    T.nap_ban_phan_tich("YT-abc", "Vì sao video không tăng trưởng", LD, client,
                       "2026-08-08T10:00:00",
                       boi_canh="Kênh Danny Why dạy YouTube.",
                       ap_dung="- Soát thumbnail.",
                       thuat_ngu="Outlier | Video vượt trung bình kênh\nCTR | Tỉ lệ click")
    noi = (kho / "01_Ban-quan-tri" / "YT-abc-PT_Phan-tich.md").read_text(encoding="utf-8")
    assert "## Mục lục" in noi
    assert "- Bối cảnh" in noi and "- Phần 1 —" in noi and "- Phần 2 —" in noi
    assert "- Áp dụng ngay" in noi and "- Bảng thuật ngữ" in noi
    assert "## Phần 1 —" in noi and "## Bài học 1" not in noi
    assert "## Bảng thuật ngữ" in noi
    assert "| Outlier | Video vượt trung bình kênh |" in noi
    assert "| CTR | Tỉ lệ click |" in noi


def test_nap_ban_phan_tich_khong_thuat_ngu_khong_hien_bang():
    kho = _setup()
    T.nap_ban_phan_tich("YT-abc", "Chủ đề", LD, client, "2026-08-08T10:00:00")
    noi = (kho / "01_Ban-quan-tri" / "YT-abc-PT_Phan-tich.md").read_text(encoding="utf-8")
    assert "Bảng thuật ngữ" not in noi


def test_nap_ban_phan_tich_chi_luan_diem_khong_hien_muc_luc():
    """Chỉ 1 bài học, không bối cảnh/áp dụng/thuật ngữ → mục lục 1 dòng vô nghĩa, bỏ hẳn."""
    kho = _setup()
    T.nap_ban_phan_tich("YT-abc", "Chủ đề", LD[:1], client, "2026-08-08T10:00:00")
    noi = (kho / "01_Ban-quan-tri" / "YT-abc-PT_Phan-tich.md").read_text(encoding="utf-8")
    assert "## Mục lục" not in noi
    assert "## Phần 1 —" in noi


def test_nap_ban_phan_tich_lan_hai_ghi_de_khong_them_dong(monkeypatch):
    kho = _setup()
    T.nap_ban_phan_tich("YT-abc", "Chủ đề", LD, client, "2026-08-06T10:00:00")
    goi = {}
    that = client.cap_nhat_noi_dung

    def spy(fp, md):
        goi["md"] = md
        return that(fp, md)
    monkeypatch.setattr(client, "cap_nhat_noi_dung", spy)
    kq = T.nap_ban_phan_tich("YT-abc", "Chủ đề mới", LD[:1], client, "2026-08-07T09:00:00")
    assert kq["lan_dau"] is False and goi["md"]["doc_code"] == "YT-abc-PT"
    assert len([r for r in doc_catalog() if r["Mã tài liệu"] == "YT-abc-PT"]) == 1
    noi = (kho / "01_Ban-quan-tri" / "YT-abc-PT_Phan-tich.md").read_text(encoding="utf-8")
    assert "Chủ đề mới" in noi and "Thumbnail gợi tò mò" not in noi   # GHI ĐÈ, không nối


def test_ma_goc_phan_tich_nhan_ca_link_lan_ma():
    # Ca thật 06/08: user dán LINK video vào ô mã Bước 2 → phải quy về YT-<id>, mã thì giữ nguyên
    from src.main import _ma_goc_phan_tich
    assert _ma_goc_phan_tich("https://www.youtube.com/watch?v=14Vm0CiyUVE") == "YT-14Vm0CiyUVE"
    assert _ma_goc_phan_tich("https://youtu.be/lL5EyiQQei0") == "YT-lL5EyiQQei0"
    assert _ma_goc_phan_tich("  YT-lL5EyiQQei0  ") == "YT-lL5EyiQQei0"
    assert _ma_goc_phan_tich("KD-2026-1814CB") == "KD-2026-1814CB"


def test_nap_ban_phan_tich_rong_raise():
    _setup()
    with pytest.raises(ValueError):
        T.nap_ban_phan_tich("YT-abc", "Chủ đề", [{"noi_dung": "  ", "neo": [1]}], client,
                            "2026-08-06T10:00:00")
