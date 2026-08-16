# -*- coding: utf-8 -*-
"""Test HR HUB (DE.md mục 10): gate theo CỜ GATEWAY 'hr' trong X-Remote-Apps (app
không tự tính quyền — thiếu cờ thì level 5 cũng 403); bảng công kỳ tháng; CHỐT
CÔNG chỉ-thêm (đã chốt → 409, không ghi đè); xếp loại KPI APPEND bản ghi + hiển
thị bản mới nhất; People đọc IAM chỉ-đọc; Leaves nguồn chết → '—'."""

import json
import os
from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src import cham_cong, kpi_danh_gia
from src.main import app

THANG_NAY = date.today().strftime("%Y-%m")


def _client(apps="to-chuc,hr,finance", ten="hr-lead", level=3):
    return TestClient(app, headers={"X-Remote-User": ten,
                                    "X-Remote-Level": str(level),
                                    "X-Remote-Role": "leader",
                                    "X-Remote-Dept": "H%C3%A0nh%20ch%C3%ADnh%20Nh%C3%A2n%20s%E1%BB%B1",
                                    "X-Remote-Apps": apps})


def _iam_seed():
    from nen.iam import iam
    conn = iam.ket_noi()
    try:
        ho_so = iam.tao_nguoi(conn, None, "Ngọc Test", "Vận hành - Sản xuất", "Content (Kịch bản)")
        return ho_so["ma"]
    finally:
        conn.close()


# ---------- gate: app CHỈ TIN cờ gateway ----------

def test_hr_gate_theo_co_gateway():
    # Owner level 5 mà gateway KHÔNG phát cờ 'hr' → vẫn 403 (app không tự tính)
    assert _client(apps="to-chuc", ten="sep", level=5).get("/hr").status_code == 403
    assert _client().get("/hr").status_code == 200          # có cờ → vào
    assert TestClient(app).get("/hr").status_code == 401     # thiếu claims


def test_hr_gate_post_cung_bi_chan():
    c = _client(apps="to-chuc")
    assert c.post("/hr/chot-cong", data={"thang": THANG_NAY}).status_code == 403
    assert c.post("/hr/kpi-danh-gia", data={
        "nguoi": "x", "ky": THANG_NAY, "xep_loai": "A"}).status_code == 403


# ---------- People: IAM chỉ-đọc ----------

def test_hr_people_doc_iam_va_planner_id():
    ma = _iam_seed()
    b = _client().get("/hr?tab=people").text
    assert ma in b and "Ngọc Test" in b
    assert "ns_" + ma.replace("-", "").lower() in b          # planner_id dẫn xuất


def test_hr_people_form_tao_sua_tro_gateway():
    """People một cửa (16/08): form tạo + sửa/đổi trạng thái POST THẲNG route
    gateway /general/people/* kèm ve=hr — app to-chuc KHÔNG viết IAM (Luật 4)."""
    _iam_seed()
    b = _client().get("/hr?tab=people").text
    assert 'action="/general/people/create"' in b
    assert 'action="/general/people/update"' in b
    assert 'name="ve" value="hr"' in b
    assert 'name="trang_thai"' in b and 'value="nghi"' in b   # đổi trạng thái (gỡ mềm)


def test_hr_people_ho_so_day_du_cccd_che_va_tai_lieu():
    """Hồ sơ ĐẦY ĐỦ (mockup H1b đã duyệt): form đủ 8 trường + dropdown danh mục;
    CCCD KHÔNG BAO GIỜ xuất hiện đầy đủ trong HTML (chỉ bản che 8 số + ****, xem
    đủ qua route gateway có vết); bảng tài liệu gốc đọc kho + link route gateway;
    bảng People có cột ngày nhập."""
    from nen.iam import iam
    conn = iam.ket_noi()
    ns = iam.tao_nguoi(conn, None, "Ngọc Test", "Vận hành - Sản xuất",
                       "Content (Kịch bản)", ngay_sinh="1998-04-12",
                       cccd="079098012345", dia_chi="123 Lê Lợi",
                       ngay_vao="2026-07-31", cap_bac="staff")
    conn.close()
    kho = Path(os.environ["HO_SO_TAI_LIEU_DIR"]) / ns["ma"]
    kho.mkdir(parents=True)
    (kho / "cccd_scan.pdf").write_bytes(b"x")

    b = _client().get("/hr?tab=people").text
    assert "079098012345" not in b                           # tuyệt đối không lộ
    assert "07909801****" in b                               # bản che 8 số + ****
    for truong in ("ngay_sinh", "cccd", "dia_chi", "ngay_vao", "cap_bac"):
        assert f'name="{truong}"' in b                       # form đủ trường
    assert 'action="/general/people/tai-lieu"' in b          # nộp tài liệu → gateway
    assert "/general/people/cccd/" in b                      # xem đủ → route có vết
    assert "cccd_scan.pdf" in b
    assert f"/general/people/tai-lieu/{ns['ma']}/cccd_scan.pdf" in b
    assert ">Created<" in b                                  # cột ngày nhập
    assert 'name="bo_phan"' in b and "Kế toán" in b          # dropdown danh mục 5
    assert "Content (Kịch bản)" in b                         # dropdown vị trí từ CSV


