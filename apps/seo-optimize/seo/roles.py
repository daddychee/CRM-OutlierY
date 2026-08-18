"""Bốn vai + phân quyền (user chốt 2026-08-02, tinh chỉnh lần 2).

**Chặn ở SERVER, không chặn ở board.** Ẩn nút đi mà endpoint vẫn nhận thì đó là bảo mật giả:
ai mở DevTools gõ một dòng `fetch` là qua. Board ẩn nút chỉ để đỡ vướng mắt — mọi quyết định
thật nằm ở đây và ở `server.PERM_OF`.

**BA trục, đừng gộp:**
  · **VAI** trả lời *"được LÀM gì"*
  · **THỊ TRƯỜNG** trả lời *"trên vùng dữ liệu nào"* (Leader/Seo)
  · **KÊNH ĐƯỢC GIAO** trả lời *"được GHI lên kênh nào"* — **chỉ chặn GHI, KHÔNG chặn ĐỌC**

**Vì sao ĐỌC và GHI tách nhau ở trục kênh (user đảo quyết định 2026-08-02):** ban đầu Seo bị
ẩn luôn kênh của người khác. Đo lại thấy hai điều: (1) ẩn không kín — title/description của
kênh khác vẫn lộ qua `title-index`, `runs?profile=`, `result?run=`; (2) thẻ TẬP in
*"kênh đã bị xoá"* cho kênh **vẫn còn nguyên**, tức board nói dối. Quan trọng hơn cả hai: cả
tool này sinh ra để **né trùng metadata khi re-up**, mà Seo không thấy kênh anh em thì không
có cách nào tra title mình sắp dùng đã bị kênh khác dùng chưa. Rủi ro thật là **sửa nhầm**,
không phải bảo mật — nên khoá GHI, mở ĐỌC.

**Vì sao tách `bank` khỏi `bank_del`:** user chốt Seo *"có thể nhập vào để làm giàu kho nhưng
không được xoá"* — hai nửa của cùng một endpoint; nhét chung vào `edit` thì không diễn tả
được, mà nới `edit` cho Seo là cho luôn quyền xoá kho.

Không LLM, không quota, thuần stdlib.
"""
from __future__ import annotations

# Thứ tự = từ cao xuống thấp. `owner` phải đứng đầu.
# `viewer` thêm 2026-08-04 (user chốt qua OUTLIERY): vai CHỈ-ĐỌC cho SSO — luật
# thường quy "Manager bộ phận khác chỉ XEM ngang nhau". Trước đó header viewer
# rơi về DEFAULT `seo` nên "chỉ xem" vẫn sinh metadata/nạp Format được (tốn
# token + quota của bộ phận chủ quản) — đó là lỗ, không phải chủ đích.
ROLES = ("owner", "manager", "leader", "seo", "viewer")

VN = {"owner": "Owner — chủ, toàn quyền + quản tài khoản",
      "manager": "Manager — toàn quyền vận hành, mọi thị trường",
      "leader": "Leader — phụ trách thị trường được giao; xoá kho được, xoá kênh/thị trường thì không",
      "seo": "Seo — tự thêm kênh của mình và làm CHỦ kênh đó; sửa/sinh trên kênh mình tạo; "
             "thêm vào kho được, xoá thì không",
      "viewer": "Viewer — chỉ xem (Manager bộ phận khác qua SSO); không sinh, không thêm, "
                "không tốn token/quota"}

PERMS = ("view", "generate", "extract_chan", "extract", "fmt_del", "edit", "bank", "bank_del",
         "market", "restore", "delete", "audit", "chan_owner", "users")
