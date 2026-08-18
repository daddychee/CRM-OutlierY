#!/usr/bin/env python3
"""
Niche Research — dark-theme desktop launcher (Author Extract design language).

Pick competitors.txt → press ▶ START. Streams the log live. Stage pills track progress.
Press 🔄 Refresh to continue any stopped run (remembered across app restarts).

    python3 niche_research_gui.py
"""
import os, sys, json, queue, threading, subprocess, re
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
ORCH = os.path.join(HERE, "orchestrator.py")
LAST_PROJECT_PTR = os.path.join(HERE, ".last_project.json")
DATA_DIRNAME = "niche-data"

# ── Palette (đồng bộ với Author Extract) ─────────────────────────────────────
PALETTE = {
    "page":       "#17191d",
    "panel":      "#24272c",
    "field":      "#1b1d21",
    "border":     "#3a3e46",
    "text":       "#e9eaec",
    "muted":      "#9aa0a8",
    "accent":     "#d2a24c",
    "accent_ink": "#241c0d",
    "btn":        "#383c44",
    "btn_hover":  "#42464f",
    "good":       "#6fbf7f",
    "bad":        "#d97b6c",
    "warn":       "#d2a24c",
    "log_bg":     "#121316",
    "log_fg":     "#cfd3d8",
}

# Các stage chính để hiển thị pills
STAGE_PILLS = [
    ("S1",  "Scan"),
    ("S3",  "Keywords"),
    ("S4",  "Comments"),
    ("S5",  "Crackability"),
    ("S6",  "Monetization"),
    ("S7",  "Demand"),
    ("S8",  "Go/No-Go"),
    ("S9",  "Sub-niche"),
    ("S10", "Beachhead"),
    ("S11", "Bets"),
    ("S12", "Auditor"),
    ("S13", "Plan"),
    ("S19", "Summary"),
    ("S18", "Report"),
]
STAGE_IDS = [s for s, _ in STAGE_PILLS]


def state_path(project):
    if not project: return None
    for cand in (os.path.join(project, DATA_DIRNAME, ".state.json"),
                 os.path.join(project, ".state.json")):
        if os.path.exists(cand): return cand
    return None


# ── RoundedButton (Canvas tự vẽ, giống Author Extract) ───────────────────────
class RoundedButton(tk.Canvas):
    def __init__(self, master, text, command=None, primary=False,
                 bg=None, min_width=0, radius=9, height=34):
        p = PALETTE
        self.primary  = primary
        self.command  = command
        self._enabled = True
        self._text    = text
        self._radius  = radius
        self._parent_bg = bg or p["panel"]
        self._font = tkfont.Font(family="Helvetica", size=12,
                                 weight="bold" if primary else "normal")
        w = max(min_width, self._font.measure(text) + 34)
        super().__init__(master, width=w, height=height, highlightthickness=0,
                         background=self._parent_bg, cursor="hand2")
        self._cw, self._ch = w, height
        self._draw(hover=False)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self._enabled and self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw(hover=False))

    def _colors(self, hover):
        p = PALETTE
        if not self._enabled:
            return ("#5a5236" if self.primary else p["panel"]), p["muted"]
        if self.primary:
            return ("#ddb267" if hover else p["accent"]), p["accent_ink"]
        return (p["btn_hover"] if hover else p["btn"]), p["text"]

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
               x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, hover):
        if not self.winfo_exists(): return
        self.delete("all")
        bg, fg = self._colors(hover)
        self._round_rect(1, 1, self._cw-1, self._ch-1, self._radius,
                         fill=bg, outline="")
        self.create_text(self._cw/2, self._ch/2, text=self._text,
                         fill=fg, font=self._font)

    def _click(self, _):
        if self._enabled and self.command:
            self.command()

    def set_enabled(self, on: bool):
        self._enabled = on
        self.configure(cursor="hand2" if on else "arrow")
        self._draw(hover=False)


