"""
generate_plots_1s.py
================================================================================
Generates thesis-ready plots from the 1-second EMS simulation results.
Run AFTER run_simulation_1s.py has produced results/EMS_1s_results.csv.

Plots produced:
  1. Full-day SC power + SOC              (shows overall SC utilisation pattern)
  2. Zoomed transient window (+-5 min)     (the key evidence plot: SC response
     around the single largest PV/load step change of the day)
  3. BESS vs SC response-speed comparison  (same window — shows SC absorbing
     the fast component while BESS handles the slow/sustained component)
  4. Full-day BESS vs Grid power           (context plot, for completeness)
================================================================================
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
from config_1s import RESULTS_DIR

RESULTS_CSV = os.path.join(RESULTS_DIR, "EMS_1s_results.csv")
PLOTS_DIR   = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)


def main():
    if not os.path.exists(RESULTS_CSV):
        raise FileNotFoundError(
            f"{RESULTS_CSV} not found. Run run_simulation_1s.py first."
        )
    df = pd.read_csv(RESULTS_CSV)
    t_hours = df["step"] / 3600.0

    # ── Plot 1: Full-day SC power and SOC ──────────────────────────────────
    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(t_hours, df["sc_kw"], color="tab:blue", linewidth=0.5)
    ax1.set_xlabel("Time (h)")
    ax1.set_ylabel("SC power (kW)", color="tab:blue")
    ax1.axhline(0, color="grey", linewidth=0.5)
    ax2 = ax1.twinx()
    ax2.plot(t_hours, df["soc_sc_pct"], color="tab:red", linewidth=0.8)
    ax2.set_ylabel("SC SOC (%)", color="tab:red")
    plt.title("Supercapacitor Power and SOC — Full Day (1-second resolution)")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "Plot1_SC_FullDay.png"), dpi=150)
    plt.close(fig)

    # ── Find the largest single-step transient (biggest PV or load jump) ──
    delta = (df["p_pv_kw"].diff().abs().fillna(0)
             + df["p_load_kw"].diff().abs().fillna(0)
             + df["p_ev_kw"].diff().abs().fillna(0))
    peak_step = int(delta.idxmax())
    lo, hi = max(0, peak_step - 300), min(len(df), peak_step + 300)
    window = df.iloc[lo:hi].copy()
    window["rel_s"] = window["step"] - peak_step

    # ── Plot 2: Zoomed transient window ────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(window["rel_s"], window["p_pv_kw"], label="PV (kW)")
    ax.plot(window["rel_s"], window["p_load_kw"], label="Load (kW)")
    ax.plot(window["rel_s"], window["p_ev_kw"], label="EV (kW)")
    ax.plot(window["rel_s"], window["sc_kw"], label="SC power (kW)")
    ax.plot(window["rel_s"], window["batt_kw"], label="BESS power (kW)")
    ax.set_xlabel("Seconds relative to largest transient")
    ax.set_ylabel("Power (kW)")
    ax.legend()
    plt.title("Transient Response Around Largest PV/Load Step Change")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "Plot2_Transient_Zoom.png"), dpi=150)
    plt.close(fig)

    # ── Plot 3: BESS vs SC response-speed comparison ──────────────────────
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(window["rel_s"], window["sc_kw"], label="SC (fast, sub-second/second scale)", linewidth=1.5)
    ax.plot(window["rel_s"], window["batt_kw"], label="BESS (slow, sustained)", linewidth=1.5)
    ax.set_xlabel("Seconds relative to largest transient")
    ax.set_ylabel("Power (kW)")
    ax.legend()
    plt.title("BESS vs Supercapacitor Response Speed Comparison")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "Plot3_BESS_vs_SC.png"), dpi=150)
    plt.close(fig)

    # ── Plot 4: Full-day BESS vs Grid power (context) ──────────────────────
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(t_hours, df["batt_kw"], label="BESS (kW)", linewidth=0.6)
    ax.plot(t_hours, df["grid_kw"], label="Grid import (kW)", linewidth=0.6)
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Power (kW)")
    ax.legend()
    plt.title("BESS and Grid Power — Full Day (1-second resolution)")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "Plot4_BESS_Grid_FullDay.png"), dpi=150)
    plt.close(fig)

    print(f"Plots saved -> {PLOTS_DIR}")
    ps = peak_step
    print(f"Largest transient found at step {ps} "
          f"({ps//3600:02d}:{(ps%3600)//60:02d}:{ps%60:02d})  "
          f"delta={delta.iloc[ps]:.1f} kW")


if __name__ == "__main__":
    main()
