"""Test luồng MỘT CỬA /nguon/tron-goi (user chốt 06/08): link → trích → tổng hợp → kiểm neo,
CHẠY NỀN + POLL (chốt 06/08 lần 3 sau sự cố chờ 30') + nháp lưu đĩa thành LỊCH SỬ.
Giả lập mạng + LLM (dispatch theo system prompt — MỘT writer phục vụ cả 3 vai khi CRITICS tắt).
TestClient chạy BackgroundTasks NGAY sau response → poll trạng thái được liền trong test."""

import json
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from fastapi.testclient import TestClient

import src.nap_youtube as ny
from src.main import CATALOG_HEADER, app, client, doc_catalog, qa

_TRANSCRIPT = [{"text": "chọn một ngách thật nhỏ để dễ lên top", "start": 0, "duration": 3}]
_THO_TRICH = ("<<<TRICH>>>\nchọn một ngách thật nhỏ để dễ lên top\n"
              "<<<LYDO>>>\nchiến lược ngách\n<<<HET>>>")
_THO_TONG_HOP = ("<<<CHUDE>>>\nChiến lược chọn ngách\n<<<HET>>>\n"
                 "<<<BOICANH>>>\nVideo dạy kênh nhỏ cách chọn ngách để dễ lên top.\n<<<HET>>>\n"
                 "<<<BAIHOC>>>\nNgách nhỏ dễ thắng\n"
                 "Ngách càng nhỏ càng dễ chiếm vị trí đầu trong tìm kiếm.\n"
                 "<<<NEO>>>\nE1\n<<<HET>>>\n"
                 "<<<APDUNG>>>\n- Chọn một ngách hẹp trước khi mở rộng.\n<<<HET>>>\n"
                 "<<<TUKHOA>>>\nngách, tìm kiếm\n<<<HET>>>")
_THO_KIEM = "L1 | DO_DUOC | bằng chứng nói thẳng"


def _writer_3_vai(system, prompt):
    if "BIÊN TẬP" in system:
        return _THO_TRICH
    if "BÀI HỌC KINH NGHIỆM" in system:
        return _THO_TONG_HOP
    return _THO_KIEM


def _login(tmp_path, monkeypatch, dong):
    # V2: claims thay users.txt — 'dong' giữ khuôn cũ ten:mk:bo_phan:level, parse ra claims
    from claims_v2 import client_claims
    ten, _, bo_phan, level = dong.strip().splitlines()[0].split(":")
    return client_claims(app, ten, bo_phan, int(level))


def _mock_llm(monkeypatch):
    monkeypatch.setattr(ny, "lay_transcript", lambda vid, ngon_ngu=("vi", "en"): _TRANSCRIPT)
    monkeypatch.setattr(qa.writer, "generate", _writer_3_vai)
    monkeypatch.setattr(qa, "critics", [])   # kiểm neo rơi về writer (dispatch THẨM PHÁN)


def _de_xuat_nen(c, url):
    """Giao việc nền → poll trạng thái (TestClient đã chạy xong task) → (task_id, trạng thái)."""
    r = c.post("/nguon/tron-goi/de-xuat", data={"url": url})
    assert r.status_code == 200 and r.json()["loai"] == "nen"
    tid = r.json()["task_id"]
    r2 = c.get(f"/nguon/tron-goi/trang-thai/{tid}")
    assert r2.status_code == 200
    return tid, r2.json()


def _file_nhap(tid):
    return Path(os.environ["KHO_TAI_LIEU"]) / "nhap-phan-tich" / f"{tid}.json"


