"""Acquisition YouTube cho module extract (supervisor.md §2b) — bước "LẤY nội dung dài".

Mỏng có chủ đích:
- lay_transcript(): gọi youtube-transcript-api (I/O MẠNG — KHÔNG unit test; YouTube có thể CHẶN
  IP máy chủ, xác minh trên máy thật). Transcript = lời nói = nội dung (không tải video).
- ghep_transcript() + video_id_tu_url(): THUẦN, tất định, có test.

Ra text sạch rồi đưa vào de_xuat_trich (trich_doan.py). CHƯA có yt-dlp liệt kê cả kênh —
bắt đầu bằng MỘT video (đủ để chạy end-to-end); quét cả kênh là bước sau.
"""

import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.trich_doan import de_xuat_trich


def video_id_tu_url(url: str) -> str:
    """Lấy video id từ URL YouTube (watch?v= / youtu.be/ / shorts/ / embed/). Đã là id trần → giữ nguyên."""
    url = url.strip()
    p = urlparse(url)
    if p.query:
        v = parse_qs(p.query).get("v")
        if v:
            return v[0]
    if p.netloc and p.path:          # youtu.be/ID, /shorts/ID, /embed/ID → id là path cuối
        return p.path.rstrip("/").split("/")[-1]
    return url                       # id trần


def ghep_transcript(segments: list[dict]) -> str:
    """Ghép các segment {text,...} → 1 text sạch cho de_xuat_trich: bỏ nhãn không-lời
    ([Music]/[Âm nhạc]/[Applause]...), gộp khoảng trắng."""
    text = " ".join(s.get("text", "") for s in segments)
    text = re.sub(r"\[[^\]]*\]", " ", text)      # bỏ nhãn trong ngoặc vuông (không phải lời nói)
    return re.sub(r"\s+", " ", text).strip()


def duong_dan_cookies() -> Path:
    """Nơi lưu cookies YouTube. .env YOUTUBE_COOKIES (đường dẫn tùy chỉnh) thắng; mặc định
    kho-tai-lieu/youtube_cookies.txt — thư mục đã gitignore (2 lớp: kho-tai-lieu/ +
    *cookies*.txt) và conftest cách ly mỗi test một kho tạm riêng."""
    tuy_chinh = os.getenv("YOUTUBE_COOKIES", "").strip()
    if tuy_chinh:
        return Path(tuy_chinh)
    return Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu")) / "youtube_cookies.txt"


def _dem_dong_cookie(noi_dung: str) -> int:
    """Đếm dòng cookie youtube.com THẬT (bỏ comment/dòng trống)."""
    return sum(1 for d in noi_dung.splitlines()
               if "youtube.com" in d and d.strip() and not d.lstrip().startswith("#"))


def luu_cookies(noi_dung: str) -> int:
    """Ghi cookies.txt (Netscape) Owner dán từ UI — nguyên tử (file tạm + os.replace), KHÔNG
    bao giờ log nội dung (cookie phiên = nhạy như mật khẩu). Không có dòng youtube.com nào →
    ValueError (dán nhầm file). Trả số dòng cookie youtube để hiện trạng thái."""
    so = _dem_dong_cookie(noi_dung)
    if not so:
        raise ValueError("Không thấy dòng cookie youtube.com nào — có đúng file cookies.txt "
                         "xuất từ youtube.com không?")
    path = duong_dan_cookies()
    path.parent.mkdir(parents=True, exist_ok=True)
    tam = path.with_name(path.name + ".tmp")
    tam.write_text(noi_dung, encoding="utf-8")
    os.replace(tam, path)
    return so


def xoa_cookies() -> None:
    duong_dan_cookies().unlink(missing_ok=True)


def trang_thai_cookies() -> dict:
    """Trạng thái cho UI: có file không + mấy dòng cookie youtube. CHỈ trạng thái —
    nội dung cookie không bao giờ gửi ra client (write-only như API key)."""
    path = duong_dan_cookies()
    if not path.is_file():
        return {"co": False, "so_dong": 0}
    try:
        return {"co": True, "so_dong": _dem_dong_cookie(path.read_text(encoding="utf-8"))}
    except OSError:
        return {"co": False, "so_dong": 0}


def _http_client_cookies():
    """Session requests nạp cookies YouTube (Netscape cookies.txt — dán qua UI Nguồn ngoài
    hoặc xuất bằng extension 'Get cookies.txt LOCALLY'). Request có phiên ĐĂNG NHẬP thường
    ÍT bị YouTube chặn hơn ẩn danh (nới rate/bot-detection). Chưa có file → None (ẩn danh
    như cũ)."""
    path = duong_dan_cookies()
    if not path.is_file():
        return None
    import http.cookiejar
    import requests
    from requests.cookies import RequestsCookieJar, merge_cookies
    jar = http.cookiejar.MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)   # cookie hết hạn/không-lưu vẫn nạp
    s = requests.Session()
    s.cookies = merge_cookies(RequestsCookieJar(), jar)
    return s


def lay_transcript(video_id: str, ngon_ngu=("vi", "en")) -> list[dict]:
    """Lấy transcript 1 video → list {text,start,duration}. Ưu tiên tiếng Việt rồi tiếng Anh.
    Dùng cookies đăng nhập nếu .env YOUTUBE_COOKIES có (giảm bị chặn IP). I/O MẠNG — không unit
    test; lỗi/không có phụ đề/bị chặn IP → ném lỗi của lib (người gọi bắt)."""
    from youtube_transcript_api import YouTubeTranscriptApi  # import tại chỗ — pure funcs không cần lib
    api = YouTubeTranscriptApi(http_client=_http_client_cookies())
    return api.fetch(video_id, languages=list(ngon_ngu)).to_raw_data()