PERM_VN = {
    "view": "xem dữ liệu trong thị trường của mình",
    "generate": "sinh metadata + xuất file (tốn token LLM)",
    # HAI VIỆC KHÁC NHAU, tách ra sau khi user chốt 2026-08-02: *"cập nhật thêm vai trò của
    # SEO, họ có thể tự nhập thêm kênh họ vào"*.
    #   · `extract_chan` = dựng hồ sơ KÊNH CỦA MÌNH. Ai cũng cần, kể cả Seo — không có nó thì
    #     Seo không bao giờ tạo được kênh, mà luật ghi lại đòi phải là CHỦ kênh mới sửa được
    #     ⇒ Seo bị khoá khỏi mọi kênh và phải đi xin bàn giao từng cái.
    #   · `extract` = dựng FORMAT từ kênh ĐỐI THỦ. Đây mới là chỗ user lo *"lỡ bấm là đốt
    #     quota cả nhóm"*: nó tốn ~2 call LLM và là dữ liệu DÙNG CHUNG cho cả niche.
    # Gộp một quyền thì hoặc Seo mất cả hai (đúng bế tắc cũ), hoặc được cả hai (mất luôn
    # hàng rào quota mà user đã cân nhắc). Cùng khuôn với `bank` / `bank_del`.
    "extract_chan": "thêm KÊNH CỦA MÌNH từ URL YouTube (~4 unit quota + 1 call LLM)",
    "extract": "nạp FORMAT từ kênh đối thủ (~5 unit quota + 2 call LLM, dùng chung cả niche)",
    # XOÁ FORMAT tách khỏi `delete` (user chốt 2026-08-02): *"tất cả các cấp đều được nhập vào
    # Format kênh, nhưng khi xoá ở bảng thống kê này thì chỉ từ cấp Leader trở lên"*.
    # Không mâu thuẫn với luật *"Leader không xoá được KÊNH"*: kênh giữ thứ user gõ tay
    # (link/CTA, sub_url, mã tập) mất là không dựng lại được; Format thì chỉ là số liệu
    # harvest từ YouTube, nạp lại một lượt là có — mất mát đo được bằng quota, không phải
    # bằng công gõ. Nên hai thứ đáng hai mức khác nhau.
    "fmt_del": "XOÁ Format khỏi bảng thống kê kênh đối thủ",
    "edit": "sửa thông tin kênh · tập",
    "bank": "THÊM title / công thức / Text on Thumb vào kho niche",
    "bank_del": "XOÁ mục khỏi kho niche",
    "market": "tạo / sửa thị trường",
    # KHÔI PHỤC ≠ XOÁ — hai quyền riêng, user chốt 2026-08-02. Khôi phục là CỨU dữ liệu, và
    # thứ đáng sợ nhất khi xoá nhầm là phải đợi người có quyền. Còn `delete` vẫn giữ nguyên
    # mức cũ vì nó gồm cả **dọn thùng rác** (`purge`) — thao tác DUY NHẤT không lấy lại được.
    "restore": "khôi phục mục vừa xoá nhầm (thùng rác 24h)",
    "delete": "xoá kênh · format · tập · thị trường (+ dọn hẳn thùng rác)",
    "audit": "xem nhật ký ai làm gì",
    "users": "thêm/khoá tài khoản, đổi vai",
    "chan_owner": "gán / đổi CHỦ của một kênh (ai được sửa kênh đó)",
}

_GRANT: dict[str, set[str]] = {
    "owner":   set(PERMS),
    # Manager: mọi thứ vận hành, KHÔNG quản tài khoản.
    "manager": {"view", "generate", "extract_chan", "extract", "fmt_del", "edit", "bank",
                "bank_del", "market", "restore", "delete", "audit", "chan_owner"},
    # Leader: nhìn được TOÀN BỘ kênh (user: "để nhìn thấy tổng thể thì từ cấp Leader trở lên"),
    # XOÁ ĐƯỢC KHO niche, nhưng KHÔNG xoá được kênh/format/tập/thị trường — user chốt
    # "không được xoá thị trường, chỉ có từ cấp quản lý trở lên".
    # Leader KHÔNG còn `audit` (user chốt 2026-08-02: *"check history riêng của từng tài
    # khoản thì chỉ owner và manager xem được"*). Nhật ký lộ việc của NGƯỜI KHÁC, kể cả
    # người ngang cấp — đó là thông tin quản lý, không phải dữ liệu công việc.
    # Leader: user chốt 2026-08-02 — được **đổi chủ kênh** (`chan_owner`) và được **khôi
    # phục** thứ xoá nhầm (`restore`), nhưng VẪN không được xoá. Ranh giới giữ nguyên tinh
    # thần cũ: cứu được, không phá được.
    "leader":  {"view", "generate", "extract_chan", "extract", "fmt_del", "edit", "bank",
                "bank_del", "market", "restore", "chan_owner"},
    # Seo (chốt lại 2026-08-02, sau hai lần nới):
    #  · XEM mọi kênh trong thị trường — để tra title mình sắp dùng đã bị kênh khác dùng chưa.
    #  · TỰ THÊM KÊNH CỦA MÌNH và làm CHỦ kênh đó ⇒ sửa/sinh được ngay, không phải xin bàn giao.
    #  · NẠP được Format đối thủ (*"cấp thêm cho cả SEO có quyền được add vào"*) — đổi lại có
    #    chốt CHỐNG TRÙNG LINK ở `niche_format.extract`, để hai người không nạp trùng một kênh
    #    rồi cùng tiêu quota cho một thứ.
    #  · KHÔNG xoá gì cả: không `fmt_del`, không `bank_del`, không `delete`.
    "seo":     {"view", "generate", "extract_chan", "extract", "edit", "bank"},
    # Viewer: CHỈ view. Cố ý không có `generate`/`extract*`/`edit`/`bank` — vai này
    # sinh ra để "xem ngang nhau" không thành "đốt tài nguyên của bộ phận khác".
    "viewer":  {"view"},
}

