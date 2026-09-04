# -*- coding: utf-8 -*-
"""Test cầu đọc kho kịch bản Content Ultimate — KHÔNG tin cờ "done" trần."""
import json

import pytest

from src import kich_ban


@pytest.fixture()
def kho(tmp_path, monkeypatch):
    monkeypatch.setenv("CU_DATA_DIR", str(tmp_path))
    (tmp_path / "admin").mkdir()
    (tmp_path / "authors" / "A001_Carl-Sagan").mkdir(parents=True)
    return tmp_path


def _dat(kho, ten_tep, sections, muc_tieu=22000, title="georgia-1", so_chuong=2):
    d = kho / "authors" / "A001_Carl-Sagan"
    (d / f"{ten_tep}.md.progress.json").write_text(
        json.dumps({"total_chars": muc_tieu, "sections": sections}), encoding="utf-8")
    (d / f"{ten_tep}.md").write_text("".join(sections.values()), encoding="utf-8")
    dong = [f"Title: {title}", ""]
    for i in range(1, so_chuong + 1):
        dong.append(f"CHAPTER {i} — Ten chuong {i}")
    (d / f"{ten_tep}.outline.txt").write_text(chr(10).join(dong), encoding="utf-8")


def _log(kho, run, nguoi="ngocht", ts=1788342643.0, status="done"):
    (kho / "admin" / "history.jsonl").write_text(json.dumps(
        {"kind": "writer", "status": status, "user": nguoi, "ts": ts, "title": run}),
        encoding="utf-8")


def test_kho_trong_khong_vo(kho):
    assert kich_ban.cac_ban() == []


def test_ban_du_dieu_kien(kho):
    _dat(kho, "script-georgia-1", {"Hook": "h" * 2000, "Chapter 1": "c" * 10000,
                                   "Chapter 2": "d" * 10000})
    _log(kho, "georgia-1")
    b = kich_ban.cac_ban()[0]
    assert b["run"] == "georgia-1" and b["nguoi"] == "ngocht"
    assert b["ky_tu"] == 22000 and b["du_dieu_kien"] and b["thieu"] == ""


def test_chuong_rong_van_hien_nhung_khong_du_dieu_kien(kho):
    """Ca thật nepal-2: history ghi done mà Chapter 2 chỉ có placeholder 19 ký tự."""
    _dat(kho, "script-nepal-2", {"Hook": "h" * 2000, "Chapter 1": "c" * 19000,
                                 "Chapter 2": "x" * 19}, title="nepal-2")
    _log(kho, "nepal-2")
    b = kich_ban.cac_ban()[0]
    assert b["thieu_chuong"] == ["Chapter 2"]
    assert not b["du_dieu_kien"] and "thiếu 1 chương" in b["thieu"]


def test_hut_do_dai_bao_ro(kho):
    _dat(kho, "script-georgia-1", {"Hook": "h" * 900, "Chapter 1": "c" * 900})
    _log(kho, "georgia-1")
    b = kich_ban.cac_ban()[0]
    assert not b["du_dieu_kien"] and "hụt độ dài" in b["thieu"]


def test_ten_chuong_doc_tu_outline(kho):
    _dat(kho, "script-georgia-1", {"Hook": "h" * 2000, "Chapter 1": "c" * 20000})
    b = kich_ban.cac_ban()[0]
    ch = {c["khoa"]: c["ten"] for c in b["chuong"]}
    assert ch["Chapter 1"] == "Ten chuong 1" and ch["Hook"] == ""


def test_mot_run_mot_dong_du_nhieu_luot_chay(kho):
    """script.md và script-<run>.md cùng một run (ca thật) — chỉ hiện bản mới nhất."""
    _dat(kho, "script", {"Hook": "h" * 100}, title="georgia-1")
    _dat(kho, "script-georgia-1", {"Hook": "h" * 2000, "Chapter 1": "c" * 20000},
         title="georgia-1")
    ds = kich_ban.cac_ban()
    assert len(ds) == 1 and ds[0]["ky_tu"] == 22000


def test_bo_qua_luot_chua_xong(kho):
    _dat(kho, "script-georgia-1", {"Hook": "h" * 22000})
    _log(kho, "georgia-1", status="running")
    assert kich_ban.cac_ban()[0]["nguoi"] == ""


def test_mot_ban_tra_dung_run(kho):
    _dat(kho, "script-georgia-1", {"Hook": "h" * 22000})
    assert kich_ban.mot_ban("georgia-1")["run"] == "georgia-1"
    assert kich_ban.mot_ban("khong-co") is None
