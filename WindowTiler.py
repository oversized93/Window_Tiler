import tkinter as tk
from tkinter import ttk, messagebox
import pygetwindow as gw
from screeninfo import get_monitors
import time
import sys
import os
import math

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
    case‑insensitively so slight changes (FPS counter, etc.) don't break it.
    Now supports custom layers with user-defined grid layouts (up to 5x5).
    """

    # ──────────────────────────── GUI SET‑UP ────────────────────────────
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Window Tiler")
        self.root.geometry("800x900")  # Larger window for layer UI
        self.root.minsize(600, 500)  # Minimum window size

        # Main scrollable frame
        self.main_canvas = tk.Canvas(root)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.canvas_window = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Configure canvas to expand scrollable frame to canvas width
        def _configure_canvas(event):
            canvas_width = event.width
            self.main_canvas.itemconfig(self.canvas_window, width=canvas_width)
        
        self.main_canvas.bind('<Configure>', _configure_canvas)

        # Original UI elements
        self.status_lbl = tk.Label(self.scrollable_frame, text="Press Detect to begin.", font=("Arial", 12))
        self.status_lbl.pack(pady=(15, 10))

        btn_bar = tk.Frame(self.scrollable_frame)
        btn_bar.pack(fill="x", padx=20, pady=(5, 10))
        
        # Center the buttons
        btn_center = tk.Frame(btn_bar)
        btn_center.pack()
        
        tk.Button(btn_center, text="Detect", width=20, height=2,
                  command=self.detect, font=("Arial", 11, "bold")).pack(side="left", padx=15)
        tk.Button(btn_center, text="Sort", width=20, height=2,
                  command=self.sort, font=("Arial", 11, "bold")).pack(side="left", padx=15)

        # Main controls frame - horizontal layout
        main_controls = tk.Frame(self.scrollable_frame)
        main_controls.pack(fill="x", padx=20, pady=10)

        # Left side - Monitor selection
        monitor_frame = tk.Frame(main_controls)
        monitor_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(monitor_frame, text="Monitor:", font=("Arial", 11, "bold")).pack(anchor="w")
        
        self.monitor_var = tk.StringVar()
        self.monitor_cbx = ttk.Combobox(
            monitor_frame, textvariable=self.monitor_var, state="readonly", 
            font=("Arial", 10), height=8
        )
        self.monitor_cbx.pack(fill="x", pady=(2, 0))

        # Right side - App selection
        app_frame = tk.Frame(main_controls)
        app_frame.pack(side="left", fill="both", expand=True, padx=(10, 0))
        tk.Label(app_frame, text="Application:", font=("Arial", 11, "bold")).pack(anchor="w")
        
        self.app_var = tk.StringVar()
        self.app_cbx = ttk.Combobox(
            app_frame, textvariable=self.app_var, state="readonly",
            font=("Arial", 10), height=8
        )
        self.app_cbx.pack(fill="x", pady=(2, 0))

        # Add Layer button - centered and wider
        add_layer_frame = tk.Frame(self.scrollable_frame)
        add_layer_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        self.add_layer_btn = tk.Button(
            add_layer_frame, text="+ Add Layer", 
            command=self.add_layer, bg="#4CAF50", fg="white", 
            font=("Arial", 12, "bold"), height=2, width=30
        )
        self.add_layer_btn.pack()

        # Separator line
        separator = ttk.Separator(self.scrollable_frame, orient='horizontal')
        separator.pack(fill='x', pady=(5, 10))

        # Layers container
        self.layers_frame = tk.Frame(self.scrollable_frame)
        self.layers_frame.pack(fill="both", expand=True, padx=15, pady=10)

        # Pack canvas and scrollbar
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── internal state ──
        self.monitors: list = []
        self.app_titles: list[str] = []
        self.target_windows: list = []
        self.layers: list = []  # List of layer configurations
        self.layer_counter = 0  # For unique layer IDs

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

        # Update all layer dropdowns with new apps and monitors
        for layer in self.layers:
            self._update_layer_app_dropdowns(layer)
            self._update_layer_monitor_dropdown(layer)

        self._update_status()

    # ─────────────────────── LAYER MANAGEMENT ─────────────────────────
    def add_layer(self):
        """Add a new layer configuration"""
        self.layer_counter += 1
        layer_id = f"layer_{self.layer_counter}"
        
        layer_config = {
            'id': layer_id,
            'name': f"Layer {self.layer_counter}",
            'app_count': 1,
            'rows': 1,
            'cols': 1,
            'frame': None,
            'preview_frame': None,
            'tile_dropdowns': {},
            'monitor_var': None,
            'monitor_dropdown': None,
            'row_var': None,
            'col_var': None,
            'row_spinner': None,
            'col_spinner': None
        }
        
        self.layers.append(layer_config)
        self._create_layer_ui(layer_config)
        
        # Reorder layers and scroll to show the new layer
        self._reorder_layers()
        self.root.after(100, lambda: self.main_canvas.yview_moveto(1.0))

    def _create_layer_ui(self, layer_config):
        """Create UI for a single layer"""
        # Main layer frame
        layer_frame = tk.LabelFrame(
            self.layers_frame, 
            text=layer_config['name'], 
            padx=15, pady=15,
            relief="ridge",
            borderwidth=2,
            font=("Arial", 11, "bold")
        )
        layer_frame.pack(fill="both", expand=True, pady=(0, 15))
        layer_config['frame'] = layer_frame

        # Layer controls frame
        controls_frame = tk.Frame(layer_frame)
        controls_frame.pack(fill="x", pady=(0, 15))

        # Left side controls
        left_controls = tk.Frame(controls_frame)
        left_controls.pack(side="left", fill="both", expand=True)

        # Grid size selectors
        tk.Label(left_controls, text="Rows:", font=("Arial", 10, "bold")).pack(side="left")
        row_var = tk.StringVar(value=str(layer_config['rows']))
        row_spinner = tk.Spinbox(
            left_controls, from_=1, to=5, width=6, 
            textvariable=row_var,
            command=lambda: self._update_grid_from_spinners(layer_config),
            font=("Arial", 10)
        )
        row_spinner.pack(side="left", padx=(8, 15))

        tk.Label(left_controls, text="Cols:", font=("Arial", 10, "bold")).pack(side="left")
        col_var = tk.StringVar(value=str(layer_config['cols']))
        col_spinner = tk.Spinbox(
            left_controls, from_=1, to=5, width=6, 
            textvariable=col_var,
            command=lambda: self._update_grid_from_spinners(layer_config),
            font=("Arial", 10)
        )
        col_spinner.pack(side="left", padx=(8, 15))

        # Store spinner references
        layer_config['row_var'] = row_var
        layer_config['col_var'] = col_var
        layer_config['row_spinner'] = row_spinner
        layer_config['col_spinner'] = col_spinner

        # Monitor selector (expandable)
        monitor_section = tk.Frame(left_controls)
        monitor_section.pack(side="left", fill="x", expand=True, padx=(0, 15))
        
        tk.Label(monitor_section, text="Monitor:", font=("Arial", 10, "bold")).pack(side="left")
        monitor_var = tk.StringVar()
        monitor_dropdown = ttk.Combobox(
            monitor_section, textvariable=monitor_var, 
            state="readonly", font=("Arial", 9)
        )
        monitor_dropdown.pack(side="left", fill="x", expand=True, padx=(8, 0))
        
        # Store monitor references
        layer_config['monitor_var'] = monitor_var
        layer_config['monitor_dropdown'] = monitor_dropdown
        
        # Set monitor options if available
        if self.monitors:
            monitor_values = [
                f"Monitor {i+1}: {m.width}×{m.height} @({m.x},{m.y})"
                for i, m in enumerate(self.monitors)
            ]
            monitor_dropdown['values'] = monitor_values
            monitor_dropdown.current(0)  # Default to first monitor

        # Sort and Remove buttons
        sort_btn = tk.Button(
            controls_frame, text="Sort Layer", 
            command=lambda: self._apply_layer(layer_config),
            bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
            width=12, height=2
        )
        sort_btn.pack(side="right", padx=(10, 0))

        remove_btn = tk.Button(
            controls_frame, text="Remove", 
            command=lambda: self._remove_layer(layer_config),
            bg="#f44336", fg="white", font=("Arial", 10, "bold"),
            width=10, height=2
        )
        remove_btn.pack(side="right", padx=(0, 10))

        # Preview frame
        preview_frame = tk.Frame(layer_frame, relief="sunken", borderwidth=2, bg="#f8f9fa")
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)
        layer_config['preview_frame'] = preview_frame

        # Initial preview
        self._update_layer_preview(layer_config)

    def _update_grid_from_spinners(self, layer_config):
        """Update grid dimensions and app count from spinner values"""
        try:
            rows = int(layer_config['row_var'].get())
            cols = int(layer_config['col_var'].get())
            layer_config['rows'] = rows
            layer_config['cols'] = cols
            layer_config['app_count'] = rows * cols
            self._update_layer_preview(layer_config)
        except ValueError:
            pass  # Ignore invalid values

    def _update_layer_preview(self, layer_config):
        """Update the visual preview of the layer layout"""
        
        # Clear existing preview
        for widget in layer_config['preview_frame'].winfo_children():
            widget.destroy()
        layer_config['tile_dropdowns'] = {}

        # Reorder layers after app count change
        self._reorder_layers()

        # Use custom grid dimensions
        rows = layer_config['rows']
        cols = layer_config['cols']
        app_count = layer_config['app_count']

        # Create grid preview
        preview_label = tk.Label(
            layer_config['preview_frame'], 
            text=f"Layout Preview ({cols}x{rows} grid - {app_count} tiles):",
            font=("Arial", 11, "bold"), bg="#f8f9fa"
        )
        preview_label.pack(pady=(10, 15))

        grid_frame = tk.Frame(layer_config['preview_frame'], bg="#f8f9fa")
        grid_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Create tile dropdowns
        for i in range(app_count):
            row = i // cols
            col = i % cols
            
            # Create frame for each tile
            tile_frame = tk.Frame(grid_frame, relief="ridge", borderwidth=2, padx=8, pady=8, bg="white")
            tile_frame.grid(row=row, column=col, padx=1, pady=4, sticky="nsew")
            
            # Configure tile frame to expand
            tile_frame.columnconfigure(0, weight=1)
            tile_frame.rowconfigure(1, weight=1)
            
            # Tile label
            tile_label = tk.Label(tile_frame, text=f"Tile {i+1}:", font=("Arial", 10, "bold"), bg="white")
            tile_label.pack(pady=(0, 5))
            
            # App dropdown
            app_var = tk.StringVar()
            app_dropdown = ttk.Combobox(
                tile_frame, 
                textvariable=app_var, 
                state="readonly", 
                font=("Arial", 9),
                values=["Select application..."] + self.app_titles
            )
            app_dropdown.pack(pady=(0, 5), fill="x", expand=True)
            app_dropdown.current(0)  # Default to "Select application..."
            
            # Store dropdown reference
            layer_config['tile_dropdowns'][i] = {
                'var': app_var,
                'dropdown': app_dropdown
            }

        # Configure grid weights for responsive layout
        for i in range(cols):
            grid_frame.columnconfigure(i, weight=1, minsize=200)
        for i in range(rows):
            grid_frame.rowconfigure(i, weight=1, minsize=100)



    def _update_layer_app_dropdowns(self, layer_config):
        """Update dropdown values when detect is run"""
        if 'tile_dropdowns' in layer_config:
            for dropdown_info in layer_config['tile_dropdowns'].values():
                current_value = dropdown_info['var'].get()
                dropdown_info['dropdown']['values'] = ["Select application..."] + self.app_titles
                # Preserve selection if it still exists
                if current_value in self.app_titles:
                    dropdown_info['dropdown'].set(current_value)
                else:
                    dropdown_info['dropdown'].current(0)

    def _update_layer_monitor_dropdown(self, layer_config):
        """Update monitor dropdown values when detect is run"""
        if layer_config['monitor_dropdown'] and self.monitors:
            current_selection = layer_config['monitor_dropdown'].current()
            monitor_values = [
                f"Monitor {i+1}: {m.width}×{m.height} @({m.x},{m.y})"
                for i, m in enumerate(self.monitors)
            ]
            layer_config['monitor_dropdown']['values'] = monitor_values
            # Preserve selection if still valid, otherwise default to first monitor
            if current_selection != -1 and current_selection < len(monitor_values):
                layer_config['monitor_dropdown'].current(current_selection)
            else:
                layer_config['monitor_dropdown'].current(0)

    def _apply_layer(self, layer_config):
        """Apply the layer configuration to tile windows"""
        if not self.monitors:
            messagebox.showerror("Error", "Run 'Detect' first.")
            return

        # Get monitor selection from layer config
        if not layer_config['monitor_dropdown']:
            messagebox.showerror("Error", "Layer monitor dropdown not initialized.")
            return
            
        mon_idx = layer_config['monitor_dropdown'].current()
        if mon_idx == -1:
            messagebox.showerror("Error", "Please select a monitor for this layer.")
            return

        # Check if any applications are selected
        selected_apps = {}
        if 'tile_dropdowns' in layer_config:
            for tile_index, dropdown_info in layer_config['tile_dropdowns'].items():
                app_selection = dropdown_info['var'].get()
                if app_selection and app_selection != "Select application...":
                    selected_apps[tile_index] = app_selection

        if not selected_apps:
            messagebox.showwarning("No Apps", "Please select applications for the tiles.")
            return

        mon = self.monitors[mon_idx]
        
        # Use custom grid dimensions
        rows = layer_config['rows']
        cols = layer_config['cols']
        app_count = layer_config['app_count']

        # Find and position windows
        positioned_windows = []
        for tile_index, app_title in selected_apps.items():
            windows = []
            for w in gw.getAllWindows():
                if w.title and app_title.lower() in w.title.lower():
                    if w.isMinimized:
                        try:
                            w.restore()
                        except Exception:
                            pass
                    windows.append(w)
            
            if windows:
                positioned_windows.append((tile_index, windows[0]))  # Take first matching window

        if not positioned_windows:
            messagebox.showinfo("No Windows", "No matching windows found for selected applications.")
            return

        # Calculate window dimensions
        title_bar_height = 30
        border_width = 8
        horizontal_gap = 1
        vertical_gap = 1
        
        base_win_w = mon.width // cols
        base_win_h = mon.height // rows
        
        win_w = base_win_w - horizontal_gap
        win_h = base_win_h - vertical_gap

        # Position windows
        for tile_index, window in positioned_windows:
            row = tile_index // cols
            col = tile_index % cols
            
            x = mon.x + col * base_win_w + (horizontal_gap // 2)
            y = mon.y + row * base_win_h + (vertical_gap // 2)
            
            try:
                window.resizeTo(win_w, win_h)
                window.moveTo(x, y)
                window.activate()
                time.sleep(0.05)
            except Exception as e:
                print(f"[!] Could not move/resize '{window.title}': {e}")

        messagebox.showinfo("Layer Sorted", f"Layer '{layer_config['name']}' sorted successfully!")

    def _remove_layer(self, layer_config):
        """Remove a layer configuration"""
        if messagebox.askyesno("Remove Layer", f"Remove '{layer_config['name']}'?"):
            layer_config['frame'].destroy()
            self.layers.remove(layer_config)
            # Reorder remaining layers
            self._reorder_layers()

    def _reorder_layers(self):
        """Reorder layers by application count (descending) and update UI"""
        # Sort layers by app count (descending), then by creation order
        self.layers.sort(key=lambda layer: (-layer['app_count'], layer['name']))
        
        # Rebuild the UI in the new order
        for layer in self.layers:
            # Temporarily remove from parent
            layer['frame'].pack_forget()
        
        # Re-pack in sorted order
        for layer in self.layers:
            layer['frame'].pack(fill="x", pady=(0, 10))

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
            f"Windows matched: {len(self.target_windows)} | "
            f"Layers: {len(self.layers)}"
        )
        self.status_lbl.config(text=txt)


if __name__ == "__main__":
    root = tk.Tk()
    WindowTiler(root)
    root.mainloop()
