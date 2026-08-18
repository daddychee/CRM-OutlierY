"""Kiểm `board.html` — 4 tầng. Chạy: `python -m seo.boardcheck`

Vì sao phải có: `board.html` là MỘT file ~2200 dòng vừa HTML vừa JS, không build,
không linter. Bốn lớp lỗi dưới đây **không làm gì báo lỗi cả** — trang vẫn nạp, chỉ là
chết câm hoặc nói dối:

  1. Ngoặc không cân / template chưa đóng      → SyntaxError, cả `<script>` không chạy
  2. `const`/`let` trùng tên trong CÙNG scope  → y hệt, mà tầng 1 mù hoàn toàn
     (cắn 2026-07-28: `const g=` hai lần trong `fdetailHTML` làm cả trang chết câm,
      triệu chứng nhìn y như "server hỏng")
  3. `$('#id')` trỏ vào id không tồn tại       → TypeError lúc load, MỌI handler đăng ký
     sau đó không được gắn (trang trông bình thường nhưng bấm gì cũng không ăn)
  4. **Ô CHẾT** — `<input|select|textarea>` có id mà giá trị KHÔNG BAO GIỜ được đọc
     → user tưởng mình đang chọn gì đó, thực ra tool bỏ qua. Ba tầng trên đều BÁO XANH
     cho lỗi này (cắn 2026-07-31: `#profSel` "chọn 1 Profile Description" bị
     `runGenerate` ghi đè ở cả hai nhánh nên không đường nào đọc tới giá trị user chọn).

Ba tầng đầu kiểm CÚ PHÁP; tầng 4 kiểm TÍNH TRUNG THỰC. Chạy sau MỌI lần vá board.html.
KHÔNG thay được việc bấm thật trong trình duyệt — xem mục "Kiểm board bằng TRÌNH DUYỆT
THẬT" trong CLAUDE.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import common                       # noqa: F401  (import = bật utf-8 cho console Windows)

BOARD = Path(__file__).parent / "board.html"

_PREV_REGEX_OK = set("(,=:[!&|?{};+-*%~^") | {"\n"}
_NAME = re.compile(r"[A-Za-z_$][\w$]*")


def _strip(raw: str) -> tuple[list[str], str, int]:
    """Quét ký tự một lượt: trả (lỗi ngoặc, bản chỉ-còn-code, số dòng).

    Bản "chỉ-còn-code" thay chuỗi/comment/regex bằng khoảng trắng nhưng GIỮ nguyên độ dài
    và số dòng → tầng 2 soi trên đó mà không vướng nội dung nằm trong chuỗi.
    """
    # GOM MỌI khối <script>, không chỉ khối đầu (sửa 2026-07-31 — suýt để lọt).
    # board.html có 2 khối: một đoạn ngắn trong <head> đặt data-theme trước khi vẽ, và khối
    # chính ~1800 dòng ở cuối. Bản cũ lấy `re.search` = khối ĐẦU TIÊN, nên vừa thêm đoạn head
    # là bộ kiểm quay sang soi 8 dòng đó và báo "SACH" cho cả file — đúng kiểu bộ kiểm nói dối
    # (số dòng tụt 2386 → 444 mới lộ ra). Trình duyệt cũng nạp các khối vào CÙNG scope global
    # nên nối lại là đúng ngữ nghĩa: `const` trùng tên giữa 2 khối vẫn là lỗi thật.
    # Quét TUẦN TỰ, mỗi lần nhảy qua trọn một thân script. KHÔNG dùng `finditer` quét cả file:
    # chữ "<script>" còn nằm trong chú thích và trong chuỗi JS (board.html có 2 chỗ như thế),
    # `finditer` đếm chúng thành thẻ mở thật ⇒ thân script chính bị nối vào hai lần, đẻ ra
    # một loạt "khai trùng const" hoàn toàn ảo. Nhảy qua thân script thì mọi thứ bên trong
    # nó — kể cả chữ "<script>" — đều được bỏ qua đúng như trình duyệt làm.
    spans, pos = [], 0
    while True:
        m = re.compile(r"<script[^>]*>").search(raw, pos)
        if not m:
            break
        close = raw.find("</script>", m.end())
        if close < 0:
            return [f"<script> ở dòng {raw[:m.start()].count(chr(10)) + 1} không có </script>"], "", 1
        spans.append((m.end(), close))
        pos = close + len("</script>")
    if not spans:
        return ["không tìm thấy <script>"], "", 1
    # ngoài thân script thay bằng khoảng trắng NHƯNG GIỮ '\n' → số dòng báo ra khớp file gốc
    parts, pos = [], 0
    for s, e in spans:
        parts.append(re.sub(r"[^\n]", " ", raw[pos:s]))
        parts.append(raw[s:e])
        pos = e
    parts.append(re.sub(r"[^\n]", " ", raw[pos:]))
    src = "".join(parts)

    stack: list[tuple[str, int]] = []
    tmpl: list[int] = []
    errors: list[str] = []
    clean: list[str] = []
    i, line, state, last_sig = 0, 1, None, "\n"

    def emit(ch: str, keep: bool) -> None:
        clean.append(ch if keep else ("\n" if ch == "\n" else " "))

    while i < len(src):
        c = src[i]
        nxt = src[i + 1] if i + 1 < len(src) else ""
        if c == "\n":
            line += 1
            if state in ("//", "re"):
                state = None
            emit(c, True); i += 1; continue
        if state in ("'", '"'):
            if c == "\\":
                emit(c, False); emit(nxt, False); i += 2; continue
            if c == state:
                state = None
            emit(c, False); i += 1; continue
        if state == "`":
            if c == "\\":
                emit(c, False); emit(nxt, False); i += 2; continue
            if c == "$" and nxt == "{":
                tmpl.append(0); state = None
                emit(" ", False); emit("{", True)          # ${…} chứa CODE → phải soi
                i += 2; continue
            if c == "`":
                state = None
            emit(c, False); i += 1; continue
        if state in ("//", "/*"):
            if state == "/*" and c == "*" and nxt == "/":
                state = None
                emit(c, False); emit(nxt, False); i += 2; continue
            emit(c, False); i += 1; continue
        if state == "re":
            if c == "\\":
                emit(c, False); emit(nxt, False); i += 2; continue
            if c == "[":
                j = src.find("]", i)
                j = (j + 1) if j > 0 else i + 1
                for k in range(i, j):
                    emit(src[k], False)
                i = j; continue
            if c == "/":
                state = None
            emit(c, False); i += 1; continue
        # ── ngoài chuỗi/comment ──
        if c == "/" and nxt == "/":
            state = "//"; emit(c, False); emit(nxt, False); i += 2; continue
        if c == "/" and nxt == "*":
            state = "/*"; emit(c, False); emit(nxt, False); i += 2; continue
        if c == "/" and last_sig in _PREV_REGEX_OK:
            state = "re"; emit(c, False); i += 1; continue
        if c in "'\"`":
            state = c; emit(c, False); i += 1; last_sig = c; continue
        if c in "([{":
            if c == "{" and tmpl:
                tmpl[-1] += 1
            stack.append((c, line))
        elif c in ")]}":
            if c == "}" and tmpl and tmpl[-1] == 0:
                tmpl.pop(); state = "`"
                emit("}", True); i += 1; last_sig = c; continue
            if c == "}" and tmpl:
                tmpl[-1] -= 1
            if not stack:
                errors.append(f"dòng {line}: thừa '{c}'")
            else:
                op, ln = stack.pop()
                if ")]}"["([{".index(op)] != c:
                    errors.append(f"dòng {line}: '{c}' không khớp '{op}' mở ở dòng {ln}")
        emit(c, True)
        if not c.isspace():
            last_sig = c
        i += 1

    if state is not None:
        errors.append(f"chưa đóng: state={state!r} (cuối file dòng {line})")
    if tmpl:
        errors.append(f"template chưa đóng: {len(tmpl)} khối")
    for op, ln in stack:
        errors.append(f"chưa đóng '{op}' mở ở dòng {ln}")
    return errors, "".join(clean), line


def _names_of(decl: str) -> list[str]:
    """`a=1, {b,c}=x, [d]=y` → ['a','b','c','d'] (tách theo dấu phẩy ở ĐỘ SÂU 0)."""
    out, depth, buf = [], 0, ""
    for ch in decl:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf); buf = ""
        else:
            buf += ch
    out.append(buf)
    res: list[str] = []
    for part in out:
        head = part.split("=", 1)[0].strip()
        if not head:
            continue
        if head[0] in "{[":                                # destructuring → lấy mọi định danh
            res += [m.group(0) for m in _NAME.finditer(head)]
        else:
            m = _NAME.match(head)
            if m:
                res.append(m.group(0))
    return res


def check_dup_decl(code: str) -> list[str]:
    """Tầng 2: `const`/`let` trùng tên trong cùng một block scope."""
    errors: list[str] = []
    scopes: list[dict[str, int]] = [{}]
    depth_paren, pos, lineno = 0, 0, 1
    while pos < len(code):
        ch = code[pos]
        if ch == "\n":
            lineno += 1
        elif ch == "{":
            scopes.append({})
        elif ch == "}":
            if len(scopes) > 1:
                scopes.pop()
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch in "cl" and (pos == 0 or not (code[pos - 1].isalnum() or code[pos - 1] in "_$.")):
            m = re.match(r"(const|let)\b", code[pos:])
            # trong ngoặc tròn = đầu vòng `for` / tham số → scope riêng, bỏ qua kẻo báo oan
            if m and depth_paren == 0:
                j, d = pos + m.end(), 0
                while j < len(code):
                    if code[j] in "([{":
                        d += 1
                    elif code[j] in ")]}":
                        if d == 0:
                            break
                        d -= 1
                    elif code[j] == ";" and d == 0:
                        break
                    j += 1
                for nm in _names_of(code[pos + m.end():j]):
                    if nm in scopes[-1]:
                        errors.append(f"dòng {lineno}: '{nm}' đã khai `const/let` ở dòng "
                                      f"{scopes[-1][nm]} trong CÙNG scope → SyntaxError, "
                                      f"cả <script> không chạy")
                    else:
                        scopes[-1][nm] = lineno
                lineno += code[pos:j].count("\n")
                pos = j
                continue
        pos += 1
    return errors


def check_ids(raw: str) -> list[str]:
    """Tầng 3: mọi `$('#id')` phải trỏ vào element có thật."""
    body, script = raw.split("<script>", 1)
    script = script.rsplit("</script>", 1)[0]
    have = set(re.findall(r'id="([^"]+)"', body)) | set(re.findall(r"id='([^']+)'", body))
    have |= set(re.findall(r'id="([A-Za-z][\w-]*)"', script))   # id dựng động trong innerHTML
    out = []
    for m in re.finditer(r"""\$\(\s*['"]#([A-Za-z][\w-]*)['"]\s*\)""", script):
        if m.group(1) not in have:
            ln = script[:m.start()].count("\n") + 1
            out.append(f"dòng {ln}: $('#{m.group(1)}') — không element nào mang id đó")
    return sorted(set(out))


def check_unterminated_str(code: str) -> list[str]:
    """Tầng 5: chuỗi `'…'`/`"…"` bị XUỐNG DÒNG THẬT ở giữa — luôn là SyntaxError trong JS.

    **Vì sao phải có (cắn 2026-08-02):** file này hay được vá bằng script Python, mà `\\n`
    viết trong heredoc/chuỗi Python qua một tầng thoát nữa là thành **xuống dòng thật** nằm
    trong chuỗi JS nháy đơn. Kết quả: SyntaxError ⇒ trình duyệt bỏ NGUYÊN khối `<script>` ⇒
    **cả trang chết câm**, không nút nào chạy. Ba tầng kiểm cũ (cân ngoặc · khai trùng · id)
    đều báo **SACH** cho đúng lỗi đó — tôi chỉ tìm ra bằng cách gắn bắt lỗi vào trình duyệt thật.

    Template literal (backtick) ĐƯỢC PHÉP xuống dòng nên bỏ qua hẳn.
    """
    out = []
    for i, line in enumerate(code.split("\n"), 1):
        q, esc, j = None, False, 0
        while j < len(line):
            c = line[j]
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif q:
                if c == q:
                    q = None
            elif c == "`":
                # backtick: xuống dòng hợp lệ → bỏ qua phần còn lại của dòng cho chắc
                q = None
                break
            elif c in "'\"":
                q = c
            elif c == "/" and j + 1 < len(line) and line[j + 1] == "/":
                break                                   # chú thích cuối dòng
            j += 1
        if q:
            out.append(f"dòng {i}: chuỗi mở bằng {q} nhưng KHÔNG đóng trước khi hết dòng — "
                       f"JS coi đây là SyntaxError và bỏ NGUYÊN khối <script>: {line.strip()[:70]}")
    return out


def check_dead_controls(raw: str) -> list[str]:
    """Tầng 4: ô nhập có id mà giá trị không bao giờ được ĐỌC.

    Phải nhận cả đường đọc GIÁN TIẾP (`$('#x')` truyền làm tham số rồi hàm kia đọc `.value`,
    như `#fmNicheSel` → `applyNicheSel(sel, box)`), không thì báo oan mọi ô kiểu đó.

    **`querySelector('#x')` cũng là đường đọc hợp lệ** (thêm 2026-08-02, sau khi báo oan `#lgPw`
    trong overlay đăng nhập — ô đó dựng động rồi lấy bằng `ov.querySelector`). Luật cho nó được
    viết CHẶT HƠN luật của `$()`: phải bắt được TÊN BIẾN rồi đòi thấy `.value`/`.checked` đọc trên
    CHÍNH biến đó. Nới bộ kiểm cho hết kêu là biến nó thành lời nói dối — thà viết luật hẹp hơn.
    """
    js = re.sub(r"(?s)^.*?<script\b[^>]*>", "", raw)
    out = []
    pat = r"""<(input|select|textarea)\b[^>]*\bid=["']([\w-]+)["']"""
    for tag, cid in re.findall(pat, raw):
        q = re.escape(cid)
        checks = [
            r"""\$\(\s*['"]#%s['"]\s*\)\s*\.\s*(value|checked|files|selectedOptions)""" % q,
            r"""getElementById\(\s*['"]%s['"]\s*\)\s*\.\s*(value|checked|files)""" % q,
            r"""querySelector\(\s*['"]#%s['"]\s*\)\s*\.\s*(value|checked|files|selectedOptions)""" % q,
            r"""[(,]\s*\$\(\s*['"]#%s['"]\s*\)\s*[,)]""" % q,        # truyền làm tham số
            r"""=\s*\$\(\s*['"]#%s['"]\s*\)\s*[;,)]""" % q,          # gán vào biến rồi đọc sau
        ]
        # `const pw = ov.querySelector('#lgPw')` → phải thấy `pw.value` ở đâu đó mới tính là ĐỌC.
        for var in re.findall(
                r"""(?:const|let|var)\s+(\w+)\s*=\s*[\w.$]*\.?querySelector\(\s*['"]#%s['"]\s*\)""" % q,
                js):
            checks.append(r"""\b%s\s*\.\s*(value|checked|files|selectedOptions)\b""" % re.escape(var))
        if not any(re.search(p, js) for p in checks):
            out.append(f"<{tag} id={cid}> — KHÔNG thấy chỗ nào đọc giá trị: ô này giả vờ có "
                       f"tác dụng, user chọn xong tool bỏ qua")
    return out


def run(path: Path = BOARD) -> int:
    raw = path.read_text(encoding="utf-8")
    brace_errs, code, nline = _strip(raw)
    groups = (("cú pháp / cân bằng ngoặc", brace_errs),
              ("khai báo trùng const/let", check_dup_decl(code)),
              ("$('#id') có element thật", check_ids(raw)),
              ("chuỗi không đóng trước khi hết dòng", check_unterminated_str(code)),
              ("ô chết (giả vờ có tác dụng)", check_dead_controls(raw)))
    bad = 0
    for name, errs in groups:
        if errs:
            bad += len(errs)
            print(f"[HONG] {name}")
            for e in errs:
                print(f"        {e}")
        else:
            print(f"[ok]   {name}")
    tail = "SACH" if not bad else f"{bad} loi"
    print(f"\n{path.name}: {tail} ({nline} dong)")
    return 1 if bad else 0


def selftest() -> int:
    """Chứng minh bộ kiểm THẬT SỰ bắt được từng lớp lỗi.

    Không có phần này thì `[ok]` bốn dòng chẳng chứng minh gì — một regex viết sai cũng
    cho ra đúng bốn dòng xanh đó. Mỗi ca dưới đây cố tình gài một lỗi rồi đòi bộ kiểm
    phải kêu; ca cuối cùng là bản LÀNH, đòi nó phải im.
    """
    def page(body: str, js: str) -> str:
        return f"<html><body>{body}</body><script>{js}</script></html>"

    cases = [
        ("ngoặc thiếu", _strip(page("", "function f(){ if(1){ }"))[0],
         "chưa đóng"),
        ("template chưa đóng", _strip(page("", "const s=`abc"))[0],
         "chưa đóng"),
        ("khai trùng const", check_dup_decl(_strip(page("", "function f(){const g=1;const g=2;}"))[1]),
         "đã khai"),
        ("id không tồn tại", check_ids(page("<div id='a'></div>", "$('#khong_co').onclick=0")),
         "không element nào"),
        ("ô chết", check_dead_controls(page("<select id='mo_coi'></select>", "var x=1")),
         "giả vờ có tác dụng"),
        # Luật querySelector mới KHÔNG được biến thành cửa sau: lấy được element rồi mà không
        # bao giờ đọc giá trị thì vẫn là ô chết.
        ("querySelector nhưng không đọc value",
         check_dead_controls(page("<input id='lay_ma_khong_doc'>",
                                  "const z=ov.querySelector('#lay_ma_khong_doc'); z.focus();")),
         "giả vờ có tác dụng"),
        # Lỗi nằm ở khối <script> THỨ HAI. Bản cũ chỉ soi khối đầu nên ca này lọt sạch —
        # đúng cái đã xảy ra khi thêm đoạn đặt data-theme vào <head>.
        ("lỗi ở khối script thứ 2",
         _strip("<html><script>var a=1;</script><body></body>"
                "<script>function f(){ if(1){ }</script></html>")[0],
         "chưa đóng"),
        ("<script> không đóng", _strip("<html><script>var a=1;")[0], "không có </script>"),
        # Lỗi GIẾT CẢ TRANG mà 3 tầng cũ đều báo SACH — xem docstring check_unterminated_str
        ("chuỗi xuống dòng thật giữa chừng",
         check_unterminated_str("alert('dong mot" + chr(10) + "dong hai');"), "KHÔNG đóng"),
    ]
    bad = 0
    for name, errs, want in cases:
        hit = any(want in e for e in errs)
        print(f"  {'bắt được ' if hit else 'BỎ LỌT   '} {name}")
        bad += 0 if hit else 1

    # ── ca LÀNH: mọi tầng phải im. Bắt oan cũng tệ ngang bỏ lọt. ──
    ok_page = page(
        "<input id='ten'><select id='sel'></select><textarea id='ghi'></textarea>"
        "<input id='mk'><input id='mk2'>",
        "const $=s=>document.querySelector(s);"
        "const v=$('#ten').value;"                          # đọc trực tiếp
        "function ap(sel){return sel.value;} ap($('#sel'));"  # đọc gián tiếp qua tham số
        "const t=$('#ghi'); const w=t.value;"                # gán vào biến rồi đọc
        "const pw=ov.querySelector('#mk'); const k=pw.value;"  # querySelector → biến → đọc
        "const d2=ov.querySelector('#mk2').value;"             # querySelector đọc thẳng
        "for(const i of [1,2]){const z=i;} for(const i of [3]){const z=i;}"  # scope lồng, không trùng
        "const re=/[)}]/; const s2=`x${1+1}y`;"              # regex + template có ${}
        # Ba ca LÀNH mà tầng 5 tuyệt đối không được kêu: chuỗi bình thường · chú thích có
        # dấu nháy đơn lửng · template literal xuống dòng (backtick ĐƯỢC PHÉP xuống dòng).
        + "const ok1='mot dong'; const ok2=\"hai\";" + chr(10)
        + "// ghi chu co ' nhay don le" + chr(10)
        + "const ok3=`template" + chr(10) + "xuong dong duoc`;")
    e1, code, _ = _strip(ok_page)
    quiet = (e1, check_dup_decl(code), check_ids(ok_page), check_dead_controls(ok_page))
    quiet = quiet + (check_unterminated_str(code),)
    for name, errs in zip(("ngoặc", "khai trùng", "id", "ô chết", "chuỗi"), quiet):
        if errs:
            bad += 1
            print(f"  BÁO OAN   trang lành mà tầng '{name}' kêu: {errs}")
    if not any(quiet):
        print("  im lặng   trên trang lành (không báo oan)")

    print("\nboardcheck selftest OK" if not bad else f"\nboardcheck selftest HỎNG: {bad} ca")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    sys.exit(run(Path(args[0]) if args else BOARD))
