"""Verify S2 hai cách (luật B4): heatmap giả có đỉnh đặt sẵn + fixture video thật.

Chạy:  python3 tests/test_peaks.py   (không cần mạng — fixture đóng gói sẵn)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from oe.heatmap import Bucket, parse_heatmap
from oe.peaks import detect_peaks

FIXTURE = Path(__file__).parent / "fixture_real_video.info.json"


def make_heatmap(values, dur=1000.0):
    n = len(values)
    blen = dur / n
    return [Bucket(i * blen, (i + 1) * blen, v) for i, v in enumerate(values)]


def test_planted_peak_found_and_head_artifact_dropped():
    vals = [0.2] * 100
    vals[0] = 0.9          # artifact đầu video — phải bị bỏ
    vals[60] = 0.95        # đỉnh đặt sẵn
    vals[61] = 0.5
    peaks = detect_peaks(make_heatmap(vals))
    idxs = [p.idx for p in peaks]
    assert 60 in idxs, f"không thấy đỉnh đặt sẵn @60: {idxs}"
    assert 0 not in idxs, f"artifact đầu lọt vào đỉnh: {idxs}"
    assert peaks[0].idx == 60
    assert peaks[0].t_start < peaks[0].t_center < peaks[0].t_end


def test_chapter_marks_navigation():
    vals = [0.2] * 100
    vals[60] = 0.95
    peaks = detect_peaks(make_heatmap(vals), chapter_starts=[600.0])
    assert any(p.idx == 60 and p.is_navigation for p in peaks)


def test_real_fixture():
    info = json.loads(FIXTURE.read_text(encoding="utf-8"))
    peaks = detect_peaks(parse_heatmap(info))
    assert peaks, "video thật phải có ít nhất 1 đỉnh"
    assert peaks[0].intensity_z >= 1.0
    # đỉnh mạnh nhất của fixture này ở ~06:45
    assert 380 <= peaks[0].t_center <= 430


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} test xanh.")