# Vai bị giới hạn theo THỊ TRƯỜNG (áp cho cả ĐỌC lẫn GHI).
SCOPED = frozenset({"leader", "seo"})
# ── GHI LÊN KÊNH = CHỦ KÊNH, không phải "được giao" (user chốt 2026-08-02, ĐẢO luật cũ) ──
# Nguyên văn: *"cho SEO xem profile của account SEO khác cũng được nhưng không được sửa… Chỉ
# những tài khoản SEO nào tự tạo ra kênh thì mới chỉnh sửa được, KỂ CẢ LEADER, trừ manager +
# owner"*. Tức cơ sở của quyền ghi chuyển từ **một field trên TÀI KHOẢN** (`users.channels`)
# sang **một field trên KÊNH** (`profile.created_by`).
# Vì sao đổi lại quan trọng chứ không chỉ là đổi chỗ đọc: bản cũ, ai có quyền `users` cũng
# giao thêm kênh cho một người là họ sửa được ngay; bản mới, chủ kênh là **thuộc tính của
# kênh**, đổi nó là một hành động riêng có tên và có ghi nhật ký (`chan_owner`).
CREATOR_ONLY = frozenset({"leader", "seo"})
# Vai được gán "kênh đang phụ trách" trong form tài khoản. Ô đó **CHỈ để theo dõi** (nuôi số
# `cầm` ở Tổng quan), **KHÔNG còn cấp quyền ghi** kể từ 2026-08-02 — nhãn trên giao diện phải
# nói đúng điều đó, không thì nó là một cái nút hứa suông.
ASSIGNABLE = frozenset({"seo"})
CHAN_SCOPED = CREATOR_ONLY          # tên cũ, giữ để chỗ gọi ngoài không gãy
# Trục ĐỌC của màn Tổng quan. CỐ Ý tách khỏi `CREATOR_ONLY`: xem và sửa là hai câu hỏi khác
# nhau, gộp lại là mỗi lần đổi luật ghi thì màn hình xem cũng đổi theo mà không ai để ý.
OVERVIEW_SCOPED = frozenset({"seo"})
# Vai bị giới hạn theo NICHE (user chốt 2026-08-02: *"leader sẽ được biết đối với những niche
# họ đang phụ trách — do manager hoặc owner cấp quyền niche"*). Rỗng = mọi niche, cùng luật
# với thị trường: chưa gom nhóm ≠ cấm. Seo KHÔNG bị giới hạn theo niche — giao KÊNH đã đủ hẹp,
# thêm một trục nữa chỉ tạo chỗ để cấu hình mâu thuẫn với chính nó.
NICHE_SCOPED = frozenset({"leader"})

# Thiếu/lạ rơi về vai THẤP NHẤT, không phải cao nhất. Từ 2026-08-04 thấp nhất là
# `viewer` (chỉ-đọc) — fail-closed đúng nghĩa: vai gõ sai/không biết thì chỉ xem,
# không âm thầm được quyền ghi như thời DEFAULT="seo".
DEFAULT = "viewer"


def norm(role: str) -> str:
    r = (role or "").strip().lower()
    return r if r in _GRANT else DEFAULT


def perms(role: str) -> set[str]:
    return set(_GRANT[norm(role)])


def can(role: str, perm: str) -> bool:
    return perm in _GRANT[norm(role)]


def is_scoped(role: str) -> bool:
    return norm(role) in SCOPED


