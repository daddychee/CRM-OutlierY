# -*- coding: utf-8 -*-
"""Thuoc NHAN DANG TAC GIA — Burrows's Delta (C4, 24/08/2026).

Vi sao can them mot thuoc nua khi app da co hai:
  nhom A (deai)  — "co giong may khong": dem dong tac + em-dash. Khong biet tac gia.
  nhom B (nhip)  — "co dung nhip khong": tu/cau, % cau cut. Hai tac gia cung nhip
                   thi thuoc nay khong phan biet noi.
  DELTA          — "giong AI NHAT trong kho": xep hang van ban vua viet tren TOAN
                   BO cac ho so. Day moi la cau hoi ma author extract sinh ra de tra loi.

Cach lam (Burrows 2002, ban goc, khong bien tau): lay N tu pho bien nhat cua toan
kho, doi moi corpus thanh vector TAN SUAT TUONG DOI, chuan hoa z-score theo TUNG TU
tren tap tac gia, roi khoang cach = trung binh |z_a - z_b|. Cang nho cang giong.

Ba dieu can biet truoc khi tin con so:
  1. Delta do bang HU TU (the, of, we, you...) — thu nguoi viet dung theo thoi quen,
     khong theo chu de. Do la ly do no khong bi chu de danh lua nhu n-gram noi dung.
  2. Can it nhat hai tac gia de co phuong sai ma chuan hoa. Mot tac gia -> vo nghia.
  3. Van ban duoi DU_MAU_TU tu thi con so dao dong manh — van xep hang, nhung PHAI
     bao la chua du mau (luat A3: bao, khong im lang).

Python do het, 0 token, khong goi model — cung luat voi Quant Engine.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from .textutils import tokenize_words

SO_TU_MAC_DINH = 150      # so tu pho bien nhat dung lam truc do (Burrows dung 100-200)
DU_MAU_TU = 500           # duoi nguong nay Delta dao dong manh — bao "chua du mau"


def _tan_suat(texts: list[str], tu_vung: list[str]) -> dict[str, float]:
    """Tan suat tuong doi cua tung tu trong tu vung (so lan / tong tu)."""
    dem: Counter = Counter()
    tong = 0
    for t in texts:
        tu = [w.lower() for w in tokenize_words(t)]
        dem.update(tu)
        tong += len(tu)
    tong = tong or 1
    return {w: dem.get(w, 0) / tong for w in tu_vung}


def xay_bang(kho: dict[str, list[str]], so_tu: int = SO_TU_MAC_DINH) -> dict:
    """Dung bang doi chieu tu kho {ma_tac_gia: [van ban]}.

    Tra {"tu_vung", "mean", "sd", "z": {ma: {tu: z}}, "so_tac_gia"}.
    """
    if len(kho) < 2:
        raise ValueError("Delta can it nhat HAI tac gia de chuan hoa — mot tac gia "
                         "thi khong co phuong sai nao de so.")

    # Tu vung: pho bien nhat tren TOAN kho, nhung uu tien tu XUAT HIEN O NHIEU tac gia
    # (tu chi mot nguoi dung la dau hieu chu de, khong phai thoi quen hanh van).
    dem_chung: Counter = Counter()
    co_mat: Counter = Counter()
    for ma, texts in kho.items():
        tu = [w.lower() for t in texts for w in tokenize_words(t)]
        dem_chung.update(tu)
        for w in set(tu):
            co_mat[w] += 1
    ung_vien = [w for w, _ in dem_chung.most_common() if co_mat[w] >= 2]
    tu_vung = ung_vien[:so_tu] or [w for w, _ in dem_chung.most_common(so_tu)]

    ts = {ma: _tan_suat(texts, tu_vung) for ma, texts in kho.items()}
    mean, sd = {}, {}
    for w in tu_vung:
        vals = [ts[ma][w] for ma in kho]
        mean[w] = statistics.mean(vals)
        sd[w] = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    # sd = 0: moi tac gia dung tu do y het nhau -> khong mang thong tin phan biet, va
    # chia cho 0 thi vo nghia. Bo han khoi truc do thay vi vá bang epsilon.
    tu_vung = [w for w in tu_vung if sd[w] > 0]
    mean = {w: mean[w] for w in tu_vung}
    sd = {w: sd[w] for w in tu_vung}
    z = {ma: {w: (ts[ma][w] - mean[w]) / sd[w] for w in tu_vung} for ma in kho}
    return {"tu_vung": tu_vung, "mean": mean, "sd": sd, "z": z, "so_tac_gia": len(kho)}


def _z_cua(text: str, bang: dict) -> dict[str, float]:
    ts = _tan_suat([text], bang["tu_vung"])
    return {w: (ts[w] - bang["mean"][w]) / bang["sd"][w] for w in bang["tu_vung"]}


def _khoang_cach(za: dict[str, float], zb: dict[str, float]) -> float:
    if not za:
        return 0.0
    return sum(abs(za[w] - zb[w]) for w in za) / len(za)


def delta_giua(ma_a: str, ma_b: str, bang: dict) -> float:
    """Khoang cach giua hai tac gia da co trong bang."""
    return _khoang_cach(bang["z"][ma_a], bang["z"][ma_b])


def xep_hang(text: str, bang: dict, tra_co: bool = False):
    """Xep hang tac gia theo do gan voi `text`. Cang nho cang giong.

    tra_co=True -> {"hang": [...], "du_mau": bool, "so_tu": int} de nguoi doc biet
    co nen tin con so khong. Mac dinh tra thang danh sach cho gon.
    """
    so_tu = len(tokenize_words(text))
    z = _z_cua(text, bang)
    hang = sorted(
        ({"ma": ma, "delta": round(_khoang_cach(z, zb), 4)} for ma, zb in bang["z"].items()),
        key=lambda r: r["delta"],
    )
    if not tra_co:
        return hang
    return {"hang": hang, "du_mau": so_tu >= DU_MAU_TU, "so_tu": so_tu}


def ghi_bang(bang: dict, duong: str | Path) -> None:
    Path(duong).write_text(json.dumps(bang, ensure_ascii=False), encoding="utf-8")


def doc_bang(duong: str | Path) -> dict:
    return json.loads(Path(duong).read_text(encoding="utf-8"))


def ma_tran(bang: dict) -> list[dict]:
    """Khoang cach doi mot giua moi cap tac gia — de soi suc khoe kho.

    Cong dung that (do 24/08): ba ho so A003/A008/A011 tro vao CUNG mot corpus.
    Delta gan 0 giua chung la bang chung may doc duoc, khong phai nghi ngo bang mat.
    """
    ma = sorted(bang["z"])
    return [{"a": a, "b": b, "delta": round(delta_giua(a, b, bang), 4)}
            for i, a in enumerate(ma) for b in ma[i + 1:]]


NGUONG_BAN_SAO = 0.05     # do that 24/08: ho so tro CUNG mot corpus cho delta = 0.000


def nhom_ban_sao(bang: dict, nguong: float = NGUONG_BAN_SAO) -> list[list[str]]:
    """Gom cac ho so gan nhu KHONG phan biet duoc (cung mot corpus dung hai ten).

    Do that 24/08 tren kho 12 ho so: A003/A008/A011 delta = 0.000 (da biet tu 23/08)
    va A007 <-> A012 cung 0.000 (chua ai biet). Tuc kho chi co 8 giong that. Nguoi
    dung dang chon giua nhung cai ten khac nhau ma ben trong la mot.
    """
    ma = sorted(bang["z"])
    cha = {m: m for m in ma}

    def goc(x):
        while cha[x] != x:
            cha[x] = cha[cha[x]]
            x = cha[x]
        return x

    for i, a in enumerate(ma):
        for b in ma[i + 1:]:
            if delta_giua(a, b, bang) < nguong:
                cha[goc(a)] = goc(b)
    nhom: dict[str, list[str]] = {}
    for m in ma:
        nhom.setdefault(goc(m), []).append(m)
    return [sorted(v) for v in nhom.values() if len(v) > 1]