def test_tron_goi_nen_tra_du_nhap_va_ghi_nhap_ra_dia(tmp_path, monkeypatch):
    _mock_llm(monkeypatch)
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    tid, tt = _de_xuat_nen(c, "https://youtu.be/XyZ_9")
    assert tt["trang_thai"] == "xong"
    kq = tt["ket_qua"]
    assert kq["che_do"] == "moi" and kq["video_id"] == "XyZ_9" and len(kq["cac_doan"]) == 1
    assert kq["chu_de"] == "Chiến lược chọn ngách"
    assert kq["boi_canh"].startswith("Video dạy kênh nhỏ")   # lesson-learned: có bối cảnh 5W1H
    assert kq["ap_dung"].startswith("- Chọn một ngách")
    assert kq["tu_khoa"] == "ngách, tìm kiếm"          # máy đề xuất từ khóa NGẮN cho màn duyệt
    assert kq["luan_diem"][0]["tieu_de"] == "Ngách nhỏ dễ thắng"
    assert kq["luan_diem"][0]["neo"] == [1]
    assert kq["luan_diem"][0]["ket_qua"] == "do_duoc"     # kiểm neo đã chạy trong nền
    assert kq["van_ban_goc"]                              # transcript theo nháp làm ngữ cảnh
    assert _file_nhap(tid).is_file()                      # nháp BỀN trên đĩa → lịch sử/sống qua restart


def test_so_doan_mac_dinh_tang_va_co_tran(tmp_path, monkeypatch):
    """08/08: so_doan mặc định 12→20 (đủ bằng chứng cho bài giảng 8-15 khối); trần 20→30."""
    import src.main as app_mod

    _mock_llm(monkeypatch)
    goi = {}
    that = app_mod.de_xuat_trich

    def spy(van_ban, writer, so_doan, nguon=""):
        goi["so_doan"] = so_doan
        return that(van_ban, writer, so_doan, nguon=nguon)
    monkeypatch.setattr(app_mod, "de_xuat_trich", spy)
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")

    _de_xuat_nen(c, "https://youtu.be/gioihan1")
    assert goi["so_doan"] == 20   # mặc định mới khi không truyền so_doan

    goi.clear()
    r = c.post("/nguon/tron-goi/de-xuat", data={"url": "https://youtu.be/gioihan2", "so_doan": "999"})
    tid = r.json()["task_id"]
    c.get(f"/nguon/tron-goi/trang-thai/{tid}")
    assert goi["so_doan"] == 30   # trần chặn số quá lớn


def _kho_co_tai_lieu_trich():
    """Dựng kho có sẵn tài liệu trích YT-abc (giả lập video đã nạp từ trước) + 1 tài liệu
    NỘI BỘ để kiểm /nguon/xem không thành đường đọc tài liệu nội bộ."""
    import csv
    kho = Path(os.environ["KHO_TAI_LIEU"])
    (kho / "05_Kinh-doanh").mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["YT-abc", "2026-08-06", "Danny Why — YouTube abc", "Kinh doanh", "Khác",
                    "Còn hiệu lực", "v1", "Công khai nội bộ", "1", "ngách", "Danny Why",
                    "YT-abc_YouTube.md", "05_Kinh-doanh", "false", "YT-abc", "",
                    "chuyen_gia", "Danny Why"])
        w.writerow(["KD-1", "2026-08-01", "SOP nội bộ", "Kinh doanh", "Quy trình",
                    "Còn hiệu lực", "v1", "Công khai nội bộ", "1", "sop", "An",
                    "KD-1_sop.md", "05_Kinh-doanh", "false", "KD-1", "", "noi_bo", "Official"])
    (kho / "05_Kinh-doanh" / "YT-abc_YouTube.md").write_text(
        "# Nguồn tham khảo: Danny Why\n\nchọn một ngách thật nhỏ để dễ lên top",
        encoding="utf-8")
    (kho / "05_Kinh-doanh" / "KD-1_sop.md").write_text("bí mật nội bộ", encoding="utf-8")