def scope_markets(user: dict) -> list[str] | None:
    """Thị trường người này được vào. `None` = không giới hạn.

    Vai không bị giới hạn → `None`. Vai bị giới hạn mà **chưa gán thị trường nào** → cũng
    `None`. Khác hẳn cách xử lý KÊNH bên dưới, và khác có chủ đích: thị trường là cách gom
    nhóm, chưa gom thì không có nghĩa là cấm.
    """
    if not is_scoped(user.get("role", "")):
        return None
    ms = [str(m).strip() for m in (user.get("markets") or []) if str(m).strip()]
    return ms or None


def in_scope(user: dict, market_name: str) -> bool:
    ms = scope_markets(user)
    return True if ms is None else (market_name or "") in ms


def scope_niches(user: dict) -> list[str] | None:
    """Niche người này phụ trách. `None` = mọi niche."""
    if norm(user.get("role", "")) not in NICHE_SCOPED:
        return None
    ns = [str(x).strip() for x in (user.get("niches") or []) if str(x).strip()]
    return ns or None


def in_niche(user: dict, niche: str) -> bool:
    ns = scope_niches(user)
    return True if ns is None else (niche or "").strip() in ns


def owns_channel(user: dict, prof: dict) -> bool:
    """Người này có phải CHỦ của kênh đó không (`profile.created_by`).

    So không phân biệt hoa/thường vì tên đăng nhập cũng so như vậy — nếu không thì đổi cách
    gõ hoa là mất quyền trên chính kênh mình tạo, mà chẳng có thông báo nào giải thích.
    """
    who = (user.get("name") or "").strip().lower()
    return bool(who) and (prof.get("created_by") or "").strip().lower() == who


def can_write_profile(user: dict, prof: dict | None) -> bool:
    """Được GHI LÊN kênh này không? Owner/Manager: mọi kênh. Leader/Seo: chỉ kênh MÌNH tạo."""
    if norm(user.get("role", "")) not in CREATOR_ONLY:
        return True
    return owns_channel(user, prof or {})


def write_channels(user: dict, profs: list[dict] | None = None) -> list[str] | None:
    """Slug các kênh người này được GHI LÊN. `None` = mọi kênh (Owner/Manager).

    **CHỈ CHẶN GHI.** Đọc thì lọc theo thị trường thôi — xem ghi chú đầu file: Seo vẫn XEM
    được kênh của mọi người, vì cả tool sinh ra để né trùng metadata, mà không thấy kênh anh
    em thì không tra được title mình sắp dùng đã bị dùng chưa.

    **KÊNH KHÔNG AI ĐỨNG TÊN (`created_by` rỗng) THÌ KHÔNG AI DƯỚI MANAGER SỬA ĐƯỢC.** Đây
    KHÔNG phải lỗi mà là hệ quả trực tiếp của luật; nhưng nó im lặng nên board **bắt buộc**
    phải nói ra và chỉ đường (Leader trở lên gán chủ bằng `chan_owner`). Kênh tạo trước
    02/08/2026 đều rơi vào diện này.
    """
    if norm(user.get("role", "")) not in CREATOR_ONLY:
        return None
    return [str(p.get("slug") or "") for p in (profs or []) if owns_channel(user, p)]


def overview_channels(user: dict) -> list[str] | None:
    """Kênh người này được THẤY trên màn Tổng quan. `None` = mọi kênh trong phạm vi.

    **TRỤC ĐỌC, KHÁC HẲN TRỤC GHI — đừng dùng `write_channels` cho việc này.** Hai trục từng
    trùng nhau một cách tình cờ (chỉ Seo bị giới hạn, và giới hạn theo cùng một danh sách),
    nên bản đầu dùng chung hàm. Đến khi luật ghi đổi sang CHỦ KÊNH thì Leader lọt vào diện
    hạn chế GHI và **mất sạch màn Tổng quan** — đo được: leader thấy 0 kênh thay vì 2.

    Ai thấy gì (user chốt 2026-08-02): *"leader được biết đối với những niche họ đang phụ
    trách… còn SEO chỉ biết được họ đang cầm bao nhiêu kênh, trong niche và thị trường nào"*.
    ⇒ Leader lọc bằng THỊ TRƯỜNG ∩ NICHE (làm ở tầng trên), không lọc theo kênh.
      Seo lọc bằng kênh ĐANG CẦM (`users.channels`) — con số "cầm", không phải "tạo".
    """
    if norm(user.get("role", "")) not in OVERVIEW_SCOPED:
        return None
    return [str(c).strip() for c in (user.get("channels") or []) if str(c).strip()]


