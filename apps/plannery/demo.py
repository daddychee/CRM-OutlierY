"""Chạy thử engine v2 với dữ liệu GIẢ — không dùng tên/năng suất thật (nguyên tắc 6).

Luồng: Dự án → Kênh → số video + thời lượng → ngày đăng từng video (leader đặt tên)
→ phân công người → engine chia unit nguyên theo EDD → lịch bàn giao + cảnh báo.

Chạy:  python3 demo.py
"""

from datetime import date

from planner import (
    Assignment,
    BestPerformance,
    Person,
    PlanInput,
    Project,
    StageConfig,
    Video,
    compute_schedule,
    default_videos,
)

KIND_LABEL = {"work": "làm chính", "wait": "chờ feedback", "revision": "sửa"}

people = [
    Person("c1", "Content A", "content", standard_rate=1, last_week_rate=1),  # kịch bản/ngày
    Person("e1", "Editor 1", "editor", standard_rate=30, last_week_rate=30),  # phút video/ngày
    Person("e2", "Editor 2", "editor", standard_rate=30, last_week_rate=15),  # mới vào
]

# Dự án X: 4 video 15 phút, đăng theo lịch mặc định 4 video/tuần (leader sửa được),
# kho sẵn 2 kịch bản, kỷ lục cũ của một editor đã nghỉ.
videos_x = list(default_videos(4, date(2026, 7, 13), 4))
videos_x[0] = Video(1, "Top 5 công cụ AI", videos_x[0].publish_date)
videos_x[1] = Video(2, "Review iPhone 17", videos_x[1].publish_date)
project_x = Project(
    id="px", name="Dự án X", channel_name="Kênh A",
    start_date=date(2026, 7, 13), video_minutes=15,
    stages=(StageConfig("content", 1, 1.0, 0.5), StageConfig("editor", 1, 1.0, 0.5)),
    videos=tuple(videos_x), script_stock=2,
    best_performance=BestPerformance(0.6, "Editor C", date(2026, 6, 20)),
)
# Dự án Y: 2 video 30 phút, mỗi thứ Bảy một video.
project_y = Project(
    id="py", name="Dự án Y", channel_name="Kênh B",
    start_date=date(2026, 7, 13), video_minutes=30,
    stages=(StageConfig("content"), StageConfig("editor")),
    videos=(
        Video(1, "Phỏng vấn: khởi nghiệp từ 0đ", date(2026, 7, 18)),
        Video(2, "Tài chính cá nhân cho người mới", date(2026, 7, 25)),
    ),
)

assignments = [
    Assignment("c1", "px"), Assignment("e2", "px"),
    Assignment("c1", "py"), Assignment("e1", "py"),
]

result = compute_schedule(PlanInput(people, [project_x, project_y], assignments))

for ps in result.projects:
    project = next(p for p in [project_x, project_y] if p.id == ps.project_id)
    print(f"=== {ps.project_name} — kênh {project.channel_name} | "
          f"video {project.video_minutes:g} phút, kho kịch bản sẵn: {project.script_stock} ===")
    for v in ps.videos:
        title = f" «{v.title}»" if v.title else ""
        status = ""
        if v.publish_date:
            status = (f" | đăng {v.publish_date:%d/%m} → "
                      + ("kịp ✓" if v.late_workdays == 0 else f"TRỄ {v.late_workdays} ngày LV"))
        print(f"\nVideo #{v.index}{title}: bàn giao {v.handoff_date:%d/%m/%Y}{status}")
        for stage in v.stages:
            print(f"  Khâu {stage.role} — {stage.person_name} (xong {stage.done_date:%d/%m}):")
            for s in stage.segments:
                print(f"    {KIND_LABEL[s.kind]:<13} {s.start_date:%d/%m} → {s.end_date:%d/%m}"
                      f"  (ngày công {s.start_t:g} → {s.end_t:g})")
    print()

if result.warnings:
    print("--- CẢNH BÁO ---")
    for w in result.warnings:
        print("•", w.message())
