"""Lắp outline.txt + outline_evidence.md từ lựa chọn của user. Thuần, không LLM, test offline.

Format outline.txt là HỢP ĐỒNG với Author Extract (khóa cứng, xem METHODOLOGY §S5):
    Title: <user nhập>
    <blank>
    HOOK
    <brief>
    <blank>
    CHAPTER 1 — <name>
    <brief>
    ...
    ENDING
    <brief>

outline.txt = bản SẠCH (không citation) cho máy sinh văn.
outline_evidence.md = song song, kèm citation để người review truy nguồn.
"""
from __future__ import annotations


def _cluster_map(clusters: list[dict]) -> dict:
    # dùng name làm khóa ổn định (board gửi lại name đã tick)
    return {c["name"]: c for c in clusters}


def _resolve(name: str, cm: dict, picks: dict) -> dict | None:
    """Cluster theo name, hoặc mục USER TỰ VIẾT (picks['custom'] = {name: brief}).

    Mục tự viết là quyền pick của user (2026-07-09) — không có bằng chứng từ video,
    được đánh dấu rõ trong evidence; board đặt tên với tiền tố '✍ '.
    """
    if name in cm:
        return cm[name]
    custom = picks.get("custom") or {}
    if name in custom:
        return {"name": name, "brief": str(custom[name]).strip()}
    return None


def _display(name: str) -> str:
    return name.removeprefix("✍ ").strip()


def _extra_items(name: str, picks: dict, cm: dict) -> list[tuple[str, dict | str]]:
    """Ý con của một mục: [('cluster', cluster_dict) | ('text', str)].

    Ý con có 2 loại (2026-07-09): kéo một cluster từ bảng vào (giữ bằng chứng),
    hoặc user gõ tay (✍, không bằng chứng). Ref cluster đã mất thì bỏ qua.
    """
    out: list[tuple[str, dict | str]] = []
    for e in (picks.get("extras") or {}).get(name, []):
        if isinstance(e, dict):
            ref = _resolve(str(e.get("cluster") or ""), cm, picks)
            if ref:
                out.append(("cluster", ref))
        elif str(e).strip():
            out.append(("text", str(e).strip()))
    return out


def _brief_with_extras(item: dict, name: str, picks: dict, cm: dict) -> str:
    """Brief + các Ý con — mỗi phần chốt dấu câu riêng (Tầng 1 Writer ước ý đúng)."""
    parts = [item["brief"].strip()]
    for kind, val in _extra_items(name, picks, cm):
        parts.append(val["brief"].strip() if kind == "cluster" else val)
    return " ".join(p if p.endswith((".", "!", "?")) else p + "." for p in parts)


def _angle_line(item: dict) -> list[str]:
    """Dòng `Angle:` = góc gốc tại điểm tua-lại nhiều nhất, giữ để Author Extract bám đúng góc,
    KHÔNG tự sinh (yêu cầu user 2026-07-14). Chỉ in khi có angle và khác brief."""
    a = (item.get("angle") or "").strip()
    return [f"Angle: {a}"] if a and a != item["brief"].strip() else []


def _cta_line(picks: dict, name: str) -> list[str]:
    """Dòng `CTA:` = lời kêu gọi user chọn cho mục này (nút CTA trên board). Author Extract
    lồng đúng CTA đó vào kịch bản (yêu cầu user 2026-07-14)."""
    cta = str((picks.get("ctas") or {}).get(name, "")).strip()
    return [f"CTA: {cta}"] if cta else []


def _mis_line(picks: dict) -> list[str]:
    """Dòng `Misconception:` (V2, 2026-07-27) = niềm tin sai user chọn ở tab M —
    Writer thấy dòng này là bật hook THE FALSE BELIEF. Không chọn → outline V1 y cũ."""
    m = str(picks.get("misconception") or "").strip()
    return [f"Misconception: {m}"] if m else []


def _q_line(picks: dict, name: str) -> list[str]:
    """Dòng `Question:` (V2) = câu hỏi khán giả NGUYÊN VĂN user chọn cho chương này
    (nút Q trên board). Writer thấy là mở chương Question-first (Q→E lòng chương)."""
    q = str((picks.get("questions") or {}).get(name, "")).strip()
    return [f"Question: {q}"] if q else []


def _vai_note(picks: dict, name: str, cho: str = "chapter") -> str:
    """Guard V3 (2026-08-16) ghi THẲNG vào brief (khuôn guard chống-rò V2 — luật
    'guard phải nằm TRONG brief', sổ bác bỏ #5): chương TRẢ HỨA/PAYOFF nhận note
    buộc Writer phục vụ lời hứa của title; không vai/không promise → brief y cũ."""
    promise = str(picks.get("promise") or "").strip()
    if not promise:
        return ""
    if cho == "hook":
        return (f' (Note to the writer: the title promises — "{promise}". '
                "Open that loop here; do NOT pay it yet.)")
    if cho == "ending":
        return " (Note to the writer: call back the fulfilled title promise in one line.)"
    vai = (picks.get("vai") or {}).get(name)
    if vai == "tra_hua":
        return (f' (Note to the writer: this chapter PAYS THE FIRST INSTALLMENT of the '
                f'title promise — "{promise}". Deliver a real, concrete part of the '
                "answer here, not a tease.)")
    if vai == "payoff":
        return (f' (Note to the writer: this chapter delivers the FULL PAYOFF of the '
                f'title promise — "{promise}". Close the loop the hook opened.)')
    return ""


