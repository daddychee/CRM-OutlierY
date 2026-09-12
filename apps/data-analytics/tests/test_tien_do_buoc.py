# -*- coding: utf-8 -*-
"""TIẾN ĐỘ THEO BƯỚC (Owner chốt 12/09) — thay con số giây trần trụi.

Owner hỏi giữa lần chạy Cooking_DEU: "tiến trình có đang chạy hay không?". Màn
hình chỉ có "Researching… 792s" nên không trả lời được — phải vào tận máy soi
tiến trình và nhật ký mới biết nó đang quét bình luận ở bước 3/20.

Nhưng nhật ký ĐÃ ghi sẵn bước: `>>> [3/20] S4  comments -> viewer questions`.
Chỉ cần bóc ra là trang nói được "Bước 3/20 · S4 …" — không tốn thêm lời gọi nào.

ĐẾM NGƯỢC thì CHƯA làm (Owner chốt mức 1 trước): cả lịch sử trên đĩa chỉ có ĐÚNG
MỘT lần chạy đủ cấu hình để đối chiếu (OldNewbie_US 12/09 — 33,7p pipeline + 6,5p
writer), ba lần tháng 8 thì chạy khi chưa có tầng LLM lẫn deepdive nên không so
được. Đoán giờ còn lại từ một mẫu là bịa. Vì vậy dòng bước kèm GIỜ (mức 2 gom dữ
liệu): mỗi lần chạy tự để lại thời lượng thật của từng bước, vài lần nữa là đủ
căn cứ cho đếm ngược.
"""
import pytest

from src import niche_run


def _log(tmp_path, monkeypatch, noi_dung: str):
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path))
    nd = tmp_path / "Proj_X" / "niche-data"
    nd.mkdir(parents=True)
    (nd / "stdout.log").write_text(noi_dung, encoding="utf-8")
    return "Proj_X"


def test_doc_duoc_buoc_dang_chay(tmp_path, monkeypatch):
    p = _log(tmp_path, monkeypatch,
             ">>> [1/20] S1  scan competitor videos\n"
             "    290/400 videos processed (290 fetched)\n"
             ">>> [3/20] S4  comments -> viewer questions\n"
             "      330/400 videos processed (30,826 comments so far)\n")
    tt = niche_run.tinh_trang(p)
    assert tt["buoc"], "nhật ký ghi sẵn [3/20] mà trạng thái không nói được đang ở bước nào"
    assert tt["buoc"]["so"] == 3 and tt["buoc"]["tong"] == 20
    assert "S4" in tt["buoc"]["ten"]


def test_dong_buoc_co_gio_van_doc_duoc(tmp_path, monkeypatch):
    """Format mới có giờ (sổ cho đếm ngược về sau) — bóc bước vẫn phải đúng."""
    p = _log(tmp_path, monkeypatch,
             ">>> [1/20] 12:24:07  S1  scan competitor videos\n"
             ">>> [4/20] 12:39:43  S5  demand & trend\n")
    tt = niche_run.tinh_trang(p)
    assert tt["buoc"]["so"] == 4 and tt["buoc"]["tong"] == 20
    assert "S5" in tt["buoc"]["ten"]
    assert tt["buoc"]["luc"] == "12:39:43"      # mốc bắt đầu bước — nguyên liệu mức 2


def test_log_cu_khong_co_dong_buoc_thi_khong_vo(tmp_path, monkeypatch):
    """Log đời cũ / vừa khởi động chưa in bước nào → nói 'chưa rõ', không nổ."""
    p = _log(tmp_path, monkeypatch, "Input: x\nProject: y\n")
    tt = niche_run.tinh_trang(p)
    assert tt["co_log"] is True
    assert tt["buoc"] is None


def test_trang_thai_tra_buoc_cho_ui(tmp_path, monkeypatch):
    """Poll của dashboard phải mang theo bước, nếu không JS vẫn chỉ có số giây."""
    p = _log(tmp_path, monkeypatch, ">>> [7/20] 12:41:00  S9b  namer (LLM)\n")

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"running": True, "has_report": False}

    monkeypatch.setattr(niche_run.requests, "get", lambda url, **kw: _Resp())
    st = niche_run.trang_thai(p, {"ten": "bot", "level": 5, "vai": "owner"})
    assert st["running"] is True
    assert st["buoc"]["so"] == 7 and "S9b" in st["buoc"]["ten"]
