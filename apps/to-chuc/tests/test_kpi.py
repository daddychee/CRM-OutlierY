"""Test KPI (bước ③) — số đo TỰ ĐỘNG tích hợp từ PlannerY/Content/SpeakY/Data Analytics,
KHÔNG nhập tay (user chốt 31/07/2026). Ghim: cửa sổ kỳ; đọc plan.json thật-cấu-trúc;
đếm script done theo user; nối tên PlannerY; VAN CHỐNG BỊA SỐ LIỆU — nguồn chết →
None/'—', không hiện 0 giả.

DI TRÚ V2: bỏ test trang /nhan-su (hồ sơ về IAM, trang không mang sang) — thay bằng
test route /kpi mới (claims gateway, gate Manager+); nguồn bao-cao giờ là dữ liệu app
data-analytics nên có thêm ca NGUỒN CHẾT (hệ cũ là nguồn nhà, không chết được);
fixture _nguon_tam cũ chuyển về conftest (4 env nguồn đã trỏ tmp mặc định)."""

import csv
import json
import os
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from src.kpi import (kpi_bao_cao, kpi_content, kpi_plannery, kpi_speaky,
                     ky_hien_tai, tong_hop_kpi)
from src.main import app

HOM_NAY = date.today().isoformat()


def _viet_plan(videos_publish):
    """plan.json đúng cấu trúc thật: 1 người content được phân 1 dự án 1 kênh.
    Đường file = env PLANNERY_PLAN (conftest đã trỏ tmp)."""
    Path(os.environ["PLANNERY_PLAN"]).write_text(json.dumps({
        "_rev": 1,
        "people": [{"id": "p1", "name": "Ngọc", "role": "content",
                    "leaves": [HOM_NAY]},
                   {"id": "p2", "name": "Hùng", "role": "editor", "leaves": []}],
        "projects": [{"id": "pr1", "name": "Life In", "channels": [{
            "id": "c1", "name": "LIFE", "stages": [{"role": "content"}],
            "videos": [{"index": i + 1, "publish_date": d} for i, d in enumerate(videos_publish)],
        }]}],
        "assignments": [{"person_id": "p1", "project_id": "pr1"},
                        {"person_id": "p2", "project_id": "pr1"}],
    }, ensure_ascii=False), encoding="utf-8")


def test_ky_hien_tai():
    tu, den = ky_hien_tai("tuan")
    assert date.fromisoformat(tu).weekday() == 0                      # Thứ 2
    assert (date.fromisoformat(den) - date.fromisoformat(tu)).days == 6  # → Chủ nhật
    assert tu <= HOM_NAY <= den
    tu_t, den_t = ky_hien_tai("thang")
    assert date.fromisoformat(tu_t).day == 1 and tu_t <= HOM_NAY <= den_t


def test_kpi_plannery_dem_dung_theo_vai_va_ky():
    tu, den = ky_hien_tai("tuan")
    _viet_plan([HOM_NAY, HOM_NAY, "2020-01-01"])  # 2 trong kỳ, 1 quá khứ xa
    kq = kpi_plannery(tu, den)
    assert kq["ngọc"]["video_den_han"] == 2                   # đúng kỳ, đúng vai content
    assert kq["ngọc"]["ngay_nghi"] == 1                       # nghỉ hôm nay trong kỳ
    assert kq["hùng"]["video_den_han"] == 0                   # editor — kênh không có stage editor


def test_kpi_plannery_nguon_chet_tra_none():
    assert kpi_plannery(*ky_hien_tai("tuan")) is None         # plan.json không tồn tại


def test_kpi_content_dem_script_done_theo_user():
    import time as _t
    ts_nay = _t.time()
    dong = [
        {"ts": ts_nay, "kind": "writer", "status": "done", "user": "ngoc"},
        {"ts": ts_nay, "kind": "writer", "status": "done", "user": "ngoc"},
        {"ts": ts_nay, "kind": "writer", "status": "error", "user": "ngoc"},   # lỗi không đếm
        {"ts": ts_nay, "kind": "extractor", "status": "done", "user": "ngoc"}, # khác loại không đếm
        {"ts": 0, "kind": "writer", "status": "done", "user": "ngoc"},         # 1970 — ngoài kỳ
    ]
    Path(os.environ["CONTENT_HISTORY"]).write_text(
        "\n".join(json.dumps(d) for d in dong), encoding="utf-8")
    kq = kpi_content(*ky_hien_tai("tuan"))
    assert kq == {"ngoc": 2}


