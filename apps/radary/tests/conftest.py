# -*- coding: utf-8 -*-
"""conftest radary V3 — chạy test TỪ THƯ MỤC APP (Luật 2 app tự đủ):
  cd apps/radary && pytest
Radary hệ cũ không có pytest suite — suite này bắt đầu từ adapter SSO V3.

18/08 (pool theo thị trường — docs/RADARY_THI_TRUONG.md): cách ly môi trường
ngay lúc nạp conftest vì db.DEFAULT_DB CHỐT LÚC IMPORT (bài học env-setdefault-
trước-import P5.1): RADARY_DATA_DIR trỏ tmp; GATEWAY_URL trỏ cổng chết — test
PHẢI mock thi_truong_v3/khoa_v3, lỡ quên là lỗi nổi rõ chứ không lặng lẽ gọi
gateway thật."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # import radary.*

_TMP = tempfile.mkdtemp(prefix="radary-test-")
os.environ["RADARY_DATA_DIR"] = _TMP
os.environ["RADARY_SCHEDULER"] = "0"
os.environ["RADARY_TRUST_PROXY"] = "1"
os.environ["GATEWAY_URL"] = "http://127.0.0.1:1"

import asyncio

import httpx
import pytest


@pytest.fixture()
def org_moi():
    """DB sạch mỗi test (xóa file + nạp lại schema) + org seed cho SSO bám vào.
    Dọn theo db.DEFAULT_DB THẬT chứ không theo _TMP: DEFAULT_DB chốt lúc import
    radary.db lần đầu — nếu test file khác (test_lam_gon) import trước với env
    riêng của nó thì _TMP không phải chỗ db đang sống (dính thật 18/08)."""
    from radary import db
    duong = Path(db.DEFAULT_DB)
    for f in duong.parent.glob(duong.name + "*"):
        f.unlink()
    db._DA_NAP_SCHEMA.clear()
    conn = db.connect()
    org = db.create_org(conn, "Outliery", "seed@test")
    conn.commit()
    conn.close()
    return org


@pytest.fixture()
def goi():
    """Gọi API radary như OUTLIERY tiêm claims: client loopback + X-Remote-*.
    vai truyền bằng chuỗi Actions (khuôn Permissions v2 — vai dịch mỗi request)."""
    ACTIONS = {"viewer": "", "leader": "them_video,tao_pool",
               "manager": "them_video,tao_pool,toan_quyen",
               "owner": "them_video,tao_pool,toan_quyen,quan_tri"}

    def _goi(method, path, vai="leader", user=None, json=None):
        from radary.api import app
        headers = {"X-Remote-User": user or f"nv-{vai}",
                   "X-Remote-Actions": ACTIONS[vai]}

        async def run():
            tr = httpx.ASGITransport(app=app, client=("127.0.0.1", 52000))
            async with httpx.AsyncClient(transport=tr, base_url="http://t",
                                         headers=headers) as cl:
                return await cl.request(method, path, json=json)
        return asyncio.run(run())
    return _goi


@pytest.fixture()
def mock_de(monkeypatch):
    """Danh mục đế giả (thị trường + ngách kèm tập thị trường của ngách) —
    không chạm gateway thật."""
    from radary import thi_truong_v3
    tt = [{"ma": "TT-US", "ten": "US", "ngon_ngu": "English"},
          {"ma": "TT-SPAIN", "ten": "Spain", "ngon_ngu": "Spanish"}]
    ng = [{"ma": "N-LIFE-IN", "ten": "LIFE IN", "thi_truong": ["TT-US", "TT-SPAIN"]},
          {"ma": "N-TRONG", "ten": "Chua khai", "thi_truong": []}]
    monkeypatch.setattr(thi_truong_v3, "danh_sach", lambda lam_moi=False: tt)
    monkeypatch.setattr(thi_truong_v3, "ds_ngach", lambda lam_moi=False: ng)
    return {"tt": tt, "ng": ng}
