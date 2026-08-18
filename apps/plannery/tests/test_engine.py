"""Test engine v2 bằng ví dụ tính tay — chỉ dùng tên giả (CLAUDE.md nguyên tắc 6).

Mỗi test ghi rõ phép tính tay trong docstring; con số trong assert chép từ đó.
Mốc: thứ Hai 13/07/2026; tuần làm việc T2–T7. Đơn vị năng suất theo khâu:
content = KỊCH BẢN/ngày (1 unit = 1 ÷ năng suất); editor = PHÚT VIDEO/ngày
(1 unit = thời lượng ÷ năng suất). Người rảnh nhận unit có ngày đăng gần nhất (EDD).
"""

from datetime import date

import pytest

from planner import (
    Assignment,
    BestPerformance,
    BottleneckWarning,
    LateWarning,
    Person,
    PlanInput,
    Project,
    StageConfig,
    UnderStandardWarning,
    UnstaffedWarning,
    Video,
    compute_schedule,
    default_videos,
)

MONDAY = date(2026, 7, 13)


def make_project(pid="p1", name="Dự án A", minutes=30.0, videos=(), stock=0, start=MONDAY,
                 content_cfg=None, editor_cfg=None, best=None):
    return Project(
        id=pid, name=name, start_date=start, video_minutes=minutes,
        stages=(content_cfg or StageConfig("content"), editor_cfg or StageConfig("editor")),
        videos=tuple(videos), script_stock=stock, best_performance=best,
    )


CONTENT_A = Person("c1", "Content A", "content", standard_rate=1, last_week_rate=1)
EDITOR_1 = Person("e1", "Editor 1", "editor", standard_rate=30, last_week_rate=30)
# KPI thấp hơn (người mới): lịch xếp theo CHUẨN 15 phút/ngày; tuần trước 7.5 → cảnh báo 50%
EDITOR_2 = Person("e2", "Editor 2", "editor", standard_rate=15, last_week_rate=7.5)


def test_chuoi_hai_khau_co_feedback():
    """Case (a) — vòng feedback n lần qua 2 khâu, video 30 phút.

    Content A 1 kịch bản/ngày → kịch bản 1 ngày công: work [0,1], chờ [1,2],
    sửa [2,2.5] → xong 2.5 (nguyên trong ngày 3 — hợp lệ).
    Editor 1 30 phút/ngày → dựng 1 ngày: work [2.5,3.5]; vòng sửa 1 ngày bắt đầu
    4.5 vắt ngày → NÉN về cuối ngày [4.5,5.0] với 0.5 QUÁ GIỜ (sửa xong trong
    ngày); chờ [5,6]; sửa 2 [6,7] tròn ngày → bàn giao 7.0 = thứ Hai 20/07.
    Ngày đăng 17/07 (ngày làm việc 5) → trễ 7 − 5 = 2 ngày làm việc.
    """
    project = make_project(
        videos=[Video(1, "Video mở kênh", date(2026, 7, 17))],
        content_cfg=StageConfig("content", 1, 1.0, 0.5),
        editor_cfg=StageConfig("editor", 2, 1.0, 1.0),
    )
    result = compute_schedule(PlanInput(
        [CONTENT_A, EDITOR_1], [project],
        [Assignment("c1", "p1"), Assignment("e1", "p1")],
    ))
    (video,) = result.projects[0].videos
    content, editor = video.stages
    assert [(s.kind, s.start_t, s.end_t) for s in content.segments] == [
        ("work", 0.0, 1.0), ("wait", 1.0, 2.0), ("revision", 2.0, 2.5),
    ]
    assert (content.person_name, content.done_t, content.done_date) == (
        "Content A", 2.5, date(2026, 7, 15),
    )
    assert [(s.kind, s.start_t, s.end_t) for s in editor.segments] == [
        ("work", 2.5, 3.5), ("wait", 3.5, 4.5), ("revision", 4.5, 5.0),
        ("wait", 5.0, 6.0), ("revision", 6.0, 7.0),
    ]
    assert editor.segments[2].overtime == pytest.approx(0.5)  # nén 1 ngày công vào nửa ngày
    assert (video.handoff_t, video.handoff_date) == (7.0, date(2026, 7, 20))
    assert video.late_workdays == 2
    (w,) = result.warnings
    assert isinstance(w, LateWarning)
    assert "«Video mở kênh»" in w.message() and "trễ 2 ngày làm việc" in w.message()