def transcript_tu_url(url: str, ngon_ngu=("vi", "en")) -> tuple[str, str]:
    """URL → (video_id, text transcript sạch). Tách riêng để route phân biệt LỖI PHỤ ĐỀ
    (YouTube) với LỖI MODEL (writer) — từng bị gộp làm một nên báo nhầm 'không lấy được
    phụ đề' khi thật ra Z.ai hết tiền (kiểm chứng 25/07)."""
    vid = video_id_tu_url(url)
    return vid, ghep_transcript(lay_transcript(vid, ngon_ngu))


def trich_tu_video(url: str, writer, so_doan: int = 8, ngon_ngu=("vi", "en")) -> dict:
    """URL 1 video YouTube → đề xuất đoạn NGUYÊN VĂN (nối acquisition + extract). Trả
    {video_id, cac_doan:[{trich,dich,ly_do}]}. de_xuat_trich giữ van verbatim (đoạn bịa bị loại)."""
    vid, text = transcript_tu_url(url, ngon_ngu)
    return {"video_id": vid,
            "cac_doan": de_xuat_trich(text, writer, so_doan, nguon=f"YouTube {vid}")}


def _noi_dung_tai_lieu(nguon_ten: str, url: str, cac_doan: list[dict]) -> str:
    """Dựng nội dung file từ các đoạn ĐÃ CHỐT. Nội dung = đoạn NGUYÊN VĂN (nguồn sự thật, được
    embed + trích khi trả lời) + dòng '🇻🇳 Dịch tham khảo' GẮN NHÃN (nếu có) — dịch giúp câu hỏi
    tiếng Việt khớp tốt hơn, KHÔNG thay lời gốc. ly_do (nhận xét LLM) KHÔNG trộn vào — vào keywords."""
    dau = f"# Nguồn tham khảo: {nguon_ten}\n# Video: {url}\n\n"
    khoi = []
    for d in cac_doan:
        phan = d["trich"]
        if d.get("dich"):
            phan += f"\n(🇻🇳 Dịch tham khảo: {d['dich']})"
        khoi.append(phan)
    return dau + "\n\n".join(khoi)


def nap_doan_video(video_id: str, url: str, nguon_ten: str, cac_doan: list[dict],
                   department: str, access_level: str, min_level: int, client,
                   kho: Path | None = None, van_ban: str = "",
                   nguoi_nhap: str = "", tu_khoa: str = "") -> dict:
    """Nạp các đoạn ĐÃ CHỐT thành 1 tài liệu tầng ngoai. doc_code ỔN ĐỊNH `YT-<videoid>`
    + file đường dẫn cố định → curate lại cùng video là GHI ĐÈ (cap_nhat_noi_dung xóa chunk cũ
    rồi nạp lại, chống mồ côi; create/update cùng một đường). Ghi file nguyên tử; chỉ thêm dòng
    catalog khi doc_code CHƯA có. Import app tại chỗ — tránh vòng import."""
    from src.main import DEPT_FOLDER, doc_catalog, ghi_catalog
    from datetime import date

    kho = kho or Path(os.getenv("KHO_TAI_LIEU", "kho-tai-lieu"))
    doc_code = f"YT-{video_id}"
    ngan = DEPT_FOLDER.get(department, "00_Chung")
    (kho / ngan).mkdir(parents=True, exist_ok=True)
    file_path = kho / ngan / f"{doc_code}_YouTube.md"        # cố định → ghi đè khi curate lại
    tam = file_path.with_name(file_path.name + ".tmp")
    tam.write_text(_noi_dung_tai_lieu(nguon_ten, url, cac_doan), encoding="utf-8")
    os.replace(tam, file_path)
    if van_ban.strip():
        # VĂN BẢN GỐC (transcript) lưu KÈM — không vào catalog/Qdrant, chỉ làm NGỮ CẢNH khi
        # phân tích lại (06/08: bản lesson-learned cần đọc cả transcript mới có đầu có cuối)
        ban_goc = kho / ngan / f"{doc_code}_transcript.txt"
        tam2 = ban_goc.with_name(ban_goc.name + ".tmp")
        tam2.write_text(van_ban, encoding="utf-8")
        os.replace(tam2, ban_goc)

    # 06/08 user chốt VAI TỪNG TRƯỜNG metadata: owner (Phụ trách) = NGƯỜI BẤM DUYỆT — nguon_ten
    # chỉ nói video ĐẾN TỪ ĐÂU, không phải ai nhập; keywords = TỪ KHÓA THẬT người chốt ở màn
    # duyệt (trước đây đổ nguyên các câu ly_do vào — thành "từ khóa" dài cả đoạn tóm tắt).
    metadata = {"title": f"{nguon_ten} — YouTube {video_id}", "keywords": tu_khoa.strip(),
                "owner": (nguoi_nhap or "").strip() or nguon_ten, "version": "v1",
                "department": department,
                "doc_type": "Khác", "effective_status": "Còn hiệu lực",
                "access_level": access_level, "min_level": int(min_level), "doc_code": doc_code,
                "import_date": date.today().isoformat(), "original_filename": file_path.name,
                "tang_nguon": "ngoai", "nguon_ten": nguon_ten}
    ket = client.cap_nhat_noi_dung(str(file_path), metadata)  # create-or-update, chống mồ côi
    if not any(r["Mã tài liệu"] == doc_code for r in doc_catalog(kho)):
        ghi_catalog(kho, [doc_code, metadata["import_date"], metadata["title"], department,
                          "Khác", "Còn hiệu lực", "v1", access_level, int(min_level),
                          metadata["keywords"], metadata["owner"], file_path.name, ngan,
                          "false", doc_code, "", "ngoai", nguon_ten])
    return {"doc_code": doc_code, "so_doan": len(cac_doan), "so_chunk": ket["so_moi"]}
