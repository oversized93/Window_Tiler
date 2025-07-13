import tkinter as tk
from tkinter import ttk, messagebox
import pygetwindow as gw
from screeninfo import get_monitors
import time
import sys
import os

# Hide console window on Windows
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass


class WindowTiler:
    """
    Resize / tile any application across a chosen monitor.
    Includes minimized windows automatically and matches titles
    case‑insensitively so slight changes (FPS counter, etc.) don’t break it.
    """

    # ──────────────────────────── GUI SET‑UP ────────────────────────────
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Window Tiler")

        self.status_lbl = tk.Label(root, text="Press Detect to begin.")
        self.status_lbl.pack(pady=(10, 6))

        btn_bar = tk.Frame(root)
        btn_bar.pack()
        tk.Button(btn_bar, text="Detect", width=10,
                  command=self.detect).pack(side="left", padx=5)
        tk.Button(btn_bar, text="Sort", width=10,
                  command=self.sort).pack(side="left", padx=5)

        self.monitor_var = tk.StringVar()
        self.monitor_cbx = ttk.Combobox(
            root, textvariable=self.monitor_var, state="readonly", width=44
        )
        self.monitor_cbx.pack(pady=(10, 4))

        self.app_var = tk.StringVar()
        self.app_cbx = ttk.Combobox(
            root, textvariable=self.app_var, state="readonly", width=44
        )
        self.app_cbx.pack(pady=4)

        # ── internal state ──
        self.monitors: list = []
        self.app_titles: list[str] = []
        self.target_windows: list = []

        # F5 quick re‑detect
        self.root.bind("<F5>", lambda *_: self.detect())

    # ─────────────────── MONITOR & TITLE DETECTION ────────────────────
    def detect(self):
        # monitors ------------------------------------------------------
        self.monitors = get_monitors()
        self.monitor_cbx["values"] = [
            f"Monitor {i+1}: {m.width}×{m.height} @({m.x},{m.y})"
            for i, m in enumerate(self.monitors)
        ]
        if self.monitors and self.monitor_cbx.current() == -1:
            self.monitor_cbx.current(0)

        # application window titles ------------------------------------
        all_wins = [w for w in gw.getAllWindows() if w.title]
        seen = set()
        self.app_titles = []
        for w in all_wins:           # first occurrence of each distinct title
            if w.title not in seen:
                seen.add(w.title)
                self.app_titles.append(w.title)

        self.app_cbx["values"] = self.app_titles
        if self.app_titles and self.app_cbx.current() == -1:
            self.app_cbx.current(0)

        self._update_status()

    # ───────────────────────── TILING LOGIC ───────────────────────────
    def sort(self):
        if not self.monitors or not self.app_titles:
            messagebox.showerror("Error", "Run 'Detect' first.")
            return

        mon_idx = self.monitor_cbx.current()
        app_idx = self.app_cbx.current()
        if mon_idx == -1 or app_idx == -1:
            messagebox.showerror("Error", "Pick a monitor and an application.")
            return

        mon = self.monitors[mon_idx]
        app_text = self.app_titles[app_idx].lower()

        # refresh window list (in case new ones opened)
        self.target_windows = []
        for w in gw.getAllWindows():
            title = w.title or ""
            if app_text in title.lower():           # case‑insensitive match
                if w.isMinimized:
                    try:
                        w.restore()                 # pop it back
                    except Exception:
                        pass
                # Always include the window regardless of visibility state
                self.target_windows.append(w)

        n = len(self.target_windows)
        if n == 0:
            messagebox.showinfo(
                "Nothing to do",
                f"No matching windows containing '{self.app_titles[app_idx]}'."
            )
            self._update_status()
            return

        # grid dimensions ------------------------------------------------
        if n == 4:
            # Special case: 2x2 quadrant split for 4 windows
            cols = 2
            rows = 2
        else:
            cols = min(3, n)  # Maximum 3 columns, prioritize horizontal spread
            rows = (n + cols - 1) // cols
        
        # Account for window decorations (title bar, borders) and add small gaps
        title_bar_height = 30  # typical title bar height
        border_width = 8       # typical window border width
        horizontal_gap = 1    # horizontal gap between columns
        vertical_gap = 1      # vertical gap between rows
        sidebar_width = 0     # no sidebar adjustment needed for tight layout
        
        # Calculate window dimensions for clean grid layout
        base_win_w = mon.width // cols
        base_win_h = mon.height // rows
        
        # Adjust for decorations and gaps
        win_w = base_win_w - horizontal_gap
        win_h = base_win_h - vertical_gap

        # tile them ------------------------------------------------------
        for i, win in enumerate(self.target_windows):
            r, c = divmod(i, cols)
            
            # Simple grid positioning with minimal gaps
            x = mon.x + c * base_win_w + (horizontal_gap // 2)
            y = mon.y + r * base_win_h + (vertical_gap // 2)
            try:
                win.resizeTo(win_w, win_h)
                win.moveTo(x, y)
                # Bring window to front and activate it
                win.activate()
                # Small delay to ensure proper activation
                time.sleep(0.05)
            except Exception as e:
                print(f"[!] Could not move/resize '{win.title}': {e}")

        self._update_status()
        messagebox.showinfo("Done", "Windows sorted!")

    # ────────────────────────── STATUS LABEL ──────────────────────────
    def _update_status(self):
        txt = (
            f"Monitors: {len(self.monitors)} | "
            f"Title choices: {len(self.app_titles)} | "
            f"Windows matched: {len(self.target_windows)}"
        )
        self.status_lbl.config(text=txt)


if __name__ == "__main__":
    root = tk.Tk()
    WindowTiler(root)
    root.mainloop()