def test_edd_nguoi_ganh_hai_du_an():
    """Case (b) — một người 2 dự án; EDD quyết thứ tự, không phải thứ tự khai báo.

    Dự án A khai báo trước (video 15' = 0.5 ngày, đăng 18/07);
    dự án B khai báo sau (video 30' = 1 ngày, đăng 15/07 — gần hơn).
    Editor 1 làm B trước: [0,1] → giao 13/07; rồi A [1,1.5] → giao 14/07. Đều kịp.
    """
    pa = make_project(pid="pa", name="Dự án A", minutes=15,
                      videos=[Video(1, publish_date=date(2026, 7, 18))], stock=1)
    pb = make_project(pid="pb", name="Dự án B", minutes=30,
                      videos=[Video(1, publish_date=date(2026, 7, 15))], stock=1)
    result = compute_schedule(PlanInput(
        [EDITOR_1], [pa, pb], [Assignment("e1", "pa"), Assignment("e1", "pb")],
    ))
    (va,) = result.projects[0].videos
    (vb,) = result.projects[1].videos
    assert vb.stages[0].segments[0].start_t == 0.0
    assert (vb.handoff_t, vb.handoff_date) == (1.0, date(2026, 7, 13))
    assert va.stages[0].segments[0].start_t == 1.0
    assert (va.handoff_t, va.handoff_date) == (1.5, date(2026, 7, 14))
    assert result.warnings == ()


def test_hai_editor_nang_suat_khac_nhau():
    """Case (d) — 2 editor khác KPI, 4 video 30' (kho đủ kịch bản).

    Lịch xếp theo CHUẨN TUYỂN DỤNG: Editor 1 KPI 30 phút/ngày → 1 ngày/video;
    Editor 2 KPI 15 → 2 ngày/video. Rảnh sớm nhất nhận trước, hoà → thứ tự khai báo:
    v1→E1 [0,1], v2→E2 [0,2], v3→E1 [1,2], v4 hoà t=2 → E1 [2,3].
    Editor 2 tuần trước 7.5/15 → cảnh báo đạt 50%, giảm 50% (không ảnh hưởng lịch).
    """
    project = make_project(videos=[Video(k, publish_date=date(2026, 7, 25)) for k in range(1, 5)],
                           stock=4)
    result = compute_schedule(PlanInput(
        [EDITOR_1, EDITOR_2], [project],
        [Assignment("e1", "p1"), Assignment("e2", "p1")],
    ))
    vids = result.projects[0].videos
    assert [(v.stages[0].person_name, v.handoff_t) for v in vids] == [
        ("Editor 1", 1.0), ("Editor 2", 2.0), ("Editor 1", 2.0), ("Editor 1", 3.0),
    ]
    (w,) = result.warnings
    assert isinstance(w, UnderStandardWarning)
    assert w.pct == 50
    assert "đạt 50%" in w.message() and "giảm 50%" in w.message()


def test_tie_break_ky_luc_du_an():
    """Hai người cùng rảnh → unit về tay người giữ Best Performance của dự án.

    Kỷ lục đứng tên "Editor 2": v1 hoà t=0 → E2 [0,2]; v2 → E1 [0,1];
    v3 → E1 rảnh sớm hơn [1,2]; v4 hoà t=2 → E2 [2,4].
    """
    project = make_project(
        videos=[Video(k, publish_date=date(2026, 7, 25)) for k in range(1, 5)], stock=4,
        best=BestPerformance(0.9, "Editor 2", date(2026, 6, 20)),
    )
    result = compute_schedule(PlanInput(
        [EDITOR_1, EDITOR_2], [project],
        [Assignment("e1", "p1"), Assignment("e2", "p1")],
    ))
    vids = result.projects[0].videos
    assert [(v.stages[0].person_name, v.handoff_t) for v in vids] == [
        ("Editor 2", 2.0), ("Editor 1", 1.0), ("Editor 1", 2.0), ("Editor 2", 4.0),
    ]


