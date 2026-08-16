from voiceprofile import library


def test_slugify():
    assert library.slugify("Carl Sagan") == "Carl-Sagan"
    assert library.slugify("  Nguyễn / Du  ") == "Nguyễn-Du"
    assert library.slugify("!!!") == "author"


def test_next_code_sequential():
    assert library.next_code([]) == "A001"
    assert library.next_code([{"code": "A001"}, {"code": "A003"}]) == "A004"
    assert library.next_code([{"code": "bad"}]) == "A001"


def test_ensure_author_creates_then_reuses(tmp_path):
    reg = tmp_path / "index.json"
    a = library.ensure_author("Carl Sagan", path=reg)
    assert a["code"] == "A001"
    assert a["slug"] == "Carl-Sagan"
    # goi lai cung ten -> dung lai, khong tao A002
    a2 = library.ensure_author("carl sagan", path=reg)  # khac hoa/thuong
    assert a2["code"] == "A001"
    b = library.ensure_author("Neil Tyson", path=reg)
    assert b["code"] == "A002"


def test_register_and_list_profile(tmp_path):
    reg = tmp_path / "index.json"
    prof = tmp_path / "A001_Carl-Sagan" / "profile.json"
    prof.parent.mkdir(parents=True)
    prof.write_text("{}", encoding="utf-8")
    entry = library.register_profile("Carl Sagan", str(prof), corpus=str(tmp_path), path=reg)
    assert entry["profile"] == str(prof.resolve())
    listed = library.list_authors(path=reg)
    assert len(listed) == 1 and listed[0]["name"] == "Carl Sagan"


def test_list_authors_skips_missing_profile(tmp_path):
    reg = tmp_path / "index.json"
    library.register_profile("Ghost", str(tmp_path / "gone" / "profile.json"), path=reg)
    assert library.list_authors(path=reg) == []                 # profile khong ton tai -> bo
    assert len(library.list_authors(path=reg, existing_only=False)) == 1


def test_author_folder_name():
    assert library.author_folder_name({"code": "A007", "slug": "Neil-Tyson"}) == "A007_Neil-Tyson"


def test_created_by_ghi_nguoi_extract(tmp_path):
    """✍ người viết trên GUI thư viện (2026-07-22): entry ghi thành viên team chạy extract;
    entry cũ không có field → payload trả chuỗi rỗng, GUI ẩn."""
    reg = tmp_path / "index.json"
    a = library.ensure_author("Carl Sagan", path=reg, created_by="thanh")
    assert a["created_by"] == "thanh"
    # ensure lại không đổi người tạo (entry đã có thì trả nguyên)
    assert library.ensure_author("Carl Sagan", path=reg, created_by="ngocth")["created_by"] == "thanh"
    # register_profile (extract xong) cập nhật người viết SAU CÙNG; rỗng thì giữ nguyên
    prof = tmp_path / "p.json"
    prof.write_text("{}", encoding="utf-8")
    e = library.register_profile("Carl Sagan", str(prof), path=reg, created_by="ngocth")
    assert e["created_by"] == "ngocth"
    e2 = library.register_profile("Carl Sagan", str(prof), path=reg, created_by="")
    assert e2["created_by"] == "ngocth"
    # entry cũ (không có field) không nổ khi đọc
    data = library.load_registry(reg)
    del data["authors"][0]["created_by"]
    library.save_registry(data, reg)
    assert library.list_authors(path=reg)[0].get("created_by") is None
