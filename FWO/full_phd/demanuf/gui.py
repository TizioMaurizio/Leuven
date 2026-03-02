"""Tkinter-based graphical interface for the demanufacturing simulation.

Launch with: ``python -m demanuf.gui``

Features:
  * Canvas shows stations and product tokens moving through the cell
  * Control panel: Start / Pause / Step / Reset
  * Event log text area (live stream)
  * Load & replay a past run from events.jsonl
"""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext
from typing import Any, Dict, List, Optional

from .config import STATION_NAMES, UncertaintyRegime
from .des.simulation import SimulationRunner
from .des.model import ProductPhase, StationStatus

# ── Layout constants ──────────────────────────────────────────────────
CANVAS_W = 800
CANVAS_H = 400
STATION_W = 100
STATION_H = 60
PAD = 30
TOKEN_R = 10

STATION_COLORS = {
    "intake": "#88ccee",
    "inspection": "#44aa99",
    "robot_disassembly": "#117733",
    "manual_disassembly": "#999933",
    "hazard_handling": "#cc6677",
    "output": "#882255",
}

PHASE_STATION_MAP = {
    ProductPhase.INSPECTION: "inspection",
    ProductPhase.ROBOT_DISASSEMBLY: "robot_disassembly",
    ProductPhase.MANUAL_DISASSEMBLY: "manual_disassembly",
    ProductPhase.HAZARD_HANDLING: "hazard_handling",
    ProductPhase.COMPLETE: "output",
}


