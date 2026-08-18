"""Server local cho UI điều phối sản xuất.

- Chỉ bind 127.0.0.1 — dữ liệu nhân sự (nguyên tắc 6) không ra ngoài máy.
- Kế hoạch lưu ở data/plan.json (được .gitignore).
- Chạy:  python3 server.py  (thêm --no-browser nếu không muốn tự mở browser)

API:
  GET  /            → ui/index.html
  GET  /api/state   → kế hoạch đã lưu (input thô)
  POST /api/plan    → nhận input, tính lịch; hợp lệ thì lưu rồi trả {"schedule": ...}
"""

from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from planner import (
    Assignment,
    BestPerformance,
    PlanInput,
    PlanResult,
    Person,
    Project,
    StageConfig,
    Video,
    compute_schedule,
)

ROOT = Path(__file__).resolve().parent
# V3 (19/08/2026): dữ liệu tách khỏi mã — PLANNER_DATA_DIR trỏ data/plannery của
# nền (luật sổ địa bạ SO_DIA_BA_DU_LIEU); không đặt (chạy standalone) → ./data như cũ.
DATA_DIR = Path(os.environ.get("PLANNER_DATA_DIR") or (ROOT / "data"))
DATA_FILE = DATA_DIR / "plan.json"
ROLES_FILE = DATA_DIR / "roles.json"
USERS_FILE = DATA_DIR / "users.json"
INDEX_FILE = ROOT / "ui" / "index.html"
# Quản trị viên gốc (username nginx) — luôn có quyền admin dù users.json trống.
# Đặt qua env ADMIN_USERS="an,binh"; mặc định 'admin' cho local.
ADMIN_USERS = {u.strip() for u in os.environ.get("ADMIN_USERS", "admin").split(",") if u.strip()}
# File .htpasswd của nginx (để tab quản trị tạo/xoá đăng nhập cho người mới)
HTPASSWD_FILE = os.environ.get("HTPASSWD_FILE", "")
# Danh sách role hợp lệ (quyền: xem SPEC mục 6)
ROLES = {"admin", "manager", "hr", "leader", "seo", "member", "viewer"}
# Lên VPS: đặt PLANNER_HOST=127.0.0.1 và che sau reverse proxy có HTTPS
HOST = os.environ.get("PLANNER_HOST", "127.0.0.1")
_port_env = os.environ.get("PLANNER_PORT")
PORTS = [int(_port_env)] if _port_env else range(8123, 8134)
MAX_BODY = 5_000_000  # 5MB — chặn body quá khổ

EMPTY_STATE = {"people": [], "projects": [], "assignments": [], "_rev": 0}
LOCK = threading.Lock()  # đọc-sửa-ghi plan.json phải tuần tự (nhiều người dùng)

# ================= PHÂN QUYỀN (server-side) =================
# Mã vai trò nằm NGOÀI mã nguồn, trong data/roles.json (gitignore) — đổi mã ở đó.
DEFAULT_ROLES = {"admin": "QT-123ABC", "hr": "HR-123ABC", "leader": "LD-123ABC", "member": "NS-123ABC"}


