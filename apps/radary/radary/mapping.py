# -*- coding: utf-8 -*-
"""MAPPING — ghep CAU (discovery) voi CUNG (kho video RadarY) thanh ban do 4 o.

Ly do ton tai (do that 21/08/2026 tren radary.db): CUNG THAP co HAI NGHIA TRAI NGUOC
  - `tuvalu`          14 video · view trung vi   781  -> it nguoi lam VI it nguoi xem
  - `why do people…`   4 video ·  2 kenh          -> CHUA AI LAM
Nhin rieng ve cung thi hai ca nay giong het nhau. Chi khi ghep voi cau moi phan biet
duoc — do la toan bo gia tri cua module nay.

VAN CHONG BIA:
  - KHONG diem tong. Hai truc de rieng, moi truc ghi ro do bang gi.
  - KHONG nguong cung ("cau >= 7.0 la tot"). Chia o bang TRUNG VI CUA CHINH PHIEN QUET
    — cao/thap la so voi cac cum cung dot, khong phai voi mot con so tu tren troi.
  - Mau nho thi KHONG chia o (duoi TOI_THIEU_CUM) — cung luat voi engine chan doan
    "khong du mau thi noi thang, khong ket luan".

Python do — 0 LLM, 0 quota: toan bo ve cung doc tu SQLite san co (31.917 title, 0,21s).
"""
from __future__ import annotations

import re
import statistics
import time

TOI_THIEU_CUM = 5        # duoi nguong nay khong chia o (mau qua nho de lay trung vi)

O_KHOANG_TRONG = "khoang_trong"    # cau cao · cung thap
O_DO_LUA = "do_lua"                # cau cao · cung cao
O_BAO_HOA = "bao_hoa"              # cau thap · cung cao
O_HOANG = "hoang"                  # cau thap · cung thap

NHAN_O = {
    O_KHOANG_TRONG: ("Khoảng trống", "Có người tìm mà gần như chưa ai làm — ưu tiên soi kỹ"),
    O_DO_LUA: ("Đỏ lửa", "Nhiều người tìm và nhiều người làm — phải hơn hẳn mới thắng"),
    O_BAO_HOA: ("Bão hoà", "Đông người làm mà ít người tìm — thường không đáng vào"),
    O_HOANG: ("Hoang", "Ít cả hai — thường có lý do, kiểm trước khi tin là cơ hội"),
}


def _rx(cum: str) -> re.Pattern:
    """Khop theo RANH GIOI TU, khong phai LIKE %x%.

    Bai hoc SEO 18/08 (khop ten ngach): 'Life' nuot 'Life In'. O day neu dung LIKE thi
    'life in' khop ca 'life incremental roblox' — sai han ban chat.
    """
    return re.compile(r"(?<!\w)" + re.escape(cum.strip().lower()).replace(r"\ ", r"\s+") + r"(?!\w)")


def tai_kho(conn, ws: int) -> list[dict]:
    """Doc MOT LAN toan bo video cua workspace (title + view moi nhat + velocity).

    Doc mot lan roi khop trong bo nho: 55 cum x 31.917 video ma ban 55 query LIKE thi
    ton ~11s; tai mot lan roi quet chuoi thi duoi 1s.
    """
    rows = conn.execute("""
        SELECT v.id, v.title, v.channel_title, v.channel_yt_id, v.yt_id,
               v.pub_ts, v.last_vph,
               (SELECT MAX(t.views) FROM ticks t WHERE t.video_id = v.id) AS views
        FROM videos v WHERE v.workspace_id = ? AND v.dead = 0
    """, (ws,)).fetchall()
    return [{"id": r["id"], "title": r["title"] or "", "title_l": (r["title"] or "").lower(),
             "kenh": r["channel_title"] or "", "kenh_yt": r["channel_yt_id"] or "",
             "yt_id": r["yt_id"], "pub_ts": r["pub_ts"] or 0,
             "vph": r["last_vph"] or 0, "views": r["views"] or 0}
            for r in rows]


