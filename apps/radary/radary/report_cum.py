# -*- coding: utf-8 -*-
"""Xuat REPORT mot tu khoa (khoi A + B + C) ra Markdown — Owner chot 22/08.

VI SAO MARKDOWN: Owner noi "toi se dua cho AI de doc ky bao cao". Markdown la
dinh dang re token nhat ma van giu cau truc (heading + bang), moi LLM parse
chuan khong can xu ly truoc; HTML ton 2-3 lan token cho the markup, PDF thi bang
hay vo thanh dong lon xon khi trich xuat. JSON tho KHONG kem mac dinh (xem docstring dung()).

VAN CHONG BIA CHO BAO CAO: moi so deu ghi RO don vi + thoi diem do + pham vi;
nguon nao KHONG co du lieu thi ghi thang "chua hoi" hoac ly do, TUYET DOI khong
bo trong de nguoi (hay AI) doc nham thanh "bang khong". Cuoi bao cao co muc
"Ranh gioi du lieu" liet ke thu bao cao KHONG tra loi duoc.
"""
from __future__ import annotations

import json
import time


def _ngay(ts: float | None) -> str:
    return time.strftime("%d/%m/%Y %H:%M", time.localtime(ts)) if ts else "—"


def _so(x, mac_dinh: str = "—") -> str:
    if x is None:
        return mac_dinh
    if isinstance(x, float):
        return f"{x:,.2f}".replace(",", ".")
    return f"{x:,}".replace(",", ".")


def _link_video(yt_id: str) -> str:
    return f"https://www.youtube.com/watch?v={yt_id}" if yt_id else ""


