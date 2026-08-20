"""
run_simulation_1s.py
================================================================================
Main entry point for the 1-second-resolution HESS transient / supercapacitor
study.

HOW TO RUN:
    cd HESS_1s_Transient_Study
    python run_simulation_1s.py

Before running, make sure data/loads/ and data/solar/ contain your real
86,400-row 1-second CSV files (see README.md for the exact list and format).
If you don't have real data yet, run make_sample_1s_data.py first to generate
realistic synthetic test data so you can validate the whole pipeline.
================================================================================
"""
import os
import time
from config_1s import RESULTS_DIR
from data_loader_1s import load_all_data
from ems_controller_1s import EMSController1s


def main():
    print("=" * 70)
    print("  UNIVERSITY OF RUHUNA - FACULTY OF ENGINEERING")
    print("  HESS 1-Second Transient / Supercapacitor Study")
    print("=" * 70 + "\n")

    t0 = time.time()
    data = load_all_data()
    print(f"Data load time: {time.time() - t0:.2f}s\n")

    ems = EMSController1s(data["loads"], data["ev"], data["pv"])

    t0 = time.time()
    ems.run_all()
    elapsed = time.time() - t0
    print(f"\nSimulation loop time: {elapsed:.2f}s  ({elapsed / 86400 * 1000:.4f} ms/step)")

    ems.print_summary()

    ems.save_results(
        os.path.join(RESULTS_DIR, "EMS_1s_results.csv"),
        os.path.join(RESULTS_DIR, "EMS_1s_alerts.txt"),
    )
    print(f"\nResults saved -> {RESULTS_DIR}")
    print("Next: run generate_plots_1s.py to produce the transient/SC plots.")


if __name__ == "__main__":
    main()
