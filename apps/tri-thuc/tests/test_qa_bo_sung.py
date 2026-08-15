"""Test LÕI Q&A bổ sung (src/qa_bo_sung.py): tạo/nối file Q&A đi kèm tài liệu gốc
(mã -QA), kế thừa quyền gốc, nạp Qdrant. Mock Qdrant (MOCK_MODE)."""

import csv
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

import pytest

from src import qa_bo_sung as Q
from src.main import CATALOG_HEADER, client, doc_catalog


def _setup():
    client._mock_chunks.clear(); client._mock_payload.clear()
    kho = Path(os.environ["KHO_TAI_LIEU"])
    (kho / "05_Kinh-doanh").mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["KD-1", "2026-07-01", "Quy trình bán hàng", "Kinh doanh", "Quy trình",
                    "Còn hiệu lực", "v1", "Giới hạn theo bộ phận", "3", "bán hàng, quy trình",
                    "An", "goc.txt", "05_Kinh-doanh", "False", "KD-1", ""])
    return kho


# ─────────────── mã Q&A xuôi–ngược ───────────────

def test_ma_qa_xuoi_nguoc():
    assert Q.ma_qa("KD-2026-1814CB") == "KD-2026-1814CB-QA"
    assert Q.ma_goc_tu_qa("KD-2026-1814CB-QA") == "KD-2026-1814CB"
    assert Q.la_ma_qa("KD-2026-1814CB-QA") is True
    assert Q.la_ma_qa("KD-2026-1814CB") is False
    assert Q.ma_goc_tu_qa("KD-1") == "KD-1"          # không phải QA → giữ nguyên


# ─────────────── lần đầu: tạo file + 1 dòng catalog, kế thừa quyền gốc ───────────────

def test_them_cap_qa_lan_dau_tao_file_va_catalog():
    kho = _setup()
    kq = Q.them_cap_qa("KD-1", "GA là gì?", "GA là Google Analytics.", client,
                       "2026-07-22T10:00:00")
    assert kq["ok"] and kq["lan_dau"] is True and kq["ma_qa"] == "KD-1-QA"

    f = kho / "05_Kinh-doanh" / "KD-1-QA_Q&A-bo-sung.md"      # đúng tên/ngăn
    assert f.is_file()
    noi = f.read_text(encoding="utf-8")
    assert "# Q&A bổ sung cho: Quy trình bán hàng (KD-1)" in noi
    assert "## Hỏi: GA là gì?" in noi and "Đáp: GA là Google Analytics." in noi

    qa = [r for r in doc_catalog() if r["Mã tài liệu"] == "KD-1-QA"]
    assert len(qa) == 1                                       # đúng 1 dòng catalog -QA
    qa = qa[0]
    goc = next(r for r in doc_catalog() if r["Mã tài liệu"] == "KD-1")
    for cot in ("Bộ phận", "Mức truy cập", "Level tối thiểu", "Hiệu lực"):
        assert qa[cot] == goc[cot], cot                       # quyền KHỚP gốc
    assert qa["document_id"] and qa["Ngăn"] == "05_Kinh-doanh"
    assert client.dem_chunk_doc_code("KD-1-QA") >= 1          # đã nạp Qdrant


# ─────────────── lần 2: nối cặp, KHÔNG thêm dòng catalog, gọi cap_nhat_noi_dung ───────────────

def test_them_cap_qa_lan_hai_khong_them_dong_catalog(monkeypatch):
    _setup()
    Q.them_cap_qa("KD-1", "câu 1?", "đáp 1", client, "2026-07-22T10:00:00")

    goi = {"n": 0}
    that = client.cap_nhat_noi_dung
    def spy(fp, md):
        goi["n"] += 1
        return that(fp, md)
    monkeypatch.setattr(client, "cap_nhat_noi_dung", spy)

    kq = Q.them_cap_qa("KD-1", "câu 2?", "đáp 2", client, "2026-07-22T11:00:00")
    assert kq["lan_dau"] is False and goi["n"] == 1           # nối → cap_nhat_noi_dung
    assert len([r for r in doc_catalog() if r["Mã tài liệu"] == "KD-1-QA"]) == 1  # KHÔNG thêm dòng
    assert len(Q.doc_cap_qa("KD-1")) == 2                     # file có 2 cặp


# ─────────────── doc_cap_qa đọc lại đúng nội dung ───────────────

def test_doc_cap_qa_doc_dung():
    _setup()
    assert Q.doc_cap_qa("KD-1") == []                         # chưa có → []
    Q.them_cap_qa("KD-1", "Hỏi A?", "Đáp A dài\ndòng 2", client, "2026-07-22T10:00:00")
    Q.them_cap_qa("KD-1", "Hỏi B?", "Đáp B", client, "2026-07-22T11:00:00")
    cap = Q.doc_cap_qa("KD-1")
    assert [c["hoi"] for c in cap] == ["Hỏi A?", "Hỏi B?"]
    assert cap[0]["dap"] == "Đáp A dài\ndòng 2"               # đáp nhiều dòng vẫn nguyên
    assert cap[0]["thoi_gian"] == "2026-07-22T10:00:00"


# ─────────────── gốc không tồn tại → ValueError ───────────────

def test_goc_khong_ton_tai_raise():
    _setup()
    with pytest.raises(ValueError):
        Q.them_cap_qa("KHONG-CO", "x?", "y", client, "2026-07-22T10:00:00")