def dung(cum: str, pool: dict, a: dict, b: dict | None, ts: float | None = None,
         kem_json: bool = False) -> str:
    """Dung bao cao Markdown tu ban luu — 0 quota, khong goi nguon nao.

    kem_json=False (mac dinh): KHONG nhet JSON tho. Do that ban dau: JSON chiem
    29k/42k ky tu — nang gap doi phan doc, phan tac dung dung muc dich "dua cho AI
    doc" ma Owner dat ra. Ai can so chinh xac de tinh toan thi goi ?json=1.
    """
    b = b or {}
    yt = b.get("youtube") or {}
    tr = b.get("trends") or {}
    gg = b.get("google") or {}
    nw = b.get("news") or {}
    wk = b.get("wiki") or {}
    rd = b.get("reddit") or {}
    d: list[str] = []
    v = d.append

    v(f'# Báo cáo từ khoá — "{cum}"')
    v("")
    v(f"- **Pool:** {pool.get('ten') or '—'}"
      f"{' · ngách ' + pool['ngach'] if pool.get('ngach') else ''}"
      f"{' · thị trường ' + pool['market'] if pool.get('market') else ''}")
    v(f"- **Thời điểm đo:** {_ngay(ts)}"
      + (f" · khối ngoài đo lúc {_ngay(b.get('ts'))}" if b.get("ts") else ""))
    v(f"- **Quy mô pool:** {_so(pool.get('so_video'))} video · "
      f"{_so(pool.get('so_kenh'))} kênh · {_so(pool.get('video_moi_30_ngay'))} video mới 30 ngày")
    v("")
    v("> Mọi số so với **chính pool này tại thời điểm đo**, không phải chuẩn ngành. "
      "Nguồn nào chưa hỏi thì ghi rõ — đừng đọc thành số không.")
    v("")

    # ---------------- A ----------------
    v("## A · Trong pool")
    v("")
    if not a.get("co_du_lieu"):
        v(f"*{a.get('ly_do') or 'Không có dữ liệu.'}*")
        v("")
    else:
        v("| Chỉ số | Giá trị | Đọc là |")
        v("|---|---|---|")
        v(f"| Video khớp cụm | {_so(a.get('so_video'))} | trên {_so(a.get('so_kenh'))} kênh |")
        v(f"| Tỉ trọng video của pool | {a.get('ti_trong_video')}% | phần chỗ cụm này chiếm |")
        v(f"| Tỉ trọng view của pool | {a.get('ti_trong_view')}% | phần view cụm này ăn |")
        vph, vpool = a.get("vph_giua"), a.get("vph_giua_pool")
        so_sanh = f"{vph / vpool:.1f}× trung vị pool ({vpool})" if vph and vpool else "—"
        v(f"| View/giờ (trung vị) | {_so(vph)} | {so_sanh} |")
        v("")
        dc = a.get("doi_chieu")
        if dc:
            v(f"**Đối chiếu cụm rút gọn `{dc['cum']}`:** {_so(dc.get('so_video'))} video · "
              f"{_so(dc.get('so_kenh'))} kênh · {dc.get('ti_trong_view')}% view pool. "
              "Cụm dài đo cạnh tranh trong *công thức* ngách, cụm ngắn đo *chủ đề*.")
            v("")
        lua = [x for x in (a.get("lua") or []) if x.get("thang")][-12:]
        if lua:
            v("### Xu hướng theo lứa đăng")
            v("")
            v("| Tháng | Video mới | View/ngày (trung vị) |")
            v("|---|---|---|")
            for x in lua:
                v(f"| {x['thang']} | {x['so_video']} | "
                  f"{_so(x.get('view_moi_ngay')) if x.get('du_mau') else '— ít mẫu'} |")
            v("")
        kenh = a.get("top_kenh") or []
        if kenh:
            v("### Kênh đẩy mạnh chủ đề này (12 tháng)")
            v("")
            v("| Kênh | Video | Tổng view | TB view/video |")
            v("|---|---|---|---|")
            for k in kenh:
                v(f"| {k.get('kenh') or '—'} | {k.get('so_video')} | {_so(k.get('views'))} | "
                  f"{_so(k.get('view_tb'))} |")
            v("")
            for k in kenh:
                vids = k.get("video") or []
                if not vids:
                    continue
                v(f"**{k.get('kenh')}** — bài về cụm này:")
                v("")
                for x in vids:
                    ngay = f"{x['ngay']} · " if x.get("ngay") else ""
                    v(f"- {_so(x.get('views'))} view · {ngay}"
                      f"[{x.get('title')}]({_link_video(x.get('yt_id'))})")
                v("")
        mn = a.get("moi_nhat")
        if mn:
            v(f"**Bài gần nhất trong pool:** [{mn.get('title')}]({_link_video(mn.get('yt_id'))}) — "
              f"{mn.get('kenh')} · {_so(mn.get('views'))} view")
            v("")

    # ---------------- B ----------------
    v(f"## B · YouTube market — ngoài pool ({pool.get('market') or 'chưa gắn thị trường'})")
    v("")
    if not yt.get("co_du_lieu"):
        v(f"*{yt.get('ly_do') or 'Chưa hỏi.'}*")
        v("")
    else:
        v(f"- **{_so(yt.get('tong_view_90n'))} view** trong 90 ngày qua "
          f"(top {yt.get('so_ket_qua')} video) · view giữa {_so(yt.get('view_giua'))}")
        knn = yt.get("kenh_moi_noi") or []
        v(f"- **Kênh nhỏ lọt top:** {len(knn)}"
          + (" — chủ đề chưa bị kênh lớn khoá cửa" if knn else " — kênh lớn đang giữ chỗ"))
        v("")
        v("> Không nền tảng nào công bố lượng tìm kiếm YouTube (API trả 1.000.000 cho mọi "
          "truy vấn — số giả). Đây là **view thật** thị trường đang trả.")
        v("")
        top = yt.get("top_video") or []
        if top:
            v("| View | Video | Kênh | Subs | Tuổi |")
            v("|---|---|---|---|---|")
            for x in top[:10]:
                v(f"| {_so(x.get('views'))} | [{x.get('title')}]({_link_video(x.get('yt_id'))}) | "
                  f"{x.get('kenh')} | {_so(x.get('subs'), 'ẩn')} | {x.get('tuoi_ngay')} ngày |")
            v("")
        if knn:
            v("**Kênh nhỏ đang thắng chủ đề này** (dưới 50k subs mà vẫn lọt top view):")
            v("")
            for k in knn:
                v(f"- {k.get('kenh')} · {_so(k.get('subs'))} subs · {k.get('so_video_top')} "
                  f"video trong top · bài tốt nhất {_so(k.get('view_tot_nhat'))} view")
            v("")
    bt = b.get("bien_the") or []
    if bt:
        v("### YouTube Autocomplete — cụm người ta gõ thật")
        v("")
        for m in bt:
            nguon = "Bing" if m.get("nguon") == "bing" else f"{m.get('do_phu')} hướng gõ"
            v(f"- `{m.get('cum')}` — {nguon}")
        v("")

    # ---------------- C ----------------
    v("## C · External traffic — ngoài nền tảng YouTube")
    v("")
    v("### Google Trends")
    v("")
    if not tr.get("co_du_lieu"):
        v(f"*{tr.get('ly_do') or 'Chưa hỏi.'}*")
    else:
        xh = tr.get("xu_huong") or {}
        v(f"- **Xu hướng 12 tháng:** {xh.get('chieu')} {xh.get('phan_tram')}% "
          f"({tr.get('geo')} · {tr.get('timeframe')})")
        for ten, khoa in (("Truy vấn ĐANG LÊN về chủ đề", "rising"),
                          ("Truy vấn phổ biến nhất", "top")):
            ds = tr.get(khoa) or []
            if ds:
                v("")
                v(f"**{ten}:**")
                v("")
                for x in ds[:12]:
                    v(f"- `{x.get('cum')}` — {x.get('gia_tri')}")
        nn = tr.get("nhom_nguoi") or []
        if nn:
            v("")
            v(f"**Người tìm chủ đề này cũng tìm gì** ({len(nn)} truy vấn — KHÔNG phải về chủ đề, "
              "Google xếp theo nhóm người cùng tìm):")
            v("")
            v(", ".join(f"`{x.get('cum')}`" for x in nn[:12]))
        vg = tr.get("vung") or []
        if vg:
            v("")
            v("**Vùng quan tâm nhất** (thang 0–100): "
              + " · ".join(f"{x['vung']} {x['gia_tri']}" for x in vg[:10]))
    v("")

    v("### Câu hỏi thật người ta hỏi")
    v("")
    if not gg.get("co_du_lieu"):
        v(f"*{gg.get('ly_do') or 'Chưa hỏi.'}*")
    else:
        for h in (gg.get("cau_hoi") or []):
            v(f"- {h}")
        if gg.get("lien_quan"):
            v("")
            v("**Tìm kiếm liên quan:** " + " · ".join(f"`{x}`" for x in gg["lien_quan"]))
        if gg.get("web"):
            v("")
            v("**Ai đang xếp hạng cho từ khoá này:**")
            v("")
            for w in gg["web"][:10]:
                v(f"- [{w.get('tieu_de')}]({w.get('link')}) — {w.get('nguon')}")
    v("")

    v("### Reddit")
    v("")
    if not rd.get("co_du_lieu"):
        v(f"*{rd.get('ly_do') or 'Chưa hỏi.'}*")
    else:
        v(f"- **{_so(rd.get('tong_upvote'))} upvote** · {_so(rd.get('tong_binh_luan'))} bình luận "
          f"trên {len(rd.get('bai') or [])} bài ({rd.get('ky')})")
        sub = rd.get("sub") or []
        if sub:
            v(f"- **Cộng đồng bàn nhiều nhất:** "
              + " · ".join(f"r/{x['sub']} ({_so(x['upvote'])})" for x in sub))
        v("")
        v("| Upvote | Bình luận | Sub | Bài |")
        v("|---|---|---|---|")
        for x in (rd.get("bai") or [])[:10]:
            v(f"| {_so(x.get('upvote'))} | {x.get('binh_luan')} | r/{x.get('sub')} | "
              f"[{x.get('tieu_de')}]({x.get('link')}) |")
    v("")

    v("### Google News")
    v("")
    if not nw.get("co_du_lieu"):
        v(f"*{nw.get('ly_do') or 'Chưa hỏi.'}*")
    else:
        for x in (nw.get("bai") or [])[:10]:
            v(f"- [{x.get('tieu_de')}]({x.get('link')}) — {x.get('nguon')} · {x.get('ngay')}")
    v("")

    v("### Wikipedia")
    v("")
    if not wk.get("co_du_lieu"):
        v(f"*{wk.get('ly_do') or 'Chưa hỏi.'}*")
    else:
        xh = wk.get("xu_huong") or {}
        v(f'- Bài "{wk.get("bai")}" — {xh.get("chieu")} {xh.get("phan_tram")}% · '
          f"tháng chốt gần nhất {_so(wk.get('xem_thang_cuoi'))} lượt xem")
        if wk.get("bai_lien_quan"):
            v(f"- Bài liên quan: {' · '.join(wk['bai_lien_quan'])}")
    v("")

    # ---------------- ranh gioi ----------------
    v("## Ranh giới dữ liệu — báo cáo này KHÔNG trả lời được")
    v("")
    v("- **Lượng tìm kiếm trên YouTube**: không nền tảng nào công bố; API trả 1.000.000 cho "
      "mọi truy vấn nên đó là số giả. Thước duy nhất đáng tin là *view thật* ở khối B.")
    v("- **Số liệu quá khứ của view**: hệ chỉ có view hiện tại, không có lịch sử view theo cụm. "
      "Biểu đồ lứa đăng dựng từ ngày đăng, không phải từ view theo thời gian.")
    v("- **Khối A chỉ tính các kênh trong pool** — không phải toàn YouTube. Muốn ngoài pool thì "
      "đọc khối B.")
    thieu = [t for t, o in (("YouTube market", yt), ("Google Trends", tr),
                            ("Câu hỏi thật", gg), ("Reddit", rd))
             if not o.get("co_du_lieu")]
    if thieu:
        v(f"- **Chưa hỏi:** {', '.join(thieu)} — phần này trống vì chưa chạy, "
          "không phải vì không có dữ liệu.")
    v("")
    if kem_json:
        v("---")
        v("")
        v("<details><summary>Dữ liệu thô (JSON) — cho công cụ cần tính toán chính xác</summary>")
        v("")
        v("```json")
        v(json.dumps({"cum": cum, "pool": pool, "trong_pool": a, "ngoai": b,
                      "xuat_luc": time.time()}, ensure_ascii=False))
        v("```")
        v("")
        v("</details>")
        v("")
    v(f"*Xuất từ RadarY · Mapping lúc {_ngay(time.time())} · 0 quota (dựng từ bản lưu).*")
    return "\n".join(d)