def test_tron_goi_nhan_ra_tai_lieu_da_nap_khong_tai_phu_de(tmp_path, monkeypatch):
    """MỘT Ô NHẬP: dán lại link video ĐÃ NẠP → che_do='kho', phân tích lại từ bằng chứng
    trong kho, TUYỆT ĐỐI không gọi YouTube lấy phụ đề."""
    def khong_duoc_goi(*a, **k):
        raise AssertionError("Đã nạp rồi thì KHÔNG được tải lại phụ đề")
    monkeypatch.setattr(ny, "lay_transcript", khong_duoc_goi)
    monkeypatch.setattr(qa.writer, "generate", _writer_3_vai)
    monkeypatch.setattr(qa, "critics", [])
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    _kho_co_tai_lieu_trich()
    for dau_vao in ("https://youtu.be/abc", "YT-abc"):     # link lẫn mã đều nhận
        _, tt = _de_xuat_nen(c, dau_vao)
        assert tt["trang_thai"] == "xong", dau_vao
        assert tt["ket_qua"]["che_do"] == "kho" and tt["ket_qua"]["doc_code_goc"] == "YT-abc"


def test_tron_goi_ma_khong_ton_tai_404_chi_duong(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").post(
        "/nguon/tron-goi/de-xuat", data={"url": "YT-khong-co"})
    assert r.status_code == 404 and "dán link YouTube" in r.json()["detail"]


def test_tron_goi_loi_phu_de_vao_trang_thai_loi(tmp_path, monkeypatch):
    """Lỗi trong NỀN không còn là HTTP 422 — thành trạng thái 'loi' của tác vụ, thông điệp
    vẫn tách đúng tầng (phụ đề vs model, bài học 25/07)."""
    def no(*a, **k):
        raise RuntimeError("no transcript")
    monkeypatch.setattr(ny, "lay_transcript", no)
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    tid, tt = _de_xuat_nen(c, "https://youtu.be/XyZ_9")
    assert tt["trang_thai"] == "loi" and "phụ đề" in tt["loi"]
    assert _file_nhap(tid).is_file()                      # lượt lỗi CŨNG vào lịch sử (xóa được)


def test_tron_goi_nhan_vien_403(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "nv:mk:Kinh doanh:2\n").post(
        "/nguon/tron-goi/de-xuat", data={"url": "https://youtu.be/XyZ_9"})
    assert r.status_code == 403


# ─────────────── 🕘 LỊCH SỬ + XEM LẠI trên GUI ───────────────

def test_lich_su_gom_nhap_va_kho(tmp_path, monkeypatch):
    _mock_llm(monkeypatch)
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    _kho_co_tai_lieu_trich()
    tid, _ = _de_xuat_nen(c, "https://youtu.be/XyZ_9")    # 1 nháp chờ duyệt
    r = c.get("/nguon/lich-su")
    assert r.status_code == 200
    j = r.json()
    assert any(n["id"] == tid and n["trang_thai"] == "xong" for n in j["nhap"])
    kho = {k["ma"]: k for k in j["kho"]}
    assert "YT-abc" in kho and kho["YT-abc"]["nguon_ten"] == "Danny Why"
    assert "KD-1" not in kho                              # tài liệu NỘI BỘ không vào lịch sử nguồn


def test_xem_noi_dung_nguon_va_chan_noi_bo(tmp_path, monkeypatch):
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    _kho_co_tai_lieu_trich()
    r = c.get("/nguon/xem/YT-abc")
    assert r.status_code == 200
    assert "chọn một ngách thật nhỏ" in r.json()["noi_dung"]
    assert c.get("/nguon/xem/KD-1").status_code == 404    # noi_bo → 404 lặng lẽ, không lộ nội dung


def test_xoa_nhap_khoi_lich_su(tmp_path, monkeypatch):
    _mock_llm(monkeypatch)
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    tid, _ = _de_xuat_nen(c, "https://youtu.be/XyZ_9")
    assert c.post("/nguon/nhap/xoa", data={"nhap_id": tid}).status_code == 200
    assert not _file_nhap(tid).is_file()
    assert c.post("/nguon/nhap/xoa", data={"nhap_id": tid}).status_code == 404