def compose_outline(picks: dict, clusters: list[dict]) -> str:
    """picks = {title, hook: name|None, chapters: [name...], ending: name|None,
    custom: {name: brief} (mục tự viết), extras: {name: [ý tự thêm...]},
    misconception: str (V2), questions: {name: câu hỏi nguyên văn} (V2),
    promise + vai: {name: tra_hua|payoff} (V3 — thành guard trong brief)}."""
    cm = _cluster_map(clusters)
    lines = [f"Title: {picks.get('title', '').strip()}", ""]

    hook = _resolve(picks.get("hook") or "", cm, picks)
    if hook:
        lines += ["HOOK", *_mis_line(picks),
                  _brief_with_extras(hook, picks["hook"], picks, cm)
                  + _vai_note(picks, picks["hook"], "hook"),
                  *_angle_line(hook), *_cta_line(picks, picks["hook"]), ""]
    i = 0
    for name in picks.get("chapters", []):
        item = _resolve(name, cm, picks)
        if item:
            i += 1
            lines += [f"CHAPTER {i} — {_display(name)}", *_q_line(picks, name),
                      _brief_with_extras(item, name, picks, cm)
                      + _vai_note(picks, name),
                      *_angle_line(item), *_cta_line(picks, name), ""]
    ending = _resolve(picks.get("ending") or "", cm, picks)
    if ending:
        lines += ["ENDING", _brief_with_extras(ending, picks["ending"], picks, cm)
                  + _vai_note(picks, picks["ending"], "ending"),
                  *_angle_line(ending), *_cta_line(picks, picks["ending"])]

    return "\n".join(lines).rstrip() + "\n"


def _cite(c: dict) -> str:
    parts = [f"{c['coverage_k']}/{c['coverage_n']} video"]
    if c.get("peak_score"):
        parts.append(f"peak z×w {c['peak_score']}")
    if c.get("pos") is not None:
        parts.append(f"pos {c['pos']}")
    if c.get("top_video"):
        parts.append("★ top-video")
    return " · ".join(parts)


def _packaging_block(picks: dict, meta: dict | None) -> list[str]:
    """Khối PACKAGING (V3) — title chính thức + lời hứa + vai chương, cho NGƯỜI UPLOAD
    đọc (bài học video RETIRING 27/07: title đổi ở khâu đăng, lời hứa không ai trả).
    Không title/promise → không in (evidence cũ y nguyên)."""
    title = str(picks.get("title") or "").strip()
    promise = str(picks.get("promise") or "").strip()
    if not (title and promise):
        return []
    out = ["## PACKAGING — dành cho người upload",
           f"- **Title chính thức:** {title}",
           f"- **Lời hứa với người click:** {promise}"]
    vai = picks.get("vai") or {}
    for name, v in vai.items():
        nhan = "TRẢ HỨA (góp 1, trước mốc AVD)" if v == "tra_hua" else "PAYOFF (~2/3 video)"
        out.append(f"- **{nhan}:** {_display(name)}")
    if meta and meta.get("avd_phut"):
        out.append(f"- AVD kênh lúc lập outline: {meta['avd_phut']}′")
    out += ["- Đăng ĐÚNG title này. Muốn đổi → quay lại board đổi để máy kiểm lại "
            "lời hứa (title đổi tay ở khâu đăng = lời hứa không ai trả).", ""]
    return out


def compose_evidence(picks: dict, clusters: list[dict], meta: dict | None = None) -> str:
    cm = _cluster_map(clusters)
    out = [f"# Outline evidence — {picks.get('title', '').strip() or '(chưa có title)'}", ""]
    out += _packaging_block(picks, meta)

    def block(header: str, name: str):
        item = _resolve(name, cm, picks)
        if not item:
            return
        c = cm.get(name)
        out.append(f"## {header}")
        out.append(f"*{_cite(c)} · videos: {', '.join(c.get('videos', []))}*" if c
                   else "*✍ tự thêm — không có bằng chứng từ video*")
        out.append("")
        out.append(item["brief"])
        if c and (c.get("angle") or "").strip() and c["angle"].strip() != item["brief"].strip():
            out.append(f"\n**Angle (đoạn tua-lại nhiều nhất):** {c['angle'].strip()}")
        for kind, val in _extra_items(name, picks, cm):
            if kind == "cluster" and val["name"] in cm:
                out.append(f"- ◇ ý con (cluster): {val['name']} — {_cite(cm[val['name']])}")
            elif kind == "cluster":
                out.append(f"- ✍ ý con (tự viết): {val['brief']}")
            else:
                out.append(f"- ✍ ý tự thêm: {val}")
        out.append("")

    if picks.get("hook"):
        block("HOOK", picks["hook"])
    for i, name in enumerate(picks.get("chapters", []), 1):
        block(f"CHAPTER {i} — {_display(name)}", name)
    if picks.get("ending"):
        block("ENDING", picks["ending"])

    missing = [s for s in ("hook", "ending") if not picks.get(s)]
    if missing:
        out.append(f"> ⚠ Thiếu: {', '.join(m.upper() for m in missing)}")
    return "\n".join(out).rstrip() + "\n"