def test_uu_tien_du_an_dang_lam():
    """Editor có "dự án đang làm" ưu tiên việc dự án nhà, kể cả khi dự án khác
    có ngày đăng sớm hơn (không nhảy dự án khi dự án nhà còn việc sẵn).

    Editor 1 đang làm B. A đăng 14/07 (sớm hơn), B đăng 18/07 — không có home
    thì EDD chọn A trước; có home → B [0,1] giao 13/07, rồi A [1,1.5] giao 14/07.
    """
    e_home = Person("e1", "Editor 1", "editor", standard_rate=30, last_week_rate=30,
                    home_project_id="pb")
    pa = make_project(pid="pa", name="Dự án A", minutes=15, stock=1,
                      videos=[Video(1, publish_date=date(2026, 7, 14))])
    pb = make_project(pid="pb", name="Dự án B", minutes=30, stock=1,
                      videos=[Video(1, publish_date=date(2026, 7, 18))])
    result = compute_schedule(PlanInput(
        [e_home], [pa, pb], [Assignment("e1", "pa"), Assignment("e1", "pb")],
    ))
    (va,) = result.projects[0].videos
    (vb,) = result.projects[1].videos
    assert (vb.stages[0].segments[0].start_t, vb.handoff_date) == (0.0, date(2026, 7, 13))
    assert (va.stages[0].segments[0].start_t, va.handoff_date) == (1.0, date(2026, 7, 14))


def test_dang_lam_thang_ca_ky_luc_khi_chon_nguoi():
    """Chọn người cho unit: "đang làm" đứng trên kỷ lục — Editor 2 đang làm dự án
    thắng Editor 1 dù Editor 1 giữ Best Performance, khi cả hai cùng rảnh."""
    e1 = Person("e1", "Editor 1", "editor", standard_rate=30, last_week_rate=30)
    e2 = Person("e2", "Editor 2", "editor", standard_rate=30, last_week_rate=30,
                home_project_id="p1")
    project = make_project(videos=[Video(1)], stock=1,
                           best=BestPerformance(0.5, "Editor 1", date(2026, 6, 20)))
    result = compute_schedule(PlanInput(
        [e1, e2], [project], [Assignment("e1", "p1"), Assignment("e2", "p1")],
    ))
    (video,) = result.projects[0].videos
    assert video.stages[0].person_name == "Editor 2"


def test_dang_lam_theo_du_an_lon_khop_moi_kenh():
    """"Đang làm" trỏ dự án lớn (group) — ưu tiên MỌI kênh trong dự án đó.

    Editor 1 đang làm dự án "G"; kênh A thuộc G (đăng 18/07) thắng kênh X
    ngoài G (đăng 14/07) dù deadline xa hơn.
    """
    ka = Project(
        id="g::a", name="G · Kênh A", start_date=MONDAY, video_minutes=30,
        stages=(StageConfig("content"), StageConfig("editor")),
        videos=(Video(1, publish_date=date(2026, 7, 18)),),
        script_stock=1, group_id="g",
    )
    kx = make_project(pid="x", name="Kênh X", stock=1,
                      videos=[Video(1, publish_date=date(2026, 7, 14))])
    e_home = Person("e1", "Editor 1", "editor", standard_rate=30, last_week_rate=30,
                    home_project_id="g")
    result = compute_schedule(PlanInput(
        [e_home], [ka, kx], [Assignment("e1", "g::a"), Assignment("e1", "x")],
    ))
    assert result.projects[0].videos[0].stages[0].segments[0].start_t == 0.0  # kênh A trước
    assert result.projects[1].videos[0].stages[0].segments[0].start_t == 1.0