def load_roles() -> dict:
    ROLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not ROLES_FILE.exists():
        ROLES_FILE.write_text(json.dumps(DEFAULT_ROLES, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        return json.loads(ROLES_FILE.read_text(encoding="utf-8"))
    except ValueError:
        return dict(DEFAULT_ROLES)


def role_of(code: str | None) -> str:
    """Local dev: đổi mã vai trò lấy role (roles.json). Production dùng X-Remote-User."""
    if not code or not code.strip():
        return "viewer"
    for role, c in load_roles().items():
        if code.strip() == c:
            return role
    return "viewer"


def _load_udb() -> dict:
    """Cơ sở người dùng: {"users": {username: {name,email,role}}, "invites": {code: {...}}}."""
    if not USERS_FILE.exists():
        return {"users": {}, "invites": {}}
    try:
        db = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except ValueError:
        return {"users": {}, "invites": {}}
    if "users" not in db:  # migrate định dạng phẳng cũ (username → rec)
        db = {"users": db, "invites": {}}
    db.setdefault("users", {})
    db.setdefault("invites", {})
    return db


def _save_udb(db: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_name("users.json.tmp")
    tmp.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(USERS_FILE)


def load_users() -> dict:
    """username (đăng nhập nginx) → {name, email, role}."""
    return _load_udb()["users"]


# ── SSO từ OUTLIERY (30/07/2026; nâng chuẩn V3 19/08/2026) ──
# Bật bằng PLANNER_TRUST_PROXY=1. Gateway V3 đăng nhập + phân quyền rồi tiêm
# X-Remote-User + X-Remote-Actions (nguồn quyền CHÍNH — app CHỈ TIN CỜ, khuôn
# niche-research) + X-Remote-Role (fallback) vào mỗi request qua proxy.
# VÁ BẪY V2 (DE.md:462): khi SSO bật, users.json/ADMIN_USERS KHÔNG thắng header
# nữa — vai 100% theo gateway; sổ riêng chỉ còn nghĩa khi chạy standalone.
# X-Remote-* CHỈ nhận từ loopback (proxy đứng cùng máy — header từ client LAN
# trực tiếp là giả mạo, bỏ; vá luôn lỗ ADMIN_USERS đứng trước kiểm loopback cũ).
_VAI_SSO = {"admin": "admin", "owner": "admin", "manager": "manager",
            "leader": "leader", "seo": "seo", "viewer": "viewer"}
_LOOPBACK = ("127.0.0.1", "::1", "localhost")


def _sso_hoat_dong(client_ip: str | None) -> bool:
    return (os.environ.get("PLANNER_TRUST_PROXY") == "1"
            and client_ip in _LOOPBACK)


def _vai_tu_actions(actions: str | None) -> str | None:
    """Dịch X-Remote-Actions (hành động phan_quyen.json của nền) → vai PlannerY,
    dừng-tại-hit-đầu như iam.vai_cho_app: quan_tri→admin · toan_quyen→manager ·
    sua→leader · khai_kenh_video→seo. Header RỖNG → None (rơi về X-Remote-Role)."""
    co = {a.strip() for a in (actions or "").split(",") if a.strip()}
    if not co:
        return None
    if "quan_tri" in co:
        return "admin"
    if "toan_quyen" in co:
        return "manager"
    if "sua" in co:
        return "leader"
    if "khai_kenh_video" in co:
        return "seo"
    return "viewer"


def identity(headers, client_ip: str | None = None) -> tuple[str | None, str]:
    """(username, role) của request. X-Remote-* chỉ nhận từ loopback; SSO bật →
    vai 100% theo gateway. Local dev: từ mã vai trò X-Role-Code."""
    user = (headers.get("X-Remote-User") or "").strip()
    if user and client_ip in _LOOPBACK:
        if _sso_hoat_dong(client_ip):
            vai = _vai_tu_actions(headers.get("X-Remote-Actions"))
            if vai is None:
                vai = _VAI_SSO.get(
                    (headers.get("X-Remote-Role") or "").strip().lower(), "viewer")
            return user, vai
        if user in ADMIN_USERS:
            return user, "admin"
        rec = load_users().get(user)
        if rec:
            return user, rec["role"]
        return user, "viewer"
    return None, role_of(headers.get("X-Role-Code"))


def normalize_username(raw: str) -> str:
    """Chuẩn hoá tên (kể cả tiếng Việt có dấu) thành username ASCII hợp lệ cho nginx.
    'Nguyễn Văn A' → 'nguyenvana'. Giữ chữ/số, bỏ dấu và ký tự khác."""
    import unicodedata
    s = raw.strip().lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # bỏ dấu thanh/mũ
    return "".join(c for c in s if c.isalnum())


def _run_htpasswd(args: list[str]) -> None:
    """Tạo/xoá đăng nhập nginx cho người mới — chỉ chạy khi được cấu hình trên VPS."""
    import shutil
    import subprocess
    if not HTPASSWD_FILE or not shutil.which("htpasswd"):
        return
    subprocess.run(["htpasswd", *args], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _member_projects_ok(old: list, new: list) -> bool:
    """Nhân sự kênh (SEO): sửa VIDEO (thêm/sửa/XOÁ) + thời lượng kênh của kênh CÓ SẴN,
    và (31/07/2026 — user OUTLIERY chốt "nhân viên L2 Kinh doanh được thêm kênh và
    video cần làm") THÊM KÊNH MỚI vào dự án có sẵn. Vẫn cấm: thêm/bớt/sửa DỰ ÁN,
    xoá kênh cũ, sửa cấu hình kênh cũ (tên, màu, khâu, ngày bắt đầu…).
    So kênh theo ID (không theo vị trí) để kênh mới chèn vào đâu cũng nhận đúng."""
    if len(old) != len(new):
        return False
    for opr, npr in zip(old, new):
        if {k: v for k, v in opr.items() if k != "channels"} != \
           {k: v for k, v in npr.items() if k != "channels"}:
            return False
        och = {c.get("id"): c for c in opr.get("channels") or []}
        nch = {c.get("id"): c for c in npr.get("channels") or []}
        if set(och) - set(nch):
            return False                      # xoá kênh cũ: không phải việc của SEO
        for cid, oc in och.items():
            nc = nch[cid]
            for k in (set(oc) | set(nc)) - {"videos", "video_minutes"}:
                if oc.get(k) != nc.get(k):
                    return False
        # kênh id MỚI (không có trong old) → là kênh vừa thêm, cho qua
    return True


def _people_diff_within(old: list, new: list, allowed: set) -> bool:
    """Mỗi người chỉ khác ở các field trong `allowed` (thứ tự danh sách bỏ qua)."""
    om = {p.get("id"): p for p in old}
    nm = {p.get("id"): p for p in new}
    if set(om) != set(nm):
        return False
    for pid, np in nm.items():
        op = om[pid]
        for k in (set(op) | set(np)) - allowed:
            if op.get(k) != np.get(k):
                return False
    return True


def _is_review_change(old: dict, new: dict) -> bool:
    """Đúng 'hình dạng' Tổng kết tuần / Chốt ngày: chỉ đụng năng suất tuần trước,
    danh sách video (gỡ tập đã xong), báo cáo, và nhật ký chốt ngày — không hơn."""
    changed = {k for k in (set(old) | set(new)) - {"_rev"} if old.get(k) != new.get(k)}
    if changed - {"people", "projects", "reports", "daily"}:
        return False
    if "people" in changed and not _people_diff_within(
        old.get("people", []), new.get("people", []), {"last_week_rate"}
    ):
        return False
    if "projects" in changed and not _member_projects_ok(
        old.get("projects", []), new.get("projects", [])
    ):
        return False
    return True


def check_permission(role: str, old: dict, new: dict) -> str | None:
    """Ma trận quyền SPEC mục 6 — trả về thông báo lỗi nếu vi phạm, None nếu ổn."""
    if role in ("admin", "manager"):  # Quản trị & Quản lý: sửa full dữ liệu
        return None
    keys = (set(old) | set(new)) - {"_rev"}
    changed = {k for k in keys if old.get(k) != new.get(k)}
    if role in ("seo", "member"):  # SEO / nhân sự kênh: thêm kênh mới + thêm/sửa video
        if changed - {"projects"}:
            return "SEO chỉ được thêm kênh mới và thêm/sửa video trong kênh."
        if not _member_projects_ok(old.get("projects", []), new.get("projects", [])):
            return ("SEO chỉ được thêm KÊNH MỚI + thêm/sửa/xoá video + thời lượng kênh "
                    "— không đụng cấu hình kênh cũ/dự án.")
        return None
    if role == "hr":
        # HR: hồ sơ nhân sự + PHÂN CÔNG (15/07) + TỔNG KẾT TUẦN (15/07)
        if changed <= {"people", "assignments"}:
            return None
        if _is_review_change(old, new):
            return None
        return "HR chỉ được sửa nhân sự, phân công, và tổng kết tuần."
    if role == "leader":
        # Leader làm được dự án/kênh/lịch; chỉ chặn sửa HỒ SƠ nhân sự — nhưng cho
        # đổi 'đang làm' + thứ tự + năng suất tuần trước (tổng kết tuần).
        if "people" in changed and not _people_diff_within(
            old.get("people", []), new.get("people", []),
            {"home_project_id", "last_week_rate", "leaves"}
        ):
            return "Leader chỉ sửa được 'đang làm', thứ tự, ngày nghỉ và tổng kết tuần — hồ sơ còn lại là của HR."
        return None
    return "Vai trò không có quyền ghi."

WARNING_TYPES = {
    "LateWarning": "late",
    "UnstaffedWarning": "unstaffed",
    "UnderStandardWarning": "under_standard",
    "BottleneckWarning": "bottleneck",
}


def plan_from_dict(d: dict) -> PlanInput:
    """Schema v3: dự án là NHÓM chứa kênh; mỗi KÊNH là một dây sản xuất hoàn chỉnh.

    Engine nhận mỗi kênh thành một Project (id = "duAn::kenh", group_id = dự án);
    phân công người ↔ dự án được nhân bản ra mọi kênh trong dự án đó.
    """
    people = [
        Person(
            p["id"], p["name"], p["role"], float(p["standard_rate"]),
            float(p["last_week_rate"]) if p.get("last_week_rate") is not None else None,
            p.get("home_project_id") or None,
            tuple((date.fromisoformat(L["from"]), date.fromisoformat(L["to"]))
                  for L in p.get("leaves", []) if L.get("from") and L.get("to")),
            float(p["clone_rate"]) if p.get("clone_rate") else None,
        )
        for p in d.get("people", [])
    ]
    projects = []
    group_channels: dict[str, list[str]] = {}
    for pr in d.get("projects", []):
        group_channels[pr["id"]] = []
        for ch in pr.get("channels", []):
            stages = tuple(
                StageConfig(
                    s["role"],
                    int(s.get("feedback_rounds", 0)),
                    float(s.get("feedback_wait_days", 0)),
                    float(s.get("revision_days", 0)),
                )
                for s in ch["stages"]
            )
            videos = tuple(
                Video(
                    int(v["index"]), v.get("title", ""),
                    date.fromisoformat(v["publish_date"]) if v.get("publish_date") else None,
                    bool(v.get("priority")),
                    bool(v.get("has_script")),
                    bool(v.get("urgent")),
                    tuple(v.get("assigned_editors", [])),
                )
                for v in ch.get("videos", [])
            )
            bp = ch.get("best_performance")
            eng_id = f"{pr['id']}::{ch['id']}"
            group_channels[pr["id"]].append(eng_id)
            projects.append(
                Project(
                    eng_id, f"{pr['name']} · {ch['name']}",
                    date.fromisoformat(ch["start_date"]),
                    float(ch["video_minutes"]), stages, videos,
                    ch["name"], int(ch.get("script_stock", 0)),
                    BestPerformance(
                        float(bp["days_per_video"]), bp["editor_name"],
                        date.fromisoformat(bp["recorded_on"]),
                    ) if bp else None,
                    group_id=pr["id"],
                )
            )
    assignments = [
        Assignment(a["person_id"], eng_id)
        for a in d.get("assignments", [])
        for eng_id in group_channels.get(a["project_id"], [])
    ]
    return PlanInput(people, projects, assignments)


def result_to_dict(result: PlanResult) -> dict:
    return {
        "anchor": result.anchor.isoformat() if result.anchor else None,
        "projects": [
            {
                "project_id": ps.project_id,
                "project_name": ps.project_name,
                "videos": [
                    {
                        "index": v.index,
                        "title": v.title,
                        "handoff_date": v.handoff_date.isoformat(),
                        "publish_date": v.publish_date.isoformat() if v.publish_date else None,
                        "late_workdays": v.late_workdays,
                        "stages": [
                            {
                                "role": st.role,
                                "person_id": st.person_id,
                                "person_name": st.person_name,
                                "done_date": st.done_date.isoformat(),
                                "segments": [
                                    {
                                        "kind": s.kind,
                                        "start_t": s.start_t,
                                        "end_t": s.end_t,
                                        "start_date": s.start_date.isoformat(),
                                        "end_date": s.end_date.isoformat(),
                                        "overtime": s.overtime,
                                    }
                                    for s in st.segments
                                ],
                            }
                            for st in v.stages
                        ],
                    }
                    for v in ps.videos
                ],
            }
            for ps in result.projects
        ],
        "warnings": [
            {"type": WARNING_TYPES[type(w).__name__], "message": w.message()}
            for w in result.warnings
        ],
    }


INVITE_PAGE = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PlannerY — Đăng ký</title>
<style>
 body{margin:0;background:#0E1117;color:#E6E2D8;font:15px/1.5 -apple-system,"Segoe UI",sans-serif;
  display:flex;min-height:100vh;align-items:center;justify-content:center}
 .card{background:#151A22;border:1px solid #2A3340;border-radius:12px;padding:26px 28px;width:min(420px,92vw)}
 h1{font-size:19px;margin:0 0 2px}h1 em{color:#E3AC45;font-style:normal}
 .sub{color:#9AA1AD;font-size:13px;margin:0 0 18px}
 label{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#6B7280;margin:12px 0 4px}
 input{width:100%;box-sizing:border-box;background:#1C232E;border:1px solid #2A3340;border-radius:7px;
  color:#E6E2D8;padding:9px 11px;font:14px inherit}
 button{width:100%;margin-top:18px;background:#E3AC45;color:#161006;font-weight:700;border:none;
  border-radius:7px;padding:10px;font:15px inherit;cursor:pointer}
 .msg{margin-top:14px;font-size:13px;padding:9px 12px;border-radius:7px;display:none}
 .msg.err{display:block;background:rgba(217,124,108,.13);border:1px solid #D97C6C;color:#D97C6C}
 .msg.ok{display:block;background:rgba(131,169,111,.13);border:1px solid #83A96F;color:#83A96F}
</style></head><body>
<div class="card">
 <h1>PLANNER<em>Y</em></h1>
 <p class="sub">Đăng ký bằng mã mời do quản trị cấp.</p>
 <label>Mã mời</label><input id="code" placeholder="ply-…">
 <label>Họ tên của bạn</label><input id="name" placeholder="vd: Nguyễn Văn A">
 <label>Email (bắt buộc)</label><input id="email" type="email" placeholder="ten@congty.com" required>
 <label>Mật khẩu (tối thiểu 6 ký tự)</label><input id="password" type="password">
 <label>Tên đăng nhập <span style="text-transform:none;color:#6B7280">— tự tạo từ họ tên, sửa nếu muốn</span></label>
 <input id="username" placeholder="tự điền khi gõ họ tên" autocapitalize="off">
 <button id="go">Tạo tài khoản</button>
 <div class="msg" id="msg"></div>
</div>
<script>
const $=s=>document.getElementById(s);
const norm=t=>t.normalize("NFD").replace(/đ/gi,"d").replace(/[\\u0300-\\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]/g,"");
const url=new URLSearchParams(location.search); if(url.get("code"))$("code").value=url.get("code");
let touched=false; $("username").addEventListener("input",()=>touched=true);
$("name").addEventListener("input",()=>{ if(!touched)$("username").value=norm($("name").value); });
$("go").onclick=async()=>{
 const b={code:$("code").value.trim(),username:$("username").value.trim()||$("name").value.trim(),
  name:$("name").value.trim(),email:$("email").value.trim(),password:$("password").value};
 const m=$("msg"); m.className="msg";
 if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(b.email)){m.className="msg err";m.textContent="Email bắt buộc và phải hợp lệ (vd ten@congty.com).";return;}
 $("go").disabled=true;
 try{
  const r=await fetch("/api/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)});
  const d=await r.json();
  if(!r.ok){m.className="msg err";m.textContent=d.error||"Lỗi.";$("go").disabled=false;return;}
  m.className="msg ok";
  m.innerHTML=d.htpasswd
   ?`Xong! Tên đăng nhập của bạn là <b>${d.username}</b>. `
    +`<a href="/" style="color:#83A96F">Bấm vào đây để đăng nhập</a> — nhập <b>${d.username}</b> và mật khẩu vừa đặt.`
   :"Đã ghi nhận (local: đăng nhập thật chỉ có khi lên VPS).";
 }catch(e){m.className="msg err";m.textContent="Không kết nối được máy chủ.";$("go").disabled=false;}
};
</script></body></html>"""


LOGOUT_PAGE = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PlannerY — Đã đăng xuất</title>
<style>body{margin:0;background:#0E1117;color:#E6E2D8;font:15px/1.5 -apple-system,"Segoe UI",sans-serif;
 display:flex;min-height:100vh;align-items:center;justify-content:center;text-align:center}
 .card{background:#151A22;border:1px solid #2A3340;border-radius:12px;padding:30px 34px}
 h1{font-size:19px;margin:0 0 6px}h1 em{color:#E3AC45;font-style:normal}
 p{color:#9AA1AD;font-size:13px;margin:0 0 18px}
 a{display:inline-block;background:#E3AC45;color:#161006;font-weight:700;text-decoration:none;
  border-radius:7px;padding:9px 20px}</style></head><body>
<div class="card"><h1>PLANNER<em>Y</em></h1>
<p>Đã đăng xuất. Bấm để đăng nhập lại (có thể bằng tài khoản khác).</p>
<a href="/">Đăng nhập lại</a></div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @property
    def route(self) -> str:
        """Đường dẫn KHÔNG kèm query (self.path còn cả ?code=... nên phải cắt)."""
        return self.path.split("?", 1)[0]

    def _sso_dong_cua(self) -> bool:
        """SSO bật → cửa tài khoản/mã mời NỘI BỘ đóng 404 VÔ ĐIỀU KIỆN (kể cả
        admin — khuôn _chot_quan_tri niche-research): tài khoản quản ở General
        của nền, app không giữ sổ vai riêng nữa."""
        if _sso_hoat_dong(self.client_address[0]):
            self._send_json(404, {"error": "Không tìm thấy"})
            return True
        return False

    def do_GET(self) -> None:
        if self.route == "/" or self.route == "/index.html":
            body = INDEX_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")  # tránh trình duyệt giữ bản cũ sau deploy
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.route == "/api/state":
            if DATA_FILE.exists():
                state = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                state.setdefault("_rev", 0)
            else:
                state = dict(EMPTY_STATE)
            self._send_json(200, state)
        elif self.route == "/api/me":
            # danh tính hiện tại (production: từ proxy X-Remote-User)
            user, role = identity(self.headers, self.client_address[0])
            rec = load_users().get(user) if user else None
            self._send_json(200, {
                "username": user, "role": role,
                "name": (rec or {}).get("name", user or ""),
                # sso=True → giao diện giấu chip 👤 + nút "Đổi tài khoản": danh tính đã hiện
                # ở topbar OUTLIERY, đổi người = đăng xuất ở OUTLIERY, không đổi ở đây.
                "sso": bool(user) and _sso_hoat_dong(self.client_address[0]),
            })
        elif self.route == "/api/users":
            if self._sso_dong_cua():
                return
            user, role = identity(self.headers, self.client_address[0])
            if role != "admin":
                self._send_json(403, {"error": "Chỉ Quản trị được xem danh sách người dùng."})
                return
            db = _load_udb()
            now = int(datetime.now().timestamp())
            invites = {c: v for c, v in db["invites"].items() if v.get("expires", 0) > now}
            self._send_json(200, {"users": db["users"], "invites": invites, "htpasswd": bool(HTPASSWD_FILE)})
        elif self.route == "/invite":
            if self._sso_dong_cua():
                return
            body = INVITE_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.route == "/logout":
            if self._sso_dong_cua():
                return
            # Đăng xuất basic-auth: trả 401 để trình duyệt QUÊN đăng nhập cũ,
            # kèm trang có link vào lại (đăng nhập tài khoản khác).
            body = LOGOUT_PAGE.encode("utf-8")
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="PlannerY"')
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send_json(404, {"error": "Không tìm thấy"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            self._send_json(413, {"error": "Dữ liệu quá lớn."})
            return
        try:
            raw = json.loads(self.rfile.read(length))
        except ValueError:
            self._send_json(400, {"error": "JSON không hợp lệ."})
            return

        if self.route == "/api/role":
            if self._sso_dong_cua():
                return
            # đăng nhập vai trò (LOCAL DEV): đổi mã lấy role. Production dùng nginx.
            code = str(raw.get("code", ""))
            if not code.strip():
                self._send_json(200, {"role": "viewer"})
                return
            role = role_of(code)
            if role == "viewer":
                self._send_json(403, {"error": "Mã vai trò không đúng."})
            else:
                self._send_json(200, {"role": role})
            return

        if self.route == "/api/register":
            if self._sso_dong_cua():
                return
            # tự đăng ký bằng MÃ MỜI — PUBLIC (nginx để location này auth_basic off)
            code = str(raw.get("code", "")).strip()
            name = str(raw.get("name", "")).strip()
            email = str(raw.get("email", "")).strip()
            # username tự chuẩn hoá từ tên (chấp nhận tiếng Việt); có thể tự nhập riêng
            username = normalize_username(str(raw.get("username", "")) or name)
            pw = str(raw.get("password", ""))
            db = _load_udb()
            now = int(datetime.now().timestamp())
            inv = db["invites"].get(code)
            if not inv or inv.get("expires", 0) <= now:
                self._send_json(403, {"error": "Mã mời không đúng hoặc đã hết hạn."})
                return
            if len(username) < 2:
                self._send_json(400, {"error": "Cần nhập Họ tên (hoặc tên đăng nhập) có chữ hoặc số."})
                return
            if "@" not in email or "." not in email.split("@")[-1]:
                self._send_json(400, {"error": "Email bắt buộc và phải hợp lệ (vd ten@congty.com)."})
                return
            if len(pw) < 6:
                self._send_json(400, {"error": "Mật khẩu tối thiểu 6 ký tự."})
                return
            if username in ADMIN_USERS or username in db["users"]:
                self._send_json(409, {"error": f"Tên đăng nhập '{username}' đã có người dùng — thêm số vào cho khác (vd {username}2)."})
                return
            db["users"][username] = {"name": name, "email": email, "role": inv["role"]}
            del db["invites"][code]  # mã mời dùng một lần
            _save_udb(db)
            if HTPASSWD_FILE:
                _run_htpasswd(["-bB", HTPASSWD_FILE, username, pw])
            self._send_json(200, {"ok": True, "username": username, "role": inv["role"],
                                  "htpasswd": bool(HTPASSWD_FILE)})
            return

        if self.route == "/api/users":
            if self._sso_dong_cua():
                return
            # Quản trị: quản lý thành viên + mã mời — chỉ admin
            _, role = identity(self.headers, self.client_address[0])
            if role != "admin":
                self._send_json(403, {"error": "Chỉ Quản trị được quản lý người dùng."})
                return
            action = raw.get("action")
            db = _load_udb()
            now = int(datetime.now().timestamp())
            if action == "make_invite":
                new_role = raw.get("user_role", "seo")
                if new_role not in ROLES or new_role == "admin":
                    self._send_json(400, {"error": "Role không hợp lệ."})
                    return
                import secrets
                code = "ply-" + secrets.token_urlsafe(9)
                db["invites"][code] = {"role": new_role, "created": now, "expires": now + 7 * 86400}
                _save_udb(db)
                self._send_json(200, {"invite": {"code": code, "role": new_role}})
                return
            if action == "revoke_invite":
                db["invites"].pop(str(raw.get("code", "")), None)
                _save_udb(db)
                self._send_json(200, {"ok": True})
                return
            username = str(raw.get("username", "")).strip().lower()
            if action == "remove":
                if username in ADMIN_USERS:
                    self._send_json(403, {"error": "Không thể xoá quản trị viên gốc."})
                    return
                db["users"].pop(username, None)
                _save_udb(db)
                if HTPASSWD_FILE:
                    _run_htpasswd(["-D", HTPASSWD_FILE, username])
                self._send_json(200, {"ok": True})
                return
            if action == "setrole":
                new_role = raw.get("user_role")
                if username not in db["users"] or new_role not in ROLES or new_role == "admin":
                    self._send_json(400, {"error": "Không đổi được role."})
                    return
                db["users"][username]["role"] = new_role
                _save_udb(db)
                self._send_json(200, {"ok": True})
                return
            if action == "setpass":
                # Quản trị đổi mật khẩu đăng nhập (nginx htpasswd) cho một tài khoản
                pw = str(raw.get("password", ""))
                if username not in db["users"] and username not in ADMIN_USERS:
                    self._send_json(404, {"error": "Không có tài khoản này."})
                    return
                if len(pw) < 6:
                    self._send_json(400, {"error": "Mật khẩu tối thiểu 6 ký tự."})
                    return
                if not HTPASSWD_FILE:
                    self._send_json(200, {"ok": True, "htpasswd": False})  # local: không có auth thật
                    return
                _run_htpasswd(["-bB", HTPASSWD_FILE, username, pw])
                self._send_json(200, {"ok": True, "htpasswd": True})
                return
            self._send_json(400, {"error": "Hành động không hợp lệ."})
            return

        if self.route != "/api/plan":
            self._send_json(404, {"error": "Không tìm thấy"})
            return

        _, role = identity(self.headers, self.client_address[0])
        if role == "viewer":
            self._send_json(403, {"error": "Cần quyền ghi — bấm 👤 đăng nhập (mã vai trò khi chạy local)."})
            return
        with LOCK:  # nhiều người cùng lưu: tuần tự + chống ghi đè chéo
            old = (json.loads(DATA_FILE.read_text(encoding="utf-8"))
                   if DATA_FILE.exists() else dict(EMPTY_STATE))
            if old.get("_rev", 0) != raw.get("_rev", 0):
                self._send_json(409, {"error": "Người khác vừa lưu bản mới hơn — trang sẽ tải lại dữ liệu mới nhất."})
                return
            err = check_permission(role, old, raw)
            if err:
                self._send_json(403, {"error": f"[{role}] {err}"})
                return
            try:
                result = compute_schedule(plan_from_dict(raw))
            except (ValueError, KeyError, TypeError) as e:
                self._send_json(400, {"error": f"Input không hợp lệ: {e}"})
                return
            raw["_rev"] = old.get("_rev", 0) + 1
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            if DATA_FILE.exists():
                # 2 lớp backup: bản ngay trước + kho bản theo thời gian (giữ 40 bản)
                backups = DATA_FILE.parent / "backups"
                backups.mkdir(exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                (backups / f"plan-{stamp}.json").write_text(
                    DATA_FILE.read_text(encoding="utf-8"), encoding="utf-8"
                )
                for f in sorted(backups.glob("plan-*.json"))[:-40]:
                    f.unlink()
                DATA_FILE.replace(DATA_FILE.with_name("plan.backup.json"))
            # ghi nguyên tử: ghi file tạm rồi thay thế — không bao giờ dở dang
            tmp = DATA_FILE.with_name("plan.json.tmp")
            tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(DATA_FILE)
            self._send_json(200, {"schedule": result_to_dict(result), "_rev": raw["_rev"]})

    def log_message(self, fmt: str, *args) -> None:  # log gọn một dòng
        print(f"[server] {self.command} {self.path} → {args[1] if len(args) > 1 else ''}")


def main() -> None:
    server = None
    for port in PORTS:
        try:
            server = ThreadingHTTPServer((HOST, port), Handler)
            break
        except OSError:
            continue
    if server is None:
        print(f"Không mở được cổng nào trong {PORTS.start}–{PORTS.stop - 1}.")
        sys.exit(1)
    url = f"http://{HOST}:{server.server_address[1]}"
    print(f"Tool điều phối sản xuất đang chạy tại {url}  (Ctrl+C để dừng)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")


if __name__ == "__main__":
    main()
