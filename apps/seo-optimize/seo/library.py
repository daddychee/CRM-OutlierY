"""Thư viện kênh — tầng NICHE → PROFILE KÊNH + lịch sử run.

Module 1 (profile.py) sinh phần MÁY phân tích được (skeleton, hashtag, example).
Module này quản phần NGƯỜI tự khai, gắn liền từng kênh:
  niche · lang (ngôn ngữ chính) · links (Link/CTA cố định) · note

Không gọi LLM, không tốn quota YouTube — chỉ đọc/ghi JSON trong `profiles/` và `runs/`.
Niche KHÔNG có store riêng: nó là 1 field trên profile (user tự nhập → không sợ LLM chẻ nhỏ/
trùng lặp niche); board.html gom nhóm khi render.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import common

# Field do user tự khai. Re-extract profile (Module 1) KHÔNG được ghi đè các field này.
# `format` = slug Format Profile của đối thủ mà kênh này học theo — GẮN SẴN vào kênh, không phải
# chọn lại mỗi lần generate (user chốt 2026-07-28).
# `sub_url` = THỨ DUY NHẤT user phải gõ tay cho khối CTA (link sub_confirmation).
# `links` = khối CTA thành phẩm, do cta.py sinh theo format đối thủ rồi user duyệt/sửa.
# `build_done` = các mục trong checklist dựng kênh đã tick (lưu theo NỘI DUNG mục, không theo
#   chỉ số: extract lại Format có thể đổi thứ tự/số lượng mục, lưu theo index là tick nhảy lung tung).
USER_FIELDS = ("niche", "lang", "links", "sub_url", "note", "format", "build_done")
_LIST_FIELDS = ("build_done",)                             # field dạng danh sách — KHÔNG được str() vào


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def profile_path(slug: str) -> Path:
    return common.profiles_dir() / f"{common.slug(slug)}.json"


def load(slug: str) -> dict | None:
    f = profile_path(slug)
    if not f.exists():
        return None
    p = common.read_json(f)
    p["slug"] = f.stem
    return p


def all_profiles(errors: list | None = None) -> list[dict]:
    """Mọi profile + slug. Field user thiếu → mặc định rỗng.

    File hỏng vẫn bị bỏ qua (một file lỗi không được giết cả tab), NHƯNG phải GHI LẠI vào
    `errors` để caller báo lên. Trước đây bỏ qua IM LẶNG: kênh biến mất khỏi board mà không
    một chữ nào ⇒ user tưởng nó đã bị xoá, đi extract lại, tốn quota cho thứ vẫn nằm trên đĩa.
    """
    d = common.profiles_dir()
    out: list[dict] = []
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        try:
            p = common.read_json(f)
        except Exception as e:                             # noqa: BLE001
            if errors is not None:
                errors.append({"kind": "kênh", "file": f.name, "error": str(e)[:200]})
            continue
        p["slug"] = f.stem
        for k in USER_FIELDS:
            p.setdefault(k, [] if k in _LIST_FIELDS else "")
        out.append(p)
    return out


def user_meta(prof: dict) -> dict:
    """Chỉ phần user khai — dùng khi re-extract để không mất dữ liệu đã nhập."""
    return {k: prof[k] for k in USER_FIELDS if prof.get(k)}


def merge_user(prof: dict, src: dict) -> dict:
    """Chép field user khai từ `src` (profile cũ hoặc body form) vào `prof`. Bỏ giá trị rỗng.

    `created_by` đi ĐƯỜNG RIÊNG, không nằm trong `USER_FIELDS`: nó KHÔNG phải thứ user gõ
    vào form được. Giữ nguyên bản CŨ nếu đã có; chỉ nhận giá trị mới khi hồ sơ chưa từng ghi,
    tức lần extract ĐẦU TIÊN. **Re-extract KHÔNG BAO GIỜ đổi chủ kênh** — nếu không thì
    Manager chạy lại số liệu một cái là cướp mất quyền sửa của Seo đang giữ kênh đó.

    Đổi chủ chỉ đi qua `set_owner()` (quyền `chan_owner` = từ Leader trở lên, có ghi nhật ký).
    """
    old = (prof.get("created_by") or "").strip()
    new = str(src.get("created_by") or "").strip()
    if new and not old:
        prof["created_by"] = new
    for k in USER_FIELDS:
        if k not in src:
            continue
        v = src[k]
        if k in _LIST_FIELDS:
            v = [str(x) for x in (v or []) if str(x).strip()]
        else:
            v = str(v or "").strip()
            if k == "sub_url" and v:                       # dán link kênh là đủ, tool tự thêm đuôi
                v = common.sub_url_from(v)
        if v:
            prof[k] = v
    return prof


def update(slug: str, patch: dict) -> dict:
    """Ghi field user khai lên profile có sẵn. Chỉ đụng USER_FIELDS — không chạm phần máy phân tích."""
    sl = common.slug(slug)
    prof = load(sl)
    if prof is None:
        raise RuntimeError(f"Không thấy profile: {sl}")
    for k in USER_FIELDS:                                  # cho phép xoá (set rỗng) → không dùng merge_user
        if k not in patch:
            continue
        if k in _LIST_FIELDS:
            prof[k] = [str(x) for x in (patch[k] or []) if str(x).strip()]
        elif k == "sub_url":
            prof[k] = common.sub_url_from(str(patch[k] or "").strip())
        else:
            prof[k] = str(patch[k] or "").strip()
    prof["updated"] = now_iso()
    prof.pop("slug", None)                                 # slug suy từ tên file, không lưu trong file
    common.write_json(profile_path(sl), prof)
    prof["slug"] = sl
    return prof


def set_code(slug: str, code: str, role: str) -> dict:
    """Đổi MÃ KÊNH — đường DUY NHẤT, có luật vai (user chốt 2026-08-04).

    Mã kênh do user nhập tay lúc tạo. Sau đó: vai **seo** chỉ được sửa **1 lần duy nhất**
    (cờ `code_seo_edited` ghi vào profile — đếm theo KÊNH, không theo người, vì mã là thuộc
    tính của kênh); leader/manager/owner sửa tự do. Cố ý KHÔNG gộp vào `update()` — cùng lý
    do với `set_owner`: update nhận nguyên body form, gộp vào là mọi cú Lưu đều có thể mang
    theo một cú đổi mã lách luật đếm.

    Slug KHÔNG đổi theo mã (slug là ID nội bộ suy từ tên file — đổi là vỡ lịch sử run, đúng
    bẫy đã ghi ở `profile.extract`). Trùng mã kênh khác → chặn, nói rõ trùng với ai.
    """
    sl = common.slug(slug)
    prof = load(sl)
    if prof is None:
        raise RuntimeError(f"Không thấy profile: {sl}")
    new = str(code or "").strip()[:24]
    if not new:
        raise RuntimeError("Mã kênh không được để trống")
    if new == (prof.get("code") or ""):
        return prof                                        # không đổi gì — không tốn lượt của Seo
    for f in (common.profiles_dir().glob("*.json") if common.profiles_dir().exists() else []):
        if f.stem == sl:
            continue
        try:
            other = common.read_json(f)
        except Exception:                                  # noqa: BLE001 — file hỏng không chặn đổi mã
            continue
        if (other.get("code") or "") == new:
            raise RuntimeError(f"Mã '{new}' đã có kênh '{other.get('channel') or f.stem}' dùng "
                               "— chọn mã khác")
    if role == "seo":
        if prof.get("code_seo_edited"):
            raise RuntimeError("Bạn đã dùng LẦN SỬA MÃ KÊNH DUY NHẤT của mình cho kênh này "
                               "— muốn đổi nữa thì nhờ Leader / Manager / Owner.")
        prof["code_seo_edited"] = True
    prof["code"] = new
    prof["updated"] = now_iso()
    prof.pop("slug", None)
    common.write_json(profile_path(sl), prof)
    prof["slug"] = sl
    return prof


def set_owner(slug: str, owner: str) -> dict:
    """Đổi CHỦ kênh (`created_by`) — quyết định AI ĐƯỢC SỬA kênh này.

    Cố ý KHÔNG gộp vào `update()`: `update` nhận nguyên body form nên gộp vào là mọi lần Lưu
    thông tin kênh đều có thể mang theo một cú đổi chủ — đúng thứ mà việc để `created_by`
    ngoài `USER_FIELDS` đang phòng. Đây là hành động RIÊNG, quyền RIÊNG (`chan_owner`), và
    hiện trong nhật ký dưới tên riêng.

    `owner` rỗng = GỠ chủ. Không cấm, vì "giao nhầm người" phải sửa lại được; nhưng gỡ xong
    thì kênh về diện chỉ Manager/Owner sửa, nên board phải nói rõ điều đó.
    """
    sl = common.slug(slug)
    prof = load(sl)
    if prof is None:
        raise RuntimeError(f"Không thấy profile: {sl}")
    prof["created_by"] = str(owner or "").strip()
    prof["updated"] = now_iso()
    prof.pop("slug", None)
    common.write_json(profile_path(sl), prof)
    prof["slug"] = sl
    return prof


_HASHTAG_RE = None


def hashtags_of(text: str) -> list[str]:
    """Hashtag trong một khối text. Giữ THỨ TỰ, bỏ trùng (không phân biệt hoa/thường).

    Nguồn thật của hashtag là ô **Link/CTA của kênh** (`profile.links`) — `describe._assemble`
    cố ý KHÔNG sinh block HASHTAG/CTA/LINKS, chúng là block cố định user tự khai.
    """
    global _HASHTAG_RE
    if _HASHTAG_RE is None:
        _HASHTAG_RE = re.compile(r"#[\wÀ-ỹ]+")
    out, seen = [], set()
    for h in _HASHTAG_RE.findall(text or ""):
        if h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out


def _run_summary(d: Path, r: dict, want: str = "") -> dict:
    created = r.get("created")
    if not created:                                        # run cũ (trước khi có field) → dùng mtime
        created = datetime.fromtimestamp((d / "result.json").stat().st_mtime).astimezone().isoformat(timespec="seconds")
    base = {"run": d.name, "created": created, "main_title": r.get("_main_title", ""),
            "main_url": r.get("main_url", ""), "exported_at": r.get("exported_at", "")}
    if r.get("mode") == "episode":                         # 1 tập → N kênh: lấy phần của kênh đang lọc
        chans = r.get("channels") or []
        mine = next((c for c in chans if c.get("slug") == want), None) if want else None
        c = mine or (chans[0] if chans else {})
        links = c.get("links", "")
        return {**base, "profile": want, "mode": "episode", "n_channels": len(chans),
                "titles": [(x.get("title") or {}).get("text", "") for x in chans],
                # KÊNH CHỦ của từng title, XẾP THẲNG HÀNG với `titles` ở trên. Không có nó thì
                # `title_index` không quy được title về kênh nào ⇒ thanh tìm kiếm không lọc được
                # theo thị trường (bug user bắt được: tìm ở SPAIN ra title của kênh US).
                "title_owners": [x.get("slug", "") for x in chans],
                "tags": (c.get("tags") or {}).get("tags", []),
                "description": (c.get("description") or {}).get("text", ""),
                "links": links,
                "hashtags": hashtags_of((c.get("description") or {}).get("text", "") + chr(10) + links),
                "picked_title": ((mine or {}).get("title") or {}).get("text", "")}
    tsets = r.get("tags") or []
    desc = (r.get("description") or {}).get("text", "")
    # Chế độ 1 kênh: result.json không lưu links (nó được ghép lúc export) → lấy từ profile kênh.
    links = ((load(r.get("profile", "")) or {}).get("links") or "") if r.get("profile") else ""
    ts = [t.get("text", "") for t in (r.get("titles") or [])]
    return {**base, "profile": r.get("profile", ""),
            "titles": ts,
            # Chế độ 1 kênh: `titles` là ×3 phương án CỦA CÙNG MỘT kênh (khác chế độ episode —
            # ở đó mỗi phần tử là title của một kênh khác nhau). Nên mọi phần tử cùng một chủ.
            "title_owners": [r.get("profile", "")] * len(ts),
            "tags": (tsets[0].get("tags") if tsets else []) or [],
            "description": desc, "links": links,
            "hashtags": hashtags_of(desc + chr(10) + links),
            "picked_title": r.get("picked_title", "")}


def runs(profile_slug: str = "", limit: int = 30) -> list[dict]:
    """Lịch sử generate (mới→cũ). Lọc theo kênh nếu có `profile_slug`.

    Đọc thẳng `runs/*/result.json` — không có file index riêng để tránh 2 nguồn sự thật;
    tool nội bộ, số run cỡ vài chục nên quét thư mục là đủ rẻ.
    """
    want = common.slug(profile_slug) if profile_slug else ""
    out: list[dict] = []
    if not common.RUNS.exists():
        return out
    for d in common.RUNS.iterdir():
        f = d / "result.json"
        if not d.is_dir() or not f.exists():
            continue
        try:
            r = common.read_json(f)
        except Exception:                                  # noqa: BLE001
            continue
        if want and (r.get("profile") or "") != want and \
                want not in [c.get("slug") for c in (r.get("channels") or [])]:
            continue                                       # run episode: khớp nếu kênh nằm trong danh sách
        out.append(_run_summary(d, r, want))
    out.sort(key=lambda x: x["created"], reverse=True)
    return out[:limit]


RUNS_SCAN = 400          # quét rộng RỒI mới gộp — cắt trước khi gộp là tập cũ rơi khỏi lịch sử
RUNS_KEEP = 40           # số DÒNG (tập) giữ lại sau khi gộp


def title_index(limit: int = RUNS_SCAN) -> list[dict]:
    """Mọi title ĐÃ TỪNG sinh, gộp theo mặt chữ → cho thanh tìm kiếm.

    Vì sao đáng có: mạng lưới re-up một tập lên nhiều kênh, và cả tool sinh ra để **né trùng
    metadata**. Câu hỏi "title này tôi dùng chưa" vì thế là câu hỏi thật, mà trước nay muốn
    trả lời phải mở từng thẻ kênh xem bảng lịch sử. Đo trên dữ liệu thật của user: 30 run,
    53 title khác nhau — đủ nhiều để không nhớ nổi.

    **Gộp theo TEXT, không theo run**: cùng một title xuất hiện ở 4 run là MỘT dòng kèm
    `uses=4`, chứ không phải 4 dòng giống hệt nhau đẩy hết kết quả khác ra khỏi danh sách.
    `run`/`created` giữ của lần **mới nhất** — đó là bản user muốn mở ra xem.

    **`channels` là thứ BẮT BUỘC phải trả** (thêm 2026-08-02, sau bug user bắt được bằng ảnh
    chụp): đứng ở thị trường SPAIN gõ tìm mà ra title của kênh US, bấm vào là khung KẾT QUẢ
    mở nguyên một run tiếng Anh **bên trong không gian SPAIN** — đúng thứ phá sự tách biệt.
    Ba nhóm kia của thanh tìm (Kênh · Format · Tập) đều lọc được vì chúng mang `lang`; nhóm
    title thì trước đây chỉ có `{text, run, created, uses}`, **board không có gì để đối chiếu**.
    Nên chỗ sửa nằm ở đây chứ không phải ở board: cấp dữ liệu, rồi board mới lọc được.

    Rỗng nghĩa là *"không quy được về kênh nào"* (run gọi API thẳng, run self-test), **KHÔNG**
    nghĩa là *"không thuộc kênh nào"* — board phải cho những dòng đó qua, đúng luật
    "chưa đo được ≠ đã đo và lệch".

    Thuần đọc đĩa, không LLM, không quota.
    """
    seen: dict[str, dict] = {}
    for r in runs("", limit=limit):
        owners = r.get("title_owners") or []
        for i, t in enumerate(r.get("titles") or []):
            t = (t or "").strip()
            if not t:                                     # title rỗng = kênh KHÔNG sinh được
                continue                                  # (đã có cảnh báo riêng), đừng đưa vào tìm kiếm
            own = (owners[i] if i < len(owners) else "") or ""
            cur = seen.get(t)
            if cur is None:
                seen[t] = {"text": t, "run": r["run"], "created": r["created"], "uses": 1,
                           "channels": [own] if own else []}
            else:
                cur["uses"] += 1
                if own and own not in cur["channels"]:    # cùng title dùng ở nhiều kênh → gom đủ
                    cur["channels"].append(own)
                if r["created"] > cur["created"]:         # runs() trả mới→cũ, nhưng đừng dựa vào
                    cur["run"], cur["created"] = r["run"], r["created"]
    return sorted(seen.values(), key=lambda x: x["created"], reverse=True)


def fold_runs(rs: list[dict]) -> list[dict]:
    """Gộp mọi lần sinh của CÙNG một tập thành MỘT dòng, lấy bản mới nhất.

    User chốt 2026-07-31: lịch sử kênh là "mỗi tập một dòng, cập nhật tới ngày mới nhất",
    không phải nhật ký từng lần bấm nút (đo thật: 1 tập của user đã đẻ 10 dòng).

    Nhận `rs` ĐÃ được server gắn `episode`/`code` (mã tập nối ở `server.py` vì `episodes`
    import `library`, import ngược lại là vòng). Hàm này thuần tính toán nên ở đây để có
    self-test chốt — đó là lý do nó không nằm cạnh endpoint.

    **Khoá gộp là slug của TẬP, KHÔNG phải `code`.** Mã tập là của user và user được phép
    đặt trùng — gộp theo mã thì hai tập khác nhau trùng mã sẽ nuốt nhau, mất hẳn một tập
    khỏi lịch sử. Run không thuộc tập nào (gọi API thẳng) thì gộp theo **video id** của
    `main_url`; không có URL thì đứng riêng.
    """
    groups: dict[tuple, list[dict]] = {}
    for r in rs:
        if r.get("episode"):
            key = ("ep", r["episode"])
        elif r.get("main_url"):
            # Chuẩn hoá về VIDEO ID: cùng một video dán hai dạng ("watch?v=X&t=3s" và
            # "youtu.be/X") mà tách nhóm thì lại đẻ ra hai dòng — đúng thứ đang muốn bỏ.
            key = ("url", common.extract_video_id(r["main_url"]) or r["main_url"])
        else:
            key = ("run", r.get("run"))
        groups.setdefault(key, []).append(r)

    out: list[dict] = []
    for g in groups.values():
        # KHÔNG tin thứ tự caller đưa vào: đại diện phải là bản created mới nhất. Trước đây
        # lấy thẳng g[0] theo giả định "rs đã sort" — giả định đúng hôm nay, nhưng nó nằm ở
        # hàm khác, đổi một chỗ là dòng lịch sử lặng lẽ hiện nội dung của bản cũ.
        g = sorted(g, key=lambda x: x.get("created") or "", reverse=True)
        top = dict(g[0])                                   # bản mới nhất = nội dung hiện hành
        # `exported_at` phải là của CHÍNH bản đang hiện, TUYỆT ĐỐI không lấy max cả nhóm.
        # Bản đầu làm thế và đẻ ra dòng tự mâu thuẫn: cột Tiêu đề của bản mới (chưa xuất) đứng
        # cạnh ngày xuất của bản cũ có title KHÁC HẲN — file dán sang Sheets khẳng định "title
        # này đã xuất lúc T" trong khi thứ thật sự lên YouTube lúc T là title khác. Bảng HTML
        # còn cãi lại được bằng một dòng chữ, nhưng CSV/TSV chỉ có 7 cột nên nó nói dối im lặng,
        # mà đây đúng là sổ user tra khi re-up. (Đo thật: 2/2 dòng của Hidden Globe đều lệch,
        # còn ra cặp bất khả thi ngày xuất 00:37 SỚM HƠN ngày tạo 00:49.)
        top["exported_at"] = g[0].get("exported_at") or ""
        # Ngày xuất của các bản CŨ vẫn giữ để board hiện làm ngữ cảnh ("bản trước đã xuất lúc…"),
        # nhưng KHÔNG bao giờ leo vào cột ngày xuất — mất tin thì thà thiếu còn hơn sai.
        top["prev_export"] = max((x.get("exported_at") or "" for x in g[1:]),
                                 key=lambda s: s[:19], default="")
        top["n_runs"] = len(g)
        # Bản cũ giữ ĐỦ THÔNG TIN, không chỉ ngày (user chốt 2026-08-01: *"tôi vẫn muốn bạn lưu
        # lại những thông tin của các lần tạo"*). Trước đây chỉ mang run/created/exported_at ⇒
        # bung "N lần tạo" ra chỉ thấy một cái ngày, muốn biết lần đó ra title gì thì phải bấm
        # "mở" để nạp cả run vào Generator — mất luôn ngữ cảnh đang xem.
        # Dữ liệu vốn đã nằm sẵn trong `_run_summary`, không phải đọc thêm file nào; chỉ là
        # trước đây bị cắt bớt lúc gộp.
        top["older"] = g[1:]
        out.append(top)
    out.sort(key=lambda x: x.get("created") or "", reverse=True)
    return out                                             # KHÔNG cắt ở đây — caller cắt và báo


def mark_export(run: str, picked_title: str = "") -> None:
    """Ghi title đã chọn vào result.json lúc xuất — để lịch sử kênh biết title NÀO đã dùng thật."""
    f = common.run_dir(run) / "result.json"
    if not f.exists():
        return
    try:
        r = common.read_json(f)
    except Exception:                                      # noqa: BLE001
        return
    r["exported_at"] = now_iso()
    if picked_title:
        r["picked_title"] = picked_title
    common.write_json(f, r)


if __name__ == "__main__":                                 # self-test offline (thư mục tạm, không đụng dữ liệu thật)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        common.PROFILES = Path(tmp) / "profiles"
        common.RUNS = Path(tmp) / "runs"
        common.write_json(common.profiles_dir(create=True) / "cosmic-lens-cl-01.json",
                          {"channel": "Cosmic Lens", "code": "CL-01", "skeleton": ["HOOK"], "n_videos": 8})
        common.write_json(common.profiles_dir() / "outland-o-01.json",
                          {"channel": "Outland", "code": "O-01", "niche": "Space", "skeleton": ["HOOK"]})

        p = update("cosmic-lens-cl-01", {"niche": "Space", "lang": "English",
                                         "links": "👉 Subscribe: https://x"})
        assert p["niche"] == "Space" and p["lang"] == "English", p

        assert p["skeleton"] == ["HOOK"], p                # KHÔNG đụng phần máy phân tích

        assert {p["niche"] for p in all_profiles()} == {"Space"}, all_profiles()
        update("outland-o-01", {"niche": ""})              # cho phép xoá về rỗng (board xếp vào nhóm cuối)
        assert load("outland-o-01")["niche"] == "", load("outland-o-01")

        keep = user_meta(load("cosmic-lens-cl-01"))
        fresh = merge_user({"channel": "Cosmic Lens", "skeleton": ["HOOK", "SUMMARY"]}, keep)
        assert fresh["niche"] == "Space" and fresh["skeleton"] == ["HOOK", "SUMMARY"], fresh

        # ── MÃ KÊNH theo luật vai (user chốt 2026-08-04): seo đúng 1 lần, leader+ tự do ──
        assert set_code("cosmic-lens-cl-01", "CL-01", "seo")["code"] == "CL-01"   # không đổi → không tốn lượt
        assert not load("cosmic-lens-cl-01").get("code_seo_edited")
        try:
            set_code("cosmic-lens-cl-01", "O-01", "seo")
            raise AssertionError("mã trùng kênh khác phải bị CHẶN")
        except RuntimeError as e:
            assert "Outland" in str(e), e                  # nói rõ trùng với AI
        assert not load("cosmic-lens-cl-01").get("code_seo_edited"), "bị chặn thì KHÔNG tốn lượt"
        assert set_code("cosmic-lens-cl-01", "CL-99", "seo")["code"] == "CL-99"   # lần sửa DUY NHẤT
        assert load("cosmic-lens-cl-01").get("code_seo_edited") is True
        try:
            set_code("cosmic-lens-cl-01", "CL-98", "seo")
            raise AssertionError("seo sửa lần 2 phải bị CHẶN")
        except RuntimeError as e:
            assert "Leader" in str(e), e
        assert load("cosmic-lens-cl-01")["code"] == "CL-99"
        for role in ("leader", "manager", "owner"):        # leader+ sửa tự do, không đụng cờ của seo
            assert set_code("cosmic-lens-cl-01", f"CL-{role[:2].upper()}", role)["code"] == f"CL-{role[:2].upper()}"
        assert load("cosmic-lens-cl-01").get("code_seo_edited") is True, "cờ seo không bị leader+ xoá"
        try:
            set_code("cosmic-lens-cl-01", "", "owner")
            raise AssertionError("mã rỗng phải bị chặn")
        except RuntimeError:
            pass
        set_code("cosmic-lens-cl-01", "CL-01", "owner")    # trả về mã cũ cho các test dưới

        rd = common.run_dir("gen-1", create=True)
        common.write_json(rd / "result.json", {"profile": "cosmic-lens-cl-01", "created": "2026-07-20T10:00:00+07:00",
                                               "_main_title": "Monster", "titles": [{"text": "A"}, {"text": "B"}],
                                               "tags": [{"tags": ["sgr a*"]}]})
        common.write_json(common.run_dir("gen-2", create=True) / "result.json",
                          {"profile": "outland-o-01", "created": "2026-07-21T10:00:00+07:00"})
        mark_export("gen-1", "A")
        rs = runs("cosmic-lens-cl-01")
        assert len(rs) == 1 and rs[0]["picked_title"] == "A" and rs[0]["titles"] == ["A", "B"], rs
        assert rs[0]["exported_at"] and rs[0]["tags"] == ["sgr a*"], rs
        assert [r["run"] for r in runs()] == ["gen-2", "gen-1"], runs()   # mới → cũ

        # run "1 tập → N kênh": phải hiện trong lịch sử của MỌI kênh trong tập đó
        common.write_json(common.run_dir("ep-1", create=True) / "result.json",
                          {"mode": "episode", "created": "2026-07-22T10:00:00+07:00",
                           "channels": [{"slug": "cosmic-lens-cl-01", "title": {"text": "T-A"},
                                         "tags": {"tags": ["a"]}},
                                        {"slug": "outland-o-01", "title": {"text": "T-B"},
                                         "tags": {"tags": ["b"]}}]})
        rc = runs("cosmic-lens-cl-01")[0]
        assert rc["run"] == "ep-1" and rc["n_channels"] == 2, rc
        assert rc["picked_title"] == "T-A" and rc["tags"] == ["a"], rc   # lấy đúng phần của kênh đang lọc
        assert runs("outland-o-01")[0]["picked_title"] == "T-B", runs("outland-o-01")[0]

        # ── field DANH SÁCH (build_done) không được bị str() thành chuỗi ──
        ck = ["Viết About theo công thức", "Điền 8-12 từ khoá kênh"]
        p = update("cosmic-lens-cl-01", {"build_done": ck})
        assert p["build_done"] == ck, p["build_done"]
        assert load("cosmic-lens-cl-01")["build_done"] == ck        # đọc lại từ đĩa vẫn là list
        assert update("cosmic-lens-cl-01", {"build_done": []})["build_done"] == []   # bỏ tick hết
        # re-extract Module 1 KHÔNG được xoá tick đã đánh
        update("cosmic-lens-cl-01", {"build_done": ck})
        fresh = merge_user({"channel": "Cosmic Lens"}, user_meta(load("cosmic-lens-cl-01")))
        assert fresh["build_done"] == ck, fresh
        assert all(isinstance(x, str) for x in fresh["build_done"]), fresh
        assert all_profiles()[0]["build_done"] == ck                # API trả về đúng kiểu list

        # ── sub_url: dán link kênh là đủ, cả 2 đường ghi đều tự thêm đuôi ──
        UC = "UC" + "z" * 22
        pu = update("cosmic-lens-cl-01", {"sub_url": f"https://www.youtube.com/channel/{UC}"})
        assert pu["sub_url"] == f"https://www.youtube.com/channel/{UC}?sub_confirmation=1", pu["sub_url"]
        assert update("cosmic-lens-cl-01", {"sub_url": "@MyChan"})["sub_url"] ==             "https://www.youtube.com/@MyChan?sub_confirmation=1"
        assert update("cosmic-lens-cl-01", {"sub_url": ""})["sub_url"] == ""     # xoá về rỗng vẫn được
        fresh2 = merge_user({"channel": "X"}, {"sub_url": "youtube.com/@Abc"})
        assert fresh2["sub_url"] == "https://www.youtube.com/@Abc?sub_confirmation=1", fresh2

        # ── file JSON hỏng: vẫn bỏ qua, nhưng PHẢI báo tên ra ngoài ──
        # Bỏ qua im lặng = nói dối: kênh vắng khỏi board thì user tưởng nó đã bị xoá và đi
        # extract lại (tốn quota YouTube) cho thứ vẫn nằm nguyên trên đĩa.
        (common.profiles_dir() / "vo-hieu-x-99.json").write_text('{"channel": "Hỏng"',
                                                                 encoding="utf-8")
        errs: list = []
        got = all_profiles(errs)
        assert all(p["slug"] != "vo-hieu-x-99" for p in got), got      # vẫn bỏ qua
        assert [e["file"] for e in errs] == ["vo-hieu-x-99.json"], errs  # nhưng có báo
        assert errs[0]["kind"] == "kênh" and errs[0]["error"], errs
        assert all_profiles() and len(all_profiles(None)) == len(got)   # không truyền list vẫn chạy
        (common.profiles_dir() / "vo-hieu-x-99.json").unlink()

    # ── fold_runs: mỗi TẬP một dòng, không phải mỗi lần bấm một dòng ──
    def _r(run, created, ep="", code="", url="", exp=""):
        return {"run": run, "created": created, "episode": ep, "code": code,
                "main_url": url, "exported_at": exp}

    # 3 lần sinh của cùng 1 tập → 1 dòng, giữ nội dung bản mới nhất
    f = fold_runs([_r("r3", "2026-07-31T10:00", ep="fin", code="LI-01"),
                   _r("r2", "2026-07-30T10:00", ep="fin", code="LI-01"),
                   _r("r1", "2026-07-29T10:00", ep="fin", code="LI-01")])
    assert len(f) == 1 and f[0]["run"] == "r3" and f[0]["n_runs"] == 3, f
    assert [o["run"] for o in f[0]["older"]] == ["r2", "r1"], f      # bản cũ không bị vứt

    # HAI TẬP KHÁC NHAU TRÙNG MÃ → phải là 2 dòng. Gộp theo `code` là nuốt mất một tập.
    f = fold_runs([_r("a", "2026-07-31T10:00", ep="tap-x", code="AMZ07"),
                   _r("b", "2026-07-30T10:00", ep="tap-y", code="AMZ07")])
    assert len(f) == 2, f

    # Run không thuộc tập nào: cùng video dán 2 dạng URL vẫn là MỘT dòng
    f = fold_runs([_r("u2", "2026-07-31T10:00", url="https://youtu.be/hWuYpfAM8TY"),
                   _r("u1", "2026-07-30T10:00", url="https://www.youtube.com/watch?v=hWuYpfAM8TY&t=3s")])
    assert len(f) == 1 and f[0]["n_runs"] == 2, f
    # …nhưng video KHÁC thì không được gộp
    assert len(fold_runs([_r("v1", "2026-07-31T10:00", url="https://youtu.be/AAAAAAAAAAA"),
                          _r("v2", "2026-07-30T10:00", url="https://youtu.be/BBBBBBBBBBB")])) == 2

    # Không tập, không URL → mỗi run một dòng (không có gì chứng minh chúng cùng việc)
    assert len(fold_runs([_r("x", "2026-07-31T10:00"), _r("y", "2026-07-30T10:00")])) == 2

    # ── ngày xuất phải là của CHÍNH bản đang hiện, không mượn của bản khác ──
    # bản mới chưa xuất, bản cũ đã xuất → ô ngày xuất phải TRỐNG (dòng nói "chưa xuất"),
    # ngày của bản cũ chỉ nằm ở `prev_export` để board hiện làm ngữ cảnh.
    f = fold_runs([_r("n2", "2026-07-31T10:00", ep="e"),
                   _r("n1", "2026-07-30T10:00", ep="e", exp="2026-07-30T11:00")])
    assert f[0]["exported_at"] == "" and f[0]["prev_export"] == "2026-07-30T11:00", f
    # bản mới CHÍNH LÀ bản đã xuất → ngày của chính nó
    f = fold_runs([_r("m2", "2026-07-31T10:00", ep="e", exp="2026-07-31T12:00"),
                   _r("m1", "2026-07-30T10:00", ep="e", exp="2026-07-30T11:00")])
    assert f[0]["exported_at"] == "2026-07-31T12:00", f
    # mở BẢN CŨ rồi xuất SAU: dòng vẫn phải mang ngày xuất của bản mới, KHÔNG phải 20:00
    # của bản cũ — nếu không, ô ngày xuất lại tả một nội dung khác với cột Tiêu đề.
    f = fold_runs([_r("k2", "2026-07-31T10:00", ep="e", exp="2026-07-31T10:30"),
                   _r("k1", "2026-07-30T10:00", ep="e", exp="2026-07-31T20:00")])
    assert f[0]["exported_at"] == "2026-07-31T10:30", f
    assert f[0]["prev_export"] == "2026-07-31T20:00", f
    # chưa xuất lần nào → cả hai đều rỗng
    f = fold_runs([_r("z1", "2026-07-31T10:00", ep="e"), _r("z0", "2026-07-30T10:00", ep="e")])
    assert f[0]["exported_at"] == "" and f[0]["prev_export"] == "", f
    # KHÔNG BAO GIỜ có ngày xuất SỚM HƠN ngày tạo của chính dòng đó (dấu hiệu ghép nhầm bản)
    for row in fold_runs([_r("p2", "2026-07-31T00:49", ep="e"),
                          _r("p1", "2026-07-31T00:20", ep="e", exp="2026-07-31T00:37")]):
        assert not row["exported_at"] or row["exported_at"] >= row["created"], row

    # caller đưa vào SAI THỨ TỰ vẫn phải lấy đúng bản mới nhất làm đại diện
    f = fold_runs([_r("old", "2026-07-01T10:00", ep="e"), _r("new", "2026-07-31T10:00", ep="e")])
    assert f[0]["run"] == "new", f
    assert fold_runs([]) == []

    # ── title_index: gộp theo MẶT CHỮ, giữ run MỚI NHẤT, bỏ title rỗng ──────────────────
    import json as _json
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        _old = common.RUNS
        common.RUNS = Path(_td) / "runs"
        try:
            def _mk(name, created, titles, prof=""):
                d = common.RUNS / name
                d.mkdir(parents=True)
                (d / "result.json").write_text(_json.dumps(
                    {"created": created, "profile": prof,
                     "titles": [{"text": t} for t in titles]}),
                    encoding="utf-8")

            def _mk_ep(name, created, pairs):
                """Run chế độ episode: mỗi kênh MỘT title (khác chế độ 1 kênh: ×3 của cùng kênh)."""
                d = common.RUNS / name
                d.mkdir(parents=True)
                (d / "result.json").write_text(_json.dumps(
                    {"created": created, "mode": "episode",
                     "channels": [{"slug": s, "title": {"text": t}} for s, t in pairs]}),
                    encoding="utf-8")
            _mk("r1", "2026-07-30T10:00:00+07:00", ["ALPHA", "BETA"], prof="kenh-a")
            _mk("r2", "2026-07-31T10:00:00+07:00", ["ALPHA", ""], prof="kenh-a")   # trùng + một bản rỗng
            _mk("r3", "2026-07-29T10:00:00+07:00", ["ALPHA"])       # KHÔNG khai profile
            idx = title_index()
            by = {x["text"]: x for x in idx}
            assert set(by) == {"ALPHA", "BETA"}, by       # title RỖNG không được vào tìm kiếm
            assert by["ALPHA"]["uses"] == 3, by           # 3 run dùng → MỘT dòng, đếm 3
            assert by["ALPHA"]["run"] == "r2", by         # giữ run MỚI NHẤT, không phải run đầu gặp
            assert by["BETA"]["uses"] == 1, by
            assert [x["text"] for x in idx] == ["ALPHA", "BETA"], idx   # mới nhất lên trước
            # `channels` là thứ board dựa vào để lọc theo THỊ TRƯỜNG — thiếu nó thì đứng ở
            # SPAIN gõ tìm vẫn ra title của kênh US (bug user bắt được 2026-08-02).
            assert by["ALPHA"]["channels"] == ["kenh-a"], by   # run r3 không khai profile → không đẻ mục rỗng
            assert by["BETA"]["channels"] == ["kenh-a"], by

            # Run không quy được về kênh nào ⇒ `channels` RỖNG. Đây là "chưa đo được", KHÔNG
            # phải "không thuộc kênh nào" — board phải cho những dòng này qua bộ lọc.
            _mk("r4", "2026-08-01T10:00:00+07:00", ["MO COI"])
            assert {x["text"]: x for x in title_index()}["MO COI"]["channels"] == []

            # Chế độ episode: title phải quy về ĐÚNG kênh của nó, không phải kênh đầu danh sách.
            _mk_ep("r5", "2026-08-02T10:00:00+07:00",
                   [("kenh-b", "TITLE B"), ("kenh-c", "TITLE C"), ("kenh-d", "")])
            by2 = {x["text"]: x for x in title_index()}
            assert by2["TITLE B"]["channels"] == ["kenh-b"], by2
            assert by2["TITLE C"]["channels"] == ["kenh-c"], by2
            assert "" not in by2                          # kênh không sinh được title → bỏ hẳn

            # Cùng một title dùng ở NHIỀU kênh → gom ĐỦ, không chỉ giữ kênh gặp đầu tiên:
            # thiếu kênh nào là title đó vắng mặt oan ở thị trường của kênh ấy.
            _mk_ep("r6", "2026-08-02T11:00:00+07:00", [("kenh-b", "CHUNG"), ("kenh-c", "CHUNG")])
            _mk("r7", "2026-08-02T12:00:00+07:00", ["CHUNG"], prof="kenh-a")
            ch = {x["text"]: x for x in title_index()}["CHUNG"]
            assert sorted(ch["channels"]) == ["kenh-a", "kenh-b", "kenh-c"], ch
            assert ch["uses"] == 3, ch
        finally:
            common.RUNS = _old
    assert title_index.__doc__

    print("library.py self-test OK - niche group, giu user fields (ke ca list) khi re-extract, lich su run · sub_url tu them duoi · fold_runs gop theo TAP · title_index gop theo mat chu")
