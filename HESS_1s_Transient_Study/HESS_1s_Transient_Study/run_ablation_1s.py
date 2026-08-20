"""
run_ablation_1s.py
================================================================================
THE "IS THE SUPERCAPACITOR ACTUALLY NEEDED?" TEST.

Runs the full 86,400-step simulation TWICE on identical real data:
  1. "filter"  — supercapacitor working normally (the adopted method)
  2. "none"    — supercapacitor completely turned off (SC_kw forced to 0 every
                  second — battery and grid must cover everything alone)

Then compares what actually changes: grid import, self-sufficiency, how hard
the battery has to work (peak power, fastest ramp rate), voltage violations,
and — most directly — what happens at the exact moment of the worst real
transient (the 16.53 kW EV-switching event) in both scenarios.

This is the direct evidence for "do we need the SC or not", instead of only
comparing two different WAYS of using it (that's run_comparison_1s.py).

Run:
    python run_ablation_1s.py
================================================================================
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config_1s as cfg
from data_loader_1s import load_all_data
from ems_controller_1s import EMSController1s
from sc_sizing_analysis import find_events

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
    export = r["export_kw"].sum() * dt
    total = max(load + ev, 1)
    batt_ramp = np.max(np.abs(np.diff(r["batt_kw"])))
    sc_throughput = np.sum(np.abs(r["sc_kw"])) * dt
    return {
        "mode": mode,
        "grid_import_kwh": grid,
        "grid_export_kwh": export,
        "self_sufficiency_pct": (1 - grid / total) * 100,
        "batt_peak_kw": np.max(np.abs(r["batt_kw"])),
        "batt_max_ramp_kw_per_s": batt_ramp,
        "sc_energy_throughput_kwh": sc_throughput,
        "voltage_violation_s": ems.voltage_violation_steps,
        "ev_alert_s": int(np.sum(r["ev_alert"])),
    }


def main():
    print("Loading data (shared across both runs)...")
    data = load_all_data()

    ems_with_sc = run_mode("filter", data)
    ems_without_sc = run_mode("none", data)

    # ── Summary comparison table ────────────────────────────────────────────
    summary_rows = [summarize(ems_with_sc, "WITH supercapacitor"),
                     summarize(ems_without_sc, "WITHOUT supercapacitor")]
    summary_df = pd.DataFrame(summary_rows).set_index("mode")
    summary_path = os.path.join(RESULTS_DIR, "SC_ablation_comparison.csv")
    summary_df.to_csv(summary_path)

    print("\n" + "=" * 70)
    print("  ABLATION TEST: WITH supercapacitor vs WITHOUT supercapacitor")
    print("=" * 70)
    print(summary_df.T.to_string())
    print(f"\nSaved -> {summary_path}")

    # ── What happens at the worst real transient, in both scenarios? ───────
    worst_step = 57600  # 16:00:00 — the real 16.53 kW EV-switching event
    lo, hi = worst_step - 15, worst_step + 30
    print("\n" + "=" * 70)
    print(f"  AT THE WORST REAL EVENT (step {worst_step}, 16:00:00):")
    print("=" * 70)
    for ems, label in [(ems_with_sc, "WITH SC"), (ems_without_sc, "WITHOUT SC")]:
        r = ems.res
        batt_before = r["batt_kw"][worst_step - 1]
        batt_at = r["batt_kw"][worst_step]
        batt_jump = abs(batt_at - batt_before)
        grid_at = r["grid_kw"][worst_step]
        export_at = r["export_kw"][worst_step]
        sc_at = r["sc_kw"][worst_step]
        print(f"  {label:12s}: batt_kw {batt_before:7.2f}->{batt_at:7.2f} kW "
              f"(delta={batt_jump:.2f})   sc_kw={sc_at:7.2f} kW   "
              f"grid_kw={grid_at:7.2f} kW   export_kw={export_at:7.2f} kW")

    # ── Inspect ALL qualifying events (>10 kW), not just the single worst ──
    r_with, r_without = ems_with_sc.res, ems_without_sc.res
    p_net_arr = r_with["p_load_kw"] + r_with["p_ev_kw"] - r_with["p_pv_kw"]
    delta_arr = np.abs(np.diff(p_net_arr))
    events = find_events(p_net_arr, delta_arr, threshold_kw=10)
    print("\n" + "=" * 70)
    print(f"  ALL {len(events)} QUALIFYING EVENTS (>10 kW) — WITH vs WITHOUT SC")
    print("=" * 70)
    for _, ev in events.iterrows():
        s = int(ev["start_step"])
        hh = s // 3600; mm = (s % 3600) // 60; ss = s % 60
        w_lo, w_hi = max(0, s - 2), min(len(p_net_arr), s + 5)
        grid_diff = np.max(np.abs(r_with["grid_kw"][w_lo:w_hi] - r_without["grid_kw"][w_lo:w_hi]))
        export_diff = np.max(np.abs(r_with["export_kw"][w_lo:w_hi] - r_without["export_kw"][w_lo:w_hi]))
        print(f"  {hh:02d}:{mm:02d}:{ss:02d}  peak_delta={ev['peak_delta_kw']:6.2f}kW   "
              f"max|grid_kw diff|={grid_diff:6.2f}   max|export_kw diff|={export_diff:6.2f}")

    # ── Plot: grid + export power around the worst event, both scenarios ───
    window_with = ems_with_sc.res
    window_without = ems_without_sc.res
    rel = np.arange(lo, hi) - worst_step

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(rel, window_with["batt_kw"][lo:hi], label="Battery power (WITH SC)", linewidth=1.5)
    axes[0].plot(rel, window_without["batt_kw"][lo:hi], label="Battery power (WITHOUT SC)", linewidth=1.5)
    axes[0].set_ylabel("Battery power (kW)")
    axes[0].legend()
    axes[0].set_title("Does the Battery Work Harder Without the Supercapacitor?")

    axes[1].plot(rel, window_with["grid_kw"][lo:hi] - window_with["export_kw"][lo:hi],
                 label="Net grid power (WITH SC)", linewidth=1.5)
    axes[1].plot(rel, window_without["grid_kw"][lo:hi] - window_without["export_kw"][lo:hi],
                 label="Net grid power (WITHOUT SC)", linewidth=1.5)
    axes[1].set_ylabel("Net grid power (kW)\n(+import / -export)")
    axes[1].set_xlabel("Seconds relative to worst event (16:00:00)")
    axes[1].legend()

    fig.tight_layout()
    plot_path = os.path.join(PLOTS_DIR, "Plot8_Ablation_Battery_Stress.png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"\nPlot saved -> {plot_path}")

    print("\nHow to read this: if the battery's power jump and ramp rate are "
          "similar with and without the SC, the battery was already fast "
          "enough to cover this event alone. If WITHOUT-SC shows a bigger, "
          "sharper jump in battery power, that is direct evidence the SC is "
          "reducing stress on the battery during real transients.")


if __name__ == "__main__":
    main()
