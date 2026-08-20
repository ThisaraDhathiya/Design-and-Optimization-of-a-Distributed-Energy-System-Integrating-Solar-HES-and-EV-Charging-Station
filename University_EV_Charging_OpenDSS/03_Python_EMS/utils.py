"""
utils.py
================================================================================
University of Ruhuna — Faculty of Engineering
Shared utilities — colours, paths, plot helpers, CSV reader

Used by all analysis scripts in 04_Analysis_Plots/
================================================================================
"""

import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator

# ── PROJECT PATHS ─────────────────────────────────────────────────────────────
_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.dirname(_THIS_DIR)
RESULTS_DIR = os.path.join(BASE_DIR, "05_Results")
PLOTS_DIR   = os.path.join(BASE_DIR, "06_Plots")
DSS_DIR     = os.path.join(BASE_DIR, "01_OpenDSS_Model")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR,   exist_ok=True)

# ── COLOUR PALETTE ────────────────────────────────────────────────────────────
# Consistent colours used across ALL plots
C = {
    "pv"         : "#F5A623",   # amber   — solar generation
    "battery"    : "#0D7377",   # teal    — battery
    "sc"         : "#185FA5",   # blue    — supercapacitor
    "grid_import": "#E24B4A",   # red     — grid import (cost)
    "grid_export": "#1D9E75",   # green   — grid export (benefit)
    "ev"         : "#534AB7",   # purple  — EV load
    "load"       : "#2C3E50",   # dark    — faculty load
    "peak_shave" : "#FF6B35",   # orange  — peak shaving active
    "evening"    : "#8E44AD",   # violet  — evening support window
    "voltage_ok" : "#27AE60",   # green   — voltage within limits
    "voltage_bad": "#E74C3C",   # red     — voltage violation
    "batt_charge": "#1ABC9C",   # mint    — charging state
    "batt_disch" : "#E67E22",   # amber   — discharging state
    "soc_batt"   : "#0D7377",   # teal    — battery SOC
    "soc_sc"     : "#185FA5",   # blue    — SC SOC
    "bg"         : "#F8FAFB",   # very light — background
    "grid_line"  : "#E0E0E0",   # light grey — grid lines
}

# ── PLOT STYLE SETUP ──────────────────────────────────────────────────────────
def setup_style():
    """Apply consistent matplotlib style for all project plots."""
    plt.rcParams.update({
        "figure.facecolor"    : C["bg"],
        "axes.facecolor"      : "white",
        "axes.grid"           : True,
        "grid.color"          : C["grid_line"],
        "grid.linewidth"      : 0.6,
        "axes.spines.top"     : False,
        "axes.spines.right"   : False,
        "axes.labelsize"      : 11,
        "axes.titlesize"      : 13,
        "axes.titleweight"    : "bold",
        "legend.fontsize"     : 9,
        "legend.framealpha"   : 0.9,
        "xtick.labelsize"     : 9,
        "ytick.labelsize"     : 9,
        "font.family"         : "DejaVu Sans",
        "lines.linewidth"     : 1.8,
        "figure.dpi"          : 120,
    })

# ── TIME AXIS ─────────────────────────────────────────────────────────────────
def make_time_axis(steps=96):
    """Return array of hour values for x-axis (0 to 24)."""
    return np.arange(steps) * 0.25  # 15-min steps → hours

def time_xticks(ax, every_n_hours=2):
    """Set x-axis ticks every N hours with HH:00 labels."""
    hours = np.arange(0, 25, every_n_hours)
    labels = [f"{int(h):02d}:00" for h in hours]
    ax.set_xticks(hours)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xlim(0, 24)
    ax.xaxis.set_minor_locator(MultipleLocator(0.5))  # 30-min minor ticks

# ── EVENING SHADING ───────────────────────────────────────────────────────────
def shade_evening(ax, alpha=0.10):
    """Add a shaded region for evening support window (17:30-22:30)."""
    ax.axvspan(17.5, 22.5, alpha=alpha, color=C["evening"], label="Evening support")

def shade_ev_cutoff(ax):
    """Add a vertical line at 16:00 (EV cutoff)."""
    ax.axvline(16.0, color=C["ev"], linewidth=1.2,
               linestyle="--", alpha=0.7, label="EV cutoff 16:00")

def shade_peak_shave_limit(ax, limit_kw=204.0):
    """Add a horizontal dashed line at peak shave limit."""
    ax.axhline(limit_kw, color=C["peak_shave"], linewidth=1.2,
               linestyle="--", alpha=0.8, label=f"Peak shave limit {limit_kw:.0f} kW")

