"""Test endpoint phản hồi 👍/👎 → ghi phan_hoi.csv trong kho — chạy: pytest

Kho tạm riêng từng test (fixture kho_tam trong conftest trỏ KHO_TAI_LIEU sang tmp_path)
→ test không bao giờ ghi rác vào kho thật.
"""

import csv
import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import PHAN_HOI_HEADER, app

tc = TestClient(app)


def _so():
    return Path(os.environ["KHO_TAI_LIEU"]) / "phan_hoi.csv"


def test_phan_hoi_tot_ghi_dung_cot():
    r = tc.post("/phan-hoi", data={
        "question": "ngày 6 cần làm gì?",
        "answer": "Bấm chuông, xem đề xuất... [KD-2026-71369B]",
        "rating": "tot",
        "sources": "KD-2026-71369B — Quy trình ngâm kênh YouTube",
    })
    assert r.status_code == 200 and r.json() == {"ok": True}

    dong = list(csv.reader(_so().open(encoding="utf-8-sig")))
    assert dong[0] == PHAN_HOI_HEADER
    assert len(dong) == 2  # header + đúng 1 dòng
    assert dong[1][1] == "ngày 6 cần làm gì?"
    assert dong[1][3] == "Tốt"
    assert dong[1][4].startswith("KD-2026-71369B")
    assert dong[1][0]  # có thời gian


def test_phan_hoi_te_va_so_chi_ghi_them():
    tc.post("/phan-hoi", data={"question": "q1", "answer": "a1", "rating": "te"})
    tc.post("/phan-hoi", data={"question": "q2", "answer": "a2", "rating": "tot"})

    dong = list(csv.reader(_so().open(encoding="utf-8-sig")))
    assert len(dong) == 3  # header + 2 dòng — chỉ ghi thêm, không sửa dòng cũ
    assert dong[1][3] == "Tệ" and dong[2][3] == "Tốt"


def test_phan_hoi_ghi_cot_bi_chan_quyen():
    """RULE 2: cột 'Bị chặn quyền' = Có/Không — để thống kê 'kho thiếu' bỏ dòng bị chặn."""
    tc.post("/phan-hoi", data={"question": "q1", "answer": "a1", "rating": "te",
                               "bi_chan_quyen": "true"})
    tc.post("/phan-hoi", data={"question": "q2", "answer": "a2", "rating": "te"})  # không gửi cờ

    dong = list(csv.reader(_so().open(encoding="utf-8-sig")))
    assert dong[0][-1] == "Bị chặn quyền"
    assert dong[1][-1] == "Có"      # 👎 do bị chặn quyền → loại khỏi thống kê kho thiếu
    assert dong[2][-1] == "Không"   # 👎 kho thiếu thật → tín hiệu bổ sung tài liệu


def test_phan_hoi_rating_la_bi_chan_422():
    r = tc.post("/phan-hoi", data={"question": "q", "answer": "a", "rating": "xyz"})
    assert r.status_code == 422
    assert not _so().exists()  # bị chặn thì không ghi gì
