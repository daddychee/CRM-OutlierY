# -*- coding: utf-8 -*-
"""APP TRI THỨC (v2, :9101) — hỏi–đáp RAG + kho tài liệu + nguồn ngoài, DI TRÚ từ agent-app.

Nghiệp vụ GIỮ NGUYÊN hệ cũ (nhập liệu dropdown bắt buộc → Qdrant + catalog; hỏi–đáp
stream + vòng phản biện + van chống bịa; đa chiều theo tầng nguồn; kho tài liệu
CRUD Owner; kho-thiếu + Q&A bổ sung; nguồn ngoài YouTube trọn gói chạy nền; lịch sử
phiên per-user). Chỉ đổi 4 mối nối theo kiến trúc nền (bắt chước data-analytics):
1. AUTH: không tự giữ user — nhận claims X-Remote-User/Level/Role/Dept từ gateway
   (gateway đã kiểm quyền "vao" app theo nen/rules/phan_quyen.json).
2. LLM: cấu hình writer/critic nạp từ KÉT qua gateway lúc khởi động
   (src/cau_hinh_llm.py) — không còn bắt sửa .env tay; gateway chết → env/mock.
3. DỮ LIỆU: data/ai-agent/{kho,db}/ theo Luật 6 (env đặt sẵn dưới đây).
4. Thêm /health (hợp đồng app); Qdrant TEST :6343 (kho thật :6333 cấm đụng).

Chạy (từ ROOT): python -m uvicorn src.main:app --app-dir "apps/ai-agent" --port 9101
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
import tempfile
import time
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

_APP_DIR = Path(__file__).resolve().parents[1]           # apps/ai-agent
ROOT = _APP_DIR.parents[1]                                # D:\AI AGENT OUTLIERY
# Luật 6: kho/ (file gốc + sổ vận hành tích lũy) vs db/ (lịch sử hội thoại per-user).
# Đặt TRƯỚC khi import module src.* (module đọc env lúc GỌI hàm nên setdefault ở đây đủ;
# conftest/test setenv trước khi gọi vẫn thắng). Các sổ phan_hoi.csv / nhom_kho_thieu.json /
# nhap-phan-tich/ / youtube_cookies.txt đều treo dưới KHO_TAI_LIEU như hệ cũ — một env dời cả cụm.
os.environ.setdefault("KHO_TAI_LIEU", str(ROOT / "data" / "ai-agent" / "kho" / "kho-tai-lieu"))
os.environ.setdefault("LICH_SU_DIR", str(ROOT / "data" / "ai-agent" / "db" / "lich-su"))
# Qdrant TEST :6343 (luật an toàn song song hệ cũ) — vector_client mặc định 6333 nên PHẢI đè ở đây.
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6343")

from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form, Header,   # noqa: E402
                     HTTPException, Request, UploadFile)
from fastapi.responses import (FileResponse, HTMLResponse, RedirectResponse,  # noqa: E402
                               StreamingResponse)
from fastapi.staticfiles import StaticFiles                                   # noqa: E402
from fastapi.templating import Jinja2Templates                                # noqa: E402
from pypdf import PdfReader                                                   # noqa: E402

from nen.common import xac_thuc_app

from src import cau_hinh_llm                                                  # noqa: E402
from src.kho_thieu import (cap_nhat_nhom_da_giai, ghi_cau_kho_thieu, ghi_co_tay,  # noqa: E402
                           loc_bang_cho, tao_nhom, xoa_cau_cho, xoa_nhom)
from src.lich_su import (danh_sach_nguoi_dung, doc_phien, doi_ten_phien,      # noqa: E402
                         loc_theo_quyen, luu_luot, phien_co_cau_da_giai)
from src.llm.factory import get_critics, get_provider                         # noqa: E402
from src.nap_youtube import (luu_cookies, nap_doan_video, trang_thai_cookies,  # noqa: E402
                             transcript_tu_url, video_id_tu_url, xoa_cookies)
from src.qa_bo_sung import la_ma_qa, ma_goc_tu_qa, them_cap_qa                # noqa: E402
from src.qa_pipeline import QAPipeline, la_cau_khong_tra_loi_duoc             # noqa: E402
from src.remake_dep import tao_ban_dep                                        # noqa: E402
from src.tai_lieu_lien_quan import doc_lien_quan, tinh_va_luu_lien_quan       # noqa: E402
from src.tong_hop_neo import (doc_doan_tu_file_goc, doc_transcript_goc, la_ma_pt,  # noqa: E402
                              ma_goc_tu_pt, nap_bai_hoc, phan_tich_co_neo)
from src.trich_doan import de_xuat_trich                                      # noqa: E402
from src.tu_khoa import lay_tu_khoa_da_co                                     # noqa: E402
from src.vector_client import QdrantClientWrapper                             # noqa: E402

PHIEN_BAN = "2.0.0"

# ================= Dropdown cố định (Input_database.md mục 4 — GIỮ NGUYÊN hệ cũ) ==========
# Nguồn DUY NHẤT: template đổ dropdown từ đây, backend cũng kiểm tra từ đây.
DEPARTMENTS = ["Ban quản trị", "Hành chính Nhân sự", "Vận hành - Sản xuất", "Kinh doanh"]
# Bộ phận ĐÃ GỠ khỏi danh mục nhưng còn trong dữ liệu cũ — ĐỌC vẫn nhận, TẠO MỚI thì cấm.
DEPARTMENTS_CU = ["IT"]
DOC_TYPES = ["Quy trình", "Chính sách", "Hướng dẫn", "Biểu mẫu", "Playbook",
             "Báo cáo", "Chiến lược", "Khác"]
EFFECTIVE_STATUSES = ["Còn hiệu lực", "Hết hiệu lực", "Bản nháp"]
ACCESS_LEVELS = ["Công khai nội bộ", "Giới hạn theo bộ phận", "Mật"]
# "IT" giữ trong 2 ánh xạ dưới CHỈ để đọc tài liệu/mã cũ (bộ phận đã gỡ 04/08/2026)
DEPT_PREFIX = {"Ban quản trị": "BQT", "Hành chính Nhân sự": "HCNS", "IT": "IT",
               "Vận hành - Sản xuất": "VH", "Kinh doanh": "KD"}
# Thang 5 level (nguyên hệ cũ — v2 level đến từ claims gateway, không còn users.txt)
BAC_LEVEL = {1: "Intern", 2: "Staff", 3: "Leader", 4: "Manager", 5: "Owner"}
MIN_LEVELS = sorted(BAC_LEVEL.items())  # [(1,"Intern"), ..., (5,"Owner")]

# Supervisor (docs/supervisor.md) — TẦNG NGUỒN: (value máy, nhãn hiển thị)
TANG_NGUON = [("noi_bo", "Tài liệu công ty (Official)"),
              ("ngoai", "Nguồn khác (chuyên gia / bên ngoài)")]
TANG_NGUON_VALUES = {v for v, _ in TANG_NGUON}
NGUON_TEN_CONG_TY = "Official"   # nhãn nguồn cho tài liệu công ty (noi_bo)

# 8 ngăn kho + ánh xạ Bộ phận → ngăn (Input_database.md mục 4)
NGAN_KHO = ["00_Chung", "01_Ban-quan-tri", "02_Hanh-chinh-Nhan-su", "03_IT",
            "04_Van-hanh-San-xuat", "05_Kinh-doanh", "06_Playbook", "99_Luu-tru"]
DEPT_FOLDER = {"Ban quản trị": "01_Ban-quan-tri", "Hành chính Nhân sự": "02_Hanh-chinh-Nhan-su",
               "IT": "03_IT", "Vận hành - Sản xuất": "04_Van-hanh-San-xuat",
               "Kinh doanh": "05_Kinh-doanh"}

CATALOG_HEADER = ["Mã tài liệu", "Ngày nhập", "Tiêu đề", "Bộ phận", "Loại tài liệu",
                  "Hiệu lực", "Phiên bản", "Mức truy cập", "Level tối thiểu",
                  "Chủ đề/Từ khóa", "Phụ trách", "Tên file mới", "Ngăn", "PDF scan",
                  "document_id", "Bản đẹp", "Tầng nguồn", "Tên nguồn"]  # 2 cột cuối: Supervisor

PHAN_HOI_HEADER = ["Thời gian", "Câu hỏi", "Câu trả lời", "Đánh giá", "Nguồn",
                   "Bị chặn quyền"]

SO_PHIEN_SIDEBAR = 15  # hiệu năng: sidebar mọi trang chỉ tính D2/highlight cho N phiên gần nhất

app = FastAPI(title="Tri thức v2 — hỏi–đáp RAG + kho tài liệu")

# Tài nguyên tĩnh (font tự host — app tự đủ, máy team không cần internet)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


# ================= CLAIMS (thay auth hệ cũ — khuôn data-analytics) =================

def ten_level(level: int) -> str:
    return BAC_LEVEL.get(level, f"Level {level}")


def lay_user(request: Request,
             x_remote_user: str = Header(""), x_remote_level: str = Header("0"),
             x_remote_role: str = Header(""), x_remote_dept: str = Header("")) -> dict:
    """User = claims gateway tiêm (an toàn vì app bind 127.0.0.1 — chỉ gateway tới được;
    header giả từ trình duyệt đã bị gateway vứt). X-Remote-Dept đi URL-encoded (header
    không chở được UTF-8 thô 'Vận hành - Sản xuất') → unquote về chuỗi gốc có dấu.
    Dict giữ ĐÚNG khuôn hệ cũ {"ten","bo_phan","level"} (+vai) — vector_client._duoc_xem
    và lich_su.loc_theo_quyen đọc 2 khóa bo_phan/level, không đổi tên trường."""
    if not xac_thuc_app.duoc_tin(request, "AA_TRUST_PROXY"):
        # SIẾT 05/09/2026 (sổ docs/bao-mat-internet.md): truoc day chi can header CO MAT la tin -> co 9101 lo ra la doc duoc ca kho tai lieu.
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    if not x_remote_user:
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    try:
        level = int(x_remote_level or 0)
    except ValueError:
        level = 0
    return {"ten": x_remote_user, "level": level, "vai": x_remote_role,
            "bo_phan": unquote(x_remote_dept) if x_remote_dept else ""}


def _hanh_dong_gateway(x_remote_actions: str) -> set[str]:
    """Cờ hành động GATEWAY phát (X-Remote-Actions — Permissions v2, DE.md mục 14):
    app CHỈ TIN CỜ, không tự tính lại quyền (luật ghim #2); thiếu header → rỗng
    → fail-closed."""
    return {s.strip() for s in (x_remote_actions or "").split(",") if s.strip()}


def yeu_cau_upload(user: dict = Depends(lay_user),
                   x_remote_actions: str = Header("")) -> dict:
    """RULE 1 hệ cũ (Manager+ nạp tài liệu) giờ là hành động 'nap_tai_lieu' trong
    luật tầng nền — tick lẻ/acting ở trang Permissions CHẢY sang ngay lượt sau."""
    if "nap_tai_lieu" not in _hanh_dong_gateway(x_remote_actions):
        raise HTTPException(403, "Bạn chưa được cấp quyền thêm tài liệu vào kho.")
    return user


def yeu_cau_quan_ly(user: dict = Depends(lay_user)) -> dict:
    """Bảng vận hành (kho cần bổ sung...) — Manager+ như hệ cũ."""
    if user["level"] < 4:
        raise HTTPException(403, "Bạn chưa được cấp quyền xem trang này.")
    return user


def yeu_cau_nguon_ngoai(user: dict = Depends(lay_user),
                        x_remote_actions: str = Header("")) -> dict:
    """Nguồn ngoài — hành động 'nguon_ngoai' (cờ gateway, khuôn yeu_cau_upload)."""
    if "nguon_ngoai" not in _hanh_dong_gateway(x_remote_actions):
        raise HTTPException(403, "Bạn chưa được cấp quyền dùng Nguồn ngoài.")
    return user


def yeu_cau_giam_sat(user: dict = Depends(lay_user),
                     x_remote_actions: str = Header("")) -> dict:
    """Giám sát (cây tri thức + lịch sử mọi người) — hành động 'giam_sat'
    (mặc định chỉ Owner, tick lẻ được ở Permissions)."""
    if "giam_sat" not in _hanh_dong_gateway(x_remote_actions):
        raise HTTPException(403, "Bạn chưa được cấp quyền xem trang giám sát.")
    return user


def yeu_cau_duyet_qa(user: dict = Depends(lay_user),
                     x_remote_actions: str = Header("")) -> dict:
    """Duyệt Q&A bổ sung — hành động 'duyet_qa' (mặc định chỉ Owner)."""
    if "duyet_qa" not in _hanh_dong_gateway(x_remote_actions):
        raise HTTPException(403, "Bạn chưa được cấp quyền duyệt Q&A.")
    return user


def yeu_cau_owner(user: dict = Depends(lay_user)) -> dict:
    """Chỉ Owner (level 5) — sửa/xóa tài liệu kho + cấu hình (nấc quan_tri;
    chuyển sang cờ hành động thuộc đợt sau — giữ level để diff gọn)."""
    if user["level"] != 5:
        raise HTTPException(403, "Chỉ Owner được thao tác này.")
    return user


def _user_tu_headers(request: Request) -> dict | None:
    """Bản đọc-nhẹ của lay_user cho context processor (không raise — trang render
    được cả khi thiếu claims; route thật vẫn chặn bằng Depends)."""
    ten = request.headers.get("x-remote-user", "")
    if not ten:
        return None
    try:
        level = int(request.headers.get("x-remote-level", "0") or 0)
    except ValueError:
        level = 0
    dept = request.headers.get("x-remote-dept", "")
    return {"ten": ten, "level": level, "vai": request.headers.get("x-remote-role", ""),
            "bo_phan": unquote(dept) if dept else "",
            "ten_hien_thi": unquote(request.headers.get("x-remote-name") or "")}


def _ctx_outliery(request: Request) -> dict:
    """Context processor: bơm ngữ cảnh khung OUTLIERY (user + recents sidebar) cho MỌI
    template extends base.html — KHÔNG raise (lỗi phụ → khung tối giản, không vỡ trang).
    Cờ sidebar theo UI_FLOW.md mục 2: GATEWAY quyết user thấy app nào qua claims
    X-Remote-Apps (danh sách slug + cờ 'nas' khi đã cấu hình) — app KHÔNG tự đoán
    quyền. App phụ chưa di trú (RadarY…) ẩn hẳn nên sb_apps luôn rỗng (chốt 16/08)."""
    ngay = datetime.now().strftime("%d/%m/%Y")
    user = _user_tu_headers(request)
    if user is None:
        return {"sb_user": None, "sb_ngay": ngay, "sb_phien": [], "sb_level_chu": "", "lite": False,
                "sb_apps": [], "sb_da": False, "sb_ns": False, "sb_cho_duyet": 0,
                "sb_nas": False, "sb_hr": False, "sb_fin": False,
                "sb_general": False}
    apps_vao = [s for s in (request.headers.get("x-remote-apps") or "").split(",") if s]
    phien = []
    # /hoi-dap tự truyền cac_phien_sidebar riêng — tính lại ở đây là phí 1 lượt Qdrant
    if user.get("bo_phan") and request.url.path != "/hoi-dap":
        try:
            phien = _danh_sach_phien(user["ten"], user, gioi_han=SO_PHIEN_SIDEBAR)
        except Exception:
            phien = []
    # App đã di trú hiện ở nhóm Tools (APPS.md): giao hợp đồng × X-Remote-Apps —
    # cùng nguồn nen.common.sidebar (Luật 4 không đụng: chỉ đọc hợp đồng chung).
    try:
        from nen.common.sidebar import sb_apps_tu_claims
        sb_apps = sb_apps_tu_claims(apps_vao)
    except Exception:
        sb_apps = []
    return {"sb_user": user, "sb_ngay": ngay, "sb_phien": phien,
            "sb_level_chu": ten_level(user["level"]),
            "lite": False, "sb_apps": sb_apps, "sb_da": "data-analytics" in apps_vao,
            "sb_ns": "quan-tri" in apps_vao, "sb_cho_duyet": 0,
            "sb_nas": "nas" in apps_vao,
            # Cờ 'general': có ít nhất một trang khu General được cấp lẻ (19/08)
            "sb_general": "general" in apps_vao,
            # Khu chức năng HR/Finance (DE.md mục 10) — cờ do gateway phát,
            # app chỉ đọc (một nguồn sự thật quyền, khuôn sb_ns/sb_nas).
            "sb_hr": "hr" in apps_vao, "sb_fin": "finance" in apps_vao}


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"),
                            context_processors=[_ctx_outliery])
templates.env.globals["BAC_LEVEL"] = BAC_LEVEL  # ánh xạ level→chữ cho template
# Nhãn MỘT DÒNG "app này để làm gì" cho lưới app màn hình chào (Owner 30/08/2026).
# Nhãn trình bày, không phải quyền — mô tả dài đã có trong apps.json; đây chỉ là câu
# ngắn đọc lướt. Slug lạ → chuỗi rỗng, thẻ vẫn hiện tên app.
templates.env.globals["viec_app"] = {
    "radary": "Theo dõi đối thủ",
    "tasky": "Giao việc trong tuần",
    "plannery": "Lịch sản xuất video",
    "content-ultimate": "Viết outline & kịch bản",
    "rendery": "Dựng video tự động",
    "video-review": "Duyệt bản dựng",
    "seo-optimize": "Sinh metadata SEO",
    "niche-research": "Nghiên cứu ngách",
}
client = QdrantClientWrapper()  # MOCK_MODE=true thì chưa cần Qdrant thật
qa = QAPipeline()  # writer + critics đọc từ env qua factory (mock mặc định)


def nap_lai_llm_tu_ket() -> bool:
    """Hỏi KÉT rồi dựng lại writer/critics. Trả True nếu nạp được vai nào.

    Tách khỏi startup vì SỰ CỐ 02/09: két chỉ được đọc MỘT LẦN lúc khởi động.
    Owner điền vai writer lúc 16:00 trong khi app chạy từ 14:38 → app giữ writer
    MOCK suốt, hỏi–đáp trả lời MẪU trên hệ thật, mà không chỗ nào nói phải
    restart. Đây đúng là ca 31/08 tái diễn, lần này vì lý do THỜI ĐIỂM chứ không
    phải két trống. Giờ health tự nạp lại khi thấy mình đang mock (xem `_writer`)
    — điền két xong là ăn ngay, không cần restart."""
    if cau_hinh_llm.nap_cau_hinh_llm():
        qa.writer = get_provider("writer")
        qa.critics = get_critics()
        return True
    return False


@app.on_event("startup")
async def _startup():
    # Cấu hình LLM từ KÉT qua gateway — nạp được vai nào thì dựng lại provider ngay
    # (qa đã khởi tạo từ env lúc import; gateway chết → giữ env/mock, app vẫn sống).
    nap_lai_llm_tu_ket()


# ================= health (hợp đồng app) =================

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "app": "ai-agent", "phien_ban": PHIEN_BAN}


# Cache canary search B6 (ts + số kết quả) — vòng giám sát nền hỏi suc-khoe
# mỗi 60s, search chỉ chạy lại khi cache quá 10 phút.
_CANARY = {"ts": 0.0, "kq": None}

# Chặn nhịp thử-nạp-lại két ở nhánh writer-đang-mock (vòng giám sát hỏi mỗi 60s).
_NAP_LAI = {"ts": 0.0}


@app.get("/api/suc-khoe")
async def api_suc_khoe():
    """Sức khỏe SÂU (B3 giám sát 31/08) — khuôn nen/common/suc_khoe.py, tab
    Applications của nền đọc qua trường `suc_khoe` trong apps.json.

    `kho-vector` là lưới sự cố 31/07 (kho rỗng 3 ngày, hỏi–đáp chết lặng lẽ)
    trồi lên hợp đồng: trước chỉ hiện khi Manager+ mở trang Kho tài liệu, giờ
    nền tự thấy. KHÔNG gọi LLM ở đây — health phải rẻ, chạy mỗi lần mở tab.
    """
    from nen.common import suc_khoe

    def _kho():
        rows = doc_catalog()
        if client.mock:
            return "canh_bao", (f"MOCK_MODE — không có kho thật để kiểm "
                                f"(catalog {len(rows)} tài liệu)")
        so_point = client.dem_point_kho()
        if so_point is None:
            return "loi", "không kết nối được kho tìm kiếm Qdrant"
        if rows and so_point == 0:
            return "loi", (f"kho RỖNG trong khi catalog có {len(rows)} tài liệu "
                           "— hỏi–đáp không trích được gì; chạy scripts/nap_lai_kho.py")
        return "ok", f"{so_point} point / {len(rows)} tài liệu catalog"

    def _catalog():
        return "ok", f"đọc được {len(doc_catalog())} dòng catalog"

    def _writer():
        # Ca thật 31/08: két có critic mà vai writer trống → trả lời MẪU trên hệ
        # thật dù kho đã thật. Chỉ đọc cờ cấu hình — không gọi LLM (health phải rẻ).
        if getattr(qa.writer, "mock", True):
            # SỰ CỐ 02/09: két điền lúc 16:00, app chạy từ 14:38 → giữ mock suốt
            # vì két chỉ đọc một lần lúc khởi động. Đang mock thì thử nạp lại
            # (rẻ: một GET loopback, và CHỈ chạy ở nhánh hỏng nên hệ khỏe không
            # tốn gì) — điền két xong là ăn ngay, không phải restart.
            import time as _t
            if _t.time() - _NAP_LAI["ts"] > 60:
                _NAP_LAI["ts"] = _t.time()
                nap_lai_llm_tu_ket()
        if getattr(qa.writer, "mock", True):
            return "canh_bao", ("writer đang MOCK — hỏi–đáp trả lời mẫu; điền vai "
                                "writer trong két (General → API keys)")
        so_critic = sum(1 for c in qa.critics if not getattr(c, "mock", True))
        return "ok", (f"writer thật ({getattr(qa.writer, 'model', '?')}), "
                      f"{so_critic} critic thật")

    def _canary():
        # B6 canary (31/08): kho có point, health khác xanh mà search câu phổ
        # quát ra 0 kết quả = tầng TRUY XUẤT lệch (model/hybrid/alias) — chỉ
        # gọi-thật mới bắt được. Search local rẻ nhưng cache 10' vì vòng giám
        # sát nền hỏi mỗi 60s. Không gọi LLM.
        if client.mock:
            return "canh_bao", "MOCK — không chạy canary search"
        import time as _t
        if _t.time() - _CANARY["ts"] > 600:
            _CANARY["kq"] = len(client.search(os.getenv("CANARY_CAU", "quy trình")))
            _CANARY["ts"] = _t.time()
        if not _CANARY["kq"]:
            return "loi", ("canary search 0 kết quả — tầng truy xuất lệch "
                           "(model/hybrid/alias) dù các health khác có thể xanh")
        return "ok", f"canary search trả {_CANARY['kq']} kết quả (cache 10 phút)"

    return suc_khoe.bao_cao("ai-agent", PHIEN_BAN, [
        ("kho-vector", _kho), ("catalog", _catalog), ("llm-writer", _writer),
        ("search-canary", _canary)])


@app.get("/api/kiem/{ma}")
async def api_kiem(ma: str, request: Request):
    """CỬA KIỂM LOGIC (02/09 — "16 logic = 16 sơ đồ"): trả SỐ ĐO THẬT của một
    logic nghiệp vụ, CHỈ-ĐỌC 0 quota (không gọi LLM); canary nền so kỳ vọng.
    Chỉ loopback — cùng khuôn /api/so-goi của nền."""
    from src import kiem
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(404)
    ham = kiem.CAC_MA.get(ma)
    if ham is None:
        raise HTTPException(404, f"không có mã kiểm {ma!r}")
    return ham()


# ================= các hàm phụ nhập liệu (chuyển thể nguyên từ app.py cũ) =================

def bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt: 'Vận hành' → 'Van hanh' (đ → d)."""
    s = s.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()


def ten_chuan(title: str, department: str, version: str, ext: str) -> str:
    """Khuôn tên file_arrangement.md Nguyên tắc 2:
    [YYYY-MM-DD]_[BoPhanCamelCase]_[Tieu-De-Gach-Noi]_[vN].ext"""
    bp = "".join(w if w.isupper() else w.capitalize()
                 for w in re.findall(r"[A-Za-z0-9]+", bo_dau(department)))
    td = "-".join(w if w.isupper() else w.capitalize()
                  for w in re.findall(r"[A-Za-z0-9]+", bo_dau(title))) or "Tai-Lieu"
    pb = re.sub(r"[^A-Za-z0-9]+", "", bo_dau(version)) or "v1"
    return f"{date.today():%Y-%m-%d}_{bp}_{td}_{pb}{ext.lower()}"


def la_pdf_scan(path: Path) -> bool:
    """PDF không có lớp chữ thật (scan/chụp ảnh) → True. Chỉ để cảnh báo, không chặn."""
    if path.suffix.lower() != ".pdf":
        return False
    try:
        so_ky_tu = 0
        for i, page in enumerate(PdfReader(str(path)).pages):
            if i >= 5:  # 5 trang đầu đủ kết luận
                break
            so_ky_tu += len((page.extract_text() or "").strip())
            if so_ky_tu >= 100:
                return False
        return so_ky_tu < 100
    except Exception:
        return True  # PDF hỏng/đọc không nổi → cảnh báo luôn cho an toàn


def duong_dan_khong_trung(ngan: Path, ten_file: str) -> Path:
    """KHÔNG ghi đè: trùng tên thì thêm hậu tố -2, -3... (quy tắc an toàn số 2)."""
    dest = ngan / ten_file
    goc = Path(ten_file)
    n = 2
    while dest.exists():
        dest = ngan / f"{goc.stem}-{n}{goc.suffix}"
        n += 1
    return dest


def ghi_csv_chi_them(so: Path, header: list, dong: list) -> None:
    """Sổ CSV CHỈ GHI THÊM, không sửa dòng cũ (quy tắc an toàn số 3).
    utf-8-sig để Excel mở tiếng Việt không lỗi font; chỉ ghi BOM lúc tạo file."""
    moi = not so.exists()
    with so.open("a", newline="", encoding="utf-8-sig" if moi else "utf-8") as f:
        w = csv.writer(f)
        if moi:
            w.writerow(header)
        w.writerow(dong)


def _nang_cap_catalog(so: Path) -> None:
    """Nâng catalog cũ lên khuôn hiện hành MỘT LẦN, dịch lại cột theo độ dài dòng gốc.
    Ghi nguyên tử (file tạm + os.replace)."""
    if not so.exists():
        return
    dong_all = list(csv.reader(so.open(encoding="utf-8-sig")))
    if not dong_all or dong_all[0] == CATALOG_HEADER:
        return  # đã đúng khuôn mới
    dong_all[0] = CATALOG_HEADER
    for d in dong_all[1:]:
        if len(d) == 14:
            d.insert(8, "")  # thiếu "Level tối thiểu" — giữ đúng vị trí các cột sau
        d.extend([""] * (len(CATALOG_HEADER) - len(d)))
    tam = so.with_name(so.name + ".tmp")
    with tam.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(dong_all)
    os.replace(tam, so)


def ghi_catalog(kho: Path, dong: list) -> None:
    _nang_cap_catalog(kho / "_catalog.csv")
    ghi_csv_chi_them(kho / "_catalog.csv", CATALOG_HEADER, dong)


def cap_nhat_ban_dep_catalog(kho: Path, doc_code: str, ten_pdf: str) -> None:
    """Bản đẹp sinh XONG Ở NỀN → điền cột 'Bản đẹp' cho dòng doc_code đã ghi trước đó.
    Ngoại lệ duy nhất của quy tắc chỉ-ghi-thêm; ghi nguyên tử file tạm + os.replace."""
    so = kho / "_catalog.csv"
    if not so.exists():
        return
    _nang_cap_catalog(so)
    dong_all = list(csv.reader(so.open(encoding="utf-8-sig")))
    for d in dong_all[1:]:
        if len(d) >= 16 and d[0] == doc_code:
            d[15] = ten_pdf
    tam = so.with_name(so.name + ".tmp")
    with tam.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(dong_all)
    os.replace(tam, so)


def _ban_dep_nen(dest: Path, title: str, doc_code: str, kho: Path) -> None:
    """Chạy NỀN sau khi /upload đã trả lời. Lỗi/timeout → chỉ log, tài liệu vẫn dùng."""
    try:
        pdf = tao_ban_dep(dest, title, doc_code)
        if pdf:
            cap_nhat_ban_dep_catalog(kho, doc_code, pdf.name)
        else:
            logging.warning("Bản đẹp nền KHÔNG sinh được cho %s — backfill bù sau", doc_code)
    except Exception as loi:
        logging.warning("Lỗi nền bản đẹp %s: %s", doc_code, loi)


# ================= trang nhập liệu + hỏi–đáp =================

@app.get("/", response_class=HTMLResponse)
def index(request: Request, user: dict = Depends(yeu_cau_upload),  # RULE 1: Manager+ mới vào
          goi_y_tieu_de: str = "", goi_y_tu_khoa: str = ""):
    # YC7: nút "Bổ sung tài liệu" từ nhóm kho-thiếu mang gợi ý điền sẵn qua query param
    return templates.TemplateResponse(request, "index.html", {
        "goi_y_tieu_de": goi_y_tieu_de,
        "goi_y_tu_khoa": goi_y_tu_khoa,
        "departments": DEPARTMENTS,
        "doc_types": DOC_TYPES,
        "effective_statuses": EFFECTIVE_STATUSES,
        "access_levels": ACCESS_LEVELS,
        "min_levels": MIN_LEVELS,
        "tang_nguon_options": TANG_NGUON,   # Supervisor — dropdown tầng nguồn
        "user": user,
        "level_chu": ten_level(user["level"]),
    })


@app.get("/hoi-dap", response_class=HTMLResponse)
def hoi_dap(request: Request, user: dict = Depends(lay_user), phien: str = ""):
    """Ý3: ?phien=<id> → MỞ LẠI cuộc trò chuyện cũ của CHÍNH MÌNH để hỏi tiếp —
    nạp lượt cũ (đã lọc D2 từng lượt) vào khung chat; id lạ → trang mở như cuộc mới."""
    nap = None
    if phien and user.get("bo_phan"):
        ph = _mot_phien(user["ten"], phien)
        if ph:
            cac_luot = loc_theo_quyen(ph["luot"], user, client)
            nap = {"phien_id": ph["id"],
                   "luot": [{"hoi": l["hoi"], "dap": l["dap"]} for l in cac_luot]}
    return templates.TemplateResponse(request, "hoi_dap.html", {
        "user": user,
        "level_chu": ten_level(user["level"]),
        "can_upload": user["level"] >= 4,  # ẩn link Nhập tài liệu với Nhân viên/Leader
        "is_owner": user["level"] == 5,    # link quản trị chỉ hiện với Owner
        "nap": nap,
        "cac_phien_sidebar": (_danh_sach_phien(user["ten"], user, gioi_han=SO_PHIEN_SIDEBAR)
                              if user.get("bo_phan") else []),
        "phien_dang_mo": nap["phien_id"] if nap else "",
    })


# ================= Ý 1 ĐỢT 3 — bảng "câu kho chưa trả lời được" + giám sát =================

@app.get("/giam-sat", response_class=HTMLResponse)
def giam_sat(request: Request, user: dict = Depends(yeu_cau_giam_sat)):
    """YC5: cây giám sát tri thức — CHỈ OWNER (luật 31/07/2026 hệ cũ).
    V2: app không còn sổ user riêng (users.txt nghỉ hưu) → cây nhân sự dựng từ
    NGƯỜI CÓ LỊCH SỬ HỘI THOẠI (quét LICH_SU_DIR — cùng khuôn doc_bao_cao_moi_nguoi
    của data-analytics); bộ phận/level từng người thuộc IAM tầng nền, không hiện ở đây."""
    cay = []
    for ten_ns in danh_sach_nguoi_dung():
        cac_phien = []
        for ph in doc_phien(ten_ns):
            cac_luot = ph.get("luot", [])
            if not cac_luot:
                continue
            cac_phien.append({
                "ten": ph.get("ten") or cac_luot[0]["hoi"][:80],
                "cau_hoi": [l["hoi"] for l in cac_luot],  # CHỈ câu hỏi, không đáp án
                "chua_dap": any(l.get("chua_tra_loi_duoc") for l in cac_luot),
            })
        cay.append({"ten": ten_ns, "bo_phan": "", "level_chu": "", "cac_phien": cac_phien})
    nhom_chu_de = cap_nhat_nhom_da_giai(client)
    return templates.TemplateResponse(request, "giam_sat.html", {
        "cay": cay,
        "cac_nhom": loc_bang_cho(nhom_chu_de),   # ẩn câu đã gom vào nhóm chưa giải
        "cac_nhom_chu_de": nhom_chu_de,
        "la_owner": user["level"] == 5,
        "is_owner": user["level"] == 5,
        "user": user,
    })


@app.post("/kho-thieu/gom")
def kho_thieu_gom(ten_chu_de: str = Form(...), cau: list[str] = Form(...),
                  ve: str = Form(""), user: dict = Depends(yeu_cau_quan_ly)):
    """YC7: Manager+ gom các câu kho-thiếu thành 1 nhóm chủ đề — baseline doc_codes
    chụp lúc tạo để sau tự nhận 'đã giải quyết' bằng search."""
    if not ten_chu_de.strip():
        raise HTTPException(422, "Tên chủ đề không được trống")
    tao_nhom(ten_chu_de, cau, client, datetime.now().isoformat(timespec="seconds"))
    return RedirectResponse("/giam-sat" if ve == "giam-sat" else "/kho-thieu",
                            status_code=303)


@app.post("/kho-thieu/xoa-nhom")
def kho_thieu_xoa_nhom(nhom_id: str = Form(...), ve: str = Form(""),
                       user: dict = Depends(yeu_cau_quan_ly)):
    """YC7: Manager+ xóa 1 nhóm chủ đề → câu của nhóm tự hiện lại ở bảng chờ."""
    xoa_nhom(nhom_id)
    return RedirectResponse("/giam-sat" if ve == "giam-sat" else "/kho-thieu",
                            status_code=303)


@app.post("/kho-thieu/xoa-cau")
def kho_thieu_xoa_cau(cau_hoi: str = Form(...), user: dict = Depends(yeu_cau_quan_ly)):
    """Manager+ xóa 1 câu KHÔNG PHÙ HỢP khỏi bảng chờ. Log gốc chỉ-ghi-thêm không đụng;
    câu vào sổ loại trừ kèm vết ai/lúc nào."""
    xoa_cau_cho(cau_hoi, user["ten"], datetime.now().isoformat(timespec="seconds"))
    return {"ok": True}


# ===== Q&A BỔ SUNG — cơ chế 2 bước (chỉ Owner bổ sung tri thức) =====

@app.post("/kho-thieu/ung-vien-qa")
def kho_thieu_ung_vien_qa(cau_hoi: str = Form(...), user: dict = Depends(yeu_cau_duyet_qa)):
    """BƯỚC 1: Owner nhập câu hỏi → top tài liệu ứng viên để chọn đích bổ sung Q&A."""
    return qa.ung_vien_qa(cau_hoi, user=user)


@app.post("/kho-thieu/soan-nhap-qa")
def kho_thieu_soan_nhap_qa(cau_hoi: str = Form(...), doc_code_goc: str = Form(...),
                           user: dict = Depends(yeu_cau_duyet_qa)):
    """BƯỚC 2: soạn NHÁP trên tài liệu Owner đã chọn (van 'KHÔNG ĐỦ CƠ SỞ'). CHỈ soạn
    nháp — KHÔNG ghi kho/Qdrant."""
    return qa.soan_nhap_qa(cau_hoi, doc_code_goc, user=user)


@app.post("/kho-thieu/duyet-qa")
def kho_thieu_duyet_qa(cau_hoi: str = Form(...), doc_code_goc: str = Form(...),
                       cau_tra_loi: str = Form(...), user: dict = Depends(yeu_cau_duyet_qa)):
    """BƯỚC 3 (DUYỆT): Owner duyệt nháp ĐÃ SỬA → ghi vào kho dạng Q&A. them_cap_qa lo
    TOÀN BỘ tạo/nối file + nạp Qdrant + kế thừa quyền gốc."""
    noi_dung = cau_tra_loi.strip()
    if not noi_dung:
        raise HTTPException(422, "Câu trả lời trống — không ghi Q&A rỗng.")
    if noi_dung.startswith("KHÔNG ĐỦ CƠ SỞ"):
        raise HTTPException(422, "Chưa đủ cơ sở để bổ sung, cần nạp thêm tài liệu.")
    try:
        kq = them_cap_qa(doc_code_goc, cau_hoi, noi_dung, client,
                         datetime.now().isoformat(timespec="seconds"))
    except ValueError as e:
        raise HTTPException(404, str(e))   # gốc không tồn tại
    logging.info("DUYỆT Q&A: owner=%s doc_goc=%s ma_qa=%s luc=%s", user["ten"],
                 doc_code_goc, kq["ma_qa"], datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "ma_qa": kq["ma_qa"], "lan_dau": kq["lan_dau"],
            "message": f"Đã bổ sung Q&A vào kho — câu hỏi này giờ tra ra được. "
                       f"Mã Q&A: {kq['ma_qa']}."}


# ===== NGUỒN NGOÀI — trích đoạn từ 1 video YouTube (Manager+) =====

@app.post("/nguon/youtube/de-xuat")
def nguon_youtube_de_xuat(url: str = Form(...), so_doan: int = Form(8),
                          user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Dán URL 1 video YouTube → LLM ĐỀ XUẤT các đoạn NGUYÊN VĂN đáng giá (van verbatim).
    CHƯA nạp kho. TÁCH 2 BƯỚC để báo lỗi ĐÚNG TẦNG (lỗi phụ đề ≠ lỗi model)."""
    try:
        vid, text = transcript_tu_url(url)
    except Exception as e:
        goi_y = ("YouTube chặn IP do gọi quá nhiều — chờ vài phút thử lại, hoặc dán cookies "
                 "đăng nhập ở box 🍪 phía trên để ít bị chặn."
                 if "block" in str(e).lower() or "ipblocked" in type(e).__name__.lower()
                 else "Video có thể không có phụ đề, sai link, hoặc bị chặn.")
        raise HTTPException(422, f"Không lấy được phụ đề video. {goi_y} Chi tiết: {e}")
    try:
        cac_doan = de_xuat_trich(text, qa.writer, max(1, min(so_doan, 20)), nguon=f"YouTube {vid}")
    except Exception as e:
        raise HTTPException(422, "Phụ đề đã lấy ĐƯỢC, nhưng gọi model đề xuất đoạn bị lỗi — "
                                 "kiểm tra API key / SỐ DƯ tài khoản nhà cung cấp model. "
                                 f"Chi tiết: {e}")
    return {"video_id": vid, "cac_doan": cac_doan}


@app.post("/nguon/youtube/duyet")
def nguon_youtube_duyet(url: str = Form(...), nguon_ten: str = Form(...),
                        cac_doan: str = Form(...), department: str = Form(...),
                        access_level: str = Form(...), min_level: int = Form(...),
                        user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Manager+ CHỐT các đoạn (đã tick/sửa) → nạp kho thành 1 tài liệu tầng ngoai."""
    for value, allowed in [(department, DEPARTMENTS), (access_level, ACCESS_LEVELS)]:
        if value not in allowed:
            raise HTTPException(422, f"Giá trị '{value}' không nằm trong dropdown cho phép")
    if not 1 <= min_level <= 5:
        raise HTTPException(422, "Level tối thiểu phải trong 1-5")
    if not nguon_ten.strip():
        raise HTTPException(422, "Phải nhập Tên nguồn (chuyên gia/kênh)")
    try:
        doan = json.loads(cac_doan)
    except ValueError:
        raise HTTPException(422, "Danh sách đoạn không hợp lệ")
    doan = [{"trich": d["trich"].strip(), "dich": (d.get("dich") or "").strip(),
             "ly_do": (d.get("ly_do") or "").strip()}
            for d in doan if isinstance(d, dict) and (d.get("trich") or "").strip()]
    if not doan:
        raise HTTPException(422, "Chưa chọn đoạn nào để nạp")

    video_id = video_id_tu_url(url)
    if not video_id:      # SIẾT 05/09: id sai khuôn → None (nap_youtube._id_sach)
        raise HTTPException(422, "Link YouTube không hợp lệ.")
    kq = nap_doan_video(video_id, url, nguon_ten.strip(), doan, department, access_level,
                        min_level, client, nguoi_nhap=user["ten"])
    logging.info("NẠP NGUỒN YOUTUBE: owner=%s nguon=%s doc=%s so_doan=%d luc=%s", user["ten"],
                 nguon_ten, kq["doc_code"], kq["so_doan"], datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, **kq,
            "message": f"Đã nạp {kq['so_doan']} đoạn từ {nguon_ten} vào kho (tầng chuyên gia). "
                       f"Mã: {kq['doc_code']}."}


# ===== TRỌN GÓI MỘT CỬA: link → trích → tổng hợp → kiểm neo → duyệt 1 lần. CHẠY NỀN + POLL =====

_TAC_VU_NGUON: dict[str, dict] = {}   # registry trong bộ nhớ — nháp bền nằm ở file


def _thu_muc_nhap_pt() -> Path:
    """Nháp phân tích nguồn nằm trong kho tài liệu (KHO_TAI_LIEU/nhap-phan-tich)."""
    return Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / "nhap-phan-tich"


def _ghi_nhap_pt(du_lieu: dict) -> None:
    """Ghi nháp nguyên tử (file tạm + os.replace). Tên file = id tác vụ (hex uuid)."""
    tm = _thu_muc_nhap_pt()
    tm.mkdir(parents=True, exist_ok=True)
    tam = tm / f"{du_lieu['id']}.json.tmp"
    tam.write_text(json.dumps(du_lieu, ensure_ascii=False), encoding="utf-8")
    os.replace(tam, tm / f"{du_lieu['id']}.json")


def _doc_nhap_pt(nhap_id: str) -> dict | None:
    """Đọc 1 nháp từ đĩa. Id lọc hex để không thành đường path traversal."""
    if not re.fullmatch(r"[0-9a-f]{12}", nhap_id or ""):
        return None
    f = _thu_muc_nhap_pt() / f"{nhap_id}.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _xoa_nhap_pt(nhap_id: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{12}", nhap_id or ""):
        return False
    f = _thu_muc_nhap_pt() / f"{nhap_id}.json"
    if f.is_file():
        f.unlink()
        _TAC_VU_NGUON.pop(nhap_id, None)
        return True
    return False


def _chay_phan_tich_nguon(dau_vao: str, ma_kho: str | None, so_doan: int) -> dict:
    """Phần MÁY của luồng một cửa (chạy nền — lỗi ném ValueError với thông điệp ĐÚNG TẦNG)."""
    verifier = qa.critics[0] if qa.critics else qa.writer
    if ma_kho:   # tài liệu đã nạp → phân tích lại từ bằng chứng trong kho, KHÔNG tải phụ đề
        cac_doan = doc_doan_tu_file_goc(ma_kho)
        if not cac_doan:
            raise ValueError(f"Tài liệu {ma_kho} không có đoạn trích nào để phân tích.")
        nhap = phan_tich_co_neo(cac_doan, qa.writer, verifier, nguon=ma_kho,
                                van_ban_goc=doc_transcript_goc(ma_kho))
        if not nhap["luan_diem"]:
            raise ValueError("Model không sinh được luận điểm nào có neo hợp lệ — thử lại.")
        return {"che_do": "kho", "doc_code_goc": ma_kho, "cac_doan": cac_doan, **nhap}
    try:
        vid, text = transcript_tu_url(dau_vao)
    except Exception as e:
        goi_y = ("YouTube chặn IP do gọi quá nhiều — chờ vài phút thử lại, hoặc dán cookies "
                 "đăng nhập ở box 🍪 để ít bị chặn."
                 if "block" in str(e).lower() or "ipblocked" in type(e).__name__.lower()
                 else "Video có thể không có phụ đề, sai link, hoặc bị chặn.")
        raise ValueError(f"Không lấy được phụ đề video. {goi_y} Chi tiết: {e}")
    try:
        cac_doan = de_xuat_trich(text, qa.writer, max(1, min(so_doan, 30)), nguon=f"YouTube {vid}")
        if not cac_doan:
            raise ValueError("Không trích được đoạn nào đủ giá trị từ video này.")
        nhap = phan_tich_co_neo(cac_doan, qa.writer, verifier, nguon=f"YouTube {vid}",
                                van_ban_goc=text)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError("Phụ đề đã lấy ĐƯỢC, nhưng gọi model bị lỗi — kiểm tra API key / SỐ DƯ "
                         f"tài khoản nhà cung cấp model. Chi tiết: {e}")
    if not nhap["luan_diem"]:
        raise ValueError("Model không sinh được luận điểm nào có neo hợp lệ — thử lại.")
    return {"che_do": "moi", "video_id": vid, "cac_doan": cac_doan, "van_ban_goc": text, **nhap}


def _phan_tich_nguon_nen(tac_vu_id: str, dau_vao: str, ma_kho: str | None, so_doan: int) -> None:
    """BackgroundTask (SYNC → threadpool, không khóa event loop). Xong/lỗi đều cập nhật
    registry VÀ ghi nháp ra đĩa — đóng tab hay restart vẫn còn lịch sử để mở lại duyệt."""
    tv = _TAC_VU_NGUON[tac_vu_id]
    try:
        kq = _chay_phan_tich_nguon(dau_vao, ma_kho, so_doan)
        tv.update(trang_thai="xong", ket_qua=kq)
    except Exception as loi:
        logging.warning("Phân tích nguồn nền lỗi (%s): %s", tac_vu_id, loi)
        tv.update(trang_thai="loi", loi=str(loi))
    try:
        _ghi_nhap_pt({"id": tac_vu_id, "nguoi": tv["nguoi"], "dau_vao": dau_vao,
                      "tao_luc": tv["tao_luc"], "trang_thai": tv["trang_thai"],
                      "loi": tv["loi"], "ket_qua": tv["ket_qua"]})
    except OSError as loi:
        logging.warning("Không ghi được nháp phân tích (%s): %s", tac_vu_id, loi)


@app.post("/nguon/tron-goi/de-xuat")
def nguon_tron_goi_de_xuat(background_tasks: BackgroundTasks, url: str = Form(...),
                           so_doan: int = Form(20),
                           user: dict = Depends(yeu_cau_nguon_ngoai)):
    """MỘT Ô NHẬP: link mới → trọn gói (phụ đề → trích → phân tích → kiểm neo); mã/link đã
    nạp → phân tích lại từ kho. Việc nặng CHẠY NỀN — trả NGAY task_id, frontend poll."""
    dau_vao = url.strip()
    ma = _ma_goc_phan_tich(dau_vao)
    cat_ma = {r["Mã tài liệu"] for r in doc_catalog()}
    if ma not in cat_ma and f"{ma}-PT" in cat_ma:
        ma = f"{ma}-PT"   # bài học đời cũ mang hậu tố -PT — vẫn nhận
    da_co = ma in cat_ma
    if not da_co and "youtube.com" not in dau_vao and "youtu.be" not in dau_vao:
        raise HTTPException(404, f"Không thấy tài liệu '{ma}' trong kho — dán link YouTube để "
                                 "phân tích video mới, hoặc kiểm lại mã tài liệu.")
    tac_vu_id = uuid.uuid4().hex[:12]
    _TAC_VU_NGUON[tac_vu_id] = {"nguoi": user["ten"], "trang_thai": "dang_chay", "loi": None,
                                "ket_qua": None, "dau_vao": dau_vao,
                                "tao_luc": datetime.now().isoformat(timespec="seconds")}
    background_tasks.add_task(_phan_tich_nguon_nen, tac_vu_id, dau_vao,
                              ma if da_co else None, so_doan)
    return {"loai": "nen", "task_id": tac_vu_id}


@app.get("/nguon/tron-goi/trang-thai/{tac_vu_id}")
def nguon_tron_goi_trang_thai(tac_vu_id: str, user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Trạng thái tác vụ phân tích nguồn. Registry trước, FALLBACK nháp trên đĩa (sống qua
    restart). Nguồn ngoài là việc CHUNG của Manager+ — ai qua gate đều xem được."""
    tv = _TAC_VU_NGUON.get(tac_vu_id) or _doc_nhap_pt(tac_vu_id)
    if tv is None:
        raise HTTPException(404, "Không thấy tác vụ này (có thể app vừa restart lúc đang chạy "
                                 "— chạy lại giúp).")
    return {"trang_thai": tv["trang_thai"], "loi": tv.get("loi"), "ket_qua": tv.get("ket_qua"),
            "dau_vao": tv.get("dau_vao"), "nguoi": tv.get("nguoi"), "nhap_id": tac_vu_id}


@app.get("/nguon/lich-su")
def nguon_lich_su(user: dict = Depends(yeu_cau_nguon_ngoai)):
    """LỊCH SỬ trang Nguồn ngoài — 2 nhóm: (1) nhap: các lượt phân tích (đang chạy / chờ
    duyệt / lỗi); (2) kho: nguồn đã duyệt vào kho (catalog tầng != noi_bo)."""
    thay = {}
    for f in sorted(_thu_muc_nhap_pt().glob("*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        d = _doc_nhap_pt(f.stem)
        if d:
            kq = d.get("ket_qua") or {}
            thay[d["id"]] = {"id": d["id"], "nguoi": d.get("nguoi"), "dau_vao": d.get("dau_vao"),
                             "tao_luc": d.get("tao_luc"), "trang_thai": d.get("trang_thai"),
                             "loi": d.get("loi"), "chu_de": kq.get("chu_de", ""),
                             "so_luan_diem": len(kq.get("luan_diem") or [])}
    for tid, tv in _TAC_VU_NGUON.items():   # đang chạy (chưa có file) đứng đầu danh sách
        if tid not in thay and tv["trang_thai"] == "dang_chay":
            thay[tid] = {"id": tid, "nguoi": tv["nguoi"], "dau_vao": tv["dau_vao"],
                         "tao_luc": tv["tao_luc"], "trang_thai": "dang_chay", "loi": None,
                         "chu_de": "", "so_luan_diem": 0}
    nhap = sorted(thay.values(), key=lambda d: d.get("tao_luc") or "", reverse=True)

    kho_map = {}
    for r in doc_catalog():
        if (r.get("Tầng nguồn") or "noi_bo") == "noi_bo":
            continue
        ma = r["Mã tài liệu"]
        goc = ma[:-3] if ma.endswith("-PT") else (ma[:-3] if ma.endswith("-QA") else ma)
        muc = kho_map.setdefault(goc, {"ma": goc, "ma_xem": "", "tieu_de": "",
                                       "nguon_ten": "", "ngay": "", "co_pt": False})
        if ma == goc:
            muc.update(ma_xem=ma, tieu_de=r.get("Tiêu đề") or goc,
                       nguon_ten=r.get("Tên nguồn") or "",
                       ngay=r.get("Ngày nhập") or r.get("Ngày") or "")
        elif ma.endswith("-PT"):
            muc["co_pt"] = True
            if not muc["ma_xem"]:
                muc.update(ma_xem=ma, tieu_de=r.get("Tiêu đề") or ma,
                           nguon_ten=r.get("Tên nguồn") or "",
                           ngay=r.get("Ngày nhập") or r.get("Ngày") or "")
    kho = sorted(kho_map.values(), key=lambda d: d.get("ngay") or "", reverse=True)
    return {"nhap": nhap, "kho": kho}


@app.get("/nguon/xem/{doc_code}")
def nguon_xem(doc_code: str, phan: str = "", user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Xem lại NỘI DUNG một tài liệu nguồn ngoài ngay trên GUI. phan='bang-chung' → đọc
    PHỤ LỤC bằng chứng đính kèm. CHỈ phục vụ tầng != noi_bo + vẫn kiểm RBAC _duoc_xem."""
    row = next((r for r in doc_catalog() if r["Mã tài liệu"] == doc_code), None)
    if row is None or (row.get("Tầng nguồn") or "noi_bo") == "noi_bo":
        raise HTTPException(404, "Không thấy tài liệu.")
    ml = str(row.get("Level tối thiểu") or "").strip()
    md = {"department": row.get("Bộ phận") or "", "access_level": row.get("Mức truy cập") or "",
          "min_level": int(ml) if ml.isdigit() else None,
          "effective_status": row.get("Hiệu lực") or ""}
    if not client._duoc_xem(md, user):
        raise HTTPException(404, "Không thấy tài liệu.")   # từ chối lặng lẽ, nhất quán Rule 2
    ngan = (row.get("Ngăn") or "").strip() or DEPT_FOLDER.get(row.get("Bộ phận"), "00_Chung")
    if phan == "bang-chung":
        f = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / ngan / f"{doc_code}_bang-chung.md"
        if not f.is_file():
            raise HTTPException(404, "Tài liệu này không có phụ lục dẫn chứng.")
        return {"doc_code": doc_code, "tieu_de": f"Dẫn chứng — {row.get('Tiêu đề') or doc_code}",
                "nguon_ten": row.get("Tên nguồn") or "", "noi_dung": f.read_text(encoding="utf-8")}
    ten = (row.get("Tên file mới") or "").strip()
    f = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / ngan / ten if ten else None
    if f is None or not f.is_file():
        raise HTTPException(404, "File của tài liệu không còn trên đĩa.")
    return {"doc_code": doc_code, "tieu_de": row.get("Tiêu đề") or doc_code,
            "nguon_ten": row.get("Tên nguồn") or "", "noi_dung": f.read_text(encoding="utf-8")}


@app.post("/nguon/nhap/xoa")
def nguon_nhap_xoa(nhap_id: str = Form(...), user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Xóa 1 nháp phân tích khỏi lịch sử (nháp lỗi / không muốn giữ)."""
    if not _xoa_nhap_pt(nhap_id.strip()):
        raise HTTPException(404, "Không thấy nháp này.")
    logging.info("XÓA NHÁP PHÂN TÍCH: user=%s id=%s", user["ten"], nhap_id.strip())
    return {"ok": True}


@app.post("/nguon/tron-goi/duyet")
def nguon_tron_goi_duyet(url: str = Form(...), nguon_ten: str = Form(...),
                         cac_doan: str = Form(...), chu_de: str = Form(""),
                         luan_diem: str = Form(...), department: str = Form(...),
                         access_level: str = Form(...), min_level: int = Form(...),
                         nhap_id: str = Form(""), boi_canh: str = Form(""),
                         ap_dung: str = Form(""), tu_khoa: str = Form(""),
                         thuat_ngu: str = Form(""),
                         user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Người duyệt MỘT lần → nạp MỘT tài liệu duy nhất = BÀI HỌC KINH NGHIỆM (kiến trúc
    1-tài-liệu 06/08). Bằng chứng KHÔNG mất: đoạn trích + transcript thành PHỤ LỤC."""
    for value, allowed in [(department, DEPARTMENTS), (access_level, ACCESS_LEVELS)]:
        if value not in allowed:
            raise HTTPException(422, f"Giá trị '{value}' không nằm trong dropdown cho phép")
    if not 1 <= min_level <= 5:
        raise HTTPException(422, "Level tối thiểu phải trong 1-5")
    if not nguon_ten.strip():
        raise HTTPException(422, "Phải nhập Tên nguồn (chuyên gia/kênh)")
    try:
        doan = json.loads(cac_doan)
        ds_ld = json.loads(luan_diem)
    except ValueError:
        raise HTTPException(422, "Dữ liệu đoạn/luận điểm không hợp lệ")
    doan = [{"trich": d["trich"].strip(), "dich": (d.get("dich") or "").strip(),
             "ly_do": (d.get("ly_do") or "").strip()}
            for d in doan if isinstance(d, dict) and (d.get("trich") or "").strip()]
    ds_ld = [{"tieu_de": (d.get("tieu_de") or "").strip(), "noi_dung": d["noi_dung"].strip(),
              "neo": sorted({int(k) for k in d.get("neo", []) if str(k).isdigit()})}
             for d in ds_ld if isinstance(d, dict) and (d.get("noi_dung") or "").strip()]
    if not doan:
        raise HTTPException(422, "Không có đoạn trích nào để nạp")
    if not ds_ld:
        raise HTTPException(422, "Chưa giữ luận điểm nào — bản phân tích rỗng")

    video_id = video_id_tu_url(url)
    if not video_id:      # SIẾT 05/09: id sai khuôn → None (nap_youtube._id_sach)
        raise HTTPException(422, "Link YouTube không hợp lệ.")
    # Transcript lấy từ NHÁP trên đĩa (không bắt trình duyệt gửi lại) → thành phụ lục
    nhap_luu = _doc_nhap_pt(nhap_id.strip()) if nhap_id.strip() else None
    van_ban = ((nhap_luu or {}).get("ket_qua") or {}).get("van_ban_goc", "")
    try:
        kq = nap_bai_hoc(f"YT-{video_id}", url, nguon_ten.strip(), chu_de.strip(), ds_ld,
                         client, datetime.now().isoformat(timespec="seconds"),
                         nguoi_nhap=user["ten"], tu_khoa=tu_khoa, boi_canh=boi_canh,
                         ap_dung=ap_dung, thuat_ngu=thuat_ngu, cac_doan=doan, van_ban=van_ban,
                         department=department, access_level=access_level,
                         min_level=min_level)
    except ValueError as e:
        raise HTTPException(422, str(e))
    logging.info("DUYỆT BÀI HỌC: user=%s nguon=%s ma=%s doan=%d luan_diem=%d luc=%s",
                 user["ten"], nguon_ten, kq["doc_code"], len(doan), kq["so_luan_diem"],
                 datetime.now().isoformat(timespec="seconds"))
    if nhap_id.strip():
        _xoa_nhap_pt(nhap_id.strip())   # duyệt xong → nháp rời lịch sử (đã thành tài liệu kho)
    return {"ok": True, "doc_code": kq["doc_code"],
            "message": f"Đã ghi bài học kinh nghiệm {kq['doc_code']} ({kq['so_luan_diem']} "
                       f"bài học, {kq['so_chunk']} chunk) — tầng chuyên gia, nguồn "
                       f"{nguon_ten.strip()}; {len(doan)} đoạn trích + transcript lưu thành "
                       "phụ lục dẫn chứng."}


# ===== TỔNG HỢP CÓ NEO (docs/supervisor.md §2c) — bài phân tích từ tài liệu trích, 3 van =====

def _ma_goc_phan_tich(chuoi: str) -> str:
    """Ô nhận CẢ mã tài liệu LẪN link video. Link → quy về mã YT-<video_id>."""
    chuoi = chuoi.strip()
    if "youtube.com" in chuoi or "youtu.be" in chuoi:
        # SIẾT 05/09: id sai khuôn → None; trả chuỗi gốc để tra catalog trượt
        # (404 lặng lẽ) thay vì dựng mã "YT-None" rồi ghi file theo mã đó.
        vid = video_id_tu_url(chuoi)
        return f"YT-{vid}" if vid else chuoi
    return chuoi


@app.post("/nguon/phan-tich/de-xuat")
def nguon_phan_tich_de_xuat(doc_code_goc: str = Form(...),
                            user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Từ tài liệu TRÍCH đã nạp kho → LLM viết BÀI PHÂN TÍCH khái quát có neo + critic
    kiểm neo. CHƯA ghi kho — trả NHÁP kèm cac_doan để màn duyệt hiện luận điểm CẠNH dẫn chứng."""
    doc_code_goc = _ma_goc_phan_tich(doc_code_goc)
    try:
        cac_doan = doc_doan_tu_file_goc(doc_code_goc)
    except ValueError as e:
        raise HTTPException(404, f"{e}. Video/tài liệu này chưa được trích nạp kho — chạy "
                                 "Bước 1 trước (dán link → Lấy đề xuất → Duyệt & ghi kho), "
                                 "rồi mới tạo bài phân tích.")
    if not cac_doan:
        raise HTTPException(422, "Tài liệu gốc không có đoạn trích nào để phân tích.")
    verifier = qa.critics[0] if qa.critics else qa.writer
    try:
        nhap = phan_tich_co_neo(cac_doan, qa.writer, verifier, nguon=doc_code_goc)
    except Exception as e:
        raise HTTPException(422, "Gọi model phân tích bị lỗi — kiểm tra API key / SỐ DƯ tài "
                                 f"khoản nhà cung cấp model. Chi tiết: {e}")
    if not nhap["luan_diem"]:
        raise HTTPException(422, "Model không sinh được luận điểm nào có neo hợp lệ "
                                 f"(bị loại vì thiếu neo: {nhap['so_loai_khong_neo']}) — "
                                 "thử lại hoặc trích thêm đoạn bằng chứng.")
    return {"doc_code_goc": doc_code_goc, "cac_doan": cac_doan, **nhap}


@app.post("/nguon/phan-tich/duyet")
def nguon_phan_tich_duyet(doc_code_goc: str = Form(...), chu_de: str = Form(""),
                          luan_diem: str = Form(...), nhap_id: str = Form(""),
                          boi_canh: str = Form(""), ap_dung: str = Form(""),
                          tu_khoa: str = Form(""), thuat_ngu: str = Form(""),
                          user: dict = Depends(yeu_cau_nguon_ngoai)):
    """VAN 3 cho tài liệu ĐÃ CÓ trong kho (phân tích lại): GHI ĐÈ chính tài liệu đó thành
    bản bài học mới — quyền/tầng nguồn giữ nguyên từ dòng catalog."""
    try:
        ds = json.loads(luan_diem)
    except ValueError:
        raise HTTPException(422, "Danh sách luận điểm không hợp lệ")
    ds = [{"tieu_de": (d.get("tieu_de") or "").strip(), "noi_dung": d["noi_dung"].strip(),
           "neo": sorted({int(k) for k in d.get("neo", []) if str(k).isdigit()})}
          for d in ds if isinstance(d, dict) and (d.get("noi_dung") or "").strip()]
    ma = _ma_goc_phan_tich(doc_code_goc)
    cat_ma = {r["Mã tài liệu"] for r in doc_catalog()}
    if ma not in cat_ma and f"{ma}-PT" in cat_ma:
        ma = f"{ma}-PT"                     # bài học đời cũ mang hậu tố -PT
    if ma not in cat_ma:
        raise HTTPException(404, f"Không thấy tài liệu {ma} trong kho.")
    try:
        kq = nap_bai_hoc(ma, "", "", chu_de.strip(), ds, client,
                         datetime.now().isoformat(timespec="seconds"),
                         nguoi_nhap=user["ten"], tu_khoa=tu_khoa,
                         boi_canh=boi_canh, ap_dung=ap_dung, thuat_ngu=thuat_ngu)
    except ValueError as e:
        raise HTTPException(422, str(e))
    logging.info("DUYỆT LẠI BÀI HỌC: user=%s ma=%s so_luan_diem=%d luc=%s", user["ten"],
                 ma, kq["so_luan_diem"], datetime.now().isoformat(timespec="seconds"))
    if nhap_id.strip():
        _xoa_nhap_pt(nhap_id.strip())   # duyệt xong → nháp rời lịch sử
    return {"ok": True, **kq,
            "message": f"Đã ghi đè bài học kinh nghiệm {kq['doc_code']} "
                       f"({kq['so_luan_diem']} bài học, {kq['so_chunk']} chunk) — quyền giữ nguyên."}


@app.get("/nguon-ngoai", response_class=HTMLResponse)
def nguon_ngoai_trang(request: Request, user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Trang nạp nguồn ngoài (YouTube): dán URL → đề xuất đoạn → chốt → ghi kho. Manager+."""
    return templates.TemplateResponse(request, "nguon_ngoai.html", {
        "user": user, "departments": DEPARTMENTS,
        "access_levels": ACCESS_LEVELS, "min_levels": MIN_LEVELS,
        "cookies": trang_thai_cookies()})


@app.post("/nguon/cookies")
def nguon_cookies_luu(noi_dung: str = Form(...), user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Manager+ dán cookies.txt YouTube (Netscape) → lưu để lay_transcript đi kèm phiên đăng
    nhập. WRITE-ONLY như API key: nội dung KHÔNG trả lại client, KHÔNG log."""
    try:
        so = luu_cookies(noi_dung)
    except ValueError as e:
        raise HTTPException(422, str(e))
    logging.info("CẬP NHẬT COOKIES YOUTUBE: owner=%s so_dong=%d luc=%s",  # KHÔNG log nội dung
                 user["ten"], so, datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "so_dong": so,
            "message": f"Đã lưu cookies ({so} dòng youtube.com). Thử lại Lấy đề xuất."}


@app.post("/nguon/cookies/xoa")
def nguon_cookies_xoa(user: dict = Depends(yeu_cau_nguon_ngoai)):
    """Manager+ gỡ file cookies (vd đổi tài khoản / thu hồi phiên)."""
    xoa_cookies()
    return {"ok": True, "message": "Đã gỡ cookies — sẽ gọi YouTube ẩn danh như cũ."}


@app.get("/kho-thieu", response_class=HTMLResponse)
def kho_thieu_trang(request: Request, user: dict = Depends(yeu_cau_quan_ly)):
    """Bảng lỗ hổng kho cho Manager+: câu kho-thiếu-thật + câu 👎 không-bị-chặn-quyền,
    gộp câu giống nhau, đếm tần suất."""
    nhom_chu_de = cap_nhat_nhom_da_giai(client)  # YC7: tự chuyển mục đã-giải
    return templates.TemplateResponse(request, "kho_thieu.html", {
        "cac_nhom": loc_bang_cho(nhom_chu_de),   # ẩn câu đã gom vào nhóm chưa giải
        "cac_nhom_chu_de": nhom_chu_de,
        "is_owner": user["level"] == 5,   # nút 💬 Bổ sung Q&A chỉ Owner
        "user": user,
    })


# ================= KHO TÀI LIỆU =================

def doc_catalog(kho: Path | None = None) -> list[dict]:
    """Đọc _catalog.csv → list dict theo CATALOG_HEADER. CHỈ ĐỌC — KHÔNG nâng cấp/ghi file.
    Dòng legacy 14 cột thiếu 'Level tối thiểu' vị trí 8 → chèn rỗng IN-MEMORY."""
    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    so = kho / "_catalog.csv"
    if not so.exists():
        return []
    ra = []
    for d in list(csv.reader(so.open(encoding="utf-8-sig")))[1:]:
        if not d or not (d[0] or "").strip():
            continue
        d = list(d)
        if len(d) == 14:                                  # legacy: thiếu 'Level tối thiểu'
            d.insert(8, "")
        d += [""] * (len(CATALOG_HEADER) - len(d))
        ra.append(dict(zip(CATALOG_HEADER, d)))
    return ra


def ghep_goc_qa(rows: list[dict]) -> list[dict]:
    """Xếp tài liệu CON (Q&A mã -QA, bản phân tích mã -PT) NGAY DƯỚI tài liệu gốc của nó,
    đánh dấu la_qa/la_pt. Gốc ngoài quyền → con cũng KHÔNG hiện (kế thừa quyền). -PT mồ côi
    là TÀI LIỆU CHÍNH (kiến trúc 1-tài-liệu) → hiện như dòng thường; Q&A mồ côi ẨN."""
    con_theo_goc: dict[str, list[dict]] = {}
    goc_rows = []
    for r in rows:
        ma = r["Mã tài liệu"]
        if la_ma_qa(ma):
            con_theo_goc.setdefault(ma_goc_tu_qa(ma), []).append({**r, "la_qa": True, "la_pt": False})
        elif la_ma_pt(ma):
            con_theo_goc.setdefault(ma_goc_tu_pt(ma), []).append({**r, "la_qa": False, "la_pt": True})
        else:
            goc_rows.append(r)
    ket = []
    for r in goc_rows:
        ket.append({**r, "la_qa": False, "la_pt": False})
        ket.extend(con_theo_goc.pop(r["Mã tài liệu"], []))
    for con in con_theo_goc.values():
        ket.extend({**c, "la_qa": False, "la_pt": False} for c in con if c["la_pt"])
    return ket


def _kho_md(row: dict) -> dict:
    """Dòng catalog → md cho client._duoc_xem (DÙNG LẠI luật quyền tài liệu, KHÔNG luật mới)."""
    ml = (row.get("Level tối thiểu") or "").strip()
    return {"access_level": row.get("Mức truy cập", ""),
            "department": row.get("Bộ phận", ""),
            "min_level": int(ml) if ml.isdigit() else None}


@app.get("/kho-tai-lieu", response_class=HTMLResponse)
def kho_tai_lieu_trang(request: Request, user: dict = Depends(lay_user)):
    """KHO TÀI LIỆU: liệt kê catalog theo RBAC. Owner thấy TOÀN BỘ; người khác chỉ thấy tài
    liệu ĐỦ QUYỀN — tái dùng client._duoc_xem. LỌC Ở SERVER."""
    is_owner = user["level"] >= 5
    rows = doc_catalog()
    tai_lieu_duoc_xem = rows if is_owner else [r for r in rows if client._duoc_xem(_kho_md(r), user)]
    ma_duoc_xem = {r["Mã tài liệu"] for r in tai_lieu_duoc_xem}
    tieu_de_theo_ma = {r["Mã tài liệu"]: r.get("Tiêu đề") or r["Mã tài liệu"] for r in rows}
    for r in tai_lieu_duoc_xem:
        ds = doc_lien_quan(r["Mã tài liệu"])
        r["lien_quan"] = [{"ma": x["ma"], "tieu_de": tieu_de_theo_ma.get(x["ma"], x["ma"])}
                          for x in ds if x["ma"] in ma_duoc_xem]
    tai_lieu = ghep_goc_qa(tai_lieu_duoc_xem)
    # LƯỚI CẢNH BÁO: catalog có tài liệu mà kho Qdrant rỗng/không nối được → hỏi-đáp
    # đang CHẾT LẶNG LẼ. Chỉ báo cho Manager+; mock không có kho thật nên bỏ qua.
    canh_bao_kho = None
    if rows and user["level"] >= 4 and not client.mock:
        so_point = client.dem_point_kho()
        if so_point == 0:
            canh_bao_kho = (f"Kho tìm kiếm (Qdrant) đang RỖNG trong khi catalog có {len(rows)} "
                            "tài liệu — hỏi–đáp sẽ không trích được gì. Chạy "
                            "scripts/nap_lai_kho.py để dựng lại kho từ file gốc.")
        elif so_point is None:
            canh_bao_kho = ("Không kết nối được kho tìm kiếm (Qdrant test :6343 chưa chạy?) — "
                            "hỏi–đáp và nhập tài liệu sẽ lỗi cho tới khi kho lên lại.")
    return templates.TemplateResponse(request, "kho_tai_lieu.html", {
        "user": user, "tai_lieu": tai_lieu, "is_owner": is_owner, "canh_bao_kho": canh_bao_kho,
        "departments": DEPARTMENTS, "access_levels": ACCESS_LEVELS,
        "effective_statuses": EFFECTIVE_STATUSES, "min_levels": MIN_LEVELS})


# File đọc thẳng thành chữ trong popup; định dạng khác → UI chỉ sang nút tải
_DUOI_XEM_TRUC_TIEP = {".md", ".txt", ".csv", ".html", ".htm"}


@app.get("/kho-tai-lieu/xem/{doc_code}")
def kho_tai_lieu_xem(doc_code: str, phan: str = "", user: dict = Depends(lay_user)):
    """Xem TRỰC TIẾP nội dung tài liệu trong popup Kho tài liệu. RBAC y hệt trang — từ chối
    404 LẶNG LẼ. phan='bang-chung' → đọc phụ lục dẫn chứng đính kèm."""
    khong_co = HTTPException(404, "Không có tài liệu này.")
    row = next((r for r in doc_catalog() if r["Mã tài liệu"] == doc_code), None)
    if row is None:
        raise khong_co
    if user.get("bo_phan") and user.get("level", 0) < 5 \
            and not client._duoc_xem(_kho_md(row), user):
        raise khong_co
    ngan = (row.get("Ngăn") or "").strip() or DEPT_FOLDER.get(row.get("Bộ phận"), "00_Chung")
    if phan == "bang-chung":
        f = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / ngan / f"{doc_code}_bang-chung.md"
        if not f.is_file():
            raise HTTPException(404, "Tài liệu này không có phụ lục dẫn chứng.")
        return {"doc_code": doc_code, "tieu_de": f"Dẫn chứng — {row.get('Tiêu đề') or doc_code}",
                "noi_dung": f.read_text(encoding="utf-8"), "duoi": ".md"}
    ten = (row.get("Tên file mới") or "").strip()
    f = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / ngan / ten if ten else None
    if f is None or not f.is_file():
        raise HTTPException(404, "File của tài liệu không còn trên đĩa.")
    if f.suffix.lower() not in _DUOI_XEM_TRUC_TIEP:
        return {"doc_code": doc_code, "tieu_de": row.get("Tiêu đề") or doc_code,
                "noi_dung": None, "duoi": f.suffix.lower()}   # UI hiện nút tải bản gốc
    return {"doc_code": doc_code, "tieu_de": row.get("Tiêu đề") or doc_code,
            "noi_dung": f.read_text(encoding="utf-8", errors="replace"),
            "duoi": f.suffix.lower()}


# Bước 2A — SỬA METADATA AN TOÀN (chỉ ảnh hưởng HIỂN THỊ, không cần đồng bộ Qdrant)
_METADATA_AN_TOAN = {"title": "Tiêu đề", "doc_type": "Loại tài liệu", "version": "Phiên bản",
                     "keywords": "Chủ đề/Từ khóa", "owner": "Phụ trách"}


def cap_nhat_metadata_an_toan(doc_code: str, updates: dict, kho: Path | None = None) -> bool:
    """Cập nhật CHỈ các trường AN TOÀN cho dòng doc_code. doc_code BẤT BIẾN — KHÔNG bao giờ
    ghi cột 0. Ghi NGUYÊN TỬ. KHÔNG đụng Qdrant. Trả True nếu tìm thấy doc_code."""
    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    so = kho / "_catalog.csv"
    if not so.exists():
        return False
    _nang_cap_catalog(so)
    dong_all = list(csv.reader(so.open(encoding="utf-8-sig")))
    idx = {ten: CATALOG_HEADER.index(cot) for ten, cot in _METADATA_AN_TOAN.items()}
    tim_thay = False
    for d in dong_all[1:]:
        if len(d) >= 16 and d[0] == doc_code:            # d[0] = Mã tài liệu — CHỈ ĐỌC
            for ten, i in idx.items():
                if ten in updates:
                    d[i] = updates[ten]
            tim_thay = True
    if not tim_thay:
        return False
    tam = so.with_name(so.name + ".tmp")
    with tam.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(dong_all)
    os.replace(tam, so)
    return True


@app.post("/kho-tai-lieu/sua")
def kho_tai_lieu_sua(doc_code: str = Form(...), title: str = Form(...),
                     doc_type: str = Form(""), version: str = Form(""),
                     keywords: str = Form(""), owner: str = Form(""),
                     user: dict = Depends(yeu_cau_owner)):
    """SỬA METADATA AN TOÀN — CHỈ OWNER (chặn ở SERVER). doc_code BẤT BIẾN."""
    if not title.strip():
        raise HTTPException(422, "Tiêu đề không được để trống.")
    ok = cap_nhat_metadata_an_toan(doc_code, {
        "title": title.strip(), "doc_type": doc_type.strip(), "version": version.strip(),
        "keywords": keywords.strip(), "owner": owner.strip()})
    if not ok:
        raise HTTPException(404, "Không tìm thấy tài liệu để sửa.")
    logging.info("SỬA metadata an toàn: owner=%s doc=%s title=%r luc=%s",
                 user["ten"], doc_code, title.strip(), datetime.now().isoformat(timespec="seconds"))
    return RedirectResponse("/kho-tai-lieu", status_code=303)


# ===== Bước 2B — CẬP NHẬT NỘI DUNG bằng file mới (chỉ Owner; nặng, chạm truy xuất) =====

_KHO_DUOI_CHO_PHEP = (".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md",
                      ".html", ".htm")


def _tang_phien_ban(cu: str) -> str:
    """Tăng phiên bản: +1 vào cụm SỐ cuối (v1→v2, v3→v4, 2→3). Không có số → thêm '-v2'."""
    m = re.search(r"(\d+)(?!.*\d)", cu or "")
    return (cu[:m.start()] + str(int(m.group(1)) + 1) + cu[m.end():]) if m else (cu or "v1") + "-v2"


def _cap_nhat_catalog_noi_dung(kho: Path, doc_code: str, version: str, ten_file: str, ngay: str) -> bool:
    """SAU khi nạp Qdrant OK: cập nhật dòng doc_code — phiên bản + tên file mới + ngày.
    doc_code + document_id + các trường quyền GIỮ NGUYÊN. Ghi NGUYÊN TỬ."""
    so = kho / "_catalog.csv"
    if not so.exists():
        return False
    _nang_cap_catalog(so)
    dong_all = list(csv.reader(so.open(encoding="utf-8-sig")))
    iV, iF, iN = (CATALOG_HEADER.index(c) for c in ("Phiên bản", "Tên file mới", "Ngày nhập"))
    tim = False
    for d in dong_all[1:]:
        if len(d) >= 16 and d[0] == doc_code:
            d[iV], d[iF], d[iN] = version, ten_file, ngay
            tim = True
    if not tim:
        return False
    tam = so.with_name(so.name + ".tmp")
    with tam.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(dong_all)
    os.replace(tam, so)
    return True


@app.post("/kho-tai-lieu/cap-nhat-noi-dung")
def kho_tai_lieu_cap_nhat_noi_dung(file: UploadFile = File(...), doc_code: str = Form(...),
                                   user: dict = Depends(yeu_cau_owner)):
    """CẬP NHẬT NỘI DUNG tài liệu bằng FILE MỚI — CHỈ OWNER. TRÌNH TỰ CHỐNG LỆCH:
    lưu trữ bản cũ → ghi file mới → QDRANT TRƯỚC (xóa chunk cũ + nạp mới + kiểm chứng)
    → CHỈ KHI OK mới ghi catalog. Qdrant LỖI → gỡ file mới, catalog vẫn trỏ bản cũ."""
    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    row = next((r for r in doc_catalog(kho) if r["Mã tài liệu"] == doc_code), None)
    if row is None:
        raise HTTPException(404, "Không tìm thấy tài liệu để cập nhật.")
    ten_goc = Path(file.filename or "tai-lieu").name
    if Path(ten_goc).suffix.lower() not in _KHO_DUOI_CHO_PHEP:
        raise HTTPException(422, f"Định dạng '{Path(ten_goc).suffix}' không được phép cập nhật.")

    version_cu = (row.get("Phiên bản") or "v1").strip() or "v1"          # BƯỚC 1
    version_moi = _tang_phien_ban(version_cu)
    ngan = (row.get("Ngăn") or "").strip() or DEPT_FOLDER.get(row.get("Bộ phận"), "00_Chung")
    ten_file_cu = (row.get("Tên file mới") or "").strip()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / ten_goc
        tmp_path.write_bytes(file.file.read())            # sync đọc (route def → threadpool)
        ten_moi = ten_chuan(row.get("Tiêu đề") or doc_code, row.get("Bộ phận") or "",
                            version_moi, tmp_path.suffix)
        (kho / ngan).mkdir(parents=True, exist_ok=True)
        dest = duong_dan_khong_trung(kho / ngan, ten_moi)
        # BƯỚC 2: COPY file cũ vào 99_Luu-tru (giữ lịch sử, KHÔNG xóa)
        luu_tru_path = None
        cu_path = (kho / ngan / ten_file_cu) if ten_file_cu else None
        if cu_path and cu_path.is_file():
            luu = kho / "99_Luu-tru"; luu.mkdir(parents=True, exist_ok=True)
            luu_tru_path = duong_dan_khong_trung(luu, f"{doc_code}_{version_cu}_{ten_file_cu}")
            shutil.copy2(cu_path, luu_tru_path)
        shutil.copy2(tmp_path, dest)                      # BƯỚC 3: ghi file mới vào ngăn

    # Quyền truy xuất GIỮ NGUYÊN từ catalog (cập nhật nội dung KHÔNG đổi quyền)
    ml = (row.get("Level tối thiểu") or "").strip()
    metadata = {
        "title": row.get("Tiêu đề") or "", "keywords": row.get("Chủ đề/Từ khóa") or "",
        "owner": row.get("Phụ trách") or "", "version": version_moi,
        "department": row.get("Bộ phận") or "", "doc_type": row.get("Loại tài liệu") or "",
        "effective_status": row.get("Hiệu lực") or "", "access_level": row.get("Mức truy cập") or "",
        "min_level": int(ml) if ml.isdigit() else None, "doc_code": doc_code,
        "import_date": date.today().isoformat(), "original_filename": ten_goc,
    }
    # BƯỚC 4: QDRANT TRƯỚC — xóa sạch chunk cũ theo doc_code rồi nạp mới + kiểm chứng
    try:
        ket = client.cap_nhat_noi_dung(str(dest), metadata)
    except Exception as e:
        dest.unlink(missing_ok=True)   # gỡ file mới (chưa vào catalog)
        raise HTTPException(422, "Cập nhật nội dung THẤT BẠI ở bước nạp tìm kiếm — CHƯA đổi catalog "
                                 f"(file cũ vẫn còn, không mất dữ liệu). Chi tiết: {e}")

    # BƯỚC 5: CHỈ KHI Qdrant OK → cập nhật catalog nguyên tử
    _cap_nhat_catalog_noi_dung(kho, doc_code, version_moi, dest.name, date.today().isoformat())
    if cu_path and cu_path.is_file() and luu_tru_path and luu_tru_path.is_file() and cu_path != dest:
        cu_path.unlink(missing_ok=True)   # bản cũ đã an toàn trong archive

    logging.info("CẬP NHẬT NỘI DUNG: owner=%s doc=%s %s→%s chunk=%d luu_tru=%s luc=%s",
                 user["ten"], doc_code, version_cu, version_moi, ket["so_moi"],
                 luu_tru_path.name if luu_tru_path else "(không có file cũ)",
                 datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "doc_code": doc_code, "version_cu": version_cu, "version_moi": version_moi,
            "so_chunk": ket["so_moi"], "luu_tru": luu_tru_path.name if luu_tru_path else None,
            "message": (f"Đã cập nhật nội dung — phiên bản {version_cu} → {version_moi}, nạp "
                        f"{ket['so_moi']} đoạn vào tìm kiếm. Bản cũ đã lưu trong 99_Luu-tru (không xóa).")}


# ===== Bước 2C — SỬA METADATA NGUY HIỂM (đổi quyền, đồng bộ payload Qdrant) — chỉ Owner =====

def _cap_nhat_catalog_quyen(kho: Path, doc_code: str, cot_moi: dict) -> bool:
    """Cập nhật các CỘT QUYỀN của dòng doc_code SAU khi đồng bộ Qdrant OK. Ghi NGUYÊN TỬ."""
    so = kho / "_catalog.csv"
    if not so.exists():
        return False
    _nang_cap_catalog(so)
    dong_all = list(csv.reader(so.open(encoding="utf-8-sig")))
    idx = {c: CATALOG_HEADER.index(c) for c in cot_moi}
    tim = False
    for d in dong_all[1:]:
        if len(d) >= 16 and d[0] == doc_code:
            for c, v in cot_moi.items():
                d[idx[c]] = v
            tim = True
    if not tim:
        return False
    tam = so.with_name(so.name + ".tmp")
    with tam.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(dong_all)
    os.replace(tam, so)
    return True


def _dong_bo_quyen(kho: Path, doc_code: str, payload_moi: dict, cot_catalog: dict) -> None:
    """ĐỒNG BỘ TRƯỜNG QUYỀN. Thứ tự CHỐNG LỆCH: (1) QDRANT TRƯỚC set_payload theo filter
    doc_code; (2) KIỂM CHỨNG đọc lại payload — lệch → raise, KHÔNG ghi catalog;
    (3) CATALOG SAU ghi nguyên tử."""
    try:
        client.cap_nhat_payload_doc_code(doc_code, payload_moi)                      # (1)
    except Exception as e:
        raise HTTPException(500, f"Đồng bộ payload Qdrant thất bại — CHƯA đổi catalog (2 kho giữ "
                                 f"giá trị cũ, không lệch). Chi tiết: {e}")
    pl = client.doc_payload_mau(doc_code)                                            # (2)
    if pl is None or any(pl.get(k) != v for k, v in payload_moi.items()):
        logging.warning("ĐỒNG BỘ QUYỀN %s KHÔNG khớp sau set_payload (đọc lại: %s, mong đợi: %s) — "
                        "Owner kiểm tra Qdrant!", doc_code, pl, payload_moi)
        raise HTTPException(500, "Đồng bộ Qdrant chưa khớp (kiểm chứng thất bại) — CHƯA ghi catalog "
                                 "để tránh lệch quyền. Hãy kiểm tra Qdrant rồi thử lại.")
    _cap_nhat_catalog_quyen(kho, doc_code, cot_catalog)                              # (3)


@app.post("/kho-tai-lieu/sua-quyen")
def kho_tai_lieu_sua_quyen(doc_code: str = Form(...), department: str = Form(...),
                           access_level: str = Form(...), effective_status: str = Form(...),
                           min_level: int = Form(...), user: dict = Depends(yeu_cau_owner)):
    """SỬA METADATA NGUY HIỂM (đổi AI ĐƯỢC THẤY tài liệu) — CHỈ OWNER. Qdrant TRƯỚC →
    kiểm chứng → catalog SAU. doc_code bất biến."""
    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    row = next((r for r in doc_catalog(kho) if r["Mã tài liệu"] == doc_code), None)
    if row is None:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    for value, allowed in [(department, DEPARTMENTS), (access_level, ACCESS_LEVELS),
                           (effective_status, EFFECTIVE_STATUSES)]:
        if value not in allowed:
            raise HTTPException(422, f"Giá trị '{value}' không nằm trong dropdown cho phép.")
    if not 1 <= min_level <= 5:
        raise HTTPException(422, "Level tối thiểu phải trong khoảng 1-5.")
    payload_moi = {"department": department, "access_level": access_level,
                   "effective_status": effective_status, "min_level": min_level}
    cot_catalog = {"Bộ phận": department, "Mức truy cập": access_level,
                   "Hiệu lực": effective_status, "Level tối thiểu": str(min_level)}
    _dong_bo_quyen(kho, doc_code, payload_moi, cot_catalog)   # Qdrant→kiểm chứng→catalog
    logging.info("SỬA QUYỀN: owner=%s doc=%s bộ_phận %r→%r mức %r→%r level %s→%s hiệu_lực %r→%r luc=%s",
                 user["ten"], doc_code, row.get("Bộ phận"), department, row.get("Mức truy cập"),
                 access_level, row.get("Level tối thiểu"), min_level, row.get("Hiệu lực"),
                 effective_status, datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "doc_code": doc_code,
            "message": f"Đã cập nhật quyền tài liệu {doc_code} và ĐỒNG BỘ hệ thống tìm kiếm (kiểm chứng đạt)."}


# ===== Bước 2D — XÓA tài liệu: ưu tiên GỠ MỀM; XÓA CỨNG xác nhận 2 lớp — chỉ Owner =====

def _xoa_dong_catalog(kho: Path, doc_code: str) -> bool:
    """Xóa DÒNG doc_code khỏi catalog (giữ header + các dòng khác), ghi NGUYÊN TỬ."""
    so = kho / "_catalog.csv"
    if not so.exists():
        return False
    _nang_cap_catalog(so)
    dong_all = list(csv.reader(so.open(encoding="utf-8-sig")))
    if not dong_all:
        return False
    header = dong_all[0]
    than = [d for d in dong_all[1:] if not (d and d[0] == doc_code)]
    if len(than) == len(dong_all) - 1:
        return False
    tam = so.with_name(so.name + ".tmp")
    with tam.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows([header] + than)
    os.replace(tam, so)
    return True


@app.post("/kho-tai-lieu/go-mem")
def kho_tai_lieu_go_mem(doc_code: str = Form(...), user: dict = Depends(yeu_cau_owner)):
    """GỠ MỀM (ƯU TIÊN, an toàn) — đổi hiệu lực → 'Hết hiệu lực' ở CẢ Qdrant lẫn catalog.
    Dữ liệu VẪN CÒN, khôi phục bằng cách đổi lại hiệu lực. Chỉ Owner."""
    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    row = next((r for r in doc_catalog(kho) if r["Mã tài liệu"] == doc_code), None)
    if row is None:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    _dong_bo_quyen(kho, doc_code, {"effective_status": "Hết hiệu lực"}, {"Hiệu lực": "Hết hiệu lực"})
    logging.info("GỠ MỀM: owner=%s doc=%s (hiệu lực %r→'Hết hiệu lực') luc=%s",
                 user["ten"], doc_code, row.get("Hiệu lực"), datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "doc_code": doc_code,
            "message": (f"Đã GỠ MỀM {doc_code} — hỏi-đáp sẽ bỏ qua tài liệu này. Dữ liệu VẪN CÒN, "
                        "khôi phục bằng cách đổi Hiệu lực về 'Còn hiệu lực'.")}


@app.post("/kho-tai-lieu/xoa-cung")
def kho_tai_lieu_xoa_cung(doc_code: str = Form(...), xac_nhan_ma: str = Form(...),
                          user: dict = Depends(yeu_cau_owner)):
    """XÓA CỨNG (XÁC NHẬN 2 LỚP — gõ lại đúng mã, kiểm Ở SERVER) — CHỈ OWNER. Thứ tự AN TOÀN
    BA NƠI: (1) chunk Qdrant TRƯỚC (lỗi → DỪNG, tránh tài liệu MA); (2) dòng catalog;
    (3) file → 99_Luu-tru tiền tố DAXOA (KHÔNG unlink, còn đường cứu)."""
    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    row = next((r for r in doc_catalog(kho) if r["Mã tài liệu"] == doc_code), None)
    if row is None:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    if (xac_nhan_ma or "").strip() != doc_code:         # LỚP 2 xác nhận Ở SERVER
        raise HTTPException(400, "Xác nhận không khớp: phải gõ lại ĐÚNG mã tài liệu để xóa cứng.")
    try:                                                 # (1) QDRANT TRƯỚC
        client.xoa_chunk_doc_code(doc_code)
    except Exception as e:
        raise HTTPException(500, "Xóa chunk Qdrant thất bại — DỪNG, KHÔNG xóa catalog (tránh tài liệu "
                                 f"ma còn chunk trong Qdrant). Chi tiết: {e}")
    _xoa_dong_catalog(kho, doc_code)                     # (2) catalog SAU
    ten_file = (row.get("Tên file mới") or "").strip()   # (3) chuyển file → 99_Luu-tru
    ngan = (row.get("Ngăn") or "").strip()
    luu_ten = None
    cu = (kho / ngan / ten_file) if (ten_file and ngan) else None
    if cu and cu.is_file():
        luu = kho / "99_Luu-tru"; luu.mkdir(parents=True, exist_ok=True)
        dst = duong_dan_khong_trung(luu, f"DAXOA_{doc_code}_{ten_file}")
        shutil.move(str(cu), str(dst)); luu_ten = dst.name
    logging.info("XÓA CỨNG: owner=%s doc=%s (xóa chunk Qdrant + dòng catalog, file→%s) luc=%s",
                 user["ten"], doc_code, luu_ten or "(không có file)",
                 datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "doc_code": doc_code,
            "message": (f"Đã XÓA CỨNG {doc_code} khỏi kho + hệ thống tìm kiếm. File chuyển vào "
                        f"99_Luu-tru ({luu_ten}) để còn đường cứu (không hủy hẳn).")}


# ================= LỊCH SỬ HỘI THOẠI — 2 tầng: list PHIÊN + chi tiết lượt =================

def _khoa_thoi_gian_tho(ph: dict) -> str:
    """Thời gian lượt cuối ĐỌC THẲNG JSON (chưa lọc quyền) — dùng để sắp xếp/cắt TRƯỚC
    khi tốn Qdrant."""
    luot = ph.get("luot") or []
    return (luot[-1].get("thoi_gian") if luot else None) or ph.get("thoi_gian_tao", "")


def _danh_sach_phien(ten_user: str, loc_user: dict | None, gioi_han: int | None = None):
    """View-model list phiên (mới nhất trước). loc_user đặt → lọc D2 TỪNG LƯỢT; phiên
    trống-sau-lọc bị ẨN lặng lẽ. Owner giám sát truyền loc_user=None → nguyên bản.
    gioi_han: cắt còn N phiên gần nhất theo thời gian THÔ trước phần tốn Qdrant."""
    tat_ca = doc_phien(ten_user)
    if gioi_han is not None:
        tat_ca = sorted(tat_ca, key=_khoa_thoi_gian_tho, reverse=True)[:gioi_han]
    ket_qua = []
    for ph in tat_ca:
        cac_luot = ph.get("luot", [])
        if loc_user is not None:
            cac_luot = loc_theo_quyen(cac_luot, loc_user, client)
        if not cac_luot:
            continue
        cuoi = cac_luot[-1]
        ket_qua.append({
            "id": ph["id"],
            "ten": ph.get("ten") or cac_luot[0]["hoi"][:80],
            "preview": cuoi["hoi"],                      # lượt GẦN NHẤT (kiểu Cowork)
            "thoi_gian": cuoi.get("thoi_gian") or ph.get("thoi_gian_tao", ""),
            "so_luot": len(cac_luot),
            "highlight": (loc_user is not None
                          and phien_co_cau_da_giai(cac_luot, loc_user, client)),
        })
    ket_qua.sort(key=lambda p: p["thoi_gian"], reverse=True)
    return ket_qua


def _mot_phien(ten_user: str, phien_id: str) -> dict | None:
    return next((p for p in doc_phien(ten_user) if p["id"] == phien_id), None)


def _kiem_quyen_xem_lich_su(ten_user: str, user: dict) -> None:
    """BẢO MẬT giữ nguyên D1: user thường chỉ xem của mình; người khác → Owner."""
    if ten_user != user["ten"] and user["level"] != 5:
        raise HTTPException(403, "Chỉ Owner được xem lịch sử người khác.")


@app.get("/lich-su", response_class=HTMLResponse)
def lich_su_trang(request: Request, user: dict = Depends(lay_user)):
    """Tầng 1 của CHÍNH user: list phiên (lọc D2 từng lượt)."""
    cac_phien = _danh_sach_phien(user["ten"], user) if user.get("bo_phan") else []
    return templates.TemplateResponse(request, "lich_su.html", {
        "cac_phien": cac_phien, "chu_nhan": user["ten"], "cua_minh": True, "user": user})


@app.post("/lich-su/doi-ten")
def lich_su_doi_ten(phien_id: str = Form(...), ten_moi: str = Form(...),
                    user: dict = Depends(lay_user)):
    """Đổi tên phiên — CHỈ của chính mình."""
    if not user.get("bo_phan"):
        raise HTTPException(403, "Khách không có lịch sử.")
    if not doi_ten_phien(user["ten"], phien_id, ten_moi):
        raise HTTPException(404, "Không thấy phiên.")
    return {"ok": True}


@app.get("/lich-su/phien/{phien_id}", response_class=HTMLResponse)
def lich_su_phien_minh(phien_id: str, request: Request, user: dict = Depends(lay_user)):
    """Tầng 2 của chính mình — vẫn lọc D2 từng lượt."""
    ph = _mot_phien(user["ten"], phien_id) if user.get("bo_phan") else None
    if ph is None:
        raise HTTPException(404, "Không thấy phiên.")
    return templates.TemplateResponse(request, "lich_su_phien.html", {
        "ten_phien": ph.get("ten", ""), "cac_luot": loc_theo_quyen(ph["luot"], user, client),
        "chu_nhan": user["ten"], "cua_minh": True, "user": user,
        "phien_id": ph["id"]})  # Ý3: nút "Tiếp tục cuộc này"


@app.get("/lich-su/{ten_user}", response_class=HTMLResponse)
def lich_su_nguoi_khac(ten_user: str, request: Request, user: dict = Depends(lay_user)):
    """Tầng 1 giám sát (Owner) — NGUYÊN BẢN không lọc; chính chủ qua URL vẫn lọc D2."""
    _kiem_quyen_xem_lich_su(ten_user, user)
    cua_minh = ten_user == user["ten"]
    return templates.TemplateResponse(request, "lich_su.html", {
        "cac_phien": _danh_sach_phien(ten_user, user if cua_minh else None),
        "chu_nhan": ten_user, "cua_minh": cua_minh, "user": user})


@app.get("/lich-su/{ten_user}/phien/{phien_id}", response_class=HTMLResponse)
def lich_su_phien_nguoi_khac(ten_user: str, phien_id: str, request: Request,
                             user: dict = Depends(lay_user)):
    """Tầng 2 giám sát (Owner) — nguyên bản; chính chủ qua URL vẫn lọc D2."""
    _kiem_quyen_xem_lich_su(ten_user, user)
    ph = _mot_phien(ten_user, phien_id)
    if ph is None:
        raise HTTPException(404, "Không thấy phiên.")
    cua_minh = ten_user == user["ten"]
    cac_luot = loc_theo_quyen(ph["luot"], user, client) if cua_minh else ph["luot"]
    return templates.TemplateResponse(request, "lich_su_phien.html", {
        "ten_phien": ph.get("ten", ""), "cac_luot": cac_luot,
        "chu_nhan": ten_user, "cua_minh": cua_minh, "user": user,
        "phien_id": ph["id"]})


# ================= HỎI–ĐÁP: đường thường + 3 đường stream =================

def _doc_lich_su(history: str) -> list[dict]:
    # history = JSON [{"hoi": ..., "dap": ...}]; hỏng/thiếu → coi như hội thoại mới
    try:
        return [l for l in json.loads(history)
                if isinstance(l, dict)
                and isinstance(l.get("hoi"), str) and isinstance(l.get("dap"), str)]
    except ValueError:
        return []


@app.post("/hoi")
def hoi(question: str = Form(...), history: str = Form("[]"),
        phien_id: str = Form(""), user: dict = Depends(lay_user)):
    # Đường KHÔNG stream — giữ nguyên để fallback/chẩn đoán, KHÔNG xóa
    lich_su = _doc_lich_su(history)
    kq = qa.hoi(question, lich_su=lich_su, user=user)
    if user.get("bo_phan"):  # D1: chỉ lưu lịch sử cho user có bộ phận (claims đủ)
        bay_gio = datetime.now().isoformat(timespec="seconds")
        luu_luot(user["ten"], question, kq["answer"],
                 [s["doc_code"] for s in kq["sources"]], bay_gio,
                 bi_chan_quyen=bool(kq.get("bi_chan_quyen")),
                 phien_id=phien_id or None)
        # Kho thiếu THẬT (không phải bị chặn quyền) → vào sổ cho quản lý
        if la_cau_khong_tra_loi_duoc(kq["answer"]) and not kq.get("bi_chan_quyen"):
            ghi_cau_kho_thieu(question, user["bo_phan"], lich_su, bay_gio)
    return kq


@app.get("/kiem-stream", response_class=HTMLResponse)
def kiem_stream_trang(request: Request, user: dict = Depends(lay_user)):
    """Trang TỰ CHẨN ĐOÁN streaming: phát 5 con số cách nhau 1s — số nhảy TỪNG GIÂY là
    stream sống; 5 số hiện CÙNG LÚC là tầng trung gian đang đệm."""
    return templates.TemplateResponse(request, "kiem_stream.html", {"user": user})


@app.get("/kiem-stream/data")
def kiem_stream_data(user: dict = Depends(lay_user)):
    def phat():
        yield ": " + " " * 2048 + "\n\n"  # mồi chống đệm như /hoi-dap/stream
        for i in range(1, 6):
            yield f"data: {i}\n\n"
            time.sleep(1)

    return StreamingResponse(phat(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    })


@app.post("/hoi-dap/stream")
def hoi_stream_route(question: str = Form(...), history: str = Form("[]"),
                     phien_id: str = Form(""), user: dict = Depends(lay_user)):
    """Đường stream chính. SSE: event sources/token/review/done."""
    lich_su = _doc_lich_su(history)

    def sse():
        # CHỐNG ĐỆM Ở TRUNG GIAN: mồi 2KB dòng chú thích SSE để vượt ngưỡng đệm-theo-KB
        yield ": " + " " * 2048 + "\n\n"
        cac_mau, doc_codes, bi_chan = [], [], False
        for su_kien in qa.hoi_stream(question, lich_su=lich_su, user=user):
            if su_kien["type"] == "token":
                cac_mau.append(su_kien["data"])
            elif su_kien["type"] == "sources":
                doc_codes = [s["doc_code"] for s in su_kien["data"]]
            elif su_kien["type"] == "done":
                bi_chan = bool(su_kien["data"].get("bi_chan_quyen"))
            yield (f"event: {su_kien['type']}\n"
                   f"data: {json.dumps(su_kien['data'], ensure_ascii=False)}\n\n")
        # D1: lưu lịch sử SAU khi stream xong. Lượt "kho rỗng/tài liệu chưa nêu" VẪN lưu.
        if user.get("bo_phan"):
            answer = "".join(cac_mau)
            bay_gio = datetime.now().isoformat(timespec="seconds")
            luu_luot(user["ten"], question, answer, doc_codes, bay_gio,
                     bi_chan_quyen=bi_chan, phien_id=phien_id or None)
            if la_cau_khong_tra_loi_duoc(answer) and not bi_chan:
                ghi_cau_kho_thieu(question, user["bo_phan"], lich_su, bay_gio)

    return StreamingResponse(sse(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",  # no-transform: cấm trung gian nén/đệm
        "X-Accel-Buffering": "no",
    })


@app.post("/hoi-dap/stream-da-chieu")
def hoi_stream_da_chieu_route(question: str = Form(...), history: str = Form("[]"),
                              phien_id: str = Form(""), user: dict = Depends(lay_user)):
    """Bước 3 Supervisor — SSE trả lời ĐA CHIỀU (tách khối theo tầng nguồn). Đường RIÊNG,
    song song /hoi-dap/stream. RBAC + lưu lịch sử giống đường thường."""
    lich_su = _doc_lich_su(history)

    def sse():
        yield ": " + " " * 2048 + "\n\n"
        cac_mau, doc_codes, cong_ty_trong, bi_chan = [], [], False, False
        for su_kien in qa.hoi_stream_da_chieu(question, lich_su=lich_su, user=user):
            if su_kien["type"] == "token":
                cac_mau.append(su_kien["data"])
            elif su_kien["type"] == "sources":
                doc_codes = [s["doc_code"] for s in su_kien["data"]]
            elif su_kien["type"] == "done":
                cong_ty_trong = bool(su_kien["data"].get("cong_ty_trong"))
                bi_chan = bool(su_kien["data"].get("bi_chan_quyen"))
            yield (f"event: {su_kien['type']}\n"
                   f"data: {json.dumps(su_kien['data'], ensure_ascii=False)}\n\n")
        if user.get("bo_phan"):
            answer = "".join(cac_mau)
            bay_gio = datetime.now().isoformat(timespec="seconds")
            luu_luot(user["ten"], question, answer, doc_codes, bay_gio,
                     bi_chan_quyen=bi_chan, phien_id=phien_id or None)
            # Công ty trống + KHÔNG bị chặn quyền = kho công ty THIẾU chủ đề này → vào sổ
            if cong_ty_trong and not bi_chan:
                ghi_cau_kho_thieu(question, user["bo_phan"], lich_su, bay_gio)

    return StreamingResponse(sse(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    })


@app.post("/hoi-dap/stream-goc-nhin-ngoai")
def hoi_stream_goc_nhin_ngoai_route(question: str = Form(...), cau_tra_loi_cong_ty: str = Form(...),
                                    history: str = Form("[]"), user: dict = Depends(lay_user)):
    """Box gợi ý '🧭 góc nhìn khác' dưới câu trả lời công ty — bấm mới gọi. Đường PHỤ:
    không ghi lịch sử/kho-thiếu (lượt gốc đã ghi)."""
    lich_su = _doc_lich_su(history)

    def sse():
        yield ": " + " " * 2048 + "\n\n"
        for su_kien in qa.hoi_stream_goc_nhin_ngoai(question, cau_tra_loi_cong_ty,
                                                    lich_su=lich_su, user=user):
            yield (f"event: {su_kien['type']}\n"
                   f"data: {json.dumps(su_kien['data'], ensure_ascii=False)}\n\n")

    return StreamingResponse(sse(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    })


# ================= tải tài liệu + từ khóa + phản hồi =================

@app.get("/tai-ban-dep/{doc_code}")
def tai_ban_dep(doc_code: str, user: dict = Depends(lay_user)):
    """Ý 4: tải bản đẹp PDF theo ĐÚNG RBAC — không quyền và không-có-file trả 404
    GIỐNG HỆT nhau (lặng lẽ)."""
    khong_co = HTTPException(404, "Không có bản đẹp cho tài liệu này.")
    md = client.metadata_theo_doc_code([doc_code]).get(doc_code)
    if not md:  # mã không còn trong kho → ẩn an toàn
        raise khong_co
    if user.get("bo_phan") and not client._duoc_xem(md, user):
        raise khong_co

    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    ten_pdf, ngan = "", ""
    catalog = kho / "_catalog.csv"
    if catalog.exists():
        for d in list(csv.reader(catalog.open(encoding="utf-8-sig")))[1:]:
            if len(d) >= 16 and d[0] == doc_code and d[15]:
                ten_pdf, ngan = d[15], d[12]
    duong = kho / ngan / ten_pdf
    if not ten_pdf or not duong.is_file():
        raise khong_co
    return FileResponse(duong, media_type="application/pdf", filename=ten_pdf)


@app.get("/tai-ban-goc/{doc_code}")
def tai_ban_goc(doc_code: str, user: dict = Depends(lay_user)):
    """YC3: tải BẢN GỐC tài liệu — RBAC y hệt /tai-ban-dep (404 lặng lẽ)."""
    khong_co = HTTPException(404, "Không có tài liệu này.")
    md = client.metadata_theo_doc_code([doc_code]).get(doc_code)
    if not md:
        raise khong_co
    if user.get("bo_phan") and not client._duoc_xem(md, user):
        raise khong_co

    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    ten, ngan = "", ""
    catalog = kho / "_catalog.csv"
    if catalog.exists():
        for d in list(csv.reader(catalog.open(encoding="utf-8-sig")))[1:]:
            if len(d) >= 13 and d[0] == doc_code and d[11]:
                ten, ngan = d[11], d[12]        # "Tên file mới" + "Ngăn", dòng mới nhất thắng
    duong = kho / ngan / ten
    if not ten or not duong.is_file():
        raise khong_co
    return FileResponse(duong, filename=ten)


@app.get("/tu-khoa-goi-y")
def tu_khoa_goi_y(user: dict = Depends(yeu_cau_upload)):
    """Từ khóa đã dùng trong kho cho autocomplete ô nhập — chỉ Manager+ (người được nhập)."""
    return lay_tu_khoa_da_co(client)


@app.post("/co-tay")
def co_tay(question: str = Form(...), answer: str = Form(""), sources: str = Form(""),
           context: str = Form(""), user: dict = Depends(lay_user)):
    """Cờ tay "Câu này chưa có lời giải": người dùng XÁC NHẬN kho thiếu → nguồn chắc chắn
    nhất của bảng /kho-thieu."""
    if user.get("bo_phan"):  # thiếu bộ phận → bỏ qua, không ghi rác
        ghi_co_tay(question, user["bo_phan"], context, sources,
                   datetime.now().isoformat(timespec="seconds"))
    return {"ok": True}


@app.post("/phan-hoi")
def phan_hoi(question: str = Form(...), answer: str = Form(...),
             rating: str = Form(...), sources: str = Form(""),
             bi_chan_quyen: str = Form(""),
             user: dict = Depends(lay_user)):
    """Ghi 👍/👎 của người dùng vào sổ phan_hoi.csv trong kho.
    RULE 2: cột "Bị chặn quyền" = Có nghĩa là câu này rỗng DO LỌC QUYỀN chứ không phải
    kho thiếu → thống kê "kho thiếu gì" phải BỎ các dòng 👎 có cột này = Có."""
    # Không tin dữ liệu trình duyệt — chặn giá trị lạ, như /upload chặn ngoài dropdown
    if rating not in ("tot", "te"):
        raise HTTPException(422, f"rating '{rating}' không hợp lệ (chỉ nhận tot/te)")

    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    kho.mkdir(parents=True, exist_ok=True)
    ghi_csv_chi_them(kho / "phan_hoi.csv", PHAN_HOI_HEADER, [
        datetime.now().isoformat(timespec="seconds"), question, answer,
        "Tốt" if rating == "tot" else "Tệ", sources,
        "Có" if bi_chan_quyen.strip().lower() == "true" else "Không",
    ])
    return {"ok": True}


# ================= NHẬP LIỆU /upload =================

@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(yeu_cau_upload),  # RULE 1: Manager+ mới được nạp tài liệu
    title: str = Form(...),
    keywords: str = Form(""),
    owner: str = Form(""),
    version: str = Form("v1"),
    department: str = Form(...),
    doc_type: str = Form(...),
    effective_status: str = Form(...),
    access_level: str = Form(...),
    min_level: int = Form(...),
    tang_nguon: str = Form("noi_bo"),   # Supervisor — mặc định tài liệu công ty
    nguon_ten: str = Form(""),
):
    # Chặn giá trị ngoài dropdown — không tin dữ liệu từ trình duyệt gửi lên
    for value, allowed in [(department, DEPARTMENTS), (doc_type, DOC_TYPES),
                           (effective_status, EFFECTIVE_STATUSES), (access_level, ACCESS_LEVELS)]:
        if value not in allowed:
            raise HTTPException(422, f"Giá trị '{value}' không nằm trong dropdown cho phép")
    if not 1 <= min_level <= 5:
        raise HTTPException(422, f"Level tối thiểu '{min_level}' phải trong khoảng 1-5")
    # Supervisor: tầng "ngoai" BẮT BUỘC có tên nguồn CHÍNH XÁC
    if tang_nguon not in TANG_NGUON_VALUES:
        raise HTTPException(422, f"Tầng nguồn '{tang_nguon}' không nằm trong dropdown cho phép")
    nguon_ten = nguon_ten.strip()
    if tang_nguon == "noi_bo":
        nguon_ten = NGUON_TEN_CONG_TY
    elif not nguon_ten:
        raise HTTPException(422, "Tầng 'Nguồn khác' phải nhập Tên nguồn (tên người/nguồn chính xác)")

    ten_goc = Path(file.filename or "tai-lieu").name
    doc_code = f"{DEPT_PREFIX[department]}-{date.today().year}-{uuid.uuid4().hex[:6].upper()}"
    kho = Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    for ngan in NGAN_KHO:
        (kho / ngan).mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / ten_goc
        tmp_path.write_bytes(await file.read())

        # 1. Phát hiện PDF scan — vẫn nhập, chỉ cảnh báo + ghi cờ
        scan = la_pdf_scan(tmp_path)
        canh_bao = ("File này có thể là PDF scan (không có lớp chữ thật). "
                    "Lõi Qdrant không tự OCR — file vẫn được lưu kho nhưng sẽ KHÔNG "
                    "tìm kiếm được; hãy OCR ra chữ thật rồi nạp lại.") if scan else None

        # 2. Đổi tên theo khuôn chuẩn + 3. chép bản gốc vào đúng ngăn, không ghi đè
        ten_moi = ten_chuan(title, department, version, tmp_path.suffix)
        ngan = DEPT_FOLDER[department]
        dest = duong_dan_khong_trung(kho / ngan, ten_moi)
        shutil.copy2(tmp_path, dest)

    metadata = {
        "title": title,
        "keywords": keywords,
        "owner": owner,
        "version": version,
        "department": department,
        "doc_type": doc_type,
        "effective_status": effective_status,
        "access_level": access_level,
        "min_level": min_level,  # SỐ nguyên — Qdrant Range(lte) lọc quyền theo level
        "doc_code": doc_code,
        "import_date": date.today().isoformat(),
        "original_filename": ten_goc,
        "is_scanned": "true" if scan else "false",
        "tang_nguon": tang_nguon,   # Supervisor — vào payload Qdrant để gom theo tầng
        "nguon_ten": nguon_ten,
    }
    try:
        document_id = client.upload_document(str(dest), metadata)
    except Exception as e:  # file hỏng/không trích được — bản gốc vẫn nằm trong kho
        raise HTTPException(422, f"Đã lưu file vào kho nhưng không nạp được vào lõi tìm kiếm: {e}")

    # 4. Ghi sổ danh mục — luôn sau cùng, khi đã có document_id
    ghi_catalog(kho, [doc_code, metadata["import_date"], title, department, doc_type,
                      effective_status, version, access_level, min_level, keywords, owner,
                      dest.name, ngan, metadata["is_scanned"], document_id, "",
                      tang_nguon, nguon_ten])   # 2 cột cuối: Supervisor

    # TÀI LIỆU LIÊN QUAN — vector similarity thuần, embedding local nên rẻ, chạy đồng bộ.
    # Lỗi không chặn nạp liệu — chỉ mất phần liên quan.
    try:
        tinh_va_luu_lien_quan(doc_code, title, keywords, client, kho)
    except Exception as e:
        logging.warning("Không tính được tài liệu liên quan cho %s: %s", doc_code, e)

    # Bản đẹp chạy NỀN — writer + critic + render PDF mất hàng chục giây.
    lam_ban_dep = (os.getenv("REMAKE_DEP", "true").strip().lower() == "true"
                   and dest.suffix.lower() == ".docx")
    if lam_ban_dep:
        background_tasks.add_task(_ban_dep_nen, dest, title, doc_code, kho)

    return {
        "document_id": document_id,
        "doc_code": doc_code,
        "new_filename": dest.name,
        "folder": ngan,
        "warning": canh_bao,
        "message": (f"Đã lưu '{title}' vào kho (mã tài liệu: {doc_code})."
                    + (" Bản đẹp đang được tạo ở chế độ nền." if lam_ban_dep else "")),
    }