def can_write_channel(user: dict, slug: str, profs: list[dict] | None = None) -> bool:
    """Dạng tra theo SLUG — cần `profs` để biết ai là chủ. Thiếu `profs` thì coi như không tra
    được chủ ⇒ **từ chối** với vai bị giới hạn (thà chặn oan còn hơn cho ghi nhầm kênh)."""
    if norm(user.get("role", "")) not in CREATOR_ONLY:
        return True
    for p in (profs or []):
        if str(p.get("slug") or "") == (slug or ""):
            return owns_channel(user, p)
    return False


# Tên cũ, giữ để không gãy chỗ gọi ngoài.
scope_channels = write_channels
sees_channel = can_write_channel


def matrix() -> list[dict]:
    """Bảng "vai nào được làm gì" cho giao diện + CLI. Dựng TỪ `_GRANT`, không chép tay —
    chép tay là có ngày bảng hiện lên một đằng, server chặn một nẻo."""
    return [{"perm": p, "label": PERM_VN[p],
             "roles": {r: (p in _GRANT[r]) for r in ROLES}} for p in PERMS]


def describe(role: str) -> dict:
    r = norm(role)
    return {"role": r, "label": VN[r], "perms": sorted(_GRANT[r]),
            "scoped": r in SCOPED, "chan_scoped": r in CREATOR_ONLY,
            "assignable": r in ASSIGNABLE,
            "niche_scoped": r in NICHE_SCOPED,
            "perm_labels": {p: PERM_VN[p] for p in sorted(_GRANT[r])}}