def test_hr_hien_bao_loi_tu_query():
    """Gateway xử lý form xong 303 về /hr kèm bao/loi ngắn — hub hiện thông báo."""
    c = _client()
    assert "Created profile NS-001." in c.get(
        "/hr?tab=people&bao=Created+profile+NS-001.").text
    assert "Thiếu họ tên." in c.get(
        "/hr?tab=people&loi=Thi%E1%BA%BFu%20h%E1%BB%8D%20t%C3%AAn.").text


# ---------- Accounts: tab CHỈ hiện khi gateway phát cờ 'accounts' ----------

def test_hr_tab_accounts_an_khi_khong_co():
    """Người không cờ 'accounts' (kể cả HR đủ cờ 'hr'): nav KHÔNG có link tab,
    gõ ?tab=accounts tay cũng bị ẩn nội dung (rơi về People) — không có chuỗi
    'tab=accounts' actionable nào trên trang."""
    b = _client().get("/hr?tab=accounts").text               # apps mặc định không 'accounts'
    assert "tab=accounts" not in b
    assert "/general/accounts" not in b                      # không lộ form tài khoản


def test_hr_tab_accounts_doc_iam_va_form_gateway():
    """Có cờ: bảng tài khoản đọc IAM CHỈ-ĐỌC (tiền lệ _ds_nguoi_iam) + form
    tạo/update đa-hành-động trỏ route gateway sẵn có kèm ve=hr; xóa giữ khuôn
    gõ-lại-tên của /general/accounts/update."""
    from nen.iam import iam
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "chu-he", "mk-6-ky-tu", "Ban quản trị", 5,
                      phai_doi_mk=False)
    conn.close()
    c = _client(apps="to-chuc,hr,accounts", ten="chu-he", level=5)
    b = c.get("/hr?tab=accounts").text
    assert "tab=accounts" in b and "chu-he" in b             # tab + bảng đọc IAM
    assert 'action="/general/accounts/create"' in b
    assert 'action="/general/accounts/update"' in b
    assert 'name="ve" value="hr"' in b
    assert 'name="hanh_dong"' in b and 'value="xoa"' in b    # đa-hành-động, giữ field cũ


# ---------- Attendance: bảng công tháng + chốt chỉ-thêm ----------

def _tin_hieu(ten, ngay_gio_vao, ngay_gio_ra):
    cham_cong.ghi_nhan(ten, luc=ngay_gio_vao)
    cham_cong.ghi_nhan(ten, "nhip", luc=ngay_gio_ra)


def test_bang_cong_thang_gop_dung():
    _tin_hieu("nv1", datetime(2026, 1, 5, 8, 0, 0), datetime(2026, 1, 5, 17, 30, 0))
    _tin_hieu("nv1", datetime(2026, 1, 6, 9, 0, 0), datetime(2026, 1, 6, 10, 0, 0))
    bang = cham_cong.bang_cong_thang("2026-01")
    assert bang["nv1"]["so_ngay"] == 2
    assert bang["nv1"]["tong_giay"] == 9 * 3600 + 30 * 60 + 3600
    assert bang["nv1"]["ngay_cuoi"] == "2026-01-06"
    assert cham_cong.bang_cong_thang("2026-02") == {}        # tháng trống — không bịa


def test_chot_cong_chi_them_khong_ghi_de():
    _tin_hieu("nv1", datetime(2026, 1, 5, 8, 0, 0), datetime(2026, 1, 5, 17, 0, 0))
    c = _client()
    r = c.post("/hr/chot-cong", data={"thang": "2026-01"}, follow_redirects=False)
    assert r.status_code == 303
    p = Path(os.environ["CHAM_CONG_CHOT_DIR"]) / "2026-01.json"
    ban_1 = json.loads(p.read_text(encoding="utf-8"))
    assert ban_1["nguoi_chot"] == "hr-lead" and ban_1["bang"]["nv1"]["so_ngay"] == 1

    # kỳ ĐÃ CHỐT: thêm tín hiệu mới rồi chốt lại → 409, file GIỮ NGUYÊN bản đầu
    _tin_hieu("nv2", datetime(2026, 1, 9, 8, 0, 0), datetime(2026, 1, 9, 17, 0, 0))
    r2 = c.post("/hr/chot-cong", data={"thang": "2026-01"})
    assert r2.status_code == 409
    assert json.loads(p.read_text(encoding="utf-8")) == ban_1

    # trang hiện nhãn Closed thay nút chốt
    b = c.get("/hr?tab=attendance&thang=2026-01").text
    assert "Closed" in b and "Close period 2026-01" not in b


