# -*- coding: utf-8 -*-
"""VIDEO REVIEW (v3, :9114) — feedback video kiểu Frame.io, app nghiệp vụ MỚI.

Nghiệp vụ: team upload bản dựng video → người khác xem, BÌNH LUẬN GẮN MỐC THỜI GIAN
(bấm bình luận là tua tới đúng giây) + VẼ CHÚ THÍCH trên khung hình → trạng thái duyệt
(In review / Changes requested / Approved). Đúng khuôn hợp đồng app (theo to-chuc):

1. AUTH: không tự giữ user — claims X-Remote-User/Level/Role/Dept từ gateway; gate
   tính năng bằng CỜ X-Remote-Actions (Permissions v2, fail-closed):
   'duyet' = đổi trạng thái video (mặc định Leader+) · 'xoa' = gỡ video (Manager+).
   Xem/bình luận/upload = mọi người có claims ('vao' min_level 1).
2. DỮ LIỆU (Luật 6): sổ SQLite data/video-review/db. VIDEO KHÔNG NẰM TRONG APP —
   app LIÊN KẾT tới file gốc trên NAS (VR_NAS_DIR), sổ chỉ giữ đường tương đối
   (user chốt 20/08: anh em up NAS rồi đưa sang app, không chép bản thứ hai).
   NAS chỉ ĐỌC — xóa video vẫn là GỠ MỀM, không bao giờ đụng file trên NAS.
3. VIDEO QUA PROXY: proxy gateway đọc TRỌN body phản hồi vào RAM (trừ SSE) →
   /media trả 206 TỪNG KHÚC ≤ VR_KHUC_MB (mặc định 8MB), trình duyệt tự xin khúc
   kế tiếp — tua được mà gateway không phình RAM. KHÔNG sửa proxy.
4. THÊM VIDEO = duyệt NAS server-side rồi liên kết — tức thì, không upload, không
   chép byte nào, không trần dung lượng (đường upload trình duyệt đã GỠ 20/08).
   File NAS bị xóa/ghi đè sau khi liên kết → app so vân tay và CẢNH BÁO, không tự sửa.

Chạy (từ ROOT): python -m uvicorn src.main:app --app-dir "apps/video-review" --port 9114
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote

from fastapi import (BackgroundTasks, Depends, FastAPI, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from src import do_thi, don_nas, hau_kiem, kho_video, nap_nas, nhan_xet

_APP_DIR = Path(__file__).resolve().parents[1]
PHIEN_BAN = "0.3.0"
app = FastAPI(title="Video Review v3")
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar UI_FLOW.md mục 2
templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])

# BA bước duyệt (user chốt 20/08). 'can_sua' đã nghỉ hưu — yêu cầu sửa nằm trong
# bình luận; bản ghi cũ đã đưa về dang_duyet ở migration 004.
NHAN_TRANG_THAI = {"dang_duyet": "In review", "da_duyet": "Approved"}
# Nhãn HIỂN THỊ: 'Awaiting review' suy từ "chưa có bình luận nào", không lưu trong sổ
NHAN_HIEN_THI = {"cho_review": "Awaiting review", "dang_review": "In review",
                 "da_duyet": "Approved"}


def _fmt_mmss(v) -> str:
    """72.4 → '01:12' (hiện mốc thời gian trong danh sách bình luận)."""
    try:
        s = int(float(v))
    except (TypeError, ValueError):
        return ""
    return f"{s // 60:02d}:{s % 60:02d}"


templates.env.filters["mmss"] = _fmt_mmss
templates.env.globals["NHAN_TRANG_THAI"] = NHAN_TRANG_THAI
templates.env.globals["NHAN_HIEN_THI"] = NHAN_HIEN_THI


@app.on_event("startup")
def _khoi_tao():
    kho_video.khoi_tao()


# ---------- claims (khuôn to-chuc) ----------

def lay_user(x_remote_user: str = Header(""), x_remote_level: str = Header("0"),
             x_remote_role: str = Header(""), x_remote_dept: str = Header("")) -> dict:
    """User = claims gateway tiêm (an toàn vì app bind 127.0.0.1 — chỉ gateway tới
    được; header giả từ trình duyệt đã bị gateway vứt trước khi tới đây)."""
    if not x_remote_user:
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    try:
        level = int(x_remote_level or 0)
    except ValueError:
        level = 0
    return {"ten": x_remote_user, "level": level, "vai": x_remote_role,
            "bo_phan": unquote(x_remote_dept or "")}


def _cac_khu(x_remote_actions: str) -> set[str]:
    return {m for m in (x_remote_actions or "").split(",") if m}


def khu_cua_toi(user: dict = Depends(lay_user),
                x_remote_actions: str = Header("")) -> dict:
    """User + cờ hành động gateway phát — app CHỈ TIN CỜ, không tự tính quyền."""
    khu = _cac_khu(x_remote_actions)
    return {**user, "co_duyet": "duyet" in khu, "co_xoa": "xoa" in khu}


def yeu_cau_duyet(user: dict = Depends(khu_cua_toi)) -> dict:
    if not user["co_duyet"]:
        raise HTTPException(403, "Đổi trạng thái duyệt dành cho Leader trở lên.")
    return user


def yeu_cau_xoa(user: dict = Depends(khu_cua_toi)) -> dict:
    if not user["co_xoa"]:
        raise HTTPException(403, "Gỡ video dành cho Quản lý trở lên.")
    return user


# ---------- health + điều hướng ----------

@app.get("/health")
async def health():
    return {"trang_thai": "ok", "app": "video-review", "phien_ban": PHIEN_BAN}


@app.get("/api/suc-khoe")
async def api_suc_khoe():
    """Sức khỏe SÂU (B3 giám sát 31/08): `nas` — video KHÔNG nằm trong app,
    gốc NAS rời là thêm/xem chết; `ffprobe` — thiếu chỉ bỏ dò codec (thiết kế
    20/08) → canh_bao, và VR_FFPROBE đang trỏ C:\\OutlierY di sản (xóa ~22/09):
    ngày đó module này tự vàng nhắc chuyển ffmpeg."""
    import os
    import shutil
    from pathlib import Path

    from nen.common import suc_khoe

    def _nas():
        d = os.environ.get("VR_NAS_DIR", "").strip()
        if not d:
            return "canh_bao", "VR_NAS_DIR chưa khai — tính năng NAS đang ẩn"
        if not Path(d).is_dir():
            return "loi", f"gốc NAS {d} không đọc được — thêm/xem video từ NAS chết"
        return "ok", f"gốc NAS đọc được ({d})"

    def _ffprobe():
        p = os.environ.get("VR_FFPROBE", "").strip()
        if p and Path(p).exists():
            return "ok", f"ffprobe tại {p}"
        if shutil.which("ffprobe"):
            return "ok", "ffprobe trong PATH"
        return "canh_bao", ("không thấy ffprobe — bỏ bước dò codec (file H.265 "
                            "phát tiếng-màn-đen sẽ không được cảnh báo); nhớ vụ "
                            "chuyển ffmpeg khỏi C:\\OutlierY trước ~22/09")

    return suc_khoe.bao_cao("video-review", PHIEN_BAN, [
        ("nas", _nas), ("ffprobe", _ffprobe)])


@app.get("/api/kiem/{ma}")
async def api_kiem(ma: str, request: Request):
    """CỬA KIỂM LOGIC (02/09 — "mỗi logic một sơ đồ"): trả SỐ ĐO THẬT của một
    logic nghiệp vụ, CHỈ-ĐỌC 0 quota — hàm thuần + thư mục tạm, không đụng NAS
    thật, không đụng sổ SQLite thật. Chỉ loopback."""
    from src import kiem
    if request.client and request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(404)
    ham = kiem.CAC_MA.get(ma)
    if ham is None:
        raise HTTPException(404, f"không có mã kiểm {ma!r}")
    return ham()


@app.get("/")
async def goc():
    return RedirectResponse("/danh-sach", status_code=303)


# ---------- trang danh sách + upload ----------

@app.get("/danh-sach", response_class=HTMLResponse)
async def danh_sach(request: Request, user: dict = Depends(khu_cua_toi)):
    cac_video = kho_video.danh_sach_video()
    # Trạng thái HIỂN THỊ (user chốt 18/08 — video up lên chưa ai review phải nổi):
    # dang_duyet + CHƯA có bình luận nào = cho_review (Awaiting) · có rồi = dang_review.
    for v in cac_video:
        if v["trang_thai"] == "dang_duyet":
            # 'Awaiting' = CHƯA AI KHÁC người đăng bình luận. Ghi chú của chính người
            # up ("em hết CapCut Pro", "anh xem giúp") KHÔNG phải là review — dùng
            # so_tong ở đây từng làm cờ Awaiting tắt sau 20 giây (sự cố 24/08).
            v["hien_thi"] = "cho_review" if v["so_khac"] == 0 else "dang_review"
        else:
            v["hien_thi"] = v["trang_thai"]
    for v in cac_video:
        # vân tay file gốc: mất file / bị ghi đè đều phải NỔI ngay ở danh sách
        v["tt_file"] = kho_video.tinh_trang_file(v)
        # codec dò lười một lần rồi nhớ (bản ghi cũ chưa có) — file H.265 phải
        # lộ ngay ở danh sách, đừng để người review mở ra mới thấy hình đen
        v["canh_codec"] = kho_video.canh_bao_codec(
            kho_video.bao_dam_codec(v) if v["tt_file"]["co"] else "")
    return templates.TemplateResponse(request, "danh_sach.html", {
        "cac_video": cac_video, "cac_tap": _gom_tap(cac_video), "user": user,
        "nas_bat": nap_nas.nas_dir() is not None})


def _gom_tap(cac_video: list[dict]) -> list[dict]:
    """Gom bản dựng THEO TẬP (user chốt 20/08: mỗi tập đẻ fix lần 1/2/Round 3…
    nên danh sách phình theo số vòng sửa, không theo số tập). Nhóm mở sẵn khi
    còn việc phải làm; tập đã duyệt hết thì gập lại cho gọn."""
    nhom: dict[str, list[dict]] = {}
    for v in cac_video:                      # đã sắp mới nhất trước
        nhom.setdefault(kho_video.ma_tap(v) or "Khác", []).append(v)
    ra = []
    for ma, ds in nhom.items():
        moi = ds[0]
        xong = any(v["trang_thai"] == "da_duyet" for v in ds)
        # khối Feedback để dọn: chỉ bản ghi nằm TRONG <tập>/Feedback mới có; bản ghi
        # đời cũ trỏ thẳng thư mục tập thì KHÔNG (trong đó có bản master của team)
        khoi = next((kho_video.thu_muc_feedback(v) for v in ds
                     if kho_video.thu_muc_feedback(v)), "")
        # Nhãn NHÓM ưu tiên 'Awaiting': còn bản nào chưa ai xem thì cả tập phải kêu,
        # kể cả khi bản mới nhất đã được review (đừng để bản cũ bị bỏ quên lặng lẽ).
        cho = next((v for v in ds if v["hien_thi"] == "cho_review"), None)
        ra.append({
            "ma": ma, "videos": ds, "so": len(ds), "moi_id": moi["id"],
            "hien_thi": (cho or moi)["hien_thi"], "ten_moi": (cho or moi)["ten"],
            "mo": not xong,
            "xong": xong, "khoi_feedback": khoi,
            "don_duoc": xong and bool(khoi),
            "canh": any((not v["tt_file"]["co"]) or v["tt_file"]["doi"]
                        or v["canh_codec"] for v in ds)})
    ra.sort(key=lambda g: -g["moi_id"])
    return ra


# ---------- trang review ----------

def _video_song(ma: str) -> dict:
    video = kho_video.lay_video(ma)
    if video is None or video["trang_thai"] == "da_xoa":
        raise HTTPException(404, "Không có video này.")
    return video


@app.get("/xem/{ma}", response_class=HTMLResponse)
async def xem(request: Request, ma: str, user: dict = Depends(khu_cua_toi)):
    video = _video_song(ma)
    _, pd_nguon = kho_video.phu_de_tim(video)
    cac_nx = nhan_xet.ds_nhan_xet(ma)
    tt_file = kho_video.tinh_trang_file(video)
    canh_codec = kho_video.canh_bao_codec(
        kho_video.bao_dam_codec(video) if tt_file["co"] else "")
    return templates.TemplateResponse(request, "xem.html", {
        "video": video, "user": user,
        "co_phu_de": pd_nguon != "",
        "pd_nguon": pd_nguon,                    # app|nas|kho — NAS thì app không gỡ được
        "tt_file": tt_file, "canh_codec": canh_codec,
        "unc_thu_muc": don_nas.duong_unc(video["duong"].rsplit("/", 1)[0])
                       if video["nguon"] == "nas" else "",
        "cac_nx": cac_nx, "so_do": nhan_xet.so_do_cua(video),
        "cac_bl": kho_video.ds_binh_luan(ma)})   # nhúng vào JS qua |tojson (script-safe)


# ---------- phụ đề (.srt/.vtt — CHỈ CHÍNH CHỦ video gắn/gỡ, user chốt 18/08;
# ai xem được video thì đọc được phụ đề) ----------

def _kiem_phu_de(du_lieu: bytes) -> str:
    if len(du_lieu) > 2 * 1024 * 1024:
        raise HTTPException(413, "File phụ đề quá 2MB.")
    chu = kho_video.doc_phu_de_bytes(du_lieu)
    if "-->" not in chu:
        raise HTTPException(422, "File không giống phụ đề SRT/VTT (thiếu mốc thời gian).")
    return chu


@app.post("/api-vr/phu-de/{ma}")
async def api_phu_de_gan(ma: str, file: UploadFile, user: dict = Depends(lay_user)):
    video = _video_song(ma)
    if user["ten"] != video["nguoi_tao"]:
        raise HTTPException(403, "Chỉ người đăng video được gắn phụ đề.")
    duoi = Path(file.filename or "").suffix.lower()
    if duoi not in kho_video.DUOI_PHU_DE:
        raise HTTPException(422, "Chỉ nhận phụ đề .srt / .vtt.")
    chu = _kiem_phu_de(await file.read())
    kho_video.ghi_phu_de(video, chu, duoi)
    return {"ok": True}


@app.post("/api-vr/phu-de/{ma}/xoa")
async def api_phu_de_xoa(ma: str, user: dict = Depends(lay_user)):
    video = _video_song(ma)
    if user["ten"] != video["nguoi_tao"]:
        raise HTTPException(403, "Chỉ người đăng video được gỡ phụ đề.")
    if not kho_video.xoa_phu_de(video):
        raise HTTPException(409, "Phụ đề này là file .srt nằm cạnh video trên NAS — "
                                 "app chỉ đọc, muốn bỏ thì gỡ file đó trên NAS.")
    return {"ok": True}


@app.get("/api-vr/phu-de/{ma}")
async def api_phu_de_doc(ma: str, user: dict = Depends(lay_user)):
    """Trả WebVTT cho <track> — .srt được chuyển ngầm, .vtt trả nguyên."""
    video = _video_song(ma)
    p = kho_video.duong_phu_de(video)
    if p is None:
        raise HTTPException(404, "Video này chưa có phụ đề.")
    chu = kho_video.srt_sang_vtt(kho_video.doc_phu_de_bytes(p.read_bytes()))
    return Response(chu, media_type="text/vtt; charset=utf-8")


# ---------- phát video (Range từng khúc — xem ghi chú đầu file) ----------

_RANGE_RE = re.compile(r"bytes=(\d+)-(\d*)$")


@app.get("/media/{ma}")
async def media(ma: str, user: dict = Depends(lay_user), range: str = Header("")):
    video = kho_video.lay_video(ma)
    if video is None or video["trang_thai"] == "da_xoa":
        raise HTTPException(404, "Không có video này.")
    duong = kho_video.duong_video(video)
    if duong is None or not duong.is_file():
        raise HTTPException(404, "File gốc không còn ở nơi đã liên kết (NAS).")
    size = duong.stat().st_size
    khuc = int(os.environ.get("VR_KHUC_MB", "8")) * 1024 * 1024

    m = _RANGE_RE.match((range or "").strip())
    if not m:
        # Không Range (nút tải về / curl): trả trọn file. Trình duyệt phát video
        # luôn gửi Range nên đường nóng vẫn là 206 từng khúc phía dưới.
        return Response(duong.read_bytes(), media_type=video["mime"],
                        headers={"Accept-Ranges": "bytes",
                                 "Content-Disposition":
                                     f'inline; filename="{video["ten_file"]}"'})
    dau = int(m.group(1))
    if dau >= size:
        raise HTTPException(416, "Range ngoài file.")
    cuoi = int(m.group(2)) if m.group(2) else size - 1
    cuoi = min(cuoi, size - 1, dau + khuc - 1)
    with open(duong, "rb") as f:
        f.seek(dau)
        du_lieu = f.read(cuoi - dau + 1)
    return Response(du_lieu, status_code=206, media_type=video["mime"],
                    headers={"Accept-Ranges": "bytes",
                             "Content-Range": f"bytes {dau}-{cuoi}/{size}"})


# ---------- thêm video từ NAS (liên kết, không chép — xem src/nap_nas.py) ----------

@app.get("/api-vr/nas")
async def api_nas_liet_ke(duong: str = "", user: dict = Depends(lay_user)):
    try:
        return nap_nas.liet_ke(duong)
    except (FileNotFoundError, PermissionError):
        # ngoài-gốc và không-tồn-tại trả CÙNG 404 — không lộ cây thư mục ngoài gốc
        raise HTTPException(404, "Không có thư mục này.")


@app.post("/api-vr/nas-lien-ket")
async def api_nas_lien_ket(duong: str = Form(...), ten: str = Form(""),
                           user: dict = Depends(khu_cua_toi)):
    """Thêm video = ghi sổ đường file NAS. Không tác vụ nền, không % — tức thì."""
    try:
        ban_ghi = nap_nas.lien_ket(duong, ten, user["ten"], user["bo_phan"])
    except FileExistsError as e:
        raise HTTPException(409, f"File này đã có trong app ({e.args[0]}).")
    except BlockingIOError:
        raise HTTPException(409, "File đang được ghi lên NAS (chép chưa xong). Đợi chép "
                                 "xong hẳn rồi thêm — thêm lúc này thì bản dựng sẽ đứt "
                                 "giữa chừng khi xem.")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except (FileNotFoundError, PermissionError):
        raise HTTPException(404, "Không thấy file trên NAS.")
    return {"ma": ban_ghi["ma"], "hong": ban_ghi.get("hong", ""),
            "canh_codec": kho_video.canh_bao_codec(ban_ghi.get("codec", ""))}


@app.post("/api-vr/quet-hong/{ma}")
async def api_quet_hong(ma: str, user: dict = Depends(khu_cua_toi)):
    """Quét lại file trên NAS xem có đứt/hỏng không (mất vài giây). Ai xem được
    video thì quét được — đây là việc CHỈ ĐỌC, và người phát hiện video chết giữa
    chừng thường chính là reviewer."""
    video = _video_song(ma)
    p = kho_video.duong_video(video)
    if p is None or not p.is_file():
        raise HTTPException(404, "File gốc không còn ở nơi đã liên kết (NAS).")
    from starlette.concurrency import run_in_threadpool
    hong = await run_in_threadpool(kho_video.quet_hong, p)   # ffmpeg: đẩy threadpool
    kho_video.ghi_hong(ma, hong)
    return {"ma": ma, "hong": hong}


@app.post("/api-vr/nhan-ban-hien-tai/{ma}")
async def api_nhan_ban_hien_tai(ma: str, user: dict = Depends(khu_cua_toi)):
    """Nhận file HIỆN TẠI trên NAS làm đúng bản đang review — xóa cảnh báo 'file
    changed'. Người ĐĂNG video hoặc Leader+ quyết, vì chỉ họ biết bản mới có đúng
    là bản mình định cho review hay không."""
    video = _video_song(ma)
    if user["ten"] != video["nguoi_tao"] and not user["co_duyet"]:
        raise HTTPException(403, "Chỉ người đăng video hoặc Leader trở lên xác nhận được.")
    try:
        return kho_video.cap_nhat_van_tay(ma)
    except FileNotFoundError:
        raise HTTPException(404, "File gốc không còn ở nơi đã liên kết (NAS).")


# ---------- dọn thư mục NAS sau khi review xong (xem src/don_nas.py) ----------

@app.get("/api-vr/nas-thu-muc/{ma}")
async def api_nas_thu_muc(ma: str, user: dict = Depends(khu_cua_toi)):
    """Mọi file trong thư mục chứa bản dựng này + đường UNC để mở bằng Explorer."""
    video = _video_song(ma)
    if video["nguon"] != "nas":
        raise HTTPException(404, "Bản ghi này không trỏ tới NAS.")
    try:
        du = don_nas.liet_ke_thu_muc(video["duong"])
    except (FileNotFoundError, PermissionError):
        raise HTTPException(404, "Không đọc được thư mục trên NAS.")
    return {**du, "co_quyen_xoa": user["co_xoa"]}


@app.post("/api-vr/nas-xoa-file")
async def api_nas_xoa_file(duong: str = Form(...), xac_nhan: str = Form(...),
                           user: dict = Depends(yeu_cau_xoa)):
    """XÓA THẬT file trên NAS — ngoại lệ có kiểm soát, 6 chốt chặn ở don_nas."""
    try:
        return don_nas.xoa_file(duong, xac_nhan, user["ten"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (FileNotFoundError, OSError):
        raise HTTPException(404, "Không thấy file trên NAS (có thể vừa bị xóa).")


@app.post("/api-vr/xoa-cung-tap")
async def api_xoa_cung_tap(ma_tap: str = Form(...), xac_nhan: str = Form(...),
                           xoa_file: str = Form(""), user: dict = Depends(yeu_cau_xoa)):
    """XÓA CỨNG cả tập đã Approved: bản ghi + bình luận biến mất khỏi sổ (khác gỡ
    mềm), tùy chọn dọn luôn khối Feedback trên NAS. Nút nằm ở nhóm đã nghiệm thu."""
    try:
        return don_nas.xoa_cung_tap(ma_tap, xac_nhan, user["ten"],
                                    xoa_file_nas=xoa_file in ("1", "true", "on"))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (FileNotFoundError, KeyError):
        raise HTTPException(404, "Không thấy tập này trong sổ.")


@app.post("/api-vr/nas-xoa-feedback")
async def api_nas_xoa_feedback(duong: str = Form(...), ma_tap: str = Form(...),
                               user: dict = Depends(yeu_cau_xoa)):
    """Dọn CẢ KHỐI <tập>/Feedback sau khi tập đã Approved (quy trình user 20/08)."""
    try:
        return don_nas.xoa_khoi_feedback(duong, ma_tap, user["ten"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (FileNotFoundError, OSError):
        raise HTTPException(404, "Không thấy khối Feedback này trên NAS.")


# ---------- luồng 2: hậu kiểm sau khi đăng (xem src/hau_kiem.py) ----------

@app.get("/tap/{ma_tap}", response_class=HTMLResponse)
async def trang_tap(request: Request, ma_tap: str, user: dict = Depends(khu_cua_toi)):
    """Thư mục tập — đối tượng cuối cùng: bản duyệt 10 phút + bản full đã đăng."""
    tap = kho_video.mot_tap(ma_tap)
    if tap is None:
        raise HTTPException(404, "Không có tập này.")
    return templates.TemplateResponse(request, "tap.html", {
        "tap": tap, "user": user, "giu_chan": hau_kiem.lay_giu_chan(ma_tap)})


@app.get("/hau-kiem/{ma_tap}", response_class=HTMLResponse)
async def trang_hau_kiem(request: Request, ma_tap: str, user: dict = Depends(khu_cua_toi)):
    """Luồng 2 — cùng khung 2 cột: trái video + đồ thị, phải chẩn đoán."""
    tap = kho_video.mot_tap(ma_tap)
    if tap is None or tap.get("full") is None:
        raise HTTPException(404, "Tập này chưa có bản full.")
    full = tap["full"]
    gc = hau_kiem.lay_giu_chan(ma_tap)
    return templates.TemplateResponse(request, "hau_kiem.html", {
        "tap": tap, "video": full, "user": user, "giu_chan": gc,
        "cong": gc["cong"] if gc else [],
        "thoi_luong": hau_kiem._thoi_luong_full(full),
        "cac_nx": nhan_xet.ds_nhan_xet(full["ma"]),
        "ket_luan_viec": (hau_kiem.chan_doan_tap(ma_tap).get("ket_luan", {}).get("viec", [])
                          if gc else [])})


@app.post("/api-vr/gan-tap")
async def api_gan_tap(ma: str = Form(...), ma_tap: str = Form(...),
                      loai: str = Form("duyet"), user: dict = Depends(khu_cua_toi)):
    try:
        kho_video.gan_tap(ma, ma_tap, loai)
    except KeyError:
        raise HTTPException(404, "Không có video này.")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}


@app.post("/api-vr/gan-youtube")
async def api_gan_youtube(ma: str = Form(...), yt: str = Form(...),
                          dang_luc: str = Form(""), user: dict = Depends(khu_cua_toi)):
    yt_id = yt.strip().rsplit("/", 1)[-1].split("?v=")[-1].split("&")[0]
    try:
        kho_video.gan_youtube(ma, yt_id, dang_luc)
    except KeyError:
        raise HTTPException(404, "Không có video này.")
    return {"ok": True, "yt_id": yt_id}


@app.post("/api-vr/giu-chan/{ma_tap}")
async def api_giu_chan(ma_tap: str, anh: UploadFile, hook_30: float = Form(...),
                       avd_giay: float = Form(...), giu_tb: float = Form(...),
                       user: dict = Depends(khu_cua_toi)):
    """Dán ảnh đồ thị Studio + 3 số đọc trên màn hình. Ảnh đọc lệch số thật quá
    ngưỡng thì TỪ CHỐI, đòi chụp lại — thà không có còn hơn có số sai."""
    import tempfile
    from starlette.concurrency import run_in_threadpool
    tap = kho_video.mot_tap(ma_tap)
    if tap is None or tap.get("full") is None:
        raise HTTPException(404, "Tập này chưa có bản full để gắn số liệu.")
    full = tap["full"]
    thoi_luong = hau_kiem._thoi_luong_full(full)
    if thoi_luong <= 0:
        raise HTTPException(422, "Chưa biết thời lượng bản full — chạy đánh giá trước.")
    du = await anh.read()
    if len(du) > 8 * 1024 * 1024:
        raise HTTPException(413, "Ảnh quá 8MB.")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(du)
        tam = Path(f.name)
    try:
        cong = await run_in_threadpool(do_thi.doc_duong_cong, tam)
    finally:
        tam.unlink(missing_ok=True)
    if cong is None:
        raise HTTPException(422, "Không tìm thấy đường cong trong ảnh — chụp lại "
                                 "phần biểu đồ giữ chân cho rõ, đừng cắt cúp.")
    neo = do_thi.neo_bang_so_that(cong, hook_30, thoi_luong)
    if not neo["dat"]:
        raise HTTPException(422, f"Ảnh không khớp số anh nhập: {neo['ly_do']}. "
                                 f"Chụp lại rõ hơn hoặc kiểm lại 3 số.")
    hau_kiem.luu_giu_chan(ma_tap, full["ma"], hook_30, avd_giay, giu_tb,
                          neo["cong"], anh.filename or "", neo.get("lech"), user["ten"])
    return {"ok": True, "so_diem": len(neo["cong"]), "lech_neo": round(neo.get("lech", 0), 2)}


@app.post("/api-vr/hau-kiem/{ma_tap}")
async def api_hau_kiem(ma_tap: str, user: dict = Depends(khu_cua_toi)):
    """Sinh chẩn đoán cho tập: chỗ tụt + mạch dựng + trích kịch bản."""
    kq = hau_kiem.chan_doan_tap(ma_tap)
    if not kq.get("co"):
        raise HTTPException(404, "Chưa đủ dữ liệu — cần bản full và số liệu giữ chân.")
    nhan_xet.luu_nhan_xet(kq["video"]["ma"], kq["cac_tut"])
    return {"ok": True, "so": len(kq["cac_tut"]), "ket_luan": kq["ket_luan"]}


# ---------- nhận xét của MÁY (xem src/nhan_xet.py) ----------

@app.post("/api-vr/danh-gia/{ma}")
async def api_danh_gia(ma: str, bg: BackgroundTasks, user: dict = Depends(khu_cua_toi)):
    """Đo mạch dựng rồi sinh nhận xét. Chạy NỀN vì video dài mất vài phút."""
    _video_song(ma)
    tid = nhan_xet.tao_tac_vu(ma, user["ten"])
    bg.add_task(nhan_xet.chay_danh_gia, tid)      # hàm SYNC → threadpool
    return {"task_id": tid}


@app.get("/api-vr/danh-gia/{tid}")
async def api_danh_gia_trang_thai(tid: str, user: dict = Depends(lay_user)):
    tt = nhan_xet.trang_thai(tid, user["ten"])
    if tt is None:
        raise HTTPException(404, "Không có tác vụ này.")
    return tt


@app.get("/api-vr/nhan-xet/{ma}")
async def api_ds_nhan_xet(ma: str, user: dict = Depends(lay_user)):
    _video_song(ma)
    return nhan_xet.ds_nhan_xet(ma)


@app.post("/api-vr/nhan-xet/{nx_id}/da-doc")
async def api_nx_da_doc(nx_id: int, user: dict = Depends(khu_cua_toi)):
    try:
        nhan_xet.danh_dau_da_doc(nx_id)
    except KeyError:
        raise HTTPException(404, "Không có nhận xét này.")
    return {"ok": True}


@app.post("/api-vr/nhan-xet/{nx_id}/phan")
async def api_nx_phan(nx_id: int, phan: str = Form(...),
                      user: dict = Depends(khu_cua_toi)):
    """Người sửa phán quyết của máy — giữ cả phán gốc để sau đối chiếu."""
    try:
        nhan_xet.sua_phan(nx_id, phan)
    except KeyError:
        raise HTTPException(404, "Không có nhận xét này.")
    return {"ok": True}


# ---------- API bình luận + trạng thái ----------

@app.post("/api-vr/binh-luan")
async def api_them_binh_luan(request: Request, user: dict = Depends(khu_cua_toi)):
    du = await request.json()
    try:
        bl = kho_video.them_binh_luan(
            du.get("video_ma", ""), user["ten"], du.get("noi_dung", ""),
            ts_giay=du.get("ts_giay"),
            ve_json=json.dumps(du["ve"], ensure_ascii=False) if du.get("ve") else None)
    except KeyError:
        raise HTTPException(404, "Không có video này.")
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(422, str(e))
    return bl


@app.get("/api-vr/binh-luan/{ma}")
async def api_ds_binh_luan(ma: str, user: dict = Depends(lay_user)):
    if kho_video.lay_video(ma) is None:
        raise HTTPException(404, "Không có video này.")
    return kho_video.ds_binh_luan(ma)


def _thao_tac_bl(ham, bl_id: int, user: dict):
    try:
        ham(bl_id, user["ten"], user["co_duyet"])
    except KeyError:
        raise HTTPException(404, "Không có bình luận này.")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    return {"ok": True}


@app.post("/api-vr/binh-luan/{bl_id}/giai")
async def api_giai(bl_id: int, user: dict = Depends(khu_cua_toi)):
    return _thao_tac_bl(kho_video.giai_binh_luan, bl_id, user)


@app.post("/api-vr/binh-luan/{bl_id}/mo-lai")
async def api_mo_lai(bl_id: int, user: dict = Depends(khu_cua_toi)):
    return _thao_tac_bl(kho_video.mo_lai_binh_luan, bl_id, user)


@app.post("/api-vr/binh-luan/{bl_id}/xoa")
async def api_xoa_bl(bl_id: int, user: dict = Depends(khu_cua_toi)):
    return _thao_tac_bl(kho_video.xoa_binh_luan, bl_id, user)


@app.post("/api-vr/trang-thai")
async def api_trang_thai(ma: str = Form(...), trang_thai: str = Form(...),
                         user: dict = Depends(yeu_cau_duyet)):
    if trang_thai not in NHAN_TRANG_THAI:
        raise HTTPException(422, "Trạng thái lạ.")
    try:
        kho_video.doi_trang_thai(ma, trang_thai)
    except KeyError:
        raise HTTPException(404, "Không có video này.")
    return {"ok": True, "trang_thai": trang_thai}


@app.post("/api-vr/xoa-video")
async def api_xoa_video(ma: str = Form(...), user: dict = Depends(yeu_cau_xoa)):
    try:
        kho_video.doi_trang_thai(ma, "da_xoa")   # GỠ MỀM — file gốc trên NAS KHÔNG bị đụng
    except KeyError:
        raise HTTPException(404, "Không có video này.")
    return {"ok": True}