# ── CSV READER ────────────────────────────────────────────────────────────────
def load_ems_results(scenario_name="clear_day_normal_load"):
    """
    Load EMS simulation results CSV into a dict of numpy arrays.

    Parameters
    ----------
    scenario_name : str  filename without .csv extension

    Returns
    -------
    dict  keys = column names, values = numpy arrays (96 elements)
    """
    path = os.path.join(RESULTS_DIR, f"EMS_{scenario_name}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Results not found: {path}\nRun simulation first.")

    data = {}
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                if k not in data:
                    data[k] = []
                try:
                    data[k].append(float(v))
                except (ValueError, TypeError):
                    data[k].append(v)

    # Convert numeric columns to numpy arrays
    numeric_keys = [
        "p_pv_kw", "p_load_kw", "p_ev_kw", "batt_kw", "soc_batt_pct",
        "sc_kw", "soc_sc_pct", "grid_kw", "export_kw", "peak_shave_kw", "step",
    ]
    for k in numeric_keys:
        if k in data:
            data[k] = np.array(data[k], dtype=float)

    return data

# ── STANDARD LEGEND PATCHES ───────────────────────────────────────────────────
def make_legend_patches():
    """Return standard legend patches for use across plots."""
    return [
        mpatches.Patch(color=C["pv"],          label="PV generation"),
        mpatches.Patch(color=C["battery"],      label="Battery"),
        mpatches.Patch(color=C["sc"],           label="Supercapacitor"),
        mpatches.Patch(color=C["grid_import"],  label="Grid import"),
        mpatches.Patch(color=C["grid_export"],  label="Grid export"),
        mpatches.Patch(color=C["ev"],           label="EV load"),
        mpatches.Patch(color=C["load"],         label="Faculty load"),
    ]

# ── SAVE PLOT ─────────────────────────────────────────────────────────────────
def save_plot(fig, filename, dpi=150):
    """Save figure to 06_Plots/ directory."""
    path = os.path.join(PLOTS_DIR, filename)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=C["bg"])
    print(f"  Plot saved → {path}")
    plt.close(fig)
    return path

# ── DAILY ENERGY SUMMARY ──────────────────────────────────────────────────────
def calc_daily_energy(data):
    """
    Calculate daily energy totals from EMS result dict.
    Returns dict with kWh values.
    """
    dt = 0.25  # 15-min step = 0.25 hours
    return {
        "pv_kwh"         : float(data["p_pv_kw"].sum()       * dt),
        "load_kwh"        : float(data["p_load_kw"].sum()     * dt),
        "ev_kwh"          : float(data["p_ev_kw"].sum()       * dt),
        "grid_import_kwh" : float(data["grid_kw"].sum()       * dt),
        "grid_export_kwh" : float(data["export_kw"].sum()     * dt),
        "batt_net_kwh"    : float(data["batt_kw"].sum()       * dt),
        "peak_shave_kwh"  : float(data["peak_shave_kw"].sum() * dt),
    }

def print_energy_summary(data, scenario_name=""):
    """Print a formatted daily energy summary."""
    e = calc_daily_energy(data)
    total_demand = e["load_kwh"] + e["ev_kwh"]
    self_suff = (1 - e["grid_import_kwh"] / max(total_demand, 1)) * 100
    print(f"\n  === DAILY ENERGY SUMMARY : {scenario_name} ===")
    print(f"  PV generation   : {e['pv_kwh']:>8.1f} kWh")
    print(f"  Faculty load    : {e['load_kwh']:>8.1f} kWh")
    print(f"  EV load         : {e['ev_kwh']:>8.1f} kWh")
    print(f"  Grid import     : {e['grid_import_kwh']:>8.1f} kWh")
    print(f"  Grid export     : {e['grid_export_kwh']:>8.1f} kWh")
    print(f"  Self-sufficiency: {self_suff:>7.1f} %")
    print(f"  Peak shave saved: {e['peak_shave_kwh']:>8.1f} kWh")
    return e

# ── ALERT READER ──────────────────────────────────────────────────────────────
def load_alerts(scenario_name="clear_day_normal_load"):
    """Load alert log for a scenario. Returns list of alert strings."""
    path = os.path.join(RESULTS_DIR, "EMS_alerts.txt")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

# ── BUS VOLTAGE CHECKER ───────────────────────────────────────────────────────
def check_voltage_violations(voltages_dict, v_min=0.94, v_max=1.06):
    """
    Check which buses have voltage violations.

    Parameters
    ----------
    voltages_dict : dict  {bus_name: voltage_pu}

    Returns
    -------
    list of (bus_name, voltage_pu, status)
    """
    violations = []
    for bus, v in voltages_dict.items():
        if v < v_min:
            violations.append((bus, v, "LOW"))
        elif v > v_max:
            violations.append((bus, v, "HIGH"))
    return violations


if __name__ == "__main__":
    # Quick test
    setup_style()
    t = make_time_axis()
    print(f"utils.py OK — time axis: {t[0]} to {t[-1]} h, {len(t)} steps")
    print(f"Results dir : {RESULTS_DIR}")
    print(f"Plots dir   : {PLOTS_DIR}")
