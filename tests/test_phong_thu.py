# -*- coding: utf-8 -*-
"""LỚP PHÒNG THỦ API NGOÀI (05/09/2026, spec docs/phong-thu-api-ngoai.md):
4 van tại điểm-ra LLM — allowlist host, secret lọt prompt, trần chi/ngày,
che PII. Vi phạm chủ đích → LoiPhongThu nổi; lỗi nội bộ van → không giết call.
"""
import json
from datetime import date

import pytest

from nen.common import phong_thu


# ---- van 1: kiem_host ----

def test_host_mac_dinh_va_rong_cho_qua():
    phong_thu.kiem_host(None)                    # rỗng = mặc định SDK
    phong_thu.kiem_host("")
    phong_thu.kiem_host("https://api.z.ai/api/paas/v4")
    phong_thu.kiem_host("https://api.anthropic.com")


def test_loopback_duoc_mien_ke_ca_http():
    phong_thu.kiem_host("http://127.0.0.1:9999/v1")
    phong_thu.kiem_host("http://localhost:8760")


def test_host_la_bi_chan():
    with pytest.raises(phong_thu.LoiPhongThu, match="allowlist"):
        phong_thu.kiem_host("https://evil.example.com/v1")


def test_http_khong_loopback_bi_chan():
    # host ĐÚNG allowlist nhưng http trần vẫn chặn — TLS bắt buộc với API ngoài
    with pytest.raises(phong_thu.LoiPhongThu, match="https"):
        phong_thu.kiem_host("http://api.z.ai/api/paas/v4")


def test_them_host_qua_env(monkeypatch):
    monkeypatch.setenv("LLM_HOST_CHO_PHEP", "api.moi.vn, api.khac.com")
    phong_thu.kiem_host("https://api.moi.vn/v1")
    with pytest.raises(phong_thu.LoiPhongThu):
        phong_thu.kiem_host("https://api.chua-khai.com/v1")


def test_moi_nha_llm_ket_khai_deu_duoc_mo_luong(monkeypatch):
    """LƯỚI (sự cố 12/09): KÉT khai nhà 'mwapi' từ 07/09 nhưng api.mwapi.dev KHÔNG có
    trong allowlist → van chặn ngay tại cửa; diễn giải chẩn đoán kênh của Data
    Analytics chết lặng lẽ kể từ đó. Khai bằng env không cứu được vì CHỈ gateway đọc
    .env, app nhận env từ start-all — dễ sót. Nhà nào KÉT đã khai thì phải mở luồng
    SẴN trong allowlist mặc định."""
    monkeypatch.delenv("LLM_HOST_CHO_PHEP", raising=False)
    from nen.ket_cau_hinh.ket import NHA_LLM_INFO
    for nha, tin in NHA_LLM_INFO.items():
        base = tin.get("base_url") or ""
        if not base:
            continue          # rỗng = SDK mặc định của nhà (đã nằm trong allowlist)
        phong_thu.kiem_host(base)   # nhà chưa mở luồng → LoiPhongThu, test đỏ đúng chỗ


# ---- van 2: kiem_secret ----

def test_secret_lot_prompt_bi_chan(monkeypatch):
    monkeypatch.setenv("PT_TEST_API_KEY", "sk-bimat-1234567890")
    with pytest.raises(phong_thu.LoiPhongThu, match="PT_TEST_API_KEY"):
        phong_thu.kiem_secret("he thong", "tai lieu chua key sk-bimat-1234567890 that")


def test_prompt_sach_cho_qua(monkeypatch):
    monkeypatch.setenv("PT_TEST_API_KEY", "sk-bimat-1234567890")
    phong_thu.kiem_secret("cau hoi thuong", "khong dinh gi toi key")


def test_gia_tri_ngan_khong_tinh_la_secret(monkeypatch):
    # tránh dương tính giả kiểu TOKENIZERS_PARALLELISM=false
    monkeypatch.setenv("PT_TEST_TOKEN", "false")
    phong_thu.kiem_secret("prompt co chu false trong cau")


# ---- van 3: kiem_tran ----

def _ghi_so_gia(tmp_path, monkeypatch, dong: list[dict]) -> None:
    monkeypatch.setenv("SO_GOI_DIR", str(tmp_path / "sg"))
    hom_nay = date.today().isoformat()
    d = tmp_path / "sg" / hom_nay[:4] / hom_nay[5:7]
    d.mkdir(parents=True, exist_ok=True)
    with open(d / f"{hom_nay}.log", "w", encoding="utf-8") as f:
        for b in dong:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")