# ── apply_theme: sơn toàn bộ ttk theo palette ─────────────────────────────────
def apply_theme(root: tk.Tk) -> None:
    p = PALETTE
    root.configure(background=p["page"])
    root.option_add("*TCombobox*Listbox.background", p["field"])
    root.option_add("*TCombobox*Listbox.foreground", p["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["accent_ink"])

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=p["panel"], foreground=p["text"],
                 fieldbackground=p["field"], bordercolor=p["border"],
                 font=("Helvetica", 12))
    st.configure("TFrame",      background=p["panel"])
    st.configure("Page.TFrame", background=p["page"])
    st.configure("TLabel",      background=p["panel"], foreground=p["text"])
    st.configure("Page.TLabel", background=p["page"],  foreground=p["text"])
    st.configure("Muted.TLabel",background=p["page"],  foreground=p["muted"])
    st.configure("H1.TLabel",   background=p["page"],  foreground=p["text"],
                 font=("Helvetica", 20, "bold"))
    st.configure("Status.TLabel", background=p["page"], foreground=p["muted"],
                 font=("Helvetica", 11))

    st.configure("TEntry", fieldbackground=p["field"], foreground=p["text"],
                 insertcolor=p["text"], bordercolor=p["border"], padding=6)

    st.configure("TButton", background=p["btn"], foreground=p["text"],
                 bordercolor=p["border"], focuscolor=p["accent"], padding=(12, 6))
    st.map("TButton",
           background=[("active", p["btn_hover"]), ("disabled", p["panel"])],
           foreground=[("disabled", p["muted"])])

    st.configure("TCheckbutton", background=p["panel"], foreground=p["text"],
                 focuscolor=p["accent"])
    st.map("TCheckbutton", background=[("active", p["panel"])])

    st.configure("TSeparator", background=p["border"])


# ── Pill widget cho stage progress ────────────────────────────────────────────
class StagePill(tk.Label):
    """Nhỏ màu theo trạng thái: idle | now | done | skip | error."""
    _COLORS = {
        "idle":  ("#3a3e46", "#9aa0a8"),   # bg, fg
        "now":   ("#3d3316", "#d2a24c"),
        "done":  ("#1a3325", "#6fbf7f"),
        "skip":  ("#2a2d33", "#555b65"),
        "error": ("#3a1c1c", "#d97b6c"),
    }

    def __init__(self, master, label: str):
        bg, fg = self._COLORS["idle"]
        super().__init__(master, text=label, fg=fg, bg=bg,
                         padx=9, pady=3, font=("Helvetica", 10, "bold"),
                         highlightthickness=1, highlightbackground=PALETTE["border"])
        self._state = "idle"

    def set_state(self, state: str):
        if state == self._state: return
        self._state = state
        bg, fg = self._COLORS.get(state, self._COLORS["idle"])
        self.configure(bg=bg, fg=fg, highlightbackground=PALETTE["border"])


# ── App ────────────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.proc = None
        self.q: queue.Queue = queue.Queue()
        self.last_out = None
        self.deepdive_anchor = None
        self._active_stage: str | None = None

        root.title("Niche Research")
        root.geometry("940x680")
        root.minsize(760, 540)
        apply_theme(root)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = ttk.Frame(root, padding=(16, 14, 16, 6), style="Page.TFrame")
        hdr.pack(fill="x")
        ttk.Label(hdr, text="Niche Research", style="H1.TLabel").pack(anchor="w")
        ttk.Label(hdr, style="Muted.TLabel",
                  text="Competitor channels → market map · Go/No-Go · beachhead · bets (Excel report)"
                  ).pack(anchor="w")

        sep = ttk.Separator(root, orient="horizontal")
        sep.pack(fill="x", padx=0)

        # ── Form ────────────────────────────────────────────────────────────
        frm = ttk.Frame(root, padding=(16, 12, 16, 8), style="Page.TFrame")
        frm.pack(fill="x")
        frm.columnconfigure(1, weight=1)

        p = PALETTE
        lkw = {"sticky": "e", "padx": (0, 8), "pady": 5}
        ekw = {"sticky": "ew", "pady": 5}

        def field_label(row, text):
            tk.Label(frm, text=text, fg=p["muted"], bg=p["page"],
                     font=("Helvetica", 11)).grid(row=row, column=0, **lkw)

        def field_entry(row, var):
            e = tk.Entry(frm, textvariable=var, bg=p["field"], fg=p["text"],
                         insertbackground=p["text"], relief="flat",
                         highlightthickness=1, highlightbackground=p["border"],
                         font=("Helvetica", 11))
            e.grid(row=row, column=1, **ekw)
            return e

        self.input_var = tk.StringVar()
        self.out_var   = tk.StringVar()
        self.work_var  = tk.StringVar()

        field_label(0, "Competitors file:")
        field_entry(0, self.input_var)
        RoundedButton(frm, "Browse…", command=self.pick_input,
                      bg=p["page"]).grid(row=0, column=2, padx=(8,0), pady=5)

        field_label(1, "Output .xlsx:")
        field_entry(1, self.out_var)
        RoundedButton(frm, "Save as…", command=self.pick_output,
                      bg=p["page"]).grid(row=1, column=2, padx=(8,0), pady=5)

        field_label(2, "Project folder:")
        field_entry(2, self.work_var)
        RoundedButton(frm, "Choose…", command=self.pick_work,
                      bg=p["page"]).grid(row=2, column=2, padx=(8,0), pady=5)

        # ── Options checkboxes ───────────────────────────────────────────────
        self.skip_comments = tk.BooleanVar(value=False)
        self.force         = tk.BooleanVar(value=False)
        self.deepdive      = tk.BooleanVar(value=False)
        self.llm           = tk.BooleanVar(value=False)

        opts = tk.Frame(frm, bg=p["page"])
        opts.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 2))

        def ck(parent, text, var):
            c = tk.Checkbutton(parent, text=text, variable=var,
                               bg=p["page"], fg=p["text"], selectcolor=p["field"],
                               activebackground=p["page"], activeforeground=p["text"],
                               font=("Helvetica", 11))
            c.pack(side="left", padx=(0, 18))
            return c

        ck(opts, "Skip comments (faster)", self.skip_comments)
        ck(opts, "Force rebuild",          self.force)
        ck(opts, "Deep-dive transcripts",  self.deepdive)
        ck(opts, "🤖 LLM analysis",        self.llm)

        # ── Buttons ──────────────────────────────────────────────────────────
        btns = tk.Frame(frm, bg=p["page"])
        btns.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 2))

        self.btn_start   = RoundedButton(btns, "▶  START",           command=self.start,
                                         primary=True, min_width=120, bg=p["page"])
        self.btn_stop    = RoundedButton(btns, "■  Stop",             command=self.stop,
                                         bg=p["page"])
        self.btn_refresh = RoundedButton(btns, "🔄  Refresh",          command=self.refresh,
                                         bg=p["page"])
        self.btn_open    = RoundedButton(btns, "Open report",         command=self.open_report,
                                         bg=p["page"])
        self.btn_start.pack(  side="left", padx=(0, 8))
        self.btn_stop.pack(   side="left", padx=(0, 8))
        self.btn_refresh.pack(side="left", padx=(0, 8))
        self.btn_open.pack(   side="left")
        self.btn_stop.set_enabled(False)
        self.btn_open.set_enabled(False)

        # ── Status hint ──────────────────────────────────────────────────────
        self.hint_var = tk.StringVar()
        tk.Label(frm, textvariable=self.hint_var, fg=p["muted"], bg=p["page"],
                 font=("Helvetica", 10), anchor="w"
                 ).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4,0))

        sep2 = ttk.Separator(root, orient="horizontal")
        sep2.pack(fill="x")

        # ── Stage pills ──────────────────────────────────────────────────────
        pill_bar = tk.Frame(root, bg=p["page"], pady=8)
        pill_bar.pack(fill="x", padx=16)
        self._pills: dict[str, StagePill] = {}
        for sid, label in STAGE_PILLS:
            pill = StagePill(pill_bar, f"{sid} {label}")
            pill.pack(side="left", padx=3)
            self._pills[sid] = pill

        sep3 = ttk.Separator(root, orient="horizontal")
        sep3.pack(fill="x")

        # ── Log ──────────────────────────────────────────────────────────────
        log_frame = tk.Frame(root, bg=p["page"])
        log_frame.pack(fill="both", expand=True, padx=16, pady=(8, 12))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        mono = "Consolas" if os.name == "nt" else "Menlo"
        self.log = tk.Text(log_frame, wrap="word",
                           background=p["log_bg"], foreground=p["log_fg"],
                           insertbackground=p["log_fg"], relief="flat",
                           font=(mono, 11), highlightthickness=1,
                           highlightbackground=p["border"])
        self.log.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(log_frame, command=self.log.yview,
                          bg=p["panel"], troughcolor=p["log_bg"],
                          activebackground=p["btn"])
        sb.grid(row=0, column=1, sticky="ns")
        self.log["yscrollcommand"] = sb.set

        # ── Kick-off ─────────────────────────────────────────────────────────
        self.root.after(100, self.drain)
        self._try_autoload_last_project()

    # ── Pills helpers ─────────────────────────────────────────────────────────
    def _reset_pills(self):
        self._active_stage = None
        for pill in self._pills.values():
            pill.set_state("idle")

    def _advance_pill(self, stage_id: str):
        """Khi S<N> bắt đầu: stage trước → done, stage này → now."""
        if self._active_stage and self._active_stage in self._pills:
            self._pills[self._active_stage].set_state("done")
        if stage_id in self._pills:
            self._pills[stage_id].set_state("now")
            self._active_stage = stage_id

    def _finish_pills(self, success: bool):
        if self._active_stage and self._active_stage in self._pills:
            self._pills[self._active_stage].set_state("done" if success else "error")
            self._active_stage = None

    def _parse_log_for_pill(self, line: str):
        """Phát hiện '>>> [N/total] S<id>  ...' để cập nhật pills."""
        m = re.search(r">>>\s*\[(\d+)/(\d+)\]\s+(S[\w/]+)", line)
        if m:
            sid = m.group(3)
            # Chuẩn hóa: "S9b" → "S9", "S16/17" → "S16/17" (giữ nguyên), etc.
            canonical = sid if sid in self._pills else sid.split("/")[0].rstrip("b")
            self.root.after(0, lambda s=canonical: self._advance_pill(s))

    # ── File dialogs ──────────────────────────────────────────────────────────
    def pick_input(self):
        f = filedialog.askopenfilename(title="Choose competitors.txt",
                                       filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if f:
            self.input_var.set(f)
            proj = os.path.dirname(f)
            stem = os.path.splitext(os.path.basename(f))[0].strip()
            self.work_var.set(proj)
            self.out_var.set(os.path.join(proj, f"{stem}_report.xlsx"))

    def pick_output(self):
        f = filedialog.asksaveasfilename(title="Save report as", defaultextension=".xlsx",
                                         filetypes=[("Excel", "*.xlsx")])
        if f: self.out_var.set(f)

    def pick_work(self):
        d = filedialog.askdirectory(title="Choose project folder")
        if d: self.work_var.set(d)

    # ── Last-project persistence ──────────────────────────────────────────────
    def _save_last_project_ptr(self, work):
        try:
            json.dump({"work": work}, open(LAST_PROJECT_PTR, "w", encoding="utf-8"))
        except Exception:
            pass

    def _try_autoload_last_project(self):
        try:
            work = json.load(open(LAST_PROJECT_PTR, encoding="utf-8")).get("work")
            state_fp = state_path(work)
            if not (work and os.path.isdir(work) and state_fp): return
            state = json.load(open(state_fp, encoding="utf-8"))
            if not (state.get("input") and os.path.isfile(state["input"])): return
            self.input_var.set(state["input"]); self.work_var.set(work)
            if state.get("out"): self.out_var.set(state["out"]); self.last_out = state["out"]
            self.skip_comments.set(bool(state.get("skip_comments")))
            self.deepdive.set(state.get("deepdive") is not None)
            self.deepdive_anchor = state.get("deepdive") or None
            self.llm.set(bool(state.get("llm")))
            self.hint_var.set(f"Loaded: {work}  —  press 🔄 Refresh to continue, or ▶ START to redo.")
        except Exception:
            pass

    # ── Run machinery ─────────────────────────────────────────────────────────
    def _run_argv(self, argv, work_for_ptr=None):
        self.log.delete("1.0", "end")
        self._reset_pills()
        self.btn_start.set_enabled(False)
        self.btn_stop.set_enabled(True)
        self.btn_open.set_enabled(False)
        if work_for_ptr: self._save_last_project_ptr(work_for_ptr)
        threading.Thread(target=self._worker, args=(argv,), daemon=True).start()

    def start(self):
        inp = self.input_var.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror("Niche Research",
                                 "Please choose a valid competitors file first."); return
        work = self.work_var.get().strip() or os.path.dirname(inp)
        argv = [sys.executable, ORCH, "run", inp]
        if self.work_var.get().strip(): argv += ["--work", self.work_var.get().strip()]
        if self.out_var.get().strip():
            argv += ["--out", self.out_var.get().strip()]
            self.last_out = self.out_var.get().strip()
        if self.skip_comments.get(): argv += ["--skip-comments"]
        if self.force.get():         argv += ["--force"]
        if self.deepdive.get():
            argv += ["--deepdive"] + ([self.deepdive_anchor] if self.deepdive_anchor else [])
        if self.llm.get():           argv += ["--llm"]
        self.hint_var.set("")
        self._run_argv(argv, work_for_ptr=work)

    def refresh(self):
        """Continue a run that stopped (closed window, crash, quota, etc.).
        Uses currently loaded project, then last-touched project, then asks."""
        work = self.work_var.get().strip()
        if not (work and os.path.isdir(work) and state_path(work)):
            work = None
            try:
                w = json.load(open(LAST_PROJECT_PTR, encoding="utf-8")).get("work")
                if w and state_path(w): work = w
            except Exception:
                pass
        if not work:
            d = filedialog.askdirectory(title="Choose the project folder to continue")
            if not d: return
            if not state_path(d):
                messagebox.showerror("Niche Research",
                    "No previous run found (missing niche-data/.state.json). "
                    "Use ▶ START on a competitors.txt first.")
                return
            work = d
        try:
            state = json.load(open(state_path(work), encoding="utf-8"))
            self.input_var.set(state.get("input", "")); self.work_var.set(work)
            if state.get("out"): self.out_var.set(state["out"]); self.last_out = state["out"]
            self.skip_comments.set(bool(state.get("skip_comments")))
            self.deepdive.set(state.get("deepdive") is not None)
            self.deepdive_anchor = state.get("deepdive") or None
            self.llm.set(bool(state.get("llm")))
        except Exception:
            pass
        self.hint_var.set(f"Resuming: {work}")
        self._run_argv([sys.executable, ORCH, "resume", work], work_for_ptr=work)

    def _worker(self, argv):
        try:
            env = dict(os.environ, PYTHONUNBUFFERED="1")
            self.proc = subprocess.Popen(
                argv, cwd=HERE, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            for line in self.proc.stdout:
                self.q.put(("log", line))
            self.proc.wait()
            self.q.put(("done", self.proc.returncode))
        except Exception as e:
            self.q.put(("log", f"\n[launcher error] {e}\n"))
            self.q.put(("done", 1))
        finally:
            self.proc = None

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.q.put(("log", "\n[stopped — press 🔄 Refresh to continue]\n"))

    def drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    clean = re.sub(r"\033\[[0-9;]*m", "", payload)
                    self.log.insert("end", clean)
                    self.log.see("end")
                    self._parse_log_for_pill(clean)
                elif kind == "done":
                    success = (payload == 0)
                    self._finish_pills(success)
                    self.btn_start.set_enabled(True)
                    self.btn_stop.set_enabled(False)
                    if success:
                        self.btn_open.set_enabled(True)
                        self.log.insert("end", "\n✓ Finished — click 'Open report'.\n")
                        self.hint_var.set("Done! Click 'Open report' to view the Excel.")
                    else:
                        self.log.insert("end",
                            f"\n✗ Exited (code {payload}) — press 🔄 Refresh to continue.\n")
                        self.hint_var.set("Run stopped. Press 🔄 Refresh once the issue is fixed.")
                    self.log.see("end")
        except queue.Empty:
            pass
        self.root.after(100, self.drain)

    def open_report(self):
        path = self.last_out
        if not path or not os.path.isfile(path):
            inp  = self.input_var.get().strip()
            stem = os.path.splitext(os.path.basename(inp))[0] if inp else "competitor"
            proj = self.work_var.get().strip() or HERE
            cands = [os.path.join(proj, "Report", f"{stem}_report.xlsx"),
                     os.path.join(proj, f"{stem}_report.xlsx")]
            path = next((c for c in cands if os.path.isfile(c)), cands[0])
        if os.path.isfile(path):
            if sys.platform == "darwin": subprocess.run(["open", path])
            elif os.name == "nt":        os.startfile(path)  # noqa
            else:                        subprocess.run(["xdg-open", path])
        else:
            messagebox.showinfo("Niche Research", "Report file not found yet.")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