def test_diem_nghen_1_nguoi_2_du_an():
    """Điểm nghẽn (08/08/2026): Content A là người content DUY NHẤT của cả 2 dự
    án lớn G1, G2 — cảnh báo cơ cấu, không cần đợi lịch trễ mới báo (ở đây
    videos rỗng nên chắc chắn không có LateWarning nào chen vào)."""
    ga = Project(
        id="g1::a", name="Dự án G1 · Kênh A", start_date=MONDAY, video_minutes=30,
        stages=(StageConfig("content"), StageConfig("editor")), videos=(), group_id="g1",
    )
    gb = Project(
        id="g2::a", name="Dự án G2 · Kênh A", start_date=MONDAY, video_minutes=30,
        stages=(StageConfig("content"), StageConfig("editor")), videos=(), group_id="g2",
    )
    result = compute_schedule(PlanInput(
        [CONTENT_A, EDITOR_1], [ga, gb],
        [Assignment("c1", "g1::a"), Assignment("c1", "g2::a"), Assignment("e1", "g1::a")],
    ))
    bottlenecks = [w for w in result.warnings if isinstance(w, BottleneckWarning)]
    assert len(bottlenecks) == 1
    w = bottlenecks[0]
    assert (w.role, w.person_name, w.group_names) == ("content", "Content A", ("Dự án G1", "Dự án G2"))
    assert "DUY NHẤT" in w.message() and "2 dự án" in w.message() and "Dự án G1, Dự án G2" in w.message()
    # editor chỉ solo ở G1 (1 group, chưa tới ngưỡng 2) → không cảnh báo cho editor
    assert not any(b.role == "editor" for b in bottlenecks)


def test_diem_nghen_co_backup_thi_khong_bao():
    """2 người cùng khâu editor trong 1 dự án → không phải điểm nghẽn."""
    ga = Project(
        id="g1::a", name="Dự án G1 · Kênh A", start_date=MONDAY, video_minutes=30,
        stages=(StageConfig("editor"),), videos=(), group_id="g1",
    )
    editor2 = Person("e2", "Editor 2", "editor", standard_rate=30)
    result = compute_schedule(PlanInput(
        [EDITOR_1, editor2], [ga], [Assignment("e1", "g1::a"), Assignment("e2", "g1::a")],
    ))
    assert not any(isinstance(w, BottleneckWarning) for w in result.warnings)


def test_diem_nghen_bo_qua_kenh_khong_co_group_id():
    """Kênh rời không khai group_id (gọi engine trực tiếp) không tính vào điểm
    nghẽn — schema "nhiều dự án" chỉ có ý nghĩa khi có group_id thật."""
    pa = make_project(pid="pa", name="Dự án A")
    pb = make_project(pid="pb", name="Dự án B")
    result = compute_schedule(PlanInput(
        [EDITOR_1], [pa, pb], [Assignment("e1", "pa"), Assignment("e1", "pb")],
    ))
    assert not any(isinstance(w, BottleneckWarning) for w in result.warnings)


def test_video_uu_tien_san_xuat_truoc():
    """Video ★ ưu tiên được sản xuất sớm nhất có thể — thắng EDD nhưng thua
    "dự án đang làm". B#1 (★, đăng 18/07) làm trước A#1 (đăng 14/07)."""
    pa = make_project(pid="pa", name="Dự án A", stock=1,
                      videos=[Video(1, publish_date=date(2026, 7, 14))])
    pb = make_project(pid="pb", name="Dự án B", stock=1,
                      videos=[Video(1, publish_date=date(2026, 7, 18), priority=True)])
    result = compute_schedule(PlanInput(
        [EDITOR_1], [pa, pb], [Assignment("e1", "pa"), Assignment("e1", "pb")],
    ))
    assert result.projects[1].videos[0].stages[0].segments[0].start_t == 0.0
    assert result.projects[0].videos[0].stages[0].segments[0].start_t == 1.0


