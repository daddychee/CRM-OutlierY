# -*- coding: utf-8 -*-
"""conftest app to-chuc — chạy test TỪ THƯ MỤC APP (app tự đủ, Luật 2):
  cd apps/to-chuc && pytest
Mỗi app một process pytest riêng → package `src` không đụng app khác.
"""
import os
import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parent
_ROOT = _APP.parents[1]
sys.path.insert(0, str(_APP))    # import src.*
sys.path.insert(0, str(_ROOT))   # import nen.* (IAM — danh sách người cho KPI)


@pytest.fixture(autouse=True)
def _cach_ly_du_lieu(tmp_path, monkeypatch):
    """Mọi test trỏ dữ liệu vào tmp — không ghi rác data thật (bài học conftest hệ cũ:
    suite từng ghi bẩn PlannerY thật + file chấm công thật)."""
    # dữ liệu của chính app
    monkeypatch.setenv("CHAM_CONG_DIR", str(tmp_path / "cham-cong"))
    monkeypatch.setenv("VAULT_DIR", str(tmp_path / "vault"))
    # HR Hub + Finance Hub: 4 store mới + log P4 + danh bạ đế đều trỏ tmp —
    # suite tuyệt đối không ghi sổ tiền/chốt công/danh bạ thật
    monkeypatch.setenv("CHAM_CONG_CHOT_DIR", str(tmp_path / "cham-cong-chot"))
    monkeypatch.setenv("KPI_DANH_GIA_DIR", str(tmp_path / "kpi-danh-gia"))
    monkeypatch.setenv("SO_THU_CHI_DIR", str(tmp_path / "so-thu-chi"))
    monkeypatch.setenv("MUC_TIEU_PATH", str(tmp_path / "muc-tieu.json"))
    monkeypatch.setenv("TY_GIA_DIR", str(tmp_path / "ty-gia"))
    monkeypatch.setenv("CHUNG_TU_DIR", str(tmp_path / "chung-tu"))
    monkeypatch.setenv("DICH_VU_PATH", str(tmp_path / "dich-vu-tra-phi.json"))
    monkeypatch.setenv("LUONG_DIR", str(tmp_path / "luong"))
    monkeypatch.setenv("HAN_MUC_PATH", str(tmp_path / "han-muc.json"))
    monkeypatch.setenv("CHOT_KY_PATH", str(tmp_path / "chot-ky-tien.json"))
    monkeypatch.setenv("DON_GIA_API_PATH", str(tmp_path / "don-gia-api.json"))
    monkeypatch.setenv("TAI_SAN_DIR", str(tmp_path / "tai-san"))
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("DANH_BA_DB", str(tmp_path / "danh_ba.db"))
    # 4 nguồn KPI: mặc định KHÔNG TỒN TẠI (thử van chống bịa "nguồn chết → —");
    # test nào cần thì tự tạo file tại đúng đường env này
    monkeypatch.setenv("PLANNERY_PLAN", str(tmp_path / "plan.json"))
    monkeypatch.setenv("CONTENT_HISTORY", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("SPEAKY_JOBS_LOG", str(tmp_path / "jobs_log.csv"))
    monkeypatch.setenv("BAO_CAO_DIR", str(tmp_path / "bao-cao-lich-su"))
    # IAM: trỏ DB tạm — route /kpi đọc sổ IAM, suite tuyệt đối không đụng iam.db thật
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    # Kho tài liệu gốc hồ sơ (DE.md mục 12.1) — trỏ tmp, không đụng kho thật
    monkeypatch.setenv("HO_SO_TAI_LIEU_DIR", str(tmp_path / "ho-so-tai-lieu"))
    # NAS: mặc định chưa cấu hình + không chạy trên server (không gọi PowerShell);
    # NAS_SO_DUONG trỏ tmp phòng test nào lỡ bật NAS_DONG_BO=true không đọc/ghi sổ thật
    monkeypatch.delenv("NAS_DUONG_DAN", raising=False)
    monkeypatch.setenv("NAS_DONG_BO", "false")
    monkeypatch.setenv("NAS_RIENG_MANAGER", "")
    monkeypatch.setenv("NAS_SO_DUONG", str(tmp_path / "nas-dong-bo.json"))
    monkeypatch.delenv("NAS_WEB", raising=False)
    # trạng thái RAM sống giữa các test: throttle chấm công + DEK vault + phiên NAS
    from src import cham_cong, vault
    from nen.common import nas_sync
    cham_cong._da_ghi.clear()
    nas_sync._da_dong_bo_phien.clear()
    vault.khoa()
    yield
    vault.khoa()


# ── SIẾT BẢO MẬT 05/09/2026 ────────────────────────────────────────────────────
# `lay_user` giờ đòi ĐỦ CẢ HAI: TC_TRUST_PROXY=1 VÀ client loopback
# (nen/common/xac_thuc_app.py). TestClient mặc định báo host='testclient' nên mọi
# test cũ sẽ nhận 401 — hai fixture dưới cho test chạy ĐÚNG như hệ thật (gateway
# gọi app qua 127.0.0.1). TUYỆT ĐỐI không nới bản vá để test xanh.

@pytest.fixture(autouse=True)
def _bat_trust_proxy_tc(monkeypatch):
    """Như Arguments của tác vụ nền thật."""
    monkeypatch.setenv("TC_TRUST_PROXY", "1")


@pytest.fixture(autouse=True)
def _testclient_loopback_tc(monkeypatch):
    """TestClient khai 127.0.0.1, NHƯNG tôn trọng test tự khai địa chỉ khác
    (ca kiểm 'gọi từ LAN thì bị chặn' phải giữ nguyên tác dụng)."""
    from starlette.testclient import _TestClientTransport
    goc = _TestClientTransport.handle_request

    def handle(self, request):
        if getattr(self, "client", None) in (None, ("testclient", 50000)):
            self.client = ("127.0.0.1", 50000)
        return goc(self, request)

    monkeypatch.setattr(_TestClientTransport, "handle_request", handle)
