"""
sc_sizing_analysis.py
================================================================================
STEP 1 of the supercapacitor sizing procedure: characterise real load/PV/EV
fluctuations at the point of connection (MainBus), from your 1-second data.

This does NOT use individual building files in isolation — it aggregates them
exactly the way your EMS does (P_net = sum(buildings) + EV - PV), because
uncorrelated building-level noise mostly cancels out on aggregation, while
correlated events (simultaneous EV charger switching, campus-wide cloud
transients) do not. Sizing off a single building's fluctuations would give
the wrong answer — see the aggregation discussion in your conversation with
Claude for why.

Produces:
  - Step-change (delta) distribution statistics for the aggregate P_net,
    plus for EV and PV individually (the two correlated drivers)
  - A ranked event table: every transient above a candidate threshold, with
    magnitude (dP), duration, and rate of change (dP/dt)
  - Candidate (Delta_P_design, dt_design) pairs for Step 2 of the sizing
    procedure, at several percentile levels
  - Plots: delta distribution histogram, and a zoom on the single worst event

Run AFTER run_simulation_1s.py or directly on data/loads + data/solar (works
either way — see USE_EMS_RESULTS below). Currently your building files are
still synthetic placeholders; re-run this unchanged once your teammate's
real 1-second data replaces them.

Run:
    python sc_sizing_analysis.py
================================================================================
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from config_1s import RESULTS_DIR
from data_loader_1s import load_all_data

PLOTS_DIR = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

# If True, reuse the aggregate load/EV/PV arrays already computed by a prior
# run_simulation_1s.py run (faster, and guarantees consistency with your EMS
# results). If False (or the file's missing), recomputes directly from the
# raw data/loads + data/solar files.
USE_EMS_RESULTS = True

# Candidate thresholds (kW) used to define "an event" for the ranked event
# table. Sweep several so you can see how the event count/severity trades
# off against threshold choice before picking a design value in Step 2.
CANDIDATE_THRESHOLDS_KW = [10, 20, 30, 50, 75, 100]


def load_aggregate_signals():
    ems_path = os.path.join(RESULTS_DIR, "EMS_1s_results.csv")
    if USE_EMS_RESULTS and os.path.exists(ems_path):
        print(f"Using aggregate signals from {ems_path}")
        df = pd.read_csv(ems_path)
        p_net = (df["p_load_kw"] + df["p_ev_kw"] - df["p_pv_kw"]).to_numpy()
        p_ev = df["p_ev_kw"].to_numpy()
        p_pv = df["p_pv_kw"].to_numpy()
        p_load = df["p_load_kw"].to_numpy()
        return p_net, p_load, p_ev, p_pv

    print("EMS_1s_results.csv not found (or USE_EMS_RESULTS=False) — "
          "recomputing aggregate directly from data/loads + data/solar.")
    data = load_all_data()
    p_load = np.sum(list(data["loads"].values()), axis=0)
    p_ev = data["ev"]
    p_pv = data["pv"]
    p_net = p_load + p_ev - p_pv
    return p_net, p_load, p_ev, p_pv


def delta_stats(signal, name):
    delta = np.abs(np.diff(signal))
    stats = {
        "signal": name,
        "mean_abs_delta_kw": delta.mean(),
        "p95_delta_kw": np.percentile(delta, 95),
        "p99_delta_kw": np.percentile(delta, 99),
        "p99_9_delta_kw": np.percentile(delta, 99.9),
        "max_delta_kw": delta.max(),
        "max_delta_at_step": int(np.argmax(delta)) + 1,
    }
    return stats, delta


def find_events(signal, delta, threshold_kw, merge_gap_s=5):
    """
    Identifies contiguous events where |delta| exceeds threshold_kw, merging
    events separated by less than merge_gap_s seconds (so one ramp doesn't
    get double-counted as many tiny sub-events).
    Returns a DataFrame: start_step, end_step, duration_s, peak_delta_kw,
    net_magnitude_kw (signal change from just before to just after).
    """
    above = delta > threshold_kw
    if not above.any():
        return pd.DataFrame(columns=[
            "start_step", "end_step", "duration_s", "peak_delta_kw", "magnitude_kw"
        ])

    idx = np.where(above)[0]
    # merge indices within merge_gap_s of each other
    groups = []
    current = [idx[0]]
    for i in idx[1:]:
        if i - current[-1] <= merge_gap_s:
            current.append(i)
        else:
            groups.append(current)
            current = [i]
    groups.append(current)

    rows = []
    for g in groups:
        start, end = g[0], g[-1] + 1
        pre = signal[max(0, start - 1)]
        post = signal[min(len(signal) - 1, end)]
        rows.append({
            "start_step": start,
            "end_step": end,
            "duration_s": end - start + 1,
            "peak_delta_kw": delta[g].max(),
            "magnitude_kw": abs(post - pre),
        })
    return pd.DataFrame(rows).sort_values("peak_delta_kw", ascending=False).reset_index(drop=True)


def main():
    p_net, p_load, p_ev, p_pv = load_aggregate_signals()
    n = len(p_net)
    print(f"\nLoaded {n} seconds of data.\n")

    # ── Delta distribution stats for each relevant signal ──────────────────
    all_stats = []
    signals = {"P_net (aggregate, at MainBus)": p_net, "EV station": p_ev, "PV (total)": p_pv}
    deltas = {}
    for name, sig in signals.items():
        stats, delta = delta_stats(sig, name)
        all_stats.append(stats)
        deltas[name] = delta

    stats_df = pd.DataFrame(all_stats)
    stats_path = os.path.join(RESULTS_DIR, "SC_sizing_delta_stats.csv")
    stats_df.to_csv(stats_path, index=False)
    print("=" * 70)
    print("  STEP-CHANGE (DELTA) DISTRIBUTION STATISTICS")
    print("=" * 70)
    print(stats_df.to_string(index=False))
    print(f"\nSaved -> {stats_path}")

    # ── Ranked event table (aggregate P_net) across candidate thresholds ──
    print("\n" + "=" * 70)
    print("  EVENT COUNTS AT CANDIDATE THRESHOLDS (aggregate P_net)")
    print("=" * 70)
    threshold_summary = []
    for thr in CANDIDATE_THRESHOLDS_KW:
        events = find_events(p_net, deltas["P_net (aggregate, at MainBus)"], thr)
        threshold_summary.append({
            "threshold_kw": thr,
            "n_events": len(events),
            "events_per_day": len(events),  # data is exactly 1 day
            "median_duration_s": events["duration_s"].median() if len(events) else np.nan,
            "max_magnitude_kw": events["magnitude_kw"].max() if len(events) else np.nan,
        })
    threshold_df = pd.DataFrame(threshold_summary)
    print(threshold_df.to_string(index=False))
    threshold_path = os.path.join(RESULTS_DIR, "SC_sizing_threshold_sweep.csv")
    threshold_df.to_csv(threshold_path, index=False)
    print(f"\nSaved -> {threshold_path}")

    # ── Full ranked event list at a sensible mid threshold (for inspection) ─
    mid_thr = CANDIDATE_THRESHOLDS_KW[len(CANDIDATE_THRESHOLDS_KW) // 2]
    events_full = find_events(p_net, deltas["P_net (aggregate, at MainBus)"], mid_thr)
    events_path = os.path.join(RESULTS_DIR, f"SC_sizing_events_thr{mid_thr}kW.csv")
    events_full.to_csv(events_path, index=False)
    print(f"\nFull ranked event list (threshold={mid_thr}kW) -> {events_path}")
    print(f"Top 5 events:\n{events_full.head().to_string(index=False)}")

    # ── Design candidates at a few percentile levels ────────────────────────
    print("\n" + "=" * 70)
    print("  CANDIDATE (Delta_P_design, dt_design) PAIRS FOR STEP 2")
    print("=" * 70)
    for pct, label in [(95, "p95"), (99, "p99"), (100, "max (worst observed)")]:
        dp = stats_df.loc[stats_df["signal"] == "P_net (aggregate, at MainBus)",
                           f"{label.split()[0]}_delta_kw" if label != "max (worst observed)"
                           else "max_delta_kw"].values
        dp = dp[0] if len(dp) else np.nan
        matching_events = find_events(p_net, deltas["P_net (aggregate, at MainBus)"],
                                       max(dp * 0.9, 1.0))
        med_dur = matching_events["duration_s"].median() if len(matching_events) else np.nan
        print(f"  {label:20s}: Delta_P_design = {dp:7.2f} kW   "
              f"typical event duration ~ {med_dur:.0f} s"
              if not np.isnan(med_dur) else
              f"  {label:20s}: Delta_P_design = {dp:7.2f} kW   (no matching events found)")

    # ── Plots ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(deltas["P_net (aggregate, at MainBus)"], bins=200, log=True)
    ax.set_xlabel("|Delta P| step-to-step (kW)")
    ax.set_ylabel("Count (log scale)")
    ax.set_title("Distribution of Second-to-Second Power Changes — Aggregate P_net at MainBus")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "Plot6_Delta_Distribution.png"), dpi=150)
    plt.close(fig)

    worst_step = int(np.argmax(deltas["P_net (aggregate, at MainBus)"])) + 1
    lo, hi = max(0, worst_step - 120), min(n, worst_step + 120)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(np.arange(lo, hi) - worst_step, p_net[lo:hi], label="P_net (aggregate)")
    ax.plot(np.arange(lo, hi) - worst_step, p_ev[lo:hi], label="EV", alpha=0.7)
    ax.plot(np.arange(lo, hi) - worst_step, p_pv[lo:hi], label="PV", alpha=0.7)
    ax.set_xlabel("Seconds relative to worst single-step event")
    ax.set_ylabel("Power (kW)")
    ax.legend()
    ax.set_title("Worst Single-Step Transient — Zoomed")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, "Plot7_Worst_Event_Zoom.png"), dpi=150)
    plt.close(fig)

    print(f"\nPlots saved -> {PLOTS_DIR}")


if __name__ == "__main__":
    main()
