"""Test parser extract_json (offline, không gọi mạng/không tốn credit)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from oe.llm import extract_json


def test_fenced():
    assert extract_json("```json\n{\"a\": 1}\n```") == {"a": 1}


def test_prose_and_trailing_comma():
    assert extract_json('kết quả: {"a":1, "b":[2,3,]}') == {"a": 1, "b": [2, 3]}


def test_truncated_array():
    assert extract_json('[{"x":1},{"y":2}') == [{"x": 1}, {"y": 2}]


def test_truncated_string():
    assert extract_json('{"t":"câu bị cắt') == {"t": "câu bị cắt"}


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} test xanh.")
