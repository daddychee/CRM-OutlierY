"""Cấu trúc dữ liệu đầu vào của engine — theo SPEC.md (v2, chốt 13/07/2026).

Dữ liệu THẬT của team (tên người, năng suất, dự án) không nằm trong repo — xem
CLAUDE.md nguyên tắc 6. Ở đây chỉ có schema; giá trị mẫu nằm trong tests/ và demo.py.

Đơn vị năng suất THEO KHÂU:
- content: KỊCH BẢN / NGÀY — một unit kịch bản mất 1 ÷ năng suất ngày công,
  không phụ thuộc thời lượng video.
- editor:  PHÚT VIDEO HOÀN THÀNH / NGÀY — một unit video mất
  thời lượng ÷ năng suất ngày công (thời lượng khai ở cấp dự án).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from .workcal import WORKDAYS_PER_WEEK, date_at


@dataclass(frozen=True)
class Person:
    """Một nhân sự sản xuất.

    standard_rate  — chuẩn tuyển dụng (KPI cam kết), Leader + HR đặt khi tuyển.
    last_week_rate — năng suất tuần trước, sinh từ Tổng kết tuần (SPEC mục 3);
                     None = chưa có tuần tổng kết nào. CHỈ dùng để cảnh báo.
    Đơn vị theo khâu: content = KỊCH BẢN/ngày; editor = PHÚT VIDEO/ngày.
    Engine phân phối lịch theo planning_rate() = CHUẨN TUYỂN DỤNG (KPI) — kế hoạch
    không tự hạ theo người yếu; ai dưới chuẩn thì cảnh báo Leader/HR xử lý.
    """

    id: str
    name: str
    role: str  # khâu đảm nhiệm: "content" | "editor"
    standard_rate: float
    last_week_rate: float | None = None
    # Dự án "đang làm" (chủ yếu cho editor): máy ưu tiên giữ người ở dự án này,
    # không nhảy sang dự án khác khi dự án nhà còn việc sẵn sàng. None = tự do.
    home_project_id: str | None = None
    # Ngày nghỉ: các khoảng (từ, đến) trọn ngày — engine coi như "chỗ đặt trước",
    # việc tự tách quanh ngày nghỉ, người đó không nhận unit mới trong khoảng này.
    leaves: tuple[tuple[date, date], ...] = ()
    # Hạng mục CLONE của editor: năng suất VIDEO/ngày làm lại video cho bản dịch.
    # Lịch clone KHÔNG qua engine (không deadline): chia đều tổng tập cần clone ra
    # các ngày làm việc rồi phân người có chỉ số này. None = không nhận việc clone.
    clone_rate: float | None = None

    def _validate_clone(self) -> None:
        if self.clone_rate is not None and self.clone_rate <= 0:
            raise ValueError(f"Nhân sự '{self.name}': clone_rate phải > 0")

    def __post_init__(self) -> None:
        if self.standard_rate <= 0:
            raise ValueError(f"Nhân sự '{self.name}': chuẩn tuyển dụng phải > 0")
        if self.last_week_rate is not None and self.last_week_rate < 0:
            raise ValueError(f"Nhân sự '{self.name}': năng suất tuần trước không được âm")
        self._validate_clone()

    def planning_rate(self) -> float:
        # Lịch phân phối tuân theo KPI đã cam kết (chốt 13/07/2026) — "tuần trước"
        # chỉ để cảnh báo, không kéo kế hoạch chậm lại theo người dưới chuẩn.
        return self.standard_rate


@dataclass(frozen=True)
class StageConfig:
    """Một khâu trong dây chuyền, kèm cấu hình vòng feedback.

    Mỗi vòng = chờ feedback_wait_days (không chiếm người) + sửa revision_days
    (chiếm người, chính người làm unit đó sửa). Đơn vị: ngày làm việc.
    """

    role: str
    feedback_rounds: int = 0
    feedback_wait_days: float = 0.0
    revision_days: float = 0.0

    def __post_init__(self) -> None:
        if self.feedback_rounds < 0:
            raise ValueError(f"Khâu '{self.role}': feedback_rounds phải >= 0")
        if self.feedback_wait_days < 0 or self.revision_days < 0:
            raise ValueError(f"Khâu '{self.role}': thời gian chờ/sửa không được âm")


@dataclass(frozen=True)
class Video:
    """Một video của dự án. Tên nội dung mặc định để trống — leader tự nhập."""

    index: int  # 1-based trong dự án
    title: str = ""
    publish_date: date | None = None  # ngày đăng — nguồn chân lý để so kịp/trễ
    priority: bool = False  # ★ — video được sản xuất sớm nhất có thể
    # ✓ đã có kịch bản (team viết KB tuần trước cho tuần sau) → bỏ qua khâu content
    has_script: bool = False
    # VIDEO GẤP (crash schedule): ưu tiên cao nhất, khâu editor CHIA cho nhiều người
    # làm song song (effort dựng = thời lượng ÷ Σ năng suất N người). Bỏ vòng feedback.
    urgent: bool = False
    assigned_editors: tuple[str, ...] = ()  # id các editor được chia (rỗng = mọi editor kênh)

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValueError(f"Video index phải >= 1, nhận {self.index}")


@dataclass(frozen=True)
class BestPerformance:
    """Kỷ lục của dự án (khâu editor) — số THỰC TẾ, nhập tay từ tool tracking.

    editor_name là chuỗi rời: người nghỉ/bị xoá thì kỷ lục vẫn giữ nguyên.
    """

    days_per_video: float
    editor_name: str
    recorded_on: date

    def __post_init__(self) -> None:
        if self.days_per_video <= 0:
            raise ValueError("Kỷ lục days_per_video phải > 0")


@dataclass(frozen=True)
class Project:
    """MỘT DÂY SẢN XUẤT — trong UI đây là một KÊNH thuộc một dự án lớn.

    (Chốt 13/07/2026: toàn bộ cấu hình sản xuất — bắt đầu, thời lượng, kho kịch
    bản, vòng feedback, kỷ lục — nằm ở cấp KÊNH; "dự án" chỉ là nhóm chứa các kênh
    và đội nhân sự chung. group_id trỏ về id dự án lớn; phân công người và "đang
    làm" tham chiếu dự án lớn — người thuộc dự án làm được mọi kênh trong đó.)

    - videos: danh sách video còn phải làm (snapshot); tính lại giữa chừng =
      snapshot mới với danh sách còn lại + start_date mới.
    - video_minutes: thời lượng một video (phút) — hệ số khối lượng của kênh.
    - script_stock: kho kịch bản sẵn — video index <= script_stock bỏ qua khâu
      ĐẦU TIÊN trong stages (content), editor có việc ngay từ ngày 1.
    """

    id: str
    name: str
    start_date: date
    video_minutes: float
    stages: tuple[StageConfig, ...]
    videos: tuple[Video, ...]
    channel_name: str | None = None
    script_stock: int = 0
    best_performance: BestPerformance | None = None
    group_id: str | None = None  # id dự án lớn chứa kênh này

    def __post_init__(self) -> None:
        if self.video_minutes <= 0:
            raise ValueError(f"Dự án '{self.name}': video_minutes phải > 0")
        if not self.stages:
            raise ValueError(f"Dự án '{self.name}': cần ít nhất một khâu")
        if self.script_stock < 0:
            raise ValueError(f"Dự án '{self.name}': script_stock phải >= 0")
        indices = [v.index for v in self.videos]
        if len(indices) != len(set(indices)):
            raise ValueError(f"Dự án '{self.name}': trùng index video")


def default_videos(n: int, start_date: date, videos_per_week: float) -> tuple[Video, ...]:
    """Sinh n video với ngày đăng mặc định rải đều theo lịch up (video/tuần).

    Video thứ k đăng sau k × (6 / videos_per_week) ngày làm việc kể từ start_date.
    Leader chỉnh từng ngày/tên sau — đây chỉ là giá trị khởi tạo.
    """
    if videos_per_week <= 0:
        raise ValueError("videos_per_week phải > 0")
    return tuple(
        Video(k, "", date_at(start_date, k * WORKDAYS_PER_WEEK / videos_per_week))
        for k in range(1, n + 1)
    )


@dataclass(frozen=True)
class Assignment:
    """Phân công người ↔ dự án (kéo-thả). Không có % — máy chia unit nguyên."""

    person_id: str
    project_id: str


@dataclass(frozen=True)
class PlanInput:
    """Toàn bộ đầu vào của một lần tính — cùng input luôn ra cùng output."""

    people: Sequence[Person]
    projects: Sequence[Project]
    assignments: Sequence[Assignment]
