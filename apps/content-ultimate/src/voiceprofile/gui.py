"""Giao dien Tkinter cho Author Extract — 2 tab = 2 function.

Tab 1 (Extractor): folder ban thao -> build/rhetoric/clonekit/dataset.
Tab 2 (Writer):    chon tac gia trong thu vien + outline + do dai + LLM -> script.md + do %.

Ca hai tab chay pipeline qua subprocess (goi `python -m voiceprofile.cli ...`), log truc
tiep. Cac ham logic thuan tach rieng de test offline khong can mo cua so.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, ttk

_REPO_ROOT = Path(os.environ.get("CU_DATA_DIR") or Path(__file__).resolve().parents[2])  # V3: CU_DATA_DIR tro kho du lieu ra data/content-ultimate (Luat 6); mac dinh giu canh repo nhu V2
# Thu muc goi y khi mo hop thoai chon folder (khong con ep corpus/output o day nua).
DEFAULT_BROWSE = Path("/Users/daddychee/Desktop/Author")
if not DEFAULT_BROWSE.is_dir():
    DEFAULT_BROWSE = Path.home()

# Bang mau — dong bo voi mockup HTML da duyet (nen toi, accent vang muc cu).
PALETTE = {
    "page": "#17191d", "panel": "#24272c", "field": "#1b1d21", "border": "#3a3e46",
    "text": "#e9eaec", "muted": "#9aa0a8", "accent": "#d2a24c", "accent_ink": "#241c0d",
    "btn": "#383c44", "btn_hover": "#42464f", "good": "#6fbf7f", "bad": "#d97b6c",
    "log_bg": "#121316", "log_fg": "#cfd3d8",
}


class RoundedButton(tk.Canvas):
    """Nut bo tron tu ve tren Canvas (ttk khong ho tro border-radius).

    Nen canvas = mau nen cha (tham so `bg`) de 4 goc hoa vao khung -> trong bo tron.
    """
    def __init__(self, master, text, command=None, primary=False, bg=None,
                 min_width=0, radius=9, height=32):
        p = PALETTE
        self.p = p
        self.primary = primary
        self.command = command
        self._enabled = True
        self._text = text
        self._radius = radius
        self._parent_bg = bg or p["panel"]
        self._font = tkfont.Font(family="Helvetica", size=12, weight="bold" if primary else "normal")
        w = max(min_width, self._font.measure(text) + 30)
        super().__init__(master, width=w, height=height, highlightthickness=0,
                         background=self._parent_bg, cursor="hand2")
        # KHONG dat self._w / self._h — trung ten noi bo cua Tkinter (widget path)
        self._cw, self._ch = w, height
        self._draw(hover=False)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._enabled and self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw(hover=False))

    def _colors(self, hover):
        p = self.p
        if not self._enabled:
            return ("#5a5236" if self.primary else p["panel"]), p["muted"]
        if self.primary:
            return ("#ddb267" if hover else p["accent"]), p["accent_ink"]
        return (p["btn_hover"] if hover else p["btn"]), p["text"]

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, hover):
        if not self.winfo_exists():  # tranh ve lai sau khi canvas da bi huy
            return
        self.delete("all")
        bg, fg = self._colors(hover)
        self._round_rect(1, 1, self._cw - 1, self._ch - 1, self._radius, fill=bg, outline="")
        self.create_text(self._cw / 2, self._ch / 2, text=self._text, fill=fg, font=self._font)

    def _click(self, _):
        if self._enabled and self.command:
            self.command()

    def set_enabled(self, on: bool):
        self._enabled = on
        self.configure(cursor="hand2" if on else "arrow")
        self._draw(hover=False)


def apply_theme(root: tk.Tk) -> None:
    """Sơn toàn bộ ttk theo PALETTE (nền tối + accent vàng), giống mockup."""
    p = PALETTE
    root.configure(background=p["page"])
    # Dropdown popup (Listbox cua Combobox) — set qua option database
    root.option_add("*TCombobox*Listbox.background", p["field"])
    root.option_add("*TCombobox*Listbox.foreground", p["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["accent_ink"])

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=p["panel"], foreground=p["text"],
                 fieldbackground=p["field"], bordercolor=p["border"], font=("Helvetica", 12))
    st.configure("TFrame", background=p["panel"])
    st.configure("Page.TFrame", background=p["page"])
    st.configure("TLabel", background=p["panel"], foreground=p["text"])
    st.configure("Page.TLabel", background=p["page"], foreground=p["text"])
    st.configure("Muted.TLabel", background=p["page"], foreground=p["muted"])
    st.configure("H1.TLabel", background=p["page"], foreground=p["text"], font=("Helvetica", 20, "bold"))

    st.configure("TEntry", fieldbackground=p["field"], foreground=p["text"],
                 insertcolor=p["text"], bordercolor=p["border"], padding=5)
    st.configure("TCombobox", fieldbackground=p["field"], foreground=p["text"],
                 background=p["field"], arrowcolor=p["text"], bordercolor=p["border"], padding=4)
    st.map("TCombobox", fieldbackground=[("readonly", p["field"])],
           foreground=[("readonly", p["text"])], selectbackground=[("readonly", p["field"])],
           selectforeground=[("readonly", p["text"])])

    st.configure("TButton", background=p["btn"], foreground=p["text"],
                 bordercolor=p["border"], focuscolor=p["accent"], padding=(12, 6))
    st.map("TButton", background=[("active", p["btn_hover"]), ("disabled", p["panel"])],
           foreground=[("disabled", p["muted"])])
    st.configure("Primary.TButton", background=p["accent"], foreground=p["accent_ink"], padding=(14, 6))
    st.map("Primary.TButton", background=[("active", "#ddb267"), ("disabled", "#5a5236")],
           foreground=[("disabled", p["muted"])])

    st.configure("TCheckbutton", background=p["panel"], foreground=p["text"], focuscolor=p["accent"])
    st.map("TCheckbutton", background=[("active", p["panel"])])

    st.configure("TNotebook", background=p["page"], bordercolor=p["border"])
    st.configure("TNotebook.Tab", background=p["panel"], foreground=p["muted"], padding=(16, 7))
    st.map("TNotebook.Tab", background=[("selected", p["panel"])],
           foreground=[("selected", p["accent"])])


# --- Logic thuan (test duoc offline) — da chuyen sang dirsuggest.py de server
# headless (VPS khong co tkinter) dung duoc; re-export tai day cho tuong thich cu.
from .dirsuggest import (  # noqa: E402,F401
    default_author_name,
    default_output_dir,
    detect_corpus_dirs,
)


# --- Base pane: log + chay CLI qua subprocess ---------------------------------------

class _Pane(ttk.Frame):
    def __init__(self, master, root_win: tk.Tk):
        super().__init__(master, padding=12)
        self.root_win = root_win
        self.proc: subprocess.Popen | None = None
        self.stop_flag = threading.Event()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.txt: tk.Text | None = None

    def _make_log(self, parent, row: int) -> None:
        ttk.Label(parent, text="Log:").grid(row=row, column=0, sticky="nw", padx=8, pady=4)
        self.txt = tk.Text(parent, height=14, state="disabled",
                           background=PALETTE["log_bg"], foreground=PALETTE["log_fg"],
                           insertbackground=PALETTE["log_fg"], relief="flat",
                           highlightthickness=1, highlightbackground=PALETTE["border"])
        self.txt.grid(row=row + 1, column=0, columnspan=3, sticky="nsew", padx=8, pady=(0, 8))
        parent.rowconfigure(row + 1, weight=1)
        self.root_win.after(200, self._drain_log)

    def on_log_line(self, line: str) -> None:
        """Hook cho lop con (vd Writer cap nhat pills). Mac dinh khong lam gi."""

    def log(self, line: str) -> None:
        self.log_queue.put(line.rstrip("\n"))

    def _drain_log(self) -> None:
        if self.txt is not None:
            try:
                while True:
                    line = self.log_queue.get_nowait()
                    self.txt.configure(state="normal")
                    self.txt.insert("end", line + "\n")
                    self.txt.see("end")
                    self.txt.configure(state="disabled")
            except queue.Empty:
                pass
        self.root_win.after(200, self._drain_log)

    def run_cli(self, label: str, args: list[str], abort_on_fail: bool) -> bool:
        """Chay `python -m voiceprofile.cli <args>`, stream stdout vao log."""
        if self.stop_flag.is_set():
            return False
        self.log(f"\n=== {label} ===")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "voiceprofile.cli", *args],
            cwd=str(_REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.log(line)
            self.on_log_line(line.rstrip("\n"))
        code = self.proc.wait()
        self.proc = None
        if self.stop_flag.is_set():
            self.log("(Da dung theo yeu cau)")
            return False
        if code != 0:
            if abort_on_fail:
                self.log(f"LOI: buoc '{label}' that bai — dung.")
                return False
            self.log(f"(Buoc '{label}' loi — bo qua, chay tiep)")
        return True

    def stop(self) -> None:
        self.stop_flag.set()
        if self.proc is not None:
            self.proc.terminate()
        self.log("Dang dung...")


# --- Tab 1: Extractor ----------------------------------------------------------------

class ExtractorPane(_Pane):
    def __init__(self, master, root_win):
        super().__init__(master, root_win)
        pad = {"padx": 8, "pady": 4}

        ttk.Label(self, text="Folder ban thao:").grid(row=0, column=0, sticky="e", **pad)
        self.var_author_dir = tk.StringVar()
        ttk.Entry(self, textvariable=self.var_author_dir).grid(row=0, column=1, sticky="ew", **pad)
        RoundedButton(self, "Browse…", command=self.pick_author_dir).grid(row=0, column=2, **pad)

        ttk.Label(self, text="Bo van ban (corpus):").grid(row=1, column=0, sticky="e", **pad)
        self.var_corpus = tk.StringVar()
        self.cbo_corpus = ttk.Combobox(self, textvariable=self.var_corpus, state="readonly")
        self.cbo_corpus.grid(row=1, column=1, sticky="ew", **pad)

        ttk.Label(self, text="Ten tac gia:").grid(row=2, column=0, sticky="e", **pad)
        self.var_name = tk.StringVar()
        ttk.Entry(self, textvariable=self.var_name).grid(row=2, column=1, sticky="ew", **pad)

        ttk.Label(self, text="Folder ket qua:").grid(row=3, column=0, sticky="e", **pad)
        self.var_out = tk.StringVar()
        ttk.Entry(self, textvariable=self.var_out).grid(row=3, column=1, sticky="ew", **pad)
        RoundedButton(self, "Choose…", command=self.pick_out_dir).grid(row=3, column=2, **pad)

        opts = ttk.Frame(self)
        opts.grid(row=4, column=0, columnspan=3, sticky="w", **pad)
        self.var_rhetoric = tk.BooleanVar(value=True)
        self.var_clonekit = tk.BooleanVar(value=True)
        self.var_dataset = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Rhetoric (LLM + kiem chung)", variable=self.var_rhetoric).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(opts, text="Clone-kit", variable=self.var_clonekit).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(opts, text="Dataset JSONL", variable=self.var_dataset).pack(side="left")

        btns = ttk.Frame(self)
        btns.grid(row=5, column=0, columnspan=3, sticky="w", **pad)
        self.btn_start = RoundedButton(btns, "▶ START", command=self.start, primary=True, min_width=110)
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_stop = RoundedButton(btns, "■ Stop", command=self.stop)
        self.btn_stop.pack(side="left", padx=(0, 8))
        self.btn_open = RoundedButton(btns, "Mở folder kết quả", command=self.open_out)
        self.btn_open.pack(side="left")
        self.btn_stop.set_enabled(False)
        self.btn_open.set_enabled(False)

        self._make_log(self, row=6)
        self.columnconfigure(1, weight=1)

    def pick_author_dir(self):
        chosen = filedialog.askdirectory(title="Chon folder ban thao tac gia",
                                         initialdir=str(DEFAULT_BROWSE))
        if not chosen:
            return
        self.var_author_dir.set(chosen)
        dirs = detect_corpus_dirs(chosen)
        self.cbo_corpus["values"] = dirs
        self.var_corpus.set(dirs[0] if dirs else "")
        name = default_author_name(chosen)
        self.var_name.set(name)
        # Folder ket qua goi y theo ma thu vien: '{parent}/A001_Ten' (user co the doi)
        from .library import ensure_author, author_folder_name
        entry = ensure_author(name)
        self.var_out.set(default_output_dir(chosen, author_folder_name(entry)))
        if not dirs:
            self.log(f"CANH BAO: khong tim thay file .txt/.md nao trong {chosen}")

    def pick_out_dir(self):
        chosen = filedialog.askdirectory(title="Chon folder ket qua")
        if chosen:
            self.var_out.set(chosen)

    def open_out(self):
        out = self.var_out.get().strip()
        if out and Path(out).is_dir():
            subprocess.Popen(["open", out])

    def start(self):
        corpus = self.var_corpus.get().strip()
        name = self.var_name.get().strip()
        out = self.var_out.get().strip()
        if not corpus or not Path(corpus).is_dir():
            self.log("LOI: chua chon folder ban thao hop le (bam Browse...).")
            return
        if not name or not out:
            self.log("LOI: thieu ten tac gia hoac folder ket qua.")
            return
        Path(out).mkdir(parents=True, exist_ok=True)
        self.stop_flag.clear()
        self._set_running(True)
        threading.Thread(target=self._run, args=(corpus, name, out), daemon=True).start()

    def _run(self, corpus, name, out):
        profile = str(Path(out) / "profile.json")
        ok = self.run_cli("1. build (self-profile)",
                          ["build", "--author-dir", corpus, "--author", name, "--out", profile],
                          abort_on_fail=True)
        if ok and self.var_rhetoric.get():
            ok = self.run_cli("2. rhetoric",
                              ["rhetoric", "--author-dir", corpus, "--profile", profile, "--author", name],
                              abort_on_fail=False)
        if ok and self.var_clonekit.get():
            ok = self.run_cli("3. clonekit",
                              ["clonekit", "--author-dir", corpus, "--author", name,
                               "--out", str(Path(out) / "clonekit.md")], abort_on_fail=False)
        if ok and self.var_dataset.get():
            self.run_cli("4. dataset",
                         ["dataset", "--author-dir", corpus, "--author", name,
                          "--out", str(Path(out) / "dataset.jsonl")], abort_on_fail=False)
        self.log(f"\n=== XONG — ket qua trong: {out} ===")
        self.root_win.after(0, lambda: self._set_running(False))

    def _set_running(self, running: bool):
        self.btn_start.set_enabled(not running)
        self.btn_stop.set_enabled(running)
        self.btn_open.set_enabled(not running)


# --- Tab 2: Writer -------------------------------------------------------------------

class WriterPane(_Pane):
    def __init__(self, master, root_win):
        super().__init__(master, root_win)
        pad = {"padx": 8, "pady": 4}

        ttk.Label(self, text="Tac gia (thu vien):").grid(row=0, column=0, sticky="e", **pad)
        self.var_author = tk.StringVar()
        self.cbo_author = ttk.Combobox(self, textvariable=self.var_author, state="readonly")
        self.cbo_author.grid(row=0, column=1, sticky="ew", **pad)
        self.cbo_author.bind("<<ComboboxSelected>>", lambda e: self._suggest_script_path())
        RoundedButton(self, "Làm mới", command=self.refresh_library).grid(row=0, column=2, **pad)

        ttk.Label(self, text="LLM viet:").grid(row=1, column=0, sticky="e", **pad)
        self.var_llm = tk.StringVar()
        self.cbo_llm = ttk.Combobox(self, textvariable=self.var_llm, state="readonly")
        self.cbo_llm.grid(row=1, column=1, sticky="ew", **pad)

        ttk.Label(self, text="Do dai (ky tu):").grid(row=2, column=0, sticky="e", **pad)
        self.var_chars = tk.StringVar(value="18000")
        ttk.Entry(self, textvariable=self.var_chars, width=12).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(self, text="Lưu kịch bản (.md):").grid(row=3, column=0, sticky="e", **pad)
        self.var_script = tk.StringVar()
        ttk.Entry(self, textvariable=self.var_script).grid(row=3, column=1, sticky="ew", **pad)
        RoundedButton(self, "Save as…", command=self.pick_script_path).grid(row=3, column=2, **pad)

        ttk.Label(self, text="Outline:").grid(row=4, column=0, sticky="ne", **pad)
        self.txt_outline = tk.Text(self, height=8, background="#1b1d21", foreground="#e9eaec",
                                   insertbackground="#e9eaec", relief="flat")
        self.txt_outline.grid(row=4, column=1, columnspan=2, sticky="ew", **pad)
        self.txt_outline.insert("1.0",
            "Title: \nHook: \nChapter 1: \nChapter 2: \nEnd: ")

        btns = ttk.Frame(self)
        btns.grid(row=5, column=0, columnspan=3, sticky="w", **pad)
        self.btn_write = RoundedButton(btns, "▶ WRITE", command=self.start, primary=True, min_width=110)
        self.btn_write.pack(side="left", padx=(0, 8))
        self.btn_continue = RoundedButton(btns, "↻ Tiếp tục", command=lambda: self.start(resume=True))
        self.btn_continue.pack(side="left", padx=(0, 8))
        self.btn_stop = RoundedButton(btns, "■ Stop", command=self.stop)
        self.btn_stop.pack(side="left", padx=(0, 8))
        self.btn_open = RoundedButton(btns, "Mở script.md", command=self.open_script)
        self.btn_open.pack(side="left")
        self.btn_stop.set_enabled(False)
        self.btn_open.set_enabled(False)

        # Dãy pill tiến độ theo chương — minh họa "sinh tuần tự, chống trôi giọng"
        self.beats = ttk.Frame(self)
        self.beats.grid(row=6, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 4))
        self.pills: dict[str, tk.Label] = {}

        self._make_log(self, row=7)
        self.columnconfigure(1, weight=1)
        self.library: list[dict] = []
        self.script_path: str | None = None
        self.refresh_library()

    def _pill(self, heading: str, state: str) -> None:
        """state: idle | now | done. Cap nhat tren main thread."""
        colors = {"idle": PALETTE["muted"], "now": PALETTE["accent"], "done": PALETTE["good"]}
        lab = self.pills.get(heading)
        text = heading + (" ✓" if state == "done" else (" …" if state == "now" else ""))
        if lab is None:
            lab = tk.Label(self.beats, text=text, background=PALETTE["field"],
                           fg=colors[state], padx=10, pady=3, font=("Helvetica", 11, "bold"),
                           highlightthickness=1, highlightbackground=PALETTE["border"])
            lab.pack(side="left", padx=3)
            self.pills[heading] = lab
        else:
            lab.configure(text=text, fg=colors[state])

    def _reset_pills(self, outline: str, done_headings: set | None = None) -> None:
        done_headings = done_headings or set()
        for lab in self.pills.values():
            lab.destroy()
        self.pills.clear()
        from .generator import parse_outline
        for sec in parse_outline(outline):
            if sec.kind != "title":
                self._pill(sec.heading, "done" if sec.heading in done_headings else "idle")

    def on_log_line(self, line: str) -> None:
        # generator in "Dang viet {heading} (~..." va "  {heading}: N ky tu"
        import re
        m = re.match(r"Dang viet (.+?) \(", line)
        if m:
            self.root_win.after(0, lambda h=m.group(1): self._pill(h, "now"))
            return
        m = re.match(r"\s+(.+?): \d+ ky tu", line)
        if m:
            self.root_win.after(0, lambda h=m.group(1): self._pill(h, "done"))

    def refresh_library(self):
        from .library import list_authors
        entries = list_authors()
        self.library = []
        labels = []
        for a in entries:
            n_moves = n_targets = 0
            try:
                data = json.loads(Path(a["profile"]).read_text(encoding="utf-8"))
                n_moves = len(data.get("signature_moves", []))
                n_targets = len(data.get("reproduction_targets", {}))
            except (json.JSONDecodeError, OSError):
                pass
            self.library.append({"name": a["name"], "code": a["code"],
                                 "profile": a["profile"], "corpus": a.get("corpus"),
                                 "output": str(Path(a["profile"]).parent)})
            labels.append(f"{a['code']} · {a['name']} — {n_targets} targets · {n_moves} moves")
        self.cbo_author["values"] = labels
        if labels:
            self.cbo_author.current(0)
            self._suggest_script_path()
        # LLM providers co key trong .env
        try:
            from .llm import available_providers, PROVIDERS
            avail = available_providers()
            llm_labels = [f"{PROVIDERS[p]['label']} — {c['model']}" for p, c in avail.items()]
            self._llm_keys = list(avail.keys())
        except Exception:
            llm_labels, self._llm_keys = [], []
        self.cbo_llm["values"] = llm_labels
        if llm_labels:
            self.cbo_llm.current(0)
        else:
            self.log("CANH BAO: chua co LLM nao trong .env — dien key roi bam 'Lam moi'.")

    def _selected(self) -> dict | None:
        i = self.cbo_author.current()
        return self.library[i] if 0 <= i < len(self.library) else None

    def _suggest_script_path(self) -> None:
        """Goi y noi luu = folder profile cua tac gia dang chon (Save as de doi cho)."""
        author = self._selected()
        if author:
            self.var_script.set(str(Path(author["output"]) / "script.md"))

    def pick_script_path(self) -> None:
        author = self._selected()
        current = self.var_script.get().strip()
        init_dir = str(Path(current).parent) if current else (
            author["output"] if author else str(DEFAULT_BROWSE))
        chosen = filedialog.asksaveasfilename(
            title="Luu kich ban tai", defaultextension=".md", initialfile="script.md",
            initialdir=init_dir, filetypes=[("Markdown", "*.md"), ("Text", "*.txt")])
        if chosen:
            self.var_script.set(chosen)

    def open_script(self):
        if self.script_path and Path(self.script_path).is_file():
            subprocess.Popen(["open", self.script_path])

    def start(self, resume: bool = False):
        from .generator import parse_outline, load_checkpoint
        author = self._selected()
        if not author:
            self.log("LOI: chua chon tac gia (bam 'Lam moi' neu thu vien trong).")
            return
        outline = self.txt_outline.get("1.0", "end").strip()
        content = [s for s in parse_outline(outline) if s.kind != "title"]
        if not content:
            self.log("LOI: outline chua co phan nao. Dien theo khung Title / Hook / "
                     "Chapter 1 / Chapter 2 / End (co the co hoac khong dau ':').")
            return
        try:
            chars = int(self.var_chars.get())
        except ValueError:
            self.log("LOI: do dai phai la so nguyen (ky tu).")
            return
        i = self.cbo_llm.current()
        if not (0 <= i < len(self._llm_keys)):
            self.log("LOI: chua chon LLM (dien key vao .env, bam 'Lam moi').")
            return
        provider = self._llm_keys[i]

        script_path = self.var_script.get().strip() or str(Path(author["output"]) / "script.md")
        out_dir = Path(script_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        # outline.txt dat canh file kich ban, theo ten file (cho phep nhieu kich ban 1 folder)
        outline_file = out_dir / (Path(script_path).stem + ".outline.txt")
        outline_file.write_text(outline, encoding="utf-8")
        self.script_path = script_path

        args = ["write", "--outline", str(outline_file), "--profile", author["profile"],
                "--out", self.script_path, "--chars", str(chars), "--provider", provider,
                "--continue" if resume else "--fresh"]
        if author["corpus"]:
            args += ["--author-dir", author["corpus"]]

        # pills: khi Tiep tuc, danh dau cac phan da co trong checkpoint la done
        done = load_checkpoint(self.script_path, outline) if resume else {}
        self._reset_pills(outline, done_headings=set(done))
        self.stop_flag.clear()
        self._set_running(True)
        threading.Thread(target=self._run, args=(args, resume), daemon=True).start()

    def _run(self, args, resume):
        label = "TIEP TUC" if resume else "WRITE"
        self.run_cli(f"{label} — {args[args.index('--provider')+1]}", args, abort_on_fail=True)
        self.log(f"\n=== XONG — script: {self.script_path} ===")
        self.root_win.after(0, lambda: self._set_running(False))

    def _set_running(self, running: bool):
        self.btn_write.set_enabled(not running)
        self.btn_continue.set_enabled(not running)
        self.btn_stop.set_enabled(running)
        self.btn_open.set_enabled(not running)


# --- App -----------------------------------------------------------------------------

class App:
    def __init__(self, root: tk.Tk):
        root.title("Author Extract")
        root.geometry("980x720")
        apply_theme(root)
        top = ttk.Frame(root, padding=(14, 12, 14, 0), style="Page.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Author Extract", style="H1.TLabel").pack(anchor="w")
        ttk.Label(top, style="Muted.TLabel",
                  text="① Extractor: bản thảo → hồ sơ giọng   ·   ② Writer: outline → kịch bản YouTube theo giọng"
                  ).pack(anchor="w")

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        nb.add(ExtractorPane(nb, root), text="  ① Extractor  ")
        nb.add(WriterPane(nb, root), text="  ② Writer  ")

        if os.environ.get("VP_GUI_SMOKE"):
            root.after(1500, root.destroy)


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