def do_cung(kho: list[dict], cum: str, tran_vi_du: int = 8) -> dict:
    """Ve CUNG cua mot cum: bao nhieu video, ai lam, view bao nhieu, moi nhat bao gio."""
    rx = _rx(cum)
    khop = [v for v in kho if rx.search(v["title_l"])]
    if not khop:
        return {"so_video": 0, "so_kenh": 0, "view_trung_vi": 0, "vph_trung_vi": 0.0,
                "moi_nhat": 0, "vi_du": []}
    views = sorted(v["views"] for v in khop)
    vph = sorted(v["vph"] for v in khop)
    vi_du = sorted(khop, key=lambda v: -v["views"])[:tran_vi_du]
    return {
        "so_video": len(khop),
        "so_kenh": len({v["kenh_yt"] or v["kenh"] for v in khop}),
        "view_trung_vi": views[len(views) // 2],
        "vph_trung_vi": round(vph[len(vph) // 2], 2),
        "moi_nhat": max(v["pub_ts"] for v in khop),
        "vi_du": [{"title": v["title"], "kenh": v["kenh"], "views": v["views"],
                   "pub_ts": v["pub_ts"], "yt_id": v["yt_id"]} for v in vi_du],
    }


# Tách từ CÓ DẤU: `[a-z0-9']+` băm vụn tiếng Việt ("Cuộc sống" -> cu/c/s/ng) nên pool
# tiếng Việt gợi ý ra rác "cu c (21)". `[^\W_]` giữ nguyên chữ Unicode có dấu.
_TU_RX = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)


# Từ quá phổ biến, có mặt ở mọi title nên không nói lên ngách nào cả.
_TU_TRO = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "is",
           "are", "was", "were", "be", "with", "from", "by", "that", "this", "it",
           "you", "your", "my", "we", "i", "how", "what", "why", "when", "where"}


def von_tu_ngach(kho: list[dict], toi_thieu: int = 2) -> set[str]:
    """Vốn từ của pool: từ xuất hiện trong >= `toi_thieu` title.

    Chỉ để tính `tu_la_voi_pool` (mức mới lạ). KHÔNG dùng làm bộ lọc — xem docstring
    hàm đó: từ chưa có trong pool vừa là dấu hiệu lạc đề, vừa là dấu hiệu khoảng trống.
    """
    dem: dict[str, int] = {}
    for v in kho:
        for t in set(_TU_RX.findall(v["title_l"])):
            if len(t) > 2 and t not in _TU_TRO:
                dem[t] = dem.get(t, 0) + 1
    return {t for t, n in dem.items() if n >= toi_thieu}


def tu_la_voi_pool(cum: str, von: set[str], seed: str = "") -> float | None:
    """Tỉ lệ từ của cụm CHƯA từng xuất hiện trong pool (0..1). Đọc là "mức mới lạ".

    ĐỌC CHO ĐÚNG — đây là chỗ suýt làm sai (đo thật 21/08 trên pool LIFE IN — US):
    thoạt tiên dùng chỉ số ngược lại làm "độ hợp ngách" để dìm cụm lạc đề, và nó dìm
    được `life incremental` (game) thật. NHƯNG nó dìm luôn `life in rio`, `life in
    kiev`, `life in the countryside` — những cụm hợp ngách hoàn hảo, chỉ là pool CHƯA
    CÓ video nào, tức đúng cái KHOẢNG TRỐNG ta đang đi tìm.

    Kết luận: máy KHÔNG phân biệt được "lạc đề" với "mới lạ" — cả hai đều là từ chưa
    có trong pool. Nên chỉ số này chỉ là CỘT THÔNG TIN, tuyệt đối không dùng để xếp
    hạng hay loại bỏ. Lọc nhiễu là việc của người (nút ✕) và của bảng từ chặn.

    Bỏ từ của seed ra khỏi phép tính — seed thì cụm nào cũng có. Không còn từ nào để
    chấm → None (không đủ cơ sở, KHÔNG cho 0).
    """
    tu_seed = {t for t in _TU_RX.findall((seed or "").lower())}
    tu = [t for t in _TU_RX.findall(cum.lower())
          if len(t) > 2 and t not in _TU_TRO and t not in tu_seed]
    if not tu:
        return None
    return round(sum(1 for t in tu if t not in von) / len(tu), 2)


def _o(cau_cao: bool, cung_cao: bool) -> str:
    if cau_cao:
        return O_DO_LUA if cung_cao else O_KHOANG_TRONG
    return O_BAO_HOA if cung_cao else O_HOANG


def ban_do(kho: list[dict], cums: list[dict]) -> dict:
    """Ghep cau x cung -> ban do. `cums` la dau ra cua discovery.quet().

    Nguong = TRUNG VI CUA CHINH PHIEN QUET (khong phai hang so). Duoi TOI_THIEU_CUM
    thi tra `du_mau=False` va KHONG xep o — noi thang thay vi doan.
    """
    von = von_tu_ngach(kho)
    muc = []
    for c in cums:
        cung = do_cung(kho, c["cum"])
        muc.append({**c, **cung,
                    "tu_la": tu_la_voi_pool(c["cum"], von, c.get("seed", ""))})

    du_mau = len(muc) >= TOI_THIEU_CUM
    nguong_cau = nguong_cung = None
    if du_mau:
        nguong_cau = statistics.median([m["do_phu"] for m in muc])
        nguong_cung = statistics.median([m["so_video"] for m in muc])
        for m in muc:
            # KHÔNG có video nào thì KHÔNG BAO GIỜ là "cung cao" — kể cả khi trung vị
            # của phiên bằng 0 (ca rất hay gặp: quét một seed mới, phần lớn cụm chưa ai
            # làm). Thiếu vế này thì cụm 0 video bị xếp 'đỏ lửa' — ngược hẳn sự thật.
            cung_cao = m["so_video"] > 0 and m["so_video"] >= nguong_cung
            m["o"] = _o(m["do_phu"] >= nguong_cau, cung_cao)
    else:
        for m in muc:
            m["o"] = None

    # Xếp theo CẦU rồi tới cung. KHÔNG xếp theo `tu_la`: xem docstring
    # tu_la_voi_pool — máy không phân biệt "lạc đề" với "mới lạ".
    muc.sort(key=lambda m: (-m["do_phu"], m["so_video"]))
    dem = {k: sum(1 for m in muc if m["o"] == k) for k in NHAN_O} if du_mau else {}
    return {
        "muc": muc,
        "du_mau": du_mau,
        "ly_do_thieu_mau": (None if du_mau else
                            f"Chỉ có {len(muc)} cụm — cần ít nhất {TOI_THIEU_CUM} "
                            "để lấy trung vị làm mốc cao/thấp. Quét thêm seed rồi xem lại."),
        "nguong": {"cau_do_phu": nguong_cau, "cung_so_video": nguong_cung},
        "dem_o": dem,
        "so_video_trong_kho": len(kho),
        "quet_luc": time.time(),
    }


# ---- PHAN LOAI QUYET DINH (21/08/2026) — dua tren THI TRUONG, khong phai pool ----
# Ban dau phan o chi bang cau(autocomplete) x cung(pool). User chi ra dung: ca hai ve
# deu la thu RadarY da biet -> "ban sao cua RadarY", khong quyet dinh duoc gi. Do that
# lat nguoc ket luan: `life in rio` bi xep "khoang trong" nhung thi truong cho thay
# 0% video moi, tuoi giua 1.106 ngay, top toan nhac phonk = CUM CHET; con `life in
# vietnam` bi xep "do lua" thi 60% video moi, 11/20 kenh nho lot top = CO CUA.
#
# Nguong duoi la MUC KHOI DAU (chinh duoc), va UI luon hien SO THAT ben canh nhan —
# nguoi doc tu danh gia, may khong quyet ho (luat A3).
SONG_TI_LE_MOI = 30          # >= 30% video top dang trong 90 ngay = thi truong con san xuat
SONG_TUOI_TOI_DA = 365       # tuoi trung vi top > 1 nam = cum da nguoi
CUA_TI_LE_KENH_NHO = 20      # >= 20% ket qua la kenh nho = nguoi moi con lot duoc
DUOI_MUC_MINH = 1 / 3        # thi truong tra < 1/3 view video moi cua pool = khong dang vao

NHAN_QD = {
    "dang_danh": ("Đáng đánh", "Thị trường còn sản xuất, kênh nhỏ vẫn lọt top, pool mình chưa làm"),
    "dang_lam": ("Mình đang làm", "Thị trường sống và pool đã có video — so hiệu suất với thị trường"),
    "kho": ("Khó", "Thị trường sống nhưng top toàn kênh lớn — vào phải có lợi thế riêng"),
    "nguoi": ("Nguội", "Thị trường gần như không còn video mới — cung thấp là hệ quả, không phải cơ hội"),
    "chua_do": ("Chưa đo", "Chưa có số liệu thị trường — bấm Đo thị trường"),
}


def phan_loai_quyet_dinh(m: dict, pool_view_moi: int | None = None) -> str:
    """Nhan quyet dinh cho MOT cum. Chua do thi truong -> 'chua_do', KHONG doan.

    `pool_view_moi` = view trung vi video MOI cua chinh pool (baseline tu minh). Thi
    truong tra duoi 1/3 muc do thi vao cung khong hon duoc cai minh dang co -> 'kho'.
    Do that 21/08: `life in the countryside` song 60% + 11/20 kenh nho nhung chi 4k
    view/video moi, trong khi pool dang o muc cao hon han -> gan "Dang danh" la sai.
    """
    tt = m.get("tt")
    if not tt or not tt.get("so_ket_qua"):
        return "chua_do"
    song = (tt.get("ti_le_moi", 0) >= SONG_TI_LE_MOI
            and tt.get("tuoi_giua_ngay", 9999) <= SONG_TUOI_TOI_DA)
    if not song:
        return "nguoi"
    if m.get("so_video", 0) > 0:
        return "dang_lam"
    vm = tt.get("view_giua_moi")
    if pool_view_moi and vm is not None and vm < pool_view_moi * DUOI_MUC_MINH:
        return "kho"
    co_cua = (100 * tt.get("kenh_nho_lot_top", 0) / max(1, tt["so_ket_qua"])) >= CUA_TI_LE_KENH_NHO
    return "dang_danh" if co_cua else "kho"


def gan_thi_truong(bd: dict, tt_theo_cum: dict, pool_view_moi: int | None = None) -> dict:
    """Gan so lieu thi truong da luu vao ban do + phan loai quyet dinh."""
    for m in bd.get("muc", []):
        m["tt"] = tt_theo_cum.get(m["cum"])
        m["qd"] = phan_loai_quyet_dinh(m, pool_view_moi)
    bd["dem_qd"] = {k: sum(1 for m in bd.get("muc", []) if m.get("qd") == k) for k in NHAN_QD}
    bd["nhan_qd"] = NHAN_QD
    bd["nguong_qd"] = {"song_ti_le_moi": SONG_TI_LE_MOI, "song_tuoi_toi_da": SONG_TUOI_TOI_DA,
                       "cua_ti_le_kenh_nho": CUA_TI_LE_KENH_NHO,
                       "duoi_muc_minh": DUOI_MUC_MINH, "pool_view_moi": pool_view_moi}
    return bd


# ---- GOI Y SEED TU CHINH NGACH (21/08/2026, sau khi user quet seed 'vietnam') ----
# Su co: o seed de tu do -> user go 'vietnam' (danh tu don) -> autocomplete tra ve
# 'vietnam airlines', 'vietnam khmer rouge war', 'vietnam economy' — ca vu tru chu de,
# khong cum nao thuoc ngach "Life in". 191 cum vo nghia.
# Chua: seed phai la MAU CAU cua ngach. May biet mau do o dau? O chinh TITLE video
# ma pool dang theo doi — n-gram lap lai nhieu nhat chinh la cach ngach nay dat ten.
def goi_y_seed(kho: list[dict], so_goi_y: int = 8, toi_thieu_video: int = 3,
               ngon_ngu: str | None = None, moi_vi_tri: bool = False) -> list[dict]:
    """N-gram 2-3 tu lap lai nhieu nhat trong title pool -> seed dung ngach.

    `moi_vi_tri=False` (mac dinh cu): chi lay n-gram MO DAU title — hop de goi y SEED
    quet, vi phan lon title dat theo mau "Life in X".
    `moi_vi_tri=True`: quet MOI vi tri trong title. User 21/08: "tu khoa trong pool
    nay co rat nhieu, tai sao chi co moi vai cum" — dung, chi lay dau title thi bo sot
    gan het chu de nam giua cau ("... abandoned village ...", "... cost of living ...").
    Che do nay bo n-gram toan tu chuc nang ("in the", "of the") cho khoi rac.
    """
    dem: dict[str, int] = {}
    for v in kho:
        if not hop_ngon_ngu(v["title"], ngon_ngu):
            continue          # pool lẫn ngôn ngữ khác thị trường -> không lấy làm seed
        tu = [t for t in _TU_RX.findall(v["title_l"]) if len(t) > 1]
        thay = set()          # mỗi cụm đếm MỘT lần cho mỗi video
        for n in (2, 3):
            if len(tu) < n:
                continue
            vi_tri = range(len(tu) - n + 1) if moi_vi_tri else [0]
            for i in vi_tri:
                cum = tu[i:i + n]
                if all(t in _TU_TRO for t in cum):
                    continue          # "in the", "of the" — không nói lên chủ đề nào
                if moi_vi_tri and cum[0] in _TU_TRO:
                    # Bỏ n-gram MỞ ĐẦU bằng từ chức năng ("the most", "of extremely",
                    # "the world") — chúng là đuôi của cụm khác, không phải chủ đề.
                    # Vẫn GIỮ n-gram kết thúc bằng từ chức năng ("life in", "land of")
                    # vì đó là mẫu mở đầu chủ đề, chính là thứ ngách này hay dùng.
                    continue
                thay.add(" ".join(cum))
        for c in thay:
            dem[c] = dem.get(c, 0) + 1
    ra = [{"seed": k, "so_video": n} for k, n in dem.items() if n >= toi_thieu_video]
    # bo n-gram 3 tu neu n-gram 2 tu dau cua no da co va pho bien hon (tranh trung lap)
    hai = {r["seed"]: r["so_video"] for r in ra if len(r["seed"].split()) == 2}
    ra = [r for r in ra
          if len(r["seed"].split()) == 2
          or hai.get(" ".join(r["seed"].split()[:2]), 0) < r["so_video"] * 1.5]
    ra.sort(key=lambda r: -r["so_video"])
    return ra[:so_goi_y]


# ---- NGON NGU / VUNG CUA POOL (21/08/2026 — user: "khong lam thi truong Viet Nam") --
# Su co: pool goc LIFE IN chua ca kenh Viet -> goi_y_seed rut "cuộc sống thực" -> quet
# ra cum Viet -> do thi truong Viet. Toan bo chuoi lech thi truong, tieu 816 units cho
# thu user khong dung. Goc chuoi la SEED, nen chan ngay o do.
# CHI ky tu RIENG tieng Viet. Ban dau gom ca à á è é ì í ò ó ù ú ý -> "La vida en
# España — dónde vivir" bi nhan nham la tieng Viet (tieng Tay Ban Nha dung chung
# cac dau do). Bo chung di, giu chu co dau/mu/moc va thanh hoi-nga-nang.
_VN_RX = re.compile(r"[ăâđêôơưảãạằắẳẵặầấẩẫậẻẽẹềếểễệỉĩịỏõọồốổỗộờớởỡợủũụừứửữựỳỷỹỵ]")

# Ngon ngu (theo ten trong de) -> ma dung cho autocomplete (hl) + YouTube API
# (relevanceLanguage). Thieu ten nao thi khong ep — de mac dinh, khong doan bua.
MA_NGON_NGU = {"english": "en", "spanish": "es", "vietnamese": "vi", "korean": "ko",
               "japanese": "ja", "french": "fr", "german": "de", "portuguese": "pt",
               "chinese": "zh", "tiếng việt": "vi", "tieng viet": "vi",
               # Đế thật do người nhập nên có lỗi (đo 21/08): TT-US khai ngôn ngữ "US",
               # TT-SPAIN khai "Spainish". Nhận luôn thay vì để rơi về "không rõ".
               "us": "en", "uk": "en", "america": "en", "spainish": "es", "espanol": "es"}
# Ma thi truong TT-xx -> regionCode ISO-3166. Chi khai cai dang dung.
MA_VUNG = {"TT-US": "US", "TT-SPAIN": "ES", "TT-KOREA": "KR", "TT-VN": "VN",
           "TT-UK": "GB", "TT-TAIWAN": "TW"}
# Vung -> ngon ngu mac dinh, dung khi ten ngon ngu trong de khong doc duoc. Suy tu MA
# thi truong (do Owner dat, on dinh hon o chu ngon ngu go tay).
NGON_NGU_THEO_VUNG = {"US": "en", "GB": "en", "ES": "es", "KR": "ko", "VN": "vi",
                      "TW": "zh", "JP": "ja", "FR": "fr", "DE": "de", "BR": "pt"}


def la_tieng_viet(s: str) -> bool:
    return bool(_VN_RX.search(s or ""))


def hop_ngon_ngu(title: str, ngon_ngu: str | None) -> bool:
    """Title co hop ngon ngu thi truong khong. MVP: chi phan biet Viet / khong-Viet —
    du cho ca dang gap (pool EN lan kenh Viet). Khong ro ngon ngu -> nhan het."""
    if not ngon_ngu:
        return True
    ma = MA_NGON_NGU.get(ngon_ngu.strip().lower())
    if ma is None and ngon_ngu.strip().upper() in NGON_NGU_THEO_VUNG:
        ma = NGON_NGU_THEO_VUNG[ngon_ngu.strip().upper()]
    if ma in (None, ""):
        return True
    cua_title = nhan_dien_ngon_ngu(title)
    if cua_title is None:
        return True                      # không đủ căn cứ -> nhận, không loại oan
    return cua_title == ma


def vung_ngon_ngu(market: str | None, ngon_ngu: str | None) -> dict:
    """Tham so vung cho autocomplete (hl/gl) va YouTube search (regionCode/
    relevanceLanguage). Khong khai duoc thi tra rong — KHONG doan mac dinh 'US'."""
    ra = {}
    ma_v = MA_VUNG.get((market or "").strip().upper())
    ma_l = MA_NGON_NGU.get((ngon_ngu or "").strip().lower()) or NGON_NGU_THEO_VUNG.get(ma_v)
    if ma_l:
        ra["hl"] = ma_l
        ra["relevanceLanguage"] = ma_l
    if ma_v:
        ra["gl"] = ma_v.lower()
        ra["regionCode"] = ma_v
    return ra


# ---- NHAN DIEN NGON NGU title (21/08, ban 2) ----------------------------------
# hop_ngon_ngu ban dau chi phan biet Viet / khong-Viet, nen title TIENG ANH van lot
# vao pool Spain. Dem TU CHUC NANG — du chinh xac cho title, khong can thu vien.
_TU_CHUC_NANG = {
    "en": {"the", "of", "and", "in", "to", "for", "with", "that", "this", "how",
           "what", "why", "from", "on", "is", "are", "you", "your", "life", "living"},
    "es": {"de", "la", "el", "en", "los", "las", "que", "para", "con", "una", "del",
           "por", "es", "un", "más", "cómo", "qué", "vida", "vivir", "país", "dónde"},
    "vi": {"của", "và", "là", "trong", "cho", "với", "những", "người", "cuộc", "sống",
           "thực", "quốc", "gia", "sự", "thật", "nhất", "này", "đất", "nước"},
}


def nhan_dien_ngon_ngu(title: str) -> str | None:
    """Ma ngon ngu cua title, hoac None khi khong du can cu (KHONG doan bua)."""
    if la_tieng_viet(title):
        return "vi"                     # dau tieng Viet la bang chung du manh
    tu = set(_TU_RX.findall((title or "").lower()))
    if not tu:
        return None
    diem = {ma: len(tu & bo) for ma, bo in _TU_CHUC_NANG.items()}
    tot = max(diem, key=lambda k: diem[k])
    if diem[tot] == 0 or diem[tot] == sorted(diem.values())[-2]:
        return None                     # hoa nhau hoac khong tu nao khop -> khong ket luan
    return tot
