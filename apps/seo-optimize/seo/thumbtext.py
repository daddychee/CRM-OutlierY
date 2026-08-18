"""TEXT ON THUMB — chữ NẰM TRÊN ảnh thumbnail (không phải ảnh). Đo cách đối thủ đặt chữ,
gợi ý Text on Thumb cho video của mình.

Vì sao user dán tay: YouTube Data API chỉ trả URL ảnh, không trả chữ nằm TRÊN ảnh. Đọc được
thì phải dùng model vision (tốn ~1–2k token mỗi ảnh). User chốt 2026-07-29: **dán tay**, tool
chỉ cần đo và gợi ý — nên module này KHÔNG gọi LLM, KHÔNG tốn quota, chạy tức thì.

Ranh giới quen thuộc của dự án: Python đếm (số từ, IN HOA, có số không, trùng title bao nhiêu),
còn việc "chữ này hay hay dở" thì để mắt user quyết — tool không chấm điểm sáng tạo.
"""
from __future__ import annotations

import re

_WORD_RE = re.compile(r"[0-9A-Za-zÀ-ỹ][0-9A-Za-zÀ-ỹ'’.%-]*")
_NUM_RE = re.compile(r"\d")
# từ quá phổ thông thì đặt lên thumb vô nghĩa — dùng để chọn từ "nặng" trong title
_WEAK = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "is", "are", "was",
         "were", "this", "that", "it", "its", "with", "from", "you", "your", "what", "why", "how",
         "khi", "của", "và", "là", "có", "cho", "một", "những", "các", "được", "trong", "với"}

MAX_LINES = 40


def parse(raw: str) -> list[str]:
    """Khối text user dán → danh sách Text on Thumb, mỗi dòng 1 cái. Bỏ dòng rỗng/trùng."""
    out: list[str] = []
    for line in (raw or "").splitlines():
        s = " ".join(line.split()).strip(" -–—•|")
        if s and s not in out:
            out.append(s)
        if len(out) >= MAX_LINES:
            break
    return out


def words_of(s: str) -> list[str]:
    return _WORD_RE.findall(s or "")