if __name__ == "__main__":                                  # self-test offline
    assert set(_GRANT) == set(ROLES)
    for r, ps in _GRANT.items():
        assert ps <= set(PERMS), (r, ps - set(PERMS))
        assert VN.get(r), r
    assert set(PERM_VN) == set(PERMS)

    # Owner là tập cha; ROLES giảm dần và không vai nào trùng vai nào
    for r in ROLES:
        assert _GRANT[r] <= _GRANT["owner"], r
    for a, b in zip(ROLES, ROLES[1:]):
        assert _GRANT[b] < _GRANT[a], f"{b} phải là tập con THẬT SỰ của {a}"

    # ── ĐÚNG NHỮNG GÌ USER CHỐT ────────────────────────────────────────────────────
    # 1. Leader KHÔNG xoá được thị trường (và không xoá được kênh/format/tập)
    assert not can("leader", "delete"), "Leader không được có quyền xoá"
    assert can("manager", "delete") and can("owner", "delete")
    # 2. Seo THÊM được vào kho nhưng KHÔNG xoá; Leader trở lên mới xoá kho
    assert can("seo", "bank") and not can("seo", "bank_del")
    for r in ("leader", "manager", "owner"):
        assert can(r, "bank_del"), r
    # 3. Seo GHI được trên kênh được giao; Leader trở lên ghi được mọi kênh
    # GHI = CHỦ KÊNH (đảo luật 2026-08-02): Leader cũng bị giới hạn, chỉ Manager/Owner tự do.
    assert CREATOR_ONLY == {"seo", "leader"}, CREATOR_ONLY
    assert not (CREATOR_ONLY & {"manager", "owner"}), "Manager/Owner phải sửa được mọi kênh"
    # 4. Seo TỰ THÊM ĐƯỢC KÊNH CỦA MÌNH (user chốt 2026-08-02, đảo luật cũ), nhưng vẫn không
    #    dựng Format đối thủ và không tạo/sửa thị trường.
    assert can("seo", "extract_chan"), "Seo phải tự thêm được kênh của mình"
    # NẠP Format: user chốt 2026-08-02 cho cả Seo. Hàng rào chuyển từ "cấm bấm" sang "chống
    # trùng link" — xem `niche_format.extract`.
    assert can("seo", "extract"), "Seo phải nạp được Format đối thủ"
    # ...nhưng XOÁ Format thì từ Leader trở lên. Hai vế phải đi cùng nhau, đừng sửa lẻ một vế.
    assert not can("seo", "fmt_del"), "Seo KHÔNG xoá được Format"
    for r in ("leader", "manager", "owner"):
        assert can(r, "fmt_del"), r
    # Leader xoá được FORMAT nhưng vẫn KHÔNG xoá được KÊNH — cả điểm của việc tách `fmt_del`.
    assert can("leader", "fmt_del") and not can("leader", "delete")
    assert not can("seo", "market")
    assert can("leader", "extract") and can("leader", "market")
    # Ai cũng phải thêm được kênh của mình — không thì vai đó không bao giờ làm chủ kênh nào,
    # mà quyền GHI lại buộc phải là chủ kênh ⇒ tự khoá mình ra ngoài.
    # TRỪ viewer (2026-08-04): vai chỉ-đọc KHÔNG BAO GIỜ làm chủ kênh — đó là chủ đích.
    for r in ROLES:
        if r != "viewer":
            assert can(r, "extract_chan"), r
    assert not can("viewer", "extract_chan"), "viewer là chỉ-đọc, không tự thêm kênh"
    # Chỉ owner quản tài khoản
    assert [r for r in ROLES if can(r, "users")] == ["owner"]
    # XEM nhật ký: owner + manager, KHÔNG có leader/seo
    assert [r for r in ROLES if can(r, "audit")] == ["owner", "manager"],         [r for r in ROLES if can(r, "audit")]
    # KHÔNG VAI NÀO XOÁ ĐƯỢC nhật ký — user chốt 2026-08-02. Nhật ký mà người trong hệ thống
    # xoá được thì mất phần lớn giá trị: chỗ đáng tra nhất chính là lúc có người muốn xoá nó.
    assert "audit_del" not in PERMS, "đừng thêm lại quyền xoá nhật ký"
    # Ai cũng XEM được; sinh + sửa là việc của vai LÀM (viewer chỉ-đọc đứng ngoài)
    for r in ROLES:
        assert can(r, "view"), r
        if r != "viewer":
            assert can(r, "generate") and can(r, "edit"), r
    # Viewer đúng một quyền `view` — thêm quyền nào vào đây là phá chủ đích của vai
    assert perms("viewer") == {"view"}, perms("viewer")

    # Vai lạ rơi về THẤP nhất — từ 2026-08-04 là `viewer` (chỉ-đọc, fail-closed thật)
    assert norm("") == "viewer" and norm("admin") == "viewer" and norm("OWNER") == "owner"
    assert norm("viewer") == "viewer"
    # `extract` ĐÃ RỜI danh sách này (2026-08-02): nay Seo cũng nạp được Format, mà vai lạ rơi
    # về `seo` ⇒ để nguyên là bài kiểm đỏ cho một luật đã đổi. Thay bằng `fmt_del`.
    for p in ("delete", "bank_del", "users", "fmt_del", "market", "audit"):
        assert not can("vai-bia-dat", p), p

    # ── PHẠM VI: kênh và thị trường xử lý KHÁC NHAU, có chủ đích ────────────────────
    _P = [{"slug": "a", "created_by": "an"}, {"slug": "b", "created_by": "Bình"},
          {"slug": "cu", "created_by": ""}]                      # kênh cũ: không ai đứng tên
    assert write_channels({"role": "manager", "name": "m"}, _P) is None, "manager ghi mọi kênh"
    assert write_channels({"role": "owner", "name": "o"}, _P) is None
    # Leader NAY cũng bị giới hạn — đây là phần đảo luật, phải có ca chốt riêng
    assert write_channels({"role": "leader", "name": "an"}, _P) == ["a"], "leader chỉ kênh mình tạo"
    assert write_channels({"role": "seo", "name": "an"}, _P) == ["a"]
    assert write_channels({"role": "seo", "name": "AN"}, _P) == ["a"], "tên so không phân biệt hoa"
    assert write_channels({"role": "seo", "name": "bình"}, _P) == ["b"]
    assert write_channels({"role": "seo", "name": "nguoi-la"}, _P) == [], "không tạo gì thì không sửa gì"
    # KÊNH KHÔNG AI ĐỨNG TÊN: không ai dưới Manager sửa được — hệ quả của luật, không phải lỗi
    for r in ("seo", "leader"):
        assert not can_write_channel({"role": r, "name": "an"}, "cu", _P), r
    assert can_write_channel({"role": "manager", "name": "m"}, "cu", _P)
    # Thiếu danh sách kênh = không tra được chủ ⇒ CHẶN, đừng cho qua
    assert not can_write_channel({"role": "seo", "name": "an"}, "a"), "thiếu profs thì phải chặn"
    assert can_write_channel({"role": "owner", "name": "o"}, "a")
    # `users.channels` KHÔNG còn cấp quyền ghi (đây chính là thứ vừa đổi)
    assert write_channels({"role": "seo", "name": "an", "channels": ["a", "b", "cu"]}, _P) == ["a"], \
        "được giao kênh KHÔNG còn nghĩa là sửa được"
    # TỔNG QUAN đọc theo trục RIÊNG: Leader phải thấy cả niche mình phụ trách, không phải
    # chỉ kênh mình tạo (bug đã đo: leader thấy 0 kênh khi hai trục dùng chung một hàm).
    assert overview_channels({"role": "leader", "name": "an", "channels": []}) is None, \
        "leader XEM được cả niche phụ trách, không bó theo kênh mình tạo"
    assert overview_channels({"role": "manager"}) is None
    assert overview_channels({"role": "seo", "name": "an", "channels": ["x", "y"]}) == ["x", "y"], \
        "Seo xem theo kênh ĐANG CẦM, không theo kênh đã tạo"
    assert overview_channels({"role": "seo", "name": "an", "channels": []}) == []
    # ĐỔI CHỦ KÊNH: từ Leader trở lên (user chốt 2026-08-02, nới từ owner+manager)
    for r in ("owner", "manager", "leader"):
        assert can(r, "chan_owner"), r
    assert not can("seo", "chan_owner"), "Seo không đụng được vào việc phân quyền kênh"
    # PHÂN CÔNG ≠ XOÁ — user chốt 2026-08-02: *"leader và SEO sẽ không được xoá kênh phải
    # thông qua manager hoặc owner"*. Hai quyền này phải RỜI NHAU, đừng có ngày nào đó gộp
    # `chan_owner` vào `delete` cho gọn: giao kênh là việc hằng ngày của Leader, còn xoá kênh
    # là thứ 24h sau không lấy lại được.
    assert can("leader", "chan_owner") and not can("leader", "delete"), \
        "Leader phân công được mà vẫn không xoá được kênh"
    for r in ("leader", "seo"):
        assert not can(r, "delete"), f"{r} không được xoá kênh — phải qua Manager/Owner"
    # KHÔI PHỤC ≠ XOÁ: Leader CỨU được nhưng vẫn không PHÁ được
    for r in ("owner", "manager", "leader"):
        assert can(r, "restore"), r
    assert not can("seo", "restore"), "Seo không khôi phục"
    assert can("leader", "restore") and not can("leader", "delete"), \
        "Leader phải cứu được mà vẫn không xoá được — đây là cả điểm của việc tách hai quyền"
    # CHƯA TẠO KÊNH NÀO = KHÔNG SỬA ĐƯỢC KÊNH NÀO (rỗng là rỗng thật)...
    assert write_channels({"role": "seo", "name": "moi-vao"}, _P) == []
    # ...nhưng RỖNG = KHÔNG GIỚI HẠN với thị trường
    assert scope_markets({"role": "seo", "markets": []}) is None
    assert scope_markets({"role": "seo", "markets": ["US"]}) == ["US"]
    assert scope_markets({"role": "manager", "markets": ["US"]}) is None

    # ── Bảng hiển thị dựng TỪ _GRANT, không chép tay ────────────────────────────────
    m = matrix()
    assert len(m) == len(PERMS)
    for row in m:
        for r in ROLES:
            assert row["roles"][r] == can(r, row["perm"]), (row["perm"], r)
    # NICHE: chỉ Leader; rỗng = mọi niche (giống THỊ TRƯỜNG, khác KÊNH)
    assert scope_niches({"role": "leader", "niches": ["Space"]}) == ["Space"]
    assert scope_niches({"role": "leader", "niches": []}) is None
    assert scope_niches({"role": "owner", "niches": ["Space"]}) is None
    assert scope_niches({"role": "seo", "niches": ["Space"]}) is None,         "Seo giới hạn theo KÊNH, không theo niche"
    assert in_niche({"role": "leader", "niches": ["Space"]}, "Space")
    assert not in_niche({"role": "leader", "niches": ["Space"]}, "Life In")
    assert in_niche({"role": "manager", "niches": []}, "bat-ky")

    d = describe("seo")
    assert d["chan_scoped"] and "bank" in d["perms"] and "bank_del" not in d["perms"]
    print("roles.py self-test OK - leader khong xoa (ke ca thi truong), seo them kho nhung "
          "khong xoa kho, kenh chi chan GHI khong chan DOC, kenh RONG=RONG THAT con thi truong "
          "RONG=KHONG GIOI HAN, bang hien thi dung tu _GRANT")
