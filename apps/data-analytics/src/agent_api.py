# -*- coding: utf-8 -*-
"""API cầu nối cho AI Agent hỏi đáp trên báo cáo — PHƯƠNG ÁN 2 đã duyệt 18/08.

Báo cáo được hỏi ở dạng JSON CÓ CẤU TRÚC (bảng không bao giờ qua vector — user
bác phương án nạp kho vì report nhiều bảng biểu). App ai-agent gọi 3 đường này
làm retriever cho nguồn "📊 Báo cáo": registry (mục lục luôn tươi) → chọn mục →
lát JSON kèm nhãn ngày. Ngoài mục lục → 404/400 rõ (van chống bịa phía agent:
"báo cáo chưa có mục này"). Claims như mọi route app (gateway đã gate quyền vào).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

# Gọi qua module (không bind hàm lúc import) — monkeypatch/test và mọi override
# về sau đều ăn; _lay_user là dependency nên bind trực tiếp được.
from src import dashboard as _db
from src import niche_bridge
from src.dashboard import _lay_user

router = APIRouter(prefix="/api/agent")

# mục được phép hỏi trên báo cáo ngách — khớp bộ artifact snapshot
MUC_NGACH = {"tom_tat", "decision1", "decision2", "bets", "gaps", "demand",
             "crackability", "monetization", "subniche", "analysis", "channels"}


@router.get("/registry")
def registry(user: dict = Depends(_lay_user)):
    """Mục lục sống: niche → thị trường (project + các ngày có snapshot) + kênh
    (+ các report đã nạp). Agent đọc cái này trước để biết hỏi được gì."""
    ten_tt = _db._ten_thi_truong()
    mapping = _db._map_projects()
    out = []
    for n in _db._ds_ngach():
        markets = []
        for tt_ma, project in mapping.get(n["ma"], {}).items():
            markets.append({"thi_truong_ma": tt_ma, "ten": ten_tt.get(tt_ma, tt_ma),
                            "project": project,
                            "snapshots": [b["id"] for b in niche_bridge.ds_snapshot(project)]})
        channels = []
        for k in _db._ds_kenh(n["ma"]):
            reports = [{"id": r.get("id"), "ngay": (r.get("thoi_gian") or "")[:10],
                        "ten_bao_cao": r.get("ten_bao_cao"), "nguoi_chay": r.get("nguoi_chay")}
                       for r in _db._bao_cao_cua_kenh(k)]
            channels.append({"ma": k["ma"], "ten": k.get("ten_chuan"),
                             "thi_truong_ma": k.get("thi_truong_ma"), "reports": reports})
        out.append({"ma": n["ma"], "ten": n.get("ten_chuan"),
                    "markets": markets, "channels": channels})
    return {"niches": out, "muc_ngach": sorted(MUC_NGACH)}


@router.get("/bao-cao/{project}")
def bao_cao_ngach(project: str, muc: str = "tom_tat", ngay: str = "latest",
                  user: dict = Depends(_lay_user)):
    """Một LÁT báo cáo ngách theo mục — số nguyên văn từ snapshot, kèm nhãn ngày."""
    if muc not in MUC_NGACH:
        raise HTTPException(400, f"Mục không có trong báo cáo ngách. Hợp lệ: {sorted(MUC_NGACH)}")
    ban_ghi = niche_bridge.chon_snapshot(project, ngay)
    if ban_ghi is None:
        raise HTTPException(404, "Chưa có báo cáo (snapshot) cho project này.")
    if muc == "tom_tat":
        du_lieu = niche_bridge.tom_tat_overall(project, ngay)
    else:
        du_lieu = niche_bridge.doc_artifact(project, ban_ghi["id"], f"{muc}.json")
        if du_lieu is None:
            raise HTTPException(404, f"Snapshot {ban_ghi['id']} không có mục {muc}.")
    return {"project": project, "snapshot": ban_ghi["id"], "muc": muc, "du_lieu": du_lieu}


@router.get("/kenh-report/{bao_cao_id}")
def kenh_report(bao_cao_id: str, user: dict = Depends(_lay_user)):
    """Bản ghi report kênh theo id (kho dùng chung) — tóm tắt máy-đọc cho agent."""
    from src.bao_cao_lich_su import doc_bao_cao_moi_nguoi
    rec = next((r for r in doc_bao_cao_moi_nguoi() if r.get("id") == bao_cao_id), None)
    if rec is None:
        raise HTTPException(404)
    return {k: rec.get(k) for k in ("id", "ten_bao_cao", "ten_kenh", "loai_kenh",
                                    "ky_bat_dau", "ky_ket_thuc", "thoi_gian",
                                    "nguoi_chay", "kenh")}