def _viet_bao_cao(ten_user: str, cac_ban_ghi: list[dict]) -> None:
    """Dựng dữ liệu ĐÚNG KHUÔN file app data-analytics ghi (bao-cao-lich-su/<tên>.json).
    V2 không import module app khác (Luật 4) nên test tự ghi file thay luu_bao_cao cũ."""
    thu_muc = Path(os.environ["BAO_CAO_DIR"])
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / f"{ten_user}.json").write_text(
        json.dumps(cac_ban_ghi, ensure_ascii=False), encoding="utf-8")


def test_kpi_speaky_va_bao_cao():
    with Path(os.environ["SPEAKY_JOBS_LOG"]).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Thời gian", "Người", "Profile", "Số giây audio", "Số đoạn"])
        w.writerow([f"{HOM_NAY}T09:00:00", "ngoc", "giong-nam", "125.5", "8"])
        w.writerow(["2020-01-01T09:00:00", "ngoc", "giong-nam", "60", "4"])  # ngoài kỳ
    kq = kpi_speaky(*ky_hien_tai("tuan"))
    assert kq["ngoc"]["so_voice"] == 1 and kq["ngoc"]["tong_giay"] == 125.5

    _viet_bao_cao("kd_nv", [
        {"id": "b1", "so_video": 80, "thoi_gian": f"{HOM_NAY}T10:00:00"},
        {"id": "b2", "so_video": 47, "thoi_gian": "2020-01-01T10:00:00"},  # ngoài kỳ
    ])
    kq2 = kpi_bao_cao("kd_nv", *ky_hien_tai("tuan"))
    assert kq2 == {"so_bao_cao": 1, "tong_video": 80}


def test_kpi_bao_cao_nguon_chet_tra_none():
    """V2: BAO_CAO_DIR là dữ liệu app data-analytics (không còn nguồn nhà) — thư mục
    không tồn tại = nguồn chết → None, KHÔNG trả 0 giả (van chống bịa)."""
    assert kpi_bao_cao("kd_nv", *ky_hien_tai("tuan")) is None
    # thư mục CÓ nhưng user chưa chạy báo cáo nào → 0 THẬT, không phải nguồn chết
    Path(os.environ["BAO_CAO_DIR"]).mkdir(parents=True, exist_ok=True)
    assert kpi_bao_cao("kd_nv", *ky_hien_tai("tuan")) == {"so_bao_cao": 0, "tong_video": 0}


def test_tong_hop_noi_ten_planner_va_van_chong_bia():
    _viet_plan([HOM_NAY])
    ds = [
        # planner_ten nối "Ngọc" dù tài khoản là "ngoc_vh"
        {"ten": "ngoc_vh", "bo_phan": "Vận hành - Sản xuất", "ho_ten": "",
         "planner_ten": "Ngọc"},
        # người VH chưa nối được tên → cờ chua_noi_planner (UI ghi chú)
        {"ten": "lan_vh", "bo_phan": "Vận hành - Sản xuất", "ho_ten": "", "planner_ten": ""},
    ]
    kq = tong_hop_kpi(ds, "tuan")
    r = kq["vh"][0]
    assert r["video_den_han"] == 1 and not r["chua_noi_planner"]
    assert r["script_xong"] is None          # log Content không tồn tại → None, KHÔNG phải 0
    assert r["tien_do"] is None              # thiếu tử số → không bịa phần trăm
    assert kq["vh"][1]["chua_noi_planner"] is True
    # V2 thêm khóa bao_cao: BAO_CAO_DIR tmp chưa tồn tại → nguồn chết
    assert kq["thieu"] == {"plannery": False, "content": True, "speaky": True,
                           "bao_cao": True}


