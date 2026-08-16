from voiceprofile.generator import (
    clear_checkpoint,
    generate_script,
    load_checkpoint,
    save_checkpoint,
)

OUTLINE = "Title: T\nHook: h\nChapter 1: a\nChapter 2: b\nEnd: e"
PROFILE = {"author": "X", "exemplars": [], "signature_moves": []}


def test_save_load_checkpoint_roundtrip(tmp_path):
    out = tmp_path / "script.md"
    save_checkpoint(out, OUTLINE, 8000, {"Hook": "hook body"}, "glm", "glm-5.2")
    done = load_checkpoint(out, OUTLINE)
    assert done == {"Hook": "hook body"}


def test_load_checkpoint_ignores_when_outline_changed(tmp_path):
    out = tmp_path / "script.md"
    save_checkpoint(out, OUTLINE, 8000, {"Hook": "x"})
    assert load_checkpoint(out, "Title: T\nHook: DIFFERENT\nEnd: e") == {}  # outline khac -> bo


def test_clear_checkpoint(tmp_path):
    out = tmp_path / "script.md"
    save_checkpoint(out, OUTLINE, 8000, {"Hook": "x"})
    clear_checkpoint(out)
    assert load_checkpoint(out, OUTLINE) == {}


def test_generate_script_resumes_skipping_done_sections():
    calls = []

    def fake_llm(system, user, mx):
        # ghi lai heading dang duoc viet
        for h in ("Hook", "Chapter 1", "Chapter 2", "End"):
            if f'"{h}"' in user:
                calls.append(h)
        return "fresh body"

    done = {"Hook": "saved hook", "Chapter 1": "saved ch1"}
    script = generate_script(OUTLINE, PROFILE, fake_llm, total_chars=8000, done_sections=done)
    # Hook + Chapter 1 dung lai tu checkpoint -> KHONG goi LLM cho chung
    assert "Hook" not in calls and "Chapter 1" not in calls
    assert set(calls) == {"Chapter 2", "End"}  # chi viet phan chua co
    bodies = dict(script.sections)
    assert bodies["Hook"] == "saved hook"       # giu nguyen phan da co
    assert bodies["Chapter 2"] == "fresh body"


def test_on_section_done_called_per_new_section():
    saved = []
    done = {"Hook": "h"}
    generate_script(OUTLINE, PROFILE, lambda s, u, mx: "body",
                    total_chars=8000, done_sections=done,
                    on_section_done=lambda h, b: saved.append(h))
    # chi goi cho phan MOI viet (khong goi cho Hook da co)
    assert "Hook" not in saved
    assert set(saved) == {"Chapter 1", "Chapter 2", "End"}