def test_sua_xong_trong_ngay_bang_qua_gio():
    """Sửa phải xong NGAY TRONG NGÀY nó diễn ra — vắt ngày thì nén bằng QUÁ GIỜ.

    Editor 15 phút/ngày, tập 25 phút → dựng 25/15 = 1.667 ngày [0, 1.667].
    Sửa 0.5 bắt đầu 1.667: chỉ còn 0.333 ngày → NÉN [1.667, 2.0], quá giờ 0.167
    → bàn giao 2.0 = ngay thứ Ba 14/07 (không dời sang hôm sau, không bỏ trống).
    """
    editor = Person("eh", "Editor Hải", "editor", standard_rate=15)
    project = make_project(minutes=25, stock=1,
                           videos=[Video(1)],
                           editor_cfg=StageConfig("editor", 1, 0, 0.5))
    result = compute_schedule(PlanInput([editor], [project], [Assignment("eh", "p1")]))
    (video,) = result.projects[0].videos
    rev = video.stages[0].segments[-1]
    assert (rev.kind, rev.start_t, rev.end_t) == ("revision", pytest.approx(5 / 3), 2.0)
    assert rev.overtime == pytest.approx(1 / 6)
    assert (video.handoff_t, video.handoff_date) == (2.0, date(2026, 7, 14))


def test_lich_khit_khong_bo_trong_nho_qua_gio():
    """Hai rule phối hợp: sửa xong trong ngày bằng QUÁ GIỜ + không bỏ trống giờ.

    Editor 15 phút/ngày, kênh A tập 25' và kênh B tập 15' (đều ✓KB, sửa 0.5, chờ 0):
    A dựng [0, 5/3]; sửa A nén cuối ngày 2 [5/3, 2.0] (OT 1/6) → A xong NGAY 14/07;
    B dựng trọn [2.0, 3.0]; sửa B [3.0, 3.5] tròn trong ngày 4.
    Lịch liền mạch không phút trống; bàn giao A = 2.0 (14/07), B = 3.5 (16/07).
    """
    editor = Person("eh", "Editor Hải", "editor", standard_rate=15)
    pa = make_project(pid="pa", name="Kênh A", minutes=25,
                      videos=[Video(1, has_script=True, publish_date=date(2026, 7, 15))],
                      editor_cfg=StageConfig("editor", 1, 0, 0.5))
    pb = make_project(pid="pb", name="Kênh B", minutes=15,
                      videos=[Video(1, has_script=True, publish_date=date(2026, 7, 15))],
                      editor_cfg=StageConfig("editor", 1, 0, 0.5))
    result = compute_schedule(PlanInput(
        [editor], [pa, pb], [Assignment("eh", "pa"), Assignment("eh", "pb")],
    ))
    (va,) = result.projects[0].videos
    (vb,) = result.projects[1].videos
    segs_a = [(s.kind, s.start_t, s.end_t) for s in va.stages[0].segments]
    segs_b = [(s.kind, s.start_t, s.end_t) for s in vb.stages[0].segments]
    assert segs_a == [("work", 0.0, pytest.approx(5 / 3)),
                      ("revision", pytest.approx(5 / 3), 2.0)]
    assert va.stages[0].segments[1].overtime == pytest.approx(1 / 6)
    assert segs_b == [("work", 2.0, 3.0), ("revision", 3.0, 3.5)]
    assert (va.handoff_t, va.handoff_date) == (2.0, date(2026, 7, 14))
    assert (vb.handoff_t, vb.handoff_date) == (3.5, date(2026, 7, 16))


def test_tick_da_co_kich_ban():
    """Tập tick ✓ đã có kịch bản (viết từ tuần trước) → bỏ khâu content, editor
    làm được ngay; tập chưa tick vẫn chờ content như thường."""
    project = make_project(videos=[Video(1), Video(2, has_script=True)])
    result = compute_schedule(PlanInput(
        [CONTENT_A, EDITOR_1], [project],
        [Assignment("c1", "p1"), Assignment("e1", "p1")],
    ))
    v1, v2 = result.projects[0].videos
    assert [st.role for st in v2.stages] == ["editor"]
    assert (v2.handoff_t, v1.handoff_t) == (1.0, 2.0)  # v2 đi ngay, v1 đợi KB [0,1]


