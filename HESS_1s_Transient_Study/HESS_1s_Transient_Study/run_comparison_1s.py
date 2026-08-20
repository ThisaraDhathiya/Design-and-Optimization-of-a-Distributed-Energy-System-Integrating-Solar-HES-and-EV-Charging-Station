"""
run_comparison_1s.py
================================================================================
Runs the full 86,400-step simulation TWICE — once with SC_DISPATCH_MODE=
"threshold" (original rule-based logic) and once with "filter" (recommended
low-pass + SOC-recovery logic) — using identical load/PV/EV data, and produces
a side-by-side comparison table + plot.

This is the "rule-based vs. filter-based supercapacitor dispatch" comparison
suggested for your thesis — it directly demonstrates why the filter-based
method is the better-justified choice, using your own data.

Run:
    python run_comparison_1s.py
================================================================================
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config_1s as cfg
from data_loader_1s import load_all_data
from ems_controller_1s import EMSController1s

RESULTS_DIR = cfg.RESULTS_DIR
PLOTS_DIR = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)


def run_mode(mode, data):
    print(f"\n{'='*70}\n  RUNNING MODE: {mode.upper()}\n{'='*70}")
    ems = EMSController1s(data["loads"], data["ev"], data["pv"], dispatch_mode=mode)
    ems.run_all()
    ems.print_summary()
    return ems


def summarize(ems, mode):
    r = ems.res
    dt = cfg.DT_HOURS
    load = r["p_load_kw"].sum() * dt
    ev = r["p_ev_kw"].sum() * dt
    grid = r["grid_kw"].sum() * dt
    total = max(load + ev, 1)
    sc_active_s = int(np.sum(np.abs(r["sc_kw"]) > 0.01))
    sc_energy_thru = np.sum(np.abs(r["sc_kw"])) * dt  # kWh throughput (charge+discharge)
    return {
        "mode": mode,
        "grid_import_kwh": grid,
        "self_sufficiency_pct": (1 - grid / total) * 100,
        "sc_active_seconds": sc_active_s,
        "sc_active_hours": sc_active_s / 3600,
        "sc_energy_throughput_kwh": sc_energy_thru,
        "sc_soc_min_pct": r["soc_sc_pct"].min(),
        "sc_soc_max_pct": r["soc_sc_pct"].max(),
        "sc_soc_final_pct": r["soc_sc_pct"][-1],
        "voltage_violation_s": ems.voltage_violation_steps,
    }


def main():
    print("Loading data (shared across both runs)...")
    data = load_all_data()

    ems_threshold = run_mode("threshold", data)
    ems_filter = run_mode("filter", data)

    # ── Summary comparison table ────────────────────────────────────────────
    summary_rows = [summarize(ems_threshold, "threshold"), summarize(ems_filter, "filter")]
    summary_df = pd.DataFrame(summary_rows).set_index("mode")
    summary_path = os.path.join(RESULTS_DIR, "SC_mode_comparison.csv")
    summary_df.to_csv(summary_path)

    print("\n" + "=" * 70)
    print("  COMPARISON: THRESHOLD vs FILTER-BASED SC DISPATCH")
    print("=" * 70)
    print(summary_df.T.to_string())
    print(f"\nSaved -> {summary_path}")

    # ── Comparison plot: SC power + SOC, both modes, full day ─────────────
    t_hours = np.arange(cfg.SIM_STEPS) / 3600.0
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)

    axes[0].plot(t_hours, ems_threshold.res["sc_kw"], linewidth=0.5, label="Threshold mode")
    axes[0].plot(t_hours, ems_filter.res["sc_kw"], linewidth=0.5, label="Filter mode", alpha=0.8)
    axes[0].set_ylabel("SC power (kW)")
    axes[0].legend()
    axes[0].set_title("Supercapacitor Power — Threshold vs Filter-Based Dispatch")

    axes[1].plot(t_hours, ems_threshold.res["soc_sc_pct"], linewidth=0.8, label="Threshold mode")
    axes[1].plot(t_hours, ems_filter.res["soc_sc_pct"], linewidth=0.8, label="Filter mode")
    axes[1].axhspan(cfg.SC_TARGET_SOC_LOW, cfg.SC_TARGET_SOC_HIGH, color="green", alpha=0.08,
                     label="Filter-mode target band")
    axes[1].set_ylabel("SC SOC (%)")
    axes[1].set_xlabel("Time (h)")
    axes[1].legend()

    fig.tight_layout()
    plot_path = os.path.join(PLOTS_DIR, "Plot5_SC_Mode_Comparison.png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"Plot saved -> {plot_path}")


if __name__ == "__main__":
    main()
