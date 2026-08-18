# -*- coding: utf-8 -*-
"""VIDEO REVIEW (v3, :9114) — feedback video kiểu Frame.io, app nghiệp vụ MỚI.

Nghiệp vụ: team upload bản dựng video → người khác xem, BÌNH LUẬN GẮN MỐC THỜI GIAN
(bấm bình luận là tua tới đúng giây) + VẼ CHÚ THÍCH trên khung hình → trạng thái duyệt
(In review / Changes requested / Approved). Đúng khuôn hợp đồng app (theo to-chuc):

1. AUTH: không tự giữ user — claims X-Remote-User/Level/Role/Dept từ gateway; gate
   tính năng bằng CỜ X-Remote-Actions (Permissions v2, fail-closed):
   'duyet' = đổi trạng thái video (mặc định Leader+) · 'xoa' = gỡ video (Manager+).
   Xem/bình luận/upload = mọi người có claims ('vao' min_level 1).
2. DỮ LIỆU (Luật 6): sổ SQLite data/video-review/db + file video
   data/video-review/kho/<năm>/<tháng>/ (Luật 5). Xóa = GỠ MỀM, file giữ nguyên.
3. VIDEO QUA PROXY: proxy gateway đọc TRỌN body phản hồi vào RAM (trừ SSE) →
   /media trả 206 TỪNG KHÚC ≤ VR_KHUC_MB (mặc định 8MB), trình duyệt tự xin khúc
   kế tiếp — tua được mà gateway không phình RAM. KHÔNG sửa proxy.
4. Upload: đọc từng khúc + đếm dung lượng (trần VR_MAX_MB, mặc định 2048), ghi file
   tạm rồi os.replace (nguyên tử). LƯU Ý đã biết: gateway buffer body request vào
   RAM → file quá lớn vẫn nặng RAM ở proxy; trần 2GB là chấp nhận được trên LAN,
   nâng nữa phải dạy proxy stream request (việc treo, ghi CLAUDE.md app).

Chạy (từ ROOT): python -m uvicorn src.main:app --app-dir "apps/video-review" --port 9114
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote

from fastapi import (BackgroundTasks, Depends, FastAPI, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from src import kho_video, nap_nas, upload_khuc

_APP_DIR = Path(__file__).resolve().parents[1]
PHIEN_BAN = "0.1.0"
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
    return templates.TemplateResponse(request, "danh_sach.html", {
        "cac_video": cac_video, "user": user,
        "max_gb": int(os.environ.get("VR_MAX_MB", "20480")) // 1024,
        "nas_bat": nap_nas.nas_dir() is not None,
        "nas_max_gb": int(os.environ.get("VR_NAS_MAX_MB", "20480")) // 1024})


def _luu_file_tai_len(f: UploadFile, dich: Path, tran_bytes: int) -> int:
    """Chép upload TỪNG KHÚC vào file tạm cùng thư mục rồi os.replace (nguyên tử);
    vượt trần → dọn file tạm + 413. Trả tổng byte. Hàm SYNC — route đẩy threadpool."""
    dich.parent.mkdir(parents=True, exist_ok=True)
    tong = 0
    fd, tam = tempfile.mkstemp(dir=dich.parent, suffix=".tam")
    try:
        with os.fdopen(fd, "wb") as ra:
            while True:
                khuc = f.file.read(1024 * 1024)
                if not khuc:
                    break
                tong += len(khuc)
                if tong > tran_bytes:
                    raise HTTPException(413, f"File quá {tran_bytes // (1024*1024)}MB.")
                ra.write(khuc)
        os.replace(tam, dich)
    except BaseException:
        try:
            os.unlink(tam)
        except OSError:
            pass
        raise
    return tong


@app.post("/upload-video")
async def upload_video(request: Request, file: UploadFile,
                       ten: str = Form(""), phu_de: UploadFile | None = None,
                       user: dict = Depends(khu_cua_toi)):
    """Đường form MỘT PHÁT — chỉ còn là fallback khi JS chết. Trần RIÊNG
    VR_MAX_FORM_MB (2GB): cả file đi một request nên proxy buffer trọn vào RAM —
    file lớn phải đi đường chunked /api-vr/upload-* (JS tự dùng)."""
    from starlette.concurrency import run_in_threadpool
    duoi = Path(file.filename or "").suffix.lower()
    if duoi not in kho_video.DUOI_CHO_PHEP:
        raise HTTPException(422, "Chỉ nhận video mp4 / webm / mov / m4v.")
    ten = (ten or "").strip() or Path(file.filename or "video").stem
    tran = int(os.environ.get("VR_MAX_FORM_MB", "2048")) * 1024 * 1024
    # phụ đề tùy chọn: kiểm TRƯỚC khi ghi sổ video — file hỏng thì 422 ngay,
    # không để lại video thiếu phụ đề mà user tưởng đã gắn
    chu_phu_de, duoi_phu_de = None, None
    if phu_de is not None and phu_de.filename:
        duoi_phu_de = Path(phu_de.filename).suffix.lower()
        if duoi_phu_de not in kho_video.DUOI_PHU_DE:
            raise HTTPException(422, "Chỉ nhận phụ đề .srt / .vtt.")
        chu_phu_de = _kiem_phu_de(await phu_de.read())
    ban_ghi = kho_video.them_video(ten, duoi, user["ten"], user["bo_phan"], 0)
    tong = await run_in_threadpool(_luu_file_tai_len, file,
                                   ban_ghi["duong_tuyet_doi"], tran)
    # cập nhật dung lượng thật sau khi chép xong
    conn = kho_video.ket_noi()
    try:
        conn.execute("UPDATE video SET kich_thuoc=? WHERE ma=?", (tong, ban_ghi["ma"]))
        conn.commit()
    finally:
        conn.close()
    if chu_phu_de is not None:
        kho_video.ghi_phu_de({"duong": ban_ghi["duong"]}, chu_phu_de, duoi_phu_de)
    return RedirectResponse(f"/xem/{ban_ghi['ma']}", status_code=303)


# ---------- trang review ----------

def _video_song(ma: str) -> dict:
    video = kho_video.lay_video(ma)
    if video is None or video["trang_thai"] == "da_xoa":
        raise HTTPException(404, "Không có video này.")
    return video


@app.get("/xem/{ma}", response_class=HTMLResponse)
async def xem(request: Request, ma: str, user: dict = Depends(khu_cua_toi)):
    video = _video_song(ma)
    return templates.TemplateResponse(request, "xem.html", {
        "video": video, "user": user,
        "co_phu_de": kho_video.duong_phu_de(video) is not None,
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
    kho_video.xoa_phu_de(video)
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
    duong = kho_video.kho_dir() / video["duong"]
    if not duong.is_file():
        raise HTTPException(404, "File video không còn trong kho.")
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


# ---------- upload TỪNG KHÚC (file 2-10GB — xem src/upload_khuc.py) ----------

@app.post("/api-vr/upload-bat-dau")
async def api_up_bat_dau(ten_file: str = Form(...), kich_thuoc: int = Form(...),
                         ten: str = Form(""), user: dict = Depends(khu_cua_toi)):
    try:
        pid = upload_khuc.bat_dau(ten_file, kich_thuoc, ten, user["ten"], user["bo_phan"])
    except OverflowError as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"phien": pid, "khuc_mb": int(os.environ.get("VR_KHUC_UP_MB", "64"))}


@app.post("/api-vr/upload-khuc/{pid}")
async def api_up_khuc(pid: str, request: Request, offset: int,
                      user: dict = Depends(lay_user)):
    from starlette.concurrency import run_in_threadpool
    du_lieu = await request.body()
    try:
        da_nhan = await run_in_threadpool(upload_khuc.ghi_khuc, pid, user["ten"],
                                          offset, du_lieu)
    except KeyError:
        raise HTTPException(404, "Không có phiên upload này.")
    except OverflowError as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"da_nhan": da_nhan}


@app.post("/api-vr/upload-xong/{pid}")
async def api_up_xong(pid: str, user: dict = Depends(lay_user)):
    try:
        ban_ghi = upload_khuc.hoan_tat(pid, user["ten"])
    except KeyError:
        raise HTTPException(404, "Không có phiên upload này.")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ma": ban_ghi["ma"]}


@app.post("/api-vr/upload-huy/{pid}")
async def api_up_huy(pid: str, user: dict = Depends(lay_user)):
    upload_khuc.huy(pid, user["ten"])
    return {"ok": True}


# ---------- nạp từ NAS (đường file lớn — xem src/nap_nas.py) ----------

@app.get("/api-vr/nas")
async def api_nas_liet_ke(duong: str = "", user: dict = Depends(lay_user)):
    try:
        return nap_nas.liet_ke(duong)
    except (FileNotFoundError, PermissionError):
        # ngoài-root và không-tồn-tại trả CÙNG 404 — không lộ cây thư mục ngoài root
        raise HTTPException(404, "Không có thư mục này.")


@app.post("/api-vr/nas-nap")
async def api_nas_nap(bg: BackgroundTasks, duong: str = Form(...), ten: str = Form(""),
                      user: dict = Depends(khu_cua_toi)):
    try:
        tid = nap_nas.tao_tac_vu(duong, ten.strip(), user["ten"], user["bo_phan"])
    except OverflowError as e:
        raise HTTPException(413, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except (FileNotFoundError, PermissionError):
        raise HTTPException(404, "Không thấy file trên NAS.")
    bg.add_task(nap_nas.chay_nap, tid)          # hàm SYNC → threadpool, không khóa loop
    return {"task_id": tid}


@app.get("/api-vr/nas-tien-do/{tid}")
async def api_nas_tien_do(tid: str, user: dict = Depends(lay_user)):
    tt = nap_nas.trang_thai(tid, user["ten"])
    if tt is None:
        raise HTTPException(404, "Không có tác vụ này.")
    return tt


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
        kho_video.doi_trang_thai(ma, "da_xoa")   # GỠ MỀM — file giữ nguyên trong kho
    except KeyError:
        raise HTTPException(404, "Không có video này.")
    return {"ok": True}