def test_kho_kich_ban_san():
    """Kho 2 kịch bản: video 1–2 bỏ khâu content, editor có việc ngay ngày 1.

    Editor 1: v1 [0,1], v2 [1,2]. Content A (1 KB/ngày) viết kịch bản v3 [0,1]
    song song; editor nhận v3 lúc rảnh (t=2): [2,3]. Kịch bản không phụ thuộc
    thời lượng video — 30 phút hay 15 phút vẫn là 1 unit KB.
    """
    project = make_project(videos=[Video(k) for k in range(1, 4)], stock=2)
    result = compute_schedule(PlanInput(
        [CONTENT_A, EDITOR_1], [project],
        [Assignment("c1", "p1"), Assignment("e1", "p1")],
    ))
    v1, v2, v3 = result.projects[0].videos
    assert [st.role for st in v1.stages] == ["editor"]
    assert [st.role for st in v3.stages] == ["content", "editor"]
    assert (v1.handoff_t, v2.handoff_t, v3.handoff_t) == (1.0, 2.0, 3.0)
    assert v3.stages[0].person_name == "Content A"
    assert v3.stages[0].done_t == 1.0
    assert result.warnings == ()  # không có ngày đăng → không so trễ


def test_chua_co_tuan_truoc_dung_chuan_tuyen_dung():
    """Người chưa có tuần tổng kết (None) → lịch dùng chuẩn tuyển dụng, không cảnh báo.
    Người tuần trước = 0 → vẫn lập lịch bằng chuẩn nhưng cảnh báo đạt 0% (giảm 100%).
    Đơn vị trong thông báo theo khâu: editor phút video/ngày, content kịch bản/ngày.
    """
    moi = Person("en", "Editor Mới", "editor", standard_rate=30, last_week_rate=None)
    treo = Person("ez", "Editor Treo", "editor", standard_rate=30, last_week_rate=0)
    cham = Person("cz", "Content Chậm", "content", standard_rate=2, last_week_rate=1)
    project = make_project(videos=[Video(1)], stock=1)
    result = compute_schedule(PlanInput([moi, treo, cham], [project], [Assignment("en", "p1")]))
    (video,) = result.projects[0].videos
    assert video.handoff_t == 1.0  # 30' ÷ 30 chuẩn = 1 ngày
    w_treo, w_cham = result.warnings
    assert isinstance(w_treo, UnderStandardWarning)
    assert (w_treo.person_name, w_treo.pct) == ("Editor Treo", 0)
    assert "giảm 100%" in w_treo.message() and "phút video/ngày" in w_treo.message()
    assert (w_cham.person_name, w_cham.pct) == ("Content Chậm", 50)
    assert "kịch bản/ngày" in w_cham.message()


def test_kho_du_thi_khong_can_content():
    """Kho phủ hết video → khâu content không cần người; kho 0 mà thiếu content
    → cảnh báo và dự án đó lịch rỗng, dự án khác vẫn tính."""
    pa = make_project(pid="pa", name="Dự án A", videos=[Video(1)], stock=1)
    pb = make_project(pid="pb", name="Dự án B", videos=[Video(1)], stock=0)
    result = compute_schedule(PlanInput(
        [EDITOR_1], [pa, pb], [Assignment("e1", "pa"), Assignment("e1", "pb")],
    ))
    assert result.projects[0].videos[0].handoff_date == date(2026, 7, 13)
    assert result.projects[1].videos == ()
    (w,) = [w for w in result.warnings if isinstance(w, UnstaffedWarning)]
    assert (w.project_id, w.role) == ("pb", "content")


