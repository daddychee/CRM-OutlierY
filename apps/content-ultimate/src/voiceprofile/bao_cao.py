# -*- coding: utf-8 -*-
"""BAO CAO QUA TRINH EXTRACT (24/08/2026) — Owner yeu cau: chay xong phai co bao cao.

Truoc day muon biet mot ho so giong co dung khong thi phai mo profile.json ra doc
tay, va khong ai doc — do la ly do ba ho so dung tren corpus transcript tho van duoc
dung de viet suot ba tuan. Bao cao nay tra loi bon cau hoi bang tieng Viet:

  1. May DA DOC GI     — file nao vao kho, file nao bi loai va vi sao, bao nhieu diem do.
  2. DO DUOC GI        — tung chieu: gia tri, sai so, va VI SAO no duoc giu hay bi loai
                         (on dinh / bat buoc / chua do duoc). Khong co con so nao "tu nhien
                         co mat" ma khong giai thich duoc.
  3. KHAC GIONG KHAC   — Delta: giong nay gan giong nao trong kho, co bi trung ai khong.
  4. GI DI VAO PROMPT  — in nguyen van khoi VOICE TARGETS ma generator that su gui di.

Van: bao cao chi VIET RA nhung gi da do duoc. Chieu chua do duoc thi ghi thang "chua
do duoc", khong doan, khong lam tron thanh 0. Toan bo la Python doc lai profile —
khong goi model, khong ton token.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import dien_ngon
from .soi_ho_so import soi_profile

# Ten tieng Viet cho tung chieu — bao cao la de NGUOI DOC, khong phai de may doc.
TEN_VIET = {
    "sentence_len_mean": "Số từ mỗi câu",
    "sentence_len_stdev": "Độ dao động độ dài câu",
    "sentence_short_ratio": "Tỉ lệ câu dưới 8 từ",
    "sentence_long_ratio": "Tỉ lệ câu trên 35 từ",
    "function_word_freq": "Mật độ hư từ",
    "punct_freq_total": "Mật độ dấu câu",
    "ttr": "Độ đa dạng từ vựng (TTR)",
    "flesch_reading_ease": "Độ dễ đọc Flesch",
    "noun_specificity_proxy": "Mật độ danh từ riêng (ước lượng)",
    "avg_word_len_chars": "Độ dài từ trung bình",
    "punct_comma_freq": "Dấu phẩy",
    "punct_semicolon_freq": "Dấu chấm phẩy",
    "punct_colon_freq": "Dấu hai chấm",
    "punct_em_dash_freq": "Gạch ngang dài (—)",
    "punct_hyphen_freq": "Gạch nối (-)",
    "punct_paren_freq": "Ngoặc đơn",
    "punct_paren_close_freq": "Ngoặc đóng",
    "punct_exclaim_freq": "Dấu chấm than",
    "punct_question_freq": "Dấu hỏi",
    "punct_ellipsis_freq": "Dấu ba chấm",
    "ngoi_thu_hai": "Gọi \"you\" (lần/1.000 từ)",
    "ngoi_thu_nhat_it": "Xưng \"I\" (lần/1.000 từ)",
    "ngoi_thu_nhat_nhieu": "Xưng \"we\" (lần/1.000 từ)",
    "cau_moi_doan": "Số câu mỗi đoạn",
    "lien_tu_mo_cau": "Câu mở bằng liên từ",
    "cau_hoi": "Câu hỏi trực tiếp",
    "bi_dong": "Thể bị động (ước lượng)",
    "hapax": "Từ chỉ dùng một lần",
    "mat_do_so": "Mật độ chữ số (/1.000 từ)",
}


def _so(x, n=2):
    return "—" if x is None else f"{x:,.{n}f}".replace(",", ".")


def _ly_do_giu(f: dict) -> str:
    """Vi sao chieu nay co mat (hoac vang mat) trong ho so — khong de trong bao gio."""
    if f.get("do_duoc") is False:
        return "chưa đo được (corpus chưa đủ điểm đo)"
    if f.get("keep"):
        return "giữ: ổn định qua các phần corpus"
    if f.get("bat_buoc"):
        return "giữ: chiều **bắt buộc** (nhịp câu — luôn giữ dù dao động)"
    return "loại: dao động quá mức giữa các phần"


def bao_cao_extract(profile: dict, corpus_dir: str | Path | None = None,
                    bang_delta: dict | None = None, ma: str | None = None,
                    neo: dict | None = None) -> str:
    """Bao cao Markdown cho MOT ho so. Ho so thieu truong van ra bao cao, khong vo."""
    profile = profile or {}
    ten = str(profile.get("author") or "(chưa đặt tên)")
    cs = profile.get("corpus_stats") or {}
    qf = [f for f in (profile.get("quant_features") or []) if isinstance(f, dict)]
    rt = profile.get("reproduction_targets") or {}
    df = profile.get("discourse_features") or {}
    soi = soi_profile(profile)

    d = [f"# Báo cáo extract giọng — {ten}", "",
         f"*Dựng lúc {datetime.now():%H:%M %d/%m/%Y}. Mọi con số dưới đây do Python đo trên "
         f"corpus của chính tác giả; không có con số nào do model ước lượng.*", ""]

    # --- Canh bao len dau: nguoi doc phai thay truoc khi tin bat cu so nao ---------
    canh = list(soi.get("canh_bao") or []) + list(df.get("canh_bao") or [])
    # soi_ho_so do 3 doan mau TRONG ho so, nhung luc viet that thi cli thay chung bang
    # neo day rut tu corpus (chon_neo). Co neo day roi ma van canh bao "neo mong" la
    # bao cao tu mau thuan voi chinh no o ngay doan duoi.
    if neo and neo.get("neo") and (neo.get("tong_tu") or 0) >= 800:
        canh = [c for c in canh if "Neo giọng chỉ" not in c and "đoạn mẫu trùng" not in c]
    if canh:
        d += ["## ⚠ Lưu ý", ""]
        d += [f"- {c}" for c in canh] + [""]

    # --- Mo ta giong: cai NGUOI DOC can truoc tien (24/08) --------------------------
    mt = profile.get("mo_ta_giong") or {}
    if mt:
        from .mo_ta_giong import dong_markdown
        d += ["## Giọng này dùng cho việc gì", ""]
        d += [f"- {x}" for x in dong_markdown(mt)] + [""]
        d += ["*Đoạn trên do model viết, nhưng chỉ được đọc số đo Python đã đo và các "
              "đoạn văn thật của tác giả — không có con số nào do nó nghĩ ra.*", ""]

    # --- 1. May da doc gi ----------------------------------------------------------
    d += ["## Corpus đã đọc", "",
          "| | |", "|---|---|",
          f"| Số file | {cs.get('n_works', '—')} |",
          f"| Tổng số từ | {cs.get('n_tokens', 0):,} |".replace(",", "."),
          f"| Điểm đo cắt ra | {cs.get('n_stability_units', '—')} |"]
    if corpus_dir:
        d.append(f"| Thư mục | `{corpus_dir}` |")
    d.append("")
    n_units = cs.get("n_stability_units")
    if isinstance(n_units, int):
        if n_units < 3:
            d += ["Dưới 3 điểm đo thì **không thể** nói đặc trưng nào là ổn định: một điểm "
                  "đo không có phương sai. Các con số vẫn đúng, nhưng chưa chứng minh được "
                  "chúng là thói quen chứ không phải ngẫu nhiên.", ""]
        else:
            d += [f"Corpus được cắt thành {n_units} phần độc lập; mỗi chỉ số dưới đây được đo "
                  f"trên từng phần rồi so với nhau — đó là cách biết chỉ số nào là thói quen "
                  f"thật của tác giả.", ""]

    # --- 2. Do duoc gi -------------------------------------------------------------
    d += ["## Chỉ số giọng", "",
          "| Chỉ số | Giá trị | Sai số (1 SD) | Vì sao có/không có trong hồ sơ |",
          "|---|---:|---:|---|"]
    for f in qf:
        ten_c = TEN_VIET.get(f.get("name"), f.get("name"))
        t = rt.get(f.get("name")) or {}
        d.append(f"| {ten_c} | {_so(f.get('value'))} | {_so(t.get('sd'))} | {_ly_do_giu(f)} |")
    if not qf:
        d.append("| *(chưa có chỉ số nào)* | — | — | hồ sơ chưa chạy bước `build` |")
    d += ["", f"**{sum(1 for f in qf if f.get('keep'))}/{len(qf)}** chỉ số đạt ngưỡng ổn định; "
          f"**{len(rt)}** chỉ số được dùng làm đích khi chấm bài viết ra.", ""]

    # --- 3. Lap truong / dien ngon --------------------------------------------------
    d += ["## Lập trường và diễn ngôn", ""]
    if df.get("chieu"):
        d += ["| Chiều | Giá trị | Sai số |", "|---|---:|---:|"]
        for k, v in df["chieu"].items():
            gt = _so(v.get("target"))
            if v.get("do_duoc") is False:
                gt += " ✗"       # chieu bi artefact dinh dang lam hong — xem canh bao dau bao cao
            d.append(f"| {TEN_VIET.get(k, k)} | {gt} | {_so(v.get('sd'))} |")
        d.append("")
        mo = dien_ngon.mo_ta(df)
        if mo:
            d += ["Đọc bằng lời:", ""] + [f"- {m}" for m in mo] + [""]
    else:
        d += ["*(hồ sơ dựng trước 24/08 — chạy lại extract để có tầng này)*", ""]

    # --- Neo giong ------------------------------------------------------------------
    ex = profile.get("exemplars") or []
    if ex or neo:
        tong_tu = (neo or {}).get("tong_tu") or sum(len(str(e).split()) for e in ex)
        d += ["## Neo giọng (đoạn mẫu đưa vào prompt)", "",
              f"- {len(neo['neo']) if neo and neo.get('neo') else len(ex)} khối · **{tong_tu:,} từ**"
              .replace(",", "."), ]
        if neo and neo.get("nhip_neo") and neo.get("nhip_corpus"):
            a, b = neo["nhip_neo"], neo["nhip_corpus"]
            d.append(f"- Nhịp neo {a['tu_moi_cau']} từ/câu so với corpus {b['tu_moi_cau']} "
                     f"(càng sát càng tốt — đây là thứ model bắt chước)")
        # Do tren SO TU THUC TE se di vao prompt (neo day neu co), khong theo co cua
        # soi_ho_so — no chi nhin 3 doan mau trong ho so.
        if tong_tu < 800:
            d.append("- ⚠ Neo mỏng: model sẽ rơi về nhịp mặc định của nó thay vì nhịp tác giả")
        d.append("")

    # --- 4. Delta -------------------------------------------------------------------
    if bang_delta and ma and ma in (bang_delta.get("z") or {}):
        from . import delta as D
        gan = sorted(({"ma": k, "delta": D.delta_giua(ma, k, bang_delta)}
                      for k in bang_delta["z"] if k != ma), key=lambda r: r["delta"])
        d += ["## So với các giọng khác trong kho", "",
              "*Khoảng cách Burrows's Delta — càng nhỏ càng giống. Đo bằng tần suất hư từ "
              "(the, of, we, you…), thứ người viết dùng theo thói quen chứ không theo chủ đề.*", "",
              "| Giọng gần nhất | Delta |", "|---|---:|"]
        for r in gan[:3]:
            d.append(f"| {r['ma']} | {r['delta']:.3f} |")
        d.append("")
        trung = [n for n in D.nhom_ban_sao(bang_delta) if ma in n]
        if trung:
            khac = [x for x in trung[0] if x != ma]
            d += [f"⚠ **Trùng hồ sơ khác**: Delta gần bằng 0 với {', '.join(khac)} — nghĩa là "
                  f"cùng một corpus đang mang nhiều tên. Chọn giọng nào cũng cho kết quả như "
                  f"nhau.", ""]

    # --- 5. Gi di vao prompt ---------------------------------------------------------
    from .generator import build_nhip_block
    khoi = build_nhip_block(profile).strip()
    d += ["## Những gì thật sự đi vào prompt", ""]
    if khoi:
        d += ["Ngoài các đoạn mẫu, generator gửi kèm đúng khối này:", "", "```", khoi, "```", ""]
    else:
        d += ["Chỉ có các đoạn mẫu và signature moves — **không có số đo nào đi vào prompt** "
              "(hồ sơ chưa đo được chỉ số nhịp nào, hoặc `CU_NHIP_PROMPT=0`).", ""]
    moves = profile.get("signature_moves") or []
    d.append(f"Signature moves đã kiểm chứng bằng trích dẫn nguyên văn: **{len(moves)}**"
             + ("" if moves else " *(chưa chạy bước `rhetoric`)*"))
    return "\n".join(d) + "\n"


def bao_cao_kho(ho_so: list[dict], bang_delta: dict | None = None) -> str:
    """Bao cao TOAN KHO: mot bang cho Owner nhin het tinh trang cac ho so giong.

    ho_so: [{"ma","ten","profile"}] — de nguoi goi tu quyet doc tu dau (thu vien, thu muc).
    """
    d = [f"# Báo cáo kho hồ sơ giọng ({len(ho_so)} hồ sơ)", "",
         f"*Dựng lúc {datetime.now():%H:%M %d/%m/%Y} — Python đo, 0 token.*", "",
         "| Mã | Tên | Số từ | Điểm đo | Chỉ số ổn định | Mẫu trong hồ sơ (từ) | Cảnh báo |",
         "|---|---|---:|---:|---:|---:|---|"]
    for h in ho_so:
        p = h.get("profile") or {}
        cs = p.get("corpus_stats") or {}
        qf = p.get("quant_features") or []
        soi = soi_profile(p)
        co = ", ".join(soi.get("co") or []) or "—"
        d.append(f"| {h.get('ma', '')} | {h.get('ten', '')} | "
                 f"{cs.get('n_tokens', 0):,} | {cs.get('n_stability_units', '—')} | "
                 f"{sum(1 for f in qf if f.get('keep'))}/{len(qf)} | "
                 f"{soi['chi_so'].get('exemplar_tong_tu', 0):,} | {co} |".replace(",", "."))
    d += ["",
          "*\"Mẫu trong hồ sơ\" là các đoạn lưu trong `profile.json`. Lúc viết thật, nếu "
          "người viết chọn cả thư mục corpus thì hệ thay chúng bằng **neo dày ~1.800 từ** "
          "rút thẳng từ corpus (`chon_neo`), nên cờ `neo_mong` ở cột cảnh báo chỉ đúng cho "
          "trường hợp viết mà không có corpus.*", ""]
    if bang_delta:
        from . import delta as D
        nhom = D.nhom_ban_sao(bang_delta)
        if nhom:
            d += ["## ⚠ Hồ sơ trùng nhau", "",
                  "Các nhóm dưới đây có Delta gần bằng 0 — cùng một corpus mang nhiều tên. "
                  "Người viết đang chọn giữa những cái tên khác nhau mà bên trong là một:", ""]
            d += [f"- **{' = '.join(n)}**" for n in nhom] + [""]
        mt = sorted(D.ma_tran(bang_delta), key=lambda r: r["delta"])
        con = [r for r in mt if r["delta"] >= D.NGUONG_BAN_SAO]
        if con:
            d += ["## Cặp giọng gần nhau nhất (dễ lẫn khi viết)", "",
                  "| Cặp | Delta |", "|---|---:|"]
            d += [f"| {r['a']} ↔ {r['b']} | {r['delta']:.3f} |" for r in con[:5]] + [""]
    return "\n".join(d) + "\n"


def ghi_bao_cao(md: str, duong: str | Path) -> Path:
    p = Path(duong)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md, encoding="utf-8")
    return p
