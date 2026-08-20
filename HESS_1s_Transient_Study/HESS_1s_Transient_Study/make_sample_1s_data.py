"""
make_sample_1s_data.py
================================================================================
Generates 1-second load/PV/EV data from your real 96-step (15-min) thesis
profiles, using the noise-generation pipeline from the MATLAB
"High-Resolution Load Profile Generator" you uploaded — ported to Python in
noise_pipeline.py (PCHIP interpolation -> AR(1) correlated noise ->
Butterworth low-pass filter -> ramp-rate limiter -> mean-preserving
correction). Same algorithm, same default parameters as your uploaded main.m.

This REPLACES the earlier, simpler ripple/cloud-dip version of this script.
The output is no longer "generic synthetic" — it is your own real 96-step
building profiles (from reference_profiles_96.py, i.e. your thesis project's
load_profiles.py) expanded to 1-second resolution with realistic, physically
constrained, energy-conserving fluctuations.

Guarantee: mean-preserving correction forces each 900-second block's average
to exactly match your original 96-step kW value, so total daily energy
(kWh) for every file is identical to your original 15-min profiles to
floating-point precision — the noise only changes the SHAPE within each
15-minute block, never the energy total.

Run:
    python make_sample_1s_data.py
================================================================================
"""
import os
import numpy as np
import pandas as pd
from config_1s import LOADS_DIR, SOLAR_DIR, PV_TOTAL_KWP, BUILDINGS
import reference_profiles_96 as ref
from noise_pipeline import generate_1s_series, validation_report, DEFAULT_CFG

N_1S = 86400


def write_csv(path, arr):
    df = pd.DataFrame({"second": np.arange(len(arr)), "kW": np.round(arr, 4)})
    df.to_csv(path, index=False)


def report_line(name, power_96, series_1s):
    v = validation_report(power_96, series_1s)
    print(f"  {name:14s} peak={series_1s.max():7.2f} kW  mean={series_1s.mean():6.2f} kW  "
          f"energy_err={v['energy_error_pct']:.2e}%  max_ramp={v['max_ramp_kw_s']:.2f} kW/s")


# ── Building -> (real 96-step per-unit profile array, peak kW) ──────────────
# Same mapping as your main project's ems_controller.py _get_load_kw()
BUILDING_MAP = {
    "ElecDept":     (ref._LS_ELEC_DEPT,        33.33),
    "Workshop":     (ref._LS_WORKSHOP_REAL,     3.51),
    "Auditorium":   (ref._LS_TEACHING,         40.94),   # no dedicated real logger yet — assumed shape
    "Admin":        (ref._LS_TEACHING,         70.69),   # no dedicated real logger yet — assumed shape
    "CivilDept":    (ref._LS_CIVIL_REAL,       13.45),
    "MechDept":     (ref._LS_MECHDEPT_REAL,    13.45),
    "LecTheatre":   (ref._LS_LECTHEATRE_REAL,   8.15),
    "Library":      (ref._LS_LIBRARY_REAL,      9.12),
    "HostelD":      (ref._LS_HOSTELD_REAL,      9.44),
    "HostelC":      (ref._LS_HOSTELC_REAL,      9.44),
    "HostelBlock":  (ref._LS_HOSTELBLOCK_REAL,  5.52),
    "BoysHostelB":  (ref._LS_HOSTELB_REAL,      5.52),
    "HostelF":      (ref._LS_HOSTELF_REAL,      5.52),
    "LowerCanteen": (ref._LS_LOWERCANTEEN_REAL,12.65),
    "GuestHouse":   (ref._LS_GUESTHOUSE_REAL,   0.001),
    "UpperCanteen": (ref._LS_UPPERCANTEEN_REAL, 0.001),
    "Gym":          (ref._LS_GYM_REAL,          0.001),
}

# Real measured EV demand profile (96-step, from your main project's
# ems_controller.py _EV_PROFILE_KW) — peak 58.3 kW at 13:00-13:45.
# Extracted programmatically from the original source file (not hand-typed)
# to eliminate transcription-error risk.
_EV_PROFILE_KW = np.array([
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 14.2, 14.2, 14.2, 14.2,
    24.8, 24.8, 24.8, 24.8, 39.7, 39.7, 39.7, 39.7,
    53.7, 53.7, 53.7, 53.7, 58.3, 58.3, 58.3, 58.3,
    49.6, 49.6, 49.6, 49.6, 33.7, 33.7, 33.7, 33.7,
    17.0, 17.0, 17.0, 17.0, 8.1, 8.1, 8.1, 8.1,
    1.4, 1.4, 1.4, 1.4, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
])
assert len(_EV_PROFILE_KW) == 96, f"EV profile must have 96 entries, has {len(_EV_PROFILE_KW)}"


def main():
    print("=" * 70)
    print("  Generating 1-second data from real 96-step profiles")
    print("  Pipeline: PCHIP -> AR(1) noise -> Butterworth filter -> "
          "ramp limit -> mean-preserving correction")
    print(f"  Config: {DEFAULT_CFG}")
    print("=" * 70 + "\n")

    print("Buildings:")
    for i, name in enumerate(BUILDINGS):
        profile_96, peak = BUILDING_MAP[name]
        power_96 = np.asarray(profile_96, dtype=float) * peak
        series_1s = generate_1s_series(power_96, seed_offset=i)
        report_line(name, power_96, series_1s)
        write_csv(os.path.join(LOADS_DIR, f"{name}_1s.csv"), series_1s)

    print("\nEV station:")
    series_ev = generate_1s_series(_EV_PROFILE_KW, seed_offset=100)
    report_line("EV", _EV_PROFILE_KW, series_ev)
    write_csv(os.path.join(LOADS_DIR, "EV_1s.csv"), series_ev)

    print("\nSolar PV:")
    power_96_pv = np.asarray(ref._CLEAR_DAY_PU, dtype=float) * PV_TOTAL_KWP
    series_pv = generate_1s_series(power_96_pv, seed_offset=200)
    report_line("PV (total)", power_96_pv, series_pv)
    write_csv(os.path.join(SOLAR_DIR, "PV_1s.csv"), series_pv)

    print("\nDone. All files derived from your real 96-step thesis profiles, "
          "with energy totals preserved to floating-point precision.")
    print("NOTE: PV noise here uses the same generic AR(1) fluctuation model as "
          "the buildings. Real solar cloud transients are typically sharper, "
          "less-frequent step-changes rather than continuous ripple — if you "
          "want that specific behaviour for the supercapacitor study, say so "
          "and cloud-dip events can be layered on top of this PV file.")


if __name__ == "__main__":
    main()