def test_chot_cong_ky_sai_dang_409():
    assert _client().post("/hr/chot-cong", data={"thang": "1-2026"}).status_code == 409


# ---------- KPI Review: append + hiện bản mới nhất ----------

def test_kpi_danh_gia_append_va_moi_nhat():
    kpi_danh_gia.them_danh_gia("nv1", "2026-01", "B", "Đều tay", "sep")
    kpi_danh_gia.them_danh_gia("nv1", "2026-01", "A", "Vượt kỳ vọng", "sep")
    ds = kpi_danh_gia.doc_danh_gia("2026-01")
    assert len(ds) == 2                                       # KHÔNG ghi đè lịch sử
    assert [b["xep_loai"] for b in ds] == ["B", "A"]
    assert kpi_danh_gia.moi_nhat_theo_nguoi("2026-01")["nv1"]["xep_loai"] == "A"


def test_kpi_danh_gia_validate():
    import pytest
    with pytest.raises(ValueError):
        kpi_danh_gia.them_danh_gia("nv1", "2026-01", "D", "", "sep")   # ngoài A/B/C
    with pytest.raises(ValueError):
        kpi_danh_gia.them_danh_gia("", "2026-01", "A", "", "sep")      # thiếu người
    with pytest.raises(ValueError):
        kpi_danh_gia.them_danh_gia("nv1", "thang-1", "A", "", "sep")   # kỳ sai dạng


def test_route_kpi_danh_gia_hien_ban_moi_nhat():
    from nen.iam import iam
    conn = iam.ket_noi()
    ho_so = iam.tao_nguoi(conn, None, "Ngọc Test", "Vận hành - Sản xuất", "Content (Kịch bản)")
    iam.tao_tai_khoan(conn, None, "ngoc-vh", "mk-6-ky-tu", "Vận hành - Sản xuất", 5,
                      nguoi_ma=ho_so["ma"], phai_doi_mk=False)
    conn.close()
    c = _client()
    r = c.post("/hr/kpi-danh-gia", data={
        "nguoi": "ngoc-vh", "ky": THANG_NAY, "xep_loai": "B", "nhan_xet": "Ổn"},
        follow_redirects=False)
    assert r.status_code == 303
    r = c.post("/hr/kpi-danh-gia", data={
        "nguoi": "ngoc-vh", "ky": THANG_NAY, "xep_loai": "A", "nhan_xet": "Tốt hơn"},
        follow_redirects=False)
    assert r.status_code == 303
    assert len(kpi_danh_gia.doc_danh_gia(THANG_NAY)) == 2
    b = c.get("/hr?tab=kpi").text
    assert "Tốt hơn" in b and "hr-lead" in b                  # bản mới nhất + người chấm
    # xếp loại lạ bị chặn 422
    assert c.post("/hr/kpi-danh-gia", data={
        "nguoi": "ngoc-vh", "ky": THANG_NAY, "xep_loai": "F"}).status_code == 422


# ---------- Leaves: nguồn chết → '—', không bịa ----------

def test_leaves_nguon_chet_hien_gach():
    ma = _iam_seed()
    from nen.iam import iam
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "ngoc-vh", "mk-6-ky-tu", "Vận hành - Sản xuất", 5,
                      nguoi_ma=ma, phai_doi_mk=False)
    conn.close()
    b = _client().get("/hr?tab=leaves").text
    assert "plan.json" in b                                   # nói thẳng nguồn không đọc được
    assert "PlannerY source dead" in b                        # ô '—' thật, không bịa 0


def test_leaves_doc_plan_that():
    ma = _iam_seed()
    from nen.iam import iam
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "ngoc-vh", "mk-6-ky-tu", "Vận hành - Sản xuất", 5,
                      nguoi_ma=ma, phai_doi_mk=False)
    conn.close()
    hom_nay = date.today().isoformat()
    Path(os.environ["PLANNERY_PLAN"]).write_text(json.dumps({
        "people": [{"id": "ns_" + ma.replace("-", "").lower(), "name": "Ngọc Test",
                    "role": "content", "leaves": [hom_nay]}],
        "projects": [], "assignments": []}), encoding="utf-8")
    b = _client().get("/hr?tab=leaves").text
    assert "ngoc-vh" in b
    assert ">1<" in b                                         # 1 ngày nghỉ trong kỳ