def test_tran_tat_mac_dinh(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_TRAN_USD_NGAY", raising=False)
    monkeypatch.delenv("LLM_TRAN_CALL_NGAY", raising=False)
    _ghi_so_gia(tmp_path, monkeypatch, [{"dich_vu": "llm", "usd": 999.0}])
    phong_thu.kiem_tran()   # không đặt trần = hành vi cũ, không chặn gì


def test_tran_usd_vuot_bi_chan(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_TRAN_USD_NGAY", "5")
    _ghi_so_gia(tmp_path, monkeypatch, [
        {"dich_vu": "llm", "usd": 3.0}, {"dich_vu": "llm", "usd": 2.5},
        {"dich_vu": "youtube", "units": 100},   # dịch vụ khác không tính vào trần LLM
    ])
    with pytest.raises(phong_thu.LoiPhongThu, match="LLM_TRAN_USD_NGAY"):
        phong_thu.kiem_tran()


def test_tran_usd_chua_cham_cho_qua(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_TRAN_USD_NGAY", "5")
    _ghi_so_gia(tmp_path, monkeypatch, [{"dich_vu": "llm", "usd": 4.9}])
    phong_thu.kiem_tran()


def test_tran_call_dem_ca_dong_khong_usd(tmp_path, monkeypatch):
    # stream/model chưa khai giá không có usd nhưng VẪN là call — call cap phải thấy
    monkeypatch.setenv("LLM_TRAN_CALL_NGAY", "2")
    _ghi_so_gia(tmp_path, monkeypatch, [
        {"dich_vu": "llm"}, {"dich_vu": "llm", "ok": False, "ma_loi": "timeout"},
    ])
    with pytest.raises(phong_thu.LoiPhongThu, match="LLM_TRAN_CALL_NGAY"):
        phong_thu.kiem_tran()


def test_tran_loi_noi_bo_khong_giet_call(monkeypatch):
    monkeypatch.setenv("LLM_TRAN_USD_NGAY", "5")
    monkeypatch.setenv("SO_GOI_DIR", "Z:/khong-ton-tai/x")
    phong_thu.kiem_tran()   # sổ không đọc được → van bỏ qua, không raise


# ---- van 4: che_pii ----

def test_che_email_va_sdt():
    ra = phong_thu.che_pii("Lien he a@b.vn hoac 0912 345 678 / +84987654321.")
    assert "a@b.vn" not in ra and "0912" not in ra and "987654321" not in ra
    assert "[email]" in ra and "[sdt]" in ra


def test_che_ten_theo_bang_khong_phan_biet_hoa_thuong():
    ra = phong_thu.che_pii(
        "Trần Việt Thanh và trần việt thanh nghỉ; Thanh Hà đi làm.",
        bang_ten={"Trần Việt Thanh": "NS-016", "Thanh Hà": "NS-002"})
    assert "Trần Việt Thanh" not in ra and "trần việt thanh" not in ra
    assert ra.count("NS-016") == 2 and "NS-002" in ra


def test_khong_an_nham_so_thuong():
    # năm / số thập phân / view count không phải SĐT
    ra = phong_thu.che_pii("Nam 2026 co 84123 video, ti le 0.81 va 100 view.")
    assert ra == "Nam 2026 co 84123 video, ti le 0.81 va 100 view."


# ---- endpoint gateway /api/phong-thu/tran-llm (app tự đủ hỏi trước mỗi call) ----

def _goi_tran(client_addr):
    import asyncio

    import httpx

    from nen.gateway.main import app as gateway_app

    async def goi():
        transport = httpx.ASGITransport(app=gateway_app, client=client_addr)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await c.get("/api/phong-thu/tran-llm")
    return asyncio.run(goi())


def test_endpoint_tran_llm_loopback(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_TRAN_USD_NGAY", raising=False)
    monkeypatch.delenv("LLM_TRAN_CALL_NGAY", raising=False)
    r = _goi_tran(("127.0.0.1", 50000))
    assert r.status_code == 200 and r.json() == {"chan": False}

    monkeypatch.setenv("LLM_TRAN_CALL_NGAY", "1")
    _ghi_so_gia(tmp_path, monkeypatch, [{"dich_vu": "llm"}])
    r = _goi_tran(("127.0.0.1", 50000))
    assert r.json()["chan"] is True and "LLM_TRAN_CALL_NGAY" in r.json()["ly_do"]


def test_endpoint_tran_llm_chan_khong_loopback():
    assert _goi_tran(("192.168.1.50", 50000)).status_code == 403
