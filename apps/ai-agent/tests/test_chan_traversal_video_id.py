# -*- coding: utf-8 -*-
"""GĐ2 — ai-agent: video_id từ URL không được thoát khỏi kho (05/09/2026).

LỖ T1 (rà 05/09, sổ `docs/bao-mat-internet.md`): `video_id_tu_url` trả THẲNG phần
cuối URL, không lọc. Giá trị đó thành `doc_code` rồi thành TÊN FILE ghi ra đĩa:
    doc_code = f"YT-{video_id}"
    file_path = kho / ngan / f"{doc_code}_YouTube.md"
    os.replace(tam, file_path)

TÁI HIỆN 05/09 (chạy thật, trước khi vá):
    video_id_tu_url("https://youtube.com/watch?v=../../../../evil")
      -> '../../../../evil'
    đường ghi -> kho/03_KinhDoanh/YT-../../../../evil_YouTube.md   ← THOÁT KHO

Dùng đường dẫn CỐ ĐỊNH + os.replace (KHÔNG qua `duong_dan_khong_trung`) nên GHI ĐÈ
IM LẶNG bất kỳ file .md/.txt nào tên khớp; nội dung do người gửi kiểm soát.
Ghi trúng `src/static` (được mount), `rules/*.csv` (luật ngoài code) hay `.env` là
nghiêm trọng.

Vá: lọc ngay tại nguồn — id YouTube thật chỉ gồm [0-9A-Za-z_-], chỉ gồm [0-9A-Za-z_-] (bộ ký tự mới là thứ chặn traversal).
"""
import pytest

from src.nap_youtube import video_id_tu_url


DOC_HAI = [
    "https://youtube.com/watch?v=../../../../evil",
    "https://youtu.be/../../etc/passwd",
    "https://youtube.com/watch?v=" + ".." + chr(92) + "evil",   # chr(92) = backslash
    "../../../evil",
    "https://youtube.com/watch?v=" + "a" * 300,
    "https://youtube.com/watch?v=x/y",
]


@pytest.mark.parametrize("url", DOC_HAI)
def test_url_doc_hai_khong_ra_id_nguy_hiem(url):
    """Không bao giờ trả về chuỗi dùng làm tên file được mà chứa ký tự đường dẫn."""
    vid = video_id_tu_url(url)
    if vid is None:
        return                       # từ chối hẳn cũng là kết quả đúng
    assert "/" not in vid and chr(92) not in vid, f"id còn ký tự đường dẫn: {vid!r}"
    assert ".." not in vid, f"id còn '..': {vid!r}"
    assert len(vid) <= 40, f"id quá dài: {len(vid)}"


@pytest.mark.parametrize("url,mong", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/abc123XYZ_-", "abc123XYZ_-"),
    ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
])
def test_url_hop_le_van_chay_nhu_cu(url, mong):
    """KHÔNG được phá tính năng: mọi dạng URL thật vẫn ra đúng id."""
    assert video_id_tu_url(url) == mong
