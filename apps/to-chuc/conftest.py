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
    # NAS: mặc định chưa cấu hình + không chạy trên server (không gọi PowerShell)
    monkeypatch.delenv("NAS_DUONG_DAN", raising=False)
    monkeypatch.setenv("NAS_DONG_BO", "false")
    monkeypatch.setenv("NAS_RIENG_MANAGER", "")
    monkeypatch.delenv("NAS_WEB", raising=False)
    # trạng thái RAM sống giữa các test: throttle chấm công + DEK vault
    from src import cham_cong, vault
    cham_cong._da_ghi.clear()
    vault.khoa()
    yield
    vault.khoa()