def analyze(raw: str, titles: list[str] | None = None) -> dict:
    """Đo cách đối thủ đặt chữ trên thumb. `titles` để tính mức trùng lặp với tiêu đề."""
    lines = parse(raw)
    if not lines:
        return {}
    tw = [words_of(s) for s in lines]
    n = len(lines)
    counts = [len(w) for w in tw]
    chars = [len(s) for s in lines]
    caps = sum(1 for s in lines if s.upper() == s and any(c.isalpha() for c in s))
    nums = sum(1 for s in lines if _NUM_RE.search(s))
    # trùng title: so từng dòng thumb với title cùng vị trí (user dán theo đúng thứ tự video)
    # Ghép thumb↔title theo CHỈ SỐ chỉ đúng khi 2 danh sách cùng độ dài. `parse()` bỏ dòng
    # rỗng/trùng, và số video mẫu có thể khác số dòng user dán → lệch 1 dòng là mọi dòng sau
    # so nhầm title. Lệch thì so với TOÀN BỘ title (biết có lặp hay không, chỉ mất phần "lặp
    # title nào") — thà kém chi tiết còn hơn ra số sai.
    tl = [t for t in (titles or []) if (t or "").strip()]
    aligned = len(tl) == len(lines)
    tset = [{w.lower() for w in words_of(t)} for t in tl]
    allw = set().union(*tset) if tset else set()
    overlap = 0
    for i, w in enumerate(tw):
        ref = tset[i] if (aligned and i < len(tset)) else allw
        if not ref:
            continue
        share = {x.lower() for x in w} & ref
        if len(share) >= max(1, len(w) // 2):              # quá nửa số từ trùng title = lặp lại title
            overlap += 1
    return {
        "n": n,
        "words": {"avg": round(sum(counts) / n, 1), "range": [min(counts), max(counts)]},
        "chars": {"avg": round(sum(chars) / n), "range": [min(chars), max(chars)]},
        "all_caps": caps, "with_number": nums, "repeat_title": overlap,
        # `aligned=False` nghĩa là "repeat_title" so với TOÀN BỘ title chứ không theo cặp —
        # số vẫn đúng nhưng thô hơn. Trả ra để board nói được, đừng để user tưởng đo theo cặp.
        "aligned": aligned,
        "samples": lines[:8],
    }


def rules(a: dict) -> list[str]:
    """Số đo → luật đặt chữ, viết bằng tiếng Việt. Thuần suy từ số, không phán đoán thêm."""
    if not a:
        return []
    n, w = a["n"], a["words"]
    out = [f"Độ dài: {w['avg']} từ/thumb (thấp nhất {w['range'][0]}, cao nhất {w['range'][1]}) "
           f"· {a['chars']['avg']} ký tự"]
    if a["all_caps"] >= n * 0.6:
        out.append(f"IN HOA toàn bộ: {a['all_caps']}/{n} thumb — niche này chuộng chữ hoa")
    elif a["all_caps"] == 0:
        out.append("Không ai IN HOA toàn bộ — giữ chữ thường/hoa đầu câu")
    if a["with_number"] >= n * 0.5:
        out.append(f"Có CON SỐ: {a['with_number']}/{n} thumb — số là điểm neo của niche này")
    if a["repeat_title"] <= n * 0.3:
        out.append(f"KHÔNG lặp lại tiêu đề: chỉ {a['repeat_title']}/{n} thumb trùng từ với title "
                   "— thumb bổ sung thông tin, không nhắc lại")
    else:
        out.append(f"Lặp lại tiêu đề: {a['repeat_title']}/{n} thumb dùng lại từ trong title")
    return out


def _overlap(a_words: set, s: str) -> int:
    return len({w.lower() for w in words_of(s)} & a_words)


def suggest(a: dict, title: str, keyword: str = "", n: int = 4,
            bank: list[str] | None = None) -> list[dict]:
    """Gợi ý Text on Thumb — **CHỈ LẤY TỪ KHO**, tool không tự nghĩ chữ (user chốt 2026-07-31).

    User: *"tôi sẽ cập nhật cho bạn vào kho và bạn sẽ gợi ý bằng cách lấy từ kho ra thôi"*.
    Trước đó có thêm hai đường tự sinh (mượn khuôn của kho · cắt chữ từ title) — **đã GỠ**.
    Chúng đẻ ra chữ chưa ai chạy thật rồi bày ngang hàng với chữ đã win, mà tool thì không có
    cách nào biết chữ tự ghép có ăn hay không. Đúng ranh giới quen thuộc của dự án: Python đo
    và XẾP HẠNG, còn "chữ nào hay" thì mắt user quyết.

    XẾP HẠNG chứ không LỌC BỎ: dòng trùng chủ đề (title + keyword) lên trước, hoà thì dòng
    ngắn lên trước (thumb ngắn dễ đọc). Dòng chưa trùng vẫn hiện, `note` nói thẳng — giấu bớt
    kho của user là tự quyết thay họ.
    KHO RỖNG = trả rỗng. Không có gì thì nói không có, tuyệt đối không bịa ra chữ để lấp chỗ.
    """
    lines = [x.strip() for x in (bank or []) if (x or "").strip()]
    if not lines:
        return []
    mine = {w.lower() for w in words_of(title) + words_of(keyword) if w.lower() not in _WEAK}
    # `len(s)` DƯƠNG: hoà điểm thì dòng NGẮN lên trước (thumb ngắn dễ đọc). Viết `-len(s)` là
    # ra đúng ngược lại — dài trước — mà nhìn code vẫn thấy "có tie-break" nên rất dễ bỏ qua.
    ranked = sorted(((_overlap(mine, s), len(s), s) for s in lines), key=lambda x: (-x[0], x[1]))
    # LẤY ĐỦ `n` dòng, KHÔNG lọc bỏ dòng chưa trùng chủ đề. Bản trước chỉ giữ dòng có trùng ⇒
    # kho 50 dòng mà video khớp đúng 1 thì user chỉ nhận 1 gợi ý, 49 dòng còn lại coi như không
    # tồn tại. Xếp hạng là đủ: dòng liên quan lên đầu, dòng còn lại vẫn hiện nhưng `note` NÓI
    # THẲNG là chưa trùng chủ đề — user tự cân, tool không giấu bớt kho của họ.
    out = [{"text": s, "src": "kho",
            "note": (f"trùng {ov} từ với video này" if ov else "chưa trùng từ nào với video này")}
           for ov, _, s in ranked[:n]]
    if a and out and a.get("n") and a["repeat_title"] <= a["n"] * 0.3:
        out.append({"text": "niche này KHÔNG lặp lại tiêu đề — chọn chữ NÓI THÊM, "
                            "đừng chép lại title", "src": "note"})
    return out


if __name__ == "__main__":                                 # self-test offline (0 LLM, 0 quota)
    RAW = ("0.125g\n"
           "MOST RADIOACTIVE\n"
           "  \n"
           "1000 ĐỘ C\n"
           "MOST RADIOACTIVE\n"                            # trùng → bỏ
           "It is not what you think\n")
    assert parse(RAW) == ["0.125g", "MOST RADIOACTIVE", "1000 ĐỘ C", "It is not what you think"]
    assert parse("") == [] and parse(None) == []

    TITLES = ["What happens if you drop 0.125 grams of antimatter?",
              "The Most Radioactive Place On Earth",
              "Bên trong lò luyện thép 1000 độ C",
              "Something is jamming GPS over Europe"]
    a = analyze(RAW, TITLES)
    assert a["n"] == 4, a
    assert a["words"] == {"avg": 3.0, "range": [1, 6]}, a["words"]   # (1+2+3+6)/4
    assert a["with_number"] == 2, a                         # "0.125g" và "1000 ĐỘ C"
    assert a["all_caps"] == 2, a                            # 2 dòng IN HOA ("0.125g" có chữ thường)
    assert a["repeat_title"] == 2, a                        # MOST RADIOACTIVE + 1000 ĐỘ C trùng title

    rs = rules(a)
    assert any("3.0 từ/thumb" in r for r in rs), rs
    assert any("CON SỐ" in r for r in rs), rs
    assert any("Lặp lại tiêu đề" in r for r in rs), rs

    # gợi ý CHỈ lấy từ kho — `a2` chỉ còn để quyết định có gắn ghi chú "đừng chép lại title"
    a2 = {"n": 5, "words": {"avg": 3.0, "range": [2, 4]}, "chars": {"avg": 14, "range": [6, 20]},
          "all_caps": 5, "with_number": 4, "repeat_title": 0, "samples": []}
    # ── CHỈ LẤY TỪ KHO: kho rỗng thì IM, không bịa chữ để lấp chỗ ──
    assert suggest(a2, "4 Million Suns Hiding in Our Galaxy", "sagittarius a*") == []
    assert suggest(a2, "x", "y", bank=[]) == [] and suggest(a2, "x", "y", bank=["  "]) == []

    BANK = ["4 MILLION SUNS", "KHONG AI TIN", "1000 DO C", "MOST RADIOACTIVE PLACE ON EARTH"]
    sg2 = suggest(a2, "4 Million Suns Hiding in Our Galaxy", "sagittarius a*", bank=BANK)
    body = [s for s in sg2 if s["src"] != "note"]
    assert body and all(s["src"] == "kho" for s in body), sg2       # KHÔNG còn 'khuôn'/'ghép'
    assert all(s["text"] in BANK for s in body), "gợi ý phải là chữ CÓ THẬT trong kho"
    assert body[0]["text"] == "4 MILLION SUNS", body                # dòng trùng chủ đề lên đầu
    assert "trùng" in body[0]["note"], body[0]
    assert any(s["src"] == "note" and "đừng chép lại title" in s["text"] for s in sg2), sg2

    # LẤY ĐỦ n dòng, không lọc bỏ dòng chưa trùng chủ đề — kho 4 dòng mà chỉ khớp 1 thì vẫn
    # phải thấy cả 4, dòng khớp lên đầu, dòng còn lại `note` nói thẳng là chưa trùng.
    assert len([s for s in sg2 if s["src"] == "kho"]) == len(BANK), sg2
    assert "trùng" in body[0]["note"] and "chưa trùng" in body[-1]["note"], body

    # kho KHÔNG dòng nào trùng chủ đề → vẫn trả kho (ngắn trước) + NÓI RÕ, không im lặng
    sg3 = suggest(a2, "Antimatter Drop", "", bank=["MOT HAI BA XYZ", "BON NAM"])
    assert [s["text"] for s in sg3 if s["src"] == "kho"] == ["BON NAM", "MOT HAI BA XYZ"], sg3
    assert "chưa trùng" in sg3[0]["note"], sg3

    # không có title/keyword vẫn trả kho — kho là NGUỒN, không phụ thuộc video
    assert [s["text"] for s in suggest(a2, "", "", bank=["AAA BBB", "CC"]) if s["src"] == "kho"]         == ["CC", "AAA BBB"]

    assert analyze("") == {} and rules({}) == [] and suggest({}, "x") == []
    assert suggest(a2, "", "") == []          # không kho → im, dù có phân tích

    print("thumbtext.py self-test OK - do Text on Thumb, goi y CHI lay tu kho, 0 LLM 0 quota")
