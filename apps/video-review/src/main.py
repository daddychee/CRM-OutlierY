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

from fastapi import (Depends, FastAPI, Form, Header, HTTPException, Request,
                     UploadFile)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from src import don_nas, kho_video, nap_nas

_APP_DIR = Path(__file__).resolve().parents[1]
PHIEN_BAN = "0.2.0"
app = FastAPI(title="Video Review v3")
from nen.common.sidebar import ctx_sidebar  # noqa: E402 — cờ sidebar UI_FLOW.md mục 2
templates = Jinja2Templates(directory=str(_APP_DIR / "src" / "templates"),
                            context_processors=[ctx_sidebar])

NHAN_TRANG_THAI = {"dang_duyet": "In review", "can_sua": "Changes requested",
                   "da_duyet": "Approved"}
# Nhãn trạng thái HIỂN THỊ trang danh sách (cho_review/dang_review suy từ bình luận)
NHAN_HIEN_THI = {"cho_review": "Awaiting review", "dang_review": "In review",
                 "can_sua": "Changes requested", "da_duyet": "Approved"}


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
            v["hien_thi"] = "cho_review" if v["so_tong"] == 0 else "dang_review"
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
        ra.append({
            "ma": ma, "videos": ds, "so": len(ds), "moi_id": moi["id"],
            "hien_thi": moi["hien_thi"], "ten_moi": moi["ten"],
            "mo": any(v["hien_thi"] != "da_duyet" for v in ds),
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
    except ValueError as e:
        raise HTTPException(422, str(e))
    except (FileNotFoundError, PermissionError):
        raise HTTPException(404, "Không thấy file trên NAS.")
    return {"ma": ban_ghi["ma"],
            "canh_codec": kho_video.canh_bao_codec(ban_ghi.get("codec", ""))}


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
