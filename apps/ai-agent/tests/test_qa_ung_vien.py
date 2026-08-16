"""Test Q&A bổ sung — cơ chế 2 bước: ung_vien_qa (tìm top ứng viên, ngưỡng liên quan) +
soan_nhap_qa (soạn nháp trên tài liệu Owner chọn, van 'KHÔNG ĐỦ CƠ SỞ') + routes (chỉ Owner).
Mock hết (MOCK_MODE). KHÔNG ghi kho ở lệnh này."""

import os

os.environ["MOCK_MODE"] = "true"

from src.llm.base import LLMProvider
from src.qa_pipeline import SYSTEM_SOAN_QA, QAPipeline
from src.vector_client import QdrantClientWrapper


class DemProvider(LLMProvider):
    def __init__(self, tra_loi="Nháp câu trả lời dựa trên tài liệu."):
        self.tra_loi = tra_loi
        self.so_lan_goi = 0
        self.cac_lan_goi = []

    def generate(self, system_prompt, user_prompt):
        self.so_lan_goi += 1
        self.cac_lan_goi.append((system_prompt, user_prompt))
        return self.tra_loi


def _pipe(writer):
    return QAPipeline(rag=QdrantClientWrapper(mock=True), writer=writer, critics=[])


# ─────────────── BƯỚC 1 — ung_vien_qa ───────────────

def test_ung_vien_qa_co_tai_lieu():
    writer = DemProvider()
    kq = _pipe(writer).ung_vien_qa("quy trình đăng video")
    assert kq["co_tai_lieu"] is True
    mas = [u["doc_code_goc"] for u in kq["ung_vien"]]
    assert 0 < len(mas) <= 3 and len(mas) == len(set(mas))      # ≤ SO_UNG_VIEN_QA, KHÔNG trùng
    assert all({"doc_code_goc", "tieu_de_goc", "diem", "doan_trich"} <= u.keys()
               for u in kq["ung_vien"])
    assert kq["ung_vien"] == sorted(kq["ung_vien"], key=lambda u: u["diem"], reverse=True)
    assert writer.so_lan_goi == 0                               # bước tìm ứng viên KHÔNG gọi LLM


def test_ung_vien_qa_duoi_nguong_bao_khong_co(monkeypatch):
    monkeypatch.setenv("NGUONG_LIEN_QUAN_QA", "0.99")           # cao hơn mọi điểm mock (max 0.91)
    writer = DemProvider()
    kq = _pipe(writer).ung_vien_qa("quy trình đăng video")
    assert kq["co_tai_lieu"] is False and "ung_vien" not in kq
    assert writer.so_lan_goi == 0                               # dưới ngưỡng → KHÔNG gọi LLM


def test_ung_vien_qa_ton_trong_so_ung_vien(monkeypatch):
    monkeypatch.setenv("SO_UNG_VIEN_QA", "1")
    kq = _pipe(DemProvider()).ung_vien_qa("quy trình đăng video")
    assert kq["co_tai_lieu"] is True and len(kq["ung_vien"]) == 1   # cắt đúng top-N từ .env


# ─────────────── BƯỚC 2 — soan_nhap_qa ───────────────

def test_soan_nhap_qa_tren_tai_lieu_da_chon():
    writer = DemProvider("Nháp: đăng khung 19h-21h.")
    kq = _pipe(writer).soan_nhap_qa("quy trình đăng video", "KD-2026-0042")
    assert kq["ok"] is True and kq["doc_code_goc"] == "KD-2026-0042"
    assert kq["nhap"].startswith("Nháp") and kq["cac_nguon"]
    assert kq["khong_du_co_so"] is False
    sys, de = writer.cac_lan_goi[0]                             # writer nhận đúng prompt + đề bài
    assert sys == SYSTEM_SOAN_QA and "KHÔNG ĐỦ CƠ SỞ" in sys
    assert "quy trình đăng video" in de and "Các đoạn tài liệu" in de


def test_soan_nhap_qa_van_khong_du_co_so():
    kq = _pipe(DemProvider("KHÔNG ĐỦ CƠ SỞ")).soan_nhap_qa("câu ngoài lề", "KD-2026-0042")
    assert kq["ok"] is True and kq["khong_du_co_so"] is True    # cờ cảnh báo Owner


def test_soan_nhap_qa_tai_lieu_khong_co_chunk_ok_false():
    writer = DemProvider()
    kq = _pipe(writer).soan_nhap_qa("quy trình đăng video", "KHONG-TON-TAI")
    assert kq["ok"] is False and "message" in kq
    assert writer.so_lan_goi == 0                               # không tài liệu → không soạn


# ─────────────── ROUTES — chỉ Owner (level<5 → 403), trả JSON đúng khóa ───────────────

def test_routes_qa_chi_owner(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from src.main import app

    from claims_v2 import client_claims  # V2: claims thay users.txt + đăng nhập

    HO_SO = {"chu": ("Kinh doanh", 5), "nv": ("Kinh doanh", 2)}

    def login(ten):
        return client_claims(app, ten, *HO_SO[ten])

    owner = login("chu")
    r1 = owner.post("/kho-thieu/ung-vien-qa", data={"cau_hoi": "quy trình đăng video"})
    assert r1.status_code == 200 and "co_tai_lieu" in r1.json()
    r2 = owner.post("/kho-thieu/soan-nhap-qa",
                    data={"cau_hoi": "quy trình đăng video", "doc_code_goc": "KD-2026-0042"})
    assert r2.status_code == 200 and r2.json()["ok"] and "nhap" in r2.json()

    nv = login("nv")                                            # level 2 < Owner → 403 ở SERVER
    assert nv.post("/kho-thieu/ung-vien-qa", data={"cau_hoi": "x"}).status_code == 403
    assert nv.post("/kho-thieu/soan-nhap-qa",
                   data={"cau_hoi": "x", "doc_code_goc": "KD-2026-0042"}).status_code == 403