def test_du_an_moi_chen_ngang():
    """Case (c) — thêm dự án mới thấy ngay tác động lên dự án đang chạy.

    Trước: Editor 1 chỉ có A (2 video 30', kho 2, đăng 15 & 18/07)
    → giao 13/07 và 14/07.
    Sau: thêm B (1 video 30', kho 1, đăng 14/07 — gần nhất) → EDD đẩy B lên đầu:
    B [0,1] giao 13/07; A dời thành [1,2]→14/07 và [2,3]→15/07. Vẫn kịp cả ba.
    """
    pa = make_project(pid="pa", name="Dự án A", stock=2, videos=[
        Video(1, publish_date=date(2026, 7, 15)), Video(2, publish_date=date(2026, 7, 18)),
    ])
    before = compute_schedule(PlanInput([EDITOR_1], [pa], [Assignment("e1", "pa")]))
    assert [v.handoff_date for v in before.projects[0].videos] == [
        date(2026, 7, 13), date(2026, 7, 14),
    ]

    pb = make_project(pid="pb", name="Dự án B", stock=1,
                      videos=[Video(1, publish_date=date(2026, 7, 14))])
    after = compute_schedule(PlanInput(
        [EDITOR_1], [pa, pb], [Assignment("e1", "pa"), Assignment("e1", "pb")],
    ))
    assert [v.handoff_date for v in after.projects[0].videos] == [
        date(2026, 7, 14), date(2026, 7, 15),
    ]
    assert after.projects[1].videos[0].handoff_date == date(2026, 7, 13)
    assert [w for w in after.warnings if isinstance(w, LateWarning)] == []


def test_cho_feedback_khong_chan_unit_khac():
    """Trong lúc video 1 chờ feedback, editor dựng video 2; feedback về thì sửa v1.

    Editor cfg 1 vòng (chờ 1, sửa 0.5), 2 video 30' kho sẵn:
    v1 work [0,1], chờ [1,2]; v2 work [1,2]; sửa v1 [2,2.5]; v2 chờ [2,3], sửa [3,3.5].
    """
    project = make_project(videos=[Video(1), Video(2)], stock=2,
                           editor_cfg=StageConfig("editor", 1, 1.0, 0.5))
    result = compute_schedule(PlanInput([EDITOR_1], [project], [Assignment("e1", "p1")]))
    v1, v2 = result.projects[0].videos
    assert [(s.kind, s.start_t, s.end_t) for s in v1.stages[0].segments] == [
        ("work", 0.0, 1.0), ("wait", 1.0, 2.0), ("revision", 2.0, 2.5),
    ]
    assert [(s.kind, s.start_t, s.end_t) for s in v2.stages[0].segments] == [
        ("work", 1.0, 2.0), ("wait", 2.0, 3.0), ("revision", 3.0, 3.5),
    ]
    assert (v1.handoff_date, v2.handoff_date) == (date(2026, 7, 15), date(2026, 7, 16))


def test_default_videos_sinh_ngay_dang_mac_dinh():
    """Lịch up 5 video/tuần → video k đăng sau k × 6/5 = 1.2 ngày làm việc.

    Tính tay: 1.2→ngày 2 (14/07), 2.4→3, 3.6→4, 4.8→5, 6.0→6 (18/07),
    7.2→ngày 8 = 21/07 (bỏ CN). Tên mặc định ĐỂ TRỐNG — leader tự nhập.
    """
    videos = default_videos(6, MONDAY, 5)
    assert [v.publish_date for v in videos] == [
        date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16),
        date(2026, 7, 17), date(2026, 7, 18), date(2026, 7, 21),
    ]
    assert all(v.title == "" for v in videos)