def test_tong_hop_kd_nguon_chet_hien_none():
    """Nhánh Kinh doanh khi BAO_CAO_DIR chết: số về None (template hiện '—'),
    không unpack vỡ, không 0 giả."""
    kq = tong_hop_kpi([{"ten": "kd_nv", "bo_phan": "Kinh doanh", "ho_ten": "Sếp"}], "tuan")
    assert kq["kd"] == [{"ten": "kd_nv", "ho_ten": "Sếp",
                         "so_bao_cao": None, "tong_video": None}]
    _viet_bao_cao("kd_nv", [{"id": "b1", "so_video": 80, "thoi_gian": f"{HOM_NAY}T10:00:00"}])
    kq2 = tong_hop_kpi([{"ten": "kd_nv", "bo_phan": "Kinh doanh"}], "tuan")
    assert kq2["kd"][0]["so_bao_cao"] == 1 and kq2["kd"][0]["tong_video"] == 80


# ─────────────────────────── route /kpi (V2 — thay trang /nhan-su cũ) ───────────────────────────
# App nhận CLAIMS từ gateway; gate trong app: Manager+ (level >= 4).

def _login(ten, level):
    return TestClient(app, headers={"X-Remote-User": ten,
                                    "X-Remote-Level": str(level),
                                    "X-Remote-Role": "manager",
                                    "X-Remote-Dept": "Kinh%20doanh"})


def _iam_seed():
    """Dựng sổ IAM TẠM (env IAM_DB → tmp, conftest lo): 1 Owner KD + 1 nhân viên VH
    có hồ sơ họ tên 'Ngọc' để nối lịch PlannerY qua tên."""
    from nen.iam import iam
    conn = iam.ket_noi()
    try:
        iam.tao_tai_khoan(conn, None, "sep", "matkhau6", "Kinh doanh", 5)
        claims = {"ten": "sep", "bo_phan": "Kinh doanh", "level": 5, "admin_uy_quyen": False}
        ho_so = iam.tao_nguoi(conn, claims, "Ngọc", "Vận hành - Sản xuất", "Content")
        iam.tao_tai_khoan(conn, claims, "ngoc_vh", "matkhau6", "Vận hành - Sản xuất", 2,
                          nguoi_ma=ho_so["ma"])
    finally:
        conn.close()


def test_route_kpi_gate_manager():
    assert _login("nv", 2).get("/kpi").status_code == 403      # dưới Manager → chặn
    assert _login("ql", 4).get("/kpi").status_code == 200      # Manager vào được
    r = TestClient(app).get("/kpi")
    assert r.status_code == 401                                # thiếu claims gateway


def test_route_kpi_hien_bang_va_van_chong_bia():
    _iam_seed()
    _viet_plan([HOM_NAY])
    b = _login("sep", 5).get("/kpi?ky=tuan").text
    assert "KPI kỳ" in b and "Tuần này" in b and "Tháng này" in b
    # người VH từ IAM nối PlannerY qua họ tên hồ sơ ("Ngọc" trong plan.json)
    assert "ngoc_vh" in b and "Ngọc" in b
    # nguồn Content/SpeakY chết → cảnh báo nguồn + ô "—" (không 0 giả)
    assert "Nguồn chưa đọc được" in b and "—" in b
    # người KD (sep) nằm bảng KD; BAO_CAO_DIR chưa tồn tại → cột báo cáo cũng "—"
    assert "Báo cáo đã chạy" in b
    # khối chấm công + van trung thực
    assert "Chấm công ngày" in b and "hiện diện trên hệ công cụ" in b


def test_route_kpi_iam_chet_khong_bia_danh_sach(monkeypatch):
    """IAM không đọc được → nói thẳng trên trang, không dựng bảng 'không ai làm gì' giả."""
    import src.main as app_mod
    monkeypatch.setattr(app_mod, "_ds_nguoi_iam",
                        lambda: (None, "Không đọc được sổ IAM (Loi) — chưa dựng được "
                                       "danh sách người cho bảng KPI."))
    b = _login("sep", 5).get("/kpi").text
    assert "Không đọc được sổ IAM" in b
