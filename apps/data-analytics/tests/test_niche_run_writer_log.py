# -*- coding: utf-8 -*-
"""niche_run._snapshot — lỗi WRITER phải vào nhật ký lần chạy (sự cố 11/09/2026).

SỰ CỐ: writer tầng NGHĨA chết 401 ở OldNewbie_US 11/09 nhưng `_snapshot` gọi nó
với capture_output rồi BỎ output → không dòng nào trong stdout.log, khối "Nhật ký
lần chạy" im lặng; chỉ lần ra được bằng cách tự chạy tay writer.

Luật ghim: writer hỏng → stdout.log có dòng lỗi (tinh_trang bắt được); writer ổn →
có dòng xác nhận, không sinh cảnh báo giả.
"""
import sys
from pathlib import Path

from src import niche_run


def _script(tmp_path: Path, ten: str, noi_dung: str) -> Path:
    p = tmp_path / ten
    p.write_text(noi_dung, encoding="utf-8")
    return p


def _du_an(tmp_path: Path, monkeypatch, writer_src: str) -> Path:
    goc = tmp_path / "projects"
    nd = goc / "Proj_X" / "niche-data"
    nd.mkdir(parents=True)
    (nd / "stdout.log").write_text("✓ Pipeline done — report: x.xlsx\n", encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(goc))
    ok = _script(tmp_path, "ok.py", "import sys; sys.exit(0)\n")
    monkeypatch.setattr(niche_run, "_WRITER_PY", _script(tmp_path, "writer.py", writer_src))
    monkeypatch.setattr(niche_run, "_BUILD_BC_PY", ok)
    monkeypatch.setattr(niche_run, "_SNAPSHOT_PY", ok)
    return nd


def test_writer_hong_thi_nhat_ky_co_dong_loi(tmp_path, monkeypatch):
    nd = _du_an(tmp_path, monkeypatch,
                "print('khoa LLM: KET (phan_tich)')\n"
                "print('LOI LLM: GLM API 401 token expired or incorrect')\n"
                "import sys; sys.exit(3)\n")
    niche_run._snapshot("Proj_X")
    t = niche_run.tinh_trang("Proj_X")
    assert any("401" in dong for dong in t["loi"]), t     # đúng lỗi 11/09: im lặng
    assert "bao_cao_writer" in (nd / "stdout.log").read_text(encoding="utf-8")


def test_writer_qua_gio_van_ghi_nhat_ky_va_van_dung_bao_cao(tmp_path, monkeypatch):
    """Lỗ bắt được khi nghiệm thu bản chép 11/09: writer claude-opus-5 chạy quá trần
    → TimeoutExpired rơi vào except chung → KHÔNG dòng nhật ký nào VÀ builder bị bỏ
    qua (HTML của lần trước ở lại, gắn vào snapshot mới)."""
    nd = _du_an(tmp_path, monkeypatch, "import sys; sys.exit(0)\n")
    moc = tmp_path / "builder-da-chay.txt"
    monkeypatch.setattr(niche_run, "_BUILD_BC_PY", _script(
        tmp_path, "builder.py", f"open(r'{moc}', 'w').write('x')\n"))
    that = niche_run.subprocess.run

    def gia(cmd, *a, **kw):
        if str(niche_run._WRITER_PY) in [str(x) for x in cmd]:
            raise niche_run.subprocess.TimeoutExpired(cmd, kw.get("timeout", 0))
        return that(cmd, *a, **kw)
    monkeypatch.setattr(niche_run.subprocess, "run", gia)
    niche_run._snapshot("Proj_X")
    t = niche_run.tinh_trang("Proj_X")
    assert any("quá thời gian" in dong for dong in t["loi"]), t
    assert moc.is_file(), "writer quá giờ không được kéo builder chết theo"


def test_writer_on_thi_khong_canh_bao_gia(tmp_path, monkeypatch):
    nd = _du_an(tmp_path, monkeypatch, "print('DONE — bao_cao_nghia.json')\n")
    niche_run._snapshot("Proj_X")
    assert niche_run.tinh_trang("Proj_X")["loi"] == []
    assert "bao_cao_writer" in (nd / "stdout.log").read_text(encoding="utf-8")
