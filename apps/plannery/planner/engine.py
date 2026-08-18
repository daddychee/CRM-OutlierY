"""Engine tính điểm rơi bàn giao v2 — tất định, truy ngược được từng con số.

Mô hình (đã chốt 13/07/2026, xem SPEC.md):
- Thời gian tính bằng ngày công (float) trên MỘT trục chung cho mọi dự án, gốc là
  ngày bắt đầu sớm nhất; quy đổi sang ngày lịch (T2–T7, nghỉ CN) ở workcal.py.
- Mỗi kịch bản / video là một UNIT NGUYÊN: một người làm trọn unit rồi mới nhận
  unit kế; chỉ ngắt khi chờ feedback (lúc chờ nhận unit khác, sửa quay về đúng
  người cũ). Không có % công suất.
- Thời gian làm chính một unit tính theo CHUẨN TUYỂN DỤNG (KPI cam kết; "tuần
  trước" chỉ để cảnh báo): khâu content = 1 ÷ năng suất (kịch bản/ngày, không
  phụ thuộc thời lượng); khâu editor = thời lượng video (phút) ÷ năng suất
  (phút/ngày).
- Video index <= script_stock của dự án bỏ qua khâu đầu (kịch bản đã có sẵn).

Quy tắc xếp việc (tất định, giải thích được):
- Việc bắt đầu được sớm nhất chạy trước; cùng thời điểm → ưu tiên unit thuộc dự án
  "ĐANG LÀM" của người thực hiện (không nhảy dự án khi dự án nhà còn việc sẵn),
  rồi VIDEO đánh dấu ƯU TIÊN (★ — sản xuất sớm nhất có thể), rồi unit có NGÀY ĐĂNG
  gần nhất (EDD; không có ngày đăng xếp sau), rồi thứ tự dự án, số video.
- Unit mới cần người → người của khâu đó rảnh sớm nhất; hoà → người ĐANG LÀM dự án
  đó, rồi người giữ KỶ LỤC của dự án (Best Performance), rồi thứ tự khai báo.

Engine chỉ TÍNH và CẢNH BÁO — không tự di chuyển nhân sự (CLAUDE.md nguyên tắc 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from .models import Person, PlanInput, Project
from .workcal import (
    date_at,
    is_workday,
    nth_workday,
    workday_index,
    workday_number_end,
    workday_number_start,
)

_FAR_FUTURE = date.max
# Bàn giao phải xong trước ngày đăng tối thiểu N ngày làm việc (chốt 15/07)
HANDOFF_LEAD_DAYS = 2


@dataclass(frozen=True)
class Segment:
    """Một đoạn trong dòng đời một video — dữ liệu truy ngược "vì sao ra ngày này"."""

    kind: str  # "work" (làm chính) | "wait" (chờ feedback) | "revision" (sửa)
    person_id: str | None  # None với "wait"
    start_t: float  # ngày công trên trục chung (gốc = anchor của kế hoạch)
    end_t: float
    start_date: date
    end_date: date
    overtime: float = 0.0  # phần QUÁ GIỜ (sửa nén vào cuối ngày — RULE sửa xong trong ngày)


@dataclass(frozen=True)
class StageResult:
    role: str
    person_id: str
    person_name: str
    segments: tuple[Segment, ...]
    done_t: float
    done_date: date


@dataclass(frozen=True)
class VideoSchedule:
    index: int
    title: str
    stages: tuple[StageResult, ...]  # chỉ gồm các khâu thật sự chạy (kho bỏ khâu đầu)
    handoff_t: float
    handoff_date: date
    publish_date: date | None
    late_workdays: int  # 0 = kịp; chỉ có nghĩa khi publish_date đặt


@dataclass(frozen=True)
class ProjectSchedule:
    project_id: str
    project_name: str
    videos: tuple[VideoSchedule, ...]


@dataclass(frozen=True)
class LateWarning:
    project_id: str
    project_name: str
    video_index: int
    video_title: str
    handoff_date: date
    publish_date: date
    late_workdays: int

    def message(self) -> str:
        title = f" «{self.video_title}»" if self.video_title else ""
        return (
            f"Trễ: video #{self.video_index}{title} ({self.project_name}) dự kiến bàn giao "
            f"{self.handoff_date:%d/%m/%Y}, lịch đăng {self.publish_date:%d/%m/%Y} "
            f"— trễ {self.late_workdays} ngày làm việc."
        )


@dataclass(frozen=True)
class UnstaffedWarning:
    project_id: str
    project_name: str
    role: str

    def message(self) -> str:
        return (
            f"Chưa có người: dự án '{self.project_name}' khâu '{self.role}' chưa được "
            f"phân công — chưa tính được lịch dự án này."
        )


@dataclass(frozen=True)
class UnderStandardWarning:
    """Năng suất tuần trước thấp hơn chuẩn tuyển dụng — cảnh báo sớm cho Leader/HR."""

    person_id: str
    person_name: str
    last_week_rate: float
    standard_rate: float
    unit: str  # "kịch bản/ngày" (content) | "phút video/ngày" (editor)

    @property
    def pct(self) -> int:
        return round(self.last_week_rate / self.standard_rate * 100)

    def message(self) -> str:
        return (
            f"Cảnh báo nhân sự: {self.person_name} tuần trước đạt {self.pct}% chuẩn "
            f"tuyển dụng ({self.last_week_rate:g}/{self.standard_rate:g} {self.unit}) "
            f"— giảm {100 - self.pct}%."
        )


@dataclass(frozen=True)
class BottleneckWarning:
    """Một người là NGƯỜI DUY NHẤT giữ một khâu cho TỪ 2 dự án trở lên — dự án
    nào cũng đứng khâu đó nếu người này bận/nghỉ, không ai thay thế. Cảnh báo cơ
    cấu, không cần đợi lịch bị trễ mới báo (chốt yêu cầu 08/08/2026).
    """

    role: str
    person_id: str
    person_name: str
    group_names: tuple[str, ...]  # tên các dự án người này một mình gánh khâu này
    leave_ranges: tuple[tuple[date, date], ...]  # đợt nghỉ đã khai của người này

    def message(self) -> str:
        projs = ", ".join(self.group_names)
        base = (
            f"Điểm nghẽn: {self.person_name} là người DUY NHẤT đảm nhiệm khâu "
            f"'{self.role}' cho {len(self.group_names)} dự án ({projs}) — dự án nào "
            f"cũng đứng khâu này nếu người này bận hoặc nghỉ, không ai thay thế."
        )
        if self.leave_ranges:
            ranges = "; ".join(
                f"{d0:%d/%m}" if d0 == d1 else f"{d0:%d/%m}–{d1:%d/%m}"
                for d0, d1 in self.leave_ranges
            )
            base += f" Đã khai nghỉ: {ranges}."
        return base


PlanWarning = LateWarning | UnstaffedWarning | UnderStandardWarning | BottleneckWarning


def _bottleneck_warnings(
    plan: PlanInput, people_by_id: dict[str, Person]
) -> list[BottleneckWarning]:
    """Vai trò nào chỉ có 1 người trong MỘT dự án (group_id) mà người đó lại là
    người-duy-nhất ở TỪ 2 dự án trở lên → điểm nghẽn thật.

    CHỈ xét dự án CÓ group_id khai báo — kênh rời không group_id (gọi engine
    trực tiếp, không qua schema "dự án lớn chứa kênh") không có khái niệm
    "nhiều dự án" nên bỏ qua.
    """
    projects_by_id = {pr.id: pr for pr in plan.projects}
    group_names: dict[str, str] = {}
    group_order: dict[str, int] = {}
    for i, pr in enumerate(plan.projects):
        if pr.group_id is None:
            continue
        group_order.setdefault(pr.group_id, i)
        group_names.setdefault(pr.group_id, pr.name.split(" · ", 1)[0])

    role_people: dict[tuple[str, str], set[str]] = {}
    for a in plan.assignments:
        pr = projects_by_id.get(a.project_id)
        p = people_by_id.get(a.person_id)
        if pr is None or p is None or pr.group_id is None:
            continue
        role_people.setdefault((p.role, pr.group_id), set()).add(p.id)

    solo_groups: dict[tuple[str, str], list[str]] = {}
    for (role, gid), people in role_people.items():
        if len(people) == 1:
            pid = next(iter(people))
            solo_groups.setdefault((role, pid), []).append(gid)

    warnings: list[BottleneckWarning] = []
    for (role, pid), gids in solo_groups.items():
        if len(gids) < 2:
            continue
        person = people_by_id[pid]
        ordered = sorted(gids, key=lambda g: group_order[g])
        names = tuple(group_names[g] for g in ordered)
        warnings.append(BottleneckWarning(role, pid, person.name, names, person.leaves))
    return warnings


@dataclass(frozen=True)
class PlanResult:
    anchor: date | None  # gốc trục thời gian = ngày bắt đầu sớm nhất
    projects: tuple[ProjectSchedule, ...]
    warnings: tuple[PlanWarning, ...]


def compute_schedule(plan: PlanInput) -> PlanResult:
    """Tính lịch cho toàn bộ kế hoạch. Thuần tính toán, không sửa input."""
    people_by_id = _validate(plan)
    warnings: list[PlanWarning] = [
        UnderStandardWarning(
            p.id, p.name, p.last_week_rate, p.standard_rate,
            "kịch bản/ngày" if p.role == "content" else "phút video/ngày",
        )
        for p in plan.people
        if p.last_week_rate is not None and p.last_week_rate < p.standard_rate
    ]
    warnings.extend(_bottleneck_warnings(plan, people_by_id))
    if not plan.projects:
        return PlanResult(None, (), tuple(warnings))

    anchor = min(p.start_date for p in plan.projects)
    staffed: list[Project] = []
    for project in plan.projects:
        missing = _missing_roles(project, plan)
        if missing:
            warnings.extend(UnstaffedWarning(project.id, project.name, r) for r in missing)
        else:
            staffed.append(project)

    schedules = _simulate(staffed, plan, people_by_id, anchor)
    project_schedules = []
    for project in plan.projects:
        ps = schedules.get(project.id, ProjectSchedule(project.id, project.name, ()))
        project_schedules.append(ps)
        for v in ps.videos:
            if v.late_workdays > 0:
                warnings.append(
                    LateWarning(
                        project.id, project.name, v.index, v.title,
                        v.handoff_date, v.publish_date, v.late_workdays,
                    )
                )
    return PlanResult(anchor, tuple(project_schedules), tuple(warnings))


def _validate(plan: PlanInput) -> dict[str, Person]:
    people_by_id: dict[str, Person] = {}
    for p in plan.people:
        if p.id in people_by_id:
            raise ValueError(f"Trùng id nhân sự: {p.id}")
        people_by_id[p.id] = p
    project_ids = set()
    for pr in plan.projects:
        if pr.id in project_ids:
            raise ValueError(f"Trùng id dự án: {pr.id}")
        project_ids.add(pr.id)
    seen = set()
    for a in plan.assignments:
        if a.person_id not in people_by_id:
            raise ValueError(f"Phân công tham chiếu nhân sự không tồn tại: {a.person_id}")
        if a.project_id not in project_ids:
            raise ValueError(f"Phân công tham chiếu dự án không tồn tại: {a.project_id}")
        key = (a.person_id, a.project_id)
        if key in seen:
            raise ValueError(f"Trùng phân công: {a.person_id} vào {a.project_id}")
        seen.add(key)
    return people_by_id


def _missing_roles(project: Project, plan: PlanInput) -> list[str]:
    """Các khâu dự án CẦN (có video chạy qua) mà chưa ai được phân công."""
    assigned = {a.person_id for a in plan.assignments if a.project_id == project.id}
    covered = {p.role for p in plan.people if p.id in assigned}
    needed: list[str] = []
    for si, st in enumerate(project.stages):
        runs = any(
            si > 0 or (v.index > project.script_stock and not v.has_script)
            for v in project.videos
        )
        if runs and st.role not in covered and st.role not in needed:
            needed.append(st.role)
    return needed


class _VideoState:
    def __init__(self, proj_idx: int, project: Project, video, offset: float) -> None:
        self.proj_idx = proj_idx
        self.project = project
        self.video = video
        # chuỗi bước: bỏ khâu đầu nếu kịch bản đã có trong kho
        self.chain: list[tuple[str, int]] = []
        for si, st in enumerate(project.stages):
            # bỏ khâu đầu (content) nếu kịch bản đã có: nằm trong kho HOẶC tick ✓ đã có KB
            if si == 0 and (video.index <= project.script_stock or video.has_script):
                continue
            self.chain.append(("work", si))
            # video gấp: bỏ vòng feedback (rushed) — chỉ content + editor chia người
            if not video.urgent:
                for _ in range(st.feedback_rounds):
                    self.chain.append(("wait", si))
                    self.chain.append(("revision", si))
        self.split_stage: int | None = None  # khâu editor bị chia (video gấp)
        self.pos = 0
        self.ready = offset
        self.stage_person: dict[int, str] = {}
        self.stage_done: dict[int, float] = {}
        self.raw_segments: dict[int, list[tuple[str, str | None, float, float]]] = {}

    def edd_key(self):
        return self.video.publish_date or _FAR_FUTURE


def _simulate(
    projects: list[Project], plan: PlanInput, people_by_id: dict[str, Person], anchor: date
) -> dict[str, ProjectSchedule]:
    people_order = {p.id: i for i, p in enumerate(plan.people)}
    by_project_role: dict[tuple[str, str], list[Person]] = {}
    for a in plan.assignments:
        p = people_by_id[a.person_id]
        by_project_role.setdefault((a.project_id, p.role), []).append(p)
    for members in by_project_role.values():
        members.sort(key=lambda p: people_order[p.id])

    free: dict[str, float] = {a.person_id: 0.0 for a in plan.assignments}
    # "chỗ đặt trước" của vòng sửa bị dời sang đầu ngày sau — khoảng trống trước đó
    # vẫn dùng được cho unit khác (RULE 13/07: tối ưu thời gian làm việc trong ngày)
    reserved: dict[str, list[tuple[float, float]]] = {a.person_id: [] for a in plan.assignments}

    # NGÀY NGHỈ = chỗ đặt trước: engine tự tách việc quanh nó, không nhận unit mới.
    for p in plan.people:
        if p.id not in reserved:
            continue
        for d0, d1 in p.leaves:
            d = d0
            while d <= d1:
                if is_workday(d):
                    i = workday_index(anchor, d)
                    if i >= 1:
                        reserved[p.id].append((float(i - 1), float(i)))
                d += timedelta(days=1)
        reserved[p.id].sort()

    def _clear_of_res(t: float, res: list[tuple[float, float]]) -> float:
        moved = True
        while moved:
            moved = False
            for rs, re_ in res:
                if rs - 1e-9 <= t < re_ - 1e-9:
                    t = re_
                    moved = True
        return t

    def _place_rev(free_t: float, ready: float, e: float,
                   res: list[tuple[float, float]]) -> tuple[float, float, float]:
        """Vòng sửa làm NGAY trong ngày nó sẵn sàng — vắt ngày thì NÉN lại, phần dư
        là QUÁ GIỜ (nhân sự chấp nhận OT để xong việc trong ngày, chốt 13/07).
        Trả về (start, end, overtime)."""
        s = _clear_of_res(max(free_t, ready), res)
        day_end = math.floor(s + 1e-9) + 1.0
        nxt = min((rs for rs, _ in res if rs > s + 1e-9), default=None)
        limit = day_end if nxt is None else min(day_end, nxt)
        end = s + e
        ot = 0.0
        if end > limit + 1e-9:
            ot = end - limit
            end = limit
        return s, end, ot

    def _place_work(free_t: float, ready: float, dur: float,
                    res: list[tuple[float, float]]) -> tuple[list[tuple[float, float]], float]:
        """Làm chính có thể TÁCH quanh chỗ đặt trước để không lãng phí giờ trống."""
        t = max(free_t, ready)
        parts: list[tuple[float, float]] = []
        remaining = dur
        for rs, re_ in sorted(res):
            if re_ <= t + 1e-9 or remaining <= 1e-9:
                continue
            if rs > t + 1e-9:
                chunk = min(remaining, rs - t)
                parts.append((t, t + chunk))
                remaining -= chunk
                t += chunk
            if remaining > 1e-9 and t >= rs - 1e-9:
                t = max(t, re_)
        if remaining > 1e-9:
            parts.append((t, t + remaining))
            t += remaining
        return parts, t
    states: list[_VideoState] = []
    for pi, project in enumerate(projects):
        offset = float(workday_index(anchor, project.start_date) - 1)
        for video in sorted(project.videos, key=lambda v: v.index):
            states.append(_VideoState(pi, project, video, offset))

    def consume_non_person_steps(vs: _VideoState) -> None:
        """Tiêu thụ các bước không cần người: chờ feedback và vòng sửa 0 ngày công."""
        while vs.pos < len(vs.chain):
            kind, si = vs.chain[vs.pos]
            st = vs.project.stages[si]
            if kind == "wait":
                if st.feedback_wait_days > 0:
                    vs.raw_segments.setdefault(si, []).append(
                        ("wait", None, vs.ready, vs.ready + st.feedback_wait_days, 0.0)
                    )
                vs.ready += st.feedback_wait_days
            elif kind == "revision" and st.revision_days == 0:
                pass
            else:
                break
            vs.pos += 1

    def is_record_holder(person: Person, project: Project) -> bool:
        bp = project.best_performance
        return bp is not None and person.name == bp.editor_name

    def is_home(person: Person, project: Project) -> bool:
        # "đang làm" trỏ tới dự án lớn — khớp mọi kênh (engine-project) trong đó
        return person.home_project_id is not None and \
            person.home_project_id in (project.id, project.group_id)

    # ---- VIDEO GẤP: xếp TRƯỚC, ưu tiên cao nhất, khâu editor chia N người ----
    def schedule_urgent(vs: _VideoState) -> None:
        assigned = {a.person_id for a in plan.assignments if a.project_id == vs.project.id}
        while vs.pos < len(vs.chain):
            _, si = vs.chain[vs.pos]  # video gấp chỉ có bước "work"
            stage = vs.project.stages[si]
            if stage.role == "editor":
                eds = [people_by_id[e] for e in vs.video.assigned_editors
                       if e in assigned and people_by_id[e].role == "editor"]
                if not eds:  # không chỉ định → mọi editor của kênh
                    eds = list(by_project_role.get((vs.project.id, "editor"), []))
                if not eds:
                    break
                rate_sum = sum(p.planning_rate() for p in eds)
                effort = vs.project.video_minutes / rate_sum  # chia song song
                start = max(_clear_of_res(max(free[p.id], vs.ready), reserved[p.id]) for p in eds)
                end = start + effort
                for p in eds:
                    vs.raw_segments.setdefault(si, []).append(("work", p.id, start, end, 0.0))
                    free[p.id] = end
                vs.stage_person[si] = eds[0].id
                vs.split_stage = si
            else:  # content — một người viết, KHÔNG chia
                eligible = by_project_role.get((vs.project.id, stage.role), [])
                if not eligible:
                    break
                person = min(eligible, key=lambda p: _clear_of_res(max(free[p.id], vs.ready), reserved[p.id]))
                start = _clear_of_res(max(free[person.id], vs.ready), reserved[person.id])
                end = start + 1.0 / person.planning_rate()
                vs.raw_segments.setdefault(si, []).append(("work", person.id, start, end, 0.0))
                free[person.id] = end
                vs.stage_person[si] = person.id
            vs.ready = end
            vs.stage_done[si] = end
            vs.pos += 1

    for vs in sorted((v for v in states if v.video.urgent),
                     key=lambda v: (v.edd_key(), v.proj_idx, v.video.index)):
        schedule_urgent(vs)

    while True:
        pending = [vs for vs in states if vs.pos < len(vs.chain)]
        if not pending:
            break
        best = None  # (start, edd, proj_idx, video_idx, vs, person)
        for vs in pending:
            kind, si = vs.chain[vs.pos]
            if si in vs.stage_person:
                eligible = [people_by_id[vs.stage_person[si]]]
            else:
                eligible = by_project_role[(vs.project.id, vs.project.stages[si].role)]
            is_rev = kind == "revision"
            rev_e = vs.project.stages[si].revision_days

            def prospective(p: Person) -> float:
                return _clear_of_res(max(free[p.id], vs.ready), reserved[p.id])

            person = min(
                eligible,
                key=lambda p: (
                    prospective(p),
                    0 if is_home(p, vs.project) else 1,
                    0 if is_record_holder(p, vs.project) else 1,
                    people_order[p.id],
                ),
            )
            start = prospective(person)
            home_mismatch = 0 if is_home(person, vs.project) else 1
            prio_mismatch = 0 if vs.video.priority else 1
            # vòng sửa chốt lịch trước (nó chỉ "đặt chỗ", không chặn giờ trống)
            key = (0 if is_rev else 1, start, home_mismatch, prio_mismatch,
                   vs.edd_key(), vs.proj_idx, vs.video.index)
            if best is None or key < best[:7]:
                best = (*key, vs, person)
        _, start, _, _, _, _, _, vs, person = best
        kind, si = vs.chain[vs.pos]
        stage = vs.project.stages[si]
        vs.stage_person.setdefault(si, person.id)
        res = reserved[person.id]
        if kind == "revision" and 0 < stage.revision_days <= 1:
            # Sửa làm NGAY trong ngày nó sẵn sàng, vắt ngày → nén bằng QUÁ GIỜ.
            # Nếu sửa sẵn sàng muộn hơn giờ rảnh (đang chờ feedback) thì chỉ
            # "đặt chỗ" — giờ trống trước đó nhường cho unit khác chen vào.
            s, end, ot = _place_rev(free[person.id], vs.ready, stage.revision_days, res)
            vs.raw_segments.setdefault(si, []).append((kind, person.id, s, end, ot))
            if s > free[person.id] + 1e-9:
                res.append((s, end))
                res.sort()
            else:
                free[person.id] = end
        else:
            workload = 1.0 if stage.role == "content" else vs.project.video_minutes
            dur = workload / person.planning_rate() if kind == "work" else stage.revision_days
            parts, end = _place_work(free[person.id], vs.ready, dur, res)
            for ps_, pe_ in parts:
                vs.raw_segments.setdefault(si, []).append((kind, person.id, ps_, pe_, 0.0))
            free[person.id] = end
        vs.ready = end
        vs.pos += 1
        consume_non_person_steps(vs)
        if vs.pos >= len(vs.chain) or vs.chain[vs.pos][1] != si:
            vs.stage_done[si] = vs.ready

    # đóng gói kết quả theo dự án
    out: dict[str, ProjectSchedule] = {}
    for pi, project in enumerate(projects):
        videos = []
        for vs in states:
            if vs.project is not project:
                continue
            stage_results = []
            for si in sorted(vs.stage_done):
                role = project.stages[si].role
                primary = vs.stage_person[si]
                raw = vs.raw_segments.get(si, [])
                waits = [r for r in raw if r[1] is None]  # chờ feedback (dùng chung khâu)
                # gộp segment theo NGƯỜI — video gấp chia editor → N StageResult
                by_person: dict[str, list] = {}
                for r in raw:
                    if r[1] is not None:
                        by_person.setdefault(r[1], []).append(r)
                persons = list(by_person) or [primary]
                for pid in persons:
                    rs = list(by_person.get(pid, []))
                    if pid == primary:
                        rs += waits
                    rs.sort(key=lambda r: r[2])
                    segments = tuple(
                        Segment(kind, p_id, s, e,
                                nth_workday(anchor, workday_number_start(s)),
                                nth_workday(anchor, workday_number_end(e)), ot)
                        for kind, p_id, s, e, ot in rs
                    )
                    done_t = max((r[3] for r in rs), default=vs.stage_done[si])
                    stage_results.append(
                        StageResult(role, pid, people_by_id[pid].name,
                                    segments, done_t, date_at(anchor, done_t))
                    )
            handoff_t = max(vs.stage_done.values())
            handoff_date = date_at(anchor, handoff_t)
            late = 0
            if vs.video.publish_date is not None:
                # Bàn giao phải trước ngày đăng ít nhất HANDOFF_LEAD_DAYS ngày làm việc
                deadline_idx = workday_index(anchor, vs.video.publish_date) - HANDOFF_LEAD_DAYS
                late = max(0, workday_number_end(handoff_t) - deadline_idx)
            videos.append(
                VideoSchedule(
                    vs.video.index, vs.video.title, tuple(stage_results),
                    handoff_t, handoff_date, vs.video.publish_date, late,
                )
            )
        out[project.id] = ProjectSchedule(project.id, project.name, tuple(videos))
    return out