class DemanufGUI:
    """Main application window."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        master.title("Demanuf — Holonic Demanufacturing Simulator")
        master.geometry("1050x700")
        master.resizable(True, True)

        self.runner: Optional[SimulationRunner] = None
        self.running = False
        self.speed_ms = 120  # ms between auto-steps
        self._station_rects: Dict[str, int] = {}
        self._station_labels: Dict[str, int] = {}
        self._station_centres: Dict[str, tuple] = {}
        self._tokens: Dict[int, int] = {}  # product_uid → canvas item id

        self._build_ui()
        self._init_runner()
        self._draw_stations()

    # ── UI construction ───────────────────────────────────────────
    def _build_ui(self) -> None:
        # Top frame — controls
        ctrl = tk.Frame(self.master)
        ctrl.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.btn_start = tk.Button(ctrl, text="▶ Start", width=8, command=self._on_start)
        self.btn_start.pack(side=tk.LEFT, padx=2)

        self.btn_pause = tk.Button(ctrl, text="⏸ Pause", width=8, command=self._on_pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=2)

        self.btn_step = tk.Button(ctrl, text="⏭ Step", width=8, command=self._on_step)
        self.btn_step.pack(side=tk.LEFT, padx=2)

        self.btn_reset = tk.Button(ctrl, text="⟲ Reset", width=8, command=self._on_reset)
        self.btn_reset.pack(side=tk.LEFT, padx=2)

        tk.Label(ctrl, text="  Seed:").pack(side=tk.LEFT)
        self.seed_var = tk.IntVar(value=1)
        tk.Spinbox(ctrl, from_=0, to=9999, textvariable=self.seed_var, width=6).pack(side=tk.LEFT)

        tk.Label(ctrl, text="  Speed:").pack(side=tk.LEFT)
        self.speed_var = tk.IntVar(value=self.speed_ms)
        spd = tk.Scale(ctrl, from_=10, to=500, orient=tk.HORIZONTAL,
                       variable=self.speed_var, length=120, showvalue=False)
        spd.pack(side=tk.LEFT)

        self.btn_load = tk.Button(ctrl, text="📂 Load Run", width=10, command=self._on_load)
        self.btn_load.pack(side=tk.RIGHT, padx=2)

        # Canvas — station visualisation
        self.canvas = tk.Canvas(self.master, width=CANVAS_W, height=CANVAS_H, bg="#f0f0f0")
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=2)

        # Info bar
        info = tk.Frame(self.master)
        info.pack(side=tk.TOP, fill=tk.X, padx=5)
        self.lbl_time = tk.Label(info, text="t = 0.000", font=("Consolas", 10))
        self.lbl_time.pack(side=tk.LEFT)
        self.lbl_stats = tk.Label(info, text="completed=0  escalated=0  events=0", font=("Consolas", 10))
        self.lbl_stats.pack(side=tk.RIGHT)

        # Event log
        self.log_text = scrolledtext.ScrolledText(self.master, height=12, font=("Consolas", 9))
        self.log_text.pack(side=tk.BOTTOM, fill=tk.BOTH, padx=5, pady=5)

    # ── Station drawing ──────────────────────────────────────────
    def _draw_stations(self) -> None:
        self.canvas.delete("all")
        self._station_rects.clear()
        self._station_labels.clear()
        self._station_centres.clear()
        self._tokens.clear()

        n = len(STATION_NAMES)
        total_w = n * STATION_W + (n - 1) * PAD
        x_start = (CANVAS_W - total_w) / 2

        for i, name in enumerate(STATION_NAMES):
            x = x_start + i * (STATION_W + PAD)
            y = CANVAS_H / 2 - STATION_H / 2
            color = STATION_COLORS.get(name, "#aaaaaa")
            rid = self.canvas.create_rectangle(x, y, x + STATION_W, y + STATION_H,
                                               fill=color, outline="black", width=2)
            tid = self.canvas.create_text(x + STATION_W / 2, y + STATION_H / 2,
                                          text=name.replace("_", "\n"),
                                          font=("Arial", 8, "bold"), justify=tk.CENTER)
            self._station_rects[name] = rid
            self._station_labels[name] = tid
            self._station_centres[name] = (x + STATION_W / 2, y + STATION_H / 2)

        # Draw arrows
        for i in range(n - 1):
            x1 = x_start + i * (STATION_W + PAD) + STATION_W
            x2 = x_start + (i + 1) * (STATION_W + PAD)
            y = CANVAS_H / 2
            self.canvas.create_line(x1, y, x2, y, arrow=tk.LAST, width=2, fill="#666666")

    # ── Simulation initialisation ─────────────────────────────────
    def _init_runner(self) -> None:
        self.runner = SimulationRunner(
            seed=self.seed_var.get(),
            max_steps=5000,
            max_products=60,
            callback=self._on_sim_event,
        )
        self.runner.reset()

    def _on_sim_event(self, entry: Dict[str, Any]) -> None:
        """Called for every event emitted by the simulation."""
        pass  # logging handled in _refresh

    # ── Controls ──────────────────────────────────────────────────
    def _on_start(self) -> None:
        if not self.running:
            self.running = True
            self.btn_start.config(state=tk.DISABLED)
            self.btn_pause.config(state=tk.NORMAL)
            self._auto_step()

    def _on_pause(self) -> None:
        self.running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)

    def _on_step(self) -> None:
        if self.runner:
            self.runner.step()
            self._refresh()

    def _on_reset(self) -> None:
        self.running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)
        self._init_runner()
        self._draw_stations()
        self.log_text.delete("1.0", tk.END)
        self._refresh()

    def _auto_step(self) -> None:
        if not self.running or self.runner is None:
            return
        evt = self.runner.step()
        if evt is None:
            self.running = False
            self.btn_start.config(state=tk.DISABLED)
            self.btn_pause.config(state=tk.DISABLED)
            self._append_log("--- Simulation ended ---\n")
            self._refresh()
            return
        self._refresh()
        self.speed_ms = self.speed_var.get()
        self.master.after(self.speed_ms, self._auto_step)

    # ── Refresh display ──────────────────────────────────────────
    def _refresh(self) -> None:
        if self.runner is None:
            return

        # Update time
        self.lbl_time.config(text=f"t = {self.runner.engine.now:.3f}")

        # Stats
        m = self.runner.metrics
        self.lbl_stats.config(
            text=f"completed={m.products_completed}  escalated={m.escalations}  events={len(m.event_log)}"
        )

        # Update tokens on canvas
        self._update_tokens()

        # Append new log entries
        log = self.runner.metrics.event_log
        displayed = int(self.log_text.index("end-1c").split(".")[0]) - 1
        for entry in log[max(0, displayed):]:
            self._append_log(json.dumps(entry) + "\n")

    def _update_tokens(self) -> None:
        """Reposition product tokens based on current product phases."""
        if self.runner is None:
            return

        # Remove old tokens
        for tid in self._tokens.values():
            self.canvas.delete(tid)
        self._tokens.clear()

        # Count products per station for stacking
        station_counts: Dict[str, int] = {s: 0 for s in STATION_NAMES}

        for uid, product in self.runner.state.products.items():
            station_name = PHASE_STATION_MAP.get(product.phase)
            if station_name is None:
                if product.phase == ProductPhase.WAITING:
                    station_name = "intake"
                elif product.phase == ProductPhase.ESCALATED:
                    continue
                else:
                    continue

            if station_name not in self._station_centres:
                continue

            cx, cy = self._station_centres[station_name]
            offset = station_counts[station_name] * (TOKEN_R * 2 + 2)
            station_counts[station_name] += 1

            # Stack tokens below station
            tx = cx - 20 + (offset % 60)
            ty = cy + STATION_H / 2 + 10 + (offset // 60) * (TOKEN_R * 2 + 2)

            color = "#ff4444" if product.latent.battery_risk else "#4488ff"
            if product.escalated:
                color = "#ffaa00"
            tid = self.canvas.create_oval(
                tx - TOKEN_R, ty - TOKEN_R, tx + TOKEN_R, ty + TOKEN_R,
                fill=color, outline="black",
            )
            self._tokens[uid] = tid

        # Update station outlines based on status
        for name, station in self.runner.state.stations.items():
            rid = self._station_rects.get(name)
            if rid is None:
                continue
            if station.status == StationStatus.FAILED:
                self.canvas.itemconfig(rid, outline="red", width=3)
            elif station.status == StationStatus.BUSY:
                self.canvas.itemconfig(rid, outline="#00aa00", width=3)
            else:
                self.canvas.itemconfig(rid, outline="black", width=2)

    def _append_log(self, text: str) -> None:
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    # ── Load & replay ─────────────────────────────────────────────
    def _on_load(self) -> None:
        filepath = filedialog.askopenfilename(
            title="Load events.jsonl",
            filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")],
        )
        if not filepath:
            return
        self._replay_file(filepath)

    def _replay_file(self, filepath: str) -> None:
        """Load and display events from a .jsonl file."""
        self.running = False
        self.log_text.delete("1.0", tk.END)
        self._draw_stations()

        with open(filepath) as f:
            for line in f:
                entry = json.loads(line.strip())
                self._append_log(json.dumps(entry) + "\n")

        self._append_log(f"\n--- Replayed {filepath} ---\n")


def main() -> None:
    """Entry point for ``python -m demanuf.gui``."""
    root = tk.Tk()
    app = DemanufGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
