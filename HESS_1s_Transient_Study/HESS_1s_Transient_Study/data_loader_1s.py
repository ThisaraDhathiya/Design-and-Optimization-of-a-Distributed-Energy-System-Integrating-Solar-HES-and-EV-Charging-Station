"""
data_loader_1s.py
================================================================================
Loads all 1-second CSV files into memory ONCE, before the simulation loop.

This is the single most important performance rule for an 86,400-step run:
NEVER read a file inside the per-second loop. Every load/PV/EV series is
read here as a numpy array and indexed by [step] afterwards — indexing a
numpy array is ~microseconds; re-opening a CSV per second would add hours.

Expected files (all must have exactly 86,400 rows):
    data/loads/<BuildingName>_1s.csv   (one per entry in config_1s.BUILDINGS)
    data/loads/EV_1s.csv               (EV charging station demand)
    data/solar/PV_1s.csv               (total campus PV generation, kW)

Each CSV needs a "kW" column (any other columns, e.g. "second"/"timestamp",
are ignored). If your column is named differently, the loader falls back to
the last column in the file.
================================================================================
"""
import os
import pandas as pd
from config_1s import LOADS_DIR, SOLAR_DIR, BUILDINGS, SIM_STEPS


def _load_series(path, expected_len=SIM_STEPS):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing file: {path}\n"
            f"Every building/EV/PV file must exist before running the simulation. "
            f"See README.md for the exact filenames expected."
        )
    df = pd.read_csv(path)
    col = "kW" if "kW" in df.columns else df.columns[-1]
    arr = df[col].to_numpy(dtype=float)
    if len(arr) != expected_len:
        raise ValueError(
            f"{os.path.basename(path)} has {len(arr)} rows, expected {expected_len}. "
            f"Every 1s file must cover exactly 24h = 86400 rows (one row per second)."
        )
    return arr


def load_all_data():
    """
    Returns
    -------
    dict with keys:
        'loads' : {building_name: np.array(86400)}   kW per second
        'ev'    : np.array(86400)                     EV station kW per second
        'pv'    : np.array(86400)                     total campus PV kW per second
    """
    print("Loading 1-second building load files...")
    loads = {}
    for name in BUILDINGS:
        path = os.path.join(LOADS_DIR, f"{name}_1s.csv")
        arr = _load_series(path)
        loads[name] = arr
        print(f"  {name:14s} peak={arr.max():7.2f} kW  mean={arr.mean():6.2f} kW")

    ev_path = os.path.join(LOADS_DIR, "EV_1s.csv")
    ev = _load_series(ev_path)
    print(f"  {'EV station':14s} peak={ev.max():7.2f} kW  mean={ev.mean():6.2f} kW")

    pv_path = os.path.join(SOLAR_DIR, "PV_1s.csv")
    pv = _load_series(pv_path)
    print(f"  {'PV (total)':14s} peak={pv.max():7.2f} kW  mean={pv.mean():6.2f} kW")

    total_mb = sum(a.nbytes for a in loads.values()) + ev.nbytes + pv.nbytes
    print(f"Total data in memory: {total_mb / 1e6:.1f} MB\n")

    return {"loads": loads, "ev": ev, "pv": pv}


if __name__ == "__main__":
    load_all_data()