def test_video_gap_chia_editor_song_song():
    """Video GẤP: khâu editor chia cho N editor làm song song.

    Video 30 phút, has_script (bỏ content), gấp, chia E1+E2 (mỗi người 15 phút/ngày).
    Σ năng suất = 30 → effort = 30 ÷ 30 = 1 ngày. Cả hai dựng [0,1] song song.
    Bàn giao = 1.0 = cuối ngày làm việc 1 = thứ Hai 13/07; đăng 14/07 → kịp.
    """
    e1 = Person("e1", "Editor 1", "editor", standard_rate=15, last_week_rate=15)
    e2 = Person("e2", "Editor 2", "editor", standard_rate=15, last_week_rate=15)
    project = make_project(minutes=30, videos=[
        Video(1, "Gấp", date(2026, 7, 14), has_script=True,
              urgent=True, assigned_editors=("e1", "e2")),
    ])
    result = compute_schedule(PlanInput(
        [e1, e2], [project], [Assignment("e1", "p1"), Assignment("e2", "p1")],
    ))
    (video,) = result.projects[0].videos
    # hai StageResult editor (mỗi editor một phần), cùng [0,1]
    editors = [st for st in video.stages if st.role == "editor"]
    assert {st.person_name for st in editors} == {"Editor 1", "Editor 2"}
    for st in editors:
        assert (st.segments[0].start_t, st.segments[0].end_t) == (0.0, 1.0)
    assert (video.handoff_t, video.handoff_date) == (1.0, date(2026, 7, 13))
    assert video.late_workdays == 0  # bàn giao 13/07 ≤ đăng 14/07


def test_video_gap_day_lui_viec_thuong():
    """Video gấp ưu tiên cao nhất — đẩy video thường của cùng editor lùi lại.

    E1 15 phút/ngày. v1 gấp (15 phút, [0,1]); v2 thường (15 phút) dù đăng sớm hơn
    vẫn xếp sau → [1,2]. (assigned 1 người = chia cho 1, effort 15/15=1.)
    """
    e1 = Person("e1", "Editor 1", "editor", standard_rate=15, last_week_rate=15)
    project = make_project(minutes=15, videos=[
        Video(1, "Gấp", date(2026, 7, 20), has_script=True, urgent=True, assigned_editors=("e1",)),
        Video(2, "Thường", date(2026, 7, 14), has_script=True),
    ])
    result = compute_schedule(PlanInput([e1], [project], [Assignment("e1", "p1")]))
    vids = {v.index: v for v in result.projects[0].videos}
    assert vids[1].stages[0].segments[0].start_t == 0.0   # gấp trước
    assert vids[2].stages[0].segments[0].start_t == 1.0   # thường lùi sau


def test_video_gap_content_truoc_khi_chia():
    """Video gấp chưa có KB: content 1 người viết trước (KHÔNG chia), rồi editor chia.

    Content A 1 KB/ngày → [0,1]. Editor E1+E2 (15+15) split 30 phút → effort 1,
    bắt đầu sau content = [1,2]. Bàn giao 2.0.
    """
    c1 = Person("c1", "Content A", "content", standard_rate=1, last_week_rate=1)
    e1 = Person("e1", "Editor 1", "editor", standard_rate=15, last_week_rate=15)
    e2 = Person("e2", "Editor 2", "editor", standard_rate=15, last_week_rate=15)
    project = make_project(minutes=30, videos=[
        Video(1, "Gấp", None, urgent=True, assigned_editors=("e1", "e2")),
    ])
    result = compute_schedule(PlanInput(
        [c1, e1, e2], [project],
        [Assignment("c1", "p1"), Assignment("e1", "p1"), Assignment("e2", "p1")],
    ))
    (video,) = result.projects[0].videos
    content = next(st for st in video.stages if st.role == "content")
    assert (content.person_name, content.segments[0].end_t) == ("Content A", 1.0)
    editors = [st for st in video.stages if st.role == "editor"]
    assert all(st.segments[0].start_t == 1.0 and st.segments[0].end_t == 2.0 for st in editors)
    assert video.handoff_t == 2.0


def test_input_khong_hop_le():
    with pytest.raises(ValueError, match="Trùng phân công"):
        compute_schedule(PlanInput(
            [EDITOR_1], [make_project(videos=[Video(1)], stock=1)],
            [Assignment("e1", "p1"), Assignment("e1", "p1")],
        ))
    with pytest.raises(ValueError, match="tuần trước không được âm"):
        Person("x", "X", "editor", standard_rate=30, last_week_rate=-1)
    with pytest.raises(ValueError, match="trùng index"):
        make_project(videos=[Video(1), Video(1)])
