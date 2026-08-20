"""
run_simulation_both_1s.py
================================================================================
Generates TWO full 86,400-row result sheets from the same real data:
  1. results/EMS_1s_results.csv         — supercapacitor working normally
  2. results/EMS_1s_results_no_SC.csv   — supercapacitor completely disabled

Both files have the identical column structure (including the new p_net_kw
and v_mainbus_pu columns), so they can be directly compared row-by-row,
column-by-column, in Excel or any analysis tool — not just the summary
comparison already produced by run_ablation_1s.py.

Run:
    python run_simulation_both_1s.py
================================================================================
"""
import os
import time
from config_1s import RESULTS_DIR
from data_loader_1s import load_all_data
from ems_controller_1s import EMSController1s


def run_and_save(data, dispatch_mode, csv_name, alerts_name):
    print("\n" + "=" * 70)
    print(f"  RUNNING: {dispatch_mode.upper()}")
    print("=" * 70)
    ems = EMSController1s(data["loads"], data["ev"], data["pv"], dispatch_mode=dispatch_mode)

    t0 = time.time()
    ems.run_all()
    elapsed = time.time() - t0
    print(f"Simulation loop time: {elapsed:.2f}s")

    ems.print_summary()

    csv_path = os.path.join(RESULTS_DIR, csv_name)
    alerts_path = os.path.join(RESULTS_DIR, alerts_name)
    ems.save_results(csv_path, alerts_path)
    print(f"Saved -> {csv_path}")
    return ems


def main():
    print("=" * 70)
    print("  UNIVERSITY OF RUHUNA - FACULTY OF ENGINEERING")
    print("  HESS 1-Second Study — Full Result Sheets (WITH and WITHOUT SC)")
    print("=" * 70)

    data = load_all_data()

    # 1. WITH supercapacitor (the adopted filter-based control logic)
    run_and_save(data, "filter", "EMS_1s_results.csv", "EMS_1s_alerts.txt")

    # 2. WITHOUT supercapacitor (SC forced to 0 kW every step)
    run_and_save(data, "none", "EMS_1s_results_no_SC.csv", "EMS_1s_alerts_no_SC.txt")

    print("\n" + "=" * 70)
    print("  BOTH RESULT SHEETS GENERATED")
    print("=" * 70)
    print(f"  WITH supercapacitor    -> {os.path.join(RESULTS_DIR, 'EMS_1s_results.csv')}")
    print(f"  WITHOUT supercapacitor -> {os.path.join(RESULTS_DIR, 'EMS_1s_results_no_SC.csv')}")
    print("  Both files have identical columns, including the new:")
    print("    p_net_kw      — combined campus demand (load + EV - PV)")
    print("    v_mainbus_pu  — voltage at MainBus (the common coupling point")
    print("                    for both the battery and supercapacitor), in")
    print("                    per-unit (1.0 = nominal 415V)")


if __name__ == "__main__":
    main()