def test_tron_goi_duyet_mot_tai_lieu_bai_hoc(tmp_path, monkeypatch):
    """User chốt 06/08 lần 4: kho chỉ chứa MỘT tài liệu = BÀI HỌC KINH NGHIỆM; bằng chứng
    + transcript thành PHỤ LỤC đính kèm (không vào catalog/Qdrant); phân tích lại đọc từ
    phụ lục; duyệt xong nháp rời lịch sử."""
    client._mock_chunks.clear(); client._mock_payload.clear()
    _mock_llm(monkeypatch)
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    tid, tt = _de_xuat_nen(c, "https://youtu.be/XyZ_9")
    nhap = tt["ket_qua"]
    r = c.post("/nguon/tron-goi/duyet", data={
        "url": "https://youtu.be/XyZ_9", "nguon_ten": "Danny Why",
        "cac_doan": json.dumps(nhap["cac_doan"]), "chu_de": nhap["chu_de"],
        "boi_canh": nhap["boi_canh"], "ap_dung": nhap["ap_dung"],
        "tu_khoa": "ngách, tìm kiếm",
        "luan_diem": json.dumps([{"tieu_de": ld["tieu_de"], "noi_dung": ld["noi_dung"],
                                  "neo": ld["neo"]} for ld in nhap["luan_diem"]]),
        "department": "Kinh doanh", "access_level": "Công khai nội bộ", "min_level": "1",
        "nhap_id": tid})
    assert r.status_code == 200 and r.json()["ok"]
    assert r.json()["doc_code"] == "YT-XyZ_9"
    # MỘT tài liệu duy nhất — không còn cặp -PT
    assert not any(d["Mã tài liệu"] == "YT-XyZ_9-PT" for d in doc_catalog())
    row = next(d for d in doc_catalog() if d["Mã tài liệu"] == "YT-XyZ_9")
    # 06/08 lần 5: user chốt "bỏ hết chữ Bài học kinh nghiệm ở tiêu đề" — title là CHỦ ĐỀ THUẦN
    assert row["Tiêu đề"] == nhap["chu_de"] == "Chiến lược chọn ngách"
    # VAI TỪNG TRƯỜNG: Phụ trách = người duyệt; từ khóa nhãn ngắn; Tên nguồn = nơi đến từ
    assert row["Phụ trách"] == "chu" and row["Tên nguồn"] == "Danny Why"
    assert row["Chủ đề/Từ khóa"] == "ngách, tìm kiếm"
    assert client.dem_chunk_doc_code("YT-XyZ_9") >= 1
    assert not _file_nhap(tid).is_file()                  # duyệt xong nháp rời lịch sử
    kho = Path(os.environ["KHO_TAI_LIEU"])
    noi = next((kho / "05_Kinh-doanh").glob("YT-XyZ_9_Bai-hoc*.md")).read_text(encoding="utf-8")
    assert "## Bối cảnh" in noi and "## Áp dụng ngay" in noi   # lesson learned đủ khung
    # PHỤ LỤC đính kèm — bằng chứng nguyên văn + transcript, KHÔNG vào catalog
    bc = (kho / "05_Kinh-doanh" / "YT-XyZ_9_bang-chung.md").read_text(encoding="utf-8")
    assert "chọn một ngách thật nhỏ" in bc
    assert (kho / "05_Kinh-doanh" / "YT-XyZ_9_transcript.txt").is_file()
    # Phân tích lại: che_do kho, bằng chứng đọc từ PHỤ LỤC (file chính giờ là bài học)
    _, tt2 = _de_xuat_nen(c, "YT-XyZ_9")
    assert tt2["trang_thai"] == "xong" and tt2["ket_qua"]["che_do"] == "kho"
    assert tt2["ket_qua"]["cac_doan"][0]["trich"] == "chọn một ngách thật nhỏ để dễ lên top"
